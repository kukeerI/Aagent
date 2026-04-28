# src/data/schemas.py
# 数据模型模块 - 定义 API 请求和响应的数据结构
# 依赖：pydantic, typing, datetime
# 注意事项：
#   - 所有类都继承自 BaseModel
#   - 字段使用 Field 进行约束和描述
#   - 用于 API 请求/响应验证和数据交换

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class DraftScore(BaseModel):
    """打分信息模型

    用于存储对单个草案的多维度评分。
    """
    draft_id: str
    factuality_score: int = Field(ge=1, le=5, description="事实准确性得分")
    logic_score: int = Field(ge=1, le=5, description="逻辑自洽性得分")
    efficiency_score: int = Field(ge=1, le=5, description="执行效率得分")
    justification: str = Field(description="打分事实依据")


class Vulnerability(BaseModel):
    """漏洞信息模型

    用于存储检测到的致命漏洞、幻觉或效率陷阱。
    """
    draft_id: str
    severity: Literal["High", "Medium", "Low"]
    description: str = Field(description="致命漏洞、幻觉或效率陷阱的描述")


class JudgeResponse(BaseModel):
    """评估响应模型

    包含多个草案的评分和漏洞检测结果。
    """
    scores: List[DraftScore]
    vulnerabilities: List[Vulnerability]
    best_draft_id: str
    winning_reason: str


class EntityCheck(BaseModel):
    """实体核查模型

    用于存储需要核实的实体信息。
    """
    entity_name: str
    confidence: Literal["High", "Medium", "Low"]
    verification_query: Optional[str] = Field(description="用于搜索引擎核实的关键词（仅中低置信度需要）")


class EntityVerificationResponse(BaseModel):
    """实体验证响应模型

    包含多个实体的核查结果。
    """
    entities: List[EntityCheck]


class TaskRequest(BaseModel):
    """任务请求模型

    用户提交任务的请求格式。
    """
    task: str = Field(..., description="任务描述")
    trace_id: Optional[str] = Field(None, description="追踪ID")


class TaskResponse(BaseModel):
    """任务响应模型

    任务执行结果的响应格式。
    """
    trace_id: str = Field(..., description="追踪ID")
    status: str = Field(..., description="任务状态")
    result: Optional[str] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")


class HealthResponse(BaseModel):
    """健康检查响应模型

    用于健康检查端点的响应。
    """
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    active_tasks: int = Field(..., description="活跃任务数")


class GatewayRequest(BaseModel):
    """网关请求模型

    网关转发请求的格式。
    """
    model: str = Field(..., description="模型名称")
    messages: List[Dict[str, str]] = Field(..., description="消息列表")
    domain_skill: str = Field(..., description="领域技能")


class ExecutionLogSchema(BaseModel):
    """执行日志模型

    用于序列化执行日志数据。
    """
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
    """API 资产模型

    用于序列化 API 资产数据。
    """
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
