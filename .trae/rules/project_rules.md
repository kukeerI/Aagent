# Aagent 项目开发规则

## 性能优化原则

### 1. 超时配置
- **HTTP 请求超时**: 默认 8s，开发模式不超过 10s
- **重试次数**: 开发模式最多 1 次，生产模式最多 3 次
- **重试延迟**: 开发模式 0.5s，生产模式 1.0s
- **沙箱执行**: 开发模式 5s，生产模式 10s

### 2. 开发模式检查
```python
from src.config import config

# 快速失败检查
if config.DEV_FAST_FAIL and not nodes:
    print("[开发模式] 无可用节点，快速失败")
    return fallback_result

# 跳过人工干预
if config.DEV_MODE and config.DEV_FAST_FAIL:
    print("[开发模式] 跳过人工干预，快速通过")
```

### 3. 性能日志规范
每个 IO 操作必须记录：
- 开始时间
- 超时设置
- 成功/失败状态
- 耗时统计

```python
start_time = time.time()
print(f"[操作名] 开始... (超时: {config.REQUEST_TIMEOUT}s)")
try:
    result = await operation()
    elapsed = time.time() - start_time
    print(f"[操作名] 成功 (耗时: {elapsed:.2f}s)")
except asyncio.TimeoutError:
    elapsed = time.time() - start_time
    print(f"[操作名] 超时 (耗时: {elapsed:.2f}s)")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"[操作名] 失败 (耗时: {elapsed:.2f}s): {e}")
```

### 4. 性能监控使用
```python
from src.utils.performance_monitor import performance_monitor

# 装饰器自动记录
@performance_monitor.timed("operation_name")
async def my_operation():
    pass

# 定期输出摘要
performance_monitor.print_summary()
```

### 5. 环境配置
- 开发环境: 复制 `.env.development` 为 `.env`
- 生产环境: 设置 `DEV_MODE=false`

## 常见卡顿点

1. **外部 API 调用**: 必须使用超时设置
2. **Docker 沙箱**: 开发模式使用 AST 沙箱替代
3. **数据库查询**: 添加查询超时
4. **文件 IO**: 使用异步操作
5. **重试机制**: 开发模式减少重试次数

## 快速失败原则

在开发模式下：
1. 网络请求失败立即返回，不重试
2. 外部服务不可用使用 mock 数据
3. 人工干预环节自动跳过
4. 超时时间设置较短，快速暴露问题
