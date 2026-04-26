import os
import time
from openai import OpenAI
from db_infrastructure import SessionLocal, APIAsset
from dotenv import load_dotenv

load_dotenv()

def verify_all_models():
    session = SessionLocal()
    assets = session.query(APIAsset).all()
    
    print(f"🔍 开始验证 {len(assets)} 个模型节点的有效性...\n")
    
    # 基础 URL 映射
    urls = {
        "AIStudio": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "Groq": "https://api.groq.com/openai/v1",
        "Cerebras": "https://api.cerebras.ai/v1",
        "SambaNova": "https://api.sambanova.ai/v1",
        "OpenRouter": "https://openrouter.ai/api/v1"
    }

    for asset in assets:
        api_key = os.getenv(asset.api_key)
        base_url = urls.get(asset.provider)
        
        if not api_key:
            print(f"❌ [{asset.provider}] 缺失 API Key ({asset.api_key})，跳过。")
            continue

        print(f"📡 正在测试: {asset.provider} -> {asset.model_name} ...", end="\r")
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        try:
            # 发送一个极短的测试请求
            client.chat.completions.create(
                model=asset.model_name,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            print(f"✅ [{asset.provider}] {asset.model_name} : 可用")
            asset.status = "ACTIVE" # 确认可用
        except Exception as e:
            error_msg = str(e)
            # 打印出完整的报错信息，方便我们分析“其他错误”
            print(f"⚠️ [{asset.provider}] {asset.model_name} : 详细报错 -> {error_msg}")
            asset.status = "BANNED" # 一律先封禁，保证网关安全
            if "model_not_found" in error_msg or "404" in error_msg:
                print(f"❌ [{asset.provider}] {asset.model_name} : 模型 ID 错误 (404)")
                asset.status = "BANNED" # 标记为禁用，防止网关调用
            elif "401" in error_msg:
                print(f"❌ [{asset.provider}] {asset.model_name} : API Key 无效 (401)")
            else:
                print(f"⚠️ [{asset.provider}] {asset.model_name} : 其他错误 ({error_msg[:50]}...)")
        
        session.commit()
        time.sleep(0.5) # 防止请求过快

    session.close()
    print("\n✨ 验证完成！无效的模型已在数据库中标记。")

if __name__ == "__main__":
    verify_all_models()