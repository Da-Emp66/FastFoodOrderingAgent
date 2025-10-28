import argparse
import copy
import json
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
from core.session.session import CompletionStatus, ObjectiveSpecification, Session, SessionCompletionStatus

class SessionInProgress:
    original_spec: Session
    current_spec: Session
    status: SessionCompletionStatus
    browser_agent: BrowserAgentSystem

    def __init__(
        self,
        user: str,
        session_id: str,
        objective_spec: ObjectiveSpecification,
        status: SessionCompletionStatus,
        browser_agent: BrowserAgentSystem,
    ):
        self.original_spec = Session(
            user=user,
            session_id=session_id,
            objective_spec=objective_spec,
        )
        self.current_spec = copy.deepcopy(self.original_spec)
        self.current_spec.__pydantic_setattr_handlers__.update({
            field: self.on_current_session_member_change for field in self.current_spec.__dict__.keys()
        })
        self.status = status
        self.browser_agent = browser_agent

    def on_current_session_member_change(self, _original, key, val):
        print(f"Current `{key}` for session `{self.current_spec.session_id}` changed to {val}")
        super().__setattr__(key, val)

    def __call__(self, *args, **kwds):
        raise NotImplementedError()

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
this_session = SessionInProgress(
    user=os.environ.get("SESSION_USER"),
    session_id=os.environ.get("SESSION_ID"),
    objective_spec=ObjectiveSpecification(
        objective=os.environ.get("SESSION_OBJECTIVE"),
        order=json.loads(os.environ.get("SESSION_OBJECTIVE_ORDER", "[]")),
    ),
    status=SessionCompletionStatus(
        state=CompletionStatus.IN_PROGRESS,
        items_ordered=[],
    ),
    browser_agent = BrowserAgentSystem(WEB_AGENT_CONFIG_PATH),
)

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
        status=this_session.status.state,
        items_ordered=this_session.status.items_ordered,
    )

@app.put("/active-session")
def update_overall_goal(session: Session):
    assert session.user == this_session.original_spec.user
    assert session.session_id == this_session.original_spec.session_id
    this_session.current_spec.objective_spec.objective = session.objective_spec.objective
    return Response(status_code=200)

def main(args):
    main_loop = threading.Thread(target=this_session)
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
