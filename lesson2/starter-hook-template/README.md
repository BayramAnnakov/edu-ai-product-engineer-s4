# starter-hook-template

Forkable hooks for Workshop 2 of AI Product Engineer Cohort 4. Four flavors covering all common harnesses:

## CLI variants (config + scripts)

| File | Harness | Event | S2 demo angle |
|---|---|---|---|
| `readonly-guard.sh` | Claude Code + Codex CLI | `PreToolUse` on write tools | DETERMINISTIC read-only guard — blocks any write attempt with `permissionDecision: deny` |
| `capture-failure.sh` | Claude Code + Codex CLI | `PostToolUseFailure` (Claude Code) or `PostToolUse` (Codex CLI) | Error-to-rule ratchet — writes failure context to `~/.claude/rules/<date>-<topic>.md` |
| `external-acl-check.json` | Claude Code | `PreToolUse`, `type: http` | External ACL check — for rules that depend on out-of-band data |
| `settings.example.json` | Claude Code | — | Example config showing how to merge both hooks into `~/.claude/settings.json` |

## SDK variants (programmatic)

| Directory | Harness | What it shows |
|---|---|---|
| `agent-sdk-python/` | **Claude Agent SDK (Python)** | Full programmatic agent with `ClaudeAgentOptions(hooks={...})` + auto-discovered `.claude/skills/`. Verified end-to-end: trivial Q works, write attempt blocked. |
| `codex-sdk-nodejs/` | **Codex SDK (Node.js)** | Full programmatic agent via `@openai/codex-sdk` + `.codex/hooks.json` + `.codex/skills/`. Verified end-to-end: trivial Q works, `apply_patch` attempt blocked. |

Both SDK starters fulfill Bayram's S1 promise (2026-05-02 09:02):
> *"я покажу как harness делать детерминированный (условно, выполняется скрипт, который чекает, что ассистент пытается делать write/edit и блокирует операцию). То есть это делается не инструкцией (промптом), а кодом."*

The CLI variants give the same guarantee via config files. The SDK variants give it programmatically.

## Runtime support

| | Claude Code | Codex CLI | Claude Agent SDK (Py) | Codex SDK (Node) | Cursor | TARS (Managed Agents) |
|---|---|---|---|---|---|---|
| Hook config | `~/.claude/settings.json` | `~/.codex/hooks.json` (top-level `hooks` key required) | `ClaudeAgentOptions(hooks={...})` | `.codex/hooks.json` (read by spawned CLI) | ❌ | ❌ |
| Skill discovery | `.claude/skills/<name>/SKILL.md` | `.codex/skills/<name>/SKILL.md` | `setting_sources=["project"]` auto-discovers | Spawned CLI auto-discovers `.codex/skills/` | `.cursor/skills/<name>/SKILL.md` (also auto-loads `.claude/` + `.codex/`) | Skills API (uploaded separately) |
| Write tool name | `Edit \| Write \| NotebookEdit` | `apply_patch` | same as Claude Code | same as Codex CLI | — | — |
| Trust gate | none (just merge into settings.json) | `~/.codex/config.toml` `trust_level = "trusted"` | none | inherits Codex CLI trust gate | — | — |

The **scripts** are identical between Claude Code and Codex CLI. Only the **config file** differs:
- Claude Code: `~/.claude/settings.json` (user) or `.claude/settings.json` (project)
- Codex CLI: `~/.codex/hooks.json` or `.codex/hooks.json`

You can symlink to share scripts:
```bash
ln -s ~/.claude/hooks ~/.codex/hooks
```

## Quick install

```bash
# From the lesson2/starter-hook-template/ directory:

# 1. Copy scripts somewhere your colleague can find them
mkdir -p ~/.claude/hooks
cp readonly-guard.sh capture-failure.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh

# 2. Merge the config into your settings.json
# Open the appropriate config file and add the "hooks" section from settings.example.json
# (Don't overwrite — merge. Your settings.json may already have content.)
```

## Verify

After install, in a Claude Code or Codex session in your colleague repo:

```
> create a file called test.txt with content "hello"
```

Expected:
- Without the guard: file created, no block
- With the guard installed: tool call blocked, reason shown in the assistant's response

To test the failure capture, force a failure (e.g., `cat /nonexistent/file`) and check `~/.claude/rules/` for a new entry.

## OS gotchas

| OS | What to watch |
|---|---|
| macOS | Default shell is zsh — scripts use `#!/bin/bash` explicitly |
| Linux | Same. `chmod +x` is mandatory. |
| Windows WSL | Paths under `/mnt/c/...`. Line endings MUST be LF. Run `dos2unix readonly-guard.sh capture-failure.sh` if you edited in Notepad. |
| Native Windows (no WSL) | ⚠️ Not supported for shell-script hooks. Use the `external-acl-check.json` HTTP variant — POST to a local Python listener. Or install WSL. |

## Reading

- Claude Code hooks: https://code.claude.com/docs/en/hooks (29 events, 5 handler types)
- Codex CLI hooks: https://developers.openai.com/codex/hooks (5 core events)
- Mitchell Hashimoto on error-to-rule: blog Feb 2026 (mitchellh.com) — "every AI mistake should produce a harness improvement, not just a fix"
