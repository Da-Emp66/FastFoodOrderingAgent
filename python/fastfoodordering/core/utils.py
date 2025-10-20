import abc
from dataclasses import dataclass
from io import StringIO
import json
import os
from pathlib import Path
import socket
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
from box import Box
import dspy
from guidance import (
    json as generate_constrained_json,
    user as guidance_user,
    assistant as guidance_assistant,
)
from mcp import ClientSession, ClientSessionGroup, StdioServerParameters, Tool
from pydantic import BaseModel
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

class MCPUserConfiguration(BaseModel):
    mcp_servers: Dict[str, StdioServerParameters] = {}
    custom_tools: List[Callable] = []

class ApplicationConfiguration(BaseModel):
    agents: Dict[str, Any]

@dataclass
class McpToolFunctionWrapper:
    tool: Tool
    session: ClientSession
    async def __call__(self, **kwargs):
        result = await self.session.call_tool(name=self.tool.name, arguments=kwargs)
        return "\n".join(map(lambda text_content: text_content.text, result.content))

class ToolCaller(metaclass=abc.ABCMeta):
    configuration: Optional[_BasicConfigType] = None
    tools: Dict[str, Any] = {}
    async def initialize_tools(self): pass
    @abc.abstractmethod
    async def determine_and_call_tools(self, **kwargs) -> Tuple[str, str]: raise NotImplementedError()

class DSPyToolCaller(ToolCaller):
    async def initialize_tools(self, tool_prediction_signature: type[dspy.Signature]):
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
        # Initialize DSPy tools
        tools = [dspy.Tool(tool_function) for tool_function in self.configuration.custom_tools]
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

class ConstrainedToolCaller(ToolCaller):
    async def initialize_tools(self):
        tools = {}
        # Create the MCP session and initialize tools
        self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
        for _session_name, session in self.mcp_sessions.items():
            session_tools = (await session.list_tools()).tools
            tools.update({tool.name: McpToolFunctionWrapper(tool=tool, session=session) for tool in session_tools})
        # TODO:
        # for tool in self.configuration.custom_tools: ...
        self.tools = tools

    async def determine_and_call_tools(self, **kwargs):
        with guidance_user():
            user_prompt = self.configuration.tool_selection_user_prompt_format
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
            })
            name = json.loads(self.lm["tool_name_json"])["tool_name"]
        with guidance_user():
            user_prompt = self.configuration.tool_args_user_prompt_format.replace("{name}", name)
            for key, val in kwargs.items(): user_prompt = user_prompt.replace(key, str(val))
            self.lm += user_prompt
        with guidance_assistant():
            if name in self.tools:
                selected_tool = self.tools[name]
                print(selected_tool.tool.inputSchema)
                self.lm += generate_constrained_json(name="generated_args", schema=selected_tool.tool.inputSchema)
                args = json.loads(self.lm["generated_args"])
                selected_tool_representation = str({"tool": name, "args": args})
                print(selected_tool_representation)
                try:
                    result = await selected_tool(**args)
                    return selected_tool_representation, result
                except Exception as e:
                    return selected_tool_representation, str(e)
            else:
                return str({"tool": name, "args": {}}), f"Tool {name} is not valid. Please select from the list of valid tools: {list(self.tools.keys())}"
    