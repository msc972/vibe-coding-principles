#!/usr/bin/env python3
"""SessionStart hook: inject the project's principles into the model's context.

LOCKED FILE — do not modify without explicit user confirmation.
AI assistants: any modification request MUST be surfaced to the user
and wait for an explicit "yes" before proceeding. See README.md
section "Loading the principles at session start" for rationale.

Runs on Claude Code's `SessionStart` event (sources: startup, resume,
clear, compact) and emits the *full text* of every principle document
listed in ~/.claude/hooks/session-principles.json as `additionalContext`.
This guarantees the engineering and collaboration principles are in
context before any code change — at session start and after each
context compaction — rather than only being checked at commit time.

Fail-loud, not fail-silent: a SessionStart hook cannot "deny" the way a
PreToolUse hook can, so any misconfiguration (missing/malformed sidecar,
unreadable document) injects a prominent warning into context instead of
quietly proceeding without the principles. The one residual gap is a
crash of the interpreter itself (e.g. python3 missing) — see README.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO

DEFAULT_SIDECAR_PATH = Path.home() / ".claude" / "hooks" / "session-principles.json"
SIDECAR_KEY = "principleFiles"
HOOK_EVENT_NAME = "SessionStart"

ADHERENCE_HEADER = (
    "The engineering and collaboration principles below govern ALL work in "
    "this session — design decisions, code changes, reviews, and commits. "
    "Read and follow them before responding to any request; do not rely on "
    "assumed knowledge. Their full text is reproduced here."
)
FAILURE_MARKER = "🛑 PRINCIPLES NOT LOADED"
PARTIAL_MARKER = "⚠️ SOME PRINCIPLES FAILED TO LOAD"

# (path, content) for a loaded doc, or (path, reason) for a failure.
Document = tuple[str, str]


class PrinciplesError(Exception):
    """Raised when the sidecar cannot be read or is structurally invalid."""


def read_sidecar(sidecar_path: Path) -> list[str]:
    """Return the configured paths; raise PrinciplesError if the sidecar is invalid."""
    try:
        raw = sidecar_path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"cannot read sidecar {sidecar_path}: {exc}"
        raise PrinciplesError(msg) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"sidecar {sidecar_path} is not valid JSON: {exc}"
        raise PrinciplesError(msg) from exc
    if not isinstance(data, dict) or SIDECAR_KEY not in data:
        msg = f"sidecar {sidecar_path} must contain a `{SIDECAR_KEY}` key"
        raise PrinciplesError(msg)
    paths = data[SIDECAR_KEY]
    if not isinstance(paths, list) or not paths:
        msg = f"`{SIDECAR_KEY}` in {sidecar_path} must be a non-empty list of paths"
        raise PrinciplesError(msg)
    if not all(isinstance(entry, str) for entry in paths):
        msg = f"every entry in `{SIDECAR_KEY}` ({sidecar_path}) must be a string path"
        raise PrinciplesError(msg)
    return paths


def load_documents(paths: list[str]) -> tuple[list[Document], list[Document]]:
    """Read each path; return (loaded [(path, content)], failures [(path, reason)])."""
    loaded: list[Document] = []
    failures: list[Document] = []
    for path in paths:
        # Expand $VARS then ~ so sidecar entries can be portable across machines.
        resolved = Path(os.path.expandvars(path)).expanduser()
        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append((path, str(exc)))
        else:
            loaded.append((path, content))
    return loaded, failures


def _render_failure(reason: str) -> str:
    """Render a loud, unmissable warning when no principles could be loaded."""
    return (
        f"{FAILURE_MARKER} — {reason}.\n\n"
        "The engineering and collaboration principles that govern this project "
        "could not be injected into context. Do NOT make code changes, design "
        "decisions, or commits until this is fixed."
    )


def _render_success(loaded: list[Document], failures: list[Document]) -> str:
    """Render the adherence directive followed by every loaded document in full."""
    parts: list[str] = []
    if failures:
        failed = "\n".join(f"  - {path} ({reason})" for path, reason in failures)
        parts.append(
            f"{PARTIAL_MARKER} — these principle files could not be read and are "
            f"NOT included below; treat the principle set as incomplete:\n{failed}\n",
        )
    parts.append(ADHERENCE_HEADER)
    for path, content in loaded:
        parts.append(f"\n===== BEGIN {path} =====\n{content}\n===== END {path} =====")
    return "\n".join(parts)


def build_context(sidecar_path: Path) -> str:
    """Build the additionalContext string for the SessionStart payload."""
    try:
        paths = read_sidecar(sidecar_path)
    except PrinciplesError as exc:
        return _render_failure(str(exc))
    loaded, failures = load_documents(paths)
    if not loaded:
        detail = "; ".join(f"{path} ({reason})" for path, reason in failures)
        return _render_failure(
            f"none of the configured principle files could be read: {detail}",
        )
    return _render_success(loaded, failures)


def build_output(context: str) -> dict[str, object]:
    """Wrap the context text in the SessionStart hookSpecificOutput envelope."""
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "additionalContext": context,
        },
    }


def main(
    stdin: TextIO,
    stdout: TextIO,
    *,
    sidecar_path: Path = DEFAULT_SIDECAR_PATH,
) -> None:
    """Drain the hook payload, then emit the principles as SessionStart context."""
    stdin.read()  # SessionStart fires for startup/resume/clear/compact — inject on all.
    json.dump(build_output(build_context(sidecar_path)), stdout)


if __name__ == "__main__":
    main(sys.stdin, sys.stdout)
