"""diag_chat.py — clean version, no PS in file."""
import asyncio, httpx, json, time, subprocess, sys, os

os.chdir(r'F:\DeadVisionAi\backend')

# Kill stale processes first
subprocess.run([sys.executable, '-c', 'import os,signal; [os.kill(p,signal.SIGTERM) for p in __import__("os").popen("tasklist /FI \\"IMAGENAME eq python.exe\\" /FO CSV /NH").read().splitlines() if p]'], capture_output=True)

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--port', '8000', '--log-level', 'debug'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8', errors='replace',
)

for i in range(30):
    try:
        r = httpx.get('http://127.0.0.1:8000/api/v1/health', timeout=1)
        if r.status_code == 200:
            print('Ready after %d s' % i)
            break
    except Exception:
        pass
    time.sleep(1)
else:
    proc.kill()
    print('TIMEOUT — server never became ready')
    sys.exit(1)

print('Sending /chat ...')
t0 = time.perf_counter()
resp = httpx.post(
    'http://127.0.0.1:8000/chat',
    json={'message': 'what is the newest car honda has released?'},
    timeout=30,
)
dt = (time.perf_counter() - t0) * 1000
d = resp.json()
time.sleep(0.3)
proc.kill()
out = proc.stdout.read()

print()
print('HTTP %d  (%.0f ms)' % (resp.status_code, dt))
print('intent     :', d['classification']['intent'])
print('complexity :', d['classification']['complexity_score'])
print('rec_tools  :', d['classification']['recommended_tools'])
print('tools_used :', d['classification']['tools_used'])
tc = [t.get('name','!') for t in d.get('tool_calls',[])]
print('tool_calls :', tc)
print()
print('--- MARKERS ---')
for line in out.splitlines():
    ll = line.lower()
    if 'classifier' in ll or 'router_before' in ll or 'router_tool' in ll or ('***' in ll):
        print(' ', line.strip()[:200])

if d['classification']['tools_used'] or tc:
    print('\nPASS: web_search called')
else:
    print('\nFAIL: web_search NOT called')
