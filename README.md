<!--
LOCKED FILE — do not modify without explicit user confirmation.
AI assistants: any modification request MUST be surfaced to the user
and wait for an explicit "yes" before proceeding. See the section
"Locking these files against AI drift" below for rationale.
-->

# Vibe-Coding Principles

Two companion documents for building software well, especially with AI coding assistants — plus a drop-in enforcement config.

- **[ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md)** — *what good code looks like.* principles covering design, readability, testing, security, and supply chain. Language-agnostic.
- **[AI_COLLABORATION.md](AI_COLLABORATION.md)** — *how humans and AI assistants should work together.* norms covering intellectual honesty, transparency, privacy, destructive-action safety, pre-commit/pre-PR discipline, guard and hook behaviour, and testing discipline.
- **[pre-commit-config.template.yaml](pre-commit-config.template.yaml)** — reusable pre-commit config for Python projects that mechanically enforces much of ENGINEERING_PRINCIPLES.md (lint, type, security, CVE scan, secrets, pinning).
- **[pre_edit_guard.py](pre_edit_guard.py)** + **[pre_commit_guard.py](pre_commit_guard.py)** — Claude Code hook scripts that enforce locked-file and spec-test rules at the harness layer (see §"Locking these files against AI drift" for wiring).
- **[pyproject.toml](pyproject.toml)** — strict ruff config (`select = ["ALL"]` + documented exceptions) for developing the hook scripts. Not shipped to consumer projects.

Both `.md` files use RFC 2119 severity tags — **MUST / SHOULD / MAY** — so teams can argue about the right axis (is this a hard rule or a default?) instead of relitigating semantics every review.

## Why two files?

Code quality and collaboration quality are different problems. ENGINEERING_PRINCIPLES.md helps building projects with high standards. AI_COLLABORATION.md is specifically about the failure modes that emerge when an LLM is writing, reviewing, or refactoring alongside you: tautological tests, silent capitulation under review pressure, secret leaks into prompts, surprise rewrites. Keeping them separate lets each evolve at its own pace.

## Usage

Drop these files into your team's central repo, or reference them as living team norms. They work as-is or as a starting point — adapt freely. If you change something and the change is general, consider opening a PR upstream. CLAUDE.md should reference these rules, so they are loaded with session start and after each conversation compact. Annotate test methods with spec attribute for Behavior/Specification tests and those tests will not be modified by AI.

```
# Locked files

Some files in this repo are locked from AI modification. A PreToolUse hook enforces this automatically.

- **Locked directories**: files under `vibe-coding-principles/` require explicit user approval before any edit.
- **Specification-locked tests**: any file containing a method annotated with case insensitive `@spec` (Python/Java/Kotlin/TS) / `@pytest.mark.spec` (Pytest) or `[spec]` (.NET) must not be modified. If blocked, stop and ask the user — don't try workarounds.

# Engineering Practices

Before making design decisions or code changes, consult the relevant practice doc:

- `.claude/practices/AI_COLLABORATION.md`
- `.claude/practices/ENGINEERING_PRINCIPLES.md`

Always read the applicable doc before implementing; don't rely on assumed knowledge
```

## Locking these files against AI drift

If you use AI coding assistants (Claude Code, Cursor, Copilot, etc.), these files are a target for silent modification — an assistant may edit principles during unrelated tasks (*"I noticed a small inconsistency and fixed it"*). That drift is exactly what undermines shared standards.

Two complementary layers of protection:

### Layer 1 — Harness-level hook (the hard lock)

If your AI tool supports pre-tool-use hooks, configure one to intercept write operations (`Edit`, `Write`, `MultiEdit`, etc.) whose target path falls under this directory. Block by default; require explicit user approval to proceed. This is the hard lock — the harness enforces it, not the AI.

For Claude Code: add a `PreToolUse` hook in your `settings.json` — either user-global (`~/.claude/settings.json`, applies to every project) or project-local (`.claude/settings.json`, scoped to one repo). Match the write tools and check `tool_input.file_path` against the repo path. See the Claude Code documentation on hooks for the exact schema. Other tools (Cursor, etc.) expose similar mechanisms under different names.

```json
{
  "model": "opus",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/pre_edit_guard.py"
          }
        ]
      }
    ]
  }
}
```

**Configure which directories the hook protects.** `pre_edit_guard.py` reads `CLAUDE_LOCKED_DIRS` (comma-separated directory names) from the environment, defaulting to `vibe-coding-principles`. To protect different directories in your repo, set the variable in your shell or via the `env` field of `settings.json`:

```json
{
  "env": {
    "CLAUDE_LOCKED_DIRS": "docs/principles,specs"
  }
}
```

The repository also ships a second optional hook, `pre_commit_guard.py`, which intercepts `git commit` commands and blocks them if any `@pytest.mark.spec` test is failing at that point. Wire it with an additional `PreToolUse` entry matching `Bash`:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python .claude/hooks/pre_commit_guard.py"
    }
  ]
}
```

**Limitation:** `pre_commit_guard.py` is Python/Pytest-specific — it runs `pytest -m spec`. It only enforces `@pytest.mark.spec` annotations. For other languages or test frameworks, provide an equivalent runner that executes your spec-annotated tests before allowing a commit.

### Layer 2 — Banner + AI instruction (the soft lock)

Each file in this directory begins with a `LOCKED FILE` banner in a comment (invisible when rendered). To activate the soft lock for your AI assistant, add a rule like the following to your AI's system prompt, rules file, or memory (e.g. `CLAUDE.md`, `.cursorrules`, `AGENTS.md`):

> **Locked-file rule.** Before modifying any file whose header contains a `LOCKED FILE` banner, surface the proposed change in plain language to the user and wait for an explicit "yes, modify the locked file" before proceeding. This applies even if the edit seems small or obvious.

**Notes for AI assistants following the soft lock:**
- The `LOCKED FILE` banner sits in a comment (HTML in markdown, `#` in YAML), so it is invisible in rendered output. Check the raw source's first few lines before deciding to edit.
- Even additive changes (e.g. adding a new test method in a file that already contains a `@spec` test) will be denied by the Layer 1 hook because the hook matches on file containment, not method scope. Ask the human before proposing such an edit.
- Do not attempt to bypass Layer 1 by routing write operations through `Bash` or other write paths — see AI_COLLABORATION.md §"Working with guards and hooks".

### Why two layers?

- **Layer 1 is strong but local.** A Claude Code hook doesn't help a Cursor user; per-person setup is required.
- **Layer 2 is portable.** The banners travel with the published repo and signal intent to any AI tool or human collaborator, but rely on the AI respecting its instructions.

Together they give hard enforcement where available and soft signaling where not. Skip either, not both.

### Temporarily allowing a legitimate change

This workflow applies to **locked-banner files only**. SPEC tests have a stricter regime — see *"Changing a SPEC-annotated test"* below.

When the hook correctly blocks an edit you actually want to apply via the AI (e.g., evolving a principle, fixing a typo, adding a new rule), lift the block briefly:

**Claude Code:**
1. Run `/hooks` in the Claude Code prompt to open the hooks management UI, or edit `~/.claude/settings.json` directly.
2. Disable or remove the `PreToolUse` hook whose matcher is `Edit|Write|MultiEdit|NotebookEdit`.
3. Ask the AI to apply the previously-approved change — it will now go through.
4. **Restore the hook immediately afterward.** Forgetting this step removes the lock entirely.

**Simpler alternative (all tools):** apply the edit yourself by hand. The LOCKED banner's rule binds AI assistants, not humans — a manual edit via your own editor is always fine and doesn't trigger any hook.

The two-step friction — explicit approval to the AI *plus* toggling the hook — is intentional: it prevents any single instruction from silently changing the principles.

### Changing a SPEC-annotated test

SPEC tests are stricter than locked-banner files: AI must never modify, rename, delete, or strip the annotation of a `@spec` / `@pytest.mark.spec` / `[spec]` test — *regardless of any approval the human gives*. The hook-lift workflow above does not apply to spec tests.

The only legitimate path to change a SPEC test:

1. **The human removes the annotation themselves**, in their own editor, with no AI involvement. The test is then a normal test, not a spec.
2. **AI may modify the now-unannotated test** like any other code, subject to the human's normal review.
3. **The human re-applies the annotation** if and when the new behaviour has been approved as the new spec.

The annotation is the boundary; while it is there, the test is the contract.
