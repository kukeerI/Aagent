import redis
import os
from db_infrastructure import engine, Base, SessionLocal, APIAsset, ErrorLog

def nuclear_reset():
    print("⚠️ 正在执行系统深度清理...")

    # 1. 清理 SQLite (资产表和错误日志)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ SQLite 数据库已重置（资产与日志已排空）。")

    # 2. 清理 Redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.flushdb() # <--- 绝杀：清空当前 Redis 数据库的所有 Key
    print("✅ Redis 缓存已全部清空。")

    # 3. 清理语义记忆 (ChromaDB)
    # 如果你想连记忆也清空，取消下面两行的注释
    # import shutil
    # if os.path.exists("./memory_db"): shutil.rmtree("./memory_db")
    # print("✅ 语义记忆库已移除。")

    print("\n🚀 系统已回到纯净状态。请现在运行 seed_full_inventory.py 重新装载算力。")

if __name__ == "__main__":
    confirm = input("此操作将删除所有 API 状态和日志，确定吗？(y/n): ")
    if confirm.lower() == 'y':
        nuclear_reset()