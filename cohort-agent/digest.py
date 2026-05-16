# pyright: reportAttributeAccessIssue=false
"""Daily digest of cohort 4 group messages.

Reads /data/messages-YYYY-MM-DD.jsonl (raw passive log), calls Claude
Messages API to produce a structured digest, writes to the cohort-learnings
memory store at /digests/YYYY-MM-DD.md.

Callable from python-telegram-bot's JobQueue (run_daily) and as a CLI:
    python digest.py --today
    python digest.py --date 2026-05-02
    python digest.py --dry-run --date 2026-05-02
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from anthropic import Anthropic

from tg_format import markdown_to_telegram_html

logger = logging.getLogger("tars.digest")

DIGEST_MODEL = "claude-sonnet-4-5-20250929"
DATA_DIR = Path(os.environ.get("TARS_DATA_DIR", "/data"))
KNOWLEDGE_STORE_ID = os.environ.get("COHORT_KNOWLEDGE_STORE_ID", "").strip()
COHORT_GROUP_CHAT_ID = int(os.environ.get("COHORT_GROUP_CHAT_ID", "-1003721817564"))
RETRO_TIMEZONE = ZoneInfo("America/Los_Angeles")

DIGEST_SYSTEM = """You are the cohort-class digest writer for cohort 4 of \
Bayram Annakov's AI Product Engineer course. Read the day's Telegram \
messages and produce a structured Markdown digest.

Each JSONL record has:
- `msg_id` (int, Telegram message id) — REQUIRED in citations, see below
- `text` (string, may be empty if attachment-only)
- `attachments` (array of tags like `photo`, `document:Constitution.md`, `voice:45s`, `poll:...`)
- `reply_to` (msg_id this replies to)
- `forward_from` (set if forwarded)
- `first_name` (display name)

# msg_id citations (REQUIRED for individually-attributable items)

When citing questions, confusions, decisions, dossiers, errors, patches, or quotes, \
append the source `msg_id` in the form `(msg <id>)`. If a question and its answer \
live in separate messages, cite both: `(question: msg 38; answer: msg 40)`. The \
weekly retro converts these into Telegram message links so students can jump to \
the original conversation.

ONLY use msg_ids you actually see in the JSONL. NEVER invent or guess. If a \
thread is unclear, cite only what you can verify.

Themes / "what was discussed" can omit msg_ids since they span many messages.

# Attachments

When a message has attachments, NOTE them in the relevant digest section. For \
example: *"<first_name> shared a screenshot — likely a Plan Mode trace (msg <id>, \
photo, no caption)"* or *"<first_name> sent a 45s voice note in reply to Bayram \
(msg <id> → <id>)."* Substitute real `first_name` and `msg_id` values from the \
JSONL. You don't have access to attachment contents; describe what you can infer \
from type + surrounding text.

# Sections (omit any with no content)

1. **Questions** — what students asked. Group similar. Cite `(msg <id>)` per question.
2. **Confusions** — places students stumbled, asked clarification, or got stuck. Cite.
3. **Dossiers shared** — colleague-target.md links/mentions, Constitution updates, document attachments. Cite.
4. **Errors discussed** — failures students hit during homework. Cite.
5. **Patches shared** — Constitution rules students added or modified. Cite.
6. **Decisions** — Bayram's announcements, schedule changes, scope shifts. Cite.
7. **Attachments** — non-trivial files/photos/voice notes shared (skip stickers, location pins, casual reaction GIFs). Cite.
8. **Notable quotes** — verbatim, attribute by `first_name`. ≤3 quotes. Cite.

# Filter ruthlessly — drop

- Greetings, acknowledgments, "thanks"
- Off-topic banter (jokes, weather, etc.)
- Technical chatter unrelated to cohort goals
- Stickers, GIFs, casual emoji-only replies

Aim for SIGNAL not coverage. ~400-800 words. Output Markdown only — no preamble.

Format the file like this:

```
# Cohort 4 Digest — YYYY-MM-DD

## Questions
- <first_name> (msg <id>): one-line summary. <answerer> replied (msg <id>) with the response shape.
- ...

## Confusions
- ...

(etc. — omit empty sections entirely)
```
"""


def log_path(date_str: str) -> Path:
    return DATA_DIR / f"messages-{date_str}.jsonl"


def digest_for(date_str: str) -> str | None:
    """Generate the digest text for a single day. Returns None if no log."""
    path = log_path(date_str)
    if not path.exists():
        logger.info("no log for %s at %s", date_str, path)
        return None

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        logger.info("log for %s is empty", date_str)
        return None

    line_count = raw.count("\n") + 1
    logger.info("digesting %d messages for %s", line_count, date_str)

    client = Anthropic()
    user_msg = (
        f"Cohort 4 messages for {date_str} (UTC). Each line is a JSON record:\n\n"
        f"{raw}\n\n"
        f"Produce the digest per the system prompt. The date heading must be {date_str}."
    )
    resp = client.messages.create(
        model=DIGEST_MODEL,
        max_tokens=2000,
        system=DIGEST_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text  # type: ignore[union-attr]


def write_digest(date_str: str, text: str) -> None:
    """Upload the digest to the knowledge memory store."""
    if not KNOWLEDGE_STORE_ID:
        sys.exit("COHORT_KNOWLEDGE_STORE_ID not set")
    client = Anthropic()
    path = f"/digests/{date_str}.md"

    # Narrow the list to /digests/ to avoid scanning the whole store.
    page = client.beta.memory_stores.memories.list(
        memory_store_id=KNOWLEDGE_STORE_ID,
        path_prefix="/digests/", depth=10, order_by="path",
    )
    existing_id: str | None = None
    existing_sha: str | None = None
    for m in (page.data if hasattr(page, "data") else page):
        if getattr(m, "path", "") == path:
            existing_id = getattr(m, "id", None)
            existing_sha = getattr(m, "content_sha256", None)
            break

    if existing_id:
        client.beta.memory_stores.memories.update(
            memory_id=existing_id, memory_store_id=KNOWLEDGE_STORE_ID, content=text,
            precondition=(
                {"type": "content_sha256", "content_sha256": existing_sha}
                if existing_sha else None
            ),
        )
        logger.info("updated %s", path)
    else:
        client.beta.memory_stores.memories.create(
            KNOWLEDGE_STORE_ID, path=path, content=text,
        )
        logger.info("created %s", path)


async def run_daily_job(_context) -> None:
    """JobQueue callback. Digests the PT calendar day that's just closing.

    Job fires at 23:00 PT. We read messages-<today-PT>.jsonl which now contains
    a full PT day's worth of records (passive_log was switched to bucket by PT
    date for exactly this — see prior incident note in 2026-05-11).
    """
    today_pt = datetime.now(RETRO_TIMEZONE).strftime("%Y-%m-%d")
    try:
        text = digest_for(today_pt)
        if text:
            write_digest(today_pt, text)
            logger.info("digest written for %s", today_pt)
        else:
            logger.info("no messages for %s, skipping digest", today_pt)
    except Exception:
        logger.exception("digest job failed for %s", today_pt)


# --- Weekly retrospective -------------------------------------------------

WEEKLY_RETRO_SYSTEM = """You are TARS, the cohort 4 AI teaching assistant for \
Bayram Annakov's AI Product Engineer course. You are writing the **Sunday \
weekly retrospective** post for the cohort 4 Telegram group.

You will receive recent digest content (daily digests + workshop supplements + \
backfills) and a list of internal answer-file slugs you can route questions to. \
Synthesize into ONE short post for the group chat with this structure (omit any \
section with no content):

```
*Эта неделя в когорте 4 — YYYY-MM-DD*

*Главное:* 1-2 sentences. Frame as what the COHORT should be doing right now — \
the next concrete action. NOT what TARS is. NOT what Bayram announced. \
Example: "До S2 две недели. Выберите задачу, соберите v0, используйте 2 раза. \
Спросите меня про ДЗ-1, если не до конца понятно, что делать."

*Открытые вопросы* (≤ 3 bullets, name asker by first_name):
- Format: `Asker — short version of question — [link to question msg] → [link to live answer if any] — спросите меня про "<тему>"`.
  • The digest cites source messages as `(msg <N>)` or `(question: msg <N>; answer: msg <M>)`. \
Convert each cited msg_id into a Telegram link using the link base provided in the user message. \
Format the inline link as `[вопрос](<base>/<N>)` and `[ответ Bayram](<base>/<M>)`.
  • Skip the link if no msg cite is present in the source (don't fabricate IDs).
- STATUS RULES (in priority order):
  • If the question topically matches one of the available answer slugs, append \
"спросите меня про <тему>" — where <тему> is a SHORT NATURAL PHRASE a student would \
type, NOT the file path. Examples: hw1-deep → "ДЗ-1" or "домашку"; \
read-only-modes → "read-only"; harness-preview → "harness"; pick-your-task → \
"выбор задачи"; pre-work-for-s2 → "что принести на S2".
  • If answered live in a workshop, status is "разобрано в S<N>".
  • If pending a future session, status is "ждём S<N> (<date>)".
  • Use "статус неизвестен" ONLY when none of the above apply.
- NEVER write a file path like "/answers/foo" in the post — students cannot \
navigate to those; they reach the content by asking you.

*Что обсуждали:* ≤ 3 bullets, themes (not message-by-message).

*Полезные ресурсы из чата:* ≤ 3 links shared by students this week. Include URL.

*Впереди:* date + topic of next workshop + what to bring. Use the COHORT SCHEDULE \
below — do NOT say "не указано в дайджесте" if the schedule covers it.
```

# COHORT SCHEDULE (biweekly Saturdays — stable, use this in "Впереди")

| # | Date       | Topic                                |
|---|------------|--------------------------------------|
| 1 | 2026-05-02 | Context (Constitution, memory seeds) |
| 2 | 2026-05-16 | Skill + Harness                      |
| 3 | 2026-05-30 | Tool / MCP                           |
| 4 | 2026-06-13 | Multi-agent + Eval + The Swap        |
| 5 | 2026-06-27 | Voice + Production + Demo Day        |

Compute "next session" as the smallest scheduled date strictly after today's date.

# TELEGRAM MARKDOWN — strict rules (parse_mode=Markdown legacy)

- Bold: `*single asterisks*`. NEVER `**double asterisks**` (not legacy syntax — \
risks parse failure that drops the whole post to plain text).
- Italic: `_underscores_`.
- Inline code: `` `backticks` ``.
- Links: `[text](url)`.
- NO `# heading` syntax — Telegram has no header support; `#` renders literally.
- NO bare `[text]` without a `(url)` after — Telegram tries to parse a link and \
fails the whole message.
- NO leading-`/` references like `/answers/foo` — Telegram highlights the `/word` \
as a non-existent command. Use natural phrases ("спросите меня про X").
- Bullets: write `- item` as plain text — Telegram doesn't render list markup.

# CONSTRAINTS (non-negotiable)

- Voice per Constitution: terse, fact-first, honesty 90, humor 30. No exclamation \
marks. No "great week / amazing progress / kudos to everyone." No AI clichés.
- Match the dominant language of the past week's digests (mostly Russian for cohort 4).
- ≤ 600 words total. Single Telegram message.
- Name students by first_name ONLY. NEVER a full name (use just "Firstname"; \
disambiguate two same-first-names with an initial like "Firstname L." — never \
the full surname). NEVER grade, rank, or compare students. NEVER speculate \
about a student's progress.
- NEVER append the persona signoff ("TARS — cohort 4 retrieval agent..."). The retro \
stands on its own.
- If <2 days of digest content, produce a SHORTER post. Don't pad. Honesty about \
thin weeks is fine.
- If no content at all, return the literal string SKIP and nothing else.

# RECENCY & ANTI-REPUBLISH (read before drafting)

The input set has been filtered to exclude any digest already published in a prior \
retro — assume nothing you see has been broadcast before. Despite that:

- PRIORITIZE the last 3 days of digests over older ones. The cohort already lived \
through the older days; the retro's job is to surface what's fresh, not to recap.
- If a "question" was discussed and answered IN THE SAME WEEK (same input set, \
same digest day or adjacent), it's resolved — frame it as "обсудили" in \
*Что обсуждали*, NOT as an *Открытый вопрос*. *Открытые вопросы* must be \
genuinely open: asked, unanswered, and pointing forward.
- If every question in the input got a Bayram answer in-chat AND links to a \
canonical /answers/ topic, the cohort doesn't need an "Открытые вопросы" section \
at all — omit it. A 3-section retro (Главное / Что обсуждали / Впереди) is fine.
- For a genuinely quiet week (≤1 daily digest with content), DO NOT manufacture \
open questions. Default to: short *Главное* + omit *Открытые вопросы* + brief \
*Впереди*. Mention the one prompt students should act on (e.g. "соберите v0 \
Constitution к S2"), nothing else.
"""


def _last_retro_date() -> date | None:
    """Date of the most recently archived retro (`/digests/retro-YYYY-MM-DD.md`).

    Used to exclude digests already covered by a prior retro so questions don't
    get republished week after week. None if no retro has ever been archived.
    """
    if not KNOWLEDGE_STORE_ID:
        return None
    try:
        client = Anthropic()
        page = client.beta.memory_stores.memories.list(
            memory_store_id=KNOWLEDGE_STORE_ID,
            path_prefix="/digests/retro-", depth=10, order_by="path",
        )
        items = page.data if hasattr(page, "data") else page
        dates: list[date] = []
        for m in items:
            path = getattr(m, "path", "")
            stem = path[len("/digests/"):-len(".md")] if path.endswith(".md") else ""
            if not stem.startswith("retro-"):
                continue
            try:
                dates.append(date.fromisoformat(stem[len("retro-"):]))
            except ValueError:
                continue
        return max(dates) if dates else None
    except Exception:
        logger.exception("_last_retro_date failed")
        return None


def _list_retro_input_digests(days: int = 7) -> list[tuple[str, str]]:
    """Return [(label, content), ...] of digest content to feed the weekly retro.

    Includes:
      - daily digests        /digests/YYYY-MM-DD.md           (date-windowed)
      - workshop supplements /digests/YYYY-MM-DD-supplement.md (date-windowed)
      - manual backfills     /digests/backfill-*.md           (always — they're rare)
    Excludes:
      - /digests/retro-*.md  (don't feed retros to retros)
      - anything whose date is on or before the most recent archived retro
        (those questions were already published last week; rebroadcasting them
        is what produced the stale 2026-05-09 draft).

    Sorted oldest first when a date is recoverable from the stem; undated entries last.
    """
    if not KNOWLEDGE_STORE_ID:
        return []
    client = Anthropic()
    page = client.beta.memory_stores.memories.list(
        memory_store_id=KNOWLEDGE_STORE_ID,
        path_prefix="/digests/", depth=10, order_by="path",
    )
    today_pt = datetime.now(RETRO_TIMEZONE).date()
    earliest = today_pt - timedelta(days=days)
    last_retro = _last_retro_date()
    items = page.data if hasattr(page, "data") else page
    rows: list[tuple[str, str, date | None]] = []
    for m in items:
        path = getattr(m, "path", "")
        if not path.endswith(".md"):
            continue
        stem = path[len("/digests/"):-len(".md")]
        if stem.startswith("retro-"):
            continue  # don't feed retros to retros
        sort_date: date | None = None
        if len(stem) >= 10:
            try:
                sort_date = date.fromisoformat(stem[:10])
            except ValueError:
                sort_date = None
        # If we have a date prefix, apply the window. Backfills (no date prefix)
        # are always included — they're meant to be read alongside recent content.
        if sort_date is not None and (sort_date < earliest or sort_date > today_pt):
            continue
        # Skip content already published in a prior retro. Without this, last
        # week's workshop digest + supplement kept dominating the input set and
        # the retro re-aired the same recurring questions week after week.
        # Strict less-than: the prior retro fires at 09:00 PT, daily digests
        # fire at 23:00 PT, so a daily digest dated == last_retro contains chat
        # that happened AFTER the prior retro and should still be included.
        if sort_date is not None and last_retro and sort_date < last_retro:
            continue
        mid = getattr(m, "id", None)
        if not mid:
            continue
        try:
            full = client.beta.memory_stores.memories.retrieve(
                memory_id=mid, memory_store_id=KNOWLEDGE_STORE_ID,
            )
        except Exception:
            logger.exception("retro: retrieve failed for %s", path)
            continue
        content = getattr(full, "content", "") or ""
        if content.strip():
            rows.append((stem, content, sort_date))
    rows.sort(key=lambda r: (r[2] is None, r[2] or date.min, r[0]))
    return [(label, content) for label, content, _ in rows]


def _telegram_chat_link_base() -> str:
    """Base URL for linking to messages in the cohort group.

    Telegram private supergroups: `https://t.me/c/<id>/<msg>` where `<id>` is the
    chat_id with the leading `-100` prefix stripped (private supergroup ids are
    -100<actual_id>). The link only resolves for users who are members of that
    group, which is exactly the audience we want for the retro post.
    """
    raw = abs(COHORT_GROUP_CHAT_ID)
    s = str(raw)
    if s.startswith("100"):
        s = s[3:]
    return f"https://t.me/c/{s}"


def _list_answer_paths() -> list[str]:
    """Enumerate /answers/*.md paths. Used to teach the retro generator how to
    route open questions to canonical answers (instead of saying 'статус неизвестен')."""
    if not KNOWLEDGE_STORE_ID:
        return []
    try:
        client = Anthropic()
        page = client.beta.memory_stores.memories.list(
            memory_store_id=KNOWLEDGE_STORE_ID,
            path_prefix="/answers/", depth=10, order_by="path",
        )
        items = page.data if hasattr(page, "data") else page
        return sorted(
            getattr(m, "path", "") for m in items
            if getattr(m, "path", "").endswith(".md")
        )
    except Exception:
        logger.exception("_list_answer_paths failed")
        return []


def generate_weekly_retro_text() -> str | None:
    """Generate the retro body. Returns None when there's nothing worth posting."""
    digests = _list_retro_input_digests(days=7)
    answer_paths = _list_answer_paths()
    if not digests:
        logger.info("retro: no digest content in past 7 days")
        return None
    body = "\n\n".join(f"### {label}\n\n{content}" for label, content in digests)
    today = datetime.now(RETRO_TIMEZONE).date().isoformat()
    answers_block = ""
    if answer_paths:
        # Strip /answers/ prefix and .md suffix → just the slug. Students never
        # see these paths; the slugs are routing keys for the retro generator.
        slugs = []
        for p in answer_paths:
            slug = p
            if slug.startswith("/answers/"):
                slug = slug[len("/answers/"):]
            if slug.endswith(".md"):
                slug = slug[:-len(".md")]
            slugs.append(slug)
        answers_block = (
            "## Available answer topics (route open questions by topic match)\n"
            "When a question matches one of these slugs, status is 'спросите меня про <тему>' "
            "where <тему> is a short natural phrase a student would type. Do NOT include "
            "the slug or any file path in the post — students reach the content by asking, "
            "not by navigating.\n"
            + "\n".join(f"  - {s}" for s in slugs)
            + "\n\n"
        )
    link_base = _telegram_chat_link_base()
    user_msg = (
        f"Today is Sunday {today} (PT).\n\n"
        f"## Telegram message link base for this cohort\n"
        f"For any `(msg N)` annotations in digest content, the link to that message is:\n"
        f"  {link_base}/<N>\n"
        f"For `(question: msg N; answer: msg M)` produce two links — one per id.\n"
        f"Only generate links for ids you actually see annotated. Do not fabricate.\n\n"
        f"{answers_block}"
        f"## Digest content from the past week (oldest first)\n\n"
        f"{body}\n\n"
        f"---\n\nProduce the weekly retro post per the system prompt."
    )
    client = Anthropic()
    resp = client.messages.create(
        model=DIGEST_MODEL,
        max_tokens=1500,
        system=WEEKLY_RETRO_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = resp.content[0].text  # type: ignore[union-attr]
    text = text.strip()
    if text == "SKIP" or not text:
        logger.info("retro: model returned SKIP or empty")
        return None
    return text


PENDING_RETRO_PATH = DATA_DIR / "pending_retro.md"
PENDING_RETRO_TTL_SEC = 86400  # drafts older than 24h are stale


async def run_weekly_retro_draft_job(context) -> None:
    """JobQueue callback. Sundays 09:00 PT.

    HUMAN-IN-THE-LOOP: TARS does NOT autopost to the cohort group. It generates
    a draft, saves it to /data/pending_retro.md, and DMs the draft to the cohort
    OWNER for approval. The owner explicitly publishes via /post_retro (or
    discards via /skip_retro) — see telegram_bot.py.

    Rationale: any TARS-initiated outbound to the cohort needs explicit owner
    approval. Reactive replies to mentions/DMs are exempt because the user
    triggered them. Scheduled posts are not.
    """
    bot = getattr(context, "bot", None)
    if bot is None:
        logger.warning("retro draft: no bot on context, skipping")
        return
    try:
        text = generate_weekly_retro_text()
    except Exception:
        logger.exception("retro draft: generation failed")
        return

    owner_id = await _resolve_owner_id(bot)
    if not owner_id:
        logger.warning("retro draft: cannot resolve owner_id; set OWNER_TELEGRAM_USER_ID")
        return

    if not text:
        try:
            await bot.send_message(
                chat_id=owner_id,
                text=("[retro] no daily digests in past 7 days — nothing to draft. "
                      "Skipping this Sunday."),
            )
        except Exception:
            logger.exception("retro draft: notify-owner-empty failed")
        return

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PENDING_RETRO_PATH.write_text(text, encoding="utf-8")
    except Exception:
        logger.exception("retro draft: failed to stage draft to disk")
        return

    # NB: keep this wrapper free of `[bracketed text]` — Telegram's legacy
    # Markdown parser treats `[foo]` as the start of a `[text](url)` link and
    # 400s when it can't find the URL, dumping the whole message back to plain
    # text and losing all formatting in the body. Past incident: 2026-05-04.
    instructions = (
        "—— retro draft, Sun ——\n"
        "Generated automatically. NOT posted to cohort yet.\n"
        "Reply /post_retro to publish as-is.\n"
        "Reply /skip_retro to discard.\n"
        "To edit: tweak /data/pending_retro.md (via fly ssh), then /post_retro.\n\n"
        "----\n\n"
    )
    full_dm = (instructions + text)[:4000]
    # Convert lite-markdown (`*bold*`, `[text](url)`) to Telegram HTML.
    # HTML mode is unambiguous; legacy Markdown is brittle (Cyrillic, colons,
    # bare URLs with `_`, etc. cause silent 400s and full plaintext fallback).
    html_dm = markdown_to_telegram_html(full_dm)
    try:
        await bot.send_message(
            chat_id=owner_id,
            text=html_dm,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info("retro draft DM'd to owner %d (%d chars HTML)", owner_id, len(html_dm))
        return
    except Exception:
        logger.warning("retro draft: HTML send failed; falling back to plain text",
                       exc_info=True)
    try:
        await bot.send_message(
            chat_id=owner_id, text=full_dm, disable_web_page_preview=True,
        )
        logger.info("retro draft DM'd as plain text (%d chars)", len(full_dm))
    except Exception:
        logger.exception("retro draft: plain-text fallback also failed")


async def _resolve_owner_id(bot) -> int:
    """Resolve the cohort owner's Telegram user_id.
    Priority: OWNER_TELEGRAM_USER_ID env var → group's `creator` admin → 0."""
    env = (os.environ.get("OWNER_TELEGRAM_USER_ID") or "").strip()
    if env:
        try:
            return int(env)
        except ValueError:
            logger.warning("OWNER_TELEGRAM_USER_ID is not int: %r", env)
    try:
        admins = await bot.get_chat_administrators(COHORT_GROUP_CHAT_ID)
        for a in admins:
            if getattr(a, "status", None) == "creator":
                uid = getattr(getattr(a, "user", None), "id", 0)
                if uid:
                    return int(uid)
    except Exception:
        logger.exception("_resolve_owner_id: get_chat_administrators failed")
    return 0


def load_pending_retro() -> str | None:
    """Read the staged retro draft if fresh; return None if missing or stale."""
    if not PENDING_RETRO_PATH.exists():
        return None
    age = datetime.now(timezone.utc).timestamp() - PENDING_RETRO_PATH.stat().st_mtime
    if age > PENDING_RETRO_TTL_SEC:
        logger.info("pending retro is %.1fh old — stale, ignoring", age / 3600)
        return None
    try:
        return PENDING_RETRO_PATH.read_text(encoding="utf-8")
    except Exception:
        logger.exception("load_pending_retro: read failed")
        return None


def archive_published_retro(text: str) -> None:
    """Move a published retro to /digests/retro-YYYY-MM-DD.md and clear staging."""
    today = datetime.now(RETRO_TIMEZONE).date().isoformat()
    try:
        write_digest(f"retro-{today}", text)
        logger.info("retro archived to /digests/retro-%s.md", today)
    except Exception:
        logger.exception("archive_published_retro: write_digest failed")
    try:
        PENDING_RETRO_PATH.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        logger.exception("archive_published_retro: unlink failed")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--today", action="store_true", help="digest today (PT)")
    g.add_argument("--date", help="digest a specific date YYYY-MM-DD (PT)")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate but don't upload to memory store")
    args = ap.parse_args()

    date_str = args.date or datetime.now(RETRO_TIMEZONE).strftime("%Y-%m-%d")

    text = digest_for(date_str)
    if not text:
        print(f"(no messages for {date_str})")
        return 0

    if args.dry_run:
        print(text)
        return 0

    write_digest(date_str, text)
    print(f"digest written: /digests/{date_str}.md ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
