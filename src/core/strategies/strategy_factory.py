# src/core/strategies/strategy_factory.py
# 策略工厂
# 依赖：typing, src.data.domain_models, src.core.strategies
# 注意事项：
#   - 基于任务的路由级别选择合适的推理策略
#   - 高级任务使用四步裁判策略
#   - 中级任务使用 ReAct 循环策略
#   - 低级任务使用简单融合策略

from typing import Dict, Any

from src.data.domain_models import AgentTask, RouteLevel
from src.core.strategies import (
    FourStepJudgeStrategy,
    SimpleFusionStrategy,
    ReactLoopStrategy,
    PlanAndSolveStrategy,
    ReflexionStrategy
)


class StrategyFactory:
    """策略工厂

    负责根据任务的路由级别选择合适的推理策略。
    不同级别的任务需要不同复杂度的推理策略。
    """

    def get_strategy(self, task: AgentTask):
        """根据任务选择策略

        基于任务的路由级别选择合适的推理策略。

        Args:
            task: 智能体任务对象

        Returns:
            ReasoningStrategy: 选择的推理策略

        Raises:
            Exception: 策略选择失败时抛出
        """
        # 基于路由级别选择策略
        if task.routing_tier:
            if task.routing_tier.value >= 5:
                # 高级任务使用四步裁判策略
                return FourStepJudgeStrategy()
            elif task.routing_tier.value >= 3:
                # 中级任务使用 ReAct 循环策略
                return ReactLoopStrategy()
            else:
                # 低级任务使用简单融合策略
                return SimpleFusionStrategy()
        else:
            # 默认使用简单融合策略
            return SimpleFusionStrategy()
