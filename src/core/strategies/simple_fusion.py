# src/core/strategies/simple_fusion.py
# SimpleFusion 策略 - 模型感知版本
# 依赖：asyncio, typing, src.core.strategies.base, src.config, 
#       src.core.prompt_manager, src.services.gateway, src.utils.logger
# 注意事项：
#   - 彻底移除硬编码，通过 config 动态适配
#   - 支持本地/远程动态切换
#   - 使用 PromptManager 注入融合元指令
#   - 实现本地冗余节点机制

import asyncio
from typing import List, Dict, Any, Optional

from src.core.strategies.base import ReasoningStrategy
from src.config import config
from src.core.prompt_manager import PromptManager
from src.services.gateway import AsyncGateway
from src.utils.logger import logger


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

        # 1. 并发获取多个候选答案（如果池子够大）
        candidates = await self._collect_candidates(messages, model_pool, trace_id)
        
        if not candidates:
            logger.warning(f"[{trace_id}] 没有获取到候选答案")
            return await self._fallback_single_inference(messages, model_pool, trace_id)

        # 2. 调用 PromptManager 获取融合指令
        fusion_instruction = PromptManager.get_fusion_prompt(candidates)
        
        # 3. 选择融合模型：优先高算力，失败转本地
        try:
            final_answer = await self._perform_fusion(fusion_instruction, model_pool, trace_id)
        except Exception as e:
            logger.warning(f"[{trace_id}] 远程融合失败 ({e})，尝试本地冗余节点...")
            final_answer = await self._call_local_redundancy(fusion_instruction, trace_id)

        logger.info(f"[{trace_id}] SimpleFusion 策略完成")
        return final_answer

    async def _collect_candidates(self, messages: list, model_pool: list, trace_id: str) -> List[str]:
        """并发收集多个候选答案
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            List[str]: 候选答案列表
        """
        # 最多从前 3 个模型获取候选答案
        tasks = []
        for i, model in enumerate(model_pool[:3]):
            tasks.append(self.gateway.call(model, messages, f"{trace_id}-candidate{i+1}"))
        
        # 并发执行，允许部分失败
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤成功的结果
        candidates = []
        for i, result in enumerate(results):
            if isinstance(result, str):
                candidates.append(result)
            else:
                logger.warning(f"[{trace_id}] 候选 {i+1} 获取失败: {result}")
        
        return candidates

    async def _fallback_single_inference(self, messages: list, model_pool: list, trace_id: str) -> str:
        """回退到单模型推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 推理结果
        """
        if model_pool:
            return await self.gateway.call(model_pool[0], messages, trace_id)
        else:
            return await self._call_local_redundancy(
                next((msg['content'] for msg in messages if msg['role'] == 'user'), ""), 
                trace_id
            )

    async def _perform_fusion(self, fusion_instruction: str, model_pool: list, trace_id: str) -> str:
        """执行融合推理
        
        Args:
            fusion_instruction: 融合指令
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 融合结果
        """
        # 优先选择第一个模型（通常是最高算力）
        if model_pool:
            fusion_messages = [{"role": "user", "content": fusion_instruction}]
            return await self.gateway.call(model_pool[0], fusion_messages, f"{trace_id}-fusion")
        
        raise Exception("没有可用的融合模型")

    async def _call_local_redundancy(self, content: str, trace_id: str) -> str:
        """调用本地冗余节点
        
        从 config 获取地址，严禁硬编码。
        
        Args:
            content: 输入内容
            trace_id: 追踪 ID
            
        Returns:
            str: 本地模型响应
        """
        # 从 config 获取本地模型配置
        local_node = {
            "base_url": config.LM_STUDIO_URL,
            "api_key": "lm-studio",
            "model_name": config.DEFAULT_EXECUTION_MODEL,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        messages = [{"role": "user", "content": content}]
        
        try:
            result = await self.gateway.call(local_node, messages, f"{trace_id}-local-fallback")
            return f"[本地融合] {result}"
        except Exception as e:
            logger.error(f"[{trace_id}] 本地冗余节点调用失败: {e}")
            return "所有模型都不可用，请稍后重试。"


# PromptManager 需要添加 get_fusion_prompt 方法
def _add_fusion_prompt_to_prompt_manager():
    """为 PromptManager 添加融合提示方法（如果尚未存在）"""
    if not hasattr(PromptManager, 'get_fusion_prompt'):
        @staticmethod
        def get_fusion_prompt(candidates: List[str]) -> str:
            """生成融合提示词
            
            Args:
                candidates: 候选答案列表
                
            Returns:
                str: 融合提示词
            """
            candidates_str = "\n\n".join([
                f"候选 {i+1}：\n{answer}" 
                for i, answer in enumerate(candidates)
            ])
            
            return f"""你是一个专业的 AI 融合专家，能够综合多个 AI 的回答，生成一个更全面、更准确的最终回答。

以下是多个 AI 对同一个问题的回答：

{candidates_str}

请基于以上回答，生成一个综合的、高质量的最终回答。要求：
1. 综合所有候选答案的优点
2. 消除重复内容
3. 保持逻辑连贯
4. 如果候选答案之间有冲突，请指出并给出你的判断"""
        
        PromptManager.get_fusion_prompt = get_fusion_prompt


# 初始化时添加融合提示方法
_add_fusion_prompt_to_prompt_manager()