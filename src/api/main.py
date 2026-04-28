# src/api/main.py
# Web API 主服务

import asyncio
import time
import signal
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from contextlib import asynccontextmanager
import uuid

from src.core.orchestrator import AgentOrchestrator
from src.data.database import init_db, AsyncSessionLocal, ExecutionLog
from src.config import config
from src.services.gateway import ComputeResourceExhaustedError
from src.utils.logger import logger

# Prometheus 指标
REQUEST_COUNT = Counter('aagent_requests_total', 'Total number of requests', ['endpoint', 'method', 'status'])
REQUEST_LATENCY = Histogram('aagent_request_latency_seconds', 'Request latency', ['endpoint'])
ACTIVE_TASKS = Gauge('aagent_active_tasks', 'Number of active tasks')
COMPLETED_TASKS = Counter('aagent_completed_tasks_total', 'Total number of completed tasks', ['status'])
MODEL_USAGE = Counter('aagent_model_usage_total', 'Model usage count', ['model', 'type'])
CACHE_HITS = Counter('aagent_cache_hits_total', 'Semantic cache hits')
ERROR_COUNT = Counter('aagent_errors_total', 'Error count', ['type'])

class TaskRequest(BaseModel):
    task: str
    trace_id: str = None

class TaskResponse(BaseModel):
    trace_id: str
    status: str
    result: str | None = None
    error: str | None = None

class HealthResponse(BaseModel):
    status: str
    version: str
    active_tasks: int

# 全局编排器实例
orchestrator = None
# 活动任务集合
active_tasks = set()
# 服务状态
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    
    # 启动时初始化
    await init_db()
    orchestrator = AgentOrchestrator()
    ACTIVE_TASKS.set(0)
    
    # 注册信号处理
    def handle_sigterm(signum, frame):
        logger.info("收到 SIGTERM 信号，准备优雅关闭")
        shutdown_event.set()
    
    # 仅在非 Windows 系统注册信号处理
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, handle_sigterm)
    
    logger.info("Aagent 服务已启动")
    
    # 启动监控任务
    monitor_task = asyncio.create_task(monitor_shutdown())
    
    try:
        yield
    finally:
        # 关闭时清理
        logger.info("开始优雅关闭流程")
        
        # 触发关闭事件
        shutdown_event.set()
        
        # 等待监控任务完成
        await monitor_task
        
        # 等待所有活动任务完成或超时
        if active_tasks:
            logger.info(f"等待 {len(active_tasks)} 个活动任务完成...")
            try:
                # 给 30 秒时间让任务优雅结束
                await asyncio.wait_for(
                    asyncio.gather(*active_tasks, return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("优雅关闭超时，强制终止剩余任务")
        
        # 关闭编排器
        if orchestrator:
            try:
                await orchestrator.gateway.close()
            except Exception as e:
                logger.error(f"关闭编排器时出错: {e}")
        
        logger.info("Aagent 服务已关闭")

async def monitor_shutdown():
    """监控关闭事件"""
    await shutdown_event.wait()
    logger.info("开始处理关闭事件")
    
    # 可以在这里添加额外的关闭逻辑
    # 比如停止接受新请求、通知正在执行的任务等


app = FastAPI(
    title="Aagent API",
    description="企业级智能体框架 API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器
@app.exception_handler(ComputeResourceExhaustedError)
async def handle_resource_exhausted(request: Request, exc: ComputeResourceExhaustedError):
    ERROR_COUNT.labels(type='resource_exhausted').inc()
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable due to resource constraints"}
    )

@app.exception_handler(asyncio.TimeoutError)
async def handle_timeout(request: Request, exc: asyncio.TimeoutError):
    ERROR_COUNT.labels(type='timeout').inc()
    return JSONResponse(
        status_code=429,
        content={"detail": "Request timeout. Please try again later"}
    )

@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception):
    ERROR_COUNT.labels(type='generic_error').inc()
    # 记录异常但不暴露给客户端
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(status="healthy", version="1.0.0", active_tasks=int(ACTIVE_TASKS._value.get()))

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/task", response_model=TaskResponse)
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    trace_id = request.trace_id or str(uuid.uuid4())
    start_time = time.time()

    try:
        ACTIVE_TASKS.inc()
        REQUEST_COUNT.labels(endpoint='/task', method='POST', status='started').inc()

        # 在后台执行任务
        async def run_task():
            global orchestrator
            task = asyncio.current_task()
            active_tasks.add(task)
            try:
                if orchestrator is None:
                    orchestrator = AgentOrchestrator(trace_id=trace_id)
                await orchestrator.start_work(request.task)
                COMPLETED_TASKS.labels(status='success').inc()
            except Exception as e:
                ERROR_COUNT.labels(type='execution_error').inc()
                COMPLETED_TASKS.labels(status='error').inc()
                logger.error(f"任务执行失败: {e}")
            finally:
                ACTIVE_TASKS.dec()
                active_tasks.remove(task)

        background_tasks.add_task(run_task)

        # 等待一小段时间让任务开始执行
        await asyncio.sleep(0.1)

        # 从数据库获取最新结果
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ExecutionLog)
                .where(ExecutionLog.trace_id == trace_id)
                .order_by(ExecutionLog.created_at.desc())
                .limit(1)
            )
            log = result.scalar_one_or_none()

            if log:
                return TaskResponse(
                    trace_id=trace_id,
                    status="completed",
                    result=log.response or ""
                )
            else:
                return TaskResponse(
                    trace_id=trace_id,
                    status="processing",
                    result=""
                )

    except Exception as e:
        ERROR_COUNT.labels(type='api_error').inc()
        REQUEST_COUNT.labels(endpoint='/task', method='POST', status='error').inc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        REQUEST_LATENCY.labels(endpoint='/task').observe(time.time() - start_time)

@app.get("/task/{trace_id}")
async def get_task(trace_id: str):
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ExecutionLog)
            .where(ExecutionLog.trace_id == trace_id)
            .order_by(ExecutionLog.created_at.desc())
        )
        logs = result.scalars().all()

        if not logs:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "trace_id": trace_id,
            "status": "completed" if logs[0].response else "processing",
            "steps": [
                {
                    "role": log.role,
                    "prompt": log.prompt[:200] + "..." if len(log.prompt) > 200 else log.prompt,
                    "response": log.response[:200] + "..." if len(log.response) > 200 else log.response,
                    "model_used": log.model_used,
                    "is_local_fallback": log.is_local_fallback,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ]
        }

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/stats")
async def stats():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func

        total_requests = await session.scalar(select(func.count(ExecutionLog.id)))
        successful_requests = await session.scalar(
            select(func.count(ExecutionLog.id))
            .where(ExecutionLog.error_message == None)
        )
        local_fallback_count = await session.scalar(
            select(func.count(ExecutionLog.id))
            .where(ExecutionLog.is_local_fallback == True)
        )

        return {
            "total_requests": total_requests or 0,
            "successful_requests": successful_requests or 0,
            "local_fallback_count": local_fallback_count or 0,
            "active_tasks": int(ACTIVE_TASKS._value.get()),
            "cache_hits": int(CACHE_HITS._value.get()),
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)