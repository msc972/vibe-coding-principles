#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

LOCKED_DIRS = ["vibe-coding-principles"]
SPEC = re.compile(r"(?<![A-Za-z0-9_])@spec(?![A-Za-z0-9_])|\[spec\]", re.I)  # @spec and [spec] - case insensitive

def deny(msg):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": msg,
    }}))
    sys.exit(0)

data = json.load(sys.stdin)
tool = data.get("tool_name", "")
fp = data.get("tool_input", {}).get("file_path") or data.get("tool_input", {}).get("notebook_path")
if not fp:
    sys.exit(0)

norm = str(Path(fp)).replace("\\", "/")
for d in LOCKED_DIRS:
    if f"/{d.strip('/')}/" in f"/{norm}/":
        deny(f"LOCKED: {fp} is in a locked directory. Ask the user before editing.")

if tool != "Write" and Path(fp).is_file():
    if SPEC.search(Path(fp).read_text(encoding="utf-8", errors="ignore")):
        deny(f"SPECIFICATION-TESTS-LOCKED: {fp} contains @spec / [spec] tests. Do not modify without user approval.")