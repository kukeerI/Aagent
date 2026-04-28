#!/usr/bin/env python3
"""
IntentAnalyzer 路由决策矩阵单元测试
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.intent_analyzer import IntentAnalyzer
from src.data.domain_models import TaskProfile, TaskPhysicalProfile, TaskBusinessProfile, TaskCognitiveProfile


def _create_profile(physical, business, cognitive):
    """辅助函数：创建完整的 TaskProfile"""
    return TaskProfile(
        trace_id="test-trace-001",
        timestamp=1234567890.0,
        physical=physical,
        business=business,
        cognitive=cognitive
    )

def test_route_decision():
    """测试路由决策矩阵（基于门槛的条件触发）"""
    print("="*60)
    print("测试路由决策矩阵")
    print("="*60)
    
    # 测试1: 快速通过任务（is_fast_pass=True 且 risk_score < 0.2）
    profile = _create_profile(
        TaskPhysicalProfile(size=5, entropy=0.1, term_density=0.0, structural_variance=0.0),
        TaskBusinessProfile(coreness=0.1, risk_score=0.05, sla_priority=0.3, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.1, dependency_gap=0.2, is_closed_loop=True, is_fast_pass=True)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert result["level"] == 1
    assert result["route_name"] == "本地吞吐"
    assert "极速分诊拦截" in str(result["triggers"])
    print("[OK] 快速通过任务分配 L1")
    
    # 测试2: 标准任务（默认级别 L2）
    profile = _create_profile(
        TaskPhysicalProfile(size=50, entropy=0.3, term_density=0.1, structural_variance=0.1),
        TaskBusinessProfile(coreness=0.2, risk_score=0.2, sla_priority=0.3, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.2, dependency_gap=0.3, is_closed_loop=True, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert result["level"] == 2
    print(f"[OK] 标准任务分配 L{result['level']}")
    
    # 测试3: 高信息熵任务（熵>0.7，触发质量提级到 L5）
    profile = _create_profile(
        TaskPhysicalProfile(size=1000, entropy=0.8, term_density=0.3, structural_variance=0.2),
        TaskBusinessProfile(coreness=0.3, risk_score=0.3, sla_priority=0.4, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.3, dependency_gap=0.4, is_closed_loop=False, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert result["level"] == 5
    assert "质量补偿" in str(result["triggers"])
    print(f"[OK] 高信息熵任务分配 L{result['level']}（质量提级）")
    
    # 测试4: 高术语密度任务（term_density>0.6，触发质量提级到 L5）
    profile = _create_profile(
        TaskPhysicalProfile(size=500, entropy=0.4, term_density=0.7, structural_variance=0.1),
        TaskBusinessProfile(coreness=0.4, risk_score=0.4, sla_priority=0.5, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.4, dependency_gap=0.3, is_closed_loop=False, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert result["level"] == 5
    assert "质量补偿" in str(result["triggers"])
    print(f"[OK] 高术语密度任务分配 L{result['level']}（质量提级）")
    
    # 测试5: 高危任务（risk_score>0.8，触发风险熔断到 L6）
    profile = _create_profile(
        TaskPhysicalProfile(size=200, entropy=0.5, term_density=0.3, structural_variance=0.2),
        TaskBusinessProfile(coreness=0.6, risk_score=0.9, sla_priority=0.6, temporal_criticality=True),
        TaskCognitiveProfile(innovation_requirement=0.3, dependency_gap=0.4, is_closed_loop=True, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert result["level"] == 6
    assert "风险熔断" in str(result["triggers"])
    print(f"[OK] 高危任务分配 L{result['level']}（风险熔断）")
    
    # 测试6: 语义波动大（不确定性补偿，提1级）
    profile = _create_profile(
        TaskPhysicalProfile(size=300, entropy=0.4, term_density=0.2, structural_variance=0.5),
        TaskBusinessProfile(coreness=0.3, risk_score=0.3, sla_priority=0.4, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.4, dependency_gap=0.3, is_closed_loop=False, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert "不确定性补偿" in str(result["triggers"])
    # 语义波动大提1级，基础L2+1=L3
    assert result["level"] == 3
    print(f"[OK] 语义波动大任务分配 L{result['level']}（触发不确定性补偿）")
    
    # 测试7: 边界检查 - 最大级别 L7（质量提级L5 + 风险熔断L6 + 不确定性补偿+1 = L7）
    profile = _create_profile(
        TaskPhysicalProfile(size=2000, entropy=0.9, term_density=0.8, structural_variance=0.6),
        TaskBusinessProfile(coreness=0.9, risk_score=0.95, sla_priority=0.9, temporal_criticality=True),
        TaskCognitiveProfile(innovation_requirement=0.9, dependency_gap=0.8, is_closed_loop=False, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    assert result["level"] == 7
    assert result["route_name"] == "巅峰博弈"
    print(f"[OK] 最高级别任务分配 L7 ({result['route_name']})")
    
    # 测试8: L2粘性测试（日常翻译任务应该钉在L2）
    profile = _create_profile(
        TaskPhysicalProfile(size=600, entropy=0.55, term_density=0.45, structural_variance=0.2),
        TaskBusinessProfile(coreness=0.15, risk_score=0.15, sla_priority=0.4, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.2, dependency_gap=0.3, is_closed_loop=True, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    # 日常翻译任务应该保持在L2
    assert result["level"] == 2
    print(f"[OK] 日常翻译任务分配 L{result['level']}（L2粘性测试通过）")
    
    return True


def test_route_mapping():
    """测试路由名称映射"""
    print("\n" + "="*60)
    print("测试路由名称映射")
    print("="*60)
    
    route_names = {
        1: "本地吞吐",
        2: "标准代理",
        3: "高价单发",
        4: "复杂执行",
        5: "逻辑深钻",
        6: "创意融合",
        7: "巅峰博弈"
    }
    
    for level, expected_name in route_names.items():
        # 创建一个简单的profile来测试映射
        profile = _create_profile(
            TaskPhysicalProfile(size=100, entropy=0.3, term_density=0.2, structural_variance=0.1),
            TaskBusinessProfile(coreness=0.2, risk_score=0.2, sla_priority=0.3, temporal_criticality=False),
            TaskCognitiveProfile(innovation_requirement=0.2, dependency_gap=0.3, is_closed_loop=True, is_fast_pass=False)
        )
        # 直接测试映射（绕过路由逻辑）
        from src.config import config
        assert config.ROUTE_LEVEL_NAMES.get(level) == expected_name
        print(f"[OK] L{level} -> {expected_name}")
    
    return True


def test_scenario_a_translate_nature():
    """测试场景 A：翻译 Nature 学术段落
    
    场景描述：输入一段高难度的学术段落，系统识别出动作是"翻译"，
    但因为检测到熵值极高和学术术语密集，自动把任务扔给 L5 策略。
    """
    print("\n" + "="*60)
    print("测试场景 A：翻译 Nature 学术段落")
    print("="*60)
    
    # 高熵值（学术文本复杂）+ 高术语密度，触发质量提级
    profile = _create_profile(
        TaskPhysicalProfile(size=800, entropy=0.85, term_density=0.75, structural_variance=0.2),
        TaskBusinessProfile(coreness=0.1, risk_score=0.1, sla_priority=0.3, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.2, dependency_gap=0.3, is_closed_loop=True, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    
    print(f"任务描述: 翻译一段 Nature 学术论文段落")
    print(f"路由级别: L{result['level']} ({result['route_name']})")
    print(f"触发规则: {result['triggers']}")
    
    # 高熵+高术语密度触发质量补偿，最终级别应为 L5（逻辑深钻）
    assert result["level"] == 5
    assert result["route_name"] == "逻辑深钻"
    assert "质量补偿" in str(result["triggers"])
    print("[OK] 场景 A 测试通过：高难度学术翻译分配到 L5 逻辑深钻")
    
    return True


def test_scenario_b_modify_core_code():
    """测试场景 B：改动核心代码
    
    场景描述：输入"修改 gateway.py 的重试逻辑"。系统通过图中心度发现 
    gateway.py 是枢纽节点，风险评分瞬间爆表，强制提级到 L6 触发评审。
    """
    print("\n" + "="*60)
    print("测试场景 B：改动核心代码")
    print("="*60)
    
    # gateway.py 是核心枢纽节点，核心度高 + 修改动作（高风险）
    # 风险评分应该达到临界值，触发风险熔断到 L6
    profile = _create_profile(
        TaskPhysicalProfile(size=100, entropy=0.4, term_density=0.3, structural_variance=0.2),
        TaskBusinessProfile(coreness=0.9, risk_score=0.85, sla_priority=0.6, temporal_criticality=True),
        TaskCognitiveProfile(innovation_requirement=0.3, dependency_gap=0.3, is_closed_loop=True, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    
    print(f"任务描述: 修改 gateway.py 的重试逻辑")
    print(f"路由级别: L{result['level']} ({result['route_name']})")
    print(f"触发规则: {result['triggers']}")
    
    # 高危任务应该触发风险熔断到 L6（创意融合）
    assert result["level"] == 6
    assert result["route_name"] == "创意融合"
    assert "风险熔断" in str(result["triggers"])
    print("[OK] 场景 B 测试通过：修改核心代码强制提级到 L6")
    
    return True


def test_scenario_c_ambiguous_instruction():
    """测试场景 C：模糊指令
    
    场景描述：输入一句歧义很大的话。TaskAnalyzer 发现生成的几个草案方差极大，
    系统会自动 +1 级，从 L2 提级到 L3，要求模型进行更深思熟虑的单发回复。
    """
    print("\n" + "="*60)
    print("测试场景 C：模糊指令")
    print("="*60)
    
    # 语义波动率高（歧义大），其他指标中等
    # 不确定性补偿应该触发 +1 级
    profile = _create_profile(
        TaskPhysicalProfile(size=50, entropy=0.3, term_density=0.2, structural_variance=0.5),
        TaskBusinessProfile(coreness=0.2, risk_score=0.2, sla_priority=0.3, temporal_criticality=False),
        TaskCognitiveProfile(innovation_requirement=0.4, dependency_gap=0.5, is_closed_loop=False, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    
    print(f"任务描述: 做一些改进")
    print(f"路由级别: L{result['level']} ({result['route_name']})")
    print(f"触发规则: {result['triggers']}")
    
    # 不确定性补偿应该触发，从基础级别提 1 级到 L3（高价单发）
    assert result["level"] == 3
    assert result["route_name"] == "高价单发"
    assert "不确定性补偿" in str(result["triggers"])
    print("[OK] 场景 C 测试通过：模糊指令触发不确定性补偿，提级到 L3")
    
    return True


def test_combined_scenario():
    """测试组合场景（所有条件都满足）"""
    print("\n" + "="*60)
    print("测试组合场景")
    print("="*60)
    
    # 高熵+高术语密度+高危+高语义波动
    profile = _create_profile(
        TaskPhysicalProfile(size=1500, entropy=0.85, term_density=0.75, structural_variance=0.5),
        TaskBusinessProfile(coreness=0.8, risk_score=0.85, sla_priority=0.85, temporal_criticality=True),
        TaskCognitiveProfile(innovation_requirement=0.8, dependency_gap=0.7, is_closed_loop=False, is_fast_pass=False)
    )
    result = IntentAnalyzer.determine_route_level(profile)
    
    print(f"组合场景路由级别: L{result['level']} ({result['route_name']})")
    print(f"触发规则: {result['triggers']}")
    
    assert result["level"] == 7
    assert "质量补偿" in str(result["triggers"])
    assert "风险熔断" in str(result["triggers"])
    assert "不确定性补偿" in str(result["triggers"])
    print("[OK] 组合场景测试通过")
    
    return True


def main():
    """运行所有测试"""
    print("="*60)
    print("IntentAnalyzer 路由决策矩阵单元测试")
    print("="*60)
    
    results = []
    results.append(test_route_decision())
    results.append(test_route_mapping())
    
    # 运行三个具体场景测试
    print("\n" + "="*60)
    print("=== 具体场景测试 ===")
    print("="*60)
    results.append(test_scenario_a_translate_nature())
    results.append(test_scenario_b_modify_core_code())
    results.append(test_scenario_c_ambiguous_instruction())
    
    results.append(test_combined_scenario())
    
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if all(results):
        print("所有测试通过！")
        return 0
    else:
        print("部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
