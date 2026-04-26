# register_nodes.py - Redis API节点注册脚本
# 运行方式: python register_nodes.py

import asyncio
import redis.asyncio as redis

async def register_api_nodes():
    r = redis.from_url('redis://localhost:6379/0', decode_responses=True)

    # 1. 清空旧的节点池
    await r.delete("ActivePool:Logic", "ActivePool:Coding", "ActivePool:Search", "ActivePool:Creative", "ActivePool:Fast")

    # 2. 注册 API 节点
    # 注意：node_id 必须与数据库 api_assets 表的 id 一致！
    #
    # 根据 init_database.py，我们插入了以下记录：
    # id=1: Logic, gpt-4o-mini
    # id=2: Coding, gpt-4o-mini
    # id=3: Fast, gpt-4o-mini

    # 注册 Logic 节点 (id=1)
    await r.hset("ActivePool:Logic", "1", "60")   # 60 RPM

    # 注册 Coding 节点 (id=2)
    await r.hset("ActivePool:Coding", "2", "60")  # 60 RPM

    # 注册 Fast 节点 (id=3)
    await r.hset("ActivePool:Fast", "3", "120")    # 120 RPM

    print("=== API 节点注册完成 ===")
    print("\n当前注册的节点池：")

    # 打印所有节点池
    domains = ["Logic", "Coding", "Search", "Creative", "Fast"]
    for domain in domains:
        nodes = await r.hgetall(f"ActivePool:{domain}")
        if nodes:
            print(f"\n[{domain}]")
            for node_id, rpm in nodes.items():
                print(f"  - 节点ID={node_id}: {rpm} RPM")
        else:
            print(f"\n[{domain}] - 无节点")

    await r.aclose()
    print("\n节点注册完成！")

if __name__ == "__main__":
    asyncio.run(register_api_nodes())
