# executor.py
import os
from typing import List
from schemas import AgentResult
from gateway_manager import IntelligentGateway # 接入智能网关

class MakerExecutor:
    def __init__(self):
        """
        初始化执行器：
        不再固定 API Key，而是初始化网关，由网关根据 Redis 状态自动分配算力
        """
        self.gateway = IntelligentGateway()
        # 初始化时同步一次 Redis 池，确保网关知道哪些模型可用
        self.gateway.sync_to_redis()

    def _single_execute(self, task_description: str, domain: str = "Fast") -> str:
        """
        单分身执行逻辑：
        根据任务性质（domain）动态选择模型池
        - domain="Fast": 适用于简单任务，路由至 Gemini Flash/Gemma 系列
        - domain="Coding": 适用于代码任务，路由至 Llama-3.3/Gemma-4 系列
        """
        messages = [{"role": "user", "content": task_description}]
        
        # 通过网关进行“平滑加权轮询”请求
        # 网关内部会自动处理 429 报错、剔除失效 Key 并更换模型重试
        try:
            return self.gateway.chat_completion(messages, domain_skill=domain)
        except Exception as e:
            return f"执行器单步执行失败: {str(e)}"

    def run_maker_k3(self, task_description: str) -> AgentResult:
        """
        MAKER K=3 模式：
        1. 启动 3 个分身并发工作（路由至 Coding/Fast 池以节省高质量额度）
        2. 裁判 (System 2) 进行共识判定（强制路由至 Logic 最强大脑池）
        """
        print(f"🚀 MAKER K=3 模式启动，正在调用算力集群生成 3 个独立方案...")
        
        outputs: List[str] = []
        # 1. 产生三个分身的结果（分流到 Coding 领域模型，如 SambaNova Llama-3.3 或 Groq）
        for i in range(3):
            print(f"  - 分身 {i+1} 正在调用集群节点工作...")
            # 这里的 domain 选择 Coding，利用 SambaNova/Groq 的高 RPM
            out = self._single_execute(task_description, domain="Coding")
            outputs.append(out)

        # 2. 裁判进行共识判定（必须使用智力最高的 Logic 池，如 Gemini 2.5 Pro 或 SambaNova 405B）
        print(f"⚖️ 裁判 (System 2) 介入，正在 Logic 池中点将最强模型进行审计...")
        judge_prompt = f"""
        任务描述：{task_description}
        以下是三个不同 Agent 给出的执行结果，请对比它们，指出其中的错误，并整合出一个最准确、最完美的最终版本。
        
        方案 1：{outputs[0]}
        方案 2：{outputs[1]}
        方案 3：{outputs[2]}
        
        请直接输出最终整合后的内容，不要废话。
        """
        
        # 裁判逻辑：强制要求 Logic 领域的顶级模型
        final_output = self.gateway.chat_completion(
            [{"role": "user", "content": judge_prompt}], 
            domain_skill="Logic"
        )
        
        # 状态更新由网关在内部完成（更新 Redis TPM/RPM 计数）
        return AgentResult(
            status="success",
            actual_cost=0, # 具体 Token 统计建议通过网关日志查看，此处为简化返回
            final_output=final_output
        )

# ================= 测试执行器 =================
if __name__ == "__main__":
    # 确保你的 .env 已经配置了完整的 API 密钥列表
    # 确保 Redis 服务已启动
    executor = MakerExecutor()
    
    test_task = "请写出查询电商系统‘前10名消费最高用户’的 SQL 语句，要求包含用户姓名、总金额，并按金额倒序。"
    
    # 执行测试：你会观察到网关在 Logic 和 Coding 池之间自动切换不同平台的模型
    result = executor.run_maker_k3(test_task)
    
    print("\n--- MAKER 集群共识输出 ---")
    print(result.final_output)