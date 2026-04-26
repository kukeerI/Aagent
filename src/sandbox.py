import ast
import asyncio

class ASTSandbox:
    async def execute_code(self, code_str: str) -> str:
        try:
            # 清理大模型可能带有的 Markdown 标记
            code_str = code_str.replace("```python", "").replace("```", "").strip()
            
            # 1. 拦截危险操作
            tree = ast.parse(code_str)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # 生产环境可设置白名单，此处演示直接拦截
                    return "[Sandbox Error] 安全拦截：禁止在沙箱内 Import 外部模块。"

            # 2. 安全编译
            compiled = compile(tree, "<ast>", "exec")
            safe_locals = {}

            def _run():
                exec(compiled, {"__builtins__": {}}, safe_locals)
                return safe_locals.get("result", "代码执行成功 (无 result 变量返回)")

            # 3. 异步包裹防死锁 (超时限制 5 秒)
            res = await asyncio.wait_for(asyncio.to_thread(_run), timeout=5.0)
            return str(res)

        except SyntaxError as e:
            return f"[Sandbox Error] 语法错误: {e}"
        except Exception as e:
            return f"[Sandbox Error] 运行时异常: {e}"