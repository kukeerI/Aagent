from pydantic import BaseModel, Field
from typing import List, Optional

class Message(BaseModel):
    role: str = Field(..., description="角色: system, user, assistant, tool")
    content: str

class GatewayRequest(BaseModel):
    messages: List[Message]
    domain_skill: str = Field(default="Logic")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)

class AgentAction(BaseModel):
    """主脑下发的路由动作，Orchestrator 将严格校验此结构"""
    thought_process: str = Field(..., description="对当前局势的分析与思考")
    next_role: str = Field(..., description="路由去向: Analyst, Operator, Researcher, Maker, Companion")
    action_input: str = Field(..., description="下发给该角色的具体 Prompt 或要执行的代码")
    is_completed: bool = Field(default=False, description="任务是否彻底完成")