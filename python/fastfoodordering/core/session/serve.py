import argparse
import atexit
import base64
import os
from pathlib import Path
import tempfile
from typing import List, Optional
import uuid
import cv2
import docker
from dotenv import find_dotenv, load_dotenv
import dspy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import litellm
from pydantic import BaseModel
from stagehand.agent.agent import MODEL_TO_CLIENT_CLASS_MAP, OpenAICUAClient
import uvicorn
import yaml

from core.session.session import (
    VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH,
    SessionManager,
    SessionManagerChatResult,
    SessionManagerPrompt,
)

# Load environment variables
dotenv_to_use = find_dotenv()
if dotenv_to_use: print(f"Using .env at path: `{dotenv_to_use}`")
load_dotenv(dotenv_to_use)

# Update how litellm interacts by default
litellm.api_base = os.getenv("OPENAI_BASE_URL")
MODEL_TO_CLIENT_CLASS_MAP.update({litellm.api_base: lambda *args, **kwargs: OpenAICUAClient(*args, **kwargs)})

import shared
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # List of allowed origins
    allow_credentials=True, # Allow cookies and credentials
    allow_methods=["*"], # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)

class SimplePrompt(BaseModel):
    prompt: str
    """The user's query, question, or request. Will be sent to the UserProxyAgent to decide what to do."""

class SimpleResponse(BaseModel):
    response: Optional[str] = None

class SessionObjective(BaseModel):
    objective: str

class SessionId(BaseModel):
    session_id: str

class BrowserBase64Screenshot(BaseModel):
    b64_encoded_image: str

@app.post("/chat")
def chat(prompt: SimplePrompt) -> SimpleResponse:
    """Obtain a basic response from the LLM."""
    response = litellm.completion(
        os.getenv("MODEL"),
        messages=[{"content": prompt.prompt, "role": "user"}],
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        max_tokens=200,
    )
    try:
        return SimpleResponse(response=response.choices.pop(0).message.content)
    except IndexError:
        return SimpleResponse(response=None)

@app.post("/{user}/sessions/chat")
async def session_manager_chat(prompt: SessionManagerPrompt) -> SessionManagerChatResult:
    return await shared.session_manager(prompt)

@app.get("/{user}/sessions")
def get_sessions(user: str) -> List[str]:
    return list(shared.session_manager.sessions.get(user, {}).keys())

@app.post("/{user}/sessions")
async def post_sessions_auto_create_id(user: str, objective: SessionObjective) -> SessionId:
    return SessionId(session_id=(await shared.session_manager.create_session(user, str(uuid.uuid4()), objective.objective)))

@app.put("/{user}/sessions/{session_id}")
async def put_sessions(user: str, session_id: str, objective: SessionObjective) -> SessionId:
    if shared.session_manager.sessions.get(user, {}).get(session_id, None) is None:
        return SessionId(session_id=(await shared.session_manager.create_session(user, session_id, objective.objective)))
    else:
        return SessionId(session_id=(await shared.session_manager.update_session(user, session_id, objective.objective)))

@app.get("/{user}/sessions/{session_id}/screenshot")
def get_screenshot(user: str, session_id: str) -> BrowserBase64Screenshot:
    screenshot = shared.session_manager.screenshot(user, session_id)
    with tempfile.NamedTemporaryFile("wb+") as named_temporary_file:
        cv2.imwrite(named_temporary_file, screenshot)
        named_temporary_file.seek(0)
        file = named_temporary_file.read()
        named_temporary_file.close()
    return BrowserBase64Screenshot(b64_encoded_image=f"data:image/png;base64,{base64.b64encode(file).decode('utf-8')}")

@app.get("/{user}/sessions/{session_id}/screenshot/stream")
def stream_screenshot(user: str, session_id: str): # -> Union[StreamingResponse, FileResponse]
    try:
        # Return a StreamingResponse that continuously streams frames
        return StreamingResponse(
            shared.session_manager.browser_screenshot_generator(user, session_id),
            media_type="multipart/x-mixed-replace;boundary=frame",
        )
    # If an exception occurs (e.g., video capture error)
    # Return an jpeg image response
    except Exception:
        return FileResponse(VIDEO_CONNECTION_PLACEHOLDER_FILE_PATH, media_type="image/jpeg")

def on_exit():
    print("Performing exit sequence...")
    container_ids = list(map(lambda x: x.id, shared.session_ids_to_containers.values()))
    print(f"Containers include:\n{yaml.safe_dump(container_ids)}")
    for container_id in container_ids:
        print(f"Stopping and removing container {container_id}...")
        container = shared.docker_client.containers.get(container_id)
        container.stop()
        container.remove()
        print(f"Stopped and removed container {container_id}.")
    print("Exit sequence stopped all session containers.")

def main(args):
    atexit.register(on_exit)
    lm = dspy.LM(
        os.getenv("OPENAI_BASE_URL"),
        api_base=os.getenv("MODEL_SERVER"),
        api_key=os.getenv("OPENAI_API_KEY"),
        model_type="chat",
    )
    dspy.settings.configure(lm=lm)

    uvicorn.run(
        app=app,
        host=args.host,
        port=args.port,
        workers=1,
    )
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    main(args)
