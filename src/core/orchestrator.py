# src/core/orchestrator.py
# 主脑 - 核心编排逻辑

import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.core.state import AgentStateMachine
from src.core.executor import AgentExecutor
from src.data.database import AsyncSessionLocal, ExecutionLog
from src.data.memory import Memory
from src.services.gateway import AsyncGateway
from src.services.sandbox.docker import DockerSandbox
from src.services.tracing import tracing
from src.config import config
from src.core.pipelines import StandardPipeline
from src.data.domain_models import AgentTask, TaskState
from src.core.exceptions import (
    ModelInferenceError,
    CodeExecutionError,
    TimeoutError
)
from src.utils.logger import logger

class AgentOrchestrator:
    """智能体编排器"""
    
    def __init__(self, trace_id: str = None, mcp_server_url: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.memory = Memory()
        self.gateway = AsyncGateway(trace_id=self.trace_id)
        self.sandbox = DockerSandbox()
        self.executor = AgentExecutor(trace_id=self.trace_id, mcp_server_url=mcp_server_url)
        self.state_machine = AgentStateMachine(self)
        self.pipeline = StandardPipeline()
        self.local_client = None
        logger.info(f"Orchestrator 初始化完成，Trace ID: {self.trace_id}")

    async def start_work(self, user_input: str, checkpoint_id: Optional[str] = None):
        """开始工作"""
        with tracing.start_span("orchestrator.start_work", attributes={
            "user_input": user_input[:100],
            "trace_id": self.trace_id
        }) as span:
            logger.info(f"Trace ID: {self.trace_id} 接收到任务: {user_input}")

            # 初始化执行器
            await self.executor.initialize()

            # 记忆检索
            with tracing.start_span("memory.retrieve"):
                previous_context = await self.memory.retrieve(user_input)
                if previous_context:
                    logger.info(f"Trace ID: {self.trace_id} 从记忆中检索到相关信息")

            # 创建任务对象
            task = AgentTask(
                trace_id=self.trace_id,
                user_input=user_input,
                state=TaskState.INIT,
                previous_context=previous_context
            )

            # 使用管道执行任务
            with tracing.start_span("pipeline.run") as pipeline_span:
                task = await self.pipeline.run(task)

            # 记忆存储
            with tracing.start_span("memory.add_experience"):
                await self.memory.add_experience(user_input, task.final_answer or "")

            # 记录执行日志
            with tracing.start_span("log.execution"):
                await self._log_execution(user_input, task)

            logger.info(f"Trace ID: {self.trace_id} 任务执行完成")

            return task.final_answer or "任务执行失败"

    async def pause_work(self, task: AgentTask, current_state: str) -> str:
        """暂停工作，创建检查点"""
        return await self.state_machine.pause(task, current_state)

    def list_checkpoints(self) -> List:
        """列出当前任务的所有检查点"""
        checkpoints = self.state_machine.list_checkpoints(self.trace_id)
        return [{
            "checkpoint_id": cp.checkpoint_id,
            "state_name": cp.state_name,
            "timestamp": cp.timestamp.isoformat()
        } for cp in checkpoints]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """获取检查点信息"""
        checkpoint = self.state_machine.get_checkpoint(checkpoint_id)
        if checkpoint:
            return {
                "checkpoint_id": checkpoint.checkpoint_id,
                "state_name": checkpoint.state_name,
                "context": checkpoint.context,
                "timestamp": checkpoint.timestamp.isoformat()
            }
        return None

    async def resume_work(self, checkpoint_id: str) -> str:
        """从检查点恢复工作"""
        checkpoint = self.state_machine.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return "检查点不存在"
        
        # 从检查点上下文重建任务
        task_dict = checkpoint.context
        task = AgentTask(**task_dict)
        
        # 使用管道执行任务
        result_task = await self.pipeline.run(task)
        
        # 保存到记忆
        user_input = task.user_input
        await self.memory.add_experience(user_input, result_task.final_answer or "")
        
        # 记录执行日志
        await self._log_execution(user_input, result_task)
        
        return result_task.final_answer or "任务执行失败"

    async def time_travel(self, checkpoint_id: str) -> str:
        """时光倒流，从指定检查点重新执行"""
        return await self.resume_work(checkpoint_id)

    async def _log_execution(self, user_input: str, task: AgentTask):
        """记录执行日志"""
        async with AsyncSessionLocal() as session:
            log = ExecutionLog(
                trace_id=task.trace_id,
                input_text=user_input,
                response=task.final_answer or "",
                model_used=task.model_used or "unknown",
                is_local_fallback=task.is_local_fallback,
                error_message=task.error,
                created_at=datetime.now()
            )
            session.add(log)
            await session.commit()

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """尝试使用本地模型"""
        try:
            from openai import AsyncOpenAI
            if not self.local_client:
                self.local_client = AsyncOpenAI(
                    base_url=config.LM_STUDIO_URL,
                    api_key="lm-studio"
                )
            response = await self.local_client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            logger.error("本地模型请求超时")
            raise TimeoutError("本地模型请求超时")
        except Exception as e:
            logger.error(f"本地模型推理失败: {str(e)}")
            raise ModelInferenceError(f"本地模型推理失败: {str(e)}")

    async def _safe_execute_code(self, code: str) -> str:
        """安全执行代码"""
        try:
            result = await self.sandbox.execute_code(code, timeout=config.SANDBOX_TIMEOUT)
            return f"执行结果: {result}"
        except asyncio.TimeoutError:
            raise TimeoutError("代码执行超时")
        except Exception as e:
            raise CodeExecutionError(f"代码执行失败: {str(e)}")

    async def _analyze_task(self, task: str) -> Dict[str, Any]:
        """分析任务"""
        return await self.executor.analyze_task(task)

    async def _execute_task(self, task: str, task_type: str) -> str:
        """执行任务"""
        return await self.executor.execute_task(task, task_type)

    async def _research_task(self, topic: str) -> str:
        """研究任务"""
        return await self.executor.research_task(topic)

    async def _create_task(self, request: str) -> str:
        """创建任务"""
        return await self.executor.create_task(request)

    async def _handle_error(self, error: str) -> str:
        """处理错误"""
        messages = [
            {"role": "system", "content": "你是一个错误处理专家，能够分析错误并提供解决方案。"},
            {"role": "user", "content": f"错误信息: {error}\n\n请分析错误原因并提供解决方案。"}
        ]

        try:
            from src.config import config
            return await self.gateway.chat_completion(
                model=config.DEFAULT_ERROR_HANDLING_MODEL,
                messages=messages,
                domain_skill="ErrorHandling"
            )
        except Exception as e:
            logger.error(f"错误处理失败: {str(e)}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "错误处理失败，请稍后重试。"
