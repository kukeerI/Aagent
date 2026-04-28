# src/core/executor.py
# 任务执行器 - 负责任务执行、MCP 工具调用、模型降级处理
# 依赖：AsyncGateway, DockerSandbox, MCPClient, IntentAnalyzer, TaskAnalyzer
# 注意事项：
#   - 所有执行方法优先使用 MCP 工具，失败时回退到网关
#   - 本地模型作为最后的降级方案
#   - 使用结构化日志记录执行过程

import asyncio
import json
from typing import Optional, List, Dict, Any

from src.services.gateway import AsyncGateway
from src.services.sandbox.docker import DockerSandbox
from src.services.mcp.client import MCPClient, MCPError
from src.data.domain_models import IntentAnalysis, RouteLevel
from src.core.exceptions import (
    ModelInferenceError,
    CodeExecutionError,
    TimeoutError
)

logger = __import__('src.utils.logger', fromlist=['logger']).logger


class AgentExecutor:
    """任务执行器 - 提供任务执行、研究、创作等多种执行能力"""

    def __init__(self, trace_id: str = None, mcp_server_url: Optional[str] = None):
        """初始化执行器

        Args:
            trace_id: 追踪 ID，用于日志关联
            mcp_server_url: MCP 服务器地址，为空则不使用 MCP 工具
        """
        self.trace_id = trace_id
        self.gateway = AsyncGateway(trace_id=trace_id)
        self.sandbox = DockerSandbox()
        self.mcp_client = MCPClient(mcp_server_url) if mcp_server_url else None
        self.tools = []
        self.local_client = None

    async def initialize(self):
        """初始化执行器，发现 MCP 工具

        Raises:
            MCPError: MCP 工具发现失败时抛出
        """
        if self.mcp_client:
            try:
                self.tools = await self.mcp_client.discover_tools()
                logger.info(f"[Executor] 已发现 {len(self.tools)} 个 MCP 工具")
            except MCPError as e:
                logger.error(f"[Executor] 发现 MCP 工具失败: {e}")

    async def execute_task(self, task: str, task_type: str) -> str:
        """执行任务

        Args:
            task: 任务描述
            task_type: 任务类型（如 Execute, Research, Create）

        Returns:
            str: 任务执行结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        if self.mcp_client and self.tools:
            return await self._execute_with_mcp(task, task_type)
        else:
            return await self._execute_with_gateway(task, task_type)

    async def _execute_with_mcp(self, task: str, task_type: str) -> str:
        """使用 MCP 工具执行任务

        Args:
            task: 任务描述
            task_type: 任务类型

        Returns:
            str: 任务执行结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        messages = [
            {"role": "system", "content": f"你是一个专业的任务执行助手，根据任务类型提供详细的执行方案。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出结果。"},
            {"role": "user", "content": f"执行任务: {task}\n\n任务类型: {task_type}\n\n请提供详细的执行步骤和结果。"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})

                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)

                    messages.append({"role": "tool", "content": json.dumps(tool_result)})

                    response = await self.mcp_client.chat_completion(messages)

            return response.content
        except MCPError as e:
            logger.error(f"[MCP Execution Error] {e}")
            return await self._execute_with_gateway(task, task_type)
        except Exception as e:
            logger.error(f"[Execution Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "任务执行失败，请稍后重试。"

    async def _execute_with_gateway(self, task: str, task_type: str) -> str:
        """使用网关执行任务

        Args:
            task: 任务描述
            task_type: 任务类型

        Returns:
            str: 任务执行结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        messages = [
            {"role": "system", "content": "你是一个专业的任务执行助手，根据任务类型提供详细的执行方案。"},
            {"role": "user", "content": f"执行任务: {task}\n\n任务类型: {task_type}\n\n请提供详细的执行步骤和结果。"}
        ]

        try:
            from src.config import config
            return await self.gateway.chat_completion(
                model=config.DEFAULT_EXECUTION_MODEL,
                messages=messages,
                domain_skill="Execution"
            )
        except Exception as e:
            logger.error(f"[Execution Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "任务执行失败，请稍后重试。"

    async def analyze_task(self, task: str) -> IntentAnalysis:
        """分析任务

        Args:
            task: 任务描述

        Returns:
            IntentAnalysis: 意图分析结果
        """
        if self.mcp_client and self.tools:
            return await self._analyze_with_mcp(task)
        else:
            return await self._analyze_with_gateway(task)

    async def _analyze_with_mcp(self, task: str) -> IntentAnalysis:
        """使用 MCP 工具分析任务

        Args:
            task: 任务描述

        Returns:
            IntentAnalysis: 意图分析结果
        """
        from src.core.intent_analyzer import IntentAnalyzer
        from src.core.task_analyzer import task_analyzer

        semantic_data = await task_analyzer.extract_semantic_data(task)

        intent_data = IntentAnalyzer.analyze_intent(task, semantic_data)

        return IntentAnalysis(
            value=intent_data["value"],
            complexity=intent_data["complexity"],
            innovation=intent_data["innovation"],
            route_level=intent_data["route_level"],
            route_name=intent_data["route_name"]
        )

    async def _analyze_with_gateway(self, task: str) -> IntentAnalysis:
        """使用网关分析任务

        Args:
            task: 任务描述

        Returns:
            IntentAnalysis: 意图分析结果
        """
        from src.core.intent_analyzer import IntentAnalyzer
        from src.core.task_analyzer import task_analyzer

        semantic_data = await task_analyzer.extract_semantic_data(task)

        intent_data = IntentAnalyzer.analyze_intent(task, semantic_data)

        return IntentAnalysis(
            value=intent_data["value"],
            complexity=intent_data["complexity"],
            innovation=intent_data["innovation"],
            route_level=intent_data["route_level"],
            route_name=intent_data["route_name"]
        )

    async def research_task(self, topic: str) -> str:
        """执行研究任务

        Args:
            topic: 研究主题

        Returns:
            str: 研究结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        if self.mcp_client and self.tools:
            return await self._research_with_mcp(topic)
        else:
            return await self._research_with_gateway(topic)

    async def _research_with_mcp(self, topic: str) -> str:
        """使用 MCP 工具进行研究

        Args:
            topic: 研究主题

        Returns:
            str: 研究结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        messages = [
            {"role": "system", "content": f"你是一个专业的研究员，能够提供全面、准确的信息。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出研究结果。"},
            {"role": "user", "content": f"研究主题: {topic}\n\n请提供详细的研究结果，包括关键信息、背景知识和相关资源。"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})

                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)

                    messages.append({"role": "tool", "content": json.dumps(tool_result)})

                    response = await self.mcp_client.chat_completion(messages)

            return response.content
        except MCPError as e:
            logger.error(f"[MCP Research Error] {e}")
            return await self._research_with_gateway(topic)
        except Exception as e:
            logger.error(f"[Research Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "研究失败，请稍后重试。"

    async def _research_with_gateway(self, topic: str) -> str:
        """使用网关进行研究

        Args:
            topic: 研究主题

        Returns:
            str: 研究结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        messages = [
            {"role": "system", "content": "你是一个专业的研究员，能够提供全面、准确的信息。"},
            {"role": "user", "content": f"研究主题: {topic}\n\n请提供详细的研究结果，包括关键信息、背景知识和相关资源。"}
        ]

        try:
            from src.config import config
            return await self.gateway.chat_completion(
                model=config.DEFAULT_RESEARCH_MODEL,
                messages=messages,
                domain_skill="Research"
            )
        except Exception as e:
            logger.error(f"[Research Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "研究失败，请稍后重试。"

    async def create_task(self, request: str) -> str:
        """执行创作任务

        Args:
            request: 创作请求

        Returns:
            str: 创作结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        if self.mcp_client and self.tools:
            return await self._create_with_mcp(request)
        else:
            return await self._create_with_gateway(request)

    async def _create_with_mcp(self, request: str) -> str:
        """使用 MCP 工具创建内容

        Args:
            request: 创作请求

        Returns:
            str: 创作结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        messages = [
            {"role": "system", "content": f"你是一个创意助手，能够根据用户需求生成各种内容。\n\n{self.mcp_client.get_tools_description()}\n\n如果需要使用工具，请按照以下格式输出：\n\n```tool\n{tool_name}\n{json.dumps(parameters)}\n```\n\n否则，直接输出创建结果。"},
            {"role": "user", "content": f"创建请求: {request}\n\n请根据请求生成相应的内容，确保质量和原创性。"}
        ]

        try:
            response = await self.mcp_client.chat_completion(messages)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    parameters = tool_call.get("parameters", {})

                    tool_result = await self.mcp_client.execute_tool(tool_name, parameters)

                    messages.append({"role": "tool", "content": json.dumps(tool_result)})

                    response = await self.mcp_client.chat_completion(messages)

            return response.content
        except MCPError as e:
            logger.error(f"[MCP Creation Error] {e}")
            return await self._create_with_gateway(request)
        except Exception as e:
            logger.error(f"[Creation Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "创建失败，请稍后重试。"

    async def _create_with_gateway(self, request: str) -> str:
        """使用网关创建内容

        Args:
            request: 创作请求

        Returns:
            str: 创作结果

        Raises:
            ModelInferenceError: 模型推理失败且无降级方案时抛出
        """
        messages = [
            {"role": "system", "content": "你是一个创意助手，能够根据用户需求生成各种内容。"},
            {"role": "user", "content": f"创建请求: {request}\n\n请根据请求生成相应的内容，确保质量和原创性。"}
        ]

        try:
            from src.config import config
            return await self.gateway.chat_completion(
                model=config.DEFAULT_CREATIVE_MODEL,
                messages=messages,
                domain_skill="Creative"
            )
        except Exception as e:
            logger.error(f"[Creation Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "创建失败，请稍后重试。"

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """尝试使用本地模型

        Args:
            messages: 对话消息列表

        Returns:
            Optional[str]: 本地模型响应内容，失败返回 None

        Raises:
            TimeoutError: 本地模型请求超时时抛出
            ModelInferenceError: 本地模型推理失败时抛出
        """
        try:
            from openai import AsyncOpenAI
            if not self.local_client:
                self.local_client = AsyncOpenAI(
                    base_url="http://localhost:1234/v1",
                    api_key="lm-studio"
                )
            response = await self.local_client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            logger.error("[Local Model Error] 本地模型请求超时")
            raise TimeoutError("本地模型请求超时")
        except Exception as e:
            logger.error(f"[Local Model Error] {e}")
            raise ModelInferenceError(f"本地模型推理失败: {str(e)}")
