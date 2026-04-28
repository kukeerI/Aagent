# src/core/strategies/react_loop.py
# ReAct 循环策略

import asyncio
import time
from typing import List, Dict, Any, Optional

from src.services.tracing import tracing
from src.data.domain_models import AgentTask
from src.config import config

class ReactLoopStrategy:
    """ReAct 循环策略"""
    
    def __init__(self):
        self.max_react_steps = 10
        self.window_size = 3  # 滑动窗口大小
    
    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行 ReAct 循环推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪ID
            
        Returns:
            推理结果
        """
        with tracing.start_span("react_loop.execute", attributes={
            "trace_id": trace_id,
            "message_count": len(messages)
        }) as span:
            print(f"\n[{trace_id}] ========================================")
            print(f"[{trace_id}] 开始 ReAct 循环策略")
            print(f"[{trace_id}] ========================================")

            # 初始化 ReAct 循环
            react_history = []
            final_answer = None
            
            for step in range(self.max_react_steps):
                print(f"\n[ReAct Step {step+1}]")
                
                # 构建当前消息（带滑动窗口）
                current_messages = self._build_react_messages(messages, react_history)
                
                # 调用模型获取思考和行动
                thought, action = await self._get_thought_and_action(current_messages, model_pool, trace_id)
                
                if not thought and not action:
                    break
                
                # 执行行动
                observation = await self._execute_action(action, trace_id)
                
                # 压缩观察结果
                compressed_observation = self._summarize_observation(observation)
                
                # 更新 ReAct 历史
                react_history.append({
                    "thought": thought,
                    "action": action,
                    "observation": compressed_observation
                })
                
                # 检查是否有最终答案
                if "最终答案" in thought or "Final Answer" in thought:
                    final_answer = self._extract_final_answer(thought)
                    break
            
            if not final_answer:
                final_answer = "ReAct 循环结束，未找到最终答案"
            
            print(f"\n[{trace_id}] ========================================")
            print(f"[{trace_id}] ReAct 循环策略完成")
            print(f"[{trace_id}] ========================================")
            
            return final_answer
    
    def _build_react_messages(self, initial_messages: List[Dict[str, str]], react_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """构建 ReAct 消息，使用滑动窗口"""
        messages = initial_messages.copy()
        
        # 添加 ReAct 格式指令
        react_instruction = {
            "role": "system",
            "content": "你是一个使用 ReAct 模式的 AI 助手。请按照以下格式进行思考和行动：\n\n思考：[你的思考过程]\n行动：[你要执行的行动]\n\n然后我会提供观察结果，你继续思考和行动，直到找到最终答案。"
        }
        messages.insert(0, react_instruction)
        
        # 使用滑动窗口添加最近的 ReAct 历史
        recent_history = react_history[-self.window_size:] if len(react_history) > self.window_size else react_history
        
        for item in recent_history:
            messages.append({"role": "assistant", "content": f"思考：{item['thought']}\n行动：{item['action']}"})
            messages.append({"role": "user", "content": f"观察：{item['observation']}"})
        
        return messages
    
    async def _get_thought_and_action(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> tuple:
        """获取思考和行动"""
        try:
            if not model_pool:
                return "", ""
            
            node = model_pool[0]
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=node["base_url"],
                api_key=node["api_key"]
            )
            response = await client.chat.completions.create(
                model=node["model_name"],
                messages=messages,
                temperature=0.7
            )
            content = response.choices[0].message.content
            
            # 解析思考和行动
            thought = ""
            action = ""
            
            if "思考：" in content:
                thought_part = content.split("思考：")[1]
                if "行动：" in thought_part:
                    thought = thought_part.split("行动：")[0].strip()
                    action = thought_part.split("行动：")[1].strip()
            
            return thought, action
        except Exception as e:
            print(f"[ReAct Error] {e}")
            return "", ""
    
    async def _execute_action(self, action: str, trace_id: str) -> str:
        """执行行动"""
        # 这里简化处理，实际应用中应该根据行动类型执行不同的操作
        print(f"[执行行动] {action}")
        await asyncio.sleep(1)  # 模拟执行时间
        return f"行动 '{action}' 执行成功"
    
    def _summarize_observation(self, observation: str) -> str:
        """压缩观察结果"""
        # 简单的压缩逻辑，实际应用中可以使用更复杂的方法
        if len(observation) > 100:
            return observation[:100] + "..."
        return observation
    
    def _extract_final_answer(self, thought: str) -> str:
        """提取最终答案"""
        # 简单的提取逻辑，实际应用中可以使用更复杂的方法
        return thought.replace("最终答案", "").replace("Final Answer", "").strip()
