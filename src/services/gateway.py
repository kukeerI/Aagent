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
                    return await self._try_local_model(messages)

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
                        return response
                    except Exception as e:
                        print(f"[Gateway] 请求失败 (尝试 {attempt+1}/{max_attempts}): {e}")
                        await asyncio.sleep(config.RETRY_DELAY)

            # 所有尝试都失败，使用本地模型
            return await self._try_local_model(messages)

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