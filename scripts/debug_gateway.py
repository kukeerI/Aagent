# debug_gateway.py - 调试网关调用
import asyncio
import os
from dotenv import load_dotenv
from src.database import AsyncSessionLocal, APIAsset
from openai import AsyncOpenAI

load_dotenv()

async def test_api_call():
    print("Testing API calls to registered models...\n")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(APIAsset))
        assets = result.scalars().all()

        for asset in assets[:3]:  # Test first 3
            print(f"\nTesting: {asset.provider} - {asset.model_name}")
            print(f"API Key env var: {asset.api_key}")
            print(f"Base URL: {asset.provider_url}")
            print(f"API Key value: {os.getenv(asset.api_key, 'NOT SET')[:20]}...")

            try:
                client = AsyncOpenAI(
                    api_key=os.getenv(asset.api_key),
                    base_url=asset.provider_url
                )

                response = await client.chat.completions.create(
                    model=asset.model_name,
                    messages=[{"role": "user", "content": "Say 'Hello' in one word"}],
                    max_tokens=50
                )

                result_text = response.choices[0].message.content
                print(f"Response: {result_text}")
                print(f"Status: SUCCESS")

            except Exception as e:
                print(f"Status: FAILED - {type(e).__name__}: {str(e)[:100]}")

from sqlalchemy import select

asyncio.run(test_api_call())
