

from itertools import chain
import os
import re
from typing import Any, Dict, Optional, Union

import PIL
import cv2
import dspy
from mcp import StdioServerParameters
from core.utils import DSPyToolCaller, GeneratedTool, MCPUserConfiguration, ToolReport, from_config
from core.web.interface import BrowserVisibilityConfiguration
from core.web.tool_calling.interface import FILEPATH_REGEX, BrowserToolCaller

class DSPyBrowserToolCallerConfiguration(MCPUserConfiguration):
    mcp_servers: Dict[str, StdioServerParameters] = {
        "playwright": {
            "command": "npx",
            "args": [
                "@playwright/mcp@latest",
                "--headless",
                "--caps=vision",
                # "--viewport-size 1280x720",
                # --config <file with something like https://github.com/microsoft/playwright-mcp/issues/1114#issuecomment-3378715243>
            ],
            "env": None,
        },
    }
    browser_visibility: BrowserVisibilityConfiguration = BrowserVisibilityConfiguration()

def dspy_image_or_blank(image: Optional[cv2.typing.MatLike]) -> dspy.Image:
    if image is None:
        return dspy.Image.from_PIL(PIL.Image.new("RGB", (256, 256), "black"))
    else:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = PIL.Image.fromarray(rgb_image)
        return dspy.Image.from_PIL(pil_image)
    
class DSPyBrowserToolCaller(DSPyToolCaller, BrowserToolCaller):
    class WebToolSelectionSignature(dspy.Signature):
        """You are an expert user of web-browsers who completes subtasks. Your current subtask is given in 'task'.
        Based on the tool you select to call in 'selected_tool_name' and 'selected_tool_args',
        you will perform that interaction with the browser. Use the 'current_browser_screenshot' to
        tell you where you are in the browser and what the state of the browser looks like.

        You should note that you can only do a single tool call at one time, so make sure the
        tool you are calling matches exactly your current 'task'.
        """
        overall_goal: str = dspy.InputField(desc="The over-arching complex task that the task is part of.")
        previous_browser_screenshot: dspy.Image = dspy.InputField(
            desc="Image of what the browser looked like last time, before the last interaction." \
            "(This can help tell you if the last call succeeded or not.) Blank if no previous interactions"
        )
        current_browser_screenshot: dspy.Image = dspy.InputField(
            desc="Image of what the browser currently looks like based on any previous interactions." \
            "Blank if no previous interactions"
        )
        current_browser_snapshot: str = dspy.InputField(
            desc="Snapshot containing refs to buttons and interactable divs in the current browser page"
        )
        task: str = dspy.InputField(
            desc="Current task to perform or target to achieve using any available tools."
        )
        tools: list[dspy.Tool] = dspy.InputField(
            desc="Available tools to select from"
        )

    def __init__(self, configuration: Union[Dict[str, Any], DSPyBrowserToolCallerConfiguration]):
        self.configuration: DSPyBrowserToolCallerConfiguration = from_config(configuration, DSPyBrowserToolCallerConfiguration)
        print("Instantiating DSPyBrowserToolCaller...")

    async def initialize_tools(self, tool_prediction_signature: Optional[type[dspy.Signature]]=None):
        return await super().initialize_tools(tool_prediction_signature or self.WebToolSelectionSignature)

    async def determine_tool(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None,
        banned_tools: Optional[str] = None,
    ) -> GeneratedTool:
        return await super().determine_tool(
            overall_goal=overall_goal,
            task=subtask,
            tools=list(self.tools.values()),
            current_browser_snapshot=current_browser_snapshot, # if visibility
            previous_browser_screenshot=dspy_image_or_blank(previous_browser_screenshot), # if visibility
            current_browser_screenshot=dspy_image_or_blank(current_browser_screenshot), # if visibility
            banned_tools=banned_tools,
        )
    
    async def determine_and_call_tools(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None
    ) -> ToolReport:
        return await super().determine_and_call_tools(
            overall_goal=overall_goal,
            task=subtask,
            tools=list(self.tools.values()),
            current_browser_snapshot=current_browser_snapshot, # if visibility
            previous_browser_screenshot=dspy_image_or_blank(previous_browser_screenshot), # if visibility
            current_browser_screenshot=dspy_image_or_blank(current_browser_screenshot), # if visibility
        )
    
    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        screenshot_tool = self.tools.get(self.configuration.browser_visibility.screenshot_tool_name, None)
        if screenshot_tool is not None:
            screenshot_text = await screenshot_tool.acall() # fullPage=True
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

    async def take_snapshot(self) -> Optional[str]:
        snapshot_tool = self.tools.get(self.configuration.browser_visibility.snapshot_tool_name, None)
        if snapshot_tool is not None:
            snapshot = await snapshot_tool.acall()
        else:
            snapshot = None
        return snapshot
