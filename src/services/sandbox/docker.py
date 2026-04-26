# src/services/sandbox/docker.py
# Docker 沙箱 - 容器级安全隔离

import docker
import time
import uuid
from typing import Optional

from src.config import config

class DockerSandbox:
    def __init__(self):
        self.use_docker = config.DOCKER_ENABLED
        try:
            if self.use_docker:
                self.client = docker.from_env()
                print("[Sandbox] Docker 初始化成功")
            else:
                raise Exception("Docker 已被禁用")
        except Exception as e:
            print(f"[Sandbox] Docker 初始化失败: {e}")
            print("[Sandbox] 将回退到 AST 沙箱模式")
            from src.services.sandbox.ast import ASTSandbox
            self.fallback_sandbox = ASTSandbox()
            self.use_docker = False

    async def execute_code(self, code: str, timeout: int = 10) -> str:
        if not self.use_docker:
            return await self.fallback_sandbox.execute_code(code)

        container_name = f"aagent-sandbox-{uuid.uuid4()}"
        try:
            # 创建容器
            container = self.client.containers.run(
                "python:3.10-slim",
                name=container_name,
                command=["python3", "-c", code],
                detach=True,
                mem_limit=config.SANDBOX_MEMORY_LIMIT,
                network_mode="none",
                remove=False
            )

            # 等待执行完成
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    container.reload()
                    if container.status == "exited":
                        break
                    time.sleep(0.1)
                except:
                    break

            # 获取输出
            try:
                output = container.logs(stdout=True, stderr=True, stream=False)
                output = output.decode('utf-8', errors='replace').strip()
            except:
                output = "获取输出失败"

            # 强制停止并删除容器
            try:
                container.stop(timeout=2)
            except:
                pass
            try:
                container.remove(force=True)
            except:
                pass

            return output
        except Exception as e:
            # 清理容器
            try:
                container = self.client.containers.get(container_name)
                container.remove(force=True)
            except:
                pass
            return f"[Sandbox Error] {str(e)}"

    def __del__(self):
        # 清理资源
        pass