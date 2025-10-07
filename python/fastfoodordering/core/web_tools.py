from fastmcp import FastMCP
from stagehand import StagehandPage
page: StagehandPage = None

mcp = FastMCP("Custom StageHand MCP Server")

@mcp.tool
async def navigate(url: str):
    global page
    await page.goto(url)
    return "success"

@mcp.tool
async def scroll(delta_x_pixels: float, delta_y_pixels: float):
    global page
    await page._page.mouse.wheel(delta_x_pixels, delta_y_pixels)
    return "success"

@mcp.tool
async def click_element_by_text(text: str):
    global page
    element = page._page.get_by_text(text)
    await element.scroll_into_view_if_needed()
    await element.click()
    return "success"

@mcp.tool
async def get_element_coordinates_by_text(text: str):
    global page
    element = page._page.get_by_text(text)
    element_bounding_box = await element.bounding_box()
    return (element_bounding_box.x + (element_bounding_box.width / 2), element_bounding_box.y + (element_bounding_box.height / 2))

@mcp.tool
async def click_coordinates(x: float, y: float):
    global page
    await page._page.mouse.click(x, y)
    return "success"

