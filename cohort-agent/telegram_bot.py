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

from digest import run_daily_job
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
MAX_PER_HOUR = int(os.environ.get("MAX_QUERIES_PER_HOUR", "30"))
MEMBER_CACHE_TTL_SEC = 300  # cache getChatMember results for 5 min

DATA_DIR = Path(os.environ.get("TARS_DATA_DIR", "/data"))
DIGEST_TIMEZONE = ZoneInfo("America/Los_Angeles")
DIGEST_HOUR = 23  # 23:00 Pacific

_anthropic: Anthropic | None = None
_recent_queries: deque[float] = deque(maxlen=MAX_PER_HOUR + 10)
_member_cache: dict[int, tuple[bool, float]] = {}  # user_id -> (is_member, fetched_at)
ALLOWED_STATUSES = {"creator", "administrator", "member", "restricted"}


def anthropic_client() -> Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = Anthropic()
    return _anthropic


def rate_limited() -> bool:
    now = time.monotonic()
    cutoff = now - 3600
    while _recent_queries and _recent_queries[0] < cutoff:
        _recent_queries.popleft()
    return len(_recent_queries) >= MAX_PER_HOUR


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
    if rate_limited():
        await msg.reply_text("Hourly query limit hit. Cooling down.")
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

    _recent_queries.append(time.monotonic())
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

    async def _send(text: str) -> None:
        for mode in ("Markdown", None):
            try:
                await placeholder.edit_text(text, parse_mode=mode)
                return
            except Exception:
                continue
        try:
            await msg.reply_text(text, reply_to_message_id=msg.message_id)
        except Exception:
            logger.exception("failed to send response")

    await _send(body)


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
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
        )
        logger.info("daily digest scheduled for 23:00 America/Los_Angeles")
    else:
        logger.warning("JobQueue unavailable — daily digest NOT scheduled")

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
