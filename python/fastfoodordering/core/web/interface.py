import enum
from typing import Optional

from pydantic import BaseModel

class BrowserVisibilityMode(str, enum.Enum):
    Debug = "debug"
    Default = "default"

class BrowserVisibilityConfiguration(BaseModel):
    screenshot_tool_name: Optional[str] = "browser_take_screenshot"
    snapshot_tool_name: Optional[str] = "browser_snapshot"
