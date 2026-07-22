"""Patch router.py: insert _TIME_SENSITIVE_SYSTEM_PROMPT and fix messages array."""
import pathlib

p = pathlib.Path(r"F:\DeadVisionAi\backend\app\gateway\router.py")
src = p.read_text(encoding="utf-8")

OLD_BLOCK = (
    "# _app_start_time = time.time()\n"
    "\n"
    "# Episodic context included in the model prompt so it has recall\n"
)

NEW_BLOCK = (
    "# _app_start_time = time.time()\n"
    "\n"
    "# ── Strict time-awareness prefix ────────────────────────────────────────────\n"
    "# Prepended as a system-role message before every user turn that follows a\n"
    "# tool call. Forces the LLM to be honest about recency: no invented current\n"
    "# readings from stale or unsourced search snippets.\n"
    '_TIME_SENSITIVE_SYSTEM_PROMPT = (\n'
    '    "You are a factual, time-aware assistant.\\n\\n"\n'
    '    "STRICT RULE — never violate this:\\n"\n'
    '    "If you used a web search to answer about conditions "\n'
    "    '(weather, stocks, traffic, scores, etc.):\\n'\n"
    '    "1. State the EXACT query you sent to the search tool (verbatim).\\n"\n'
    '    "2. Both an explicit timestamp AND a quoted number in the SAME passage\\n"\n'
    '    "   are required to call anything a current value. Missing either = STALE.\\n"\n'
    '    "3. If ALL results are STALE, say: \\"I searched but could not find a\\n"\n'
    '    "   confirmed current reading for this location.\\"\\n"\n'
    '    "4. Never invent or name-drop a current number from past or forecast data.\\n"\n'
    '    "5. If any source is a .gov weather domain, prioritise its value.\\n"\n'
    ")\n"
    "\n"
    "# Episodic context included in the model prompt so it has recall\n"
)

count = src.count(OLD_BLOCK)
print(f"Step 1 — found {count} occurrence(s) of the region to patch")
assert count == 1, f"Expected 1, got {count}"
src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

old_call = '        messages = [{"role": "user", "content": enhanced_message}]'
new_call = (
    "        # Strict time-instruction injected as system message so the LLM\n"
    "        # cannot ignore or drift past it.\n"
    '        if tool_results:\n'
    '            messages = [\n'
    '                {"role": "system", "content": _TIME_SENSITIVE_SYSTEM_PROMPT},\n'
    '                {"role": "user",   "content": enhanced_message},\n'
    "            ]\n"
    '        else:\n'
    '            messages = [{"role": "user", "content": enhanced_message}]'
)

count2 = src.count(old_call)
print(f"Step 2 — found {count2} occurrence(s) of messages = [...]")
assert count2 == 1, f"Expected 1, got {count2}"
src = src.replace(old_call, new_call, 1)

p.write_text(src, encoding="utf-8")
print(f"Done — file is now {src.count(chr(10))} lines")
