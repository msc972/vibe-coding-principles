#!/usr/bin/env python3
"""Block `git commit` if SPEC-marked pytest tests fail."""
import json, subprocess, sys

# Runs only tests marked @pytest.mark.spec
SPEC_TESTING_COMMAND = ["pytest", "-m", "spec", "--tb=short", "-q"]

def deny(msg):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": msg,
    }}))
    sys.exit(0)

data = json.load(sys.stdin)
if data.get("tool_name") != "Bash":
    sys.exit(0)

cmd = data.get("tool_input", {}).get("command", "")
# Detect `git commit` even when chained with && ; |
segments = cmd.replace(";", "&&").replace("|", "&&").split("&&")
if not any(s.strip().startswith("git commit") for s in segments):
    sys.exit(0)

result = subprocess.run(SPEC_TESTING_COMMAND, capture_output=True, text=True)
if result.returncode == 5:  # no SPEC tests collected — nothing to verify
    sys.exit(0)
if result.returncode != 0:
    output = (result.stdout + result.stderr)[-2000:]
    deny(
        "COMMIT BLOCKED: @spec tests failed. Fix the code (do not modify the tests) "
        f"before committing.\n\n--- pytest output ---\n{output}"
    )