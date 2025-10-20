
import os
from typing import Any, Optional

import cv2
import litellm
import numpy as np
from stagehand import Stagehand, StagehandConfig
from stagehand.agent.agent import MODEL_TO_CLIENT_CLASS_MAP, OpenAICUAClient
from core.web.tool_calling.interface import BrowserToolCaller

litellm.api_base = os.getenv("OPENAI_BASE_URL")
MODEL_TO_CLIENT_CLASS_MAP.update({litellm.api_base: lambda *args, **kwargs: OpenAICUAClient(*args, **kwargs)})

class StageHandBrowserToolCaller(BrowserToolCaller):
    def __init__(self, configuration: Optional[Any] = None):
        # Stagehand
        self.stagehand_config = StagehandConfig(
            env="LOCAL",
            model_name=os.getenv("MODEL_NAME"),
            model_api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.stagehand = Stagehand(self.stagehand_config)

    async def initialize_tools(self):
        await self.stagehand.init()
        self.page = self.stagehand.page

    async def determine_and_call_tools(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None
    ):
        # TODO: Enable dynamic navigation
        # await browser_search_agent.tool_caller.page.goto("https://www.mcdonalds.com/")
        tool_call_result = str((await self.page.act(subtask)))
        return tool_call_result, tool_call_result
    
    async def screenshot(self) -> Optional[cv2.typing.MatLike]:
        image_bytes = await self.stagehand.page._page.screenshot(path="tmp.jpg")
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return image
    
    async def close(self): self.stagehand.close()
    