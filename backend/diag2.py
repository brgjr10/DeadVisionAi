import asyncio, httpx, json, time, subprocess, sys, os

os.chdir(r'F:\DeadVisionAi\backend')

# Kill stale
subprocess.run([sys.executable, '-c',
    'import os; [os.kill(int(p),9) for p in os.popen("tasklist /FI "
    '"'"'IMAGENAME eq python.exe'"'"' /FO CSV /NH").read().splitlines() if p]'],
    capture_output=True)
import time; time.sleep(1)

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--port', '8000', '--log-level', 'debug'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8', errors='replace',
    bufsize=1,
)

# Wait up to 45 s for ready
for i in range(45):
    try:
        r = httpx.get('http://127.0.0.1:8000/api/v1/health', timeout=1)
        if r.status_code == 200:
            print('Ready at %ds' % (i+1))
            break
    except: pass
    time.sleep(1)
else:
    proc.kill(); print('STARTUP TIMEOUT'); sys.exit(1)

# Hit /chat — wait up to 30 s for reply
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
out = proc.stdout.read()

print('HTTP %d  (%.0f ms)' % (resp.status_code, dt))
print('intent      :', d['classification']['intent'])
print('rec_tools   :', d['classification']['recommended_tools'])
print('tools_used  :', d['classification']['tools_used'])
tc = [t.get('name','!') for t in d.get('tool_calls',[])]
print('tool_calls  :', tc)
print()
print('--- MARKERS ---')
for line in out.splitlines():
    ll = line.lower()
    if '***' in ll or 'classifier' in ll or 'router_before' in ll or 'router_tool' in ll:
        print(' ', line.strip()[:200])

ok = bool(d['classification']['tools_used'] or tc)
print('\n==> %s' % ('PASS' if ok else 'FAIL'))
