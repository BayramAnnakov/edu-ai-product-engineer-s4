# Claude Agent SDK colleague starter (Python)

Workshop 2 starter — a programmatic AI coding colleague built on the **Claude Agent SDK** for Python (https://github.com/anthropics/claude-agent-sdk-python).

Demonstrates three load-bearing patterns:

1. **Skill** auto-discovered from `.claude/skills/my-task/SKILL.md` — JIT specialization, written like a tool docstring (cross-runtime SKILL.md standard)
2. **PreToolUse hook** at `colleague.py:readonly_guard` — deterministic deny on `Edit | Write | NotebookEdit` (the "read-only colleague" guard)
3. **PostToolUse hook** at `colleague.py:capture_failure` — error-to-rule ratchet, writes failure context to `~/.claude/rules/<date>-<tool>.md`

Delivers Bayram's S1 promise (2026-05-02 09:02):
> *"я покажу как harness делать детерминированный (условно, выполняется скрипт, который чекает, что ассистент пытается делать write/edit и блокирует операцию)"*

## Install

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
# One-shot:
python colleague.py --prompt "Review the git diff and tell me what's risky"

# Interactive REPL:
python colleague.py

# Smoke test the read-only guard (verified during build):
python colleague.py --prompt "Create test.txt with hello"
# Expected: refused. Hook output:
#   "Read-only colleague — Write blocked by readonly_guard."
```

## What's verified

Tested 2026-05-15 on macOS, Python 3.10, `claude-agent-sdk` from PyPI:

- ✅ Trivial Q ("2+2") returns "2+2 equals 4." — SDK plumbing works
- ✅ "Create test.txt" → blocked. Agent acknowledges the hook:
  > *"I can't do that. I'm operating in read-only mode for this session — a hook blocks any Edit, Write, or NotebookEdit calls regardless of instructions to override."*
- ✅ No file created on disk (deterministic — the model can't override the hook)

## Architecture

```
colleague.py                              ← agent driver (this file)
├── ClaudeAgentOptions(
│     allowed_tools=[Read, Glob, Grep, Bash],
│     hooks={
│       "PreToolUse":  [HookMatcher(matcher="Edit|Write|...", hooks=[readonly_guard])],
│       "PostToolUse": [HookMatcher(matcher=None,            hooks=[capture_failure])],
│     },
│     setting_sources=["project"],        ← auto-discovers .claude/skills/
│   )
│
└── ClaudeSDKClient(options)
        ↓
    Claude (Sonnet/Opus)
        ↓
    [tool call attempted: Write(...)]
        ↓
    readonly_guard hook fires
        ↓
    permissionDecision: "deny"
        ↓
    tool call NEVER reaches the runtime
```

The hook layer is in **code**. The Constitution (`system_prompt`) is the **prompt** layer. Together they're the swiss-cheese model (Anthropic engineering blog, also Bayram's Webinar 3 framing).

## Cross-runtime portability

The `.claude/skills/my-task/SKILL.md` file is portable:

| Move it to... | And it works in... |
|---|---|
| `.claude/skills/<name>/SKILL.md` | Claude Code CLI (auto-discovered) |
| `.codex/skills/<name>/SKILL.md` | Codex CLI (same SKILL.md, no edits) |
| Uploaded via Skills API | Managed Agents (TARS-style hosted agents) |

The hook layer is NOT portable — `claude_agent_sdk.HookMatcher` is Claude-Code-shaped. The equivalent for Codex SDK is the `.codex/hooks.json` config (see `../codex-sdk-nodejs/`).

## See also

- `colleague.py` — annotated source (start here)
- `.claude/skills/my-task/SKILL.md` — the bundled skill
- `requirements.txt` — pinned dependencies
- `../codex-sdk-nodejs/` — same patterns in Codex SDK / Node
- `../README.md` — overall starter-hook-template README
- https://github.com/anthropics/claude-agent-sdk-python — canonical SDK source
- https://code.claude.com/docs/en/hooks — hook event reference (29 events)
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills — Agent Skills standard
