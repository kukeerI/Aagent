# src/core/prompts.py
# 提示词模板

class SystemPrompts:
    ANALYST = "你是一个专业的任务分析专家，能够快速准确地分析用户请求的类型和复杂度。"
    OPERATOR = "你是一个高效的任务执行操作员，能够按照指示完成各种任务。"
    RESEARCHER = "你是一个博学多才的研究员，能够提供全面、准确的信息。"
    MAKER = "你是一个创意丰富的内容创作者，能够生成高质量的原创内容。"
    COMPANION = "你是一个友好的智能助手，能够回答各种问题并提供帮助。"

class UserPrompts:
    ANALYZE_TASK = "分析任务: {task}\n\n请输出一个JSON对象，包含以下字段：\n- task_type: 任务类型 (如 code_generation, analysis, research, creative)\n- complexity: 复杂度 (low, medium, high)\n- required_skills: 需要的技能列表\n- estimated_time: 估计执行时间（分钟）"
    EXECUTE_TASK = "执行任务: {task}\n\n任务类型: {task_type}\n\n请提供详细的执行步骤和结果。"
    RESEARCH_TASK = "研究主题: {topic}\n\n请提供详细的研究结果，包括关键信息、背景知识和相关资源。"
    CREATE_TASK = "创建请求: {request}\n\n请根据请求生成相应的内容，确保质量和原创性。"
    HANDLE_ERROR = "错误信息: {error}\n\n请分析错误原因并提供解决方案。"

class JudgePrompts:
    DUAL_PERSONA_JUDGE_PROMPT = """
你是一个专业的AI评审系统，需要对多个匿名方案进行双角色评审。

## 输入信息
以下是已匿名的方案，随机打乱顺序后重新标记为 Draft A, Draft B, Draft C：

{DRAFTS}

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

{
  "scores": [
    {
      "draft_id": "Draft A",
      "factuality_score": 5,
      "logic_score": 4,
      "efficiency_score": 3,
      "justification": "详细的打分依据"
    },
    {
      "draft_id": "Draft B",
      "factuality_score": 4,
      "logic_score": 5,
      "efficiency_score": 4,
      "justification": "详细的打分依据"
    },
    {
      "draft_id": "Draft C",
      "factuality_score": 3,
      "logic_score": 3,
      "efficiency_score": 5,
      "justification": "详细的打分依据"
    }
  ],
  "vulnerabilities": [
    {
      "draft_id": "Draft A",
      "severity": "Medium",
      "description": "漏洞描述"
    }
  ],
  "best_draft_id": "Draft A",
  "winning_reason": "详细的获胜理由"
}
"""

    ENTITY_VERIFICATION_PROMPT = """
你是一个专业的实体核查专家，需要对获胜方案中的实体进行置信度评估。

## 输入信息
以下是获胜方案的内容：

{WINNING_DRAFT}

## 核查要求
1. 提取方案中所有的专有名词、数据、工具名等实体
2. 对每个实体标注置信度：
   - High：非常确定实体存在且信息准确
   - Medium：有一定把握但需要核实
   - Low：不确定，需要搜索引擎核实
3. 对于 Medium 和 Low 置信度的实体，生成用于搜索引擎核实的关键词（verification_query）

## 输出格式
请严格按照以下 JSON 格式输出，不要添加任何额外内容：

{
  "entities": [
    {
      "entity_name": "实体名称",
      "confidence": "High",
      "verification_query": null
    },
    {
      "entity_name": "实体名称",
      "confidence": "Medium",
      "verification_query": "核实关键词"
    },
    {
      "entity_name": "实体名称",
      "confidence": "Low",
      "verification_query": "核实关键词"
    }
  ]
}
"""
