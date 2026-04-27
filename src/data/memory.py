# src/data/memory.py
# 记忆系统 - GraphRAG实现

import asyncio
import networkx as nx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re
import hashlib
import json

from src.config import config

class Entity:
    """实体"""
    def __init__(self, name: str, entity_type: str):
        self.name = name
        self.entity_type = entity_type
        self.occurrences = 1
        self.confidence = 0.8  # 实体置信度
        self.last_seen = datetime.now()  # 最后出现时间

class Relationship:
    """关系"""
    def __init__(self, source: str, target: str, relationship_type: str):
        self.source = source
        self.target = target
        self.relationship_type = relationship_type
        self.strength = 1.0  # 关系强度
        self.timestamp = datetime.now()  # 关系创建时间

class Memory:
    def __init__(self):
        self.short_term_memory = []  # 短期记忆（滑动窗口）
        self.long_term_memory = []    # 长期记忆
        self.logical_memory = nx.DiGraph()  # 逻辑依赖图
        self.knowledge_graph = nx.DiGraph()  # 知识图谱
        self.entities = {}  # 实体字典
        self.relationships = {}  # 关系字典
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
            "relationships": [],
            "subgraph": None
        }
        
        # 从知识图谱中检索相关实体和关系
        if query_entities:
            # 构建子图
            subgraph_nodes = set()
            for entity in query_entities:
                entity_name = entity["name"]
                if entity_name in self.knowledge_graph:
                    # 获取相关实体（2跳范围内）
                    for neighbor in nx.single_source_shortest_path_length(self.knowledge_graph, entity_name, cutoff=2):
                        subgraph_nodes.add(neighbor)
            
            # 构建子图
            if subgraph_nodes:
                subgraph = self.knowledge_graph.subgraph(subgraph_nodes)
                result["subgraph"] = self._graph_to_dict(subgraph)
            
            # 获取相关实体和关系
            for entity in query_entities:
                entity_name = entity["name"]
                if entity_name in self.knowledge_graph:
                    # 获取相关实体
                    for neighbor in self.knowledge_graph.neighbors(entity_name):
                        edge_data = self.knowledge_graph.get_edge_data(entity_name, neighbor)
                        result["related_entities"].append({
                            "name": neighbor,
                            "type": self.entities.get(neighbor, {}).entity_type if hasattr(self.entities.get(neighbor, {}), 'entity_type') else "unknown",
                            "relationship": edge_data.get("type", "related"),
                            "strength": edge_data.get("strength", 1.0)
                        })
                    
                    # 获取相关关系
                    for u, v, data in self.knowledge_graph.in_edges(entity_name, data=True):
                        result["relationships"].append({
                            "source": u,
                            "target": entity_name,
                            "type": data.get("type", "related"),
                            "strength": data.get("strength", 1.0)
                        })

        return result

    async def retrieve_by_entity(self, entity_name: str, depth: int = 2) -> Optional[Dict[str, Any]]:
        """基于实体的检索"""
        result = {
            "entity": entity_name,
            "entity_type": self.entities.get(entity_name, {}).entity_type if hasattr(self.entities.get(entity_name, {}), 'entity_type') else "unknown",
            "related_entities": [],
            "relationships": [],
            "memories": []
        }
        
        # 从知识图谱中检索
        if entity_name in self.knowledge_graph:
            # 获取相关实体
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
            
            # 获取相关关系
            for u, v, data in self.knowledge_graph.in_edges(entity_name, data=True):
                result["relationships"].append({
                    "source": u,
                    "target": entity_name,
                    "type": data.get("type", "related"),
                    "strength": data.get("strength", 1.0)
                })
        
        # 从记忆中检索包含该实体的内容
        for memory in reversed(self.short_term_memory + self.long_term_memory):
            if entity_name in memory["input"] or entity_name in memory["response"]:
                result["memories"].append(memory)
                if len(result["memories"]) >= 5:
                    break
        
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
        self.logical_memory.add_node(input_key, text=input_text, type="input", timestamp=datetime.now())
        self.logical_memory.add_node(response_key, text=response, type="response", timestamp=datetime.now())
        
        # 添加边
        self.logical_memory.add_edge(input_key, response_key, relationship="generates", timestamp=datetime.now())

    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取实体"""
        # 简单的实体抽取（实际应用中可以使用更复杂的NLP工具）
        entities = []
        
        # 提取人名（简单示例）
        person_pattern = r"(Mr\.|Ms\.|Mrs\.)?\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)"
        person_matches = re.findall(person_pattern, text)
        for match in person_matches:
            full_name = f"{match[1]} {match[2]}"
            entities.append({"name": full_name, "type": "person", "confidence": 0.9})
            
            # 更新实体字典
            if full_name not in self.entities:
                self.entities[full_name] = Entity(full_name, "person")
            else:
                self.entities[full_name].occurrences += 1
                self.entities[full_name].last_seen = datetime.now()
                self.entities[full_name].confidence = min(self.entities[full_name].confidence + 0.05, 1.0)
        
        # 提取组织名（简单示例）
        org_pattern = r"(Google|Microsoft|Apple|Amazon|Facebook|OpenAI|百度|阿里巴巴|腾讯|华为|字节跳动)"
        org_matches = re.findall(org_pattern, text)
        for match in org_matches:
            entities.append({"name": match, "type": "organization", "confidence": 0.95})
            
            # 更新实体字典
            if match not in self.entities:
                self.entities[match] = Entity(match, "organization")
            else:
                self.entities[match].occurrences += 1
                self.entities[match].last_seen = datetime.now()
                self.entities[match].confidence = min(self.entities[match].confidence + 0.05, 1.0)
        
        # 提取技术术语（简单示例）
        tech_pattern = r"(Python|Java|JavaScript|React|Node\.js|Docker|Kubernetes|AI|ML|DL|大语言模型|GPT|LLM|LangChain|OpenAI|Azure|AWS|GCP)"
        tech_matches = re.findall(tech_pattern, text)
        for match in tech_matches:
            entities.append({"name": match, "type": "technology", "confidence": 0.9})
            
            # 更新实体字典
            if match not in self.entities:
                self.entities[match] = Entity(match, "technology")
            else:
                self.entities[match].occurrences += 1
                self.entities[match].last_seen = datetime.now()
                self.entities[match].confidence = min(self.entities[match].confidence + 0.05, 1.0)
        
        # 提取地点（简单示例）
        location_pattern = r"(北京|上海|广州|深圳|杭州|美国|中国|日本|英国|德国|法国|纽约|东京|伦敦|巴黎)"
        location_matches = re.findall(location_pattern, text)
        for match in location_matches:
            entities.append({"name": match, "type": "location", "confidence": 0.85})
            
            # 更新实体字典
            if match not in self.entities:
                self.entities[match] = Entity(match, "location")
            else:
                self.entities[match].occurrences += 1
                self.entities[match].last_seen = datetime.now()
                self.entities[match].confidence = min(self.entities[match].confidence + 0.05, 1.0)
        
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
                
                # 提取"属于"关系
                if f"{entity1} 属于 {entity2}" in text or f"{entity1} belongs to {entity2}" in text:
                    relationships.append(Relationship(entity1, entity2, "belongs_to"))
                
                # 提取"位于"关系
                if f"{entity1} 位于 {entity2}" in text or f"{entity1} is located in {entity2}" in text:
                    relationships.append(Relationship(entity1, entity2, "located_in"))
        
        return relationships

    def _extract_entities_and_relationships(self, input_text: str, response: str):
        """提取实体和关系并更新知识图谱"""
        # 提取输入文本中的实体
        input_entities = self._extract_entities_from_text(input_text)
        # 提取响应文本中的实体
        response_entities = self._extract_entities_from_text(response)
        
        # 合并实体
        all_entities = input_entities + response_entities
        
        # 提取关系
        input_relationships = self._extract_relationships(input_text, input_entities)
        response_relationships = self._extract_relationships(response, response_entities)
        
        # 合并关系
        all_relationships = input_relationships + response_relationships
        
        # 更新知识图谱
        self._update_knowledge_graph(all_entities, all_relationships)

    def _update_knowledge_graph(self, entities: List[Dict[str, Any]], relationships: List[Relationship]):
        """更新知识图谱"""
        # 添加实体节点
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
                # 更新节点属性
                self.knowledge_graph.nodes[entity_name]["occurrences"] = self.knowledge_graph.nodes[entity_name].get("occurrences", 0) + 1
                self.knowledge_graph.nodes[entity_name]["last_seen"] = datetime.now()
                current_confidence = self.knowledge_graph.nodes[entity_name].get("confidence", 0.8)
                new_confidence = entity.get("confidence", 0.8)
                self.knowledge_graph.nodes[entity_name]["confidence"] = max(current_confidence, new_confidence)
        
        # 添加关系边
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
                # 更新关系强度
                existing_relationship = self.relationships[edge_key]
                existing_relationship.strength = min(existing_relationship.strength + 0.1, 5.0)
                existing_relationship.timestamp = datetime.now()
                self.knowledge_graph.edges[relationship.source, relationship.target]["strength"] = existing_relationship.strength
                self.knowledge_graph.edges[relationship.source, relationship.target]["last_updated"] = datetime.now()

    def _graph_to_dict(self, graph: nx.DiGraph) -> Dict[str, Any]:
        """将图转换为字典格式"""
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
        """获取实体统计信息"""
        stats = {
            "total_entities": len(self.entities),
            "entity_types": {},
            "top_entities": []
        }
        
        # 统计实体类型
        for entity_name, entity in self.entities.items():
            if entity.entity_type not in stats["entity_types"]:
                stats["entity_types"][entity.entity_type] = 0
            stats["entity_types"][entity.entity_type] += 1
        
        # 按出现次数排序
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
        """获取图谱统计信息"""
        return {
            "nodes": self.knowledge_graph.number_of_nodes(),
            "edges": self.knowledge_graph.number_of_edges(),
            "density": nx.density(self.knowledge_graph),
            "average_clustering": nx.average_clustering(self.knowledge_graph.to_undirected())
        }

    async def save_graph(self, filename: str = "knowledge_graph.json"):
        """保存知识图谱"""
        graph_data = {
            "nodes": [],
            "edges": []
        }
        
        # 保存节点
        for node in self.knowledge_graph.nodes:
            node_data = self.knowledge_graph.nodes[node]
            graph_data["nodes"].append({
                "id": node,
                "data": node_data
            })
        
        # 保存边
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
        """加载知识图谱"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            
            # 清空现有图谱
            self.knowledge_graph.clear()
            
            # 加载节点
            for node_data in graph_data.get("nodes", []):
                self.knowledge_graph.add_node(node_data["id"], **node_data["data"])
            
            # 加载边
            for edge_data in graph_data.get("edges", []):
                self.knowledge_graph.add_edge(
                    edge_data["source"],
                    edge_data["target"],
                    **edge_data["data"]
                )
            
            print(f"[Memory] 知识图谱已从 {filename} 加载")
        except Exception as e:
            print(f"[Memory] 加载知识图谱失败: {e}")
