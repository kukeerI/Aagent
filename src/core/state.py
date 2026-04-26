# src/core/state.py
# 状态机系统 - 图结构状态管理

from enum import Enum
from typing import Dict, Any, Callable, Optional, List
import asyncio

class State(Enum):
    INIT = "init"
    ANALYZE = "analyze"
    EXECUTE = "execute"
    RESEARCH = "research"
    CREATE = "create"
    ERROR = "error"
    COMPLETE = "complete"

class StateNode:
    def __init__(self, name: str, handler: Callable, transitions: Dict[str, str]):
        self.name = name
        self.handler = handler
        self.transitions = transitions

class StateMachine:
    def __init__(self):
        self.nodes = {}

    def add_node(self, node: StateNode):
        self.nodes[node.name] = node

    async def run(self, context: Dict[str, Any], start_state: str = State.INIT.value) -> Dict[str, Any]:
        current_state = start_state
        
        while current_state != State.COMPLETE.value:
            if current_state not in self.nodes:
                context["error"] = f"状态不存在: {current_state}"
                current_state = State.ERROR.value
            
            node = self.nodes[current_state]
            try:
                # 执行状态处理函数
                transition_key, context = await node.handler(context)
                
                # 确定下一个状态
                if transition_key in node.transitions:
                    current_state = node.transitions[transition_key]
                else:
                    current_state = State.COMPLETE.value
            except Exception as e:
                context["error"] = str(e)
                current_state = State.ERROR.value
        
        return context

class AgentStateMachine(StateMachine):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self._setup_nodes()

    def _setup_nodes(self):
        # 初始化节点
        self.add_node(StateNode(
            State.INIT.value,
            self._init_handler,
            {"analyze": State.ANALYZE.value, "execute": State.EXECUTE.value, "research": State.RESEARCH.value, "create": State.CREATE.value}
        ))
        
        # 分析节点
        self.add_node(StateNode(
            State.ANALYZE.value,
            self._analyze_handler,
            {"complete": State.COMPLETE.value, "error": State.ERROR.value}
        ))
        
        # 执行节点
        self.add_node(StateNode(
            State.EXECUTE.value,
            self._execute_handler,
            {"complete": State.COMPLETE.value, "error": State.ERROR.value}
        ))
        
        # 研究节点
        self.add_node(StateNode(
            State.RESEARCH.value,
            self._research_handler,
            {"complete": State.COMPLETE.value, "error": State.ERROR.value}
        ))
        
        # 创建节点
        self.add_node(StateNode(
            State.CREATE.value,
            self._create_handler,
            {"complete": State.COMPLETE.value, "error": State.ERROR.value}
        ))
        
        # 错误节点
        self.add_node(StateNode(
            State.ERROR.value,
            self._error_handler,
            {"complete": State.COMPLETE.value}
        ))
        
        # 完成节点
        self.add_node(StateNode(
            State.COMPLETE.value,
            self._complete_handler,
            {}
        ))

    async def _init_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        user_input = context.get("user_input", "")
        
        # 简单的任务类型判断
        if any(keyword in user_input.lower() for keyword in ["代码", "编程", "function", "python"]):
            return "execute", context
        elif any(keyword in user_input.lower() for keyword in ["分析", "原理", "工作", "如何"]):
            return "analyze", context
        elif any(keyword in user_input.lower() for keyword in ["研究", "信息", "数据", "背景"]):
            return "research", context
        elif any(keyword in user_input.lower() for keyword in ["写", "创建", "设计", "生成"]):
            return "create", context
        else:
            return "analyze", context

    async def _analyze_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        from src.services.tracing import tracing
        with tracing.start_span("state.analyze"):
            user_input = context.get("user_input", "")
            try:
                analysis = await self.orchestrator._analyze_task(user_input)
                result = await self.orchestrator._execute_task(user_input, "analysis")
                context["final_answer"] = result
                context["analysis"] = analysis
                return "complete", context
            except Exception as e:
                context["error"] = str(e)
                return "error", context

    async def _execute_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        from src.services.tracing import tracing
        with tracing.start_span("state.execute"):
            user_input = context.get("user_input", "")
            try:
                result = await self.orchestrator._execute_task(user_input, "code_generation")
                # 提取代码并执行
                if "```python" in result:
                    code = result.split("```python")[1].split("```")[0].strip()
                    execution_result = await self.orchestrator._safe_execute_code(code)
                    context["final_answer"] = f"{result}\n\n{execution_result}"
                else:
                    context["final_answer"] = result
                return "complete", context
            except Exception as e:
                context["error"] = str(e)
                return "error", context

    async def _research_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        from src.services.tracing import tracing
        with tracing.start_span("state.research"):
            user_input = context.get("user_input", "")
            try:
                result = await self.orchestrator._research_task(user_input)
                context["final_answer"] = result
                return "complete", context
            except Exception as e:
                context["error"] = str(e)
                return "error", context

    async def _create_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        from src.services.tracing import tracing
        with tracing.start_span("state.create"):
            user_input = context.get("user_input", "")
            try:
                result = await self.orchestrator._create_task(user_input)
                context["final_answer"] = result
                return "complete", context
            except Exception as e:
                context["error"] = str(e)
                return "error", context

    async def _error_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        from src.services.tracing import tracing
        with tracing.start_span("state.error", attributes={
            "error_message": context.get("error", "Unknown error")
        }):
            error = context.get("error", "Unknown error")
            print(f"[Error] {error}")
            try:
                error_response = await self.orchestrator._handle_error(error)
                context["final_answer"] = f"任务执行失败: {error}\n\n解决方案: {error_response}"
            except Exception as e:
                context["final_answer"] = f"任务执行失败: {error}\n\n错误处理也失败: {str(e)}"
            return "complete", context

    async def _complete_handler(self, context: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        return "", context