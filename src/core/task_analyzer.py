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
import zlib
from typing import List, Dict, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from src.services.gateway import AsyncGateway
from src.services.tracing import tracing
from src.config import config
from src.utils.logger import logger
from src.data.domain_models import TaskPhysicalProfile


class TaskAnalyzer:
    """任务分析器

    仅负责 NLP 语义提取，包括：
    - 生成多个草案
    - 计算文本嵌入和语义方差
    - 分类任务类型
    - 支持 Fast Pass 极速分诊
    - 提取物理特征指纹（信息熵、术语密度、N-gram多样性）
    """

    # 类级别预编译正则表达式 - 避免每次实例化重复编译
    # 核心领域关键词正则（学术/技术领域）
    DOMAIN_REGEX = re.compile(
        r'\b(nature|manuscript|pathway|protocol|mechanism|algorithm|refactor|framework|optimization|implementation|paradigm)\b',
        re.IGNORECASE
    )
    
    # 技术术语正则
    TECH_REGEX = re.compile(
        r'\b(python|java|javascript|sql|api|docker|kubernetes|aws|azure|machine learning|deep learning|neural network)\b',
        re.IGNORECASE
    )

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

    def _calculate_entropy(self, text: str) -> float:
        """计算压缩比作为信息熵的近似值

        使用 Gzip 压缩比来衡量文本的信息密度。
        压缩比越高（接近1.0），代表信息熵越大（文本越难压缩）。
        压缩比越低（接近0.0），代表信息熵越小（文本越容易压缩）。

        Args:
            text: 输入文本

        Returns:
            float: 信息熵值（0.0-1.0），0.0 表示低信息密度，1.0 表示高信息密度
        """
        if not text:
            return 0.0

        try:
            encoded = text.encode('utf-8')
            # 限制输入大小，防止内存溢出
            if len(encoded) > 1024 * 1024:  # 超过 1MB 截断
                encoded = encoded[:1024 * 1024]
            
            compressed = zlib.compress(encoded)
            compression_ratio = len(compressed) / len(encoded)
            
            # 将压缩比转换为熵值（压缩越困难，熵越高）
            # 压缩比接近 1.0 表示很难压缩，信息熵高
            # 压缩比接近 0.0 表示容易压缩，信息熵低
            return min(max(compression_ratio, 0.0), 1.0)
        except Exception as e:
            logger.error(f"[TaskAnalyzer] 信息熵计算失败: {e}")
            return 0.0

    def _calculate_term_density(self, text: str) -> float:
        """计算术语密度

        统计文本中领域关键词的出现频率，反映任务的专业性。

        Args:
            text: 输入文本

        Returns:
            float: 术语密度（0.0-1.0），0.0 表示无专业术语，1.0 表示高度专业
        """
        if not text:
            return 0.0

        words = text.split()
        if not words:
            return 0.0

        # 统计领域关键词匹配
        domain_matches = self.DOMAIN_REGEX.findall(text)
        tech_matches = self.TECH_REGEX.findall(text)
        total_matches = len(domain_matches) + len(tech_matches)

        # 归一化处理：除以词数的 1/10，确保结果在合理范围内
        density = total_matches / (len(words) / 10 + 1)
        
        return min(max(density, 0.0), 1.0)

    def _calculate_ngram_diversity(self, text: str, n: int = 2) -> float:
        """计算 N-gram 多样性

        作为语义方差的轻量级补充，通过统计 N-gram 的唯一性来衡量文本的丰富度。

        Args:
            text: 输入文本
            n: N-gram 的 N 值，默认为 2（双词）

        Returns:
            float: N-gram 多样性（0.0-1.0），0.0 表示重复度高，1.0 表示多样性高
        """
        if not text or len(text) < n:
            return 0.0

        # 生成所有 N-gram
        ngrams = []
        for i in range(len(text) - n + 1):
            ngrams.append(text[i:i+n])

        if not ngrams:
            return 0.0

        # 计算唯一 N-gram 的比例
        unique_ngrams = set(ngrams)
        diversity = len(unique_ngrams) / len(ngrams)

        return min(max(diversity, 0.0), 1.0)

    async def extract_physical_profile(self, task: str) -> TaskPhysicalProfile:
        """提取物理特征画像

        极速计算任务的物理特征，不调用任何 LLM 或 Embedding 模型。
        对于简单任务（is_fast_pass），直接返回基础画像。

        Args:
            task: 任务描述文本

        Returns:
            TaskPhysicalProfile: 物理特征画像对象
        """
        # 短路逻辑：简单任务直接返回基础画像
        is_simple = await self._check_fast_pass(task)
        if is_simple:
            logger.info(f"[TaskAnalyzer] 任务 '{task[:30]}...' 符合快速通过条件，返回基础物理画像")
            return TaskPhysicalProfile(
                size=len(task),
                entropy=0.0,
                term_density=0.0,
                structural_variance=0.0
            )

        # 极速计算物理指标（纯 CPU 计算，毫秒级完成）
        entropy = self._calculate_entropy(task)
        term_density = self._calculate_term_density(task)
        
        # 只有在熵值或密度达到一定阈值，才计算结构方差（N-gram多样性）
        structural_variance = 0.0
        if entropy > 0.5 or term_density > 0.3:
            structural_variance = self._calculate_ngram_diversity(task)

        logger.debug(f"[TaskAnalyzer] 物理特征提取完成 - 熵: {entropy:.4f}, 密度: {term_density:.4f}, 方差: {structural_variance:.4f}")

        return TaskPhysicalProfile(
            size=len(task),
            entropy=entropy,
            term_density=term_density,
            structural_variance=structural_variance
        )

    def _calculate_ngram_volatility(self, drafts: List[str]) -> float:
        """计算 N-gram 波动率（语义波动率）

        学术方法：自我一致性检验。
        计算多个草案之间的 Bigram 重合度标准差，用于衡量模型生成的多个草案之间的差异。
        波动率越高，表示草案之间差异越大，任务可能越复杂或需要更多思考。

        Args:
            drafts: 多个草案文本列表

        Returns:
            float: 波动率值（0.0-1.0），0.0 表示草案高度一致，1.0 表示草案差异很大
        """
        if len(drafts) < 2:
            logger.debug("[TaskAnalyzer] 草案数量不足，无法计算波动率")
            return 0.0

        # 生成每个草案的 Bigram 集合
        def get_bigrams(text: str) -> set:
            """提取文本的 Bigram 集合"""
            if len(text) < 2:
                return set()
            return set(zip(text[:-1], text[1:]))

        bigram_sets = []
        for draft in drafts:
            if len(draft) > 1:
                bigrams = get_bigrams(draft)
                if bigrams:
                    bigram_sets.append(bigrams)

        # 处理所有草案都无法生成有效 Bigram 的情况
        if not bigram_sets:
            logger.debug("[TaskAnalyzer] 所有草案都无法生成有效 Bigram，波动率设为 1.0")
            return 1.0

        # 计算两两之间的 Jaccard 距离
        distances = []
        for i in range(len(bigram_sets)):
            for j in range(i + 1, len(bigram_sets)):
                set_i = bigram_sets[i]
                set_j = bigram_sets[j]
                
                intersection = len(set_i & set_j)
                union = len(set_i | set_j)
                
                if union > 0:
                    jaccard_similarity = intersection / union
                    jaccard_distance = 1.0 - jaccard_similarity
                    distances.append(jaccard_distance)
                else:
                    distances.append(1.0)  # 两个空集合的距离视为最大

        if not distances:
            return 0.0

        # 根据草案数量选择计算方式
        if len(distances) == 1:
            # 只有一对草案时，直接使用距离值作为波动率
            return distances[0]
        else:
            # 多对草案时，计算距离的标准差作为波动率指标
            std_dev = float(np.std(distances))
            
            # 归一化处理：标准差的最大值理论上可以很大
            # 使用 tanh 进行归一化，使结果在 [0, 1] 之间
            volatility = float(np.tanh(std_dev * 3))
            
            # 确保结果在 [0.0, 1.0] 范围内
            return min(max(volatility, 0.0), 1.0)

    async def generate_physical_profile(self, task: str) -> TaskPhysicalProfile:
        """生成物理特征画像（阶梯式计算）

        采用分层计算策略：
        1. 首先进行 CPU 密集型计算（熵和术语密度）- 毫秒级完成
        2. 只有当熵或术语密度达到阈值时，才触发昂贵的 LLM 草案生成
        3. 根据草案计算语义波动率

        这种设计可以节省大量的响应时间和 API 费用，因为简单任务不需要调用 LLM。

        Args:
            task: 任务描述文本

        Returns:
            TaskPhysicalProfile: 物理特征画像对象，包含：
                - size: 文本长度
                - entropy: 信息熵（0.0-1.0）
                - term_density: 术语密度（0.0-1.0）
                - structural_variance: 语义波动率（0.0-1.0）
        """
        logger.debug(f"[TaskAnalyzer] 开始生成物理特征画像: '{task[:50]}...'")
        
        # 1. CPU 密集型计算：熵与术语密度（毫秒级完成）
        entropy = self._calculate_entropy(task)
        logger.debug(f"[TaskAnalyzer] 信息熵计算完成: {entropy:.4f}")
        
        # 统计领域关键词匹配（使用预编译正则）
        domain_matches = self.DOMAIN_REGEX.findall(task)
        tech_matches = self.TECH_REGEX.findall(task)
        total_matches = len(domain_matches) + len(tech_matches)
        
        words = task.split()
        if not words:
            term_density = 0.0
        else:
            # 归一化处理：除以词数的 1/10，确保结果在合理范围内
            term_density = min(1.0, total_matches / (len(words) / 10 + 1))
        logger.debug(f"[TaskAnalyzer] 术语密度计算完成: {term_density:.4f}")
        
        # 2. 阶梯式决策：只有信息熵或术语密度达到中等水平，才触发昂贵的草案生成
        # 阈值设定：entropy > 0.4 或 term_density > 0.2
        volatility = 0.0
        if entropy > 0.4 or term_density > 0.2:
            logger.info(f"[TaskAnalyzer] 触发草案生成 - 熵: {entropy:.4f}, 密度: {term_density:.4f}")
            try:
                # 调用 LLM 生成多个草案
                drafts = await self._generate_multiple_drafts(task)
                logger.debug(f"[TaskAnalyzer] 草案生成完成，共 {len(drafts)} 个草案")
                
                # 计算语义波动率
                if drafts:
                    volatility = self._calculate_ngram_volatility(drafts)
                    logger.debug(f"[TaskAnalyzer] 语义波动率计算完成: {volatility:.4f}")
                else:
                    logger.warning("[TaskAnalyzer] 草案生成失败，波动率设为 0.0")
            except Exception as e:
                logger.error(f"[TaskAnalyzer] 生成草案或计算波动率失败: {e}")
                # 失败时保持波动率为 0.0，不影响后续流程
        
        # 3. 组装并返回物理特征画像
        profile = TaskPhysicalProfile(
            size=len(task),
            entropy=entropy,
            term_density=term_density,
            structural_variance=volatility
        )
        
        logger.debug(f"[TaskAnalyzer] 物理特征画像生成完成: {profile}")
        return profile

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
