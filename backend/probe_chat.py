"""Trigger /chat and print full response."""
import httpx, json, time

t0 = time.perf_counter()
r = httpx.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "what is the newest car mazda has released?"},
    timeout=30,
)
dt = (time.perf_counter() - t0) * 1000
print(f"HTTP {r.status_code}  ({dt:.0f} ms)")
print(json.dumps(r.json(), indent=2))
