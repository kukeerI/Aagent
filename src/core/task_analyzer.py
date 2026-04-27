# src/core/task_analyzer.py
# 任务动态路由器 - 任务分析与路由决策

import asyncio
import json
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import time

from src.services.gateway import AsyncGateway
from src.services.tracing import tracing
from src.config import config

class TaskAnalyzer:
    """任务分析器 - 用于分析任务的创新度和确定性"""
    
    def __init__(self):
        self.gateway = AsyncGateway()
        # 使用轻量级的句子嵌入模型
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.use_local_embedding = True
        except Exception as e:
            print(f"[TaskAnalyzer] 本地嵌入模型加载失败: {e}")
            print("[TaskAnalyzer] 将使用远程 API 进行嵌入计算")
            self.use_local_embedding = False
    
    async def analyze_task(self, user_input: str) -> Dict[str, Any]:
        """分析任务的创新度和确定性
        
        Args:
            user_input: 用户输入的任务描述
            
        Returns:
            Dict: 包含任务分析结果的字典
        """
        with tracing.start_span("task_analyzer.analyze_task") as span:
            span.set_attribute("user_input", user_input[:100])
            
            start_time = time.time()
            print(f"[TaskAnalyzer] 开始分析任务: {user_input[:50]}...")
            
            # 步骤 1: 生成多个草案
            drafts = await self._generate_multiple_drafts(user_input, k=3)
            
            if not drafts:
                print("[TaskAnalyzer] 无法生成草案，使用默认路由")
                return {
                    "task_type": "default",
                    "innovation_score": 0.5,
                    "certainty_score": 0.5,
                    "recommended_route": "fast",
                    "drafts_generated": False
                }
            
            # 步骤 2: 计算语义方差
            embedding_distances = await self._calculate_embedding_distances(drafts)
            semantic_variance = self._calculate_semantic_variance(embedding_distances)
            
            # 步骤 3: 计算创新度和确定性
            innovation_score = self._calculate_innovation_score(semantic_variance)
            certainty_score = self._calculate_certainty_score(embedding_distances)
            
            # 步骤 4: 确定推荐路由
            recommended_route = self._determine_route(innovation_score, certainty_score)
            
            # 步骤 5: 分析任务类型
            task_type = self._classify_task_type(user_input)
            
            analysis_result = {
                "task_type": task_type,
                "innovation_score": innovation_score,
                "certainty_score": certainty_score,
                "semantic_variance": semantic_variance,
                "recommended_route": recommended_route,
                "drafts_generated": True,
                "drafts_count": len(drafts),
                "analysis_time": time.time() - start_time
            }
            
            print(f"[TaskAnalyzer] 分析结果:")
            print(f"  任务类型: {task_type}")
            print(f"  创新度: {innovation_score:.2f}")
            print(f"  确定性: {certainty_score:.2f}")
            print(f"  语义方差: {semantic_variance:.4f}")
            print(f"  推荐路由: {recommended_route}")
            
            return analysis_result
    
    async def _generate_multiple_drafts(self, user_input: str, k: int = 3) -> List[str]:
        """生成多个草案
        
        Args:
            user_input: 用户输入
            k: 生成的草案数量
            
        Returns:
            List[str]: 草案列表
        """
        with tracing.start_span("task_analyzer.generate_drafts"):
            drafts = []
            
            # 使用不同的提示词生成多个草案
            prompts = [
                "请直接回答以下问题，提供简洁明了的答案：\n{user_input}",
                "请从专业角度分析以下问题，并提供详细的解决方案：\n{user_input}",
                "请从创新角度思考以下问题，提供独特的见解：\n{user_input}"
            ]
            
            tasks = []
            for i, prompt in enumerate(prompts[:k]):
                messages = [
                    {"role": "user", "content": prompt.format(user_input=user_input)}
                ]
                # 使用轻量级模型快速生成
                task = self.gateway.chat_completion(
                    model="fast",
                    messages=messages,
                    domain_skill="General"
                )
                tasks.append(task)
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"[TaskAnalyzer] 生成草案 {i+1} 失败: {result}")
                    elif result:
                        drafts.append(result)
            except Exception as e:
                print(f"[TaskAnalyzer] 生成草案失败: {e}")
            
            return drafts
    
    async def _calculate_embedding_distances(self, texts: List[str]) -> List[float]:
        """计算文本之间的嵌入距离
        
        Args:
            texts: 文本列表
            
        Returns:
            List[float]: 距离列表
        """
        with tracing.start_span("task_analyzer.calculate_embeddings"):
            if self.use_local_embedding:
                # 使用本地模型计算嵌入
                embeddings = self.embedding_model.encode(texts)
            else:
                # 使用远程 API 计算嵌入
                embeddings = await self._get_embeddings_from_api(texts)
            
            if len(embeddings) < 2:
                return [0.0]
            
            # 计算所有两两之间的余弦距离
            distances = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    similarity = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                    distance = 1 - similarity  # 余弦距离
                    distances.append(distance)
            
            return distances
    
    async def _get_embeddings_from_api(self, texts: List[str]) -> List[List[float]]:
        """从 API 获取嵌入
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[float]]: 嵌入列表
        """
        # 这里可以实现调用远程嵌入 API 的逻辑
        # 暂时返回随机嵌入
        return [np.random.rand(384).tolist() for _ in texts]
    
    def _calculate_semantic_variance(self, distances: List[float]) -> float:
        """计算语义方差
        
        Args:
            distances: 距离列表
            
        Returns:
            float: 语义方差
        """
        if not distances:
            return 0.0
        
        return np.var(distances)
    
    def _calculate_innovation_score(self, semantic_variance: float) -> float:
        """计算创新度分数
        
        Args:
            semantic_variance: 语义方差
            
        Returns:
            float: 创新度分数 (0-1)
        """
        # 语义方差越大，创新度越高
        # 将方差映射到 0-1 范围
        max_variance = 2.0  # 理论最大余弦距离为 2
        innovation_score = min(semantic_variance / max_variance, 1.0)
        return innovation_score
    
    def _calculate_certainty_score(self, distances: List[float]) -> float:
        """计算确定性分数
        
        Args:
            distances: 距离列表
            
        Returns:
            float: 确定性分数 (0-1)
        """
        if not distances:
            return 0.5
        
        # 平均距离越小，确定性越高
        avg_distance = np.mean(distances)
        max_distance = 2.0
        certainty_score = max(1.0 - (avg_distance / max_distance), 0.0)
        return certainty_score
    
    def _determine_route(self, innovation_score: float, certainty_score: float) -> str:
        """确定推荐路由
        
        Args:
            innovation_score: 创新度分数
            certainty_score: 确定性分数
            
        Returns:
            str: 推荐路由 ("fast" 或 "reasoning")
        """
        # 决策逻辑
        # 高创新度 + 低确定性 → 需要深度推理
        # 低创新度 + 高确定性 → 快速路由
        
        if innovation_score > 0.6 or certainty_score < 0.4:
            return "reasoning"
        else:
            return "fast"
    
    def _classify_task_type(self, user_input: str) -> str:
        """分类任务类型
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 任务类型
        """
        user_input_lower = user_input.lower()
        
        # 代码相关
        code_keywords = ["code", "编程", "写代码", "debug", "调试", "function", "函数", "algorithm", "算法"]
        if any(keyword in user_input_lower for keyword in code_keywords):
            return "code"
        
        # 分析相关
        analysis_keywords = ["分析", "analyze", "分析一下", "评估", "evaluate", "研究", "research"]
        if any(keyword in user_input_lower for keyword in analysis_keywords):
            return "analysis"
        
        # 创意相关
        creative_keywords = ["创意", "creative", "设计", "design", "写", "写一篇", "创作", "create"]
        if any(keyword in user_input_lower for keyword in creative_keywords):
            return "creative"
        
        # 信息查询
        info_keywords = ["什么是", "是什么", "how", "如何", "怎样", "why", "为什么", "查询", "查找"]
        if any(keyword in user_input_lower for keyword in info_keywords):
            return "information"
        
        # 默认类型
        return "general"

# 全局任务分析器实例
task_analyzer = TaskAnalyzer()
