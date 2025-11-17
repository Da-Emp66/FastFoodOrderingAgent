
from typing import Any, Dict, Optional, Union
import cv2
import dspy

from core.web.planning.interface import BrowserActionPlanner, PlannerConfiguration
from core.utils import FINISH_TOKEN, from_config
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller, dspy_image_or_blank

class DSPyPlanner(BrowserActionPlanner):
    class WebToolOutputEvaluatorSignature(dspy.Signature):
        """You are an expert who can evaluate if a given subtask in the process of completing an overall goal 
        was successful or not and planning what the next steps are based on 
        Your sole job is to determine what the next action to perform is based on the 'overall_goal', 
        previously completed steps and tool calls, and current browser state."""

        overall_goal: str = dspy.InputField(desc="The over-arching complex task to complete. ")
        tools: list[dspy.Tool] = dspy.InputField(
            desc="Tools available for use. Use these to help you better plan and describe the 'next_subtask' in natural language. "
        )
        history: dspy.History = dspy.InputField(
            desc="Previous browser interactions, tool calls, and reasoning. " \
            "THIS IS VERY IMPORTANT! PAY ATTENTION TO THIS FIELD AND DO NOT REPEAT ACTIONS THAT ARE NOT WORKING MORE THAN ONCE. " \
            "IF THE BROWSER SCREEN DID NOT CHANGE AFTER A TOOL CALL, WHETHER OR NOT THE TOOL CALL RETURNED SUCCESS MEANS NOTHING. " \
            "EITHER THAT WAS THE WRONG TOOL TO CHOOSE OR YOU GAVE IT THE WRONG ARGUMENTS. " \
            "Try to reason and come up with a different solution if your original idea is not working. "
        )
        previous_browser_screenshot: dspy.Image = dspy.InputField(
            desc="Image of what the browser looked like last time, before the last interaction. " \
            "(This, along with 'current_browser_screenshot' can help tell you if the last call " \
            "succeeded or not.) Blank if no previous interactions "
        )
        previous_subtask: str = dspy.InputField(
            desc="The subtask that was either completed or errored out in the last step. " \
            "See the 'previous_tool_call_name', 'previous_tool_call_args', and 'previous_tool_call_output' fields " \
            "as well as the 'previous_browser_screenshot' and 'current_browser_screenshot' fields to determine if " \
            "the previous tool call was successful. "
        )
        previous_tool_call: str = dspy.InputField(desc="The name of the tool called in the previous step ")
        previous_tool_call_output: str = dspy.InputField(desc="The output of the previous tool call. ")
        current_browser_screenshot: dspy.Image = dspy.InputField(
            desc="Image of what the browser currently looks like based on any previous interactions. " \
            "Blank if no previous interactions"
        )
        current_browser_snapshot: str = dspy.InputField(
            desc="Snapshot containing refs to buttons and interactable divs in the current browser page "
        )
        reasoning: str = dspy.OutputField(
            desc="This should NEVER EVER be 'None', and it should NEVER EVER be empty. You should ALWAYS: " \
            "1. First describe what the browser looks like at the current time.\n" \
            "2. Then evaluate if the previous tool call was successful based on if the screen changed at all. If the screen did not change at all, then the previous tool call was not the correct tool to call, and you should not call that tool again.\n" \
            "   If the previous tool call was not successful, give your thoughts as to why, and give details on what different to try next time in the 'next_subtask' field.\n" \
            "3. Then, based on these thoughts, reason about what should be the 'next_subtask' based on the browser's state and the 'overall_goal'. " \
        )
        next_subtask: str = dspy.OutputField(
            desc="Instructions for what sub-task to do now to work towards the overall goal based on the " \
            f"current browser screen state, or, if the overall goal is complete, fill with {FINISH_TOKEN} in all caps. " \
            "Make sure to describe this step in detail in human-readable natural language. NOTE THAT THIS FIELD SHOULD NEVER EVER BE None, 'None', null or anything similar. It should always be your plan for the next action to perform. " \
            "Only reference buttons and items directly visible in the 'current_browser_screenshot'. If a required button is not directly visible, " \
            "the 'next_subtask' might be to scroll to find the button, or click on another button first. Each subtask should only involve a single click or typing a string into a text box. " \
            "IF THE BUTTON OR BOX IS LABELED BY A NUMBER, ALWAYS INCLUDE THAT NUMBER IN YOUR SUBTASK DESCRIPTION. This is VERY IMPORTANT THAT YOU GET THE BOX NUMBER CORRECT. TAKE YOUR TIME TO READ THE BOX NUMBER CORRECTLY. " \
            "If another click is required, you should include that in the next subtask. " \
            "Note that on the very first step, this sub-task should be to navigate to the url. In that case, just specify the URL and say to navigate to it, not clicking anything. " \
            "NOTE: ALWAYS share your location with the browser. " \
            "NOTE: ALWAYS CLOSE POP-UPs FIRST before continuing on a screen. This is VERY IMPORTANT. " \
            "NOTE: DO NOT REPEATEDLY TRY TO CLICK THE SAME BOX AS BEFORE IF THE PREVIOUS SCREENSHOT IS THE SAME AS THE CURRENT SCREENSHOT. THAT IS LIKELY THE WRONG BOUNDING BOX. "
        )

    def __init__(self, configuration: Union[Dict[str, Any], PlannerConfiguration]):
        self.configuration: PlannerConfiguration = from_config(configuration, PlannerConfiguration)
        # Instantiate task evaluator
        self.next_step_planner = dspy.Predict(self.WebToolOutputEvaluatorSignature)
        self.stream_next_step_planning = dspy.streamify(
            self.next_step_planner,
            stream_listeners=[
                dspy.streaming.StreamListener(signature_field_name="reasoning"),
                dspy.streaming.StreamListener(signature_field_name="next_subtask"),
            ],
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
        tool_caller: Optional[Union[Any, dspy.Tool]] = None,
        history: Optional[dspy.History] = None,
    ) -> str:
        tools = None if not isinstance(tool_caller, DSPyBrowserToolCaller) else list(tool_caller.tools.values())
        # Create the output stream object based on the current task
        output_stream = self.stream_next_step_planning(
            previous_browser_screenshot=None if not self.configuration.visibility_settings.previous_screenshot_visible else dspy_image_or_blank(previous_browser_screenshot),
            current_browser_screenshot=None if not self.configuration.visibility_settings.current_screenshot_visible else dspy_image_or_blank(current_browser_screenshot),
            overall_goal=overall_goal if self.configuration.visibility_settings.overall_goal_visible else None,
            previous_subtask=previous_subtask if self.configuration.visibility_settings.previous_subtask_visible else None,
            previous_tool_call=previous_tool_call if self.configuration.visibility_settings.previous_tool_call_visible else None,
            previous_tool_call_output=previous_tool_call_output if self.configuration.visibility_settings.previous_tool_call_output_visible else None,
            history=history if self.configuration.visibility_settings.history_visible else None,
            current_browser_snapshot=current_browser_snapshot if self.configuration.visibility_settings.snapshot_visible else None,
            tools=None if not self.configuration.visibility_settings.tools_visible else tools,
        )
        
        async for chunk in output_stream:
            # print(chunk)
            if isinstance(chunk, dspy.streaming.StreamResponse):
                print(chunk.chunk, end="", flush=True)
            elif isinstance(chunk, dspy.Prediction):
                task_planning_response = chunk
                subtask = task_planning_response.next_subtask

        # subtask = self.next_step_planner(
        #     previous_browser_screenshot=None if not self.configuration.visibility_settings.previous_screenshot_visible else dspy_image_or_blank(previous_browser_screenshot),
        #     current_browser_screenshot=None if not self.configuration.visibility_settings.current_screenshot_visible else dspy_image_or_blank(current_browser_screenshot),
        #     overall_goal=overall_goal if self.configuration.visibility_settings.overall_goal_visible else None,
        #     previous_subtask=previous_subtask if self.configuration.visibility_settings.previous_subtask_visible else None,
        #     previous_tool_call=previous_tool_call if self.configuration.visibility_settings.previous_tool_call_visible else None,
        #     previous_tool_call_output=previous_tool_call_output if self.configuration.visibility_settings.previous_tool_call_output_visible else None,
        #     history=history if self.configuration.visibility_settings.history_visible else None,
        #     current_browser_snapshot=current_browser_snapshot if self.configuration.visibility_settings.snapshot_visible else None,
        #     tools=None if not self.configuration.visibility_settings.tools_visible else tools,
        # ).next_subtask

        return subtask
