import asyncio
from app.routing.classifier import get_task_classifier

async def test_classifier():
    classifier = get_task_classifier()
    # Test with a simple question
    result = await classifier.classify("What is the capital of France?", [])
    print(f"Intent: {result.intent}")
    print(f"Complexity: {result.complexity_score}")
    print(f"Estimated tokens: {result.estimated_tokens}")
    print(f"Recommended tools: {result.recommended_tools}")
    print(f"Tool only: {result.tool_only_flag}")
    print(f"Confidence: {result.confidence}")

if __name__ == "__main__":
    asyncio.run(test_classifier())