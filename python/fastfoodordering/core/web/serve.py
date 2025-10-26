import argparse
import os
from pathlib import Path
import threading
import cv2
from dotenv import find_dotenv, load_dotenv
import dspy
from fastapi import FastAPI, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.web.agent import BrowserAgentSystem
from core.session.session import CompletionStatus, Session, SessionCompletionStatus

ME = Session(
    user=os.environ.get("SESSION_USER"),
    session_id=os.environ.get("SESSION_ID"),
    objective=os.environ.get("SESSION_OBJECTIVE"),
)
STATUS = SessionCompletionStatus(
    status=CompletionStatus.IN_PROGRESS,
)
CURRENT_ITEMS_ORDERED = []

# Load environment variables
dotenv_to_use = find_dotenv()
if dotenv_to_use: print(f"Using .env at path: `{dotenv_to_use}`")
load_dotenv(dotenv_to_use)

MAX_WEBSOCKET_FAILURES = os.environ.get("MAX_WEBSOCKET_FAILURES", 10)
CURRENT_SCREENSHOT_PATH = os.environ.get("CURRENT_SCREENSHOT_PATH", "/tmp/tmp_browser_screenshot.jpg")
NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH = os.environ.get(
    "NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH",
    str(Path(__file__).parent.parent.parent / "assets" / "no_browser_placeholder.jpg")
)
WEB_AGENT_CONFIG_PATH = os.environ.get(
    "WEB_AGENT_CONFIG_PATH",
    str(Path(__file__).parent.parent.parent / "configuration" / "dspy-planner-constrained-tools-custom-mcp.yaml")
)

# Instantiate globals
lm = dspy.LM(
    "openai/models/ggml-model-Q4_K_M.gguf",
    api_base=os.getenv("MODEL_SERVER"),
    api_key="sk-1234",
    model_type="chat",
)
dspy.settings.configure(lm=lm)
browser_agent = BrowserAgentSystem(WEB_AGENT_CONFIG_PATH)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # List of allowed origins
    allow_credentials=True, # Allow cookies and credentials
    allow_methods=["*"], # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)

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
