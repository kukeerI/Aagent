# Aagent - 企业级智能体框架

Aagent 是一个高性能、可扩展的企业级智能体框架，专为复杂任务的自动化处理而设计。它采用模块化架构，支持多模型联邦、本地/云端双轨降级、全链路追踪等企业级特性。

## 核心特性

- **模块化架构**：清晰的目录结构，便于维护和扩展
- **多模型联邦**：支持多种大语言模型，智能路由和负载均衡
- **本地/云端双轨降级**：网络不稳定时自动切换到本地模型
- **全链路追踪**：集成 OpenTelemetry，支持 Jaeger 导出
- **语义缓存**：基于 Redis 的语义级缓存，提升响应速度
- **安全沙箱**：Docker 容器隔离执行环境，防止资源耗尽攻击
- **记忆系统**：短期记忆 + 长期记忆 + 逻辑依赖图
- **实时监控**：Prometheus 指标集成，提供详细的运行状态

## 目录结构

```
src/
├── api/           # Web API 服务
├── core/          # 核心逻辑
├── data/          # 数据层
├── services/      # 服务层
│   ├── sandbox/   # 沙箱执行环境
│   ├── gateway/   # 模型网关
│   ├── tracing/   # 全链路追踪
│   └── semantic_cache/ # 语义缓存
├── utils/         # 工具函数
└── config.py      # 配置管理
```

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/aagent.git
cd aagent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件，配置以下环境变量：

```env
# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# 模型配置
LM_STUDIO_URL=http://localhost:1234/v1

# 存储配置
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite+aiosqlite:///./agent_data.db

# 沙箱配置
DOCKER_ENABLED=True
SANDBOX_TIMEOUT=10
SANDBOX_MEMORY_LIMIT=512m

# 监控配置
JAEGER_HOST=localhost
JAEGER_PORT=6831

# 日志配置
LOG_LEVEL=INFO
```

### 4. 启动服务

```bash
python -m src.api.main
```

## 快速开始

### 1. 基本使用

```python
from src.core.orchestrator import AsyncRealOrchestrator

async def main():
    # 创建编排器实例
    orchestrator = AsyncRealOrchestrator()
    
    # 执行任务
    await orchestrator.start_work("帮我分析一下当前市场趋势")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 2. API 调用

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我生成一个Python函数，计算斐波那契数列"}'
```

### 3. 查看执行结果

```bash
curl http://localhost:8000/task/{trace_id}
```

## 配置管理

Aagent 使用集中式配置管理，所有配置项都可以通过环境变量或 `src/config.py` 文件进行调整。

### 主要配置项

- `API_HOST`：API 服务监听地址
- `API_PORT`：API 服务监听端口
- `LM_STUDIO_URL`：本地模型服务地址
- `REDIS_URL`：Redis 连接地址
- `DATABASE_URL`：数据库连接地址
- `DOCKER_ENABLED`：是否启用 Docker 沙箱
- `SANDBOX_TIMEOUT`：沙箱执行超时时间（秒）
- `JAEGER_HOST`：Jaeger 追踪服务地址
- `JAEGER_PORT`：Jaeger 追踪服务端口

## 监控与可观测性

### 1. 指标端点

- `/metrics`：Prometheus 指标
- `/stats`：系统统计信息
- `/health`：健康检查

### 2. 全链路追踪

Aagent 集成了 OpenTelemetry，可以将追踪数据导出到 Jaeger：

1. 启动 Jaeger 服务：
   ```bash
docker run -d --name jaeger -p 6831:6831/udp -p 16686:16686 jaegertracing/all-in-one:latest
   ```

2. 访问 Jaeger UI：
   ```
   http://localhost:16686
   ```

## 沙箱执行

Aagent 支持两种沙箱执行模式：

1. **Docker 沙箱**：使用 Docker 容器隔离执行环境，提供最强的安全性
2. **AST 沙箱**：基于 AST 解析的沙箱，作为 Docker 不可用时的 fallback

## 语义缓存

Aagent 集成了基于 Redis 的语义缓存，可以：
- 缓存相似查询的结果，提升响应速度
- 减少重复请求，节省模型调用成本
- 支持域隔离，不同领域的缓存相互独立

## 记忆系统

Aagent 的记忆系统包含三个层次：

1. **短期记忆**：滑动窗口，存储最近的交互
2. **长期记忆**：持久化存储，存储重要的交互
3. **逻辑依赖图**：记录任务间的逻辑关系，支持因果推理

## 开发指南

### 1. 添加新服务

在 `src/services/` 目录下创建新的服务模块，然后在需要的地方导入使用。

### 2. 扩展模型支持

在 `src/services/gateway.py` 中添加新的模型配置，支持更多的大语言模型。

### 3. 自定义沙箱

在 `src/services/sandbox/` 目录下创建新的沙箱实现，实现 `execute_code` 方法。

## 测试

### 运行单元测试

```bash
python -m pytest tests/
```

### 运行性能测试

```bash
python tests/test_model_performance.py --model gemma
python tests/test_model_performance.py --model qwen
python tests/test_model_performance.py --compare
```

## 部署

### Docker 部署

```bash
docker build -t aagent .
docker run -p 8000:8000 --env-file .env aagent
```

### Kubernetes 部署

参考 `k8s/` 目录下的部署配置文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License