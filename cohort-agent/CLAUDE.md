# cohort-agent — TARS deployment

Telegram bot the cohort talks to. Anthropic Managed Agents (Opus 4.7 + memory stores) on fly.io. **Live in production** with ~20 students in `edu-ai-product-engineer-s4` Telegram group.

`AGENTS.md` is a symlink to this file — Codex / Cursor / Gemini / JetBrains agents read the same rules as Claude Code. One source of truth.

**Two different "rules" files in this repo — do not confuse them.**

- `memory_seeds/00-constitution.md` is TARS's runtime system prompt. Shapes what TARS *says* to students. Synced to the agent's `instructions` field by `provision.py`.
- This file (`CLAUDE.md`) is for Claude Code editing TARS's source. Shapes how Claude Code *modifies* TARS. Never reaches the bot.

## Bash commands

- `python provision.py` — idempotent. Re-walks `memory_seeds/`, re-uploads changed files to the cohort-knowledge store, re-syncs the Constitution to the agent's `instructions`. Run after any edit under `memory_seeds/` or to `00-constitution.md`.
- `python memory_writer.py list --prefix /` — list every path TARS sees in cohort-knowledge.
- `python memory_writer.py read /path/to/seed.md` — verify a seed actually loaded.
- `python memory_writer.py write /path /local/file.md` — manual upload (bypasses the audience-boundary filter — prefer `provision.py`).
- `python memory_writer.py delete /path` — remove from store.
- `fly logs --app edu-aipe-s4-tars` — bot not replying → start here.
- `fly ssh console --app edu-aipe-s4-tars` — for `/data/working_memory.db` inspection (sliding-window state).
- `fly deploy` — push to prod. Never from a dirty branch; fly has no easy rollback below 24h.

## Architecture

- `provision.py` is the source of truth for what reaches students. Memory_writer.py is the manual escape hatch — use it for one-off scrubs, not bulk syncs.
- `INSTRUCTOR_ONLY_PATTERNS` in `provision.py` filters `memory_seeds/` before upload. Patterns: `*-design.md`, `*-rubric.md`, `pre-class*`, `*tensions*`, `instructor/*`, `run-sheet*`, `handouts*`, `slide-deck-outline*`. **Anything else under `memory_seeds/` is visible to all 20 students.**
- Two memory stores: `cohort-knowledge` (read-only seeds, `provision.py` writes) and `cohort-learnings` (TARS read-write scratchpad). The Constitution mounts them at distinct prefixes.
- `working_memory.py` uses SQLite with `journal_mode=WAL` on the `tars_data` fly volume mounted at `/data`. Required env: `TARS_DATA_DIR=/data` in prod. Don't write the DB anywhere else — non-volume paths vanish on fly restart. Schema: `working_memory.py:_init_schema` (`recent_messages` + `idx_recent_chat_ts`) — re-read before writing SQL.
- Telegram filter for cohort group: `(filters.TEXT | filters.CAPTION) & filters.Chat(COHORT_GROUP_CHAT_ID) & ~filters.COMMAND`. DMs additionally allow `PHOTO | Document.IMAGE`. Narrowing the filter silently drops modalities to `_dm_unmatched` (no reply at all).
- fly.io VM: `shared-cpu-1x`, 512MB. Hard concurrency 25, soft 20. Roughly 5 concurrent Anthropic streaming sessions before OOM — for >5 simultaneous turns, prefer `passive_log` ingestion over `query_tars`.

## Do not

- **Edit `00-constitution.md` without re-running `provision.py`.** It's the runtime system prompt. Without re-sync, the live bot keeps using the old version.
- **Add a file to `memory_seeds/` without checking it against `INSTRUCTOR_ONLY_PATTERNS`.** Default = visible to all students. Instructor planning artifacts MUST match a filter pattern or live in `instructor/`.
- **Commit `.env`, fly tokens, or anything matching `secrets.baseline`.** `.env.example` ships; `.env` stays local. A leak rotates the prod bot.
- **Drop the audience-boundary section from the Constitution.** That rule is load-bearing — without it, files matching `INSTRUCTOR_ONLY_PATTERNS` that slip past the upload filter would still be quoted.
- **Append the persona signature to non-identity replies** when editing `telegram_bot.py` or any reply formatter. Already a Constitution rule; agents have re-introduced this regression by helpfully adding `signoff = "TARS — cohort 4..."` lines. Read the Identity section of `00-constitution.md` first.
- **Auto-bump persona settings** (Honesty 90 → 80, Humor 30 → 40, Warmth 55 → ?) without tagging a release. These are versioned behavior, not cosmetic.

## Conventions

- Python imports at top of every file (no inline imports unless behind a feature flag).
- venv per checkout: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- `memory_seeds/<path>.md` paths mirror what TARS reads — `memory_seeds/team/cohort-roster.md` ↔ TARS sees `/team/cohort-roster.md`. Don't break the mirror.
- Reply text is asker-language-matched at runtime by TARS itself. Format helpers should pass strings through; do not hardcode language switches.
- New skill ideas, hooks, MCP tools, evals, voice, multi-agent dispatch all belong to S2-S5. They live under `lesson{2,3,4,5}/staging/` until promoted. **`cohort-agent/` stays at S1 capability** until the relevant session airs.

## Common gotchas

- **Webhook URL drift.** python-telegram-bot v21 re-registers the webhook on app startup. If the app's URL changes (rare on fly), the old webhook still points at the dead URL — update `TELEGRAM_WEBHOOK_URL` and restart.
- **`managed-agents-2026-04-01` beta header.** Auto-attached by the anthropic SDK. If you see "unknown beta," `pip install -U anthropic`.
- **Long-running tools timeout silently.** Anthropic Managed Agents tool execution is bounded — if a tool hangs >30s, the turn fails with a generic error. Add explicit timeouts to any HTTP/MCP calls.

## See also

- `memory_seeds/00-constitution.md` — TARS's runtime persona/rules (system prompt, audience boundary, identity)
- `README.md` — human onboarding (quickstart, deploy, status checklist)
- `DEPLOY.md` — fly.io provisioning runbook
- `DIGEST_DESIGN.md` — daily digest pipeline design
- `../CLAUDE.md` — cohort-4 course-level context (TARS as canonical demo)
