# src/core/executor.py
# 执行器 - 任务执行逻辑

import asyncio
import json
from typing import Optional, List, Dict, Any

from src.services.gateway import AsyncGateway
from src.services.sandbox.docker import DockerSandbox

class AsyncAgentLegion:
    def __init__(self, trace_id: str = None):
        self.trace_id = trace_id
        self.gateway = AsyncGateway(trace_id=trace_id)
        self.sandbox = DockerSandbox()

    async def execute_task(self, task: str, task_type: str) -> str:
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