# src/core/intent_analyzer.py
# 兼容层 - 保持对旧代码的向后兼容
# 已迁移到 TaskRouter，此文件仅用于兼容旧引用

from typing import Dict, Any
from src.core.task_router import TaskRouter, RouteDecision
from src.data.domain_models import TaskProfile


class IntentAnalyzer:
    """意图分析器（兼容层）
    
    已迁移到 TaskRouter，此类仅提供向后兼容的接口。
    """
    
    def __init__(self):
        self.router = TaskRouter()
    
    def determine_route_level(self, profile: TaskProfile) -> Dict[str, Any]:
        """确定路由级别（兼容旧接口）
        
        Args:
            profile: 任务画像
            
        Returns:
            Dict: 兼容旧格式的路由结果
        """
        decision = self.router.route(profile)
        
        return {
            "level": decision.final_level.value,
            "level_num": decision.final_level.value,
            "route_name": self._get_route_name(decision.final_level.value),
            "initial_level": decision.initial_level.value if decision.initial_level else decision.final_level.value,
            "trigger_rule": decision.source,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "latency_ms": decision.latency_ms,
            "distance_map": decision.distance_map,
            "score_details": decision.score_details
        }
    
    @staticmethod
    def _get_route_name(level_num: int) -> str:
        """获取路由级别名称"""
        from src.config import config
        return config.ROUTE_LEVEL_NAMES.get(level_num, "Unknown")