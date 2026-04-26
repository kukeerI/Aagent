import uuid
import chromadb
from chromadb.utils import embedding_functions
import networkx as nx
from schemas import Message

class UltimateMemory:
    def __init__(self, max_short_term_tokens=8000):
        # 1. 短期工作记忆 (滑动窗口)
        self.short_term_history = []
        self.max_tokens = max_short_term_tokens

        # 2. 长期语义记忆 (ChromaDB)
        self.chroma_client = chromadb.PersistentClient(path="./memory_db/vector_db")
        self.emb_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name="task_memory", embedding_function=self.emb_fn
        )

        # 3. 长期逻辑图谱 (NetworkX)
        self.graph = nx.DiGraph()

    # --- 短期记忆控制 ---
    def add_message(self, role: str, content: str):
        self.short_term_history.append(Message(role=role, content=content))
        self._trim_window()

    def _trim_window(self):
        """防止爆 Token，保留首条 System，淘汰最早的历史"""
        while sum(len(m.content) * 0.5 for m in self.short_term_history) > self.max_tokens:
            if len(self.short_term_history) > 2:
                self.short_term_history.pop(1)
            else:
                break

    def get_context(self) -> list[Message]:
        return self.short_term_history

    # --- 长期经验沉淀 ---
    def add_experience(self, task_desc: str, outcome: str):
        task_id = str(uuid.uuid4())
        self.collection.add(
            documents=[task_desc],
            metadatas=[{"outcome": outcome}],
            ids=[task_id]
        )
        self.graph.add_node(task_id, desc=task_desc, outcome=outcome)
        return task_id

    def query_related_memory(self, current_task: str) -> str:
        results = self.collection.query(query_texts=[current_task], n_results=1)
        if results['distances'] and len(results['distances'][0]) > 0:
            if results['distances'][0][0] < 0.4: # 相似度阈值拦截
                return results['metadatas'][0][0]['outcome']
        return None