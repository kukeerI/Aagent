# gateway_manager.py
import os
import time
import random
import asyncio
from dotenv import load_dotenv
import redis.asyncio as redis  # 【改动1】使用异步 Redis
from openai import AsyncOpenAI, RateLimitError, APIError # 【改动2】使用异步 OpenAI SDK
from sqlalchemy.future import select
from db_infrastructure import AsyncSessionLocal, APIAsset  # 需确保 DB 层已改为异步引擎

# 加载环境变量
load_dotenv()

# 【改动3】引入 Lua 脚本，将“查配额 -> 拦截 -> 扣减”打包成绝对安全的原子操作
LUA_RATE_LIMIT = """
local rpm_key = KEYS[1]
local tpm_key = KEYS[2]
local max_rpm = tonumber(ARGV[1])
local max_tpm = tonumber(ARGV[2])
local req_tpm = tonumber(ARGV[3])

local current_rpm = tonumber(redis.call('GET', rpm_key) or "0")
local current_tpm = tonumber(redis.call('GET', tpm_key) or "0")

-- 如果超限，立刻拒绝 (返回 0)
if (current_rpm + 1 > max_rpm) or (current_tpm + req_tpm > max_tpm) then
    return 0
end

-- 如果通过，立刻扣减并刷新过期时间 (返回 1)
redis.call('INCR', rpm_key)
redis.call('INCRBY', tpm_key, req_tpm)
redis.call('EXPIRE', rpm_key, 65)
redis.call('EXPIRE', tpm_key, 65)

return 1
"""

class AsyncIntelligentGateway:
    def __init__(self):
        """
        初始化：连接异步 Redis 并准备路由映射
        """
        self.r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # 预编译 Lua 脚本提高性能
        self._lua_rate_limit = self.r.register_script(LUA_RATE_LIMIT)
        
        self.base_urls = {
            "AIStudio": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "Groq": "https://api.groq.com/openai/v1",
            "Cerebras": "https://api.cerebras.ai/v1",
            "SambaNova": "https://api.sambanova.ai/v1",
            "OpenRouter": "https://openrouter.ai/api/v1"
        }

    async def sync_to_redis(self):
        """
        同步：异步搬运数据库资产到 Redis
        """
        async with AsyncSessionLocal() as session:
            # 异步清空旧数据
            keys = await self.r.keys("ActivePool:*")
            if keys:
                await self.r.delete(*keys)

            stmt = select(APIAsset).where(APIAsset.status == "ACTIVE")
            result = await session.execute(stmt)
            assets = result.scalars().all()
            
            count = 0
            for asset in assets:
                if os.getenv(asset.api_key):
                    await self.r.hset(f"ActivePool:{asset.domain_skill}", asset.id, asset.rpm_limit)
                    await self.r.set(f"Limit:TPM:{asset.id}", asset.tpm_limit)
                    count += 1
            
            print(f"💡 [Async] Redis 活跃池同步完成，已加载 {count} 个可用节点。")

    async def get_best_node(self, skill_domain, req_tpm=1000):
        """
        调度：加权轮询 + Lua 原子并发锁
        """
        pool_key = f"ActivePool:{skill_domain}"
        nodes = await self.r.hgetall(pool_key)
        
        if not nodes:
            return None

        candidates = []
        weights = []
        now_min = int(time.time() / 60)

        for node_id, rpm_limit in nodes.items():
            used_rpm = int(await self.r.get(f"Used:RPM:{node_id}:{now_min}") or 0)
            used_tpm = int(await self.r.get(f"Used:TPM:{node_id}:{now_min}") or 0)
            tpm_limit = int(await self.r.get(f"Limit:TPM:{node_id}") or 1)

            rpm_score = max(0, (int(rpm_limit) - used_rpm) / int(rpm_limit))
            tpm_score = max(0, (tpm_limit - used_tpm) / tpm_limit)
            final_weight = rpm_score * tpm_score * 100
            
            if final_weight > 0.1:
                candidates.append({"id": node_id, "rpm_limit": rpm_limit, "tpm_limit": tpm_limit})
                weights.append(final_weight)

        if not candidates:
            return None

        # 加权随机选择
        selected = random.choices(candidates, weights=weights, k=1)[0]
        node_id = selected["id"]
        
        # 【核心拦截】执行 Lua 脚本进行原子操作验证
        rpm_key = f"Used:RPM:{node_id}:{now_min}"
        tpm_key = f"Used:TPM:{node_id}:{now_min}"
        
        allowed = await self._lua_rate_limit(
            keys=[rpm_key, tpm_key],
            args=[selected["rpm_limit"], selected["tpm_limit"], req_tpm]
        )
        
        # allowed == 1 代表抢占配额成功，0 代表瞬间被其他协程抢空了
        if allowed == 1:
            return node_id
        return None 

    async def chat_completion(self, messages, domain_skill="Logic"):
        """
        执行：全异步 API 请求入口与熔断隔离
        """
        for attempt in range(3):
            node_id = await self.get_best_node(domain_skill)
            if not node_id:
                await asyncio.sleep(1) # 没抢到节点，退避 1 秒重试
                continue

            async with AsyncSessionLocal() as session:
                asset = await session.get(APIAsset, int(node_id))
                if not asset:
                    continue

                api_key = os.getenv(asset.api_key)
                base_url = self.base_urls.get(asset.provider, "")
                
                # 【改动4】使用异步客户端，解放 CPU
                client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                
                try:
                    print(f"📡 [网关分发] 目标: {asset.provider} | 模型: {asset.model_name}")
                    
                    resp = await client.chat.completions.create(
                        model=asset.model_name,
                        messages=messages,
                        timeout=60
                    )
                    
                    # 此时配额已经在 get_best_node 中被 Lua 原子预扣除了
                    # 不需要再调用容易引发超卖的同步 update_usage 方法
                    return resp.choices[0].message.content

                except RateLimitError:
                    print(f"⚠️ [熔断] {asset.provider} 达到限制 (429)，从活跃池剔除...")
                    await self.r.hdel(f"ActivePool:{domain_skill}", node_id)
                    continue
                    
                except Exception as e:
                    err_str = str(e).lower()
                    print(f"❌ [异常] {asset.provider} 报错: {err_str}")
                    
                    if any(x in err_str for x in ["404", "401", "not_found", "invalid_api_key"]):
                        print(f"🚫 [封禁] 节点 {asset.model_name} 鉴权失败，永久 BANNED。")
                        await self.r.hdel(f"ActivePool:{domain_skill}", node_id)
                        asset.status = "BANNED"
                        await session.commit()
                    continue
                    
        raise Exception(f"🚨 算力池耗尽：{domain_skill} 领域的可用节点全部失效或正忙。")