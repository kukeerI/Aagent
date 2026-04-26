import os
import time
import random
import asyncio
from openai import AsyncOpenAI, RateLimitError
import redis.asyncio as redis
from src.schemas import GatewayRequest
from src.database import AsyncSessionLocal, APIAsset

LUA_RATE_LIMIT = """
local rpm_key = KEYS[1]
local max_rpm = tonumber(ARGV[1])
local current_rpm = tonumber(redis.call('GET', rpm_key) or "0")
if current_rpm + 1 > max_rpm then return 0 end
redis.call('INCR', rpm_key)
redis.call('EXPIRE', rpm_key, 65)
return 1
"""

_redis_pool = None
_redis_lock = asyncio.Lock()

async def get_redis_pool(redis_url: str = "redis://localhost:6379/0"):
    """获取 Redis 连接池单例"""
    global _redis_pool
    if _redis_pool is None:
        async with _redis_lock:
            if _redis_pool is None:
                _redis_pool = redis.from_url(redis_url, decode_responses=True)
    return _redis_pool

async def close_redis_pool():
    """关闭 Redis 连接池"""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None

class GatewayError(Exception):
    """网关错误基类"""
    pass

class NetworkError(GatewayError):
    """网络错误"""
    pass

class RateLimitExceededError(GatewayError):
    """速率限制错误"""
    pass

class NoAvailableNodesError(GatewayError):
    """无可用节点错误"""
    pass

class AsyncGateway:
    def __init__(self, redis_url: str = "redis://localhost:6379/0", trace_id: str = None):
        self.redis_url = redis_url
        self.r = None
        self.lua_script = None
        self.trace_id = trace_id

    async def connect(self):
        """获取 Redis 连接（单例模式）"""
        if not self.r:
            try:
                self.r = await get_redis_pool(self.redis_url)
                self.lua_script = self.r.register_script(LUA_RATE_LIMIT)
            except Exception as e:
                raise NetworkError(f"Redis 连接失败: {e}")

    async def close(self):
        """安全释放 Redis 连接（单例模式不关闭全局连接）"""
        pass

    async def get_best_node(self, domain_skill: str):
        try:
            await self.connect()

            nodes = await self.r.hgetall(f"ActivePool:{domain_skill}")
            if not nodes:
                raise NoAvailableNodesError(f"没有可用的 {domain_skill} 节点")

            candidates, weights = [], []
            now_min = int(time.time() / 60)

            for node_id, rpm_limit in nodes.items():
                used_rpm = int(await self.r.get(f"Used:RPM:{node_id}:{now_min}") or 0)
                rpm_score = max(0, (int(rpm_limit) - used_rpm) / int(rpm_limit))

                if rpm_score > 0.1:
                    candidates.append({"id": node_id, "limit": rpm_limit})
                    weights.append(rpm_score * 100)

            if not candidates:
                raise NoAvailableNodesError(f"所有 {domain_skill} 节点都达到速率限制")

            selected = random.choices(candidates, weights=weights, k=1)[0]
            allowed = await self.lua_script(keys=[f"Used:RPM:{selected['id']}:{now_min}"], args=[selected['limit']])
            if allowed != 1:
                raise RateLimitExceededError(f"节点 {selected['id']} 速率限制")
            return selected['id']
        except GatewayError:
            raise
        except Exception as e:
            raise NetworkError(f"获取节点失败: {e}")

    async def chat_completion(self, request: GatewayRequest) -> str:
        """执行聊天完成，返回结果或抛出详细错误"""
        for attempt in range(3):
            try:
                node_id = await self.get_best_node(request.domain_skill)

                async with AsyncSessionLocal() as session:
                    asset = await session.get(APIAsset, int(node_id))
                    if not asset:
                        continue

                    client = AsyncOpenAI(
                        api_key=os.getenv(asset.api_key),
                        base_url=asset.provider_url
                    )

                    try:
                        resp = await client.chat.completions.create(
                            model=asset.model_name,
                            messages=[m.model_dump() for m in request.messages],
                            timeout=60
                        )
                        return resp.choices[0].message.content
                    except RateLimitError as e:
                        if self.r:
                            await self.r.hdel(f"ActivePool:{request.domain_skill}", node_id)
                        raise RateLimitExceededError(f"API 速率限制: {e}")
                    except Exception as e:
                        if "connection" in str(e).lower() or "timeout" in str(e).lower():
                            raise NetworkError(f"网络连接失败: {e}")
                        raise GatewayError(f"API 调用失败: {e}")
            except GatewayError:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)
                continue
            except Exception as e:
                if attempt == 2:
                    raise NetworkError(f"未知错误: {e}")
                await asyncio.sleep(1)
                continue
        raise NoAvailableNodesError("所有尝试都失败")