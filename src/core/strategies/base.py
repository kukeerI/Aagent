# src/core/strategies/base.py
# 推理策略基类
# 依赖：abc, typing
# 注意事项：
#   - 定义了推理策略的基本接口
#   - 所有具体策略都需要实现 execute 方法

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ReasoningStrategy(ABC):
    """推理策略接口

    定义了智能体推理策略的基本接口，所有具体策略都需要实现此接口。
    推理策略负责根据输入消息和模型池执行推理过程，返回推理结果。
    """

    @abstractmethod
    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行推理

        根据输入消息和模型池执行推理过程，返回推理结果。

        Args:
            messages: 消息列表，包含用户输入和系统提示
            model_pool: 模型池，包含可用的模型信息
            trace_id: 追踪 ID，用于日志和追踪

        Returns:
            str: 推理结果

        Raises:
            Exception: 推理过程中出现错误时抛出
        """
        pass
