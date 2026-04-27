# test_fast_route.py
# 测试快速路由模式

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
            {"role": "user", "content": "你好，请简单介绍一下你自己"}
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            print("测试快速路由模式...")
            response = await client.post(url, headers=headers, json=data, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            print("=" * 60)
            print("测试快速路由模式 (aagent-fast)")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"模型: {result.get('model')}")
            print(f"响应:")
            print(result.get('choices', [{}])[0].get('message', {}).get('content', ''))
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            return None

async def test_health_check():
    """测试健康检查"""
    url = "http://localhost:8001/health"

    async with httpx.AsyncClient() as client:
        try:
            print("测试健康检查...")
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            print("=" * 60)
            print("测试健康检查")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"状态: {result.get('status')}")
            print(f"服务: {result.get('service')}")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            return None

async def test_models():
    """测试模型列表"""
    url = "http://localhost:8001/v1/models"

    async with httpx.AsyncClient() as client:
        try:
            print("测试模型列表...")
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            print("=" * 60)
            print("测试模型列表")
            print("=" * 60)
            print(f"状态码: {response.status_code}")
            print(f"模型数量: {len(result.get('data', []))}")
            print("模型列表:")
            for model in result.get('data', []):
                print(f"  - {model.get('id')}")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            return None

async def main():
    """主测试函数"""
    print("\n开始测试双引擎路由功能...\n")

    # 测试健康检查
    await test_health_check()
    
    # 测试模型列表
    await test_models()
    
    # 测试快速路由模式
    await test_fast_route()

    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())
