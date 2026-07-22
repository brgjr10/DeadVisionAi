"""diag3b — warning log level, threaded reader, 45s ready wait."""
import httpx, json, time, subprocess, sys, os, threading

os.chdir(r'F:\DeadVisionAi\backend')

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--port', '8000', '--log-level', 'warning'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding='utf-8',
)

server_lines = []
def read_out():
    for line in proc.stdout:
        server_lines.append(line)
t = threading.Thread(target=read_out, daemon=True)
t.start()

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

t0 = time.perf_counter()
resp = httpx.post(
    'http://127.0.0.1:8000/chat',
    json={'message': 'what is the newest car honda has released?'},
    timeout=35,
)
dt = (time.perf_counter() - t0) * 1000
d = resp.json()
time.sleep(0.3)
proc.kill()

print('HTTP %d  (%.0f ms)' % (resp.status_code, dt))
print('intent     :', d['classification']['intent'])
print('rec_tools  :', d['classification']['recommended_tools'])
print('tools_used :', d['classification']['tools_used'])
tc = [t.get('name','!') for t in d.get('tool_calls',[])]
print('tool_calls :', tc)
print()
print('--- ALL MARKERS ---')
for line in server_lines:
    low = line.lower()
    if 'router_class' in low or 'router_before' in low or 'router_fallback' in low or 'router_tool' in low or '***' in low or 'CLASSIFIER' in low:
        print(' |', line.rstrip()[:250])

ok = bool(d['classification']['tools_used'] or tc)
print('\n==>', 'PASS  tools_used' if ok else 'FAIL: tools_used=[] and tool_calls=[]')
print('Full classification:', d['classification'])
