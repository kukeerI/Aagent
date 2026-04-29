#!/usr/bin/env python3
"""
TaskRouter 多维路由矩阵单元测试 - 终极进化版
测试核心功能：原型匹配 + 硬约束门限 + SQL注入拦截 + 决策审计
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.task_router import TaskRouter, RouteDecision
from src.config import config
from src.data.domain_models import (
    TaskProfile, TaskPhysicalProfile, TaskBusinessProfile, TaskCognitiveProfile, RoutingLevel
)


def _create_profile(entropy: float, term_density: float, 
                   coreness: float, risk_score: float,
                   structural_variance: float = 0.2,
                   is_fast_pass: bool = False,
                   sla_priority: float = 0.5,
                   has_privacy_data: bool = False,
                   raw_query: str = None) -> TaskProfile:
    """辅助函数：创建测试用的完整画像"""
    return TaskProfile(
        trace_id="test-trace-001",
        timestamp=1714100000.0,
        raw_query=raw_query,
        physical=TaskPhysicalProfile(
            size=100,
            entropy=entropy,
            term_density=term_density,
            structural_variance=structural_variance
        ),
        business=TaskBusinessProfile(
            coreness=coreness,
            risk_score=risk_score,
            sla_priority=sla_priority,
            temporal_criticality=False,
            has_privacy_data=has_privacy_data
        ),
        cognitive=TaskCognitiveProfile(
            innovation_requirement=0.3,
            dependency_gap=0.3,
            is_closed_loop=True,
            is_fast_pass=is_fast_pass
        )
    )


def test_task_router_prototype_matching():
    """测试原型匹配算法 - 覆盖所有典型场景"""
    print("="*60)
    print("测试 TaskRouter 原型匹配")
    print("="*60)
    
    router = TaskRouter()
    
    # ==============================================
    # 场景 1：日常标准任务 (L2)
    # ==============================================
    print("\n[测试 1] 日常标准任务 → 期望 L2")
    profile = _create_profile(
        entropy=0.3, term_density=0.2,
        coreness=0.2, risk_score=0.2
    )
    result = router.route(profile)
    assert result.final_level.value == 2, f"期望 L2，实际 L{result.final_level.value}"
    print(f"[OK] 日常任务: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 置信度: {result.confidence:.4f}")
    
    # ==============================================
    # 场景 2：快速通道 (L1)
    # ==============================================
    print("\n[测试 2] 快速通道 → 期望 L1")
    profile = _create_profile(
        entropy=0.1, term_density=0.1,
        coreness=0.1, risk_score=0.1,
        is_fast_pass=True
    )
    result = router.route(profile)
    assert result.final_level.value == 1, f"期望 L1，实际 L{result.final_level.value}"
    print(f"[OK] 快速通道: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 原因: {result.reason}")
    
    # ==============================================
    # 场景 3：Nature 级高熵任务 → L5
    # ==============================================
    print("\n[测试 3] Nature 学术翻译 → 期望 L5")
    profile = _create_profile(
        entropy=0.9, term_density=0.85,
        coreness=0.2, risk_score=0.2
    )
    result = router.route(profile)
    assert result.final_level.value >= 5, f"期望至少 L5，实际 L{result.final_level.value}"
    print(f"[OK] 高熵学术: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 置信度: {result.confidence:.4f}")
    
    # ==============================================
    # 场景 4：极高风险强制跳级 (硬约束)
    # ==============================================
    print("\n[测试 4] 极高风险 + 高核心 → 期望强制 L6")
    profile = _create_profile(
        entropy=0.3, term_density=0.3,
        coreness=0.9, risk_score=0.95
    )
    result = router.route(profile)
    assert result.final_level.value >= 6, f"期望至少 L6，实际 L{result.final_level.value}"
    print(f"[OK] 高风险任务: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 原因: {result.reason}")
    
    # ==============================================
    # 场景 5：复杂执行 (L4)
    # ==============================================
    print("\n[测试 5] 复杂执行 → 期望 L4")
    profile = _create_profile(
        entropy=0.6, term_density=0.5,
        coreness=0.5, risk_score=0.5
    )
    result = router.route(profile)
    assert result.final_level.value == 4 or result.final_level.value == 3, f"期望 L3/L4，实际 L{result.final_level.value}"
    print(f"[OK] 复杂执行: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 置信度: {result.confidence:.4f}")
    
    # ==============================================
    # 场景 6：SQL 注入拦截 → L7
    # ==============================================
    print("\n[测试 6] SQL 注入检测 → 期望 L7")
    profile = _create_profile(
        entropy=0.5, term_density=0.5,
        coreness=0.5, risk_score=0.5,
        raw_query="DROP TABLE users; -- malicious"
    )
    result = router.route(profile)
    assert result.final_level.value == 7, f"期望 L7，实际 L{result.final_level.value}"
    print(f"[OK] SQL注入拦截: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 原因: {result.reason}")
    
    # ==============================================
    # 场景 7：隐私数据拦截 → L1
    # ==============================================
    print("\n[测试 7] 隐私数据拦截 → 期望 L1")
    profile = _create_profile(
        entropy=0.5, term_density=0.5,
        coreness=0.5, risk_score=0.5,
        has_privacy_data=True
    )
    result = router.route(profile)
    assert result.final_level.value == 1, f"期望 L1，实际 L{result.final_level.value}"
    print(f"[OK] 隐私数据拦截: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    print(f"     来源: {result.source}, 原因: {result.reason}")
    
    return True


def test_hard_constraint_behavior():
    """测试硬约束修正逻辑"""
    print("\n" + "="*60)
    print("测试硬约束门限机制")
    print("="*60)
    
    router = TaskRouter()
    
    # 测试极高风险强制 L6
    print("\n[测试 A] 极高风险 (0.95) + 高核心度 (0.8)")
    profile = _create_profile(
        entropy=0.2, term_density=0.2,  # 物理特征很普通，应该匹配 L2
        coreness=0.8, risk_score=0.95  # 但业务风险极高
    )
    result = router.route(profile)
    assert result.final_level.value >= 6, "硬约束应该强制提级到 L6"
    initial_level = result.initial_level.value if result.initial_level else "Unknown"
    print(f"[OK] 硬约束生效: L{initial_level} → {result.final_level.name}")
    
    # 测试高质量强制 L5
    print("\n[测试 B] 高质量信号 (0.9 熵)")
    profile = _create_profile(
        entropy=0.9, term_density=0.8,
        coreness=0.2, risk_score=0.2
    )
    result = router.route(profile)
    assert result.final_level.value >= 5, "硬约束应该强制提级到 L5"
    print(f"[OK] 质量约束生效: {result.final_level.name}")
    
    return True


def test_prototype_distance_calculation():
    """测试距离计算与权重应用"""
    print("\n" + "="*60)
    print("测试向量距离计算")
    print("="*60)
    
    router = TaskRouter()
    
    # 创建一个完全匹配 L2 原型的任务
    print("\n[测试] L2 原型完全匹配")
    profile = _create_profile(
        entropy=0.3, term_density=0.2,
        coreness=0.2, risk_score=0.2
    )
    result = router.route(profile)
    assert result.final_level.value == 2
    print(f"[OK] 原型最近匹配: L{result.final_level.value}")
    if result.distance_map:
        print(f"     距离: {result.distance_map.get('2', 'N/A'):.4f}")
    
    return True


def test_typical_business_scenarios():
    """测试典型业务场景"""
    print("\n" + "="*60)
    print("测试典型业务场景")
    print("="*60)
    
    router = TaskRouter()
    
    # 场景 A: Nature 学术翻译
    print("\n场景 A: Nature 学术翻译")
    profile = _create_profile(
        entropy=0.85, term_density=0.9,
        coreness=0.1, risk_score=0.1,
        sla_priority=0.9
    )
    result = router.route(profile)
    print(f"[OK] Nature 翻译: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    
    # 场景 B: 修改核心配置文件
    print("\n场景 B: 修改 gateway.py (高核心)")
    profile = _create_profile(
        entropy=0.4, term_density=0.4,
        coreness=0.9, risk_score=0.85
    )
    result = router.route(profile)
    print(f"[OK] 核心资产修改: {result.final_level.name} ({config.ROUTE_LEVEL_NAMES[result.final_level.value]})")
    
    return True


def test_decision_audit():
    """测试决策审计信息完整性"""
    print("\n" + "="*60)
    print("测试决策审计信息")
    print("="*60)
    
    router = TaskRouter()
    
    profile = _create_profile(
        entropy=0.7, term_density=0.6,
        coreness=0.4, risk_score=0.4
    )
    result = router.route(profile)
    
    # 验证决策对象的完整性
    assert isinstance(result, RouteDecision), "返回值必须是 RouteDecision 对象"
    assert result.final_level is not None, "必须有最终级别"
    assert result.source is not None, "必须有来源信息"
    assert result.reason is not None, "必须有原因说明"
    assert result.latency_ms >= 0, "耗时必须非负"
    assert 0 <= result.confidence <= 1, "置信度必须在 [0, 1] 范围内"
    
    print(f"[OK] 决策对象完整")
    print(f"     级别: {result.final_level.name}")
    print(f"     来源: {result.source}")
    print(f"     原因: {result.reason}")
    print(f"     耗时: {result.latency_ms:.2f}ms")
    print(f"     置信度: {result.confidence:.4f}")
    
    return True


def main():
    """运行所有测试"""
    print("="*60)
    print("TaskRouter 原型匹配路由系统 - 单元测试 (终极进化版)")
    print("="*60)
    
    tests = [
        test_task_router_prototype_matching,
        test_hard_constraint_behavior,
        test_prototype_distance_calculation,
        test_typical_business_scenarios,
        test_decision_audit
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAILED] {test.__name__}: {e}")
    
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    print(f"通过: {passed}, 失败: {failed}")
    
    if failed == 0:
        print("所有测试通过！")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())