# src/data/schemas.py
# 数据模型

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

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