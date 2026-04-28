# src/core/pipelines/stages.py
# 管道阶段
# 依赖：abc, typing, src.data.domain_models, src.services.tracing
# 注意事项：
#   - 定义了管道的各个处理阶段
#   - 所有阶段都继承自 Stage 基类
#   - 每个阶段负责特定的处理功能

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.data.domain_models import AgentTask
from src.services.tracing import tracing


class Stage(ABC):
    """管道阶段基类

    定义了管道阶段的基本接口，所有具体阶段都需要实现此接口。
    每个阶段负责执行特定的处理任务，是管道系统的基本组成单元。
    """

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentTask:
        """执行阶段

        执行当前阶段的处理逻辑，处理智能体任务。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 阶段执行过程中出现错误时抛出
        """
        pass


class ContextRetrievalStage(Stage):
    """上下文检索阶段

    负责检索与任务相关的上下文信息，为后续处理提供背景知识。
    """

    async def execute(self, task: AgentTask) -> AgentTask:
        """执行上下文检索

        检索与任务相关的历史上下文、相关信息等。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 上下文检索失败时抛出
        """
        with tracing.start_span("context_retrieval.execute", attributes={
            "trace_id": task.trace_id
        }) as span:
            print(f"\n[{task.trace_id}] ========================================")
            print(f"[{task.trace_id}] 开始上下文检索阶段")
            print(f"[{task.trace_id}] ========================================")

            # 这里可以添加上下文检索逻辑
            # 例如从数据库或缓存中获取历史上下文

            print(f"[{task.trace_id}] 上下文检索完成")
            return task


class TaskAnalysisStage(Stage):
    """任务分析阶段

    负责分析任务的语义内容，提取意图信息，确定任务的复杂度和路由级别。
    """

    async def execute(self, task: AgentTask) -> AgentTask:
        """执行任务分析

        分析任务的语义内容，提取意图信息，确定任务的复杂度和路由级别。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 任务分析失败时抛出
        """
        with tracing.start_span("task_analysis.execute", attributes={
            "trace_id": task.trace_id
        }) as span:
            print(f"\n[{task.trace_id}] ========================================")
            print(f"[{task.trace_id}] 开始任务分析阶段")
            print(f"[{task.trace_id}] ========================================")

            # 分析任务
            from src.core.task_analyzer import task_analyzer
            semantic_data = await task_analyzer.extract_semantic_data(task.user_input)

            # 分析意图
            from src.core.intent_analyzer import IntentAnalyzer
            intent_data = IntentAnalyzer.analyze_intent(task.user_input, semantic_data)

            # 转换为 IntentAnalysis 对象
            from src.data.domain_models import IntentAnalysis, RouteLevel
            intent_analysis = IntentAnalysis(
                value=intent_data["value"],
                complexity=intent_data["complexity"],
                innovation=intent_data["innovation"],
                route_level=RouteLevel(intent_data["route_level"]),
                route_name=intent_data["route_name"]
            )

            # 更新任务
            task.semantic_data = semantic_data
            task.extracted_intent = intent_analysis
            task.routing_tier = RouteLevel(intent_data["route_level"])

            print(f"[{task.trace_id}] 任务分析完成")
            print(f"  路由级别: {task.routing_tier.value}")
            print(f"  路由名称: {intent_data['route_name']}")

            return task


class RoutingStage(Stage):
    """路由阶段

    基于任务分析结果，选择合适的处理策略和模型。
    """

    async def execute(self, task: AgentTask) -> AgentTask:
        """执行路由

        基于任务分析结果，选择合适的处理策略和模型。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 路由失败时抛出
        """
        with tracing.start_span("routing.execute", attributes={
            "trace_id": task.trace_id
        }) as span:
            print(f"\n[{task.trace_id}] ========================================")
            print(f"[{task.trace_id}] 开始路由阶段")
            print(f"[{task.trace_id}] ========================================")

            # 基于任务分析结果选择路由
            if task.routing_tier:
                # 这里可以添加更复杂的路由逻辑
                print(f"[{task.trace_id}] 路由选择: 级别 {task.routing_tier.value}")
            else:
                # 默认路由
                from src.data.domain_models import RouteLevel
                task.routing_tier = RouteLevel(2)  # 标准智能体
                print(f"[{task.trace_id}] 路由选择: 默认级别 2")

            print(f"[{task.trace_id}] 路由完成")
            return task


class ExecutionStage(Stage):
    """执行阶段

    负责执行具体的任务处理逻辑，使用选择的策略和模型。
    """

    def __init__(self, strategy_factory):
        """初始化执行阶段

        Args:
            strategy_factory: 策略工厂对象，用于创建推理策略
        """
        self.strategy_factory = strategy_factory

    async def execute(self, task: AgentTask) -> AgentTask:
        """执行任务

        使用选择的策略和模型执行任务处理。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 执行失败时抛出
        """
        with tracing.start_span("execution.execute", attributes={
            "trace_id": task.trace_id
        }) as span:
            print(f"\n[{task.trace_id}] ========================================")
            print(f"[{task.trace_id}] 开始执行阶段")
            print(f"[{task.trace_id}] ========================================")

            # 获取模型池
            from src.services.gateway import Gateway
            gateway = Gateway()
            model_pool = await gateway.get_available_models()

            # 选择策略
            strategy = self.strategy_factory.get_strategy(task)

            # 构建消息
            messages = [
                {"role": "user", "content": task.user_input}
            ]

            # 执行策略
            result = await strategy.execute(messages, model_pool, task.trace_id)

            # 更新任务
            task.final_answer = result

            print(f"[{task.trace_id}] 执行完成")
            return task


class CritiqueAndRefinementStage(Stage):
    """评审和改进阶段

    负责评审任务执行结果，进行改进和优化。
    """

    async def execute(self, task: AgentTask) -> AgentTask:
        """执行评审和改进

        评审任务执行结果，检查质量和准确性，进行必要的改进。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 评审和改进失败时抛出
        """
        with tracing.start_span("critique.execute", attributes={
            "trace_id": task.trace_id
        }) as span:
            print(f"\n[{task.trace_id}] ========================================")
            print(f"[{task.trace_id}] 开始评审和改进阶段")
            print(f"[{task.trace_id}] ========================================")

            # 这里可以添加评审和改进逻辑
            # 例如检查回答的质量、准确性等

            print(f"[{task.trace_id}] 评审和改进完成")
            return task


class FinalizationStage(Stage):
    """最终阶段

    负责最终处理，包括保存结果、清理资源等。
    """

    async def execute(self, task: AgentTask) -> AgentTask:
        """执行最终处理

        执行最终处理，包括保存结果、清理资源等。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 最终处理失败时抛出
        """
        with tracing.start_span("finalization.execute", attributes={
            "trace_id": task.trace_id
        }) as span:
            print(f"\n[{task.trace_id}] ========================================")
            print(f"[{task.trace_id}] 开始最终阶段")
            print(f"[{task.trace_id}] ========================================")

            # 这里可以添加最终处理逻辑
            # 例如保存任务结果、清理资源等

            print(f"[{task.trace_id}] 最终处理完成")
            return task
