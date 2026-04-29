# src/core/task_router.py
# TaskRouter 终极进化版
# 核心特性：
#   - 维度 1：安全拦截（SQL注入检测、隐私数据保护）
#   - 维度 2：决策审计（可解释性、完整报告）
#   - 维度 3：性能监控（耗时追踪、埋点分析）
#   - 维度 4：动态阈值（热配置支持）

from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass
from pydantic import BaseModel
import numpy as np
import logging
import time
import re

from src.config import config
from src.data.domain_models import TaskProfile, RoutingLevel

# 配置日志
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)


# ==================== 安全检测模式 ====================
# SQL 注入专项检测正则
SQL_INJECTION_PATTERN = re.compile(
    r"(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE\s+TABLE|ALTER\s+TABLE|"
    r"UPDATE\s+.*SET|UNION\s+SELECT|OR\s+1=1|--.*|;.*--)",
    re.IGNORECASE
)


# ==================== 决策审计模型 ====================
class RouteDecision(BaseModel):
    """决策审计模型 - 确保每一行路由都有据可查"""
    final_level: RoutingLevel
    source: str                    # "HardGate: Name" 或 "VectorMatch"
    reason: str
    latency_ms: float              # 路由决策耗时（毫秒）
    confidence: float              # 决策置信度（0.0-1.0）
    distance_map: Optional[Dict[str, float]] = None  # 向量距离分布
    score_details: Optional[Dict[str, Any]] = None   # 原始特征得分
    initial_level: Optional[RoutingLevel] = None     # 初始匹配级别


# ==================== 声明式规约规则 ====================
@dataclass
class GuardRule:
    """硬约束规则定义
    
    采用声明式规约模式，将"判断条件（谓词）"和"路由结果"解耦，
    使路由逻辑更易于扩展和维护。
    """
    name: str
    predicate: Callable[[TaskProfile], bool]
    target_level: RoutingLevel
    reason: str


# 硬约束规则清单（声明式规则表）
# 规则按优先级从高到低排列，命中即返回
HARD_GATES: List[GuardRule] = [
    # --- P0: SQL 注入专项拦截 ---
    GuardRule(
        name="Security_SQL_Injection",
        predicate=lambda p: (
            bool(SQL_INJECTION_PATTERN.search(getattr(p, 'raw_query', '') or '')) or
            getattr(p.business, 'risk_score', 0.0) > 0.95
        ),
        target_level=RoutingLevel.L7_PEAK_GAME,
        reason="[P0] 检测到潜在的破坏性 SQL 指令或极端操作风险，转入 L7 巅峰评审"
    ),

    # --- P1: 法律与隐私拦截 ---
    GuardRule(
        name="Privacy_Compliance_Gate",
        predicate=lambda p: getattr(p.business, 'has_privacy_data', False),
        target_level=RoutingLevel.L1_LOCAL_FAST,
        reason="[P1] 检测到敏感隐私数据，强制本地快速处理，不流向公有云模型"
    ),

    # --- P2: 极速分诊层 ---
    GuardRule(
        name="FastPass_Gate",
        predicate=lambda p: (
            getattr(p.cognitive, 'is_fast_pass', False) and
            getattr(p.business, 'risk_score', 0.0) < config.FAST_PASS_RISK_LIMIT
        ),
        target_level=RoutingLevel.L1_LOCAL_FAST,
        reason="[L1] 快速通道：属于高频简单指令且风险可控"
    ),

    # --- P3: 安全与风险熔断层 (L6) ---
    GuardRule(
        name="Security_Critical_Gate",
        predicate=lambda p: (
            getattr(p.business, 'risk_score', 0.0) > config.HIGH_RISK_GATE and
            getattr(p.business, 'coreness', 0.0) > config.HIGH_CORENESS_GATE
        ),
        target_level=RoutingLevel.L6_CREATIVE_REVIEW,
        reason="[L6] 安全熔断：触碰高危核心资产，强制评审"
    ),

    # --- P4: 深度保障与合规层 (L5) ---
    GuardRule(
        name="Expert_Quality_Gate",
        predicate=lambda p: (
            (getattr(p.physical, 'entropy', 0.0) > config.HIGH_QUALITY_GATE and
             getattr(p.physical, 'term_density', 0.0) >= config.HIGH_QUALITY_GATE) or
            getattr(p.business, 'sla_priority', 0.0) > config.HIGH_SLA_THRESHOLD
        ),
        target_level=RoutingLevel.L5_LOGIC_DEEP_DIVE,
        reason="[L5] 专家保障：涉及学术论文、专业文档或高SLA法律金融任务"
    ),

    # --- P5: 复杂度与方差层 (L4) ---
    GuardRule(
        name="Complex_Logical_Gate",
        predicate=lambda p: (
            getattr(p.business, 'risk_score', 0.0) > config.MEDIUM_RISK_GATE or
            getattr(p.physical, 'structural_variance', 0.0) > config.HIGH_VARIANCE_GATE or
            getattr(p.cognitive, 'dependency_gap', 0.0) > config.HIGH_GAP_THRESHOLD
        ),
        target_level=RoutingLevel.L4_COMPLEX_EXECUTION,
        reason="[L4] 复杂分发：检测到中等风险、高语义方差或上下文缺口"
    ),

    # --- P6: 思考感知层 (L3) ---
    GuardRule(
        name="Mindful_Response_Gate",
        predicate=lambda p: (
            max(getattr(p.physical, 'entropy', 0.0),
                getattr(p.physical, 'term_density', 0.0)) > config.MEDIUM_QUALITY_GATE
        ),
        target_level=RoutingLevel.L3_THOUGHTFUL_REPLY,
        reason="[L3] 思考启发：文本具备一定信息密度，需模型深思熟虑"
    )
]


# ==================== 任务路由器核心类 ====================
class TaskRouter:
    """多维任务路由器（终极进化版）
    
    基于物理、业务、认知特征的向量匹配路由算法，
    配合硬约束门限机制和安全拦截，确保任务精准分配。
    """

    def __init__(self):
        """初始化路由器"""
        # 维度 4：支持动态加载的阈值
        self.centroids = config.get_route_prototypes()
        self.weights = np.array(config.ROUTE_WEIGHTS_VEC)
        logger.info("[TaskRouter] 路由系统初始化完成 - 终极进化版")

    def route(self, profile: TaskProfile) -> RouteDecision:
        """执行路由决策（同步版本）
        
        算法流程：
        1. 记录开始时间
        2. 执行硬约束拦截（包含 SQL 注入检查）
        3. 执行向量聚类匹配（气质感应）
        4. 构建决策对象并记录审计日志
        
        Args:
            profile: 完整任务画像对象
            
        Returns:
            RouteDecision: 包含完整审计信息的决策对象
        """
        start_time = time.perf_counter()

        # 1. 执行硬约束拦截
        for rule in HARD_GATES:
            if rule.predicate(profile):
                latency = (time.perf_counter() - start_time) * 1000
                decision = RouteDecision(
                    final_level=rule.target_level,
                    source=f"HardGate: {rule.name}",
                    reason=rule.reason,
                    latency_ms=latency,
                    confidence=1.0  # 硬约束置信度为 100%
                )
                self._log_decision(decision)
                return decision

        # 2. 执行向量聚类匹配（气质感应）
        vector_result = self._match_vector(profile)
        latency = (time.perf_counter() - start_time) * 1000

        decision = RouteDecision(
            final_level=vector_result['level'],
            source="VectorMatch",
            reason="[向量匹配] 基于原型向量相似度的气质感应",
            latency_ms=latency,
            confidence=vector_result['confidence'],
            distance_map=vector_result['distance_map'],
            score_details=vector_result['score_details'],
            initial_level=vector_result['level']
        )

        self._log_decision(decision)
        return decision

    def _match_vector(self, profile: TaskProfile) -> Dict[str, Any]:
        """执行向量聚类匹配
        
        计算任务画像向量与各原型的加权欧几里得距离，选择最近的级别。
        
        Args:
            profile: 任务画像
            
        Returns:
            Dict: 包含级别、置信度、距离分布的匹配结果
        """
        # 提取特征向量
        V_task, score_details = self._extract_task_vector(profile)

        # 计算与所有原型的加权距离
        distance_map = self._compute_weighted_distances(V_task)

        # 选择最近距离的级别
        best_level_num = min(distance_map, key=distance_map.get)
        best_level = RoutingLevel(best_level_num)

        # 计算置信度（基于距离归一化）
        min_distance = distance_map[best_level_num]
        max_distance = max(distance_map.values())
        confidence = 1.0 - (min_distance / (max_distance + 1e-9))

        logger.debug(f"[Router] 向量匹配级别: {best_level.name}, 置信度: {confidence:.4f}")
        logger.debug(f"[Router] 距离分布: {distance_map}")

        return {
            "level": best_level,
            "confidence": confidence,
            "distance_map": {str(k): float(v) for k, v in distance_map.items()},
            "score_details": score_details
        }

    def _extract_task_vector(self, profile: TaskProfile) -> Tuple[np.ndarray, Dict[str, Any]]:
        """提取任务的特征向量
        
        从多维画像中提取关键特征，构建用于匹配的四维向量：
        [熵, 术语密度, 核心度, 风险]
        
        Args:
            profile: 完整任务画像
            
        Returns:
            Tuple: (特征向量 numpy 数组, 原始特征字典)
        """
        entropy = getattr(profile.physical, 'entropy', 0.3)
        term_density = getattr(profile.physical, 'term_density', 0.2)
        coreness = getattr(profile.business, 'coreness', 0.2)
        risk_score = getattr(profile.business, 'risk_score', 0.2)

        V_task = np.array([entropy, term_density, coreness, risk_score])

        score_details = {
            "entropy": entropy,
            "term_density": term_density,
            "coreness": coreness,
            "risk_score": risk_score
        }

        logger.debug(f"[Router] 任务向量: {V_task}")
        return V_task, score_details

    def _compute_weighted_distances(self, V_task: np.ndarray) -> Dict[int, float]:
        """计算任务向量与各原型的加权欧几里得距离
        
        使用哈达玛积（Hadamard Product）应用权重：
        V_weighted = V_task * W_mask
        
        Args:
            V_task: 4 维任务特征向量
            
        Returns:
            Dict: 级别到距离的映射
        """
        distance_map = {}

        for level_num, centroid in self.centroids.items():
            V_centroid = np.array(centroid)

            # 计算加权向量（哈达玛积）
            V_task_weighted = V_task * self.weights
            V_centroid_weighted = V_centroid * self.weights

            # 计算加权欧几里得距离
            distance = np.linalg.norm(V_task_weighted - V_centroid_weighted)
            distance_map[level_num] = distance

        return distance_map

    def _log_decision(self, decision: RouteDecision):
        """决策审计日志 - 维度 2：可解释性"""
        route_name = config.ROUTE_LEVEL_NAMES.get(decision.final_level.value, "Unknown")
        
        logger.info(
            f"决策审计 | 最终等级: {decision.final_level.name} ({route_name}) | "
            f"来源: {decision.source} | 耗时: {decision.latency_ms:.2f}ms | "
            f"置信度: {decision.confidence:.4f}"
        )
        
        if decision.reason:
            logger.info(f"决策原因: {decision.reason}")
            
        if decision.source.startswith("Vector") and decision.distance_map:
            logger.debug(f"距离分布: {decision.distance_map}")
            
        if decision.score_details:
            logger.debug(f"特征详情: {decision.score_details}")