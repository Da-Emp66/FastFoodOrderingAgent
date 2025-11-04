import copy
import json
import os
from pathlib import Path

from core.session.session import CompletionStatus, ObjectiveSpecification, Session, SessionCompletionStatus
from core.web.agent import BrowserAgentSystem
from core.utils import FINISH_TOKEN

MAX_TASK_ITERATIONS = os.getenv("MAX_TASK_ITERATIONS", -1)

MAX_WEBSOCKET_FAILURES = os.getenv("MAX_WEBSOCKET_FAILURES", -1)
CURRENT_SCREENSHOT_PATH = os.getenv("CURRENT_SCREENSHOT_PATH", "/tmp/fast-food-custom-stagehand-server/tmp.jpg")
NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH = os.getenv(
    "NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH",
    str(Path(__file__).parent.parent.parent / "assets" / "no_browser_placeholder.jpg")
)
WEB_AGENT_CONFIG_PATH = os.getenv(
    "WEB_AGENT_CONFIG_PATH",
    str(Path(__file__).parent.parent.parent / "configuration" / "dspy-planner-constrained-tools-custom-mcp.yaml")
)
print(f"Using WEB_AGENT_CONFIG_PATH at {WEB_AGENT_CONFIG_PATH}")

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

    async def __call__(self, *args, **kwds):
        print("In call", flush=True)
        async for task_result in self.browser_agent.iterate_task():
            print("iteration", flush=True)
            if task_result == FINISH_TOKEN:
                print(FINISH_TOKEN)
                return
            else:
                print(task_result)

print(f"Session User: {os.getenv('SESSION_USER')}")
print(f"Session ID: {os.getenv('SESSION_ID')}")
print(f"Session Objective: {os.getenv('SESSION_OBJECTIVE')}")
# Instantiate globals
this_session = SessionInProgress(
    user=os.getenv("SESSION_USER"),
    session_id=os.getenv("SESSION_ID"),
    objective_spec=ObjectiveSpecification(
        objective=os.getenv("SESSION_OBJECTIVE"),
        order=json.loads(os.getenv("SESSION_OBJECTIVE_ORDER", "[]")),
    ),
    status=SessionCompletionStatus(
        state=CompletionStatus.IN_PROGRESS,
        items_ordered=[],
    ),
    browser_agent=BrowserAgentSystem(WEB_AGENT_CONFIG_PATH),
)
print("SessionInProgress instantiated...")
