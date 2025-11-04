
import math
from typing import Any, AsyncGenerator, Literal, Tuple, Union
import cv2
import dspy
from pydantic import BaseModel

from core.utils import from_config
from core.web.agent import BrowserAgentConfiguration, IterativeTaskResult
from core.web.planning.dspy_planner import DSPyPlanner
from core.web.planning.interface import PlannerTypes
from core.web.tool_calling.code_tools import CodeBrowserToolCaller
from core.web.tool_calling.constrained_json_tools import ConstrainedBrowserToolCaller
from core.web.tool_calling.dspy_tools import DSPyBrowserToolCaller
from core.web.tool_calling.interface import ToolModes
from core.web.tool_calling.stagehand_tools import StageHandBrowserToolCaller


class TARSLikeBrowserAgentSystem:
    IMAGE_FACTOR = 28
    MIN_PIXELS = 100 * 28 * 28
    MAX_PIXELS = 16384 * 28 * 28
    MAX_RATIO = 200

    VIDEO_MIN_PIXELS = 128 * 28 * 28
    VIDEO_MAX_PIXELS = 768 * 28 * 28
    FRAME_FACTOR = 2
    FPS = 2.0
    FPS_MIN_FRAMES = 4
    FPS_MAX_FRAMES = 768

    def __init__(self, configuration: Union[BrowserAgentConfiguration, Any]):
        self.configuration: BrowserAgentConfiguration = from_config(configuration, BrowserAgentConfiguration)
        match self.configuration.planner_type:
            case PlannerTypes.DSPy: self.planner = DSPyPlanner(self.configuration.planner)
            case _: self.planner = None
        match self.configuration.tool_mode:
            case ToolModes.Code: self.tool_caller = CodeBrowserToolCaller(self.configuration.tools)
            case ToolModes.Constrained: self.tool_caller = ConstrainedBrowserToolCaller(self.configuration.tools)
            case ToolModes.DSPy: self.tool_caller = DSPyBrowserToolCaller(self.configuration.tools)
            case ToolModes.StageHand: self.tool_caller = StageHandBrowserToolCaller(self.configuration.tools)
            case _: self.tool_caller = None
        self.history = dspy.History(messages=[])
        self.screenshot = None

    @classmethod
    def round_by_factor(cls, number: int, factor: int) -> int:
        """Returns the closest integer to 'number' that is divisible by 'factor'."""
        return round(number / factor) * factor

    @classmethod
    def ceil_by_factor(cls, number: int, factor: int) -> int:
        """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
        return math.ceil(number / factor) * factor

    @classmethod
    def floor_by_factor(cls, number: int, factor: int) -> int:
        """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
        return math.floor(number / factor) * factor

    @classmethod
    def smart_resize(
        cls,
        height: int,
        width: int,
        factor: int = IMAGE_FACTOR,
        min_pixels: int = MIN_PIXELS,
        max_pixels: int = MAX_PIXELS,
    ) -> Tuple[int, int]:
        """
        Rescales the image so that the following conditions are met:

        1. Both dimensions (height and width) are divisible by 'factor'.

        2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].

        3. The aspect ratio of the image is maintained as closely as possible.
        """
        if max(height, width) / min(height, width) > cls.MAX_RATIO:
            raise ValueError(
                f"absolute aspect ratio must be smaller than {cls.MAX_RATIO}, got {max(height, width) / min(height, width)}"
            )
        h_bar = max(factor, cls.round_by_factor(height, factor))
        w_bar = max(factor, cls.round_by_factor(width, factor))
        if h_bar * w_bar > max_pixels:
            beta = math.sqrt((height * width) / max_pixels)
            h_bar = cls.floor_by_factor(height / beta, factor)
            w_bar = cls.floor_by_factor(width / beta, factor)
        elif h_bar * w_bar < min_pixels:
            beta = math.sqrt(min_pixels / (height * width))
            h_bar = cls.ceil_by_factor(height * beta, factor)
            w_bar = cls.ceil_by_factor(width * beta, factor)
        return h_bar, w_bar

    @classmethod
    def calculate_coordinate(
        cls,
        original_image_height: int,
        original_image_width: int,
        model_output_height: int,
        model_output_width: int,
    ) -> Tuple[int, int]:
        new_height, new_width = cls.smart_resize(original_image_height, original_image_width)
        new_coordinate = (int(model_output_width/new_width * original_image_width), int(model_output_height/new_height * original_image_height))
        return new_coordinate

    async def iterate_task(self) -> AsyncGenerator[IterativeTaskResult, IterativeTaskResult]:
        pass

class VisibleDotCoordinateOptions(BaseModel):
    radius: int = 10
    color: cv2.typing.Scalar = (0,0,255)
    thickness: int = -1

class VisibleAnchoredEmbedImageOptions(BaseModel):
    representation_image_path: str
    offset_x: int
    offset_y: int
    scale: float

def place_coordinate_on_image(
    image: cv2.typing.MatLike,
    coordinate: Tuple[int, int],
    coordinate_system: Literal['relative', 'tars'] = 'relative',
    coordinate_options: Union[VisibleDotCoordinateOptions, VisibleAnchoredEmbedImageOptions] = VisibleDotCoordinateOptions()
) -> cv2.typing.MatLike:
    height, width, _color_dims = image.shape
    processed_coordinate = coordinate
    if coordinate_system == 'relative':
        processed_coordinate = (int(coordinate[0] * width), int(coordinate[1] * height))
    elif coordinate_system == 'tars':
        processed_coordinate = TARSLikeBrowserAgentSystem.calculate_coordinate(
            original_image_height=height,
            original_image_width=width,
            model_output_height=coordinate[1],
            model_output_width=coordinate[0],
        )
    else:
        print(f"Unsupported coordinate system `{coordinate_system}`. Defaulting to keeping coordinate the same as input coordinate.")
    if isinstance(coordinate_options, VisibleDotCoordinateOptions):
        image_with_coordinate_embed = cv2.circle(image, processed_coordinate, **coordinate_options.model_dump())
    elif isinstance(coordinate_options, VisibleAnchoredEmbedImageOptions):
        # Use IMREAD_UNCHANGED to preserve alpha channel if present
        overlay = cv2.imread(coordinate_options.representation_image_path, cv2.IMREAD_UNCHANGED)
        # Define the position where the overlay will be placed
        x_coord = coordinate[0] + coordinate_options.offset_x
        y_coord = coordinate[1] + coordinate_options.offset_y
        # Get dimensions of the overlay
        h, w = overlay.shape[:2]
        # Extract the region of interest (ROI) from the background
        roi = image_with_coordinate_embed[y_coord:y_coord+h, x_coord:x_coord+w]
        # If the overlay has an alpha channel (transparency)
        if overlay.shape[2] == 4:
            # Split the overlay into BGR and Alpha channels
            overlay_bgr = overlay[:, :, :3]
            overlay_alpha = overlay[:, :, 3] / 255.0  # Normalize alpha to range [0, 1]
            # Blend the overlay with the ROI
            for c in range(3):  # Loop over B, G, R channels
                roi[:, :, c] = (overlay_alpha * overlay_bgr[:, :, c] + (1 - overlay_alpha) * roi[:, :, c])
        else:
            # If no alpha channel, simply replace the ROI with the overlay
            roi[:] = overlay
        # Place the blended ROI back into the background
        image_with_coordinate_embed[y_coord:y_coord+h, x_coord:x_coord+w] = roi
    else:
        print("Unsupported coordinate options. Failed to place coordinates on image.")
        return image_with_coordinate_embed
    return image_with_coordinate_embed
