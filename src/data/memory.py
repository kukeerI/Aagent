# src/data/memory.py
# 记忆系统 - GraphRAG实现
# 用途: 实现记忆系统的管理，包括短期记忆、长期记忆、逻辑依赖图和知识图谱的维护与检索功能。
# 依赖: networkx, asyncio, typing, datetime, re, hashlib, json, src.config
# 注意事项:
#   1. 知识图谱使用NetworkX实现，注意节点和边的数据结构。
#   2. 实体和关系提取采用了简单正则规则，请根据实际需求替换为更复杂的NLP工具。
#   3. 本系统为GraphRAG实现的核心记忆模块，与外部系统交互需要通过异步方法。

import asyncio
import networkx as nx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re
import hashlib
import json

from src.config import config


class Entity:
    """实体

    Attributes:
        name (str): 实体名称
        entity_type (str): 实体类型
        occurrences (int): 出现次数
        confidence (float): 实体置信度
        last_seen (datetime): 最后出现时间
    """

    def __init__(self, name: str, entity_type: str):
        self.name = name
        self.entity_type = entity_type
        self.occurrences = 1
        self.confidence = 0.8
        self.last_seen = datetime.now()


class Relationship:
    """关系

    Attributes:
        source (str): 源实体
        target (str): 目标实体
        relationship_type (str): 关系类型
        strength (float): 关系强度
        timestamp (datetime): 关系创建时间
    """

    def __init__(self, source: str, target: str, relationship_type: str):
        self.source = source
        self.target = target
        self.relationship_type = relationship_type
        self.strength = 1.0
        self.timestamp = datetime.now()


class Memory:
    """记忆系统主类

    用于管理短期记忆、长期记忆、逻辑依赖图和知识图谱。
    """

    def __init__(self):
        self.short_term_memory = []
        self.long_term_memory = []
        self.logical_memory = nx.DiGraph()
        self.knowledge_graph = nx.DiGraph()
        self.entities = {}
        self.relationships = {}
        self.max_short_term = config.MAX_SHORT_TERM_MEMORY
        print("[Memory] 初始化成功")

    async def add_experience(self, input_text: str, response: str):
        """添加经验

        Args:
            input_text (str): 输入文本
            response (str): 回复文本
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

        self._extract_entities_and_relationships(input_text, response)

    async def retrieve(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """检索相关记忆

        Args:
            query (str): 查询关键词

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
            query (str): 查询关键词

        Returns:
            Optional[Dict[str, Any]]: 检索结果字典或None
        """
        query_entities = self._extract_entities_from_text(query)

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
                entity_name = entity["name"]
                if entity_name in self.knowledge_graph:
                    for neighbor in nx.single_source_shortest_path_length(self.knowledge_graph, entity_name, cutoff=2):
                        subgraph_nodes.add(neighbor)

            if subgraph_nodes:
                subgraph = self.knowledge_graph.subgraph(subgraph_nodes)
                result["subgraph"] = self._graph_to_dict(subgraph)

            for entity in query_entities:
                entity_name = entity["name"]
                if entity_name in self.knowledge_graph:
                    for neighbor in self.knowledge_graph.neighbors(entity_name):
                        edge_data = self.knowledge_graph.get_edge_data(entity_name, neighbor)
                        result["related_entities"].append({
                            "name": neighbor,
                            "type": self.entities.get(neighbor, {}).entity_type if hasattr(self.entities.get(neighbor, {}), 'entity_type') else "unknown",
                            "relationship": edge_data.get("type", "related"),
                            "strength": edge_data.get("strength", 1.0)
                        })

                    for u, v, data in self.knowledge_graph.in_edges(entity_name, data=True):
                        result["relationships"].append({
                            "source": u,
                            "target": entity_name,
                            "type": data.get("type", "related"),
                            "strength": data.get("strength", 1.0)
                        })

        return result

    async def retrieve_by_entity(self, entity_name: str, depth: int = 2) -> Optional[Dict[str, Any]]:
        """基于实体的检索

        Args:
            entity_name (str): 实体名称
            depth (int): 检索深度（默认为2）

        Returns:
            Optional[Dict[str, Any]]: 检索结果字典或None
        """
        result = {
            "entity": entity_name,
            "entity_type": self.entities.get(entity_name, {}).entity_type if hasattr(self.entities.get(entity_name, {}), 'entity_type') else "unknown",
            "related_entities": [],
            "relationships": [],
            "memories": []
        }

        if entity_name in self.knowledge_graph:
            for neighbor in nx.single_source_shortest_path_length(self.knowledge_graph, entity_name, cutoff=depth):
                if neighbor != entity_name:
                    edge_data = self.knowledge_graph.get_edge_data(entity_name, neighbor)
                    if edge_data:
                        result["related_entities"].append({
                            "name": neighbor,
                            "type": self.entities.get(neighbor, {}).entity_type if hasattr(self.entities.get(neighbor, {}), 'entity_type') else "unknown",
                            "relationship": edge_data.get("type", "related"),
                            "strength": edge_data.get("strength", 1.0)
                        })

            for u, v, data in self.knowledge_graph.in_edges(entity_name, data=True):
                result["relationships"].append({
                    "source": u,
                    "target": entity_name,
                    "type": data.get("type", "related"),
                    "strength": data.get("strength", 1.0)
                })

        for memory in reversed(self.short_term_memory + self.long_term_memory):
            if entity_name in memory["input"] or entity_name in memory["response"]:
                result["memories"].append(memory)
                if len(result["memories"]) >= 5:
                    break

        return result

    def _is_relevant(self, text: str, query: str) -> bool:
        """判断文本是否相关

        Args:
            text (str): 要检查的文本
            query (str): 查询关键词

        Returns:
            bool: 是否相关
        """
        if query in text:
            return True
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        return len(query_words.intersection(text_words)) > 0

    def _update_logical_memory(self, input_text: str, response: str):
        """更新逻辑依赖记忆

        Args:
            input_text (str): 输入文本
            response (str): 回复文本
        """
        input_key = f"input:{hash(input_text)}"
        response_key = f"response:{hash(response)}"

        self.logical_memory.add_node(input_key, text=input_text, type="input", timestamp=datetime.now())
        self.logical_memory.add_node(response_key, text=response, type="response", timestamp=datetime.now())

        self.logical_memory.add_edge(input_key, response_key, relationship="generates", timestamp=datetime.now())

    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取实体

        Args:
            text (str): 文本

        Returns:
            List[Dict[str, Any]]: 实体列表
        """
        entities = []

        person_pattern = r"(Mr\.|Ms\.|Mrs\.)?\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)"
        person_matches = re.findall(person_pattern, text)
        for match in person_matches:
            full_name = f"{match[1]} {match[2]}"
            entities.append({"name": full_name, "type": "person", "confidence": 0.9})

            if full_name not in self.entities:
                self.entities[full_name] = Entity(full_name, "person")
            else:
                self.entities[full_name].occurrences += 1
                self.entities[full_name].last_seen = datetime.now()
                self.entities[full_name].confidence = min(self.entities[full_name].confidence + 0.05, 1.0)

        org_pattern = r"(Google|Microsoft|Apple|Amazon|Facebook|OpenAI|百度|阿里巴巴|腾讯|华为|字节跳动)"
        org_matches = re.findall(org_pattern, text)
        for match in org_matches:
            entities.append({"name": match, "type": "organization", "confidence": 0.95})

            if match not in self.entities:
                self.entities[match] = Entity(match, "organization")
            else:
                self.entities[match].occurrences += 1
                self.entities[match].last_seen = datetime.now()
                self.entities[match].confidence = min(self.entities[match].confidence + 0.05, 1.0)

        tech_pattern = r"(Python|Java|JavaScript|React|Node\.js|Docker|Kubernetes|AI|ML|DL|大语言模型|GPT|LLM|LangChain|OpenAI|Azure|AWS|GCP)"
        tech_matches = re.findall(tech_pattern, text)
        for match in tech_matches:
            entities.append({"name": match, "type": "technology", "confidence": 0.9})

            if match not in self.entities:
                self.entities[match] = Entity(match, "technology")
            else:
                self.entities[match].occurrences += 1
                self.entities[match].last_seen = datetime.now()
                self.entities[match].confidence = min(self.entities[match].confidence + 0.05, 1.0)

        location_pattern = r"(北京|上海|广州|深圳|杭州|美国|中国|日本|英国|德国|法国|纽约|东京|伦敦|巴黎)"
        location_matches = re.findall(location_pattern, text)
        for match in location_matches:
            entities.append({"name": match, "type": "location", "confidence": 0.85})

            if match not in self.entities:
                self.entities[match] = Entity(match, "location")
            else:
                self.entities[match].occurrences += 1
                self.entities[match].last_seen = datetime.now()
                self.entities[match].confidence = min(self.entities[match].confidence + 0.05, 1.0)

        return entities

    def _extract_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Relationship]:
        """从文本中提取关系

        Args:
            text (str): 文本
            entities (List[Dict[str, Any]]): 实体列表

        Returns:
            List[Relationship]: 关系列表
        """
        relationships = []

        entity_names = [entity["name"] for entity in entities]

        for i, entity1 in enumerate(entity_names):
            for j, entity2 in enumerate(entity_names):
                if i != j:
                    if f"{entity1} 是 {entity2}" in text or f"{entity1} is {entity2}" in text:
                        relationships.append(Relationship(entity1, entity2, "is"))

                    if f"{entity1} 使用 {entity2}" in text or f"{entity1} uses {entity2}" in text:
                        relationships.append(Relationship(entity1, entity2, "uses"))

                    if f"{entity1} 开发 {entity2}" in text or f"{entity1} developed {entity2}" in text:
                        relationships.append(Relationship(entity1, entity2, "develops"))

                    if f"{entity1} 属于 {entity2}" in text or f"{entity1} belongs to {entity2}" in text:
                        relationships.append(Relationship(entity1, entity2, "belongs_to"))

                    if f"{entity1} 位于 {entity2}" in text or f"{entity1} is located in {entity2}" in text:
                        relationships.append(Relationship(entity1, entity2, "located_in"))

        return relationships

    def _extract_entities_and_relationships(self, input_text: str, response: str):
        """提取实体和关系并更新知识图谱

        Args:
            input_text (str): 输入文本
            response (str): 回复文本
        """
        input_entities = self._extract_entities_from_text(input_text)
        response_entities = self._extract_entities_from_text(response)

        all_entities = input_entities + response_entities

        input_relationships = self._extract_relationships(input_text, input_entities)
        response_relationships = self._extract_relationships(response, response_entities)

        all_relationships = input_relationships + response_relationships

        self._update_knowledge_graph(all_entities, all_relationships)

    def _update_knowledge_graph(self, entities: List[Dict[str, Any]], relationships: List[Relationship]):
        """更新知识图谱

        Args:
            entities (List[Dict[str, Any]]): 实体列表
            relationships (List[Relationship]): 关系列表
        """
        for entity in entities:
            entity_name = entity["name"]
            if entity_name not in self.knowledge_graph:
                self.knowledge_graph.add_node(
                    entity_name,
                    type=entity["type"],
                    confidence=entity.get("confidence", 0.8),
                    occurrences=1,
                    created_at=datetime.now()
                )
            else:
                self.knowledge_graph.nodes[entity_name]["occurrences"] = self.knowledge_graph.nodes[entity_name].get("occurrences", 0) + 1
                self.knowledge_graph.nodes[entity_name]["last_seen"] = datetime.now()
                current_confidence = self.knowledge_graph.nodes[entity_name].get("confidence", 0.8)
                new_confidence = entity.get("confidence", 0.8)
                self.knowledge_graph.nodes[entity_name]["confidence"] = max(current_confidence, new_confidence)

        for relationship in relationships:
            edge_key = (relationship.source, relationship.target, relationship.relationship_type)
            if edge_key not in self.relationships:
                self.relationships[edge_key] = relationship
                self.knowledge_graph.add_edge(
                    relationship.source,
                    relationship.target,
                    type=relationship.relationship_type,
                    strength=relationship.strength,
                    created_at=relationship.timestamp
                )
            else:
                existing_relationship = self.relationships[edge_key]
                existing_relationship.strength = min(existing_relationship.strength + 0.1, 5.0)
                existing_relationship.timestamp = datetime.now()
                self.knowledge_graph.edges[relationship.source, relationship.target]["strength"] = existing_relationship.strength
                self.knowledge_graph.edges[relationship.source, relationship.target]["last_updated"] = datetime.now()

    def _graph_to_dict(self, graph: nx.DiGraph) -> Dict[str, Any]:
        """将图转换为字典格式

        Args:
            graph (nx.DiGraph): 要转换的图

        Returns:
            Dict[str, Any]: 图的字典表示
        """
        nodes = {}
        for node in graph.nodes:
            nodes[node] = graph.nodes[node]

        edges = []
        for u, v, data in graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "data": data
            })

        return {
            "nodes": nodes,
            "edges": edges
        }

    def get_entity_stats(self) -> Dict[str, Any]:
        """获取实体统计信息

        Returns:
            Dict[str, Any]: 实体统计信息字典
        """
        stats = {
            "total_entities": len(self.entities),
            "entity_types": {},
            "top_entities": []
        }

        for entity_name, entity in self.entities.items():
            if entity.entity_type not in stats["entity_types"]:
                stats["entity_types"][entity.entity_type] = 0
            stats["entity_types"][entity.entity_type] += 1

        sorted_entities = sorted(self.entities.items(), key=lambda x: x[1].occurrences, reverse=True)
        stats["top_entities"] = [
            {
                "name": entity_name,
                "type": entity.entity_type,
                "occurrences": entity.occurrences,
                "confidence": entity.confidence
            }
            for entity_name, entity in sorted_entities[:10]
        ]

        return stats

    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息

        Returns:
            Dict[str, Any]: 图谱统计信息字典
        """
        return {
            "nodes": self.knowledge_graph.number_of_nodes(),
            "edges": self.knowledge_graph.number_of_edges(),
            "density": nx.density(self.knowledge_graph),
            "average_clustering": nx.average_clustering(self.knowledge_graph.to_undirected())
        }

    async def save_graph(self, filename: str = "knowledge_graph.json"):
        """保存知识图谱

        Args:
            filename (str): 保存文件名，默认为"knowledge_graph.json"
        """
        graph_data = {
            "nodes": [],
            "edges": []
        }

        for node in self.knowledge_graph.nodes:
            node_data = self.knowledge_graph.nodes[node]
            graph_data["nodes"].append({
                "id": node,
                "data": node_data
            })

        for u, v, data in self.knowledge_graph.edges(data=True):
            graph_data["edges"].append({
                "source": u,
                "target": v,
                "data": data
            })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        print(f"[Memory] 知识图谱已保存到 {filename}")

    async def load_graph(self, filename: str = "knowledge_graph.json"):
        """加载知识图谱

        Args:
            filename (str): 加载文件名，默认为"knowledge_graph.json"
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)

            self.knowledge_graph.clear()

            for node_data in graph_data.get("nodes", []):
                self.knowledge_graph.add_node(node_data["id"], **node_data["data"])

            for edge_data in graph_data.get("edges", []):
                self.knowledge_graph.add_edge(
                    edge_data["source"],
                    edge_data["target"],
                    **edge_data["data"]
                )

            print(f"[Memory] 知识图谱已从 {filename} 加载")
        except Exception as e:
            print(f"[Memory] 加载知识图谱失败: {e}")
