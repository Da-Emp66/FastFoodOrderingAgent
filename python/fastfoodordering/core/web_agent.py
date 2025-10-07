import abc
import asyncio
import enum
from itertools import chain
import os
import re
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
import PIL
import cv2
from dotenv import load_dotenv
import dspy
import litellm
from mcp import ClientSession, StdioServerParameters
from mcp.client.session_group import ClientSessionGroup
import numpy as np
from openai import OpenAI
from pydantic import BaseModel, Field
from stagehand import StagehandConfig, Stagehand
from stagehand.agent.agent import MODEL_TO_CLIENT_CLASS_MAP, OpenAICUAClient

from core.utils import MCPUserConfiguration, FINISH_TOKEN, from_config

# Environment
os.environ["MODEL"] = "openai/models/ggml-model-Q4_K_M.gguf"
os.environ["OPENAI_API_KEY"] = "sk-1234"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000"
os.environ["MODEL_SERVER"] = os.getenv("OPENAI_BASE_URL")
litellm.api_base = os.getenv("OPENAI_BASE_URL")
MODEL_TO_CLIENT_CLASS_MAP.update({litellm.api_base: lambda *args, **kwargs: OpenAICUAClient(*args, **kwargs)})

# Load environment variables
load_dotenv()

class BrowserToolCaller(metaclass=abc.ABCMeta):
    async def initialize_tools(self):
        pass
    
    @abc.abstractmethod
    async def determine_and_call_tools(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None
    ) -> Tuple[str, str]:
        raise NotImplementedError()
    
    async def close(self):
        pass
    
    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        return None
    
    async def take_snapshot(self) -> Optional[str]:
        return None

class StageHandBrowserToolCaller(BrowserToolCaller):
    def __init__(self, configuration: Optional[Any] = None):
        # Stagehand
        self.stagehand_config = StagehandConfig(
            env="LOCAL",
            model_name=os.getenv("MODEL_NAME"),
            model_api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.stagehand = Stagehand(self.stagehand_config)

    async def initialize_tools(self):
        await self.stagehand.init()
        self.page = self.stagehand.page

    async def determine_and_call_tools(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None
    ):
        tool_call_result = str((await self.page.act(subtask)))
        return tool_call_result, tool_call_result
    
    async def close(self):
        self.stagehand.close()

    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        image_bytes = await self.stagehand.page._page.screenshot(path="tmp.jpg")
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return image

class DSPyBrowserVisibilityConfiguration(BaseModel):
    screenshot_tool_name: Optional[str] = "browser_take_screenshot"
    snapshot_tool_name: Optional[str] = "browser_snapshot"

class DSPyBrowserToolCallerConfiguration(MCPUserConfiguration):
    mcp_servers: Dict[str, StdioServerParameters] = {
        "playwright": {
            "command": "npx",
            "args": [
                "@playwright/mcp@latest",
                "--headless",
                "--caps=vision",
            ],
            "env": None,
        },
    }
    browser_visibility: DSPyBrowserVisibilityConfiguration = DSPyBrowserVisibilityConfiguration()

def dspy_image_or_blank(image: Optional[cv2.typing.MatLike]) -> dspy.Image:
    if image is None:
        return dspy.Image.from_PIL(PIL.Image.new("RGB", (256, 256), "black"))
    else:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = PIL.Image.fromarray(rgb_image)
        return dspy.Image.from_PIL(pil_image)
    
class DSPyBrowserToolCaller(BrowserToolCaller):
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

    async def initialize_tools(self):
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
        # Initialize DSPy tools
        tools = [dspy.Tool(tool_function) for tool_function in self.configuration.custom_tools]
        for _session_name, session in self.mcp_sessions.items():
            session_tools = (await session.list_tools()).tools
            dspy_session_tools = [dspy.Tool.from_mcp_tool(session, tool) for tool in session_tools]
            tools += dspy_session_tools

        self.tools = {tool.name: tool for tool in tools}
        
        # Instantiate tool predictor
        self.tool_prediction = dspy.Predict(self.WebToolSelectionSignature
            .prepend("selected_tool_name", dspy.OutputField(), type_=Literal[tuple(self.tools.keys())])
            .prepend("selected_tool_args", dspy.OutputField(
                    desc="This should ALWAYS be a valid JSON. If using browser_click, always pass the JSON fields 'element' and 'ref' as their string values based on the 'task' and 'current_browser_snapshot' definitions."
                ),
                type_=dict[str, Any]
            )
        )
        self.stream_tool_prediction = dspy.streamify(self.tool_prediction)

    async def determine_and_call_tools(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None
    ):
        # Create the output stream object based on the current task
        output_stream = self.stream_tool_prediction(
            overall_goal=overall_goal,
            task=subtask,
            tools=list(self.tools.values()),
            current_browser_snapshot=current_browser_snapshot,
            previous_browser_screenshot=dspy_image_or_blank(previous_browser_screenshot),
            current_browser_screenshot=dspy_image_or_blank(current_browser_screenshot),
        )

        # Show the LLM's outputs as it generates the tool prediction
        async for chunk in output_stream:
            if isinstance(chunk, dspy.streaming.StreamResponse):
                print(chunk.chunk, end="", flush=True)
            elif isinstance(chunk, dspy.Prediction):
                tool_prediction_response = chunk.toDict()

        selected_tool_name = tool_prediction_response.get("selected_tool_name", None)
        selected_tool_args = tool_prediction_response.get("selected_tool_args", None)
        if selected_tool_name in self.tools:
            try:
                try:
                    # Correct a common formatting mistake in JSON structure
                    if selected_tool_name in selected_tool_args and \
                        isinstance(selected_tool_args[selected_tool_name], dict):
                        selected_tool_args = selected_tool_args[selected_tool_name]
                except Exception as e:
                    print(f"Error in correcting JSON: {e}")
                
                print(f"Tool: {selected_tool_name}")
                print(f"Args: {selected_tool_args}")

                tool = self.tools[selected_tool_name]
                tool_call_result = await tool.acall(**selected_tool_args)
            except Exception as e:
                print(e)
                tool_call_result = e
        else:
            tool_call_result = f"Tool {selected_tool_name} not in list of available tools. List of available tools is {list(self.tools.keys())}."
    
        return str({"tool": selected_tool_name, "args": selected_tool_args}), tool_call_result

    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        screenshot_tool = self.tools.get(self.configuration.browser_visibility.screenshot_tool_name, None)
        if screenshot_tool is not None:
            screenshot_text = await screenshot_tool.acall() # fullPage=True
            screenshot_filepath = next(chain(re.findall(r"((?:/[^\s\/]+)+(?:\.(?:\w+)))", screenshot_text), [None]))
            image = cv2.imread(screenshot_filepath)
            if os.path.exists(screenshot_filepath) and \
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

class CodeBrowserToolCallerConfiguration(MCPUserConfiguration):
    pass

class CodeBrowserToolCaller(BrowserToolCaller):
    def __init__(self, configuration: Union[Dict[str, Any], CodeBrowserToolCallerConfiguration]):
        self.configuration: CodeBrowserToolCallerConfiguration = from_config(configuration, CodeBrowserToolCallerConfiguration)

    async def initialize_tools(self):
        # # Create the MCP session and initialize tools
        # self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        # self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
        pass

class ConstrainedBrowserToolCallerConfiguration(MCPUserConfiguration):
    pass

class ConstrainedBrowserToolCaller(BrowserToolCaller):
    def __init__(self, configuration: Union[Dict[str, Any], ConstrainedBrowserToolCallerConfiguration]):
        self.configuration: ConstrainedBrowserToolCallerConfiguration = from_config(configuration, ConstrainedBrowserToolCallerConfiguration)

    async def initialize_tools(self):
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }

class ToolModes(str, enum.Enum):
    Code = "code"
    Constrained = "constrained"
    DSPy = "dspy"
    StageHand = "stagehand"

class BrowserVisibilityMode(str, enum.Enum):
    Debug = "debug"
    Default = "default"

class BrowserActionPlanner(metaclass=abc.ABCMeta):
    @abc.abstractmethod
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
        raise NotImplementedError()

class PlannerVisibilitySettings(BaseModel):
    previous_screenshot_visible: bool = True
    current_screenshot_visible: bool = True
    overall_goal_visible: bool = True
    previous_subtask_visible: bool = True
    previous_tool_call_visible: bool = True
    previous_tool_call_output_visible: bool = True
    history_visible: bool = True
    snapshot_visible: bool = False
    tools_visible: bool = False

class DSPyPlannerConfiguration(BaseModel):
    visibility_settings: PlannerVisibilitySettings = PlannerVisibilitySettings()

class DSPyPlanner:

    class WebToolOutputEvaluatorSignature(dspy.Signature):
        """You are an expert who can evaluate if a given subtask in the process of completing an overall goal
        was successful or not and planning what the next steps are based on 
        Your sole job is to determine what the next action to perform is based on the 'overall_goal',
        previously completed steps and tool calls, and current browser state."""

        overall_goal: str = dspy.InputField(desc="The over-arching complex task to complete.")
        previous_browser_screenshot: dspy.Image = dspy.InputField(
            desc="Image of what the browser looked like last time, before the last interaction." \
            "(This, along with 'current_browser_screenshot' can help tell you if the last call" \
            "succeeded or not.) Blank if no previous interactions"
        )
        previous_subtask: str = dspy.InputField(
            desc="The subtask that was either completed or errored out in the last step." \
            "See the 'previous_tool_call_name', 'previous_tool_call_args', and 'previous_tool_call_output' fields" \
            "as well as the 'previous_browser_screenshot' and 'current_browser_screenshot' fields to determine if" \
            "the previous tool call was successful."
        )
        previous_tool_call: str = dspy.InputField(desc="The name of the tool called in the previous step")
        previous_tool_call_output: str = dspy.InputField(desc="The output of the previous tool call.")
        current_browser_screenshot: dspy.Image = dspy.InputField(
            desc="Image of what the browser currently looks like based on any previous interactions." \
            "Blank if no previous interactions"
        )
        current_browser_snapshot: str = dspy.InputField(
            desc="Snapshot containing refs to buttons and interactable divs in the current browser page"
        )
        reasoning: str = dspy.OutputField(
            desc="This should never be 'None'. First describe what the browser looks like at the current time." \
            "Then evaluate if the previous tool call was successful." \
            "Then, based on these thoughts, reason about what should be the 'next_task' based on the browser's state and the 'overall_goal'." \
            "If the previous tool call was not successful, give your thoughts as to why, and give details on what different to try next time in the 'next_task' field."
        )
        next_subtask: str = dspy.OutputField(
            desc="Instructions for what sub-task to do now to work towards the overall goal based on the" \
            f"current state, or, if the overall goal is complete, fill with {FINISH_TOKEN} in all caps." \
            "Make sure to describe this step in detail in human-readable natural language. This field should never be 'None'." \
            "Only reference buttons and items directly visible in the 'current_browser_screenshot'. If a required button is not directly visible," \
            "the 'next_subtask' might be to scroll to find the button, or click on another button first. Each subtask should only involve a single click." \
            "If another click is required, you should include that in the next subtask."
        )
        tools: list[dspy.Tool] = dspy.InputField(
            desc="Tools available for use. Use these to help you better plan and describe the 'next_subtask' in natural language."
        )
        history: dspy.History = dspy.InputField(desc="Previous browser interactions, tool calls, and reasoning")

    def __init__(self, configuration: Union[Dict[str, Any], DSPyPlannerConfiguration]):
        self.configuration: DSPyPlannerConfiguration = from_config(configuration, DSPyPlannerConfiguration)
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
            if isinstance(chunk, dspy.streaming.StreamResponse):
                print(chunk.chunk, end="", flush=True)
            elif isinstance(chunk, dspy.Prediction):
                task_planning_response = chunk
                subtask = task_planning_response.next_subtask

        return subtask

class PlannerTypes(str, enum.Enum):
    DSPy = "dspy"

class BrowserAgentConfiguration(BaseModel):
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Union[DSPyBrowserToolCallerConfiguration, Any]] = None
    planner_type: PlannerTypes = PlannerTypes.DSPy
    planner: Union[DSPyPlannerConfiguration] = DSPyPlannerConfiguration()
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

            if FINISH_TOKEN in subtask:
                break
            
            print(f"\nIteration {iteration}: Task: {subtask}")

            ### Step 2: Tool prediction

            # Take a screenshot of the browser before the tool call
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.tool_caller.screenshot()
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

            # Take a screenshot of the browser after the tool was called
            previous_browser_screenshot = current_browser_screenshot
            current_browser_screenshot = await self.tool_caller.screenshot()
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

if __name__ == "__main__":
    
    lm = dspy.LM(
        "openai/models/ggml-model-Q4_K_M.gguf",
        api_base=os.getenv("MODEL_SERVER"),
        api_key="sk-1234",
        model_type="chat",
    )
    dspy.settings.configure(lm=lm)

    ### DSPy Tools
    browser_search_agent = BrowserAgentSystem({
        "tool_mode": "dspy",
        "tools": {
            "mcp_servers": {
                "playwright": {
                    "command": "npx",
                    "args": [
                        "@playwright/mcp@latest",
                        # "--headless",
                        "--caps=vision",
                    ],
                    "env": None,
                },
            },
            "browser_visibility": {
                "screenshot_tool_name": "browser_take_screenshot",
                "snapshot_tool_name": "browser_snapshot",
            },
        },
        "browser_visibility_mode": "debug",
    })

    ### StageHand Tools
    # browser_search_agent = BrowserAgentSystem({
    #     "tool_mode": "stagehand",
    #     "browser_visibility_mode": "debug",
    # })


    ### Example inference
    browser_search_agent(
        "Go to McDonald's website (https://www.mcdonalds.com/) and add a burger to the order. DO NOT ORDER THE BURGER. Simply put it in the cart and DO NOT GO TO CHECKOUT." \
        "Return to me the full name of the burger you added to the order."
    )
    # browser_search_agent(
    #     "Go to McDonald's website (https://www.mcdonalds.com/), close out of any cookies tabs, and scroll all the way down"
    # )
