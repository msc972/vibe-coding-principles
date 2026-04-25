#!/usr/bin/env python3
"""Block `git commit` if SPEC-marked pytest tests fail."""

import json
import subprocess  # nosec B404 — needed to invoke pytest; command is fixed below.
import sys
from typing import NoReturn

# Runs only tests marked @pytest.mark.spec
SPEC_TESTING_COMMAND = ["pytest", "-m", "spec", "--tb=short", "-q"]
SPEC_RUN_TIMEOUT_SECONDS = 60
# pytest exit code 5 = no tests were collected (nothing to verify, allow commit)
PYTEST_NO_TESTS_COLLECTED = 5


def deny(msg: str) -> NoReturn:
    """Emit a deny JSON response on stdout and exit, blocking the tool call."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": msg,
                }
            }
        )
    )
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as exc:
    deny(f"HOOK ERROR: malformed hook input — {exc}. Failing closed.")

if data.get("tool_name") != "Bash":
    sys.exit(0)

cmd = data.get("tool_input", {}).get("command", "")
# Detect `git commit` even when chained with && ; |
segments = cmd.replace(";", "&&").replace("|", "&&").split("&&")
if not any(s.strip().startswith("git commit") for s in segments):
    sys.exit(0)

try:
    result = subprocess.run(  # nosec B603 — fixed command list, not user-controlled.
        SPEC_TESTING_COMMAND,
        capture_output=True,
        text=True,
        timeout=SPEC_RUN_TIMEOUT_SECONDS,
        check=False,
    )
except FileNotFoundError:
    deny(
        "COMMIT BLOCKED: pytest is not installed in the current environment. "
        "Install it (`pip install pytest`) or remove the @spec gate before committing."
    )
except subprocess.TimeoutExpired:
    deny(
        f"COMMIT BLOCKED: @spec tests exceeded {SPEC_RUN_TIMEOUT_SECONDS}s. "
        "Investigate hung tests before committing."
    )

if result.returncode == PYTEST_NO_TESTS_COLLECTED:
    sys.exit(0)
if result.returncode != 0:
    output = (result.stdout + result.stderr)[-2000:]
    deny(
        "COMMIT BLOCKED: @spec tests failed. Fix the code (do not modify the tests) "
        f"before committing.\n\n--- pytest output ---\n{output}"
    )
