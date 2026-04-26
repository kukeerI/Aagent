# gateway_manager.py
import redis
import random
import time
import os
from openai import OpenAI, RateLimitError, APIError
from db_infrastructure import SessionLocal, APIAsset, ErrorLog
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class IntelligentGateway:
    def __init__(self):
        """
        初始化：连接本地 Redis 并准备路由映射
        """
        # 默认连接本地 Redis 6379 端口
        self.r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # 不同平台的 API Base URL 映射（AIStudio 强制使用 v1beta 路径）
        self.base_urls = {
            "AIStudio": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "Groq": "https://api.groq.com/openai/v1",
            "Cerebras": "https://api.cerebras.ai/v1",
            "SambaNova": "https://api.sambanova.ai/v1",
            "OpenRouter": "https://openrouter.ai/api/v1"
        }

    def sync_to_redis(self):
        """
        同步：将数据库中所有 ACTIVE 状态的 Key 搬运到 Redis 活跃池
        """
        session = SessionLocal()
        try:
            # 清空 Redis 中的旧活跃池数据
            for key in self.r.keys("ActivePool:*"):
                self.r.delete(key)

            assets = session.query(APIAsset).filter_by(status="ACTIVE").all()
            count = 0
            for asset in assets:
                # 检查环境变量中是否真的配置了该 Key
                if os.getenv(asset.api_key):
                    # 存入哈希表：ActivePool:领域 -> 资产ID: RPM限制
                    self.r.hset(f"ActivePool:{asset.domain_skill}", asset.id, asset.rpm_limit)
                    # 记录 TPM 限制到单独的键中
                    self.r.set(f"Limit:TPM:{asset.id}", asset.tpm_limit)
                    count += 1
            
            print(f"💡 Redis 活跃池同步完成，已加载 {count} 个可用节点。")
        finally:
            session.close()

    def get_best_node(self, skill_domain):
        """
        调度：基于加权轮询算法选出当前负载最低的节点
        """
        pool_key = f"ActivePool:{skill_domain}"
        nodes = self.r.hgetall(pool_key)
        
        if not nodes:
            return None

        candidates = []
        weights = []

        for node_id, rpm_limit in nodes.items():
            # 获取当前分钟的消耗数据
            now_min = int(time.time() / 60)
            used_rpm = int(self.r.get(f"Used:RPM:{node_id}:{now_min}") or 0)
            used_tpm = int(self.r.get(f"Used:TPM:{node_id}:{now_min}") or 0)
            
            tpm_limit = int(self.r.get(f"Limit:TPM:{node_id}") or 1)

            # 计算健康得分 (0.0 - 1.0)
            rpm_score = max(0, (int(rpm_limit) - used_rpm) / int(rpm_limit))
            tpm_score = max(0, (tpm_limit - used_tpm) / tpm_limit)
            
            # 综合权重
            final_weight = rpm_score * tpm_score * 100
            
            if final_weight > 0.1: # 节点仍有余力
                candidates.append(node_id)
                weights.append(final_weight)

        if not candidates:
            return None

        # 加权随机选择节点
        return random.choices(candidates, weights=weights, k=1)[0]

    def update_usage(self, node_id, tokens_count):
        """
        更新：请求成功后记录消耗情况
        """
        now_min = int(time.time() / 60)
        # RPM 计数
        self.r.incr(f"Used:RPM:{node_id}:{now_min}")
        self.r.expire(f"Used:RPM:{node_id}:{now_min}", 65) # 略长于一分钟
        
        # TPM 计数
        self.r.incrby(f"Used:TPM:{node_id}:{now_min}", tokens_count)
        self.r.expire(f"Used:TPM:{node_id}:{now_min}", 65)

    def chat_completion(self, messages, domain_skill="Logic"):
        """
        执行：统一的 API 请求入口，带自动熔断重试逻辑
        """
        for attempt in range(3): # 对不同节点进行重试
            node_id = self.get_best_node(domain_skill)
            if not node_id:
                break

            session = SessionLocal()
            asset = session.query(APIAsset).get(node_id)
            
            # 获取 API Key 和对应平台的 Base URL
            api_key = os.getenv(asset.api_key)
            base_url = self.base_urls.get(asset.provider, "")
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            try:
                print(f"📡 [网关分发] 目标: {asset.provider} | 模型: {asset.model_name}")
                
                resp = client.chat.completions.create(
                    model=asset.model_name,
                    messages=messages,
                    timeout=60
                )
                
                # 记录成功消耗
                self.update_usage(node_id, resp.usage.total_tokens)
                session.close()
                return resp.choices[0].message.content

            except RateLimitError:
                print(f"⚠️ [熔断] {asset.provider} 达到限制 (429)，从活跃池剔除...")
                # 仅从 Redis 移除，不修改数据库，等重置后再同步
                self.r.hdel(f"ActivePool:{domain_skill}", node_id)
                session.close()
                continue
                
            except Exception as e:
                err_str = str(e)
                print(f"❌ [异常] {asset.provider} 报错: {err_str}")
                
                # 针对 ID 错误 (404) 或 Key 错误 (401) 进行永久封禁处理
                if any(x in err_str for x in ["404", "401", "model_not_found", "invalid_request_error"]):
                    print(f"🚫 [封禁] 节点 {asset.model_name} 信息有误，标记为 BANNED。")
                    self.r.hdel(f"ActivePool:{domain_skill}", node_id)
                    asset.status = "BANNED"
                    session.commit()
                
                session.close()
                continue
                
        raise Exception(f"🚨 算力池耗尽：{domain_skill} 领域的可用节点全部失效。")