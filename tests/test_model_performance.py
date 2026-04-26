# test_model_performance.py - 模型性能测试脚本（显存优化版）
# 运行方式:
#   Step 1: python test_model_performance.py --model gemma
#   Step 2: python test_model_performance.py --model qwen
#   Step 3: python test_model_performance.py --compare
# 注意：需要确保 LM Studio 已启动并加载对应模型

import asyncio
import time
import json
import os
import aiohttp
from openai import AsyncOpenAI

# LM Studio 配置
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
LMSTUDIO_API_KEY = "lm-studio"

# 测试任务
TEST_TASKS = [
    {
        "name": "搜索结果摘要",
        "prompt": "请为以下搜索结果生成一个简明扼要的摘要（不超过50字）：\n\n搜索结果：\n1. 深度学习是机器学习的一个分支，它通过模拟人脑的神经网络来学习数据中的模式。\n2. 深度学习在图像识别、自然语言处理等领域取得了显著的成果。\n3. 深度学习需要大量的数据和计算资源来训练模型。\n4. 常见的深度学习框架包括TensorFlow、PyTorch等。"
    },
    {
        "name": "文本格式化/润色",
        "prompt": "请将以下文本格式化并润色，使其更流畅：\n\n今天天气真的非常好，阳光很充足，我决定要去公园散步，然后可能会去图书馆看一些书，之后再回家准备晚餐。"
    },
    {
        "name": "翻译",
        "prompt": "请将以下中文翻译成英文：\n\n人工智能正在改变我们的生活方式，从智能助手到自动驾驶，它的应用越来越广泛。"
    },
    {
        "name": "简单问答",
        "prompt": "什么是人工智能？请用一句话回答。"
    }
]

# 模型配置
MODEL_CONFIGS = {
    "gemma": {
        "name": "google/gemma-4-e2b-it",
        "display": "Gemma-4-e2b-it (4B)",
        "expected_size": "4B"
    },
    "qwen": {
        "name": "qwen/qwen3.5-9b",
        "display": "Qwen3.5-9b (9B)",
        "expected_size": "9B"
    }
}

RESULTS_FILE = "model_test_results.json"

async def test_single_task(client, model_name, task):
    """测试单个任务"""
    try:
        start_time = time.time()

        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": task["prompt"]}],
            max_tokens=200,
            temperature=0.7
        )

        elapsed_time = time.time() - start_time
        result = response.choices[0].message.content.strip()

        # 简单质量评分
        quality_score = 0
        if task["name"] == "搜索结果摘要":
            keywords = ["深度学习", "机器学习", "神经网络", "图像识别", "NLP", "数据", "计算资源", "TensorFlow", "PyTorch"]
            for keyword in keywords:
                if keyword in result:
                    quality_score += 1
        elif task["name"] == "文本格式化/润色":
            if "天气" in result and "公园" in result and "图书馆" in result and "晚餐" in result:
                quality_score = 5
        elif task["name"] == "翻译":
            if "Artificial intelligence" in result or "AI" in result:
                quality_score += 2
            if "changing" in result or "transforming" in result:
                quality_score += 2
            if "life" in result:
                quality_score += 1
        elif task["name"] == "简单问答":
            if "人工智能" in result and ("智能" in result or "计算机" in result):
                quality_score = 5

        speed_score = max(0, 5 - int(elapsed_time * 2))

        return {
            "success": True,
            "result": result,
            "time": round(elapsed_time, 2),
            "quality_score": quality_score,
            "speed_score": speed_score
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:100]
        }

async def test_model(model_key):
    """测试指定模型的所有任务"""
    config = MODEL_CONFIGS[model_key]
    model_name = config["name"]

    print("=" * 70)
    print(f"模型测试: {config['display']}")
    print("=" * 70)

    # 检查 LM Studio 连接
    print("\n[1] 检查 LM Studio...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{LMSTUDIO_BASE_URL}/models",
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    print("[OK] LM Studio 连接成功")
                else:
                    print(f"[ERROR] LM Studio 状态码: {resp.status}")
                    return
    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        return

    # 预热模型
    print("\n[2] 预热模型...")
    try:
        client = AsyncOpenAI(api_key=LMSTUDIO_API_KEY, base_url=LMSTUDIO_BASE_URL)
        await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print("[OK] 预热成功")
    except Exception as e:
        print(f"[ERROR] 预热失败: {e}")
        print(f"\n请确保已加载模型: {model_name}")
        return

    # 正式测试
    print("\n[3] 开始测试...")
    results = {}

    for task in TEST_TASKS:
        print(f"  - {task['name']}...", end=" ", flush=True)

        result = await test_single_task(client, model_name, task)

        if result["success"]:
            print(f"OK ({result['time']}s)")
            results[task["name"]] = result
        else:
            print(f"失败")
            results[task["name"]] = result

        await asyncio.sleep(1)  # 避免过快

    # 计算统计
    success_count = sum(1 for r in results.values() if r["success"])
    total_time = sum(r["time"] for r in results.values() if r["success"])
    total_quality = sum(r["quality_score"] for r in results.values() if r["success"])
    total_speed = sum(r["speed_score"] for r in results.values() if r["success"])

    summary = {
        "model_key": model_key,
        "model_name": config["name"],
        "display_name": config["display"],
        "expected_size": config["expected_size"],
        "tasks": results,
        "stats": {
            "success_count": success_count,
            "total_tasks": len(TEST_TASKS),
            "avg_time": round(total_time / success_count, 2) if success_count > 0 else 0,
            "avg_quality": round(total_quality / success_count, 1) if success_count > 0 else 0,
            "avg_speed": round(total_speed / success_count, 1) if success_count > 0 else 0
        }
    }

    # 保存结果
    all_results = {}
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                all_results = json.load(f)
        except:
            pass

    all_results[model_key] = summary

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("\n[4] 测试结果:")
    print("-" * 40)
    for task_name, result in results.items():
        status = "OK" if result["success"] else "FAIL"
        if result["success"]:
            print(f"  {task_name}: [{status}] {result['time']}s, 质量{result['quality_score']}/5, 速度{result['speed_score']}/5")
        else:
            print(f"  {task_name}: [{status}] {result.get('error', 'Unknown error')}")

    if success_count > 0:
        print("-" * 40)
        print(f"成功率: {success_count}/{len(TEST_TASKS)}")
        print(f"平均耗时: {summary['stats']['avg_time']}s")
        print(f"平均质量: {summary['stats']['avg_quality']}/5")
        print(f"平均速度: {summary['stats']['avg_speed']}/5")

    print(f"\n结果已保存到 {RESULTS_FILE}")
    print("\n" + "=" * 70)
    print("下一步:")
    if model_key == "gemma":
        print("  1. 在 LM Studio 中切换模型 (加载 qwen/qwen3.5-9b)")
        print("  2. 运行: python test_model_performance.py --model qwen")
    else:
        print("  运行: python test_model_performance.py --compare")

async def compare_results():
    """对比已保存的测试结果"""
    print("=" * 70)
    print("模型对比分析")
    print("=" * 70)

    if not os.path.exists(RESULTS_FILE):
        print(f"\n错误: 未找到结果文件 {RESULTS_FILE}")
        print("请先运行测试:")
        print("  1. python test_model_performance.py --model gemma")
        print("  2. python test_model_performance.py --model qwen")
        return

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        all_results = json.load(f)

    if len(all_results) < 2:
        print(f"\n错误: 需要至少2个模型的测试结果，当前只有 {len(all_results)} 个")
        return

    # 打印每个模型的结果
    for model_key, summary in all_results.items():
        print(f"\n{summary['display_name']}:")
        print("-" * 40)
        print(f"  测试任务数: {summary['stats']['success_count']}/{summary['stats']['total_tasks']}")
        print(f"  平均耗时: {summary['stats']['avg_time']}s")
        print(f"  平均质量: {summary['stats']['avg_quality']}/5")
        print(f"  平均速度: {summary['stats']['avg_speed']}/5")

    # 详细对比
    print("\n" + "=" * 70)
    print("任务级别对比")
    print("=" * 70)

    for task in TEST_TASKS:
        task_name = task["name"]
        print(f"\n{task_name}:")

        for model_key, summary in all_results.items():
            result = summary["tasks"].get(task_name, {"success": False})
            display_name = summary["display_name"]

            if result["success"]:
                print(f"  {display_name}: {result['time']}s, 质量{result['quality_score']}/5")
            else:
                print(f"  {display_name}: 失败")

    # 最终推荐
    print("\n" + "=" * 70)
    print("综合推荐")
    print("=" * 70)

    gemma_stats = all_results.get("gemma", {}).get("stats", {})
    qwen_stats = all_results.get("qwen", {}).get("stats", {})

    if gemma_stats and qwen_stats:
        print("\n根据测试结果：")

        # 速度比较
        if gemma_stats["avg_time"] < qwen_stats["avg_time"]:
            print(f"  - 速度最快: Gemma (平均 {gemma_stats['avg_time']}s vs Qwen {qwen_stats['avg_time']}s)")
        else:
            print(f"  - 速度最快: Qwen (平均 {qwen_stats['avg_time']}s vs Gemma {gemma_stats['avg_time']}s)")

        # 质量比较
        if gemma_stats["avg_quality"] > qwen_stats["avg_quality"]:
            print(f"  - 质量最佳: Gemma (平均 {gemma_stats['avg_quality']}/5 vs Qwen {qwen_stats['avg_quality']}/5)")
        elif qwen_stats["avg_quality"] > gemma_stats["avg_quality"]:
            print(f"  - 质量最佳: Qwen (平均 {qwen_stats['avg_quality']}/5 vs Gemma {gemma_stats['avg_quality']}/5)")
        else:
            print(f"  - 质量相当: 均为 {(gemma_stats['avg_quality'] + qwen_stats['avg_quality'])/2}/5")

        # 综合推荐
        print("\n推荐用途:")
        print("  - Gemma: 简单翻译、快速问答、格式润色 (免费极速)")
        print("  - Qwen: 搜索摘要、复杂分析、代码生成 (更强但稍慢)")

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="模型性能测试")
    parser.add_argument("--model", choices=["gemma", "qwen"], help="测试指定模型")
    parser.add_argument("--compare", action="store_true", help="对比已保存的结果")

    args = parser.parse_args()

    if args.compare:
        await compare_results()
    elif args.model:
        await test_model(args.model)
    else:
        print("使用方法:")
        print("  Step 1: python test_model_performance.py --model gemma")
        print("  Step 2: 在 LM Studio 中切换模型 (加载 qwen/qwen3.5-9b)")
        print("  Step 3: python test_model_performance.py --model qwen")
        print("  Step 4: python test_model_performance.py --compare")

if __name__ == "__main__":
    asyncio.run(main())
