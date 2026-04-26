# test_openai_shim.py
# 测试 OpenAI 兼容接口

import asyncio
import httpx
import json

async def test_chat_completions():
    """测试聊天补全接口"""
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
            print("=" * 60)
            print("测试 /v1/chat/completions")
            print("=" * 60)
            print(f"请求: {json.dumps(data, ensure_ascii=False, indent=2)}")
            print(f"\n响应:")
            print(f"ID: {result.get('id')}")
            print(f"Model: {result.get('model')}")
            print(f"Choices:")
            for choice in result.get('choices', []):
                print(f"  - {choice.get('message', {}).get('content', '')[:200]}...")
            print(f"Usage: {result.get('usage')}")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            return None

async def test_models():
    """测试模型列表接口"""
    url = "http://localhost:8001/v1/models"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            print("\n" + "=" * 60)
            print("测试 /v1/models")
            print("=" * 60)
            print(f"模型数量: {len(result.get('data', []))}")
            print("模型列表:")
            for model in result.get('data', []):
                print(f"  - {model.get('id')}")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            return None

async def test_health():
    """测试健康检查接口"""
    url = "http://localhost:8001/health"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            print("\n" + "=" * 60)
            print("测试 /health")
            print("=" * 60)
            print(f"状态: {result.get('status')}")
            print(f"服务: {result.get('service')}")
            print("=" * 60)
            return result
        except Exception as e:
            print(f"错误: {e}")
            return None

async def main():
    """主测试函数"""
    print("\n开始测试 OpenAI 兼容接口...\n")

    await test_health()
    await test_models()
    await test_chat_completions()

    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())
