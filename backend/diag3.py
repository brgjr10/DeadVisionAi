"""diag3-no-kill: threaded stdout reader."""
import asyncio, httpx, json, time, subprocess, sys, os, threading

os.chdir(r'F:\DeadVisionAi\backend')

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--port', '8000', '--log-level', 'info'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8',
)

server_lines = []
def read_out():
    for line in proc.stdout:
        server_lines.append(line)
threading.Thread(target=read_out, daemon=True).start()

for i in range(45):
    try:
        if httpx.get('http://127.0.0.1:8000/api/v1/health', timeout=1).status_code == 200:
            print('Ready at %ds' % (i+1)); break
    except: pass
    time.sleep(1)
else:
    proc.kill(); print('TIMEOUT'); sys.exit(1)

print('Calling /chat ...')
t0 = time.perf_counter()
resp = httpx.post(
    'http://127.0.0.1:8000/chat',
    json={'message': 'what is the newest car honda has released?'},
    timeout=35,
)
dt = (time.perf_counter() - t0) * 1000
d = resp.json()
time.sleep(0.5)
proc.kill()

print()
print('HTTP %d  (%.0f ms)' % (resp.status_code, dt))
print('intent     :', d['classification']['intent'])
print('rec_tools  :', d['classification']['recommended_tools'])
print('tools_used :', d['classification']['tools_used'])
tc = [t.get('name','!') for t in d.get('tool_calls',[])]
print('tool_calls :', tc)
print()
print('--- MARKERS ---')
for line in server_lines:
    low = line.lower()
    if 'classifier' in low or 'router_before' in low or 'router_tool' in low:
        print(' |', line.strip()[:200])

ok = bool(d['classification']['tools_used'] or tc)
print('\n==>', 'PASS' if ok else 'FAIL')
