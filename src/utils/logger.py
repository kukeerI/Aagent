# src/utils/logger.py
# 结构化日志配置模块 - 提供统一的日志管理
# 依赖：logging, os, typing
# 注意事项：
#   - 使用单例模式，全局共享同一个日志记录器
#   - 日志级别可通过 LOG_LEVEL 环境变量配置
#   - 默认输出到控制台，格式：时间 - 名称 - 级别 - 消息

import logging
import os
from typing import Optional


class Logger:
    """结构化日志管理器

    提供统一的日志管理功能，支持：
    - 可配置的日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    - 标准化的日志格式
    - 单例模式，避免重复创建日志处理器

    使用方式：
        from src.utils.logger import logger
        logger.info("这是一条信息日志")
        logger.error("这是一条错误日志")
    """

    @staticmethod
    def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
        """获取日志记录器

        如果指定名称的日志记录器不存在，则创建一个新的。
        每个日志记录器只会有一个控制台处理器，避免重复输出。

        Args:
            name: 日志记录器名称，通常使用模块名
            log_level: 日志级别，默认为 INFO

        Returns:
            logging.Logger: 配置好的日志记录器实例
        """
        logger = logging.getLogger(name)

        if not log_level:
            log_level = os.getenv("LOG_LEVEL", "INFO")

        logger.setLevel(log_level)

        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)

            logger.addHandler(console_handler)

        return logger


# 创建全局日志记录器，供整个应用使用
logger = Logger.get_logger("aagent")
