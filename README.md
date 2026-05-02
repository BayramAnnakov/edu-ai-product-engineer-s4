# AI Product Engineer — Cohort 4 (Season 4)

**May 2 → June 27, 2026 · 5 × 2h biweekly · live + recorded · 20 mid+ devs / tech leads**

## The Anchor

**Build Your AI Coding Colleague.** Each student picks one recurring coding task they currently do by hand and ships an AI pair-programmer that does it. Each session adds one capability to the same artifact. By Demo Day, the colleague has been running on real code for ≥14 consecutive days with usage logs proving ≥50% time reduction on the chosen task.

## The 5 Sessions

| # | Date | Discipline | Capability added |
|---|------|-----------|------------------|
| 1 | May 2 | Context | CLAUDE.md + Plan-Mode discipline |
| 2 | May 16 | Skill + Harness | Custom skill + hook (error-to-rule ratchet) |
| 3 | May 30 | Tool | MCP integration + agent loop |
| 4 | Jun 13 | Multi-agent + Eval + **Harness Swap** | Evals + autoresearch + ship in a stranger's harness |
| 5 | Jun 27 | Voice + Production | Voice layer + live-streamed Demo Day |

## What's in this repo

- `cohort-agent/` — **TARS**, the cohort's live AI assistant. Telegram bot on Anthropic Managed Agents. Built and grown live across all 5 sessions; `git log cohort-agent/` *is* the curriculum.
- `lesson1/block2-stochasticity-demo/` — the Block 2 stochasticity demo (Lesson 1). Clone this repo, `cd cohort-agent`, run the demo prompt.
- `CLAUDE.md` — working notes for the cohort.

## Cross-Session Threads

- **Persistent Cohort Agent (TARS)** — fed every transcript, CLAUDE.md, error from the cohort
- **Cohort Error-to-Rule Dataset** — published as `cohort-4-rules` package by S5
- **Retrieval Quiz** — 10 min at start of every session (no Claude open)
