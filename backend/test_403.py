"""Test if a 403 has hidden Set-Cookie / X-CSRF headers."""
import httpx

BASE = "http://localhost:8888"
q = "honda 2025 car"

r = httpx.get("%s/search?q=%s&format=json" % (BASE, q.replace(" ","+")), timeout=10)
print("HTTP %d" % r.status_code)
if r.status_code == 403:
    print("Headers:")
    for k,v in r.headers.items():
        print("  %s: %s" % (k, v))
    print("Body (first 200):", r.text[:200])
else:
    print("OK! Results:", len(r.json().get("results",[])))
