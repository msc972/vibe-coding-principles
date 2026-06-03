# Vibe-Coding Principles

Two short standards documents for building software well — especially with AI coding assistants — plus optional Claude Code hooks that keep the AI honest about them.

## The documents

- **[ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md)** — what good code looks like: design, readability, testing, security, supply chain. Language-agnostic, RFC-2119 tagged (MUST / SHOULD / MAY).
- **[AI_COLLABORATION.md](AI_COLLABORATION.md)** — how humans and AI assistants work together: intellectual honesty, transparency, privacy, destructive-action safety, guard/hook behaviour, testing discipline.

Drop them into your repo or reference them as team norms. They work as-is; adapt freely.

## The enforcement (optional, Claude Code)

Four small files turn the documents from "nice to read" into "actually applied":

| File | Role |
|------|------|
| `ai_edit_guard.py` | PreToolUse hook. Denies edits to files matching `locked-paths.json`, and to any test annotated `@spec` / `@pytest.mark.spec` / `[spec]`. |
| `pre_commit_guard.py` | PreToolUse Bash hook. Blocks shell commands that write to a locked path, and blocks `git commit` while any `@spec` test fails. |
| `failclose.sh` | Wraps each hook so a crash denies the action instead of silently allowing it. |
| `locked-paths.json` | The glob list of inviolable paths. Locks itself. |

Two more files help you hold your own repo to the principles:

- **[pre-commit-config.template.yaml](pre-commit-config.template.yaml)** — drop-in pre-commit config (lint, type, security, CVE scan, secrets, pinning).
- **[pyproject.toml](pyproject.toml)** — strict ruff + pytest + coverage config used to develop the hooks.

## Setup

1. Copy the four hook files to `~/.claude/hooks/`, and the two documents to `~/.claude/`.
2. Edit `~/.claude/hooks/locked-paths.json` to fit your repo.
3. Add this to `~/.claude/settings.json` (or a project `.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write|MultiEdit|NotebookEdit|mcp__.*",
        "hooks": [{ "type": "command",
          "command": "~/.claude/hooks/failclose.sh python3 ~/.claude/hooks/ai_edit_guard.py" }] },
      { "matcher": "Bash",
        "hooks": [{ "type": "command",
          "command": "~/.claude/hooks/failclose.sh python3 ~/.claude/hooks/pre_commit_guard.py" }] }
    ],
    "SessionStart": [
      { "hooks": [{ "type": "command",
        "command": "cat ~/.claude/ENGINEERING_PRINCIPLES.md ~/.claude/AI_COLLABORATION.md" }] }
    ]
  }
}
```

The `SessionStart` line puts the full text of both documents into the model's context at the start of each session and after every compaction — so the AI works to the principles from the first edit, not just at commit time. (No hook support? Add `@~/.claude/ENGINEERING_PRINCIPLES.md` and `@~/.claude/AI_COLLABORATION.md` to a `CLAUDE.md` instead.)

## Two kinds of lock

- **Path locks** — anything matching a glob in `locked-paths.json` can't be edited, created, deleted, renamed, or redirected into by the AI. To change a locked file, edit it yourself or remove it from the list.
- **Spec tests** — a test annotated `@spec` / `@pytest.mark.spec` / `[spec]` is inviolable *while annotated*, even with your approval. To change one, remove the annotation yourself first.

## Developing the hooks

The hook scripts use only the Python standard library — no runtime dependencies. To run the test suite (the project holds itself to 100% branch coverage on the guards):

```sh
pip install -r requirements-dev.txt
pytest --cov=ai_edit_guard --cov=pre_commit_guard --cov-branch --cov-fail-under=100
```

Lint / type / security checks are pinned in `.pre-commit-config.yaml`:

```sh
pip install pre-commit && pre-commit run --all-files
```

CI (`.github/workflows/ci.yml`) runs both on every push and PR — the repo dogfoods the rules it ships.

## What this is and isn't

A hygiene guardrail against over-eager AI, **not** a security boundary. It catches the common cases (direct edits, basic shell writes); it doesn't chase every exotic bypass — `AI_COLLABORATION.md §11` covers the rest by forbidding rerouting outright. Harness-level escapes (`--no-hooks`, bypass mode) are out of scope by definition.
