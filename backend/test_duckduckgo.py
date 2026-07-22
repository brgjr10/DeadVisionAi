import asyncio
import json
import httpx

async def test_duckduckgo_directly():
    """Test DuckDuckGo API directly to see what it returns for time queries"""
    query = "current time in japan"
    url = "https://api.duckduckgo.com/"
    
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
    }
    
    print(f"Testing DuckDuckGo API with query: {query}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            print(f"Raw response keys: {list(data.keys())}")
            print(f"AbstractText: {repr(data.get('AbstractText'))}")
            print(f"Abstract: {repr(data.get('Abstract'))}")
            print(f"Heading: {repr(data.get('Heading'))}")
            print(f"RelatedTopics count: {len(data.get('RelatedTopics', []))}")
            
            # Show first few related topics
            for i, topic in enumerate(data.get('RelatedTopics', [])[:3]):
                if isinstance(topic, dict):
                    print(f"  RelatedTopic {i}: {topic.get('Text', '')[:100]}...")
                else:
                    print(f"  RelatedTopic {i}: {str(topic)[:100]}...")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_duckduckgo_directly())