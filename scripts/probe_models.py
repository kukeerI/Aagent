# probe_models.py - 模型可用性探测脚本
# 运行方式: python probe_models.py
# 注意：需要先确保 Redis 和数据库已初始化

import asyncio
import os
import time
from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError
from sqlalchemy import select, delete
from src.database import AsyncSessionLocal, APIAsset, init_db

load_dotenv()

# 定义所有平台的模型配置
# 格式: (provider, model_name, base_url, domain_skill, rpm_limit)
PLATFORM_MODELS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            ("deepseek-chat", "Logic", 60),
            ("deepseek-chat", "Coding", 60),
            ("deepseek-chat", "Fast", 120),
            ("deepseek-reasoner", "Logic", 30),
        ]
    },
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            ("llama-3.3-70b-versatile", "Logic", 30),
            ("llama-3.1-8b-instant", "Fast", 30),
            ("mixtral-8x7b-32768", "Coding", 30),
            ("gemma-7b-it", "Fast", 30),
        ]
    },
    "cerebras": {
        "api_key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "models": [
            ("llama3.1-8b", "Fast", 30),
            ("qwen-3-235b-a22b-instruct-2507", "Logic", 5),
        ]
    },
    "mistral": {
        "api_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "models": [
            ("mistral-large-latest", "Logic", 60),
            ("mistral-small-latest", "Fast", 60),
            ("codestral-latest", "Coding", 60),
            ("mixtral-8x22b-instruct", "Coding", 30),
        ]
    },
    "togetherai": {
        "api_key_env": "TOGETHERAI_API_KEY",
        "base_url": "https://api.together.ai/v1",
        "models": [
            ("meta-llama/Llama-3.3-70B-Instruct", "Logic", 30),
            ("meta-llama/Llama-3.2-3B-Instruct", "Fast", 60),
            ("NousResearch/Hermes-3-405B", "Logic", 5),
            ("Qwen/Qwen2.5-72B-Instruct", "Logic", 20),
        ]
    },
    "openrouter": {
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            ("google/gemma-3-4b-it", "Fast", 60),
            ("google/gemma-3-12b-it", "Logic", 60),
            ("google/gemma-3-27b-it", "Logic", 30),
            ("meta-llama/llama-3.3-70b-instruct", "Logic", 30),
            ("nousresearch/hermes-3-405b", "Logic", 5),
        ]
    },
    "sambanova": {
        "api_key_env": "SAMBANOVA_API_KEY",
        "base_url": "https://api.sambanext.com/v1",
        "models": [
            ("Meta-Llama-3.3-70B-Instruct", "Logic", 60),
            ("Qwen-2.5-72B-Instruct", "Logic", 60),
            ("MiniMax-M2.1-8k", "Fast", 60),
            ("DeepSeek-V3.1-128K", "Logic", 30),
        ]
    },
    "aistudio": {
        "api_key_env": "AISTUDIO_API_KEY",
        "base_url": "https://aistudio.googleapis.com/v1beta",
        "models": [
            ("gemini-2.5-flash", "Fast", 60),
            ("gemini-2.0-flash", "Fast", 60),
            ("gemini-2.0-flash-lite", "Fast", 60),
            ("gemini-1.5-pro", "Logic", 60),
            ("gemini-1.5-flash", "Fast", 60),
            ("gemini-1.5-flash-8b", "Fast", 60),
        ]
    }
}

# 文字类模型关键词（包含这些关键词的不测试）
TEXT_ONLY_KEYWORDS = ["generate", "tts", "audio", "video", "image", "veo", "imagen", "lyria", "embedding"]

def is_text_model(model_name: str) -> bool:
    """检查是否是文字类模型"""
    model_lower = model_name.lower()
    for keyword in TEXT_ONLY_KEYWORDS:
        if keyword in model_lower:
            return False
    return True

async def test_model(client: AsyncOpenAI, model_name: str) -> tuple[bool, str]:
    """测试单个模型是否可用"""
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10,
            timeout=30
        )
        if response and response.choices:
            return True, "OK"
        return False, "Empty response"
    except RateLimitError as e:
        return False, f"Rate limit: {str(e)[:50]}"
    except Exception as e:
        error_msg = str(e)
        # 提取关键错误信息
        if "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
            return False, "Invalid API key"
        if "model" in error_msg.lower() or "not found" in error_msg.lower():
            return False, "Model not found"
        if "context" in error_msg.lower() or "length" in error_msg.lower():
            return False, "Context length issue"
        return False, error_msg[:80]

async def test_platform(platform_name: str, config: dict) -> list[dict]:
    """测试单个平台的所有模型"""
    api_key = os.getenv(config["api_key_env"])
    if not api_key:
        print(f"  [{platform_name}] 无 API 密钥，跳过")
        return []

    base_url = config["base_url"]
    print(f"  [{platform_name}] 开始测试 ({len(config['models'])} 个模型)...")

    results = []
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    for model_name, domain_skill, rpm_limit in config["models"]:
        if not is_text_model(model_name):
            print(f"    - {model_name}: 跳过（非文字模型）")
            continue

        print(f"    - {model_name}: 测试中...", end=" ")
        success, message = await test_model(client, model_name)

        if success:
            print(f"OK!")
            results.append({
                "provider": platform_name,
                "model_name": model_name,
                "domain_skill": domain_skill,
                "rpm_limit": rpm_limit,
                "api_key": config["api_key_env"],
                "provider_url": base_url,
                "status": "ACTIVE"
            })
        else:
            print(f"失败 ({message})")

        # 每个模型测试后等待，避免触发限流
        await asyncio.sleep(1)

    return results

async def clear_old_data():
    """清除旧的API资产数据"""
    async with AsyncSessionLocal() as session:
        await session.execute(delete(APIAsset))
        await session.commit()
    print("[数据库] 已清除旧数据")

async def main():
    print("=" * 60)
    print("模型可用性探测脚本")
    print("=" * 60)

    # 初始化数据库
    await init_db()

    # 清除旧数据
    await clear_old_data()

    # 并行测试所有平台（不同平台可以并行）
    print("\n开始探测模型可用性...\n")

    tasks = [test_platform(name, config) for name, config in PLATFORM_MODELS.items()]
    all_results = await asyncio.gather(*tasks)

    # 收集成功的模型
    valid_models = []
    for platform_results in all_results:
        valid_models.extend(platform_results)

    # 写入数据库
    print(f"\n写入数据库... ({len(valid_models)} 个可用模型)")
    async with AsyncSessionLocal() as session:
        for model_data in valid_models:
            asset = APIAsset(**model_data)
            session.add(asset)
        await session.commit()

    # 打印结果汇总
    print("\n" + "=" * 60)
    print("探测完成！可用模型汇总：")
    print("=" * 60)

    by_provider = {}
    for m in valid_models:
        provider = m["provider"]
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(m["model_name"])

    for provider, models in sorted(by_provider.items()):
        print(f"\n[{provider}] ({len(models)} 个模型)")
        for model in models:
            print(f"  - {model}")

    print(f"\n总计: {len(valid_models)} 个可用模型")
    print("=" * 60)

    # 同时更新 Redis 节点池
    print("\n更新 Redis 节点池...")
    import redis.asyncio as redis
    r = redis.from_url('redis://localhost:6379/0', decode_responses=True)

    # 清除旧节点
    await r.delete("ActivePool:Logic", "ActivePool:Coding", "ActivePool:Search", "ActivePool:Creative", "ActivePool:Fast")

    # 按 domain_skill 分组注册节点
    node_id = 1
    for model_data in valid_models:
        domain = model_data["domain_skill"]
        await r.hset(f"ActivePool:{domain}", str(node_id), str(model_data["rpm_limit"]))
        node_id += 1

    await r.aclose()
    print(f"已注册 {node_id - 1} 个节点到 Redis")

if __name__ == "__main__":
    asyncio.run(main())
