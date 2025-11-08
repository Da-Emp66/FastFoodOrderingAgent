
import math
from typing import Any, AsyncGenerator, Literal, Tuple, Union
import cv2
import dspy
from pydantic import BaseModel

from core.utils import from_config
from core.web.agent import BrowserAgentConfiguration, BrowserAgentSystem, IterativeTaskResult
from core.web.planning.dspy_planner import DSPyPlanner
from core.web.planning.interface import PlannerTypes
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.interface import ToolModes
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller


class TARSLikeBrowserAgentSystem(BrowserAgentSystem):
    IMAGE_FACTOR = 28
    MIN_PIXELS = 100 * 28 * 28
    MAX_PIXELS = 16384 * 28 * 28
    MAX_RATIO = 200

    VIDEO_MIN_PIXELS = 128 * 28 * 28
    VIDEO_MAX_PIXELS = 768 * 28 * 28
    FRAME_FACTOR = 2
    FPS = 2.0
    FPS_MIN_FRAMES = 4
    FPS_MAX_FRAMES = 768

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

    @classmethod
    def round_by_factor(cls, number: int, factor: int) -> int:
        """Returns the closest integer to 'number' that is divisible by 'factor'."""
        return round(number / factor) * factor

    @classmethod
    def ceil_by_factor(cls, number: int, factor: int) -> int:
        """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
        return math.ceil(number / factor) * factor

    @classmethod
    def floor_by_factor(cls, number: int, factor: int) -> int:
        """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
        return math.floor(number / factor) * factor

    @classmethod
    def smart_resize(
        cls,
        height: int,
        width: int,
        factor: int = IMAGE_FACTOR,
        min_pixels: int = MIN_PIXELS,
        max_pixels: int = MAX_PIXELS,
    ) -> Tuple[int, int]:
        """
        Rescales the image so that the following conditions are met:

        1. Both dimensions (height and width) are divisible by 'factor'.

        2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].

        3. The aspect ratio of the image is maintained as closely as possible.
        """
        if max(height, width) / min(height, width) > cls.MAX_RATIO:
            raise ValueError(
                f"absolute aspect ratio must be smaller than {cls.MAX_RATIO}, got {max(height, width) / min(height, width)}"
            )
        h_bar = max(factor, cls.round_by_factor(height, factor))
        w_bar = max(factor, cls.round_by_factor(width, factor))
        if h_bar * w_bar > max_pixels:
            beta = math.sqrt((height * width) / max_pixels)
            h_bar = cls.floor_by_factor(height / beta, factor)
            w_bar = cls.floor_by_factor(width / beta, factor)
        elif h_bar * w_bar < min_pixels:
            beta = math.sqrt(min_pixels / (height * width))
            h_bar = cls.ceil_by_factor(height * beta, factor)
            w_bar = cls.ceil_by_factor(width * beta, factor)
        return h_bar, w_bar

    @classmethod
    def calculate_coordinate(
        cls,
        original_image_height: int,
        original_image_width: int,
        model_output_height: int,
        model_output_width: int,
    ) -> Tuple[int, int]:
        new_height, new_width = cls.smart_resize(original_image_height, original_image_width)
        new_coordinate = (int(model_output_width/new_width * original_image_width), int(model_output_height/new_height * original_image_height))
        return new_coordinate

    # async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
    #     import shared
    #     print("Starting iterative task...", flush=True)

    #     complete = False
    #     iterations = 0
    #     # Vars
    #     previous_browser_screenshot = None
    #     current_browser_screenshot = None
    #     current_browser_snapshot = "None"
    #     previous_subtask = "None"
    #     previous_tool_call = "None"
    #     previous_tool_call_output = "None"
    #     # Init
    #     print("Initializing tools...", flush=True)
    #     await self.tool_caller.initialize_tools()
    #     print("Tools initialized successfully.", flush=True)

    #     while not complete and (shared.MAX_TASK_ITERATIONS == -1 or iterations < shared.MAX_TASK_ITERATIONS):
    #         overall_goal = shared.this_session.current_spec.objective_spec.objective
    #         print(f"Overall goal is currently: {overall_goal}", flush=True)
    #         ### Step 1: Determine sub-task
    #         if not self.planner.configuration.disable:
    #             print("Determining subtask...", flush=True)
    #             # response = litellm.completion(
    #             #     os.getenv("MODEL"),
    #             #     messages=[
    #             #         {"content": "You are a helpful assistant.", "role": "system"},
    #             #         {"content": "This is a test. Respond 'Test complete'", "role": "user"},
    #             #     ],
    #             #     api_key=os.getenv("OPENAI_API_KEY"),
    #             #     base_url=os.getenv("OPENAI_BASE_URL"),
    #             #     max_tokens=100, # self.configuration.response.max_tokens
    #             # ).choices[0].message.content
    #             # print(f"response >{response}<", flush=True)
                
    #             subtask = await self.planner.infer_subtask(
    #                 overall_goal=overall_goal,
    #                 previous_subtask=previous_subtask,
    #                 previous_tool_call=previous_tool_call,
    #                 previous_tool_call_output=previous_tool_call_output,
    #                 previous_browser_screenshot=previous_browser_screenshot,
    #                 current_browser_screenshot=current_browser_screenshot,
    #                 current_browser_snapshot=current_browser_snapshot,
    #                 tool_caller=self.tool_caller,
    #                 history=self.history,
    #             )
    #             yield Plan(plan=subtask)
    #             print(f"Successfully determined subtask. Current subtask is `{subtask}`", flush=True)
    #         else:
    #             subtask = None

    #         print("Taking pre-action browser screenshot...", flush=True)
    #         # Take a screenshot of the browser before the tool call
    #         previous_browser_screenshot = current_browser_screenshot
    #         current_browser_screenshot = await self.tool_caller.screenshot()
    #         self.screenshot = current_browser_screenshot
    #         if current_browser_screenshot is not None:
    #             print(current_browser_screenshot.shape, flush=True)
    #             current_browser_screenshot = cv2.resize(current_browser_screenshot, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
    #         if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug and current_browser_screenshot is not None: await self.show_browser(current_browser_screenshot)
    #         current_browser_snapshot = await self.tool_caller.take_snapshot()
    #         if current_browser_snapshot is not None: print(current_browser_snapshot, flush=True)
    #         print("Pre-action browser screenshot obtained.", flush=True)

    #         ### Step 2: Determine, process, and call the tool
    #         print("Determining tool to call...", flush=True)
    #         generated_tool = await self.tool_caller.determine_tool(
    #             overall_goal=overall_goal,
    #             subtask=subtask,
    #             previous_browser_screenshot=previous_browser_screenshot,
    #             current_browser_screenshot=current_browser_screenshot,
    #             current_browser_snapshot=current_browser_snapshot,
    #         )
    #         print(f"Tool to call determined to be: {generated_tool}", flush=True)

    #         ### TODO: PROCESS TRANSFORMS

    #         print(f"Calling generated tool...", flush=True)
    #         tool_prediction_response = generated_tool.spec.model_dump_json()
    #         tool_call_result = await self.tool_caller.call_tool(generated_tool)
    #         previous_tool_call = tool_prediction_response
    #         previous_tool_call_output = tool_call_result
    #         print(tool_call_result, flush=True)
    #         yield ToolReport(
    #             generated_tool=generated_tool,
    #             result=tool_call_result,
    #         )
    #         print(f"Generated tool called. Tool report result: {tool_call_result}", flush=True)

    #         # Take a screenshot of the browser after the tool was called
    #         print("Taking post-action browser screenshot...", flush=True)
    #         previous_browser_screenshot = current_browser_screenshot
    #         current_browser_screenshot = await self.tool_caller.screenshot()
    #         self.screenshot = current_browser_screenshot
    #         if current_browser_screenshot is not None:
    #             print(current_browser_screenshot.shape, flush=True)
    #             current_browser_screenshot = cv2.resize(current_browser_screenshot, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
    #         if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug and current_browser_screenshot is not None: await self.show_browser(current_browser_screenshot)
    #         current_browser_snapshot = await self.tool_caller.take_snapshot()
    #         print("Post-action browser screenshot obtained.", flush=True)

    #         # Append the current messages to the history
    #         print("Updating current history...", flush=True)
    #         self.history.messages.append({
    #             "overall_goal": overall_goal,
    #             "subtask": subtask,
    #             "tool_call": tool_prediction_response,
    #             "tool_call_result": tool_call_result,
    #         })
    #         previous_subtask = subtask
    #         print("History updated.", flush=True)

    #         iterations += 1
