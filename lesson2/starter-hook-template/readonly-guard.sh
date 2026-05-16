#!/bin/bash
# readonly-guard.sh — PreToolUse hook for Claude Code / Codex CLI.
#
# Purpose: deterministically block Edit / Write / apply_patch tool calls when
# the colleague is supposed to be read-only.
#
# Delivers Bayram's S1 promise (2026-05-02 09:02):
#   "выполняется скрипт, который чекает, что ассистент пытается делать
#   write/edit и блокирует операцию. То есть это делается не инструкцией
#   (промптом), а кодом."
#
# Wiring (Claude Code): add to ~/.claude/settings.json or .claude/settings.json.
# Claude Code's write-class tools are: Edit, Write, NotebookEdit.
#
#   "PreToolUse": [{
#     "matcher": "Edit|Write|NotebookEdit",
#     "hooks": [{ "type": "command", "command": "~/.claude/hooks/readonly-guard.sh" }]
#   }]
#
# Wiring (Codex CLI): add to ~/.codex/hooks.json.
# Codex's unified patch/edit/write tool is: apply_patch.
#
#   "PreToolUse": [{
#     "matcher": "apply_patch",
#     "hooks": [{ "type": "command", "command": "~/.codex/hooks/readonly-guard.sh" }]
#   }]
#
# Hook input arrives on stdin as JSON. We emit a JSON decision on stdout.

set -euo pipefail

# Read the hook payload from stdin.
INPUT=$(cat)

# Extract the tool name. (jq is usually available; if not, you can grep.)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# Allowed reads: pass through. (PreToolUse only fires on the matcher's tools,
# so we're already filtered to write-class tools — but this is defense in depth.)
case "$TOOL_NAME" in
  Edit|Write|NotebookEdit|apply_patch)
    # Compose the deny decision.
    jq -n --arg reason "Read-only colleague — write/edit blocked by readonly-guard.sh hook. Remove the hook from settings.json to re-enable writes." '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: $reason
      }
    }'
    exit 0
    ;;
  *)
    # Anything else: allow.
    exit 0
    ;;
esac
