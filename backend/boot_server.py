"""One-shot: start server, hit /chat, kill server, report tool status."""
# boot_server.py
import subprocess, time, httpx, json, os, signal, sys

os.chdir(r"F:\DeadVisionAi\backend")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000", "--log-level", "debug"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Wait for ready
for i in range(30):
    try:
        r = httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1)
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(1)
else:
    proc.kill()
    print("TIMEOUT: server never became ready")
    sys.exit(1)

print(f"Server up (PID {proc.pid}). Sending chat request...")

t0 = time.perf_counter()
try:
    resp = httpx.post(
        "http://127.0.0.1:8000/chat",
        json={"message": "what is the newest car honda has released?"},
        timeout=30,
    )
except Exception as e:
    proc.kill()
    print(f"Request error: {e}")
    sys.exit(1)

dt = (time.perf_counter() - t0) * 1000
d = resp.json()

print(f"\nHTTP {resp.status_code}  ({dt:.0f} ms)")
print(f"  intent       : {d['classification']['intent']}")
print(f"  tools_used   : {d['classification']['tools_used']}")
print(f"  tool_calls   : {[t.get('name','?') for t in d.get('tool_calls',[])]}")
print(f"  model_used   : {d.get('model_used')}")
print(f"  provider     : {d.get('provider')}")
print()

if d["classification"]["tools_used"] or d.get("tool_calls"):
    print("PASS: web_search WAS called")
else:
    print("FAIL: web_search WAS NOT called")

proc.kill()
proc.wait(timeout=5)
print("Server shut down.")
