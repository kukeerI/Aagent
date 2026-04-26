# init_database.py - 数据库初始化脚本
# 运行方式: python init_database.py
# 需要先运行: pip install aiosqlite

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.database import AsyncSessionLocal, APIAsset, init_db

async def init_api_assets():
    # 1. 初始化数据库表
    await init_db()
    print("数据库表创建完成！")

    # 2. 添加 API 资产记录
    # 使用 DeepSeek 作为默认 provider
    assets_data = [
        {
            "model_name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "DEEPSEEK_API_KEY",
            "weight": 100,
        },
        {
            "model_name": "gemma-3-12b-it",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "DEEPSEEK_API_KEY",
            "weight": 80,
        },
        {
            "model_name": "llama3-70b",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "DEEPSEEK_API_KEY",
            "weight": 90,
        },
    ]

    async with AsyncSessionLocal() as session:
        for data in assets_data:
            asset = APIAsset(**data)
            session.add(asset)
        await session.commit()
        print(f"已添加 {len(assets_data)} 条 API 资产记录！")

    print("\n数据库初始化完成！")

if __name__ == "__main__":
    asyncio.run(init_api_assets())
