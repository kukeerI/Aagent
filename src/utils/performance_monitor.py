# src/utils/performance_monitor.py
# 性能监控工具 - 用于记录和分析卡顿问题

import time
import json
from typing import Dict, List, Optional, Callable
from datetime import datetime
from functools import wraps

class PerformanceMonitor:
    """性能监控器 - 记录和分析系统性能"""
    
    def __init__(self):
        self.records: List[Dict] = []
        self.thresholds = {
            "gateway_request": 5.0,  # 网关请求超过5秒视为卡顿
            "judge_workflow": 30.0,  # 评审工作流超过30秒视为卡顿
            "entity_extraction": 10.0,  # 实体核查超过10秒视为卡顿
            "sandbox_execution": 5.0,  # 沙箱执行超过5秒视为卡顿
        }
    
    def record(self, operation: str, elapsed_time: float, status: str = "success", details: Optional[Dict] = None):
        """记录操作性能数据"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "elapsed_time": elapsed_time,
            "status": status,
            "details": details or {},
            "is_slow": False
        }
        
        # 检查是否超过阈值
        if operation in self.thresholds:
            threshold = self.thresholds[operation]
            if elapsed_time > threshold:
                record["is_slow"] = True
                print(f"[性能警告] {operation} 耗时 {elapsed_time:.2f}s，超过阈值 {threshold}s")
        
        self.records.append(record)
        return record
    
    def timed(self, operation: str):
        """装饰器 - 自动记录函数执行时间"""
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    elapsed_time = time.time() - start_time
                    self.record(operation, elapsed_time, "success", {
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    })
                    return result
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    self.record(operation, elapsed_time, "error", {
                        "function": func.__name__,
                        "error": str(e)
                    })
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    elapsed_time = time.time() - start_time
                    self.record(operation, elapsed_time, "success", {
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    })
                    return result
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    self.record(operation, elapsed_time, "error", {
                        "function": func.__name__,
                        "error": str(e)
                    })
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
    
    def get_slow_operations(self) -> List[Dict]:
        """获取所有卡顿的操作记录"""
        return [r for r in self.records if r.get("is_slow", False)]
    
    def get_summary(self) -> Dict:
        """获取性能摘要"""
        if not self.records:
            return {"message": "暂无性能记录"}
        
        total_operations = len(self.records)
        slow_operations = len(self.get_slow_operations())
        avg_time = sum(r["elapsed_time"] for r in self.records) / total_operations
        
        # 按操作类型分组统计
        operation_stats = {}
        for record in self.records:
            op = record["operation"]
            if op not in operation_stats:
                operation_stats[op] = {"count": 0, "total_time": 0, "slow_count": 0}
            operation_stats[op]["count"] += 1
            operation_stats[op]["total_time"] += record["elapsed_time"]
            if record.get("is_slow", False):
                operation_stats[op]["slow_count"] += 1
        
        # 计算平均时间
        for op in operation_stats:
            stats = operation_stats[op]
            stats["avg_time"] = stats["total_time"] / stats["count"]
        
        return {
            "total_operations": total_operations,
            "slow_operations": slow_operations,
            "slow_rate": f"{(slow_operations/total_operations*100):.1f}%",
            "avg_time": f"{avg_time:.2f}s",
            "operation_stats": operation_stats
        }
    
    def export_report(self, filename: Optional[str] = None) -> str:
        """导出性能报告"""
        if filename is None:
            filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_summary(),
            "slow_operations": self.get_slow_operations(),
            "all_records": self.records
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"[性能监控] 报告已导出: {filename}")
        return filename
    
    def print_summary(self):
        """打印性能摘要"""
        summary = self.get_summary()
        print("\n" + "="*60)
        print("性能监控摘要")
        print("="*60)
        
        if "message" in summary:
            print(summary["message"])
        else:
            print(f"总操作数: {summary['total_operations']}")
            print(f"卡顿操作数: {summary['slow_operations']}")
            print(f"卡顿率: {summary['slow_rate']}")
            print(f"平均耗时: {summary['avg_time']}")
            
            if summary['operation_stats']:
                print("\n各操作类型统计:")
                for op, stats in summary['operation_stats'].items():
                    print(f"  {op}:")
                    print(f"    执行次数: {stats['count']}")
                    print(f"    平均耗时: {stats['avg_time']:.2f}s")
                    print(f"    卡顿次数: {stats['slow_count']}")
        
        print("="*60)

# 全局性能监控实例
performance_monitor = PerformanceMonitor()

# 导入 asyncio 用于检测异步函数
import asyncio
