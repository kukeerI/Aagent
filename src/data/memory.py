# src/data/memory.py
# 记忆系统 - GraphRAG实现
# 用途: 实现记忆系统的管理，包括短期记忆、长期记忆、逻辑依赖图和知识图谱的维护与检索功能。
# 依赖: networkx, asyncio, pydantic, typing, datetime, re, hashlib, json, src.config, src.utils.parser, src.utils.logger
# 注意事项:
#   1. 知识图谱使用NetworkX实现，注意节点和边的数据结构。
#   2. 实体和关系提取使用大模型结构化输出（Pydantic Schema约束），废弃了原有脆弱的正则表达式。
#   3. 本系统为GraphRAG实现的核心记忆模块，与外部系统交互需要通过异步方法。

import asyncio
import networkx as nx
from typing import List, Dict, Any, Optional, Set, Tuple, TYPE_CHECKING
from datetime import datetime
import re
import hashlib
import json

from pydantic import BaseModel, Field

import aiofiles

from src.config import config
from src.utils.parser import extract_json
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.services.gateway import AsyncGateway


# ==================== LLM 结构化输出 Schema ====================

class ExtractedEntity(BaseModel):
    name: str = Field(..., description="实体名称，如 'Python', '张三'")
    entity_type: str = Field(..., description="实体类型，如 'Technology', 'Person'")


class ExtractedRelation(BaseModel):
    source: str = Field(..., description="源实体名称")
    target: str = Field(..., description="目标实体名称")
    relationship_type: str = Field(..., description="关系类型，如 'uses', 'developed_by'")
    strength: float = Field(default=0.8, description="关系置信度 0.0-1.0")


class KnowledgeExtractionResult(BaseModel):
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelation]


class KnowledgeGraphUpdate(BaseModel):
    entities: List[Dict[str, str]] = Field(description="实体列表: [{'name': '...', 'type': '...'}]")
    relations: List[Dict[str, Any]] = Field(description="关系列表: [{'source': '...', 'target': '...', 'relation': '...'}]")


# ==================== 工作记忆滑动窗口 ====================

class WorkingMemory:
    """情景记忆（工作记忆）管理器：负责防止对话记录溢出，并在归档时实现"图谱自愈"

    特性：
    - 滑动窗口：保留最近 N 轮对话，超出阈值触发归档
    - 并行归档：文本摘要 + 知识图谱提取同时执行，防止精度丢失
    - 图谱自愈：归档消息中的实体关系被提取并永久存入 knowledge_graph
    - 上下文增强：get_augmented_context 基于查询词从图谱中召回关联三元组
    """

    def __init__(self, max_history_turns: int = 10):
        self.max_history_turns = max_history_turns
        self.history: List[Dict[str, str]] = []
        self.global_summary: str = ""

    async def add_interaction(self, role: str, content: str, gateway: "AsyncGateway", memory: "Memory"):
        """添加对话，并在触发阈值时执行滑动压缩与图谱归档"""
        self.history.append({"role": role, "content": content})

        if len(self.history) > self.max_history_turns:
            await self._archiving_process(gateway, memory)

    async def _archiving_process(self, gateway: "AsyncGateway", memory: "Memory"):
        """优雅的归档：文本摘要 + 知识提取并行执行

        当滑动窗口超出阈值，将早期消息并行做两件事：
        1. 文本摘要 — 保留语义精华
        2. 图谱抽取 — 将实体关系永久存入 NetworkX，确保"记忆精度"不丢失
        """
        to_archive = self.history[:-4]
        self.history = self.history[-4:]

        context_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_archive])

        tasks = [
            self._summarize_text(context_text, gateway),
            self._extract_entities_to_graph(context_text, gateway, memory)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summary_result = results[0]
        if isinstance(summary_result, Exception):
            logger.error(f"[WorkingMemory] 归档摘要失败: {summary_result}")
        else:
            self.global_summary = summary_result
            logger.info("[WorkingMemory] 归档摘要成功")

        extract_result = results[1]
        if isinstance(extract_result, Exception):
            logger.error(f"[WorkingMemory] 归档图谱提取失败: {extract_result}")
        else:
            logger.info("[WorkingMemory] 归档图谱提取成功")

    async def _summarize_text(self, text: str, gateway: "AsyncGateway") -> str:
        """将归档文本压缩为摘要，并与已有全局摘要融合"""
        prompt = f"""请将以下对话总结为一段紧凑的摘要，提取关键事实、用户的偏好和已达成结论的任务。
之前的旧摘要：{self.global_summary}
新对话记录：
{text}
请将两者融合，输出一份最新的全局摘要："""

        msgs = [{"role": "user", "content": prompt}]
        new_summary = await gateway.fast_route(messages=msgs, domain_skill="Summarization")
        return new_summary

    async def _extract_entities_to_graph(self, text: str, gateway: "AsyncGateway", memory: "Memory"):
        """利用 LLM 将即将丢失的上下文转化为永久图谱记忆

        从待归档文本中提取实体和关系，通过 memory._upsert_entity / _upsert_relationship
        写入 knowledge_graph，确保硬逻辑被永久保留。
        """
        prompt = f"""请从以下对话中提取核心知识点，以 JSON 格式输出实体和关系。
必须严格按照以下 JSON Schema 输出，不要输出任何额外的 markdown 标记：
{{
  "entities": [
    {{"name": "实体名称", "type": "实体类型"}}
  ],
  "relations": [
    {{"source": "源实体名称", "target": "目标实体名称", "relation": "关系类型"}}
  ]
}}

对话内容：
{text}
"""
        try:
            msgs = [
                {"role": "system", "content": "你是一个知识抽取专家，擅长从对话中提取实体和关系。请严格按照 JSON 格式输出。"},
                {"role": "user", "content": prompt}
            ]
            raw_response = await gateway.fast_route(messages=msgs, domain_skill="Extraction")

            clean_json = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if not clean_json:
                raise ValueError("未在响应中找到 JSON 对象")
            data = KnowledgeGraphUpdate.model_validate_json(clean_json.group(0))

            for ent in data.entities:
                memory._upsert_entity(ent["name"], ent.get("type", "Unknown"))

            for rel in data.relations:
                memory._upsert_relationship(
                    rel["source"],
                    rel["target"],
                    rel.get("relation", "related_to"),
                    0.8
                )
        except Exception as e:
            logger.error(f"[WorkingMemory] 图谱提取失败，但不影响主流程: {e}")
            raise

    def get_augmented_context(self, current_query: str, knowledge_graph: nx.DiGraph) -> str:
        """从图谱中根据当前问题检索 1-degree 关联知识，注入上下文

        将查询词分词后，对每个匹配的图节点提取 ego_graph 一度关系，
        格式化为三元组文本，作为背景知识注入 System Prompt。
        """
        query_keywords = self._simple_tokenize(current_query)
        related_knowledge: List[str] = []

        for word in query_keywords:
            if knowledge_graph.has_node(word):
                subgraph = nx.ego_graph(knowledge_graph, word, radius=1)
                for u, v, d in subgraph.edges(data=True):
                    rel = d.get('relationship_type', d.get('relation', 'related_to'))
                    related_knowledge.append(f"({u}) --[{rel}]--> ({v})")

        if not related_knowledge:
            return ""

        return "背景知识图谱关联：\n" + "\n".join(sorted(set(related_knowledge)))

    @staticmethod
    def _simple_tokenize(text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def get_full_context(self, query: str = "", knowledge_graph: Optional[nx.DiGraph] = None) -> List[Dict[str, str]]:
        """组装完整的上下文投递给最终模型

        如果提供了 query 和 knowledge_graph，会自动注入关联三元组作为背景知识。

        Args:
            query: 当前用户查询（用于图谱召回）
            knowledge_graph: NetworkX DiGraph（用于三元组检索）

        Returns:
            List[Dict[str, str]]: 可直接作为 LLM messages 使用的上下文列表
        """
        context_msgs: List[Dict[str, str]] = []

        context_parts = []
        if self.global_summary:
            context_parts.append(f"[系统自动生成的早期历史摘要]\n{self.global_summary}")

        if query and knowledge_graph is not None:
            triples = self.get_augmented_context(query, knowledge_graph)
            if triples:
                context_parts.append(triples)

        if context_parts:
            context_msgs.append({
                "role": "system",
                "content": "\n\n".join(context_parts)
            })

        context_msgs.extend(self.history)
        return context_msgs


# ==================== 记忆系统主类 ====================

class Memory:
    """记忆系统主类

    用于管理短期记忆、长期记忆、逻辑依赖图和知识图谱。
    核心升级：使用大模型结构化输出替代正则表达式进行实体和关系抽取。
    """

    def __init__(self):
        self.short_term_memory: List[Dict[str, Any]] = []
        self.long_term_memory: List[Dict[str, Any]] = []
        self.logical_memory = nx.DiGraph()
        self.knowledge_graph = nx.DiGraph()
        self.working_memory = WorkingMemory()
        self.entities: Dict[str, ExtractedEntity] = {}
        self.relationships: Dict[Tuple[str, str, str], ExtractedRelation] = {}
        self.max_short_term = config.MAX_SHORT_TERM_MEMORY
        logger.info("[Memory] 初始化成功 (混合记忆引擎)")

    # ==================== 核心升级：基于 LLM 的知识抽取 ====================

    async def extract_knowledge_via_llm(self, text: str, gateway: "AsyncGateway") -> None:
        """核心升级：使用大模型替代正则进行实体和关系抽取

        通过 AsyncGateway 调用 LLM，获取结构化 JSON 输出，
        再经过 Pydantic 严格校验后更新知识图谱。

        Args:
            text: 待抽取的文本
            gateway: 异步网关实例，通过参数注入避免阻塞
        """
        if not text or len(text.strip()) < 10:
            return

        prompt = f"""请从以下文本中提取核心实体和它们之间的关系。
必须严格按照提供的 JSON Schema 输出，不要输出任何额外的 markdown 标记。
{{
  "entities": [
    {{"name": "实体名称", "entity_type": "实体类型"}}
  ],
  "relationships": [
    {{"source": "源实体名称", "target": "目标实体名称", "relationship_type": "关系类型", "strength": 0.8}}
  ]
}}

文本内容：
{text}
"""
        try:
            messages = [
                {"role": "system", "content": "你是一个知识抽取专家，擅长从文本中提取实体和关系。请严格按照 JSON 格式输出。"},
                {"role": "user", "content": prompt}
            ]
            raw_response = await gateway.chat_completion(
                model=config.DEFAULT_EXECUTION_MODEL,
                messages=messages,
                domain_skill="Extraction"
            )

            parsed = extract_json(raw_response)
            result = KnowledgeExtractionResult.model_validate(parsed)

            for ent in result.entities:
                self._upsert_entity(ent.name, ent.entity_type)

            for rel in result.relationships:
                self._upsert_relationship(rel.source, rel.target, rel.relationship_type, rel.strength)

            logger.info(f"[Memory] 成功抽取 {len(result.entities)} 个实体与 {len(result.relationships)} 条关系")
        except Exception as e:
            logger.error(f"[Memory] 知识抽取失败 (可能是模型输出非标准 JSON): {e}")

    async def _llm_extract_knowledge(self, text: str, gateway: "AsyncGateway", task_level: str = "L4") -> None:
        """LLM 辅助提取：当任务等级为 L4 以上时，由 AgentExecutor 驱动进行实体关系抽取

        参考 src/data/schemas.py 中的 EntityCheck / EntityVerificationResponse 设计，
        使用 Pydantic 模型严格校验 LLM 输出，确保语义提取的健壮性。

        Args:
            text: 待抽取文本
            gateway: 异步网关实例
            task_level: 任务等级标识，仅 L4 及以上触发
        """
        level_map = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
        current_level = level_map.get(task_level.upper(), 0)
        if current_level < 4:
            return

        if not text or len(text.strip()) < 10:
            return

        prompt = f"""请从以下文本中提取核心实体和它们之间的关系。
要求：
1. 实体需包含名称和类型（如 Person, Technology, Organization, Location, Concept）
2. 关系需描述实体间的具体语义关联
3. 必须严格按照 JSON Schema 输出

{{
  "entities": [
    {{"name": "实体名称", "entity_type": "实体类型"}}
  ],
  "relationships": [
    {{"source": "源实体名称", "target": "目标实体名称", "relationship_type": "关系类型", "strength": 0.8}}
  ]
}}

文本内容：
{text}
"""
        try:
            messages = [
                {"role": "system", "content": "你是一个知识抽取专家，擅长从文本中提取实体和关系。请严格按照 JSON 格式输出。"},
                {"role": "user", "content": prompt}
            ]
            raw_response = await gateway.chat_completion(
                model=config.DEFAULT_EXECUTION_MODEL,
                messages=messages,
                domain_skill="Extraction"
            )

            clean_json = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if not clean_json:
                logger.error(f"[Memory] _llm_extract_knowledge: 响应中未找到 JSON: {raw_response[:100]}")
                return
            result = KnowledgeExtractionResult.model_validate_json(clean_json.group(0))

            for ent in result.entities:
                self._upsert_entity(ent.name, ent.entity_type)

            for rel in result.relationships:
                self._upsert_relationship(rel.source, rel.target, rel.relationship_type, rel.strength)

            logger.info(f"[Memory] _llm_extract_knowledge (等级 {task_level}) 成功: {len(result.entities)} 实体, {len(result.relationships)} 关系")
        except Exception as e:
            logger.error(f"[Memory] _llm_extract_knowledge 失败: {e}")

    def _upsert_entity(self, name: str, entity_type: str):
        """健壮的实体更新逻辑：增加词频和更新时间戳"""
        name = name.strip().lower()
        if name not in self.entities:
            self.entities[name] = ExtractedEntity(name=name, entity_type=entity_type)
            self.knowledge_graph.add_node(
                name,
                entity_type=entity_type,
                occurrences=1,
                last_seen=datetime.now()
            )
        else:
            self.knowledge_graph.nodes[name]['occurrences'] += 1
            self.knowledge_graph.nodes[name]['last_seen'] = datetime.now()

    def _upsert_relationship(self, source: str, target: str, rel_type: str, strength: float):
        """健壮的关系更新逻辑

        新增循环引用检测：如果 target → source 路径已存在，跳过添加，
        防止 A->B->A 导致的死循环检索。
        """
        source, target = source.strip().lower(), target.strip().lower()
        if not self.knowledge_graph.has_node(source):
            self._upsert_entity(source, "Unknown")
        if not self.knowledge_graph.has_node(target):
            self._upsert_entity(target, "Unknown")

        if self.knowledge_graph.has_node(source) and self.knowledge_graph.has_node(target):
            try:
                if nx.has_path(self.knowledge_graph, target, source):
                    logger.warning(f"[Memory] 检测到循环引用: {source} -> {target} 将导致死循环，跳过")
                    return
            except nx.NetworkXError:
                pass

        edge_key = (source, target, rel_type)
        if edge_key in self.relationships:
            existing = self.relationships[edge_key]
            existing.strength = min(existing.strength + 0.05, 1.0)
        else:
            rel = ExtractedRelation(source=source, target=target, relationship_type=rel_type, strength=strength)
            self.relationships[edge_key] = rel

        if self.knowledge_graph.has_edge(source, target):
            self.knowledge_graph.edges[source, target]['strength'] = min(
                self.knowledge_graph.edges[source, target].get('strength', 0) + 0.05, 1.0
            )
            self.knowledge_graph.edges[source, target]['timestamp'] = datetime.now()
        else:
            self.knowledge_graph.add_edge(source, target, relationship_type=rel_type, strength=strength, timestamp=datetime.now())

    # ==================== GraphRAG 核心：子图检索 ====================

    def get_subgraph_context(self, query_entities: List[str], depth: int = 1) -> str:
        """GraphRAG 核心：基于 Ego Graph 获取局部关联子图，避免 Prompt 爆炸

        使用 networkx.ego_graph 提取以查询词为中心的一度/二度关系子图，
        格式化为文本上下文，供 LLM Prompt 使用。

        Args:
            query_entities: 查询实体列表
            depth: 子图深度（1 = 一度关系，2 = 二度关系）

        Returns:
            str: 格式化的子图上下文描述
        """
        subgraph_nodes: Set[str] = set()

        for q_ent in query_entities:
            q_ent = q_ent.lower()
            if self.knowledge_graph.has_node(q_ent):
                ego_g = nx.ego_graph(self.knowledge_graph, q_ent, radius=depth)
                subgraph_nodes.update(ego_g.nodes)

        if not subgraph_nodes:
            return "未在图谱中找到相关背景知识。"

        target_subgraph = self.knowledge_graph.subgraph(subgraph_nodes)
        context_lines = []
        for u, v, data in target_subgraph.edges(data=True):
            rel = data.get('relationship_type', 'related to')
            context_lines.append(f"- [{u}] {rel} [{v}]")

        return "背景知识图谱片段：\n" + "\n".join(context_lines)

    def get_context_for_task(self, query_entities: List[str], depth: int = 1, top_k: int = 5) -> str:
        """检索加权：在遍历 ego_graph 时，结合 strength 和 last_seen 进行排序

        优先返回"最强关联"且"最新"的 top_k 条背景知识，避免低质量或过时的关系
        污染 Prompt，同时控制 Token 使用量。

        Args:
            query_entities: 查询实体列表
            depth: 子图深度（1 = 一度关系，2 = 二度关系）
            top_k: 返回的最优三元组数量

        Returns:
            str: 格式化的排序后子图上下文描述
        """
        subgraph_nodes: Set[str] = set()

        for q_ent in query_entities:
            q_ent = q_ent.lower()
            if self.knowledge_graph.has_node(q_ent):
                ego_g = nx.ego_graph(self.knowledge_graph, q_ent, radius=depth)
                subgraph_nodes.update(ego_g.nodes)

        if not subgraph_nodes:
            return "未在图谱中找到相关背景知识。"

        target_subgraph = self.knowledge_graph.subgraph(subgraph_nodes)
        scored_edges = []
        now = datetime.now()

        for u, v, data in target_subgraph.edges(data=True):
            strength = data.get('strength', 0.5)
            last_seen = data.get('timestamp', data.get('last_seen', now))
            if isinstance(last_seen, str):
                try:
                    last_seen = datetime.fromisoformat(last_seen)
                except Exception:
                    last_seen = now

            recency = (now - last_seen).total_seconds()
            recency_score = max(0.0, 1.0 - recency / 86400.0)
            combined_score = strength * 0.7 + recency_score * 0.3
            rel = data.get('relationship_type', 'related to')
            scored_edges.append((combined_score, u, v, rel))

        scored_edges.sort(key=lambda x: x[0], reverse=True)
        top_edges = scored_edges[:top_k]

        context_lines = []
        for score, u, v, rel in top_edges:
            context_lines.append(f"- [{u}] {rel} [{v}] (权重: {score:.2f})")

        return "背景知识图谱片段（按关联强度排序）：\n" + "\n".join(context_lines)

    # ==================== 原有记忆管理方法 ====================

    async def add_experience(self, input_text: str, response: str):
        """添加经验

        Args:
            input_text: 输入文本
            response: 回复文本
        """
        experience = {
            "input": input_text,
            "response": response,
            "timestamp": datetime.now(),
            "embedding": None
        }

        self.short_term_memory.append(experience)
        if len(self.short_term_memory) > self.max_short_term:
            self.short_term_memory.pop(0)

        if len(self.short_term_memory) % 10 == 0:
            self.long_term_memory.append(experience)

        self._update_logical_memory(input_text, response)

    async def retrieve(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """检索相关记忆

        Args:
            query: 查询关键词

        Returns:
            Optional[List[Dict[str, Any]]]: 相关记忆列表或None
        """
        relevant_memories = []

        for memory in reversed(self.short_term_memory):
            if self._is_relevant(memory["input"], query) or self._is_relevant(memory["response"], query):
                relevant_memories.append(memory)
                if len(relevant_memories) >= 5:
                    break

        if len(relevant_memories) < 5:
            for memory in reversed(self.long_term_memory):
                if self._is_relevant(memory["input"], query) or self._is_relevant(memory["response"], query):
                    relevant_memories.append(memory)
                    if len(relevant_memories) >= 5:
                        break

        return relevant_memories if relevant_memories else None

    async def retrieve_with_graph(self, query: str) -> Optional[Dict[str, Any]]:
        """基于图的检索

        Args:
            query: 查询关键词

        Returns:
            Optional[Dict[str, Any]]: 检索结果字典或None
        """
        query_entities = self._simple_extract_entities(query)

        result = {
            "memories": await self.retrieve(query),
            "entities": query_entities,
            "related_entities": [],
            "relationships": [],
            "subgraph": None
        }

        if query_entities:
            subgraph_nodes = set()
            for entity in query_entities:
                entity_name = entity["name"].lower()
                if entity_name in self.knowledge_graph:
                    for neighbor in nx.single_source_shortest_path_length(self.knowledge_graph, entity_name, cutoff=2):
                        subgraph_nodes.add(neighbor)

            if subgraph_nodes:
                subgraph = self.knowledge_graph.subgraph(subgraph_nodes)
                result["subgraph"] = self._graph_to_dict(subgraph)

            for entity in query_entities:
                entity_name = entity["name"].lower()
                if entity_name in self.knowledge_graph:
                    for neighbor in self.knowledge_graph.neighbors(entity_name):
                        edge_data = self.knowledge_graph.get_edge_data(entity_name, neighbor)
                        result["related_entities"].append({
                            "name": neighbor,
                            "type": self.knowledge_graph.nodes[neighbor].get("entity_type", "unknown"),
                            "relationship": edge_data.get("relationship_type", "related"),
                            "strength": edge_data.get("strength", 1.0)
                        })

                    for u, v, data in self.knowledge_graph.in_edges(entity_name, data=True):
                        result["relationships"].append({
                            "source": u,
                            "target": entity_name,
                            "type": data.get("relationship_type", "related"),
                            "strength": data.get("strength", 1.0)
                        })

        return result

    async def retrieve_by_entity(self, entity_name: str, depth: int = 2) -> Optional[Dict[str, Any]]:
        """基于实体的检索

        Args:
            entity_name: 实体名称
            depth: 检索深度（默认为2）

        Returns:
            Optional[Dict[str, Any]]: 检索结果字典或None
        """
        entity_key = entity_name.lower()
        result = {
            "entity": entity_name,
            "entity_type": self.knowledge_graph.nodes[entity_key].get("entity_type", "unknown") if entity_key in self.knowledge_graph else "unknown",
            "related_entities": [],
            "relationships": [],
            "memories": []
        }

        if entity_key in self.knowledge_graph:
            for neighbor in nx.single_source_shortest_path_length(self.knowledge_graph, entity_key, cutoff=depth):
                if neighbor != entity_key:
                    edge_data = self.knowledge_graph.get_edge_data(entity_key, neighbor)
                    if edge_data:
                        result["related_entities"].append({
                            "name": neighbor,
                            "type": self.knowledge_graph.nodes[neighbor].get("entity_type", "unknown"),
                            "relationship": edge_data.get("relationship_type", "related"),
                            "strength": edge_data.get("strength", 1.0)
                        })

            for u, v, data in self.knowledge_graph.in_edges(entity_key, data=True):
                result["relationships"].append({
                    "source": u,
                    "target": entity_key,
                    "type": data.get("relationship_type", "related"),
                    "strength": data.get("strength", 1.0)
                })

        for memory in reversed(self.short_term_memory + self.long_term_memory):
            if entity_name in memory["input"] or entity_name in memory["response"]:
                result["memories"].append(memory)
                if len(result["memories"]) >= 5:
                    break

        return result

    def _is_relevant(self, text: str, query: str) -> bool:
        """判断文本是否相关"""
        if query.lower() in text.lower():
            return True
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        return len(query_words.intersection(text_words)) > 0

    def _update_logical_memory(self, input_text: str, response: str):
        """更新逻辑依赖记忆"""
        input_key = f"input:{hash(input_text)}"
        response_key = f"response:{hash(response)}"

        self.logical_memory.add_node(input_key, text=input_text, type="input", timestamp=datetime.now())
        self.logical_memory.add_node(response_key, text=response, type="response", timestamp=datetime.now())
        self.logical_memory.add_edge(input_key, response_key, relationship="generates", timestamp=datetime.now())

    def _simple_extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """从文本中简单提取已知实体（轻量级，非 LLM 版本）

        仅在 LLM 无法使用时作为兜底，只匹配图谱中已有的实体。
        新实体抽取请使用 extract_knowledge_via_llm。

        Args:
            text: 文本

        Returns:
            List[Dict[str, Any]]: 实体列表
        """
        entities = []
        text_lower = text.lower()

        for entity_name, entity_data in self.entities.items():
            if entity_name in text_lower:
                entities.append({
                    "name": entity_name,
                    "type": getattr(entity_data, 'entity_type', 'unknown'),
                    "confidence": getattr(entity_data, 'confidence', 0.8)
                })

        return entities

    def _graph_to_dict(self, graph: nx.DiGraph) -> Dict[str, Any]:
        """将图转换为字典格式"""
        nodes = {}
        for node in graph.nodes:
            nodes[node] = dict(graph.nodes[node])

        edges = []
        for u, v, data in graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "data": {k: str(v) if isinstance(v, datetime) else v for k, v in data.items()}
            })

        return {
            "nodes": nodes,
            "edges": edges
        }

    def get_entity_stats(self) -> Dict[str, Any]:
        """获取实体统计信息"""
        stats = {
            "total_entities": len(self.entities),
            "entity_types": {},
            "top_entities": []
        }

        for entity_name, entity in self.entities.items():
            entity_type = entity.entity_type
            if entity_type not in stats["entity_types"]:
                stats["entity_types"][entity_type] = 0
            stats["entity_types"][entity_type] += 1

        node_stats = []
        for entity_name, entity in self.entities.items():
            occurrences = 1
            confidence = 0.8
            if self.knowledge_graph.has_node(entity_name):
                node_data = self.knowledge_graph.nodes[entity_name]
                occurrences = node_data.get('occurrences', 1)
            node_stats.append((entity_name, entity, occurrences, confidence))

        node_stats.sort(key=lambda x: x[2], reverse=True)
        stats["top_entities"] = [
            {
                "name": entity_name,
                "type": entity.entity_type,
                "occurrences": occurrences,
                "confidence": confidence
            }
            for entity_name, entity, occurrences, confidence in node_stats[:10]
        ]

        return stats

    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        try:
            undirected = self.knowledge_graph.to_undirected()
            avg_clustering = nx.average_clustering(undirected) if undirected.number_of_nodes() > 1 else 0.0
        except Exception:
            avg_clustering = 0.0

        return {
            "nodes": self.knowledge_graph.number_of_nodes(),
            "edges": self.knowledge_graph.number_of_edges(),
            "density": nx.density(self.knowledge_graph),
            "average_clustering": avg_clustering,
            "working_memory_messages": len(self.working_memory.history),
            "working_memory_has_summary": bool(self.working_memory.global_summary)
        }

    async def save_graph(self, filename: str = "knowledge_graph.json"):
        """保存知识图谱（异步 IO，使用 aiofiles 避免阻塞协程）"""
        graph_data = {
            "nodes": [],
            "edges": []
        }

        for node in self.knowledge_graph.nodes:
            node_data = dict(self.knowledge_graph.nodes[node])
            node_data = {k: str(v) if isinstance(v, datetime) else v for k, v in node_data.items()}
            graph_data["nodes"].append({
                "id": node,
                "data": node_data
            })

        for u, v, data in self.knowledge_graph.edges(data=True):
            edge_data = {k: str(v) if isinstance(v, datetime) else v for k, v in data.items()}
            graph_data["edges"].append({
                "source": u,
                "target": v,
                "data": edge_data
            })

        async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(graph_data, ensure_ascii=False, indent=2))

        logger.info(f"[Memory] 知识图谱已保存到 {filename}")

    async def load_graph(self, filename: str = "knowledge_graph.json"):
        """加载知识图谱（异步 IO，使用 aiofiles 避免阻塞协程）"""
        try:
            async with aiofiles.open(filename, 'r', encoding='utf-8') as f:
                content = await f.read()
                graph_data = json.loads(content)

            self.knowledge_graph.clear()
            self.entities.clear()
            self.relationships.clear()

            for node_data in graph_data.get("nodes", []):
                node_id = node_data["id"]
                data = node_data.get("data", {})
                self.knowledge_graph.add_node(node_id, **data)

                entity_type = data.get("entity_type", "Unknown")
                entity = ExtractedEntity(name=node_id, entity_type=entity_type)
                self.entities[node_id] = entity

            for edge_data in graph_data.get("edges", []):
                source = edge_data["source"]
                target = edge_data["target"]
                data = edge_data.get("data", {})
                self.knowledge_graph.add_edge(source, target, **data)

                rel = ExtractedRelation(
                    source=source,
                    target=target,
                    relationship_type=data.get("relationship_type", "related"),
                    strength=data.get("strength", 0.8)
                )
                edge_key = (source, target, data.get("relationship_type", "related"))
                self.relationships[edge_key] = rel

            logger.info(f"[Memory] 知识图谱已从 {filename} 加载 ({self.knowledge_graph.number_of_nodes()} 节点, {self.knowledge_graph.number_of_edges()} 边)")
        except Exception as e:
            logger.error(f"[Memory] 加载知识图谱失败: {e}")
