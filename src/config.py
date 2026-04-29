# src/config.py
# 配置管理模块 - 集中管理系统所有配置参数
# 依赖：os, typing
# 配置来源：环境变量，支持默认值
# 注意事项：
#   - 所有配置项必须提供默认值，确保系统在无环境变量时也能运行
#   - 开发模式默认开启，便于本地调试
#   - 敏感配置（如 API Key）应通过环境变量传入，不硬编码在此文件

import os
from typing import Optional, List


class Config:
    """Aagent 配置管理类

    集中管理系统所有配置参数，配置值来自环境变量。
    使用环境变量可以做到：
    - 开发环境、测试环境、生产环境使用不同配置
    - 敏感信息（如密码、密钥）不暴露在代码中
    - 配置变更无需修改代码

    使用方式：
        from src.config import config
        timeout = config.REQUEST_TIMEOUT
    """

    # 服务配置
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # 监控配置
    JAEGER_HOST: str = os.getenv("JAEGER_HOST", "localhost")
    JAEGER_PORT: int = int(os.getenv("JAEGER_PORT", "6831"))

    # 存储配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agent_data.db")

    # 模型配置
    # 默认使用 google/gemma-3-12b-it 模型，可通过环境变量覆盖
    LM_STUDIO_URL: str = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    DEFAULT_EXECUTION_MODEL: str = os.getenv("DEFAULT_EXECUTION_MODEL", "google/gemma-3-12b-it")
    DEFAULT_RESEARCH_MODEL: str = os.getenv("DEFAULT_RESEARCH_MODEL", "google/gemma-3-12b-it")
    DEFAULT_CREATIVE_MODEL: str = os.getenv("DEFAULT_CREATIVE_MODEL", "google/gemma-3-12b-it")
    DEFAULT_ERROR_HANDLING_MODEL: str = os.getenv("DEFAULT_ERROR_HANDLING_MODEL", "google/gemma-3-12b-it")
    # 并发模型数量，用于四步评审等并发场景
    ENSEMBLE_SIZE: int = int(os.getenv("ENSEMBLE_SIZE", "3"))
    # 嵌入模型配置
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # 沙箱配置
    DOCKER_ENABLED: bool = os.getenv("DOCKER_ENABLED", "True").lower() == "true"
    SANDBOX_TIMEOUT: int = int(os.getenv("SANDBOX_TIMEOUT", "5"))
    SANDBOX_MEMORY_LIMIT: str = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")

    # 语义缓存配置
    # CACHE_THRESHOLD: 语义相似度阈值，超过该阈值认为缓存命中
    CACHE_THRESHOLD: float = float(os.getenv("CACHE_THRESHOLD", "0.95"))
    # CACHE_EXPIRY: 缓存过期时间（秒）
    CACHE_EXPIRY: int = int(os.getenv("CACHE_EXPIRY", "3600"))

    # 记忆系统配置
    # 最大短期记忆条目数量
    MAX_SHORT_TERM_MEMORY: int = int(os.getenv("MAX_SHORT_TERM_MEMORY", "100"))

    # 网关配置
    # 开发模式：减少重试次数和延迟，快速失败
    MAX_RETRY_ATTEMPTS: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "1"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "0.5"))
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "8.0"))

    # 开发模式配置
    DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() == "true"
    DEV_FAST_FAIL: bool = os.getenv("DEV_FAST_FAIL", "true").lower() == "true"
    DEV_SKIP_EXTERNAL_CALLS: bool = os.getenv("DEV_SKIP_EXTERNAL_CALLS", "false").lower() == "true"

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # 安全配置
    # 沙箱中禁止导入的模块，防止恶意代码执行
    BANNED_IMPORTS: set = {
        'os', 'sys', 'subprocess', 'shutil', 'ctypes', 'pickle',
        'socket', 'urllib', 'http', 'requests', 'tempfile',
        'pathlib', 'glob', 'io', 'builtins', '__import__'
    }

    # Fast Pass 模式配置
    # 用于极速层分诊，短且符合正则模式的任务直接跳过深度分析
    FAST_PASS_PATTERNS: List[str] = [
        r'^\s*(你好|hello|hi|您好|早上好|下午好|晚上好)\s*$',
        r'^\s*(谢谢|thank you|thanks)\s*$',
        r'^\s*(再见|bye|拜拜|再见了)\s*$',
        r'^\s*(好的|好|ok|okay|知道了|明白了)\s*$',
        r'^\s*(是|不是|对|不对|是的|不是的)\s*$',
        r'^\s*(\?|\？)\s*$',
        r'^\s*$'
    ]

    # 业务画像配置
    # 高危动作动词及其权重
    HIGH_RISK_ACTIONS: dict = {
        'delete': 0.9,
        'drop': 0.9,
        'remove': 0.8,
        'destroy': 0.95,
        'delete': 0.9,
        '删除': 0.9,
        '移除': 0.8,
        '销毁': 0.95,
        '删除': 0.9
    }
    
    # 中危动作动词及其权重
    MEDIUM_RISK_ACTIONS: dict = {
        'modify': 0.5,
        'change': 0.5,
        'update': 0.5,
        'alter': 0.5,
        'refactor': 0.6,
        '重构': 0.6,
        '修改': 0.5,
        '变更': 0.5,
        '更新': 0.5
    }
    
    # 低危动作动词及其权重
    LOW_RISK_ACTIONS: dict = {
        'create': 0.2,
        'add': 0.15,
        'write': 0.2,
        'build': 0.25,
        'develop': 0.25,
        '创建': 0.2,
        '添加': 0.15,
        '编写': 0.2,
        '构建': 0.25,
        '开发': 0.25
    }
    
    # 高质量领域关键词（Nature级任务标识）
    HIGH_QUALITY_TERMS: List[str] = [
        'nature', 'manuscript', 'protocol', 'research', 'academic',
        '论文', '研究', '学术', '协议', '规范', '标准'
    ]
    
    # 核心度归一化参数（最大连接数阈值）
    CORENESS_MAX_DEGREE: int = 10

    # 路由决策配置
    # 基础级别计算权重
    ROUTE_WEIGHTS: dict = {
        'entropy': 0.3,
        'term_density': 0.2,
        'coreness': 0.2,
        'risk_score': 0.15,
        'sla_priority': 0.15
    }
    
    # 提级门槛配置（阻尼决策 - 架构师规范）
    HIGH_QUALITY_GATE: float = 0.8             # 高质量门槛 (熵/术语密度) - 触发 L5
    MEDIUM_QUALITY_GATE: float = 0.5           # 中等质量门槛 - 触发 L3
    HIGH_RISK_GATE: float = 0.8                # 高风险门槛
    HIGH_CORENESS_GATE: float = 0.6            # 高核心度门槛 (结合风险触发 L6)
    MEDIUM_RISK_GATE: float = 0.5              # 中等风险门槛 - 触发 L4
    HIGH_VARIANCE_GATE: float = 0.5            # 高语义方差门槛 (仅 L4+ 才生效)
    FAST_PASS_RISK_LIMIT: float = 0.2          # 快速通道风险限制
    HIGH_SLA_THRESHOLD: float = 0.8            # 高SLA门槛 - 金融/法律合规任务触发 L5
    HIGH_GAP_THRESHOLD: float = 0.6            # 高依赖缺口门槛 - 触发 L4
    
    # 提级门槛配置（兼容旧代码）
    ROUTE_THRESHOLDS: dict = {
        'entropy_high': 0.7,          # 信息熵高阈值，触发提级
        'term_density_high': 0.6,     # 术语密度高阈值，触发提级
        'risk_score_critical': 0.8,   # 风险分数临界值，强制高路由
        'sla_priority_high': 0.7,     # SLA优先级高阈值，触发提级
        'structural_variance_high': 0.4,  # 语义波动率阈值，触发不确定性补偿
        'dependency_gap_high': 0.6    # 依赖缺口高阈值，触发提级
    }
    
    # 最低级别限制
    ROUTE_MIN_LEVELS: dict = {
        'nature_min_level': 4,        # Nature级任务最低级别
        'critical_min_level': 6       # 高危任务最低级别
    }
    
    # 路由级别原型向量 (架构师金标准)
    # 格式: [熵 (entropy), 术语密度 (term_density), 核心度 (coreness), 风险 (risk_score)]
    ROUTE_PROTOTYPES: dict = {
        1: [0.1, 0.1, 0.1, 0.0],      # L1 极速分诊: 极简/无险/闭环
        2: [0.3, 0.2, 0.2, 0.2],      # L2 标准代理: 清晰/常规/低危/确定
        3: [0.5, 0.3, 0.3, 0.3],      # L3 思考回复: 中密/关注/可控/微量缺口
        4: [0.6, 0.5, 0.5, 0.5],      # L4 复杂执行: 逻辑链/业务关联/中危/工具调用
        5: [0.8, 0.9, 0.2, 0.4],      # L5 逻辑深钻: 高熵/高SLA/低危/深度推理
        6: [0.5, 0.4, 0.9, 0.9],      # L6 评审与发散: 中熵/核心资产/高危/高发散
        7: [0.9, 0.9, 1.0, 1.0]       # L7 巅峰博弈: 极限熵/极致/命根子/极致风险
    }
    
    # 路由权重向量 (用于加权欧几里得空间)
    # 格式: [熵权重, 术语密度权重, 核心度权重, 风险权重]
    ROUTE_WEIGHTS_VEC: list = [1.0, 1.0, 1.5, 2.0]
    
    # 路由级别名称映射
    ROUTE_LEVEL_NAMES: dict = {
        1: "本地吞吐",
        2: "标准代理",
        3: "高价单发",
        4: "复杂执行",
        5: "逻辑深钻",
        6: "创意融合",
        7: "巅峰博弈"
    }


# 创建全局配置实例，供整个应用使用
config = Config()
