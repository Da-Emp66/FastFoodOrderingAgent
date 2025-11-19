
import enum
import os
from typing import Any, Dict, Union
import typing_extensions

from pydantic import BaseModel

class StrategyRepeatedScreenshots(typing_extensions.TypedDict):
    delay_seconds: float

class ScreenshotStrategy(str, enum.Enum):
    ExternalRepeated = "externalrepeated"
    """Repeatedly take screenshots outside of the browser agent."""
    OnBrowserAgent = "onbrowseragent"
    """Allow the browser agent class to directly call to screenshot."""

class ScreenshotConfiguration(BaseModel):
    strategy: ScreenshotStrategy = os.getenv("SCREENSHOT_STRATEGY", ScreenshotStrategy.OnBrowserAgent)
    spec: Union[Dict[str, Any], StrategyRepeatedScreenshots] = {}
