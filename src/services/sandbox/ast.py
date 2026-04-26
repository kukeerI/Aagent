# src/services/sandbox/ast.py
# AST 沙箱 - 语法级安全隔离

import ast
import asyncio
from typing import Optional

from src.config import config

class ASTSandbox:
    def __init__(self):
        self.banned_imports = config.BANNED_IMPORTS
        print("[Sandbox] AST 沙箱初始化成功")

    async def execute_code(self, code: str, timeout: int = 10) -> str:
        try:
            # 解析代码
            tree = ast.parse(code)
            
            # 检查安全
            self._check_security(tree)
            
            # 执行代码
            result = await asyncio.wait_for(
                self._execute_safely(code),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return "[Sandbox Error] 执行超时"
        except Exception as e:
            return f"[Sandbox Error] {str(e)}"

    def _check_security(self, tree: ast.AST):
        """检查代码安全性"""
        for node in ast.walk(tree):
            # 检查导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.banned_imports:
                        raise Exception(f"安全拦截：禁止导入 {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in self.banned_imports:
                    raise Exception(f"安全拦截：禁止从 {node.module} 导入")
            # 检查危险操作
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['__import__', 'eval', 'exec', 'compile']:
                        raise Exception("安全拦截：禁止使用危险函数")
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                        raise Exception("安全拦截：禁止使用危险函数")

    async def _execute_safely(self, code: str) -> str:
        """安全执行代码"""
        # 创建安全的全局环境
        safe_globals = {
            '__builtins__': {
                'print': print,
                'range': range,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'abs': abs,
                'max': max,
                'min': min,
                'sum': sum,
                'sorted': sorted,
                'reversed': reversed,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'round': round,
                'pow': pow,
                'divmod': divmod,
                'all': all,
                'any': any,
                'chr': chr,
                'ord': ord,
                'hex': hex,
                'bin': bin,
                'oct': oct,
                'repr': repr,
                'str': str,
                'type': type,
                'isinstance': isinstance,
                'issubclass': issubclass,
                'hasattr': hasattr,
                'getattr': getattr,
                'setattr': setattr,
                'delattr': delattr,
                'dir': dir,
                'vars': vars,
                'help': help,
                'id': id,
                'hash': hash,
                'bool': bool,
                'float': float,
                'int': int,
                'complex': complex,
                'list': list,
                'tuple': tuple,
                'set': set,
                'dict': dict,
                'frozenset': frozenset,
                'slice': slice,
                'type': type,
                'object': object,
                'Ellipsis': Ellipsis,
                'NotImplemented': NotImplemented,
                'None': None,
            }
        }
        
        # 执行代码
        local_vars = {}
        exec(code, safe_globals, local_vars)
        
        # 返回结果
        if 'result' in local_vars:
            return str(local_vars['result'])
        return "执行完成"

    def __del__(self):
        pass