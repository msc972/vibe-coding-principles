#!/usr/bin/env python3
"""PreToolUse guard: deny edits in locked dirs and to spec-annotated test files."""

import json
import re
import sys
from pathlib import Path
from typing import NoReturn

LOCKED_DIRS = ["vibe-coding-principles"]
# @spec, @pytest.mark.spec, [spec] — case insensitive
SPEC = re.compile(
    r"(?<![A-Za-z0-9_])@spec(?![A-Za-z0-9_])"
    r"|@pytest\.mark\.spec(?![A-Za-z0-9_])"
    r"|\[spec\]",
    re.IGNORECASE,
)


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

file_path = data.get("tool_input", {}).get("file_path") or data.get(
    "tool_input", {}
).get("notebook_path")
if not file_path:
    sys.exit(0)

# Lock if either the original or symlink-resolved path is in a locked dir,
# so a symlink in or out of a locked dir can't escape the check.
resolved = Path(file_path).resolve()
norms = [str(p).replace("\\", "/") for p in (Path(file_path), resolved)]
for d in LOCKED_DIRS:
    needle = f"/{d.strip('/')}/"
    if any(needle in f"/{n}/" for n in norms):
        deny(
            f"LOCKED: {file_path} is in (or links to) a locked directory. "
            f"Ask the user before editing."
        )

if resolved.is_file() and SPEC.search(
    resolved.read_text(encoding="utf-8", errors="ignore")
):
    deny(
        f"SPECIFICATION-TESTS-LOCKED: {file_path} contains "
        f"@spec / @pytest.mark.spec / [spec] tests. "
        f"Do not modify without user approval."
    )
