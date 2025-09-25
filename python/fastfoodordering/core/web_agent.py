import asyncio
from itertools import chain
import os
import re
import time
from typing import Any, Literal, Optional
import cv2
import dspy
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import numpy as np
from openai import OpenAI

os.environ["MODEL_SERVER"] = "http://localhost:8000"

FINISH_TOKEN = "<|COMPLETED_OVERALL_TASK|>"

blank_image = np.zeros((256, 256, 3), dtype=np.uint8)
blank_image_path = os.path.join(os.path.dirname(__file__), "blank.jpg")
cv2.imwrite(blank_image_path, blank_image)

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
    task: str = dspy.InputField(
        desc="Current task to perform or target to achieve using any available tools."
    )
    tools: list[dspy.Tool] = dspy.InputField(
        desc="Available tools to select from"
    )

class WebToolOutputEvaluatorSignature(dspy.Signature):
    """You are an expert who can evaluate if a given subtask in the process of completing an overall goal
    was successful or not and planning what the next steps are based on 
    Your sole job is to determine what the next action to perform is based on the 'overall_goal',
    previously completed steps and tool calls, and current browser state."""

    overall_goal: str = dspy.InputField(desc="The over-arching complex task to complete.")
    # previous_browser_screenshot: dspy.Image = dspy.InputField(
    #     desc="Image of what the browser looked like last time, before the last interaction." \
    #     "(This, along with 'current_browser_screenshot' can help tell you if the last call" \
    #     "succeeded or not.) Blank if no previous interactions"
    # )
    previous_subtask: str = dspy.InputField(
        desc="The subtask that was either completed or errored out in the last step." \
        "See the 'previous_tool_call_name', 'previous_tool_call_args', and 'previous_tool_call_output' fields" \
        "as well as the 'previous_browser_screenshot' and 'current_browser_screenshot' fields to determine if" \
        "the previous tool call was successful."
    )
    previous_tool_call_name: str = dspy.InputField(desc="The name of the tool called in the previous step")
    previous_tool_call_args: dict[str, Any] = dspy.InputField(desc="The arguments given to the tool called in the previous step")
    previous_tool_call_output: str = dspy.InputField(desc="The output of the previous tool call.")
    # current_browser_screenshot: dspy.Image = dspy.InputField(
    #     desc="Image of what the browser currently looks like based on any previous interactions." \
    #     "Blank if no previous interactions"
    # )
    reasoning: str = dspy.OutputField(
        desc="This should never be 'None'. First describe what the browser looks like at the current time." \
        "Then evaluate if the previous tool call was successful." \
        "Then, based on these thoughts, reason about what should be the 'next_task' based on the browser's state and the 'overall_goal'." \
        "If the previous tool call was not successful, give your thoughts as to why, and give details on what different to try next time in the 'next_task' field."
    )
    next_subtask: str = dspy.OutputField(
        desc="This should never be 'None'. Instructions for what sub-task to do now to work towards the overall goal based on the" \
        f"current state, or, if the overall goal is complete, fill with {FINISH_TOKEN} in all caps." \
        "Make sure to describe this step in detail in human-readable natural language."
    )
    tools: list[dspy.Tool] = dspy.InputField(
        desc="Tools available for use. Use these to help you better plan and describe the 'next_subtask' in natural language."
    )
    history: dspy.History = dspy.InputField(desc="Previous browser interactions, tool calls, and reasoning")
    
class BrowserAgentSystem:
    def __init__(self):
        asyncio.run(self.instantiate())

    async def instantiate(self):
        self.lm = dspy.LM(
            "openai/models/ggml-model-Q4_K_M.gguf",
            api_base=os.getenv("MODEL_SERVER"),
            api_key="sk-1234",
            model_type="chat",
        )
        dspy.settings.configure(lm=self.lm)
        self.server_params = StdioServerParameters(
            command="npx",
            args=[
                "@playwright/mcp@latest",
                "--headless",
                "--caps=vision",
            ],
            env=None,
        )
        # Task management and problem solving-loop
        self.history = dspy.History(messages=[])
    
    def __call__(self, prompt: str):
        return asyncio.run(self.process_request(prompt))
    
    async def process_request(self, prompt: str, maximum_iterations: int = -1):
        overall_goal = prompt
        print(f"Goal: {overall_goal}")

        previous_browser_screenshot = None
        current_browser_screenshot = None
        previous_subtask = "None"
        previous_tool_call_name = "None"
        previous_tool_call_args = "None"
        previous_tool_call_output = "None"

        # Create the MCP session and initialize tools
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tools = [dspy.Tool.from_mcp_tool(session, tool) for tool in tools.tools]
                self.tools = {tool.name: tool for tool in tools}
                screenshot_tool = self.tools["browser_take_screenshot"]

                # Instantiate task evaluator
                self.next_step_planner = dspy.Predict(WebToolOutputEvaluatorSignature)
                stream_next_step_planning = dspy.streamify(
                    self.next_step_planner,
                    stream_listeners=[
                        dspy.streaming.StreamListener(signature_field_name="reasoning"),
                        dspy.streaming.StreamListener(signature_field_name="next_subtask"),
                    ],
                )

                # Instantiate tool predictor
                self.tool_prediction = dspy.Predict(WebToolSelectionSignature
                    .prepend("selected_tool_name", dspy.OutputField(), type_=Literal[tuple(self.tools.keys())])
                    .prepend("selected_tool_args", dspy.OutputField(), type_=dict[str, Any]))
                stream_tool_prediction = dspy.streamify(
                    self.tool_prediction,
                    # stream_listeners=[
                    #     dspy.streaming.StreamListener(signature_field_name="reasoning"),
                    #     dspy.streaming.StreamListener(signature_field_name="next_task"),
                    # ],
                )

                # Main Reasoning Loop
                iteration = 0
                while maximum_iterations == -1 or iteration < maximum_iterations:

                    ### Step 1: Determine sub-task

                    # Create the output stream object based on the current task
                    output_stream = stream_next_step_planning(
                        # previous_browser_screenshot=image_or_blank(previous_browser_screenshot),
                        # current_browser_screenshot=image_or_blank(current_browser_screenshot),
                        overall_goal=overall_goal,
                        previous_subtask=previous_subtask,
                        previous_tool_call_name=previous_tool_call_name,
                        previous_tool_call_args=previous_tool_call_args,
                        previous_tool_call_output=previous_tool_call_output,
                        tools=self.tools,
                        history=self.history,
                    )
                    
                    async for chunk in output_stream:
                        if isinstance(chunk, dspy.streaming.StreamResponse):
                            print(chunk.chunk, end="", flush=True)
                        elif isinstance(chunk, dspy.Prediction):
                            task_planning_response = chunk
                            subtask = task_planning_response.next_subtask

                    if FINISH_TOKEN in subtask:
                        break
                    
                    print(f"\nIteration {iteration}: Task: {subtask}")

                    ### Step 2: Tool prediction

                    # Create the output stream object based on the current task
                    output_stream = stream_tool_prediction(
                        overall_goal=overall_goal,
                        previous_browser_screenshot=image_or_blank(previous_browser_screenshot),
                        current_browser_screenshot=image_or_blank(current_browser_screenshot),
                        task=subtask,
                        tools=self.tools,
                    )

                    # Show the LLM's outputs as it generates the tool prediction
                    async for chunk in output_stream:
                        if isinstance(chunk, dspy.streaming.StreamResponse):
                            print(chunk.chunk, end="", flush=True)
                        elif isinstance(chunk, dspy.Prediction):
                            tool_prediction_response = chunk

                    # Take a screenshot of the browser before the tool call
                    previous_browser_screenshot = current_browser_screenshot
                    current_browser_screenshot = await show_browser(screenshot_tool)

                    # Determine the result of the tool call (Success or Error)
                    tool_call_result = ""
                    if tool_prediction_response.selected_tool_name in self.tools:
                        try:
                            tool = self.tools[tool_prediction_response.selected_tool_name]
                            tool_call_result = await tool.acall(**tool_prediction_response.selected_tool_args)
                            print(f"Tool: {tool_prediction_response.selected_tool_name}")
                            print(f"Args: {tool_prediction_response.selected_tool_args}")
                        except Exception as e:
                            print(e)
                            tool_call_result = e
                    else:
                        tool_call_result = f"Tool {tool_prediction_response.selected_tool_name} not in list of available tools. List of available tools is {list(self.tools.keys())}."
                    previous_tool_call_name = tool_prediction_response.selected_tool_name
                    previous_tool_call_args = tool_prediction_response.selected_tool_args
                    previous_tool_call_output = tool_call_result

                    # Take a screenshot of the browser after the tool was called
                    previous_browser_screenshot = current_browser_screenshot
                    current_browser_screenshot = await show_browser(screenshot_tool)

                    # Append the current messages to the history
                    self.history.messages.append({"overall_goal": overall_goal, "subtask": subtask, **tool_prediction_response.toDict()})
                    previous_subtask = subtask

                    # Increment the iteration
                    iteration += 1

                    # print(dspy.inspect_history())

                return tool_prediction_response

async def show_browser(screenshot_tool: dspy.Tool):
    screenshot_text = await screenshot_tool.acall() # fullPage=True
    screenshot_file = next(chain(re.findall(r"((?:/[^\s\/]+)+(?:\.(?:\w+)))", screenshot_text), [None]))
    image = cv2.imread(screenshot_file)
    cv2.imshow('Browser Watcher', image)
    cv2.waitKey(1)
    time.sleep(0.2)
    return screenshot_file

def image_or_blank(filepath: Optional[str]) -> dspy.Image:
    return dspy.Image.from_file(blank_image_path) \
        if filepath is None \
        else dspy.Image.from_file(filepath),

if __name__ == "__main__":
    browser_search_agent = BrowserAgentSystem()

    browser_search_agent(
        "Go to McDonald's website (https://www.mcdonalds.com/) and add a burger to the order. DO NOT ORDER THE BURGER. Simply put it in the cart and DO NOT GO TO CHECKOUT." \
        "Return to me the full name of the burger you added to the order."
    )

    # browser_search_agent(
    #     "Go to McDonald's website (https://www.mcdonalds.com/), close out of any cookies tabs, and scroll all the way down"
    # )

    # browser_search_agent("Scroll and click the button")
    
    # output = browser_search_agent("Navigate to McDonald's website (https://www.mcdonalds.com/)")
    # print(output)
