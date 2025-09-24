import asyncio
from itertools import chain
import os
import re
import time
import cv2
import dspy
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

os.environ["MODEL_SERVER"] = "http://localhost:8000"
    
class ToolSignature(dspy.Signature):
    """Signature for manual tool handling."""
    question: str = dspy.InputField()
    tools: list[dspy.Tool] = dspy.InputField()
    outputs: dspy.ToolCalls = dspy.OutputField()
    answer: str = dspy.OutputField()

    
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
        dspy.configure(lm=self.lm)
        self.server_params = StdioServerParameters(
            command="npx",
            args=[
                "@playwright/mcp@latest",
                "--headless",
                "--caps=vision",
            ],
            env=None,
        )
    
    def __call__(self, prompt: str):
        return asyncio.run(self.process_request(prompt))
    
    async def process_request(self, prompt: str):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.tools = [dspy.Tool.from_mcp_tool(session, tool) for tool in tools.tools]
                screenshot_tool = next(filter(lambda tool: tool.name == "browser_take_screenshot", self.tools), None)
                self.agent = dspy.Predict(ToolSignature)
                stream_predict = dspy.streamify(
                    self.agent,
                    stream_listeners=[
                        dspy.streaming.StreamListener(signature_field_name="answer"),
                    ],
                )
                output_stream = stream_predict(question=prompt, tools=self.tools)

                async for chunk in output_stream:
                    if isinstance(chunk, dspy.streaming.StreamResponse):
                        print(chunk.chunk, end="", flush=True)
                    elif isinstance(chunk, dspy.Prediction):
                        print(chunk.answer)
                        response = chunk

                await show_browser(screenshot_tool)
                # # Execute the tool calls
                for call in response.outputs.tool_calls:
                    tool_to_be_called = next(chain(filter(lambda tool: tool.name == call.name, self.tools), self.tools, [None]))
                    result = await tool_to_be_called.acall(**call.args)
                    print(f"Tool: {call.name}")
                    print(f"Args: {call.args}")
                    print(f"Result: {result}")
                    await show_browser(screenshot_tool)

                return response

async def show_browser(screenshot_tool: dspy.Tool):
    print(screenshot_tool)
    screenshot_text = await screenshot_tool.acall() # fullPage=True
    screenshot_file = next(chain(re.findall(r"((?:/[^\s\/]+)+(?:\.(?:\w+)))", screenshot_text), [None]))
    cv2.imshow('Browser Watcher', cv2.imread(screenshot_file))
    cv2.waitKey(1)
    time.sleep(0.2)

if __name__ == "__main__":
    browser_search_agent = BrowserAgent()

    print(browser_search_agent(
        "Go to McDonald's website and add a burger to the order. DO NOT ORDER THE BURGER. Simply put it in the cart and DO NOT GO TO CHECKOUT." \
        "Return to me the full name of the burger you added to the order."
    ))

    # print(browser_search_agent("Tell me a long story"))
    
    # output = browser_search_agent("Navigate to McDonald's website")
    # print(output)
