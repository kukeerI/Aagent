# src/core/pipelines/base.py
# 管道基类
# 依赖：abc, typing, src.data.domain_models
# 注意事项：
#   - 定义了管道的基本接口
#   - 所有具体管道都需要实现 run 方法

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.data.domain_models import AgentTask


class Pipeline(ABC):
    """管道接口

    定义了智能体处理管道的基本接口，所有具体管道都需要实现此接口。
    管道负责按顺序执行一系列处理阶段，完成任务的处理流程。
    """

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentTask:
        """运行管道

        执行管道的所有处理阶段，处理智能体任务。

        Args:
            task: 智能体任务对象

        Returns:
            AgentTask: 执行后的任务对象

        Raises:
            Exception: 管道执行过程中出现错误时抛出
        """
        pass
