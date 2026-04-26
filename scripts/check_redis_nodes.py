# check_redis_nodes.py - 检查Redis中的节点
import asyncio
import redis.asyncio as redis

async def check():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    domains = ['Fast', 'Logic', 'Coding']

    for domain in domains:
        nodes = await r.hgetall(f'ActivePool:{domain}')
        print(f'\nDomain: {domain}')
        print('-' * 50)
        if not nodes:
            print('  No nodes registered')
        else:
            for node_id, rpm_limit in nodes.items():
                used_key = f'Used:RPM:{node_id}:*'
                # Check if the key pattern exists
                keys = await r.keys(used_key)
                if keys:
                    used_value = await r.get(keys[0])
                    print(f'  {node_id}: RPM limit={rpm_limit}, Used={used_value}')
                else:
                    print(f'  {node_id}: RPM limit={rpm_limit}, No usage data')

    await r.close()

asyncio.run(check())
