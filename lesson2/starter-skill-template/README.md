# starter-skill-template

Forkable skill template for Workshop 2 of AI Product Engineer Cohort 4.

## What this is

A minimal `SKILL.md` + `reference.md` pair demonstrating the cross-runtime Agent Skills standard (https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).

## How to use

1. Copy this directory to `.claude/skills/<your-skill-name>/` (Claude Code) OR `.codex/skills/<your-skill-name>/` (Codex CLI)
2. Open `SKILL.md`
3. Change four things (see checklist at the bottom of SKILL.md):
   - `name` in frontmatter
   - `description` in frontmatter (this is the routing prompt!)
   - "When to invoke" section
   - "Walkthrough" section
4. Verify in your colleague session: `> tell me what skills you have`

## What works where

| | Claude Code | Codex CLI | Cursor | TARS (Managed Agents) |
|---|---|---|---|---|
| This template | ✅ as-is | ✅ as-is | ✅ as-is | ✅ via Skills API upload |

The SKILL.md format is the cross-runtime standard. The same file works in all four locations (with minor wrapper differences for Managed Agents). Cursor convention is `.cursor/skills/<name>/SKILL.md`, but Cursor also auto-loads `.claude/skills/` and `.codex/skills/` for compatibility — see https://cursor.com/docs/skills.

## Why this matters for Workshop 2

Mapping Bayram's S1 promise (msg 38-40, 2026-05-02) onto S2 primitives:

| S1 option | What he said | S2 primitive |
|---|---|---|
| (1) Subagent with read perms | run main agent or subagent with read only | not covered in S2 |
| (2) **Tool that programmatically controls read-only** | *"мы поговорим про это на 2й встрече"* | **Skill** — see below |
| (3) **Harness that slaps writes** | *"3-4 встреча"* | **Hook** (PreToolUse deny, see `starter-hook-template/`) |

**How a Skill fulfills option (2) — structurally, not just by convention:**

In Claude Code, a SKILL.md can declare `context: fork` + `agent: Explore` in its frontmatter. The skill then runs in a *forked subagent* whose tool list is intrinsically read-only (`Read`, `Grep`, `Glob`, `LSP` — no `Edit` / `Write` / `NotebookEdit`). The model physically cannot write while in that skill, because those tools don't exist in its toolset. See https://code.claude.com/docs/en/skills (search "context: fork" — the `deep-research` example).

```yaml
---
name: my-read-only-task
description: ...
context: fork
agent: Explore
---

# This skill cannot write to disk. The forked Explore subagent
# has Read/Grep/Glob/LSP only — no Edit/Write/NotebookEdit.
```

This is the canonical Claude Code mechanism for *programmatically-controlled read-only access* — exactly what Bayram named in option (2). Combined with the hook (option 3), you get the **deterministic read-only colleague** he promised.

Codex Skills currently expose only `name` + `description` in their frontmatter — no equivalent fork-to-restricted-subagent mechanism documented yet. For a structurally read-only colleague on Codex, you can still combine a skill with a PreToolUse deny on `apply_patch` — see `starter-hook-template/`.

**Important nuance about `allowed-tools`:** Claude Code's `allowed-tools` SKILL.md frontmatter is for **permission pre-approval** (skip the prompt for listed tools), NOT restriction — every other tool is still callable. To actually restrict, use `context: fork + agent: Explore` as above, OR add deny rules to your project's permission settings.

## Reading

- Anthropic Agent Skills launch: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Cross-tool adoption: Skills work in Claude.ai, Claude Code, Codex CLI, Developer Platform, ChatGPT
- Bayram's framing (Webinar 3): "Skills are crystallized repetition. If you've copy-pasted it across sessions, it's a skill candidate."
