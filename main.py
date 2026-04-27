# main.py - Aagent Ultimate V1.1 启动入口
import asyncio
from dotenv import load_dotenv
from src.core.orchestrator import AsyncRealOrchestrator

load_dotenv()  # 加载 .env 文件

async def main():
    orchestrator = AsyncRealOrchestrator()
    try:
        await orchestrator.start_work("写一个快排并分析时间复杂度")
    finally:
        # 确保系统退出时，断开 Redis 连接，防止句柄泄漏
        await orchestrator.gateway.close()

if __name__ == "__main__":
    asyncio.run(main())
