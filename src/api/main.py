# src/api/main.py
# Web API 主服务

import asyncio
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from contextlib import asynccontextmanager
import uuid

from src.core.orchestrator import AsyncRealOrchestrator
from src.data.database import init_db, AsyncSessionLocal, ExecutionLog
from src.config import config

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
    result: str = None
    error: str = None

class HealthResponse(BaseModel):
    status: str
    version: str
    active_tasks: int

# 全局编排器实例
orchestrator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    # 启动时初始化
    await init_db()
    orchestrator = AsyncRealOrchestrator()
    ACTIVE_TASKS.set(0)
    print("[API] Aagent 服务已启动")
    yield
    # 关闭时清理
    print("[API] Aagent 服务已关闭")

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
            try:
                if orchestrator is None:
                    orchestrator = AsyncRealOrchestrator(trace_id=trace_id)
                await orchestrator.start_work(request.task)
                COMPLETED_TASKS.labels(status='success').inc()
            except Exception as e:
                ERROR_COUNT.labels(type='execution_error').inc()
                COMPLETED_TASKS.labels(status='error').inc()
                print(f"[API] 任务执行失败: {e}")
            finally:
                ACTIVE_TASKS.dec()

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
                    result=log.response
                )
            else:
                return TaskResponse(
                    trace_id=trace_id,
                    status="processing",
                    result=None
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