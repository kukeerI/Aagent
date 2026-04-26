# test_features.py
# 功能测试

import asyncio
import unittest
from unittest.mock import Mock, patch

from src.core.executor import AsyncAgentLegion
from src.core.orchestrator import AsyncRealOrchestrator
from src.core.state import AgentStateMachine
from src.data.memory import Memory
from src.services.gateway import AsyncGateway
from src.services.llmops.langfuse import langfuse_integration

class TestMCP(unittest.IsolatedAsyncioTestCase):
    """测试MCP功能"""

    @patch('src.services.mcp.client.httpx.AsyncClient')
    async def test_mcp_client(self, mock_client):
        """测试MCP客户端"""
        # 模拟MCP服务器响应
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "name": "search",
                "description": "搜索网络",
                "parameters": {
                    "query": "string"
                }
            }
        ]
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value.post.return_value = Mock(
            json=lambda: {"result": "搜索结果"}
        )

        # 创建执行器并初始化
        executor = AsyncAgentLegion(mcp_server_url="http://localhost:8000")
        await executor.initialize()

        # 验证工具发现
        self.assertEqual(len(executor.tools), 1)
        self.assertEqual(executor.tools[0].name, "search")

    async def test_mcp_fallback(self):
        """测试MCP失败时的回退机制"""
        # 创建执行器但不提供MCP服务器URL
        executor = AsyncAgentLegion()
        await executor.initialize()

        # 验证回退到原始执行方式
        result = await executor.execute_task("测试任务", "test")
        self.assertIsInstance(result, str)

class TestStateMachine(unittest.IsolatedAsyncioTestCase):
    """测试状态机功能"""

    async def test_state_machine_run(self):
        """测试状态机运行"""
        # 创建编排器和状态机
        orchestrator = AsyncRealOrchestrator()
        state_machine = AgentStateMachine(orchestrator)

        # 运行状态机
        context = await state_machine.run({
            "user_input": "测试任务",
            "trace_id": orchestrator.trace_id
        })

        # 验证状态机执行完成
        self.assertIn("final_answer", context)

    async def test_checkpoint_creation(self):
        """测试检查点创建"""
        # 创建编排器
        orchestrator = AsyncRealOrchestrator()

        # 运行任务
        result = await orchestrator.start_work("测试任务")

        # 验证任务执行完成
        self.assertIsInstance(result, str)

class TestMemorySystem(unittest.IsolatedAsyncioTestCase):
    """测试记忆系统功能"""

    async def test_memory_add_retrieve(self):
        """测试记忆添加和检索"""
        # 创建记忆系统
        memory = Memory()

        # 添加经验
        await memory.add_experience("测试输入", "测试响应")

        # 检索记忆
        retrieved = await memory.retrieve("测试")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 1)

    async def test_graph_retrieve(self):
        """测试基于图的检索"""
        # 创建记忆系统
        memory = Memory()

        # 添加包含实体的经验
        await memory.add_experience("Python是一种编程语言", "是的，Python是一种广泛使用的编程语言")

        # 基于图检索
        result = await memory.retrieve_with_graph("Python")
        self.assertIsNotNone(result)
        self.assertIn("entities", result)

    async def test_knowledge_graph(self):
        """测试知识图谱"""
        # 创建记忆系统
        memory = Memory()

        # 添加经验
        await memory.add_experience("Google开发了TensorFlow", "是的，Google在2015年开源了TensorFlow")

        # 获取知识图谱
        graph = await memory.get_knowledge_graph()
        self.assertIsNotNone(graph)
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)

class TestLLMOps(unittest.IsolatedAsyncioTestCase):
    """测试LLMOps功能"""

    async def test_prompt_management(self):
        """测试Prompt管理"""
        # 创建网关
        gateway = AsyncGateway()

        # 获取默认Prompt
        default_prompt = gateway.get_prompt()
        self.assertIsInstance(default_prompt, str)

        # 设置新Prompt
        new_prompt = "测试Prompt"
        gateway.set_prompt("test", new_prompt, "1.0.0")

        # 获取新Prompt
        retrieved_prompt = gateway.get_prompt("test")
        self.assertEqual(retrieved_prompt, new_prompt)

    async def test_prompt_listing(self):
        """测试Prompt列表"""
        # 创建网关
        gateway = AsyncGateway()

        # 列出Prompt
        prompts = gateway.list_prompts()
        self.assertIsInstance(prompts, dict)

    async def test_ab_test(self):
        """测试A/B测试"""
        # 创建网关
        gateway = AsyncGateway()

        # 准备测试数据
        variants = ["Prompt 1", "Prompt 2"]
        test_inputs = ["测试输入1", "测试输入2"]

        # 运行A/B测试
        results = await gateway.a_b_test_prompts("test", variants, test_inputs)
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 2)

class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """测试集成功能"""

    async def test_full_workflow(self):
        """测试完整工作流"""
        # 创建编排器
        orchestrator = AsyncRealOrchestrator()

        # 运行任务
        result = await orchestrator.start_work("编写一个简单的Python函数")

        # 验证任务执行完成
        self.assertIsInstance(result, str)
        self.assertIn("Python", result)

if __name__ == "__main__":
    unittest.main()