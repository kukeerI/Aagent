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

## 项目结构

```
Aagent/
├── src/
│   ├── api/                    # API接入层
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI主入口，提供RESTful API
│   │   └── openai_shim.py      # OpenAI兼容API适配层，支持Open Interpreter
│   ├── core/                   # 核心服务群
│   │   ├── __init__.py
│   │   ├── checkpoint.py       # 检查点管理，支持任务中断/恢复/时光倒流
│   │   ├── executor.py         # 任务执行器，协调策略执行
│   │   ├── orchestrator.py     # 编排器，状态机驱动的任务管理
│   │   ├── prompt_manager.py   # 提示词管理器，支持版本管理和A/B测试
│   │   ├── prompts.py          # 内置提示词模板
│   │   ├── state.py            # 状态机定义
│   │   ├── task_analyzer.py    # 任务分析器，NLP语义提取
│   │   ├── task_router.py      # 任务路由器，L1-L7路由策略
│   │   ├── exceptions.py       # 自定义异常类
│   │   ├── pipelines/          # 管道处理模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # 管道基类
│   │   │   ├── stages.py       # 管道阶段定义
│   │   │   └── standard_pipeline.py  # 标准管道实现
│   │   └── strategies/         # 推理策略引擎
│   │       ├── __init__.py
│   │       ├── base.py         # 策略基类
│   │       ├── four_step_judge.py  # 四步裁判策略
│   │       ├── plan_and_solve.py   # PlanAndSolve策略
│   │       ├── react_loop.py       # ReAct循环策略
│   │       ├── reflexion.py        # Reflexion策略
│   │       ├── simple_fusion.py    # SimpleFusion策略
│   │       ├── strategy_factory.py # 策略工厂
│   │       └── strategy_selector.py # 策略选择器
│   ├── data/                   # 数据与记忆底座
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite数据库操作
│   │   ├── domain_models.py    # 领域模型定义
│   │   ├── memory.py           # GraphRAG记忆系统
│   │   └── schemas.py          # Pydantic数据模型
│   ├── services/               # 服务层
│   │   ├── __init__.py
│   │   ├── gateway.py          # 智能网关，多模型路由
│   │   ├── semantic_cache.py   # 语义缓存，基于Sentence-BERT
│   │   ├── tracing.py          # 全链路追踪，OpenTelemetry集成
│   │   ├── llmops/             # LLMOps功能
│   │   │   ├── __init__.py
│   │   │   └── langfuse.py     # Langfuse集成
│   │   ├── mcp/                # MCP协议支持
│   │   │   ├── __init__.py
│   │   │   └── client.py       # MCP客户端
│   │   └── sandbox/            # 沙箱执行
│   │       ├── __init__.py
│   │       ├── ast.py          # AST沙箱，轻量级代码解析
│   │       └── docker.py       # Docker沙箱，隔离执行环境
│   ├── utils/                  # 工具函数
│   │   ├── __init__.py
│   │   ├── logger.py           # 日志工具
│   │   ├── parser.py           # 解析工具
│   │   └── performance_monitor.py  # 性能监控
│   └── config.py               # 配置管理
├── examples/                   # 使用示例
│   ├── openinterpreter_integration.py  # Open Interpreter集成示例
│   └── usage_example.py       # 基础使用示例
├── scripts/                    # 脚本
│   ├── init_database.py       # 数据库初始化
│   ├── start.bat              # Windows启动脚本
│   └── start.sh               # Linux启动脚本
├── config.yaml                # 模型路由配置
├── model_router.py            # 多模型智能路由
├── rate_limit_monitor.py      # 限流监控
├── start_openai_shim.py       # OpenAI Shim启动入口
├── main.py                    # 主启动入口
├── requirements.txt           # 依赖清单
├── docker-compose.yml         # Docker编排
├── prometheus.yml             # Prometheus配置
└── .gitignore                 # Git忽略配置
```

## 文件功能详解

### API层 (src/api/)
| 文件 | 功能 |
|------|------|
| `main.py` | FastAPI主入口，提供RESTful API端点 |
| `openai_shim.py` | OpenAI兼容API，支持Open Interpreter接入 |

### 核心层 (src/core/)
| 文件 | 功能 |
|------|------|
| `orchestrator.py` | 编排器，管理任务生命周期和状态转换 |
| `executor.py` | 执行器，协调策略执行流程 |
| `checkpoint.py` | 检查点管理，支持任务中断、恢复和时光倒流 |
| `task_router.py` | 任务路由器，根据复杂度自动选择L1-L7策略 |
| `task_analyzer.py` | 任务分析器，NLP语义提取和意图识别 |
| `prompt_manager.py` | 提示词管理器，版本管理和A/B测试 |

### 策略引擎 (src/core/strategies/)
| 文件 | 策略名称 | 适用场景 |
|------|----------|----------|
| `reflexion.py` | Reflexion | 逻辑深钻，需要深度推理的任务 |
| `plan_and_solve.py` | PlanAndSolve | 复杂规划任务，多步骤分解 |
| `simple_fusion.py` | SimpleFusion | 多模型聚合，高可用答案融合 |
| `react_loop.py` | ReAct | 工具调用循环 |
| `four_step_judge.py` | 四步裁判 | 创意评审，多模型博弈 |

### 数据层 (src/data/)
| 文件 | 功能 |
|------|------|
| `memory.py` | GraphRAG记忆系统，实体关系提取和图谱检索 |
| `database.py` | SQLite数据库操作封装 |
| `schemas.py` | Pydantic数据模型定义 |

### 服务层 (src/services/)
| 文件 | 功能 |
|------|------|
| `gateway.py` | 智能网关，多模型路由和负载均衡 |
| `semantic_cache.py` | 语义缓存，基于向量相似度匹配 |
| `tracing.py` | 全链路追踪，OpenTelemetry集成 |
| `mcp/client.py` | MCP协议客户端，接入外部工具 |
| `sandbox/ast.py` | AST沙箱，轻量级代码安全解析 |
| `sandbox/docker.py` | Docker沙箱，隔离执行环境 |

## 启动方式

### 环境要求
- Python 3.8+
- Redis（用于限流和缓存）
- Docker（可选，用于沙箱执行）
- LM Studio（可选，用于本地模型）

### 安装依赖

```bash
cd D:\workspace\agentworkspace\Aagent
pip install -r requirements.txt
```

### 环境配置

复制 `.env.development` 为 `.env` 并配置：

```bash
# 服务配置
API_HOST=0.0.0.0
API_PORT=8000

# Redis配置
REDIS_URL=redis://localhost:6379/0

# 模型配置
LM_STUDIO_URL=http://localhost:1234/v1
DEFAULT_EXECUTION_MODEL=google/gemma-3-12b-it

# 沙箱配置
DOCKER_ENABLED=True

# 语义缓存配置
CACHE_THRESHOLD=0.95
```

### 启动命令

**方式一：启动完整服务**
```bash
python -m src.api.main
```

**方式二：使用启动脚本**
```bash
# Windows
scripts/start.bat

# Linux/Mac
scripts/start.sh
```

**方式三：启动OpenAI兼容接口（供Open Interpreter使用）**
```bash
python start_openai_shim.py
```

**方式四：运行示例**
```bash
python main.py
```

### 启动步骤

1. **启动Redis**
```bash
redis-server
```

2. **启动LM Studio（可选）**
```bash
# 下载并启动LM Studio，加载本地模型
```

3. **启动Aagent**
```bash
python -m src.api.main
```

4. **验证服务**
```bash
curl http://localhost:8000/health
```

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

## 多模型路由

项目支持多模型智能路由，自动根据任务类型选择最优模型：

| 任务类型 | 默认模型 | 成本 |
|----------|----------|------|
| code | DeepSeek-Coder-V2 | ~$0.10-0.20/1M tokens |
| creative | Google AI Studio (free) | $0 |
| analysis | GLM-4-Edge | ~$0.50/1M tokens |
| math | Google AI Studio | $0 |

## API接口

### 健康检查
```
GET /health
```

### 任务执行
```
POST /api/task/execute
Content-Type: application/json

{
  "prompt": "编写一个快排算法",
  "task_type": "code",
  "strategy": "auto"
}
```

### 检查点管理
```
GET  /api/checkpoint/list
POST /api/checkpoint/create
POST /api/checkpoint/restore/{checkpoint_id}
```

## 许可证

MIT License

## 联系方式

- 项目地址：https://github.com/kukeerI/Aagent
- 问题反馈：https://github.com/kukeerI/Aagent/issues