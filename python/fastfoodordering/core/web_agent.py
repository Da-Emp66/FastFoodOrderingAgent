import asyncio
from itertools import chain
import os
import re
import time
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

# dspy.settings.configure() # adapter=dspy.JSONAdapter()

class WebToolSignature(dspy.Signature):
    """Signature for manual tool handling."""
    # previous_browser_screenshot: dspy.Image = dspy.InputField(desc="Image of what the browser looked like last time, before the last interaction. If this image is different than the current browser screenshot, you know some call succeeded. Blank if no previous interactions")
    current_browser_screenshot: dspy.Image = dspy.InputField(desc="Image of what the browser currently looks like based on any previous interactions. Blank if no previous interactions")
    task: str = dspy.InputField(desc="Task to perform or target to achieve using any available tools")
    tools: list[dspy.Tool] = dspy.InputField(desc="Tools available to call")
    history: dspy.History = dspy.InputField(desc="Previous tool calls, outputs, and reasoning")
    outputs: dspy.ToolCalls = dspy.OutputField(desc="Tools to call")
    reasoning: str = dspy.OutputField(desc="Reasoning behind the choice that led to the next_task.")
    next_task: str = dspy.OutputField(desc=f"Text-based output describing the next action to perform, or, if complete, fill with {FINISH_TOKEN} in all caps.")
    
class BrowserAgent:
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
        # Screenshots - browser temporal-visual states
        self.previous_browser_screenshot = None
        self.current_browser_screenshot = None
        # Task management and problem solving-loop
        self.most_recent_new_task = ""
        self.history = dspy.History(messages=[])
    
    def __call__(self, prompt: str):
        return asyncio.run(self.process_request(prompt))
    
    async def process_request(self, prompt: str):

        # Create the MCP session
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.tools = [dspy.Tool.from_mcp_tool(session, tool) for tool in tools.tools]
                screenshot_tool = next(filter(lambda tool: tool.name == "browser_take_screenshot", self.tools), None)
                self.agent = dspy.Predict(WebToolSignature)
                stream_predict = dspy.streamify(
                    self.agent,
                    stream_listeners=[
                        dspy.streaming.StreamListener(signature_field_name="reasoning"),
                        dspy.streaming.StreamListener(signature_field_name="next_task"),
                    ],
                )

                # Main Reasoning Loop
                iteration = 0
                while FINISH_TOKEN not in self.most_recent_new_task:
                    print(f"Iteration {iteration}:")
                    print(self.history)

                    output_stream = stream_predict(
                        # previous_browser_screenshot=dspy.Image.from_file(blank_image_path) \
                        #     if self.previous_browser_screenshot is None \
                        #         else dspy.Image.from_file(self.previous_browser_screenshot),
                        current_browser_screenshot=dspy.Image.from_file(blank_image_path) \
                            if self.current_browser_screenshot is None \
                                else dspy.Image.from_file(self.current_browser_screenshot),
                        task=prompt,
                        tools=self.tools,
                        history=self.history,
                    )

                    async for chunk in output_stream:
                        if isinstance(chunk, dspy.streaming.StreamResponse):
                            print(chunk.chunk, end="", flush=True)
                        elif isinstance(chunk, dspy.Prediction):
                            print(f"Reasoning: {chunk.reasoning}")
                            print(f"Next task: {chunk.next_task}")
                            response = chunk
                            self.most_recent_new_task = response

                    self.previous_browser_screenshot = self.current_browser_screenshot
                    self.current_browser_screenshot = await show_browser(screenshot_tool)
                    for call in response.outputs.tool_calls:
                        try:
                            tool_to_be_called = next(chain(filter(lambda tool: tool.name == call.name, self.tools), self.tools, [None]))
                            result = await tool_to_be_called.acall(**call.args)
                            print(f"Tool: {call.name}")
                            print(f"Args: {call.args}")
                            print(f"Result: {result}")
                            self.previous_browser_screenshot = self.current_browser_screenshot
                            self.current_browser_screenshot = await show_browser(screenshot_tool)
                        except Exception as e:
                            print(e)

                    iteration += 1

                return response

async def show_browser(screenshot_tool: dspy.Tool):
    screenshot_text = await screenshot_tool.acall() # fullPage=True
    screenshot_file = next(chain(re.findall(r"((?:/[^\s\/]+)+(?:\.(?:\w+)))", screenshot_text), [None]))
    image = cv2.imread(screenshot_file)
    cv2.imshow('Browser Watcher', image)
    cv2.waitKey(1)
    time.sleep(0.2)
    return screenshot_file

if __name__ == "__main__":
    browser_search_agent = BrowserAgent()

    # print(browser_search_agent(
    #     "Go to McDonald's website (https://www.mcdonalds.com/) and add a burger to the order. DO NOT ORDER THE BURGER. Simply put it in the cart and DO NOT GO TO CHECKOUT." \
    #     "Return to me the full name of the burger you added to the order."
    # ))

    
    print(browser_search_agent(
        "Go to McDonald's website (https://www.mcdonalds.com/), and scroll all the way down"
    ))

    # print(browser_search_agent("Scroll and click the button"))
    
    # output = browser_search_agent("Navigate to McDonald's website (https://www.mcdonalds.com/)")
    # print(output)
