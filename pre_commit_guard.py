#!/usr/bin/env python3
"""PreToolUse Bash guard: deny destructive ops on locked paths, gate `git commit`.

LOCKED FILE — do not modify without explicit user confirmation.
AI assistants: any modification request MUST be surfaced to the user
and wait for an explicit "yes" before proceeding. See README.md
section "Locking these files against AI drift" for rationale.

Two responsibilities:

1. **Locked-path backstop**: every Bash command is parsed and any token that
   matches a glob in ~/.claude/hooks/locked-paths.json triggers a deny —
   unless every verb in the command is on the read-only allowlist (cat,
   grep, ls, etc.). Catches `rm`, `mv`, `cp`, `chmod`, redirection (`>`),
   `tee`, interpreter `-c` invocations that mention a locked path, etc.
2. **git-commit spec gate**: when the command contains `git commit`, run
   `pytest -m spec` and deny if any SPEC-marked test fails.
"""

import json
import os
import re
import shlex
import subprocess  # nosec B404 — fixed command list below.
import sys
from pathlib import Path
from typing import NoReturn

SIDECAR_PATH = Path.home() / ".claude" / "hooks" / "locked-paths.json"

SPEC_TESTING_COMMAND = ["pytest", "-m", "spec", "--tb=short", "-q"]
SPEC_RUN_TIMEOUT_SECONDS = 60
# pytest exit code 5 = no tests were collected (nothing to verify, allow commit)
PYTEST_NO_TESTS_COLLECTED = 5

# Verbs that strictly read; everything else is treated as potentially destructive
# when combined with a locked-path token in the same command.
READ_ONLY_VERBS = frozenset(
    {
        "cat",
        "less",
        "more",
        "head",
        "tail",
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "ack",
        "wc",
        "diff",
        "cmp",
        "md5sum",
        "sha256sum",
        "ls",
        "stat",
        "file",
        "find",
        "tree",
        "readlink",
        "echo",
        "printf",
        "test",
        "[",
        "true",
        "false",
        "pwd",
        "whoami",
        "id",
        "date",
        "uname",
    },
)

# Interpreters whose -c flag runs inline code — a common bypass vector.
INTERPRETER_C_PATTERN = re.compile(
    r"\b(python3?|perl|ruby|node|bash|sh|zsh|awk|gawk)\s+(-[a-zA-Z]*c|--command)\b",
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


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a `**` / `*` / `?` glob into a fullmatch regex on POSIX paths."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def load_locked_globs() -> list[re.Pattern[str]]:
    """Read sidecar; fail closed on any error so the lock can't be silently bypassed."""
    try:
        sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        deny(f"HOOK ERROR: cannot read {SIDECAR_PATH} ({exc}). Failing closed.")
    patterns = sidecar.get("lockedPaths", [])
    if not isinstance(patterns, list):
        deny(
            f"HOOK ERROR: {SIDECAR_PATH} must contain a list at `lockedPaths`. "
            f"Failing closed."
        )
    return [glob_to_regex(p) for p in patterns if isinstance(p, str)]


def expanded(token: str) -> list[str]:
    """Variants for robust matching: literal, ~-expanded, $VAR-expanded."""
    return list(
        {
            token,
            os.path.expanduser(token),
            os.path.expandvars(token),
            os.path.expandvars(os.path.expanduser(token)),
        }
    )


def token_matches_locked(token: str, globs: list[re.Pattern[str]]) -> bool:
    """Check whether any expansion of token matches any locked glob."""
    return any(g.match(v) for v in expanded(token) for g in globs)


def check_locked_paths(cmd: str, globs: list[re.Pattern[str]]) -> str | None:
    """Return a deny reason if `cmd` touches any locked path with a non-readonly verb.

    Returns None when the command is allowed.
    """
    # Quick-win patterns surface clear error messages.
    for match in re.finditer(r">>?\s*(\S+)", cmd):
        target = match.group(1).strip("'\"")
        if token_matches_locked(target, globs):
            return f"redirection to locked path: {target}"

    if INTERPRETER_C_PATTERN.search(cmd):
        # Inline-code path; scan whole command for any locked-path mention.
        for tok in re.findall(r"\S+", cmd):
            stripped = tok.strip("'\"`")
            if token_matches_locked(stripped, globs):
                return f"interpreter -c invocation mentions locked path: {stripped}"

    # General case: split on shell operators, then check each segment's verb + args.
    segments = re.split(r"&&|\|\||;|\|(?!\|)", cmd)
    for seg in segments:
        seg_stripped = seg.strip()
        if not seg_stripped:
            continue
        try:
            tokens = shlex.split(seg_stripped)
        except ValueError:
            continue
        if not tokens:
            continue
        verb = os.path.basename(tokens[0])
        locked_tokens = [tok for tok in tokens[1:] if token_matches_locked(tok, globs)]
        if locked_tokens and verb not in READ_ONLY_VERBS:
            return f"`{verb}` targets locked path(s): {', '.join(locked_tokens)}"

    return None


try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as exc:
    deny(f"HOOK ERROR: malformed hook input — {exc}. Failing closed.")

if data.get("tool_name") != "Bash":
    sys.exit(0)

cmd = data.get("tool_input", {}).get("command", "")

# 1. Locked-path backstop on the whole command.
locked_globs = load_locked_globs()
reason = check_locked_paths(cmd, locked_globs)
if reason:
    deny(
        f"LOCKED-PATH PROTECTION: bash command would {reason}. "
        f"Ask the user to lift the lock before retrying."
    )

# 2. git-commit spec-test gate.
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
