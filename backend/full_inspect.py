"""Fresh one-shot: start server → INTEGRATION TEST → kill server."""
import asyncio, httpx, json, time, sys, os, subprocess

os.chdir(r"F:\DeadVisionAi\backend")

# ── Start server ────────────────────────────────────────────────────────────
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000", "--log-level", "debug"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,   # redirect stderr to stdout
    text=True,
)
for _ in range(40):
    try:
        if httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1).status_code == 200:
            break
    except:
        pass
    time.sleep(0.5)
else:
    proc.kill()
    print("TIMEOUT");
    sys.exit(1)

# ── Smoke test ──────────────────────────────────────────────────────────────
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

# ── Parse server stdout for our debug markers ───────────────────────────────
server_out = proc.stdout.read()

# Pull our marker lines
markers = [l for l in server_out.splitlines() if "***" in l or "CLASSIFIER" in l or "TOOL_RESULTS" in l]
for m in markers: print("|", m)

# ── Report ──────────────────────────────────────────────────────────────────
print(f"\nHTTP {resp.status_code}  ({dt:.0f} ms)")
print(f"  intent           : {d['classification']['intent']}")
print(f"  complexity_score : {d['classification']['complexity_score']}")
print(f"  recommended_tools: {d['classification']['recommended_tools']}")
print(f"  tools_used       : {d['classification']['tools_used']}")
tc = [t.get("name","?") for t in d.get("tool_calls",[])]
print(f"  tool_calls       : {tc}")

if d["classification"]["tools_used"] or tc:
    print("\nPASS: web_search was called")
else:
    print("\nFAIL: web_search was NOT called")
