# src/core/task_router.py
# 多维路由矩阵 - TaskRouter（架构师最终版）
# 依赖：numpy, pydantic, typing, logging
# 核心特性：
#   - 基于原型向量匹配算法
#   - 声明式规约表驱动硬约束机制
#   - 加权欧几里得距离计算
#   - 透明化调试日志

from typing import Dict, Any, Tuple, Callable, List
from dataclasses import dataclass
import numpy as np
import logging

from src.config import config
from src.data.domain_models import TaskProfile, RoutingLevel

# 配置日志
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)


@dataclass
class GuardRule:
    """硬约束规则定义
    
    采用声明式规约模式，将"判断条件（谓词）"和"路由结果"解耦，
    使路由逻辑更易于扩展和维护。
    """
    name: str
    # 谓词函数：接收 TaskProfile，返回 bool 表示是否命中
    predicate: Callable[[TaskProfile], bool]
    target_level: RoutingLevel
    reason: str


# 硬约束规则清单（声明式规则表）
# 规则按优先级从高到低排列，命中即返回
# 原则：同一级别的多个触发条件使用 OR 合并，避免逻辑重复
HARD_GATES: List[GuardRule] = [
    # --- P0: 极速分诊层 (L1) ---
    GuardRule(
        name="FastPass_Gate",
        predicate=lambda p: (
            getattr(p.cognitive, 'is_fast_pass', False) and
            getattr(p.business, 'risk_score', 0.0) < config.FAST_PASS_RISK_LIMIT
        ),
        target_level=RoutingLevel.L1_LOCAL_FAST,
        reason="[L1] 快速通道：属于高频简单指令且风险可控"
    ),

    # --- P1: 安全与风险熔断层 (L6) ---
    # 合并 ExtremeRisk 和 Safety 逻辑，通过 config 内部控制阈值
    GuardRule(
        name="Security_Critical_Gate",
        predicate=lambda p: (
            getattr(p.business, 'risk_score', 0.0) > config.HIGH_RISK_GATE and
            getattr(p.business, 'coreness', 0.0) > config.HIGH_CORENESS_GATE
        ),
        target_level=RoutingLevel.L6_CREATIVE_REVIEW,
        reason="[L6] 安全熔断：触碰高危核心资产，强制评审"
    ),

    # --- P2: 深度保障与合规层 (L5) ---
    # 组合 Nature 逻辑与法律/金融 SLA 逻辑
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

    # --- P3: 复杂度与方差层 (L4) ---
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

    # --- P4: 思考感知层 (L3) ---
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


class TaskRouter:
    """多维任务路由器

    基于物理、业务、认知特征的向量匹配路由算法，
    配合硬约束门限机制，确保任务精准分配到对应处理策略。
    """

    def __init__(self):
        """初始化路由器"""
        self.centroids = config.ROUTE_PROTOTYPES
        self.weights = np.array(config.ROUTE_WEIGHTS_VEC)
        logger.info("[TaskRouter] 路由系统初始化完成")

    def route(self, profile: TaskProfile) -> Dict[str, Any]:
        """执行路由决策

        算法流程：
        1. 提取任务画像多维特征向量
        2. 计算与 7 个原型的加权欧几里得距离
        3. 选择距离最短的级别作为初始匹配结果
        4. 应用声明式硬约束规则（遍历规则表，第一个命中即返回）
        5. 应用级别增益（波动率补偿，仅 L4+ 生效）
        6. 返回路由结果与调试信息

        Args:
            profile: 完整任务画像对象

        Returns:
            Dict: 路由结果，包含：
                - level: 路由级别 (RoutingLevel)
                - route_name: 路由名称
                - distance_map: 与各原型的距离分布
                - score_details: 原始特征得分
                - trigger_rule: 触发的规则名称
        """
        # 1. 提取特征向量
        V_task, score_details = self._extract_task_vector(profile)

        # 2. 计算与所有原型的加权距离
        distance_map = self._compute_weighted_distances(V_task)

        # 3. 选择最近距离的级别作为初始匹配
        initial_level_num = min(distance_map, key=distance_map.get)
        initial_level = RoutingLevel(initial_level_num)

        logger.debug(f"[Router] 初始向量匹配级别: {initial_level.name}")
        logger.debug(f"[Router] 距离分布: {distance_map}")

        # 4. 应用声明式硬约束规则表
        constrained_level, trigger_rule = self._apply_hard_constraints(initial_level, profile)

        # 5. 应用级别增益（波动率补偿）
        final_level = self._apply_level_bonus(constrained_level, profile)

        # 6. 确保级别不会越界
        final_level = self._clamp_level(final_level)

        # 7. 构建返回结果
        route_name = config.ROUTE_LEVEL_NAMES[final_level.value]

        result = {
            "level": final_level,
            "level_num": final_level.value,
            "route_name": route_name,
            "initial_level": initial_level,
            "trigger_rule": trigger_rule,
            "distance_map": distance_map,
            "score_details": score_details
        }

        # 审计日志
        self._log_audit_info(initial_level, final_level, trigger_rule, distance_map, score_details)

        return result

    def _extract_task_vector(self, profile: TaskProfile) -> Tuple[np.ndarray, Dict[str, Any]]:
        """提取任务的特征向量

        从多维画像中提取关键特征，构建用于匹配的四维向量：
        [熵, 术语密度, 核心度, 风险]

        Args:
            profile: 完整任务画像

        Returns:
            Tuple: (特征向量 numpy 数组, 原始特征字典)
        """
        # 安全提取特征（带默认值）
        entropy = getattr(profile.physical, 'entropy', 0.3)
        term_density = getattr(profile.physical, 'term_density', 0.2)
        coreness = getattr(profile.business, 'coreness', 0.2)
        risk_score = getattr(profile.business, 'risk_score', 0.2)

        # 构建向量
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

    def _apply_hard_constraints(self, initial_level: RoutingLevel, profile: TaskProfile) -> Tuple[RoutingLevel, str]:
        """应用硬约束门限机制（声明式规则表驱动）

        遍历硬约束规则清单，第一个命中的规则即为最终结果。
        硬约束优先级高于向量匹配结果，确保系统安全。

        Args:
            initial_level: 初始匹配的级别
            profile: 任务画像

        Returns:
            Tuple[RoutingLevel, str]: (最终约束后的级别, 触发的规则名称)
        """
        # 遍历硬约束规则清单（按优先级顺序）
        for rule in HARD_GATES:
            if rule.predicate(profile):
                logger.info(f"✅ [HardGate] {rule.name} 触发: {rule.reason}")
                return rule.target_level, rule.name

        # 如果硬门槛全都没中，返回初始匹配级别
        logger.debug("ℹ️ [Router] 未命中硬门槛，保持向量匹配结果")
        return initial_level, "Vector_Match"

    def _apply_level_bonus(self, level: RoutingLevel, profile: TaskProfile) -> RoutingLevel:
        """应用级别增益（仅对高阶任务生效）

        语义方差作为偏置，仅在基础分已达 L4 时才允许 +1 级。

        Args:
            level: 当前级别
            profile: 任务画像

        Returns:
            RoutingLevel: 增益后的级别
        """
        structural_variance = getattr(profile.physical, 'structural_variance', 0.0)

        # 波动率补偿：仅当级别 >= L4 时才生效
        if structural_variance > config.HIGH_VARIANCE_GATE and level.value >= RoutingLevel.L4_COMPLEX_EXECUTION.value:
            new_level = min(RoutingLevel.L7_PEAK_GAME.value, level.value + 1)
            if new_level > level.value:
                logger.info(f"[Router] 波动率补偿：级别提升 +1 ({level.name} → {RoutingLevel(new_level).name})")
                return RoutingLevel(new_level)

        return level

    def _clamp_level(self, level: RoutingLevel) -> RoutingLevel:
        """钳制级别到 [1, 7] 范围

        Args:
            level: 输入级别

        Returns:
            RoutingLevel: 安全范围内的级别
        """
        value = level.value
        value = max(1, min(7, value))
        return RoutingLevel(value)

    def _log_audit_info(self, initial_level: RoutingLevel, final_level: RoutingLevel,
                        trigger_rule: str, distance_map: Dict[int, float], score_details: Dict[str, Any]):
        """记录路由决策审计信息

        Args:
            initial_level: 初始匹配级别
            final_level: 最终路由级别
            trigger_rule: 触发的规则名称
            distance_map: 距离分布
            score_details: 特征详情
        """
        route_name = config.ROUTE_LEVEL_NAMES[final_level.value]

        if initial_level != final_level:
            logger.info(f"[Router] 级别修正: {initial_level.name} → {final_level.name} (触发规则: {trigger_rule})")
        else:
            logger.info(f"[Router] 路由确定: {final_level.name} ({route_name}) (触发规则: {trigger_rule})")

        logger.debug(f"[Router] 距离详情: {distance_map}")
        logger.debug(f"[Router] 特征详情: {score_details}")
