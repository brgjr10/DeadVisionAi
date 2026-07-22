"""html_parse_test — extract results from <div class=result> HTML block."""
import httpx, re, json

BASE = "http://localhost:8888"

Strategies
strategies = [
    # (label, method, url_fn)
    ("GET /search plain",           "GET",  lambda q: "%s/search?q=%s&format=json" % (BASE, q.replace(" ","+"))),
    ("GET /search no-format",       "GET",  lambda q: "%s/search?q=%s" % (BASE, q.replace(" ","+"))),
    ("POST /search form",           "POST", lambda q: "%s/search" % BASE),
    ("POST form no-format",         "POST", lambda q: "%s/search" % BASE),
]

def extract_results_from_html(text):
    """Naive regex extractor from SearXNG HTML results block."""
    results = []
    # style 1: <div class="result" ...>
    # style 2: <a class="result__url" ...>
    blocks = re.findall(r'<div class="result[^"]*">(.*?)</div>\s*</div>', text, re.DOTALL)
    if not blocks:
        # broader: grab <a href=...> links near title-like text
        links = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]+)', text)
        results = [{"url": u, "title": t.strip()} for u, t in links[:10]]
    else:
        for block in blocks[:5]:
            title_m = re.search(r'<a[^>]+>([^<]+)</a>', block)
            url_m   = re.search(r'href="(https?://[^"]+)"', block)
            if title_m:
                results.append({
                    "title": title_m.group(1).strip(),
                    "url":   url_m.group(1) if url_m else "",
                })
    return results

q = "newest honda car 2025"
for label, method, url_fn in strategies:
    try:
        if method == "GET":
            r = httpx.get(url_fn(q), timeout=10)
        else:
            data = {"q": q}
            r = httpx.post(url_fn(q), data=data, timeout=10)
        print("%-35s HTTP %d" % (label, r.status_code), end="")
        if r.status_code == 200:
            ct = r.headers.get("Content-Type","")
            if "json" in ct:
                print(" | JSON | format=json")
                try:
                    j = r.json()
                    n = len(j.get("results",[]))
                    print("  results=%d  first=%r" % (n, (j["results"][0]["title"] if j.get("results") else "NONE")))
                except Exception as e:
                    print("  JSON parse fail:", e)
            else:
                print(" | HTML | format=none")
                n_results = extract_results_from_html(r.text)
                print("  results=%d" % len(n_results))
                for nr in n_results[:3]:
                    print("   %r -> %r" % (nr.get("title",""), nr.get("url","")))
        else:
            print(" | body=%s" % r.text[:80])
    except Exception as e:
        print("%-35s ERROR %s" % (label, e))
    print()
