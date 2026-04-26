# comprehensive_test.py - 饱和测试脚本
# 测试系统在高负载下的稳定性

import asyncio
import time
import concurrent.futures
import sys
import os
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.orchestrator import AsyncRealOrchestrator
from src.data.memory import Memory

async def test_memory_performance():
    """测试记忆系统性能"""
    print("=== 测试记忆系统性能 ===")
    memory = Memory()
    
    # 测试添加大量经验
    start_time = time.time()
    for i in range(100):
        await memory.add_experience(f"测试输入 {i}", f"测试响应 {i}")
    end_time = time.time()
    print(f"添加 100 条经验耗时: {end_time - start_time:.2f} 秒")
    
    # 测试检索性能
    start_time = time.time()
    for i in range(10):
        result = await memory.retrieve(f"测试 {i}")
    end_time = time.time()
    print(f"检索 10 次耗时: {end_time - start_time:.2f} 秒")
    
    # 测试知识图谱性能
    start_time = time.time()
    graph = await memory.get_knowledge_graph()
    end_time = time.time()
    print(f"获取知识图谱耗时: {end_time - start_time:.2f} 秒")
    print(f"知识图谱节点数: {len(graph['nodes'])}, 边数: {len(graph['edges'])}")

async def test_orchestrator_performance():
    """测试编排器性能"""
    print("\n=== 测试编排器性能 ===")
    
    # 测试单任务执行
    orchestrator = AsyncRealOrchestrator()
    start_time = time.time()
    result = await orchestrator.start_work("编写一个简单的Python函数，计算斐波那契数列")
    end_time = time.time()
    print(f"单任务执行耗时: {end_time - start_time:.2f} 秒")
    print(f"任务结果长度: {len(result)}")

async def test_concurrent_tasks():
    """测试并发任务处理"""
    print("\n=== 测试并发任务处理 ===")
    
    tasks = [
        "编写一个Python函数，计算阶乘",
        "编写一个Python函数，计算平方和",
        "编写一个Python函数，判断素数",
        "编写一个Python函数，反转字符串",
        "编写一个Python函数，计算最大公约数"
    ]
    
    start_time = time.time()
    orchestrators = [AsyncRealOrchestrator() for _ in tasks]
    results = await asyncio.gather(
        *[orchestrator.start_work(task) for orchestrator, task in zip(orchestrators, tasks)]
    )
    end_time = time.time()
    print(f"并发执行 {len(tasks)} 个任务耗时: {end_time - start_time:.2f} 秒")
    print(f"所有任务都完成: {all(len(result) > 0 for result in results)}")

async def test_checkpoint_performance():
    """测试检查点性能"""
    print("\n=== 测试检查点性能 ===")
    
    orchestrator = AsyncRealOrchestrator()
    
    # 运行任务并创建检查点
    start_time = time.time()
    result = await orchestrator.start_work("编写一个复杂的Python函数，实现二分查找")
    end_time = time.time()
    print(f"任务执行耗时: {end_time - start_time:.2f} 秒")
    
    # 列出检查点
    checkpoints = orchestrator.list_checkpoints()
    print(f"创建的检查点数: {len(checkpoints)}")
    
    if checkpoints:
        # 测试从检查点恢复
        checkpoint_id = checkpoints[0]['checkpoint_id']
        start_time = time.time()
        resume_result = await orchestrator.resume_work(checkpoint_id)
        end_time = time.time()
        print(f"从检查点恢复耗时: {end_time - start_time:.2f} 秒")
        print(f"恢复结果长度: {len(resume_result)}")

async def test_memory_persistence():
    """测试记忆持久性"""
    print("\n=== 测试记忆持久性 ===")
    
    # 创建第一个记忆系统并添加经验
    memory1 = Memory()
    for i in range(50):
        await memory1.add_experience(f"持久化测试输入 {i}", f"持久化测试响应 {i}")
    
    # 创建第二个记忆系统，验证记忆是否共享
    memory2 = Memory()
    result = await memory2.retrieve("持久化测试")
    print(f"从新记忆系统检索到的结果数: {len(result) if result else 0}")

async def main():
    """主测试函数"""
    print("开始执行饱和测试...")
    
    # 运行所有测试
    await test_memory_performance()
    await test_orchestrator_performance()
    await test_concurrent_tasks()
    await test_checkpoint_performance()
    await test_memory_persistence()
    
    print("\n饱和测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
