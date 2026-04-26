# src/core/executor.py
# 执行器 - 任务执行逻辑

import asyncio
import json
from typing import Optional, List, Dict, Any

from src.services.gateway import AsyncGateway
from src.services.sandbox.docker import DockerSandbox
from src.services.mcp.client import MCPClient, MCPError

class AsyncAgentLegion:
    def __init__(self, trace_id: str = None, mcp_server_url: Optional[str] = None):
        self.trace_id = trace_id
        self.gateway = AsyncGateway(trace_id=trace_id)
        self.sandbox = DockerSandbox()
        self.mcp_client = MCPClient(mcp_server_url) if mcp_server_url else None
        self.tools = []

    async def initialize(self):
        """初始化执行器，发现MCP工具"""
        if self.mcp_client:
            try:
                self.tools = await self.mcp_client.discover_tools()
                print(f"[Executor] Discovered {len(self.tools)} MCP tools")
            except MCPError as e:
                print(f"[Executor] Failed to discover MCP tools: {e}")

    async def execute_task(self, task: str, task_type: str) -> str:
        # 检查是否使用MCP工具
        if self.mcp_client and self.tools:
            return await self._execute_with_mcp(task, task_type)
        else:
            # 回退到原始执行方式
            return await self._execute_with_gateway(task, task_type)

    async def _execute_with_mcp(self, task: str, task_type: str) -> str:
        """使用MCP工具执行任务"""
        messages = [
            {"role": "system", "content": f"你是一个专业的任务执行助手，根据任务类型提供详细的执行方案。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出结果。"},
            {"role": "user", "content": f"执行任务: {task}\n\n任务类型: {task_type}\n\n请提供详细的执行步骤和结果。"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)
            
            # 处理工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})
                    
                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)
                    
                    # 将工具执行结果添加到消息中
                    messages.append({"role": "tool", "content": json.dumps(tool_result)})
                    
                    # 再次调用MCP服务器处理工具执行结果
                    response = await self.mcp_client.chat_completion(messages)
            
            return response.content
        except MCPError as e:
            print(f"[MCP Execution Error] {e}")
            # 回退到原始执行方式
            return await self._execute_with_gateway(task, task_type)
        except Exception as e:
            print(f"[Execution Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "任务执行失败，请稍后重试。"

    async def _execute_with_gateway(self, task: str, task_type: str) -> str:
        """使用网关执行任务"""
        messages = [
            {"role": "system", "content": "你是一个专业的任务执行助手，根据任务类型提供详细的执行方案。"},
            {"role": "user", "content": f"执行任务: {task}\n\n任务类型: {task_type}\n\n请提供详细的执行步骤和结果。"}
        ]

        try:
            return await self.gateway.chat_completion(
                model="google/gemma-3-12b-it",
                messages=messages,
                domain_skill="Execution"
            )
        except Exception as e:
            print(f"[Execution Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "任务执行失败，请稍后重试。"

    async def analyze_task(self, task: str) -> Dict[str, Any]:
        # 检查是否使用MCP工具
        if self.mcp_client and self.tools:
            return await self._analyze_with_mcp(task)
        else:
            # 回退到原始执行方式
            return await self._analyze_with_gateway(task)

    async def _analyze_with_mcp(self, task: str) -> Dict[str, Any]:
        """使用MCP工具分析任务"""
        messages = [
            {"role": "system", "content": f"你是一个任务分析专家，负责分析用户的请求并确定最合适的执行路径。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出JSON对象。"},
            {"role": "user", "content": f"分析任务: {task}\n\n请输出一个JSON对象，包含以下字段：\n- task_type: 任务类型 (如 code_generation, analysis, research, creative)\n- complexity: 复杂度 (low, medium, high)\n- required_skills: 需要的技能列表\n- estimated_time: 估计执行时间（分钟）"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)
            
            # 处理工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})
                    
                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)
                    
                    # 将工具执行结果添加到消息中
                    messages.append({"role": "tool", "content": json.dumps(tool_result)})
                    
                    # 再次调用MCP服务器处理工具执行结果
                    response = await self.mcp_client.chat_completion(messages)
            
            try:
                return json.loads(response.content)
            except json.JSONDecodeError:
                print(f"[MCP Analysis Error] Invalid JSON response: {response.content}")
                return {
                    "task_type": "analysis",
                    "complexity": "medium",
                    "required_skills": ["general"],
                    "estimated_time": 5
                }
        except MCPError as e:
            print(f"[MCP Analysis Error] {e}")
            # 回退到原始执行方式
            return await self._analyze_with_gateway(task)
        except Exception as e:
            print(f"[Analysis Error] {e}")
            return {
                "task_type": "analysis",
                "complexity": "medium",
                "required_skills": ["general"],
                "estimated_time": 5
            }

    async def _analyze_with_gateway(self, task: str) -> Dict[str, Any]:
        """使用网关分析任务"""
        messages = [
            {"role": "system", "content": "你是一个任务分析专家，负责分析用户的请求并确定最合适的执行路径。"},
            {"role": "user", "content": f"分析任务: {task}\n\n请输出一个JSON对象，包含以下字段：\n- task_type: 任务类型 (如 code_generation, analysis, research, creative)\n- complexity: 复杂度 (low, medium, high)\n- required_skills: 需要的技能列表\n- estimated_time: 估计执行时间（分钟）"}
        ]

        try:
            response = await self.gateway.chat_completion(
                model="google/gemma-3-12b-it",
                messages=messages,
                domain_skill="Analysis"
            )
            return json.loads(response)
        except Exception as e:
            print(f"[Analysis Error] {e}")
            return {
                "task_type": "analysis",
                "complexity": "medium",
                "required_skills": ["general"],
                "estimated_time": 5
            }

    async def research_task(self, topic: str) -> str:
        # 检查是否使用MCP工具
        if self.mcp_client and self.tools:
            return await self._research_with_mcp(topic)
        else:
            # 回退到原始执行方式
            return await self._research_with_gateway(topic)

    async def _research_with_mcp(self, topic: str) -> str:
        """使用MCP工具进行研究"""
        messages = [
            {"role": "system", "content": f"你是一个专业的研究员，能够提供全面、准确的信息。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出研究结果。"},
            {"role": "user", "content": f"研究主题: {topic}\n\n请提供详细的研究结果，包括关键信息、背景知识和相关资源。"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)
            
            # 处理工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})
                    
                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)
                    
                    # 将工具执行结果添加到消息中
                    messages.append({"role": "tool", "content": json.dumps(tool_result)})
                    
                    # 再次调用MCP服务器处理工具执行结果
                    response = await self.mcp_client.chat_completion(messages)
            
            return response.content
        except MCPError as e:
            print(f"[MCP Research Error] {e}")
            # 回退到原始执行方式
            return await self._research_with_gateway(topic)
        except Exception as e:
            print(f"[Research Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "研究失败，请稍后重试。"

    async def _research_with_gateway(self, topic: str) -> str:
        """使用网关进行研究"""
        messages = [
            {"role": "system", "content": "你是一个专业的研究员，能够提供全面、准确的信息。"},
            {"role": "user", "content": f"研究主题: {topic}\n\n请提供详细的研究结果，包括关键信息、背景知识和相关资源。"}
        ]

        try:
            return await self.gateway.chat_completion(
                model="google/gemma-3-12b-it",
                messages=messages,
                domain_skill="Research"
            )
        except Exception as e:
            print(f"[Research Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "研究失败，请稍后重试。"

    async def create_task(self, request: str) -> str:
        # 检查是否使用MCP工具
        if self.mcp_client and self.tools:
            return await self._create_with_mcp(request)
        else:
            # 回退到原始执行方式
            return await self._create_with_gateway(request)

    async def _create_with_mcp(self, request: str) -> str:
        """使用MCP工具创建内容"""
        messages = [
            {"role": "system", "content": f"你是一个创意助手，能够根据用户需求生成各种内容。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出创建结果。"},
            {"role": "user", "content": f"创建请求: {request}\n\n请根据请求生成相应的内容，确保质量和原创性。"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)
            
            # 处理工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})
                    
                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)
                    
                    # 将工具执行结果添加到消息中
                    messages.append({"role": "tool", "content": json.dumps(tool_result)})
                    
                    # 再次调用MCP服务器处理工具执行结果
                    response = await self.mcp_client.chat_completion(messages)
            
            return response.content
        except MCPError as e:
            print(f"[MCP Creation Error] {e}")
            # 回退到原始执行方式
            return await self._create_with_gateway(request)
        except Exception as e:
            print(f"[Creation Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "创建失败，请稍后重试。"

    async def _create_with_gateway(self, request: str) -> str:
        """使用网关创建内容"""
        messages = [
            {"role": "system", "content": "你是一个创意助手，能够根据用户需求生成各种内容。"},
            {"role": "user", "content": f"创建请求: {request}\n\n请根据请求生成相应的内容，确保质量和原创性。"}
        ]

        try:
            return await self.gateway.chat_completion(
                model="google/gemma-3-12b-it",
                messages=messages,
                domain_skill="Creative"
            )
        except Exception as e:
            print(f"[Creation Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "创建失败，请稍后重试。"

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> Optional[str]:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url="http://localhost:1234/v1",
                api_key="lm-studio"
            )
            response = await client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[Local Model Error] {e}")
            return None