import os
import time
import random
import asyncio
from openai import AsyncOpenAI, RateLimitError
import redis.asyncio as redis
from schemas import GatewayRequest
from db_infrastructure import AsyncSessionLocal, APIAsset # 假设已改为异步

LUA_RATE_LIMIT = """
local rpm_key = KEYS[1]
local max_rpm = tonumber(ARGV[1])
local current_rpm = tonumber(redis.call('GET', rpm_key) or "0")
if current_rpm + 1 > max_rpm then return 0 end
redis.call('INCR', rpm_key)
redis.call('EXPIRE', rpm_key, 65)
return 1
"""

class AsyncGateway:
    def __init__(self):
        self.r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.lua_script = self.r.register_script(LUA_RATE_LIMIT)

    async def get_best_node(self, domain_skill: str):
        """加权轮询 + Lua 并发锁"""
        nodes = await self.r.hgetall(f"ActivePool:{domain_skill}")
        if not nodes: return None

        candidates, weights = [], []
        now_min = int(time.time() / 60)

        for node_id, rpm_limit in nodes.items():
            used_rpm = int(await self.r.get(f"Used:RPM:{node_id}:{now_min}") or 0)
            rpm_score = max(0, (int(rpm_limit) - used_rpm) / int(rpm_limit))
            
            if rpm_score > 0.1:
                candidates.append({"id": node_id, "limit": rpm_limit})
                weights.append(rpm_score * 100)

        if not candidates: return None

        selected = random.choices(candidates, weights=weights, k=1)[0]
        # Lua 原子扣减
        allowed = await self.lua_script(keys=[f"Used:RPM:{selected['id']}:{now_min}"], args=[selected['limit']])
        return selected['id'] if allowed == 1 else None

    async def chat_completion(self, request: GatewayRequest) -> str:
        for attempt in range(3):
            node_id = await self.get_best_node(request.domain_skill)
            if not node_id:
                await asyncio.sleep(1) # 退避重试
                continue

            async with AsyncSessionLocal() as session:
                asset = await session.get(APIAsset, int(node_id))
                client = AsyncOpenAI(api_key=os.getenv(asset.api_key), base_url=asset.provider_url)
                
                try:
                    resp = await client.chat.completions.create(
                        model=asset.model_name,
                        messages=[m.model_dump() for m in request.messages],
                        timeout=60
                    )
                    return resp.choices[0].message.content
                except RateLimitError:
                    await self.r.hdel(f"ActivePool:{request.domain_skill}", node_id)
                    continue
                except Exception as e:
                    continue
        raise Exception("网关多次重试均失败，算力池枯竭。")