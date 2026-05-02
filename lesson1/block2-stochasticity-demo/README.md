# Block 2 — Stochasticity Demo (TARS edition)

**Purpose:** prove to the room that even with identical inputs (same prompt, same Constitution, same starter repo), AI coding outputs diverge. Sets up the lesson's thesis: *"constraints and review are not optional. They are the work."*

This block uses **TARS** (`cohort-agent/`) as the starter repo — the same Telegram bot the cohort sees in their group. TARS is the course-long demo project. Students aren't editing a toy scooter API; they're shipping a feature into the real bot they all just met.

## The locked prompt

```
Add a way for cohort members to opt out of having their Telegram
messages logged for the daily digest.
```

This is deliberately ambiguous. Expected divergence axes:
- **Storage:** new file on `/data/` volume? new memory store path? in-process set with reload? row in `optouts.json`?
- **Trigger:** `/optout` slash command? mention-based? a button? DM-only?
- **Retroactivity:** delete already-logged messages? only future? offer both?
- **Granularity:** per-message ("delete this one") vs. per-user-forever?
- **Confirmation:** silent vs. explicit reply?
- **Opt back in:** `/optin` provided? what about admins overriding?
- **Privacy of the opt-outs themselves:** does TARS publicly acknowledge who opted out?
- **Touched files:** does it edit `passive_log` only, or also the digest pipeline?

The variance is wider than a CRUD endpoint because TARS has more moving parts: passive logger + JSONL writer + memory store + digest job + Constitution rules + bot UX layer. Same prompt, same model, different code.

## The setup

The starter repo is a snapshot of `cohort-agent/` (minus `venv/`, `.env`, and any IDs):

```bash
mkdir -p /tmp/tars-block2 && rsync -a \
  --exclude=venv --exclude='.env' --exclude='__pycache__' --exclude='.DS_Store' \
  /path/to/cohort-agent/ /tmp/tars-block2/
```

Students don't need fly access, an API key, or a working bot. They only need Claude Code + the source tree to read.

## Dry-run procedure (Bayram, before class)

Run the prompt 3× against isolated copies:

```bash
for i in 1 2 3; do
  rm -rf /tmp/tars-run-$i
  rsync -a --exclude=venv --exclude='.env' --exclude='__pycache__' \
    cohort-agent/ /tmp/tars-run-$i/
done

for i in 1 2 3; do
  cd /tmp/tars-run-$i
  claude -p "Add a way for cohort members to opt out of having their Telegram messages logged for the daily digest." \
    --permission-mode acceptEdits > /tmp/tars-run-$i.log
done
```

Compare with `diff -ru /tmp/tars-run-1 /tmp/tars-run-2`. Look at:
1. *Which files changed* (passive_log only? + digest? + Constitution? + new file?)
2. *Where opt-out state lives* (this is the biggest spread)
3. *Whether the model proposes a slash command* and what name (`/optout`, `/mute`, `/forget`, `/privacy`)

If the 3 outputs are 60-95% similar (visible divergence in the axes above), the demo is ready. If they're 95%+ similar, see "Risk: spread compresses" below.

## In-class flow (Block 2, 15 min)

1. **Setup (90 sec):** Bayram opens TARS source on screen. *"You all just met TARS in the chat. Here's its source. We're going to ship a feature into it together. Same prompt, same starter repo, same Constitution. Each of you runs it on your own machine."*
2. **Run (3-5 min):** Bayram runs first, projects output. Students run on theirs from the snapshot tarball.
3. **Vote (60 sec):** *"Rate similarity to my output, 0-100% in chat."*
4. **Plot (30 sec):** show histogram on screen. Expected spread: 50-95%.
5. **Teaching beat (3 min):** *"We have identical inputs and we still diverge. Constraints and review are not optional. They are the work."* + privacy callback: *"And notice — every single one of these solutions made a different choice about what counts as 'opting out.' That ambiguity is the Constitution's job to close."*
6. **Pivot to verification (4-5 min):** Anthropic's #1 move — verification is the highest-leverage thing you can add to a Constitution. We'll see this play out in Block 5.

## Risk: spread compresses

If 3 dry-runs all produce ~90%+ similar outputs (could happen if Claude tightly converges on `/optout` + `optouts.json` + skip-in-passive_log), the backup is to **change the prompt mid-run**: ask half the room to run *"Let users delete a single past message of theirs from the digest log retroactively."* (per-message, retroactive — opens the same axes harder). The two prompts together produce visible spread even if either alone wouldn't.

The fallback teaching beat: *"the model is more predictable than you'd expect — but ambiguity in a one-line prompt is still ambiguity. The Constitution is what closes the gap."* Still lands the lesson, weaker than the variance-histogram version.

## Sharing the snapshot with the cohort

Drop in Telegram during Block 1 (background install msg, while talking):

```
🤖 BLOCK 2 SETUP
TARS snapshot: <link to a tarball or gist>
tar -xzf tars-block2.tgz && cd tars-block2 && claude (or codex)
Wait for the prompt I'll drop in 12 minutes.
```

(Bayram: tarball or gist tonight. The snapshot is `cohort-agent/` minus `venv/` and `.env`.)
