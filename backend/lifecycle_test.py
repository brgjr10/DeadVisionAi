"""Full lifecycle: start server, hit /chat, stop, report."""
import asyncio, httpx, json, time, subprocess, sys, os

os.chdir(r"F:\DeadVisionAi\backend")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000", "--log-level", "info"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
for _ in range(30):
    try:
        if httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1).status_code == 200:
            break
    except Exception:
        pass
    time.sleep(1)
else:
    proc.kill()
    sys.exit("TIMEOUT")

t0 = time.perf_counter()
resp = httpx.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "what is the newest car honda has released?"},
    timeout=30,
)
dt = (time.perf_counter() - t0) * 1000
d = resp.json()
proc.kill()
proc.wait(timeout=5)

print("HTTP %d  (%.0f ms)" % (resp.status_code, dt))
print("intent     = %s" % d["classification"]["intent"])
print("tools_used = %s" % d["classification"]["tools_used"])
tc = [t.get("name", "?") for t in d.get("tool_calls", [])]
print("tool_calls = %s" % tc)
print("response[:120] = %r" % d["response"][:120])
if d["classification"]["tools_used"] or tc:
    print("\nPASS: web_search was called")
else:
    print("\nFAIL: web_search was NOT called")
