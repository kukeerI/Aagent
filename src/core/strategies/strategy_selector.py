# src/core/strategies/strategy_selector.py
# 策略选择器：根据路由决策选择执行路径、模型和认知模式
# 依赖：typing, src.config, src.data.domain_models, src.utils.logger
# 注意事项：
#   - 实现策略映射、模型降级、Thinking 开启、本地模型冗余
#   - 包含容错降级逻辑，支持双路热备
#   - L5+ 强制开启思考模式，L4 根据复杂度按需开启

from typing import Dict, Any, Optional, Type
import asyncio
import time

from src.config import config
from src.data.domain_models import RoutingLevel, RouteDecision
from src.core.strategies import (
    ReasoningStrategy,
    SimpleFusionStrategy,
    ReactLoopStrategy,
    ReflexionStrategy,
    PlanAndSolveStrategy,
    FourStepJudgeStrategy
)
from src.utils.logger import logger


class ExecutionPlan:
    """执行计划：包含策略类型、模型配置、思考模式和迭代限制"""
    def __init__(
        self,
        strategy: Type[ReasoningStrategy],
        model_config: Dict[str, Any],
        thinking: bool = False,
        max_iterations: int = 5,
        is_fallback: bool = False
    ):
        self.strategy = strategy
        self.model_config = model_config
        self.thinking = thinking
        self.max_iterations = max_iterations
        self.is_fallback = is_fallback
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.__name__,
            "model": self.model_config,
            "thinking": self.thinking,
            "max_iterations": self.max_iterations,
            "is_fallback": self.is_fallback
        }


class StrategySelector:
    """策略选择器：根据路由决策选择执行路径、模型和认知模式"""

    # 策略类型映射（原子策略）
    STRATEGY_MAP: Dict[RoutingLevel, Type[ReasoningStrategy]] = {
        RoutingLevel.L1_LOCAL_FAST: SimpleFusionStrategy,
        RoutingLevel.L2_STANDARD_PROXY: SimpleFusionStrategy,
        RoutingLevel.L3_THOUGHTFUL_REPLY: SimpleFusionStrategy,
        RoutingLevel.L4_COMPLEX_EXECUTION: ReactLoopStrategy,
        RoutingLevel.L5_LOGIC_DEEP_DIVE: ReflexionStrategy,
        RoutingLevel.L6_CREATIVE_REVIEW: FourStepJudgeStrategy,
        RoutingLevel.L7_PEAK_GAME: PlanAndSolveStrategy
    }

    def __init__(self):
        """初始化策略选择器"""
        self.fallback_strategies = [
            ReflexionStrategy,
            ReactLoopStrategy,
            SimpleFusionStrategy
        ]
        logger.info("[StrategySelector] 策略选择器初始化完成")

    def get_execution_plan(self, decision: RouteDecision) -> ExecutionPlan:
        """获取执行计划
        
        Args:
            decision: 路由决策对象
            
        Returns:
            ExecutionPlan: 执行计划，包含策略、模型、思考模式等配置
        """
        start_time = time.perf_counter()
        level = decision.final_level
        
        # 1. 策略类型决策 (Strategy Choice)
        strategy_type = self._map_to_strategy(level)
        
        # 2. 思考模式判定 (Thinking Mode)
        # L5+ 强制开启，L4 根据复杂度按需开启
        enable_thinking = (level.value >= 5) or \
                         (level == RoutingLevel.L4_COMPLEX_EXECUTION and decision.confidence < 0.8)
        
        # 3. 模型分配与降级逻辑 (Model Allocation & Fallback)
        # 如果触发了隐私或安全 Gate，强制切换为 Fallback 模型
        is_fallback = decision.source.startswith("HardGate: Privacy") or \
                     decision.source.startswith("HardGate: Security")
        
        model_config = config.get_model_config(level, is_fallback=is_fallback)
        
        # 4. 获取最大迭代次数
        max_iterations = self._get_max_iters(level)
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"[StrategySelector] 生成执行计划 | 级别: L{level.value} | "
            f"策略: {strategy_type.__name__} | 思考: {enable_thinking} | "
            f"模型: {model_config.get('name', 'unknown')} | 耗时: {latency_ms:.2f}ms"
        )
        
        return ExecutionPlan(
            strategy=strategy_type,
            model_config=model_config,
            thinking=enable_thinking,
            max_iterations=max_iterations,
            is_fallback=is_fallback
        )

    def _map_to_strategy(self, level: RoutingLevel) -> Type[ReasoningStrategy]:
        """将路由级别映射到策略类型
        
        Args:
            level: 路由级别
            
        Returns:
            Type[ReasoningStrategy]: 策略类
        """
        return self.STRATEGY_MAP.get(level, SimpleFusionStrategy)

    def _get_max_iters(self, level: RoutingLevel) -> int:
        """获取最大迭代次数
        
        Args:
            level: 路由级别
            
        Returns:
            int: 最大迭代次数
        """
        iters_map = {
            RoutingLevel.L1_LOCAL_FAST: 1,
            RoutingLevel.L2_STANDARD_PROXY: 1,
            RoutingLevel.L3_THOUGHTFUL_REPLY: 1,
            RoutingLevel.L4_COMPLEX_EXECUTION: 5,
            RoutingLevel.L5_LOGIC_DEEP_DIVE: 3,
            RoutingLevel.L6_CREATIVE_REVIEW: 4,
            RoutingLevel.L7_PEAK_GAME: 7
        }
        return iters_map.get(level, 3)

    async def execute_with_fallback(
        self,
        plan: ExecutionPlan,
        messages: list,
        model_pool: list,
        trace_id: str
    ) -> str:
        """执行策略并处理降级（容错降级）
        
        如果当前策略失败，自动尝试降级策略链中的下一个策略。
        
        Args:
            plan: 执行计划
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            
        Returns:
            str: 推理结果
            
        Raises:
            Exception: 所有策略都失败时抛出
        """
        # 获取降级策略链
        fallback_chain = self._get_fallback_chain(plan.strategy)
        
        # 从当前策略开始尝试降级链
        for i, strategy_class in enumerate(fallback_chain):
            strategy_instance = strategy_class()
            
            try:
                logger.info(f"[{trace_id}] 尝试策略 [{i+1}/{len(fallback_chain)}]: {strategy_class.__name__}")
                
                # L7 级别使用异步并发执行
                if plan.max_iterations > 5 and i == 0:
                    result = await self._execute_parallel(
                        strategy_instance, messages, model_pool, trace_id, plan.max_iterations
                    )
                else:
                    result = await strategy_instance.execute(messages, model_pool, trace_id)
                
                logger.info(f"[{trace_id}] 策略 {strategy_class.__name__} 执行成功")
                return result
                
            except Exception as e:
                logger.warning(
                    f"[{trace_id}] 策略 {strategy_class.__name__} 执行失败 ({type(e).__name__}): {e}"
                )
                if i < len(fallback_chain) - 1:
                    logger.info(f"[{trace_id}] 尝试降级到下一个策略")
                    continue
                else:
                    logger.error(f"[{trace_id}] 所有策略都执行失败")
                    raise
        
        # 所有策略都失败
        raise Exception("所有策略都执行失败")

    def _get_fallback_chain(self, primary_strategy: Type[ReasoningStrategy]) -> list:
        """获取降级策略链
        
        Args:
            primary_strategy: 主策略类
            
        Returns:
            list: 降级策略链（从主策略开始）
        """
        # 找到主策略在降级链中的位置
        try:
            index = self.fallback_strategies.index(primary_strategy)
            return self.fallback_strategies[index:]
        except ValueError:
            # 如果主策略不在降级链中，返回完整降级链
            return self.fallback_strategies.copy()

    async def _execute_parallel(
        self,
        strategy: ReasoningStrategy,
        messages: list,
        model_pool: list,
        trace_id: str,
        num_paths: int = 3
    ) -> str:
        """并行执行多条推理路径（异步并发优化）
        
        L7 级别在生成多条路径时使用并行生成，提升性能。
        
        Args:
            strategy: 策略实例
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪 ID
            num_paths: 并行路径数量
            
        Returns:
            str: 最佳推理结果
        """
        logger.info(f"[{trace_id}] 启动并行推理，路径数: {num_paths}")
        
        # 并行执行多条路径
        tasks = []
        for path_idx in range(num_paths):
            path_messages = messages.copy()
            # 为每条路径添加路径标识
            path_messages.append({
                "role": "system",
                "content": f"这是第 {path_idx + 1}/{num_paths} 条推理路径，请独立思考。"
            })
            tasks.append(strategy.execute(path_messages, model_pool, f"{trace_id}-path{path_idx}"))
        
        # 使用 asyncio.gather 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 收集成功的结果
        valid_results = []
        for idx, result in enumerate(results):
            if isinstance(result, str):
                valid_results.append((idx, result))
            else:
                logger.warning(f"[{trace_id}] 路径 {idx + 1} 执行失败: {result}")
        
        if not valid_results:
            raise Exception("所有并行路径都执行失败")
        
        # 选择最佳结果（这里简化处理，选择第一条成功的路径）
        _, best_result = valid_results[0]
        logger.info(f"[{trace_id}] 并行推理完成，选择路径 {valid_results[0][0] + 1}")
        
        return best_result