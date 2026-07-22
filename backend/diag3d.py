"""diag3d: threaded stdout, post-classifier logic, fast start-up. 90s timeout."""
import asyncio, httpx, json, time, subprocess, sys, os, threading

os.chdir(r'F:\DeadVisionAi\backend')
sys.path.insert(0, r'F:\DeadVisionAi\backend')

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--port', '8000', '--log-level', 'warning'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8',
)

buffs = []
def reader():
    for chunk in proc.stdout:
        buffs.append(chunk)
threading.Thread(target=reader, daemon=True).start()

for i in range(45):
    try:
        r = httpx.get('http://127.0.0.1:8000/api/v1/health', timeout=1)
        if r.status_code == 200:
            break
    except:
        pass
    time.sleep(1)
else:
    proc.kill(); print('TIMEOUT'); sys.exit(1)

t0 = time.perf_counter()
resp = httpx.post(
    'http://127.0.0.1:8000/chat',
    json={'message': 'what is the newest car honda has released?'},
    timeout=35,
)
dt = (time.perf_counter() - t0) * 1000
time.sleep(0.5)
proc.kill()

out = ''.join(buffs)
# Extract ONLY our injected print markers
markers = [l for l in out.splitlines() if '***' in l]
for m in markers:
    print(m.strip())

d = resp.json()
cls = d.get('classification', {})
tools_used = cls.get('tools_used') or []
tc = [t.get('name','!') for t in d.get('tool_calls',[])]

print()
print('HTTP %d  (%.0f ms)' % (resp.status_code, dt))
print('intent:      ', cls.get('intent'))
print('rec_tools:   ', cls.get('recommended_tools'))
print('tools_used:  ', tools_used)
print('tool_calls:  ', tc)

ok = bool(tools_used or tc)
print()
print('==> %s' % ('PASS  web_search was called' if ok else 'FAIL  web_search was NOT called'))
