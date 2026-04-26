# debug_memory_issue.py - 调试记忆系统问题
import asyncio
import re
import os
from dotenv import load_dotenv
from src.schemas import GatewayRequest, Message, AgentAction
from src.gateway import AsyncGateway
from src.memory import UltimateMemory
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

async def test_memory_issue():
    print("Testing memory system impact on JSON parsing...\n")

    # 模拟 main.py 的记忆系统
    memory = UltimateMemory()
    gateway = AsyncGateway()

    # 1. 植入系统提示词
    memory.add_message("system", ORCHESTRATOR_PROMPT)

    # 2. 模拟查询记忆（找到过往经验）
    past_exp = "这是之前成功完成的任务经验..."
    memory.add_message("system", f"参考过往成功经验：{past_exp}")

    # 3. 添加用户输入
    user_input = "写一个快排并分析时间复杂度"
    memory.add_message("user", user_input)

    # 4. 查看记忆内容
    print("Current memory context:")
    for i, msg in enumerate(memory.get_context()):
        print(f"  {i+1}. [{msg.role}] {msg.content[:80]}...")
    print()

    # 5. 尝试路由决策
    req = GatewayRequest(messages=memory.get_context(), domain_skill="Logic")

    print("Calling gateway.chat_completion()...")
    try:
        raw_output = await gateway.chat_completion(req)
        print(f"Raw Output received (length: {len(raw_output)})")
        print(f"Raw Output preview:\n{raw_output[:300]}...\n")
        print("="*70)

        # 尝试解析 JSON
        clean_json = re.sub(r'```json\n|\n```|```', '', raw_output).strip()
        print(f"Cleaned JSON preview:\n{clean_json[:300]}...\n")
        print("="*70)

        try:
            action = AgentAction.model_validate_json(clean_json)
            print(f"Parsed Successfully!")
            print(f"next_role: {action.next_role}")
            print(f"is_completed: {action.is_completed}")
        except ValidationError as e:
            print(f"Validation Error: {e}")
            print("\nFailed JSON content:")
            print(clean_json)

    except Exception as e:
        print(f"Gateway Error: {e}")
    finally:
        await gateway.close()

asyncio.run(test_memory_issue())
