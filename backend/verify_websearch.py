"""One-shot: start server → hit /chat → report tool status → stop server."""
import subprocess, time, httpx, json, os, signal, sys

os.chdir(r"F:\DeadVisionAi\backend")

# Start server
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000", "--log-level", "error"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"Server PID {proc.pid} — waiting for ready…")
for _ in range(30):
    try:
        r = httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1)
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(1)
else:
    proc.terminate()
    print("TIMEOUT — server never became ready")
    sys.exit(1)

print("Ready — sending Mazda question…")
t0 = time.perf_counter()
resp = httpx.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "what is the newest car mazda has released?"},
    timeout=30,
)
dt = (time.perf_counter() - t0) * 1000
d = resp.json()
print(f"\nHTTP {resp.status_code}  ({dt:.0f} ms)")
print(f"  intent       = {d['classification']['intent']}")
print(f"  tools_used   = {d['classification']['tools_used']}")
print(f"  tool_calls   = {[t['name'] for t in d.get('tool_calls', [])]}")
print(f"  model_used   = {d.get('model_used')}")
print(f"  provider     = {d.get('provider')}")
if d["classification"]["tools_used"]:
    print("\n✅ WEB SEARCH WAS CALLED")
else:
    print("\n❌ WEB SEARCH WAS NOT CALLED — bug still present")

proc.terminate()
proc.wait(timeout=5)
