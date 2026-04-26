# start_openai_shim.py
# 启动 OpenAI 兼容接口

import uvicorn
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 60)
    print("启动 Aagent OpenAI 兼容接口")
    print("=" * 60)
    print("\n接口地址: http://localhost:8001")
    print("文档地址: http://localhost:8001/docs")
    print("\nOpen Interpreter 配置示例:")
    print("  interpreter.llm.api_base = 'http://localhost:8001/v1'")
    print("  interpreter.llm.model = 'auto'")
    print("\n按 Ctrl+C 停止服务")
    print("=" * 60)

    uvicorn.run(
        "src.api.openai_shim:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
