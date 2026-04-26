# register_lmstudio.py - LM Studio 本地模型注册脚本
# 运行方式: python register_lmstudio.py
# 注意：需要先确保 LM Studio 已启动并加载模型

import asyncio
import os
import aiohttp
from dotenv import load_dotenv
from sqlalchemy import select, delete
from src.database import AsyncSessionLocal, APIAsset, init_db

load_dotenv()

# LM Studio 配置
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
LMSTUDIO_API_KEY = "lm-studio"  # LM Studio 通常不需要真实的 API key

async def check_lmstudio_connection():
    """检查 LM Studio 是否可用"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{LMSTUDIO_BASE_URL}/models",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"[LM Studio] 连接成功！")
                    return True, data.get("data", [])
                return False, []
    except Exception as e:
        print(f"[LM Studio] 连接失败: {e}")
        return False, []

async def test_lmstudio_model(model_name: str) -> tuple[bool, str]:
    """测试 LM Studio 模型是否可用"""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{LMSTUDIO_BASE_URL}/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Say 'OK' in one word"}],
                    "max_tokens": 10
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return True, data.get("choices", [{}])[0].get("message", {}).get("content", "OK")
                error = await resp.text()
                return False, f"Status {resp.status}: {error[:100]}"
    except asyncio.TimeoutError:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)[:50]

async def register_lmstudio_models():
    """注册 LM Studio 模型到数据库"""
    print("=" * 60)
    print("LM Studio 本地模型注册")
    print("=" * 60)

    # 1. 检查连接
    print("\n[1] 检查 LM Studio 连接...")
    connected, models = await check_lmstudio_connection()
    if not connected:
        print("错误: 无法连接到 LM Studio！")
        print("请确保：")
        print("  1. LM Studio 已启动")
        print("  2. 已加载 Gemma-4-e4b 模型")
        print("  3. API Server 已开启 (通常在 localhost:1234)")
        return

    if models:
        print(f"发现 {len(models)} 个模型:")
        for m in models:
            model_id = m.get('id', 'unknown')
            # 提取不带供应商前缀的名称
            if '/' in model_id:
                clean_name = model_id.split('/')[-1]
            else:
                clean_name = model_id
            print(f"  - {model_id} (clean: {clean_name})")

    # 2. 初始化数据库
    print("\n[2] 初始化数据库...")
    await init_db()

    # 3. 清除旧的 LM Studio 数据（如果存在）
    print("\n[3] 清除旧的 LM Studio 数据...")
    async with AsyncSessionLocal() as session:
        await session.execute(delete(APIAsset).where(APIAsset.provider == "lmstudio"))
        await session.commit()

    # 4. 获取 LM Studio 可用的模型并测试注册
    print("\n[4] 测试并注册模型...")

    # 获取模型列表中的实际名称
    available_models = []
    for m in models:
        model_id = m.get('id', '')
        if '/' in model_id:
            clean_name = model_id.split('/')[-1]
        else:
            clean_name = model_id
        available_models.append(clean_name)

    # 默认配置 - 如果获取不到列表则使用
    if not available_models:
        available_models = ["gemma-4-e4b", "nemotron-3-nano-4b", "qwen3.5-9b"]

    # 测试每个模型
    success_models = []
    for model_name in available_models:
        # 跳过 embedding 模型
        if "embedding" in model_name.lower():
            print(f"  跳过 embedding 模型: {model_name}")
            continue

        print(f"\n  测试 {model_name}...", end=" ", flush=True)
        success, result = await test_lmstudio_model(model_name)

        if success:
            print(f"OK! -> {result[:30] if len(result) > 30 else result}")
            success_models.append(model_name)
        else:
            print(f"失败: {result}")

        await asyncio.sleep(0.5)  # 避免过快

    if not success_models:
        print("\n警告: 没有模型通过测试！")
        return

    print(f"\n通过测试的模型: {success_models}")

    # 5. 注册成功的模型到数据库
    print("\n[5] 注册到数据库...")

    # 根据模型大小和用途分配任务
    # Gemma-4-e4b (4B参数) - 小而快，适合简单任务
    # Nemotron-3-nano-4b (4B) - 也适合简单任务
    # Qwen3.5-9b (9B) - 稍大，可以处理更复杂的任务

    role_assignments = {
        "gemma-4-e4b": {
            "domain_skill": "Fast",
            "rpm_limit": 999999,
            "description": "本地快速模型，处理翻译、简单问答"
        },
        "nemotron-3-nano-4b": {
            "domain_skill": "Fast",
            "rpm_limit": 999999,
            "description": "本地快速模型，处理翻译、简单问答"
        },
        "qwen3.5-9b": {
            "domain_skill": "Logic",  # 稍大的模型可以处理逻辑任务
            "rpm_limit": 999999,
            "description": "本地逻辑模型，处理简单分析"
        }
    }

    async with AsyncSessionLocal() as session:
        for model_name in success_models:
            # 查找对应的角色分配，如果没有则默认 Fast
            role_config = role_assignments.get(model_name, {
                "domain_skill": "Fast",
                "rpm_limit": 999999,
                "description": "本地模型"
            })

            asset = APIAsset(
                provider="lmstudio",
                model_name=model_name,
                domain_skill=role_config["domain_skill"],
                rpm_limit=role_config["rpm_limit"],
                api_key="lm-studio",
                provider_url=LMSTUDIO_BASE_URL,
                status="ACTIVE"
            )
            session.add(asset)
            print(f"  注册: {model_name} -> {role_config['domain_skill']}")

        await session.commit()

    # 6. 更新 Redis
    print("\n[6] 更新 Redis 节点池...")
    import redis.asyncio as redis
    r = redis.from_url('redis://localhost:6379/0', decode_responses=True)

    # 清除旧的 LM Studio 节点
    domains = ["Logic", "Coding", "Search", "Creative", "Fast"]
    for domain in domains:
        # 删除所有 LM Studio 相关的节点（通过遍历方式）
        nodes = await r.hgetall(f"ActivePool:{domain}")
        for node_id, rpm in nodes.items():
            # 检查是否是 LM Studio 的节点（ID >= 1000）
            try:
                if int(node_id) >= 1000:
                    await r.hdel(f"ActivePool:{domain}", node_id)
            except:
                pass

    # 获取新注册的节点
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(APIAsset).where(APIAsset.provider == "lmstudio")
        )
        assets = result.scalars().all()

        node_id = 1000  # 使用较大的起始ID避免冲突
        for asset in assets:
            await r.hset(
                f"ActivePool:{asset.domain_skill}",
                str(node_id),
                str(asset.rpm_limit)
            )
            print(f"  注册节点 {node_id} -> {asset.domain_skill} ({asset.model_name})")
            node_id += 1

    await r.aclose()

    print(f"\n[完成] 成功注册 {len(success_models)} 个 LM Studio 模型")
    print("\n" + "=" * 60)
    print("任务分配策略建议：")
    print("=" * 60)
    print("""
根据模型大小和能力，建议如下分配：

【本地 LM Studio 模型 - 免费】
├─ Gemma-4-e4b (4B) - 最小最快
│  └─ Fast 任务：翻译、简单问答、格式润色
│
├─ Nemotron-3-nano-4b (4B)
│  └─ Fast 任务：翻译、搜索结果整理
│
└─ Qwen3.5-9b (9B) - 本地最强
   └─ Logic 任务：简单分析、方案打分

【付费 API 模型 - 收费】
├─ DeepSeek (deepseek-chat/reasoner)
│  └─ Logic/Coding：复杂推理、代码生成
│
├─ Groq (llama-3.3-70b)
│  └─ Logic：长文本分析
│
├─ Mistral (mistral-large)
│  └─ Logic：复杂推理
│
└─ OpenRouter (gemma-3/llama-3.3)
   └─ Fast/Logic：备用

混用策略：
1. 简单翻译 -> LM Studio (免费)
2. 方案打分 -> LM Studio Qwen (本地)
3. 搜索整理 -> LM Studio (免费)
4. 复杂分析 -> DeepSeek/Mistral (付费)
5. 代码生成 -> DeepSeek/Codestral (付费)
    """)

if __name__ == "__main__":
    asyncio.run(register_lmstudio_models())
