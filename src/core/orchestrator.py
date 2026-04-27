# src/core/orchestrator.py
# 主脑 - 核心编排逻辑

import asyncio
import json
import uuid
import time
import random
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from src.core.state import AgentStateMachine
from src.core.executor import AsyncAgentLegion
from src.data.database import AsyncSessionLocal, ExecutionLog, APIAsset
from src.data.memory import Memory
from src.data.schemas import JudgeResponse, EntityVerificationResponse
from src.core.prompts import JudgePrompts
from src.services.gateway import AsyncGateway
from src.services.sandbox.docker import DockerSandbox
from src.services.tracing import tracing
from src.config import config
from src.core.intent_analyzer import IntentAnalyzer

class AsyncRealOrchestrator:
    def __init__(self, trace_id: str = None, mcp_server_url: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.memory = Memory()
        self.gateway = AsyncGateway(trace_id=self.trace_id)
        self.sandbox = DockerSandbox()
        self.executor = AsyncAgentLegion(trace_id=self.trace_id, mcp_server_url=mcp_server_url)
        self.state_machine = AgentStateMachine(self)
        print(f"[Orchestrator] 初始化完成，Trace ID: {self.trace_id}")

    async def start_work(self, user_input: str, checkpoint_id: Optional[str] = None):
        with tracing.start_span("orchestrator.start_work", attributes={
            "user_input": user_input[:100],
            "trace_id": self.trace_id
        }) as span:
            print(f"\n[{self.trace_id}] ========================================")
            print(f"[{self.trace_id}] 接收到任务: {user_input}")
            print(f"[{self.trace_id}] ========================================")

            # 初始化执行器
            await self.executor.initialize()

            # 记忆检索
            with tracing.start_span("memory.retrieve"):
                previous_context = await self.memory.retrieve(user_input)
                if previous_context:
                    print(f"[{self.trace_id}] 从记忆中检索到相关信息")

            # 使用状态机执行任务
            with tracing.start_span("state_machine.run") as state_span:
                context = await self.state_machine.run({
                    "user_input": user_input,
                    "trace_id": self.trace_id,
                    "previous_context": previous_context
                }, checkpoint_id=checkpoint_id)

            # 记忆存储
            with tracing.start_span("memory.add_experience"):
                await self.memory.add_experience(user_input, context.get("final_answer", ""))

            # 记录执行日志
            with tracing.start_span("log.execution"):
                await self._log_execution(user_input, context)

            print(f"[{self.trace_id}] ========================================")
            print(f"[{self.trace_id}] 任务执行完成")
            print(f"[{self.trace_id}] ========================================")

            return context.get("final_answer", "任务执行失败")

    async def pause_work(self, context: Dict[str, Any], current_state: str) -> str:
        """暂停工作，创建检查点"""
        return await self.state_machine.pause(context, current_state)

    def list_checkpoints(self) -> List:
        """列出当前任务的所有检查点"""
        checkpoints = self.state_machine.list_checkpoints(self.trace_id)
        return [{
            "checkpoint_id": cp.checkpoint_id,
            "state_name": cp.state_name,
            "timestamp": cp.timestamp.isoformat()
        } for cp in checkpoints]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """获取检查点信息"""
        checkpoint = self.state_machine.get_checkpoint(checkpoint_id)
        if checkpoint:
            return {
                "checkpoint_id": checkpoint.checkpoint_id,
                "state_name": checkpoint.state_name,
                "context": checkpoint.context,
                "timestamp": checkpoint.timestamp.isoformat()
            }
        return None

    async def resume_work(self, checkpoint_id: str) -> str:
        """从检查点恢复工作"""
        checkpoint = self.state_machine.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return "检查点不存在"
        
        result = await self.state_machine.run(checkpoint.context, checkpoint_id=checkpoint_id)
        
        # 保存到记忆
        user_input = checkpoint.context.get("user_input", "")
        await self.memory.add_experience(user_input, result.get("final_answer", ""))
        
        # 记录执行日志
        await self._log_execution(user_input, result)
        
        return result.get("final_answer", "任务执行失败")

    async def time_travel(self, checkpoint_id: str) -> str:
        """时光倒流，从指定检查点重新执行"""
        return await self.resume_work(checkpoint_id)

    async def _log_execution(self, user_input: str, context: Dict[str, Any]):
        async with AsyncSessionLocal() as session:
            log = ExecutionLog(
                trace_id=self.trace_id,
                input_text=user_input,
                response=context.get("final_answer", ""),
                model_used=context.get("model_used", "unknown"),
                is_local_fallback=context.get("is_local_fallback", False),
                error_message=context.get("error", None),
                created_at=datetime.now()
            )
            session.add(log)
            await session.commit()

    async def _try_local_model(self, messages: List[Dict[str, str]]) -> Optional[str]:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=config.LM_STUDIO_URL,
                api_key="lm-studio"
            )
            response = await client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[Local Model Error] {e}")
            return None

    async def _safe_execute_code(self, code: str) -> str:
        try:
            result = await self.sandbox.execute_code(code, timeout=config.SANDBOX_TIMEOUT)
            return f"执行结果: {result}"
        except Exception as e:
            return f"执行错误: {str(e)}"

    async def _analyze_task(self, task: str) -> Dict[str, Any]:
        return await self.executor.analyze_task(task)

    async def _execute_task(self, task: str, task_type: str) -> str:
        return await self.executor.execute_task(task, task_type)

    async def _research_task(self, topic: str) -> str:
        return await self.executor.research_task(topic)

    async def _create_task(self, request: str) -> str:
        return await self.executor.create_task(request)

    async def _handle_error(self, error: str) -> str:
        messages = [
            {"role": "system", "content": "你是一个错误处理专家，能够分析错误并提供解决方案。"},
            {"role": "user", "content": f"错误信息: {error}\n\n请分析错误原因并提供解决方案。"}
        ]

        try:
            return await self.gateway.chat_completion(
                model="google/gemma-3-12b-it",
                messages=messages,
                domain_skill="ErrorHandling"
            )
        except Exception as e:
            print(f"[Error Handling Error] {e}")
            local_response = await self._try_local_model(messages)
            if local_response:
                return f"[本地模型] {local_response}"
            return "错误处理失败，请稍后重试。"

    async def run_reasoning_flow(self, messages: List[Dict[str, str]], trace: Optional[str] = None) -> str:
        """执行深度推理流程（Maker-Checker 模式）
        
        Args:
            messages: 消息列表
            trace: 追踪 ID
            
        Returns:
            融合后的响应
        """
        trace_id = trace or str(uuid.uuid4())
        
        with tracing.start_span("orchestrator.run_reasoning_flow", attributes={
            "trace_id": trace_id,
            "message_count": len(messages)
        }) as span:
            print(f"\n[{trace_id}] ========================================")
            print(f"[{trace_id}] 开始深度推理流程")
            print(f"[{trace_id}] ========================================")

            # 步骤 1: 并发拉取多个廉价模型生成
            with tracing.start_span("concurrent_generation"):
                # 获取可用节点
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select
                    result = await session.execute(
                        select(APIAsset).where(APIAsset.enabled == True)
                    )
                    nodes = [
                        {
                            "node_id": asset.id,
                            "model_name": asset.model_name,
                            "base_url": asset.base_url,
                            "api_key": asset.api_key
                        }
                        for asset in result.scalars().all()
                    ]

                if not nodes:
                    # 没有可用节点，使用本地模型
                    local_response = await self._try_local_model(messages)
                    return local_response or "所有模型都不可用"

                # 选择前 3 个节点进行并发请求
                selected_nodes = nodes[:3] if len(nodes) >= 3 else nodes
                tasks = [self._make_concurrent_request(node, messages) for node in selected_nodes]
                
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    print(f"[并发生成失败] {e}")
                    # 回退到本地模型
                    local_response = await self._try_local_model(messages)
                    return local_response or "并发生成失败"

                # 收集成功的响应
                successful_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"[节点 {i+1} 失败] {result}")
                    else:
                        successful_results.append(result)

                if not successful_results:
                    # 所有节点都失败，使用本地模型
                    local_response = await self._try_local_model(messages)
                    return local_response or "所有模型都失败"

            # 步骤 2: 使用四步 AI 裁判工作流
            with tracing.start_span("four_step_judge"):
                # 使用四步评审工作流
                final_answer, need_human_intervention = await self._four_step_judge_workflow(successful_results, nodes, trace_id)

            # 步骤 3: Pydantic 校验（简化版）
            with tracing.start_span("validation"):
                # 这里可以添加更复杂的 Pydantic 校验逻辑
                # 目前使用简单的长度检查
                if len(final_answer) < 10:
                    # 回答太短，使用本地模型重新生成
                    local_response = await self._try_local_model(messages)
                    final_answer = local_response or "回答验证失败"

            print(f"[{trace_id}] ========================================")
            print(f"[{trace_id}] 深度推理流程完成")
            print(f"[{trace_id}] ========================================")

            # 追踪到Langfuse
            system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), "")
            user_input = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")
            input_text = f"System: {system_prompt}\nUser: {user_input}"
            
            from src.services.llmops.langfuse import langfuse_integration
            langfuse_integration.trace_prompt(
                prompt_name="ReasoningFlow",
                prompt_version="1.0.0",
                input_text=input_text,
                output_text=final_answer,
                metadata={"trace_id": trace_id, "mode": "deep_reasoning"}
            )

            return final_answer

    async def _make_concurrent_request(self, node: Dict[str, Any], messages: List[Dict[str, str]]) -> str:
        """并发请求单个节点"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=node["base_url"],
                api_key=node["api_key"]
            )
            response = await client.chat.completions.create(
                model=node["model_name"],
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            raise e

    async def _four_step_judge_workflow(self, drafts: List[str], nodes: List[Dict[str, Any]], trace_id: str) -> Tuple[str, bool]:
        """四步 AI 裁判工作流
        
        Args:
            drafts: 草案列表
            nodes: 可用节点列表
            trace_id: 追踪 ID
            
        Returns:
            Tuple[str, bool]: (最终答案, 是否需要人工干预)
        """
        workflow_start_time = time.time()
        print(f"\n[Aagent 评审系统] ========================================")
        print(f"[Aagent 评审系统] 开始四步评审工作流 (开发模式: {config.DEV_MODE})")
        print(f"[Aagent 评审系统] ========================================")
        
        # 开发模式：快速失败检查
        if config.DEV_FAST_FAIL and not nodes:
            print("[开发模式] 无可用节点，快速失败")
            return await self._simple_fusion(drafts), False

        # Step 1: 盲测准备 (Blind Prep)
        step1_start = time.time()
        with tracing.start_span("blind_prep"):
            print("[Step 1] 盲测准备: 匿名化并打乱草案顺序")
            # 随机打乱顺序
            random.shuffle(drafts)
            # 重新标记为 Draft A, Draft B, Draft C
            anonymous_drafts = {}
            for i, draft in enumerate(drafts):
                draft_id = f"Draft {chr(65 + i)}"  # A, B, C
                anonymous_drafts[draft_id] = draft
            
            # 构建草稿文本
            drafts_text = ""
            for draft_id, draft_content in anonymous_drafts.items():
                drafts_text += f"{draft_id}:\n{draft_content}\n\n"
            
            step1_elapsed = time.time() - step1_start
            print(f"[Aagent 评审系统]：已生成 {len(drafts)} 份匿名草稿进行博弈。(耗时: {step1_elapsed:.2f}s)")

        # Step 2: 双角色打分 (Dual-Persona Scoring)
        step2_start = time.time()
        with tracing.start_span("dual_persona_scoring"):
            print("[Step 2] 双角色打分: 调用高算力节点进行评审")
            # 构建评审提示
            judge_prompt = JudgePrompts.DUAL_PERSONA_JUDGE_PROMPT.replace("{DRAFTS}", drafts_text)
            
            # 选择高算力节点
            high_power_node = None
            for node in nodes:
                if any(model in node["model_name"].lower() for model in ["gpt-4", "gemini-1.5", "claude-3"]):
                    high_power_node = node
                    break
            if not high_power_node:
                high_power_node = nodes[0]
            
            # 调用评审
            judge_messages = [
                {"role": "system", "content": "你是一个专业的AI评审系统，严格按照指示进行评审。"},
                {"role": "user", "content": judge_prompt}
            ]
            
            try:
                import httpx
                print(f"[Step 2] 开始评审请求 (超时: {config.REQUEST_TIMEOUT}s)")
                from openai import AsyncOpenAI
                http_client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT)
                client = AsyncOpenAI(
                    base_url=high_power_node["base_url"],
                    api_key=high_power_node["api_key"],
                    http_client=http_client
                )
                judge_response = await client.chat.completions.create(
                    model=high_power_node["model_name"],
                    messages=judge_messages,
                    temperature=0.7
                )
                judge_content = judge_response.choices[0].message.content
                step2_elapsed = time.time() - step2_start
                print(f"[Step 2] 评审请求成功 (耗时: {step2_elapsed:.2f}s)")
                
                # 解析评审结果
                judge_result = json.loads(judge_content)
                judge_response_obj = JudgeResponse(**judge_result)
                
                # 打印评审结果
                print("[评审结果]")
                for score in judge_response_obj.scores:
                    print(f"  {score.draft_id}: 事实准确性={score.factuality_score}, 逻辑自洽性={score.logic_score}, 执行效率={score.efficiency_score}")
                
                for vulnerability in judge_response_obj.vulnerabilities:
                    print(f"  [审查官警报]：{vulnerability.draft_id} 存在 {vulnerability.description} (Severity: {vulnerability.severity})")
                
                print(f"  [最终决策]：采纳 {judge_response_obj.best_draft_id}")
                print(f"  获胜理由: {judge_response_obj.winning_reason}")
                
            except asyncio.TimeoutError:
                step2_elapsed = time.time() - step2_start
                print(f"[Step 2] 评审请求超时 (耗时: {step2_elapsed:.2f}s)")
                # 回退到简单融合
                final_answer = await self._simple_fusion(drafts)
                return final_answer, False
            except Exception as e:
                step2_elapsed = time.time() - step2_start
                print(f"[Step 2] 评审失败 (耗时: {step2_elapsed:.2f}s): {e}")
                # 回退到简单融合
                final_answer = await self._simple_fusion(drafts)
                return final_answer, False

        # Step 3: 实体核查 (Entity Extraction)
        step3_start = time.time()
        with tracing.start_span("entity_extraction"):
            print("[Step 3] 实体核查: 对获胜方案进行实体提取和置信度评估")
            # 获取获胜方案
            best_draft_content = anonymous_drafts.get(judge_response_obj.best_draft_id, drafts[0])
            
            # 构建实体核查提示
            entity_prompt = JudgePrompts.ENTITY_VERIFICATION_PROMPT.replace("{WINNING_DRAFT}", best_draft_content)
            
            # 调用实体核查
            entity_messages = [
                {"role": "system", "content": "你是一个专业的实体核查专家，严格按照指示进行核查。"},
                {"role": "user", "content": entity_prompt}
            ]
            
            try:
                import httpx
                print(f"[Step 3] 开始实体核查请求 (超时: {config.REQUEST_TIMEOUT}s)")
                from openai import AsyncOpenAI
                http_client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT)
                client = AsyncOpenAI(
                    base_url=high_power_node["base_url"],
                    api_key=high_power_node["api_key"],
                    http_client=http_client
                )
                entity_response = await client.chat.completions.create(
                    model=high_power_node["model_name"],
                    messages=entity_messages,
                    temperature=0.7
                )
                entity_content = entity_response.choices[0].message.content
                step3_elapsed = time.time() - step3_start
                print(f"[Step 3] 实体核查请求成功 (耗时: {step3_elapsed:.2f}s)")
                
                # 解析实体核查结果
                entity_result = json.loads(entity_content)
                entity_response_obj = EntityVerificationResponse(**entity_result)
                
                # 打印实体核查结果
                print("[实体核查结果]")
                for entity in entity_response_obj.entities:
                    if entity.confidence == "Low":
                        print(f"  [低置信度] {entity.entity_name} - 核实关键词: {entity.verification_query}")
                    elif entity.confidence == "Medium":
                        print(f"  [中等置信度] {entity.entity_name} - 核实关键词: {entity.verification_query}")
                    else:
                        print(f"  [高置信度] {entity.entity_name}")
                
            except asyncio.TimeoutError:
                step3_elapsed = time.time() - step3_start
                print(f"[Step 3] 实体核查请求超时 (耗时: {step3_elapsed:.2f}s)")
                entity_response_obj = EntityVerificationResponse(entities=[])
            except Exception as e:
                step3_elapsed = time.time() - step3_start
                print(f"[Step 3] 实体核查失败 (耗时: {step3_elapsed:.2f}s): {e}")
                entity_response_obj = EntityVerificationResponse(entities=[])

        # Step 4: 人工锚定拦截点 (Human-in-the-Loop Anchoring)
        step4_start = time.time()
        with tracing.start_span("human_in_the_loop"):
            print("[Step 4] 人工锚定拦截: 检查高危漏洞和低置信度实体")
            
            # 检查高危漏洞
            high_risk_vulnerabilities = [v for v in judge_response_obj.vulnerabilities if v.severity == "High"]
            
            # 检查低置信度实体
            low_confidence_entities = [e for e in entity_response_obj.entities if e.confidence == "Low"]
            
            # 决定是否需要人工干预
            need_human_intervention = bool(high_risk_vulnerabilities or low_confidence_entities)
            
            # 开发模式：跳过人工干预，快速通过
            if config.DEV_MODE and config.DEV_FAST_FAIL:
                print("[开发模式] 跳过人工干预，快速通过")
                need_human_intervention = False
            
            if need_human_intervention:
                print("[系统挂起] 🚨 发现高危漏洞或低置信度实体，等待人工核实与指令...")
                
                # 打印详细信息
                if high_risk_vulnerabilities:
                    print("[高危漏洞]")
                    for vuln in high_risk_vulnerabilities:
                        print(f"  - {vuln.description} (Draft: {vuln.draft_id})")
                
                if low_confidence_entities:
                    print("[低置信度实体]")
                    for entity in low_confidence_entities:
                        print(f"  - {entity.entity_name} - 核实关键词: {entity.verification_query}")
                
                # 模拟人工输入（实际应用中应该通过前端或控制台交互）
                print("\n请在搜索引擎核实上述实体，输入 y 继续执行，或输入 n 废弃方案:")
                # 这里简化处理，默认继续执行
                user_input = "y"
                print(f"模拟用户输入: {user_input}")
                
                if user_input.lower() != "y":
                    return "方案被人工废弃", True
            else:
                print("[系统放行] 未发现高危风险，方案正常执行")
            
            step4_elapsed = time.time() - step4_start
            print(f"[Step 4] 人工锚定拦截完成 (耗时: {step4_elapsed:.2f}s)")

        # 返回最终结果
        final_answer = best_draft_content
        workflow_elapsed = time.time() - workflow_start_time
        print(f"\n[Aagent 评审系统] ========================================")
        print(f"[Aagent 评审系统] 四步评审工作流完成 (总耗时: {workflow_elapsed:.2f}s)")
        print(f"[Aagent 评审系统] ========================================")
        
        return final_answer, need_human_intervention

    async def run_dynamic_reasoning(self, task: str, model_pool: List[Dict[str, Any]]) -> str:
        """执行动态推理流
        
        Args:
            task: 任务描述
            model_pool: 模型池
            
        Returns:
            推理结果
        """
        with tracing.start_span("orchestrator.run_dynamic_reasoning", attributes={
            "task": task[:100],
            "model_count": len(model_pool)
        }) as span:
            print(f"\n[{self.trace_id}] ========================================")
            print(f"[{self.trace_id}] 开始动态推理流")
            print(f"[{self.trace_id}] ========================================")
            
            # 分类任务类型
            task_type = IntentAnalyzer.classify_task_type(task)
            print(f"[{self.trace_id}] 任务类型: {task_type}")
            
            # 根据任务类型选择推理策略
            if task_type == "Tool/Code":
                result = await self._run_react_loop(task, model_pool)
            elif task_type == "Logic/Math":
                result = await self._run_plan_and_solve(task, model_pool)
            else:  # Writing/Design
                result = await self._run_reflexion(task, model_pool)
            
            print(f"\n[{self.trace_id}] ========================================")
            print(f"[{self.trace_id}] 动态推理流完成")
            print(f"[{self.trace_id}] ========================================")
            
            return result
    
    async def _run_react_loop(self, task: str, model_pool: List[Dict[str, Any]]) -> str:
        """运行 ReAct 循环（工具/代码类任务）"""
        print(f"[{self.trace_id}] 采用 ReAct Loop 策略")
        
        MAX_ITERATIONS = 5
        MAX_OBSERVATION_TOKENS = 500
        
        # 构建 ReAct 提示
        react_prompt = f"""你是一个解决问题的专家，采用 ReAct 模式：思考 -> 行动 -> 观察 -> 修正。
        
        任务：{task}
        
        请按照以下格式输出：
        
        思考：[你的思考过程]
        行动：[你要执行的代码或操作]
        观察：[执行结果]
        修正：[根据观察结果的修正]
        
        重复这个过程，直到问题解决。
        """
        
        # 初始化消息
        messages = [
            {"role": "system", "content": "你是一个解决问题的专家，擅长使用 ReAct 模式解决工具和代码相关问题。"},
            {"role": "user", "content": react_prompt}
        ]
        
        # 历史记录
        history = []
        
        # 选择合适的模型
        model = self._select_model(model_pool, task_type="Tool/Code")
        
        try:
            for iteration in range(MAX_ITERATIONS):
                print(f"[{self.trace_id}] ReAct 迭代 {iteration+1}/{MAX_ITERATIONS}")
                
                # 构建当前消息（包含历史记录的滑动窗口）
                current_messages = self._build_react_messages(messages, history, MAX_OBSERVATION_TOKENS)
                
                # 调用模型
                response = await self.gateway.chat_completion(
                    model=model["model_name"],
                    messages=current_messages,
                    domain_skill="CodeExecution"
                )
                
                # 提取 ReAct 组件
                import re
                thought_match = re.search(r"思考：(.*?)(?=行动：|$)", response)
                action_match = re.search(r"行动：(.*?)(?=观察：|修正：|$)", response)
                correction_match = re.search(r"修正：(.*?)(?=思考：|$)", response)
                
                thought = thought_match.group(1).strip() if thought_match else ""
                action = action_match.group(1).strip() if action_match else ""
                correction = correction_match.group(1).strip() if correction_match else ""
                
                # 执行行动
                observation = ""
                if action:
                    print(f"[{self.trace_id}] 执行代码:")
                    print(action)
                    execution_result = await self._safe_execute_code(action)
                    print(f"[{self.trace_id}] 执行结果: {execution_result}")
                    observation = execution_result
                
                # 记录历史
                history.append({
                    "thought": thought,
                    "action": action,
                    "observation": observation,
                    "correction": correction
                })
                
                # 检查是否解决
                if "问题已解决" in response or "完成" in response or not action:
                    print(f"[{self.trace_id}] ReAct 循环结束")
                    break
            
            # 基于最终结果生成答案
            final_answer = await self._generate_final_answer(task, history)
            return final_answer
        except Exception as e:
            print(f"[ReAct Loop Error] {e}")
            # 回退到本地模型
            local_response = await self._try_local_model(messages)
            return local_response or "ReAct 循环执行失败"
    
    def _build_react_messages(self, base_messages: list, history: list, max_observation_tokens: int) -> list:
        """构建包含历史记录的消息，实现滑动窗口和信息浓缩"""
        messages = base_messages.copy()
        
        # 处理历史记录
        if history:
            # 只保留最近的几条记录
            recent_history = history[-3:]  # 滑动窗口大小为3
            
            for i, entry in enumerate(recent_history):
                # 浓缩观察结果
                observation = entry["observation"]
                if len(observation) > max_observation_tokens:
                    observation = self._summarize_observation(observation)
                
                # 构建历史消息
                history_content = f"""
                迭代 {len(history) - len(recent_history) + i + 1}:
                思考：{entry["thought"]}
                行动：{entry["action"]}
                观察：{observation}
                修正：{entry["correction"]}
                """
                messages.append({"role": "assistant", "content": history_content})
        
        return messages
    
    def _summarize_observation(self, observation: str) -> str:
        """浓缩观察结果"""
        # 简单的浓缩逻辑
        if "错误" in observation or "Exception" in observation:
            # 提取错误类型和关键信息
            import re
            error_match = re.search(r"(\w+Error): (.*?)(?=\\n|$)", observation)
            if error_match:
                error_type = error_match.group(1)
                error_msg = error_match.group(2)
                return f"尝试执行操作，由于 {error_type}: {error_msg} 失败"
            return "尝试执行操作失败"
        else:
            # 对于成功的执行结果，提取关键信息
            lines = observation.split('\n')
            if len(lines) > 3:
                return f"执行成功，输出: {lines[0]}... (共 {len(lines)} 行)"
            return observation
    
    async def _generate_final_answer(self, task: str, history: list) -> str:
        """基于历史记录生成最终答案"""
        # 构建总结提示
        history_summary = ""
        for i, entry in enumerate(history):
            history_summary += f"迭代 {i+1}: 思考 '{entry['thought'][:50]}...', 行动 '{entry['action'][:50]}...', 观察 '{entry['observation'][:50]}...'\n"
        
        final_prompt = f"""基于以下 ReAct 历史记录，生成最终答案：
        
        任务：{task}
        
        历史记录：
        {history_summary}
        
        请生成一个清晰、完整的最终答案，总结解决问题的过程和结果。
        """
        
        final_messages = [
            {"role": "system", "content": "你是一个总结专家，基于 ReAct 历史记录生成最终答案。"},
            {"role": "user", "content": final_prompt}
        ]
        
        # 选择合适的模型
        model_pool = await self._get_model_pool()
        model = self._select_model(model_pool, task_type="Writing/Design")
        
        try:
            final_response = await self.gateway.chat_completion(
                model=model["model_name"],
                messages=final_messages,
                domain_skill="Summary"
            )
            return final_response
        except Exception as e:
            print(f"[Generate Final Answer Error] {e}")
            # 回退到本地模型
            local_response = await self._try_local_model(final_messages)
            return local_response or "生成最终答案失败"
    
    async def _get_model_pool(self) -> List[Dict[str, Any]]:
        """获取模型池"""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(APIAsset).where(APIAsset.enabled == True)
                )
                nodes = [
                    {
                        "node_id": asset.id,
                        "model_name": asset.model_name,
                        "base_url": asset.base_url,
                        "api_key": asset.api_key
                    }
                    for asset in result.scalars().all()
                ]
            return nodes
        except Exception as e:
            print(f"[Get Model Pool Error] {e}")
            return []

    async def _simple_fusion(self, drafts: List[str]) -> str:
        """简单融合逻辑（作为回退）"""
        fusion_prompt = "你是一个专业的 AI 融合专家，能够综合多个 AI 的回答，生成一个更全面、更准确的最终回答。\n\n"
        fusion_prompt += "以下是多个 AI 对同一个问题的回答：\n\n"
        
        for i, draft in enumerate(drafts):
            fusion_prompt += f"AI {i+1}: {draft}\n\n"
        
        fusion_prompt += "请基于以上回答，生成一个综合的、高质量的最终回答。"
        
        # 使用本地模型进行融合
        messages = [{"role": "user", "content": fusion_prompt}]
        local_response = await self._try_local_model(messages)
        return local_response or "融合失败"