# src/database.py
import datetime
from sqlalchemy import Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs

# 使用 aiosqlite 异步驱动 (需要 pip install aiosqlite)
engine = create_async_engine("sqlite+aiosqlite:///agent_data.db", echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class APIAsset(Base):
    """大模型资产表"""
    __tablename__ = "api_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    domain_skill: Mapped[str] = mapped_column(String(50))
    rpm_limit: Mapped[int] = mapped_column(Integer, default=60)
    api_key: Mapped[str] = mapped_column(String(255)) # 环境变量名称
    provider_url: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

# 初始化数据库函数
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
