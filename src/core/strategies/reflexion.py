# src/core/strategies/reflexion.py
# Reflexion 策略 - 强控制循环版本
# 依赖：asyncio, typing, src.core.strategies.base, src.core.prompt_manager, 
#       src.services.gateway, src.utils.logger, src.config
# 注意事项：
#   - 实现真正的 Generate -> Critique -> Refine 三阶段闭环
#   - 使用独立评审模型避免自我路径依赖
#   - 实现上下文压缩机制防止上下文膨胀

import asyncio
from typing import List, Dict, Any

from src.core.strategies.base import ReasoningStrategy
from src.core.prompt_manager import PromptManager
from src.services.gateway import AsyncGateway
from src.utils.logger import logger
from src.config import config


class ReflexionStrategy(ReasoningStrategy):
    """
    Reflexion 策略：实现真正的『生成-评审-修正』三阶段逻辑循环。
    
    核心逻辑：
    1. 初始生成阶段：生成初步答案
    2. 评审阶段(Critique)：使用独立模型评审，避免自我路径依赖
    3. 修正阶段(Refine)：基于评审意见修正答案
    """

    def __init__(self, max_iterations: int = 3):
        """初始化 Reflexion 策略
        
        Args:
            max_iterations: 最大反思迭代次数，默认 3 次
        """
        self.max_iterations = max_iterations
        self.gateway = AsyncGateway()

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行 Reflexion 推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 推理结果
        """
        logger.info(f"[{trace_id}] 开始 Reflexion 策略，最大迭代次数: {self.max_iterations}")

        # 1. 初始生成阶段
        current_content = await self._generate_draft(messages, model_pool[0], trace_id)
        logger.info(f"[{trace_id}] 初始草稿生成完成")

        for iteration in range(self.max_iterations):
            logger.info(f"[{trace_id}] 开始第 {iteration + 1} 轮反思迭代...")

            # 2. 评审阶段 (Critique)
            # 敏感细节：如果模型池有多个，用第二个模型来评审，避免『自我路径依赖』
            reviewer_model = model_pool[min(1, len(model_pool) - 1)] if len(model_pool) > 1 else model_pool[0]
            critique = await self._get_critique(messages, current_content, reviewer_model, trace_id)
            
            # 检查收敛条件
            if self._is_converged(critique):
                logger.info(f"[{trace_id}] 反思收敛，提前结束迭代")
                break

            # 3. 修正阶段 (Refine)
            current_content = await self._refine_content(messages, current_content, critique, model_pool[0], trace_id)
            
            # 上下文压缩：只保留核心内容，防止上下文膨胀
            messages = self._compress_context(messages, current_content)

        logger.info(f"[{trace_id}] Reflexion 策略完成")
        return current_content

    async def _generate_draft(self, original_msgs: list, model: dict, trace_id: str) -> str:
        """生成初始草稿
        
        Args:
            original_msgs: 原始消息列表
            model: 模型配置
            trace_id: 追踪 ID
            
        Returns:
            str: 初始草稿内容
        """
        # 注入 Reflexion 初始生成提示词
        draft_prompt = PromptManager.build_system_prompt(
            level=5,  # L5 级别提示词
            task_type="analysis"
        )
        
        draft_messages = [{"role": "system", "content": draft_prompt}] + original_msgs
        
        return await self.gateway.call(model, draft_messages, f"{trace_id}-draft")

    async def _get_critique(self, original_msgs: list, draft: str, model: dict, trace_id: str) -> str:
        """获取评审意见
        
        Args:
            original_msgs: 原始消息列表
            draft: 当前草稿
            model: 评审模型配置
            trace_id: 追踪 ID
            
        Returns:
            str: 评审意见
        """
        # 注入专门的评审提示词
        critique_prompt = """请作为严苛的评审员，对以下回答进行全面审查：

审查维度：
1. 逻辑自洽性：论证是否严密，是否存在漏洞
2. 证据充分性：是否有足够的证据支持结论
3. 术语准确性：专业术语使用是否正确
4. 完整性：是否覆盖了问题的所有方面
5. 改进建议：具体的改进方向

请直接给出评审意见，不需要客套话。如果回答已足够完善，请回复"满意"。"""

        review_messages = original_msgs + [
            {"role": "assistant", "content": draft},
            {"role": "system", "content": critique_prompt}
        ]
        
        return await self.gateway.call(model, review_messages, f"{trace_id}-critique")

    async def _refine_content(self, original_msgs: list, draft: str, critique: str, model: dict, trace_id: str) -> str:
        """基于评审意见修正内容
        
        Args:
            original_msgs: 原始消息列表
            draft: 当前草稿
            critique: 评审意见
            model: 模型配置
            trace_id: 追踪 ID
            
        Returns:
            str: 修正后的内容
        """
        refine_prompt = f"""请基于以下评审意见对回答进行全面修正：

评审意见：
{critique}

修正要求：
1. 逐条回应评审意见中的问题
2. 保持回答的完整性和逻辑性
3. 修正后请再次检查是否满足要求"""

        refine_messages = original_msgs + [
            {"role": "assistant", "content": draft},
            {"role": "user", "content": refine_prompt}
        ]
        
        return await self.gateway.call(model, refine_messages, f"{trace_id}-refine")

    def _is_converged(self, critique: str) -> bool:
        """判断是否收敛
        
        Args:
            critique: 评审意见
            
        Returns:
            bool: 是否收敛
        """
        if not critique:
            return True
            
        # 简单的收敛条件：包含"满意"且内容简短
        if "满意" in critique and len(critique) < 50:
            return True
            
        # 检查是否没有实质性改进建议
        if len(critique) < 20:
            return True
            
        return False

    def _compress_context(self, messages: list, latest_content: str) -> list:
        """上下文压缩：只保留核心内容
        
        Args:
            messages: 原始消息列表
            latest_content: 最新内容
            
        Returns:
            list: 压缩后的消息列表
        """
        # 保留系统提示和最新用户输入
        compressed = []
        
        for msg in messages:
            if msg["role"] == "system":
                compressed.append(msg)
            elif msg["role"] == "user":
                # 只保留最后一个用户消息
                compressed = [m for m in compressed if m["role"] != "user"]
                compressed.append(msg)
        
        # 添加最新的反思结果作为上下文
        compressed.append({"role": "assistant", "content": latest_content[:2000]})
        
        return compressed