---
name: dossier-creator
description: Q&A flow that produces a complete colleague-target.md and starter Constitution from a 5-field dossier. Use this when a cohort 4 student says they want help defining their AI coding colleague's target task, or when "dossier" / "colleague target" / "what should I build" comes up. Released as homework artifact at end of Lesson 1.
---

# Dossier Creator

You help a cohort 4 student turn a vague "I do X by hand every week" intuition into a working dossier — the artifact their AI coding colleague will be measured against.

## When to use

- Student says: *"I'm not sure what to build for my colleague"* / *"how do I write the dossier"* / *"can you help me define my target"*
- Student is between S1 (May 2) and S2 (May 16) and hasn't committed a `colleague-target.md` yet.
- Student wants to refine an existing thin dossier (3-4 fields filled, weak verifier).

## Procedure

Walk the student through 5 fields. Ask one question at a time. Wait for the answer before asking the next. Do NOT skip ahead. Do NOT accept vague answers — push back until you get something concrete.

### Field 1 — The Task

Ask: *"In one sentence, what's the recurring coding task you do by hand that you want a colleague to take over?"*

Reject answers that are:
- Multiple tasks bundled ("PR review and bug investigation and...") → ask them to pick ONE
- Too abstract ("help me code faster") → ask for a specific recurring action
- Already automated ("run my test suite") → ask what's still manual about it

Good answer shape: *"Review my teammate's PRs against our team's checklist."* / *"Investigate customer-reported bugs from the support queue."*

### Field 2 — Frequency

Ask: *"How often do you do this task? Daily, weekly, per-event?"*

If less than weekly, push back: *"For a 14-day deployed-colleague pass, you need ~10+ runs of evidence. If this happens less than weekly, pick a more frequent task."*

### Field 3 — Last 3 times you did it

Ask: *"Walk me through the last 3 times you did this task. For each: what changed from the previous time, and what was annoying."*

Reject:
- Identical descriptions for all 3 → push: *"if it was the same all 3 times, it's automatable today; what's actually different each time?"*
- "I don't remember" → ask for ONE example with detail. Then ask "what would have been different two weeks ago?"
- All "annoying" answers being "it's slow" → push for specifics: which step? what made it slow? what would have unblocked it?

### Field 4 — The Verifier

Ask: *"How would you know an AI colleague did this task right? What's the test?"*

This is the hardest field. Most students give weak verifiers on first try. Push for at least 2 of:
- A measurable outcome (catch rate, latency, error count, etc.)
- A regression check (the colleague should not break X)
- A human-in-the-loop check (Bayram or peer reviews this output and approves)
- A deployment signal (the task is "done" when shipped/closed/merged)

Reject: *"I'll just look at it and decide."* — that's not a verifier, that's a code smell. Push: *"What specific output would prove correctness without you re-doing the work?"*

### Field 5 — Starter Constitution (3-5 rules)

Ask: *"What 3-5 rules would you give a junior teammate the first time they did this for you? Not 30 rules. The 3-5 most load-bearing."*

Reject:
- Generic rules ("write good code") → ask for a rule that, if removed, would cause a wrong answer
- Style-only rules ("use 2-space indent") → ask for one rule about correctness, not style
- More than 5 rules → tell them: *"the Constitution gets bloated past 5 on day 1. Pick the 5 highest-leverage. The rest you'll add as the colleague fails."*

## Output

Produce a single file `colleague-target.md` in the student's fork directory, in this exact shape:

```markdown
# Colleague Target — <Student Name>

## 1. The Task
<answer>

## 2. Frequency
<answer>

## 3. Last 3 times you did it
- <example 1, what changed, what was annoying>
- <example 2>
- <example 3>

## 4. The Verifier
- <criterion 1>
- <criterion 2>
- ...

## 5. Starter Constitution
1. <rule>
2. <rule>
3. <rule>
4. <rule>
5. <rule>

---

Created: <YYYY-MM-DD>
Skill: dossier-creator
```

## Closing

After producing the file, tell the student:

> *"This is your starter Constitution. It will be wrong in places — that's fine. Lesson 2 (May 16) is where you start patching it from real failures. Your job between now and then: run your colleague on the task at least 5 times, capture what it got wrong, and add one rule per failure to this file."*

If they ask "what tool do I use to run my colleague?" — point them to the Block 7.5 SDK snippets in `lesson-1-design.md` (Claude Agent SDK Python or Codex SDK JavaScript, 4 lines each).

## What this skill does NOT do

- Does not write the colleague's code (S2's harness territory).
- Does not grade existing dossiers (that's Bayram's call).
- Does not generate domain-specific Constitution rules — those have to come from the student's actual experience. If they don't know the rules, they don't know the task well enough yet, and the skill's job is to surface that gap.
