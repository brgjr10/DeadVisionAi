import asyncio
from app.utils.routing_helper import local_classify

async def test_local_classify_detailed():
    result = await local_classify("what time is it in japan?")
    print(f"Local classifier raw result: {result}")
    print(f"Category: {result.get('category')}")
    print(f"Reason: {result.get('reason')}")

if __name__ == "__main__":
    asyncio.run(test_local_classify_detailed())