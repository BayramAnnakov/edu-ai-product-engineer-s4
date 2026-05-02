# pyright: reportAttributeAccessIssue=false
"""One-shot backfill digest for the cohort group.

When TARS comes online mid-stream (e.g., the passive logger started after the
group was already active), the daily-digest pipeline misses everything before
the start date. This script takes a file containing pre-bot history (in any
human-readable form) and produces a single backfill digest covering it,
uploaded to the cohort-knowledge memory store at
`/digests/backfill-<label>.md`.

Run locally with ANTHROPIC_API_KEY + COHORT_KNOWLEDGE_STORE_ID set:

    python backfill.py --label apr27-may1 /tmp/tg-history-backfill.txt

Use `--dry-run` to preview the digest without uploading.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from anthropic import Anthropic

DIGEST_MODEL = "claude-sonnet-4-5-20250929"

BACKFILL_SYSTEM = """You are the cohort-class digest writer for cohort 4 of \
Bayram Annakov's AI Product Engineer course. You're producing a ONE-SHOT \
BACKFILL — summarizing pre-bot history so future TARS sessions can answer \
"what happened before I came online."

Input is a free-form transcript or chronological dump of Telegram messages \
that may include join events, polls, attachments, stickers, and casual chatter.

Sections (omit any with no content):
1. **Period covered** — date range, member count grown, who joined.
2. **Decisions / announcements** — Bayram's or Madina's announcements: schedule, tools, format.
3. **Questions raised** — what students asked, even if answered later.
4. **Tools / preferences shared** — what stack students mentioned (Claude Code / Codex / Cursor / etc.).
5. **Notable moments** — first hellos, polls run, materials posted.
6. **Open threads** — questions left unanswered or topics still active.

Filter ruthlessly. Drop join events except as a count summary. Drop stickers \
and acknowledgments. Aim for SIGNAL not coverage. ~200-500 words. Output \
Markdown only — no preamble, no closing pleasantry.

Format:

```
# Cohort 4 Backfill Digest — <LABEL>

## Period covered
- ...

## Decisions / announcements
- ...

(etc. — omit empty sections)
```
"""


def write_digest(client: Anthropic, store_id: str, path: str, content: str) -> None:
    page = client.beta.memory_stores.memories.list(
        memory_store_id=store_id, depth=10, order_by="path",
    )
    existing_id: str | None = None
    for m in (page.data if hasattr(page, "data") else page):
        if getattr(m, "path", "") == path:
            existing_id = getattr(m, "id", None)
            break
    if existing_id:
        client.beta.memory_stores.memories.update(
            memory_id=existing_id, memory_store_id=store_id, content=content,
        )
        print(f"updated {path}")
    else:
        client.beta.memory_stores.memories.create(store_id, path=path, content=content)
        print(f"created {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="path to transcript/history file (UTF-8 text)")
    ap.add_argument("--label", required=True,
                    help="short label for the digest filename, e.g. apr27-may1")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the digest, don't upload")
    args = ap.parse_args()

    raw = Path(args.file).read_text(encoding="utf-8").strip()
    if not raw:
        sys.exit("input file is empty")

    client = Anthropic()
    user_msg = (
        f"Pre-bot history for cohort 4. Produce the backfill digest per the \
system prompt. Label this digest '{args.label}'.\n\n{raw}"
    )
    resp = client.messages.create(
        model=DIGEST_MODEL,
        max_tokens=2000,
        system=BACKFILL_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = resp.content[0].text  # type: ignore[union-attr]

    if args.dry_run:
        print(text)
        return 0

    store_id = (os.environ.get("COHORT_KNOWLEDGE_STORE_ID") or "").strip()
    if not store_id:
        sys.exit("COHORT_KNOWLEDGE_STORE_ID not set")
    write_digest(client, store_id, f"/digests/backfill-{args.label}.md", text)
    print(f"({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
