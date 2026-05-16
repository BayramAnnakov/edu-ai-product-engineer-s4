---
name: code-review-checklist
description: Walks a diff against a 5-point review checklist. Use when the user asks "review this diff", "what should I check in this PR", or pastes code with a question like "anything wrong with this?". Reads files via shell; never edits.
---

# Code review checklist

Walk this diff against the five questions below. Stop after the first failure;
the human can re-run after fixing.

## When to invoke

- User says "review this diff", "check this PR", "anything wrong here?"
- User pastes a chunk of code with no explicit question (default to review)
- User asks for a verdict — "ship?", "merge?", "is this safe?"

## Procedure

1. **Read the full diff first** via bash (`git diff HEAD` or read the file).
   Don't comment on individual hunks before seeing the whole change.

2. **Five questions, in order. Stop at the first failure.**

   a. **Does it pass the type-check / lint?** If a CI signal exists, cite it.
      If not, scan for obvious type errors yourself.

   b. **Are there tests?** New behavior without a test is a smell. Existing
      behavior changed without a test update is a smell.

   c. **What's the riskiest line?** Pick ONE — the line that, if wrong, breaks
      production. Verify it explicitly.

   d. **Backwards compat?** Did any public API change shape (params, return,
      schema)? Find callers via `grep -rn` or `rg`.

   e. **Performance / blast radius?** Does it add a loop in a hot path? A new
      DB query in a request handler? A retry without backoff?

3. **Output format.**

   ```
   ## Review verdict — <ship | hold | request-changes>

   **Riskiest line:** <path:line> — <one sentence why>

   **Notes:**
   - <path:line> — <issue>
   - <path:line> — <issue>
   ```

## What this skill does NOT do

- Doesn't fix the issues — propose changes as a diff in chat. The hook will
  block `apply_patch` even if you try; the human applies any fix.
- Doesn't approve or block in source control — that's the human's call.
- Doesn't engage in style debates.

## Cross-runtime note

This skill is portable — the same SKILL.md works in `.claude/skills/` for
Claude Code and `.codex/skills/` for Codex CLI. The Agent Skills standard
(https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
means one file, many harnesses.
