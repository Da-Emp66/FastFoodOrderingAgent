import asyncio
import enum
import json
import logging
import os
from pathlib import Path
import time
import traceback
from typing import Any, Dict, List, Optional, Union

import cv2
import litellm
from pydantic import BaseModel, Field
import websockets

from core.utils import (
    ConstrainedToolCaller,
    DSPyToolCaller,
    extract_final_message_content,
    from_config,
    populate_environment_specifications,
)
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
    ordering_mode: Optional[str] = None
    """The ordering mode: 'GUI' for AI agent, 'API-Wendys' or 'API-McDonalds' for hardcoded script ordering."""

class SessionManagerToolCallResult(BaseModel):
    result: str
    """The result of the tool call."""
    session_id: Optional[str] = None
    """If a session was created for the first time by this tool call, the session_id is returned. Otherwise, null."""

class SessionManagerChatResult(BaseModel):
    response: str
    """The LLM's response to the user's query."""
    session_id: Optional[str] = None
    """If there is a session created for the first time during this chat, the session_id is returned. Otherwise, null."""

class FoodOrDrinkItem(BaseModel):
    official_name: str
    special_instructions: Optional[str] = None

class ObjectiveSpecification(BaseModel):
    objective: str = Field(alias="objective")
    order: List[FoodOrDrinkItem] = []

class Session(BaseModel):
    user: str
    session_id: str
    objective_spec: ObjectiveSpecification

class CompletionStatus(enum.Enum):
    IN_PROGRESS = "in_progress"
    DONE = "done"

class SessionCompletionStatus(BaseModel):
    state: CompletionStatus
    items_ordered: List[FoodOrDrinkItem] = []

class SessionManagerResponseConfiguration(BaseModel):
    response_system_prompt: str = """You are a helpful assistant who specializes in helping users place food orders at restaurants nearby. Respond to the user based on the user's request. 
    For example, if the user asks for help finding a restaurant, say something like "Okay, I will help you look for a restaurant nearby." 
    If the user asks for help placing an order, say "I will work to schedule an order" at the restaurant of their choice."""
    max_tokens: int = 200

class SessionManagerConfiguration(BaseModel):
    response: SessionManagerResponseConfiguration = SessionManagerResponseConfiguration()
    tool_mode: ToolModes = ToolModes.Constrained
    tools: Optional[Dict[str, Any]] = None
    web_agent_spec: Dict[str, Any] = {}

class SessionManager:
    def __init__(self, configuration: Union[SessionManagerConfiguration, Any]):
        self.configuration: SessionManagerConfiguration = from_config(configuration, SessionManagerConfiguration)
        match self.configuration.tool_mode:
            case ToolModes.Constrained: self.tool_caller = ConstrainedToolCaller(self.configuration.tools)
            case ToolModes.DSPy: self.tool_caller = DSPyToolCaller(self.configuration.tools)
            case _: self.tool_caller = None
        
        # Outer key is user, inner key is session_id
        self.sessions: Dict[str, Dict[str, Session]] = {}
        
        # Single-user-per-instance lock
        self.active_user: Optional[str] = None  # Currently locked user
        self.last_activity: Optional[float] = None  # Timestamp of last activity
    
    async def __call__(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
        # Check if using API mode (hardcoded scripts)
        if prompt.ordering_mode and prompt.ordering_mode.startswith("API-"):
            return await self.handle_api_ordering(prompt)

        # Otherwise use GUI mode (current AI agent behavior)
        return await self.handle_gui_ordering(prompt)

    async def handle_gui_ordering(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
        """Handle ordering using the AI agent (GUI mode)"""
        # Check and enforce single-user-per-instance lock
        current_time = time.time()
        TIMEOUT = 3600  # 1 hour timeout
        
        # Release lock if timeout expired
        if self.active_user and self.last_activity and (current_time - self.last_activity > TIMEOUT):
            BACKEND_LOGGER.info(f"Lock timeout expired for user {self.active_user}")
            self.active_user = None
        
        # Check if instance is locked by another user
        if self.active_user and self.active_user != prompt.user:
            BACKEND_LOGGER.warning(f"User {prompt.user} attempted to access instance locked by {self.active_user}")
            return SessionManagerChatResult(
                response=f"This instance is currently in use by another user. Please try again later or use a different instance.",
                session_id=None
            )
        
        # Acquire lock for this user
        if not self.active_user:
            BACKEND_LOGGER.info(f"User {prompt.user} acquired instance lock")
        self.active_user = prompt.user
        self.last_activity = current_time
        
        session_id = None
        await self.tool_caller.initialize_tools()
        # Determine what to do and inform the user
        response = litellm.completion(
            os.getenv("MODEL"),
            messages=[
                {"content": self.configuration.response.response_system_prompt, "role": "system"},
                {"content": prompt.prompt, "role": "user"},
            ],
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            max_tokens=self.configuration.response.max_tokens,
        ).choices[0].message.content
        response = extract_final_message_content(response)
        # Determine and call the tool
        try:
            generated_tool = await self.tool_caller.determine_tool(
                user=prompt.user,
                prompt=prompt.prompt,
                response=response,
                session_id=prompt.session_id,
                current_geolocation=prompt.current_geolocation,
            )
        except Exception as e:
            generated_tool = None
            result = f"Failed to call tool: {e}"
            print(result)

        if generated_tool is not None:
            try:
                result = await self.tool_caller.call_tool(generated_tool)
                session_id = json.loads(result).get("session_id", None)
            except Exception as e:
                result = f"Failed to call tool {generated_tool.spec}: {e}"
                print(result)

        return SessionManagerChatResult(
            response=response,
            session_id=session_id,
        )

    async def handle_api_ordering(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
        """Handle ordering using hardcoded scripts (API mode)"""
        # Extract food item from the prompt
        food_item = self.extract_food_item(prompt.prompt)

        # Determine which script to call
        if prompt.ordering_mode == "API-Wendys":
            # TODO: implement wendys_script
            # result = await call_wendys_script(food_item)
            response = f"API Mode: Would order '{food_item}' from Wendy's (script not implemented yet)"
        elif prompt.ordering_mode == "API-McDonalds":
            # TODO: implement mcdonalds_script
            # result = await call_mcdonalds_script(food_item)
            response = f"API Mode: Would order '{food_item}' from McDonald's (script not implemented yet)"
        else:
            response = f"Unknown ordering mode: {prompt.ordering_mode}"

        return SessionManagerChatResult(
            response=response,
            session_id=prompt.session_id,
        )

    def extract_food_item(self, prompt: str) -> str:
        """Extract food item name from user prompt using keyword matching"""
        # List of known menu items (can be expanded)
        KNOWN_ITEMS = [
            # Wendy's items
            "Baconator", "Dave's Single", "Dave's Double", "Dave's Triple",
            "Junior Cheeseburger", "Spicy Chicken Sandwich", "Asiago Ranch Chicken Club",
            "Classic Chicken Sandwich", "Homestyle Chicken Sandwich",
            "Son of Baconator", "Pretzel Bacon Pub", "Big Bacon Classic",

            # McDonald's items
            "Big Mac", "Quarter Pounder", "McChicken", "Filet-O-Fish",
            "McDouble", "Cheeseburger", "Hamburger", "Chicken McNuggets",
            "McFlurry", "Happy Meal", "Egg McMuffin", "Sausage McMuffin",
        ]

        # Check for exact matches (case insensitive)
        prompt_lower = prompt.lower()
        for item in KNOWN_ITEMS:
            if item.lower() in prompt_lower:
                return item

        # Fallback: return the entire prompt (let the script handle it)
        return prompt.strip()
    
    async def browser_screenshot_generator(self, user: str, session_id: str):
        container_spec = populate_environment_specifications(
            self.configuration.web_agent_spec,
            _DYN_WEB_AGENT_USER=user,
            _DYN_WEB_AGENT_SESSION_ID=session_id,
        )
        session_url = f"ws://{container_spec['name']}:9000/active-session/view" # TODO: Don't hardcode this port
        print(f"Connecting to `{session_url}`...")

        while True:
            try:
                async with websockets.connect(session_url, open_timeout=10.0) as websocket:
                    print(f"Connected to {session_url}")

                    while True:
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                            if not response:
                                # If empty, send placeholder frame
                                frame_bytes = cv2.imencode(
                                    ".jpeg",
                                    cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
                                )[1].tobytes()
                            else:
                                frame_bytes = response

                            yield (
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n\r\n" +
                                frame_bytes +
                                b"\r\n"
                            )

                        except asyncio.TimeoutError:
                            print(f"Timeout waiting for frame from {session_url}")
                            break  # reconnect

                        except websockets.ConnectionClosed:
                            print(f"WebSocket closed, reconnecting to {session_url}")
                            break

                        await asyncio.sleep(float(os.getenv("BROWSER_SCREENSHOT_WEBSOCKET_DELAY")))

            except Exception as e:
                BACKEND_LOGGER.error(f"Error in screenshot generator: {e}\n{traceback.format_exc()}")

            finally:
                BACKEND_LOGGER.info(f"Closing {user} websocket connection to session {session_id}")

            # Short delay before attempting reconnect
            await asyncio.sleep(float(os.getenv("BROWSER_SCREENSHOT_WEBSOCKET_RETRY_DELAY")))

    # def screenshot(self, user: str, session_id: str) -> cv2.typing.MatLike:
    #     session = self.sessions.get(user, {}).get(session_id, None)
    #     if session is None:
    #         return cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
    #     return session.web_agent.screenshot or cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)

    async def create_session(user: str, session_id: str, objective: str):
        raise NotImplementedError()

    async def update_session(user: str, session_id: str, objective: str):
        raise NotImplementedError()
    