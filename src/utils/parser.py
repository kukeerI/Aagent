# src/utils/parser.py
# JSON 解析工具：应对模型输出杂质的健壮解析器
# 依赖：re, json, typing
# 注意事项：
#   - 处理 LLM 输出的 Markdown 标记、多余文本
#   - 支持多种格式的 JSON 提取
#   - 提供兜底机制防止解析失败

import re
import json
from typing import Any, Optional


def extract_json(text: str) -> dict:
    """提取字符串中第一个合法的 JSON 对象
    
    支持从 Markdown 格式中提取，处理各种边界情况。
    
    Args:
        text: 包含 JSON 的文本
        
    Returns:
        dict: 解析后的 JSON 对象，失败时返回包含 error 的字典
    """
    try:
        # 方法1：尝试匹配 ```json ... ``` 块
        json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # 方法2：尝试匹配直接的 { ... }
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # 方法3：尝试直接解析整个文本
        return json.loads(text)
        
    except Exception as e:
        return {"error": "parse_failed", "raw": text, "exception": str(e)}


def extract_json_array(text: str) -> list:
    """提取字符串中第一个合法的 JSON 数组
    
    Args:
        text: 包含 JSON 数组的文本
        
    Returns:
        list: 解析后的 JSON 数组，失败时返回空列表
    """
    try:
        # 方法1：尝试匹配 ```json ... ``` 块
        json_block_pattern = r'```(?:json)?\s*(\[.*?\])\s*```'
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # 方法2：尝试匹配直接的 [ ... ]
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # 方法3：尝试直接解析整个文本
        result = json.loads(text)
        if isinstance(result, list):
            return result
        
    except Exception:
        pass
    
    return []


def extract_steps(text: str) -> list:
    """从文本中提取步骤列表
    
    支持多种格式：JSON 数组、数字编号列表等。
    
    Args:
        text: 包含步骤的文本
        
    Returns:
        list: 步骤列表
    """
    # 首先尝试 JSON 数组解析
    steps = extract_json_array(text)
    if steps:
        return steps
    
    # 尝试提取引号内的内容
    quoted_items = re.findall(r'"([^"]+)"', text)
    if quoted_items:
        return quoted_items
    
    # 尝试按数字序号分割
    numbered_steps = re.findall(r'\d+[.\uff0e、]([^\n]+)', text)
    if numbered_steps:
        return [s.strip() for s in numbered_steps]
    
    # 简单行分割
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines and len(lines) <= 10:
        return lines
    
    return []


def clean_text(text: str) -> str:
    """清理文本中的多余格式
    
    Args:
        text: 原始文本
        
    Returns:
        str: 清理后的文本
    """
    # 移除 Markdown 代码块标记
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```', '', text)
    
    # 移除首尾空白
    text = text.strip()
    
    return text


def parse_plan(text: str) -> dict:
    """解析计划输出
    
    从模型输出中提取步骤列表，支持多种格式。
    
    Args:
        text: 模型输出的计划文本
        
    Returns:
        dict: 包含 steps 键的字典
    """
    # 尝试解析 JSON
    result = extract_json(text)
    if "steps" in result:
        return result
    
    # 如果没有 steps 键，尝试提取步骤列表
    steps = extract_steps(text)
    if steps:
        return {"steps": steps}
    
    # 兜底：将整个文本作为单步骤
    return {"steps": [text.strip()]}