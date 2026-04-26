# src/core/orchestrator.py
# 主脑 - 核心编排逻辑

import asyncio
import json
import uuid
import time
import random
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from src.core.state import AgentStateMachine
from src.data.database import AsyncSessionLocal, ExecutionLog, APIAsset
from src.data.memory import Memory
from src.services.gateway import AsyncGateway
from src.services.sandbox.docker import DockerSandbox
from src.services.tracing import tracing
from src.config import config

class AsyncRealOrchestrator:
    def __init__(self, trace_id: str = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.memory = Memory()
        self.gateway = AsyncGateway(trace_id=self.trace_id)
        self.sandbox = DockerSandbox()
        print(f"[Orchestrator] 初始化完成，Trace ID: {self.trace_id}")

    async def start_work(self, user_input: str):
        with tracing.start_span("orchestrator.start_work", attributes={
            "user_input": user_input[:100],
            "trace_id": self.trace_id
        }) as span:
            print(f"\n[{self.trace_id}] ========================================")
            print(f"[{self.trace_id}] 接收到任务: {user_input}")
            print(f"[{self.trace_id}] ========================================")

            # 记忆检索
            with tracing.start_span("memory.retrieve"):
                previous_context = await self.memory.retrieve(user_input)
                if previous_context:
                    print(f"[{self.trace_id}] 从记忆中检索到相关信息")

            # 使用状态机执行任务
            with tracing.start_span("state_machine.run") as state_span:
                state_machine = AgentStateMachine(self)
                context = await state_machine.run({
                    "user_input": user_input,
                    "trace_id": self.trace_id,
                    "previous_context": previous_context
                })

            # 记忆存储
            with tracing.start_span("memory.add_experience"):
                await self.memory.add_experience(user_input, context.get("final_answer", ""))

            # 记录执行日志
            with tracing.start_span("log.execution"):
                await self._log_execution(user_input, context)

            print(f"[{self.trace_id}] ========================================")
            print(f"[{self.trace_id}] 任务执行完成")
            print(f"[{self.trace_id}] ========================================")

    async def _log_execution(self, user_input: str, context: Dict[str, Any]):
        async with AsyncSessionLocal() as session:
            log = ExecutionLog(
                trace_id=self.trace_id,
                input_text=user_input,
                response=context.get("final_answer", ""),
                model_used=context.get("model_used", "unknown"),
                is_local_fallback=context.get("is_local_fallback", False),
                error_message=context.get("error", None),
                created_at=datetime.now()
            )
            session.add(log)
            await session.commit()

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> Optional[str]:
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
            return response.choices[0].message.content
        except Exception as e:
            print(f"[Local Model Error] {e}")
            return None

    async def _safe_execute_code(self, code: str) -> str:
        try:
            result = await self.sandbox.execute_code(code, timeout=config.SANDBOX_TIMEOUT)
            return f"执行结果: {result}"
        except Exception as e:
            return f"执行错误: {str(e)}"

    async def _analyze_task(self, task: str) -> Dict[str, Any]:
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

    async def _execute_task(self, task: str, task_type: str) -> str:
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

    async def _research_task(self, topic: str) -> str:
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

    async def _create_task(self, request: str) -> str:
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

    async def _handle_error(self, error: str) -> str:
        messages = [
            {"role": "system", "content": "你是一个错误处理专家，能够分析错误并提供解决方案。"},
            {"role": "user", "content": f"错误信息: {error}\n\n请分析错误原因并提供解决方案。"}
        ]

        try:
            return await self.gateway.chat_completion(
                model="google/gemma-3-12b-it",
                messages=messages,
                domain_skill="ErrorHandling"
            )
        except Exception as e:
            print(f"[Error Handling Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "错误处理失败，请稍后重试。"