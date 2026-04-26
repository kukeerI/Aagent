# debug_json.py - 调试 JSON 解析问题
import asyncio
import re
import os
from dotenv import load_dotenv
from src.database import AsyncSessionLocal, APIAsset
from src.schemas import GatewayRequest, Message, AgentAction
from openai import AsyncOpenAI
from pydantic import ValidationError

load_dotenv()

ORCHESTRATOR_PROMPT = """你是一个 AI 军团的最高司令 (Orchestrator)。
你的职责是分析用户的原始任务，并决定将其指派给哪个专业下属。

可调用的下属角色：
1. Analyst: 负责逻辑拆解和方案设计。
2. Operator: 负责编写和修改 Python 代码。
3. Researcher: 负责联网搜索和资料整理。
4. Maker: 负责发散性生成和通用任务兜底。
5. Companion: 负责最终结果的情感润色与输出。

请你严格按照 JSON 格式返回下一步的行动计划，包含 thought_process, next_role, action_input 和 is_completed。"""

async def test_json_parsing():
    print("Testing Orchestrator JSON parsing...\n")

    # 构造请求
    messages = [
        Message(role="system", content=ORCHESTRATOR_PROMPT),
        Message(role="user", content="写一个快排并分析时间复杂度")
    ]

    req = GatewayRequest(messages=messages, domain_skill="Logic")

    # 调用 API
    async with AsyncSessionLocal() as session:
        asset = await session.get(APIAsset, 1)  # DeepSeek

        client = AsyncOpenAI(
            api_key=os.getenv(asset.api_key),
            base_url=asset.provider_url
        )

        print(f"Calling: {asset.model_name}")
        print(f"Messages: {len(req.messages)}\n")

        response = await client.chat.completions.create(
            model=asset.model_name,
            messages=[m.model_dump() for m in req.messages],
            max_tokens=500
        )

        raw_output = response.choices[0].message.content
        print(f"Raw Output:\n{raw_output}\n")
        print("="*70)

        # 尝试解析 JSON
        clean_json = re.sub(r'```json\n|\n```|```', '', raw_output).strip()
        print(f"Cleaned JSON:\n{clean_json}\n")
        print("="*70)

        try:
            action = AgentAction.model_validate_json(clean_json)
            print(f"Parsed Successfully!")
            print(f"thought_process: {action.thought_process}")
            print(f"next_role: {action.next_role}")
            print(f"action_input: {action.action_input}")
            print(f"is_completed: {action.is_completed}")
        except ValidationError as e:
            print(f"Validation Error:")
            print(e.json())

from sqlalchemy import select

asyncio.run(test_json_parsing())
