import asyncio
import json
import os
import threading
import time
from typing import Any, AsyncGenerator, Dict, Optional, Union
from browser_use import Agent, Browser, BrowserProfile, ChatBrowserUse

from pydantic import BaseModel

from core.utils import from_config, FINISH_TOKEN
from core.web.agent_interface import IterativeTaskResult
from core.web.tool_calling.interface import ToolModes
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller
from core.web.browser_utils import ScreenshotConfiguration, ScreenshotStrategy
from core.web.interface import BrowserVisibilityMode

BROWSER_GEOLOCATION = json.loads(os.getenv("BROWSER_GEOLOCATION", '''{
    "latitude": 28.5383,
    "longitude": -81.3792,
    "accuracy": 100
}'''))

class SimpleBrowserAgentConfiguration(BaseModel):
    task_prompt_template: str
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None
    screenshot_call_configuration: ScreenshotConfiguration = ScreenshotConfiguration(strategy=ScreenshotStrategy.ExternalRepeated)
    browser_visibility_mode: BrowserVisibilityMode = BrowserVisibilityMode.Default

class SimpleBrowserAgent:
    def __init__(self, configuration: Union[SimpleBrowserAgentConfiguration, Any]):
        self.configuration: SimpleBrowserAgentConfiguration = from_config(configuration, SimpleBrowserAgentConfiguration)
        match self.configuration.tool_mode:
            case ToolModes.Code: self.tool_caller = CodeBrowserToolCaller(self.configuration.tools)
            case ToolModes.Constrained: self.tool_caller = ConstrainedBrowserToolCaller(self.configuration.tools)
            case ToolModes.DSPy: self.tool_caller = DSPyBrowserToolCaller(self.configuration.tools)
            case ToolModes.StageHand: self.tool_caller = StageHandBrowserToolCaller(self.configuration.tools)
            case _: self.tool_caller = None
        self.browser = None
        self.llm = None

    async def __call__(self):
        if not self.tool_caller.initialized:
            await self.tool_caller.initialize_tools()
        if self.browser is None:
            # self.browser = Browser(headless=False)
            self.browser = Browser(browser_profile=BrowserProfile(
                disable_security=True,
                user_data_dir=None,
                headless=False,
                chromium_sandbox=False,
                args=["--disable-gpu"],
            ))
            # context = self.browser._context  # (or another way to access Playwright context)
            # await context.set_geolocation(BROWSER_GEOLOCATION)
        if self.llm is None:
            self.llm = ChatBrowserUse()
        return await self.process_request()
    
    async def process_request(self):
        print("In process_request", flush=True)
        if self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.ExternalRepeated:
            print("Starting continuous screenshot thread...", flush=True)
            self.screenshot_thread_stopped = False
            self.screenshot_thread = threading.Thread(target=self.run_screenshot_until_stopped_thread)
            self.screenshot_thread.start()
            print("Continuous screenshot thread started!", flush=True)
        async for task_result in self.iterate_task():
            print("Iteration complete.", flush=True)
            if task_result == FINISH_TOKEN:
                print(f"Received finish token: {FINISH_TOKEN}")

                if self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.ExternalRepeated:
                    self.screenshot_thread_stopped = True
                    print("Waiting for screenshot thread to stop...")
                    self.screenshot_thread.join()
                    print("Screenshot thread joined. Request processed.")
                return
            else:
                print(f"Task result: {task_result}")

    def run_screenshot_until_stopped_thread(self):
        return asyncio.run(self.screenshot_until_stopped())

    async def screenshot_until_stopped(self):
        print(f"In self.screenshot_until_stopped, {self.screenshot_thread_stopped}", flush=True)
        while not self.screenshot_thread_stopped:
            screenshot = await self.tool_caller.screenshot()
            # print("Screenshot taken!", flush=True)
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug \
                and screenshot is not None:
                await self.show_browser(screenshot)
            await asyncio.sleep(self.configuration.screenshot_call_configuration.spec.get("delay_seconds", 0.1))

    async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
        import shared
        overall_goal = shared.this_session.current_spec.objective_spec.objective
        print(f"Overall goal is currently: {overall_goal}", flush=True)

        task = self.configuration.task_prompt_template.replace("{overall_goal}", overall_goal)
        self.agent = Agent(
            task=task,
            llm=self.llm,
            browser=self.browser,
        )
        yield await self.agent.run()
