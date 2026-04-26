#!/usr/bin/env python3
# examples/usage_example.py
"""
Aagent 使用示例

本示例展示如何使用 Aagent 框架的核心功能：
1. 基本任务执行
2. 代码生成与执行
3. 状态机编排
4. 语义缓存
5. 全链路追踪
"""
import os
import sys
import asyncio

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.orchestrator import AsyncRealOrchestrator

async def basic_task_example():
    """基本任务执行示例"""
    print("\n=== 基本任务执行示例 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 执行一个简单的问题
    await orchestrator.start_work("什么是人工智能？")

async def code_generation_example():
    """代码生成示例"""
    print("\n=== 代码生成示例 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 生成并执行代码
    await orchestrator.start_work("写一个 Python 函数，计算圆的面积，输入半径")

async def complex_analysis_example():
    """复杂分析示例"""
    print("\n=== 复杂分析示例 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 执行复杂的分析任务
    await orchestrator.start_work("分析 Python 中 asyncio 的工作原理，以及与多线程的区别")

async def creative_task_example():
    """创意任务示例"""
    print("\n=== 创意任务示例 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 执行创意生成任务
    await orchestrator.start_work("为一个智能客服系统设计 5 个核心功能")

async def semantic_cache_example():
    """语义缓存示例"""
    print("\n=== 语义缓存示例 ===")
    orchestrator = AsyncRealOrchestrator()
    
    # 第一次请求
    print("\n第一次请求:")
    await orchestrator.start_work("什么是机器学习？")
    
    # 第二次语义相似请求（应该命中缓存）
    print("\n第二次请求（语义相似）:")
    await orchestrator.start_work("机器学习的定义是什么？")

async def main():
    """主函数"""
    print("Aagent 使用示例")
    print("=" * 50)
    
    try:
        await basic_task_example()
        await code_generation_example()
        await complex_analysis_example()
        await creative_task_example()
        await semantic_cache_example()
        
        print("\n" + "=" * 50)
        print("🎉 所有示例执行完成！")
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())