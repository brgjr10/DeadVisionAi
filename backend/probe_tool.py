"""Quick sanity — verify web_search class and registry."""
import sys, os
sys.path.insert(0, r"F:\DeadVisionAi\backend")
os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:1234"
for k in list(sys.modules.keys()):
    if k.startswith("app"):
        del sys.modules[k]

from app.tools.web_search import WebSearchTool
from app.tools.registry import get_tool_registry

ws = WebSearchTool()
print("WebSearchTool.tool_id:", ws.tool_id)

reg = get_tool_registry()
print("registry class:", type(reg).__name__)
print("registry tools:", list(reg._tools.keys()))
print("web_search in registry:", "web_search" in reg._tools)
