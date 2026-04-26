# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Any
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


class Message(BaseModel):
    role: str = Field(..., description="角色: system, user, assistant, tool")
    content: str
    name: Optional[str] = None

class GatewayRequest(BaseModel):
    messages: List[Message]
    domain_skill: str = Field(default="Logic")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)

class AgentAction(BaseModel):
    """总司令下发的动作指令，Orchestrator 将严格校验此结构"""
    thought_process: str = Field(..., description="对当前局势的分析与思考")
    next_role: str = Field(..., description="路由到哪个下属角色 (Maker, Checker, Operator, Done)")
    action_input: str = Field(..., description="给下属角色的具体 Prompt 或要执行的代码")
    is_completed: bool = Field(default=False, description="任务是否彻底完成")