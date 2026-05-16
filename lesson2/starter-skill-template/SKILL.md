---
name: my-colleague-task
description: REPLACE THIS — one-line trigger summary that tells Claude when to load this skill. Write it like a tool docstring, not a title. Concrete trigger phrases beat abstract descriptions. Example "Triggers when the user asks about <specific recurring task in your domain>; expects <input shape>; produces <output shape>."
---

# My Colleague Task

> Fork this template, change four things, ship it. See the bottom of this file for the "Things to change" checklist.

## When to invoke

Describe the specific situations where this skill should fire. The clearer this is, the better Claude routes to it.

Concrete trigger examples (rewrite for your task):
- "User pastes a stack trace and asks 'why does this fail'"
- "User asks to triage a Jira ticket"
- "User asks to draft a PR description"
- "User mentions one of: `<list of keywords specific to your task>`"

## Inputs the skill needs

Before producing output, gather these inputs (ask the user if missing):
1. **[input 1]** — what kind of artifact, where it lives
2. **[input 2]** — context the skill needs to do its job well
3. **[input 3]** — optional but helps

## Walkthrough — what the skill actually does

This is the steps the skill follows. Write it as instructions to Claude, not as documentation.

Example for a code-review skill:
1. Read the diff fully before commenting
2. Find the highest-risk change — the one that, if wrong, breaks production
3. Check that change against `reference.md` patterns
4. If anything matches a known anti-pattern, cite it
5. Default to silence on style issues; only flag substance
6. Output: 1-3 bullets, each citing a file:line

## Output format

Describe what the skill produces. Show an example.

```markdown
## Review summary

**Highest risk:** path/to/file.ts:42 — comment explaining the risk

**Other notes:**
- path/to/other.ts:99 — secondary issue
```

## What this skill does NOT do

Naming non-goals makes the skill sharper.
- Doesn't refactor (just reviews)
- Doesn't run tests (just reads code)
- Doesn't engage with style preferences (substance only)

## Linked resources (progressive disclosure)

This skill bundles `reference.md` with deeper anti-pattern catalog. Claude loads it on demand when reviewing a substantial diff. Keep these references **focused** — under 500 lines each. Long references defeat the progressive-disclosure design.

## See also

- `reference.md` — anti-pattern catalog
- `scripts/check.sh` — optional verification helper (loaded on demand)

---

## Things to change before shipping

- [ ] **`name`** in frontmatter — must match the directory name
- [ ] **`description`** in frontmatter — this IS the routing prompt. Specific > general. Trigger phrases > abstract description.
- [ ] **"When to invoke"** — concrete examples from YOUR colleague target
- [ ] **"Walkthrough"** — the actual steps your colleague should follow

## Verification (after install)

In your colleague session:
```
> tell me what skills you have
```

Your skill should appear by name. Then test:
```
> [type a trigger phrase from your "When to invoke" section]
```

Does the colleague route to this skill? If not — the description isn't routing well. Tune it.

## Why this works (the canonical framing)

Per Bayram (Webinar 3, line 515-527):
> *"Скиллы — претендент на повторяющийся путь экономии энергии."*

A skill is a **repeating pattern crystallized into a callable**. The test: did you copy-paste this between sessions before? If yes → skill candidate. If you only did it once → keep it in CLAUDE.md.

Cross-runtime note: this same SKILL.md works in Claude Code (`.claude/skills/`), Codex CLI (`.codex/skills/`), Anthropic Developer Platform, and ChatGPT. **Skills are the portable layer of harness engineering.**
