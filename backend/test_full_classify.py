import asyncio
import json
from app.routing.classifier import get_task_classifier

async def test_full_classification():
    """Test the full classifier flow"""
    classifier = get_task_classifier()
    result = await classifier.classify("what time is it in japan?", [])
    print(f"Full classification result:")
    print(f"  Intent: {result.intent}")
    print(f"  Complexity: {result.complexity_score}")
    print(f"  Estimated tokens: {result.estimated_tokens}")
    print(f"  Recommended tools: {result.recommended_tools}")
    print(f"  Tool only: {result.tool_only_flag}")
    print(f"  Confidence: {result.confidence}")

if __name__ == "__main__":
    asyncio.run(test_full_classification())