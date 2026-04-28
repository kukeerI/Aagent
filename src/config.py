# src/config.py
# 配置管理模块 - 集中管理系统所有配置参数
# 依赖：os, typing
# 配置来源：环境变量，支持默认值
# 注意事项：
#   - 所有配置项必须提供默认值，确保系统在无环境变量时也能运行
#   - 开发模式默认开启，便于本地调试
#   - 敏感配置（如 API Key）应通过环境变量传入，不硬编码在此文件

import os
from typing import Optional


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


# 创建全局配置实例，供整个应用使用
config = Config()
