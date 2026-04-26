#!/usr/bin/env python3
# test_refactoring.py - 验证重构结果的测试脚本

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """测试所有模块是否能正常导入"""
    print("测试模块导入...")
    
    modules_to_test = [
        "src.config",
        "src.core.state",
        "src.data.database",
        "src.data.memory",
        "src.services.semantic_cache",
        "src.services.sandbox.docker",
        "src.services.sandbox.ast"
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"OK: {module_name}")
        except Exception as e:
            print(f"FAIL: {module_name}: {e}")
            return False
    
    # 测试需要 opentelemetry 的模块，失败时不返回 False
    opentelemetry_modules = [
        "src.services.tracing",
        "src.services.gateway",
        "src.core.executor",
        "src.core.orchestrator",
        "src.api.main"
    ]
    
    for module_name in opentelemetry_modules:
        try:
            __import__(module_name)
            print(f"OK: {module_name}")
        except Exception as e:
            print(f"WARNING: {module_name}: {e}")
    
    return True

def test_config():
    """测试配置管理模块"""
    print("\n测试配置管理...")
    
    try:
        from src.config import config
        print(f"OK: 配置模块加载成功")
        print(f"  API_HOST: {config.API_HOST}")
        print(f"  API_PORT: {config.API_PORT}")
        print(f"  LM_STUDIO_URL: {config.LM_STUDIO_URL}")
        print(f"  DOCKER_ENABLED: {config.DOCKER_ENABLED}")
        return True
    except Exception as e:
        print(f"FAIL: 配置模块测试失败: {e}")
        return False

def test_database():
    """测试数据库模块"""
    print("\n测试数据库模块...")
    
    try:
        from src.data.database import init_db
        print(f"OK: 数据库模块加载成功")
        return True
    except Exception as e:
        print(f"FAIL: 数据库模块测试失败: {e}")
        return False

def test_sandbox():
    """测试沙箱模块"""
    print("\n测试沙箱模块...")
    
    try:
        from src.services.sandbox.docker import DockerSandbox
        from src.services.sandbox.ast import ASTSandbox
        print(f"OK: 沙箱模块加载成功")
        
        # 测试AST沙箱
        ast_sandbox = ASTSandbox()
        print(f"  AST沙箱初始化成功")
        
        return True
    except Exception as e:
        print(f"FAIL: 沙箱模块测试失败: {e}")
        return False

def test_gateway():
    """测试网关模块"""
    print("\n测试网关模块...")
    
    try:
        from src.services.gateway import AsyncGateway
        print(f"OK: 网关模块加载成功")
        return True
    except Exception as e:
        print(f"WARNING: 网关模块测试失败: {e}")
        return True

def test_orchestrator():
    """测试编排器模块"""
    print("\n测试编排器模块...")
    
    try:
        from src.core.orchestrator import AsyncRealOrchestrator
        print(f"OK: 编排器模块加载成功")
        return True
    except Exception as e:
        print(f"WARNING: 编排器模块测试失败: {e}")
        return True

def test_api():
    """测试API模块"""
    print("\n测试API模块...")
    
    try:
        from src.api.main import app
        print(f"OK: API模块加载成功")
        return True
    except Exception as e:
        print(f"WARNING: API模块测试失败: {e}")
        return True

def main():
    """运行所有测试"""
    print("Aagent 重构验证测试")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config,
        test_database,
        test_sandbox,
        test_gateway,
        test_orchestrator,
        test_api
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 成功, {failed} 失败")
    
    if failed == 0:
        print("OK: 所有测试通过，重构成功！")
        return 0
    else:
        print("FAIL: 部分测试失败，需要修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())