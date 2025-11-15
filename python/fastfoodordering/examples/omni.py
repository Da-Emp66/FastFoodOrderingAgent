from pathlib import Path
import time
import cv2
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import dspy

from core.web.agent import BrowserAgentSystem

"""
First go run (in another terminal)
```
cd parser/OmniParserFork
USE_LOCAL_SEMANTICS=false uv run omnitool/omniparserserver/omniparserserver.py --device cpu
```
"""

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
    )
    dspy.settings.configure(lm=lm)
    os.environ["SESSION_USER"] = "user"
    os.environ["SESSION_ID"] = "id"
    os.environ["SESSION_OBJECTIVE"] = "Order me a burger from Burger King (https://www.bk.com/)"
    browser_search_agent = BrowserAgentSystem(WEB_AGENT_CONFIG_PATH)

    # Parsing
    image = str(Path(__file__).parent / "assets" / "test_BK_image_for_coords.png")
    # image = str(Path(__file__).parent / "examples" / "assets" / "test_BK_image_for_location.jpg")
    image = cv2.imread(image)
    details = browser_search_agent.parse_details(image)
    print(details.parsed_content_list)
    for item in details.parsed_content_list:
        if item.model_extra is not None and len(item.model_extra) != 0: print(f"A model had extra fields: {item.model_extra}")
    print(f"Details obtained in {details.latency} seconds")
    cv2.imshow('Browser Window Details', details.matlike_image())
    cv2.waitKey(3)
    time.sleep(10)
