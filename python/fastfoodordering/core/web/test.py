import os
from dotenv import load_dotenv
import dspy

from core.web.agent import BrowserAgentSystem

# Environment
os.environ["MODEL"] = "openai/models/ggml-model-Q4_K_M.gguf"
os.environ["OPENAI_API_KEY"] = "sk-1234"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000"
os.environ["MODEL_SERVER"] = os.getenv("OPENAI_BASE_URL")

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    lm = dspy.LM(
        "openai/models/ggml-model-Q4_K_M.gguf",
        api_base=os.getenv("MODEL_SERVER"),
        api_key="sk-1234",
        model_type="chat",
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
    browser_search_agent = BrowserAgentSystem({
        "tool_mode": "constrained",
        "tools": {
            "mcp_servers": {
                "playwright": {
                    "command": "uv",
                    "args": [
                        "run",
                        "core/web/toolserver.py",
                    ],
                    "env": None,
                },
            },
            "browser_visibility": {
                "screenshot_tool_name": "screenshot",
                # "snapshot_tool_name": "browser_snapshot",
            },
        },
        "planner": {
            "visibility_settings": {
                "tools_visible": True,
            },
        },
        "browser_visibility_mode": "debug",
    })

    ### Example inference
    browser_search_agent(
        "Order me a burger from Burger King (https://www.bk.com/)"
    )

    ### Example inference
    # browser_search_agent(
    #     "Order me a ham and cheese sub from Subway (https://www.subway.com/)"
    # )

    # ### Example inference
    # browser_search_agent(
    #     "Order me a burger from McDonald's (https://www.mcdonalds.com/)"
    # )
