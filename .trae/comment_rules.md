# 注释生成规则

## 1. 文件头

每个源代码文件应在顶部包含文件头注释，包含：

- **模块名**：文件的主要功能模块
- **用途**：文件的功能描述
- **依赖**：主要的外部依赖和模块
- **注意事项**：使用时的关键点

```python
# src/core/orchestrator.py
# 智能体编排器 - 负责任务调度、推理流程编排和结果整合
# 依赖：AgentExecutor, AgentStateMachine, StandardPipeline, Memory
# 注意：所有 IO 操作需记录性能日志
```

## 2. 函数注释

使用 docstring 格式，包含：

- **功能描述**：函数的核心功能
- **Args**：参数说明，包括类型和含义
- **Returns**：返回值说明
- **Raises**：可能抛出的异常

```python
async def execute_task(self, task: TaskRequest) -> TaskResponse:
    """执行智能体任务

    Args:
        task: 任务请求对象，包含任务描述和配置

    Returns:
        TaskResponse: 任务执行结果，包含状态和响应内容

    Raises:
        TaskExecutionError: 任务执行失败时抛出
        ResourceExhaustedError: 资源耗尽时抛出
    """
```

## 3. 行内注释

只在以下情况添加行内注释：

- **算法逻辑**：复杂的算法实现
- **边界条件**：重要的边界判断
- **兼容性处理**：平台特定的代码
- **性能关键**：影响性能的代码段

```python
# 使用指数退避策略避免惊群效应
delay = min(base_delay * (2 ** attempt), max_delay)
# Windows 平台需要特殊处理路径分隔符
if sys.platform == 'win32':
    path = path.replace('/', '\\')
```

## 4. TODO 格式

使用标准 TODO 格式，便于追踪：

```python
# TODO(zhangsan): 2026-06-01 实现异步模型加载
# TODO(lisi): 2026-07-01 优化查询性能，添加索引
```

## 5. 禁止事项

- **禁止**给简单操作加注释（如 `i++`、`count += 1`）
- **禁止**保留注释掉的代码（使用版本控制）
- **禁止**无意义的注释（如 `// 这是循环`）
- **禁止**中文拼音变量名

## 6. 示例

### 正确示例

```python
# src/core/task_analyzer.py
# 任务分析器 - 提取语义数据、分类任务难度、生成执行策略
# 依赖：SentenceTransformer, AsyncGateway

class TaskAnalyzer:
    """任务分析器"""

    async def extract_semantic_data(self, user_input: str) -> Dict[str, Any]:
        """提取用户输入的语义数据

        Args:
            user_input: 用户的原始输入文本

        Returns:
            Dict: 包含意图、实体、情感等语义特征

        Raises:
            ExtractionError: 语义提取失败时抛出
        """
        # 使用滑动窗口处理超长输入，避免模型截断
        windows = self._create_sliding_windows(user_input, window_size=512)
        results = await asyncio.gather(*[self._analyze_window(w) for w in windows])
        return self._merge_results(results)
```

### 错误示例

```python
# 错误：给简单操作加注释
# 增加计数
count += 1

# 错误：保留注释掉的代码
# old_code = do_something()
# new_code = do_something_else()

# 错误：无意义注释
# 这是循环
for i in range(10):
    pass
```
