from io import StringIO
import os
from pathlib import Path
import socket
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List, Optional, Union
from box import Box
import cv2
import dspy
from mcp import StdioServerParameters
import numpy as np
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
