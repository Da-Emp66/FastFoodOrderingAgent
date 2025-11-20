import asyncio
import json
import os
import time
from typing import Literal
import Xlib.display
import cv2
from pyvirtualdisplay.display import Display
from stagehand import StagehandPage
from fastmcp import FastMCP
from core.utils import place_coordinate_on_image
from core.web.parser import get_item_by_label_number
import shared

# Default browser geolocation is Orlando
# Accuracy denotes coordinate accuracy in meters.
BROWSER_GEOLOCATION = json.loads(os.getenv("BROWSER_GEOLOCATION", '''{
    "latitude": 28.5383,
    "longitude": -81.3792,
    "accuracy": 100
}'''))
GLOBAL_BROWSER_LOAD_WAIT_SLEEP = 1.0
# Most recent click in exact pixelwise coordinates
MOST_RECENT_CLICK = None

page: StagehandPage = None
mcp = FastMCP("Custom Desktop MCP Server")

def get_viewport_size():
    import pyautogui
    try:
        # Get the screen resolution (width, height)
        screen_size = pyautogui.size()
        # Validate the result
        if not (isinstance(screen_size.width, int) and isinstance(screen_size.height, int)):
            raise ValueError("Invalid screen size returned.")
        return screen_size.width, screen_size.height
    except Exception as e:
        print(f"Error retrieving viewport size: {e}")
        return None, None
    
#####################################################################
### Tools for LLM
#####################################################################

@mcp.tool
async def navigate(url: str):
    global page
    print("In function call `navigate`...")
    try:
        await page.goto(url)
        await asyncio.sleep(0.1)
        await page._page.context.grant_permissions(["geolocation"])
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return "success"
    except Exception as e:
        return str(e)
    
@mcp.tool
async def scroll(direction: Literal["left", "right", "up", "down"], delta_pixels: float):
    global page
    # print("In function call `scroll`...")
    try:
        delta_x_pixels = 0.0
        delta_y_pixels = 0.0
        match direction:
            case "left": delta_x_pixels -= delta_pixels
            case "right": delta_x_pixels += delta_pixels
            case "down": delta_y_pixels += delta_pixels
            case "up": delta_y_pixels -= delta_pixels

        await page._page.mouse.wheel(delta_x_pixels, delta_y_pixels)
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return "success"
    except Exception as e:
        return str(e)

@mcp.tool
async def click_element_by_box_label_number(number: int):
    import pyautogui
    global page, MOST_RECENT_CLICK
    # print("In function call `click_by_box_label_number`...")

    try:
        item = get_item_by_label_number(number)
        if type(item) == str: return item
        viewport_width, viewport_height = get_viewport_size()
        center_x = ((item.bbox[0] + item.bbox[2]) / 2) * viewport_width
        center_y = ((item.bbox[1] + item.bbox[3]) / 2) * viewport_height
        pyautogui.moveTo(center_x, center_y)
        await asyncio.sleep(0.1)
        pyautogui.click(center_x, center_y)
        MOST_RECENT_CLICK = (center_x, center_y)
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return f"[✅] Success: Clicked element labeled {number} at ({center_x}, {center_y})"
    except Exception as e:
        return str(e)
    
@mcp.tool
async def type_text_by_box_label_number(number: int, text: str):  
    """
    Finds the element at the given coordinates (x, y)
    and fills it with the specified text.
    """
    import pyautogui
    global page, MOST_RECENT_CLICK
    # print("In function call `type_text_by_box_label_number`...")
    
    try:
        item = get_item_by_label_number(number)
        if type(item) == str: return item
        viewport_width, viewport_height = get_viewport_size()
        center_x = ((item.bbox[0] + item.bbox[2]) / 2) * viewport_width
        center_y = ((item.bbox[1] + item.bbox[3]) / 2) * viewport_height
        pyautogui.moveTo(center_x, center_y)
        await asyncio.sleep(0.1)
        pyautogui.click(center_x, center_y)
        await asyncio.sleep(0.1)
        pyautogui.typewrite(text, interval=0.05)
        await asyncio.sleep(0.1)
        pyautogui.press('enter')
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        MOST_RECENT_CLICK = center_x, center_y
        return f"[✅] Success: Filled element at ({center_x}, {center_y}) with text: {text}"
    except Exception as e:
        return str(e)

#####################################################################
### Tools required for integration, not necessarily given to LLM
#####################################################################

def run_screenshot() -> str:
    import pyautogui
    global MOST_RECENT_CLICK
    path = shared.CURRENT_SCREENSHOT_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pyautogui.screenshot(path)
    if MOST_RECENT_CLICK is not None:
        cv2.imwrite(path, place_coordinate_on_image(cv2.imread(path), coordinate=MOST_RECENT_CLICK))
    return path

@mcp.tool
async def screenshot():
    try:
        path = run_screenshot()
        return path
    except Exception as e:
        return str(e)

@mcp.tool
async def click_relative_coordinates(x: float, y: float):
    import pyautogui
    global MOST_RECENT_CLICK
    try:
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            viewport_width, viewport_height = get_viewport_size()
            exact_x = x * viewport_width
            exact_y = y * viewport_height
        else:
            exact_x = x
            exact_y = y
        pyautogui.click(exact_x, exact_y)
        MOST_RECENT_CLICK = (exact_x, exact_y)
        run_screenshot()
        return "success"
    except Exception as e:
        return str(e)

@mcp.tool
async def type_text_character_by_character(text_input: str):
    import pyautogui
    global MOST_RECENT_CLICK
    try:
        if MOST_RECENT_CLICK is not None:
            exact_x, exact_y = MOST_RECENT_CLICK
            pyautogui.click(exact_x, exact_y)
            await asyncio.sleep(0.1)
        pyautogui.typewrite(text_input, interval=0.05)
        run_screenshot()
        return "success"
    except Exception as e:
        return str(e)

async def init_globals_for_screenshot_only():
    print("INSIDE INIT GLOBALS FOR SCREENSHOT DESKTOP")
    disp = Display(visible=True, size=(1024 + 30, 768 + 150), backend="xvfb", use_xauth=True)
    disp.start()
    import pyautogui
    pyautogui._pyautogui_x11._display = Xlib.display.Display(os.environ['DISPLAY'])
    pyautogui.FAILSAFE = False
    print("INIT GLOBALS FOR SCREENSHOT DESKTOP COMPLETE")

async def init_globals():
    print("INSIDE INIT GLOBALS DESKTOP")
    disp = Display(visible=True, size=(1024 + 30, 768 + 150), backend="xvfb", use_xauth=True)
    disp.start()
    import pyautogui
    from stagehand import Stagehand, StagehandConfig
    pyautogui._pyautogui_x11._display = Xlib.display.Display(os.environ['DISPLAY'])
    pyautogui.FAILSAFE = False
    global page
    stagehand_config = StagehandConfig(
        env="LOCAL",
        model_name=os.getenv("MODEL_NAME"),
        model_api_key=os.getenv("OPENAI_API_KEY"),
        local_browser_launch_options={
            "headless": False,
            "ignoreDefaultArgs": [
                "--start-maximized",
                "--hide-scrollbars",
            ],
        }
    )
    stagehand = Stagehand(stagehand_config)
    await stagehand.init()
    page = stagehand.page
    await page.set_viewport_size({"width": 1024, "height": 768})

    # Set the browser geolocation
    await page._page.context.set_geolocation(BROWSER_GEOLOCATION)

    # Ensure we do not wait more than 5 seconds for failing tool calls
    page._page.context.set_default_timeout(int(os.getenv("BROWSER_ACTION_TIMEOUT_MS", "5000")))
    print("INIT GLOBALS DESKTOP COMPLETE")

async def main():
    await init_globals()
    # Run the MCP server
    await mcp.run_async()

if __name__ == "__main__":
    asyncio.run(main())
