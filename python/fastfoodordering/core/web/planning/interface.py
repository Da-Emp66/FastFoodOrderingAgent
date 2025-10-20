
import abc
import enum
from typing import Any, Optional, Union

import cv2
import dspy
from pydantic import BaseModel

class PlannerTypes(str, enum.Enum):
    DSPy = "dspy"

class PlannerConfiguration(BaseModel):
    disable: bool = False

class PlannerVisibilitySettings(BaseModel):
    previous_screenshot_visible: bool = True
    current_screenshot_visible: bool = True
    overall_goal_visible: bool = True
    previous_subtask_visible: bool = True
    previous_tool_call_visible: bool = True
    previous_tool_call_output_visible: bool = True
    history_visible: bool = True
    snapshot_visible: bool = False
    tools_visible: bool = False

class BrowserActionPlanner(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def infer_subtask(
        self,
        overall_goal: str,
        previous_subtask: str,
        previous_tool_call: str,
        previous_tool_call_output: str,
        previous_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_screenshot: Optional[cv2.typing.MatLike] = None,
        current_browser_snapshot: Optional[str] = None,
        tool_caller: Optional[Union[Any, dspy.Tool]] = None,
        history: Optional[dspy.History] = None,
    ) -> str:
        raise NotImplementedError()
    