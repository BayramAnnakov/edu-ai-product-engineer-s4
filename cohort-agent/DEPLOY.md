# TARS — Deployment Runbook

**Goal:** TARS provisioned + bot in Telegram + deployed to fly.io, queryable from `edu-ai-product-engineer-s4` group, before Lesson 1 (May 2, 2026).

**Estimated time:** 25-40 minutes if everything goes clean. Most failure modes are documented inline.

---

## Prereqs (one-time setup)

- [ ] Anthropic API key (with Managed Agents beta access — enabled by default for API accounts).
- [ ] `fly` CLI installed and logged in (`fly auth whoami` returns your account).
- [ ] Python 3.12+ available locally.
- [ ] You're already in `~/GH/edu-ai-product-engineer/edu-ai-product-engineer-s4/cohort-agent/`.

---

## Step 1 — Local provisioning (5-10 min)

```bash
cd cohort-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Source your Anthropic key (wherever it lives)
export ANTHROPIC_API_KEY=sk-ant-...

python provision.py
```

**What this does:** creates the agent (`edu-aipe-s4-tars`, model `claude-opus-4-7`, system prompt = `memory_seeds/00-constitution.md`), the environment, and two memory stores. Syncs all `memory_seeds/*.md` files except the Constitution into the knowledge store. Idempotent — safe to re-run.

**Expected output (last few lines):**
```
[knowledge] sync: 5 created, 0 updated, 0 unchanged
[learnings] seeded skeleton: /learnings/staged/.keep
============================================================
Set these as Fly secrets:
  fly secrets set --app edu-aipe-s4-tars \
      COHORT_AGENT_ID=agnt_... \
      COHORT_ENVIRONMENT_ID=env_... \
      COHORT_KNOWLEDGE_STORE_ID=memstore_... \
      COHORT_LEARNINGS_STORE_ID=memstore_...
============================================================
```

**Capture the four IDs.** You'll paste them in Step 4.

### Failure modes

- `403 / managed-agents-2026-04-01 not enabled` → request access at https://claude.com/form/claude-managed-agents (the docs say this is enabled by default for API accounts but verify).
- `Cannot access attribute "agents"` → `pip install -U anthropic` for the latest beta types.
- `ROBIN_*` env vars showing up — those are from onsa-robin's pattern; you can ignore them. Our env vars are `COHORT_*`.

---

## Step 2 — Create the Telegram bot via @BotFather (3 min)

In your Telegram client:

1. Open chat with **@BotFather**.
2. Send: `/newbot`
3. When asked for the bot's name: **`TARS — Cohort 4 TA`**
4. When asked for the username: **`edu_aipe_s4_tars_bot`** (must end in `bot`)
5. Save the token BotFather replies with — it looks like `123456789:ABCdef-ghi_JKL...`

Then add the bot to the cohort group:

6. Open `edu-ai-product-engineer-s4` group.
7. Group settings → **Add Members** → search `edu_aipe_s4_tars_bot` → Add.
8. Make the bot an **admin** if you want it to read all messages (otherwise it only sees mentions and slash commands — which is fine for our use case; admin not required).
9. Disable group privacy if you want the bot to read all messages: send `/setprivacy` to BotFather, pick the bot, choose `Disable`. (Default `Enabled` means bot only sees mentions/commands — recommended for now.)

### Failure modes

- Username taken → try `edu_aipe_s4_tars_assistant_bot` or `edu_aipe_s4_tars_ta_bot`.
- BotFather doesn't reply within 30 sec → retry the command.

---

## Step 3 — fly.io app creation (2 min)

```bash
# from cohort-agent/ directory
fly apps create edu-aipe-s4-tars
# (or: fly launch --no-deploy --name edu-aipe-s4-tars  — uses fly.toml in cwd)
```

If `edu-aipe-s4-tars` is taken on fly.io, edit `fly.toml`'s `app = "..."` line and pick another name (e.g., `edu-aipe-s4-tars-bot`). Update `TELEGRAM_WEBHOOK_URL` accordingly.

---

## Step 4 — Set fly secrets (2 min)

```bash
fly secrets set --app edu-aipe-s4-tars \
    ANTHROPIC_API_KEY=sk-ant-... \
    TELEGRAM_BOT_TOKEN=123456789:ABCdef... \
    COHORT_AGENT_ID=agnt_... \
    COHORT_ENVIRONMENT_ID=env_... \
    COHORT_KNOWLEDGE_STORE_ID=memstore_... \
    COHORT_LEARNINGS_STORE_ID=memstore_...
```

Verify:
```bash
fly secrets list --app edu-aipe-s4-tars
```

---

## Step 5 — Deploy (3-5 min)

```bash
fly deploy --app edu-aipe-s4-tars
```

`fly.toml` already specifies port 8080, /health endpoint, and the webhook URL. The `telegram_bot.py` registers the webhook on startup automatically.

Watch the logs for confirmation:
```bash
fly logs --app edu-aipe-s4-tars
```

You're looking for:
```
[INFO] tars: starting webhook on :8080 -> https://edu-aipe-s4-tars.fly.dev/webhook
[INFO] application: bot started
```

### Failure modes

- `Build failed: requirements.txt` → check Python version compatibility; `python-telegram-bot >= 21.6` requires Python 3.9+.
- Webhook registration fails → check `TELEGRAM_BOT_TOKEN` is set correctly. Run `fly ssh console` and `curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe`.
- App crashes on startup with `KeyError: 'ANTHROPIC_API_KEY'` → secret didn't propagate; re-run `fly secrets set` and `fly deploy --strategy immediate`.

---

## Step 6 — Smoke test (2 min)

In the cohort Telegram group, post:

```
@edu_aipe_s4_tars_bot summarize lesson 1 in 3 bullets
```

Expected:
- Within ~5 sec, bot reacts (typing indicator).
- Within ~15-30 sec, bot replies with grounded content + a citation to a seed path (e.g., `(see: /team/cohort-roster.md)`).

Other smoke tests:
```
/ping            → "ok"
/start           → persona greeting
/ask who is in the cohort?  → roster lookup citing /team/cohort-roster.md
```

### If the smoke test fails

1. **No response** → `fly logs --app edu-aipe-s4-tars`. Look for webhook errors.
2. **"TARS not provisioned" reply** → fly secrets are missing the four `COHORT_*_ID` values. Re-run Step 4.
3. **Empty response** → memory store probably wasn't synced. Re-run `python provision.py` locally with the IDs in env, then `fly deploy` again to refresh anything.
4. **Citation to a file that doesn't exist** → seed sync failed silently. Run `python memory_writer.py list --prefix /` and verify all expected files are there.

---

## Step 7 — Live demo dry-run (5 min)

Before Lesson 1 starts, run the actual demo query yourself to confirm latency + grounding:

```
@edu_aipe_s4_tars_bot what's your discretion setting?
```

Expected response time: 5-15 sec. Expected shape: a terse answer that pulls the value from `00-constitution.md` and cites it (e.g., `(see: 00-constitution.md)`).

If the response is slow (>30 sec) or thin, increase `QUERY_TIMEOUT_SEC` in `telegram_bot.py` and re-deploy.

---

## Post-Lesson-1 — transcript ingestion

After Lesson 1 ends (~9 PM your time), pull today's transcript via the `onsa-meetings` MCP. From a Claude Code session in this directory:

> *"Pull today's lesson 1 transcript via onsa-meetings MCP, save it to `transcript-2026-05-02.txt`, then run `python memory_writer.py write /transcripts/lesson-1-2026-05-02.md transcript-2026-05-02.txt`."*

Or by hand:
```bash
# in your venv with COHORT_KNOWLEDGE_STORE_ID exported
python memory_writer.py write /transcripts/lesson-1-2026-05-02.md path/to/transcript.txt
```

Verify ingestion:
```bash
python memory_writer.py list --prefix /transcripts/
```

By tomorrow morning, students querying TARS about *"what did Bayram say about X"* will get grounded answers from the transcript.

---

## Rollback / kill switch

If something goes catastrophically wrong during class:

```bash
fly scale count 0 --app edu-aipe-s4-tars   # bot stops responding
fly scale count 1 --app edu-aipe-s4-tars   # back online
```

Bot down ≠ class down. The cohort-agent code is on screen; the architectural beat survives even if the live call doesn't return. Block 8 has a documented "demo from source" backup path.

---

## Cost ceiling

Daily API budget: `DAILY_API_BUDGET_USD=10.0` (advisory, not enforced — S2 territory). With ~30 queries/day at ~$0.10/query average, that's plenty of headroom for the cohort. Monitor spend via the Anthropic Console for the first week.

---

## Status board (mark off as you go)

- [ ] Step 1: provision.py run, 4 IDs captured
- [ ] Step 2: bot created via BotFather, added to cohort group, token saved
- [ ] Step 3: fly app created
- [ ] Step 4: secrets set
- [ ] Step 5: fly deploy success, webhook registered, /health 200
- [ ] Step 6: smoke test passes — `/ping` and `@-mention` both respond
- [ ] Step 7: Block 8 dry-run query returns grounded answer
- [ ] (Post-S1) Step 8: transcript ingested
