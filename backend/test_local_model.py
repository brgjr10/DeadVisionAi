import asyncio
import json
from app.utils.routing_helper import call_local_model

async def test_local_model_direct():
    """Test the local model directly with the classification prompt"""
    system_prompt = """
You are a routing classifier.

Return ONLY valid JSON:

{
  "category": "simple|coding|complex|huge_context",
  "reason": "short reason"
}
"""
    
    prompt = "what time is it in japan?"
    
    print(f"Testing local model with prompt: {prompt}")
    
    try:
        result = await call_local_model(
            prompt=f"{system_prompt}\n\nTask: {prompt}",
            model="qwen2.5-0.5b-instruct"  # Use the classifier model
        )
        print(f"Local model raw response: {repr(result)}")
        
        # Try to parse as JSON
        try:
            # Strip markdown code fences if present
            content = result.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            print(f"After stripping: {repr(content)}")
            parsed = json.loads(content)
            print(f"Parsed JSON: {parsed}")
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Response content: {repr(result)}")
            
    except Exception as e:
        print(f"Error calling local model: {e}")

if __name__ == "__main__":
    asyncio.run(test_local_model_direct())