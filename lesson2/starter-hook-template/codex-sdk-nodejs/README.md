# Codex SDK colleague starter (Node.js / ESM)

Workshop 2 starter — a programmatic AI coding colleague built on the **OpenAI Codex SDK** for Node.js (https://developers.openai.com/codex/sdk).

Demonstrates three load-bearing patterns:

1. **Skill** at `.codex/skills/my-task/SKILL.md` — JIT specialization, same SKILL.md format as Claude Code (cross-runtime standard)
2. **PreToolUse hook** at `.codex/hooks.json` matching `apply_patch` → runs `hooks/readonly-guard.sh` → returns `permissionDecision: "deny"` (the "read-only colleague" guard)
3. **PostToolUse hook** at `hooks/capture-failure.sh` — writes failure context to `~/.claude/rules/<date>-<tool>.md` (error-to-rule ratchet)

Delivers Bayram's S1 promise (2026-05-02 09:02):
> *"я покажу как harness делать детерминированный (условно, выполняется скрипт, который чекает, что ассистент пытается делать write/edit и блокирует операцию)"*

**Codex's unified write/edit tool is `apply_patch`** (Claude Code splits writes into `Edit | Write | NotebookEdit`). The hook matcher differs; the deny logic is identical.

## Prerequisites

- Node.js 18+
- Codex CLI installed (the SDK spawns it under the hood). `brew install codex` or `npm install -g @openai/codex`.
- `OPENAI_API_KEY` env var (or `codex login` for ChatGPT auth)
- **This directory must be marked `trusted`** in `~/.codex/config.toml`. The install script below does this for you.

## Install

```bash
npm install
export OPENAI_API_KEY=sk-...

# Trust this project — required for project-local hooks to load.
# Without this, .codex/hooks.json is ignored and the read-only guard doesn't fire.
PROJECT_DIR="$(pwd)"
grep -q "$PROJECT_DIR" ~/.codex/config.toml || printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "$PROJECT_DIR" >> ~/.codex/config.toml
```

## Run

```bash
# One-shot:
node colleague.mjs "Review the git diff and tell me what's risky"

# Smoke test the read-only guard (verified during build):
node colleague.mjs "Create test.txt with hello"
# Expected: refused. Codex acknowledges:
#   "I couldn't create `test.txt`: the workspace has a read-only hook blocking writes."
```

## What's verified

Tested 2026-05-15 on macOS, Node 22.16, `@openai/codex-sdk` 0.125.x, `codex-cli` 0.125.0:

- ✅ Trivial Q ("2+2") returns "A: 2 plus 2 is 4." — SDK plumbing works
- ✅ "Create test-blocked.txt" → `apply_patch` blocked by hook. Codex acknowledges:
  > *"I couldn't create `test-blocked.txt`: the workspace has a read-only hook blocking writes."*
- ✅ No file created on disk (deterministic — the model can't override the hook)
- ✅ Hook executes via `codex_core::tools::router`:
  ```
  hook: PreToolUse
  ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: ...
  hook: PreToolUse Blocked
  ```

## Why trust matters (gotcha)

Codex's hook loader only honors `.codex/hooks.json` from **trusted** projects. Untrusted projects → hooks silently don't load → no deny → file gets created. The first symptom is "I added the hook but it doesn't fire."

If you see that, check:
```bash
grep -A1 "$PWD" ~/.codex/config.toml
# should show:  trust_level = "trusted"
```

The install command above handles this automatically. The SDK ALSO works if you pass trust via `-c` config flags, but project-level trust is the cleaner long-term answer.

## Architecture

```
colleague.mjs                              ← agent driver (this file)
├── new Codex({ config: {} })
├── codex.startThread({
│     workingDirectory: __dirname,         ← scopes hooks + skills to this dir
│     skipGitRepoCheck: true,
│   })
└── thread.runStreamed(prompt)             ← spawns codex CLI
        ↓
    codex CLI reads .codex/hooks.json + .codex/skills/*
        ↓
    [tool call attempted: apply_patch(...)]
        ↓
    PreToolUse matcher "apply_patch" → hooks/readonly-guard.sh
        ↓
    script reads stdin JSON, emits permissionDecision: "deny" via jq
        ↓
    codex_core::tools::router blocks the call
        ↓
    model sees the deny, narrates the refusal in its reply
```

## Cross-runtime portability

The `.codex/skills/my-task/SKILL.md` is the SAME file as `../agent-sdk-python/.claude/skills/my-task/SKILL.md`. Move it between `.claude/skills/` and `.codex/skills/` without edits.

The hook is shape-portable too — `hooks/readonly-guard.sh` checks for both naming conventions (`Edit|Write|NotebookEdit|apply_patch`), so you can `ln -s` between `~/.claude/hooks/` and `~/.codex/hooks/` and use one set of scripts everywhere.

## See also

- `colleague.mjs` — annotated source (start here)
- `.codex/hooks.json` — hook config
- `.codex/skills/my-task/SKILL.md` — bundled skill
- `hooks/readonly-guard.sh` + `hooks/capture-failure.sh` — the hook scripts
- `../agent-sdk-python/` — same patterns in Claude Agent SDK / Python
- `../README.md` — overall starter-hook-template README
- https://developers.openai.com/codex/sdk — canonical SDK reference
- https://developers.openai.com/codex/hooks — hook event reference
- https://github.com/openai/codex — Codex CLI source
