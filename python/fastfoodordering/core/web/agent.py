import base64
import enum
import hashlib
import json
import os
import threading
import time
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Union
import typing_extensions
import cv2
import dspy
from pydantic import BaseModel
import requests

from core.utils import (
    FINISH_TOKEN,
    BaseModelJSONEncoder,
    GeneratedToolSpec,
    ImageResizeConfiguration,
    IoU,
    Relative2DScale,
    ToolReport,
    from_config,
    resize_cv2_image,
)
from core.web.interface import BrowserVisibilityMode
from core.web.planning.interface import PlannerTypes
from core.web.planning.dspy_planner import DSPyPlanner, DSPyPlannerConfiguration
from core.web.tool_calling.interface import ToolModes
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller
from core.web.parser import FilterConfig, ParseRequest, ParseRequestConfiguration, ParserConfiguration, ParserDetails, ParserMode, get_item_by_label_number

class Plan(BaseModel):
    plan: str

IterativeTaskResult = Union[Plan, ToolReport, Literal['<|COMPLETED_OVERALL_TASK|>']]

class StrategyRepeatedScreenshots(typing_extensions.TypedDict):
    delay_seconds: float

class ScreenshotStrategy(str, enum.Enum):
    ExternalRepeated = "externalrepeated"
    """Repeatedly take screenshots outside of the browser agent."""
    OnBrowserAgent = "onbrowseragent"
    """Allow the browser agent class to directly call to screenshot."""

class ScreenshotConfiguration(BaseModel):
    strategy: ScreenshotStrategy = os.getenv("SCREENSHOT_STRATEGY", ScreenshotStrategy.OnBrowserAgent)
    spec: Union[Dict[str, Any], StrategyRepeatedScreenshots] = {}

class ExtractionConfiguration(BaseModel):
    iou_threshold: float = os.getenv("BLACKLIST_IOU_THRESHOLD", 0.7)
    image_hashing_function: str = "sha256"

class AnyToolCallWithOrWithoutExceptions(BaseModel):
    could_be: Literal["any"]
    exceptions: List[Union[str, GeneratedToolSpec]] = []

# Used to ease configuration
ToolBlacklistIdentifier = Union[str, GeneratedToolSpec, AnyToolCallWithOrWithoutExceptions]

class BlacklistWhenToolsExhaustedOnRegion(BaseModel):
    all_these_tools_attempted_on_region: List[ToolBlacklistIdentifier]
    """Blacklist a bbox only when all of the these exact tools or all tools of these names have been attempted on that region."""

class BlacklistWhenToolRepeatedNTimes(BaseModel):
    tool_call: Union[ToolBlacklistIdentifier]
    repeated_n_times: int = 3

def is_generated_spec_instance_of_blacklist_identifier(generated_spec: GeneratedToolSpec, identifier: Union[ToolBlacklistIdentifier, List[ToolBlacklistIdentifier]]):
    type_of_identifier = type(identifier)
    if type_of_identifier == str:
        return (generated_spec.tool == identifier)
    elif type_of_identifier == list:
        for sub_identifier in identifier:
            if is_generated_spec_instance_of_blacklist_identifier(generated_spec, sub_identifier):
                return True
        return False
    elif type_of_identifier == GeneratedToolSpec:
        return (generated_spec == identifier)
    elif type_of_identifier == AnyToolCallWithOrWithoutExceptions:
        for exception in identifier.exceptions:
            if is_generated_spec_instance_of_blacklist_identifier(generated_spec, exception):
                return False
        return True

BlacklistConditional = Union[BlacklistWhenToolsExhaustedOnRegion, BlacklistWhenToolRepeatedNTimes]

class BoundingBoxBlacklistEntry(BaseModel):
    xyxy: List[List[float]]
    blacklists_bbox: bool = False
    
class ToolFailureHashSpec(BaseModel):
    tool_spec: GeneratedToolSpec
    blacklists_tool: bool = False
    associated_bbox: Optional[BoundingBoxBlacklistEntry] = None
    source_rule: BlacklistConditional

class BlacklistingConfiguration(BaseModel):
    enabled: bool = os.getenv("ENABLE_BLACKLISTING", True)
    filter_parser_bboxes: ExtractionConfiguration = ExtractionConfiguration()
    when_filter: List[BlacklistConditional] = [
        BlacklistWhenToolRepeatedNTimes(
            tool_call=AnyToolCallWithOrWithoutExceptions(
                could_be="any",
                exceptions=["click_element_by_box_label_number", "type_text_by_box_label_number"]
            ),
            repeated_n_times=3,
        ),
        BlacklistWhenToolsExhaustedOnRegion(
            all_these_tools_attempted_on_region=[
                "click_element_by_box_label_number",
                "type_text_by_box_label_number",
            ],
        ),
    ]

class BrowserAgentConfiguration(BaseModel):
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None
    planner_type: PlannerTypes = PlannerTypes.DSPy
    planner: Union[Dict[str, Any]] = DSPyPlannerConfiguration()
    browser_visibility_mode: BrowserVisibilityMode = BrowserVisibilityMode.Default
    parser: ParserConfiguration = ParserConfiguration()
    image_resize_configuration: ImageResizeConfiguration = Relative2DScale()
    screenshot_call_configuration: ScreenshotConfiguration = ScreenshotConfiguration()
    blacklisting: Optional[BlacklistingConfiguration] = BlacklistingConfiguration()

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
        # This acts as an enforcement policy not to click on
        # bboxes that we have already clicked on in images
        # we have already seen. Key is the screenshot hash (hex bytes)
        # for the mapping.
        self.blacklist: Dict[str, List[ToolFailureHashSpec]] = {}
    
    def get_banned_bboxes(self, image_or_image_hash: Union[str, cv2.typing.MatLike]):
        blacklisted_tool_items: List[ToolFailureHashSpec] = []
        if isinstance(image_or_image_hash, cv2.typing.MatLike):
            image_or_image_hash = self.hash_image(image_or_image_hash)
        blacklisted_tool_items = self.blacklist.get(image_or_image_hash, [])
        return list(map(
            lambda failed_tool_call: failed_tool_call.associated_bbox.xyxy,
            filter(
                lambda failed_tool_call: failed_tool_call.associated_bbox is not None \
                    and failed_tool_call.associated_bbox.blacklists_bbox,
                blacklisted_tool_items
            )
        ))
    
    def get_banned_tools(self, image_or_image_hash: Union[str, cv2.typing.MatLike]):
        blacklisted_tool_items: List[ToolFailureHashSpec] = []
        if isinstance(image_or_image_hash, cv2.typing.MatLike):
            image_or_image_hash = self.hash_image(image_or_image_hash)
        blacklisted_tool_items = self.blacklist.get(image_or_image_hash, [])
        return list(filter(
            lambda failed_tool_call: failed_tool_call.blacklists_tool,
            blacklisted_tool_items
        ))
    
    def evaluate_blacklist_criteria_and_update_blacklist(self, image_hash: str, new_tool_call: GeneratedToolSpec):
        potentially_blacklisted_items: List[ToolFailureHashSpec] = self.blacklist.get(image_hash, [])
        if len(potentially_blacklisted_items) == 0 or \
            self.configuration.blacklisting is None or \
            self.configuration.blacklisting.enabled == False:
                return
        
        region = None
        if new_tool_call.tool in ["click_element_by_box_label_number", "type_text_by_box_label_number"]:
            try:
                item = get_item_by_label_number(new_tool_call.args.get("number", -1))
            except Exception:
                return
            if type(item) == str: return
            region = item.bbox

        for blacklist_rule in self.configuration.blacklisting.when_filter:
            blacklist_rule_type = type(blacklist_rule)
            blacklist_indices_to_prune = set()
            if blacklist_rule_type == BlacklistWhenToolsExhaustedOnRegion:
                possible_calls_remaining_on_region = blacklist_rule.all_these_tools_attempted_on_region
                possible_call_indices_to_remove = set()

                for idx, item in enumerate(potentially_blacklisted_items):
                    if item.source_rule != blacklist_rule: continue
                    if item.associated_bbox is None or item.associated_bbox.xyxy is None: continue
                    if IoU(item.associated_bbox.xyxy, region) > self.configuration.blacklisting.filter_parser_bboxes.iou_threshold:
                        for possible_call_index, possible_call in enumerate(possible_calls_remaining_on_region):
                            if is_generated_spec_instance_of_blacklist_identifier(
                                generated_spec=item.tool_spec,
                                identifier=possible_call,
                            ):
                                blacklist_indices_to_prune.add(idx)
                                possible_call_indices_to_remove.add(possible_call_index)

                sorted_indices_calls_to_remove = sorted(list(possible_call_indices_to_remove))
                counter = 0
                for idx in sorted_indices_calls_to_remove:
                    possible_calls_remaining_on_region.pop(idx - counter)
                    counter += 1
                
                if len(possible_calls_remaining_on_region) == 1 and is_generated_spec_instance_of_blacklist_identifier(new_tool_call, possible_calls_remaining_on_region[0]):
                    sorted_indices_blacklisted_items_to_remove = sorted(list(blacklist_indices_to_prune))
                    counter = 0
                    for idx in sorted_indices_blacklisted_items_to_remove:
                        potentially_blacklisted_items.pop(idx - counter)
                        counter += 1
                    potentially_blacklisted_items.append(ToolFailureHashSpec(
                        tool_spec=new_tool_call,
                        blacklists_tool=True,
                        associated_bbox=BoundingBoxBlacklistEntry(
                            xyxy=region,
                            blacklists_bbox=True,
                        ),
                        source_rule=blacklist_rule,
                    ))
                else:
                    potentially_blacklisted_items.append(ToolFailureHashSpec(
                        tool_spec=new_tool_call,
                        blacklists_tool=False,
                        associated_bbox=BoundingBoxBlacklistEntry(
                            xyxy=region,
                            blacklists_bbox=False,
                        ),
                        source_rule=blacklist_rule,
                    ))
            elif blacklist_rule_type == BlacklistWhenToolRepeatedNTimes:
                evaluated_true = False
                if is_generated_spec_instance_of_blacklist_identifier(new_tool_call, blacklist_rule.tool_call):
                    counter = 1
                    for idx, item in enumerate(potentially_blacklisted_items):
                        if item.source_rule != blacklist_rule: continue
                        if is_generated_spec_instance_of_blacklist_identifier(item.tool_spec, blacklist_rule.tool_call):
                            blacklist_indices_to_prune.add(idx)
                            counter += 1
                            if counter >= blacklist_rule.repeated_n_times:
                                evaluated_true = True
                                break
                if evaluated_true:
                    sorted_indices_blacklisted_items_to_remove = sorted(list(blacklist_indices_to_prune))
                    counter = 0
                    for idx in sorted_indices_blacklisted_items_to_remove:
                        potentially_blacklisted_items.pop(idx - counter)
                        counter += 1
                    potentially_blacklisted_items.append(ToolFailureHashSpec(
                        tool_spec=new_tool_call,
                        blacklists_tool=True,
                        associated_bbox=None if region is None else BoundingBoxBlacklistEntry(
                            xyxy=region,
                            blacklists_bbox=True,
                        ),
                        source_rule=blacklist_rule,
                    ))
                else:
                    potentially_blacklisted_items.append(ToolFailureHashSpec(
                        tool_spec=new_tool_call,
                        blacklists_tool=False,
                        associated_bbox=None if region is None else BoundingBoxBlacklistEntry(
                            xyxy=region,
                            blacklists_bbox=False,
                        ),
                        source_rule=blacklist_rule,
                    ))
            else:
                raise NotImplementedError(f"Unsupported blacklist rule: {type(blacklist_rule)}")
            self.blacklist[image_hash] = potentially_blacklisted_items
    
    async def __call__(self):
        return await self.process_request()
    
    async def process_request(self):
        print("In process_request", flush=True)
        if self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.ExternalRepeated:
            self.screenshot_thread_stopped = False
            self.screenshot_thread = threading.Thread(target=self.screenshot_until_stopped)
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

    async def screenshot_until_stopped(self):
        while not self.screenshot_thread_stopped:
            screenshot = await self.tool_caller.screenshot()
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug \
                and screenshot is not None:
                await self.show_browser(screenshot)
            time.sleep(self.configuration.screenshot_call_configuration.spec.get("delay_seconds", 0.1))

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
        previous_browser_screenshot_preprocessed = previous_browser_screenshot
        current_browser_screenshot_preprocessed = current_browser_screenshot
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

            print("Taking pre-action browser screenshot...", flush=True)
            # Take a screenshot of the browser before the tool call
            previous_browser_screenshot = current_browser_screenshot
            raw_browser_screenshot_before_action = await self.get_current_browser_screenshot(screenshot_save_path=shared.CURRENT_SCREENSHOT_PATH)
            current_browser_screenshot = None if raw_browser_screenshot_before_action is None else raw_browser_screenshot_before_action.copy()

            banned_tools = None
            if self.configuration.blacklisting is not None and self.configuration.blacklisting.enabled:
                raw_browser_screenshot_before_action_hash = self.hash_image(raw_browser_screenshot_before_action)
                banned_tools = self.get_banned_tools(raw_browser_screenshot_before_action_hash)

            print("Pre-action browser screenshot obtained.", flush=True)
            previous_browser_screenshot_preprocessed = current_browser_screenshot_preprocessed
            current_browser_screenshot_preprocessed = self.preprocess_image_for_llm(current_browser_screenshot, image_metadata_save_path=shared.CURRENT_IMAGE_PARSE_METADATA_PATH)
            
            # Show the browser if in debug mode
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug \
                and current_browser_screenshot_preprocessed is not None \
                and self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.OnBrowserAgent:
                await self.show_browser(current_browser_screenshot_preprocessed)
            current_browser_snapshot = await self.tool_caller.take_snapshot()
            if current_browser_snapshot is not None: print(current_browser_snapshot, flush=True)

            if self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.OnBrowserAgent:
                cv2.imwrite(shared.CURRENT_SCREENSHOT_PATH, current_browser_screenshot_preprocessed)

            ### Step 1: Determine sub-task
            if not self.planner.configuration.disable:
                print("Determining subtask...", flush=True)
                subtask = await self.planner.infer_subtask(
                    overall_goal=overall_goal,
                    previous_subtask=previous_subtask,
                    previous_tool_call=previous_tool_call,
                    previous_tool_call_output=previous_tool_call_output,
                    previous_browser_screenshot=previous_browser_screenshot_preprocessed,
                    current_browser_screenshot=current_browser_screenshot_preprocessed,
                    current_browser_snapshot=current_browser_snapshot,
                    tool_caller=self.tool_caller,
                    history=self.history,
                )
                yield Plan(plan=subtask)
                print(f"Successfully determined subtask. Current subtask is `{subtask}`", flush=True)
            else:
                subtask = None
            ### Step 2: Determine, process, and call the tool
            print("Determining tool to call...", flush=True)
            generated_tool = await self.tool_caller.determine_tool(
                overall_goal=overall_goal,
                subtask=subtask,
                previous_browser_screenshot=previous_browser_screenshot_preprocessed,
                current_browser_screenshot=current_browser_screenshot_preprocessed,
                current_browser_snapshot=current_browser_snapshot,
                banned_tools=None if banned_tools is None else json.dumps(banned_tools, indent=2, cls=BaseModelJSONEncoder),
            )
            print(f"Tool to call determined to be: {generated_tool}", flush=True)

            ### TODO: PROCESS TRANSFORMS

            print(f"Calling generated tool...", flush=True)
            tool_prediction_response = generated_tool.spec.model_dump_json()
            tool_call_result = await self.tool_caller.call_tool(generated_tool)
            previous_tool_call, previous_tool_call_output = tool_prediction_response, tool_call_result
            yield ToolReport(
                generated_tool=generated_tool,
                result=tool_call_result,
            )
            print(f"Generated tool called. Tool report result: {tool_call_result}", flush=True)

            # Take a screenshot of the browser after the tool was called
            print("Taking post-action browser screenshot...", flush=True)
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.get_current_browser_screenshot(screenshot_save_path=shared.CURRENT_SCREENSHOT_PATH)
            previous_browser_screenshot_preprocessed = current_browser_screenshot_preprocessed
            current_browser_screenshot_preprocessed = self.preprocess_image_for_llm(current_browser_screenshot, image_metadata_save_path=shared.CURRENT_IMAGE_PARSE_METADATA_PATH)

            if self.configuration.blacklisting is not None and self.configuration.blacklisting.enabled:
                current_browser_screenshot_hash = self.hash_image(current_browser_screenshot)
                if raw_browser_screenshot_before_action_hash is not None and \
                    current_browser_screenshot_hash is not None and \
                    raw_browser_screenshot_before_action_hash == current_browser_screenshot_hash:
                    print("Tool call failure detected. Screenshot after action is the same as screenshot before action. Logging this failure.")
                    self.evaluate_blacklist_criteria_and_update_blacklist(
                        current_browser_screenshot_hash,
                        new_tool_call=generated_tool.spec,
                    )
                    print(f"Tool call {previous_tool_call} banned on this screen.")

            # Show the browser if in debug mode
            if self.configuration.browser_visibility_mode == BrowserVisibilityMode.Debug \
                and current_browser_screenshot_preprocessed is not None \
                and self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.OnBrowserAgent:
                await self.show_browser(current_browser_screenshot_preprocessed)
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

    async def get_current_browser_screenshot(self, screenshot_save_path: str):
        if self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.OnBrowserAgent \
            or not os.path.exists(screenshot_save_path):
            return await self.tool_caller.screenshot()
        elif self.configuration.screenshot_call_configuration.strategy == ScreenshotStrategy.ExternalRepeated \
            and os.path.exists(screenshot_save_path):
            return cv2.imread(screenshot_save_path)
        else:
            raise Exception("Could not obtain the browser screenshot.")

    def preprocess_image_for_llm(self, current_browser_screenshot: cv2.typing.MatLike, image_metadata_save_path: str):
        print("Performing preprocessing steps...")
        if current_browser_screenshot is not None:
            print(f"Screenshot shape: {current_browser_screenshot.shape}", flush=True)
            if self.configuration.parser.parser_mode == ParserMode.Enabled:
                print("Parsing details...", flush=True)
                parsed_details = self.parse_details(
                    current_browser_screenshot,
                    configuration=None if self.configuration.blacklisting is None or \
                        not self.configuration.blacklisting.enabled
                        else ParseRequestConfiguration(
                        filter=FilterConfig(
                            banned_regions=self.get_banned_bboxes(current_browser_screenshot),
                            iou_threshold=self.configuration.blacklisting.filter_parser_bboxes.iou_threshold,
                        )
                    )
                )
                if parsed_details is not None:
                    # Update the parsed details shared with the tool server
                    open(image_metadata_save_path, 'w').write(json.dumps(parsed_details.parsed_content_list, cls=BaseModelJSONEncoder))
                    current_browser_screenshot = parsed_details.matlike_image()
                    print(f"Parsing took {parsed_details.latency} seconds", flush=True)
                else:
                    print("Parsing failed. See server logs for more details.", flush=True)
            current_browser_screenshot = resize_cv2_image(current_browser_screenshot, params=self.configuration.image_resize_configuration)
        
        return current_browser_screenshot

    def parse_details(self, image: cv2.typing.MatLike, configuration: Optional[ParseRequestConfiguration] = None) -> Optional[ParserDetails]:
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        response = requests.post(
            f"{self.configuration.parser.parser_uri}/parse",
            data=ParseRequest(
                base64_image=image_base64,
                configuration=configuration,
            ).model_dump_json(),
        )
        try:
            response = response.json()
        except Exception as e:
            print(e)
            return None
        return ParserDetails.model_validate(response)

    def hash_image(self, image: cv2.typing.MatLike) -> Optional[str]:
        if image is None:
            return None
        try:
            image_hash = image.tobytes().hex()
        except Exception as e:
            print(f"Error hashing: {e}")
            return None
        return image_hash
    