# src/core/strategies/reflexion.py
# Reflexion 策略
# 依赖：typing, src.services.tracing, src.utils.logger
# 注意事项：
#   - 实现了 Reflexion 推理模式
#   - 通过反思和自我修正来改进解决方案

from typing import List, Dict, Any

from src.services.tracing import tracing
from src.utils.logger import logger


class ReflexionStrategy:
    """Reflexion 策略

    通过尝试-反思-调整循环来解决问题，适合需要自我修正的复杂任务。
    """

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行 Reflexion 推理

        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪ID

        Returns:
            str: 推理结果
        """
        with tracing.start_span("reflexion.execute", attributes={
            "trace_id": trace_id,
            "message_count": len(messages)
        }) as span:
            logger.info(f"[{trace_id}] 开始 Reflexion 策略")

            # 构建 Reflexion 提示
            reflexion_prompt = "你是一个使用 Reflexion 模式的 AI 助手。请按照以下步骤解决问题：\n\n"
            reflexion_prompt += "1. 首先尝试解决问题\n"
            reflexion_prompt += "2. 然后反思你的解决方案，找出可能的错误或改进点\n"
            reflexion_prompt += "3. 基于反思结果，重新调整并最终解决问题\n\n"

            # 提取用户输入
            user_input = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")
            reflexion_prompt += f"用户问题: {user_input}"

            # 构建消息
            reflexion_messages = [
                {"role": "system", "content": reflexion_prompt},
                {"role": "user", "content": user_input}
            ]

            # 调用模型
            if model_pool:
                node = model_pool[0]
                try:
                    from openai import AsyncOpenAI
                    client = AsyncOpenAI(
                        base_url=node["base_url"],
                        api_key=node["api_key"]
                    )
                    response = await client.chat.completions.create(
                        model=node["model_name"],
                        messages=reflexion_messages,
                        temperature=0.7
                    )
                    logger.info(f"[{trace_id}] Reflexion 策略完成")
                    return response.choices[0].message.content
                except Exception as e:
                    logger.error(f"[{trace_id}] [Reflexion Error] {e}")
                    return "Reflexion 执行失败"
            else:
                logger.warning(f"[{trace_id}] 没有可用的模型")
                return "没有可用的模型"
