# src/data/schemas.py
# 数据模型

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

class DraftScore(BaseModel):
    draft_id: str
    factuality_score: int = Field(ge=1, le=5, description="事实准确性得分")
    logic_score: int = Field(ge=1, le=5, description="逻辑自洽性得分")
    efficiency_score: int = Field(ge=1, le=5, description="执行效率得分")
    justification: str = Field(description="打分事实依据")

class Vulnerability(BaseModel):
    draft_id: str
    severity: Literal["High", "Medium", "Low"]
    description: str = Field(description="致命漏洞、幻觉或效率陷阱的描述")

class JudgeResponse(BaseModel):
    scores: List[DraftScore]
    vulnerabilities: List[Vulnerability]
    best_draft_id: str
    winning_reason: str

class EntityCheck(BaseModel):
    entity_name: str
    confidence: Literal["High", "Medium", "Low"]
    verification_query: Optional[str] = Field(description="用于搜索引擎核实的关键词（仅中低置信度需要）")

class EntityVerificationResponse(BaseModel):
    entities: List[EntityCheck]

class TaskRequest(BaseModel):
    task: str = Field(..., description="任务描述")
    trace_id: Optional[str] = Field(None, description="追踪ID")

class TaskResponse(BaseModel):
    trace_id: str = Field(..., description="追踪ID")
    status: str = Field(..., description="任务状态")
    result: Optional[str] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")

class HealthResponse(BaseModel):
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    active_tasks: int = Field(..., description="活跃任务数")

class GatewayRequest(BaseModel):
    model: str = Field(..., description="模型名称")
    messages: List[Dict[str, str]] = Field(..., description="消息列表")
    domain_skill: str = Field(..., description="领域技能")

class ExecutionLogSchema(BaseModel):
    id: int
    trace_id: str
    input_text: str
    response: Optional[str]
    model_used: Optional[str]
    is_local_fallback: bool
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class APIAssetSchema(BaseModel):
    id: int
    model_name: str
    base_url: str
    weight: int
    consecutive_failures: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True