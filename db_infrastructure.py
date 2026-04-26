import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///agent_data.db', echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class APIAsset(Base):
    __tablename__ = 'api_assets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50))        
    model_name = Column(String(100))     
    category = Column(String(50))        
    domain_skill = Column(String(50))    
    rpm_limit = Column(Integer)          
    tpm_limit = Column(BigInteger)       
    rpd_limit = Column(Integer)          
    weight = Column(Float, default=1.0)
    status = Column(String(20), default="ACTIVE") 
    reset_hour_utc = Column(Integer, default=0)    
    api_key = Column(String(200)) # 存储环境变量的 Key 名称

class ErrorLog(Base):
    __tablename__ = 'error_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_id = Column(Integer, nullable=False)
    error_type = Column(String(50))
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_infrastructure():
    Base.metadata.create_all(engine)