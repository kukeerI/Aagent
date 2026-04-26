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
from src.database import AsyncSessionLocal, ExecutionLog, generate_trace_id

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
    def __init__(self, trace_id: str = None):
        self.trace_id = trace_id or generate_trace_id()
        self.gateway = AsyncGateway(trace_id=self.trace_id)
        self.legion = AsyncAgentLegion(self.gateway)
        self.memory = UltimateMemory()
        self.sandbox = ASTSandbox()
        self.memory.add_message("system", ORCHESTRATOR_SYSTEM_PROMPT)

    async def _log_execution(self, role: str, prompt: str, response: str, model_used: str = None, is_local_fallback: bool = False, error_message: str = None):
        """异步记录执行日志到数据库"""
        try:
            async with AsyncSessionLocal() as session:
                log = ExecutionLog(
                    trace_id=self.trace_id,
                    task_description=self.memory.short_term_history[0].content if self.memory.short_term_history else "",
                    role=role,
                    prompt=prompt,
                    response=response,
                    model_used=model_used,
                    is_local_fallback=is_local_fallback,
                    error_message=error_message
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            print(f"[{self.trace_id}] [Log Error] {e}")

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
                    print(f"[{self.trace_id}] [Self-Healing] JSON解析失败，尝试要求大模型修正...")
                    self.memory.add_message("assistant", raw_output)
                    self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                    req.messages = self.memory.get_context()
                    continue
            except NetworkError as e:
                print(f"[{self.trace_id}] [Network Error] {e}")
                print(f"[{self.trace_id}] [Orchestrator] 网络失败，尝试本地模型...")
                local_prompt = LOCAL_PROMPTS.get("Logic", LOCAL_THINKING_PROMPT)
                local_output = await self._try_local_model(req, local_prompt)
                if local_output:
                    clean_json = re.sub(r'```json\n|\n```|```', '', local_output).strip()
                    try:
                        return AgentAction.model_validate_json(clean_json)
                    except ValidationError as e:
                        print(f"[{self.trace_id}] [Self-Healing] 本地模型 JSON解析失败，尝试修正...")
                        self.memory.add_message("assistant", local_output)
                        self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                        req.messages = self.memory.get_context()
                        continue
                else:
                    print(f"[{self.trace_id}] [Orchestrator] 本地模型也失败，继续尝试云端...")
                    await asyncio.sleep(1)
                    continue
            except (RateLimitExceededError, NoAvailableNodesError) as e:
                print(f"[{self.trace_id}] [Gateway Error] {e}")
                print(f"[{self.trace_id}] [Orchestrator] 无可用节点，尝试本地模型...")
                local_prompt = LOCAL_PROMPTS.get("Logic", LOCAL_THINKING_PROMPT)
                local_output = await self._try_local_model(req, local_prompt)
                if local_output:
                    clean_json = re.sub(r'```json\n|\n```|```', '', local_output).strip()
                    try:
                        return AgentAction.model_validate_json(clean_json)
                    except ValidationError as e:
                        print(f"[{self.trace_id}] [Self-Healing] 本地模型 JSON解析失败，尝试修正...")
                        self.memory.add_message("assistant", local_output)
                        self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                        req.messages = self.memory.get_context()
                        continue
                else:
                    print(f"[{self.trace_id}] [Orchestrator] 本地模型也失败，继续尝试...")
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

        raise Exception(f"[{self.trace_id}] 司令部三次思考格式均崩溃，触发系统级降级。")

    async def start_work(self, user_input: str):
        print(f"\n[{self.trace_id}] >>> [接单] {user_input}")

        past_exp = self.memory.query_related_memory(user_input)
        if past_exp:
            print(f"[{self.trace_id}] [记忆命中] 提取过往解法！")
            self.memory.add_message("system", f"参考过往成功经验：{past_exp}")

        self.memory.add_message("user", user_input)

        step = 0
        while step < 5:
            action = await self._safe_route_decision()
            print(f"[{self.trace_id}] [路由] 调度: {action.next_role} | 思考: {action.thought_process}")

            if action.is_completed or action.next_role == "Companion":
                break

            role = action.next_role
            res = ""
            is_local = False

            try:
                if action.next_role == "Analyst":
                    res = await self.legion.run_analyst(action.action_input)
                elif action.next_role == "Operator":
                    code = await self.legion.run_operator(action.action_input)
                    print(f"[{self.trace_id}] [沙箱验证] 正在执行生成的代码...")
                    obs = await self.sandbox.execute_code(code)
                    res = f"代码执行反馈: {obs}"
                elif action.next_role == "Researcher":
                    res = await self.legion.run_researcher(action.action_input)
                else:
                    res = await self.legion.run_maker_k3(action.action_input)

                print(f"[{self.trace_id}] [{action.next_role} 产出] {res[:50]}...")
            except Exception as e:
                print(f"[{self.trace_id}] [{action.next_role} 执行异常] {e}")
                res = f"执行异常: {e}"

            context = self.memory.get_context()
            prompt_text = "\n".join([f"{m.role}: {m.content}" for m in context])

            asyncio.create_task(self._log_execution(
                role=role,
                prompt=prompt_text,
                response=res,
                model_used="local" if is_local else "cloud",
                is_local_fallback=is_local
            ))

            self.memory.add_message("assistant", action.model_dump_json())
            self.memory.add_message("user", f"执行结果反馈:\n{res}\n请评估是否需要继续后续步骤，或者结束任务。")
            step += 1

        final_draft = self.memory.get_context()[-1].content
        final_output = await self.legion.run_companion(final_draft)

        self.memory.add_experience(task_desc=user_input, outcome=final_output, importance=1.0)

        asyncio.create_task(self._log_execution(
            role="Companion",
            prompt=final_draft,
            response=final_output,
            model_used="cloud"
        ))

        safe_output = final_output.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print(f"\n[{self.trace_id}] " + "="*40 + "\n" + safe_output + "\n" + "="*40)