import os
import json
from openai import OpenAI
from prompts import ORCHESTRATOR_SYSTEM_PROMPT
from schemas import TaskEvaluation
from executor import AgentLegion
from memory_logic import SimpleMemory

class RealOrchestrator:
    def __init__(self):
        self.legion = AgentLegion()
        self.memory = SimpleMemory()
        self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL"))

    def evaluate_task(self, user_input):
        # 增加一个更加明确的 prompt 引导
        resp = self.client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"请仅对以下任务进行架构评估，不要执行任务：{user_input}"}
            ],
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        print(f"📊 架构师评估原始输出: {content}") # 增加一行日志方便调试
        return TaskEvaluation(**json.loads(content))

    def start_work(self, user_input):
        # 1. 记忆检索
        mem = self.memory.search(user_input)
        if mem: print("🎯 命中记忆！"); return self._final_show(mem)

        # 2. 评估
        evaluation = self.evaluate_task(user_input)
        
        # 3. 路由点将
        if "代码" in user_input:
            logic = self.legion.run_analyst(f"拆解逻辑：{user_input}")
            result = self.legion.run_operator(f"根据逻辑写代码：{logic}")
        elif "搜索" in user_input:
            result = self.legion.run_researcher(user_input)
        else:
            result = self.legion.run_maker_k3(user_input).final_output

        # 4. 润色
        final = self.legion.run_companion(result)
        self.memory.save(user_input, final)
        self._final_show(final)

    def _final_show(self, content):
        print("\n" + "="*40 + "\n" + content + "\n" + "="*40)