# src/core/intent_analyzer.py
# 意图量化与七级路由矩阵
# 依赖：typing, re, numpy
# 注意事项：
#   - 基于三个维度（价值、复杂度、创新度）计算路由级别
#   - 路由级别从 L1（本地吞吐）到 L7（巅峰博弈）
#   - 支持中文和英文关键词识别
#   - 业务画像基于知识图谱的实体核心度评估
#   - 认知画像识别任务的收敛/发散特性
#   - 阻尼决策：从 Sum 改为 Max，普通任务稳在 L2/L3

from typing import Dict, Tuple, Any, Optional, List
import re
import numpy as np
import asyncio
import logging

from src.config import config
from src.data.domain_models import TaskBusinessProfile, TaskCognitiveProfile, TaskProfile

# 配置日志
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)


class IntentAnalyzer:
    """意图分析器

    负责分析任务意图并计算路由级别，基于价值、复杂度和创新度三个维度。
    同时支持业务画像和认知画像的生成。
    """

    # 预编译的正则表达式
    # 使用非单词边界匹配，支持中英文混合文本
    ACTION_REGEX = re.compile(r'(?:^|[\s\W])(' + '|'.join(
        list(config.HIGH_RISK_ACTIONS.keys()) +
        list(config.MEDIUM_RISK_ACTIONS.keys()) +
        list(config.LOW_RISK_ACTIONS.keys())
    ) + r')(?:$|[\s\W])', re.IGNORECASE)

    HIGH_QUALITY_REGEX = re.compile(r'(?:^|[\s\W])(' + '|'.join(config.HIGH_QUALITY_TERMS) + r')(?:$|[\s\W])', re.IGNORECASE)

    @staticmethod
    def analyze_intent(task: str, semantic_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析任务意图并计算路由级别

        Args:
            task: 任务描述
            semantic_data: 从 TaskAnalyzer 提取的语义数据

        Returns:
            Dict: 包含意图分析结果的字典，包括：
                - value: 价值分数 (1-10)
                - complexity: 复杂度分数 (1-10)
                - innovation: 创新度分数 (1-5)
                - route_level: 路由级别 (1-7)
                - route_name: 路由级别名称

        Raises:
            Exception: 分析过程中出现错误时抛出
        """
        # 计算三个维度的分数
        value = IntentAnalyzer._calculate_value(task)
        complexity = IntentAnalyzer._calculate_complexity(task, semantic_data)
        innovation = IntentAnalyzer._calculate_innovation(task, semantic_data)

        # 确定路由级别
        route_level = IntentAnalyzer._determine_route_level(value, complexity, innovation)

        return {
            "value": value,
            "complexity": complexity,
            "innovation": innovation,
            "route_level": route_level,
            "route_name": IntentAnalyzer._get_route_name(route_level)
        }

    @staticmethod
    def _calculate_value(task: str) -> int:
        """计算价值/重要性分数 [1-10]

        Args:
            task: 任务描述

        Returns:
            int: 价值分数 (1-10)
        """
        # 高价值关键词
        high_value_keywords = [
            "重要", "紧急", "关键", "核心", "重要性", "价值", "商业", "业务", "收入",
            "important", "urgent", "critical", "core", "value", "business", "revenue"
        ]

        # 中价值关键词
        medium_value_keywords = [
            "分析", "研究", "评估", "建议", "方案", "策略",
            "analyze", "research", "evaluate", "recommend", "plan", "strategy"
        ]

        # 低价值关键词
        low_value_keywords = [
            "查询", "简单", "快速", "基础", "日常",
            "query", "simple", "quick", "basic", "routine"
        ]

        score = 5  # 基础分

        # 增加高价值关键词分数
        for keyword in high_value_keywords:
            if keyword in task.lower():
                score += 2

        # 增加中价值关键词分数
        for keyword in medium_value_keywords:
            if keyword in task.lower():
                score += 1

        # 降低低价值关键词分数
        for keyword in low_value_keywords:
            if keyword in task.lower():
                score -= 1

        # 确保分数在 1-10 范围内
        return max(1, min(10, score))

    @staticmethod
    def _calculate_complexity(task: str, semantic_data: Dict[str, Any] = None) -> int:
        """计算复杂程度分数 [1-10]

        Args:
            task: 任务描述
            semantic_data: 语义数据（可选）

        Returns:
            int: 复杂度分数 (1-10)
        """
        # 高复杂度关键词
        high_complexity_keywords = [
            "复杂", "困难", "挑战", "多步骤", "多阶段", "集成", "系统", "架构",
            "complex", "difficult", "challenge", "multi-step", "system", "architecture"
        ]

        # 中复杂度关键词
        medium_complexity_keywords = [
            "代码", "编程", "开发", "算法", "数学", "逻辑", "推理",
            "code", "program", "develop", "algorithm", "math", "logic", "reasoning"
        ]

        # 低复杂度关键词
        low_complexity_keywords = [
            "简单", "快速", "基础", "直接", "查询", "信息",
            "simple", "quick", "basic", "direct", "query", "information"
        ]

        score = 5  # 基础分

        # 增加高复杂度关键词分数
        for keyword in high_complexity_keywords:
            if keyword in task.lower():
                score += 2

        # 增加中复杂度关键词分数
        for keyword in medium_complexity_keywords:
            if keyword in task.lower():
                score += 1

        # 降低低复杂度关键词分数
        for keyword in low_complexity_keywords:
            if keyword in task.lower():
                score -= 1

        # 检查任务长度（长度越长，复杂度可能越高）
        if len(task) > 500:
            score += 1
        elif len(task) > 1000:
            score += 2

        # 根据语义数据调整复杂度分数
        if semantic_data:
            # 语义方差越大，复杂度可能越高
            semantic_variance = semantic_data.get("semantic_variance", 0.0)
            if semantic_variance > 0.1:
                score += 1
            elif semantic_variance > 0.2:
                score += 2

        # 确保分数在 1-10 范围内
        return max(1, min(10, score))

    @staticmethod
    def _calculate_innovation(task: str, semantic_data: Dict[str, Any] = None) -> int:
        """计算创新程度分数 [1-5]

        Args:
            task: 任务描述
            semantic_data: 语义数据（可选）

        Returns:
            int: 创新度分数 (1-5)
        """
        # 高创新关键词
        high_innovation_keywords = [
            "创新", "创意", "新", "独特", "原创", "发明", "设计",
            "innovative", "creative", "new", "unique", "original", "invent", "design"
        ]

        # 中创新关键词
        medium_innovation_keywords = [
            "改进", "优化", "提升", "增强",
            "improve", "optimize", "enhance", "upgrade"
        ]

        score = 3  # 基础分

        # 增加高创新关键词分数
        for keyword in high_innovation_keywords:
            if keyword in task.lower():
                score += 1

        # 增加中创新关键词分数
        for keyword in medium_innovation_keywords:
            if keyword in task.lower():
                score += 0.5

        # 根据语义数据调整创新分数
        if semantic_data:
            # 语义方差越大，创新度可能越高
            semantic_variance = semantic_data.get("semantic_variance", 0.0)
            if semantic_variance > 0.1:
                score += 0.5
            elif semantic_variance > 0.2:
                score += 1

        # 确保分数在 1-5 范围内
        return max(1, min(5, int(score)))

    @staticmethod
    def _determine_route_level(value: int, complexity: int, innovation: int) -> int:
        """根据分数确定路由级别

        Args:
            value: 价值分数 (1-10)
            complexity: 复杂度分数 (1-10)
            innovation: 创新度分数 (1-5)

        Returns:
            int: 路由级别 (1-7)
        """
        # L7（巅峰博弈): V>8, C>6, I>3
        if value > 8 and complexity > 6 and innovation > 3:
            return 7
        # L6（创意融合): V>8, C<=6, I>3
        elif value > 8 and complexity <= 6 and innovation > 3:
            return 6
        # L5（逻辑深钻): V>8, C>6, I<=3
        elif value > 8 and complexity > 6 and innovation <= 3:
            return 5
        # L4（复杂执行): V<=8, C>6
        elif value <= 8 and complexity > 6:
            return 4
        # L3（高价单发): V>8, C<=5, I<=3
        elif value > 8 and complexity <= 5 and innovation <= 3:
            return 3
        # L2（标准代理): V<=8, C<=5, I<=3
        elif value <= 8 and complexity <= 5 and innovation <= 3:
            return 2
        # L1（本地吞吐): V<4, C<3
        elif value < 4 and complexity < 3:
            return 1
        # 默认到 L2
        else:
            return 2

    @staticmethod
    def _get_route_name(route_level: int) -> str:
        """获取路由级别名称

        Args:
            route_level: 路由级别 (1-7)

        Returns:
            str: 路由级别中文名称
        """
        return config.ROUTE_LEVEL_NAMES.get(route_level, "标准代理")

    # ==================== 业务画像相关方法 ====================

    @staticmethod
    async def generate_business_profile(task: str, memory) -> TaskBusinessProfile:
        """生成业务特征画像

        根据任务中的实体在知识图谱中的连接度计算核心度，
        结合动作动词计算风险分数，以及根据领域关键词计算 SLA 优先级。

        Args:
            task: 任务描述
            memory: 记忆系统实例

        Returns:
            TaskBusinessProfile: 业务画像对象
        """
        # 1. 计算核心度
        coreness = await IntentAnalyzer._calculate_coreness(task, memory)

        # 2. 计算风险分数
        risk_score = IntentAnalyzer._calculate_risk_score(task, coreness)

        # 3. 计算 SLA 优先级
        sla_priority = IntentAnalyzer._calculate_sla_priority(task, coreness)

        # 4. 判断是否具有时间关键性
        temporal_criticality = IntentAnalyzer._detect_temporal_criticality(task)

        return TaskBusinessProfile(
            coreness=coreness,
            risk_score=risk_score,
            sla_priority=sla_priority,
            temporal_criticality=temporal_criticality
        )

    @staticmethod
    async def _calculate_coreness(task: str, memory) -> float:
        """计算核心度

        通过知识图谱中实体的 Degree（连接数）来评估任务与核心资产的关联度。

        Args:
            task: 任务描述
            memory: 记忆系统实例

        Returns:
            float: 核心度分数 (0.0-1.0)
        """
        # 提取任务中的实体
        entities = memory._extract_entities_from_text(task)

        if not entities:
            # 没有提取到实体，返回基础核心度
            return 0.1

        graph = memory.knowledge_graph
        max_degree = 0

        # 批量查询实体的连接度
        for entity in entities:
            entity_name = entity["name"]
            if entity_name in graph:
                # 获取该实体在图中的连接度（入度+出度）
                degree = graph.degree(entity_name)
                max_degree = max(max_degree, degree)

        # 归一化：假设连接数超过 CORENESS_MAX_DEGREE 即为极其核心
        coreness = min(1.0, max_degree / config.CORENESS_MAX_DEGREE)

        return coreness

    @staticmethod
    def _calculate_risk_score(task: str, coreness: float) -> float:
        """计算风险分数

        风险 = 动作权重 * (1 + 核心度)

        Args:
            task: 任务描述
            coreness: 核心度分数

        Returns:
            float: 风险分数 (0.0-1.0)
        """
        # 获取动作权重
        action_weight = IntentAnalyzer._get_action_weight(task)

        # 风险计算：基础风险 * (1 + 核心度)
        # 核心度越高，相同动作的风险越大
        risk_score = action_weight * (1.0 + coreness)

        # 归一化到 [0.0, 1.0]
        return min(1.0, max(0.0, risk_score))

    @staticmethod
    def _get_action_weight(task: str) -> float:
        """获取动作动词的权重

        根据配置中的高危、中危、低危动作词匹配任务中的动作。

        Args:
            task: 任务描述

        Returns:
            float: 动作权重 (0.0-1.0)
        """
        task_lower = task.lower()
        max_weight = 0.0

        # 检查高危动作
        for action, weight in config.HIGH_RISK_ACTIONS.items():
            if action in task_lower:
                max_weight = max(max_weight, weight)

        # 检查中危动作
        for action, weight in config.MEDIUM_RISK_ACTIONS.items():
            if action in task_lower:
                max_weight = max(max_weight, weight)

        # 检查低危动作
        for action, weight in config.LOW_RISK_ACTIONS.items():
            if action in task_lower:
                max_weight = max(max_weight, weight)

        return max_weight

    @staticmethod
    def _calculate_sla_priority(task: str, coreness: float) -> float:
        """计算 SLA 优先级（质量门槛）

        结合文本特征（如 Nature 关键词）和核心度，综合给出质量要求分。

        Args:
            task: 任务描述
            coreness: 核心度分数

        Returns:
            float: SLA 优先级 (0.0-1.0)
        """
        base_score = 0.3  # 基础分

        # 检查高质量领域关键词（使用简单的字符串包含检查，支持中英文混合）
        task_lower = task.lower()
        has_high_quality_term = any(term.lower() in task_lower for term in config.HIGH_QUALITY_TERMS)
        if has_high_quality_term:
            base_score += 0.5

        # 核心度加成
        base_score += coreness * 0.2

        # 归一化到 [0.0, 1.0]
        return min(1.0, max(0.0, base_score))

    @staticmethod
    def _detect_temporal_criticality(task: str) -> bool:
        """检测任务是否具有时间关键性

        Args:
            task: 任务描述

        Returns:
            bool: 是否具有时间关键性
        """
        temporal_keywords = [
            "立即", "马上", "立刻", "紧急", "尽快", "限时", "deadline",
            "urgent", "immediately", "now", "as soon as possible", "within"
        ]

        task_lower = task.lower()
        return any(keyword in task_lower for keyword in temporal_keywords)

    # ==================== 认知画像相关方法 ====================

    @staticmethod
    async def generate_cognitive_profile(task: str, memory) -> TaskCognitiveProfile:
        """生成认知特征画像

        判断任务是收敛型执行还是发散型创意，并识别隐性依赖缺口。

        Args:
            task: 任务描述
            memory: 记忆系统实例（用于依赖分析）

        Returns:
            TaskCognitiveProfile: 认知画像对象
        """
        # 1. 判断创新需求（发散性程度）
        innovation_requirement = IntentAnalyzer._calculate_innovation_requirement(task)

        # 2. 计算依赖缺口
        dependency_gap = await IntentAnalyzer._calculate_dependency_gap(task, memory)

        # 3. 判断是否为闭环任务
        is_closed_loop = IntentAnalyzer._detect_closed_loop(task)

        return TaskCognitiveProfile(
            innovation_requirement=innovation_requirement,
            dependency_gap=dependency_gap,
            is_closed_loop=is_closed_loop
        )

    @staticmethod
    def _calculate_innovation_requirement(task: str) -> float:
        """计算创新需求程度

        判断任务需要多大程度的发散性思维。

        Args:
            task: 任务描述

        Returns:
            float: 创新需求程度 (0.0-1.0)
        """
        # 发散型关键词（需要创意）
        divergent_keywords = [
            "创意", "创新", "设计", "发明", "创造", "想象", "构思",
            "creative", "innovative", "design", "invent", "create", "imagine", "brainstorm"
        ]

        # 收敛型关键词（有明确答案）
        convergent_keywords = [
            "查询", "查找", "计算", "分析", "验证", "确认", "执行",
            "query", "find", "calculate", "analyze", "verify", "confirm", "execute"
        ]

        task_lower = task.lower()
        divergent_count = sum(1 for kw in divergent_keywords if kw in task_lower)
        convergent_count = sum(1 for kw in convergent_keywords if kw in task_lower)

        total = divergent_count + convergent_count
        if total == 0:
            # 默认中等创新需求
            return 0.3

        # 发散型关键词越多，创新需求越高
        return min(1.0, divergent_count / total)

    @staticmethod
    async def _calculate_dependency_gap(task: str, memory) -> float:
        """计算依赖缺口

        评估任务所需信息与当前知识库中可用信息的差距。

        Args:
            task: 任务描述
            memory: 记忆系统实例

        Returns:
            float: 依赖缺口 (0.0-1.0)，0.0 表示信息完整，1.0 表示严重缺失
        """
        # 提取任务中的实体
        entities = memory._extract_entities_from_text(task)

        if not entities:
            # 无法提取实体，依赖缺口较高
            return 0.7

        graph = memory.knowledge_graph
        unknown_entity_count = 0

        # 检查实体在知识图谱中的存在情况
        for entity in entities:
            entity_name = entity["name"]
            if entity_name not in graph:
                unknown_entity_count += 1

        # 计算未知实体比例作为依赖缺口
        dependency_gap = unknown_entity_count / len(entities)

        # 检查是否存在疑问词（表示需要更多信息）
        question_keywords = ["什么", "如何", "为什么", "哪里", "谁", "何时",
                             "what", "how", "why", "where", "who", "when"]
        task_lower = task.lower()
        has_question = any(kw in task_lower for kw in question_keywords)

        if has_question:
            # 有疑问词增加依赖缺口
            dependency_gap = min(1.0, dependency_gap + 0.2)

        return dependency_gap

    @staticmethod
    def _detect_closed_loop(task: str) -> bool:
        """检测任务是否为闭环执行

        闭环任务：有明确的输入输出，结果可以验证
        开环任务：开放式探索，没有明确答案

        Args:
            task: 任务描述

        Returns:
            bool: True 表示闭环任务，False 表示开环任务
        """
        # 闭环指示词
        closed_loop_keywords = [
            "编写", "实现", "执行", "计算", "验证", "测试", "完成",
            "write", "implement", "execute", "calculate", "verify", "test", "complete"
        ]

        # 开环指示词
        open_loop_keywords = [
            "讨论", "探索", "分析", "研究", "思考", "建议", "创意",
            "discuss", "explore", "analyze", "research", "think", "suggest", "creative"
        ]

        task_lower = task.lower()
        closed_count = sum(1 for kw in closed_loop_keywords if kw in task_lower)
        open_count = sum(1 for kw in open_loop_keywords if kw in task_lower)

        # 如果闭环词更多，则认为是闭环任务
        return closed_count >= open_count

    # ==================== 路由决策相关方法 ====================

    @staticmethod
    def determine_route_level(profile: TaskProfile) -> Dict[str, Any]:
        """基于多维画像的阻尼决策矩阵

        决策逻辑（架构师规范 - 阻尼决策）：
        1. 基础级别设为 L2
        2. 质量提级（基于 Max 触发，非累加）：
           - 高质量门槛: entropy>0.8 或 term_density>0.7 → max(level,5)
           - 中等质量: max(entropy, term_density)>0.5 → max(level,3)
        3. 风险提级（风险必须结合核心度）：
           - 高风险 + 高核心度: risk_score>0.8 且 coreness>0.6 → max(level,6)
           - 中等风险: risk_score>0.5 → max(level,4)
        4. 不确定性补偿（仅作为高阶任务微调）：
           - structural_variance>0.5 且 level>=4 → level+1（最高 L7）
        5. 快速通道（最高优先级拦截）：
           - is_fast_pass 且 risk_score<0.2 → L1

        Args:
            profile: 任务完整画像（包含物理、业务、认知三个维度）

        Returns:
            Dict: 路由决策结果，包含：
                - level: 路由级别 (1-7)
                - route_name: 路由级别名称
                - triggers: 触发的补偿规则列表
                - score_details: 决策审计信息
        """
        # 1. 确立基准
        level = 2
        triggers = []
        score_details = {}

        try:
            # 提取各项指标（带默认值处理）
            entropy = getattr(profile.physical, 'entropy', 0.0)
            term_density = getattr(profile.physical, 'term_density', 0.0)
            structural_variance = getattr(profile.physical, 'structural_variance', 0.0)
            risk_score = getattr(profile.business, 'risk_score', 0.0)
            coreness = getattr(profile.business, 'coreness', 0.0)
            is_fast_pass = getattr(profile.cognitive, 'is_fast_pass', False)

            # 记录原始得分
            score_details["entropy"] = entropy
            score_details["term_density"] = term_density
            score_details["risk_score"] = risk_score
            score_details["coreness"] = coreness
            score_details["structural_variance"] = structural_variance
            score_details["is_fast_pass"] = is_fast_pass

            # 2. 快速通道判定（必须在其他规则之前）
            if is_fast_pass and risk_score < config.FAST_PASS_RISK_LIMIT:
                level = 1
                triggers = ["极速分诊拦截"]
                score_details["gate_triggered"] = "FAST_PASS_GATE"
                logger.info(f"[Decision] 快速通道触发: is_fast_pass={is_fast_pass}, risk_score={risk_score:.2f}")

            else:
                # 3. 质量门槛（针对 Nature 等高质量任务 - 采用 Max 触发，非累加）
                quality_signal = max(entropy, term_density)
                if quality_signal > config.HIGH_QUALITY_GATE:
                    old_level = level
                    level = max(level, 5)
                    reason = f"高质量门槛触发 (quality_signal={quality_signal:.2f})"
                    triggers.append(reason)
                    score_details["gate_triggered"] = "HIGH_QUALITY_GATE"
                    logger.info(f"[Decision] {reason}, 提级到 L{level}")
                elif quality_signal > config.MEDIUM_QUALITY_GATE:
                    old_level = level
                    level = max(level, 3)
                    reason = f"中等质量门槛触发 (quality_signal={quality_signal:.2f})"
                    triggers.append(reason)
                    score_details["gate_triggered"] = "MEDIUM_QUALITY_GATE"
                    logger.info(f"[Decision] {reason}, 提级到 L{level}")

                # 4. 风险门槛（针对核心资产修改 - 风险必须结合核心度才有意义）
                if risk_score > config.HIGH_RISK_GATE and coreness > config.HIGH_CORENESS_GATE:
                    old_level = level
                    level = max(level, 6)
                    reason = f"高风险+高核心度门槛触发 (risk={risk_score:.2f}, coreness={coreness:.2f})"
                    triggers.append(reason)
                    score_details["gate_triggered"] = "HIGH_RISK_GATE"
                    logger.info(f"[Decision] {reason}, 提级到 L{level}")
                elif risk_score > config.MEDIUM_RISK_GATE:
                    old_level = level
                    level = max(level, 4)
                    reason = f"中等风险门槛触发 (risk={risk_score:.2f})"
                    triggers.append(reason)
                    score_details["gate_triggered"] = "MEDIUM_RISK_GATE"
                    logger.info(f"[Decision] {reason}, 提级到 L{level}")

                # 5. 波动率补偿（仅作为高阶任务微调）
                if structural_variance > config.HIGH_VARIANCE_GATE and level >= 4:
                    old_level = level
                    level = min(7, level + 1)
                    reason = f"语义方差补偿触发 (variance={structural_variance:.2f}, 仅 L4+ 生效)"
                    triggers.append(reason)
                    score_details["gate_triggered"] = "VARIANCE_COMPENSATION"
                    logger.info(f"[Decision] {reason}, 从 L{old_level} 提级到 L{level}")

        except AttributeError as e:
            # 画像数据不完整，降级到默认路由 L2
            logger.warning(f"[Decision] 任务画像数据不完整: {e}, 降级到默认路由 L2")
            level = 2
            triggers = ["画像数据不完整，使用默认路由"]
            score_details["gate_triggered"] = "FALLBACK_GATE"

        # 6. 边界限制（确保级别在 [1,7] 范围内）
        level = max(1, min(7, level))

        # 7. 路由名称映射
        route_mapping = config.ROUTE_LEVEL_NAMES
        route_name = route_mapping.get(level, "标准代理")

        # 审计日志
        logger.info(f"[Decision] 任务画像路由完成: Level {level} ({route_name}), 触发规则: {', '.join(triggers)}")
        logger.debug(f"[Decision] 得分详情: {score_details}")

        return {
            "level": level,
            "route_name": route_name,
            "triggers": triggers,
            "score_details": score_details
        }
