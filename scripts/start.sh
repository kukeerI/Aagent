#!/bin/bash
# scripts/start.sh - 启动 Aagent 服务

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Aagent 企业级智能体框架${NC}"
echo -e "${GREEN}=====================================${NC}"

# 检查 Docker
if command -v docker &> /dev/null; then
    echo -e "${YELLOW}检测到 Docker，正在启动监控服务...${NC}"
    docker-compose up -d
    echo -e "${GREEN}监控服务已启动！${NC}"
    echo "  - Jaeger UI: http://localhost:16686"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
else
    echo -e "${YELLOW}未检测到 Docker，跳过监控服务启动${NC}"
fi

# 启动 API 服务
echo -e "${YELLOW}正在启动 Aagent API 服务...${NC}"
cd "$(dirname "$0")/.." || exit
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload