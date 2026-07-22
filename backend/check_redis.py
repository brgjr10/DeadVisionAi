"""Check Redis keys for classifier cache state."""
import asyncio, redis.asyncio as aioredis

async def main():
    c = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
    for p in ["clf_cache:*", "rdocl:version_lock", "rdocl:schema_lock"]:
        r = await c.scan(match=p, count=200)
        if r[1]:
            for k in r[1]:
                v = await c.get(k)
                t = await c.ttl(k)
                print(f"{k}: {str(v)[:100]}  ttl={t}s")
        else:
            print(f"{p}: (empty)")
    await c.aclose()

asyncio.run(main())
