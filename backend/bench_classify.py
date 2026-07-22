"""Benchmark local classifier + heuristic latency."""
import asyncio, time, httpx, json, statistics

LMSTUDIO_URL = "http://localhost:1234/chat/completions"
LMSTUDIO_KEY = "sk-lm-oWIgaJqa:EzedWIId47dvcYlduV2H"
CLASSIFIER_MODEL = "qwen2.5-0.5b-instruct"

SYSTEM_PROMPT = """You are a routing classifier.
Return ONLY valid JSON with these keys:
  category: one of: simple, coding, complex, huge_context
  reason: short reason string"""


async def bench_classifier(n=5):
    headers = {"Authorization": f"Bearer {LMSTUDIO_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": CLASSIFIER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "What is 2+2?"},
        ],
        "temperature": 0,
        "max_tokens": 60,
    }
    times = []
    for i in range(n):
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(LMSTUDIO_URL, json=payload, headers=headers)
            dt = (time.perf_counter() - t0) * 1000
            ok = r.status_code == 200
            print(f"  call {i+1}: {dt:.0f} ms  status={r.status_code}  ok={ok}")
            times.append(dt)
        except Exception as e:
            dt = (time.perf_counter() - t0) * 1000
            print(f"  call {i+1}: {dt:.0f} ms  ERROR: {e}")
    return times


def bench_heuristic(n=10000):
    """Time pure heuristics over 10k synthetic prompts."""
    import re, random

    _COMPLEXITY_KEYWORDS = [
        "explain", "analyze", "compare", "design", "architect", "implement",
        "refactor", "optimize", "debug", "why", "how does", "step by step",
    ]

    prompts = []
    for _ in range(n):
        words = random.choices(
            ["what", "is", "the", "meaning", "of", "life", "write", "a",
             "function", "in", "python", "to", "sort", "a", "list", "debug",
             "this", "code", "explain", "how", "async", "works"],
            k=random.randint(3, 30),
        )
        prompts.append(" ".join(words))

    t0 = time.perf_counter()
    for p in prompts:
        lower = p.lower()
        complexity = min(len(lower.split()) / 200, 0.3)
        if re.search(r"```|def ", p):
            complexity += 0.1
        reasoning = sum(1 for kw in _COMPLEXITY_KEYWORDS if kw in lower)
        complexity += min(reasoning * 0.04, 0.2)
        complexity = min(complexity, 1.0)
    dt = (time.perf_counter() - t0) * 1000
    return dt


async def main():
    print("=== Local classifier (LM Studio qwen2.5-0.5b-instruct) ===")
    times = await bench_classifier(n=5)
    if times:
        times_sorted = sorted(times)
        print(f"  n={len(times)}  min={times_sorted[0]:.0f}ms  median={times_sorted[len(times_sorted)//2]:.0f}ms  "
              f"max={times_sorted[-1]:.0f}ms  avg={statistics.mean(times):.0f}ms")

    print("\n=== Heuristics only (no network, 10 000 prompts) ===")
    dt = bench_heuristic(10000)
    print(f"  10 000 prompts: {dt:.0f} ms  ({dt/10000:.3f} ms/prompt)")


asyncio.run(main())
