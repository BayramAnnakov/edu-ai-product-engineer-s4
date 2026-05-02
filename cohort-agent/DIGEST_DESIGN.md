# TARS Digest — Design

**Status:** V1 design, ship for S1 (May 2, 2026). V2/V3 noted as future work.

**Goal:** TARS periodically reflects on cohort group messages and stores key learnings + digests. By Demo Day, querying TARS about *"what happened in week 3?"* returns a grounded summary.

**Non-goals (V1):** real-time learning extraction, per-event triggers, eval suite, learnings promotion workflow. All deferred to S2-S4.

---

## Architecture — three layers

```
   ┌───────────────────────────┐
   │  Telegram cohort group    │
   │  (~20-50 msgs/day)        │
   └─────────────┬─────────────┘
                 │ every text msg
                 ▼
   ┌───────────────────────────┐  ← V1 ships this
   │  Layer 1: RAW LOG         │
   │  /data/messages-DATE.jsonl│
   │  (fly volume, append-only)│
   │  cheap, never lost        │
   └─────────────┬─────────────┘
                 │ daily 23:00 PT
                 ▼
   ┌───────────────────────────┐  ← V1 ships this
   │  Layer 2: DIGEST          │
   │  Claude Messages API call │
   │  → /digests/YYYY-MM-DD.md │
   │  in cohort-learnings store│
   │  TARS-queryable, structured│
   └─────────────┬─────────────┘
                 │ weekly (S2+)
                 ▼
   ┌───────────────────────────┐  ← V2 (S2)
   │  Layer 3: LEARNINGS       │
   │  /learnings/staged/       │
   │  one-insight-per-file     │
   │  Bayram promotes weekly   │
   └───────────────────────────┘
```

The three layers exist for cost and signal-to-noise reasons:
- **Raw log** is cheap to write, expensive to query (lots of noise). Lives outside the agent's working memory.
- **Digest** is the daily synthesis — what TARS will actually reach for during recall.
- **Learnings** are the gold — distilled patterns Bayram has reviewed and promoted.

V1 ships layer 1 + 2. Layer 3 lands in S2 alongside the harness lesson (the "error-to-rule ratchet" pattern).

---

## Layer 1 — Raw message log (V1)

### What gets logged

Every message in the cohort group (chat_id `-1003721817564`) that's a text message. Privacy mode is OFF, so the bot sees all messages.

### Format (JSONL, one record per line)

```jsonl
{"ts":"2026-05-02T05:32:20Z","msg_id":1146455,"user_id":54129318,"username":"bayram","first_name":"Bayram","text":"what is cohort 4? and who is TARS?","reply_to":null}
{"ts":"2026-05-02T14:01:03Z","msg_id":1146470,"user_id":...,"username":"...","first_name":"Ruslan","text":"я добавил dossier в свою папку","reply_to":null}
```

Filter out:
- Service messages (joins, leaves, pinned changes)
- Empty/null text (photos with no caption)

Capture but flag separately:
- Bot's own messages (we already log these to fly's log; no need to duplicate to JSONL)
- Forwarded messages (note `forward_from` in the JSONL)

### Storage location

`/data/messages-YYYY-MM-DD.jsonl` on a fly volume. New file per day (UTC midnight rotation). Why per-day:
- Daily digest reads exactly one file
- Easy retention (delete files older than N weeks if size becomes a concern)
- Crash-safety: append-only, no chance of corrupting the entire history

### fly.toml volume mount

```toml
[mounts]
  source = "tars_data"
  destination = "/data"
```

Run once: `fly volumes create tars_data --app edu-aipe-s4-tars --size 1 --region sjc`. 1 GB is wildly more than needed (cohort generates ~500 KB total over 8 weeks even with verbose chatter).

### Code surface

```python
# In telegram_bot.py — new handler
async def passive_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None or not msg.text:
        return
    if not (chat := update.effective_chat) or chat.id != COHORT_GROUP_CHAT_ID:
        return
    record = {
        "ts": msg.date.isoformat(),
        "msg_id": msg.message_id,
        "user_id": msg.from_user.id if msg.from_user else None,
        "username": msg.from_user.username if msg.from_user else None,
        "first_name": msg.from_user.first_name if msg.from_user else None,
        "text": msg.text,
        "reply_to": msg.reply_to_message.message_id if msg.reply_to_message else None,
    }
    path = Path(f"/data/messages-{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl")
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

Handler registration: `MessageHandler(filters.TEXT & filters.Chat(COHORT_GROUP_CHAT_ID), passive_log)` — runs IN ADDITION to the query handlers (which only fire on mentions/replies). Group order matters; passive_log runs first via `group=-1` (handler priority).

### Constraints / risks

- **fly volume single-region.** Volume lives in `sjc`. If the bot moves to another region, the log is gone. Acceptable for V1 — cohort uses one region.
- **No PII review.** Anyone who can `fly ssh console` can read the raw log. Same trust boundary as the cohort group itself (Bayram + Madina are admins; cohort members in the group). Bayram should disclose in Block 1.

---

## Layer 2 — Daily digest (V1)

### When

23:00 Pacific time, every day. Catches the full day's activity (Bayram's work-day perspective). Russia students post in their evening (12pm-4pm PT) and that's all included.

Implemented via python-telegram-bot's `JobQueue.run_daily(callback, time=time(23, 0, tzinfo=ZoneInfo("America/Los_Angeles")))`.

If the bot crashes or restarts mid-day, the digest job is missed for that day — that's acceptable. Backup: a CLI command `python digest.py --date 2026-05-02` for manual catch-up.

### How (Claude Messages API, not Managed Agents)

A digest is a one-shot synthesis, not an interactive agent loop. Cheaper and faster via direct Messages API:

```python
# In digest.py
from anthropic import Anthropic

DIGEST_SYSTEM = """You are a cohort-class digest writer. Read the day's
Telegram messages from the AI Product Engineer cohort 4 group and produce
a structured Markdown digest.

Sections (omit any with no content):
1. **Questions** — what students asked (group similar)
2. **Confusions** — places students stumbled or asked clarification
3. **Dossiers shared** — links/mentions of colleague-target.md or constitution updates
4. **Errors discussed** — failures students hit during homework
5. **Patches shared** — Constitution rules students added
6. **Decisions** — Bayram's announcements, schedule changes
7. **Notable quotes** — verbatim, attribute by first_name

Filter ruthlessly. Drop greetings, acknowledgments, technical chatter
unrelated to the cohort goals. Aim for SIGNAL not coverage.

Output Markdown only. ~400-800 words. No preamble."""


def digest_for(date_str: str) -> str:
    client = Anthropic()
    log_path = Path(f"/data/messages-{date_str}.jsonl")
    if not log_path.exists():
        return ""
    raw = log_path.read_text(encoding="utf-8")
    messages_block = raw  # raw JSONL is fine; the model parses it
    user_msg = (
        f"Cohort 4 messages for {date_str} (UTC). Each line is a JSON record:\n\n"
        f"{messages_block}\n\n"
        f"Produce the digest per the system prompt."
    )
    resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",  # cheaper than opus for synthesis
        max_tokens=2000,
        system=DIGEST_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text
```

Then write to memory store:

```python
from memory_writer import write
write("learnings", f"/digests/{date_str}.md", digest_text)
```

### Cost estimate

- Daily input: ~30 messages avg × 100 chars = ~3000 chars ≈ ~750 input tokens
- Output: ~600 word digest ≈ ~800 output tokens
- Sonnet 4.5 pricing: ~$0.003/1K in + ~$0.015/1K out = ~$0.014 per digest
- Over 8-week cohort: ~$0.80 total. Negligible.

### Failure modes

- **Empty day** (no messages or only bot replies): skip silently, don't write empty digest.
- **Anthropic API error**: log, alert on next day's bot startup, retry manually via CLI.
- **Memory store write fails**: keep the digest text in `/data/digests-fallback/` on the volume; sync next day.

---

## Layer 3 — Distilled learnings (V2 / S2)

Once weekly digests pile up, a second-pass reflection extracts patterns across days into one-insight-per-file under `/learnings/staged/`. Bayram reviews staged learnings, promotes the keepers to `/learnings/promoted/`.

This is **S2 territory** because S2 is "Skill + Harness" — the error-to-rule ratchet. The digest-to-learnings promotion is exactly that pattern at cohort scale. Pre-building it would steal S2's reveal.

V2 placeholder: `digest.py weekly` produces `/learnings/staged/weekly-WW.md` candidates.

---

## Privacy & disclosure (Block 1 disclosure)

In Block 1's contract, Bayram mentions explicitly:

> *"TARS sees every message in this group and digests them daily into `/digests/`. Querying TARS later about "what happened in week 3" will reach those digests. If you don't want something logged — DM me, and I'll delete it. Default: assume everything in the cohort group becomes part of the cohort's collective memory."*

Add to `lesson1/lesson-1-design.md` Block 1 (60-sec mention).

The Telegram group is invite-only (Bayram is owner, Madina is admin), so this is consent-by-context: members joined for a class with explicit AI tooling, and the disclosure makes the loop visible.

---

## Connection to S1-S5 staircase (the meta-payoff)

The digest is itself a teaching artifact across the cohort:

| Session | Digest evolution | Teaching beat |
|---|---|---|
| **S1** (May 2) | Passive logger + daily Claude Messages digest. Manual CLI for catch-up. | Context — "TARS sees, TARS reflects." |
| **S2** (May 16) | Digest writes one-insight-per-file to `/learnings/staged/`. **Error-to-rule ratchet** lives here — students see the pattern at cohort scale. | Harness — "the ratchet." |
| **S3** (May 30) | Digest-trigger becomes an MCP-style hook (post-session, not just daily). | Tool/MCP — events fire reflections. |
| **S4** (Jun 13) | Eval suite asks: *"did the digest correctly capture this fact?"* | Eval-driven. |
| **S5** (Jun 27) | Real-time digest streaming during the live session. | Production. |

Students can `git diff S1..S2 cohort-agent/digest.py` and see what S2 *means*.

---

## V1 implementation plan (ship today)

Files to add:
- `digest.py` — the digest worker (callable from JobQueue or CLI)
- Update `telegram_bot.py` — add `passive_log` handler + JobQueue daily schedule
- Update `fly.toml` — add `[mounts]` for `/data`
- Update `Dockerfile` — ensure `/data` exists and is writable by `tars` user
- Update `requirements.txt` — `tzdata` (for ZoneInfo)

CLI shape:
```bash
# Manual catch-up for a missed day
python digest.py --date 2026-05-02

# Test digest with a specific log file (no API call)
python digest.py --dry-run --log /data/messages-2026-05-02.jsonl

# What the JobQueue calls each night
python digest.py --today
```

Volume create (one-time):
```bash
fly volumes create tars_data --app edu-aipe-s4-tars --size 1 --region sjc
```

After volume creation, redeploy. Bot restarts, mount lands at `/data`, passive logger starts writing.

First digest: ~23:00 Pacific tonight (May 2), capturing Lesson 1 + post-session chatter. Available to TARS by tomorrow morning at `/mnt/memory/cohort-learnings/digests/2026-05-02.md`.

---

## Things deliberately NOT in V1

- **Per-event triggers** — *"a student posted a dossier link → digest it now"*. S2 territory.
- **Cross-day pattern extraction** — *"this is the third time someone asked about verification."* S2-S3 territory.
- **Quality eval** — *"did the digest accurately capture day X?"* S4 territory.
- **Voice digest** — *"narrate yesterday's digest as a podcast."* S5 territory.
- **Per-student digests** — *"what did Ruslan ask this week?"* Privacy/scope question; defer.

The V1 digest is the simplest thing that could possibly work. Each future capability lands in the session where it belongs pedagogically.
