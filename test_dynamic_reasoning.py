#!/usr/bin/env python3
# 测试动态推理流

import asyncio
from src.core.orchestrator import AsyncRealOrchestrator
from src.core.intent_analyzer import IntentAnalyzer

async def test_dynamic_reasoning():
    print("=== 测试动态推理流 ===")
    
    # 创建 orchestrator 实例
    orchestrator = AsyncRealOrchestrator()
    
    # 测试用例 1: 工具/代码类任务
    task1 = "编写一个 Python 函数来计算斐波那契数列的第 n 项"
    print(f"\n测试 1: 工具/代码类任务\n任务: {task1}")
    task_type1 = IntentAnalyzer.classify_task_type(task1)
    print(f"任务类型: {task_type1}")
    
    # 测试用例 2: 逻辑/推演类任务
    task2 = "分析为什么 Python 中的列表是可变的，而元组是不可变的"
    print(f"\n测试 2: 逻辑/推演类任务\n任务: {task2}")
    task_type2 = IntentAnalyzer.classify_task_type(task2)
    print(f"任务类型: {task_type2}")
    
    # 测试用例 3: 文本/方案类任务
    task3 = "写一篇关于人工智能发展趋势的短文"
    print(f"\n测试 3: 文本/方案类任务\n任务: {task3}")
    task_type3 = IntentAnalyzer.classify_task_type(task3)
    print(f"任务类型: {task_type3}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_dynamic_reasoning())
