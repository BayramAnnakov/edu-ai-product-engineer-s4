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
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger("tars.digest")

DIGEST_MODEL = "claude-sonnet-4-5-20250929"
DATA_DIR = Path(os.environ.get("TARS_DATA_DIR", "/data"))
KNOWLEDGE_STORE_ID = os.environ.get("COHORT_KNOWLEDGE_STORE_ID", "").strip()

DIGEST_SYSTEM = """You are the cohort-class digest writer for cohort 4 of \
Bayram Annakov's AI Product Engineer course. Read the day's Telegram \
messages and produce a structured Markdown digest.

Each JSONL record may have:
- `text` (string, may be empty if attachment-only)
- `attachments` (array of tags like `photo`, `document:Constitution.md`, `voice:45s`, `poll:...`)
- `reply_to` (msg_id this replies to)
- `forward_from` (set if forwarded)

When a message has attachments, NOTE them in the relevant digest section. For
example: *"Ruslan shared a screenshot — likely a Plan Mode trace (photo, no caption)"*
or *"Igor sent a 45s voice note in reply to Bayram's question about reflexes."*
You don't have access to attachment contents; describe what you can infer from
type + surrounding text.

Sections (omit any with no content):
1. **Questions** — what students asked. Group similar questions.
2. **Confusions** — places students stumbled, asked clarification, or got stuck.
3. **Dossiers shared** — colleague-target.md links/mentions, Constitution updates, document attachments that look like dossiers.
4. **Errors discussed** — failures students hit during homework.
5. **Patches shared** — Constitution rules students added or modified.
6. **Decisions** — Bayram's announcements, schedule changes, scope shifts.
7. **Attachments** — non-trivial files/photos/voice notes shared (skip stickers, location pins, casual reaction GIFs).
8. **Notable quotes** — verbatim, attribute by `first_name`. ≤3 quotes.

Filter ruthlessly. Drop:
- Greetings, acknowledgments, "thanks"
- Off-topic banter (jokes, weather, etc.)
- Technical chatter unrelated to cohort goals
- Stickers, GIFs, casual emoji-only replies

Aim for SIGNAL not coverage. ~400-800 words. Output Markdown only — no preamble.

Format the file like this:

```
# Cohort 4 Digest — YYYY-MM-DD

## Questions
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

    # Resolve existing path → upsert
    page = client.beta.memory_stores.memories.list(
        memory_store_id=KNOWLEDGE_STORE_ID, depth=10, order_by="path",
    )
    existing_id: str | None = None
    for m in (page.data if hasattr(page, "data") else page):
        if getattr(m, "path", "") == path:
            existing_id = getattr(m, "id", None)
            break

    if existing_id:
        client.beta.memory_stores.memories.update(
            memory_id=existing_id, memory_store_id=KNOWLEDGE_STORE_ID, content=text,
        )
        logger.info("updated %s", path)
    else:
        client.beta.memory_stores.memories.create(
            KNOWLEDGE_STORE_ID, path=path, content=text,
        )
        logger.info("created %s", path)


async def run_daily_job(_context) -> None:
    """JobQueue callback. Digests yesterday (UTC) since the job fires at 23:00 PT
    which is ~07:00 UTC the next day; we want the closing day's log."""
    yesterday = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Note: at 23:00 PT (07:00 UTC), today's UTC date *is* the just-ended PT day.
    # If we want the calendar day that just closed in PT, this is correct.
    try:
        text = digest_for(yesterday)
        if text:
            write_digest(yesterday, text)
            logger.info("digest written for %s", yesterday)
        else:
            logger.info("no messages for %s, skipping digest", yesterday)
    except Exception:
        logger.exception("digest job failed for %s", yesterday)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--today", action="store_true", help="digest today (UTC)")
    g.add_argument("--date", help="digest a specific date YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate but don't upload to memory store")
    args = ap.parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

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
