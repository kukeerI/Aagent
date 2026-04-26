# src/services/llmops/langfuse.py
# Langfuse集成

import os
from typing import Optional, Dict, Any, List

from src.config import config

# 尝试导入Langfuse，如果失败则使用模拟实现
Langfuse = None
OpenAI = None
try:
    from langfuse import Langfuse
    from langfuse.openai import OpenAI
except ImportError:
    print("[Langfuse] 库未安装，将使用模拟实现")
    Langfuse = None
    OpenAI = None

class LangfuseIntegration:
    """Langfuse集成"""
    def __init__(self):
        self.langfuse = None
        self._setup()

    def _setup(self):
        """设置Langfuse"""
        try:
            if Langfuse:
                public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
                secret_key = os.getenv("LANGFUSE_SECRET_KEY")
                host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

                if public_key and secret_key:
                    self.langfuse = Langfuse(
                        public_key=public_key,
                        secret_key=secret_key,
                        host=host
                    )
                    print("[Langfuse] 初始化成功")
                else:
                    print("[Langfuse] 未配置环境变量，跳过初始化")
            else:
                print("[Langfuse] 库未安装，跳过初始化")
        except Exception as e:
            print(f"[Langfuse] 初始化失败: {e}")

    def get_openai_client(self):
        """获取OpenAI客户端"""
        if self.langfuse and OpenAI:
            return OpenAI()
        return None

    def trace_prompt(self, prompt_name: str, prompt_version: str, input_text: str, output_text: str, metadata: Optional[Dict[str, Any]] = None):
        """追踪Prompt"""
        if not self.langfuse:
            return

        try:
            trace = self.langfuse.trace(name=prompt_name, metadata=metadata)
            generation = trace.generation(
                name=prompt_name,
                model="unknown",  # 可以根据实际情况设置
                input=input_text,
                output=output_text,
                metadata={
                    "version": prompt_version,
                    **(metadata or {})
                }
            )
            generation.end()
            trace.end()
        except Exception as e:
            print(f"[Langfuse] 追踪失败: {e}")

    def create_prompt(self, name: str, content: str, version: str = "1.0.0"):
        """创建Prompt"""
        if not self.langfuse:
            return

        try:
            self.langfuse.create_prompt(
                name=name,
                prompt=content,
                version=version
            )
            print(f"[Langfuse] Prompt创建成功: {name} v{version}")
        except Exception as e:
            print(f"[Langfuse] Prompt创建失败: {e}")

    def get_prompt(self, name: str, version: Optional[str] = None):
        """获取Prompt"""
        if not self.langfuse:
            return None

        try:
            prompt = self.langfuse.get_prompt(name, version)
            return prompt
        except Exception as e:
            print(f"[Langfuse] 获取Prompt失败: {e}")
            return None

    def list_prompts(self) -> List[str]:
        """列出所有Prompt"""
        if not self.langfuse:
            return []

        try:
            prompts = self.langfuse.list_prompts()
            return [prompt.name for prompt in prompts]
        except Exception as e:
            print(f"[Langfuse] 列出Prompt失败: {e}")
            return []

    def start_observation(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """开始观察"""
        if not self.langfuse:
            return None

        try:
            observation = self.langfuse.observation(name=name, metadata=metadata)
            return observation
        except Exception as e:
            print(f"[Langfuse] 开始观察失败: {e}")
            return None

langfuse_integration = LangfuseIntegration()