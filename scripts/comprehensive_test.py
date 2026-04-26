#!/usr/bin/env python3
# scripts/comprehensive_test.py
import os
import sys
import asyncio
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.orchestrator import AsyncRealOrchestrator

async def test_docker_sandbox():
    """测试 Docker 容器化沙箱"""
    print("\n=== 测试 Docker 容器化沙箱 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 测试简单代码执行
    code = "result = 1 + 1"
    output = await orchestrator.sandbox.execute_code(code)
    print(f"简单代码执行: {output}")
    
    # 测试耗时较长的代码（应该被超时限制）
    code = "import time; time.sleep(15); result = '超时测试'"
    output = await orchestrator.sandbox.execute_code(code)
    print(f"超时测试: {output}")
    
    # 测试复杂代码
    code = """
result = []
for i in range(10):
    result.append(i * i)
result
"""
    output = await orchestrator.sandbox.execute_code(code)
    print(f"复杂代码执行: {output}")

async def test_state_machine():
    """测试状态机编排"""
    print("\n=== 测试状态机编排 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 测试分析 -> 执行流程
    result = await orchestrator.start_work("写一个简单的 Python 函数，计算斐波那契数列的第 10 项")
    print("状态机测试完成")

async def test_semantic_cache():
    """测试语义缓存"""
    print("\n=== 测试语义缓存 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 第一次请求（应该触发 API 调用）
    start_time = time.time()
    await orchestrator.start_work("什么是 Python 装饰器？")
    first_time = time.time() - start_time
    print(f"第一次请求耗时: {first_time:.2f} 秒")
    
    # 第二次请求（应该命中缓存）
    start_time = time.time()
    await orchestrator.start_work("Python 装饰器的作用是什么？")
    second_time = time.time() - start_time
    print(f"第二次请求耗时: {second_time:.2f} 秒")
    
    if second_time < first_time * 0.5:
        print("[OK] 语义缓存工作正常")
    else:
        print("[ERROR] 语义缓存可能未生效")

async def test_complete_workflow():
    """测试完整工作流"""
    print("\n=== 测试完整工作流 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 测试代码生成任务
    print("\n测试 1: 代码生成任务")
    await orchestrator.start_work("写一个 Python 函数，实现快速排序算法")
    
    # 测试分析任务
    print("\n测试 2: 分析任务")
    await orchestrator.start_work("分析 Python 中列表推导式的优缺点")
    
    # 测试创意任务
    print("\n测试 3: 创意任务")
    await orchestrator.start_work("为一个在线学习平台设计 5 个功能模块")

async def main():
    """主测试函数"""
    print("开始综合测试...")
    
    try:
        await test_docker_sandbox()
        await test_state_machine()
        await test_semantic_cache()
        await test_complete_workflow()
        print("\n[SUCCESS] 所有测试完成！")
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())