# src/core/strategies/plan_and_solve.py
# PlanAndSolve 策略 - 计划与步进执行版本
# 依赖：json, re, typing, src.core.strategies.base, src.services.gateway, src.utils.logger
# 注意事项：
#   - 强制模型先输出 JSON 格式的计划表
#   - 实现强大的 JSON 解析和修复逻辑
#   - 按步骤执行并处理每一步的异常
#   - 实现上下文压缩防止膨胀

import json
import re
from typing import List, Dict, Any

from src.core.strategies.base import ReasoningStrategy
from src.services.gateway import AsyncGateway
from src.utils.logger import logger


class PlanAndSolveStrategy(ReasoningStrategy):
    """
    PlanAndSolve 策略：先规划任务树，再步进执行。
    
    核心逻辑：
    1. 规划阶段：强制要求模型输出 JSON 格式的步骤列表
    2. 步进执行阶段：按步骤执行，记录每一步的结果
    3. 终结汇总阶段：基于执行过程给出最终答案
    """

    def __init__(self):
        """初始化 PlanAndSolve 策略"""
        self.gateway = AsyncGateway()

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行 PlanAndSolve 推理
        
        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 推理结果
        """
        logger.info(f"[{trace_id}] 开始 PlanAndSolve 策略")
        
        model = model_pool[0]
        
        # 1. 规划阶段：强制要求 JSON 输出
        plan_raw = await self._generate_plan(messages, model, trace_id)
        
        try:
            steps = self._parse_steps(plan_raw)
            logger.info(f"[{trace_id}] 解析到 {len(steps)} 个步骤")
        except Exception as e:
            logger.warning(f"[{trace_id}] 解析计划失败 ({e})，使用兜底计划")
            steps = ["分析问题", "执行解决", "总结结果"]

        # 2. 步进执行阶段
        context = ""
        execution_history = []
        
        for i, step in enumerate(steps):
            logger.info(f"[{trace_id}] 执行计划步骤 {i+1}/{len(steps)}: {step}")
            
            try:
                step_result = await self._execute_step(messages, context, step, i + 1, len(steps), model, trace_id)
                execution_history.append({"step": step, "result": step_result})
                context += f"\n步骤{i+1}({step}): {step_result[:1000]}"  # 限制长度
            except Exception as e:
                logger.error(f"[{trace_id}] 步骤 {i+1} 执行失败: {e}")
                execution_history.append({"step": step, "result": f"执行失败: {str(e)}", "error": True})
                # 继续执行下一步，不中断整个流程
            
            # 上下文压缩：只保留最近的步骤结果
            context = self._compress_context(execution_history)

        # 3. 终结汇总
        final_answer = await self._summarize_results(messages, execution_history, model, trace_id)
        
        logger.info(f"[{trace_id}] PlanAndSolve 策略完成")
        return final_answer

    async def _generate_plan(self, messages: list, model: dict, trace_id: str) -> str:
        """生成执行计划
        
        Args:
            messages: 消息列表
            model: 模型配置
            trace_id: 追踪 ID
            
        Returns:
            str: 计划内容（期望 JSON 格式）
        """
        plan_prompt = """请将任务分解为 3-5 个逻辑步骤。
        
要求：
1. 只输出 JSON 数组格式，例如：["步骤1", "步骤2", "步骤3"]
2. 步骤要具体、可执行
3. 不要输出任何额外文字

用户问题："""
        
        user_input = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")
        plan_messages = messages + [{"role": "system", "content": plan_prompt + user_input}]
        
        return await self.gateway.call(model, plan_messages, f"{trace_id}-plan")

    def _parse_steps(self, plan_raw: str) -> List[str]:
        """解析计划步骤
        
        实现强大的 JSON 解析和修复逻辑，处理模型输出不稳定的问题。
        
        Args:
            plan_raw: 原始计划字符串
            
        Returns:
            List[str]: 步骤列表
            
        Raises:
            ValueError: 解析失败时抛出
        """
        if not plan_raw:
            raise ValueError("计划内容为空")
            
        # 尝试提取 JSON 数组
        # 方法1：直接解析
        try:
            result = json.loads(plan_raw)
            if isinstance(result, list) and all(isinstance(s, str) for s in result):
                return result
        except json.JSONDecodeError:
            pass
        
        # 方法2：使用正则表达式提取数组内容
        match = re.search(r'\[.*?\]', plan_raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list) and all(isinstance(s, str) for s in result):
                    return result
            except json.JSONDecodeError:
                pass
        
        # 方法3：提取引号内的内容作为步骤
        steps = re.findall(r'"([^"]+)"', plan_raw)
        if steps:
            return steps
        
        # 方法4：按数字序号分割
        numbered_steps = re.findall(r'\d+[.\uff0e、]([^\\n]+)', plan_raw)
        if numbered_steps:
            return [s.strip() for s in numbered_steps]
        
        # 方法5：简单分割
        lines = [line.strip() for line in plan_raw.split('\n') if line.strip()]
        if lines and len(lines) <= 10:
            return lines
        
        raise ValueError(f"无法解析计划: {plan_raw[:100]}...")

    async def _execute_step(self, original_messages: list, context: str, step: str, 
                           step_num: int, total_steps: int, model: dict, trace_id: str) -> str:
        """执行单个步骤
        
        Args:
            original_messages: 原始消息列表
            context: 上下文信息
            step: 当前步骤描述
            step_num: 当前步骤序号
            total_steps: 总步骤数
            model: 模型配置
            trace_id: 追踪 ID
            
        Returns:
            str: 步骤执行结果
        """
        step_prompt = f"""当前任务进度：{step_num}/{total_steps}
        
当前上下文：
{context}

请执行第 {step_num} 步：{step}

要求：
1. 专注于当前步骤
2. 提供详细的执行过程
3. 输出步骤结果"""

        step_messages = original_messages + [
            {"role": "system", "content": step_prompt}
        ]
        
        return await self.gateway.call(model, step_messages, f"{trace_id}-step{step_num}")

    async def _summarize_results(self, original_messages: list, execution_history: list, model: dict, trace_id: str) -> str:
        """总结执行结果
        
        Args:
            original_messages: 原始消息列表
            execution_history: 执行历史
            model: 模型配置
            trace_id: 追踪 ID
            
        Returns:
            str: 最终总结
        """
        history_str = "\n".join([
            f"{i+1}. {item['step']}: {item['result'][:500]}" 
            for i, item in enumerate(execution_history)
        ])
        
        summary_prompt = f"""请基于以下执行过程给出最终答案：

执行步骤：
{history_str}

要求：
1. 综合所有步骤的结果
2. 提供清晰、完整的最终答案
3. 如果有步骤失败，请说明影响"""

        summary_messages = original_messages + [{"role": "system", "content": summary_prompt}]
        
        return await self.gateway.call(model, summary_messages, f"{trace_id}-summary")

    def _compress_context(self, execution_history: list, max_steps: int = 3) -> str:
        """压缩上下文，只保留最近的步骤
        
        Args:
            execution_history: 执行历史
            max_steps: 最大保留步骤数
            
        Returns:
            str: 压缩后的上下文
        """
        recent_history = execution_history[-max_steps:]
        return "\n".join([
            f"步骤{i+1}({item['step']}): {item['result'][:500]}" 
            for i, item in enumerate(recent_history)
        ])