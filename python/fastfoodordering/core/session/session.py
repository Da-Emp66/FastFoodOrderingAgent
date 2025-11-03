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
    
    async def __call__(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
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

                        await asyncio.sleep(0.1)

            except Exception as e:
                BACKEND_LOGGER.error(f"Error in screenshot generator: {e}\n{traceback.format_exc()}")

            finally:
                BACKEND_LOGGER.info(f"Closing {user} websocket connection to session {session_id}")

            # Short delay before attempting reconnect
            await asyncio.sleep(1.0)


        # print(f"Connecting to `{session_url}/active-session/view`...")
        # # Loop until the client connection exist
        # while True:
        #     try:
        #         # Check if the camera capture is successfully opened
        #         async with websockets.connect(f"{session_url}/active-session/view", open_timeout=60.0) as websocket:
        #             # Wait for a response from the server
        #             response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
        #             if len(response) == 0:
        #                 yield (
        #                     b'--frame\r\n'
        #                     b'Content-Type: image/jpeg\r\n\r\n' +
        #                     cv2.imencode(".jpeg", cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH))[1].tobytes() +
        #                     b'\r\n'
        #                 )
        #             else:
        #                 yield (
        #                     b'--frame\r\n'
        #                     b'Content-Type: image/jpeg\r\n\r\n' +
        #                     response +
        #                     b'\r\n'
        #                 )
        #         # # yield b'--frame--\r\n'
        #         # break
        #     except Exception as e:
        #         BACKEND_LOGGER.error(f"{e} : {traceback.format_exc()}")
        #     finally:
        #         BACKEND_LOGGER.info(f"Closing {user} websocket connection to session with Session ID {session_id}.")
                
        #     time.sleep(0.1)




        # try:
        #     container_spec = populate_environment_specifications(
        #         self.configuration.web_agent_spec,
        #         _DYN_WEB_AGENT_USER=user,
        #         _DYN_WEB_AGENT_SESSION_ID=session_id,
        #     )
        #     session_url = f"http://{container_spec['name']}:9000" # TODO: Don't hardcode this port
        #     # Loop until the client connection exist
        #     while True:
        #         # Check if the camera capture is successfully opened
        #         async with websockets.connect(f"{session_url}/active-session/view") as websocket:
        #             # Wait for a response from the server
        #             response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
        #             if len(response) == 0:
        #                 yield (
        #                     b'--frame\r\n'
        #                     b'Content-Type: image/jpeg\r\n\r\n' +
        #                     cv2.imencode(".jpeg", cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH))[1].tobytes() +
        #                     b'\r\n'
        #                 )
        #             else:
        #                 yield (
        #                     b'--frame\r\n'
        #                     b'Content-Type: image/jpeg\r\n\r\n' +
        #                     response +
        #                     b'\r\n'
        #                 )
        #         # yield b'--frame--\r\n'
        #         break
        # except GeneratorExit:
        #     BACKEND_LOGGER.error("Exiting the generator for browser screenshot.")
        # except Exception:
        #     BACKEND_LOGGER.error("Exiting the generator function for browser screenshot due to general exception.")
        # finally:
        #     BACKEND_LOGGER.info("Closing connection.")

    # def screenshot(self, user: str, session_id: str) -> cv2.typing.MatLike:
    #     session = self.sessions.get(user, {}).get(session_id, None)
    #     if session is None:
    #         return cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
    #     return session.web_agent.screenshot or cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)

    async def create_session(user: str, session_id: str, objective: str):
        raise NotImplementedError()

    async def update_session(user: str, session_id: str, objective: str):
        raise NotImplementedError()
    