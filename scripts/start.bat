@echo off
REM scripts\start.bat - 启动 Aagent 服务 (Windows)

echo =====================================
echo   Aagent 企业级智能体框架
echo =====================================

where docker >nul 2>nul
if %errorlevel% equ 0 (
    echo 检测到 Docker，正在启动监控服务...
    docker-compose up -d
    echo 监控服务已启动！
    echo   - Jaeger UI: http://localhost:16686
    echo   - Prometheus: http://localhost:9090
    echo   - Grafana: http://localhost:3000
) else (
    echo 未检测到 Docker，跳过监控服务启动
)

echo 正在启动 Aagent API 服务...
cd /d %~dp0..
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload