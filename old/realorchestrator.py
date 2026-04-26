import asyncio
import re
from pydantic import ValidationError
from prompts import ORCHESTRATOR_SYSTEM_PROMPT
from schemas import TaskEvaluation, GatewayRequest, Message, AgentAction
from executor import AgentLegion
from memorypro import UltimateMemory  # 接入双轨记忆
from gateway_manager import AsyncIntelligentGateway # 接入高可用网关
from sandbox import ASTSandbox # 接入代码沙箱

class AsyncRealOrchestrator:
    def __init__(self):
        # 初始化所有底层基建
        self.legion = AgentLegion() 
        self.memory = UltimateMemory()
        self.gateway = AsyncIntelligentGateway()
        self.sandbox = ASTSandbox()

    async def evaluate_task_safe(self, user_input: str) -> AgentAction:
        """
        带伤重试的架构评估：绝不崩溃，且 100% 走网关！
        """
        # 将你的 Prompt 组装成标准网关请求
        messages = [
            Message(role="system", content=ORCHESTRATOR_SYSTEM_PROMPT),
            Message(role="user", content=f"请对任务进行架构评估并决定调度的角色（Analyst/Operator/Researcher/Maker）。任务：{user_input}")
        ]
        
        # 强制走网关的 Logic 高智商领域池子（网关会自己找 DeepSeek 或 Gemini）
        req = GatewayRequest(messages=messages, domain_skill="Logic")
        
        for attempt in range(3):
            # 异步调用网关
            raw_output = await self.gateway.chat_completion(req)
            print(f"📊 [架构师原始输出] Attempt {attempt+1}: {raw_output}")
            
            # 1. 正则清洗 Markdown 代码块标记
            clean_json = re.sub(r'```json\n|\n```|```', '', raw_output).strip()
            
            try:
                # 2. Pydantic 强类型校验转换
                return AgentAction.model_validate_json(clean_json)
            except ValidationError as e:
                print(f"⚠️ [格式崩溃] JSON 解析失败，触发自动自愈修复...")
                # 将错误喂回给大模型，要求其修正
                messages.append(Message(role="assistant", content=raw_output))
                messages.append(Message(role="user", content=f"你的输出不符合 JSON 格式约束。Pydantic 报错: {e}。请修正并仅输出纯 JSON。"))
                req.messages = messages
                
        raise Exception("🚨 架构师节点三次思考格式均崩溃，触发系统级降级。")

    async def start_work(self, user_input: str):
        print(f"\n🚀 [Orchestrator] 接收到新任务: {user_input}")
        
        # ================= 1. 记忆双轨检索 =================
        # 优先检索过往成功经验
        past_experience = self.memory.query_related_memory(user_task=user_input)
        if past_experience:
            print("🎯 命中长期语义记忆！直接提取过往解法...")
            return self._final_show(past_experience)
            
        self.memory.add_message("user", user_input)

        # ================= 2. 闭环执行 (最多迭代 5 步) =================
        step = 0
        current_context = user_input
        
        while step < 5:
            # 安全评估与动态路由
            action: AgentAction = await self.evaluate_task_safe(current_context)
            print(f"🧠 [主脑决策] 路由去向: {action.next_role} | 思考: {action.thought_process}")
            
            if action.is_completed or action.next_role == "Companion":
                break # 任务完成，跳出循环进入润色环节
                
            # ================= 3. 军团执行层 =================
            # 注意：如果你的 AgentLegion 还是同步的，为了不阻塞主事件循环，
            # 这里使用了 asyncio.to_thread 将其放入后台线程执行
            if action.next_role == "Analyst":
                result = await asyncio.to_thread(self.legion.run_analyst, action.action_input)
                
            elif action.next_role == "Operator":
                code_result = await asyncio.to_thread(self.legion.run_operator, action.action_input)
                print("🛠️ [沙箱拦截] 正在验证 Operator 产出的代码...")
                # Operator 写完后，强制进入沙箱运行拿结果
                sandbox_obs = await self.sandbox.execute_code(code_result)
                result = f"代码执行反馈:\n{sandbox_obs}"
                
            elif action.next_role == "Researcher":
                result = await asyncio.to_thread(self.legion.run_researcher, action.action_input)
                
            else: # Maker_k3 作为默认兜底
                maker_res = await asyncio.to_thread(self.legion.run_maker_k3, action.action_input)
                result = maker_res.final_output

            print(f"✅ [节点产出] {action.next_role} 返回结果: {result[:50]}...")
            
            # 将执行结果更新到上下文中，供主脑下一轮评估
            current_context = f"刚才 {action.next_role} 节点执行了操作，结果是：\n{result}\n请评估是否需要继续后续步骤，或者任务已完成。"
            step += 1

        # ================= 4. 情感润色与固化 =================
        final_draft = current_context
        # 使用 Companion 润色
        final_output = await asyncio.to_thread(self.legion.run_companion, final_draft)
        
        # 固化到 ChromaDB 和 Graph，让它变得更聪明
        self.memory.add_experience(task_desc=user_input, outcome=final_output)
        
        self._final_show(final_output)

    def _final_show(self, content):
        print("\n" + "="*40 + "\n" + content + "\n" + "="*40)