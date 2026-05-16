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
| This template | ✅ as-is | ✅ as-is | ⚠️ partial | ✅ via Skills API upload |

The SKILL.md format is the cross-runtime standard. The same file works in all four locations (with minor wrapper differences for Managed Agents).

## Why this matters for Workshop 2

Skill = **read-side** of the deterministic read-only colleague Bayram promised in S1 (msg 38-40, 2026-05-02). The hook (see `starter-hook-template/`) is the **write-side** guard. Together they implement the harness Bayram named.

## Reading

- Anthropic Agent Skills launch: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Cross-tool adoption: Skills work in Claude.ai, Claude Code, Codex CLI, Developer Platform, ChatGPT
- Bayram's framing (Webinar 3): "Skills are crystallized repetition. If you've copy-pasted it across sessions, it's a skill candidate."
