import base64
import enum
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Union
import cv2
import dspy
import numpy as np
from pydantic import BaseModel, ConfigDict
import requests

from core.utils import FINISH_TOKEN, BaseModelJSONEncoder, ToolReport, from_config
from core.web.interface import BrowserVisibilityMode
from core.web.planning.interface import PlannerTypes
from core.web.planning.dspy_planner import DSPyPlanner, DSPyPlannerConfiguration
from core.web.tool_calling.interface import ToolModes
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller

class Plan(BaseModel):
    plan: str

IterativeTaskResult = Union[Plan, ToolReport, Literal['<|COMPLETED_OVERALL_TASK|>']]

class ParsedItemDetails(BaseModel):
    type: str
    bbox: List[float]
    """xyxy relative coordinates of each box."""
    interactivity: bool
    content: Optional[str] = None
    source: str

    model_config = ConfigDict(extra="allow")

class ParserDetails(BaseModel):
    som_image_base64: str
    parsed_content_list: List[ParsedItemDetails]
    """Order matters. Index `0` corresponds to box `0` in the labeled `som_image_base64`, and so forth."""
    latency: float

    def matlike_image(self):
        image_data = base64.b64decode(self.som_image_base64)
        np_array = np.frombuffer(image_data, np.uint8)
        return cv2.imdecode(np_array, cv2.IMREAD_COLOR)

class ParserMode(str, enum.Enum):
    Enabled = "enabled"
    Disabled = "disabled"

class ParserConfiguration(BaseModel):
    parser_mode: ParserMode = os.getenv("PARSER_MODE", ParserMode.Enabled)
    parser_uri: str = "http://" + os.getenv("PARSER_HOST", "localhost") + ":" + os.getenv("PARSER_PORT", "8055")

class BrowserAgentConfiguration(BaseModel):
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None
    planner_type: PlannerTypes = PlannerTypes.DSPy
    planner: Union[Dict[str, Any]] = DSPyPlannerConfiguration()
    browser_visibility_mode: BrowserVisibilityMode = BrowserVisibilityMode.Default
    parser: ParserConfiguration = ParserConfiguration()

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
    
    async def __call__(self):
        return await self.process_request()
    
    async def process_request(self):
        print("In call", flush=True)
        async for task_result in self.iterate_task():
            print("iteration", flush=True)
            if task_result == FINISH_TOKEN:
                print(FINISH_TOKEN)
                return
            else:
                print(task_result)

    async def show_browser(self, image: cv2.typing.MatLike):
        cv2.imshow('Browser Watcher', image)
        cv2.waitKey(1)
        time.sleep(0.2)

    async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
        import shared
        print("Starting iterative task...", flush=True)

        #############################################
        # State Initialization
        #############################################

        complete = False
        iterations = 0
        # Vars
        previous_browser_screenshot = None
        current_browser_screenshot = None
        current_browser_snapshot = "None"
        previous_subtask = "None"
        previous_tool_call = "None"
        previous_tool_call_output = "None"

        #############################################
        # Tool Initialization
        #############################################

        print("Initializing tools...", flush=True)
        await self.tool_caller.initialize_tools()
        print("Tools initialized successfully.", flush=True)

        #############################################
        # Main Observation-Reasoning-Action Loop
        #############################################

        while not complete and (shared.MAX_TASK_ITERATIONS == -1 or iterations < shared.MAX_TASK_ITERATIONS):
            overall_goal = shared.this_session.current_spec.objective_spec.objective
            print(f"Overall goal is currently: {overall_goal}", flush=True)
            ### Step 1: Determine sub-task
            if not self.planner.configuration.disable:
                print("Determining subtask...", flush=True)
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
                yield Plan(plan=subtask)
                print(f"Successfully determined subtask. Current subtask is `{subtask}`", flush=True)
            else:
                subtask = None

            print("Taking pre-action browser screenshot...", flush=True)
            # Take a screenshot of the browser before the tool call
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.tool_caller.screenshot()
            self.screenshot = current_browser_screenshot
            if current_browser_screenshot is not None:
                print(current_browser_screenshot.shape, flush=True)
                if self.configuration.parser.parser_mode == ParserMode.Enabled:
                    print("Parsing details...")
                    parsed_details = self.parse_details(current_browser_screenshot)
                    if parsed_details is not None:
                        open(shared.CURRENT_IMAGE_PARSE_METADATA_PATH, 'w').write(json.dumps(parsed_details.parsed_content_list, cls=BaseModelJSONEncoder))
                        parsed_image = parsed_details.matlike_image()
                        current_browser_screenshot = parsed_image
                        print(f"Parsing took {parsed_details.latency} seconds")
                    else:
                        print("Parsing failed. See server logs for more details.")
                print(current_browser_screenshot.shape, flush=True)
                current_browser_screenshot = cv2.resize(current_browser_screenshot, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug and current_browser_screenshot is not None: await self.show_browser(current_browser_screenshot)
            current_browser_snapshot = await self.tool_caller.take_snapshot()
            if current_browser_snapshot is not None: print(current_browser_snapshot, flush=True)
            print("Pre-action browser screenshot obtained.", flush=True)

            ### Step 2: Determine, process, and call the tool
            print("Determining tool to call...", flush=True)
            generated_tool = await self.tool_caller.determine_tool(
                overall_goal=overall_goal,
                subtask=subtask,
                previous_browser_screenshot=previous_browser_screenshot,
                current_browser_screenshot=current_browser_screenshot,
                current_browser_snapshot=current_browser_snapshot,
            )
            print(f"Tool to call determined to be: {generated_tool}", flush=True)

            ### TODO: PROCESS TRANSFORMS

            print(f"Calling generated tool...", flush=True)
            tool_prediction_response = generated_tool.spec.model_dump_json()
            tool_call_result = await self.tool_caller.call_tool(generated_tool)
            previous_tool_call = tool_prediction_response
            previous_tool_call_output = tool_call_result
            print(tool_call_result, flush=True)
            yield ToolReport(
                generated_tool=generated_tool,
                result=tool_call_result,
            )
            print(f"Generated tool called. Tool report result: {tool_call_result}", flush=True)

            # Take a screenshot of the browser after the tool was called
            print("Taking post-action browser screenshot...", flush=True)
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.tool_caller.screenshot()
            self.screenshot = current_browser_screenshot
            if current_browser_screenshot is not None:
                print(current_browser_screenshot.shape, flush=True)
                if self.configuration.parser.parser_mode == ParserMode.Enabled:
                    print("Parsing details...")
                    parsed_details = self.parse_details(current_browser_screenshot)
                    if parsed_details is not None:
                        open(shared.CURRENT_IMAGE_PARSE_METADATA_PATH, 'w').write(json.dumps(parsed_details.parsed_content_list, cls=BaseModelJSONEncoder))
                        parsed_image = parsed_details.matlike_image()
                        current_browser_screenshot = parsed_image
                        print(f"Parsing took {parsed_details.latency} seconds")
                    else:
                        print("Parsing failed. See server logs for more details.")
                print(current_browser_screenshot.shape, flush=True)
                current_browser_screenshot = cv2.resize(current_browser_screenshot, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug and current_browser_screenshot is not None: await self.show_browser(current_browser_screenshot)
            current_browser_snapshot = await self.tool_caller.take_snapshot()
            print("Post-action browser screenshot obtained.", flush=True)

            # Append the current messages to the history
            print("Updating current history...", flush=True)
            self.history.messages.append({
                "overall_goal": overall_goal,
                "subtask": subtask,
                "tool_call": tool_prediction_response,
                "tool_call_result": tool_call_result,
            })
            previous_subtask = subtask
            print("History updated.", flush=True)

            iterations += 1

        await self.close_tools()
        yield FINISH_TOKEN

    def parse_details(self, image: cv2.typing.MatLike) -> Optional[ParserDetails]:
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        # For now, just make the request twice because the image never comes back the first time.
        # We probably need to investigate that and fix that in the omni parser fork itself, but
        # that might take too much time.
        response = requests.post(f"{self.configuration.parser.parser_uri}/parse", data=json.dumps({"base64_image": image_base64}))
        # response = requests.post("http://localhost:8055/parse", data=json.dumps({"base64_image": image_base64}))
        try:
            response = response.json()
        except Exception as e:
            print(e)
            return None
        return ParserDetails.model_validate(response)
