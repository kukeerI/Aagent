# seed_full_inventory.py
from db_infrastructure import SessionLocal, APIAsset, Base, engine
import datetime

def seed():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    session.query(APIAsset).delete() # 全量覆盖更新

    # 定义全量算力清单
    inventory = [
        # === AI Studio (Google) 阵列 - 核心大脑与多模态 ===
        # (Provider, Model, Category, Skill, RPM, TPM, RPD, Reset_UTC)
        ("AIStudio", "gemini-2.5-pro", "文本输出", "Logic", 15, 1000000, 1500, 8),
        ("AIStudio", "gemini-2.5-flash", "文本输出", "Fast", 15, 1000000, 2000, 8),
        ("AIStudio", "gemini-3.1-pro", "文本输出", "Logic", 10, 1000000, 1000, 8),
        ("AIStudio", "gemini-3.1-flash-lite", "文本输出", "Fast", 15, 250000, 500, 8),
        ("AIStudio", "gemma-4-31b", "其他模型", "Logic", 15, 1000000, 1500, 8),
        ("AIStudio", "gemma-4-26b", "其他模型", "Coding", 15, 1000000, 1500, 8),
        ("AIStudio", "gemma-3-27b", "其他模型", "Fast", 30, 15000, 14400, 8),
        ("AIStudio", "gemma-3-12b", "其他模型", "Fast", 30, 15000, 14400, 8),
        ("AIStudio", "gemini-2.5-flash-tts", "多模态生成", "Special", 3, 10000, 10, 8),
        ("AIStudio", "gemini-robotics-er-1.6", "其他模型", "Special", 5, 250000, 20, 8),
        ("AIStudio", "gemini-embedding-2", "其他模型", "Embedding", 100, 30000, 1000, 8),
        ("AIStudio", "computer-use-preview", "其他模型", "Special", 5, 500000, 500, 8),

        # === SambaNova 阵列 - 极速推理巨兽 ===
        ("SambaNova", "llama-3.1-405b", "文本输出", "Logic", 10, 100000, 1000, 0),
        ("SambaNova", "llama-3.3-70b", "文本输出", "Coding", 100, 250000, 5000, 0),
        ("SambaNova", "qwen-2.5-72b", "文本输出", "Logic", 100, 250000, 5000, 0),
        ("SambaNova", "llama-3.2-3b", "文本输出", "Fast", 100, 250000, 10000, 0),

        # === Groq 阵列 - 延迟最低的执行者 ===
        ("Groq", "llama-3.3-70b-versatile", "文本输出", "Coding", 30, 15000, 14400, 0),
        ("Groq", "mixtral-8x7b-32768", "文本输出", "Fast", 30, 5000, 14400, 0),
        ("Groq", "gemma-2-9b-it", "文本输出", "Fast", 30, 15000, 14400, 0),

        # === Cerebras 阵列 - 高 TPM 吞吐专家 ===
        ("Cerebras", "llama-3.1-70b", "文本输出", "Search", 30, 60000, 14400, 0),
        ("Cerebras", "llama-3.1-8b", "文本输出", "Search", 30, 60000, 14400, 0),

        # === Mistral AI 阵列 - 欧洲顶级逻辑 ===
        ("Mistral", "mistral-large-latest", "文本输出", "Logic", 1, 50000, 1000, 0),
        ("Mistral", "pixtral-large-latest", "多模态", "Special", 1, 50000, 1000, 0),
        ("Mistral", "codestral-latest", "文本输出", "Coding", 1, 50000, 1000, 0),

        # === Together AI 阵列 - 多样化专家池 ===
        ("TogetherAI", "deepseek-v3", "文本输出", "Logic", 5, 20000, 1000, 0),
        ("TogetherAI", "qwen-2.5-coder-32b", "文本输出", "Coding", 10, 30000, 1000, 0),
        ("TogetherAI", "llama-3.2-11b-vision", "多模态", "Special", 5, 20000, 1000, 0),

        # === OpenRouter 免费池 - 动态兜底阵列 ===
        ("OpenRouter", "google/gemma-2-9b-it:free", "文本输出", "Fast", 20, 100000, 1000, 0),
        ("OpenRouter", "mistralai/mistral-7b-instruct:free", "文本输出", "Fast", 20, 100000, 1000, 0),
        ("OpenRouter", "liquid/lfm-40b:free", "文本输出", "Search", 10, 100000, 1000, 0),
        ("OpenRouter", "huggingfaceh4/zephyr-7b-beta:free", "文本输出", "Fast", 20, 100000, 1000, 0),
    ]

    for p, m, cat, skill, rpm, tpm, rpd, reset in inventory:
        # 获取对应的环境变量 key 名
        env_key = f"{p.upper()}_API_KEY"
        
        asset = APIAsset(
            provider=p,
            model_name=m,
            category=cat,
            domain_skill=skill,
            rpm_limit=rpm,
            tpm_limit=tpm,
            rpd_limit=rpd,
            api_key=env_key, # 这里存入环境变量名，运行时动态读取
            reset_hour_utc=reset
        )
        session.add(asset)

    session.commit()
    session.close()
    print(f"✅ 史诗级资产包装填完毕！共计部署 {len(inventory)} 个异构算力节点。")

if __name__ == "__main__":
    seed()