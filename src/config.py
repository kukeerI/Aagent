# src/config.py
# 配置管理

import os
from typing import Optional

class Config:
    """Aagent 配置管理"""
    
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
    LM_STUDIO_URL: str = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    
    # 沙箱配置
    DOCKER_ENABLED: bool = os.getenv("DOCKER_ENABLED", "True").lower() == "true"
    SANDBOX_TIMEOUT: int = int(os.getenv("SANDBOX_TIMEOUT", "10"))  # 秒
    SANDBOX_MEMORY_LIMIT: str = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")
    
    # 语义缓存配置
    CACHE_THRESHOLD: float = float(os.getenv("CACHE_THRESHOLD", "0.95"))
    CACHE_EXPIRY: int = int(os.getenv("CACHE_EXPIRY", "3600"))  # 秒
    
    # 记忆系统配置
    MAX_SHORT_TERM_MEMORY: int = int(os.getenv("MAX_SHORT_TERM_MEMORY", "100"))
    
    # 网关配置
    MAX_RETRY_ATTEMPTS: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "1.0"))  # 秒
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 安全配置
    BANNED_IMPORTS: set = {
        'os', 'sys', 'subprocess', 'shutil', 'ctypes', 'pickle',
        'socket', 'urllib', 'http', 'requests', 'tempfile',
        'pathlib', 'glob', 'io', 'builtins', '__import__'
    }

# 创建全局配置实例
config = Config()