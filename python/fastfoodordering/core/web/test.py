import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import dspy

from core.web.agent import BrowserAgentSystem
from core.web.tars_like import TARSLikeBrowserAgentSystem
from core.web.simple_agent import SimpleBrowserAgent

# Load environment variables
dotenv_to_use = find_dotenv()
if dotenv_to_use: print(f"Using .env at path: `{dotenv_to_use}`")
load_dotenv(dotenv_to_use)

WEB_AGENT_CONFIG_PATH = os.environ.get(
    "WEB_AGENT_CONFIG_PATH",
    str(Path(__file__).parent.parent.parent / "configuration" / "dspy-planner-constrained-tools-custom-mcp.yaml")
)
print(f"Using WEB_AGENT_CONFIG_PATH at {WEB_AGENT_CONFIG_PATH}")

if __name__ == "__main__":
    lm = dspy.LM(
        "openai/models/ggml-model-Q4_K_M.gguf",
        api_base=os.getenv("OPENAI_BASE_URL"),
        api_key="sk-1234",
        model_type="chat",
        temperature=0.7,
    )
    dspy.settings.configure(lm=lm)

    ### DSPy + PlayWright MCP Tools
    # browser_search_agent = BrowserAgentSystem({
    #     "tool_mode": "dspy",
    #     "tools": {
    #         "mcp_servers": {
    #             "playwright": {
    #                 "command": "npx",
    #                 "args": [
    #                     "@playwright/mcp@latest",
    #                     # "--headless",
    #                     "--caps=vision",
    #                 ],
    #                 "env": None,
    #             },
    #         },
    #         "browser_visibility": {
    #             "screenshot_tool_name": "browser_take_screenshot",
    #             "snapshot_tool_name": "browser_snapshot",
    #         },
    #     },
    #     "browser_visibility_mode": "debug",
    # })

    ### StageHand Tools
    # browser_search_agent = BrowserAgentSystem({
    #     "tool_mode": "stagehand",
    #     "browser_visibility_mode": "debug",
    # })

    ### DSPy + Custom StageHand MCP Tools
    # browser_search_agent = BrowserAgentSystem({
    #     "tool_mode": "dspy",
    #     "tools": {
    #         "mcp_servers": {
    #             "playwright": {
    #                 "command": "uv",
    #                 "args": [
    #                     "run",
    #                     "core/web_tools.py",
    #                     # "--caps=vision",
    #                 ],
    #                 "env": None,
    #             },
    #         },
    #         "browser_visibility": {
    #             "screenshot_tool_name": "screenshot",
    #             # "snapshot_tool_name": "browser_snapshot",
    #         },
    #     },
    #     "browser_visibility_mode": "debug",
    # })

    ### Constrained inference
    # browser_search_agent = BrowserAgentSystem({
    #     "tool_mode": "constrained",
    #     "tools": {
    #         "mcp_servers": {
    #             "playwright": {
    #                 "command": "uv",
    #                 "args": [
    #                     "run",
    #                     "core/web/toolserver.py",
    #                 ],
    #                 "env": None,
    #             },
    #         },
    #         "browser_visibility": {
    #             "screenshot_tool_name": "screenshot",
    #             # "snapshot_tool_name": "browser_snapshot",
    #         },
    #     },
    #     "planner": {
    #         "visibility_settings": {
    #             "tools_visible": True,
    #         },
    #     },
    #     "browser_visibility_mode": "debug",
    # })

    os.environ["SESSION_USER"] = "user"
    os.environ["SESSION_ID"] = "id"
    os.environ["SESSION_OBJECTIVE"] = "Order me a burger from Burger King (https://www.bk.com/) for delivery"
    # os.environ["SESSION_OBJECTIVE"] = "Order me a taco from Taco Bell (https://www.tacobell.com/). Stop when you get to the payment screen."

    # browser_search_agent = TARSLikeBrowserAgentSystem(WEB_AGENT_CONFIG_PATH)
    browser_search_agent = BrowserAgentSystem(WEB_AGENT_CONFIG_PATH)
    
    # WEB_AGENT_CONFIG_PATH = str(Path(__file__).parent.parent.parent / "configuration" / "simple-browser-agent.yaml")
    # browser_search_agent = SimpleBrowserAgent(WEB_AGENT_CONFIG_PATH)

    ### Example inference
    asyncio.run(browser_search_agent())

    ### Example inference
    # browser_search_agent(
    #     "Order me a ham and cheese sub from Subway (https://www.subway.com/)"
    # )

    # ### Example inference
    # browser_search_agent(
    #     "Order me a burger from McDonald's (https://www.mcdonalds.com/)"
    # )
