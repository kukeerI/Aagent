import chromadb
from chromadb.utils import embedding_functions
import networkx as nx
import uuid
from schemas import Message  # 引入强类型契约

class UltimateMemory:
    def __init__(self, max_short_term_tokens=8000):
        # ================= 1. 短期工作记忆 (RAM) =================
        # 用于保存当前的对话流，喂给大模型。带滑动窗口防止爆 Token
        self.short_term_history = []
        self.max_tokens = max_short_term_tokens

        # ================= 2. 长期语义记忆 (Hard Drive) =================
        self.chroma_client = chromadb.PersistentClient(path="./memory/vector_db")
        self.emb_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name="task_memory", 
            embedding_function=self.emb_fn
        )

        # ================= 3. 长期逻辑记忆 (Graph) =================
        # 用于记录任务之间的依赖：A依赖B
        self.graph = nx.DiGraph()

    # ------------------ 短期记忆管理区 ------------------
    def add_message(self, role: str, content: str):
        """记录当前对话，并自动修剪防止超出大模型上下文"""
        self.short_term_history.append(Message(role=role, content=content))
        self._trim_sliding_window()

    def _trim_sliding_window(self):
        """FIFO 截断短期记忆"""
        # 粗略估算：中文字符数 * 0.5 ≈ Token 数量
        while sum(len(m.content) * 0.5 for m in self.short_term_history) > self.max_tokens:
            if len(self.short_term_history) > 2:
                # 永远保留 index 0 (System Prompt)，剔除最早的旧对话
                self.short_term_history.pop(1) 
            else:
                break

    def get_context(self) -> list[Message]:
        """Orchestrator 发请求时调用的接口"""
        return self.short_term_history

    # ------------------ 长期记忆管理区 (你的原版神作) ------------------
    def add_experience(self, task_desc: str, outcome: str, importance: float = 1.0):
        """记录一次成功的经验"""
        task_id = str(uuid.uuid4())
        
        # 存入向量库：用于以后的语义检索
        self.collection.add(
            documents=[task_desc],
            metadatas=[{"outcome": outcome, "importance": importance}],
            ids=[task_id]
        )
        
        # 存入图谱：如果是复合任务，这里记录逻辑节点
        self.graph.add_node(task_id, desc=task_desc, outcome=outcome)
        return task_id

    def query_related_memory(self, current_task: str) -> str:
        """语义搜索：找找以前做过没"""
        results = self.collection.query(
            query_texts=[current_task],
            n_results=1 # 只取最相关的一个
        )
        
        # 防空判断增强，并判断阈值
        if results['distances'] and len(results['distances'][0]) > 0:
            if results['distances'][0][0] < 0.4:
                return results['metadatas'][0][0]['outcome']
        return None

    def add_logic_dependency(self, parent_id: str, child_id: str):
        """逻辑链条：记录‘因为做了A，所以产生B’"""
        self.graph.add_edge(parent_id, child_id)