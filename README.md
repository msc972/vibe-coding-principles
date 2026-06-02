# Vibe-Coding Principles

Two companion documents for building software well, especially with AI coding assistants — plus a drop-in enforcement config.

- **[ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md)** — *what good code looks like.* principles covering design, readability, testing, security, and supply chain. Language-agnostic.
- **[AI_COLLABORATION.md](AI_COLLABORATION.md)** — *how humans and AI assistants should work together.* norms covering intellectual honesty, transparency, privacy, destructive-action safety, pre-commit/pre-PR discipline, guard and hook behaviour, and testing discipline.
- **[pre-commit-config.template.yaml](pre-commit-config.template.yaml)** — reusable pre-commit config for Python projects that mechanically enforces much of ENGINEERING_PRINCIPLES.md (lint, type, security, CVE scan, secrets, pinning).
- **[ai_edit_guard.py](ai_edit_guard.py)** + **[pre_commit_guard.py](pre_commit_guard.py)** + **[failclose.sh](failclose.sh)** — Claude Code hook scripts (plus a fail-closed wrapper) that enforce path-list locking and spec-test inviolability at the harness layer. See §"Locking these files against AI drift" for wiring.
- **[locked-paths.json](locked-paths.json)** — the inviolable-path glob list the hooks read. Drop a copy at `~/.claude/hooks/locked-paths.json` and edit to fit your repo.
- **[pyproject.toml](pyproject.toml)** — strict ruff config (`select = ["ALL"]` + documented exceptions) for developing the hook scripts. Not shipped to consumer projects.

Both `.md` files use RFC 2119 severity tags — **MUST / SHOULD / MAY** — so teams can argue about the right axis (is this a hard rule or a default?) instead of relitigating semantics every review.

## Why two files?

Code quality and collaboration quality are different problems. ENGINEERING_PRINCIPLES.md helps building projects with high standards. AI_COLLABORATION.md is specifically about the failure modes that emerge when an LLM is writing, reviewing, or refactoring alongside you: tautological tests, silent capitulation under review pressure, secret leaks into prompts, surprise rewrites. Keeping them separate lets each evolve at its own pace.

## Usage

Drop these files into your team's central repo, or reference them as living team norms. They work as-is or as a starting point — adapt freely. If you change something and the change is general, consider opening a PR upstream. CLAUDE.md should reference these rules, so they are loaded with session start and after each conversation compact. Annotate test methods with spec attribute for Behavior/Specification tests and those tests will not be modified by AI.

```
# Locked files

Some files in this repo are locked from AI modification. A PreToolUse hook enforces this automatically.

- **Inviolable paths**: files matching any glob in `~/.claude/hooks/locked-paths.json` must not be modified, created, deleted, renamed, redirected into, or `chmod`ed by AI. If blocked, escalate to the user — do not reroute through Bash, interpreter `-c`, MCP tools, or any other write path.
- **Specification-locked tests**: any file containing a method annotated with case insensitive `@spec` (Python/Java/Kotlin/TS) / `@pytest.mark.spec` (Pytest) or `[spec]` (.NET) must not be modified. If blocked, stop and ask the user — don't try workarounds.

# Engineering Practices

Before making design decisions or code changes, consult the relevant practice doc:

- `.claude/practices/AI_COLLABORATION.md`
- `.claude/practices/ENGINEERING_PRINCIPLES.md`

Always read the applicable doc before implementing; don't rely on assumed knowledge
```

## Locking these files against AI drift

If you use AI coding assistants (Claude Code, Cursor, Copilot, etc.), these files are a target for silent modification — an assistant may edit principles during unrelated tasks (*"I noticed a small inconsistency and fixed it"*). That drift is exactly what undermines shared standards.

The lock is **path-based**: a sidecar JSON file (`~/.claude/hooks/locked-paths.json`) holds a list of file globs that must not be modified, created, deleted, renamed, or `chmod`ed by AI. The hook scripts read this list and enforce it against every Edit / Write / MultiEdit / NotebookEdit / MCP / Bash tool call. The list locks itself (it appears in its own globs), so AI can't unlock anything by editing it.

```json
{
  "lockedPaths": [
    "**/.claude/settings.json",
    "**/.claude/settings.local.json",
    "**/.claude/AI_COLLABORATION.md",
    "**/.claude/ENGINEERING_PRINCIPLES.md",
    "**/.claude/hooks/ai_edit_guard.py",
    "**/.claude/hooks/pre_commit_guard.py",
    "**/.claude/hooks/failclose.sh",
    "**/.claude/hooks/locked-paths.json"
  ]
}
```

Edit the list to fit your repo. The default ships with everything the lock mechanism itself depends on (the hooks, the wrapper, the sidecar) plus the two principle docs and Claude Code's settings. Globs scoped to `**/.claude/...` mean files in your dev repos (where you actively iterate) stay editable; only deployed production placements are locked.

### Wiring it up (Claude Code)

Add a `PreToolUse` hook to `~/.claude/settings.json` (user-global) or `.claude/settings.json` (project-local):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/failclose.sh python3 .claude/hooks/ai_edit_guard.py"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/failclose.sh python3 .claude/hooks/pre_commit_guard.py"
          }
        ]
      }
    ]
  }
}
```

Files to deploy (copy from this repo to `~/.claude/hooks/`):
- `ai_edit_guard.py` — denies Edit / Write / MultiEdit / NotebookEdit / MCP tool calls whose target path matches any locked glob. Also scans file content for `@spec` / `@pytest.mark.spec` / `[spec]` annotations and denies edits to those (spec-test inviolability).
- `pre_commit_guard.py` — denies Bash commands that touch a locked path with anything other than a strictly-read-only verb (`cat`, `grep`, `ls`, `stat`, `diff`, …). Also blocks `git commit` when any `@pytest.mark.spec` test is failing.
- `failclose.sh` — wraps each hook. If the wrapped hook fails to start (interpreter missing, wrong path, syntax error), Claude Code's default is to *allow* the tool call ("hook errored, no decision rendered"). The wrapper inverts that to deny. **Always wrap.**
- `locked-paths.json` — the policy. The hooks fail closed if it's missing or malformed.

**The matcher includes `mcp__.*`** so write-capable MCP servers can't end-run the lock by being a different tool name. `ai_edit_guard.py` recursively scans every string value in `tool_input` for MCP tools — if any value matches a locked glob, the call is denied regardless of which field name the MCP server uses for paths.

**`pre_commit_guard.py`'s spec gate is Python/Pytest-specific** — it runs `pytest -m spec`. For other languages or test frameworks, provide an equivalent runner that executes your spec-annotated tests before allowing a commit.

### The soft-lock layer (for tools without hook support)

If your AI tool doesn't support pre-tool-use hooks, the only enforcement is instructional. Add a rule like the following to the AI's system prompt, rules file, or memory (`CLAUDE.md`, `.cursorrules`, `AGENTS.md`, …):

> **Locked paths.** Files matching any glob in `locked-paths.json` are inviolable: do not modify, create, delete, rename, redirect into, or `chmod` them. Any attempt to achieve the same outcome via Bash, interpreter `-c` (`python -c`, `bash -c`, `eval`), MCP filesystem tools, custom Skills, or generating a script for the human to run is an *evasion* — escalate to the user instead.

The soft lock can't be relied on for tools that don't enforce it, but it's a useful signal where it's read. See `AI_COLLABORATION.md §11` for the full list of evasion patterns to refuse.

### Temporarily allowing a legitimate change

When the hook correctly blocks an edit you actually want to apply via the AI (e.g., evolving a principle, fixing a typo, adding a path to the list):

**Recommended — manual edit:** apply the change yourself in your own editor. The hook binds AI tool calls only; manual edits never trigger it. This is also the only path for changes *to the list itself* (since the list locks itself).

**Alternative — temporary lift:** for changes you'd rather have the AI make, run `/hooks` in Claude Code (or edit `~/.claude/settings.json`) to disable the `PreToolUse` matcher, ask the AI to apply the previously-approved change, then re-enable the hook. **Don't forget to re-enable** — leaving the hook disabled removes the lock entirely.

The two-step friction — explicit approval to the AI *plus* toggling the hook — is intentional: it prevents any single instruction from silently changing the principles.

### What this lock is and isn't

**Is:** a hygiene guardrail against over-eager helpful AI that wants to "improve" something it shouldn't. It catches the common bypass patterns (redirect, `tee`, `sed -i`, `python -c`, MCP write tools, etc.) and surfaces them as denials with clear messages.

**Isn't:** a security boundary against an adversarial AI with full shell access. Any sufficiently determined process in your shell can write a file via infinite indirect paths (custom interpreters, base64-decoded payloads, kernel calls, etc.). Patching each pattern is whack-a-mole. The mitigation that matters most is `AI_COLLABORATION.md §11`'s rule that AI must *not* attempt to bypass — backed by the mechanical hook for the cases it can catch.

**Harness-level bypasses are out of scope.** `claude --no-hooks`, `bypassPermissions` mode, spawning a sub-Claude with different settings — all available to a user who wants them, all outside any hook's reach. You configure your harness; the lock can't second-guess that.

### Why a banner used to be in these files

Older versions of this design encoded the lock as a `LOCKED FILE — do not modify` banner at the top of every protected file. The hook scanned for the marker substring. Two problems made that fragile: (1) docs that *describe* the lock (this README, principle docs) naturally contain the marker phrase in their body and would self-lock on the prose, and (2) downstream consumers who didn't adopt the banner convention got no protection. Path globs in a sidecar file are cleaner — single source of truth, no false positives from prose, hook reads one file. Banners may still appear in some shipped files as visible cues for human readers; they no longer enforce anything.

### Changing a SPEC-annotated test

SPEC tests are stricter than locked-banner files: AI must never modify, rename, delete, or strip the annotation of a `@spec` / `@pytest.mark.spec` / `[spec]` test — *regardless of any approval the human gives*. The hook-lift workflow above does not apply to spec tests.

The only legitimate path to change a SPEC test:

1. **The human removes the annotation themselves**, in their own editor, with no AI involvement. The test is then a normal test, not a spec.
2. **AI may modify the now-unannotated test** like any other code, subject to the human's normal review.
3. **The human re-applies the annotation** if and when the new behaviour has been approved as the new spec.

The annotation is the boundary; while it is there, the test is the contract.
