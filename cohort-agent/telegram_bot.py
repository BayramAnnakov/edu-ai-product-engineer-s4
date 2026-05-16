# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportReturnType=false, reportMissingImports=false
"""TARS — Telegram webhook bot for cohort 4.

Listens for @-mentions and /ask in the cohort group. Queries Anthropic Managed
Agents with the TARS Constitution + cohort seed files. Replies grounded in seeds.

Triggers:
- `@edu_aipe_s4_tars_bot <question>` — group mention
- `/ask <question>` — slash command
- Reply-to-bot — continues the thread

Boundary: only responds in COHORT_GROUP_CHAT_ID. Other chats get silence.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from anthropic import Anthropic
from telegram import ReactionTypeEmoji, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters,
)

from digest import (
    run_daily_job,
    run_weekly_retro_draft_job,
    load_pending_retro,
    archive_published_retro,
    PENDING_RETRO_PATH,
)
from tg_format import markdown_to_telegram_html
import working_memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tars")

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "edu_aipe_s4_tars_bot")
COHORT_GROUP_CHAT_ID = int(os.environ.get("COHORT_GROUP_CHAT_ID", "-1003721817564"))
WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "8080"))

AGENT_ID = os.environ.get("COHORT_AGENT_ID", "").strip()
ENV_ID = os.environ.get("COHORT_ENVIRONMENT_ID", "").strip()
KNOWLEDGE_ID = os.environ.get("COHORT_KNOWLEDGE_STORE_ID", "").strip()
LEARNINGS_ID = os.environ.get("COHORT_LEARNINGS_STORE_ID", "").strip()

QUERY_TIMEOUT_SEC = 120
# Per-user cap. Replaces an earlier global cap; a single fast-firing student
# could otherwise starve the whole cohort. Env var name kept for back-compat
# but semantics changed: this is now per-user-per-hour.
MAX_PER_USER_PER_HOUR = int(os.environ.get("MAX_QUERIES_PER_HOUR", "10"))
MEMBER_CACHE_TTL_SEC = 300  # cache getChatMember results for 5 min

DATA_DIR = Path(os.environ.get("TARS_DATA_DIR", "/data"))
DIGEST_TIMEZONE = ZoneInfo("America/Los_Angeles")
DIGEST_HOUR = 23  # 23:00 Pacific
RETRO_DRAFT_HOUR = 9  # 09:00 Pacific — TARS DMs draft to owner; owner publishes manually
RETRO_WEEKDAY = 6  # Sunday in python-telegram-bot (Mon=0..Sun=6)

_anthropic: Anthropic | None = None
_recent_queries: dict[int, deque[float]] = {}
_member_cache: dict[int, tuple[bool, float]] = {}  # user_id -> (is_member, fetched_at)
ALLOWED_STATUSES = {"creator", "administrator", "member", "restricted"}


def anthropic_client() -> Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = Anthropic()
    return _anthropic


def rate_limited(user_id: int) -> bool:
    """Per-user 1h sliding window. Each user gets their own bucket so a single
    fast-firing student can't starve the cohort."""
    cutoff = time.monotonic() - 3600
    q = _recent_queries.get(user_id)
    if q is None:
        return False
    while q and q[0] < cutoff:
        q.popleft()
    return len(q) >= MAX_PER_USER_PER_HOUR


def record_query(user_id: int) -> None:
    q = _recent_queries.get(user_id)
    if q is None:
        q = deque(maxlen=MAX_PER_USER_PER_HOUR + 10)
        _recent_queries[user_id] = q
    q.append(time.monotonic())


# --- Opt-out -------------------------------------------------------------
# Constitution v0.2 promises students can /optout in DM and we stop logging
# their messages + excluding from digest. The orchestrator (this file) owns
# the exclusion; the agent only acknowledges in voice. Without this filter
# the verbal acknowledgement would be a lie.
OPTOUTS_PATH = DATA_DIR / "optouts.json"
_optouts_cache: tuple[set[int], float] | None = None


def _load_optouts() -> set[int]:
    """Return the set of user_ids that have opted out. mtime-cached."""
    global _optouts_cache
    try:
        st = OPTOUTS_PATH.stat()
    except FileNotFoundError:
        return set()
    if _optouts_cache is not None and _optouts_cache[1] == st.st_mtime:
        return _optouts_cache[0]
    try:
        data = json.loads(OPTOUTS_PATH.read_text(encoding="utf-8"))
        ids = {int(x) for x in data.get("user_ids", [])}
    except Exception:
        logger.exception("_load_optouts failed")
        return set()
    _optouts_cache = (ids, st.st_mtime)
    return ids


def _write_optouts(ids: set[int]) -> None:
    global _optouts_cache
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    payload = {"user_ids": sorted(ids)}
    OPTOUTS_PATH.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _optouts_cache = None  # force reload on next read


def build_resources() -> list[dict]:
    resources: list[dict] = []
    if KNOWLEDGE_ID:
        resources.append({
            "type": "memory_store",
            "memory_store_id": KNOWLEDGE_ID,
            "access": "read_only",
            "instructions": (
                "Cohort 4 curated knowledge. Check /team/cohort-roster.md when a "
                "student is named. Check /lessons/ for session designs. Check "
                "/dossiers/ for instructor and student colleague targets. Check "
                "/transcripts/ for what was actually said in past sessions. "
                "READ-ONLY."
            ),
        })
    if LEARNINGS_ID:
        resources.append({
            "type": "memory_store",
            "memory_store_id": LEARNINGS_ID,
            "access": "read_write",
            "instructions": (
                "TARS's scratchpad. WRITE only to /learnings/staged/<YYYY-MM-DD>-"
                "<topic>.md when noticing a recurring pattern, a cohort-specific "
                "preference, or a mistake to avoid. One insight per file. Never "
                "modify or delete anything outside /learnings/staged/."
            ),
        })
    return resources


def today_context() -> str:
    """One-line current date/time so TARS doesn't fabricate dates.
    Anchored to America/Los_Angeles since that's the cohort/instructor TZ."""
    now_pt = datetime.now(DIGEST_TIMEZONE)
    return (
        f"[Context: today is {now_pt.strftime('%Y-%m-%d (%A)')}, "
        f"current time {now_pt.strftime('%H:%M %Z')}.]"
    )


async def query_tars(
    prompt: str,
    title: str,
    *,
    allow_learnings: bool = True,
    image_blocks: list[dict] | None = None,
    chat_id: int | None = None,
    trigger_msg_id: int | None = None,
) -> str:
    """Run one Managed-Agent session against the cohort agent.

    allow_learnings: when False, the read_write learnings store is omitted.
    Use False for private DMs — anything said there must not leak into shared
    cohort memory.

    image_blocks: optional list of Anthropic image content blocks to include
    alongside the text prompt (for photos/screenshots/image-mime documents).

    chat_id / trigger_msg_id: when set, working memory (last ~30 msgs in this
    chat + reply chain to the trigger) is prepended to the prompt as a
    <recent_chat> block. Only set for the cohort group; DMs stay private.
    """
    if not (AGENT_ID and ENV_ID):
        return ("TARS not provisioned. Bayram needs to run `python provision.py` "
                "and set COHORT_AGENT_ID + COHORT_ENVIRONMENT_ID.")

    def _sync() -> str:
        client = anthropic_client()
        resources = build_resources()
        if not allow_learnings:
            resources = [r for r in resources if r.get("memory_store_id") != LEARNINGS_ID]
        recent_block = ""
        if chat_id is not None:
            try:
                recent_block = working_memory.render_block(
                    chat_id, trigger_msg_id=trigger_msg_id,
                )
            except Exception:
                logger.exception("working_memory.render_block failed")
        parts = [today_context()]
        if recent_block:
            parts.append(recent_block)
        if prompt:
            parts.append(prompt)
        prefixed_prompt = "\n\n".join(parts)
        content: list[dict] = []
        if image_blocks:
            content.extend(image_blocks)
        content.append({"type": "text", "text": prefixed_prompt})
        try:
            session = client.beta.sessions.create(
                agent=AGENT_ID,
                environment_id=ENV_ID,
                title=title[:100],
                resources=resources or None,
            )
        except Exception as exc:
            logger.exception("session create failed")
            return f"(session_create_failed: {exc!r})"

        text_parts: list[str] = []
        deadline = time.monotonic() + QUERY_TIMEOUT_SEC
        try:
            with client.beta.sessions.events.stream(session.id) as stream:
                client.beta.sessions.events.send(
                    session.id,
                    events=[{
                        "type": "user.message",
                        "content": content,
                    }],
                )
                for event in stream:
                    if time.monotonic() > deadline:
                        text_parts.append("\n\n(timed out)")
                        break
                    etype = getattr(event, "type", None)
                    if etype == "agent.message":
                        for block in getattr(event, "content", []):
                            if getattr(block, "type", None) == "text":
                                text_parts.append(getattr(block, "text", ""))
                    elif etype == "session.status_idle":
                        stop = getattr(event, "stop_reason", None)
                        stop_type = getattr(stop, "type", None) if stop else None
                        if stop_type in ("end_turn", None):
                            break
                    elif etype == "session.status_terminated":
                        text_parts.append("\n\n(session terminated)")
                        break
        except Exception as exc:
            logger.exception("stream failed")
            return f"(stream_failed: {exc!r})"
        return "".join(text_parts).strip() or "(empty response)"

    return await asyncio.to_thread(_sync)


def strip_mention(text: str) -> str:
    if not text:
        return ""
    handle = f"@{TELEGRAM_BOT_USERNAME}"
    return text.replace(handle, "").strip()


async def is_cohort_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user_id is a current member of the cohort group. Cached 5 min."""
    now = time.monotonic()
    cached = _member_cache.get(user_id)
    if cached and (now - cached[1]) < MEMBER_CACHE_TTL_SEC:
        return cached[0]
    try:
        member = await context.bot.get_chat_member(
            chat_id=COHORT_GROUP_CHAT_ID, user_id=user_id,
        )
        is_member = member.status in ALLOWED_STATUSES
    except Exception:
        logger.exception("get_chat_member failed for %s", user_id)
        is_member = False
    _member_cache[user_id] = (is_member, now)
    return is_member


async def keep_typing(bot, chat_id: int, cancel: asyncio.Event) -> None:
    """Re-send TYPING every 4s until cancel fires. Telegram expires after 5s."""
    try:
        while not cancel.is_set():
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                pass
            try:
                await asyncio.wait_for(cancel.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass
    except Exception:
        pass


SUPPORTED_IMAGE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per image, Anthropic API ceiling
MAX_IMAGES_PER_MESSAGE = 4


async def fetch_image_blocks(bot, msg) -> list[dict]:
    """Pull image attachments from a Telegram message. Returns [] on no images
    or fetch failure. Best-effort — never raises."""
    blocks: list[dict] = []
    targets: list[tuple[str, str]] = []  # (file_id, media_type)
    if msg.photo:
        # photo is a list of PhotoSize, last one is the largest
        targets.append((msg.photo[-1].file_id, "image/jpeg"))
    if msg.document and (msg.document.mime_type or "") in SUPPORTED_IMAGE_MIME:
        targets.append((msg.document.file_id, msg.document.mime_type))
    if msg.sticker and not msg.sticker.is_animated and not msg.sticker.is_video:
        # static webp stickers — Anthropic supports webp
        targets.append((msg.sticker.file_id, "image/webp"))
    targets = targets[:MAX_IMAGES_PER_MESSAGE]
    for file_id, mime in targets:
        try:
            tg_file = await bot.get_file(file_id)
            data = await tg_file.download_as_bytearray()
            if len(data) > MAX_IMAGE_BYTES:
                logger.warning("image %s too big (%d bytes), skipping", file_id, len(data))
                continue
            b64 = base64.b64encode(bytes(data)).decode("ascii")
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64},
            })
        except Exception:
            logger.exception("failed to fetch image %s", file_id)
    return blocks


def _persist_outbound(sent_msg, body: str, *, reply_to_id: int | None) -> None:
    """Log TARS's own reply to JSONL + working memory.
    Cohort-group only — DM replies stay private (Constitution: discretion 100).
    Telegram does NOT echo bot-sent messages back via webhook, so passive_log
    never sees these. Without this call the daily digest sees questions but not
    answers, and TARS's own working-memory window forgets what it just said.
    """
    if sent_msg is None:
        return
    try:
        chat_id = sent_msg.chat_id
    except Exception:
        return
    if chat_id != COHORT_GROUP_CHAT_ID:
        return
    ts = sent_msg.date or datetime.now(timezone.utc)
    text_body = body or "(empty response)"
    record = {
        "ts": ts.isoformat(),
        "msg_id": sent_msg.message_id,
        "user_id": 0,  # synthetic — TARS isn't a real Telegram user_id
        "username": TELEGRAM_BOT_USERNAME,
        "first_name": "TARS",
        "text": text_body,
        "attachments": [],
        "reply_to": reply_to_id,
        "forward_from": None,
    }
    try:
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        # Bucket by PT date, not UTC. Why: daily digests fire at 23:00 PT and
        # we want each digest to summarize one PT calendar day. UTC bucketing
        # split every PT day across two files, half of which was never read.
        date_str = datetime.now(DIGEST_TIMEZONE).strftime("%Y-%m-%d")
        path = DATA_DIR / f"messages-{date_str}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("_persist_outbound jsonl failed")
    try:
        working_memory.record_message(
            chat_id=chat_id,
            msg_id=sent_msg.message_id,
            ts=ts,
            user_id=0,
            user_name="TARS",
            text=text_body,
            reply_to=reply_to_id,
        )
    except Exception:
        logger.exception("_persist_outbound working_memory failed")


async def react(bot, chat_id: int, message_id: int, emoji: str | None) -> None:
    """Set (or clear, if emoji=None) a reaction on a message. Errors are silent."""
    try:
        reaction = [ReactionTypeEmoji(emoji=emoji)] if emoji else []
        await bot.set_message_reaction(
            chat_id=chat_id, message_id=message_id, reaction=reaction,
        )
    except Exception:
        # Reactions can fail (privacy, supergroup type, etc.) — never block the response
        logger.debug("set_message_reaction failed", exc_info=True)


class _ReplyToBotFilter(filters.MessageFilter):
    """Match group messages whose reply target is THIS bot.

    Without this, `filters.REPLY` matches every reply in the group — including
    Telegram's pin/forward service messages, whose reply_to_message points at
    the pinned target, not the bot. That misfire is what made TARS chime in
    when nothing was asked of it.
    """

    def filter(self, message) -> bool:
        rep = getattr(message, "reply_to_message", None)
        if rep is None:
            return False
        sender = getattr(rep, "from_user", None)
        if sender is None:
            return False
        return getattr(sender, "username", None) == TELEGRAM_BOT_USERNAME


_reply_to_bot = _ReplyToBotFilter()


class _MentionsBotFilter(filters.MessageFilter):
    """Match group messages whose text/caption contains @<bot_username>
    as a substring (case-insensitive).

    `filters.Mention(username)` relies on Telegram's server-side `mention`
    entity, which silently drops the mention on edited messages and on
    some multi-paragraph layouts (entity not regenerated). The bot then
    never fires. Substring match is robust because it's purely text-based
    and ignores Telegram's entity parser.
    """

    _needle = f"@{TELEGRAM_BOT_USERNAME}".lower()

    def filter(self, message) -> bool:
        text = (getattr(message, "text", None) or getattr(message, "caption", None) or "")
        return self._needle in text.lower()


_mentions_bot = _MentionsBotFilter()


async def is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Authorize a chat. Allow:
    - Cohort group itself.
    - Private DMs from verified cohort members.
    Other chats (other groups, DMs from non-members) are silently ignored.
    """
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return False
    if chat.id == COHORT_GROUP_CHAT_ID:
        return True
    if chat.type == "private":
        return await is_cohort_member(context, user.id)
    return False


async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_authorized(update, context):
        return
    msg = update.effective_message
    user = update.effective_user
    if msg is None or user is None:
        return
    if rate_limited(user.id):
        await msg.reply_text(
            f"You've hit the hourly cap ({MAX_PER_USER_PER_HOUR}/h per user). "
            "Cooling down — try again in a bit."
        )
        return

    prompt = strip_mention(msg.text or msg.caption or "")

    # Pull any image attachments so TARS can actually see them. Vision is
    # supported on managed agents; voice/video isn't, so those still degrade
    # to caption-only.
    image_blocks = await fetch_image_blocks(context.bot, msg)

    if not prompt and not image_blocks:
        await msg.reply_text("Mention me with a question (text, image, or both).")
        return
    if not prompt and image_blocks:
        prompt = "(Image-only message. Describe / analyze it for the cohort.)"

    title = f"tg:{user.username or user.id}:{int(time.time())}"
    logger.info(
        "query from %s: %s%s",
        user.username or user.id, prompt[:80],
        f" [+{len(image_blocks)} img]" if image_blocks else "",
    )

    # 1. Immediate "I saw you" reaction on the user's message
    await react(context.bot, msg.chat_id, msg.message_id, "👀")

    # 2. Status placeholder reply (will be edited with final answer)
    placeholder = await msg.reply_text(
        "🤔 thinking…", reply_to_message_id=msg.message_id,
    )

    # 3. Typing indicator loop while the managed-agent session runs
    cancel_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, msg.chat_id, cancel_typing))

    # Private DMs: don't allow writing to shared cohort learnings store.
    is_dm = update.effective_chat.type == "private"

    record_query(user.id)
    t0 = time.monotonic()
    error: str | None = None
    # Working memory only injected for cohort-group queries. DMs stay isolated.
    wm_chat_id = msg.chat_id if not is_dm else None
    wm_trigger_id = msg.message_id if not is_dm else None
    try:
        response = await query_tars(
            prompt, title,
            allow_learnings=not is_dm,
            image_blocks=image_blocks or None,
            chat_id=wm_chat_id,
            trigger_msg_id=wm_trigger_id,
        )
    except Exception as exc:
        logger.exception("query_tars failed")
        response = f"(error: {exc!r})"
        error = str(exc)
    finally:
        cancel_typing.set()
        try:
            await typing_task
        except Exception:
            pass

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    is_error = error is not None or response.startswith("(") and response.endswith(")")
    logger.info("query done in %d ms (dm=%s, error=%s)", elapsed_ms, is_dm, is_error)

    # 4. Final reaction: 🫡 on success, 💔 on error
    await react(
        context.bot, msg.chat_id, msg.message_id,
        "💔" if is_error else "🫡",
    )

    # 5. Edit the placeholder with the final reply. Try Markdown rendering
    #    first (TARS produces **bold**, `code`, lists); fall back to plain
    #    text if Telegram rejects the formatting (unbalanced markers, etc.).
    body = response[:4000]

    async def _send(text: str):
        for mode in ("Markdown", None):
            try:
                return await placeholder.edit_text(text, parse_mode=mode)
            except Exception:
                continue
        try:
            return await msg.reply_text(text, reply_to_message_id=msg.message_id)
        except Exception:
            logger.exception("failed to send response")
            return None

    sent = await _send(body)
    # Persist TARS's own reply so it shows up in the digest and working memory.
    # DM replies skipped — they must not leak into shared cohort stores.
    if sent is not None and not is_dm:
        try:
            _persist_outbound(sent, body, reply_to_id=msg.message_id)
        except Exception:
            logger.exception("persist outbound failed")


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(context.args or [])
    msg = update.effective_message
    if msg is None:
        return
    if not args:
        await msg.reply_text("Usage: /ask <question>")
        return
    msg.text = args
    await handle_query(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_authorized(update, context):
        return
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_text(
        "TARS — cohort 4 retrieval agent. Honesty 90, humor 30.\n"
        "Mention me or use /ask. I cite my sources."
    )


async def cmd_health(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_text("ok")


async def cmd_optout(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """DM-only: mark the sender as opted out of digest/working-memory writes.

    Silently ignored in group chats — we never confirm opt-out status in front
    of other students (Constitution §"Opt-out": do not reveal who opted out).
    """
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if msg is None or user is None or chat is None or chat.type != "private":
        return
    ids = _load_optouts()
    if user.id not in ids:
        ids.add(user.id)
        _write_optouts(ids)
    await msg.reply_text(
        "You're opted out — I won't include your messages in the digest or "
        "learn from them. Send /optin in DM to reverse."
    )


async def cmd_optin(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """DM-only: reverse a prior /optout."""
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if msg is None or user is None or chat is None or chat.type != "private":
        return
    ids = _load_optouts()
    if user.id in ids:
        ids.discard(user.id)
        _write_optouts(ids)
        await msg.reply_text("You're back in — your messages will be logged again.")
    else:
        await msg.reply_text("You weren't opted out.")


async def _is_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True iff the asker is the cohort owner (Bayram).
    Used to gate proactive-outbound publish commands."""
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None or chat.type != "private":
        return False
    env = (os.environ.get("OWNER_TELEGRAM_USER_ID") or "").strip()
    if env:
        try:
            return user.id == int(env)
        except ValueError:
            pass
    # Fallback: ask Telegram who the cohort group's creator is.
    try:
        admins = await context.bot.get_chat_administrators(COHORT_GROUP_CHAT_ID)
        for a in admins:
            if getattr(a, "status", None) == "creator":
                creator_id = getattr(getattr(a, "user", None), "id", 0)
                return user.id == int(creator_id)
    except Exception:
        logger.exception("_is_owner: get_chat_administrators failed")
    return False


async def cmd_post_retro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only, DM-only: publishes the staged Sunday retro to the cohort group.

    Workflow:
    1. Sunday 09:00 PT, TARS DMs the owner with a generated draft.
    2. Owner reviews. If they want to edit, they can rewrite /data/pending_retro.md
       (via fly ssh) before calling /post_retro.
    3. /post_retro publishes the on-disk draft to the cohort group.
    """
    msg = update.effective_message
    if msg is None:
        return
    if not await _is_owner(update, context):
        # Silent for non-owners — don't leak the existence of the command.
        return
    text = load_pending_retro()
    if text is None:
        await msg.reply_text(
            "No fresh retro draft staged. Drafts auto-generate Sundays 09:00 PT "
            "and expire after 24h."
        )
        return
    body = text[:4000]
    # Convert lite-markdown to Telegram HTML. See tg_format.py for rationale —
    # legacy Markdown is too brittle for Cyrillic + URLs, has 400'd retros to
    # the cohort group with literal asterisks showing.
    html_body = markdown_to_telegram_html(body)
    sent = None
    last_err = None
    try:
        sent = await context.bot.send_message(
            chat_id=COHORT_GROUP_CHAT_ID,
            text=html_body,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        last_err = exc
        logger.warning("cmd_post_retro: HTML send failed; falling back to plain",
                       exc_info=True)
        try:
            sent = await context.bot.send_message(
                chat_id=COHORT_GROUP_CHAT_ID,
                text=body,
                disable_web_page_preview=True,
            )
        except Exception as exc2:
            last_err = exc2
    if sent is None:
        await msg.reply_text(f"Publish failed: {last_err!r}")
        return
    # Persist outbound + archive + clear pending
    try:
        _persist_outbound(sent, body, reply_to_id=None)
    except Exception:
        logger.exception("cmd_post_retro: persist failed")
    try:
        archive_published_retro(text)
    except Exception:
        logger.exception("cmd_post_retro: archive failed")
    await msg.reply_text(f"Posted to cohort group ({len(body)} chars). Archived.")


async def cmd_skip_retro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only, DM-only: discards the staged Sunday retro draft."""
    msg = update.effective_message
    if msg is None:
        return
    if not await _is_owner(update, context):
        return
    if PENDING_RETRO_PATH.exists():
        try:
            PENDING_RETRO_PATH.unlink()
            await msg.reply_text("Discarded.")
        except Exception as exc:
            await msg.reply_text(f"Failed to discard: {exc!r}")
    else:
        await msg.reply_text("No staged retro.")


# ───────────────────────── owner-only quiz/poll publishing ─────────────────
# Anonymous Telegram quiz polls. Per Telegram API: when is_anonymous=True,
# the bot only sees aggregate Poll counts — no PollAnswer events with user_id.
# Each student sees their own correctness inline (Telegram UI), instructor
# sees how many got each option. Matches "auto-collected · auto-graded" on
# slide 06 without exposing per-user answers.
#
# Workshop 2 retrieval quiz (slide 06). All 5 questions are answerable from
# Workshop 1 alone (workshop1-notes-ru.md) — no new knowledge required.
# Telegram limits: question ≤ 300 chars, each option ≤ 100 chars, max 10 options,
# explanation ≤ 200 chars.

QUIZ_WORKSHOP1_RETRIEVAL = [
    {
        "question": "S1 Q1 · What does Plan Mode prevent in Claude Code / Codex?",
        "options": [
            "The model from making up facts (hallucinations)",
            "The model from writing/editing files until you approve the plan",
            "The model from running Bash commands",
            "The model from searching the web",
        ],
        "correct_option_id": 1,
        "explanation": "Plan Mode adds a system instruction: 'do not edit files, describe a plan'. (S1 §5)",
    },
    {
        "question": "S1 Q2 · Constitution vs CLAUDE.md / AGENTS.md — what's the real difference?",
        "options": [
            "They're the same thing — different names for one concept",
            "Constitution = prod-agent system prompt; CLAUDE.md = coding-assistant prompt",
            "Constitution is for humans; CLAUDE.md is for machines",
            "CLAUDE.md is just a longer Constitution",
        ],
        "correct_option_id": 1,
        "explanation": "Constitution is the agent's prod prompt (loaded once); CLAUDE.md is the coding assistant's prompt (loaded every turn). (S1 §6)",
    },
    {
        "question": "S1 Q3 · Same prompt, same model — 10 different implementations. Why?",
        "options": [
            "The model's cache was cold and invalidated between calls",
            "Each student used a different model version",
            "LLM sampling is non-deterministic — same prompt yields different outputs",
            "Claude Code automatically adds randomness to prevent plagiarism",
        ],
        "correct_option_id": 2,
        "explanation": "Stochasticity demo: ~10 different opt-out implementations from one prompt. Variance is real; constraints close it. (S1 §4)",
    },
    {
        "question": "S1 Q4 · The '100:1' metric for production AI agents — what does it tell you?",
        "options": [
            "Send 100 messages, expect 1 response — the model is slow",
            "Output tokens should be 100× input tokens — more is better",
            "Healthy ratio is ~100 input : 1 output. Close to 1:1 means too little context provided",
            "100 tools, 1 model — the orchestration ratio",
        ],
        "correct_option_id": 2,
        "explanation": "Empirical: prod agents see ~100:1 input-to-output tokens. Near 1:1 = under-investing in context. Directional, not strict. (S1 §3)",
    },
    {
        "question": "S1 Q5 · Operator → Approver — what actually shifts?",
        "options": [
            "Developer goes from writing code to writing specs and reviewing results",
            "Developer becomes the AI's manager (HR / admin role)",
            "Operator and Approver are the same role — different terms",
            "Approver is the AI; Operator is the human",
        ],
        "correct_option_id": 0,
        "explanation": "S1 table: 'пишет код' → 'пишет спеку, ревьюит результат'. One person = N agents; testing becomes statistical. (S1 §2)",
    },
]

QUIZ_LIBRARY = {
    "workshop1_retrieval": QUIZ_WORKSHOP1_RETRIEVAL,
}


async def _send_one_poll(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    question: str,
    options: list[str],
    correct_option_id: int,
    explanation: str | None,
) -> None:
    """Send a single anonymous quiz poll. Centralised so all paths share the
    same anonymity / type / explanation policy.

    `is_anonymous=True` is REQUIRED — per Telegram, only anonymous polls suppress
    PollAnswer updates that would otherwise expose per-user choices.
    """
    # python-telegram-bot types correct_option_id as Literal[0..9]; cast for the
    # generic int we accept at the boundary (Telegram's own cap is 10 options).
    await context.bot.send_poll(
        chat_id=chat_id,
        question=question[:300],
        options=[o[:100] for o in options],
        is_anonymous=True,
        type="quiz",
        correct_option_id=correct_option_id,  # type: ignore[arg-type]
        explanation=(explanation or "")[:200] or None,
    )


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: post a pre-defined quiz as a sequence of anonymous polls.

    Usage:
      /quiz                          → list available quizzes
      /quiz workshop1_retrieval      → post to THIS DM (test mode)
      /quiz workshop1_retrieval --to-group  → post to cohort group (production)

    Silent for non-owners — don't leak the command's existence to students."""
    msg = update.effective_message
    if msg is None:
        return
    if not await _is_owner(update, context):
        return
    args = context.args or []
    if not args:
        names = ", ".join(QUIZ_LIBRARY.keys())
        await msg.reply_text(
            f"Usage: /quiz <name> [--to-group]\nAvailable: {names}\n"
            "Default target = this DM (test mode). Add --to-group to publish."
        )
        return
    name = args[0]
    to_group = "--to-group" in args[1:]
    questions = QUIZ_LIBRARY.get(name)
    if questions is None:
        await msg.reply_text(
            f"Unknown quiz: {name}. Available: {', '.join(QUIZ_LIBRARY.keys())}"
        )
        return
    target = COHORT_GROUP_CHAT_ID if to_group else msg.chat_id
    label = "cohort group" if to_group else "this DM"
    await msg.reply_text(
        f"Posting {len(questions)} anonymous quiz poll(s) to {label}…"
    )
    for i, q in enumerate(questions, start=1):
        try:
            await _send_one_poll(
                context,
                chat_id=target,
                question=q["question"],
                options=q["options"],
                correct_option_id=q["correct_option_id"],
                explanation=q.get("explanation"),
            )
            # Small gap so the channel doesn't render 5 polls in one chunk and
            # so we stay well under Telegram's 30 msg/sec global rate ceiling.
            await asyncio.sleep(1.0)
        except Exception as exc:
            logger.exception("cmd_quiz: send_poll failed at Q%d", i)
            await msg.reply_text(f"Q{i} failed: {exc!r}")
            return
    await msg.reply_text(f"Posted {len(questions)}/{len(questions)} to {label}. Anonymous; bot sees aggregate counts only.")


async def cmd_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: ad-hoc anonymous quiz poll. Posts to wherever the command
    came from (DM for testing, group if owner sends it there).

    Usage:
      /poll <question> | <opt1> | <opt2> | ... | correct=<index> [| explain=<text>]

    Example:
      /poll What blocks Edit/Write in our hook? | system prompt | PreToolUse deny | nothing | correct=1 | explain=Hooks are code, prompts are advisory.
    """
    msg = update.effective_message
    if msg is None:
        return
    if not await _is_owner(update, context):
        return
    raw = (msg.text or "").split(maxsplit=1)
    if len(raw) < 2:
        await msg.reply_text(
            "Usage: /poll <question> | <opt1> | <opt2> | ... | correct=<index> [| explain=<text>]\n"
            "Posts an anonymous quiz poll to THIS chat."
        )
        return
    parts = [p.strip() for p in raw[1].split("|")]
    if len(parts) < 4:
        await msg.reply_text("Need: question | opt1 | opt2 | correct=N (minimum 2 options + correct)")
        return
    question = parts[0]
    correct_idx: int | None = None
    explanation: str | None = None
    options: list[str] = []
    for p in parts[1:]:
        if p.startswith("correct="):
            try:
                correct_idx = int(p.split("=", 1)[1])
            except ValueError:
                await msg.reply_text(f"Bad correct= value: {p!r}")
                return
        elif p.lower().startswith("explain=") or p.lower().startswith("explanation="):
            explanation = p.split("=", 1)[1].strip()
        else:
            options.append(p)
    if len(options) < 2:
        await msg.reply_text(f"Need ≥ 2 options (got {len(options)}).")
        return
    if correct_idx is None or correct_idx < 0 or correct_idx >= len(options):
        await msg.reply_text(
            f"correct= must be a 0-based index into options. "
            f"got correct={correct_idx}, options={len(options)}."
        )
        return
    try:
        await _send_one_poll(
            context,
            chat_id=msg.chat_id,
            question=question,
            options=options,
            correct_option_id=correct_idx,
            explanation=explanation,
        )
    except Exception as exc:
        logger.exception("cmd_poll: send_poll failed")
        await msg.reply_text(f"send_poll failed: {exc!r}")


async def cmd_preview_retro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only, DM-only: regenerates the retro draft on demand and DMs it.
    Useful for testing the pipeline outside the Sunday 9am window."""
    msg = update.effective_message
    if msg is None:
        return
    if not await _is_owner(update, context):
        return
    await msg.reply_text("Generating draft…")

    class _FakeContext:
        def __init__(self, bot):
            self.bot = bot

    try:
        await run_weekly_retro_draft_job(_FakeContext(context.bot))
    except Exception as exc:
        await msg.reply_text(f"Draft job failed: {exc!r}")


def extract_attachments(msg) -> list[str]:
    """Return a list of attachment-type tags (e.g., ['photo'], ['document:foo.pdf'])."""
    out: list[str] = []
    if msg.photo:
        out.append("photo")
    if msg.document:
        name = msg.document.file_name or "?"
        out.append(f"document:{name}")
    if msg.voice:
        dur = msg.voice.duration
        out.append(f"voice:{dur}s")
    if msg.audio:
        out.append("audio")
    if msg.video:
        out.append("video")
    if msg.video_note:
        out.append("video_note")
    if msg.animation:
        out.append("animation")
    if msg.sticker:
        out.append("sticker")
    if msg.poll:
        q = (msg.poll.question or "")[:80]
        out.append(f"poll:{q}")
    if msg.location:
        out.append("location")
    if msg.contact:
        out.append("contact")
    return out


async def passive_log(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Append every cohort-group message (text + attachments) to JSONL.

    Captures text, captions, and attachment metadata. Doesn't download files —
    that's S3 territory (MCP/vision integration). For V1, the digest sees
    attachment TYPES and any caption text, so it can note 'Ruslan shared a
    screenshot' or 'Igor sent a 45s voice note' even without content extraction.

    Errors silenced — logging never blocks the bot.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if msg is None or chat is None or user is None:
        return
    if chat.id != COHORT_GROUP_CHAT_ID:
        return
    if user.is_bot:
        return
    if user.id in _load_optouts():
        # Honor the Constitution's opt-out promise: no JSONL, no working
        # memory, no digest inclusion. The student remains free to ask
        # questions in the group; we just don't *record* them.
        return
    text = msg.text or msg.caption or ""
    attachments = extract_attachments(msg)
    if not text and not attachments:
        # Skip pure service messages (joins, leaves, etc.)
        return
    msg_ts = msg.date or datetime.now(timezone.utc)
    reply_to_id = msg.reply_to_message.message_id if msg.reply_to_message else None
    try:
        record = {
            "ts": msg_ts.isoformat(),
            "msg_id": msg.message_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "text": text,
            "attachments": attachments,
            "reply_to": reply_to_id,
            "forward_from": (
                msg.forward_origin.type.value if msg.forward_origin else None
            ),
        }
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        # PT date — see comment in _persist_outbound. The daily digest reads
        # this file by PT date at firing time so the contents cover one PT day.
        date_str = datetime.now(DIGEST_TIMEZONE).strftime("%Y-%m-%d")
        path = DATA_DIR / f"messages-{date_str}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("passive_log failed")
    # Dual-write into working-memory SQLite. Annotate text-less messages with
    # an attachment tag so the rolling window still surfaces "Igor sent a
    # screenshot" instead of silently dropping it.
    wm_text = text or f"[{', '.join(attachments)}]" if attachments else text
    if not wm_text:
        return
    try:
        working_memory.record_message(
            chat_id=chat.id,
            msg_id=msg.message_id,
            ts=msg_ts,
            user_id=user.id,
            user_name=user.username or user.first_name,
            text=wm_text,
            reply_to=reply_to_id,
        )
    except Exception:
        logger.exception("working_memory.record_message failed")


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Initialize working-memory SQLite up front so the first message doesn't
    # race the table creation.
    try:
        working_memory.init_db()
    except Exception:
        logger.exception("working_memory.init_db failed")

    # Group-level passive logger runs FIRST (group=-1) on every text-bearing
    # message in the cohort group. Captions on photos/docs are kept; pure
    # media without caption is dropped (working memory needs text to be
    # useful). Doesn't reply, just persists to /data/.
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION)
            & filters.Chat(COHORT_GROUP_CHAT_ID) & ~filters.COMMAND,
            passive_log,
        ),
        group=-1,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_health))
    app.add_handler(CommandHandler("ask", cmd_ask))
    # Opt-out is DM-only (handler enforces); in groups the command is silent.
    app.add_handler(CommandHandler("optout", cmd_optout))
    app.add_handler(CommandHandler("optin", cmd_optin))
    # Owner-only retro publish controls. Silent for non-owners (don't leak).
    app.add_handler(CommandHandler("post_retro", cmd_post_retro))
    app.add_handler(CommandHandler("skip_retro", cmd_skip_retro))
    app.add_handler(CommandHandler("preview_retro", cmd_preview_retro))
    # Owner-only anonymous quiz polls. /quiz posts a pre-defined batch
    # (Workshop 2 retrieval quiz lives in QUIZ_LIBRARY); /poll is ad-hoc.
    # Default target = sender's chat (DM for testing). --to-group publishes
    # to the cohort group.
    app.add_handler(CommandHandler("quiz", cmd_quiz))
    app.add_handler(CommandHandler("poll", cmd_poll))
    # Substring match on @<bot_username> instead of the entity-based
    # `filters.Mention()`. Telegram's server-side `mention` entity drops on
    # some edited / multi-paragraph messages, leaving the bot silent — past
    # incidents: 2026-05-02 13:53, 2026-05-02 16:24.
    app.add_handler(MessageHandler(
        _mentions_bot & filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL,
        handle_query,
    ))
    # Reply-to-bot continues the thread. Must be a reply to OUR bot specifically;
    # plain `filters.REPLY` matches every reply in the group, including pin/forward
    # service messages whose `reply_to_message` points at the pinned target — those
    # spuriously woke handle_query and made TARS post "Mention me with a question".
    app.add_handler(MessageHandler(
        _reply_to_bot & filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL,
        handle_query,
    ))
    # Private DMs from a verified cohort member. Match text, captions, and
    # bare image attachments (so a photo with no caption still gets seen).
    # Voice/video without caption falls through to the catch-all logger.
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.PHOTO | filters.Document.IMAGE)
        & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_query,
    ))

    # Catch-all for DMs that didn't match anything above (e.g. pure media
    # without caption, edits, polls). Log so we don't silently drop again.
    async def _dm_unmatched(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        msg = update.effective_message
        user = update.effective_user
        if chat is None or chat.type != "private" or user is None or msg is None:
            return
        kinds = []
        if msg.photo: kinds.append("photo")
        if msg.document: kinds.append("document")
        if msg.voice: kinds.append("voice")
        if msg.video: kinds.append("video")
        if msg.sticker: kinds.append("sticker")
        if msg.animation: kinds.append("animation")
        logger.warning(
            "DM unmatched from %s: text=%r caption=%r media=%s",
            user.username or user.id, msg.text, msg.caption, kinds or "none",
        )

    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND,
        _dm_unmatched,
    ))

    # Daily digest at 23:00 Pacific
    if app.job_queue is not None:
        app.job_queue.run_daily(
            run_daily_job,
            time=dtime(hour=DIGEST_HOUR, minute=0, tzinfo=DIGEST_TIMEZONE),
            name="daily_digest",
            job_kwargs={"misfire_grace_time": 300, "coalesce": True},
        )
        logger.info("daily digest scheduled for 23:00 America/Los_Angeles")
        # Weekly retro DRAFT job — Sundays 09:00 PT. TARS does NOT autopost.
        # It generates the retro, stages it to /data/pending_retro.md, and DMs
        # the draft to the cohort owner for approval. Owner publishes via
        # /post_retro (or discards via /skip_retro) — see cmd_post_retro below.
        # Rule: any TARS-initiated outbound to the cohort needs explicit owner
        # approval. Reactive replies (mentions/DMs) are exempt because the user
        # triggered them.
        app.job_queue.run_daily(
            run_weekly_retro_draft_job,
            time=dtime(hour=RETRO_DRAFT_HOUR, minute=0, tzinfo=DIGEST_TIMEZONE),
            days=(RETRO_WEEKDAY,),  # Sunday only
            name="weekly_retro_draft",
            job_kwargs={"misfire_grace_time": 1800, "coalesce": True},
        )
        logger.info("weekly retro DRAFT scheduled for Sundays 09:00 America/Los_Angeles "
                    "(owner approves via /post_retro)")
    else:
        logger.warning("JobQueue unavailable — daily digest + weekly retro NOT scheduled")

    if WEBHOOK_URL:
        logger.info("starting webhook on :%d -> %s", PORT, WEBHOOK_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("no TELEGRAM_WEBHOOK_URL set, falling back to long-polling")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
