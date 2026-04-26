# src/services/semantic_cache.py
# 语义缓存系统

import asyncio
import json
import hashlib
from typing import Optional, Dict, Any

import redis
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import config

class SemanticCache:
    def __init__(self, redis_url: str = None, threshold: float = None):
        self.redis_url = redis_url or config.REDIS_URL
        self.redis = None
        self.model = None
        self.threshold = threshold or config.CACHE_THRESHOLD  # 相似度阈值
        # 启动时不初始化，延迟到第一次使用时初始化
        self.initialized = False

    async def _setup(self):
        """初始化"""
        try:
            # 连接 Redis
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)
            print("[SemanticCache] Redis 连接成功")
        except Exception as e:
            print(f"[SemanticCache] Redis 连接失败: {e}")
            self.redis = None

        try:
            # 加载模型
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[SemanticCache] 模型加载成功")
        except Exception as e:
            print(f"[SemanticCache] 模型加载失败: {e}")
            self.model = None

    async def get_cache_key(self, request: Dict[str, Any]) -> str:
        """生成缓存键"""
        messages = request.get("messages", [])
        user_message = next((m for m in messages if m.get("role") == "user"), None)
        if not user_message:
            return None

        content = user_message.get("content", "")
        domain = request.get("domain_skill", "general")
        key = f"semantic_cache:{domain}:{hashlib.md5(content.encode()).hexdigest()}"
        return key

    async def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """生成文本嵌入"""
        if not self.model:
            return None
        try:
            return self.model.encode(text)
        except Exception as e:
            print(f"[SemanticCache] 生成嵌入失败: {e}")
            return None

    async def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """计算余弦相似度"""
        return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))

    async def get(self, request: Dict[str, Any]) -> Optional[str]:
        """获取缓存"""
        # 延迟初始化
        if not self.initialized:
            await self._setup()
            self.initialized = True

        if not self.redis or not self.model:
            return None

        cache_key = await self.get_cache_key(request)
        if not cache_key:
            return None

        try:
            # 获取缓存的嵌入和内容
            cached_data = await self.redis.get(cache_key)
            if not cached_data:
                return None

            cached = json.loads(cached_data)
            cached_embedding = np.array(cached["embedding"])

            # 计算当前请求的嵌入
            messages = request.get("messages", [])
            user_message = next((m for m in messages if m.get("role") == "user"), None)
            if not user_message:
                return None

            current_embedding = await self.get_embedding(user_message.get("content", ""))
            if current_embedding is None:
                return None

            # 计算相似度
            similarity = await self.cosine_similarity(current_embedding, cached_embedding)
            if similarity >= self.threshold:
                print(f"[SemanticCache] 命中缓存，相似度: {similarity:.4f}")
                return cached["content"]
            else:
                print(f"[SemanticCache] 缓存未命中，相似度: {similarity:.4f}")
                return None
        except Exception as e:
            print(f"[SemanticCache] 获取缓存失败: {e}")
            return None

    async def set(self, request: Dict[str, Any], content: str) -> bool:
        """设置缓存"""
        # 延迟初始化
        if not self.initialized:
            await self._setup()
            self.initialized = True

        if not self.redis or not self.model:
            return False

        cache_key = await self.get_cache_key(request)
        if not cache_key:
            return False

        try:
            # 生成嵌入
            messages = request.get("messages", [])
            user_message = next((m for m in messages if m.get("role") == "user"), None)
            if not user_message:
                return False

            embedding = await self.get_embedding(user_message.get("content", ""))
            if embedding is None:
                return False

            # 存储到 Redis
            cached_data = {
                "content": content,
                "embedding": embedding.tolist(),
                "timestamp": asyncio.get_event_loop().time()
            }
            await self.redis.setex(cache_key, config.CACHE_EXPIRY, json.dumps(cached_data))  # 1小时过期
            print(f"[SemanticCache] 缓存设置成功: {cache_key}")
            return True
        except Exception as e:
            print(f"[SemanticCache] 设置缓存失败: {e}")
            return False

    async def clear(self, domain: str = None) -> bool:
        """清除缓存"""
        if not self.redis:
            return False

        try:
            if domain:
                pattern = f"semantic_cache:{domain}:*"
            else:
                pattern = "semantic_cache:*"

            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
                print(f"[SemanticCache] 清除缓存: {len(keys)} 个键")
            return True
        except Exception as e:
            print(f"[SemanticCache] 清除缓存失败: {e}")
            return False

    def __del__(self):
        if self.redis:
            try:
                self.redis.close()
            except:
                pass