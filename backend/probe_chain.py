"""Probe all parts of the chain with direct Python calls, no server."""
import asyncio, httpx, json, sys, os

sys.path.insert(0, r"F:\DeadVisionAi\backend")
os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:1234"

# Clear any stale caches
for k in list(sys.modules.keys()):
    if "app" in k:
        del sys.modules[k]

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import importlib, logging
logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")

from app.routing.classifier import get_task_classifier
from app.tools.registry import get_tool_registry
from app.tools.web_search import WebSearchTool
from app.utils.routing_helper import local_classify

async def main():
    tc = get_task_classifier()

    # 1. Is web_search registered?
    reg = get_tool_registry()
    print("REGISTRY KEYS:", list(reg._tools.keys()))
    print("web_search in registry:", "web_search" in reg._tools)

    # 2. direct local_classify check
    lc = await local_classify("what is the newest car honda has released?")
    print("local_classify result:", lc)

    # 3. full classify
    cls = await tc.classify("what is the newest car honda has released?", context=[])
    print("classify result:")
    print("  intent           :", cls.intent)
    print("  recommended_tools:", cls.recommended_tools)
    print("  complexity       :", cls.complexity_score)
    print("  confidence       :", cls.confidence)

    # 4. If web_search in recommended_tools, call it directly
    if "web_search" in cls.recommended_tools:
        tool = reg._tools["web_search"]
        result = await tool.execute({"query": "what is the newest car honda has released?", "max_results": 3})
        print("web_search result:", result.success, str(result.result)[:200] if result.result else "None")
    else:
        print("web_search NOT in recommended_tools — checking keyword detection…")
        lower = "what is the newest car honda has released?".lower()
        signs = {"newest","new ","latest","recent","just released","released","launched","announced","debuted","introduced","unveiled","coming out","coming soon","upcoming","this year","this month","current model","latest model","current version","new model","just came out","is out","is available"}
        matched = [kw for kw in signs if kw in lower]
        print("keyword matches:", matched)

asyncio.run(main())
