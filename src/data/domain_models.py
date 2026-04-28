# src/data/domain_models.py
# 领域模型模块 - 定义系统核心实体和值对象
# 依赖：pydantic, typing, enum, datetime
# 注意事项：
#   - 使用 Pydantic 进行数据验证和类型管理
#   - 枚举值可以在序列化时自动转换
#   - 所有时间字段使用 ISO 格式

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class TaskType(str, Enum):
    """任务类型枚举

    定义系统支持的任务类型，用于任务分类和路由决策。
    """
    CODE = "code"           # 代码生成/修改任务
    ANALYSIS = "analysis"   # 数据分析任务
    CREATIVE = "creative"   # 创意创作任务
    INFORMATION = "information"  # 信息查询任务
    GENERAL = "general"     # 通用对话任务


class RouteLevel(int, Enum):
    """路由级别枚举

    定义任务复杂度等级，用于选择合适的推理策略和模型。
    级别越高，需要的算力和模型能力越强。
    """
    LOCAL_THROUGHPUT = 1  # 本地吞吐，简单任务
    STANDARD_AGENT = 2    # 标准智能体
    HIGH_VALUE_SINGLE = 3 # 高价值单步任务
    COMPLEX_EXECUTION = 4 # 复杂执行任务
    LOGIC_DEEP_DIVE = 5   # 逻辑深度任务
    CREATIVE_FUSION = 6   # 创意融合任务
    PEAK_GAME = 7         # 巅峰挑战任务


class TaskState(str, Enum):
    """任务状态枚举

    定义任务的生命周期状态。
    """
    INIT = "init"         # 初始化状态
    ANALYZE = "analyze"   # 分析中
    EXECUTE = "execute"   # 执行中
    RESEARCH = "research" # 研究中
    CREATE = "create"     # 创作中
    SUSPEND = "suspend"   # 挂起/暂停
    ERROR = "error"       # 执行错误
    COMPLETE = "complete" # 已完成


class SemanticData(BaseModel):
    """语义数据模型

    存储从用户输入中提取的语义特征，用于任务分析和路由决策。
    """
    task_type: TaskType                          # 任务类型
    drafts: List[str]                            # 多个草案
    embedding_distances: List[float]             # 嵌入距离
    semantic_variance: float                     # 语义方差
    extraction_time: float                       # 提取耗时（秒）


class IntentAnalysis(BaseModel):
    """意图分析结果模型

    存储任务意图分析的结果，包括价值、复杂度、创新性评分，
    以及推荐的路由级别。
    """
    value: int = Field(ge=1, le=10)             # 任务价值评分
    complexity: int = Field(ge=1, le=10)         # 复杂度评分
    innovation: int = Field(ge=1, le=5)          # 创新性评分
    route_level: RouteLevel                      # 推荐路由级别
    route_name: str                              # 路由级别名称

    @classmethod
    def determine_route_level(cls, complexity: int, innovation: int) -> RouteLevel:
        """根据复杂度和创新性确定路由级别

        Args:
            complexity: 复杂度评分（1-10）
            innovation: 创新性评分（1-5）

        Returns:
            RouteLevel: 推荐的路由级别
        """
        if complexity >= 8 and innovation >= 4:
            return RouteLevel.CREATIVE_FUSION
        elif complexity >= 7:
            return RouteLevel.LOGIC_DEEP_DIVE
        elif complexity >= 5:
            return RouteLevel.COMPLEX_EXECUTION
        elif complexity >= 3:
            return RouteLevel.HIGH_VALUE_SINGLE
        elif complexity >= 2:
            return RouteLevel.STANDARD_AGENT
        else:
            return RouteLevel.LOCAL_THROUGHPUT

    @classmethod
    def from_task(cls, user_input: str, semantic_data: Optional[SemanticData] = None) -> 'IntentAnalysis':
        """从任务创建意图分析

        Args:
            user_input: 用户输入文本
            semantic_data: 可选的语义数据

        Returns:
            IntentAnalysis: 意图分析结果
        """
        # 基于输入长度计算复杂度
        complexity = min(len(user_input) // 50 + 1, 10)
        innovation = 3

        if semantic_data:
            if semantic_data.task_type == TaskType.CREATIVE:
                innovation = 4
            elif semantic_data.task_type == TaskType.CODE:
                innovation = 3
            elif semantic_data.task_type == TaskType.ANALYSIS:
                innovation = 3
            elif semantic_data.task_type == TaskType.INFORMATION:
                innovation = 2

        route_level = cls.determine_route_level(complexity, innovation)
        route_name = route_level.name

        return cls(
            value=complexity,
            complexity=complexity,
            innovation=innovation,
            route_level=route_level,
            route_name=route_name
        )


class AgentTask(BaseModel):
    """智能体任务模型

    表示一个完整的任务执行上下文，包含所有相关状态和信息。
    这是系统在任务执行过程中的核心数据结构。
    """
    trace_id: str                                # 追踪 ID
    user_input: str                             # 用户输入
    state: TaskState = TaskState.INIT           # 当前状态
    routing_tier: Optional[RouteLevel] = None    # 路由级别
    extracted_intent: Optional[IntentAnalysis] = None  # 意图分析结果
    semantic_data: Optional[SemanticData] = None # 语义数据
    previous_context: Optional[Dict[str, Any]] = None  # 上一轮上下文
    final_answer: Optional[str] = None           # 最终答案
    error: Optional[str] = None                  # 错误信息
    model_used: Optional[str] = None             # 使用的模型
    is_local_fallback: bool = False             # 是否使用本地模型降级
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间

    class Config:
        use_enum_values = True

    def update_state(self, new_state: TaskState):
        """更新任务状态

        Args:
            new_state: 新状态
        """
        self.state = new_state
        self.updated_at = datetime.now()

    def set_error(self, error_message: str):
        """设置错误信息

        Args:
            error_message: 错误描述
        """
        self.error = error_message
        self.state = TaskState.ERROR
        self.updated_at = datetime.now()

    def set_final_answer(self, answer: str):
        """设置最终答案并标记完成

        Args:
            answer: 最终答案内容
        """
        self.final_answer = answer
        self.state = TaskState.COMPLETE
        self.updated_at = datetime.now()

    def analyze_intent(self):
        """分析任务意图

        根据用户输入和语义数据，进行意图分析并确定路由级别。
        """
        if not self.extracted_intent and self.semantic_data:
            self.extracted_intent = IntentAnalysis.from_task(self.user_input, self.semantic_data)
            self.routing_tier = self.extracted_intent.route_level
        elif not self.extracted_intent:
            self.extracted_intent = IntentAnalysis.from_task(self.user_input)
            self.routing_tier = self.extracted_intent.route_level

    def is_complex(self) -> bool:
        """判断任务是否复杂

        Returns:
            bool: 如果路由级别 >= 4 或输入长度 > 200 则为复杂任务
        """
        if self.routing_tier:
            return self.routing_tier.value >= 4
        return len(self.user_input) > 200

    def should_use_advanced_model(self) -> bool:
        """判断是否应该使用高级模型

        Returns:
            bool: 如果路由级别 >= 5 或任务为复杂任务
        """
        if self.routing_tier:
            return self.routing_tier.value >= 5
        return self.is_complex()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 包含所有字段的字典，枚举值会被转换为字符串
        """
        data = self.model_dump()
        if isinstance(data.get('state'), TaskState):
            data['state'] = data['state'].value
        if isinstance(data.get('routing_tier'), RouteLevel):
            data['routing_tier'] = data['routing_tier'].value
        if data.get('extracted_intent') and isinstance(data['extracted_intent'], IntentAnalysis):
            intent_data = data['extracted_intent']
            if isinstance(intent_data.get('route_level'), RouteLevel):
                intent_data['route_level'] = intent_data['route_level'].value
        return data


class CheckpointData(BaseModel):
    """检查点数据模型

    用于保存任务状态快照，支持任务恢复和断点续传。
    """
    checkpoint_id: str           # 检查点 ID
    state_name: TaskState         # 状态名称
    context: Dict[str, Any]      # 上下文数据
    timestamp: datetime           # 时间戳

    class Config:
        use_enum_values = True


class ExecutionResult(BaseModel):
    """执行结果模型

    表示任务执行的结果，包含状态、结果内容和可选的错误信息。
    """
    trace_id: str                           # 追踪 ID
    status: str                            # 执行状态
    result: Optional[str] = None           # 执行结果
    error: Optional[str] = None            # 错误信息
    steps: Optional[List[Dict[str, Any]]] = None  # 执行步骤详情


class BaseProfile(BaseModel):
    """画像基类

    所有画像类的基类，提供统一的配置：
    - extra='forbid': 禁止额外字段，确保数据结构严格符合定义
    - frozen=True: 锁定属性，防止运行时篡改，提高性能和数据一致性
    """
    model_config = ConfigDict(extra='forbid', frozen=True)


class TaskPhysicalProfile(BaseProfile):
    """任务物理特征画像

    描述任务的物理特征指纹，决定"它看起来多重"。
    这些特征在任务分析完成后不再变化，因此使用 frozen=True。
    """
    size: int = Field(..., description="原始输入字符长度")
    entropy: float = Field(
        0.0, 
        ge=0, le=1, 
        description="信息熵/压缩比，反映文本信息密度。0.0 表示高度重复/低信息，1.0 表示信息密度极高"
    )
    term_density: float = Field(
        0.0, 
        ge=0, le=1, 
        description="术语/罕见词密度，反映领域深度。0.0 表示无专业术语，1.0 表示高度专业"
    )
    structural_variance: float = Field(
        0.0, 
        ge=0, le=1, 
        description="语义方差，反映表述的不确定性。0.0 表示表述清晰确定，1.0 表示高度模糊"
    )


class TaskBusinessProfile(BaseProfile):
    """任务业务特征画像

    描述任务的业务/社会特征，决定"它有多贵/多险"。
    """
    coreness: float = Field(
        0.0, 
        ge=0, le=1, 
        description="与核心代码或资产的关联度。0.0 表示无关联，1.0 表示直接涉及核心资产"
    )
    risk_score: float = Field(
        0.0, 
        ge=0, le=1, 
        description="操作风险分值，反映失败后果的严重性。0.0 表示无风险，1.0 表示高危操作"
    )
    sla_priority: float = Field(
        0.0, 
        ge=0, le=1, 
        description="质量门槛要求，Nature 级任务此项必高。0.0 表示低要求，1.0 表示最高要求"
    )
    temporal_criticality: bool = Field(
        False, 
        description="是否具有极强的实时性要求"
    )


class TaskCognitiveProfile(BaseProfile):
    """任务认知特征画像

    描述任务的认知特征，决定"它需要什么样的执行策略"。
    """
    innovation_requirement: float = Field(
        0.0, 
        ge=0, le=1, 
        description="发散性/创意需求程度。0.0 表示常规任务，1.0 表示高度创新需求"
    )
    dependency_gap: float = Field(
        0.0, 
        ge=0, le=1, 
        description="上下文缺失度，反映是否需要额外追问。0.0 表示信息完整，1.0 表示严重缺失"
    )
    is_closed_loop: bool = Field(
        True, 
        description="是否为确定性的闭环执行任务。True 表示有明确答案，False 表示开放式探索"
    )
    is_fast_pass: bool = Field(
        False,
        description="是否为快速通道任务。True 表示可直接通过极速分诊，无需深度分析"
    )


class TaskProfile(BaseModel):
    """任务完整画像集成

    任务的三维画像整合，包含物理、业务、认知三个维度。
    画像应该是纯净的、可序列化的 JSON 对象，方便存入数据库或日志进行审计。
    """
    physical: TaskPhysicalProfile
    business: TaskBusinessProfile
    cognitive: TaskCognitiveProfile
    
    # 辅助元数据
    trace_id: str
    timestamp: float

    model_config = ConfigDict(extra='forbid')
