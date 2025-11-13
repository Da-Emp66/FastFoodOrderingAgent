
import base64
import enum
import json
import os
from typing import List, Optional
import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict


class ParsedItemDetails(BaseModel):
    type: str
    bbox: List[float]
    """xyxy relative coordinates of each box."""
    interactivity: bool
    content: Optional[str] = None
    source: str

    model_config = ConfigDict(extra="allow")

def get_item_by_label_number(number: int):
    import shared
    if not os.path.exists(shared.CURRENT_IMAGE_PARSE_METADATA_PATH): return "[❌] Error: There are no labeled boxes."
    current_image_parse_metadata = json.loads(open(shared.CURRENT_IMAGE_PARSE_METADATA_PATH).read())
    if current_image_parse_metadata is None: return "[❌] Error: Image parse metadata is `null`. Try again."
    if len(current_image_parse_metadata) <= number:
        return f"[❌] Error: There is no box labeled by number {number}."
    item = current_image_parse_metadata[number]
    item = ParsedItemDetails.model_validate_json(item)
    return item

class ParserDetails(BaseModel):
    som_image_base64: str
    parsed_content_list: List[ParsedItemDetails]
    """Order matters. Index `0` corresponds to box `0` in the labeled `som_image_base64`, and so forth."""
    latency: float

    def matlike_image(self):
        image_data = base64.b64decode(self.som_image_base64)
        np_array = np.frombuffer(image_data, np.uint8)
        return cv2.imdecode(np_array, cv2.IMREAD_COLOR)

class ParserMode(str, enum.Enum):
    Enabled = "enabled"
    Disabled = "disabled"

class ParserConfiguration(BaseModel):
    parser_mode: ParserMode = os.getenv("PARSER_MODE", ParserMode.Enabled)
    parser_uri: str = "http://" + os.getenv("PARSER_HOST", "localhost") + ":" + os.getenv("PARSER_PORT", "8055")

class FilterConfig(BaseModel):
    banned_regions: List[List[float]]
    """xyxy bboxes to blacklist in image parsing."""
    iou_threshold: float

class ParseRequestConfiguration(BaseModel):
    filter: FilterConfig

class ParseRequest(BaseModel):
    base64_image: str
    configuration: Optional[ParseRequestConfiguration] = None
