# Cohort 4 — Working Notes

May 2 → Jun 27, 2026. 5 × 2h biweekly. ~20 mid+ devs.

Anchor: **Build Your AI Coding Colleague.** See `cohort-4-design.md`.

## TARS is the canonical demo project for the entire course

**TARS** (the cohort-agent in `cohort-agent/`) is the live, deployed AI colleague we are building together — a Telegram bot on Anthropic Managed Agents that watches the cohort group, answers questions grounded in lesson seeds, and produces a daily digest. It is the **course-long demo** — every session adds one capability to it, mirroring the discipline students are learning that week.

**Use TARS as the example everywhere** — slides, demos, dossiers, dry-runs, exercises. Do not invent toy projects (no scooter API, no hypothetical SaaS). If you need a "starter repo" for an exercise, point at a snapshot of `cohort-agent/`.

| Session | Discipline | Capability added to TARS |
|---|---|---|
| 1 | Context | Constitution v1, memory seeds, passive logger, daily digest |
| 2 | Skill + Harness | Custom skill (e.g., dossier-creator), error-to-rule hook, opt-out + retention rules |
| 3 | Tool | MCP integration (e.g., onsa-meetings transcripts, GitHub) + agent loop |
| 4 | Multi-agent + Eval + Swap | Eval harness on TARS replies; sub-agents for digest/research; swap day |
| 5 | Voice + Production | Voice layer; load shedding; production telemetry; Demo Day |

When designing demos, dry-runs, or exercises:
- **Block 2 stochasticity demo** uses TARS source + an ambiguous TARS feature prompt
- **Block 5 forensics dossiers** are TARS-related when possible (real bugs/PRs from TARS development)
- **Skills students author** can target TARS as the colleague (TARS == colleague target for instructor's dossier)
- **Memory seeding examples** use the actual TARS memory store layout

## What lives where

- `cohort-4-design.md` — top-level design (master frame, pass contract, session matrix)
- `cohort-agent/` — TARS source (deployed to fly.io). Constitution at `00-constitution.md`. Persona = TARS from Interstellar (Honesty 90, Humor 30).
- `lesson1/`–`lesson5/` — per-session design docs, slide outlines, handouts, dossiers, demo scaffolds
- `instructor/` — Bayram's prep (rubrics, fluency exam, retrieval quizzes)
- `case_studies/` — guest-week material

## Conventions

- Don't push lesson code to a public repo without scrubbing API keys and Telegram tokens. `.env` files stay local; `.env.example` ships.
- For dry-runs / variance tests, copy `cohort-agent/` minus `venv/` and `.env*` to `/tmp/tars-run-N/`.
- TARS bot (@edu_aipe_s4_tars_bot) is **live in production** for the cohort group. Don't `fly deploy` from a dirty branch.
