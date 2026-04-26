import asyncio
import re
from pydantic import ValidationError
from openai import AsyncOpenAI
from src.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    LOCAL_ANALYST_PROMPT, LOCAL_OPERATOR_PROMPT, LOCAL_RESEARCHER_PROMPT,
    LOCAL_MAKER_PROMPT, LOCAL_COMPANION_PROMPT, LOCAL_THINKING_PROMPT
)
from src.schemas import GatewayRequest, Message, AgentAction
from src.executor import AsyncAgentLegion
from src.memory import UltimateMemory
from src.gateway import AsyncGateway, GatewayError, NetworkError, RateLimitExceededError, NoAvailableNodesError
from src.sandbox import ASTSandbox

LOCAL_PROMPTS = {
    "Analyst": LOCAL_ANALYST_PROMPT,
    "Operator": LOCAL_OPERATOR_PROMPT,
    "Researcher": LOCAL_RESEARCHER_PROMPT,
    "Maker": LOCAL_MAKER_PROMPT,
    "Companion": LOCAL_COMPANION_PROMPT,
    "Logic": LOCAL_THINKING_PROMPT,
    "Coding": LOCAL_OPERATOR_PROMPT,
    "Fast": LOCAL_THINKING_PROMPT,
}

class AsyncRealOrchestrator:
    def __init__(self):
        self.gateway = AsyncGateway()
        self.legion = AsyncAgentLegion(self.gateway)
        self.memory = UltimateMemory()
        self.sandbox = ASTSandbox()

        # 植入主脑的系统级设定
        self.memory.add_message("system", ORCHESTRATOR_SYSTEM_PROMPT)

    async def _try_local_model(self, request: GatewayRequest, local_prompt: str = None) -> str:
        """尝试使用本地 LM Studio 模型，使用特化的 prompt"""
        try:
            local_client = AsyncOpenAI(
                api_key="lm-studio",
                base_url="http://localhost:1234/v1"
            )

            messages = [Message(role="system", content=local_prompt)] if local_prompt else []
            messages.extend(request.messages[1:] if len(request.messages) > 1 else request.messages)

            resp = await local_client.chat.completions.create(
                model="google/gemma-4-e2b-it",
                messages=[m.model_dump() for m in messages],
                timeout=120
            )
            print("[Orchestrator] Using specialized local model fallback")
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[Local Model Error] {e}")
            return None

    async def _safe_route_decision(self) -> AgentAction:
        """带伤自愈的路由决策"""
        req = GatewayRequest(messages=self.memory.get_context(), domain_skill="Logic")

        for attempt in range(3):
            try:
                raw_output = await self.gateway.chat_completion(req)
                clean_json = re.sub(r'```json\n|\n```|```', '', raw_output).strip()

                try:
                    return AgentAction.model_validate_json(clean_json)
                except ValidationError as e:
                    print(f"[Self-Healing] JSON解析失败，尝试要求大模型修正...")
                    self.memory.add_message("assistant", raw_output)
                    self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                    req.messages = self.memory.get_context()
                    continue
            except NetworkError as e:
                print(f"[Network Error] {e}")
                print("[Orchestrator] 网络失败，尝试本地模型...")
                local_prompt = LOCAL_PROMPTS.get("Logic", LOCAL_THINKING_PROMPT)
                local_output = await self._try_local_model(req, local_prompt)
                if local_output:
                    clean_json = re.sub(r'```json\n|\n```|```', '', local_output).strip()
                    try:
                        return AgentAction.model_validate_json(clean_json)
                    except ValidationError as e:
                        print(f"[Self-Healing] 本地模型 JSON解析失败，尝试修正...")
                        self.memory.add_message("assistant", local_output)
                        self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                        req.messages = self.memory.get_context()
                        continue
                else:
                    print("[Orchestrator] 本地模型也失败，继续尝试云端...")
                    await asyncio.sleep(1)
                    continue
            except (RateLimitExceededError, NoAvailableNodesError) as e:
                print(f"[Gateway Error] {e}")
                print("[Orchestrator] 无可用节点，尝试本地模型...")
                local_prompt = LOCAL_PROMPTS.get("Logic", LOCAL_THINKING_PROMPT)
                local_output = await self._try_local_model(req, local_prompt)
                if local_output:
                    clean_json = re.sub(r'```json\n|\n```|```', '', local_output).strip()
                    try:
                        return AgentAction.model_validate_json(clean_json)
                    except ValidationError as e:
                        print(f"[Self-Healing] 本地模型 JSON解析失败，尝试修正...")
                        self.memory.add_message("assistant", local_output)
                        self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                        req.messages = self.memory.get_context()
                        continue
                else:
                    print("[Orchestrator] 本地模型也失败，继续尝试...")
                    await asyncio.sleep(1)
                    continue
            except GatewayError as e:
                print(f"[Gateway Error] {e}")
                await asyncio.sleep(1)
                continue
            except Exception as e:
                print(f"[Unexpected Error] {e}")
                await asyncio.sleep(1)
                continue

        raise Exception("司令部三次思考格式均崩溃，触发系统级降级。")

    async def start_work(self, user_input: str):
        print(f"\n>>> [接单] {user_input}")

        # 1. 记忆双轨检索
        past_exp = self.memory.query_related_memory(user_input)
        if past_exp:
            print("[记忆命中] 提取过往解法！")
            self.memory.add_message("system", f"参考过往成功经验：{past_exp}")

        self.memory.add_message("user", user_input)

        # 2. 任务执行流 (最多迭代 5 步)
        step = 0
        while step < 5:
            action = await self._safe_route_decision()
            print(f"[路由] 调度: {action.next_role} | 思考: {action.thought_process}")

            if action.is_completed or action.next_role == "Companion":
                break

            # 3. 动态分发给下属角色 (使用原生异步方法)
            if action.next_role == "Analyst":
                res = await self.legion.run_analyst(action.action_input)

            elif action.next_role == "Operator":
                code = await self.legion.run_operator(action.action_input)
                print("[沙箱验证] 正在执行生成的代码...")
                obs = await self.sandbox.execute_code(code)
                res = f"代码执行反馈: {obs}" # 将沙箱反馈闭环喂回主脑

            elif action.next_role == "Researcher":
                res = await self.legion.run_researcher(action.action_input)

            else: # Maker 兜底
                res = await self.legion.run_maker_k3(action.action_input)

            print(f"[{action.next_role} 产出] {res[:50]}...")

            # 将执行结果固化入短期记忆，供主脑继续评估
            self.memory.add_message("assistant", action.model_dump_json())
            self.memory.add_message("user", f"执行结果反馈:\n{res}\n请评估是否需要继续后续步骤，或者结束任务。")
            step += 1

        # 4. 情感润色与固化长期记忆
        final_draft = self.memory.get_context()[-1].content
        final_output = await self.legion.run_companion(final_draft)

        self.memory.add_experience(task_desc=user_input, outcome=final_output, importance=1.0)

        # 安全输出，处理编码问题
        safe_output = final_output.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print("\n" + "="*40 + "\n" + safe_output + "\n" + "="*40)