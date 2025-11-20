import asyncio
import json
import os
import re
import time
import traceback
from typing import Iterable, Literal, Optional
import Xlib.display
import cv2
from pyvirtualdisplay.display import Display
from fastmcp import FastMCP
from stagehand import StagehandPage

from core.utils import place_coordinate_on_image
from core.web.parser import get_item_by_label_number
import shared

HEADLESS = False

# Default browser geolocation is UCF, Orlando
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
mcp = FastMCP("Custom StageHand MCP Server")

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

#####################################################################
### Main Ordering Functions and Tool
#####################################################################

DEFAULT_ZIP_CODE = "32801"
WENDYS_ORIGIN = "https://order.wendys.com"

# Small hardcoded menu mapping
WENDYS_MENU = {
    "Dave's Single": ["Dave's Single", "Dave’s Single"],
    "Big Bacon Classic": ["Big Bacon Classic"],
    "Son of Baconator": ["Son of Baconator"],
}


# -------------------------------------------------
# LOGGING WRAPPERS – THESE ALWAYS PRINT WITH STAGEHAND
# -------------------------------------------------
def log(msg: str):
    print(f"[LOG] {msg}", flush=True)

def log_err(msg: str):
    print(f"[ERROR] {msg}", flush=True)


# -------------------------------------------------
# CLICK HELPERS
# -------------------------------------------------

async def click_point(page, x, y):
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.up()


async def _click_any_text(page, labels: Iterable[str], exact: bool = False, timeout_ms: int = 10000) -> bool:
    labels_list = list(labels)
    log(f"_click_any_text called with labels={labels_list}, exact={exact}, timeout_ms={timeout_ms}")

    for label in labels_list:
        try:
            log(f"Trying to click text label='{label}'")

            matcher = re.compile(rf"^{re.escape(label)}$") if exact else re.compile(label, re.I)
            loc = page.get_by_text(matcher).first

            await loc.wait_for(timeout=timeout_ms)
            await loc.scroll_into_view_if_needed()
            await loc.click()

            log(f"Clicked text label='{label}'")
            return True

        except Exception as e:
            log_err(f"_click_any_text failed for label='{label}': {e}")

    log_err(f"_click_any_text could not click any of labels={labels_list}")
    return False


async def _click_any_button(page, labels: Iterable[str], timeout_ms: int = 10000) -> bool:
    labels_list = list(labels)
    log(f"_click_any_button called with labels={labels_list}, timeout_ms={timeout_ms}")

    for label in labels_list:
        try:
            log(f"Trying button with name pattern='{label}'")
            btn = page.get_by_role("button", name=re.compile(label, re.I)).first
            await btn.wait_for(timeout=timeout_ms)
            await btn.scroll_into_view_if_needed()
            await btn.click()
            log(f"Clicked button with label pattern='{label}'")
            return True

        except Exception as e:
            log_err(f"_click_any_button failed via role for label='{label}': {e}")

        try:
            log(f"Falling back to clicking text for button label='{label}'")
            if await _click_any_text(page, [label], exact=False, timeout_ms=timeout_ms):
                return True
        except Exception as e:
            log_err(f"Fallback click via text failed for '{label}': {e}")

    log_err(f"_click_any_button could not click any of labels={labels_list}")
    return False


# -------------------------------------------------
# POPUPS / LOCATION HANDLING
# -------------------------------------------------
async def _maybe_click_cookie_banner(page):
    log("Checking for cookie banner")
    texts = ["Accept All", "Accept all cookies", "Accept", "I Agree", "Got it", "Continue", "Allow All", "Save & Accept"]
    await _click_any_button(page, texts, timeout_ms=3000)


async def _close_any_map_popup(page):
    log("Trying to close any map popup")

    for sel in ["button:has-text('×')", "[aria-label=Close]", ".gm-ui-hover-effect"]:
        try:
            log(f"Trying popup selector='{sel}'")
            await page.locator(sel).first.click(timeout=800)
            log(f"Closed popup selector='{sel}'")
            return
        except Exception as e:
            log_err(f"Popup selector '{sel}' failed: {e}")


async def _select_first_wendys_store(page) -> bool:
    log("Selecting first Wendys store")

    await _close_any_map_popup(page)

    selectors = [
        "button:has-text('Order here')",
        "a:has-text('Order here')",
        "role=button[name=/Order here/i]",
        "role=link[name=/Order here/i]",
        "text=/Order here/i]",
        "//button[contains(., 'Order here')]",
        "(//button[contains(., 'Order here')]|//a[contains(., 'Order here')])[1]",
    ]

    for sel in selectors:
        try:
            log(f"Trying store selector='{sel}'")
            loc = page.locator(sel).first
            await loc.wait_for(timeout=6000)
            await loc.scroll_into_view_if_needed()
            await loc.click(force=True)
            log(f"Clicked store selector='{sel}'")
            return True

        except Exception as e:
            log_err(f"Store selector '{sel}' failed: {e}")

    log("Trying JS fallback for store selection")

    try:
        clicked = await page.evaluate("""
            () => {
              const xs = Array.from(document.querySelectorAll('*'))
                .filter(el => /order\\s*here/i.test(el.textContent || ''));
              if (xs.length) {
                xs[0].dispatchEvent(new MouseEvent('click', {bubbles:true}));
                return true;
              }
              return false;
            }
        """)
        if clicked:
            log("JS fallback store selection succeeded")
            return True

    except Exception as e:
        log_err(f"JS fallback error: {e}")

    log_err("Store selection failed")
    return False


async def _menu_visible(page) -> bool:
    log("Checking if menu is visible")

    try:
        loc = page.get_by_text(re.compile(r"Hamburgers|Burgers", re.I)).first
        await loc.wait_for(timeout=800)
        log("Menu is visible")
        return True
    except Exception as e:
        log_err(f"Menu not visible: {e}")
        return False


async def _ensure_store_selected_and_menu(page) -> bool:
    log("Ensuring store is selected and menu is visible")

    for attempt in range(8):
        log(f"Attempt {attempt+1}, current URL={page.url}")

        if await _menu_visible(page):
            log("Menu found")
            return True

        # if "location" in page.url:
        #     log("Still on /location, trying to select store")
        #     clicked = await _select_first_wendys_store(page)
        #     log(f"Store selection result={clicked}")

        #     await _click_any_button(page, ["Order Pickup", "Order Here", "Pick Up Here", "Continue"])
        #     await page.mouse.wheel(0, 600)
        #     await page.wait_for_timeout(1000)
        #     continue

        log("Trying generic menu entry clicks")
        await _click_any_text(page, ["View Our Menu", "Menu"], exact=False, timeout_ms = 1000)
        await page.wait_for_timeout(800)

    log("Max attempts reached, final check:")
    final_ok = await _menu_visible(page)
    log(f"Menu visible at end={final_ok}")
    return final_ok


# -------------------------------------------------
# MAIN ORDER FLOW
# -------------------------------------------------
async def order_wendys(page: StagehandPage, item: str, zip_code: Optional[str]):
    log("=== Starting Wendy's Order Flow ===")

    log("Navigating to homepage")
    await page.goto("https://order.wendys.com/")
    log(f"Loaded URL: {page.url}")

    await page.context.grant_permissions(["geolocation"], origin=WENDYS_ORIGIN)
    await page.context.set_geolocation(BROWSER_GEOLOCATION)

    await _maybe_click_cookie_banner(page)

    log("Starting pickup")
    await _click_any_button(page, ["Order Pickup", "Pick Up", "Start Order", "Start Order Pickup", "Continue"])

    log("Trying to dismiss any 'Oops' modal")
    try:
        await page.get_by_role("button", name=re.compile(r"Okay|Close", re.I)).click(timeout=1500)
        log("Dismissed Oops modal")
    except Exception:
        log("No Oops modal shown")

    log("Entering ZIP code if present")
    try:
        loc = page.get_by_placeholder(re.compile(r"(City.*State.*|ZIP|Zipcode|Postal)", re.I)).first
        await loc.click()

        zip_filled = zip_code or DEFAULT_ZIP_CODE
        log(f"Filling ZIP: {zip_filled}")
        await loc.fill(zip_filled)

        try:
            await page.get_by_role("button", name=re.compile(r"Search", re.I)).click(timeout=1500)
        except Exception:
            log("Search button unavailable, pressing Enter")
            await page.keyboard.press("Enter")
    except Exception as e:
        log(f"No ZIP box found or already set: {e}")

    log("Ensuring menu is visible")
    ok = await _ensure_store_selected_and_menu(page)
    log(f"Store+menu result: {ok}")

    if not ok:
        raise RuntimeError("Could not get past the location page into the menu.")

    log("Clicking 'Hamburgers' category")
    await _click_any_text(page, ["Hamburgers", "Burgers"], exact=False)

    log(f"Attempting to click item: {item}")
    labels = WENDYS_MENU.get(item)
    if not labels:
        raise ValueError(f"Unsupported item: {item}")

    if not await _click_any_text(page, labels, exact=False):
        raise RuntimeError(f"Could not find item: {item}")

 
    log("Handling new Wendy’s product flow")

    # Floating Start Order button
    await _click_any_button(page, ["Start an order", "Start Order", "Start Your Order"], timeout_ms=15000)

    # Pickup selection
    #await _click_any_button(page, ["Pickup", "Order Pickup", "Pick Up"], timeout_ms=15000)

    # Drive-thru option
    await _click_any_button(page, ["Drive-Thru", "Drive Thru", "Drive-Thru Pickup", "Drive Thru Pickup"], timeout_ms=15000)

    # Final Add button
    await _click_any_button(page, ["Add", "Add to Order", "Add to Cart"], timeout_ms=15000)

    log("Trying coordinate-based click for 'Single Item' combo card")

    try:
        # Locate the text FIRST (this always shows up)
        single_text = page.get_by_text(re.compile(r"Single Item", re.I)).first
        await single_text.wait_for(timeout=6000)

        box = await single_text.bounding_box()
        if not box:
            raise RuntimeError("Single Item bounding box not found")

        # Compute a click point ABOVE the text — where the card icon is
        click_x = box["x"] + box["width"] / 2
        click_y = box["y"] - 60   # 60px above text usually hits the burger icon

        log(f"Clicking Single Item at coords x={click_x}, y={click_y}")
        await click_point(page, click_x, click_y)

        log("Coordinate-based click succeeded")

    except Exception as e:
        log_err(f"Coordinate click failed: {e}")

@mcp.tool
async def order_wendys_tool(official_food_item_name: str, zip_code: Optional[str]):
    global page
    if not zip_code: zip_code = DEFAULT_ZIP_CODE
    try:
        return (await order_wendys(page, official_food_item_name, zip_code))
    except Exception as e:
        print(traceback.format_exc())
        return str(e)

#####################################################################
### Initialization
#####################################################################

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
    ctx = page.context
    await page.set_viewport_size({"width": 1024, "height": 768})

    # Set the browser geolocation
    await page._page.context.set_geolocation(BROWSER_GEOLOCATION)
    await ctx.grant_permissions(["geolocation"], origin=WENDYS_ORIGIN)
    await ctx.set_geolocation(BROWSER_GEOLOCATION)

    # Ensure we do not wait more than 5 seconds for failing tool calls
    page._page.context.set_default_timeout(int(os.getenv("BROWSER_ACTION_TIMEOUT_MS", "5000")))
    print("INIT GLOBALS DESKTOP COMPLETE")

async def main():
    await init_globals()
    # Run the MCP server
    await mcp.run_async()

if __name__ == "__main__":
    asyncio.run(main())
