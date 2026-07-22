"""diag3c — robust key access, marker dump."""
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
threading.Thread(target=read_out, daemon=True).start()

for i in range(45):
    try:
        if httpx.get('http://127.0.0.1:8000/api/v1/health', timeout=1).status_code == 200:
            break
    except: pass
    time.sleep(1)
else:
    proc.kill(); print('TIMEOUT'); sys.exit(1)

print('Ready. Calling /chat ...')
t0 = time.perf_counter()
resp = httpx.post(
    'http://127.0.0.1:8000/chat',
    json={'message': 'what is the newest car honda has released?'},
    timeout=35,
)
dt = (time.perf_counter() - t0) * 1000
time.sleep(0.5)
proc.kill()

d = resp.json()
print('HTTP %d  (%.0f ms)' % (resp.status_code, dt))
print('top-level keys:', list(d.keys()))

cls = d.get('classification', d)
print('classification keys:', list(cls.keys()))
print('intent         :', cls.get('intent'))
print('recommended_tools:', cls.get('recommended_tools'))
print('tools_used     :', cls.get('tools_used'))
tc = [t.get('name','!') for t in d.get('tool_calls',[])]
print('tool_calls     :', tc)
print('response[:200] :', d.get('response','')[:200])

print()
print('--- ALL LOG LINES WITH PRINT ***---')
for line in server_lines:
    if '***' in line or 'router' in line.lower() or 'Classifier' in line or 'classified' in line.lower():
        print(' |', line.rstrip()[:250])

ok = bool(cls.get('recommended_tools') or cls.get('tools_used') or tc)
print('\n==> %s  (rec_tools=%r tools_used=%r tc=%r)' % (
    'PASS' if ok else 'FAIL',
    cls.get('recommended_tools'), cls.get('tools_used'), tc))
