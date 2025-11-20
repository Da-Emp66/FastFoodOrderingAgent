
import asyncio
import threading
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel
from core.web.tool_calling.interface import ToolModes
from core.utils import GeneratedTool, GeneratedToolSpec, from_config
from core.web.browser_utils import ScreenshotConfiguration, ScreenshotStrategy
from core.web.interface import BrowserVisibilityMode
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller

class WendysOrderArguments(BaseModel):
    resolved_food_item: Literal["Dave's Single"] # , "Big Bacon Classic", "Son of Baconator"
    zip_code: Optional[str] = None

class SimpleAPIConfiguration(BaseModel):
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None
    screenshot_call_configuration: ScreenshotConfiguration = ScreenshotConfiguration(strategy=ScreenshotStrategy.ExternalRepeated)
    browser_visibility_mode: BrowserVisibilityMode = BrowserVisibilityMode.Default

class SimpleAPI:
    def __init__(self, configuration: Dict[str, Any] = {}):
        self.configuration: SimpleAPIConfiguration = from_config(configuration, SimpleAPIConfiguration)
        match self.configuration.tool_mode:
            case ToolModes.Code: self.tool_caller = CodeBrowserToolCaller(self.configuration.tools)
            case ToolModes.Constrained: self.tool_caller = ConstrainedBrowserToolCaller(self.configuration.tools)
            case ToolModes.DSPy: self.tool_caller = DSPyBrowserToolCaller(self.configuration.tools)
            case ToolModes.StageHand: self.tool_caller = StageHandBrowserToolCaller(self.configuration.tools)
            case _: self.tool_caller = None

    async def __call__(self):
        if not self.tool_caller.initialized:
            await self.tool_caller.initialize_tools()
        await self.process_request()
            
    async def process_request(self):
        import shared
        print("In process_request", flush=True)
        if self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.ExternalRepeated:
            print("Starting continuous screenshot thread...", flush=True)
            self.screenshot_thread_stopped = False
            self.screenshot_thread = threading.Thread(target=self.run_screenshot_until_stopped_thread)
            self.screenshot_thread.start()
            print("Continuous screenshot thread started!", flush=True)

        # Constrained generate item, zip
        overall_goal = shared.this_session.current_spec.objective_spec.objective
        wendys_arguments: WendysOrderArguments = await self.tool_caller.extract_via_schema(
            prompt=overall_goal,
            schema_cls=WendysOrderArguments,
        )

        tool_name = "order_wendys_tool"
        usable = self.tool_caller.tools.get(tool_name, None)
        tool = GeneratedTool(
            usable=usable,
            spec=GeneratedToolSpec(
                tool=tool_name,
                args={
                    "official_food_item_name": wendys_arguments.resolved_food_item,
                    "zip_code": wendys_arguments.zip_code,
                },
            ),
        )
        result = await self.tool_caller.call_tool(tool)
        return result

    def run_screenshot_until_stopped_thread(self):
        return asyncio.run(self.screenshot_until_stopped())

    async def screenshot_until_stopped(self):
        print(f"In self.screenshot_until_stopped, {self.screenshot_thread_stopped}", flush=True)
        while not self.screenshot_thread_stopped:
            screenshot = await self.tool_caller.screenshot()
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug \
                and screenshot is not None:
                await self.show_browser(screenshot)
            await asyncio.sleep(self.configuration.screenshot_call_configuration.spec.get("delay_seconds", 0.1))
