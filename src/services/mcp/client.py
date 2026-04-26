# src/services/mcp/client.py
# MCP 客户端 - 实现与 MCP 服务器的通信

import asyncio
import json
import httpx
from typing import Optional, Dict, Any, List

class MCPError(Exception):
    """MCP 相关错误"""
    pass

class MCPTool:
    """MCP 工具定义"""
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters

class MCPResponse:
    """MCP 响应"""
    def __init__(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.content = content
        self.tool_calls = tool_calls or []

class MCPClient:
    """MCP 客户端"""
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.tools = []

    async def discover_tools(self) -> List[MCPTool]:
        """发现 MCP 服务器提供的工具"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.server_url}/tools")
                response.raise_for_status()
                tools_data = response.json()
                
                self.tools = []
                for tool_data in tools_data:
                    tool = MCPTool(
                        name=tool_data.get("name"),
                        description=tool_data.get("description"),
                        parameters=tool_data.get("parameters", {})
                    )
                    self.tools.append(tool)
                
                return self.tools
        except Exception as e:
            raise MCPError(f"Failed to discover tools: {e}")

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行 MCP 工具"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/execute",
                    json={
                        "tool": tool_name,
                        "parameters": parameters
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise MCPError(f"Failed to execute tool: {e}")

    async def chat_completion(self, messages: List[Dict[str, str]]) -> MCPResponse:
        """与 MCP 服务器进行聊天完成"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/chat",
                    json={"messages": messages}
                )
                response.raise_for_status()
                response_data = response.json()
                
                return MCPResponse(
                    content=response_data.get("content", ""),
                    tool_calls=response_data.get("tool_calls", [])
                )
        except Exception as e:
            raise MCPError(f"Failed to chat completion: {e}")

    def get_tool_by_name(self, tool_name: str) -> Optional[MCPTool]:
        """根据名称获取工具"""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None

    def get_tools_description(self) -> str:
        """获取工具描述，用于构建提示词"""
        if not self.tools:
            return "No tools available."
        
        tools_desc = "Available tools:\n"
        for tool in self.tools:
            tools_desc += f"- {tool.name}: {tool.description}\n"
            if tool.parameters:
                tools_desc += "  Parameters:\n"
                for param_name, param_info in tool.parameters.items():
                    tools_desc += f"    {param_name}: {param_info.get('description', '')} (type: {param_info.get('type', 'string')})\n"
        
        return tools_desc