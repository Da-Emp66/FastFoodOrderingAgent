
import asyncio
import time
from typing import Any, Dict, Optional, Union
import cv2
import dspy
from pydantic import BaseModel

from core.utils import FINISH_TOKEN, from_config
from core.web.interface import BrowserVisibilityMode
from core.web.planning.interface import PlannerTypes
from core.web.planning.dspy_planner import DSPyPlanner, DSPyPlannerConfiguration
from core.web.tool_calling.interface import ToolModes
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller


class BrowserAgentConfiguration(BaseModel):
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None
    planner_type: PlannerTypes = PlannerTypes.DSPy
    planner: Union[Dict[str, Any]] = DSPyPlannerConfiguration()
    browser_visibility_mode: BrowserVisibilityMode = BrowserVisibilityMode.Default

class BrowserAgentSystem:
    def __init__(self, configuration: Union[BrowserAgentConfiguration, Any]):
        self.configuration: BrowserAgentConfiguration = from_config(configuration, BrowserAgentConfiguration)
        match self.configuration.planner_type:
            case PlannerTypes.DSPy: self.planner = DSPyPlanner(self.configuration.planner)
            case _: self.planner = None
        match self.configuration.tool_mode:
            case ToolModes.Code: self.tool_caller = CodeBrowserToolCaller(self.configuration.tools)
            case ToolModes.Constrained: self.tool_caller = ConstrainedBrowserToolCaller(self.configuration.tools)
            case ToolModes.DSPy: self.tool_caller = DSPyBrowserToolCaller(self.configuration.tools)
            case ToolModes.StageHand: self.tool_caller = StageHandBrowserToolCaller(self.configuration.tools)
            case _: self.tool_caller = None
        self.history = dspy.History(messages=[])
        self.screenshot = None
    
    def __call__(self, prompt: str):
        return asyncio.run(self.process_request(prompt))
    
    async def process_request(self, prompt: str, maximum_iterations: int = -1):

        #############################################
        # State Initialization
        #############################################

        overall_goal = prompt
        print(f"Goal: {overall_goal}")

        previous_browser_screenshot = None
        current_browser_screenshot = None
        current_browser_snapshot = "None"
        previous_subtask = "None"
        previous_tool_call = "None"
        previous_tool_call_output = "None"

        #############################################
        # Tool Initialization
        #############################################

        await self.tool_caller.initialize_tools()

        #############################################
        # Main Observation-Reasoning-Action Loop
        #############################################

        iteration = 0
        while maximum_iterations == -1 or iteration < maximum_iterations:

            ### Step 1: Determine sub-task

            if not self.planner.configuration.disable:
                subtask = await self.planner.infer_subtask(
                    overall_goal=overall_goal,
                    previous_subtask=previous_subtask,
                    previous_tool_call=previous_tool_call,
                    previous_tool_call_output=previous_tool_call_output,
                    previous_browser_screenshot=previous_browser_screenshot,
                    current_browser_screenshot=current_browser_screenshot,
                    current_browser_snapshot=current_browser_snapshot,
                    tool_caller=self.tool_caller,
                    history=self.history,
                )
            else:
                subtask = None

            # TODO: Finish should also account for if you have planner disabled
            if FINISH_TOKEN in subtask:
                break
            
            print(f"\nIteration {iteration}: Task: {subtask}")

            ### Step 2: Tool prediction

            # Take a screenshot of the browser before the tool call
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.tool_caller.screenshot()
            self.screenshot = current_browser_screenshot
            # current_browser_screenshot = cv2.resize(current_browser_screenshot, (300, 200))
            current_browser_screenshot = cv2.resize(current_browser_screenshot, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug: await self.show_browser(current_browser_screenshot)
            current_browser_snapshot = await self.tool_caller.take_snapshot()
            if current_browser_snapshot is not None: print(current_browser_snapshot)

            # Determine and call the tool
            tool_prediction_response, tool_call_result = await self.tool_caller.determine_and_call_tools(
                overall_goal=overall_goal,
                subtask=subtask,
                previous_browser_screenshot=previous_browser_screenshot,
                current_browser_screenshot=current_browser_screenshot,
                current_browser_snapshot=current_browser_snapshot,
            )
            previous_tool_call = tool_prediction_response
            previous_tool_call_output = tool_call_result
            print(tool_call_result)

            # Take a screenshot of the browser after the tool was called
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.tool_caller.screenshot()
            self.screenshot = current_browser_screenshot
            # current_browser_screenshot = cv2.resize(current_browser_screenshot, (300, 200))
            print(current_browser_screenshot.shape)
            current_browser_screenshot = cv2.resize(current_browser_screenshot, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug: await self.show_browser(current_browser_screenshot)
            current_browser_snapshot = await self.tool_caller.take_snapshot()

            # Append the current messages to the history
            self.history.messages.append({
                "overall_goal": overall_goal,
                "subtask": subtask,
                "tool_call": tool_prediction_response,
                "tool_call_result": tool_call_result,
            })
            previous_subtask = subtask

            # Increment the iteration
            iteration += 1

            # print(dspy.inspect_history())

        await self.close_tools()

        return tool_prediction_response

    async def show_browser(self, image: cv2.typing.MatLike):
        cv2.imshow('Browser Watcher', image)
        cv2.waitKey(1)
        time.sleep(0.2)
