import asyncio
import enum
import json
import logging
import math
import os
from pathlib import Path
import traceback
from typing import Any, Dict, List, Literal, Optional, Union
import uuid

import cv2
import litellm
from pydantic import BaseModel, Field
import websockets
import yaml

from core.utils import (
    BaseModelJSONEncoder,
    BaseModelYAMLDumper,
    ConstrainedToolCaller,
    DSPyToolCaller,
    extract_final_message_content,
    from_config,
    populate_environment_specifications,
    remove_special_characters,
)
from core.web.tool_calling.interface import ToolModes
from core.session.session_utils import get_restaurant_locations_nearby

BACKEND_LOGGER: logging.Logger = logging.getLogger("BACKEND_LOGGER")
VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH: str = Path(__file__).parent.parent / "assets" / "video_placeholder.jpg"

class BrowserGeoLocation(BaseModel):
    latitude: float
    """User location latitude component."""
    longitude: float
    """User location longitude component."""
    accuracy: float
    """A measure of how accurate the (latitude, longitude) coordinate is, in meters."""

DEFAULT_UI_UUID = uuid.uuid4()
class SessionManagerPrompt(BaseModel):
    user: str
    """Username, user ID, or email."""
    prompt: str
    """The user's query, question, or request. Will be sent to the SessionManager to decide what to do."""
    ui_id: str = DEFAULT_UI_UUID
    """Randomly generated ID by the UI. Defaults to a UUID for the class, but needs to be provided by the UI if the user is to be able to have multiple sessions."""
    session_id: Optional[str] = None
    """If the user has a session open and this query is for updating that session, pass the session_id returned when you first created the session."""
    current_geolocation: Optional[BrowserGeoLocation] = None
    """The user's current geolocation. To be used for the browser proxied location on session launch."""
    ordering_mode: Optional[str] = None
    """The ordering mode: i.e., ~GUI for GUI-based agent or ~API for API-based ordering method."""

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
    official_food_item_name: str
    special_instructions: Optional[str] = None

class OrderDetails(BaseModel):
    restaurant_or_food_chain_name: Optional[str] = None
    food_items_to_order: Optional[List[FoodOrDrinkItem]] = None
    pickup_or_delivery: Optional[Literal['pickup', 'delivery']] = None
    restaurant_address: Optional[str] = None
    delivery_address_if_for_delivery: Optional[str] = None

    def incomplete_fields(self) -> List[str]:
        required_fields = [
            "restaurant_or_food_chain_name",
            "food_items_to_order",
            "pickup_or_delivery",
            "restaurant_address",
        ]
        conditional_fields = [
            "delivery_address_if_for_delivery",
        ]

        incomplete = []
        for field in required_fields:
            if self.field_not_provided(getattr(self, field)):
                incomplete.append(field)
        
        for field in conditional_fields:
            if field == "delivery_address_if_for_delivery" \
                and self.pickup_or_delivery == "delivery" \
                and self.field_not_provided(getattr(self, field)):
                incomplete.append(field)
        
        return list(incomplete)
    
    def field_not_provided(self, field: Any) -> bool:
        if field is None or (
            isinstance(field, str) and
            ('None' in field or 
            'none' in field or 
            'null' in field or 
            'not_provided' in field)
        ):
            return True
        return False


class ObjectiveSpecification(BaseModel):
    objective: str = Field(alias="objective")
    extracted_order_details: OrderDetails = OrderDetails()

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

class SessionManagerExtractionConfiguration(BaseModel):
    extraction_system_prompt: str
    force_current_order_detail_preservation: bool = False

class SessionManagerPlanConfiguration(BaseModel):
    plan_system_prompt: str
    max_tokens: int = 200
    enabled: bool = True

class SessionManagerResponseConfiguration(BaseModel):
    response_incomplete_restaurant_location_system_prompt: str
    response_incomplete_fields_system_prompt: str
    response_system_prompt: str
    max_tokens: int = 200

class SessionManagerConfiguration(BaseModel):
    extraction: SessionManagerExtractionConfiguration
    plan: SessionManagerPlanConfiguration
    response: SessionManagerResponseConfiguration
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
        # Outer key is user, inner key is UI's ID
        self.order_details: Dict[str, Dict[str, OrderDetails]] = {}
        self.order_chat_history: Dict[str, Dict[str, str]] = {}
    
    async def __call__(self, prompt: SessionManagerPrompt) -> SessionManagerChatResult:
        from core.session.session_tools import (
            cancel_ordering_session,
            start_ordering_session,
            update_ordering_session,
        )
        ui_id = (prompt.ui_id or DEFAULT_UI_UUID)
        if self.tool_caller is not None and not self.tool_caller.initialized:
            await self.tool_caller.initialize_tools()
        current_history = json.dumps(
            self.order_chat_history.get(prompt.user, {}).get(ui_id, None),
            indent=2,
            cls=BaseModelJSONEncoder,
        )

        # Describe what the user wants and how it relates to
        # starting, updating, or canceling an order
        if self.configuration.plan.enabled:
            plan = litellm.completion(
                os.getenv("MODEL"),
                messages=[
                    {
                        "content": self.configuration.plan.plan_system_prompt.replace(
                                "{tool_options}",
                                yaml.safe_dump(list(self.tool_caller.tools.keys()))
                            ) \
                            .replace("{history}", current_history),
                        "role": "system"
                    },
                    {"content": prompt.prompt, "role": "user"},
                ],
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
                max_tokens=self.configuration.response.max_tokens,
            ).choices[0].message.content

        # Determine the tool
        result = None
        try:
            print(f"Plan: {plan}")
            generated_tool = await self.tool_caller.determine_tool(
                user=prompt.user,
                prompt=prompt.prompt,
                response=plan,
                session_id=prompt.session_id,
                current_geolocation=prompt.current_geolocation,
                history=current_history,
                skip_args=True,
            )
        except Exception as e:
            generated_tool = None
            result = f"Failed to determine tool: {e}"
            print(result)

        session_id = None
        user_prompt_for_final_response = ""
        if generated_tool is not None \
            and generated_tool.spec.tool is not None \
            and generated_tool.spec.tool != "null_function":

            # Preprocess
            if generated_tool.spec.tool == "start_ordering_session" and prompt.session_id is not None:
                    generated_tool.spec.tool = "update_ordering_session"
            elif generated_tool.spec.tool == "update_ordering_session" and prompt.session_id is None:
                    generated_tool.spec.tool = "start_ordering_session"
            
            # Validate order details before starting and/or updating the session
            current_known_order_details = self.order_details.get(prompt.user, {}).get(ui_id, OrderDetails())
            if generated_tool.spec.tool == "start_ordering_session" \
                or generated_tool.spec.tool == "update_ordering_session":
                if self.order_details.get(prompt.user, None) is None: self.order_details[prompt.user] = {}
                current_known_order_details = await self.extract_order_details(
                    prompt=self.configuration.extraction.extraction_system_prompt \
                        .replace("{user_prompt}", prompt.prompt) \
                        .replace("{history}", current_history),
                    current_known_order_details=current_known_order_details,
                    force_current_order_detail_preservation=self.configuration.extraction.force_current_order_detail_preservation,
                )
                self.order_details[prompt.user][ui_id] = current_known_order_details
                print(f"Updating extracted order details for user {prompt.user} to: {json.dumps(current_known_order_details, indent=2, cls=BaseModelJSONEncoder)}")
                if prompt.current_geolocation is not None \
                    and current_known_order_details.restaurant_or_food_chain_name is not None \
                    and current_known_order_details.restaurant_address is None:
                    restaurant_location_options = get_restaurant_locations_nearby(
                        latitude=prompt.current_geolocation.latitude,
                        longitude=prompt.current_geolocation.longitude,
                        restaurant_name_or_food_chain=current_known_order_details.restaurant_or_food_chain_name,
                    )
                    if type(restaurant_location_options) == list and len(restaurant_location_options) > 0:
                        # Query the user with these locations as options
                        response_incomplete_restaurant_location = litellm.completion(
                            os.getenv("MODEL"),
                            messages=[
                                {
                                    "content": self.configuration.response.response_incomplete_restaurant_location_system_prompt \
                                        .replace("{history}", current_history) \
                                        .replace("{user_prompt}", prompt.prompt),
                                    "role": "system"
                                },
                                {
                                    "content": "Based on the current user's prompt and your chat history with the user, mention that you have to first get the location of the restaurant they want their order to be placed at.\n" \
                                                f"Query the user for their preferred restaurant location out of these three options. Make sure to include the addresses and distances (up to 2 decimal points) of these options (but not the latitude and longitude) in your response:\n{yaml.dump(restaurant_location_options[:3], Dumper=BaseModelYAMLDumper)}",
                                    "role": "user",
                                },
                            ],
                            api_key=os.getenv("OPENAI_API_KEY"),
                            base_url=os.getenv("OPENAI_BASE_URL"),
                            max_tokens=self.configuration.response.max_tokens,
                        ).choices[0].message.content

                        if self.order_chat_history.get(prompt.user, None) is None: self.order_chat_history[prompt.user] = {}
                        self.order_chat_history[prompt.user][ui_id] = self.order_chat_history[prompt.user].get(ui_id, []) + [
                            {"user": prompt.prompt},
                            {"assistant": response_incomplete_restaurant_location},
                        ]
                        return SessionManagerChatResult(
                            response=extract_final_message_content(response_incomplete_restaurant_location),
                        )

                self.order_details[prompt.user][ui_id] = current_known_order_details
                incomplete_fields = current_known_order_details.incomplete_fields()
                if len(incomplete_fields) > 0:
                    print(f"Current known fields: {current_known_order_details.model_dump_json(indent=2)}")
                    print(f"Fields identified as incomplete: {incomplete_fields}")
                    response_incomplete_fields = litellm.completion(
                        os.getenv("MODEL"),
                        messages=[
                            {"content": self.configuration.response.response_incomplete_fields_system_prompt, "role": "system"},
                            {"content": f"User's prompt was: '{prompt.prompt}'\nRemaining items to ask the user for:\n{yaml.safe_dump(incomplete_fields)}", "role": "user"},
                        ],
                        api_key=os.getenv("OPENAI_API_KEY"),
                        base_url=os.getenv("OPENAI_BASE_URL"),
                        max_tokens=self.configuration.response.max_tokens,
                    ).choices[0].message.content

                    if self.order_chat_history.get(prompt.user, None) is None: self.order_chat_history[prompt.user] = {}
                    self.order_chat_history[prompt.user][ui_id] = self.order_chat_history[prompt.user].get(ui_id, []) + [
                        {"user": prompt.prompt},
                        {"assistant": response_incomplete_fields},
                    ]
                    return SessionManagerChatResult(
                        response=extract_final_message_content(response_incomplete_fields),
                    )

            if generated_tool.spec.tool == "start_ordering_session":
                print("Starting session...")
                result = await start_ordering_session(
                    exact_user_query=prompt.prompt,
                    user=prompt.user,
                    current_geolocation=prompt.current_geolocation,
                    session_mode=prompt.ordering_mode,
                    order_details=current_known_order_details,
                )
            elif generated_tool.spec.tool == "update_ordering_session":
                print("Updating session...")
                result = await update_ordering_session(
                    user=prompt.user,
                    session_id=prompt.session_id,
                    updated_objective_spec=ObjectiveSpecification(
                        objective=prompt.prompt,
                        extracted_order_details=current_known_order_details,
                    )
                )
            elif generated_tool.spec.tool == "cancel_ordering_session":
                print("Canceling session...")
                result = await cancel_ordering_session(
                    user=prompt.user,
                    session_id=prompt.session_id,
                )
            else:
                result = "No function called."
            
            if generated_tool.spec.tool == "start_ordering_session":
                try:
                    session_id = json.loads(result).get("session_id", None)
                except json.JSONDecodeError as e:
                    result = f"Failed to parse tool result as JSON {generated_tool.spec}: {e}"
                    print(result)
                except Exception as e:
                    result = f"Failed to call tool {generated_tool.spec}: {e}"
                    print(result)
            
            user_prompt_for_final_response = f"User's prompt was: '{prompt.prompt}'\nYour tool call was: '{generated_tool.spec.model_dump_json(indent=2)}'\nThat tool's result was: '{result}'\n"
        else:
            user_prompt_for_final_response = f"User's prompt was: '{prompt.prompt}'\nYou did not call a tool, so simply respond according to the user's prompt.\n"

        print(f"User prompt for final response: {user_prompt_for_final_response}")
        response = litellm.completion(
            os.getenv("MODEL"),
            messages=[
                {
                    "content": self.configuration.response.response_system_prompt.replace("{history}", current_history),
                    "role": "system",
                },
                {"content": user_prompt_for_final_response, "role": "user"},
            ],
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            max_tokens=self.configuration.response.max_tokens,
        ).choices[0].message.content
        
        if self.order_chat_history.get(prompt.user, None) is None: self.order_chat_history[prompt.user] = {}
        self.order_chat_history[prompt.user][ui_id] = self.order_chat_history[prompt.user].get(ui_id, []) + [
            {"user": prompt.prompt},
            {"assistant": response},
        ]
        return SessionManagerChatResult(
            response=extract_final_message_content(response),
            session_id=session_id,
        )

    # def extract_food_item(self, prompt: str) -> str:
    #     """Extract food item name from user prompt using keyword matching"""
    #     # List of known menu items (can be expanded)
    #     KNOWN_ITEMS = [
    #         # Wendy's items
    #         "Baconator", "Dave's Single", "Dave's Double", "Dave's Triple",
    #         "Junior Cheeseburger", "Spicy Chicken Sandwich", "Asiago Ranch Chicken Club",
    #         "Classic Chicken Sandwich", "Homestyle Chicken Sandwich",
    #         "Son of Baconator", "Pretzel Bacon Pub", "Big Bacon Classic",

    #         # McDonald's items
    #         "Big Mac", "Quarter Pounder", "McChicken", "Filet-O-Fish",
    #         "McDouble", "Cheeseburger", "Hamburger", "Chicken McNuggets",
    #         "McFlurry", "Happy Meal", "Egg McMuffin", "Sausage McMuffin",
    #     ]

    #     # Check for exact matches (case insensitive)
    #     prompt_lower = prompt.lower()
    #     for item in KNOWN_ITEMS:
    #         if item.lower() in prompt_lower:
    #             return item

    #     # Fallback: return the entire prompt (let the script handle it)
    #     return prompt.strip()
    
    async def extract_order_details(self, prompt: str, current_known_order_details: OrderDetails, force_current_order_detail_preservation: bool = False) -> OrderDetails:
        if force_current_order_detail_preservation:
            extracted = self.tool_caller.extract_via_schema(
                prompt,
                schema_cls=OrderDetails,
                known_details=current_known_order_details.model_dump_json(indent=2),
            ).model_dump()
            for key, val in extracted.items():
                if val is not None:
                    setattr(current_known_order_details, key, val)
        else:
            current_known_order_details = self.tool_caller.extract_via_schema(
                prompt,
                schema_cls=OrderDetails,
                known_details=current_known_order_details.model_dump_json(indent=2),
            )
        # Postprocess
        if current_known_order_details.delivery_address_if_for_delivery is not None \
            and (current_known_order_details.pickup_or_delivery != 'delivery') and \
            current_known_order_details.restaurant_address is None:
            # Fix it if the model wrongly places restaurant_location in delivery address
            current_known_order_details.restaurant_address = current_known_order_details.delivery_address_if_for_delivery
        return current_known_order_details
    
    async def browser_screenshot_generator(self, user: str, session_id: str):
        user_without_special_characters = remove_special_characters(user)
        container_spec = populate_environment_specifications(
            self.configuration.web_agent_spec,
            _DYN_WEB_AGENT_USER=user_without_special_characters,
            _DYN_WEB_AGENT_SESSION_ID=session_id,
        )
        session_url = f"ws://{container_spec['name']}:9000/active-session/view" # TODO: Don't hardcode this port
        retry_count = 0
        max_retries = int(os.getenv("BROWSER_SCREENSHOT_MAX_RETRIES", "-1"))  # -1 means infinite
        
        BACKEND_LOGGER.info(f"[Session {session_id}] Initializing WebSocket connection to {session_url}")

        while max_retries == -1 or retry_count < max_retries:
            try:
                BACKEND_LOGGER.info(f"[Session {session_id}] Attempting WebSocket connection (attempt #{retry_count + 1})...")
                async with websockets.connect(session_url, open_timeout=10.0) as websocket:
                    BACKEND_LOGGER.info(f"[Session {session_id}] ✅ Successfully connected to {session_url}")
                    retry_count = 0  # Reset retry count on successful connection

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
                            BACKEND_LOGGER.warning(f"[Session {session_id}] Timeout waiting for frame from {session_url}, reconnecting...")
                            break  # reconnect

                        except websockets.ConnectionClosed:
                            BACKEND_LOGGER.warning(f"[Session {session_id}] WebSocket closed, reconnecting to {session_url}")
                            break

                        await asyncio.sleep(float(os.getenv("BROWSER_SCREENSHOT_WEBSOCKET_DELAY", "0.1")))

            except Exception as e:
                retry_count += 1
                error_type = type(e).__name__
                if "ConnectionRefusedError" in error_type or "111" in str(e):
                    BACKEND_LOGGER.warning(
                        f"[Session {session_id}] ⏳ WebSocket not ready yet (attempt #{retry_count}). "
                        f"Container may still be starting up. Retrying in 5s..."
                    )
                else:
                    BACKEND_LOGGER.error(
                        f"[Session {session_id}] ❌ WebSocket error (attempt #{retry_count}): {error_type}: {e}\n"
                        f"{traceback.format_exc()}"
                    )

            finally:
                if max_retries != -1 and retry_count >= max_retries:
                    BACKEND_LOGGER.error(f"[Session {session_id}] Max retries ({max_retries}) reached. Giving up.")
                    break

            # Short delay before attempting reconnect
            await asyncio.sleep(float(os.getenv("BROWSER_SCREENSHOT_WEBSOCKET_RETRY_DELAY", "5.0")))

    # def screenshot(self, user: str, session_id: str) -> cv2.typing.MatLike:
    #     session = self.sessions.get(user, {}).get(session_id, None)
    #     if session is None:
    #         return cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)
    #     return session.web_agent.screenshot or cv2.imread(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH)

    async def create_session(self, user: str, session_id: str, objective: str):
        raise NotImplementedError()
        # return await start_session(objective, user, )

    async def update_session(self, user: str, session_id: str, objective: str):
        raise NotImplementedError()
    
    async def validate_order_details(self):
        pass
