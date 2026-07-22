import asyncio
from app.utils.routing_helper import local_classify

async def test_local_classify():
    result = await local_classify("what time is it in japan?")
    print(f"Local classifier result: {result}")

if __name__ == "__main__":
    asyncio.run(test_local_classify())