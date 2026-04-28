# src/core/pipelines/__init__.py
# 管道系统初始化文件
# 依赖：.base, .standard_pipeline, .stages
# 导出管道相关组件供其他模块使用

from .base import Pipeline
from .standard_pipeline import StandardPipeline
from .stages import (
    ContextRetrievalStage,
    TaskAnalysisStage,
    RoutingStage,
    ExecutionStage,
    CritiqueAndRefinementStage,
    FinalizationStage
)

__all__ = [
    "Pipeline",
    "StandardPipeline",
    "ContextRetrievalStage",
    "TaskAnalysisStage",
    "RoutingStage",
    "ExecutionStage",
    "CritiqueAndRefinementStage",
    "FinalizationStage"
]
