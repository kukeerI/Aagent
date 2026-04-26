import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- 配置区 ---
AI_STUDIO_KEY = os.getenv("AISTUDIO_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# 这里的 raw_json 就是你贴给我的那串数据
raw_json = """
[
    [
        ["gemini-2.5-flash", 20, 2, 1, ["250000"], 4],
        ["gemini-2.5-pro", 30, 2, 1, ["2000000"], 4],
        ["gemini-2.0-flash", 20, 2, 1, ["0"], 4],
        ["gemma-3-27b", 20, 2, 1, ["15000"], 1],
        ["deep-research-pro-preview", 20, 2, 1, ["0"], 5]
        # ... (脚本会自动遍历你提供的完整列表)
    ]
]
"""

def parse_and_verify():
    if not AI_STUDIO_KEY:
        print("❌ 错误: 请先在 .env 中设置 AISTUDIO_API_KEY")
        return

    # 1. 解析 JSON 提取所有唯一模型 ID
    try:
        data = json.loads(raw_json)
        # 根据你提供的结构：data[0] 是内层列表，每一项的 index 0 是名字
        all_model_names = sorted(list(set([item[0] for item in data[0]])))
        print(f"📊 解析完成：共发现 {len(all_model_names)} 个待测模型 ID。")
    except Exception as e:
        print(f"❌ JSON 解析失败: {e}")
        return

    client = OpenAI(api_key=AI_STUDIO_KEY, base_url=BASE_URL)
    
    results = {"SUCCESS": [], "FAILED": [], "RATE_LIMIT": [], "NEEDS_PREFIX": []}

    print(f"\n🚀 开始全量循环验证...\n" + "="*60)

    for model_id in all_model_names:
        # 跳过一些明显不是文本生成类的模型（可选）
        if any(x in model_id for x in ["embedding", "tts", "generate", "clip"]):
            print(f"⏭️  [跳过] {model_id.ljust(35)} | 非对话类模型")
            continue

        try:
            # 第一次尝试：直接调用
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=2
            )
            print(f"✅ [可用] {model_id.ljust(35)}")
            results["SUCCESS"].append(model_id)
            
        except Exception as e:
            err_str = str(e)
            
            # 如果 404，尝试加上 models/ 前缀再试一次
            if "404" in err_str:
                try:
                    client.chat.completions.create(
                        model=f"models/{model_id}",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=2
                    )
                    print(f"⚠️ [修正] {model_id.ljust(35)} | 需使用 models/ 前缀")
                    results["NEEDS_PREFIX"].append(f"models/{model_id}")
                except:
                    print(f"❌ [无效] {model_id.ljust(35)} | 404 Not Found")
                    results["FAILED"].append(model_id)
            
            elif "429" in err_str:
                print(f"⏳ [限流] {model_id.ljust(35)} | 频率过高")
                results["RATE_LIMIT"].append(model_id)
            else:
                print(f"🚫 [异常] {model_id.ljust(35)} | {err_str[:40]}...")
                results["FAILED"].append(model_id)
        
        # 适当减速，避免验证本身触发全局限流
        time.sleep(0.5)

    # --- 最终汇总 ---
    print("\n" + "="*60)
    print("📈 最终验证报告:")
    print(f"🟢 完全可用: {len(results['SUCCESS'])} 个")
    print(f"🟡 需加前缀: {len(results['NEEDS_PREFIX'])} 个")
    print(f"🔴 无法激活: {len(results['FAILED'])} 个")
    print(f"🔵 触发限流: {len(results['RATE_LIMIT'])} 个")
    
    print("\n📋 建议加入军火库的 ID 清单：")
    final_list = results['SUCCESS'] + results['NEEDS_PREFIX']
    for fid in final_list:
        print(f"'{fid}',")

if __name__ == "__main__":
    # 如果你想从文件读取，可以改写这一行
    # with open('models.json', 'r') as f: raw_json = f.read()
    parse_and_verify()