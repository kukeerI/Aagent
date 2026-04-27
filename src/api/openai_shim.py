# src/api/openai_shim.py
# OpenAI 兼容接口 - 供 Open Interpreter 等客户端直接接入

import asyncio
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uuid

from src.services.gateway import AsyncGateway
from src.services.semantic_cache import SemanticCache
from src.services.tracing import tracing
from src.data.database import init_db, AsyncSessionLocal, APIAsset, record_token_usage, get_token_estimate
from src.config import config
from src.core.orchestrator import AsyncRealOrchestrator
from src.core.task_analyzer import task_analyzer

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "auto"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage

class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]]

# 全局网关实例
gateway: AsyncGateway = None
semantic_cache: SemanticCache = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global gateway, semantic_cache
    await init_db()
    gateway = AsyncGateway()
    semantic_cache = SemanticCache()
    print("[OpenAI-Shim] OpenAI 兼容接口已启动")
    yield
    print("[OpenAI-Shim] OpenAI 兼容接口已关闭")

app = FastAPI(
    title="Aagent OpenAI-Compatible API",
    description="符合 OpenAI 格式的 API，供 Open Interpreter 等客户端直接接入",
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

@app.get("/v1/models", response_model=ModelsResponse)
async def list_models():
    """列出可用模型"""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(APIAsset).where(APIAsset.enabled == True)
            )
            assets = result.scalars().all()

            models = [
                {
                    "id": asset.model_name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "aagent",
                    "permission": [],
                    "root": asset.model_name,
                    "parent": None
                }
                for asset in assets
            ]

            # 添加本地模型
            models.append({
                "id": "local-model",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "aagent",
                "permission": [],
                "root": "local-model",
                "parent": None
            })

            return ModelsResponse(data=models)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, raw_request: Request):
    """OpenAI 兼容的 chat completions 接口"""
    try:
        trace_id = str(uuid.uuid4())
        with tracing.start_span("openai_shim.chat_completions", attributes={
            "trace_id": trace_id,
            "model": request.model,
            "message_count": len(request.messages)
        }) as span:
            # 转换消息格式
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

            # Token 预估：先报价格，再执行
            task_type = "general"
            if messages:
                user_input = messages[-1]["content"]
                # 简单任务类型分类
                if any(keyword in user_input.lower() for keyword in ["code", "编程", "写代码"]):
                    task_type = "code"
                elif any(keyword in user_input.lower() for keyword in ["分析", "评估", "研究"]):
                    task_type = "analysis"
                elif any(keyword in user_input.lower() for keyword in ["创意", "设计", "写"]):
                    task_type = "creative"
                elif any(keyword in user_input.lower() for keyword in ["什么是", "如何", "为什么"]):
                    task_type = "information"
            
            # 获取 Token 预估
            model_name = request.model or "auto"
            token_estimate = await get_token_estimate(task_type, model_name)
            print(f"[OpenAI-Shim] Token 预估: {token_estimate['avg_total_tokens']} tokens")

            # 尝试语义缓存
            with tracing.start_span("semantic_cache.get"):
                cache_key = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": request.temperature
                }
                cached_response = await semantic_cache.get(cache_key)
                if cached_response:
                    span.set_attribute("cache_hit", True)
                    return cached_response
                span.set_attribute("cache_hit", False)

            # 双引擎动态路由
            is_reasoning_mode = False
            
            # 检查模型名称
            if request.model and "reasoning" in request.model:
                is_reasoning_mode = True
            
            # 检查请求头
            if raw_request.headers.get("X-Aagent-Mode") == "deep":
                is_reasoning_mode = True

            # 任务分析器：使用语义方差法自动判断路由
            if not is_reasoning_mode:
                with tracing.start_span("task_analyzer.analyze"):
                    # 获取用户输入
                    user_input = messages[-1]["content"] if messages else ""
                    if user_input:
                        analysis_result = await task_analyzer.analyze_task(user_input)
                        recommended_route = analysis_result["recommended_route"]
                        is_reasoning_mode = (recommended_route == "reasoning")
                        
                        if is_reasoning_mode:
                            print(f"[OpenAI-Shim] TaskAnalyzer 推荐深度推理模式")
                        else:
                            print(f"[OpenAI-Shim] TaskAnalyzer 推荐快速路由模式")

            if is_reasoning_mode:
                # 走深度思考慢车道
                with tracing.start_span("orchestrator.run_reasoning_flow"):
                    print(f"[OpenAI-Shim] 进入深度推理模式")
                    orchestrator = AsyncRealOrchestrator(trace_id=trace_id)
                    response_text = await orchestrator.run_reasoning_flow(messages, trace=trace_id)
            else:
                # 走 OI 极速代理快车道
                with tracing.start_span("gateway.fast_route"):
                    print(f"[OpenAI-Shim] 进入快速路由模式")
                    response_text = await gateway.fast_route(messages, domain_skill="Desktop_Assistant")

            # 构建响应
            response = _build_response(response_text, model_name, messages)
            
            # 记录 Token 使用情况
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # 异步记录 Token 使用
            asyncio.create_task(
                record_token_usage(task_type, model_name, prompt_tokens, completion_tokens, total_tokens)
            )
            print(f"[OpenAI-Shim] 记录 Token 使用: {total_tokens} tokens")
            
            # 设置缓存
            await semantic_cache.set(cache_key, response)
            
            return response

    except Exception as e:
        print(f"[OpenAI-Shim] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _build_response(content: str, model: str, messages: List[Dict[str, str]]) -> ChatCompletionResponse:
    """构建 OpenAI 格式的响应"""
    # 清理内容中的 [本地模型] 标记
    if content.startswith("[本地模型]"):
        content = content[7:].strip()

    response_message = Message(role="assistant", content=content)

    # 估算 token 使用量
    prompt_tokens = sum(len(msg["content"]) // 4 for msg in messages)
    completion_tokens = len(content) // 4

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(time.time()),
        model=model,
        choices=[ChatCompletionChoice(
            index=0,
            message=response_message,
            finish_reason="stop"
        )],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
    )

@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy", "service": "openai-shim"}

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Aagent OpenAI-Compatible API",
        "version": "1.0.0",
        "endpoints": {
            "/v1/models": "列出可用模型",
            "/v1/chat/completions": "聊天补全（OpenAI 兼容）",
            "/health": "健康检查"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
