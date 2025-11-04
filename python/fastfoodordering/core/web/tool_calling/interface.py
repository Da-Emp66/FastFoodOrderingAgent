
import abc
import enum
from typing import Optional, Tuple

import cv2
from core.utils import ToolCaller

# Constants
FILEPATH_REGEX = r"((?:/[^\s\/]+)+(?:\.(?:\w+)))"

# Definitions
class ToolModes(str, enum.Enum):
    Code = "code"
    Constrained = "constrained"
    DSPy = "dspy"
    StageHand = "stagehand"

class BrowserToolCaller(ToolCaller):
    async def determine_and_call_tools(
        self,
        overall_goal: str,
        subtask: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None
    ) -> Tuple[str, str]:
        return await super().determine_and_call_tools(
            overall_goal=overall_goal,
            subtask=subtask,
            previous_browser_screenshot=previous_browser_screenshot,
            current_browser_screenshot=current_browser_screenshot,
            current_browser_snapshot=current_browser_snapshot,
        )
    async def close(self): pass
    async def screenshot(self) -> Optional[cv2.typing.MatLike]: return None
    async def take_snapshot(self) -> Optional[str]: return None
