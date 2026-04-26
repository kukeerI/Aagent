import asyncio
import re
from pydantic import ValidationError
from prompts import ORCHESTRATOR_SYSTEM_PROMPT
from schemas import GatewayRequest, Message, AgentAction
from executor import AgentLegion  # 你原有的军团实现（只需确保它是线程安全的）
from memory import UltimateMemory
from gateway import AsyncGateway
from sandbox import ASTSandbox

class AsyncRealOrchestrator:
    def __init__(self):
        self.legion = AgentLegion()
        self.memory = UltimateMemory()
        self.gateway = AsyncGateway()
        self.sandbox = ASTSandbox()
        
        # 植入主脑的系统级设定
        self.memory.add_message("system", ORCHESTRATOR_SYSTEM_PROMPT)

    async def _safe_route_decision(self) -> AgentAction:
        """带伤自愈的路由决策"""
        req = GatewayRequest(messages=self.memory.get_context(), domain_skill="Logic")
        
        for attempt in range(3):
            raw_output = await self.gateway.chat_completion(req)
            clean_json = re.sub(r'```json\n|\n```|```', '', raw_output).strip()
            
            try:
                return AgentAction.model_validate_json(clean_json)
            except ValidationError as e:
                print(f"⚠️ [自愈修复] JSON解析失败，尝试要求大模型修正...")
                self.memory.add_message("assistant", raw_output)
                self.memory.add_message("user", f"请严格输出 JSON 格式。Pydantic 报错: {e}")
                req.messages = self.memory.get_context()
                
        raise Exception("司令部三次思考格式均崩溃，触发系统级降级。")

    async def start_work(self, user_input: str):
        print(f"\n🚀 [接单] {user_input}")
        
        # 1. 记忆双轨检索
        past_exp = self.memory.query_related_memory(user_input)
        if past_exp:
            print("🎯 [记忆命中] 提取过往解法！")
            self.memory.add_message("system", f"参考过往成功经验：{past_exp}")
            
        self.memory.add_message("user", user_input)

        # 2. 任务执行流 (最多迭代 5 步)
        step = 0
        while step < 5:
            action = await self._safe_route_decision()
            print(f"🧠 [路由] 调度: {action.next_role} | 思考: {action.thought_process}")
            
            if action.is_completed or action.next_role == "Companion":
                break
                
            # 3. 动态分发给下属角色 (使用 to_thread 防止同步代码阻塞主循环)
            if action.next_role == "Analyst":
                res = await asyncio.to_thread(self.legion.run_analyst, action.action_input)
                
            elif action.next_role == "Operator":
                code = await asyncio.to_thread(self.legion.run_operator, action.action_input)
                print("🛠️ [沙箱验证] 正在执行生成的代码...")
                obs = await self.sandbox.execute_code(code)
                res = f"代码执行反馈: {obs}" # 将沙箱反馈闭环喂回主脑
                
            elif action.next_role == "Researcher":
                res = await asyncio.to_thread(self.legion.run_researcher, action.action_input)
                
            else: # Maker 兜底
                maker_res = await asyncio.to_thread(self.legion.run_maker_k3, action.action_input)
                res = maker_res.final_output

            print(f"✅ [{action.next_role} 产出] {res[:50]}...")
            
            # 将执行结果固化入短期记忆，供主脑继续评估
            self.memory.add_message("assistant", action.model_dump_json())
            self.memory.add_message("user", f"执行结果反馈:\n{res}\n请评估是否需要继续后续步骤，或者结束任务。")
            step += 1

        # 4. 情感润色与固化长期记忆
        final_draft = self.memory.get_context()[-1].content
        final_output = await asyncio.to_thread(self.legion.run_companion, final_draft)
        
        self.memory.add_experience(task_desc=user_input, outcome=final_output)
        
        print("\n" + "="*40 + "\n" + final_output + "\n" + "="*40)