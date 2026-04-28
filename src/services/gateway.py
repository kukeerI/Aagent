# src/services/gateway.py
# 网关 - 模型路由和负载均衡
# 依赖：asyncio, json, random, time, typing, uuid, enum, src.services.semantic_cache, src.services.tracing, src.data.database, src.config, src.services.llmops.langfuse, src.core.intent_analyzer, src.core.exceptions
# 注意事项：
#   - 实现了熔断器模式，防止服务雪崩
#   - 支持语义缓存，提高响应速度
#   - 实现了智能路由，根据任务级别选择合适的模型
#   - 支持本地模型回退，提高系统可靠性

import asyncio
import json
import random
import time
from typing import Optional, List, Dict, Any
import uuid
from enum import Enum

from src.services.semantic_cache import SemanticCache
from src.services.tracing import tracing
from src.data.database import AsyncSessionLocal, APIAsset
from src.config import config
from src.services.llmops.langfuse import langfuse_integration
from src.core.intent_analyzer import IntentAnalyzer
from src.core.exceptions import (
    ComputeResourceExhaustedError,
    ModelInferenceError,
    GatewayError,
    TimeoutError
)


class CircuitState(Enum):
    """熔断器状态枚举

    定义了熔断器的三种状态：
    - CLOSED: 正常状态，允许请求通过
    - OPEN: 熔断状态，拒绝请求
    - HALF_OPEN: 半开状态，允许部分请求通过以测试服务是否恢复
    """
    CLOSED = "closed"    # 正常
    OPEN = "open"        # 熔断
    HALF_OPEN = "half_open"  # 半开


class ResourceGuard:
    """资源保护类

    负责管理 API 健康状态和熔断器，确保系统在 API 故障时能够优雅降级。
    实现了以下功能：
    - API 健康检查
    - 熔断器模式
    - 资源可用性检查
    - 安全降级链管理
    """

    def __init__(self):
        """初始化资源保护类

        - 初始化 API 健康状态字典
        - 初始化熔断器状态字典
        - 设置健康检查间隔和失败阈值
        """
        self.api_health_status = {}  # API 健康状态
        self.last_health_check = 0  # 上次健康检查时间
        self.health_check_interval = 300  # 健康检查间隔（5分钟）
        self.circuit_breakers = {}  # 熔断器状态
        self.failure_threshold = 3  # 失败阈值
        self.base_retry_delay = 30  # 基础重试延迟（秒）
        self.max_retry_delay = 3600  # 最大重试延迟（秒）

    async def check_api_health(self):
        """检查 API 连通性

        定期检查所有启用的 API 节点的健康状态，更新熔断器状态。
        使用 httpx 发送 ping 请求来验证 API 连通性。
        """
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return

        print("[ResourceGuard] 开始 API 健康检查")

        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(APIAsset).where(APIAsset.enabled == True)
                )
                nodes = [
                    {
                        "node_id": asset.id,
                        "model_name": asset.model_name,
                        "base_url": asset.base_url,
                        "api_key": asset.api_key
                    }
                    for asset in result.scalars().all()
                ]

            for node in nodes:
                model_name = node["model_name"]
                # 检查熔断器状态
                if not self._should_attempt_request(model_name):
                    print(f"[ResourceGuard] 熔断器开启，跳过 {model_name} 的健康检查")
                    continue

                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        # 发送一个简单的请求来检查连通性
                        response = await client.post(
                            f"{node['base_url']}/v1/chat/completions",
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {node['api_key']}"
                            },
                            json={
                                "model": node["model_name"],
                                "messages": [{"role": "user", "content": "ping"}],
                                "max_tokens": 1
                            }
                        )
                        self.api_health_status[model_name] = {
                            "healthy": response.status_code == 200,
                            "status_code": response.status_code
                        }
                        # 重置熔断器
                        self._reset_circuit_breaker(model_name)
                except Exception as e:
                    self.api_health_status[model_name] = {
                        "healthy": False,
                        "error": str(e)
                    }
                    # 更新熔断器状态
                    self._update_circuit_breaker(model_name, False)

            self.last_health_check = current_time
            print("[ResourceGuard] API 健康检查完成")
        except Exception as e:
            print(f"[ResourceGuard] 健康检查失败: {e}")

    def _should_attempt_request(self, model_name: str) -> bool:
        """判断是否应该尝试请求

        根据熔断器状态判断是否应该尝试请求某个模型。

        Args:
            model_name: 模型名称

        Returns:
            bool: 是否应该尝试请求
        """
        breaker = self.circuit_breakers.get(model_name, {
            "state": CircuitState.CLOSED.value,
            "failure_count": 0,
            "last_failure_time": 0,
            "retry_delay": self.base_retry_delay
        })

        if breaker["state"] == CircuitState.CLOSED.value:
            return True
        elif breaker["state"] == CircuitState.HALF_OPEN.value:
            return True
        elif breaker["state"] == CircuitState.OPEN.value:
            # 检查是否达到重试时间
            current_time = time.time()
            if current_time - breaker["last_failure_time"] >= breaker["retry_delay"]:
                # 进入半开状态
                breaker["state"] = CircuitState.HALF_OPEN.value
                self.circuit_breakers[model_name] = breaker
                return True
            return False

        return True

    def _update_circuit_breaker(self, model_name: str, success: bool):
        """更新熔断器状态

        根据请求结果更新熔断器状态，实现熔断器模式的核心逻辑。

        Args:
            model_name: 模型名称
            success: 请求是否成功
        """
        breaker = self.circuit_breakers.get(model_name, {
            "state": CircuitState.CLOSED.value,
            "failure_count": 0,
            "last_failure_time": 0,
            "retry_delay": self.base_retry_delay
        })

        if success:
            # 成功，重置熔断器
            self._reset_circuit_breaker(model_name)
        else:
            # 失败，增加失败计数
            breaker["failure_count"] += 1
            breaker["last_failure_time"] = time.time()

            if breaker["failure_count"] >= self.failure_threshold:
                # 达到失败阈值，进入熔断状态
                breaker["state"] = CircuitState.OPEN.value
                # 计算带抖动的指数退避延迟
                breaker["retry_delay"] = min(
                    breaker["retry_delay"] * 2,
                    self.max_retry_delay
                )
                # 添加抖动
                jitter = random.uniform(0.8, 1.2)
                breaker["retry_delay"] *= jitter
                print(f"[ResourceGuard] {model_name} 进入熔断状态，重试延迟: {breaker['retry_delay']:.2f}s")

            self.circuit_breakers[model_name] = breaker

    def _reset_circuit_breaker(self, model_name: str):
        """重置熔断器

        将熔断器状态重置为初始状态。

        Args:
            model_name: 模型名称
        """
        self.circuit_breakers[model_name] = {
            "state": CircuitState.CLOSED.value,
            "failure_count": 0,
            "last_failure_time": 0,
            "retry_delay": self.base_retry_delay
        }
        print(f"[ResourceGuard] {model_name} 熔断器重置")

    def is_api_healthy(self, model_name: str) -> bool:
        """检查特定 API 是否健康

        同时考虑熔断器状态和 API 健康状态。

        Args:
            model_name: 模型名称

        Returns:
            bool: API 是否健康
        """
        # 首先检查熔断器状态
        if not self._should_attempt_request(model_name):
            return False

        status = self.api_health_status.get(model_name, {})
        return status.get("healthy", False)

    def get_healthy_apis(self) -> List[str]:
        """获取健康的 API 列表

        Returns:
            List[str]: 健康的 API 模型名称列表
        """
        healthy_apis = []
        for model_name in self.api_health_status:
            if self.is_api_healthy(model_name):
                healthy_apis.append(model_name)
        return healthy_apis

    async def get_safe_fallback_chain(self, route_level: int) -> List[str]:
        """获取安全降级链

        根据任务的路由级别返回相应的降级链。

        Args:
            route_level: 路由级别

        Returns:
            List[str]: 降级链列表
        """
        # 对于 L2 及以下任务
        if route_level <= 2:
            return ["API", "免费 API", "本地 4B 模型"]
        # 对于 L3 至 L7 任务
        else:
            return ["Pro API", "Flash API", "免费 API"]

    async def check_resource_availability(self, route_level: int) -> bool:
        """检查资源可用性

        根据任务的路由级别检查相应的资源是否可用。

        Args:
            route_level: 路由级别

        Returns:
            bool: 资源是否可用
        """
        # 对于 L3 至 L7 任务，需要检查高级 API 是否可用
        if route_level >= 3:
            # 检查是否有健康的 Pro/Flash API
            healthy_apis = self.get_healthy_apis()
            has_high_power_api = any(
                any(keyword in api.lower() for keyword in ["gpt-4", "gemini-1.5", "claude-3", "flash"])
                for api in healthy_apis
            )
            return has_high_power_api
        return True

    def should_block_local_fallback(self, route_level: int) -> bool:
        """判断是否应该阻止本地回退

        对于高价值/高复杂度的任务，禁止回退到本地模型以保证质量。

        Args:
            route_level: 路由级别

        Returns:
            bool: 是否应该阻止本地回退
        """
        # 对于 L3 至 L7 任务，禁止回退到本地 8B 模型
        return route_level >= 3


class GatewayRequest:
    """网关请求类

    封装了网关请求的相关信息，包括模型、消息和领域技能。
    """

    def __init__(self, model: str, messages: List[Dict[str, str]], domain_skill: str):
        """初始化网关请求

        Args:
            model: 模型名称
            messages: 消息列表
            domain_skill: 领域技能
        """
        self.model = model
        self.messages = messages
        self.domain_skill = domain_skill

    def model_dump(self) -> Dict[str, Any]:
        """将请求转换为字典

        Returns:
            Dict[str, Any]: 请求字典
        """
        return {
            "model": self.model,
            "messages": self.messages,
            "domain_skill": self.domain_skill
        }


class AsyncGateway:
    """异步网关类

    负责模型路由、负载均衡和请求处理，是系统与外部模型服务的接口。
    实现了以下功能：
    - 语义缓存
    - 智能路由
    - 熔断器模式
    - 本地模型回退
    - Prompt 管理
    """

    def __init__(self, trace_id: str = None):
        """初始化异步网关

        Args:
            trace_id: 追踪 ID，用于日志和追踪
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.semantic_cache = SemanticCache()
        self.r = None
        self.redis_initialized = False
        self.resource_guard = ResourceGuard()
        self.prompts = {
            "default": "你是一个专业的AI助手，能够提供准确、清晰的回答。",
            "code": "你是一个专业的编程助手，能够提供高质量的代码和解释。",
            "analysis": "你是一个专业的分析助手，能够提供深入、全面的分析。",
            "research": "你是一个专业的研究助手，能够提供准确、全面的研究结果。",
            "creative": "你是一个创意助手，能够提供原创、有趣的内容。"
        }
        self.prompt_versions = {
            "default": "1.0.0",
            "code": "1.0.0",
            "analysis": "1.0.0",
            "research": "1.0.0",
            "creative": "1.0.0"
        }
        # API 健康检查将在外部事件循环中调用

    async def chat_completion(self, model: str, messages: List[Dict[str, str]], domain_skill: str) -> str:
        """聊天完成

        处理聊天请求，包括语义缓存、意图分析、资源检查、节点选择和请求执行。

        Args:
            model: 模型名称
            messages: 消息列表
            domain_skill: 领域技能

        Returns:
            str: 模型响应

        Raises:
            ComputeResourceExhaustedError: 高阶算力池耗尽时抛出
            TimeoutError: 请求超时时抛出
            ModelInferenceError: 模型推理失败时抛出
        """
        with tracing.start_span("gateway.chat_completion", attributes={
            "domain_skill": domain_skill,
            "trace_id": self.trace_id
        }) as span:
            # 尝试语义缓存
            with tracing.start_span("semantic_cache.get"):
                request = GatewayRequest(model, messages, domain_skill)
                cached_response = await self.semantic_cache.get(request.model_dump())
                if cached_response:
                    span.set_attribute("cache_hit", True)
                    return cached_response
                span.set_attribute("cache_hit", False)

            # 分析任务意图，确定路由级别
            user_input = next((msg["content"] for msg in messages if msg["role"] == "user"), "")

            # 首先通过 TaskAnalyzer 提取语义数据
            from src.core.task_analyzer import task_analyzer
            semantic_data = await task_analyzer.extract_semantic_data(user_input)

            # 然后通过 IntentAnalyzer 计算路由级别
            intent_analysis = IntentAnalyzer.analyze_intent(user_input, semantic_data)
            route_level = intent_analysis["route_level"]
            print(f"[Gateway] 任务路由级别: L{route_level} ({intent_analysis['route_name']})")

            # 检查资源可用性
            resource_available = await self.resource_guard.check_resource_availability(route_level)
            if not resource_available:
                # 对于 L3-L7 任务，触发硬熔断
                if route_level >= 3:
                    print("🚨 高阶算力池已耗尽，为保证【高价值/高复杂】任务执行质量，已拒绝使用本地模型强行处理。任务已挂起，等待 API 恢复或人工干预。")
                    raise ComputeResourceExhaustedError("高阶算力池已耗尽，任务已挂起")

            # 获取最佳节点
            with tracing.start_span("gateway.get_best_node"):
                node = await self.get_best_node(domain_skill)
                if not node:
                    # 检查是否允许本地回退
                    if self.resource_guard.should_block_local_fallback(route_level):
                        print("🚨 高阶算力池已耗尽，为保证【高价值/高复杂】任务执行质量，已拒绝使用本地模型强行处理。任务已挂起，等待 API 恢复或人工干预。")
                        raise ComputeResourceExhaustedError("高阶算力池已耗尽，任务已挂起")
                    else:
                        response = await self._try_local_model(messages)
                        self._trace_prompt_usage(domain_skill, messages, response)
                        return response

            # 尝试请求
            max_attempts = config.MAX_RETRY_ATTEMPTS
            for attempt in range(max_attempts):
                with tracing.start_span(f"attempt_{attempt}", attributes={
                    "attempt": attempt,
                    "node_id": node["node_id"],
                    "model_name": node["model_name"]
                }):
                    try:
                        response = await self._make_request(node, messages)
                        # 设置缓存
                        await self.semantic_cache.set(request.model_dump(), response)
                        # 追踪Prompt使用情况
                        self._trace_prompt_usage(domain_skill, messages, response)
                        return response
                    except Exception as e:
                        print(f"[Gateway] 请求失败 (尝试 {attempt+1}/{max_attempts}): {e}")
                        await asyncio.sleep(config.RETRY_DELAY)

            # 所有尝试都失败，检查是否允许本地回退
            if self.resource_guard.should_block_local_fallback(route_level):
                print("🚨 高阶算力池已耗尽，为保证【高价值/高复杂】任务执行质量，已拒绝使用本地模型强行处理。任务已挂起，等待 API 恢复或人工干预。")
                raise ComputeResourceExhaustedError("高阶算力池已耗尽，任务已挂起")
            else:
                response = await self._try_local_model(messages)
                self._trace_prompt_usage(domain_skill, messages, response)
                return response

    async def get_best_node(self, domain_skill: str) -> Optional[Dict[str, Any]]:
        """获取最佳节点

        根据权重和失败次数选择最佳的 API 节点。

        Args:
            domain_skill: 领域技能

        Returns:
            Optional[Dict[str, Any]]: 最佳节点信息，如果没有可用节点返回 None
        """
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(APIAsset)
                    .where(APIAsset.enabled == True)
                )
                nodes = [
                    {
                        "node_id": asset.id,
                        "model_name": asset.model_name,
                        "base_url": asset.base_url,
                        "api_key": asset.api_key,
                        "weight": asset.weight,
                        "consecutive_failures": asset.consecutive_failures
                    }
                    for asset in result.scalars().all()
                ]

            if not nodes:
                return None

            # 基于权重和失败次数计算分数
            for node in nodes:
                # 失败次数越多，分数越低
                failure_penalty = node.get("consecutive_failures", 0) * 0.1
                node["score"] = node.get("weight", 1.0) - failure_penalty

            # 按分数排序
            nodes.sort(key=lambda x: x["score"], reverse=True)

            # 选择最高分的节点
            return nodes[0]
        except Exception as e:
            print(f"[Gateway] 获取节点失败: {e}")
            return None

    async def _make_request(self, node: Dict[str, Any], messages: List[Dict[str, str]]) -> str:
        """发送请求到模型节点

        Args:
            node: 节点信息
            messages: 消息列表

        Returns:
            str: 模型响应

        Raises:
            TimeoutError: 请求超时时抛出
            ModelInferenceError: 模型推理失败时抛出
        """
        import httpx
        start_time = time.time()
        model_name = node["model_name"]
        try:
            print(f"[Gateway] 开始请求节点 {model_name} (超时: {config.REQUEST_TIMEOUT}s)")
            from openai import AsyncOpenAI
            http_client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT)
            client = AsyncOpenAI(
                base_url=node["base_url"],
                api_key=node["api_key"],
                http_client=http_client
            )
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7
            )
            elapsed_time = time.time() - start_time
            print(f"[Gateway] 请求成功，耗时: {elapsed_time:.2f}s")
            # 更新熔断器状态（成功）
            self.resource_guard._update_circuit_breaker(model_name, True)
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            elapsed_time = time.time() - start_time
            print(f"[Gateway] 请求超时 (耗时: {elapsed_time:.2f}s)，节点: {model_name}")
            await self._update_failure_count(node["node_id"])
            # 更新熔断器状态（失败）
            self.resource_guard._update_circuit_breaker(model_name, False)
            raise TimeoutError(f"请求节点 {model_name} 超时")
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"[Gateway] 请求失败 (耗时: {elapsed_time:.2f}s): {e}")
            # 更新失败次数
            await self._update_failure_count(node["node_id"])
            # 更新熔断器状态（失败）
            self.resource_guard._update_circuit_breaker(model_name, False)
            raise ModelInferenceError(f"模型推理失败: {str(e)}")

    async def _update_failure_count(self, node_id: int):
        """更新节点失败次数

        Args:
            node_id: 节点 ID
        """
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select, update
                result = await session.execute(
                    select(APIAsset).where(APIAsset.id == node_id)
                )
                asset = result.scalar_one_or_none()
                if asset:
                    asset.consecutive_failures += 1
                    await session.commit()
        except Exception as e:
            print(f"[Gateway] 更新失败次数失败: {e}")

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> str:
        """尝试使用本地模型

        当所有远程模型都不可用时，尝试使用本地模型。

        Args:
            messages: 消息列表

        Returns:
            str: 本地模型响应
        """
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=config.LM_STUDIO_URL,
                api_key="lm-studio"
            )
            response = await client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=0.7
            )
            return f"[本地模型] {response.choices[0].message.content}"
        except Exception as e:
            print(f"[Local Model Error] {e}")
            return "所有模型都不可用，请稍后重试。"

    def _trace_prompt_usage(self, domain_skill: str, messages: List[Dict[str, str]], response: str):
        """追踪Prompt使用情况

        将Prompt使用情况追踪到 Langfuse。

        Args:
            domain_skill: 领域技能
            messages: 消息列表
            response: 模型响应
        """
        # 提取系统提示
        system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), self.get_prompt(domain_skill))
        # 提取用户输入
        user_input = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")

        # 构建完整输入
        input_text = f"System: {system_prompt}\nUser: {user_input}"

        # 追踪到Langfuse
        langfuse_integration.trace_prompt(
            prompt_name=domain_skill,
            prompt_version=self.prompt_versions.get(domain_skill, "1.0.0"),
            input_text=input_text,
            output_text=response,
            metadata={"model": "unknown"}
        )

    def get_prompt(self, domain_skill: str = "default") -> str:
        """获取Prompt

        尝试从 Langfuse 获取最新版本的 Prompt，失败则回退到本地 Prompt。

        Args:
            domain_skill: 领域技能

        Returns:
            str: Prompt 内容
        """
        # 尝试从Langfuse获取最新版本的Prompt
        langfuse_prompt = langfuse_integration.get_prompt(domain_skill)
        if langfuse_prompt:
            return langfuse_prompt.prompt
        # 回退到本地Prompt
        return self.prompts.get(domain_skill, self.prompts["default"])

    def set_prompt(self, domain_skill: str, prompt: str, version: str = "1.0.0"):
        """设置Prompt

        设置本地 Prompt 并同步到 Langfuse。

        Args:
            domain_skill: 领域技能
            prompt: Prompt 内容
            version: 版本号
        """
        self.prompts[domain_skill] = prompt
        self.prompt_versions[domain_skill] = version
        # 同步到Langfuse
        langfuse_integration.create_prompt(
            name=domain_skill,
            content=prompt,
            version=version
        )

    def list_prompts(self) -> Dict[str, str]:
        """列出所有Prompt

        从 Langfuse 获取 Prompt 列表，失败则回退到本地 Prompt。

        Returns:
            Dict[str, str]: Prompt 名称和内容的字典
        """
        # 从Langfuse获取Prompt列表
        langfuse_prompts = langfuse_integration.list_prompts()
        if langfuse_prompts:
            return {prompt: "1.0.0" for prompt in langfuse_prompts}  # 简化处理
        # 回退到本地Prompt
        return self.prompts

    async def a_b_test_prompts(self, domain_skill: str, variants: List[str], test_inputs: List[str]) -> Dict[str, float]:
        """A/B测试Prompt

        测试不同 Prompt 变体的效果。

        Args:
            domain_skill: 领域技能
            variants: Prompt 变体列表
            test_inputs: 测试输入列表

        Returns:
            Dict[str, float]: 各变体的得分
        """
        results = {}

        for i, variant in enumerate(variants):
            # 临时设置Prompt
            original_prompt = self.prompts.get(domain_skill)
            self.prompts[domain_skill] = variant

            # 测试每个输入
            scores = []
            for test_input in test_inputs:
                messages = [
                    {"role": "system", "content": variant},
                    {"role": "user", "content": test_input}
                ]
                response = await self.chat_completion("local-model", messages, domain_skill)
                # 简单的评分机制（实际应用中可以使用更复杂的评估方法）
                score = len(response) / 100  # 示例：基于响应长度的评分
                scores.append(score)

            # 计算平均得分
            average_score = sum(scores) / len(scores)
            results[f"variant_{i+1}"] = average_score

            # 恢复原始Prompt
            if original_prompt:
                self.prompts[domain_skill] = original_prompt

        return results

    async def fast_route(self, messages: List[Dict[str, str]], domain_skill: str = "Desktop_Assistant") -> str:
        """快速路由

        用于 Open Interpreter 等需要极速响应的场景，不进行复杂的路由和重试逻辑。

        Args:
            messages: 消息列表
            domain_skill: 领域技能

        Returns:
            str: 模型响应
        """
        with tracing.start_span("gateway.fast_route", attributes={
            "domain_skill": domain_skill,
            "trace_id": self.trace_id
        }) as span:
            # 尝试语义缓存
            with tracing.start_span("semantic_cache.get"):
                request = GatewayRequest("auto", messages, domain_skill)
                cached_response = await self.semantic_cache.get(request.model_dump())
                if cached_response:
                    span.set_attribute("cache_hit", True)
                    return cached_response
                span.set_attribute("cache_hit", False)

            # 获取最佳节点
            with tracing.start_span("gateway.get_best_node"):
                node = await self.get_best_node(domain_skill)
                if not node:
                    response = await self._try_local_model(messages)
                    self._trace_prompt_usage(domain_skill, messages, response)
                    return response

            # 单次请求，不重试
            with tracing.start_span("gateway.make_request", attributes={
                "node_id": node["node_id"],
                "model_name": node["model_name"]
            }):
                try:
                    response = await self._make_request(node, messages)
                    # 设置缓存
                    await self.semantic_cache.set(request.model_dump(), response)
                    # 追踪Prompt使用情况
                    self._trace_prompt_usage(domain_skill, messages, response)
                    return response
                except Exception as e:
                    print(f"[Fast Route] 请求失败: {e}")
                    # 直接降级到本地模型，不重试
                    response = await self._try_local_model(messages)
                    self._trace_prompt_usage(domain_skill, messages, response)
                    return response

    async def close(self):
        """关闭网关，清理资源

        关闭语义缓存等资源。
        """
        try:
            if hasattr(self, 'semantic_cache') and hasattr(self.semantic_cache, 'close'):
                await self.semantic_cache.close()
            print("[Gateway] 已关闭")
        except Exception as e:
            print(f"[Gateway] 关闭失败: {e}")
