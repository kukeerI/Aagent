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