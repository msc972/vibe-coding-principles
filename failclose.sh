#!/bin/bash
# Fail-closed wrapper for Claude Code PreToolUse hooks.
#
# Usage in settings.json:
#   "command": "/path/to/failclose.sh python3 /path/to/your_hook.py"
#
# Behavior:
#   - Wrapped command exits 0 → its stdout is forwarded verbatim
#     (preserving the allow / deny decision the hook itself emitted).
#   - Wrapped command exits non-zero (interpreter missing, script
#     crash, syntax error, etc.) → this wrapper emits a deny JSON,
#     blocking the tool call. The harness's default on hook crash
#     is to allow — this wrapper inverts that to fail closed.

if [ $# -eq 0 ]; then
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"HOOK ERROR: failclose wrapper invoked with no command. Failing closed."}}\n'
    exit 0
fi

output=$("$@")
rc=$?
if [ "$rc" -eq 0 ]; then
    printf '%s' "$output"
    exit 0
fi

printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"HOOK ERROR: %s exited %d (hook failed to run or crashed). Failing closed — investigate the hook command in settings.json."}}\n' "$1" "$rc"
exit 0
