# src/data/database.py
# 数据库操作

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime

from src.config import config

# 数据库配置
DATABASE_URL = config.DATABASE_URL

# 创建引擎
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
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String, nullable=False, index=True)
    input_text = Column(Text, nullable=False)
    response = Column(Text)
    model_used = Column(String)
    is_local_fallback = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Database] 初始化完成")

async def get_db():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()