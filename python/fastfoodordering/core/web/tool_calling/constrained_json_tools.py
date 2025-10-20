
from itertools import chain
import json
import os
import re
from typing import Any, Dict, Optional, Union

import cv2
from guidance import (
    image as guidance_image,
    json as generate_constrained_json,
    system as guidance_system,
    user as guidance_user,
    assistant as guidance_assistant,
)
from guidance.models import OpenAI as GuidanceOpenAI
from core.utils import ConstrainedToolCaller, MCPUserConfiguration, from_config
from core.web.interface import BrowserVisibilityConfiguration
from core.web.tool_calling.interface import FILEPATH_REGEX, BrowserToolCaller


class ConstrainedBrowserToolCallerConfiguration(MCPUserConfiguration):
    system_prompt: str = "Your goal is to select the best tool to select the best tool for the user based on the current task."
    tool_selection_user_prompt_format: str = "Overall Goal: {overall_goal}\nCurrent Task: {subtask}\n\nNotes: If asked to go to a url, use 'navigate', not a 'click' tool."
    tool_args_user_prompt_format: str = "Overall Goal: {overall_goal}\nCurrent Task: {subtask}\n\nSelected tool is {name}. Now determine the arguments:"
    browser_visibility: BrowserVisibilityConfiguration = BrowserVisibilityConfiguration()

class ConstrainedBrowserToolCaller(ConstrainedToolCaller, BrowserToolCaller):
    def __init__(self, configuration: Union[Dict[str, Any], ConstrainedBrowserToolCallerConfiguration]):
        self.configuration: ConstrainedBrowserToolCallerConfiguration = from_config(configuration, ConstrainedBrowserToolCallerConfiguration)
        self.tools = {}
        self.lm = GuidanceOpenAI(
            "o1-" + os.getenv("MODEL"),
            echo=True,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        with guidance_system():
            self.lm += self.configuration.system_prompt

    async def determine_and_call_tools(
        self,
        overall_goal,
        subtask,
        previous_browser_screenshot = None,
        current_browser_screenshot = None,
        current_browser_snapshot = None
    ):
        cv2.imwrite("tmp.jpg", current_browser_screenshot)
        with guidance_user():
            self.lm += guidance_image("tmp.jpg") + self.configuration.tool_selection_user_prompt_format.replace("{overall_goal}", overall_goal).replace("{subtask}", subtask)
        name = None
        with guidance_assistant():
            self.lm += generate_constrained_json(name='tool_name_json', schema={
                'properties': {
                    'tool_name': {
                        'enum': list(self.tools.keys()),
                        'title': 'Tool Name',
                        'type': 'string'
                    }
                },
                'required': ['tool_name'],
                'title': 'ToolName',
                'type': 'object',
            })
            name = json.loads(self.lm["tool_name_json"])["tool_name"]
        with guidance_user():
            self.lm += self.configuration.tool_args_user_prompt_format.replace("{overall_goal}", overall_goal).replace("{subtask}", subtask).replace("{name}", name)
        with guidance_assistant():
            if name in self.tools:
                selected_tool = self.tools[name]
                print(selected_tool.tool.inputSchema)
                self.lm += generate_constrained_json(name="generated_args", schema=selected_tool.tool.inputSchema)
                args = json.loads(self.lm["generated_args"])
                selected_tool_representation = str({"tool": name, "args": args})
                print(selected_tool_representation)
                try:
                    result = await selected_tool(**args)
                    return selected_tool_representation, result
                except Exception as e:
                    return selected_tool_representation, str(e)
            else:
                return str({"tool": name, "args": {}}), f"Tool {name} is not valid. Please select from the list of valid tools: {list(self.tools.keys())}"
    
    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        screenshot_tool = self.tools.get(self.configuration.browser_visibility.screenshot_tool_name, None)
        if screenshot_tool is not None:
            screenshot_text = await screenshot_tool()
            screenshot_filepath = next(chain(re.findall(FILEPATH_REGEX, screenshot_text), [None]))
            image = cv2.imread(screenshot_filepath)
            if os.path.exists(screenshot_filepath) and \
                os.path.isfile(screenshot_filepath) and \
                os.path.splitext(screenshot_filepath)[-1] in ["jpg", "jpeg", "png"]:
                    os.remove(screenshot_filepath)
        else:
            image = None
        return image
