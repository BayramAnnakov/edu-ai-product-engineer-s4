# TARS — Cohort 4 Retrieval Agent

Telegram-fronted Claude Managed Agent for `edu-ai-product-engineer-s4`. Persona: TARS (Interstellar). Honesty 90, humor 30. Cites sources by filename. Declines to speculate.

**Architecture:** Anthropic Managed Agents (system prompt = TARS Constitution, model `claude-opus-4-7`, default agent toolset) + Memory Stores (cohort-knowledge read-only seeds + cohort-learnings TARS scratchpad) + Telegram bot (webhook on fly.io).

**Lineage:** forked from `~/GH/onsa-robin/agent_managed/`.

---

## Quickstart (one-time setup)

### 1. Provision the managed agent

Set your Anthropic API key, then run the provisioner:

```bash
cd edu-ai-product-engineer-s4/cohort-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python provision.py
```

This creates the agent, environment, and two memory stores (idempotent). It prints the four IDs you'll set as fly secrets.

### 2. Create the Telegram bot

Talk to `@BotFather` (in your normal Telegram client, or via the `telegram-mcp` MCP):
- `/newbot`
- Name: **TARS — Cohort 4 TA**
- Handle: **`edu_aipe_s4_tars_bot`**
- Save the bot token.

Then add the bot to the cohort group (`edu-ai-product-engineer-s4`, chat_id `-1003721817564`).

### 3. Deploy to fly.io

```bash
fly launch --no-deploy   # or: fly apps create edu-aipe-s4-tars
fly secrets set --app edu-aipe-s4-tars \
    ANTHROPIC_API_KEY=sk-ant-... \
    TELEGRAM_BOT_TOKEN=123:ABC... \
    COHORT_AGENT_ID=agnt_... \
    COHORT_ENVIRONMENT_ID=env_... \
    COHORT_KNOWLEDGE_STORE_ID=memstore_... \
    COHORT_LEARNINGS_STORE_ID=memstore_...
fly deploy
```

The bot's webhook URL is set via `TELEGRAM_WEBHOOK_URL` env var (defaults to `https://edu-aipe-s4-tars.fly.dev/webhook` in `fly.toml`). Telegram-python-bot registers the webhook automatically on startup.

### 4. Smoke test

In the cohort group:
- `/ping` → bot replies "ok"
- `@edu_aipe_s4_tars_bot summarize lesson 1 in 3 bullets` → grounded answer with citations

---

## Day operations

### Post-session transcript ingestion (manual, S1)

After Lesson 1 ends, pull the transcript via the `onsa-meetings` MCP (in a Claude Code session):

> *"Pull today's lesson 1 transcript via onsa-meetings MCP, save it to a local file, then upload to TARS's knowledge store at `/transcripts/lesson-1-2026-05-02.md` using `cohort-agent/memory_writer.py write`."*

Or by hand:
```bash
python memory_writer.py write /transcripts/lesson-1-2026-05-02.md path/to/transcript.txt
```

### Add a new dossier or lesson design

Edit `memory_seeds/<path>.md`, then re-run `python provision.py` (it's idempotent and only updates changed files).

### Inspect what TARS sees

```bash
python memory_writer.py list --prefix /
python memory_writer.py read /team/cohort-roster.md
```

---

## File layout

```
cohort-agent/
├── README.md                       (you are here)
├── provision.py                    (create/update agent, env, memory stores)
├── memory_writer.py                (CLI: read/write/list memory stores)
├── telegram_bot.py                 (webhook bot, runs on fly.io)
├── Dockerfile                      (slim python:3.12)
├── fly.toml                        (app: edu-aipe-s4-tars, port 8080, /health)
├── requirements.txt
├── .env.example
├── memory_seeds/
│   ├── 00-constitution.md          (TARS system prompt; NOT uploaded — set as agent instructions)
│   ├── team/                       (cohort roster — gitignored, instructor-private)
│   ├── lessons/                    (per-session design docs — gitignored, instructor-private)
│   ├── dossiers/                   (planted forensics dossiers — gitignored until session airs)
│   └── transcripts/                (populated post-session — gitignored, may contain PII)
└── (skills/ — not yet wired; drafts staged in `../lesson2/staging/skills/` until S2)
```

---

## TARS as the cohort's living case study

Each session adds one capability to TARS. Students can read TARS's source as a worked example for their own colleague — and `git log cohort-agent/` is literally the curriculum unfolding.

| Session | What lands in TARS | Discipline taught | New paths |
|---|---|---|---|
| **S1** (May 2) | Constitution + memory stores + Telegram bot + post-session manual transcript ingest | **Context** — Constitution as the asset; memory layout; CLI/SDK/runtime portability | `00-constitution.md`, `memory_seeds/`, `provision.py`, `telegram_bot.py` |
| **S2** (May 16) | Real Skills (cohort-search, dossier-creator) + post-message hook (error-to-rule ratchet) | **Harness** — skills as JIT specialization; hooks as event-driven memory updates | `skills/<name>/SKILL.md` made live, `hooks/post_message.py` |
| **S3** (May 30) | onsa-meetings MCP wired into TARS's toolset (auto-pulls transcripts on demand); subagent for "summarize session N" | **Tool / MCP** — TARS becomes a tool-calling agent | `mcp/onsa_meetings.py`, `subagents/session_summarizer.py` |
| **S4** (Jun 13) | Eval suite + multi-agent dispatch + the Swap (a student ships a feature into TARS's harness without warning) | **Eval-driven + multi-agent** — testing recall accuracy, dispatching by question type | `evals/`, `multi_agent/router.py` |
| **S5** (Jun 27) | Voice layer + real-time transcript streaming during live session + Demo Day | **Voice + production** | `voice/`, `streaming/transcript_listener.py` |

**The transcript pipeline alone evolves through every session** — manual → hook → MCP → eval-tested → real-time. That sub-thread is a teaching artifact in itself.

The **cohort 4 GitHub repo's `cohort-agent/` directory is the syllabus**. Each session ends with a commit that adds the new capability. Students can `git diff S1..S2 cohort-agent/` to see what S2 *actually means* in code.

---

## Boundary

- TARS only responds in `COHORT_GROUP_CHAT_ID` (`-1003721817564`). Any other chat: silence.
- Hourly rate limit: `MAX_QUERIES_PER_HOUR=30` (configurable via env).
- Daily API budget cap: `DAILY_API_BUDGET_USD=10.0` (advisory; not yet enforced — S2 territory).
- TARS never grades students or judges work. Those questions get redirected to Bayram or Madina.

---

## When TARS breaks

- **Bot doesn't respond** → check `fly logs --app edu-aipe-s4-tars`. Most common: webhook URL drift (Telegram registers once; if the app restarts and the URL changes, re-register).
- **"TARS not provisioned" reply** → the four `COHORT_*_ID` fly secrets are missing. Re-run `provision.py` locally and set them.
- **Empty answers** → seed files probably aren't synced. Run `provision.py` again.
- **Beta API errors** → `managed-agents-2026-04-01` beta header is set automatically by the SDK. If errors persist, check `pip install -U anthropic` for the latest beta types.

---

## Status

- **Provisioned:** ❌ pending (Bayram runs `python provision.py` once API key is in env)
- **Bot created:** ❌ pending (telegram-mcp + BotFather)
- **Deployed to fly.io:** ❌ pending
- **In cohort group:** ❌ pending
- **First transcript ingested:** ❌ post-S1 (May 2 evening)
