
import asyncio
from itertools import chain
import json
import os
import re
import traceback
from typing import Any, Dict, Optional, Union

import cv2
from guidance import (
    image as guidance_image,
    json as generate_constrained_json,
    user as guidance_user,
    assistant as guidance_assistant,
)
import yaml
from core.utils import (
    ConstrainedToolCaller,
    ConstrainedToolCallerConfiguration,
    GeneratedTool,
    GeneratedToolSpec,
    from_config,
)
from core.web.interface import BrowserVisibilityConfiguration
from core.web.tool_calling.interface import FILEPATH_REGEX, BrowserToolCaller

class ConstrainedBrowserToolCallerConfiguration(ConstrainedToolCallerConfiguration):
    browser_visibility: BrowserVisibilityConfiguration = BrowserVisibilityConfiguration()
    tool_specific_prompt_additions: Dict[str, str] = {}

class ConstrainedBrowserToolCaller(ConstrainedToolCaller, BrowserToolCaller):
    def __init__(self, configuration: Union[Dict[str, Any], ConstrainedBrowserToolCallerConfiguration]):
        self.configuration: ConstrainedBrowserToolCallerConfiguration = from_config(configuration, ConstrainedBrowserToolCallerConfiguration)
        print("Instantiating ConstrainedBrowserToolCaller...")
        super().__init__(self.configuration)

    async def determine_tool(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None,
        banned_tools: Optional[str] = None,
        skip_args: bool = False,
    ) -> GeneratedTool:
        success = False
        while not success:
            try:
                tool_options = list(self.tools.keys())
                if current_browser_screenshot is not None:
                    print("Writing current_browser_screenshot to tmp.jpg...")
                    cv2.imwrite("tmp.jpg", current_browser_screenshot)
                    print("Done writing current_browser_screenshot.")
                with guidance_user():
                    if current_browser_screenshot is not None:
                        self.lm += guidance_image("tmp.jpg") + \
                            self.configuration.tool_selection_user_prompt_format \
                                .replace("{overall_goal}", overall_goal) \
                                .replace("{subtask}", str(subtask)) \
                                .replace("{tool_options}", yaml.safe_dump(tool_options)) \
                                .replace("{banned_tools}", str(banned_tools))
                    else:
                        self.lm += self.configuration.tool_selection_user_prompt_format \
                                .replace("{overall_goal}", overall_goal) \
                                .replace("{subtask}", str(subtask)) \
                                .replace("{tool_options}", yaml.safe_dump(tool_options)) \
                                .replace("{banned_tools}", str(banned_tools))
                name = None
                with guidance_assistant():
                    self.lm += generate_constrained_json(
                        name='tool_name_json',
                        schema={
                            'properties': {
                                'tool_name': {
                                    'enum': tool_options,
                                    'title': 'Tool Name',
                                    'type': 'string'
                                }
                            },
                            'required': ['tool_name'],
                            'title': 'ToolName',
                            'type': 'object',
                        },
                        temperature=self.configuration.tool_generation_params.temperature,
                        # logit_bias=logit_bias,
                    )
                    name = json.loads(self.lm["tool_name_json"])["tool_name"]
                    if skip_args and name in self.tools:
                        return GeneratedTool(usable=self.tools[name], spec=GeneratedToolSpec(tool=name, args={}))

                tool_args_prompt = (self.configuration.tool_args_user_prompt_format + \
                    self.configuration.tool_specific_prompt_additions.get(name, "")) \
                    .replace("{overall_goal}", overall_goal) \
                    .replace("{subtask}", str(subtask)) \
                    .replace("{name}", name) \
                    .replace("{banned_tools}", str(banned_tools))
                
                with guidance_user():
                    self.lm += tool_args_prompt
                with guidance_assistant():
                    if name in self.tools:
                        selected_tool = self.tools[name]
                        print(selected_tool.tool.inputSchema)
                        self.lm += generate_constrained_json(
                            name="generated_args",
                            schema=selected_tool.tool.inputSchema,
                            temperature=self.configuration.tool_generation_params.temperature,
                        )
                        args = json.loads(self.lm["generated_args"])
                        selected_tool_representation = str({"tool": name, "args": args})
                        print(selected_tool_representation)
                    else:
                        raise ValueError(f"Tool {name} is not valid. Please select from the list of valid tools: {list(self.tools.keys())}")
                    
                    success = True
                    return GeneratedTool(
                        usable=selected_tool,
                        spec=GeneratedToolSpec(
                            tool=name,
                            args=args,
                        )
                    )
            except Exception as e:
                print(traceback.format_exc())
                print(f"Encountered exception when determining tool for constrained generation: {str(e)}")
                print("Retrying in 5 seconds...")
                asyncio.sleep(5)
                print("Retrying...")
    
    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        screenshot_tool = self.tools.get(self.configuration.browser_visibility.screenshot_tool_name, None)
        if screenshot_tool is not None:
            screenshot_text = await screenshot_tool()
            screenshot_filepath = next(chain(re.findall(FILEPATH_REGEX, screenshot_text), [None]))
            if screenshot_filepath is None:
                return None
            image = cv2.imread(screenshot_filepath)
            if screenshot_filepath != os.getenv("CURRENT_SCREENSHOT_PATH", None) and \
                os.path.exists(screenshot_filepath) and \
                os.path.isfile(screenshot_filepath) and \
                os.path.splitext(screenshot_filepath)[-1] in ["jpg", "jpeg", "png"]:
                    os.remove(screenshot_filepath)
        else:
            image = None
        return image
