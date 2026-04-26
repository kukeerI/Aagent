# gateway_manager.py
import redis
import random
import time
from db_infrastructure import SessionLocal, APIAsset
from openai import OpenAI, RateLimitError, APIError

class IntelligentGateway:
    def __init__(self):
        # 你的本地 Windows Redis
        self.r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    def chat_completion(self, messages, domain_skill="Logic"):
        for attempt in range(3): # 最多重试 3 次
            node_id = self.get_best_node(domain_skill)
            if not node_id:
                raise Exception(f"灾难！{domain_skill} 领域可用节点已全军覆没！")

            # 去数据库拿真实的配置
            session = SessionLocal()
            asset = session.query(APIAsset).get(node_id)
            
            # 动态读取环境变量里的真实 Key
            import os
            real_api_key = os.getenv(asset.api_key) 
            
            # 兼容各大平台的 Base URL 路由逻辑
            base_url = "https://api.openai.com/v1" # 默认兜底
            if asset.provider == "AIStudio": base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            elif asset.provider == "Groq": base_url = "https://api.groq.com/openai/v1"
            elif asset.provider == "Cerebras": base_url = "https://api.cerebras.ai/v1"
            elif asset.provider == "SambaNova": base_url = "https://api.sambanova.ai/v1"
            elif asset.provider == "OpenRouter": base_url = "https://openrouter.ai/api/v1"

            client = OpenAI(api_key=real_api_key, base_url=base_url)
            
            try:
                print(f"📡 [路由分发] 选中节点: {asset.provider} ({asset.model_name}) | 领域: {domain_skill}")
                response = client.chat.completions.create(
                    model=asset.model_name,
                    messages=messages
                )
                # 成功后，提取真实的 TPM 消耗，更新 Redis
                used_tokens = response.usage.total_tokens
                self.update_usage(node_id, used_tokens)
                session.close()
                return response.choices[0].message.content

            except RateLimitError:
                print(f"⚠️ [熔断剔除] {asset.provider} 返回 429 额度耗尽！从 Redis 池中踢出。")
                self.r.hdel(f"ActivePool:{domain_skill}", node_id)
                session.close()
                continue # 继续循环，找下一个最闲的节点
            except Exception as e:
                print(f"❌ [请求异常] {asset.provider} 报错: {e}")
                session.close()
                continue
                
        raise Exception("多次重试均失败，网关放弃请求。")
    def sync_to_redis(self):
        """将数据库中的 ACTIVE 节点和权重同步到 Redis 活跃池"""
        session = SessionLocal()
        # 清空旧池子
        for key in self.r.keys("ActivePool:*"):
            self.r.delete(key)

        assets = session.query(APIAsset).filter_by(status="ACTIVE").all()
        for asset in assets:
            # 初始权重 = RPM，确保高 RPM 模型分担更多流量
            self.r.hset(f"ActivePool:{asset.domain_skill}", asset.id, asset.rpm_limit)
            # 记录 TPM 限制到 Redis
            self.r.set(f"Limit:TPM:{asset.id}", asset.tpm_limit)
        session.close()
        print("💡 Redis 活跃池已同步，负载均衡权重已就绪。")

    def get_best_node(self, skill_domain):
        """
        Nginx 风格的加权轮询：
        不仅仅是随机，而是根据剩余 RPM/TPM 空间动态调整
        """
        pool_key = f"ActivePool:{skill_domain}"
        nodes = self.r.hgetall(pool_key)
        
        if not nodes:
            return None

        candidates = []
        weights = []

        for node_id, rpm_limit in nodes.items():
            # 1. 检查当前分钟已消耗
            now_min = int(time.time() / 60)
            used_rpm = int(self.r.get(f"Used:RPM:{node_id}:{now_min}") or 0)
            used_tpm = int(self.r.get(f"Used:TPM:{node_id}:{now_min}") or 0)
            
            tpm_limit = int(self.r.get(f"Limit:TPM:{node_id}") or 1)

            # 2. 计算健康得分 (负载越低得分越高)
            rpm_score = max(0, (int(rpm_limit) - used_rpm) / int(rpm_limit))
            tpm_score = max(0, (tpm_limit - used_tpm) / tpm_limit)
            
            # 综合得分作为随机权重
            final_weight = rpm_score * tpm_score * 100
            
            if final_weight > 0.1: # 还有余力
                candidates.append(node_id)
                weights.append(final_weight)

        if not candidates:
            return None

        # 按权重随机点将
        selected_id = random.choices(candidates, weights=weights, k=1)[0]
        return selected_id

    def update_usage(self, node_id, tokens_count):
        """请求完成后，更新 Redis 计数器"""
        now_min = int(time.time() / 60)
        # RPM +1
        self.r.incr(f"Used:RPM:{node_id}:{now_min}")
        self.r.expire(f"Used:RPM:{node_id}:{now_min}", 65) # 自动过期清理
        
        # TPM 增加
        self.r.incrby(f"Used:TPM:{node_id}:{now_min}", tokens_count)
        self.r.expire(f"Used:TPM:{node_id}:{now_min}", 65)