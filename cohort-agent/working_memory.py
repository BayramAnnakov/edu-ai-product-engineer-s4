# pyright: reportAttributeAccessIssue=false
"""Working memory — the *live* context tier for TARS.

Where the layered memory model breaks down by tier:

    Sensory   : the literal incoming Telegram update (free, no storage)
    Working   : last ~30 group messages or last 60 min — THIS MODULE
    Short-term: today's raw JSONL (passive_log writes one file per UTC day)
    Episodic  : daily digest, rolled into the knowledge store at 23:00 PT
    Semantic  : distilled learnings + curated seeds in the knowledge store

The pedagogy: each tier compresses the prior one, and each makes a different
decision about *what's worth keeping*. Working memory keeps recency and
the conversation graph; everything older has to earn a slot in the digest.

Storage: SQLite on the fly tars_data volume (/data/working_memory.db).
The bot writes to it; the bot also reads from it at query time and injects
the rendered window into TARS's prompt as a <recent_chat> block. The agent
itself stays stateless — it never touches this DB directly.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_DB_PATH = Path(os.environ.get("TARS_DATA_DIR", "/data")) / "working_memory.db"
DISPLAY_TZ = ZoneInfo("America/Los_Angeles")

# Tunables — small enough that the prompt overhead stays well under 2k tokens.
WINDOW_LIMIT = 30
WINDOW_MAX_AGE_MIN = 60
REPLY_CHAIN_DEPTH = 10
RETENTION_PER_CHAT = 500  # hard cap; oldest rows pruned on insert

_lock = threading.Lock()
_initialized = False


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    global _initialized
    with _lock:
        with _connect(db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS recent_messages (
                    chat_id  INTEGER NOT NULL,
                    msg_id   INTEGER NOT NULL,
                    ts       TEXT    NOT NULL,
                    user_id  INTEGER NOT NULL,
                    user_name TEXT,
                    text     TEXT    NOT NULL,
                    reply_to INTEGER,
                    PRIMARY KEY (chat_id, msg_id)
                );
                CREATE INDEX IF NOT EXISTS idx_recent_chat_ts
                    ON recent_messages(chat_id, ts DESC);
                """
            )
        _initialized = True


def record_message(
    *,
    chat_id: int,
    msg_id: int,
    ts: datetime,
    user_id: int,
    user_name: str | None,
    text: str,
    reply_to: int | None,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """Insert one message. Idempotent on (chat_id, msg_id) — re-runs are safe."""
    if not _initialized:
        init_db(db_path)
    iso = ts.astimezone(timezone.utc).isoformat()
    with _lock:
        with _connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO recent_messages "
                "(chat_id, msg_id, ts, user_id, user_name, text, reply_to) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, msg_id, iso, user_id, user_name, text, reply_to),
            )
            # Hard cap per chat — prune oldest beyond RETENTION_PER_CHAT.
            conn.execute(
                "DELETE FROM recent_messages WHERE chat_id = ? AND msg_id IN ("
                "  SELECT msg_id FROM recent_messages WHERE chat_id = ? "
                "  ORDER BY ts DESC LIMIT -1 OFFSET ?"
                ")",
                (chat_id, chat_id, RETENTION_PER_CHAT),
            )


def _row(conn: sqlite3.Connection, chat_id: int, msg_id: int) -> tuple | None:
    cur = conn.execute(
        "SELECT msg_id, ts, user_name, text, reply_to "
        "FROM recent_messages WHERE chat_id = ? AND msg_id = ?",
        (chat_id, msg_id),
    )
    return cur.fetchone()


def reply_chain(
    chat_id: int,
    leaf_msg_id: int,
    *,
    max_depth: int = REPLY_CHAIN_DEPTH,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[tuple]:
    """Walk reply_to pointers up from leaf_msg_id. Returns chain root-first.

    Excludes leaf_msg_id itself (the trigger), since the caller already has it.
    """
    if not _initialized:
        init_db(db_path)
    chain: list[tuple] = []
    with _lock:
        with _connect(db_path) as conn:
            row = _row(conn, chat_id, leaf_msg_id)
            if not row:
                return []
            cursor_id = row[4]  # reply_to of the leaf
            seen = {leaf_msg_id}
            while cursor_id and cursor_id not in seen and len(chain) < max_depth:
                seen.add(cursor_id)
                parent = _row(conn, chat_id, cursor_id)
                if not parent:
                    break
                chain.append(parent)
                cursor_id = parent[4]  # parent.reply_to
    chain.reverse()  # root-first
    return chain


def recent_window(
    chat_id: int,
    *,
    exclude_msg_id: int | None = None,
    limit: int = WINDOW_LIMIT,
    max_age_min: int = WINDOW_MAX_AGE_MIN,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[tuple]:
    """Last `limit` messages in this chat within `max_age_min` minutes.

    Returned oldest-first so it reads naturally as a transcript.
    """
    if not _initialized:
        init_db(db_path)
    cutoff_dt = datetime.now(timezone.utc).timestamp() - max_age_min * 60
    cutoff_iso = datetime.fromtimestamp(cutoff_dt, tz=timezone.utc).isoformat()
    with _lock:
        with _connect(db_path) as conn:
            cur = conn.execute(
                "SELECT msg_id, ts, user_name, text, reply_to "
                "FROM recent_messages "
                "WHERE chat_id = ? AND ts >= ? "
                + ("AND msg_id != ? " if exclude_msg_id else "")
                + "ORDER BY ts DESC LIMIT ?",
                (chat_id, cutoff_iso, exclude_msg_id, limit) if exclude_msg_id
                else (chat_id, cutoff_iso, limit),
            )
            rows = cur.fetchall()
    rows.reverse()
    return rows


def _format_row(row: tuple, *, mark_reply_chain: bool = False) -> str:
    _, ts, user_name, text, reply_to = row
    try:
        local = datetime.fromisoformat(ts).astimezone(DISPLAY_TZ)
        stamp = local.strftime("%I:%M %p").lstrip("0")
    except Exception:
        stamp = ts
    who = user_name or "?"
    chain_marker = "↳ " if mark_reply_chain else ""
    reply_marker = f" (replies to #{reply_to})" if reply_to else ""
    # Truncate runaway messages so one essay can't blow the prompt budget.
    body = text if len(text) <= 600 else text[:600] + "…"
    return f"[{stamp}] {chain_marker}{who}{reply_marker}: {body}"


def render_block(
    chat_id: int,
    *,
    trigger_msg_id: int | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> str:
    """Render the full <recent_chat> block to inject into TARS's prompt.

    Composition:
    - Reply chain leading to the trigger (if any) — surfaces context older than
      the rolling window when the asker explicitly threaded a reply.
    - Rolling window of last ~30 msgs in last ~60 min, excluding the trigger.

    Returns "" when there's nothing to inject (fresh chat, very first message).
    """
    chain: list[tuple] = []
    if trigger_msg_id is not None:
        chain = reply_chain(chat_id, trigger_msg_id, db_path=db_path)
    window = recent_window(
        chat_id, exclude_msg_id=trigger_msg_id, db_path=db_path,
    )
    # De-dupe: any chain msg that's also in the window should appear once.
    chain_ids = {r[0] for r in chain}
    window = [r for r in window if r[0] not in chain_ids]
    lines: list[str] = []
    if chain:
        lines.append("# Reply chain (older context the asker is referencing):")
        lines.extend(_format_row(r, mark_reply_chain=True) for r in chain)
        lines.append("")
    if window:
        lines.append("# Recent group activity (last hour, oldest first):")
        lines.extend(_format_row(r) for r in window)
    if not lines:
        return ""
    body = "\n".join(lines)
    return (
        "<recent_chat>\n"
        "Working memory — last group messages, for resolving 'that', 'we', 'they', "
        "and elliptical references. Do NOT cite this as a seed file. Use it only "
        "to disambiguate what the asker is talking about.\n\n"
        f"{body}\n"
        "</recent_chat>"
    )
