# src/core/strategies/simple_fusion.py
# SimpleFusion 策略 - 模型感知版本
# 依赖：asyncio, typing, src.core.strategies.base, src.config, 
#       src.core.prompt_manager, src.services.gateway, src.utils.logger, src.core.checkpoint
# 注意事项：
#   - 彻底移除硬编码，通过 config 动态适配
#   - 支持本地/远程动态切换
#   - 使用 PromptManager 注入融合元指令
#   - 实现本地冗余节点机制
#   - 支持状态持久化（checkpoint）
#   - 使用 asyncio.gather 并发请求多个模型

import asyncio
from typing import List, Dict, Any

from src.core.strategies.base import ReasoningStrategy
from src.config import config
from src.core.prompt_manager import PromptManager
from src.services.gateway import AsyncGateway
from src.utils.logger import logger
from src.core.checkpoint import CheckpointManager


class SimpleFusionStrategy(ReasoningStrategy):
    """
    SimpleFusion 策略：多模型答案聚合，适配本地/远程动态切换。
    
    核心逻辑：
    1. 并发获取多个候选答案（如果模型池够大）
    2. 使用 PromptManager 获取融合指令
    3. 选择融合模型：优先高算力，失败转本地冗余
    """

    def __init__(self):
        """初始化 SimpleFusion 策略"""
        self.gateway = AsyncGateway()
        self.checkpoint_manager = CheckpointManager()

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行简单融合推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 推理结果
        """
        logger.info(f"[{trace_id}] 开始 SimpleFusion 策略")

        # 如果没有消息，返回默认值
        if not messages:
            logger.warning(f"[{trace_id}] 融合失败：没有可用的消息")
            return "融合失败：没有可用的消息"
        
        # 保存开始检查点
        await self._save_checkpoint(trace_id, "fusion_start", {
            "model_pool_size": len(model_pool),
            "max_fusion_models": config.MAX_FUSION_MODELS
        })

        # 1. 并发获取多个模型的响应（高可用：即便远程失败，也有其他路）
        # 敏感细节：自动从 config 加载模型列表
        tasks = [self.gateway.call(m, messages, trace_id) for m in model_pool[:config.MAX_FUSION_MODELS]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_answers = [r for r in results if isinstance(r, str)]
        logger.info(f"[{trace_id}] 获取到 {len(valid_answers)}/{len(tasks)} 个有效响应")
        
        # 保存中间结果检查点
        await self._save_checkpoint(trace_id, "fusion_results", {
            "valid_answers_count": len(valid_answers),
            "total_tasks": len(tasks),
            "answers": valid_answers[:3]  # 只保存前3个以节省空间
        })
        
        if not valid_answers:
            logger.warning(f"[{trace_id}] 没有获取到候选答案")
            return await self._execute_local(messages)

        # 2. 汇总决策
        fusion_prompt = PromptManager.build_fusion_prompt(valid_answers)
        
        # 3. 本地模型降级逻辑
        try:
            final_answer = await self.gateway.call(model_pool[0], fusion_prompt, trace_id)
        except Exception as e:
            logger.error(f"[{trace_id}] 远程聚合失败 ({e})，降级至本地模型处理")
            final_answer = await self._execute_local(fusion_prompt)

        # 保存最终结果检查点
        await self._save_checkpoint(trace_id, "fusion_completed", {
            "final_answer": final_answer,
            "valid_answers_count": len(valid_answers)
        })

        logger.info(f"[{trace_id}] SimpleFusion 策略完成")
        return final_answer

    async def _execute_local(self, prompt: list) -> str:
        """调用本地冗余节点
        
        彻底移除 localhost:1234，从配置加载。
        
        Args:
            prompt: 提示词消息列表
            
        Returns:
            str: 本地模型响应
        """
        # 从 config 获取本地模型配置
        local_node = {
            "base_url": config.LOCAL_MODEL_URL,
            "api_key": config.LOCAL_API_KEY,
            "model_name": config.LOCAL_MODEL_NAME,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        try:
            result = await self.gateway.call(local_node, prompt, "local-fallback")
            return f"[本地融合] {result}"
        except Exception as e:
            logger.error(f"本地冗余节点调用失败: {e}")
            return "所有模型都不可用，请稍后重试。"

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