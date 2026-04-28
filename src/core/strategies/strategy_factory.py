# src/core/strategies/strategy_factory.py
# 策略工厂
# 依赖：typing, src.data.domain_models, src.core.strategies, src.core.exceptions, src.utils.logger
# 注意事项：
#   - 基于任务的路由级别选择合适的推理策略
#   - 实现了降级机制，当前策略失败时自动尝试降级策略
#   - 高级任务使用四步裁判策略，中级使用 ReAct，低级使用简单融合

from typing import Dict, Any

from src.data.domain_models import AgentTask, RouteLevel
from src.core.strategies import (
    FourStepJudgeStrategy,
    SimpleFusionStrategy,
    ReactLoopStrategy,
    PlanAndSolveStrategy,
    ReflexionStrategy
)
from src.core.exceptions import StrategyFallbackError
from src.utils.logger import logger


class StrategyFactory:
    """策略工厂

    负责根据任务的路由级别选择合适的推理策略，并实现降级机制。
    不同级别的任务需要不同复杂度的推理策略。
    """

    def __init__(self):
        """初始化策略工厂

        定义降级策略链，用于当前策略失败时的降级处理。
        """
        self.fallback_chains = {
            7: [FourStepJudgeStrategy, ReactLoopStrategy, SimpleFusionStrategy],
            6: [FourStepJudgeStrategy, ReactLoopStrategy, SimpleFusionStrategy],
            5: [ReactLoopStrategy, PlanAndSolveStrategy, SimpleFusionStrategy],
            4: [ReactLoopStrategy, SimpleFusionStrategy],
            3: [PlanAndSolveStrategy, SimpleFusionStrategy],
            2: [SimpleFusionStrategy],
            1: [SimpleFusionStrategy]
        }

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
            return self._get_strategy_by_level(task.routing_tier.value)
        else:
            # 默认使用简单融合策略
            return SimpleFusionStrategy()

    def _get_strategy_by_level(self, route_level: int) -> object:
        """根据路由级别获取策略

        Args:
            route_level: 路由级别

        Returns:
            ReasoningStrategy: 选择的推理策略
        """
        # 基于路由级别选择策略
        if route_level >= 5:
            # 高级任务使用四步裁判策略
            return FourStepJudgeStrategy()
        elif route_level >= 3:
            # 中级任务使用 ReAct 循环策略
            return ReactLoopStrategy()
        else:
            # 低级任务使用简单融合策略
            return SimpleFusionStrategy()

    async def execute_with_fallback(self, strategy, messages: list, model_pool: list, trace_id: str, route_level: int):
        """执行策略并处理降级

        当当前策略失败时，自动尝试降级策略链中的下一个策略。

        Args:
            strategy: 当前策略实例
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            route_level: 路由级别

        Returns:
            str: 推理结果

        Raises:
            Exception: 所有策略都失败时抛出
        """
        # 获取降级策略链
        fallback_chain = self.fallback_chains.get(route_level, [SimpleFusionStrategy])
        
        # 获取当前策略的索引位置
        current_class = strategy.__class__
        start_index = 0
        for i, strategy_class in enumerate(fallback_chain):
            if strategy_class == current_class:
                start_index = i
                break
        
        # 从当前策略开始尝试降级链
        for i in range(start_index, len(fallback_chain)):
            strategy_class = fallback_chain[i]
            strategy_instance = strategy_class()
            
            try:
                logger.info(f"[{trace_id}] 尝试策略: {strategy_class.__name__}")
                result = await strategy_instance.execute(messages, model_pool, trace_id)
                logger.info(f"[{trace_id}] 策略 {strategy_class.__name__} 执行成功")
                return result
            except StrategyFallbackError as e:
                logger.warning(f"[{trace_id}] 策略 {strategy_class.__name__} 执行失败，尝试降级: {e}")
                continue
            except Exception as e:
                logger.error(f"[{trace_id}] 策略 {strategy_class.__name__} 执行异常: {e}")
                continue
        
        # 所有策略都失败
        logger.error(f"[{trace_id}] 所有策略都执行失败")
        raise StrategyFallbackError("所有策略都执行失败")
