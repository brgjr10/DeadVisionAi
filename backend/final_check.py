"""Fresh backpack: full router instrumentation (prints) to catch tool calls."""
import asyncio, httpx, json, time, sys, os, subprocess

os.chdir(r"F:\DeadVisionAi\backend")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000", "--log-level", "error"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
for _ in range(30):
    try:
        if httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1).status_code == 200:
            break
    except:
        pass
    time.sleep(1)
else:
    proc.kill()
    sys.exit("TIMEOUT")

# Inline: what does the /chat handler see for tools?
HAVE_TOOLS = httpx.get("http://127.0.0.1:8000/tools", timeout=5).json()["tools"]
print("Registered tools:")
for t in HAVE_TOOLS:
    print(f"  {t['tool_id']:30s}  {t['category']}")

t0 = time.perf_counter()
resp = httpx.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "what is the newest car honda has released?"},
    timeout=30,
)
dt = (time.perf_counter() - t0) * 1000
d = resp.json()
proc.kill()
proc.wait(5)

print("\nResponse summary:")
print(f"  HTTP {resp.status_code}  ({dt:.0f} ms)")
print(f"  intent       : {d['classification']['intent']}")
print(f"  tools_used   : {d['classification']['tools_used']}")
tc = [t.get("name","?") for t in d.get("tool_calls",[])]
print(f"  tool_calls   : {tc}")
print(f"  response[:200]: {d['response'][:200]!r}")
if d["classification"]["tools_used"] or tc:
    print("\n==> PASS")
else:
    print("\n==> FAIL: tools_used is empty")
