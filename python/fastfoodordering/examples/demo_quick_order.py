# python/fastfoodordering/examples/demo_quick_order.py
import asyncio
import time
import re
import argparse
from typing import Iterable, Optional

from stagehand import Stagehand, StagehandConfig

DEFAULT_GEO = {"latitude": 28.5383, "longitude": -81.3792}  # Orlando
WENDYS_ORIGIN = "https://order.wendys.com"

# --- Small, hardcoded “menu” mapping to likely visible labels -----------------
WENDYS_MENU = {
    "Dave's Single": ["Dave's Single", "Dave’s Single"],
    "Big Bacon Classic": ["Big Bacon Classic"],
    "Son of Baconator": ["Son of Baconator"],
}

# --- Helpers ------------------------------------------------------------------
async def _click_any_text(page, labels: Iterable[str], exact: bool = False, timeout_ms: int = 10000) -> bool:
    for label in labels:
        try:
            matcher = re.compile(rf"^{re.escape(label)}$") if exact else re.compile(label, re.I)
            loc = page.get_by_text(matcher).first
            await loc.wait_for(timeout=timeout_ms)
            await loc.scroll_into_view_if_needed()
            await loc.click()
            return True
        except Exception:
            continue
    return False

async def _click_any_button(page, labels: Iterable[str], timeout_ms: int = 10000) -> bool:
    for label in labels:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I)).first
            await btn.wait_for(timeout=timeout_ms)
            await btn.scroll_into_view_if_needed()
            await btn.click()
            return True
        except Exception:
            pass
        if await _click_any_text(page, [label], exact=False, timeout_ms=timeout_ms):
            return True
    return False

async def _maybe_click_cookie_banner(page):
    texts = ["Accept All","Accept all cookies","Accept","I Agree","Got it","Continue","Allow All","Save & Accept"]
    await _click_any_button(page, texts, timeout_ms=3000)

async def _close_any_map_popup(page):
    for sel in ["button:has-text('×')", "[aria-label=Close]", ".gm-ui-hover-effect"]:
        try:
            await page.locator(sel).first.click(timeout=800)
            break
        except Exception:
            pass

async def _select_first_wendys_store(page) -> bool:
    await _close_any_map_popup(page)

    # Try list and map popover buttons
    selectors = [
        "button:has-text('Order here')",
        "a:has-text('Order here')",
        "role=button[name=/Order here/i]",
        "role=link[name=/Order here/i]",
        "text=/Order here/i",
        "//button[contains(., 'Order here')]",
        "(//button[contains(., 'Order here')]|//a[contains(., 'Order here')])[1]",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(timeout=6000)
            await loc.scroll_into_view_if_needed()
            await loc.click(force=True)
            return True
        except Exception:
            continue

    # JS fallback (sometimes event handlers are higher up the tree)
    try:
        clicked = await page.evaluate("""
        () => {
          const xs = Array.from(document.querySelectorAll('*'))
            .filter(el => /order\\s*here/i.test(el.textContent || ''));
          if (xs.length) { xs[0].dispatchEvent(new MouseEvent('click', {bubbles:true})); return true; }
          return false;
        }
        """)
        if clicked:
            return True
    except Exception:
        pass
    return False

async def _go_to_cart(page):
    candidates = [
        ("button", r"Cart"),
        ("button", r"View Cart"),
        ("button", r"Checkout"),
        ("link",   r"Cart"),
        ("text",   r"Cart"),
        ("text",   r"View Cart"),
    ]
    for kind, label in candidates:
        try:
            rx = re.compile(label, re.I)
            if kind == "button":
                el = page.get_by_role("button", name=rx).first
            elif kind == "link":
                el = page.get_by_role("link", name=rx).first
            else:
                el = page.get_by_text(rx).first
            await el.wait_for(timeout=6000)
            await el.scroll_into_view_if_needed()
            await el.click()
            return True
        except Exception:
            continue
    return False

async def _menu_visible(page) -> bool:
    try:
        loc = page.get_by_text(re.compile(r"Hamburgers|Burgers", re.I)).first
        await loc.wait_for(timeout=800)
        return True
    except Exception:
        return False

async def _ensure_store_selected_and_menu(page) -> bool:
    """Keep trying until we leave /location and see menu categories."""
    for _ in range(8):
        if await _menu_visible(page):
            return True

        # If we’re still on /location, push on it
        if "location" in page.url:
            # Try clicking the first Order here
            clicked = await _select_first_wendys_store(page)
            # Also try the header CTA as a fallback
            await _click_any_button(page, ["Order Pickup", "Order Here", "Pick Up Here", "Continue"])
            if not clicked:
                # Nudge the page a bit
                await page.mouse.wheel(0, 600)
            await page.wait_for_timeout(1000)
            continue

        # If we’re not on /location but no menu, try obvious nav words
        await _click_any_text(page, ["View Our Menu", "Menu"], exact=False, timeout_ms=1500)
        await page.wait_for_timeout(800)

    return await _menu_visible(page)

# --- Wendy's flow -------------------------------------------------------------
async def order_wendys(page, item: str, zip_code: Optional[str]):
    await page.goto("https://order.wendys.com/")
    await page.context.grant_permissions(["geolocation"], origin=WENDYS_ORIGIN)
    await page.context.set_geolocation(DEFAULT_GEO)

    await _maybe_click_cookie_banner(page)

    # Start pickup (several variants)
    await _click_any_button(page, ["Order Pickup", "Pick Up", "Start Order", "Start Order Pickup", "Continue"])

    # Dismiss “Oops…” modal if it appears
    try:
        await page.get_by_role("button", name=re.compile(r"Okay|Close", re.I)).click(timeout=1500)
    except Exception:
        pass

    # Enter ZIP if the location box exists
    try:
        loc = page.get_by_placeholder(re.compile(r"(City.*State.*|ZIP|Zipcode|Postal)", re.I)).first
        await loc.click()
        await loc.fill((zip_code or "32801"))
        try:
            await page.get_by_role("button", name=re.compile(r"Search", re.I)).click(timeout=1500)
        except Exception:
            await page.keyboard.press("Enter")
    except Exception:
        pass  # Sometimes the box is not present or location already set

    # Make sure we actually leave /location and see a menu
    ok = await _ensure_store_selected_and_menu(page)
    if not ok:
        raise RuntimeError("Could not get past the location page into the menu.")

    # Click category
    await _click_any_text(page, ["Hamburgers", "Burgers"], exact=False)

    # Click item
    labels = WENDYS_MENU.get(item)
    if not labels:
        raise ValueError(f"Unsupported Wendy's item: {item}. Supported: {list(WENDYS_MENU)}")
    if not await _click_any_text(page, labels, exact=False):
        raise RuntimeError(f"Couldn't find Wendy's item on page: {item}")

    # Add to cart
    added = await _click_any_button(page, ["Add to Order", "Add to Cart", "Add", "Customize"])
    if not added:
        await asyncio.sleep(1)
        await _click_any_button(page, ["Add to Order", "Add to Cart", "Add"])

    await _go_to_cart(page)

# --- Runner -------------------------------------------------------------------
async def run(item: str, headless: bool, zip_code: Optional[str]):
    config = StagehandConfig(
        env="LOCAL",
        model_name=None,
        model_api_key=None,
        local_browser_launch_options={"headless": headless, "ignoreDefaultArgs": ['--hide-scrollbars']},
    )
    sh = Stagehand(config)
    await sh.init()
    page = sh.page._page
    ctx = page.context
    await ctx.grant_permissions(["geolocation"], origin=WENDYS_ORIGIN)
    await ctx.set_geolocation(DEFAULT_GEO)
    page.set_default_timeout(15000)

    try:
        await order_wendys(page, item, zip_code)
        print("✅ Reached cart (or at least tried). Check the browser window.")
        if not headless:
            time.sleep(5)
    except Exception as e:
        print(f"⚠️ Script error: {e}")
        if not headless:
            print("Leaving the browser open for inspection (Ctrl+C to quit).")
            while True:
                await asyncio.sleep(3600)
        else:
            raise
    finally:
        if headless:
            await page.context.close()
            await page.context.browser.close()

def main():
    parser = argparse.ArgumentParser(description="Wendy's quick-order demo (no LLM).")
    parser.add_argument("--item", required=True, help="Menu item string (e.g., \"Dave's Single\")")
    parser.add_argument("--zip", type=str, default=None, help="US ZIP or 'City, ST' to search")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    args = parser.parse_args()
    asyncio.run(run(args.item, args.headless, args.zip))

if __name__ == "__main__":
    main()
