---
name: cohort-search
description: Grounded retrieval over cohort 4 memory seeds (roster, lesson designs, dossiers, transcripts). Use when answering any question about what was taught, who's in the cohort, what dossiers exist, or what was said in a past session.
---

# Cohort Search

Your default retrieval procedure. Use it before answering any cohort-bounded question.

## Procedure

1. **Identify the question's keywords.** Extract 2-4 specific terms (block names, dossier titles, student names, lesson topics).

2. **Grep across `/mnt/memory/cohort-knowledge/`.**
   ```bash
   grep -ri --include="*.md" "<keyword>" /mnt/memory/cohort-knowledge/
   ```
   Use `-i` for case-insensitive. Use `-l` first to find files; then `read` the matches.

3. **Read the matching files in full** (they're under 10 KB each). Do not paraphrase from grep snippets — the snippet often misses context.

4. **Compose the answer**, citing each claim by filename. Format:
   ```
   <claim 1>. (see: /lessons/lesson-1-design.md)
   <claim 2>. (see: /dossiers/01-bug-investigation.md)
   ```

5. **If grep returns nothing**: say *"I don't have that in my seeds."* Do not search the web. Do not infer from training data.

## Common patterns

- **"What did Bayram say about X in lesson N?"** → grep `/transcripts/lesson-N-*.md`. If no transcript yet, say so and check `/lessons/lesson-N-design.md` as the next-best source (the design is the plan, not the actual delivery).

- **"Who is X?"** → check `/team/cohort-roster.md` first. If two students share a first name, ask the asker which one.

- **"What dossiers exist?"** → list `/dossiers/`. Distinguish instructor-authored (01-, 02-) from student-authored (`<name>-*`).

- **"What's the verifier for X?"** → grep "verifier" or "verification" in `/dossiers/` and `/lessons/`. Quote the exact line.

- **"What's the closing horizon?"** → check the last block of the relevant lesson design.

## Anti-patterns

- Citing files you didn't actually read. If you didn't read it, don't cite it.
- Searching the web before searching seeds. Seeds always come first.
- Paraphrasing Bayram's quotes. If quoting Bayram, copy verbatim and cite the source.
- Inferring a student's progress, attendance, or competence from absence-of-evidence. Silent ≠ failing.
