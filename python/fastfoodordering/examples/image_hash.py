
# Load environment variables
import os
from pathlib import Path
import cv2
from dotenv import find_dotenv, load_dotenv
import dspy

from core.web.agent import BlacklistingConfiguration, BrowserAgentSystem


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
    browser_search_agent.configuration.blacklisting = BlacklistingConfiguration()

    # Parsing
    image = str(Path(__file__).parent / "assets" / "test_BK_image_for_coords.png")
    # image = str(Path(__file__).parent / "examples" / "assets" / "test_BK_image_for_location.jpg")
    image = cv2.imread(image)
    image_hash_before_change = browser_search_agent.hash_image(image)
    image_hash2_before_change = browser_search_agent.hash_image(image.copy())
    print(f"image_hash_before_change == image_hash2_before_change : {image_hash_before_change == image_hash2_before_change}")
    x, y = 32, 180
    before_pixel = image[x,y]
    image[y,x] = (0, 0, 255)
    image_hash_after_change = browser_search_agent.hash_image(image)
    print(f"image_hash_before_change == image_hash_after_change : {image_hash_before_change == image_hash_after_change}")
    image[y,x] = before_pixel
    image_hash_after_change_back = browser_search_agent.hash_image(image)
    print(f"image_hash_before_change == image_hash_after_change_back : {image_hash_before_change == image_hash_after_change_back}")
