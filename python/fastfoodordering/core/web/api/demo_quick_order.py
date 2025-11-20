# python/fastfoodordering/examples/demo_quick_order.py
import asyncio
import json
import os
import time
import re
import argparse
from typing import Iterable, Optional

from stagehand import Stagehand, StagehandConfig

BROWSER_GEOLOCATION = json.loads(os.getenv("BROWSER_GEOLOCATION", '''{
    "latitude": 28.5383,
    "longitude": -81.3792,
    "accuracy": 100
}'''))
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
async def order_wendys(page, item: str, zip_code: Optional[str]):
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



# -------------------------------------------------
# RUNNER
# -------------------------------------------------
async def run(item: str, headless: bool, zip_code: Optional[str]):
    log(f"Starting run() with item={item}, zip={zip_code}, headless={headless}")

    config = StagehandConfig(
        env="LOCAL",
        model_name=None,
        model_api_key=None,
        local_browser_launch_options={"headless": headless, "ignoreDefaultArgs": ['--hide-scrollbars']},
    )

    sh = Stagehand(config)
    log("Initializing Stagehand…")
    await sh.init()

    page = sh.page._page
    ctx = page.context

    log("Setting geolocation")
    await ctx.grant_permissions(["geolocation"], origin=WENDYS_ORIGIN)
    await ctx.set_geolocation(BROWSER_GEOLOCATION)

    page.set_default_timeout(15000)
    log("Timeout set to 15000ms")

    try:
        await order_wendys(page, item, zip_code)
        log("Order flow completed. Check browser.")
        if not headless:
            time.sleep(5)

    except Exception as e:
        log_err(f"Script error: {e}")
        if not headless:
            print("Leaving browser open… Ctrl+C to quit.")
            while True:
                await asyncio.sleep(3600)
        else:
            raise

    # finally:
    #     if headless:
    #         log("Closing browser")
    #         await ctx.close()
    #         await ctx.browser.close()


def main():
    parser = argparse.ArgumentParser(description="Wendy's quick order demo with logging")
    parser.add_argument("--item", required=True)
    parser.add_argument("--zip", type=str, default=None)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    log(f"Arguments: item={args.item}, zip={args.zip}, headless={args.headless}")
    asyncio.run(run(args.item, args.headless, args.zip))


if __name__ == "__main__":
    main()
