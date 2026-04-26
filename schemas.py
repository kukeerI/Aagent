# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

# 1. 任务 ROI 评估结果的格式
class TaskEvaluation(BaseModel):
    importance_weight: int = Field(..., ge=1, le=10, description="任务重要程度 1-10")
    estimated_tokens: int = Field(..., description="预估消耗的 Token 数量")
    is_approved: bool = Field(..., description="是否批准执行")
    strategy: str = Field(..., description="执行策略：单线程 / MAKER多副本")

# 2. 发给子 Agent 的任务包格式
class SubTaskPacket(BaseModel):
    task_id: str
    description: str
    target_agent_type: str = Field(..., description="如: Operator, Researcher")
    token_budget_limit: int
    fallback_action: str = Field(..., description="超支策略: skip 或 human_intervention")

# 3. 子 Agent 返回的执行结果格式
class AgentResult(BaseModel):
    status: str = Field(..., description="success 或 failed")
    actual_cost: int = Field(..., description="实际消耗 Token")
    final_output: str
    error_log: Optional[str] = None # 如果失败了，记录错误原因