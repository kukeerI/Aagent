# src/core/strategies/simple_fusion.py
# 简单融合策略
# 依赖：typing, src.utils.logger
# 注意事项：
#   - 简单融合多个 AI 回答生成最终结果
#   - 使用本地模型进行融合处理

from typing import List, Dict, Any

from src.utils.logger import logger


class SimpleFusionStrategy:
    """简单融合策略

    将多个 AI 的回答进行综合，生成一个更全面、更准确的最终回答。
    """

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行简单融合推理

        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪ID

        Returns:
            str: 推理结果
        """
        logger.info(f"[{trace_id}] 开始简单融合策略")

        # 构建融合提示
        fusion_prompt = "你是一个专业的 AI 融合专家，能够综合多个 AI 的回答，生成一个更全面、更准确的最终回答。\n\n"
        fusion_prompt += "以下是多个 AI 对同一个问题的回答：\n\n"

        # 如果没有消息，返回默认值
        if not messages:
            logger.warning(f"[{trace_id}] 融合失败：没有可用的消息")
            return "融合失败：没有可用的消息"

        # 提取用户输入
        user_input = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")
        fusion_prompt += f"用户问题: {user_input}\n\n"

        # 模拟多个 AI 回答（实际应用中应该从模型池获取）
        for i in range(3):
            fusion_prompt += f"AI {i+1}: 这是对问题的回答 {i+1}\n\n"

        fusion_prompt += "请基于以上回答，生成一个综合的、高质量的最终回答。"

        # 使用本地模型进行融合
        local_response = await self._try_local_model([{"role": "user", "content": fusion_prompt}])
        
        if local_response:
            logger.info(f"[{trace_id}] 简单融合策略完成")
            return local_response
        else:
            logger.error(f"[{trace_id}] 简单融合策略失败")
            return "融合失败"

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> str:
        """尝试使用本地模型

        Args:
            messages: 消息列表

        Returns:
            str: 本地模型响应，失败返回 None
        """
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
            logger.error(f"[Local Model Error] {e}")
            return None
