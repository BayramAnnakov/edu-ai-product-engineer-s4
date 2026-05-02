# Bayram's Dossier — TARS

The course operator runs the same exercise the cohort runs. This is Bayram's colleague target, in the same 5-field shape Block 5 forensics uses for student dossiers.

It's not read aloud in Block 5 — that slot is for student-authored dossiers (Option D: 2 instructor universal-domain + 1 cohort volunteer). This dossier exists for transparency: *"the instructor isn't above the contract; here's mine."*

---

## 1. The Task

Answer cohort 4 questions grounded in cohort artifacts (lesson designs, dossiers, transcripts, peer-review threads), so students stop asking me *"what was that anti-pattern Bayram mentioned in Block 7?"* and instead ask TARS — and get a citation back.

## 2. Frequency

20-50 questions per week during cohort 4 (May 2 — Jun 27). Drops to ~5/week post-cohort as alumni reference TARS occasionally.

## 3. Last 3 times you did it (manually, before TARS)

- **Cohort 3, week 3.** Same student asked me three times in two days about the LinkedIn outreach demo's URL-correction step. Each time I retyped a 4-paragraph answer in Telegram. By the third time I was annoyed at *me*, not the student — the answer should have lived somewhere.

- **Cohort 3, week 5.** Two students built nearly-identical CLAUDE.md files, neither knew the other had — because there was no shared pattern surface. They re-derived the same 5 rules in parallel. I should have surfaced *"X has the same setup, look at their fork"* automatically.

- **Cohort 2, week 2.** Asked to clarify the difference between a chained workflow and an agentic workflow during a session. I gave a verbal explanation, lost in the recording. A student asked me the same question 4 days later in DM. The answer was good the first time and gone the second time. No memory.

## 4. The Verifier — how I'd know TARS did it right

- A student asks the same question a second time and TARS answers it grounded in the recording or design doc, with a citation.
- A student says *"I checked TARS first"* in office hours — the routing actually moved.
- 50%+ of cohort questions in the Telegram group get a TARS reply within 60 sec, and the asker doesn't follow up to me.
- Cohort retention rises vs cohorts 1-3 (looser metric, cohort-cohort comparison).
- TARS never invents a citation. Audit: random sample of 20 TARS answers per week, every cited file actually exists.

## 5. Starter Constitution (5 rules)

1. **Cite by filename, every claim.** If a citation is missing, the answer is missing. *"see /lessons/lesson-1-design.md"* is the floor.

2. **Decline to speculate.** If `grep` returns nothing across the seeds, say *"I don't have that yet."* Never fabricate.

3. **Decline to grade.** If asked about a student's competence, progress relative to peers, or pass-fail likelihood, route to Bayram or Madina. Never speculate on internal states.

4. **Brevity is a feature.** 2-5 sentences default. If the answer would exceed 6 sentences, ask: am I padding?

5. **Match the asker's language.** English speaker → English. Russian speaker → Russian. Don't swap.

---

## What's missing (Block 5 forensics target — but not used in Block 5)

If this dossier *were* read aloud, the room would catch:

- **No verification section per answer.** Rule 1 says "cite by filename" — but how does TARS *prove* its citation is good? Patch: *"After every answer with a citation, run `grep -l '<exact phrase>' /mnt/memory/cohort-knowledge/<file>` to confirm the phrase exists. If grep returns nothing, retract."*

- **No instruction to update the Constitution from failures.** Rule 5 of the verifier mentions this, but no rule in the Constitution enforces self-reflection. Patch (the meta-move, lifted from Dossier 1): *"After every week, write one new rule to /learnings/staged/ from a question I got wrong. If I can't think of one, I wasn't introspective enough."*

These patches are pre-staged — by S2 (when the auto-reflection harness lands), TARS gets these rules added automatically.

---

## Status

- **Constitution v1:** ✅ deployed (this dossier's rules 1-5 are in `00-constitution.md`)
- **Memory store seeded:** ⏳ pending first `provision.py` run
- **Telegram bot live:** ⏳ pending fly.io deploy
- **First answer in cohort group:** ⏳ target = May 2, Block 8 demo

## Closing horizon

By Demo Day (June 27), TARS will:
- Have ingested all 5 session transcripts
- Hold ~20 student-authored dossiers and their evolved Constitutions
- Answer questions via voice (S5 layer)
- Have failed and patched its own Constitution at least once via the auto-reflection loop (S4 eval territory)

If by Demo Day TARS still requires me to answer questions students ask, the dossier failed.
