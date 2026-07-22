"""Test /chat end-to-end like the frontend would."""
import httpx, json

resp = httpx.post(
    "http://localhost:8000/chat",
    json={"message": "what is the newest car mazda has released?"},
    timeout=30,
)
print(f"HTTP {resp.status_code}")
print(json.dumps(resp.json(), indent=2))
