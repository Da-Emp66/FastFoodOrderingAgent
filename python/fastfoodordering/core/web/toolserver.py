import asyncio
import json
import os
import time
from typing import Literal
from fastmcp import FastMCP
from stagehand import Stagehand, StagehandConfig, StagehandPage

import shared

# Default browser geolocation is Orlando
# Accuracy denotes coordinate accuracy in meters.
BROWSER_GEOLOCATION = json.loads(os.getenv("BROWSER_GEOLOCATION", '''{
    "latitude": 28.5383,
    "longitude": -81.3792,
    "accuracy": 100
}'''))
GLOBAL_BROWSER_LOAD_WAIT_SLEEP = 1.0
page: StagehandPage = None
mcp = FastMCP("Custom StageHand MCP Server")

@mcp.tool
async def navigate(url: str):
    global page
    print("In function call `navigate`...")
    try:
        await page.goto(url)
        await page._page.context.grant_permissions(["geolocation"])
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return "success"
    except Exception as e:
        return str(e)

@mcp.tool
async def scroll(direction: Literal["left", "right", "up", "down"], delta_pixels: float):
    global page
    print("In function call `scroll`...")
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
async def click_element_by_text(text: str):
    global page
    print("In function call `click_element_by_text`...")
    try:
        any_elements_clicked = False
        for element in await page._page.get_by_text(text).all():
            # Check that the element is visible
            # NOTE: This relies on the LLM to give valid inputs on what is and is not visible
            if await element.bounding_box() is not None:
                await element.click()
                any_elements_clicked = True
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return "success" if any_elements_clicked else f"No elements with text '{text}' found in visible screen."
    except Exception as e:
        return str(e)

@mcp.tool
async def get_element_coordinates_by_text(text: str):
    global page
    print("In function call `get_element_coordinates_by_text`...")
    try:
        bboxes = []
        for element in await page._page.get_by_text(text).all():
            element_bounding_box = await element.bounding_box()
            if element_bounding_box is not None:
                bboxes.append((element_bounding_box["x"] + (element_bounding_box["width"] / 2), element_bounding_box["y"] + (element_bounding_box["height"] / 2)))
        return (str(bboxes) if len(bboxes) > 0 else f"No elements with text '{text}' found in visible screen.")
    except Exception as e:
        return str(e)

@mcp.tool
async def click_coordinates(x: float, y: float):
    global page
    print("In function call `click_coordinates`...")
    try:
        await page._page.mouse.click(x, y)
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return "success"
    except Exception as e:
        return str(e)

@mcp.tool
async def fill_text_box(text: str):
    global page
    print("In function call `fill_text_box`...")
    try:
        for el in await page.query_selector_all("input, textarea"):
            if await el.is_visible() and await el.is_enabled():
                try:
                    await el.fill(text)
                    await el.press("Enter")
                except Exception:
                    pass  # skip read-only or non-fillable elements
    except Exception as e:
        return str(e)

@mcp.tool
async def screenshot():
    global page
    print("In function call `screenshot`...")
    try:
        path = shared.CURRENT_SCREENSHOT_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await page._page.screenshot(path=path, full_page=True)
        return path
    except Exception as e:
        return str(e)
    
@mcp.tool
async def set_location(latitude: float, longitude: float, accuracy: int = 0):
    global page
    print("In function call `set_location`...")
    await page._page.context.set_geolocation({
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
    })

async def main():
    # Initialize StageHand webpage
    global page
    stagehand_config = StagehandConfig(
        env="LOCAL",
        model_name=os.getenv("MODEL_NAME"),
        model_api_key=os.getenv("OPENAI_API_KEY"),
        local_browser_launch_options={
            "headless": True,
            "ignoreDefaultArgs": ['--hide-scrollbars'],
        }
    )
    stagehand = Stagehand(stagehand_config)
    await stagehand.init()
    page = stagehand.page

    # Set the browser geolocation
    await page._page.context.set_geolocation(BROWSER_GEOLOCATION)

    # Ensure we do not wait more than 5 seconds
    # for failing tool calls
    page._page.context.set_default_timeout(5000)

    # Run the MCP server
    await mcp.run_async()

if __name__ == "__main__":
    asyncio.run(main())
