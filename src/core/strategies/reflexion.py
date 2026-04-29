# src/core/strategies/reflexion.py
# Reflexion 策略 - 强控制循环版本
# 依赖：asyncio, typing, src.core.strategies.base, src.core.prompt_manager, 
#       src.services.gateway, src.utils.logger, src.config, src.core.checkpoint
# 注意事项：
#   - 实现真正的 Generate -> Critique -> Refine 三阶段闭环
#   - 使用独立评审模型避免自我路径依赖
#   - 实现上下文压缩机制防止上下文膨胀
#   - 支持状态持久化（checkpoint）

import asyncio
from typing import List, Dict, Any

from src.core.strategies.base import ReasoningStrategy
from src.core.prompt_manager import PromptManager
from src.services.gateway import AsyncGateway
from src.utils.logger import logger
from src.config import config
from src.core.checkpoint import CheckpointManager


class ReflexionStrategy(ReasoningStrategy):
    """
    Reflexion 策略：实现真正的『生成-评审-修正』三阶段逻辑循环。
    
    核心逻辑：
    1. 初始生成阶段：生成初步答案
    2. 评审阶段(Critique)：使用独立模型评审，避免自我路径依赖
    3. 修正阶段(Refine)：基于评审意见修正答案
    """

    def __init__(self):
        """初始化 Reflexion 策略"""
        self.gateway = AsyncGateway()
        self.checkpoint_manager = CheckpointManager()

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行 Reflexion 推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 推理结果
        """
        logger.info(f"[{trace_id}] 开始 Reflexion 策略，最大迭代次数: {config.REFLEXION_MAX_ITERS}")

        # 1. 初始生成阶段
        main_model = model_pool[0]
        draft = await self.gateway.call(main_model, messages, trace_id)
        logger.info(f"[{trace_id}] [Step 1/{config.REFLEXION_MAX_ITERS}] 初始草稿生成完成")
        
        # 保存初始检查点
        await self._save_checkpoint(trace_id, "initial_draft", {
            "draft": draft,
            "iteration": 0,
            "messages": messages
        })

        # 2. 迭代反思（使用 while 循环，上限 config.REFLEXION_MAX_ITERS 次）
        iteration = 0
        while iteration < config.REFLEXION_MAX_ITERS:
            iteration += 1
            logger.info(f"[{trace_id}] [Step {iteration+1}/{config.REFLEXION_MAX_ITERS}] 启动第 {iteration} 轮反思...")

            # 2.1 评审阶段：使用独立模型池中第二个模型（若有）进行"第三方评审"
            reviewer_model = model_pool[min(1, len(model_pool)-1)] if len(model_pool) > 1 else model_pool[0]
            critique_prompt = PromptManager.build_critique_prompt(messages, draft)
            critique = await self.gateway.call(reviewer_model, critique_prompt, f"{trace_id}-rev-{iteration}")
            
            logger.info(f"[{trace_id}] [Step {iteration+1}/{config.REFLEXION_MAX_ITERS}] 评审完成: {critique[:50]}...")
            
            # 保存评审检查点
            await self._save_checkpoint(trace_id, f"critique_{iteration}", {
                "draft": draft,
                "critique": critique,
                "iteration": iteration
            })

            # 收敛判定：评审员若给出"满意"关键字则提前终止
            if "满意" in critique[:20] or "PASS" in critique.upper():
                logger.info(f"[{trace_id}] [Step {iteration+1}/{config.REFLEXION_MAX_ITERS}] 评审通过，提前结束反思")
                break
                
            # 2.2 修正阶段：将评审意见反馈给主模型进行重写
            logger.info(f"[{trace_id}] [Step {iteration+1}/{config.REFLEXION_MAX_ITERS}] [Refining...] 基于评审意见修正...")
            refine_prompt = PromptManager.build_refine_prompt(messages, draft, critique)
            draft = await self.gateway.call(main_model, refine_prompt, f"{trace_id}-ref-{iteration}")
            logger.info(f"[{trace_id}] [Step {iteration+1}/{config.REFLEXION_MAX_ITERS}] 修正完成")
            
            # 保存修正检查点
            await self._save_checkpoint(trace_id, f"refined_{iteration}", {
                "draft": draft,
                "critique": critique,
                "iteration": iteration
            })

        # 保存最终结果检查点
        await self._save_checkpoint(trace_id, "final_result", {
            "result": draft,
            "total_iterations": iteration,
            "converged": iteration < config.REFLEXION_MAX_ITERS
        })

        logger.info(f"[{trace_id}] Reflexion 策略完成")
        return draft

    async def _save_checkpoint(self, trace_id: str, state_name: str, context: dict):
        """保存检查点
        
        Args:
            trace_id: 追踪 ID
            state_name: 状态名称
            context: 上下文数据
        """
        try:
            context['trace_id'] = trace_id
            await self.checkpoint_manager.create_checkpoint(state_name, context)
            logger.debug(f"[{trace_id}] 检查点已保存: {state_name}")
        except Exception as e:
            logger.warning(f"[{trace_id}] 检查点保存失败: {e}")