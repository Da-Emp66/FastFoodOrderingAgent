import copy
import json
import os
from pathlib import Path

from core.session.session import CompletionStatus, ObjectiveSpecification, OrderDetails, Session, SessionCompletionStatus
from core.web.agent import BrowserAgentSystem
from core.web.agent_interface import Agent
from core.web.simple_agent import SimpleBrowserAgent
from core.utils import remove_special_characters

# MAX_WEBSOCKET_FAILURES = os.getenv("MAX_WEBSOCKET_FAILURES", -1)
MAX_TASK_ITERATIONS = os.getenv("MAX_TASK_ITERATIONS", -1)
CURRENT_SCREENSHOT_PATH = os.getenv("CURRENT_SCREENSHOT_PATH", "/tmp/fast-food-custom-stagehand-server/tmp.jpg")
CURRENT_IMAGE_PARSE_METADATA_PATH = os.getenv("CURRENT_IMAGE_PARSE_METADATA_PATH", "/tmp/fast-food-custom-stagehand-server/tmp.json")
NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH = os.getenv(
    "NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH",
    str(Path(__file__).parent.parent.parent / "assets" / "no_browser_placeholder.jpg")
)
WEB_AGENT_CONFIG_PATH = os.getenv("WEB_AGENT_CONFIG_PATH", None)
BROWSER_AGENT_TYPE = os.getenv("BROWSER_AGENT_TYPE", "")

browser_agent = None
_filtered_browser_agent_type = remove_special_characters(BROWSER_AGENT_TYPE.lower())
if "browseruse" in _filtered_browser_agent_type:
    WEB_AGENT_CONFIG_PATH = str(Path(__file__).parent.parent.parent / "configuration" / "simple-browser-agent.yaml")
    print("Using BROWSER_AGENT_TYPE default = Instantiating SimpleBrowserAgent")
    os.environ["SCREENSHOT_STRATEGY"] = "externalrepeated" # TODO: SUPPORT THIS IN SIMPLEBROWSERAGENT AND API
    browser_agent = SimpleBrowserAgent(WEB_AGENT_CONFIG_PATH)
    browser_agent.configuration.screenshot_call_configuration.strategy = "externalrepeated"
    print("SimpleBrowserAgent instantiated!")
elif "base" in _filtered_browser_agent_type and "gpt" in _filtered_browser_agent_type:
    pass
elif "base" in _filtered_browser_agent_type or "minicpm" in _filtered_browser_agent_type:
    WEB_AGENT_CONFIG_PATH = str(Path(__file__).parent.parent.parent / "configuration" / "dspy-planner-constrained-tools-simple-import.yaml")
    print("Using BROWSER_AGENT_TYPE base = Instantiating BrowserAgentSystem")
    browser_agent = BrowserAgentSystem(WEB_AGENT_CONFIG_PATH)
    print("BrowserAgentSystem instantiated!")
elif "api" in _filtered_browser_agent_type:
    os.environ["SCREENSHOT_STRATEGY"] = "externalrepeated" # TODO: SUPPORT THIS IN SIMPLEBROWSERAGENT AND API
    pass
elif WEB_AGENT_CONFIG_PATH is not None:
    try:
        browser_agent = BrowserAgentSystem(WEB_AGENT_CONFIG_PATH)
    except Exception as e1:
        try:
            browser_agent = SimpleBrowserAgent(WEB_AGENT_CONFIG_PATH)
        except Exception as e2:
            raise ValueError(f"Could not instantiate browser_agent of type BrowserAgentSystem or SimpleBrowserAgent from configuration: {WEB_AGENT_CONFIG_PATH}\nError1: {e1}\nError2: {e2}")
else:
    raise NotImplementedError(f"Could not determine agent type for mode '{BROWSER_AGENT_TYPE}' interpreted as -> '{_filtered_browser_agent_type}'. Also, no WEB_AGENT_CONFIG_PATH passed. Failing to instantiate agent.")

print(f"Using WEB_AGENT_CONFIG_PATH at {WEB_AGENT_CONFIG_PATH}")

class SessionInProgress:
    original_spec: Session
    current_spec: Session
    status: SessionCompletionStatus
    browser_agent: Agent

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
        return await self.browser_agent()

print(f"Session User: {os.getenv('SESSION_USER')}")
print(f"Session ID: {os.getenv('SESSION_ID')}")
print(f"Session Objective: {os.getenv('SESSION_OBJECTIVE')}")
# Instantiate globals
this_session = SessionInProgress(
    user=os.getenv("SESSION_USER"),
    session_id=os.getenv("SESSION_ID"),
    objective_spec=ObjectiveSpecification(
        objective=os.getenv("SESSION_OBJECTIVE"),
        order=OrderDetails.model_validate_json(os.getenv("SESSION_OBJECTIVE_ORDER", "{}")),
    ),
    status=SessionCompletionStatus(
        state=CompletionStatus.IN_PROGRESS,
        items_ordered=[],
    ),
    browser_agent=browser_agent,
)
print("SessionInProgress instantiated...")
