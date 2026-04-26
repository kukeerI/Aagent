# check_models.py - 检查数据库中的模型
import asyncio
from src.database import AsyncSessionLocal, APIAsset
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(APIAsset))
        assets = result.scalars().all()
        print(f'Database has {len(assets)} models')
        print('='*70)
        for asset in assets:
            status_mark = '[ACTIVE]' if asset.status == 'ACTIVE' else '[INACTIVE]'
            print(f'{status_mark} {asset.provider:15} | {asset.model_name:35} | {asset.status}')
        print('='*70)
        active_count = len([a for a in assets if a.status == 'ACTIVE'])
        print(f'Available models: {active_count} / {len(assets)}')

asyncio.run(check())
