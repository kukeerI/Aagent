# examples/openinterpreter_integration.py
# Open Interpreter 与 Aagent 集成示例
# 用作 Windows 桌面 AI 小助手

import asyncio
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreter import interpreter

from src.services.gateway import AsyncGateway
from src.services.semantic_cache import SemanticCache
from src.config import config

class AagentOpenAIAdapter:
    """Aagent OpenAI 适配器 - 让 Open Interpreter 可以直接使用 Aagent 网关"""

    def __init__(self):
        self.gateway = AsyncGateway()
        self.semantic_cache = SemanticCache()

    async def complete(self, messages, temperature=0.7, max_tokens=None):
        """
        兼容 Open Interpreter 的 complete 方法

        Args:
            messages: 消息列表，格式为 [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            响应对象，包含 choices 列表
        """
        try:
            # 获取最佳节点
            node = await self.gateway.get_best_node("Desktop_Assistant")
            if not node:
                # 使用本地模型
                response_text = await self.gateway._try_local_model(messages)
            else:
                # 尝试请求
                try:
                    response_text = await self.gateway._make_request(node, messages)
                except Exception as e:
                    print(f"[AagentAdapter] 请求失败，尝试本地模型: {e}")
                    response_text = await self.gateway._try_local_model(messages)

            # 清理 [本地模型] 标记
            if response_text.startswith("[本地模型]"):
                response_text = response_text[7:].strip()

            # 构建兼容 Open Interpreter 的响应格式
            return type('Response', (), {
                'choices': [
                    type('Choice', (), {
                        'message': type('Message', (), {
                            'content': response_text,
                            'role': 'assistant'
                        })(),
                        'finish_reason': 'stop',
                        'index': 0
                    })()
                ],
                'usage': type('Usage', (), {
                    'prompt_tokens': sum(len(msg['content']) // 4 for msg in messages),
                    'completion_tokens': len(response_text) // 4,
                    'total_tokens': sum(len(msg['content']) // 4 for msg in messages) + len(response_text) // 4
                })()
            })()

        except Exception as e:
            print(f"[AagentAdapter] 错误: {e}")
            # 返回错误响应
            return type('Response', (), {
                'choices': [
                    type('Choice', (), {
                        'message': type('Message', (), {
                            'content': f"抱歉，发生了错误: {str(e)}",
                            'role': 'assistant'
                        })(),
                        'finish_reason': 'stop',
                        'index': 0
                    })()
                ]
            })()

    async def chat(self, message, context=None):
        """
        简单的聊天接口

        Args:
            message: 用户消息
            context: 上下文消息列表

        Returns:
            AI 响应文本
        """
        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})

        response = await self.complete(messages)
        return response.choices[0].message.content


class AagentDesktopAssistant:
    """Aagent 桌面助手 - 基于 Open Interpreter 和 Aagent"""

    def __init__(self):
        self.adapter = AagentOpenAIAdapter()
        self.setup_interpreter()

    def setup_interpreter(self):
        """配置 Open Interpreter"""
        # 设置 Open Interpreter 使用 Aagent 作为后端
        interpreter.llm.model = "auto"
        interpreter.llm.temperature = 0.7
        interpreter.llm.max_tokens = 2000

        # 使用自定义适配器
        interpreter.llm.completions = self.adapter.complete

        # 禁用自动运行，由 Aagent Checker 审核
        interpreter.auto_run = False

        # 禁止危险操作
        interpreter.os = False  # 禁用操作系统级命令
        interpreter.safe_mode = "ask"  # 安全模式询问

        # 本地模式配置
        interpreter.local = True  # 优先使用本地模型
        interpreter.model = "local-model"

    async def chat(self, message: str) -> str:
        """
        处理用户消息

        Args:
            message: 用户输入的消息

        Returns:
            AI 响应
        """
        try:
            # 使用 Aagent 适配器处理
            response = await self.adapter.chat(message)
            return response
        except Exception as e:
            print(f"[DesktopAssistant] 错误: {e}")
            return f"抱歉，发生了错误: {str(e)}"

    async def run_code(self, code: str) -> str:
        """
        执行代码（通过 Open Interpreter）

        Args:
            code: 要执行的代码

        Returns:
            执行结果
        """
        try:
            # 通过 Open Interpreter 执行代码
            result = await interpreter.instantiate_completion(code)
            return result
        except Exception as e:
            return f"代码执行错误: {str(e)}"

    async def desktop_task(self, task: str) -> str:
        """
        执行桌面任务（如操作文件、文件夹等）

        Args:
            task: 任务描述

        Returns:
            任务执行结果
        """
        try:
            # 先通过 AI 理解任务
            response = await self.chat(task)

            # 如果需要执行代码
            if "```" in response:
                # 提取代码
                code_blocks = response.split("```")[1::2]
                for code in code_blocks:
                    language = code.split("\n")[0].strip() if code.startswith("python") else ""
                    actual_code = "\n".join(code.split("\n")[1:]) if language else code

                    # 通过沙箱执行代码
                    result = await self.run_code(actual_code)
                    response += f"\n\n执行结果:\n{result}"

            return response
        except Exception as e:
            return f"任务执行错误: {str(e)}"


async def main():
    """主函数 - 演示如何使用桌面助手"""
    print("=" * 60)
    print("Aagent 桌面 AI 小助手")
    print("=" * 60)

    assistant = AagentDesktopAssistant()

    # 演示对话
    tasks = [
        "帮我整理一下桌面上的文件",
        "计算一下 1 到 100 的累加和",
        "帮我写一个排序算法",
    ]

    for task in tasks:
        print(f"\n用户: {task}")
        print("-" * 40)
        response = await assistant.desktop_task(task)
        print(f"AI: {response}")
        print("-" * 40)

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
