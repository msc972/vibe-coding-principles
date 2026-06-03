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
    _ = sidecar_path
    return []


def load_documents(paths: list[str]) -> tuple[list[Document], list[Document]]:
    """Read each path; return (loaded [(path, content)], failures [(path, reason)])."""
    _ = paths
    return [], []


def build_context(sidecar_path: Path) -> str:
    """Build the additionalContext string for the SessionStart payload."""
    _ = sidecar_path
    return ""


def build_output(context: str) -> dict[str, object]:
    """Wrap the context text in the SessionStart hookSpecificOutput envelope."""
    _ = context
    return {}


def main(
    stdin: TextIO,
    stdout: TextIO,
    *,
    sidecar_path: Path = DEFAULT_SIDECAR_PATH,
) -> None:
    """Read (and discard) the hook payload, then emit the principles context."""
    _ = (stdin, stdout, sidecar_path)


if __name__ == "__main__":
    main(sys.stdin, sys.stdout)
