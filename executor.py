from typing import List
from schemas import AgentResult
from gateway_manager import IntelligentGateway
from prompts import *

class AgentLegion:
    def __init__(self):
        self.gateway = IntelligentGateway()
        self.gateway.sync_to_redis()

    def _call(self, prompt, user_input, domain):
        return self.gateway.chat_completion([
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ], domain_skill=domain)

    def run_researcher(self, q): return self._call(RESEARCHER_SYSTEM_PROMPT, q, "Search")
    def run_operator(self, t): return self._call(OPERATOR_SYSTEM_PROMPT, t, "Coding")
    def run_analyst(self, p): return self._call(ANALYST_SYSTEM_PROMPT, p, "Logic")
    def run_creator(self, t): return self._call(CREATOR_SYSTEM_PROMPT, t, "Creative")
    def run_companion(self, c): return self._call(COMPANION_SYSTEM_PROMPT, c, "Fast")

    def run_maker_k3(self, task):
        print("🚀 MAKER K=3 分身协作中...")
        outputs = [self._call(OPERATOR_SYSTEM_PROMPT, task, "Coding") for _ in range(3)]
        print("⚖️ 裁判正在进行共识审计...")
        judge_p = f"整合以下方案并去重纠错：\n1:{outputs[0]}\n2:{outputs[1]}\n3:{outputs[2]}"
        final = self._call(ANALYST_SYSTEM_PROMPT, judge_p, "Logic")
        return AgentResult(status="success", actual_cost=0, final_output=final)