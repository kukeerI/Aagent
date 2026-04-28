# src/core/exceptions.py
# 异常定义模块 - 定义系统所有异常的层次结构
# 依赖：无
# 异常层次：
#   AagentException (基类)
#   ├── ComputeResourceExhaustedError - 计算资源耗尽
#   ├── ModelInferenceError - 模型推理失败
#   ├── CodeExecutionError - 代码执行错误
#   ├── StateMachineError - 状态机错误
#   ├── CheckpointError - 检查点错误
#   ├── TaskAnalysisError - 任务分析错误
#   │   ├── TaskRiskEscalation - 任务风险熔断
#   │   └── ProfileInconsistencyError - 画像不一致
#   ├── GatewayError - 网关错误
#   ├── ConfigurationError - 配置错误
#   ├── TimeoutError - 超时错误
#   └── ValidationError - 验证错误

class AagentException(Exception):
    """Aagent 基础异常类

    所有 Aagent 自定义异常的基类，继承自 Python 内置 Exception 类。
    所有具体异常都应该继承此类，以便统一捕获和处理。
    """
    pass

class ComputeResourceExhaustedError(AagentException):
    """计算资源耗尽异常

    当高阶算力池（如 GPT-4、Gemini 等高级 API）耗尽时抛出。
    系统会阻止低质量降级，保证高价值任务的执行质量。
    """
    pass

class ModelInferenceError(AagentException):
    """模型推理异常

    当语言模型推理失败时抛出，包括：
    - 模型 API 返回错误
    - 模型响应格式异常
    - 模型服务不可用
    """
    pass

class CodeExecutionError(AagentException):
    """代码执行异常

    当代码执行沙箱执行用户代码失败时抛出，包括：
    - 代码语法错误
    - 代码运行时错误
    - 沙箱资源限制
    """
    pass

class StateMachineError(AagentException):
    """状态机异常

    当状态机发生非法状态转换或处理错误时抛出。
    表明系统处于不一致状态，需要人工干预。
    """
    pass

class CheckpointError(AagentException):
    """检查点异常

    当任务状态保存或恢复失败时抛出，包括：
    - 数据库写入失败
    - 检查点数据损坏
    - 状态回滚失败
    """
    pass

class TaskAnalysisError(AagentException):
    """任务分析异常

    当任务分析器（TaskAnalyzer）无法正确解析任务时抛出，包括：
    - 语义提取失败
    - 意图分析错误
    - 复杂度评估异常
    """
    pass


class TaskRiskEscalation(TaskAnalysisError):
    """任务风险触发强制熔断/提级异常

    当任务的风险评分超过阈值时抛出，触发熔断机制或升级处理流程。
    例如：risk_score >= 0.9 的高危操作需要人工确认。
    """
    pass


class ProfileInconsistencyError(TaskAnalysisError):
    """画像数据不一致错误

    当任务画像的各维度评分存在逻辑矛盾时抛出。
    例如：物理特征极高（如超长文本）但业务评分极低，可能存在伪装任务。
    """
    pass

class GatewayError(AagentException):
    """网关异常

    当网关（Gateway）处理请求失败时抛出，包括：
    - 节点选择失败
    - 请求发送失败
    - 响应解析错误
    """
    pass

class ConfigurationError(AagentException):
    """配置异常

    当系统配置无效或缺失时抛出，包括：
    - 必需配置项缺失
    - 配置格式错误
    - 配置值超出有效范围
    """
    pass

class TimeoutError(AagentException):
    """超时异常

    当操作超过预定时间未完成时抛出，包括：
    - HTTP 请求超时
    - 模型推理超时
    - 数据库操作超时
    """
    pass

class ValidationError(AagentException):
    """验证异常

    当数据验证失败时抛出，包括：
    - 输入参数验证失败
    - 状态转换验证失败
    - 数据完整性验证失败
    """
    pass


class StrategyFallbackError(AagentException):
    """策略降级异常

    当当前策略执行失败需要降级到其他策略时抛出。
    StrategyFactory 会捕获此异常并尝试使用降级策略。
    """
    pass
