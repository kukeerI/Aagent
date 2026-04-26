# src/database.py
import datetime
import uuid
from sqlalchemy import Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs

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
    api_key: Mapped[str] = mapped_column(String(255))
    provider_url: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

class ExecutionLog(Base):
    """执行日志表 - 用于收集思考过程和执行结果，为未来 SFT 微调积累数据"""
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    task_description: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(50))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)
    is_local_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def generate_trace_id() -> str:
    """生成全局唯一的 Trace ID"""
    return str(uuid.uuid4())