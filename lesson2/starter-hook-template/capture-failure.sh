#!/bin/bash
# capture-failure.sh — PostToolUseFailure hook.
#
# The error-to-rule ratchet (Mitchell Hashimoto, Feb 2026 (mitchellh.com)):
# "Every AI mistake should produce a harness improvement, not just a fix."
#
# When a tool call fails, this hook writes the failure context to
# ~/.claude/rules/<YYYY-MM-DD>-<short-topic>.md so you can review and
# promote it into your CLAUDE.md / AGENTS.md.
#
# Wiring (Claude Code): add to ~/.claude/settings.json:
#
#   "PostToolUseFailure": [{
#     "hooks": [{ "type": "command", "command": "~/.claude/hooks/capture-failure.sh" }]
#   }]
#
# Codex CLI does not have a PostToolUseFailure event yet — use PostToolUse
# and check tool_result.is_error inside the script.

set -euo pipefail

INPUT=$(cat)

# Where to stage captures. Override via CLAUDE_RULES_DIR env var.
RULES_DIR="${CLAUDE_RULES_DIR:-$HOME/.claude/rules}"
mkdir -p "$RULES_DIR"

# Derive a topic slug from the tool name + a timestamp.
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
DATE=$(date -u +%Y-%m-%d)
TIME=$(date -u +%H%M%S)
SLUG=$(echo "$TOOL_NAME" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]' '-' | sed 's/-*$//' | head -c 32)
OUT_FILE="$RULES_DIR/${DATE}-${TIME}-${SLUG}.md"

# Pull the relevant fields. (Field names per Claude Code hook docs.)
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
TOOL_RESULT=$(echo "$INPUT" | jq -c '.tool_result // {}')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')

# Write the failure capture.
cat > "$OUT_FILE" <<EOF
---
captured_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
tool: $TOOL_NAME
session_id: $SESSION_ID
cwd: $CWD
---

# Failure: $TOOL_NAME (captured $(date -u +%Y-%m-%d))

## What was the agent trying to do?
\`\`\`json
$TOOL_INPUT
\`\`\`

## What happened?
\`\`\`json
$TOOL_RESULT
\`\`\`

## Proposed rule (TODO — fill in by hand or via Claude)
Add a rule to your CLAUDE.md / AGENTS.md so this doesn't happen again. Examples:
- "When doing X, always check Y first"
- "Don't use tool Z for task W; use V instead"
- "Verify the file exists before attempting to edit it"

## Status
- [ ] Reviewed
- [ ] Promoted to CLAUDE.md / AGENTS.md
- [ ] Captured into cohort-4-rules (paste into the cohort thread or POST to the ingest endpoint when it ships)
EOF

# Optional: notify the cohort-4-rules pipeline.
# Uncomment and set COHORT_RULES_ENDPOINT to enable.
# if [ -n "${COHORT_RULES_ENDPOINT:-}" ]; then
#   curl -s -X POST -H 'Content-Type: application/json' \
#     -d "{\"tool\":\"$TOOL_NAME\",\"input\":$TOOL_INPUT,\"result\":$TOOL_RESULT}" \
#     "$COHORT_RULES_ENDPOINT" || true
# fi

# Don't block on capture failure — exit 0.
exit 0
