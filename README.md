<!--
LOCKED FILE — do not modify without explicit user confirmation.
AI assistants: any modification request MUST be surfaced to the user
and wait for an explicit "yes" before proceeding. See the section
"Locking these files against AI drift" below for rationale.
-->

# Vibe-Coding Principles

Two companion documents for building software well, especially with AI coding assistants — plus a drop-in enforcement config.

- **[ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md)** — *what good code looks like.* 32 principles covering design, readability, testing, security, and supply chain. Language-agnostic.
- **[AI_COLLABORATION.md](AI_COLLABORATION.md)** — *how humans and AI assistants should work together.* 13 norms covering intellectual honesty, transparency, privacy, destructive-action safety, and testing discipline.
- **[pre-commit-config.template.yaml](pre-commit-config.template.yaml)** — reusable pre-commit config for Python projects that mechanically enforces much of ENGINEERING_PRINCIPLES.md (lint, type, security, CVE scan, secrets, pinning).

Both `.md` files use RFC 2119 severity tags — **MUST / SHOULD / MAY** — so teams can argue about the right axis (is this a hard rule or a default?) instead of relitigating semantics every review.

## Why two files?

Code quality and collaboration quality are different problems. ENGINEERING_PRINCIPLES.md would be roughly the same rules in 2015 or 2030 — it's evergreen. AI_COLLABORATION.md is specifically about the failure modes that emerge when an LLM is writing, reviewing, or refactoring alongside you: tautological tests, silent capitulation under review pressure, secret leaks into prompts, surprise rewrites. Keeping them separate lets each evolve at its own pace.

## Usage

Drop these files into your team's central repo, or reference them as living team norms. They work as-is or as a starting point — adapt freely. If you change something and the change is general, consider opening a PR upstream.

## Locking these files against AI drift

If you use AI coding assistants (Claude Code, Cursor, Copilot, etc.), these files are a target for silent modification — an assistant may edit principles during unrelated tasks (*"I noticed a small inconsistency and fixed it"*). That drift is exactly what undermines shared standards.

Two complementary layers of protection:

### Layer 1 — Harness-level hook (the hard lock)

If your AI tool supports pre-tool-use hooks, configure one to intercept write operations (`Edit`, `Write`, `MultiEdit`, etc.) whose target path falls under this directory. Block by default; require explicit user approval to proceed. This is the hard lock — the harness enforces it, not the AI.

For Claude Code: add a `PreToolUse` hook in your user `settings.json` that matches the write tools and checks `tool_input.file_path` against the repo path. See the Claude Code documentation on hooks for the exact schema. Other tools (Cursor, etc.) expose similar mechanisms under different names.

```
{
  "model": "opus",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "fp=$(jq -r \".tool_input.file_path // empty\"); case \"$fp\" in /<path_to_projects>/vibe-coding-principles/*) jq -cn --arg p \"$fp\" \"{hookSpecificOutput:{hookEventName:\\\"PreToolUse\\\",permissionDecision:\\\"deny\\\",permissionDecisionReason:(\\\"LOCKED FILE: \\\" + \\$p + \\\" — in the locked vibe-coding-principles directory. Explicit user approval required before modification. See the repo README section on locking.\\\")}}\" ;; esac"
          }
        ]
      }
    ]
  }
}

```

### Layer 2 — Banner + AI instruction (the soft lock)

Each file in this directory begins with a `LOCKED FILE` banner in a comment (invisible when rendered). To activate the soft lock for your AI assistant, add a rule like the following to your AI's system prompt, rules file, or memory (e.g. `CLAUDE.md`, `.cursorrules`, `AGENTS.md`):

> **Locked-file rule.** Before modifying any file whose header contains a `LOCKED FILE` banner, surface the proposed change in plain language to the user and wait for an explicit "yes, modify the locked file" before proceeding. This applies even if the edit seems small or obvious.

### Why two layers?

- **Layer 1 is strong but local.** A Claude Code hook doesn't help a Cursor user; per-person setup is required.
- **Layer 2 is portable.** The banners travel with the published repo and signal intent to any AI tool or human collaborator, but rely on the AI respecting its instructions.

Together they give hard enforcement where available and soft signaling where not. Skip either, not both.

### Temporarily allowing a legitimate change

When the hook correctly blocks an edit you actually want to apply via the AI (e.g., evolving a principle, fixing a typo, adding a new rule), lift the block briefly:

**Claude Code:**
1. Run `/hooks` in the Claude Code prompt to open the hooks management UI, or edit `~/.claude/settings.json` directly.
2. Disable or remove the `PreToolUse` hook whose matcher is `Edit|Write|MultiEdit|NotebookEdit`.
3. Ask the AI to apply the previously-approved change — it will now go through.
4. **Restore the hook immediately afterward.** Forgetting this step removes the lock entirely.

**Simpler alternative (all tools):** apply the edit yourself by hand. The LOCKED banner's rule binds AI assistants, not humans — a manual edit via your own editor is always fine and doesn't trigger any hook.

The two-step friction — explicit approval to the AI *plus* toggling the hook — is intentional: it prevents any single instruction from silently changing the principles.
