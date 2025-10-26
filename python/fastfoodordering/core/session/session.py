import asyncio
import enum
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2
import docker
import litellm
from pydantic import BaseModel
import websockets

from core.utils import ConstrainedToolCaller, DSPyToolCaller, from_config
from core.web.tool_calling.interface import ToolModes

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

class FoodOrDrinkItem(BaseModel):
    official_name: str
    special_instructions: Optional[str] = None

class Session(BaseModel):
    user: str
    session_id: str
    objective: str
    order: List[FoodOrDrinkItem] = []

class CompletionStatus(enum.Enum):
    IN_PROGRESS = "in_progress"
    DONE = "done"

class SessionCompletionStatus(BaseModel):
    status: CompletionStatus
    items_ordered: List[FoodOrDrinkItem] = []

class SessionManagerConfiguration(BaseModel):
    response_system_prompt: str = """You are a helpful assistant who specializes in helping users place food orders at restaurants nearby. Respond to the user based on the user's request. 
    For example, if the user asks for help finding a restaurant, say something like "Okay, I will help you look for a restaurant nearby." 
    If the user asks for help placing an order, say "I will work to schedule an order" at the restaurant of their choice."""
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None

class SessionManager:
    def __init__(self, configuration: Union[SessionManagerConfiguration, Any]):
        self.configuration: SessionManagerConfiguration = from_config(configuration, SessionManagerConfiguration)
        match self.configuration.tool_mode:
            case ToolModes.Constrained: self.tool_caller = ConstrainedToolCaller(self.configuration.tools)
            case ToolModes.DSPy: self.tool_caller = DSPyToolCaller(self.configuration.tools)
            case _: self.tool_caller = None
        
        # Outer key is user, inner key is session_id
        self.sessions: Dict[str, Dict[str, Session]] = {}
        self.client = docker.from_env()
    
    async def __call__(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
        await self.tool_caller.initialize_tools()
        # Determine what to do and inform the user
        response = litellm.completion(
            os.getenv("OPENAI_BASE_URL"),
            messages=[
                {"content": self.configuration.response_system_prompt, "role": "system"},
                {"content": prompt.prompt, "role": "user"},
            ],
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            max_tokens=200,
        )
        # Determine and call the tool
        tool_prediction_response, tool_call_result = await self.tool_caller.determine_and_call_tools(
            user=prompt.user,
            prompt=prompt.prompt,
            response=response,
            session_id=prompt.session_id,
            current_geolocation=prompt.current_geolocation,
        )
        previous_tool_call = tool_prediction_response
        previous_tool_call_output = tool_call_result
        print(tool_call_result)
        return response
    
    async def browser_screenshot_generator(self, user: str, session_id: str):
        try:
            # Loop until the client connection exist
            while True:
                # Check if the camera capture is successfully opened
                async with websockets.connect(f"http://{user}-session-{session_id}/active-session/view") as websocket:
                    # Wait for a response from the server
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    if len(response) == 0:
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' +
                            cv2.imencode(".jpeg", cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH))[1].tobytes() +
                            b'\r\n'
                        )
                    else:
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' +
                            response +
                            b'\r\n'
                        )
                # yield b'--frame--\r\n'
                break
        except GeneratorExit:
            BACKEND_LOGGER.error("Exiting the generator for browser screenshot.")
        except Exception:
            BACKEND_LOGGER.error("Exiting the generator function for browser screenshot due to general exception.")
        finally:
            BACKEND_LOGGER.info("Closing connection.")

    # def screenshot(self, user: str, session_id: str) -> cv2.typing.MatLike:
    #     session = self.sessions.get(user, {}).get(session_id, None)
    #     if session is None:
    #         return cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
    #     return session.web_agent.screenshot or cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
