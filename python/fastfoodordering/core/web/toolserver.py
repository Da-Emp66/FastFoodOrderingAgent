import asyncio
import json
import os
import time
from typing import Literal
import cv2
from fastmcp import FastMCP
from stagehand import Stagehand, StagehandConfig, StagehandPage

from core.web.agent import ParsedItemDetails
from core.utils import place_coordinate_on_image
import shared

# Default browser geolocation is Orlando
# Accuracy denotes coordinate accuracy in meters.
BROWSER_GEOLOCATION = json.loads(os.getenv("BROWSER_GEOLOCATION", '''{
    "latitude": 28.5383,
    "longitude": -81.3792,
    "accuracy": 100
}'''))
GLOBAL_BROWSER_LOAD_WAIT_SLEEP = 1.0
MOST_RECENT_CLICK = None

page: StagehandPage = None
mcp = FastMCP("Custom StageHand MCP Server")

@mcp.tool
async def screenshot():
    global page, MOST_RECENT_CLICK
    # print("In function call `screenshot`...")
    try:
        path = shared.CURRENT_SCREENSHOT_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await page._page.screenshot(path=path, full_page=True) # , full_page=True
        if MOST_RECENT_CLICK is not None:
            cv2.imwrite(path, place_coordinate_on_image(cv2.imread(path), coordinate=MOST_RECENT_CLICK))
        return path
    except Exception as e:
        return str(e)

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
async def click_element_by_its_text_content(text: str):
    global page, MOST_RECENT_CLICK
    # print("In function call `click_element_by_text`...")
    try:
        any_elements_clicked = False
        for element in await page._page.get_by_text(text).all():
            # Check that the element is visible
            # NOTE: This relies on the LLM to give valid inputs on what is and is not visible
            bbox = await element.bounding_box()
            if bbox is not None:
                await element.click()
                MOST_RECENT_CLICK = bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2
                any_elements_clicked = True
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        return "success" if any_elements_clicked else f"No elements with text '{text}' found in visible screen."
    except Exception as e:
        return str(e)

# @mcp.tool
# async def click_coordinates(x: float, y: float):
#     global page
#     print("In function call `click_coordinates`...")
#     try:
#         await page._page.mouse.click(x, y)
#         time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
#         return "success"
#     except Exception as e:
#         return str(e)

def get_item_by_label_number(number: int):
    if not os.path.exists(shared.CURRENT_IMAGE_PARSE_METADATA_PATH): return "[❌] Error: There are no labeled boxes."
    current_image_parse_metadata = json.loads(open(shared.CURRENT_IMAGE_PARSE_METADATA_PATH).read())
    if current_image_parse_metadata is None: return "[❌] Error: Image parse metadata is `null`. Try again."
    if len(current_image_parse_metadata) <= number:
        return f"[❌] Error: There is no box labeled by number {number}."
    item = current_image_parse_metadata[number]
    item = ParsedItemDetails.model_validate_json(item)
    return item

@mcp.tool
async def click_element_by_box_label_number(number: int):
    global page, MOST_RECENT_CLICK
    # print("In function call `click_by_box_label_number`...")

    try:
        item = get_item_by_label_number(number)
        if type(item) == str: return item
        center_x = (item.bbox[0] + item.bbox[2]) / 2
        center_y = (item.bbox[1] + item.bbox[3]) / 2
        await page.wait_for_load_state("domcontentloaded")
        scroll_x, scroll_y = await page.evaluate("() => [window.scrollX, window.scrollY]")
        vx, vy = center_x * page._page.viewport_size['width'] + scroll_x, center_y * page._page.viewport_size['height'] + scroll_y
        await page.bring_to_front()
        await page._page.mouse.move(vx, vy)
        await page._page.mouse.click(vx, vy)
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
    global page, MOST_RECENT_CLICK
    # print("In function call `type_text_by_box_label_number`...")
    
    try:
        item = get_item_by_label_number(number)
        if type(item) == str: return item
        center_x = (item.bbox[0] + item.bbox[2]) / 2
        center_y = (item.bbox[1] + item.bbox[3]) / 2
        # Use JS to find the element at those coordinates
        element_handle = await page.evaluate_handle(
            """([x, y]) => document.elementFromPoint(x, y)""",
            [center_x, center_y],
        )
        if not element_handle:
            return f"[❌] Error: No element found at ({center_x}, {center_y})"
        # Wrap it back into a Playwright ElementHandle
        element = element_handle.as_element()
        if element is None:
            return f"[❌] Error: Element at ({center_x}, {center_y}) is not a valid input element"
        # Optional: check visibility
        if not await element.is_visible():
            return f"[⚠️] Error: Element at ({center_x}, {center_y}) is not visible"
        # Fill the element
        await element.click()
        await element.fill(text)
        await element.press("Enter")
        time.sleep(GLOBAL_BROWSER_LOAD_WAIT_SLEEP)
        bbox = await element.bounding_box()
        MOST_RECENT_CLICK = bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2
        return f"[✅] Success: Filled element at ({center_x}, {center_y}) with text: {text}"
    except Exception as e:
        return str(e)

@mcp.tool
async def fill_all_text_boxes_with(text: str):
    global page, MOST_RECENT_CLICK
    # print("In function call `fill_text_box`...")
    try:
        for el in await page.query_selector_all("input, textarea"):
            if await el.is_visible() and await el.is_enabled():
                try:
                    await el.fill(text)
                    await el.press("Enter")
                    bbox = await el.bounding_box()
                    MOST_RECENT_CLICK = bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2
                except Exception:
                    pass  # skip read-only or non-fillable elements
        return "success"
    except Exception as e:
        return str(e)

# @mcp.tool
# async def get_element_coordinates_by_text(text: str):
#     global page
#     print("In function call `get_element_coordinates_by_text`...")
#     try:
#         bboxes = []
#         for element in await page._page.get_by_text(text).all():
#             element_bounding_box = await element.bounding_box()
#             if element_bounding_box is not None:
#                 bboxes.append((element_bounding_box["x"] + (element_bounding_box["width"] / 2), element_bounding_box["y"] + (element_bounding_box["height"] / 2)))
#         return (str(bboxes) if len(bboxes) > 0 else f"No elements with text '{text}' found in visible screen.")
#     except Exception as e:
#         return str(e)

# @mcp.tool
# async def set_location(latitude: float, longitude: float, accuracy: int = 0):
#     global page
#     print("In function call `set_location`...")
#     await page._page.context.set_geolocation({
#         "latitude": latitude,
#         "longitude": longitude,
#         "accuracy": accuracy,
#     })

async def init_globals():
    print("INSIDE INIT GLOBALS")
    # Initialize StageHand webpage
    global page
    stagehand_config = StagehandConfig(
        env="LOCAL",
        model_name=os.getenv("MODEL_NAME"),
        model_api_key=os.getenv("OPENAI_API_KEY"),
        local_browser_launch_options={
            # "headless": True,
            "headless": False,
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
    page._page.context.set_default_timeout(int(os.getenv("BROWSER_ACTION_TIMEOUT_MS", "5000")))
    print("INIT GLOBALS COMPLETE")

async def main():
    await init_globals()
    # Run the MCP server
    await mcp.run_async()

if __name__ == "__main__":
    asyncio.run(main())
