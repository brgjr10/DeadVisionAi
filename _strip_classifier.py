"""
Remove dead cloud-classify methods from classifier.py.
"""
from pathlib import Path

fn = Path(r"F:\DeadVisionAi\backend\app\routing\classifier.py")
lines = fn.read_text(encoding="utf-8").splitlines()

live_methods = {
    "_classify_with_local_model",
    "_heuristic_classify",
}

skip_until_next = False
keep = []
current_method = ""

for i, l in enumerate(lines):
    stripped = l.strip()
    # detect start of a dead classify_with method
    if stripped.startswith("async def _classify_with_"):
        method_name = stripped[24:].split("(")[0]  # after "async def _classify_with_"
        if method_name in live_methods:
            keep.append(l)
            continue
        else:
            skip_until_next = True
            continue
    if skip_until_next:
        # skip until the next live method at class/async-def indent
        if stripped.startswith("async def ") or stripped.startswith("def ") or stripped.startswith("class ") or stripped == "":
            skip_until_next = False
            if stripped == "":
                pass
            else:
                keep.append(l)
        continue
    keep.append(l)

result = "\n".join(keep)
fn.write_text(result + "\n", encoding="utf-8")
print(f"Reduced classifier.py from {len(lines)} to {len(keep)} lines")
