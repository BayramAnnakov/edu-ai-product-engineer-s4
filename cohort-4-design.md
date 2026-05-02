# Cohort 4 — High-Level Design

**Dates:** May 2 → June 27, 2026 (5 × 2h biweekly)
**Cohort:** 20 mid+ devs / tech leads
**Format:** live sessions, 14-day gaps with daily artifacts, fluency exam, live-streamed Demo Day
**Anchor:** Build Your AI Coding Colleague

---

## The Master Frame

Each student picks ONE recurring **coding** task they currently do by hand (PR review of a kind, test scaffolding, migration of a kind, refactor pattern, issue triage, bug investigation, schema evolution, doc-syncing, deployment narration). They ship an AI pair-programmer that does it. Each session adds **one capability** to the same artifact. By Demo Day, the colleague has been running on real code for ≥14 consecutive days with usage logs proving it cut the task time ≥50%.

The artifact = **CLAUDE.md + skills + hooks + MCPs + agents + evals + voice layer**, all coherent for one purpose, on one codebase the student picked (personal repo, OSS repo they care about, or shared cohort sample).

**Why this anchor wins:**
- Real-stakes (it's their own pain, observable in their daily work)
- No employer-IP friction (they pick the codebase)
- Coherent artifact (one colleague, six capabilities) — not six disconnected toys
- Demos itself ("watch this colleague write code on my real repo")
- Career-portable (they leave with a pair-programmer they actually use)
- Maps cleanly to the website's 5 sessions

---

## The Pass Contract (announced Session 1)

Pass IF EITHER:
- **(a) Deployed Colleague:** AI coding colleague has run for ≥14 consecutive days with logs proving real usage and ≥50% time reduction on the chosen task, OR
- **(b) Fluency Exam:** 90-min recorded exam — take an unfamiliar OSS repo, set up a CLAUDE.md harness, ship an agent-assisted PR with a passing eval. Public rubric.

Refund only if both fail. Refund offer is a **front-end selection filter**, not a back-end safety net.

---

## The 5-Session Matrix

| # | Date | Discipline | Capability added | Pattern-break shape | Bayram's role | Daily artifact (gap) | Retrieval quiz next session |
|---|------|-----------|------------------|---------------------|---------------|----------------------|------------------------------|
| 1 | May 2 | Context | CLAUDE.md + Plan-Mode discipline | Bayram opens by reading 3 students' GitHub dossiers live, unprompted | Improv coach | 1 commit/day to colleague repo | "3 things in your CLAUDE.md from memory" |
| 2 | May 16 | Skill + Harness | 1 custom skill + 1 hook (error-to-rule ratchet) | Live forensics — Bayram builds a rule LIVE from a student's gap-week fail tape | Detective | 1 skill/hook iteration/day | "Hook lifecycle on paper, no Claude" |
| 3 | May 30 | Tool | 1 MCP integration + agent loop | Improv wiring — students nominate which system, Bayram wires live in <10 min | Improv tool-wirer | 1 agent commit/day | "Draw your agent's loop" |
| 4 | Jun 13 | Multi-agent + Eval + **The Swap** | Evals + autoresearch + harness swap | THE HARNESS SWAP — anonymized, ship a feature in someone else's CLAUDE.md/skills | Spectator + referee | Work in your stranger's harness | "What broke when you used someone else's setup?" |
| 5 | Jun 27 | Voice + Production + Demo Day | Voice layer + Demo Day | Live-streamed adversarial demos + voice stunt + critic live-review | Show host | (Demo prep + recorded fluency exam window) | (final exam, not retrieval) |

---

## Per-Session Detail

### S1 — May 2 — Day One: Context Engineering

**Aim:** Every student leaves with (a) a chosen colleague target with a measurable baseline, (b) a Day-1 CLAUDE.md committed to the cohort repo, (c) the contract signed.

**Hook (0:00-0:15):** Bayram pre-runs an autoresearch agent on each student's public GitHub before class. Opens by reading 3 dossiers aloud — what kind of engineer the student appears to be, what their commit history says about how they work. Unprompted. Establishes that coaching is real and personal in the first 10 minutes (Wes Kao mechanic).

**Body:**
- Demo: same task, two CLAUDE.md regimes (monolithic vs. layered, generic vs. team-specific). Same model, same prompt, visibly different output. (Lifted from corporate program W1.)
- Concept: Plan Mode + verification discipline. Why same prompt yields different code.
- Exercise: Each student picks their colleague target (recurring coding task), names it, baselines it (current time/week, current pain). Writes Day-1 CLAUDE.md in cohort repo. Bayram bounces between live, critiques in chat.
- Live: 3 students read their CLAUDE.md aloud while the cohort critiques (Feynman mechanic — "you don't know a thing until you can hand it to a stranger and watch them not break").

**Close (1:50-2:00):**
- Announce: harness swap at S4, fluency exam window in S5 gap, contract terms.
- Public commitment: each student posts in cohort Slack — "My colleague target: X. Current weekly time: Yh. Target by Demo Day: Y/2."

**S1 risk:** Students freeze on target choice. Mitigation: pre-class survey asks for 3 candidate targets so we narrow live.

---

### S2 — May 16 — First PR Review: Skill + Harness Engineering

**Aim:** Every student leaves with 1 custom skill + 1 hook running on their colleague.

**Hook (0:00-0:20):** Retrieval quiz (10 min, no Claude). Then: 1-2 student fail tapes from the gap. Bayram picks the most interesting failure and announces it'll be the live forensics case.

**Body — Live Forensics:**
- Bayram performs the **error-to-rule ratchet** live, on the student's actual gap-week failure. Doesn't know what the failure will be in advance. Reverse-engineers the bug → writes the rule → installs it as a hook → tests it. ~25 minutes. The pedagogy IS the demo.
- Concept: skills as encoded process; three layers of defense (skills/hooks/CI).
- Exercise: each student installs a starter skill template, customizes it for their colleague target, gets it running. Then adds a Stop or PostToolUse hook.
- Live: 2 students demo their skill running. Cohort agent (already collecting transcripts since S1) auto-grades trajectory.

**Plant for S4:** "Your CLAUDE.md and skills will be used by a stranger in S4. Build accordingly." (Productive constraint installed early — Feynman insight.)

**Close:** Public commitment + preview S3.

**Cohort artifact spawned:** the `cohort-4-rules` dataset — a hook installed in S2 captures every Claude failure on every student's machine into a shared corpus. By S5 this becomes a public package.

**S2 risk:** Skills/hooks feel abstract; students nod, don't build. Mitigation: starter templates pre-shipped; everyone leaves with running code, not understanding.

---

### S3 — May 30 — First On-Call: Tool Engineering

**Aim:** Every student's colleague is connected to ≥1 real system and doing ≥1 autonomous thing.

**Hook (0:00-0:20):** Retrieval quiz. Then: cohort leaderboard recap — token efficiency, streak status, shipping velocity.

**Body — Improv MCP Wiring:**
- Bayram doesn't know in advance which MCP he'll demo. Students nominate from a pre-verified shortlist (GitHub, Linear, Postgres, Sentry, Slack, custom). Bayram wires it live in <10 minutes. (If it breaks, that's also pedagogy.)
- Concept: chains vs. agents; the agent loop; reflection pattern; subagents for specialized roles.
- Exercise: each student wires their colleague to ≥1 real system. Pre-verified fixtures available for everyone (don't fight auth on workshop time).
- Live: 2 students demo their colleague reading from a real system and acting on it.

**Mid-cohort dry run:** During S3-S4 gap, Bayram orchestrates a low-stakes anonymous CLAUDE.md swap (no full repo, just the markdown). Lets him spot harness-swap collapse modes before S4.

**Close:** Public commitment + preview the harness swap.

**S3 risk:** MCP setup auth is fiddly. Mitigation: pre-verified fixtures; pick from the list, don't roll your own that day.

---

### S4 — June 13 — The Swap: Multi-agent + Eval + **THE HARNESS SWAP**

**Aim:** Every student has experienced their colleague being used by a stranger AND has evals running. This is the session people will tell their friends about.

**Hook (0:00-0:25):** Retrieval quiz. Then THE SWAP IS LIVE. Random anonymized assignment is published in Slack: each student gets another student's CLAUDE.md + skills + hooks (no identifying info). They have until 1:30 to ship a feature in their colleague's domain using the stranger's setup.

**Body — Spectator Bayram:**
- 0:25-1:30 — students work in strangers' harnesses. Bayram bounces between, mostly observing. AI co-instructor scores trajectory in real time.
- 1:30-1:55 — debrief. What broke? What was tacit in your harness that you didn't realize? Blind guess-whose-harness-this-was reveals at the end.
- 1:55-2:00 — concept overlay (delivered as debrief, not lecture): multi-agent orchestration, evals as harness fitness tests, autoresearch as overnight optimization, prompt-injection patterns. ALL of these are now experienced, not lectured.

**Why this works:** This session is structured so that the EXPERIENCE precedes the CONCEPT. Students felt the pain of someone else's harness for 60 minutes; the multi-agent / eval / autoresearch concepts land as solutions to felt problems instead of frameworks to memorize.

**Plant for S5:** Each student schedules their fluency exam slot in the S4-S5 gap.

**S4 risk:** Swap collapses into chaos (students stuck, harnesses incompatible). Mitigations: dry run in S3-S4 gap; allow students to fall back to their own harness after 30 min if completely stuck (they pay a token cost); keep it anonymous to remove ego.

---

### S5 — June 27 — Demo Day: Voice + Production + Live Adversarial

**Aim:** The deployed colleague demonstrates ≥14 days of real usage. Public artifact published. Cohort 5 funnel built.

**Pre-S5 (gap):**
- Fluency exam window (90 min, recorded, public rubric, scheduled slots)
- Voice layer added to each colleague (STT→LLM→TTS or Realtime API)
- Demo Day dress rehearsal: 3 student volunteers, full production stack tested

**Demo Day format (2h, live-streamed):**
- 0:00-0:10 — Open + Hashimoto (or swyx / simonw — pick the one whose framework is closest to the cohort artifact; Hashimoto's error-to-rule ratchet is literally in S2, so he's the structural fit)
- 0:10-0:11 — 60-second cohort hype reel auto-clipped from the streak tracker
- 0:11-1:30 — 4-min demos × 20 students. Per student: 60s "what I built" → 60s live demo (colleague running on real data) → 60s **failure tape** (90s of the worst breakage during the cohort) → 60s critic question
- 1:30-1:50 — Hashimoto deep-review on 3 selected colleagues, picked live by audience vote
- 1:50-1:58 — **The voice stunt:** Bayram dials a real number; a student's voice agent handles a real conversation. Single take. No retries. (If it fails, that's the demo.)
- 1:58-2:00 — Top-3 announce, group photo, livestream archive locked

**Stakes attached for top-3:** Onsa interview / paid bounty / public intro. Real, not theatrical.

**S5 risk:** Production fails on live stream. Mitigations: dress rehearsal mid-gap; pre-recorded backup of voice stunt; bandwidth-isolated demo machines.

**Alt format if N=20 too tight:** split into two parallel rooms with two critics; longer per-student time. More logistically expensive but gives every student deeper feedback.

---

## Cross-Session Threads (the "AI as co-instructor" weaving)

### 1. Persistent Cohort Agent (S1 → S5)
Fed every transcript, every CLAUDE.md, every error. By S4 it knows more about the cohort than Bayram does. Used by students for self-debugging. Used by Bayram in S5 to surface "the three things this whole cohort got wrong all term."

### 2. Cohort Error-to-Rule Dataset (S2 → S5)
Hook installed in S2 captures every Claude failure on every student's machine into a shared corpus. By S5 this is published as `cohort-4-rules` — a public package. Cohort-as-curriculum made literal. Recruiting tool for Cohort 5.

### 3. Trajectory-Graded Commits (S2 → S5)
Each gap-day commit auto-scored on token efficiency, tool-call economy, harness fitness. Public leaderboard. (Karpathy's "the trace IS the grade.")

### 4. Daily Streak + Peer-Review-as-Currency (S1 → S5)
1 commit/day to cohort repo. Miss a day → review 2 peers' PRs to earn a freeze token. Public streak visible. No money, no decrement (per Bayram's call) — social proof + peer-pressure carry the load.

### 5. Retrieval Quiz at Session Start (S2-S5)
10 minutes, no Claude, written. Non-negotiable (Oakley's spacing-effect math — 14-day gaps are past the forgetting cliff without retrieval scaffolding).

### 6. 9am Slack Streak Post (every gap day)
"Yesterday: who shipped, who didn't, who's on streak, leaderboard delta." One ping per day, automated, signed by the cohort agent.

---

## Bayram's Role per Session — the boredom killer

| Session | Bayram's role | Why fresh |
|---|---|---|
| S1 | Improv coach | Reading dossiers — different per cohort, fresh per student |
| S2 | Detective | Building a rule LIVE from an unknown failure |
| S3 | Improv tool-wirer | Doesn't know which MCP until 30s before |
| S4 | Spectator + referee | Watches the swap unfold; debriefs; the work isn't his |
| S5 | Show host | Banter, emcee, voice stunt — performance energy, not pedagogy energy |

5 different cognitive shapes. None is "deliver the same slides as Cohort 3."

---

## The Fluency Exam (the third pass-path; held in S4-S5 gap)

- 90 minutes, recorded
- Scheduled slots (proctored async via recording)
- Public rubric released Day 1
- Each student gets a randomly assigned unfamiliar OSS repo from a curated list
- Task: set up a CLAUDE.md harness for the new repo, ship a small feature with a passing eval, narrate design choices on camera
- Scoring: correctness 40% / trajectory + agent-economy 30% / CLAUDE.md fitness 20% / failure-recovery 10%
- Recordings released to all students (the artifact has half-life — Cohort 5 watches the tape)

---

## What Locks Tomorrow (S1, irreversible once announced)

- The contract: Deployed Colleague (≥14 days) OR Fluency Exam → pass; refund if neither
- The anchor: Build Your AI Coding Colleague (one task, one artifact, six capabilities across 5 sessions)
- The harness swap pre-announce (so students design for stranger-readability from Day 1)
- The cohort error-to-rule dataset collection (hook ships S2, but consent collected S1)
- Daily commit + peer-review-as-currency mechanic
- Retrieval quiz format

## What Stays Reversible

- Specific demo-day format (lock by S4)
- Which surprise critic (lock 2 weeks out — confirm with Hashimoto or fallback)
- Exact streak rules (tune from S1-S2 data)
- Whether to split Demo Day into 2 parallel rooms (decide based on demos quality at S4)

---

## One-line summary

**One coherent artifact (the AI coding colleague), built across 5 sessions where each adds one capability, anchored by daily commits and a harness swap at S4, capped by a live-streamed adversarial Demo Day with the actual person whose framework is in the curriculum (Hashimoto) live-reviewing the work.**
