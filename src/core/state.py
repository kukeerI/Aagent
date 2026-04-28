# src/core/state.py
# 状态机系统 - 图结构状态管理
# 依赖：enum, typing, asyncio, pydantic, src.core.checkpoint, src.data.domain_models
# 注意事项：
#   - 支持从检查点恢复执行
#   - 自动创建检查点，确保任务可恢复
#   - 任务完成后自动清理检查点

from enum import Enum
from typing import Dict, Any, Callable, Optional, List, Union
import asyncio
from pydantic import BaseModel, Field

from src.core.checkpoint import CheckpointManager, Checkpoint
from src.data.domain_models import AgentTask, TaskState, RouteLevel


class CommandType(str, Enum):
    """命令类型枚举

    定义状态处理器返回的命令类型，用于控制状态转换。
    """
    ANALYZE = "analyze"   # 分析任务
    EXECUTE = "execute"   # 执行任务
    RESEARCH = "research" # 研究任务
    CREATE = "create"     # 创建任务
    COMPLETE = "complete" # 完成任务
    ERROR = "error"       # 错误处理
    SUSPEND = "suspend"   # 挂起任务


class Command(BaseModel):
    """状态处理器返回的命令

    包含命令类型、参数和下一个状态信息。
    """
    type: CommandType                # 命令类型
    args: Dict[str, Any] = Field(default_factory=dict)  # 命令参数
    next_state: Optional[str] = None  # 下一个状态（可选）


class StateNode:
    """状态节点类

    表示状态机中的一个状态，包含状态名称、处理函数和转换规则。
    """

    def __init__(self, name: str, handler: Callable, transitions: Dict[str, str]):
        """初始化状态节点

        Args:
            name: 状态名称
            handler: 状态处理函数
            transitions: 状态转换规则
        """
        self.name = name
        self.handler = handler
        self.transitions = transitions


class StateMachine:
    """状态机基类

    提供状态机的核心功能，包括：
    - 添加状态节点
    - 运行状态机
    - 暂停和恢复执行
    - 管理检查点
    """

    def __init__(self):
        """初始化状态机

        - 初始化状态节点字典
        - 初始化检查点管理器
        """
        self.nodes = {}
        self.checkpoint_manager = CheckpointManager()

    def add_node(self, node: StateNode):
        """添加状态节点

        Args:
            node: 状态节点对象
        """
        self.nodes[node.name] = node

    async def run(self, task: AgentTask, start_state: str = TaskState.INIT, checkpoint_id: Optional[str] = None) -> AgentTask:
        """运行状态机，支持从检查点恢复

        Args:
            task: 智能体任务对象
            start_state: 起始状态，默认为 INIT
            checkpoint_id: 检查点 ID，用于恢复执行

        Returns:
            AgentTask: 执行完成的任务对象

        Raises:
            Exception: 状态机执行过程中出现错误时抛出
        """
        # 如果提供了检查点ID，从检查点恢复
        if checkpoint_id:
            checkpoint = await self.checkpoint_manager.get_checkpoint(checkpoint_id)
            if checkpoint:
                print(f"[StateMachine] 从检查点 {checkpoint_id} 恢复执行")
                current_state = checkpoint.state_name
                # 从检查点上下文重建任务
                task_dict = checkpoint.context
                task = AgentTask(**task_dict)
            else:
                print(f"[StateMachine] 检查点 {checkpoint_id} 不存在，从初始状态开始")
                current_state = start_state
        else:
            current_state = start_state

        while current_state != TaskState.COMPLETE:
            if current_state not in self.nodes:
                task.error = f"状态不存在: {current_state}"
                current_state = TaskState.ERROR

            node = self.nodes[current_state]
            try:
                # 创建检查点
                checkpoint = await self.checkpoint_manager.create_checkpoint(current_state, task.model_dump())
                print(f"[StateMachine] 创建检查点 {checkpoint.checkpoint_id} 用于状态 {current_state}")

                # 执行状态处理函数
                command = await node.handler(task)

                # 确定下一个状态
                if command.next_state:
                    current_state = command.next_state
                elif command.type.value in node.transitions:
                    current_state = node.transitions[command.type.value]
                else:
                    current_state = TaskState.COMPLETE
            except Exception as e:
                task.error = str(e)
                current_state = TaskState.ERROR

        # 清理检查点
        if task.trace_id:
            deleted = await self.checkpoint_manager.delete_checkpoints_by_trace_id(task.trace_id)
            print(f"[StateMachine] 清理了 {deleted} 个检查点")

        return task

    async def pause(self, task: AgentTask, current_state: str) -> str:
        """暂停执行，创建检查点

        Args:
            task: 智能体任务对象
            current_state: 当前状态

        Returns:
            str: 检查点 ID

        Raises:
            Exception: 创建检查点失败时抛出
        """
        checkpoint = await self.checkpoint_manager.create_checkpoint(current_state, task.model_dump())
        print(f"[StateMachine] 执行已暂停，创建检查点 {checkpoint.checkpoint_id}")
        return checkpoint.checkpoint_id

    async def list_checkpoints(self, trace_id: str) -> List[Checkpoint]:
        """列出指定 trace_id 的所有检查点

        Args:
            trace_id: 追踪 ID

        Returns:
            List[Checkpoint]: 检查点列表

        Raises:
            Exception: 数据库操作失败时抛出
        """
        return await self.checkpoint_manager.list_checkpoints(trace_id)

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """获取检查点

        Args:
            checkpoint_id: 检查点 ID

        Returns:
            Optional[Checkpoint]: 检查点对象，如果不存在返回 None

        Raises:
            Exception: 数据库操作失败时抛出
        """
        return await self.checkpoint_manager.get_checkpoint(checkpoint_id)

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除检查点

        Args:
            checkpoint_id: 检查点 ID

        Returns:
            bool: 删除是否成功

        Raises:
            Exception: 数据库操作失败时抛出
        """
        return await self.checkpoint_manager.delete_checkpoint(checkpoint_id)


class AgentStateMachine(StateMachine):
    """智能体状态机

    继承自 StateMachine，实现了智能体的具体状态处理逻辑。
    """

    def __init__(self, orchestrator):
        """初始化智能体状态机

        Args:
            orchestrator: 智能体编排器对象
        """
        super().__init__()
        self.orchestrator = orchestrator
        self._setup_nodes()

    def _setup_nodes(self):
        """设置状态节点

        初始化所有状态节点，包括：
        - 初始化状态
        - 分析状态
        - 执行状态
        - 研究状态
        - 创建状态
        - 挂起状态
        - 错误状态
        - 完成状态
        """
        # 初始化节点
        self.add_node(StateNode(
            TaskState.INIT,
            self._init_handler,
            {"analyze": TaskState.ANALYZE, "execute": TaskState.EXECUTE, "research": TaskState.RESEARCH, "create": TaskState.CREATE}
        ))

        # 分析节点
        self.add_node(StateNode(
            TaskState.ANALYZE,
            self._analyze_handler,
            {"complete": TaskState.COMPLETE, "error": TaskState.ERROR}
        ))

        # 执行节点
        self.add_node(StateNode(
            TaskState.EXECUTE,
            self._execute_handler,
            {"complete": TaskState.COMPLETE, "error": TaskState.ERROR}
        ))

        # 研究节点
        self.add_node(StateNode(
            TaskState.RESEARCH,
            self._research_handler,
            {"complete": TaskState.COMPLETE, "error": TaskState.ERROR}
        ))

        # 创建节点
        self.add_node(StateNode(
            TaskState.CREATE,
            self._create_handler,
            {"complete": TaskState.COMPLETE, "error": TaskState.ERROR}
        ))

        # 挂起节点
        self.add_node(StateNode(
            TaskState.SUSPEND,
            self._suspend_handler,
            {"resume": TaskState.INIT, "complete": TaskState.COMPLETE}
        ))

        # 错误节点
        self.add_node(StateNode(
            TaskState.ERROR,
            self._error_handler,
            {"complete": TaskState.COMPLETE}
        ))

        # 完成节点
        self.add_node(StateNode(
            TaskState.COMPLETE,
            self._complete_handler,
            {}
        ))

    async def _init_handler(self, task: AgentTask) -> Command:
        """初始化处理器

        分析任务意图，确定后续状态。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令

        Raises:
            Exception: 初始化失败时抛出
        """
        user_input = task.user_input
        # 确保任务中有trace_id
        if not task.trace_id:
            task.trace_id = getattr(self.orchestrator, "trace_id", "unknown")

        # 使用 TaskAnalyzer 进行任务分析
        try:
            from src.core.task_analyzer import task_analyzer
            semantic_data = await task_analyzer.extract_semantic_data(user_input)
            task.semantic_data = semantic_data

            # 分析意图
            from src.core.intent_analyzer import IntentAnalyzer
            intent_data = IntentAnalyzer.analyze_intent(user_input, semantic_data)

            # 基于意图决定下一个状态
            route_level = intent_data["route_level"]
            task.routing_tier = route_level

            # 根据任务类型和路由级别决定下一步
            task_type = semantic_data.get("task_type", "general")
            if task_type == "code":
                return Command(type=CommandType.EXECUTE)
            elif task_type == "analysis":
                return Command(type=CommandType.ANALYZE)
            elif task_type == "research":
                return Command(type=CommandType.RESEARCH)
            elif task_type == "creative":
                return Command(type=CommandType.CREATE)
            else:
                # 默认使用分析
                return Command(type=CommandType.ANALYZE)
        except Exception as e:
            task.error = str(e)
            return Command(type=CommandType.ERROR)

    async def _analyze_handler(self, task: AgentTask) -> Command:
        """分析处理器

        处理分析类型的任务。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令

        Raises:
            Exception: 分析失败时抛出
        """
        from src.services.tracing import tracing
        with tracing.start_span("state.analyze"):
            user_input = task.user_input
            try:
                analysis = await self.orchestrator._analyze_task(user_input)
                result = await self.orchestrator._execute_task(user_input, "analysis")
                task.final_answer = result
                task.extracted_intent = analysis
                return Command(type=CommandType.COMPLETE)
            except Exception as e:
                task.error = str(e)
                return Command(type=CommandType.ERROR)

    async def _execute_handler(self, task: AgentTask) -> Command:
        """执行处理器

        处理执行类型的任务，包括代码执行。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令

        Raises:
            Exception: 执行失败时抛出
        """
        from src.services.tracing import tracing
        with tracing.start_span("state.execute"):
            user_input = task.user_input
            try:
                result = await self.orchestrator._execute_task(user_input, "code_generation")
                # 提取代码并执行
                if "```python" in result:
                    code = result.split("```python")[1].split("```")[0].strip()
                    execution_result = await self.orchestrator._safe_execute_code(code)
                    task.final_answer = f"{result}\n\n{execution_result}"
                else:
                    task.final_answer = result
                return Command(type=CommandType.COMPLETE)
            except Exception as e:
                task.error = str(e)
                return Command(type=CommandType.ERROR)

    async def _research_handler(self, task: AgentTask) -> Command:
        """研究处理器

        处理研究类型的任务。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令

        Raises:
            Exception: 研究失败时抛出
        """
        from src.services.tracing import tracing
        with tracing.start_span("state.research"):
            user_input = task.user_input
            try:
                result = await self.orchestrator._research_task(user_input)
                task.final_answer = result
                return Command(type=CommandType.COMPLETE)
            except Exception as e:
                task.error = str(e)
                return Command(type=CommandType.ERROR)

    async def _create_handler(self, task: AgentTask) -> Command:
        """创建处理器

        处理创建类型的任务。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令

        Raises:
            Exception: 创建失败时抛出
        """
        from src.services.tracing import tracing
        with tracing.start_span("state.create"):
            user_input = task.user_input
            try:
                result = await self.orchestrator._create_task(user_input)
                task.final_answer = result
                return Command(type=CommandType.COMPLETE)
            except Exception as e:
                task.error = str(e)
                return Command(type=CommandType.ERROR)

    async def _suspend_handler(self, task: AgentTask) -> Command:
        """挂起处理器

        处理资源耗尽等需要挂起的情况。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令
        """
        from src.services.tracing import tracing
        with tracing.start_span("state.suspend"):
            error = task.error or "资源耗尽"
            print(f"[StateMachine] 任务挂起: {error}")
            task.final_answer = f"任务已挂起:\n{error}\n\n请等待 API 资源恢复或进行人工干预后重试。"
            return Command(type=CommandType.COMPLETE)

    async def _error_handler(self, task: AgentTask) -> Command:
        """错误处理器

        处理执行过程中的错误，包括资源耗尽错误的特殊处理。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令
        """
        from src.services.tracing import tracing
        with tracing.start_span("state.error", attributes={
            "error_message": task.error or "Unknown error"
        }):
            error = task.error or "Unknown error"
            print(f"[Error] {error}")

            # 检查是否是资源耗尽错误
            if "ComputeResourceExhaustedError" in str(error) or "高阶算力池已耗尽" in str(error):
                print("[StateMachine] 检测到资源耗尽错误，将任务挂起")
                return Command(type=CommandType.SUSPEND, next_state=TaskState.SUSPEND)

            try:
                error_response = await self.orchestrator._handle_error(error)
                task.final_answer = f"任务执行失败: {error}\n\n解决方案: {error_response}"
            except Exception as e:
                task.final_answer = f"任务执行失败: {error}\n\n错误处理也失败: {str(e)}"
            return Command(type=CommandType.COMPLETE)

    async def _complete_handler(self, task: AgentTask) -> Command:
        """完成处理器

        处理任务完成的情况。

        Args:
            task: 智能体任务对象

        Returns:
            Command: 下一步命令
        """
        return Command(type=CommandType.COMPLETE)
