import os
import time
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def safe_scan():
    api_key = os.getenv("AISTUDIO_API_KEY")
    if not api_key:
        print("❌ 错误: .env 中未配置 AISTUDIO_API_KEY")
        return

    # AI Studio OpenAI 兼容端点
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    output_file = "aistudio_scan_results.json"
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # 待测模型列表（包含你提供的所有 ID）
    models_to_scan = [
        "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite",
        "gemma-3-1b", "gemma-3-4b", "gemma-3-12b", "gemma-3-27b",
        "gemma-4-26b", "gemma-4-31b", "gemini-3-flash", "gemini-3.1-flash-lite",
        "gemini-3.1-pro", "deep-research-pro-preview", "computer-use-preview",
        "gemini-robotics-er-1.6-preview"
    ]
    
    final_report = {
        "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "working_ids": [],
        "failed_details": []
    }

    print(f"🐢 启动安全扫描程序 (总计 {len(models_to_scan)} 个模型)")
    print("⏳ 每个请求间隔 2 秒，请耐心等待，防止封号...\n")

    for index, model_id in enumerate(models_to_scan):
        print(f"[{index+1}/{len(models_to_scan)}] 正在测试: {model_id}...", end="", flush=True)
        
        success = False
        working_id = model_id
        error_info = ""

        # 策略 1: 直接测试
        try:
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=2,
                timeout=10
            )
            success = True
        except Exception as e:
            error_info = str(e)
            # 策略 2: 尝试带 models/ 前缀 (针对部分 AI Studio 路由)
            if "404" in error_info:
                try:
                    test_id = f"models/{model_id}"
                    client.chat.completions.create(
                        model=test_id,
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=2,
                        timeout=10
                    )
                    success = True
                    working_id = test_id
                except Exception as e2:
                    error_info = f"Direct: {e} | Prefixed: {e2}"

        if success:
            print(" ✅")
            final_report["working_ids"].append(working_id)
        else:
            print(" ❌")
            final_report["failed_details"].append({"id": model_id, "error": error_info})

        # 每次测试完写入一次文件，防止程序崩溃丢失进度
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=4, ensure_ascii=False)

        # 关键：强制休眠 2 秒，模拟人类操作，避开风控
        time.sleep(2)

    print(f"\n✨ 扫描完成！可用清单已保存至: {output_file}")

if __name__ == "__main__":
    safe_scan()