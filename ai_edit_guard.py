#!/usr/bin/env python3
"""PreToolUse guard: deny edits to inviolable paths and specification tests.

Reads the `lockedPaths` glob list from ~/.claude/hooks/locked-paths.json.

- Edit / Write / MultiEdit / NotebookEdit: matches the tool's `file_path`
  against every locked glob.
- For any code file at `file_path`, also scans content for specification-test
  markers (the spec decorator, the pytest.mark.spec marker, or the bracketed
  spec attribute) used at the start of a line, i.e. as real decorators or
  attributes rather than prose mentions. Spec-test inviolability is
  content-based; no path list is possible. Documentation extensions
  (.md, .rst, .yaml, etc.) are skipped to avoid false positives on prose
  that describes the convention.

Deliberate evasion via other write paths (MCP filesystem tools, custom
interpreters, generated scripts) is out of scope by design: AI_COLLABORATION.md
§11 forbids rerouting regardless of the detection list. This guard is a
hygiene backstop for the common honest-mistake cases, not a security boundary.

Fails closed on any error reading or parsing the sidecar.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn

SIDECAR_PATH = Path.home() / ".claude" / "hooks" / "locked-paths.json"

# Markers must appear at line start (optional indent) to count as a real
# decorator / attribute — excludes prose mentions in docs and string literals
# that happen to contain the marker text. Case-insensitive: Java/Kotlin's
# capitalised `@Spec` matches the same pattern as Python's lowercase `@spec`.
SPEC = re.compile(
    # Python decorator:        @spec\ndef test_x():
    # Pytest marker:            @pytest.mark.spec\ndef test_x():
    # Pytest marker with args:  @pytest.mark.spec(reason="...")\ndef test_x():
    # Java/Kotlin annotation:   @Spec\npublic void testX() { ... }
    # Java/Kotlin with args:    @Spec(name="...")\npublic void testX()
    # TypeScript decorator:     @Spec()\nclass FooTest { ... }
    r"^\s*@(?:spec|pytest\.mark\.spec)\b"
    # .NET / C# attribute:        [Spec]\npublic void TestX() { ... }
    # .NET / C# attribute + args: [Spec(Reason="...")]\npublic void TestX()
    r"|^\s*\[\s*spec\s*[\]\(]",
    re.IGNORECASE | re.MULTILINE,
)

# Docs/config never legitimately carry spec annotations; skipping these by
# extension is defense-in-depth against the prose-false-positive class of bug.
NON_CODE_EXTS = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".html",
        ".htm",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".ini",
        ".cfg",
        ".conf",
        ".log",
        ".csv",
        ".tsv",
    },
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


def expanded(path: str) -> list[str]:
    """Variants for robust matching: literal and ~-expanded."""
    return list({path, os.path.expanduser(path)})


def path_matches_any(path: str, globs: list[re.Pattern[str]]) -> bool:
    """Check whether path (literal or ~-expanded) matches any locked glob."""
    return any(g.match(c) for c in expanded(path) for g in globs)


def main() -> None:
    """Read the PreToolUse payload from stdin and enforce the locks."""
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        deny(f"HOOK ERROR: malformed hook input — {exc}. Failing closed.")

    tool_input = data.get("tool_input", {})
    locked_globs = load_locked_globs()

    # Path-based lock on the standard editing tools.
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if file_path and path_matches_any(file_path, locked_globs):
        deny(
            f"LOCKED: {file_path} matches an inviolable path in "
            f"~/.claude/hooks/locked-paths.json. Ask the user to lift before editing."
        )

    # Spec-annotation lock (content-based; orthogonal to path globs).
    if not file_path:
        return
    try:
        resolved_path = Path(file_path).resolve()
    except OSError:
        resolved_path = Path(file_path)
    if resolved_path.is_file() and resolved_path.suffix.lower() not in NON_CODE_EXTS:
        content = resolved_path.read_text(encoding="utf-8", errors="ignore")
        if SPEC.search(content):
            deny(
                f"SPECIFICATION-TESTS-LOCKED: {file_path} contains "
                f"@spec / @pytest.mark.spec / [spec] tests. AI must not modify "
                f"these even with user approval. The human must remove the "
                f"annotation themselves first."
            )


if __name__ == "__main__":
    main()
