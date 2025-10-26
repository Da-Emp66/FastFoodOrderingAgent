import abc
from dataclasses import dataclass
import importlib
from inspect import signature, Parameter
from io import StringIO
import json
import os
from pathlib import Path
import socket
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
import typing_extensions
from box import Box
import dspy
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

def populate_environment_specifications(spec: Union[str, Dict[str, Any]], **kwargs):
    """Recursively populates a dictionary's keys and values or populates a string with environment variables."""
    if type(spec) == str:
        previous = os.environ
        os.environ.update(kwargs)
        value = os.path.expandvars(spec)
        os.environ = previous
        return value
    elif type(spec) == dict:
        return {
            populate_environment_specifications(key, kwargs=kwargs): populate_environment_specifications(val, kwargs=kwargs)
            for key, val in spec
        }
    else:
        return spec

def extract_final_message_content(response: str):
    """Returns only the final response, with all proper thinking tokens and sections removed."""
    return response.split("|>")[-1]

class CustomToolSpecification(BaseModel):
    function_name: Optional[str]
    """The name of the function. None if it references the null function, but this must be specified explicitly."""
    import_spec: Optional[str] = None
    """The filepath to the file the function is defined in."""

LocalToolSpec = Union[str, CustomToolSpecification, Callable]

class MCPUserConfiguration(BaseModel):
    mcp_servers: Dict[str, StdioServerParameters] = {}
    custom_tools: List[LocalToolSpec] = []

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
    return

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
            spec = importlib.util.spec_from_file_location("dynamic_module", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, function_name):
                return getattr(module, function_name)
            else:
                raise AttributeError(f"Function '{function_name}' not found in {filepath}")
        else:
            if function_name in globals():
                try:
                    return callable(globals().get(function_name))
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
    else:
        raise NotImplementedError(f"Function specification of type `{type(function_spec)}` not yet supported.")

class MockMCPToolSchemaDefinition:
    inputSchema: dict[str, Any] = {}

    def __init__(self, function_ref: Callable):
        self.inputSchema = self.function_args_to_schema(function_ref)
    
    def function_args_to_schema(self, func: Callable):
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

class ToolCaller(metaclass=abc.ABCMeta):
    configuration: Optional[_BasicConfigType] = None
    tools: Dict[str, UsableTool] = {}
    async def initialize_tools(self): pass
    @abc.abstractmethod
    async def determine_and_call_tools(self, **kwargs) -> Tuple[str, str]: raise NotImplementedError()

class DSPyToolCaller(ToolCaller):
    async def initialize_tools(self, tool_prediction_signature: type[dspy.Signature]):
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
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
    
    async def determine_and_call_tools(self, **kwargs):
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
                tool_call_result = await tool.acall(**selected_tool_args)
            except Exception as e:
                print(e)
                tool_call_result = e
        else:
            tool_call_result = f"Tool {selected_tool_name} not in list of available tools. List of available tools is {list(self.tools.keys())}."
        print({"tool": selected_tool_name, "args": selected_tool_args})
        print(tool_call_result)
        return str({"tool": selected_tool_name, "args": selected_tool_args}), tool_call_result

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
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
        for _session_name, session in self.mcp_sessions.items():
            session_tools = (await session.list_tools()).tools
            tools.update({tool.name: McpToolFunctionWrapper(tool=tool, session=session) for tool in session_tools})
        for tool in self.configuration.custom_tools:
            tool = find_or_return_function(tool)
            tools.update({tool.__name__: BasicToolFunctionWrapper(tool)})
        self.tools = tools
        tool_options = list(self.tools.keys())
        with guidance_system():
            self.lm += self.configuration.tool_system_prompt \
                .replace("{tool_options}", yaml.safe_dump(tool_options))

    async def determine_and_call_tools(self, **kwargs):
        tool_options = list(self.tools.keys())
        with guidance_user():
            user_prompt = self.configuration.tool_selection_user_prompt_format \
                .replace("{tool_options}", yaml.safe_dump(tool_options))
            for key, val in kwargs.items(): user_prompt = user_prompt.replace(key, str(val))
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
        with guidance_user():
            user_prompt = self.configuration.tool_args_user_prompt_format.replace("{name}", name)
            for key, val in kwargs.items(): user_prompt = user_prompt.replace(key, str(val))
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
                try:
                    result = await selected_tool(**args)
                    return selected_tool_representation, result
                except Exception as e:
                    return selected_tool_representation, str(e)
            else:
                return (
                    str({"tool": name, "args": {}}),
                    f"Tool {name} is not valid. Please select from the list of valid tools: {list(self.tools.keys())}"
                )
    