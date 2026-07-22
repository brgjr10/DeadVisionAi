"""Search adapter: try multiple fallback strategies to get SearXNG working."""
import httpx, json, time

BASE = "http://localhost:8888"

def try_request(url, **kwargs):
    try:
        r = httpx.get(url, timeout=10, **kwargs)
        print("GET %s -> HTTP %d" % (url, r.status_code))
        if r.status_code == 200:
            try:
                j = r.json()
                results = j.get("results", [])
                print("  JSON OK | results=%d | first title=%r" % (
                    len(results), results[0].get("title","")[:80] if results else "NONE"))
                return True
            except:
                print("  JSON parse fail:", r.text[:120])
        else:
            print("  Got HTML body:", r.text[:120])
    except Exception as e:
        print("GET %s -> ERROR: %s" % (url, e))
    return False

# Strategy 1 — GET with all params
print("=== Strategy 1: GET /search with format=json + safesearch=0 ===")
try_request("%s/search?q=honda+2025+car&format=json" % BASE)
print()

# Strategy 2 — POST as x-www-form-urlencoded (matches HTML form)
print("=== Strategy 2: POST /search form-encoded ===")
try:
    r = httpx.post("%s/search" % BASE,
        data={"q": "honda 2025 car", "format": "json"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10)
    print("POST /search -> HTTP %d" % r.status_code)
    if r.status_code == 200:
        j = r.json()
        print("  JSON OK | results=%d" % len(j.get("results",[])))
    else:
        print("  BODY:", r.text[:120])
except Exception as e:
    print("POST /search -> ERROR:", e)
print()

# Strategy 3 — minimal GET (no safesearch, no format param; is /search an HTML-only redirect?)
print("=== Strategy 3: GET /search plain ===")
try_request("%s/search?q=honda" % BASE)
print()

# Strategy 4 — try the Apprise style alias (Some installs use /api/search)
print("=== Strategy 4: GET /api/search ===")
try_request("%s/api/search?q=honda&format=json" % BASE)
print()

# Strategy 5 — re-check /healthz and / OK
print("=== Strategy 5: health / root ===")
r1 = httpx.get("%s/healthz" % BASE, timeout=5)
r2 = httpx.get("%s/" % BASE, timeout=5)
print("/healthz -> HTTP %d" % r1.status_code)
print("/       -> HTTP %d (len=%d)" % (r2.status_code, len(r2.text)))
