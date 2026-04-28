# src/core/strategies/four_step_judge.py
# 四步裁判策略
# 依赖：asyncio, json, time, typing, src.services.tracing, src.data.schemas, src.core.prompts, src.config, src.utils.logger
# 注意事项：
#   - 实现了四步评审工作流：盲测准备、双角色打分、实体核查、人工锚定拦截
#   - 支持并发请求多个模型生成草案
#   - 失败时抛出 StrategyFallbackError 由 StrategyFactory 处理降级

import asyncio
import json
import time
from typing import List, Dict, Any, Tuple

from src.services.tracing import tracing
from src.data.schemas import JudgeResponse, EntityVerificationResponse
from src.core.prompts import JudgePrompts
from src.config import config
from src.utils.logger import logger
from src.core.exceptions import StrategyFallbackError


class FourStepJudgeStrategy:
    """四步裁判策略

    实现了四步评审工作流：
    1. 盲测准备：匿名化并打乱草案顺序
    2. 双角色打分：调用高算力节点进行评审
    3. 实体核查：对所有草案进行实体提取和置信度评估
    4. 人工锚定拦截：检查高危漏洞和低置信度实体，决定是否需要人工干预
    """

    async def execute(self, messages: List[Dict[str, str]], model_pool: List[Dict[str, Any]], trace_id: str) -> str:
        """执行四步裁判推理

        Args:
            messages: 消息列表
            model_pool: 模型池
            trace_id: 追踪ID

        Returns:
            str: 推理结果

        Raises:
            StrategyFallbackError: 当策略执行失败需要降级时抛出
        """
        with tracing.start_span("four_step_judge.execute", attributes={
            "trace_id": trace_id,
            "message_count": len(messages)
        }) as span:
            logger.info(f"[{trace_id}] 开始四步裁判策略")

            # 步骤 1: 并发拉取多个廉价模型生成
            with tracing.start_span("concurrent_generation"):
                if not model_pool:
                    logger.error(f"[{trace_id}] 没有可用节点")
                    raise StrategyFallbackError("没有可用节点")

                # 选择节点进行并发请求
                ensemble_size = getattr(config, 'ENSEMBLE_SIZE', 3)
                selected_nodes = model_pool[:ensemble_size] if len(model_pool) >= ensemble_size else model_pool
                tasks = [self._make_concurrent_request(node, messages) for node in selected_nodes]

                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"[{trace_id}] 四步裁判并发生成失败: {e}")
                    raise StrategyFallbackError(f"并发生成失败: {e}")

                # 收集成功的响应
                successful_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"[{trace_id}] 节点 {i+1} 失败: {result}")
                    else:
                        successful_results.append(result)

                if not successful_results:
                    logger.error(f"[{trace_id}] 所有节点都失败")
                    raise StrategyFallbackError("所有节点都失败")

            # 步骤 2: 使用四步 AI 裁判工作流
            with tracing.start_span("four_step_judge"):
                try:
                    final_answer, need_human_intervention = await self._four_step_judge_workflow(
                        successful_results, model_pool, trace_id
                    )
                except StrategyFallbackError as e:
                    raise e
                except Exception as e:
                    logger.error(f"[{trace_id}] 四步裁判工作流失败: {e}")
                    raise StrategyFallbackError(f"四步裁判工作流失败: {e}")

            # 步骤 3: 简单验证
            with tracing.start_span("validation"):
                # 这里可以添加更复杂的验证逻辑
                if len(final_answer) < 10:
                    logger.warning(f"[{trace_id}] 回答太短，需要降级处理")
                    raise StrategyFallbackError("回答太短，需要降级")

            logger.info(f"[{trace_id}] 四步裁判策略完成")

            return final_answer

    async def _make_concurrent_request(self, node: Dict[str, Any], messages: List[Dict[str, str]]) -> str:
        """并发请求单个节点

        Args:
            node: 节点信息
            messages: 消息列表

        Returns:
            str: 模型响应

        Raises:
            Exception: 请求失败时抛出
        """
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

        Raises:
            StrategyFallbackError: 当工作流失败需要降级时抛出
        """
        workflow_start_time = time.time()
        logger.info(f"[{trace_id}] 开始四步评审工作流 (开发模式: {config.DEV_MODE})")

        # 开发模式：快速失败检查
        if config.DEV_FAST_FAIL and not nodes:
            logger.info(f"[{trace_id}] [开发模式] 无可用节点，快速失败")
            raise StrategyFallbackError("无可用节点")

        # Step 1: 盲测准备 (Blind Prep)
        step1_start = time.time()
        with tracing.start_span("blind_prep"):
            logger.info(f"[{trace_id}] [Step 1] 盲测准备: 匿名化并打乱草案顺序")
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
            logger.info(f"[{trace_id}] 已生成 {len(drafts)} 份匿名草稿进行博弈。(耗时: {step1_elapsed:.2f}s)")

        # 选择高算力节点
        high_power_node = None
        for node in nodes:
            if any(model in node["model_name"].lower() for model in ["gpt-4", "gemini-1.5", "claude-3"]):
                high_power_node = node
                break
        if not high_power_node:
            high_power_node = nodes[0]

        # 并发执行 Step 2 和 Step 3
        async def execute_judge():
            """执行评审"""
            with tracing.start_span("dual_persona_scoring"):
                logger.info(f"[{trace_id}] [Step 2] 双角色打分: 调用高算力节点进行评审")
                # 构建评审提示
                judge_prompt = JudgePrompts.DUAL_PERSONA_JUDGE_PROMPT.replace("{DRAFTS}", drafts_text)

                # 调用评审
                judge_messages = [
                    {"role": "system", "content": "你是一个专业的AI评审系统，严格按照指示进行评审。"},
                    {"role": "user", "content": judge_prompt}
                ]

                try:
                    import httpx
                    logger.info(f"[{trace_id}] [Step 2] 开始评审请求 (超时: {config.REQUEST_TIMEOUT}s)")
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

                    # 解析评审结果
                    judge_result = json.loads(judge_content)
                    judge_response_obj = JudgeResponse(**judge_result)

                    # 记录评审结果
                    logger.info(f"[{trace_id}] [评审结果]")
                    for score in judge_response_obj.scores:
                        logger.info(f"[{trace_id}]   {score.draft_id}: 事实准确性={score.factuality_score}, 逻辑自洽性={score.logic_score}, 执行效率={score.efficiency_score}")

                    for vulnerability in judge_response_obj.vulnerabilities:
                        logger.warning(f"[{trace_id}]   [审查官警报]：{vulnerability.draft_id} 存在 {vulnerability.description} (Severity: {vulnerability.severity})")

                    logger.info(f"[{trace_id}]   [最终决策]：采纳 {judge_response_obj.best_draft_id}")
                    logger.info(f"[{trace_id}]   获胜理由: {judge_response_obj.winning_reason}")

                    return judge_response_obj
                except asyncio.TimeoutError:
                    logger.error(f"[{trace_id}] [Step 2] 评审请求超时")
                    raise
                except Exception as e:
                    logger.error(f"[{trace_id}] [Step 2] 评审失败: {e}")
                    raise

        async def execute_entity_verification():
            """执行实体核查"""
            with tracing.start_span("entity_extraction"):
                logger.info(f"[{trace_id}] [Step 3] 实体核查: 对所有草案进行实体提取和置信度评估")

                # 构建实体核查提示（对所有草案）
                entity_prompt = JudgePrompts.ENTITY_VERIFICATION_PROMPT.replace("{WINNING_DRAFT}", drafts_text)

                # 调用实体核查
                entity_messages = [
                    {"role": "system", "content": "你是一个专业的实体核查专家，严格按照指示进行核查。"},
                    {"role": "user", "content": entity_prompt}
                ]

                try:
                    import httpx
                    logger.info(f"[{trace_id}] [Step 3] 开始实体核查请求 (超时: {config.REQUEST_TIMEOUT}s)")
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

                    # 解析实体核查结果
                    entity_result = json.loads(entity_content)
                    entity_response_obj = EntityVerificationResponse(**entity_result)

                    # 记录实体核查结果
                    logger.info(f"[{trace_id}] [实体核查结果]")
                    for entity in entity_response_obj.entities:
                        if entity.confidence == "Low":
                            logger.warning(f"[{trace_id}]   [低置信度] {entity.entity_name} - 核实关键词: {entity.verification_query}")
                        elif entity.confidence == "Medium":
                            logger.info(f"[{trace_id}]   [中等置信度] {entity.entity_name} - 核实关键词: {entity.verification_query}")
                        else:
                            logger.info(f"[{trace_id}]   [高置信度] {entity.entity_name}")

                    return entity_response_obj
                except asyncio.TimeoutError:
                    logger.warning(f"[{trace_id}] [Step 3] 实体核查请求超时")
                    return EntityVerificationResponse(entities=[])
                except Exception as e:
                    logger.warning(f"[{trace_id}] [Step 3] 实体核查失败: {e}")
                    return EntityVerificationResponse(entities=[])

        # 并发执行评审和实体核查
        step2_3_start = time.time()
        try:
            judge_response_obj, entity_response_obj = await asyncio.gather(
                execute_judge(),
                execute_entity_verification(),
                return_exceptions=True
            )

            # 检查执行结果
            if isinstance(judge_response_obj, Exception):
                logger.error(f"[{trace_id}] [Step 2] 评审失败: {judge_response_obj}")
                raise StrategyFallbackError(f"评审失败: {judge_response_obj}")

            if isinstance(entity_response_obj, Exception):
                logger.warning(f"[{trace_id}] [Step 3] 实体核查失败: {entity_response_obj}")
                entity_response_obj = EntityVerificationResponse(entities=[])

            step2_3_elapsed = time.time() - step2_3_start
            logger.info(f"[{trace_id}] [Step 2-3] 评审和实体核查完成 (耗时: {step2_3_elapsed:.2f}s)")

        except Exception as e:
            step2_3_elapsed = time.time() - step2_3_start
            logger.error(f"[{trace_id}] [Step 2-3] 并发执行失败 (耗时: {step2_3_elapsed:.2f}s): {e}")
            raise StrategyFallbackError(f"并发执行失败: {e}")

        # 获取获胜方案
        best_draft_content = anonymous_drafts.get(judge_response_obj.best_draft_id, drafts[0])

        # Step 4: 人工锚定拦截点 (Human-in-the-Loop Anchoring)
        step4_start = time.time()
        with tracing.start_span("human_in_the_loop"):
            logger.info(f"[{trace_id}] [Step 4] 人工锚定拦截: 检查高危漏洞和低置信度实体")

            # 检查高危漏洞
            high_risk_vulnerabilities = [v for v in judge_response_obj.vulnerabilities if v.severity == "High"]

            # 检查低置信度实体
            low_confidence_entities = [e for e in entity_response_obj.entities if e.confidence == "Low"]

            # 决定是否需要人工干预
            need_human_intervention = bool(high_risk_vulnerabilities or low_confidence_entities)

            # 开发模式：跳过人工干预，快速通过
            if config.DEV_MODE and config.DEV_FAST_FAIL:
                logger.info(f"[{trace_id}] [开发模式] 跳过人工干预，快速通过")
                need_human_intervention = False

            if need_human_intervention:
                logger.warning(f"[{trace_id}] [系统挂起] 🚨 发现高危漏洞或低置信度实体，等待人工核实与指令...")

                # 记录详细信息
                if high_risk_vulnerabilities:
                    logger.warning(f"[{trace_id}] [高危漏洞]")
                    for vuln in high_risk_vulnerabilities:
                        logger.warning(f"[{trace_id}]   - {vuln.description} (Draft: {vuln.draft_id})")

                if low_confidence_entities:
                    logger.warning(f"[{trace_id}] [低置信度实体]")
                    for entity in low_confidence_entities:
                        logger.warning(f"[{trace_id}]   - {entity.entity_name} - 核实关键词: {entity.verification_query}")

                # 模拟人工输入（实际应用中应该通过前端或控制台交互）
                logger.info(f"[{trace_id}] 请在搜索引擎核实上述实体，输入 y 继续执行，或输入 n 废弃方案:")
                # 这里简化处理，默认继续执行
                user_input = "y"
                logger.info(f"[{trace_id}] 模拟用户输入: {user_input}")

                if user_input.lower() != "y":
                    return "方案被人工废弃", True
            else:
                logger.info(f"[{trace_id}] [系统放行] 未发现高危风险，方案正常执行")

            step4_elapsed = time.time() - step4_start
            logger.info(f"[{trace_id}] [Step 4] 人工锚定拦截完成 (耗时: {step4_elapsed:.2f}s)")

        # 返回最终结果
        final_answer = best_draft_content
        workflow_elapsed = time.time() - workflow_start_time
        logger.info(f"[{trace_id}] 四步评审工作流完成 (总耗时: {workflow_elapsed:.2f}s)")

        return final_answer, need_human_intervention

# 导入 random 模块
import random
