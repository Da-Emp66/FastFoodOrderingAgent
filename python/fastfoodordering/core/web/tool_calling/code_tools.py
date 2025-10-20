
from typing import Any, Dict, Union
from core.utils import MCPUserConfiguration, from_config
from core.web.tool_calling.interface import BrowserToolCaller

class CodeBrowserToolCallerConfiguration(MCPUserConfiguration): pass
class CodeBrowserToolCaller(BrowserToolCaller):
    def __init__(self, configuration: Union[Dict[str, Any], CodeBrowserToolCallerConfiguration]):
        self.configuration: CodeBrowserToolCallerConfiguration = from_config(configuration, CodeBrowserToolCallerConfiguration)

    async def initialize_tools(self):
        # # Create the MCP session and initialize tools
        # self.group = ClientSessionGroup(component_name_hook=lambda name, server_info: f"{(server_info.name)}_{name}")
        # self.mcp_sessions = { server_name: (await self.group.connect_to_server(server_params)) for server_name, server_params in self.configuration.mcp_servers.items() }
        raise NotImplementedError()
