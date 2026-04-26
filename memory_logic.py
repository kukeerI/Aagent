import chromadb
from chromadb.utils import embedding_functions

class SimpleMemory:
    def __init__(self):
        # 1. 在本地创建一个名为 memory_db 的文件夹存数据
        self.client = chromadb.PersistentClient(path="./memory_db")
        # 2. 默认的“翻译官”：把你的话转成坐标
        self.emb_fn = embedding_functions.DefaultEmbeddingFunction()
        # 3. 创建或打开一个叫 "task_archive" 的抽屉
        self.collection = self.client.get_or_create_collection(
            name="task_archive", 
            embedding_function=self.emb_fn
        )

    def search(self, query_text):
        """看看以前有没有类似的"""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=1
        )
        # 如果距离(distances)小于0.4，说明以前做过类似的任务
        if results['distances'] and results['distances'][0] and results['distances'][0][0] < 0.4:
            return results['metadatas'][0][0]['outcome']
        return None

    def save(self, task_text, outcome):
        """把这次成功的经验存起来"""
        import uuid
        self.collection.add(
            documents=[task_text],
            metadatas=[{"outcome": outcome}],
            ids=[str(uuid.uuid4())]
        )