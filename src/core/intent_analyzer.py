# src/core/intent_analyzer.py
# 意图量化与七级路由矩阵

from typing import Dict, Tuple, Any
import re

class IntentAnalyzer:
    """意图分析器"""
    
    @staticmethod
    def analyze_intent(task: str, semantic_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析任务意图并计算路由级别
        
        Args:
            task: 任务描述
            semantic_data: 从 TaskAnalyzer 提取的语义数据
            
        Returns:
            Dict: 包含意图分析结果的字典
        """
        # 计算三个维度的分数
        value = IntentAnalyzer._calculate_value(task)
        complexity = IntentAnalyzer._calculate_complexity(task, semantic_data)
        innovation = IntentAnalyzer._calculate_innovation(task, semantic_data)
        
        # 确定路由级别
        route_level = IntentAnalyzer._determine_route_level(value, complexity, innovation)
        
        return {
            "value": value,
            "complexity": complexity,
            "innovation": innovation,
            "route_level": route_level,
            "route_name": IntentAnalyzer._get_route_name(route_level)
        }
    
    @staticmethod
    def _calculate_value(task: str) -> int:
        """计算价值/重要性分数 [1-10]"""
        # 高价值关键词
        high_value_keywords = [
            "重要", "紧急", "关键", "核心", "重要性", "价值", "商业", "业务", "收入",
            "important", "urgent", "critical", "core", "value", "business", "revenue"
        ]
        
        # 中价值关键词
        medium_value_keywords = [
            "分析", "研究", "评估", "建议", "方案", "策略",
            "analyze", "research", "evaluate", "recommend", "plan", "strategy"
        ]
        
        # 低价值关键词
        low_value_keywords = [
            "查询", "简单", "快速", "基础", "日常",
            "query", "simple", "quick", "basic", "routine"
        ]
        
        score = 5  # 基础分
        
        # 增加高价值关键词分数
        for keyword in high_value_keywords:
            if keyword in task.lower():
                score += 2
        
        # 增加中价值关键词分数
        for keyword in medium_value_keywords:
            if keyword in task.lower():
                score += 1
        
        # 降低低价值关键词分数
        for keyword in low_value_keywords:
            if keyword in task.lower():
                score -= 1
        
        # 确保分数在 1-10 范围内
        return max(1, min(10, score))
    
    @staticmethod
    def _calculate_complexity(task: str, semantic_data: Dict[str, Any] = None) -> int:
        """计算复杂程度分数 [1-10]"""
        # 高复杂度关键词
        high_complexity_keywords = [
            "复杂", "困难", "挑战", "多步骤", "多阶段", "集成", "系统", "架构",
            "complex", "difficult", "challenge", "multi-step", "system", "architecture"
        ]
        
        # 中复杂度关键词
        medium_complexity_keywords = [
            "代码", "编程", "开发", "算法", "数学", "逻辑", "推理",
            "code", "program", "develop", "algorithm", "math", "logic", "reasoning"
        ]
        
        # 低复杂度关键词
        low_complexity_keywords = [
            "简单", "快速", "基础", "直接", "查询", "信息",
            "simple", "quick", "basic", "direct", "query", "information"
        ]
        
        score = 5  # 基础分
        
        # 增加高复杂度关键词分数
        for keyword in high_complexity_keywords:
            if keyword in task.lower():
                score += 2
        
        # 增加中复杂度关键词分数
        for keyword in medium_complexity_keywords:
            if keyword in task.lower():
                score += 1
        
        # 降低低复杂度关键词分数
        for keyword in low_complexity_keywords:
            if keyword in task.lower():
                score -= 1
        
        # 检查任务长度（长度越长，复杂度可能越高）
        if len(task) > 500:
            score += 1
        elif len(task) > 1000:
            score += 2
        
        # 根据语义数据调整复杂度分数
        if semantic_data:
            # 语义方差越大，复杂度可能越高
            semantic_variance = semantic_data.get("semantic_variance", 0.0)
            if semantic_variance > 0.1:
                score += 1
            elif semantic_variance > 0.2:
                score += 2
        
        # 确保分数在 1-10 范围内
        return max(1, min(10, score))
    
    @staticmethod
    def _calculate_innovation(task: str, semantic_data: Dict[str, Any] = None) -> int:
        """计算创新程度分数 [1-5]"""
        # 高创新关键词
        high_innovation_keywords = [
            "创新", "创意", "新", "独特", "原创", "发明", "设计",
            "innovative", "creative", "new", "unique", "original", "invent", "design"
        ]
        
        # 中创新关键词
        medium_innovation_keywords = [
            "改进", "优化", "提升", "增强",
            "improve", "optimize", "enhance", "upgrade"
        ]
        
        score = 3  # 基础分
        
        # 增加高创新关键词分数
        for keyword in high_innovation_keywords:
            if keyword in task.lower():
                score += 1
        
        # 增加中创新关键词分数
        for keyword in medium_innovation_keywords:
            if keyword in task.lower():
                score += 0.5
        
        # 根据语义数据调整创新分数
        if semantic_data:
            # 语义方差越大，创新度可能越高
            semantic_variance = semantic_data.get("semantic_variance", 0.0)
            if semantic_variance > 0.1:
                score += 0.5
            elif semantic_variance > 0.2:
                score += 1
        
        # 确保分数在 1-5 范围内
        return max(1, min(5, int(score)))
    
    @staticmethod
    def _determine_route_level(value: int, complexity: int, innovation: int) -> int:
        """根据分数确定路由级别"""
        # L7 (巅峰博弈): V>8, C>6, I>3
        if value > 8 and complexity > 6 and innovation > 3:
            return 7
        # L6 (创意融合): V>8, C<=6, I>3
        elif value > 8 and complexity <= 6 and innovation > 3:
            return 6
        # L5 (逻辑深钻): V>8, C>6, I<=3
        elif value > 8 and complexity > 6 and innovation <= 3:
            return 5
        # L4 (复杂执行): V<=8, C>6
        elif value <= 8 and complexity > 6:
            return 4
        # L3 (高价单发): V>8, C<=5, I<=3
        elif value > 8 and complexity <= 5 and innovation <= 3:
            return 3
        # L2 (标准代理): V<=8, C<=5, I<=3
        elif value <= 8 and complexity <= 5 and innovation <= 3:
            return 2
        # L1 (本地吞吐): V<4, C<3
        elif value < 4 and complexity < 3:
            return 1
        # 默认到 L2
        else:
            return 2
    
    @staticmethod
    def _get_route_name(route_level: int) -> str:
        """获取路由级别名称"""
        route_names = {
            1: "本地吞吐",
            2: "标准代理",
            3: "高价单发",
            4: "复杂执行",
            5: "逻辑深钻",
            6: "创意融合",
            7: "巅峰博弈"
        }
        return route_names.get(route_level, "标准代理")
