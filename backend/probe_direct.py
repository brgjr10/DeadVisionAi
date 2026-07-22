"""Direct test: classify real question, call web_search, report all steps."""
import asyncio, httpx, json, sys, os, time

sys.path.insert(0, r"F:\DeadVisionAi\backend")
os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:1234"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# Force fresh imports - drop all app modules
for k in list(sys.modules.keys()):
    if k.startswith("app"):
        del sys.modules[k]

import logging
logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")

from app.routing.classifier import get_task_classifier

async def main():
    tc = get_task_classifier()
    
    print("--- classifying ---")
    cls = await tc.classify("what is the newest car honda has released?", context=[])
    print("intent:", cls.intent)
    print("recommended_tools:", cls.recommended_tools)
    print("complexity:", cls.complexity_score)
    print("confidence:", cls.confidence)
    
    if cls.recommended_tools:
        print("\n--- calling tool ---")
        from app.tools.registry import get_tool_registry
        reg = get_tool_registry()
        for tid in cls.recommended_tools:
            print(f"  tool_id={tid!r}  in_registry={tid in reg._tools}")
            if tid in reg._tools:
                res = await reg.execute_tool(tid, {"query": "what is the newest car honda has released?", "max_results": 3})
                print(f"  result.success={res.success}")
                if res.result:
                    print(f"  result[:200]={str(res.result)[:200]}")
                if res.error:
                    print(f"  result.error={res.error}")
    else:
        print("\nrecommended_tools is EMPTY")

asyncio.run(main())
