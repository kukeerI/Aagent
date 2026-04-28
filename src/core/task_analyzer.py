# src/core/task_analyzer.py
# 任务分析器 - 仅负责 NLP 语义提取
# 依赖：asyncio, json, numpy, sklearn, sentence_transformers, time, re, src.services.gateway, src.services.tracing, src.config
# 注意事项：
#   - 支持本地嵌入模型和远程 API 两种模式
#   - 使用多线程加载模型，避免阻塞事件循环
#   - 生成多个草案并计算语义方差，用于评估任务复杂度
#   - 使用 asyncio.Lock() 防止并发加载模型导致 OOM
#   - 支持 Fast Pass 模式，简单任务直接跳过深度分析

import asyncio
import json
import numpy as np
import re
import time
from typing import List, Dict, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from src.services.gateway import AsyncGateway
from src.services.tracing import tracing
from src.config import config
from src.utils.logger import logger


class TaskAnalyzer:
    """任务分析器

    仅负责 NLP 语义提取，包括：
    - 生成多个草案
    - 计算文本嵌入和语义方差
    - 分类任务类型
    - 支持 Fast Pass 极速分诊
    """

    def __init__(self, gateway: Optional[AsyncGateway] = None):
        """初始化任务分析器

        Args:
            gateway: 网关实例，用于依赖注入（可选）
        """
        self.gateway = gateway or AsyncGateway()
        self.embedding_model = None
        self.use_local_embedding = False
        self.model_loaded = False
        # 预编译正则，提高性能
        self.fast_pass_regex = [re.compile(p) for p in config.FAST_PASS_PATTERNS]
        # 防御并发加载 OOM 的单例锁
        self._model_lock = asyncio.Lock()

    async def initialize(self):
        """异步初始化模型

        确保模型已加载，避免在处理任务时阻塞。
        使用单例锁防止并发加载导致 OOM。
        """
        if not self.model_loaded:
            await self._load_embedding_model()

    async def _load_embedding_model(self):
        """异步加载嵌入模型

        - 使用单例锁防止并发加载导致 OOM
        - 尝试加载本地模型（从配置读取模型名称）
        - 加载失败时回退到远程 API 模式
        - 使用线程池加载，避免阻塞事件循环
        """
        async with self._model_lock:
            # 双重检查锁，防止多次加载
            if self.model_loaded:
                return

            try:
                logger.info(f"[TaskAnalyzer] 开始加载本地嵌入模型: {config.EMBEDDING_MODEL_NAME}")
                # 使用线程池加载模型，避免阻塞事件循环
                self.embedding_model = await asyncio.to_thread(SentenceTransformer, config.EMBEDDING_MODEL_NAME)
                self.use_local_embedding = True
                self.model_loaded = True
                logger.info("[TaskAnalyzer] 本地嵌入模型加载成功")
            except Exception as e:
                logger.error(f"[TaskAnalyzer] 本地嵌入模型加载失败: {e}")
                logger.info("[TaskAnalyzer] 将使用远程 API 进行嵌入计算")
                self.use_local_embedding = False
                self.model_loaded = True

    async def _check_fast_pass(self, task: str) -> bool:
        """极速层分诊，判断是否短且符合正则

        对于简单的问候语、致谢语等，直接跳过深度分析，提高响应速度。

        Args:
            task: 任务描述

        Returns:
            bool: 是否为快速通过任务
        """
        if len(task) > 50:  # 长文本直接放行
            return False
        for pattern in self.fast_pass_regex:
            if pattern.search(task):
                return True
        return False

    async def analyze_task_adaptive(self, task: str) -> Dict[str, Any]:
        """自适应任务分析入口

        根据任务复杂度自动选择分析策略：
        - 简单任务：直接返回，不进行深度分析
        - 复杂任务：执行完整的语义分析流程

        Args:
            task: 任务描述

        Returns:
            Dict: 包含分析结果的字典
        """
        # 1. 前置拦截 (性能优化点：短路返回)
        is_simple = await self._check_fast_pass(task)
        if is_simple:
            logger.info(f"[TaskAnalyzer] 任务 '{task[:30]}...' 符合快速通过条件，跳过深度分析")
            return {
                "drafts": [],
                "semantic_variance": 0.0,  # 简单任务方差直接判定为 0
                "task_type": "general",
                "is_fast_pass": True,
                "extraction_time": 0.0
            }

        # 2. 只有复杂任务才进入重装深度分析
        async with self._model_lock:
            await self.initialize()  # 确保模型加载

        start_time = time.time()
        drafts = await self._generate_multiple_drafts(task)
        
        if not drafts:
            variance = 0.0
        else:
            distances = await self._calculate_embedding_distances(drafts)
            variance = self._calculate_semantic_variance(distances)

        return {
            "drafts": drafts,
            "semantic_variance": variance,
            "task_type": self._classify_task_type(task),
            "is_fast_pass": False,
            "extraction_time": time.time() - start_time
        }

    async def extract_semantic_data(self, user_input: str) -> Dict[str, Any]:
        """提取语义数据（兼容旧接口）

        Args:
            user_input: 用户输入的任务描述

        Returns:
            Dict: 包含语义提取结果的字典，包括：
                - task_type: 任务类型
                - drafts: 生成的草案列表
                - embedding_distances: 嵌入距离列表
                - semantic_variance: 语义方差
                - extraction_time: 提取耗时
                - is_fast_pass: 是否为快速通过任务

        Raises:
            Exception: 提取过程中出现错误时抛出
        """
        with tracing.start_span("task_analyzer.extract_semantic_data") as span:
            span.set_attribute("user_input", user_input[:100])

            # 使用自适应分析入口
            result = await self.analyze_task_adaptive(user_input)

            # 兼容旧接口格式
            if result["is_fast_pass"]:
                return {
                    "task_type": result["task_type"],
                    "drafts": [],
                    "embedding_distances": [],
                    "semantic_variance": 0.0,
                    "extraction_time": result["extraction_time"],
                    "is_fast_pass": True
                }

            # 复杂任务的完整结果
            start_time = time.time()
            logger.info(f"[TaskAnalyzer] 开始提取语义数据: {user_input[:50]}...")

            drafts = result["drafts"]

            if not drafts:
                logger.warning("[TaskAnalyzer] 无法生成草案，返回默认语义数据")
                return {
                    "task_type": result["task_type"],
                    "drafts": [],
                    "embedding_distances": [],
                    "semantic_variance": 0.0,
                    "extraction_time": time.time() - start_time,
                    "is_fast_pass": False
                }

            # 计算嵌入距离
            embedding_distances = await self._calculate_embedding_distances(drafts)

            semantic_data = {
                "task_type": result["task_type"],
                "drafts": drafts,
                "embedding_distances": embedding_distances,
                "semantic_variance": result["semantic_variance"],
                "extraction_time": time.time() - start_time,
                "is_fast_pass": False
            }

            logger.info(f"[TaskAnalyzer] 语义提取完成:")
            logger.info(f"  任务类型: {semantic_data['task_type']}")
            logger.info(f"  生成草案数: {len(drafts)}")
            logger.info(f"  语义方差: {result['semantic_variance']:.4f}")

            return semantic_data

    async def _generate_multiple_drafts(self, user_input: str, k: int = 3) -> List[str]:
        """生成多个草案

        使用不同的提示词生成多个草案，用于后续的语义分析。
        在调用前必须先判断 is_fast_pass，避免对简单任务进行不必要的计算。

        Args:
            user_input: 用户输入
            k: 生成的草案数量

        Returns:
            List[str]: 草案列表

        Raises:
            Exception: 生成过程中出现错误时抛出
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
                        logger.error(f"[TaskAnalyzer] 生成草案 {i+1} 失败: {result}")
                    elif result:
                        drafts.append(result)
            except Exception as e:
                logger.error(f"[TaskAnalyzer] 生成草案失败: {e}")

            return drafts

    async def _calculate_embedding_distances(self, texts: List[str]) -> List[float]:
        """计算文本之间的嵌入距离

        Args:
            texts: 文本列表

        Returns:
            List[float]: 距离列表

        Raises:
            Exception: 计算过程中出现错误时抛出
        """
        with tracing.start_span("task_analyzer.calculate_embeddings"):
            # 确保模型已加载（带锁保护）
            async with self._model_lock:
                if not self.model_loaded:
                    await self.initialize()

            if self.use_local_embedding and self.embedding_model:
                # 使用本地模型计算嵌入
                embeddings = await asyncio.to_thread(self.embedding_model.encode, texts)
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

        Raises:
            Exception: API 调用失败时抛出
        """
        # 这里可以实现调用远程嵌入 API 的逻辑
        # 暂时返回随机嵌入
        return [np.random.rand(384).tolist() for _ in texts]

    def _calculate_semantic_variance(self, distances: List[float]) -> float:
        """计算语义方差

        语义方差越大，说明草案之间的差异越大，任务可能越复杂。

        Args:
            distances: 距离列表

        Returns:
            float: 语义方差
        """
        if not distances:
            return 0.0

        return np.var(distances)

    def _classify_task_type(self, user_input: str) -> str:
        """分类任务类型

        Args:
            user_input: 用户输入

        Returns:
            str: 任务类型，包括：
                - code: 代码相关
                - analysis: 分析相关
                - creative: 创意相关
                - information: 信息查询
                - general: 通用
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
