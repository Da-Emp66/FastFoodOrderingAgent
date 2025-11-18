import argparse
import asyncio
import os
import threading
import time
import cv2
from dotenv import find_dotenv, load_dotenv
import dspy
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from core.session.session import Session, SessionCompletionStatus

# Load environment variables
dotenv_to_use = find_dotenv()
if dotenv_to_use: print(f"Using .env at path: `{dotenv_to_use}`")
load_dotenv(dotenv_to_use)

import shared
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # List of allowed origins
    allow_credentials=True, # Allow cookies and credentials
    allow_methods=["*"], # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)

class BrowserClickCoordinates(BaseModel):
    x: float
    """Relative X coordinate (0-1 range)"""
    y: float
    """Relative Y coordinate (0-1 range)"""

class BrowserTextInput(BaseModel):
    text: str
    """Text to type into the currently focused element"""

@app.websocket("/active-session/view")
async def stream_browser(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            image_path = (
                shared.CURRENT_SCREENSHOT_PATH
                if os.path.exists(shared.CURRENT_SCREENSHOT_PATH)
                else shared.NO_BROWSER_SCREENSHOT_PLACEHOLDER_PATH
            )
            success, jpeg = cv2.imencode(".jpeg", cv2.imread(image_path))
            if success:
                await websocket.send_bytes(jpeg.tobytes())
            await asyncio.sleep(float(os.getenv("BROWSER_SCREENSHOT_WEBSOCKET_DELAY")))
    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket closed.")

@app.get("/active-session/status")
def get_status():
    return SessionCompletionStatus(
        status=shared.this_session.status.state,
        items_ordered=shared.this_session.status.items_ordered,
    )

@app.put("/active-session")
def update_overall_goal(session: Session):
    assert session.user == shared.this_session.original_spec.user
    assert session.session_id == shared.this_session.original_spec.session_id
    shared.this_session.current_spec.objective_spec.objective = session.objective_spec.objective
    return Response(status_code=200)

@app.post("/active-session/click")
async def handle_click(coordinates: BrowserClickCoordinates):
    """Handle a user click at relative coordinates (0-1 range)."""
    try:
        # Get the browser agent's tool caller
        agent = shared.this_session.web_agent

        # Get viewport size from the page
        page = agent.tool_caller.page if hasattr(agent.tool_caller, 'page') else None
        if page is None:
            return Response(status_code=400, content="Browser page not available")

        # Convert relative coordinates to absolute pixel coordinates
        viewport_width = page._page.viewport_size['width']
        viewport_height = page._page.viewport_size['height']
        abs_x = coordinates.x * viewport_width
        abs_y = coordinates.y * viewport_height

        # Perform the click
        await page.mouse.click(abs_x, abs_y)

        return Response(status_code=200)
    except Exception as e:
        print(f"Error handling click: {e}")
        return Response(status_code=500, content=str(e))

@app.post("/active-session/type")
async def handle_type(text_input: BrowserTextInput):
    """Type text into the currently focused element."""
    try:
        # Get the browser agent's tool caller
        agent = shared.this_session.web_agent

        # Get the page
        page = agent.tool_caller.page if hasattr(agent.tool_caller, 'page') else None
        if page is None:
            return Response(status_code=400, content="Browser page not available")

        # Type the text into the currently focused element
        await page.keyboard.type(text_input.text)

        return Response(status_code=200)
    except Exception as e:
        print(f"Error handling text input: {e}")
        return Response(status_code=500, content=str(e))

def main(args):
    print(f"Using MODEL=`{os.getenv('MODEL')}`", flush=True)
    print(f"Using OPENAI_BASE_URL=`{os.getenv('OPENAI_BASE_URL')}`", flush=True)
    print(f"Using OPENAI_API_KEY=`{os.getenv('OPENAI_API_KEY')}`", flush=True)

    lm = dspy.LM(
        os.getenv('MODEL'),
        api_base=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        model_type="chat",
    )
    dspy.settings.configure(lm=lm)

    print(f"🚀 Starting WebSocket server on {args.host}:{args.port}", flush=True)
    main_loop = threading.Thread(target=uvicorn.run, args=(app,), kwargs={"host": args.host, "port": args.port})
    main_loop.start()
    
    # Give the WebSocket server time to start up
    startup_delay = float(os.getenv("WEBSOCKET_STARTUP_DELAY", "2.0"))
    print(f"⏳ Waiting {startup_delay}s for WebSocket server to initialize...", flush=True)
    time.sleep(startup_delay)
    print(f"✅ WebSocket server ready at ws://{args.host}:{args.port}/active-session/view", flush=True)
    
    asyncio.run(shared.this_session())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    main(args)
