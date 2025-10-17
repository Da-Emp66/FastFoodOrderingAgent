from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import cv2
from pydantic import BaseModel

from core.utils import from_config
from core.web_agent import BrowserAgentSystem, ConstrainedBrowserToolCaller, DSPyBrowserToolCaller, ToolModes

BACKEND_LOGGER: logging.Logger = logging.getLogger("BACKEND_LOGGER")
VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH: str = Path(__file__).parent.parent / "assets" / "video_placeholder.jpg"

class BrowserGeoLocation(BaseModel):
    latitude: float
    """User location latitude component."""
    longitude: float
    """User location longitude component."""
    accuracy: float
    """A measure of how accurate the (latitude, longitude) coordinate is, in meters."""

class SessionManagerPrompt(BaseModel):
    user: str
    """Username, user ID, or email."""
    prompt: str
    """The user's query, question, or request. Will be sent to the SessionManager to decide what to do."""
    session_id: Optional[str] = None
    """If the user has a session open and this query is for updating that session, pass the session_id returned when you first created the session."""
    current_geolocation: Optional[BrowserGeoLocation] = None
    """The user's current geolocation. To be used for the browser proxied location on session launch."""

class SessionManagerChatResult(BaseModel):
    response: str
    """The LLM's response to the user's query."""
    session_id: Optional[str] = None
    """If there is a session created for the first time during this chat, the session_id is returned. Otherwise, null."""

@dataclass
class Session:
    user: str
    session_id: str
    objective: str
    web_agent: BrowserAgentSystem
    """Placeholder -- TODO: This should be a reference to an isolated docker container spun up dynamically that can be communicated with."""

class SessionManagerConfiguration(BaseModel):
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None

class SessionManager:
    def __init__(self, configuration: Union[SessionManagerConfiguration, Any]):
        # self.configuration: SessionManagerConfiguration = from_config(configuration, SessionManagerConfiguration)
        # match self.configuration.tool_mode:
        #     case ToolModes.Constrained: self.tool_caller = ConstrainedBrowserToolCaller(self.configuration.tools)
        #     case ToolModes.DSPy: self.tool_caller = DSPyBrowserToolCaller(self.configuration.tools)
        #     case _: self.tool_caller = None
        
        # Outer key is user, inner key is session_id
        self.sessions: Dict[str, Dict[str, Session]] = {}
    
    def __call__(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
        pass
    
    def browser_screenshot_generator(self, user: str, session_id: str):
        try:
            # Loop until the client connection exist
            while True:
                # Check if the camera capture is successfully opened
                if not video_interface.isOpened():
                    yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH + b'\r\n')
                    yield b'--frame--\r\n'
                    BACKEND_LOGGER.info("The kvm interface is not opening, closing the stream.")
                    break
        except GeneratorExit:
            BACKEND_LOGGER.error("Exiting the generator for browser screenshot.")
        except Exception:
            BACKEND_LOGGER.error("Exiting the generator function for browser screenshot due to general exception.")
        finally:
            BACKEND_LOGGER.info("Closing connection.")

    def screenshot(self, user: str, session_id: str) -> cv2.typing.MatLike:
        session = self.sessions.get(user, {}).get(session_id, None)
        if session is None:
            return cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
        return session.web_agent.screenshot or cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
