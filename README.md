# Aagent V6.0 企业级多智能体网关

Aagent是一个面向企业级生产环境的LLM原生高并发网关与多智能体编排操作系统。

## 核心特性

### 四大核心引擎
- **智能网关 (Intelligent Gateway)**：内置Redis Lua限流、语义缓存、跨厂商协议抹平与异构模型负载均衡。支持断网自动降级至本地LM Studio算力。
- **确定性图编排 (Deterministic Orchestrator)**：基于状态机的并发Maker-Checker对抗网络，确保输出的绝对确定性和强类型契约。
- **双核执行沙箱 (Dual-Core Sandbox)**：兼具轻量级无服务器AST动态解析，与工业级隔离的Docker容器化代码执行底座。
- **全栈可观测性 (Full-Stack Observability)**：原生集成Prometheus监控、全局Trace ID链路追踪，以及详尽的执行日志飞轮。

### 新功能
1. **MCP协议支持**：接入标准的Model Context Protocol，可直接挂载全球开发者写好的成千上万个工具。
2. **Checkpointer和Time Travel**：支持任务中断、恢复和人工干预，实现状态的持久化和时光倒流。
3. **GraphRAG记忆系统**：从向量存储升级到基于实体和关系的知识图谱，实现更智能的记忆检索。
4. **LLMOps增强**：支持Prompt的A/B测试、版本管理，以及与Langfuse的集成，实现可视化的Prompt调优。
5. **强控制流策略引擎**：实现Reflexion、PlanAndSolve、SimpleFusion三大策略，支持真正的思考-评审-修正闭环。

## 目录结构

```
Aagent/
├── src/
│   ├── api/             # API接入层
│   ├── core/            # 核心服务群
│   │   ├── checkpoint.py # 检查点管理
│   │   ├── executor.py   # 执行器
│   │   ├── orchestrator.py # 编排器
│   │   ├── state.py      # 状态机
│   │   ├── prompt_manager.py # 提示词管理器
│   │   └── strategies/   # 推理策略
│   │       ├── base.py           # 策略基类
│   │       ├── reflexion.py      # Reflexion策略
│   │       ├── plan_and_solve.py # PlanAndSolve策略
│   │       ├── simple_fusion.py  # SimpleFusion策略
│   │       ├── react_loop.py     # ReAct循环策略
│   │       └── four_step_judge.py # 四步裁判策略
│   ├── data/            # 数据与记忆底座
│   │   ├── database.py   # 数据库
│   │   └── memory.py     # 记忆系统（GraphRAG）
│   ├── services/        # 服务层
│   │   ├── gateway.py    # 智能网关
│   │   ├── llmops/       # LLMOps功能
│   │   │   └── langfuse.py # Langfuse集成
│   │   ├── mcp/          # MCP协议支持
│   │   │   └── client.py # MCP客户端
│   │   ├── sandbox/      # 沙箱执行
│   │   ├── semantic_cache.py # 语义缓存
│   │   └── tracing.py    # 全链路追踪
│   ├── config.py         # 配置管理
│   └── utils/            # 工具函数
├── test_strategy_system.py # 策略系统测试
├── test_features.py      # 功能测试
├── docker-compose.yml    # Docker编排
├── prometheus.yml        # Prometheus配置
└── README.md             # 项目文档
```

## 安装

### 环境要求
- Python 3.8+
- Redis
- Docker (可选，用于沙箱执行)
- LM Studio (可选，用于本地模型)

### 安装依赖

```bash
pip install -r requirements.txt
```

### 环境变量配置

```bash
# 服务配置
API_HOST=0.0.0.0
API_PORT=8000

# 监控配置
JAEGER_HOST=localhost
JAEGER_PORT=6831

# 存储配置
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite+aiosqlite:///./agent_data.db

# 模型配置
LM_STUDIO_URL=http://localhost:1234/v1
DEFAULT_EXECUTION_MODEL=google/gemma-3-12b-it
DEFAULT_RESEARCH_MODEL=google/gemma-3-12b-it
DEFAULT_CREATIVE_MODEL=google/gemma-3-12b-it

# 策略配置
REFLEXION_MAX_ITERS=3
MAX_FUSION_MODELS=3
ENSEMBLE_SIZE=3

# 本地冗余节点配置
LOCAL_MODEL_URL=http://localhost:1234/v1
LOCAL_API_KEY=lm-studio
LOCAL_MODEL_NAME=deepseek-chat

# 沙箱配置
DOCKER_ENABLED=True
SANDBOX_TIMEOUT=10
SANDBOX_MEMORY_LIMIT=512m

# 语义缓存配置
CACHE_THRESHOLD=0.95
CACHE_EXPIRY=3600

# 记忆系统配置
MAX_SHORT_TERM_MEMORY=100

# Langfuse配置（可选）
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com

# MCP服务器配置（可选）
MCP_SERVER_URL=http://localhost:8000
```

## 快速开始

### 启动服务

```bash
# 启动Redis
redis-server

# 启动LM Studio（可选）
# 下载并安装LM Studio，启动本地模型服务

# 启动Aagent
python -m src.api.main
```

### 使用示例

```python
from src.core.orchestrator import AsyncRealOrchestrator
import asyncio

async def main():
    # 创建编排器
    orchestrator = AsyncRealOrchestrator()
    
    # 运行任务
    result = await orchestrator.start_work("编写一个简单的Python函数")
    print(result)
    
    # 列出检查点
    checkpoints = orchestrator.list_checkpoints()
    print(checkpoints)
    
    # 时光倒流（如果有检查点）
    if checkpoints:
        checkpoint_id = checkpoints[0]["checkpoint_id"]
        result = await orchestrator.time_travel(checkpoint_id)
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## 核心功能

### 强控制流策略引擎

Aagent实现了三大核心策略，支持真正的思考闭环：

#### 1. Reflexion策略（逻辑深钻）
实现Generate→Critique→Refine三阶段闭环，支持独立模型评审避免自我路径依赖。

```python
from src.core.strategies.reflexion import ReflexionStrategy

strategy = ReflexionStrategy()
result = await strategy.execute(messages, model_pool, trace_id)
```

#### 2. PlanAndSolve策略（巅峰博弈）
将复杂任务拆解为可控步骤，步进执行并汇总结果。

```python
from src.core.strategies.plan_and_solve import PlanAndSolveStrategy

strategy = PlanAndSolveStrategy()
result = await strategy.execute(messages, model_pool, trace_id)
```

#### 3. SimpleFusion策略（多模型聚合）
并发获取多个模型响应，实现高可用的答案融合。

```python
from src.core.strategies.simple_fusion import SimpleFusionStrategy

strategy = SimpleFusionStrategy()
result = await strategy.execute(messages, model_pool, trace_id)
```

### MCP协议支持

Aagent支持标准的Model Context Protocol，可直接接入外部MCP服务器，使用全球开发者提供的工具。

```python
# 创建带有MCP支持的编排器
orchestrator = AsyncRealOrchestrator(mcp_server_url="http://localhost:8000")
```

### 状态机与检查点

Aagent实现了基于状态机的编排系统，支持任务的暂停、恢复和时光倒流。

- **暂停任务**：创建检查点，保存当前执行状态
- **恢复任务**：从检查点恢复执行
- **时光倒流**：从指定检查点重新执行

### GraphRAG记忆系统

Aagent的记忆系统已升级为GraphRAG，能够：
- 从文本中提取实体和关系
- 构建知识图谱
- 基于图进行智能检索
- 支持跨会话的深度理解

### LLMOps功能

Aagent提供了完善的LLMOps功能：
- Prompt管理：创建、更新、列出Prompt
- A/B测试：比较不同Prompt的效果
- 版本管理：追踪Prompt的版本变化
- Langfuse集成：实现可视化的Prompt调优

## 路由策略

Aagent实现了L1-L7七级路由策略，根据任务复杂度自动选择合适的推理路径：

| 级别 | 策略 | 适用场景 |
|------|------|----------|
| L1 | 极速分诊 | 简单问答、快速响应 |
| L2 | 标准代理 | 常规任务、日常对话 |
| L3 | 思考回复 | 需要一定推理的问题 |
| L4 | 复杂执行 | 工具调用、多步骤任务 |
| L5 | 逻辑深钻 | Reflexion策略，深度推理 |
| L6 | 创意评审 | 四步裁判，多模型博弈 |
| L7 | 巅峰博弈 | PlanAndSolve，复杂规划任务 |

## 监控与可观测性

### 全链路追踪

Aagent集成了OpenTelemetry，支持：
- 全局Trace ID贯穿始终
- 详细的Span记录
- 与Jaeger的集成

### 监控指标

Aagent提供了丰富的监控指标：
- llm_request_latency_seconds：各模型响应延迟
- gateway_cache_hit_ratio：语义缓存命中率
- token_consumption_total：基于租户/模型的Token消耗
- sandbox_execution_timeouts：沙箱超时拦截率

## 开发指南

### 扩展策略

1. 继承 `ReasoningStrategy` 基类
2. 实现 `execute()` 方法
3. 使用 `AsyncGateway` 调用模型
4. 从 `PromptManager` 获取提示词

```python
from src.core.strategies.base import ReasoningStrategy

class CustomStrategy(ReasoningStrategy):
    def __init__(self):
        self.gateway = AsyncGateway()
    
    async def execute(self, messages, model_pool, trace_id):
        # 实现自定义逻辑
        pass
```

### 自定义Prompt

```python
# 设置自定义Prompt
gateway = AsyncGateway()
gateway.set_prompt("code", "你是一个专业的Python编程助手，能够提供高质量的代码和详细的解释。", "2.0.0")

# A/B测试Prompt
variants = [
    "你是一个专业的Python编程助手",
    "你是一个经验丰富的Python开发者"
]
test_inputs = ["编写一个排序函数", "如何实现装饰器"]
results = await gateway.a_b_test_prompts("code", variants, test_inputs)
print(results)
```

### 运行测试

```bash
# 运行策略系统测试
python test_strategy_system.py

# 运行功能测试
python test_features.py
```

### 贡献代码

1. Fork仓库
2. 创建特性分支
3. 提交代码
4. 运行测试
5. 创建Pull Request

## 许可证

MIT License

## 联系方式

- 项目地址：https://github.com/yourusername/aagent
- 问题反馈：https://github.com/yourusername/aagent/issues