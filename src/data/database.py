# src/data/database.py
# 数据库操作模块 - 管理 SQLite 数据库的创建、查询和记录
# 依赖：asyncio, sqlalchemy, datetime
# 注意事项：
#   - 使用 aiosqlite 实现异步数据库操作
#   - 数据库文件位置由 config.DATABASE_URL 指定
#   - 所有数据库操作使用事务确保数据一致性

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime

from src.config import config

# 数据库配置
DATABASE_URL = config.DATABASE_URL

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# 创建会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 创建基类
Base = declarative_base()


class APIAsset(Base):
    """API 资产模型

    存储可用的 API 节点信息，包括模型名称、地址、权重等。
    """
    __tablename__ = "api_assets"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    weight = Column(Integer, default=100)
    consecutive_failures = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ExecutionLog(Base):
    """执行日志模型

    记录每次任务执行的详细信息，用于审计和调试。
    """
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String, nullable=False, index=True)
    input_text = Column(Text, nullable=False)
    response = Column(Text)
    model_used = Column(String)
    is_local_fallback = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class TokenUsage(Base):
    """Token 使用量模型

    记录各任务类型和模型的 Token 消耗统计，用于成本分析和性能优化。
    """
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, nullable=False, index=True)
    model_name = Column(String, nullable=False, index=True)
    avg_prompt_tokens = Column(Integer, default=0)
    avg_completion_tokens = Column(Integer, default=0)
    avg_total_tokens = Column(Integer, default=0)
    execution_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)


async def init_db():
    """初始化数据库

    创建所有表结构。应该在应用启动时调用一次。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Database] 初始化完成")


async def get_db():
    """获取数据库会话

    这是一个生成器函数，用于 FastAPI 的依赖注入。
    使用方式：
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def record_token_usage(task_type: str, model_name: str, prompt_tokens: int, completion_tokens: int, total_tokens: int):
    """记录 Token 使用情况

    Args:
        task_type: 任务类型
        model_name: 模型名称
        prompt_tokens: 提示词 Token 数量
        completion_tokens: 完成 Token 数量
        total_tokens: 总 Token 数量
    """
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(TokenUsage).where(
                TokenUsage.task_type == task_type,
                TokenUsage.model_name == model_name
            )
        )
        token_usage = result.scalar_one_or_none()

        if token_usage:
            total_prompt_tokens = token_usage.avg_prompt_tokens * token_usage.execution_count
            total_completion_tokens = token_usage.avg_completion_tokens * token_usage.execution_count
            total_total_tokens = token_usage.avg_total_tokens * token_usage.execution_count

            new_count = token_usage.execution_count + 1
            token_usage.avg_prompt_tokens = (total_prompt_tokens + prompt_tokens) // new_count
            token_usage.avg_completion_tokens = (total_completion_tokens + completion_tokens) // new_count
            token_usage.avg_total_tokens = (total_total_tokens + total_tokens) // new_count
            token_usage.execution_count = new_count
        else:
            token_usage = TokenUsage(
                task_type=task_type,
                model_name=model_name,
                avg_prompt_tokens=prompt_tokens,
                avg_completion_tokens=completion_tokens,
                avg_total_tokens=total_tokens,
                execution_count=1
            )
            session.add(token_usage)

        await session.commit()
        return token_usage


async def get_token_estimate(task_type: str, model_name: str) -> dict:
    """获取 Token 消耗预估

    Args:
        task_type: 任务类型
        model_name: 模型名称

    Returns:
        dict: 包含平均 Token 消耗的字典
    """
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(TokenUsage).where(
                TokenUsage.task_type == task_type,
                TokenUsage.model_name == model_name
            )
        )
        token_usage = result.scalar_one_or_none()

        if token_usage:
            return {
                "avg_prompt_tokens": token_usage.avg_prompt_tokens,
                "avg_completion_tokens": token_usage.avg_completion_tokens,
                "avg_total_tokens": token_usage.avg_total_tokens,
                "execution_count": token_usage.execution_count
            }
        else:
            return {
                "avg_prompt_tokens": 100,
                "avg_completion_tokens": 200,
                "avg_total_tokens": 300,
                "execution_count": 0
            }


async def get_all_token_usage() -> list:
    """获取所有 Token 使用记录

    Returns:
        list: 所有 Token 使用记录的列表
    """
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(TokenUsage))
        token_usages = result.scalars().all()

        return [
            {
                "task_type": tu.task_type,
                "model_name": tu.model_name,
                "avg_prompt_tokens": tu.avg_prompt_tokens,
                "avg_completion_tokens": tu.avg_completion_tokens,
                "avg_total_tokens": tu.avg_total_tokens,
                "execution_count": tu.execution_count,
                "last_updated": tu.last_updated.isoformat()
            }
            for tu in token_usages
        ]
