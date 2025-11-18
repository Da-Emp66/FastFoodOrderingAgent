import abc
import asyncio
import base64
from dataclasses import dataclass
import functools
import importlib
from inspect import signature, Parameter
from io import StringIO
import json
import os
from pathlib import Path
import re
import socket
import sys
from tempfile import NamedTemporaryFile
import traceback
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
import warnings
import cv2
import numpy as np
import typing_extensions
from box import Box
import dspy
from fastmcp.tools.tool import FunctionTool as FastMCPFunctionTool
from guidance import (
    json as generate_constrained_json,
    user as guidance_user,
    system as guidance_system,
    assistant as guidance_assistant,
)
from guidance.models import OpenAI as GuidanceOpenAI
from mcp import ClientSession, ClientSessionGroup, StdioServerParameters, Tool
from pydantic import BaseModel, create_model
import yaml

FINISH_TOKEN = "<|COMPLETED_OVERALL_TASK|>"

#########################################################
### Configuration
#########################################################

T = type
_BasicConfigType = Union[Box, dict, str]

def from_config(configuration: _BasicConfigType, coerced_type: T = Box) -> Union[Box, T]:
    if isinstance(configuration, coerced_type):
        return configuration
    elif issubclass(coerced_type, BaseModel) and not (isinstance(configuration, str) or isinstance(configuration, Path)):
        return coerced_type.model_validate(configuration)
    elif isinstance(configuration, dict):
        return coerced_type(configuration)
    elif isinstance(configuration, str) or isinstance(configuration, Path):
        with NamedTemporaryFile(
            dir=os.path.dirname(configuration),
            suffix=".yaml",
            mode="w+",
        ) as _configuration_file_with_env_variables_populated:
            _expanded_variable_string = os.path.expandvars(
                open(configuration).read()
            )\
            .replace("$HOSTNAME", socket.gethostname())\
            .replace("${HOSTNAME}", socket.gethostname())

            _configuration_file_with_env_variables_populated.write(_expanded_variable_string)
            _configuration_file_with_env_variables_populated.seek(0)

            loaded_configuration_file = yaml.safe_load(_configuration_file_with_env_variables_populated)
        if issubclass(coerced_type, BaseModel):
            return coerced_type.model_validate(loaded_configuration_file)
        else:
            try:
                return coerced_type(loaded_configuration_file)
            except Exception:
                return coerced_type(**loaded_configuration_file)
    else:
        raise TypeError(f"[Configuration] Failed to open configuration `{configuration}` of type `{type(configuration)}`.")

def load_yaml_string(yaml_string: str) -> Any:
    file_buffer = StringIO(yaml_string)
    file_buffer.write(yaml_string)
    file_buffer.seek(0)
    return yaml.safe_load(file_buffer)

def deprecated(message):
    def inner(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated. {message}",
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)
        return wrapper
    return inner

ENV_VAR_WITH_POSSIBLE_DEFAULT_PATTERN = re.compile(r"\$\{([^\}\:]+)(?:\:\-([^\}]+?))?\}|\$([A-Za-z0-9\_\-\\\/]+)")
def expand_env_vars_with_defaults_sub_repl(match):
    var_name = match.group(1) or match.group(3)
    default_value = match.group(2)
    return os.environ.get(var_name, default_value or "")
def expand_env_vars_with_defaults(s: str) -> str:
    """
    Expand environment variables like:
        $VAR
        ${VAR}
        ${VAR:-default}
    """
    return ENV_VAR_WITH_POSSIBLE_DEFAULT_PATTERN.sub(expand_env_vars_with_defaults_sub_repl, s)

def populate_environment_specifications(spec: Union[str, Dict[str, Any]], **kwargs):
    """Recursively populates a dictionary's keys and values or populates a string with environment variables."""
    if type(spec) == str:
        original = os.environ
        os.environ.update(kwargs)
        value = expand_env_vars_with_defaults(spec)
        os.environ = original
        return value
    elif type(spec) == dict:
        return {
            populate_environment_specifications(key, **kwargs): populate_environment_specifications(val, **kwargs)
            for key, val in spec.items()
        }
    elif type(spec) == list:
        return [populate_environment_specifications(item, **kwargs) for item in spec]
    else:
        return spec

MESSAGE_SPECIAL_TOKEN_PATTERN = re.compile(r"\<(?:\\|\||\w|\_|\d)*\>")
def extract_final_message_content(response: str):
    """Returns only the final response, with all proper thinking tokens and sections removed."""
    return re.split(MESSAGE_SPECIAL_TOKEN_PATTERN, response)[-1]

def remove_special_characters(original_string: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', original_string)

def sanitize_container_name(name: str) -> str:
    """
    Sanitize a string to make it a valid Docker container name.
    Docker container names must match the pattern: [a-zA-Z0-9][a-zA-Z0-9_.-]*
    
    This function:
    - Replaces @ and other invalid characters with hyphens
    - Ensures the name starts with alphanumeric character
    - Preserves only valid characters: letters, numbers, underscores, dots, and hyphens
    """
    # Replace @ and other invalid characters with hyphens
    sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '-', name)
    
    # Ensure it starts with alphanumeric character
    if sanitized and not sanitized[0].isalnum():
        sanitized = 'c' + sanitized
    
    return sanitized


class BaseModelJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any):
        if isinstance(obj, BaseModel):
            return obj.model_dump_json()
        return super().default(obj)

#########################################################
### Tools
#########################################################

class CustomToolSpecification(BaseModel):
    function_name: Optional[str]
    """The name of the function. None if it references the null function, but this must be specified explicitly."""
    import_spec: Optional[str] = None
    """The filepath to the file the function is defined in."""

LocalToolSpec = Union[str, CustomToolSpecification, Callable, FastMCPFunctionTool]

class ToolImportHook(BaseModel):
    spec: LocalToolSpec
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}

class MCPUserConfiguration(BaseModel):
    mcp_servers: Dict[str, StdioServerParameters] = {}
    custom_tools: List[LocalToolSpec] = []
    import_hooks: List[ToolImportHook] = []

class ApplicationConfiguration(BaseModel):
    agents: Dict[str, Any]

@dataclass
class McpToolFunctionWrapper:
    tool: Tool
    session: ClientSession
    async def __call__(self, **kwargs):
        result = await self.session.call_tool(name=self.tool.name, arguments=kwargs)
        return "\n".join(map(lambda text_content: text_content.text, result.content))

async def null_function():
    """The function that gets called when the model chooses not to call a function."""
    return "{}"

def find_or_return_function(function_spec: LocalToolSpec):
    if type(function_spec) == str:
        function_spec = CustomToolSpecification(function_name=function_spec)
    if isinstance(function_spec, Callable):
        return function_spec
    elif isinstance(function_spec, CustomToolSpecification):
        function_name = function_spec.function_name
        filepath = function_spec.import_spec
        if function_name is None: return null_function
        if function_spec.import_spec is not None:
            module_name = f"dynamic_{os.path.basename(filepath).replace('.py', '')}"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            if hasattr(module, function_name):
                return getattr(module, function_name)
            else:
                raise AttributeError(f"Function '{function_name}' not found in {filepath}")
        else:
            if function_name in globals():
                try:
                    return globals().get(function_name)
                except Exception as e:
                    NotImplementedError(
                        f"Tool with name `{function_name}` exists but is not callable. "
                        f"Error that indicates this: {e}"
                    )
            else:
                raise NotImplementedError(
                    f"Function name {function_name} not defined in `globals()`. "
                    "Did you mean to pass an `import_spec` to the filepath where that function is defined in your `CustomToolSpecification`?"
                )
    elif isinstance(function_spec, FastMCPFunctionTool):
        return function_spec.fn
    else:
        raise NotImplementedError(f"Function specification of type `{type(function_spec)}` not yet supported.")

class MockMCPToolSchemaDefinition:
    inputSchema: dict[str, Any] = {}

    def __init__(self, function_ref: Callable):
        self.inputSchema = self.function_args_to_schema(function_ref)
    
    def function_args_to_schema(self, func: Callable):
        """NOTE: Pydantic models in the signature are actually passed back as JSON dicts if using a ConstrainedToolCaller."""
        sig = signature(func)
        fields = {}
        for name, param in sig.parameters.items():
            annotation = param.annotation if param.annotation != Parameter.empty else Any
            default = param.default if param.default != Parameter.empty else ...
            fields[name] = (annotation, default)
        return create_model(f"{func.__name__.capitalize()}Schema", **fields).model_json_schema()

class BasicToolFunctionWrapper:
    tool: Optional[MockMCPToolSchemaDefinition] = None

    def __init__(self, function: LocalToolSpec):
        self.function_ref = find_or_return_function(function)
        self.tool = MockMCPToolSchemaDefinition(self.function_ref)
    
    async def __call__(self, **kwargs):
        result = await self.function_ref(**kwargs)
        return result
    
UsableTool = Union[
    McpToolFunctionWrapper,
    BasicToolFunctionWrapper,
    Any,
]

class GeneratedToolSpec(BaseModel):
    tool: str
    args: Dict[str, Any] = {}

@dataclass
class GeneratedTool:
    usable: UsableTool
    spec: GeneratedToolSpec

@dataclass
class ToolReport:
    generated_tool: GeneratedTool
    result: str

class ToolCaller(metaclass=abc.ABCMeta):
    configuration: Optional[_BasicConfigType] = None
    tools: Dict[str, UsableTool] = {}

    async def initialize_tools(self): pass

    @abc.abstractmethod
    async def determine_tool(self, **kwargs) -> GeneratedTool: raise NotImplementedError()
    
    async def call_tool(self, generated_tool: GeneratedTool, **kwargs) -> str:
        return str(await generated_tool.usable(**generated_tool.spec.args))
    
    async def determine_and_call_tools(self, **kwargs) -> ToolReport:
        try:
            generated_tool = await self.determine_tool(**kwargs)
        except Exception as e:
            generated_tool = None
            result = f"Failed to call tool: {e}"

        if generated_tool is not None:
            try:
                result = await self.call_tool(generated_tool)
            except Exception as e:
                result = f"Failed to call tool {generated_tool.spec}: {e}"

        return ToolReport(
            generated_tool=generated_tool,
            result=result,
        )

class DSPyToolCaller(ToolCaller):
    async def initialize_tools(self, tool_prediction_signature: type[dspy.Signature]):
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        updated_mcp_servers = {}
        for server_name, server_params in self.configuration.mcp_servers.items():
            server_params.env = os.environ.copy()
            updated_mcp_servers[server_name] = server_params
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in updated_mcp_servers.items() }
        # Initialize DSPy tools
        tools = [dspy.Tool(find_or_return_function(tool_function)) for tool_function in self.configuration.custom_tools]
        for _session_name, session in self.mcp_sessions.items():
            session_tools = (await session.list_tools()).tools
            dspy_session_tools = [dspy.Tool.from_mcp_tool(session, tool) for tool in session_tools]
            tools += dspy_session_tools
        self.tools = {tool.name: tool for tool in tools}
        # Instantiate tool predictor
        self.tool_prediction = dspy.Predict(
            tool_prediction_signature
                .prepend(
                    "selected_tool_name",
                    dspy.OutputField(),
                    type_=Literal[tuple(self.tools.keys())]
                )
                .prepend(
                    "selected_tool_args",
                    dspy.OutputField(desc="This should ALWAYS be a valid JSON. If using browser_click, always pass the JSON fields 'element' and 'ref' as their string values based on the 'task' and 'current_browser_snapshot' definitions."),
                    type_=dict[str, Any],
                )
        )
        self.stream_tool_prediction = dspy.streamify(self.tool_prediction)
    
    async def determine_tool(self, **kwargs) -> GeneratedTool:
        # Create the output stream object based on the current task
        output_stream = self.stream_tool_prediction(**kwargs)
        # Show the LLM's outputs as it generates the tool prediction
        async for chunk in output_stream:
            if isinstance(chunk, dspy.streaming.StreamResponse):
                print(chunk.chunk, end="", flush=True)
            elif isinstance(chunk, dspy.Prediction):
                tool_prediction_response = chunk.toDict()
        selected_tool_name = tool_prediction_response.get("selected_tool_name", None)
        selected_tool_args = tool_prediction_response.get("selected_tool_args", None)
        if selected_tool_name in self.tools:
            try:
                # Correct a common formatting mistake in JSON structure
                if selected_tool_name in selected_tool_args and \
                    isinstance(selected_tool_args[selected_tool_name], dict):
                    selected_tool_args = selected_tool_args[selected_tool_name]
            except Exception as e:
                print(f"Error in correcting JSON: {e}")
            print(f"Tool: {selected_tool_name}")
            print(f"Args: {selected_tool_args}")
            tool = self.tools[selected_tool_name]
        else:
            raise ValueError(f"Tool {selected_tool_name} not in list of available tools. List of available tools is {list(self.tools.keys())}.")
        
        return GeneratedTool(
            usable=tool,
            spec=GeneratedToolSpec(
                tool=selected_tool_name,
                args=selected_tool_args,
            )
        )

    async def call_tool(self, generated_tool: GeneratedTool, **kwargs) -> str:
        return str(await generated_tool.usable.acall(**generated_tool.spec.args))

class SamplingParams(typing_extensions.TypedDict):
    """Mirrors `from guidance._schema import SamplingParams` but with Python3.10 Pydantic support."""
    top_p: typing_extensions.NotRequired[float] = None
    top_k: typing_extensions.NotRequired[int] = None
    min_p: typing_extensions.NotRequired[float] = None
    repetition_penalty: typing_extensions.NotRequired[float] = None
    
class ConstrainedToolCallerGenerationConfiguration(BaseModel):
    sampling_params: SamplingParams = SamplingParams()
    temperature: float = 0.0

class ConstrainedToolCallerConfiguration(MCPUserConfiguration):
    tool_system_prompt: str
    tool_selection_user_prompt_format: str
    tool_args_user_prompt_format: str
    tool_generation_params: ConstrainedToolCallerGenerationConfiguration = ConstrainedToolCallerGenerationConfiguration(
        sampling_params=SamplingParams(top_p=0.9),
        temperature=0.7,
    )

class ConstrainedToolCaller(ToolCaller):
    def __init__(self, configuration: ConstrainedToolCallerConfiguration):
        if isinstance(configuration, ConstrainedToolCallerConfiguration):
            self.configuration: ConstrainedToolCallerConfiguration = configuration
        else:
            self.configuration: ConstrainedToolCallerConfiguration = from_config(configuration, ConstrainedToolCallerConfiguration)

        self.tools = {}
        self.lm = GuidanceOpenAI(
            "o1-" + os.getenv("MODEL"),
            echo=True,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            sampling_params=SamplingParams(**self.configuration.tool_generation_params.sampling_params),
        )

    async def initialize_tools(self):
        tools = {}
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        updated_mcp_servers = {}
        for server_name, server_params in self.configuration.mcp_servers.items():
            server_params.env = os.environ.copy()
            updated_mcp_servers[server_name] = server_params
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in updated_mcp_servers.items() }
        for _session_name, session in self.mcp_sessions.items():
            session_tools = (await session.list_tools()).tools
            tools.update({tool.name: McpToolFunctionWrapper(tool=tool, session=session) for tool in session_tools})
        for import_hook in self.configuration.import_hooks:
            hook = find_or_return_function(import_hook.spec)
            await hook(*import_hook.args, **import_hook.kwargs)
        for tool in self.configuration.custom_tools:
            tool = find_or_return_function(tool)
            if hasattr(tool, "__name__"):
                tool_name = tool.__name__
            elif hasattr(tool, "name"):
                tool_name = tool.name
            else:
                raise f"Tool {tool} is neither a custom function or a locally-referenced MCP function."
            tools.update({tool_name: BasicToolFunctionWrapper(tool)})
        self.tools = tools
        tool_options = list(self.tools.keys())
        with guidance_system():
            self.lm += self.configuration.tool_system_prompt \
                .replace("{tool_options}", yaml.safe_dump(tool_options))

    async def determine_tool(self, skip_args: bool = False, **kwargs) -> GeneratedTool:
        success = False
        while not success:
            try:
                tool_options = list(self.tools.keys())
                with guidance_user():
                    user_prompt = self.configuration.tool_selection_user_prompt_format \
                        .replace("{tool_options}", yaml.safe_dump(tool_options))
                    user_prompt = self.format_prompt_string_with_arguments(user_prompt, kwargs)
                    self.lm += user_prompt
                name = None
                with guidance_assistant():
                    self.lm += generate_constrained_json(name='tool_name_json', schema={
                            'properties': {
                                'tool_name': {
                                    'enum': list(self.tools.keys()),
                                    'title': 'Tool Name',
                                    'type': 'string'
                                }
                            },
                            'required': ['tool_name'],
                            'title': 'ToolName',
                            'type': 'object',
                        },
                        temperature=self.configuration.tool_generation_params.temperature,
                        # logit_bias=logit_bias,
                    )
                    name = json.loads(self.lm["tool_name_json"])["tool_name"]
                    if skip_args and name in self.tools:
                        return GeneratedTool(usable=self.tools[name], spec=GeneratedToolSpec(tool=name, args={}))
                with guidance_user():
                    user_prompt = self.configuration.tool_args_user_prompt_format.replace("{name}", name)
                    user_prompt = self.format_prompt_string_with_arguments(user_prompt, kwargs)
                    self.lm += user_prompt
                with guidance_assistant():
                    if name in self.tools:
                        selected_tool = self.tools[name]
                        print(selected_tool.tool.inputSchema)
                        self.lm += generate_constrained_json(
                            name="generated_args",
                            schema=selected_tool.tool.inputSchema,
                            temperature=self.configuration.tool_generation_params.temperature,
                        )
                        args = json.loads(self.lm["generated_args"])
                        selected_tool_representation = str({"tool": name, "args": args})
                        print(selected_tool_representation)
                    else:
                        raise ValueError(f"Tool {name} is not valid. Please select from the list of valid tools: {list(self.tools.keys())}")
                    
                    return GeneratedTool(
                        usable=selected_tool,
                        spec=GeneratedToolSpec(
                            tool=name,
                            args=args,
                        )
                    )
            except Exception as e:
                print(traceback.format_exc())
                print(f"Encountered exception when determining tool for constrained generation: {str(e)}")
                print("Retrying in 5 seconds...")
                asyncio.sleep(5)
                print("Retrying...")
    
    def format_prompt_string_with_arguments(self, prompt: str, kwargs: Dict[str, Any]):
        for key, val in kwargs.items(): 
            # Convert value to string, handling Pydantic models and None specially
            if val is None:
                val_str = "null"
            elif isinstance(val, BaseModel):
                val_str = val.model_dump_json()
            else:
                val_str = str(val)
            prompt = prompt.replace(f"{{{key}}}", val_str)
        return prompt
    
    def extract_via_schema(self, prompt: str, schema_cls: type[BaseModel], **kwargs) -> BaseModel:
        success = False
        while not success:
            try:
                schema = schema_cls.model_json_schema()
                with guidance_user():
                    prompt = self.format_prompt_string_with_arguments(prompt, kwargs)
                    self.lm += prompt
                with guidance_assistant():
                    self.lm += generate_constrained_json(
                        name="extracted_values",
                        schema=schema,
                        temperature=0.0, # 0.0 temperature for extraction task
                    )
                    extracted = schema_cls.model_validate_json(self.lm["extracted_values"])
                    success = True
                    return extracted
            except Exception as e:
                print(traceback.format_exc())
                print(f"Encountered exception when determining tool for constrained generation: {str(e)}")
                print("Retrying in 5 seconds...")
                asyncio.sleep(5)
                print("Retrying...")

class History(BaseModel):
    messages: List[Dict[str, Any]] = []

#########################################################
### Image
#########################################################

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
        from core.web.tars_like import TARSLikeBrowserAgentSystem
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

class AbsolutePixelwiseSize(BaseModel):
    width: int
    height: int

class Relative2DScale(BaseModel):
    scale_x: float = 0.7
    scale_y: float = 0.7

ImageResizeConfiguration = Union[AbsolutePixelwiseSize, Relative2DScale]

def resize_cv2_image(image: cv2.typing.MatLike, params: ImageResizeConfiguration):
    if isinstance(params, Relative2DScale):
        image = cv2.resize(image, None, fx=params.scale_x, fy=params.scale_y, interpolation=cv2.INTER_LINEAR)
    elif isinstance(params, AbsolutePixelwiseSize):
        image = cv2.resize(image, (params.width, params.height), interpolation=cv2.INTER_LINEAR)
    return image

def cv2_image_to_base64(image: cv2.typing.MatLike, file_type='.jpg') -> str:
    _, buffer = cv2.imencode(file_type, image)
    return base64.b64encode(buffer).decode('utf-8')

def create_black_image(width=256, height=256, channels=1) -> cv2.typing.MatLike:
    """
    Create an all-black image using OpenCV and NumPy.

    Args:
        width (int): Width of the image in pixels.
        height (int): Height of the image in pixels.
        channels (int): Number of color channels (1=grayscale, 3=RGB/BGR).

    Returns:
        np.ndarray: Black image array.
    """
    # Validate inputs
    if not (isinstance(width, int) and isinstance(height, int) and isinstance(channels, int)):
        raise ValueError("Width, height, and channels must be integers.")
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive integers.")
    if channels not in (1, 3, 4):
        raise ValueError("Channels must be 1 (grayscale), 3 (BGR), or 4 (BGRA).")
    # Create a black image (all zeros)
    black_img = np.zeros((height, width, channels), dtype=np.uint8)
    return black_img

def present_or_black(image: Optional[cv2.typing.MatLike] = None) -> cv2.typing.MatLike:
    return image if image is not None else create_black_image()

def IoU(boxA: List[float], boxB: List[float]):
    # Unpack coordinates
    xA1, yA1, xA2, yA2 = tuple(boxA)
    xB1, yB1, xB2, yB2 = tuple(boxB)
    # Compute intersection
    x_left = max(xA1, xB1)
    y_top = max(yA1, yB1)
    x_right = min(xA2, xB2)
    y_bottom = min(yA2, yB2)
    if x_right < x_left or y_bottom < y_top:
        return 0.0  # No overlap
    intersection = (x_right - x_left) * (y_bottom - y_top)
    # Compute areas
    areaA = (xA2 - xA1) * (yA2 - yA1)
    areaB = (xB2 - xB1) * (yB2 - yB1)
    # Compute union
    union = areaA + areaB - intersection
    return intersection / union
