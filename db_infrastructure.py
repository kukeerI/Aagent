import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler

# 数据库文件路径
engine = create_engine('sqlite:///agent_data.db', echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class APIAsset(Base):
    __tablename__ = 'api_assets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50))        # 平台：AIStudio, Groq等
    model_name = Column(String(100))     # 模型全名
    category = Column(String(50))        # 类别
    domain_skill = Column(String(50))    # 领域：Logic, Coding, Fast, Search, Creative
    rpm_limit = Column(Integer)          # RPM
    tpm_limit = Column(BigInteger)       # TPM
    rpd_limit = Column(Integer)          # RPD
    weight = Column(Float, default=1.0)
    status = Column(String(20), default="ACTIVE") 
    reset_hour_utc = Column(Integer, default=0)    
    api_key = Column(String(200))        # 存储环境变量的 Key 名称

class ErrorLog(Base):
    __tablename__ = 'error_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_id = Column(Integer, nullable=False)
    error_type = Column(String(50))
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

def run_database_gc():
    """生命周期管理：删除 48 小时前的流水日志"""
    session = SessionLocal()
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=2)
        session.query(ErrorLog).filter(ErrorLog.created_at < cutoff_time).delete()
        session.commit()
    finally:
        session.close()

def init_infrastructure():
    Base.metadata.create_all(engine)
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_database_gc, 'interval', hours=12)
    scheduler.start()

if __name__ == "__main__":
    init_infrastructure()
    print("✅ 数据库基建初始化完成。")