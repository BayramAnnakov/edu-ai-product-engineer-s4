# pyright: reportMissingImports=false
"""Convert lite-markdown to Telegram HTML for proactive outbound posts.

Why HTML instead of Markdown / MarkdownV2:
- Telegram's *legacy Markdown* is brittle: subtle issues (Cyrillic word boundaries,
  bare URLs with underscores, colons adjacent to bold close, etc.) can cause the
  parser to 400 the whole message. When that happens, our send-loop falls back to
  parse_mode=None and the message ships as plain text — every `*` and `[`/`]`
  showing literally to the cohort.
- *MarkdownV2* requires escaping `_*[]()~`>#+-=|{}.!` in plain text — every period,
  hyphen, exclamation. The escape burden falls on the model and is fragile.
- *HTML* is structural, not character-driven. Telegram supports a small allowlist
  (`<b>`, `<i>`, `<a>`, `<code>`, `<pre>`, `<u>`, `<s>`). We emit only `<b>` and
  `<a>` for retro posts, with `&`, `<`, `>` HTML-escaped in plain text. No
  character-class landmines.

The converter recognizes:
- `*bold*`  (single asterisks, word-boundary aware)
- `[text](url)`

Everything else is plain text (HTML-escaped). `**double**` is intentionally NOT
recognized — the system prompt forbids it. If the model emits it anyway, the inner
`*foo*` matches and the outer `*`s ship as literal asterisks (graceful degradation).
"""
from __future__ import annotations

import html
import re

# Markdown link: [text](url). text excludes `]`; url excludes `)`.
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# Single-asterisk bold with word-boundary lookarounds. \w in Python 3 re is
# Unicode-aware, so it correctly excludes Cyrillic word chars on either side.
BOLD_RE = re.compile(r"(?<!\w)\*([^\n*]+?)\*(?!\w)")

# Sentinels chosen to be unlikely to occur naturally in cohort posts.
_LINK_SENTINEL = "\x00LINK\x00{idx}\x00"
_BOLD_SENTINEL = "\x00BOLD\x00{idx}\x00"


def markdown_to_telegram_html(text: str) -> str:
    """Render lite-markdown as Telegram HTML.

    Order of operations:
    1. Extract `[text](url)` to opaque sentinels (so HTML-escape doesn't break URLs)
    2. Extract `*bold*` to opaque sentinels
    3. HTML-escape what remains (plain text)
    4. Restore bold sentinels as `<b>...</b>`, with text inside also escaped
    5. Restore link sentinels as `<a href="...">...</a>`
    """
    # 1. Extract links first so URLs don't get double-processed by bold rules.
    links: list[tuple[str, str]] = []

    def _link_sub(m: re.Match) -> str:
        idx = len(links)
        links.append((m.group(1), m.group(2)))
        return _LINK_SENTINEL.format(idx=idx)

    text = LINK_RE.sub(_link_sub, text)

    # 2. Extract bold spans
    bolds: list[str] = []

    def _bold_sub(m: re.Match) -> str:
        idx = len(bolds)
        bolds.append(m.group(1))
        return _BOLD_SENTINEL.format(idx=idx)

    text = BOLD_RE.sub(_bold_sub, text)

    # 3. HTML-escape everything that remains (plain prose)
    text = html.escape(text, quote=False)

    # 4. Restore bold runs (with inner text escaped — defends against any `<`/`>`
    # the model emitted inside a bold span, e.g. `*<= 3 bullets*`).
    for idx, inner in enumerate(bolds):
        text = text.replace(
            _BOLD_SENTINEL.format(idx=idx),
            f"<b>{html.escape(inner, quote=False)}</b>",
        )

    # 5. Restore links. URL goes in href="..." so use quote=True; visible text
    # uses quote=False (plain HTML body context).
    for idx, (link_text, link_url) in enumerate(links):
        text = text.replace(
            _LINK_SENTINEL.format(idx=idx),
            f'<a href="{html.escape(link_url, quote=True)}">'
            f'{html.escape(link_text, quote=False)}</a>',
        )

    return text
