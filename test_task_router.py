#!/usr/bin/env python3
"""
TaskRouter 多维路由矩阵单元测试
测试核心功能：原型匹配 + 硬约束门限
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.task_router import TaskRouter
from src.data.domain_models import (
    TaskProfile, TaskPhysicalProfile, TaskBusinessProfile, TaskCognitiveProfile, RoutingLevel
)


def _create_profile(entropy: float, term_density: float, 
                   coreness: float, risk_score: float,
                   structural_variance: float = 0.2,
                   is_fast_pass: bool = False) -> TaskProfile:
    """辅助函数：创建测试用的完整画像"""
    return TaskProfile(
        trace_id="test-trace-001",
        timestamp=1714100000.0,
        physical=TaskPhysicalProfile(
            size=100,
            entropy=entropy,
            term_density=term_density,
            structural_variance=structural_variance
        ),
        business=TaskBusinessProfile(
            coreness=coreness,
            risk_score=risk_score,
            sla_priority=0.5,
            temporal_criticality=False
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
    assert result['level_num'] == 2, f"期望 L2，实际 L{result['level_num']}"
    print(f"[OK] 日常任务: {result['level'].name} ({result['route_name']})")
    print(f"     距离详情: {result['distance_map']}")
    
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
    assert result['level_num'] == 1, f"期望 L1，实际 L{result['level_num']}"
    print(f"[OK] 快速通道: {result['level'].name} ({result['route_name']})")
    
    # ==============================================
    # 场景 3：Nature 级高熵任务 → L5
    # ==============================================
    print("\n[测试 3] Nature 学术翻译 → 期望 L5")
    profile = _create_profile(
        entropy=0.9, term_density=0.85,
        coreness=0.2, risk_score=0.2
    )
    result = router.route(profile)
    assert result['level_num'] >= 5, f"期望至少 L5，实际 L{result['level_num']}"
    print(f"[OK] 高熵学术: {result['level'].name} ({result['route_name']})")
    print(f"     距离详情: {result['distance_map']}")
    
    # ==============================================
    # 场景 4：极高风险强制跳级 (硬约束)
    # ==============================================
    print("\n[测试 4] 极高风险 + 高核心 → 期望强制 L6")
    profile = _create_profile(
        entropy=0.3, term_density=0.3,
        coreness=0.9, risk_score=0.95
    )
    result = router.route(profile)
    assert result['level_num'] >= 6, f"期望至少 L6，实际 L{result['level_num']}"
    print(f"[OK] 高风险任务: {result['level'].name} ({result['route_name']})")
    print(f"     距离详情: {result['distance_map']}")
    
    # ==============================================
    # 场景 5：复杂执行 (L4)
    # ==============================================
    print("\n[测试 5] 复杂执行 → 期望 L4")
    profile = _create_profile(
        entropy=0.6, term_density=0.5,
        coreness=0.5, risk_score=0.5
    )
    result = router.route(profile)
    assert result['level_num'] == 4 or result['level_num'] == 3, f"期望 L3/L4，实际 L{result['level_num']}"
    print(f"[OK] 复杂执行: {result['level'].name} ({result['route_name']})")
    
    # ==============================================
    # 场景 6：巅峰博弈 (L7)
    # ==============================================
    print("\n[测试 6] 巅峰博弈 → 期望 L7")
    profile = _create_profile(
        entropy=0.95, term_density=0.95,
        coreness=1.0, risk_score=1.0
    )
    result = router.route(profile)
    assert result['level_num'] >= 6, f"期望至少 L6，实际 L{result['level_num']}"
    print(f"[OK] 巅峰博弈: {result['level'].name} ({result['route_name']})")
    
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
    assert result['level_num'] >= 6, "硬约束应该强制提级到 L6"
    print(f"[OK] 硬约束生效: L{result['initial_level'].value} → {result['level'].name}")
    
    # 测试高质量强制 L5
    print("\n[测试 B] 高质量信号 (0.9 熵)")
    profile = _create_profile(
        entropy=0.9, term_density=0.8,
        coreness=0.2, risk_score=0.2
    )
    result = router.route(profile)
    assert result['level_num'] >= 5, "硬约束应该强制提级到 L5"
    print(f"[OK] 质量约束生效: {result['level'].name}")
    
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
    # L2 的距离应该最小
    distances = result['distance_map']
    min_key = min(distances, key=distances.get)
    assert min_key == 2, f"L2 原型应该距离最近，但实际是 L{min_key}"
    print(f"[OK] 原型最近匹配: L{min_key}")
    
    print(f"     距离: {distances[min_key]:.4f}")
    return True


def test_scenario_cases():
    """测试架构师指定的典型场景"""
    print("\n" + "="*60)
    print("测试典型业务场景")
    print("="*60)
    
    router = TaskRouter()
    
    # 场景 A：Nature 论文翻译
    print("\n场景 A: Nature 学术翻译")
    profile = _create_profile(
        entropy=0.85, term_density=0.9,
        coreness=0.2, risk_score=0.3
    )
    result = router.route(profile)
    assert result['level_num'] >= 5, "Nature 翻译应该 ≥ L5"
    print(f"[OK] Nature 翻译: {result['level'].name} ({result['route_name']})")
    
    # 场景 B：修改 gateway.py
    print("\n场景 B: 修改 gateway.py (高核心)")
    profile = _create_profile(
        entropy=0.3, term_density=0.3,
        coreness=0.9, risk_score=0.9
    )
    result = router.route(profile)
    assert result['level_num'] >= 6, "核心资产修改应该 ≥ L6"
    print(f"[OK] 核心资产修改: {result['level'].name} ({result['route_name']})")
    
    return True


def main():
    """运行所有测试"""
    print("="*60)
    print("TaskRouter 原型匹配路由系统 - 单元测试")
    print("="*60)
    
    try:
        # 运行所有测试
        test1_ok = test_task_router_prototype_matching()
        test2_ok = test_hard_constraint_behavior()
        test3_ok = test_prototype_distance_calculation()
        test4_ok = test_scenario_cases()
        
        print("\n" + "="*60)
        print("测试汇总")
        print("="*60)
        all_ok = test1_ok and test2_ok and test3_ok and test4_ok
        
        if all_ok:
            print("✅ 所有测试通过！")
            return 0
        else:
            print("❌ 部分测试失败")
            return 1
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
