# test_dual_engine.py
# 测试双引擎路由功能

import asyncio
import httpx
import json

async def test_fast_route():
    """测试快速路由模式"""
    url = "http://localhost:8001/v1/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "model": "aagent-fast",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            print("=" * 60)
            print("测试快速路由模式 (aagent-fast)")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"模型: {result.get('model')}")
            print(f"响应: {result.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]}...")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            return None

async def test_reasoning_mode_by_model():
    """通过模型名称测试深度推理模式"""
    url = "http://localhost:8001/v1/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "model": "aagent-reasoning",
        "messages": [
            {"role": "user", "content": "请分析一下人工智能对未来就业市场的影响"}
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            print("\n" + "=" * 60)
            print("测试深度推理模式 (model=aagent-reasoning)")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"模型: {result.get('model')}")
            print(f"响应: {result.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]}...")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            return None

async def test_reasoning_mode_by_header():
    """通过请求头测试深度推理模式"""
    url = "http://localhost:8001/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "X-Aagent-Mode": "deep"
    }

    data = {
        "model": "auto",
        "messages": [
            {"role": "user", "content": "请分析一下人工智能对未来就业市场的影响"}
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            print("\n" + "=" * 60)
            print("测试深度推理模式 (X-Aagent-Mode: deep)")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"模型: {result.get('model')}")
            print(f"响应: {result.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]}...")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            return None

async def test_default_mode():
    """测试默认模式（应该走快速路由）"""
    url = "http://localhost:8001/v1/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "model": "auto",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            print("\n" + "=" * 60)
            print("测试默认模式 (auto)")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"模型: {result.get('model')}")
            print(f"响应: {result.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]}...")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            return None

async def main():
    """主测试函数"""
    print("\n开始测试双引擎路由功能...\n")

    # 测试快速路由模式
    await test_fast_route()
    
    # 测试默认模式
    await test_default_mode()
    
    # 测试深度推理模式（通过模型名称）
    await test_reasoning_mode_by_model()
    
    # 测试深度推理模式（通过请求头）
    await test_reasoning_mode_by_header()

    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())
