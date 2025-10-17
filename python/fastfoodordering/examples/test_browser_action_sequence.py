import asyncio
import os
import time

from stagehand import Stagehand, StagehandConfig

async def main():
    stagehand_config = StagehandConfig(
        env="LOCAL",
        model_name=os.getenv("MODEL_NAME"),
        model_api_key=os.getenv("OPENAI_API_KEY"),
        local_browser_launch_options={
            # "headless": True,
        }
    )
    stagehand = Stagehand(stagehand_config)
    await stagehand.init()
    page = stagehand.page
    await page.goto("https://www.mcdonalds.com/")

    text = "Our Menu"

    any_elements_clicked = False
    for element in await page._page.get_by_text(text).all():
        # Check that the element is visible
        # NOTE: This relies on the 
        if await element.bounding_box() is not None:
            await element.click()
            any_elements_clicked = True

    return "success" if any_elements_clicked else f"No element with text '{text}' found in visible screen."

    # .bounding_box()
    # print(element_bounding_box)
    # await page._page.mouse.click(*(element_bounding_box["x"] + (element_bounding_box["width"] / 2), element_bounding_box["y"] + (element_bounding_box["height"] / 2)))
    # time.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
