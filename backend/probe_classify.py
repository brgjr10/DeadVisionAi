"""Direct router probe — add debug log lines to classify path before restarts."""
import asyncio, sys, os, json
sys.path.insert(0, r"F:\DeadVisionAi\backend")
os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:1234"

# Patch ProbeChat — log everything
import logging
logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")

# Direct unit test of the path that's broken
from app.routing.classifier import TaskClassifier
import time

async def main():
    tc = TaskClassifier()
    t0 = time.perf_counter()
    cls = await tc.classify("what is the newest car honda has released?", context=[])
    dt = (time.perf_counter() - t0) * 1000
    print(f"\nclassify result ({dt:.0f} ms):")
    print(f"  intent   = {cls.intent}")
    print(f"  complexity = {cls.complexity_score}")
    print(f"  recommended_tools = {cls.recommended_tools}")
    print(f"  confidence = {cls.confidence}")

asyncio.run(main())
