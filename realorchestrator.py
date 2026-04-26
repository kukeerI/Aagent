# realorchestrator.py
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

from prompts import ORCHESTRATOR_SYSTEM_PROMPT
from schemas import TaskEvaluation, AgentResult
from executor import MakerExecutor 
from memory_logic import SimpleMemory

load_dotenv()

class RealOrchestrator:
    def __init__(self):
        self.memory = SimpleMemory()
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL")
        )
        self.model = "deepseek-reasoner"
        self.executor = MakerExecutor()

    def evaluate_task(self, user_input: str) -> TaskEvaluation:
        print(f"🔍 正在进行真实 ROI 评估...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"请评估以下任务并给出规划方案：{user_input}"}
            ],
            response_format={ "type": "json_object" } 
        )
        raw_content = response.choices[0].message.content
        data = json.loads(raw_content)
        return TaskEvaluation(**data)

    def start_work(self, user_input: str):
        print(f"\n🚀 收到任务: {user_input}")
        
        # --- 步骤 1：查记忆 (Memory Check) ---
        past_experience = self.memory.search(user_input)
        if past_experience:
            print("🎯 [命中记忆] 发现高度相关的历史方案，直接提取！")
            print(f"💰 成本消耗: 0 Tokens (无需调用大模型)")
            self._final_show(past_experience)
            return

        # --- 步骤 2：评估 (Evaluation) ---
        try:
            evaluation = self.evaluate_task(user_input)
        except Exception as e:
            print(f"❌ 评估阶段出错了: {e}")
            return

        print("\n" + "="*30)
        print("🚦 决策中心已就绪")
        print(f"💎 重要程度: {evaluation.importance_weight}")
        print(f"🛠️ 初始策略: {evaluation.strategy}")
        print(f"💡 决策理由: {getattr(evaluation, 'reason', '无说明')}")
        print("="*30 + "\n")

        # --- 步骤 3：物理约束 (强制降级) ---
        final_strategy = evaluation.strategy
        if evaluation.importance_weight < 7 and final_strategy == "MAKER_K3":
            print("⚠️ [检测到决策溢价] 任务重要性较低，物理强制降级为 SINGLE_FAST 以节省成本。")
            final_strategy = "SINGLE_FAST"

        # --- 步骤 4：分发执行 (Execution) ---
        final_response = None
        if final_strategy == "MAKER_K3" or evaluation.importance_weight >= 8:
            print("🚀 [高权重任务] 正在拉起 MAKER K=3 多副本纠错模式...")
            final_response = self.executor.run_maker_k3(user_input)
        else:
            print("⚡ [常规任务] 正在切换至 SINGLE_FAST 单路执行模式...")
            final_content = self.executor._single_execute(user_input)
            final_response = AgentResult(
                status="success", 
                actual_cost=150, 
                final_output=final_content
            )

        # --- 步骤 5：保存记忆与交付 (Memory Save & Delivery) ---
        if final_response and final_response.status == "success":
            print("💾 任务成功，正在将此经验存入语义库...")
            self.memory.save(user_input, final_response.final_output) # 保存到向量库
            
            print("\n" + "✨" * 15)
            print("✅ 任务最终交付结果:")
            self._final_show(final_response.final_output)
            print(f"💰 本次项目实际消耗总计: {final_response.actual_cost} tokens")
            print("✨" * 15)

    def _final_show(self, content):
        """注意：这个函数现在正确地缩进在类里面了"""
        print("-" * 40)
        print(content)
        print("-" * 40)