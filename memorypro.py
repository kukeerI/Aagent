import chromadb
from chromadb.utils import embedding_functions
import networkx as nx
import uuid

class MemoryPro:
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path="./memory/vector_db")
        self.emb_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name="task_memory", 
            embedding_function=self.emb_fn
        )

        # 2. 初始化逻辑记忆 (图谱)
        # 用于记录任务之间的依赖：A依赖B
        self.graph = nx.DiGraph()

    def add_experience(self, task_desc, outcome, importance):
        """记录一次经验"""
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

    def query_related_memory(self, current_task):
        """语义搜索：找找以前做过没"""
        results = self.collection.query(
            query_texts=[current_task],
            n_results=1 # 只取最相关的一个
        )
        
        # 如果相似度足够高（阈值判定），则返回记忆
        if results['distances'][0] and results['distances'][0][0] < 0.4:
            return results['metadatas'][0][0]['outcome']
        return None

    def add_logic_dependency(self, parent_id, child_id):
        """逻辑链条：记录‘因为做了A，所以产生B’"""
        self.graph.add_edge(parent_id, child_id)    