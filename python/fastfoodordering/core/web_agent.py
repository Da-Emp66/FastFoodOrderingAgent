import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
# from openai import OpenAI

os.environ["MODEL_SERVER"] = "http://localhost:8000"

# client = OpenAI()
llm = LiteLlm(
    model="/models/ggml-model-Q4_K_M.gguf",
    base_url=os.getenv("MODEL_SERVER"),
    # llm_client=client
)

root_agent = Agent(
    name="search_assistant",
    model=llm,
    instruction="You are a helpful assistant. Answer user questions using Google Search when needed.",
    description="An assistant that can search the web.",
    tools=[]
)

print(llm.llm_client.completion("/models/ggml-model-Q4_K_M.gguf", messages=[{ "content": "Hello, how are you?","role": "user"}], tools=[], base_url=os.getenv("MODEL_SERVER")))
