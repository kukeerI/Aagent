# src/executor.py
import asyncio
from openai import AsyncOpenAI
from src.gateway import AsyncGateway, GatewayError, NetworkError, RateLimitExceededError, NoAvailableNodesError
from src.schemas import GatewayRequest, Message
from src.prompts import (
    ANALYST_SYSTEM_PROMPT, OPERATOR_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT, COMPANION_SYSTEM_PROMPT, MAKER_SYSTEM_PROMPT, JUDGE_PROMPT_TEMPLATE,
    LOCAL_ANALYST_PROMPT, LOCAL_OPERATOR_PROMPT, LOCAL_RESEARCHER_PROMPT,
    LOCAL_MAKER_PROMPT, LOCAL_COMPANION_PROMPT, LOCAL_THINKING_PROMPT
)

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

class AsyncAgentLegion:
    def __init__(self, gateway: AsyncGateway):
        self.gateway = gateway
        self.trace_id = gateway.trace_id if hasattr(gateway, 'trace_id') else None

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
            print(f"[{self.trace_id}] [Executor] Using specialized local model fallback")
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[{self.trace_id}] [Local Model Error] {e}")
            return None

    async def _dispatch(self, sys_prompt: str, user_input: str, domain: str = "Logic") -> str:
        req = GatewayRequest(
            messages=[Message(role="system", content=sys_prompt), Message(role="user", content=user_input)],
            domain_skill=domain
        )

        for attempt in range(2):
            try:
                return await self.gateway.chat_completion(req)
            except NetworkError as e:
                print(f"[{self.trace_id}] [Network Error] {e}")
                print(f"[{self.trace_id}] [Executor] 网络失败，尝试本地模型...")
                local_prompt = LOCAL_PROMPTS.get(domain, LOCAL_THINKING_PROMPT)
                local_output = await self._try_local_model(req, local_prompt)
                if local_output:
                    return local_output
                print(f"[{self.trace_id}] [Executor] 本地模型也失败，继续尝试云端...")
                await asyncio.sleep(1)
                continue
            except (RateLimitExceededError, NoAvailableNodesError) as e:
                print(f"[{self.trace_id}] [Gateway Error] {e}")
                print(f"[{self.trace_id}] [Executor] 无可用节点，尝试本地模型...")
                local_prompt = LOCAL_PROMPTS.get(domain, LOCAL_THINKING_PROMPT)
                local_output = await self._try_local_model(req, local_prompt)
                if local_output:
                    return local_output
                print(f"[{self.trace_id}] [Executor] 本地模型也失败，继续尝试...")
                await asyncio.sleep(1)
                continue
            except GatewayError as e:
                print(f"[{self.trace_id}] [Gateway Error] {e}")
                await asyncio.sleep(1)
                continue
            except Exception as e:
                print(f"[{self.trace_id}] [Unexpected Error] {e}")
                await asyncio.sleep(1)
                continue

        local_prompt = LOCAL_PROMPTS.get(domain, LOCAL_THINKING_PROMPT)
        local_output = await self._try_local_model(req, local_prompt)
        if local_output:
            return local_output

        raise Exception(f"[{self.trace_id}] 所有模型尝试都失败")

    async def run_analyst(self, user_input: str):
        return await self._dispatch(ANALYST_SYSTEM_PROMPT, user_input, "Logic")

    async def run_operator(self, user_input: str):
        return await self._dispatch(OPERATOR_SYSTEM_PROMPT, user_input, "Coding")

    async def run_researcher(self, user_input: str):
        return await self._dispatch(RESEARCHER_SYSTEM_PROMPT, user_input, "Fast")

    async def run_companion(self, text: str):
        return await self._dispatch(COMPANION_SYSTEM_PROMPT, text, "Fast")

    async def run_maker_k3(self, user_input: str):
        tasks = [self._dispatch(MAKER_SYSTEM_PROMPT, user_input, "Fast") for _ in range(3)]
        drafts = await asyncio.gather(*tasks, return_exceptions=True)
        valid_drafts = [d for d in drafts if isinstance(d, str)]

        if not valid_drafts: return "生成草稿失败。"
        judge_input = JUDGE_PROMPT_TEMPLATE.format(drafts="\n---\n".join(valid_drafts))
        return await self._dispatch("你是一个严格的审核员", judge_input, "Logic")