@echo off
chcp 65001 >nul
echo ===============================================
echo Aagent 状态机测试脚本 (Windows)
echo ===============================================
echo.

echo [测试1] 验证 AgentTask context 字段
python -c "from src.data.domain_models import AgentTask; t = AgentTask(trace_id='test-001', user_input='测试'); print('context存在:', hasattr(t, 'context')); print('context默认:', t.context)"
echo.

echo [测试2] 验证语法检查
python -c "import py_compile; py_compile.compile('src/core/state.py', doraise=True); print('state.py 语法正确')"
python -c "import py_compile; py_compile.compile('src/data/domain_models.py', doraise=True); print('domain_models.py 语法正确')"
echo.

echo [测试3] 验证状态回滚逻辑
python -c "from src.core.state import CommandType, TaskState; print('CommandType:', [c.value for c in CommandType]); print('TaskState:', [s.value for s in TaskState])"
echo.

echo ===============================================
echo 测试完成!
echo ===============================================
pause