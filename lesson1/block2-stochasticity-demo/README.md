# Block 2 — Stochasticity Demo

You'll run a single one-line prompt against a real codebase. So will everyone else in the room. The point is to see what *diverges* — and why.

The starter codebase is **TARS** (`cohort-agent/`) — the Telegram bot you've already met in the cohort group. Same source. Same Constitution. Same model. Same prompt. Different code falls out.

## The locked prompt

```
Add a way for cohort members to opt out of having their Telegram
messages logged for the daily digest.
```

Deliberately ambiguous. Watch for divergence on:

- **Storage** — new file on disk? memory store path? in-process set? what filename?
- **Trigger** — slash command? mention? button? DM-only?
- **Retroactivity** — delete already-logged messages? only future? both?
- **Granularity** — per-message vs. per-user-forever?
- **Confirmation** — silent vs. explicit reply?
- **Opt back in** — `/optin` provided?
- **Privacy of opt-outs themselves** — does the bot publicly acknowledge who opted out?
- **Touched files** — passive logger only? + digest pipeline? + Constitution?

The surface is wider than a CRUD endpoint: TARS has a passive logger + JSONL writer + memory store + daily digest job + Constitution rules + bot UX layer. Same prompt, same model, different code.

## The setup

```bash
git clone https://github.com/BayramAnnakov/edu-ai-product-engineer-s4.git
cd edu-ai-product-engineer-s4/cohort-agent
```

You don't need fly access, an API key, or a working bot — only Claude Code (or Codex) + the source tree to read.

Run the prompt:

```bash
claude -p "Add a way for cohort members to opt out of having their Telegram messages logged for the daily digest." --permission-mode acceptEdits
```

Then compare your output with the room.
