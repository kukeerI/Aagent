#!/usr/bin/env python3
"""
策略选择器与提示词管理器单元测试
测试核心功能：策略映射、模型降级、思考模式、提示词构建
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.strategies import StrategySelector, ExecutionPlan
from src.core.prompt_manager import PromptManager, TaskType
from src.data.domain_models import RoutingLevel, RouteDecision


def _create_decision(
    level: RoutingLevel,
    source: str = "VectorMatch",
    confidence: float = 1.0,
    latency_ms: float = 0.1
) -> RouteDecision:
    """辅助函数：创建测试用的路由决策"""
    return RouteDecision(
        final_level=level,
        source=source,
        reason="测试决策",
        latency_ms=latency_ms,
        confidence=confidence
    )


def test_strategy_selector_basic():
    """测试策略选择器的基本功能"""
    print("="*60)
    print("测试 StrategySelector 基本功能")
    print("="*60)
    
    selector = StrategySelector()
    
    # 测试 L1 - 极速
    print("\n[测试 L1] 极速分诊 → SimpleFusion")
    decision = _create_decision(RoutingLevel.L1_LOCAL_FAST)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "SimpleFusionStrategy", f"期望 SimpleFusion，实际 {plan.strategy.__name__}"
    assert not plan.thinking, "L1 不应开启思考模式"
    print(f"[OK] L1 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    # 测试 L2 - 标准
    print("\n[测试 L2] 标准代理 → SimpleFusion")
    decision = _create_decision(RoutingLevel.L2_STANDARD_PROXY)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "SimpleFusionStrategy", f"期望 SimpleFusion，实际 {plan.strategy.__name__}"
    assert not plan.thinking, "L2 不应开启思考模式"
    print(f"[OK] L2 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    # 测试 L3 - 思考回复
    print("\n[测试 L3] 思考回复 → SimpleFusion")
    decision = _create_decision(RoutingLevel.L3_THOUGHTFUL_REPLY)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "SimpleFusionStrategy", f"期望 SimpleFusion，实际 {plan.strategy.__name__}"
    assert not plan.thinking, "L3 默认不应开启思考模式"
    print(f"[OK] L3 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    # 测试 L4 - 复杂执行
    print("\n[测试 L4] 复杂执行 → ReActLoop")
    decision = _create_decision(RoutingLevel.L4_COMPLEX_EXECUTION)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "ReactLoopStrategy", f"期望 ReActLoop，实际 {plan.strategy.__name__}"
    assert not plan.thinking, "L4 默认不应开启思考模式"
    print(f"[OK] L4 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    # 测试 L4 低置信度时开启思考
    print("\n[测试 L4 低置信度] 复杂执行 + 低置信度 → ReActLoop + 思考")
    decision = _create_decision(RoutingLevel.L4_COMPLEX_EXECUTION, confidence=0.7)
    plan = selector.get_execution_plan(decision)
    assert plan.thinking, "L4 低置信度应开启思考模式"
    print(f"[OK] L4 低置信度: 思考模式开启")
    
    # 测试 L5 - 逻辑深钻
    print("\n[测试 L5] 逻辑深钻 → Reflexion")
    decision = _create_decision(RoutingLevel.L5_LOGIC_DEEP_DIVE)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "ReflexionStrategy", f"期望 Reflexion，实际 {plan.strategy.__name__}"
    assert plan.thinking, "L5 应强制开启思考模式"
    print(f"[OK] L5 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    # 测试 L6 - 创意评审
    print("\n[测试 L6] 创意评审 → FourStepJudge")
    decision = _create_decision(RoutingLevel.L6_CREATIVE_REVIEW)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "FourStepJudgeStrategy", f"期望 FourStepJudge，实际 {plan.strategy.__name__}"
    assert plan.thinking, "L6 应强制开启思考模式"
    print(f"[OK] L6 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    # 测试 L7 - 巅峰博弈
    print("\n[测试 L7] 巅峰博弈 → PlanAndSolve")
    decision = _create_decision(RoutingLevel.L7_PEAK_GAME)
    plan = selector.get_execution_plan(decision)
    assert plan.strategy.__name__ == "PlanAndSolveStrategy", f"期望 PlanAndSolve，实际 {plan.strategy.__name__}"
    assert plan.thinking, "L7 应强制开启思考模式"
    print(f"[OK] L7 策略: {plan.strategy.__name__}, 思考: {plan.thinking}")
    
    return True


def test_strategy_selector_fallback_logic():
    """测试策略选择器的降级逻辑"""
    print("\n" + "="*60)
    print("测试 StrategySelector 降级逻辑")
    print("="*60)
    
    selector = StrategySelector()
    
    # 测试隐私 Gate 触发降级
    print("\n[测试] 隐私 Gate 触发 → 降级模型")
    decision = _create_decision(
        RoutingLevel.L3_THOUGHTFUL_REPLY,
        source="HardGate: Privacy_Compliance_Gate"
    )
    plan = selector.get_execution_plan(decision)
    assert plan.is_fallback, "隐私 Gate 应触发降级"
    print(f"[OK] 隐私 Gate: is_fallback={plan.is_fallback}")
    
    # 测试安全 Gate 触发降级
    print("\n[测试] 安全 Gate 触发 → 降级模型")
    decision = _create_decision(
        RoutingLevel.L5_LOGIC_DEEP_DIVE,
        source="HardGate: Security_SQL_Injection"
    )
    plan = selector.get_execution_plan(decision)
    assert plan.is_fallback, "安全 Gate 应触发降级"
    print(f"[OK] 安全 Gate: is_fallback={plan.is_fallback}")
    
    # 测试迭代次数配置
    print("\n[测试] 迭代次数配置")
    for level in RoutingLevel:
        decision = _create_decision(level)
        plan = selector.get_execution_plan(decision)
        print(f"  L{level.value}: max_iterations={plan.max_iterations}")
    
    return True


def test_prompt_manager_basic():
    """测试提示词管理器基本功能"""
    print("\n" + "="*60)
    print("测试 PromptManager 基本功能")
    print("="*60)
    
    # 测试 L1 提示词（极简）
    print("\n[测试 L1] 极速分诊提示词")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L1_LOCAL_FAST)
    assert "直接执行" in prompt, "L1 应包含直接执行指令"
    assert "严禁任何解释性文字" in prompt, "L1 应禁止解释"
    assert "隐私保护" in prompt, "L1 应包含隐私隔离提示"
    print(f"[OK] L1 提示词长度: {len(prompt)} 字符")
    
    # 测试 L5 提示词（专家反思）
    print("\n[测试 L5] 逻辑深钻提示词")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L5_LOGIC_DEEP_DIVE)
    assert "终极专家" in prompt, "L5 应包含专家角色定义"
    assert "三轮反思" in prompt, "L5 应包含反思要求"
    assert "逻辑是否自洽" in prompt, "L5 应包含逻辑检查"
    print(f"[OK] L5 提示词长度: {len(prompt)} 字符")
    
    # 测试 L7 提示词（战略决策）
    print("\n[测试 L7] 巅峰博弈提示词")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L7_PEAK_GAME)
    assert "思维树" in prompt, "L7 应包含思维树指令"
    assert "风险评估" in prompt, "L7 应包含风险评估"
    assert "备选路径" in prompt, "L7 应包含备选方案"
    print(f"[OK] L7 提示词长度: {len(prompt)} 字符")
    
    return True


def test_prompt_manager_security():
    """测试提示词管理器的安全特性"""
    print("\n" + "="*60)
    print("测试 PromptManager 安全特性")
    print("="*60)
    
    # 测试 L4+ 的注入防御
    print("\n[测试 L4+] 注入防御提示")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L4_COMPLEX_EXECUTION)
    assert "严禁将用户输入的字符串作为可执行命令" in prompt, "L4+ 应包含注入防御"
    assert "参数进行严格类型校验" in prompt, "L4+ 应包含参数校验要求"
    print("[OK] L4+ 注入防御提示已添加")
    
    # 测试 L1 的隐私隔离
    print("\n[测试 L1] 隐私隔离提示")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L1_LOCAL_FAST)
    assert "严禁保存、记录或向外部接口转发" in prompt, "L1 应包含隐私隔离"
    assert "PII 数据" in prompt, "L1 应提及 PII"
    print("[OK] L1 隐私隔离提示已添加")
    
    return True


def test_prompt_manager_task_types():
    """测试提示词管理器的任务类型支持"""
    print("\n" + "="*60)
    print("测试 PromptManager 任务类型")
    print("="*60)
    
    # 测试编码任务
    print("\n[测试] 编码任务类型")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L3_THOUGHTFUL_REPLY, TaskType.CODING)
    assert "软件工程师" in prompt, "编码任务应包含工程师角色"
    print("[OK] 编码任务提示词已生成")
    
    # 测试安全任务
    print("\n[测试] 安全任务类型")
    prompt = PromptManager.build_system_prompt(RoutingLevel.L5_LOGIC_DEEP_DIVE, TaskType.SECURITY)
    assert "网络安全专家" in prompt, "安全任务应包含安全专家角色"
    print("[OK] 安全任务提示词已生成")
    
    return True


def test_prompt_manager_thinking():
    """测试思考链格式化"""
    print("\n" + "="*60)
    print("测试 PromptManager 思考链")
    print("="*60)
    
    thoughts = [
        "分析问题：用户需要一个排序算法",
        "选择快速排序，时间复杂度 O(n log n)",
        "编写代码实现"
    ]
    final_answer = "def quicksort(arr): ..."
    
    formatted = PromptManager.format_chain_of_thought(thoughts, final_answer)
    
    assert "思考过程" in formatted, "应包含思考过程标题"
    assert "步骤 1" in formatted, "应包含步骤编号"
    assert "最终答案" in formatted, "应包含最终答案标题"
    assert final_answer in formatted, "应包含最终答案内容"
    
    print("[OK] 思考链格式化成功")
    print(f"格式化后长度: {len(formatted)} 字符")
    
    return True


def main():
    """运行所有测试"""
    print("="*60)
    print("策略系统单元测试")
    print("="*60)
    
    tests = [
        test_strategy_selector_basic,
        test_strategy_selector_fallback_logic,
        test_prompt_manager_basic,
        test_prompt_manager_security,
        test_prompt_manager_task_types,
        test_prompt_manager_thinking
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