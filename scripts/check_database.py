# check_database.py - 检查数据库中的 API 资产
import asyncio
from sqlalchemy import select
from src.database import AsyncSessionLocal, APIAsset

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(APIAsset))
        assets = result.scalars().all()

        print("=== 数据库 API 资产 ===\n")
        print(f"{'ID':<4} {'Provider':<12} {'Model':<40} {'Domain':<8} {'RPM':<6}")
        print("-" * 80)

        for asset in assets:
            print(f"{asset.id:<4} {asset.provider:<12} {asset.model_name:<40} {asset.domain_skill:<8} {asset.rpm_limit:<6}")

        print(f"\n总计: {len(assets)} 条记录")

asyncio.run(check())
