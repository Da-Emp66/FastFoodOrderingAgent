import argparse
import os
from pathlib import Path
import threading
import cv2
from dotenv import load_dotenv
import dspy
from fastapi import FastAPI, Response, WebSocket
import uvicorn

from core.web.agent import BrowserAgentSystem
from core.session import CompletionStatus, Session, SessionCompletionStatus

ME = Session(
    user=os.environ.get("SESSION_USER"),
    session_id=os.environ.get("SESSION_ID"),
    objective=os.environ.get("SESSION_OBJECTIVE"),
)
STATUS = SessionCompletionStatus(
    status=CompletionStatus.IN_PROGRESS,
)
CURRENT_ITEMS_ORDERED = []

# Environment
os.environ["MODEL"] = "openai/models/ggml-model-Q4_K_M.gguf"
os.environ["OPENAI_API_KEY"] = "sk-1234"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000"
os.environ["MODEL_SERVER"] = os.getenv("OPENAI_BASE_URL")

# Load environment variables
load_dotenv()

MAX_WEBSOCKET_FAILURES = os.environ.get("MAX_WEBSOCKET_FAILURES", 10)
CURRENT_SCREENSHOT_PATH = os.environ.get("CURRENT_SCREENSHOT_PATH", "/tmp/tmp_browser_screenshot.jpg")
NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH = os.environ.get("NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH", Path(__file__).parent.parent.parent / "assets" / "no_browser_placeholder.jpg")

# Instantiate globals
lm = dspy.LM(
    "openai/models/ggml-model-Q4_K_M.gguf",
    api_base=os.getenv("MODEL_SERVER"),
    api_key="sk-1234",
    model_type="chat",
)
dspy.settings.configure(lm=lm)
### Constrained inference
browser_agent = BrowserAgentSystem({
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
app = FastAPI()

@app.websocket("/active-session/view")
async def stream_browser(websocket: WebSocket):
    await websocket.accept()
    n_failures = 0
    while True:
        try:
            if os.path.exists(CURRENT_SCREENSHOT_PATH) and os.path.isfile(CURRENT_SCREENSHOT_PATH):
                image_path = CURRENT_SCREENSHOT_PATH
            else:
                image_path = NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH
            await websocket.send_bytes(cv2.imencode(".jpeg", cv2.imread(image_path))[1].tobytes())
        except Exception as e:
            if n_failures > MAX_WEBSOCKET_FAILURES:
                await websocket.close()
            else:
                print(f"Error in websocket: {e}")

@app.get("/active-session/status")
def get_status():
    return SessionCompletionStatus(
        status=STATUS,
        items_ordered=CURRENT_ITEMS_ORDERED,
    )

@app.put("/active-session")
def update_overall_goal(session: Session):
    assert session.user == ME.user
    assert session.session_id == ME.session_id
    os.environ["SESSION_OBJECTIVE"] = session.objective
    return Response()

def main(args):
    main_loop = threading.Thread(target=browser_agent.run_until_complete)
    main_loop.start()
    uvicorn.run(
        app, 
        host=args.host,
        port=args.port,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    main(args)
