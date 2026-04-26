# src/data/memory.py
# 记忆系统 - GraphRAG实现

import asyncio
import networkx as nx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re

from src.config import config

class Entity:
    """实体"""
    def __init__(self, name: str, entity_type: str):
        self.name = name
        self.entity_type = entity_type
        self.occurrences = 1

class Relationship:
    """关系"""
    def __init__(self, source: str, target: str, relationship_type: str):
        self.source = source
        self.target = target
        self.relationship_type = relationship_type

class Memory:
    def __init__(self):
        self.short_term_memory = []  # 短期记忆（滑动窗口）
        self.long_term_memory = []    # 长期记忆
        self.logical_memory = nx.DiGraph()  # 逻辑依赖图
        self.knowledge_graph = nx.DiGraph()  # 知识图谱
        self.entities = {}  # 实体字典
        self.max_short_term = config.MAX_SHORT_TERM_MEMORY  # 短期记忆容量
        print("[Memory] 初始化成功")

    async def add_experience(self, input_text: str, response: str):
        """添加经验"""
        experience = {
            "input": input_text,
            "response": response,
            "timestamp": datetime.now(),
            "embedding": None  # 可以后续添加向量嵌入
        }

        # 添加到短期记忆
        self.short_term_memory.append(experience)
        if len(self.short_term_memory) > self.max_short_term:
            self.short_term_memory.pop(0)

        # 添加到长期记忆（每10次添加一次）
        if len(self.short_term_memory) % 10 == 0:
            self.long_term_memory.append(experience)

        # 更新逻辑依赖
        self._update_logical_memory(input_text, response)

        # 提取实体和关系，更新知识图谱
        self._extract_entities_and_relationships(input_text, response)

    async def retrieve(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """检索相关记忆"""
        # 简单的基于关键词的检索
        relevant_memories = []
        
        # 从短期记忆中检索
        for memory in reversed(self.short_term_memory):
            if self._is_relevant(memory["input"], query) or self._is_relevant(memory["response"], query):
                relevant_memories.append(memory)
                if len(relevant_memories) >= 5:
                    break

        # 从长期记忆中检索
        if len(relevant_memories) < 5:
            for memory in reversed(self.long_term_memory):
                if self._is_relevant(memory["input"], query) or self._is_relevant(memory["response"], query):
                    relevant_memories.append(memory)
                    if len(relevant_memories) >= 5:
                        break

        return relevant_memories if relevant_memories else None

    async def retrieve_with_graph(self, query: str) -> Optional[Dict[str, Any]]:
        """基于图的检索"""
        # 提取查询中的实体
        query_entities = self._extract_entities_from_text(query)
        
        # 构建检索结果
        result = {
            "memories": await self.retrieve(query),
            "entities": query_entities,
            "related_entities": [],
            "relationships": []
        }
        
        # 从知识图谱中检索相关实体和关系
        for entity in query_entities:
            entity_name = entity["name"]
            if entity_name in self.knowledge_graph:
                # 获取相关实体
                for neighbor in self.knowledge_graph.neighbors(entity_name):
                    edge_data = self.knowledge_graph.get_edge_data(entity_name, neighbor)
                    result["related_entities"].append({
                        "name": neighbor,
                        "relationship": edge_data.get("type", "related")
                    })
                
                # 获取相关关系
                for u, v, data in self.knowledge_graph.in_edges(entity_name, data=True):
                    result["relationships"].append({
                        "source": u,
                        "target": entity_name,
                        "type": data.get("type", "related")
                    })
        
        return result

    def _is_relevant(self, text: str, query: str) -> bool:
        """判断文本是否相关"""
        # 对于中文，直接检查子字符串
        if query in text:
            return True
        # 对于英文，检查单词
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        return len(query_words.intersection(text_words)) > 0

    def _update_logical_memory(self, input_text: str, response: str):
        """更新逻辑依赖记忆"""
        # 简单的逻辑依赖分析
        input_key = f"input:{hash(input_text)}"
        response_key = f"response:{hash(response)}"
        
        # 添加节点
        self.logical_memory.add_node(input_key, text=input_text, type="input")
        self.logical_memory.add_node(response_key, text=response, type="response")
        
        # 添加边
        self.logical_memory.add_edge(input_key, response_key, relationship="generates")

    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取实体"""
        # 简单的实体抽取（实际应用中可以使用更复杂的NLP工具）
        entities = []
        
        # 提取人名（简单示例）
        person_pattern = r"(Mr\.|Ms\.|Mrs\.)?\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)"
        person_matches = re.findall(person_pattern, text)
        for match in person_matches:
            full_name = f"{match[1]} {match[2]}"
            entities.append({"name": full_name, "type": "person"})
            
            # 更新实体字典
            if full_name not in self.entities:
                self.entities[full_name] = Entity(full_name, "person")
            else:
                self.entities[full_name].occurrences += 1
        
        # 提取组织名（简单示例）
        org_pattern = r"(Google|Microsoft|Apple|Amazon|Facebook|OpenAI)"
        org_matches = re.findall(org_pattern, text)
        for match in org_matches:
            entities.append({"name": match, "type": "organization"})
            
            # 更新实体字典
            if match not in self.entities:
                self.entities[match] = Entity(match, "organization")
            else:
                self.entities[match].occurrences += 1
        
        # 提取技术术语（简单示例）
        tech_pattern = r"(Python|Java|JavaScript|React|Node\.js|Docker|Kubernetes|AI|ML|DL)"
        tech_matches = re.findall(tech_pattern, text)
        for match in tech_matches:
            entities.append({"name": match, "type": "technology"})
            
            # 更新实体字典
            if match not in self.entities:
                self.entities[match] = Entity(match, "technology")
            else:
                self.entities[match].occurrences += 1
        
        return entities

    def _extract_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Relationship]:
        """从文本中提取关系"""
        relationships = []
        
        # 简单的关系抽取（实际应用中可以使用更复杂的NLP工具）
        entity_names = [entity["name"] for entity in entities]
        
        # 提取"是"关系
        for i, entity1 in enumerate(entity_names):
            for j, entity2 in enumerate(entity_names):
                if i != j:
                    if f"{entity1} 是 {entity2}" in text or f"{entity1} is {entity2}" in text:
                        relationships.append(Relationship(entity1, entity2, "is"))
                
                # 提取"使用"关系
                if f"{entity1} 使用 {entity2}" in text or f"{entity1} uses {entity2}" in text:
                    relationships.append(Relationship(entity1, entity2, "uses"))
                
                # 提取"开发"关系
                if f"{entity1} 开发 {entity2}" in text or f"{entity1} developed {entity2}" in text:
                    relationships.append(Relationship(entity1, entity2, "develops"))
        
        return relationships

    def _extract_entities_and_relationships(self, input_text: str, response: str):
        """提取实体和关系，更新知识图谱"""
        # 从输入和响应中提取实体
        input_entities = self._extract_entities_from_text(input_text)
        response_entities = self._extract_entities_from_text(response)
        
        # 合并实体
        all_entities = input_entities + response_entities
        
        # 提取关系
        input_relationships = self._extract_relationships(input_text, input_entities)
        response_relationships = self._extract_relationships(response, response_entities)
        
        # 合并关系
        all_relationships = input_relationships + response_relationships
        
        # 更新知识图谱
        for entity in all_entities:
            entity_name = entity["name"]
            if entity_name not in self.knowledge_graph:
                self.knowledge_graph.add_node(entity_name, type=entity["type"])
        
        for relationship in all_relationships:
            if not self.knowledge_graph.has_edge(relationship.source, relationship.target):
                self.knowledge_graph.add_edge(relationship.source, relationship.target, type=relationship.relationship_type)

    async def get_logical_connections(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """获取逻辑连接"""
        # 简单的逻辑连接检索
        connections = []
        query_key = f"input:{hash(query)}"
        
        if query_key in self.logical_memory:
            for neighbor in self.logical_memory.neighbors(query_key):
                node_data = self.logical_memory.nodes[neighbor]
                connections.append({
                    "type": node_data.get("type"),
                    "text": node_data.get("text"),
                    "relationship": "generates"
                })
        
        return connections if connections else None

    async def get_knowledge_graph(self) -> Dict[str, Any]:
        """获取知识图谱"""
        nodes = []
        edges = []
        
        for node, data in self.knowledge_graph.nodes(data=True):
            nodes.append({
                "id": node,
                "type": data.get("type", "unknown")
            })
        
        for u, v, data in self.knowledge_graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "type": data.get("type", "related")
            })
        
        return {
            "nodes": nodes,
            "edges": edges
        }

    async def get_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        return [{
            "name": entity.name,
            "type": entity.entity_type,
            "occurrences": entity.occurrences
        } for entity in self.entities.values()]

    def clear_short_term(self):
        """清除短期记忆"""
        self.short_term_memory.clear()
        print("[Memory] 短期记忆已清除")

    def clear_all(self):
        """清除所有记忆"""
        self.short_term_memory.clear()
        self.long_term_memory.clear()
        self.logical_memory.clear()
        self.knowledge_graph.clear()
        self.entities.clear()
        print("[Memory] 所有记忆已清除")