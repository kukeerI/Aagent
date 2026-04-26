# seed_full_inventory.py
from db_infrastructure import SessionLocal, APIAsset, init_infrastructure
import os

def seed_full_inventory():
    init_infrastructure()
    session = SessionLocal()
    
    try:
        print("🧹 物理清理旧数据...")
        session.query(APIAsset).delete()
        session.commit() 

        # === 2026 最终精校清单 ===
        inventory = [
            # --- AIStudio (Google) ---
            # 修正：去掉了前面的 models/，因为 v1beta 路径已经包含了模型空间
            ("AIStudio", "gemini-1.5-pro", "文本输出", "Logic", 15, 1000000, 1500),
            ("AIStudio", "gemini-1.5-flash", "文本输出", "Fast", 15, 1000000, 2000),
            ("AIStudio", "gemini-2.0-flash-exp", "文本输出", "Fast", 10, 1000000, 1500),
            
            # --- SambaNova (验证通过) ---
            ("SambaNova", "Meta-Llama-3.3-70B-Instruct", "文本输出", "Coding", 100, 250000, 5000),
            
            # --- Groq (验证通过) ---
            ("Groq", "llama-3.3-70b-versatile", "文本输出", "Coding", 30, 15000, 14400),
            ("Groq", "llama-3.1-8b-instant", "文本输出", "Fast", 30, 20000, 14400),

            # --- OpenRouter (更新为目前 100% 可用的免费全路径) ---
            ("OpenRouter", "google/gemini-2.0-flash-001", "文本输出", "Fast", 15, 100000, 1000),
            ("OpenRouter", "google/gemini-2.0-flash-lite-preview-02-05:free", "文本输出", "Fast", 10, 100000, 1000),
            ("OpenRouter", "deepseek/deepseek-r1:free", "文本输出", "Logic", 5, 50000, 500),
        ]

        for p, m, cat, skill, rpm, tpm, rpd in inventory:
            session.add(APIAsset(
                provider=p, model_name=m, category=cat, domain_skill=skill,
                rpm_limit=rpm, tpm_limit=tpm, rpd_limit=rpd,
                api_key=f"{p.upper()}_API_KEY", status="ACTIVE"
            ))
        
        session.commit()
        print(f"🚀 军火库重装完毕！已录入 {len(inventory)} 个精校节点。")

    except Exception as e:
        session.rollback()
        print(f"❌ 录入失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_full_inventory()