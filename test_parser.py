#!/usr/bin/env python3
# 测试 JSON 解析工具

from src.utils.parser import extract_json, extract_json_array, extract_steps, parse_plan, clean_text

def test_extract_json():
    print("=== 测试 extract_json ===")
    
    # 测试带 Markdown 代码块的 JSON
    test1 = '```json\n{"key": "value", "number": 123}\n```'
    result1 = extract_json(test1)
    print(f"输入: {test1[:30]}...")
    print(f"输出: {result1}")
    assert result1 == {"key": "value", "number": 123}, "测试1失败"
    
    # 测试直接的 JSON
    test2 = '{"name": "test", "data": [1, 2, 3]}'
    result2 = extract_json(test2)
    print(f"输入: {test2}")
    print(f"输出: {result2}")
    assert result2 == {"name": "test", "data": [1, 2, 3]}, "测试2失败"
    
    # 测试解析失败的情况
    test3 = "这不是有效的 JSON"
    result3 = extract_json(test3)
    print(f"输入: {test3}")
    print(f"输出: {result3}")
    assert "error" in result3, "测试3失败"
    
    print("extract_json 测试通过!\n")

def test_extract_json_array():
    print("=== 测试 extract_json_array ===")
    
    # 测试带 Markdown 代码块的数组
    test1 = '```json\n["a", "b", "c"]\n```'
    result1 = extract_json_array(test1)
    print(f"输入: {test1}")
    print(f"输出: {result1}")
    assert result1 == ["a", "b", "c"], "测试1失败"
    
    # 测试直接的数组
    test2 = '[1, 2, 3, 4, 5]'
    result2 = extract_json_array(test2)
    print(f"输入: {test2}")
    print(f"输出: {result2}")
    assert result2 == [1, 2, 3, 4, 5], "测试2失败"
    
    print("extract_json_array 测试通过!\n")

def test_extract_steps():
    print("=== 测试 extract_steps ===")
    
    # 测试数字编号列表
    test1 = "1. 分析问题\n2. 制定计划\n3. 执行任务\n4. 总结结果"
    result1 = extract_steps(test1)
    print(f"输入: {test1}")
    print(f"输出: {result1}")
    assert result1 == ["分析问题", "制定计划", "执行任务", "总结结果"], "测试1失败"
    
    # 测试 JSON 数组格式
    test2 = '["步骤1", "步骤2", "步骤3"]'
    result2 = extract_steps(test2)
    print(f"输入: {test2}")
    print(f"输出: {result2}")
    assert result2 == ["步骤1", "步骤2", "步骤3"], "测试2失败"
    
    print("extract_steps 测试通过!\n")

def test_parse_plan():
    print("=== 测试 parse_plan ===")
    
    test1 = '{"steps": ["分析问题", "执行解决", "总结结果"]}'
    result1 = parse_plan(test1)
    print(f"输入: {test1}")
    print(f"输出: {result1}")
    assert result1 == {"steps": ["分析问题", "执行解决", "总结结果"]}, "测试1失败"
    
    test2 = "1. 第一步\n2. 第二步\n3. 第三步"
    result2 = parse_plan(test2)
    print(f"输入: {test2}")
    print(f"输出: {result2}")
    assert result2 == {"steps": ["第一步", "第二步", "第三步"]}, "测试2失败"
    
    print("parse_plan 测试通过!\n")

def test_clean_text():
    print("=== 测试 clean_text ===")
    
    test1 = '```json\n{"key": "value"}\n```'
    result1 = clean_text(test1)
    print(f"输入: {test1}")
    print(f"输出: {result1}")
    assert result1 == '{"key": "value"}', "测试1失败"
    
    print("clean_text 测试通过!\n")

if __name__ == "__main__":
    test_extract_json()
    test_extract_json_array()
    test_extract_steps()
    test_parse_plan()
    test_clean_text()
    print("="*50)
    print("所有 JSON 解析工具测试通过!")
    print("="*50)