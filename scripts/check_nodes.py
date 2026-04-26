# check_nodes.py - 检查 Redis 节点池
import asyncio
import redis.asyncio as redis

async def check():
    r = redis.from_url('redis://localhost:6379/0', decode_responses=True)

    print("=== Redis 节点池状态 ===\n")

    domains = ["Logic", "Coding", "Search", "Creative", "Fast"]
    for domain in domains:
        nodes = await r.hgetall(f"ActivePool:{domain}")
        if nodes:
            print(f"[{domain}]")
            for node_id, rpm in nodes.items():
                print(f"  - 节点 {node_id}: {rpm} RPM")
        else:
            print(f"[{domain}] - 无节点")

    await r.aclose()

asyncio.run(check())
