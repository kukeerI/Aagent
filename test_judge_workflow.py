# test_judge_workflow.py
# 测试四步 AI 裁判工作流

import asyncio
import json
from src.core.orchestrator import AsyncRealOrchestrator

async def test_judge_workflow():
    """测试四步 AI 裁判工作流"""
    print("开始测试四步 AI 裁判工作流...")
    
    # 创建测试草稿
    test_drafts = [
        "我认为人工智能将在未来 10 年内完全取代人类的工作。根据最新的研究，AI 的能力已经超越了人类在许多领域的表现，包括数学、语言和视觉识别。",
        "人工智能在未来会对人类工作产生重大影响，但不会完全取代人类。AI 更适合处理重复性和计算密集型任务，而人类在创造性、情感理解和复杂决策方面仍有优势。",
        "人工智能的发展速度确实很快，但要完全取代人类工作还需要很长时间。目前的 AI 系统缺乏真正的理解能力和创造力，只能在特定领域内表现出色。"
    ]
    
    # 模拟节点
    test_nodes = [
        {
            "node_id": 1,
            "model_name": "gpt-4",
            "base_url": "https://api.openai.com/v1",
            "api_key": "test_key"
        }
    ]
    
    # 创建 orchestrator
    orchestrator = AsyncRealOrchestrator()
    
    try:
        # 调用四步裁判工作流
        final_answer, need_human_intervention = await orchestrator._four_step_judge_workflow(test_drafts, test_nodes, "test-trace-id")
        
        print("\n测试结果:")
        print(f"最终答案: {final_answer[:200].encode('utf-8', 'ignore').decode('gbk', 'ignore')}...")
        print(f"是否需要人工干预: {need_human_intervention}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_reasoning_flow():
    """测试完整的推理流程"""
    print("\n开始测试完整的推理流程...")
    
    # 创建测试消息
    test_messages = [
        {"role": "user", "content": "人工智能对未来就业市场的影响是什么？"}
    ]
    
    # 创建 orchestrator
    orchestrator = AsyncRealOrchestrator()
    
    try:
        # 调用推理流程
        result = await orchestrator.run_reasoning_flow(test_messages)
        
        print("\n推理结果:")
        print(result)
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    await test_judge_workflow()
    # await test_reasoning_flow()

if __name__ == "__main__":
    asyncio.run(main())
