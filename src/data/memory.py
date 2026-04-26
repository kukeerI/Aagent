# src/data/memory.py
# 记忆系统

import asyncio
import networkx as nx
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import config

class Memory:
    def __init__(self):
        self.short_term_memory = []  # 短期记忆（滑动窗口）
        self.long_term_memory = []    # 长期记忆
        self.logical_memory = nx.DiGraph()  # 逻辑依赖图
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

    def _is_relevant(self, text: str, query: str) -> bool:
        """判断文本是否相关"""
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

    def clear_short_term(self):
        """清除短期记忆"""
        self.short_term_memory.clear()
        print("[Memory] 短期记忆已清除")

    def clear_all(self):
        """清除所有记忆"""
        self.short_term_memory.clear()
        self.long_term_memory.clear()
        self.logical_memory.clear()
        print("[Memory] 所有记忆已清除")