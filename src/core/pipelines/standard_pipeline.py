# src/core/pipelines/standard_pipeline.py
# 标准管道实现
# 依赖：typing, src.core.pipelines.base, src.core.pipelines.stages, src.core.strategies
# 注意事项：
#   - 按照固定顺序执行所有管道阶段
#   - 包含上下文检索、任务分析、路由、执行、评审和最终处理

from typing import List

from src.core.pipelines.base import Pipeline
from src.core.pipelines.stages import (
    ContextRetrievalStage,
    TaskAnalysisStage,
    RoutingStage,
    ExecutionStage,
    CritiqueAndRefinementStage,
    FinalizationStage
)
from src.core.strategies import StrategyFactory


class StandardPipeline(Pipeline):
    """标准管道实现

    实现了标准的智能体处理管道，按顺序执行各个处理阶段。
    包含以下阶段：
    1. 上下文检索
    2. 任务分析
    3. 路由
    4. 执行
    5. 评审和改进
    6. 最终处理
    """

    def __init__(self):
        """初始化标准管道

        - 初始化策略工厂
        - 构建管道阶段列表
        """
        # 初始化策略工厂
        self.strategy_factory = StrategyFactory()

        # 构建管道阶段
        self.stages = [
            ContextRetrievalStage(),
            TaskAnalysisStage(),
            RoutingStage(),
            ExecutionStage(self.strategy_factory),
            CritiqueAndRefinementStage(),
            FinalizationStage()
        ]

    async def run(self, task):
        """运行管道

        按顺序执行所有管道阶段，处理智能体任务。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 管道执行过程中出现错误时抛出
        """
        current_task = task

        # 按顺序执行各个阶段
        for stage in self.stages:
            current_task = await stage.execute(current_task)

        return current_task
