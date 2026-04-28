# src/core/strategies/plan_and_solve.py
# Plan and Solve 策略

from typing import List, Dict, Any

from src.services.tracing import tracing

class PlanAndSolveStrategy:
    """Plan and Solve 策略"""
    
    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行 Plan and Solve 推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪ID
            
        Returns:
            推理结果
        """
        with tracing.start_span("plan_and_solve.execute", attributes={
            "trace_id": trace_id,
            "message_count": len(messages)
        }) as span:
            print(f"\n[{trace_id}] ========================================")
            print(f"[{trace_id}] 开始 Plan and Solve 策略")
            print(f"[{trace_id}] ========================================")

            # 构建 Plan and Solve 提示
            plan_prompt = "你是一个使用 Plan and Solve 模式的 AI 助手。请按照以下步骤解决问题：\n\n"
            plan_prompt += "1. 首先分析问题，制定一个详细的解决方案计划\n"
            plan_prompt += "2. 然后按照计划逐步执行，解决问题\n"
            plan_prompt += "3. 最后总结解决方案和结果\n\n"
            
            # 提取用户输入
            user_input = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")
            plan_prompt += f"用户问题: {user_input}"
            
            # 构建消息
            plan_messages = [
                {"role": "system", "content": plan_prompt},
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
                        messages=plan_messages,
                        temperature=0.7
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    print(f"[Plan and Solve Error] {e}")
                    return "Plan and Solve 执行失败"
            else:
                return "没有可用的模型"
