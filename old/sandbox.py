import ast
import asyncio

class ASTSandbox:
    async def execute_code(self, plan_code: str) -> str:
        try:
            # 1. 拦截高危操作 (import os 等)
            tree = ast.parse(plan_code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return "[Sandbox] Error: 禁止引入外部模块！"
            
            # 2. 安全编译与局部执行
            compiled = compile(tree, "<ast>", "exec")
            safe_locals = {}
            
            def _run():
                exec(compiled, {"__builtins__": {}}, safe_locals)
                return safe_locals.get("result", "执行成功，但未返回结果变量 'result'")

            # 3. 异步防止死锁，超时时间 5 秒
            return str(await asyncio.wait_for(asyncio.to_thread(_run), timeout=5.0))
        except Exception as e:
            return f"[Sandbox] Execution Failed: {str(e)}"