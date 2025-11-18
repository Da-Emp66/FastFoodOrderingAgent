from itertools import chain
import json
from typing import Any, Dict, List, Optional, Union
import cv2
import dspy
import litellm
from openai import OpenAI
import yaml

from core.web.planning.interface import BrowserActionPlanner, PlannerConfiguration
from core.utils import FINISH_TOKEN, History, cv2_image_to_base64, from_config, present_or_black
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.interface import BrowserToolCaller


class GeneralPlanner(BrowserActionPlanner):
    def __init__(self, configuration: Union[Dict[str, Any], PlannerConfiguration]):
        print("Instantiating GeneralPlanner...")
        self.configuration: PlannerConfiguration = from_config(configuration, PlannerConfiguration)
        self.client = OpenAI(
            base_url="http://localhost:8000",
            api_key="sk-1234",
        )

    async def infer_subtask(
        self,
        overall_goal: str,
        previous_subtask: str,
        previous_tool_call: str,
        previous_tool_call_output: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None,
        tool_caller: Optional[BrowserToolCaller] = None,
        history: Optional[Union[History, dspy.History]] = None,
    ) -> str:
        tools = None if isinstance(tool_caller, DSPyBrowserToolCaller) else list(tool_caller.tools.keys())
        file_type = 'png'
        response = self.client.chat.completions.create(
            model="openai/models/ggml-model-Q4_K_M.gguf",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.configuration.prompt_template \
                                        .replace("{overall_goal}", overall_goal) \
                                        .replace("{tool_options}", yaml.safe_dump(tools)) \
                                        # .replace("{banned_tools}", str(banned_tools))
                        },
                        {
                            "type": "text",
                            "text": "\nHistory of previous actions:\n"
                        },
                    ] + self.format_history(history, file_type) + [
                        {
                            "type": "text",
                            "text": "\nPrevious Browser:\n"
                        },
                        self.openai_spec_image_or_none_text(previous_browser_screenshot, file_type),
                        {
                            "type": "text",
                            "text": f"""\nPrevious tool call:\n{json.dumps({
                                'overall_goal': overall_goal,
                                'subtask': previous_subtask,
                                'tool_call': previous_tool_call,
                                'tool_call_result': previous_tool_call_output,
                            }, indent=2)}""",
                        },
                        {
                            "type": "text",
                            "text": "\nCurrent Browser:\n"
                        },
                        self.openai_spec_image_or_none_text(current_browser_screenshot, file_type),
                    ]
                },
            ],
            stream=True,
        )
        text_response = ""
        for chunk in response:
            if len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                text_response += text
        print()
        return text_response

    def format_history(self, history: History, image_file_type: str) -> List[Dict[str, Any]]:
        if len(history.messages) == 0: return []
        if history.messages[0].get("screenshot_with_bounding_boxes", None) is not None:
            return list(chain([[
                {
                    "type": "text",
                    "text": f"\nMost recent - {n + 1} browser image:\n"
                },
                self.openai_spec_image_or_none_text(history_message.get('screenshot_with_bounding_boxes'), image_file_type),
                {
                    "type": "text",
                    "text": f"""\nMost recent - {n + 1} tool call:\n{json.dumps({
                        'overall_goal': history_message.get('overall_goal'),
                        'subtask': history_message.get('subtask'),
                        'tool_call': history_message.get('tool_call'),
                        'tool_call_result': history_message.get('tool_call_result'),
                    }, indent=2)}""",
                },
            ] for n, history_message in enumerate(history.messages[::-1])]))
        else:
            return [
                {
                    "type": "text",
                    "text": f"""\nMost recent - {n + 1} Tool call:\n{json.dumps({
                        'overall_goal': history_message.get('overall_goal'),
                        'subtask': history_message.get('subtask'),
                        'tool_call': history_message.get('tool_call'),
                        'tool_call_result': history_message.get('tool_call_result'),
                    }, indent=2)}""",
                } for n, history_message in enumerate(history.messages[::-1])
            ]

    def openai_spec_image_or_none_text(self, image: Optional[cv2.typing.MatLike], file_type='png'):
        if image is None:
            return {
                "type": "text",
                "text": "None"
            }
        else:
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{file_type};base64,{cv2_image_to_base64(image, f'.{file_type}')}"
                }
            }
