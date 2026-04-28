# src/core/prompts.py
# 提示词模板引擎模块 - 提供各类提示词模板和消息构建功能
# 依赖：typing, src.data.domain_models
# 注意事项：
#   - SystemPrompts: 系统角色提示词
#   - UserPrompts: 用户任务提示词
#   - JudgePrompts: 评审提示词（用于四步评审工作流）
#   - PromptEngine: 提示词引擎，用于构建消息列表

from typing import Dict, Any, Optional
from src.data.domain_models import AgentTask, TaskType, RouteLevel


class PromptTemplate:
    """提示词模板基类

    定义提示词模板的接口，所有具体模板都应该继承此类。
    """

    def render(self, **kwargs) -> str:
        """渲染模板

        Args:
            **kwargs: 渲染参数

        Returns:
            str: 渲染后的提示词文本

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError


class SystemPrompts:
    """系统提示词类

    提供各种角色的系统提示词，用于定义 AI 的角色和行为。
    """

    @staticmethod
    def get_analyst_prompt() -> str:
        """获取分析师提示词

        Returns:
            str: 分析师角色提示词
        """
        return "你是一个专业的任务分析专家，能够快速准确地分析用户请求的类型和复杂度。"

    @staticmethod
    def get_operator_prompt() -> str:
        """获取操作员提示词

        Returns:
            str: 操作员角色提示词
        """
        return "你是一个高效的任务执行操作员，能够按照指示完成各种任务。"

    @staticmethod
    def get_researcher_prompt() -> str:
        """获取研究员提示词

        Returns:
            str: 研究员角色提示词
        """
        return "你是一个博学多才的研究员，能够提供全面、准确的信息。"

    @staticmethod
    def get_maker_prompt() -> str:
        """获取创作者提示词

        Returns:
            str: 创作者角色提示词
        """
        return "你是一个创意丰富的内容创作者，能够生成高质量的原创内容。"

    @staticmethod
    def get_companion_prompt() -> str:
        """获取智能助手提示词

        Returns:
            str: 智能助手角色提示词
        """
        return "你是一个友好的智能助手，能够回答各种问题并提供帮助。"

    @staticmethod
    def get_prompt_for_task(task: AgentTask) -> str:
        """根据任务类型获取系统提示词

        Args:
            task: 智能体任务对象

        Returns:
            str: 对应任务类型的系统提示词
        """
        if task.semantic_data:
            task_type = task.semantic_data.task_type
        else:
            task_type = TaskType.GENERAL

        if task_type == TaskType.CODE:
            return SystemPrompts.get_operator_prompt()
        elif task_type == TaskType.ANALYSIS:
            return SystemPrompts.get_analyst_prompt()
        elif task_type == TaskType.CREATIVE:
            return SystemPrompts.get_maker_prompt()
        elif task_type == TaskType.INFORMATION:
            return SystemPrompts.get_researcher_prompt()
        else:
            return SystemPrompts.get_companion_prompt()


class UserPrompts:
    """用户提示词类

    提供各种用户任务的提示词，用于指导 AI 执行具体任务。
    """

    @staticmethod
    def analyze_task(task: str) -> str:
        """获取任务分析提示词

        Args:
            task: 任务描述

        Returns:
            str: 任务分析提示词
        """
        return f"分析任务: {task}\n\n请输出一个JSON对象，包含以下字段：\n- task_type: 任务类型 (如 code_generation, analysis, research, creative)\n- complexity: 复杂度 (low, medium, high)\n- required_skills: 需要的技能列表\n- estimated_time: 估计执行时间（分钟）"

    @staticmethod
    def execute_task(task: str, task_type: str) -> str:
        """获取任务执行提示词

        Args:
            task: 任务描述
            task_type: 任务类型

        Returns:
            str: 任务执行提示词
        """
        return f"执行任务: {task}\n\n任务类型: {task_type}\n\n请提供详细的执行步骤和结果。"

    @staticmethod
    def research_task(topic: str) -> str:
        """获取研究任务提示词

        Args:
            topic: 研究主题

        Returns:
            str: 研究任务提示词
        """
        return f"研究主题: {topic}\n\n请提供详细的研究结果，包括关键信息、背景知识和相关资源。"

    @staticmethod
    def create_task(request: str) -> str:
        """获取创作任务提示词

        Args:
            request: 创作请求

        Returns:
            str: 创作任务提示词
        """
        return f"创建请求: {request}\n\n请根据请求生成相应的内容，确保质量和原创性。"

    @staticmethod
    def handle_error(error: str) -> str:
        """获取错误处理提示词

        Args:
            error: 错误信息

        Returns:
            str: 错误处理提示词
        """
        return f"错误信息: {error}\n\n请分析错误原因并提供解决方案。"

    @staticmethod
    def get_prompt_for_task(task: AgentTask) -> str:
        """根据任务类型获取用户提示词

        Args:
            task: 智能体任务对象

        Returns:
            str: 对应任务类型的用户提示词
        """
        if task.semantic_data:
            task_type = task.semantic_data.task_type
        else:
            task_type = TaskType.GENERAL

        if task_type == TaskType.CODE:
            return UserPrompts.execute_task(task.user_input, "code")
        elif task_type == TaskType.ANALYSIS:
            return UserPrompts.analyze_task(task.user_input)
        elif task_type == TaskType.CREATIVE:
            return UserPrompts.create_task(task.user_input)
        elif task_type == TaskType.INFORMATION:
            return UserPrompts.research_task(task.user_input)
        else:
            return UserPrompts.execute_task(task.user_input, "general")


class JudgePrompts:
    """评审提示词类

    提供评审和实体核查的提示词模板，用于四步评审工作流。
    """

    @staticmethod
    def dual_persona_judge(drafts: str) -> str:
        """获取双角色评审提示词

        Args:
            drafts: 草案内容

        Returns:
            str: 双角色评审提示词
        """
        return f"""
你是一个专业的AI评审系统，需要对多个匿名方案进行双角色评审。

## 输入信息
以下是已匿名的方案，随机打乱顺序后重新标记为 Draft A, Draft B, Draft C：

{drafts}

## 评审要求
1. **严谨的评分官角色**：
   - 基于以下三个维度对每个方案进行 1-5 分的评分：
     - 事实准确性（factuality_score）：信息是否准确，是否有事实依据
     - 逻辑自洽性（logic_score）：逻辑是否严密，推理是否合理
     - 执行效率（efficiency_score）：方案是否高效，是否有优化空间
   - 为每个评分提供详细的事实依据（justification）

2. **尖刻的审查官角色**：
   - 全力找出每个方案中的致命漏洞、幻觉或效率陷阱
   - 忽略优点，只关注问题
   - 对每个问题标注严重程度（High/Medium/Low）

3. **最终决策**：
   - 综合考虑评分和漏洞，选出最佳方案（best_draft_id）
   - 提供明确的获胜理由（winning_reason）

## 输出格式
请严格按照以下 JSON 格式输出，不要添加任何额外内容：

{{
  "scores": [
    {{
      "draft_id": "Draft A",
      "factuality_score": 5,
      "logic_score": 4,
      "efficiency_score": 3,
      "justification": "详细的打分依据"
    }},
    {{
      "draft_id": "Draft B",
      "factuality_score": 4,
      "logic_score": 5,
      "efficiency_score": 4,
      "justification": "详细的打分依据"
    }},
    {{
      "draft_id": "Draft C",
      "factuality_score": 3,
      "logic_score": 3,
      "efficiency_score": 5,
      "justification": "详细的打分依据"
    }}
  ],
  "vulnerabilities": [
    {{
      "draft_id": "Draft A",
      "severity": "Medium",
      "description": "漏洞描述"
    }}
  ],
  "best_draft_id": "Draft A",
  "winning_reason": "详细的获胜理由"
}}
"""

    @staticmethod
    def entity_verification(winning_draft: str) -> str:
        """获取实体核查提示词

        Args:
            winning_draft: 获胜方案内容

        Returns:
            str: 实体核查提示词
        """
        return f"""
你是一个专业的实体核查专家，需要对获胜方案中的实体进行置信度评估。

## 输入信息
以下是获胜方案的内容：

{winning_draft}

## 核查要求
1. 提取方案中所有的专有名词、数据、工具名等实体
2. 对每个实体标注置信度：
   - High：非常确定实体存在且信息准确
   - Medium：有一定把握但需要核实
   - Low：不确定，需要搜索引擎核实
3. 对于 Medium 和 Low 置信度的实体，生成用于搜索引擎核实的关键词（verification_query）

## 输出格式
请严格按照以下 JSON 格式输出，不要添加任何额外内容：

{{
  "entities": [
    {{
      "entity_name": "实体名称",
      "confidence": "High",
      "verification_query": null
    }},
    {{
      "entity_name": "实体名称",
      "confidence": "Medium",
      "verification_query": "核实关键词"
    }},
    {{
      "entity_name": "实体名称",
      "confidence": "Low",
      "verification_query": "核实关键词"
    }}
  ]
}}
"""


class PromptEngine:
    """提示词引擎类

    提供消息列表构建功能，用于组装系统提示词、用户提示词和对话历史。
    """

    @staticmethod
    def build_messages(task: AgentTask) -> list:
        """根据任务构建消息列表

        Args:
            task: 智能体任务对象

        Returns:
            list: 消息列表，包含 system 和 user 角色消息
        """
        system_prompt = SystemPrompts.get_prompt_for_task(task)
        user_prompt = UserPrompts.get_prompt_for_task(task)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 如果有之前的上下文，添加到消息中
        if task.previous_context and "conversation_history" in task.previous_context:
            for msg in task.previous_context["conversation_history"]:
                messages.insert(1, msg)

        return messages

    @staticmethod
    def build_judge_messages(drafts: list) -> list:
        """构建评审消息

        Args:
            drafts: 草案列表

        Returns:
            list: 评审消息列表
        """
        drafts_text = "\n".join([f"Draft {chr(65+i)}: {draft}" for i, draft in enumerate(drafts)])
        prompt = JudgePrompts.dual_persona_judge(drafts_text)

        return [
            {"role": "system", "content": "你是一个专业的AI评审系统，需要对多个匿名方案进行双角色评审。"},
            {"role": "user", "content": prompt}
        ]

    @staticmethod
    def build_entity_verification_messages(winning_draft: str) -> list:
        """构建实体核查消息

        Args:
            winning_draft: 获胜方案内容

        Returns:
            list: 实体核查消息列表
        """
        prompt = JudgePrompts.entity_verification(winning_draft)

        return [
            {"role": "system", "content": "你是一个专业的实体核查专家，需要对获胜方案中的实体进行置信度评估。"},
            {"role": "user", "content": prompt}
        ]
