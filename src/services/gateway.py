# src/services/gateway.py
# 网关 - 模型路由和负载均衡

import asyncio
import json
import random
import time
from typing import Optional, List, Dict, Any
import uuid

from src.services.semantic_cache import SemanticCache
from src.services.tracing import tracing
from src.data.database import AsyncSessionLocal, APIAsset
from src.config import config
from src.services.llmops.langfuse import langfuse_integration

class GatewayRequest:
    def __init__(self, model: str, messages: List[Dict[str, str]], domain_skill: str):
        self.model = model
        self.messages = messages
        self.domain_skill = domain_skill

    def model_dump(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.messages,
            "domain_skill": self.domain_skill
        }

class AsyncGateway:
    def __init__(self, trace_id: str = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.semantic_cache = SemanticCache()
        self.r = None
        self.redis_initialized = False
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

    async def chat_completion(self, model: str, messages: List[Dict[str, str]], domain_skill: str) -> str:
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

            # 获取最佳节点
            with tracing.start_span("gateway.get_best_node"):
                node = await self.get_best_node(domain_skill)
                if not node:
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

            # 所有尝试都失败，使用本地模型
            response = await self._try_local_model(messages)
            self._trace_prompt_usage(domain_skill, messages, response)
            return response

    async def get_best_node(self, domain_skill: str) -> Optional[Dict[str, Any]]:
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
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=node["base_url"],
                api_key=node["api_key"]
            )
            response = await client.chat.completions.create(
                model=node["model_name"],
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            # 更新失败次数
            await self._update_failure_count(node["node_id"])
            raise

    async def _update_failure_count(self, node_id: int):
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
        """追踪Prompt使用情况"""
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
        """获取Prompt"""
        # 尝试从Langfuse获取最新版本的Prompt
        langfuse_prompt = langfuse_integration.get_prompt(domain_skill)
        if langfuse_prompt:
            return langfuse_prompt.prompt
        # 回退到本地Prompt
        return self.prompts.get(domain_skill, self.prompts["default"])

    def set_prompt(self, domain_skill: str, prompt: str, version: str = "1.0.0"):
        """设置Prompt"""
        self.prompts[domain_skill] = prompt
        self.prompt_versions[domain_skill] = version
        # 同步到Langfuse
        langfuse_integration.create_prompt(
            name=domain_skill,
            content=prompt,
            version=version
        )

    def list_prompts(self) -> Dict[str, str]:
        """列出所有Prompt"""
        # 从Langfuse获取Prompt列表
        langfuse_prompts = langfuse_integration.list_prompts()
        if langfuse_prompts:
            return {prompt: "1.0.0" for prompt in langfuse_prompts}  # 简化处理
        # 回退到本地Prompt
        return self.prompts

    async def a_b_test_prompts(self, domain_skill: str, variants: List[str], test_inputs: List[str]) -> Dict[str, float]:
        """A/B测试Prompt"""
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
        """快速路由 - 用于 Open Interpreter 等需要极速响应的场景
        
        Args:
            messages: 消息列表
            domain_skill: 领域技能
            
        Returns:
            响应内容
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