# Wire your colleague — 5 min exercise

You leave Lesson 1 with a colleague that runs against one input. MVP. Not pretty. Not complete. Running.

The architecture is **Constitution + runtime = colleague**. You'll write the Constitution with help from your existing AI assistant, then point a 4-line SDK runtime at it. That's the whole shape of the S5 capstone.

---

## Pre-flight (do this BEFORE Block 7.5 starts)

Pick one runtime. **Python is the recommended path** — it's been validated end-to-end with a clean API-key auth path (~27s run, no extra setup). The Codex path requires a ChatGPT Pro/Plus subscription with `codex login` already done; an `OPENAI_API_KEY` alone will NOT work (silent 401).

- **Python (Claude Agent SDK)** — recommended:
  ```bash
  python3 -m venv venv && source venv/bin/activate    # required on modern macOS/Ubuntu (PEP 668)
  pip install claude-agent-sdk
  export ANTHROPIC_API_KEY=sk-ant-...                  # OR have Claude Code CLI installed and authed
  ```
- **JS (Codex SDK)** — only if you already have ChatGPT Pro/Plus + `codex login` configured:
  ```bash
  npm i @openai/codex-sdk
  codex login    # ChatGPT Pro/Plus subscription auth — OPENAI_API_KEY does NOT work
  ```

**60-second self-check before class:**
```bash
# Python path:
claude --version || echo "no Claude CLI — you'll need ANTHROPIC_API_KEY"
echo "${ANTHROPIC_API_KEY:0:8}" || echo "no API key set"
# At least ONE of these must work or Phase 3 will fail.

# Codex path:
codex --version && cat ~/.codex/auth.json >/dev/null 2>&1 && echo "codex authed" || echo "run codex login first"
```

Have ready (mentally — write them down on paper if it helps):
- Your AI assistant of choice running (Claude Code, Codex CLI, Cursor, JetBrains AI, or anything that reads `CLAUDE.md`/`AGENTS.md`)
- One sentence describing the recurring coding task you want a colleague to take over
- One sentence describing what would prove the colleague did it right (the "verifier")
- **2 specific past incidents** — actual times you did this task by hand. What was annoying? What would have helped? 1-2 sentences each. Don't sanitize them.

The incidents are the most important input. The dossier framework says: *rules derive from constraints, not from imagination*. Without incidents, your AI generates a generic Constitution; with them, every rule is grounded in a real failure you've already lived through.

If you don't have a task in mind, pick one from the [fallback tasks](#fallback-tasks-pick-one) at the bottom — each comes with 2 example incidents you can use.

---

## The exercise

### Phase 1 — Generate your Constitution (2 min)

The single most important move in the dossier framework: **rules derive from incidents, not from imagination.** Generic prompts produce generic Constitutions. So before asking your AI to write rules, you tell it about 2 actual times you did the task by hand and what was annoying. The rules write themselves.

Open your AI assistant. Paste this exact prompt (replace the four bracketed lines):

```
Read this dossier as a shape reference:
https://github.com/BayramAnnakov/edu-ai-product-engineer-s4/blob/master/cohort-agent/dossier.md

My recurring task: [ONE SENTENCE]
My verifier (what proves the colleague did it right): [ONE SENTENCE]
Last 2 times I did this manually:
  1. [INCIDENT — 1-2 sentences: what happened, what was annoying, what I wish I'd had]
  2. [INCIDENT — 1-2 sentences]

Generate a starter colleague Constitution as a Markdown file. Hard requirement:
EACH rule must trace back to ONE of the incidents above. If a rule doesn't fix
something I described, don't include it. Better 3 grounded rules than 7 generic ones.

Structure:
- Persona settings (honesty %, brevity expectation)
- Voice rules (terse / formal / language-matched / etc.)
- 3-5 incident-grounded rules
- A "what NOT to do" section
- An "Identity" section (only when asked)

Output the file content only. No commentary. I'll save it as ./CLAUDE.md.
```

Save the output to `./CLAUDE.md` in any local directory.

Apply Slide 33's lesson — make it dual-runtime in 5 seconds:

```bash
ln -s CLAUDE.md AGENTS.md
```

Now Codex / Cursor / Gemini / JetBrains read the same Constitution as Claude Code.

### Phase 2 — Tweak (30 sec)

Read what your AI wrote. Change **one** rule (or delete one that's still too generic). Trust your gut. Don't over-think.

### Phase 3 — Run (90 sec)

Pick your runtime. Copy-paste-run.

**Python (recommended):**

```python
# runner.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for msg in query(
        prompt="<ONE EXAMPLE INPUT YOUR COLLEAGUE WOULD HANDLE>",
        options=ClaudeAgentOptions(setting_sources=["project"]),
    ):
        print(msg)

asyncio.run(main())
```

```bash
# In your venv (created in Pre-flight). Validated end-to-end: ~27s clean run.
python runner.py
```

**JS:**

```javascript
// runner.mjs
import { Codex } from "@openai/codex-sdk";

const codex = new Codex();
const result = await codex.startThread().run(
  "<ONE EXAMPLE INPUT YOUR COLLEAGUE WOULD HANDLE>"
);
console.log(result.finalResponse);
```

```bash
node runner.mjs
```

The SDK auto-discovers your `CLAUDE.md` (Python) or `AGENTS.md` (JS) in the current directory. **You did not pass your Constitution. You did not pass an API key.** The runtime found both.

### Phase 4 — Post (30 sec)

Copy the first sentence of your colleague's response. Paste into the cohort group chat. That's your win.

---

## What you should have after 5 min

- `./CLAUDE.md` — your starter Constitution (3-5 incident-grounded rules)
- `./AGENTS.md` — symlink to the same file
- `runner.py` or `runner.mjs` — 4-line SDK invocation
- One real output from your colleague, posted to the cohort chat

Each rule in your CLAUDE.md should trace back to a specific past incident. Open the file and do this audit: read each rule, ask *"which incident does this fix?"* — if you can't answer in one sentence, the rule is too generic and you should rewrite or delete it.

This is the architecture. Everything S2-S5 adds (skills, hooks, MCPs, evals, voice) layers on this same shape. **You shipped the colleague's first version today.**

---

## Fallback tasks (pick one if you don't have a task in mind)

Each comes with 2 example incidents you can paste into Phase 1 verbatim — but your real task and incidents will produce a richer Constitution.

1. **PR review.** *Task:* Read a diff and flag the things you'd flag in a senior code review.
   - Incident 1: Reviewed a 400-line PR at 5pm; missed a SQL injection because I was tired, caught it in production 3 days later.
   - Incident 2: Approved a refactor that quietly changed the public API contract; broke 4 downstream services next morning.

2. **Bug investigation.** *Task:* Read a stack trace + recent commits and propose 3 ranked root causes.
   - Incident 1: Spent 90 min on a NullPointerException that turned out to be one commit ago — would have caught it in 5 min if I'd diffed first.
   - Incident 2: Investigated "intermittent" auth failures for two days; was a clock skew between two servers no one mentioned.

3. **Log triage.** *Task:* Read 200 lines of server log and surface the 3 anomalies that would page on-call.
   - Incident 1: Missed a slow-burn memory leak (20-min increments over 6 hours) because I scrolled to the bottom and only read errors.
   - Incident 2: Paged the team for "auth failures" that turned out to be one specific bot client; should have rate-grouped by IP first.

4. **Customer email triage.** *Task:* Read 10 support emails, classify P0/P1/P2 and route by domain.
   - Incident 1: Marked a "billing question" as P2; turned out to be a payment-processor outage affecting 200 users.
   - Incident 2: Routed a security report to the data team; sat 3 days in someone's inbox before getting to security.

5. **Design QA.** *Task:* Read a design description and flag accessibility + the weakest UX choices.
   - Incident 1: Reviewed a checkout flow; missed that primary CTA had 2.4:1 contrast — failed WCAG AA — until QA caught it.
   - Incident 2: Approved a notification pattern that we'd already deprecated three sprints earlier; team had to re-do the work.

Drop the example task input into Phase 3's `<EXAMPLE INPUT>` slot. You can paste raw text — the colleague is just an LLM with a Constitution.

---

## Troubleshooting (Madina + Sasha pinned in cohort chat during Block 7.5)

- **`error: externally-managed-environment` on `pip install`** → you're on system Python (PEP 668). Run `python3 -m venv venv && source venv/bin/activate` first, then retry.
- **`ModuleNotFoundError: claude_agent_sdk`** → `pip install claude-agent-sdk` (uppercase Python pkg, lowercase import). Make sure you're in the venv (`which python` should show `…/venv/bin/python`).
- **`claude: command not found` or the SDK silently hangs** → the Python SDK needs EITHER Claude Code CLI installed (so it can auto-discover subscription auth) OR `ANTHROPIC_API_KEY` set in env. Pick one. Check with: `claude --version || echo "${ANTHROPIC_API_KEY:0:8}"`.
- **`401 unauthorized` (Python)** → `export ANTHROPIC_API_KEY=sk-ant-...` and re-run.
- **`401 unauthorized` (JS / Codex)** → Codex SDK does NOT accept `OPENAI_API_KEY`. It requires `codex login` (ChatGPT Pro/Plus subscription auth stored in `~/.codex/`). If you don't have a ChatGPT subscription, switch to the Python path.
- **Codex SDK: `not in a git repo`** → `git init && git commit --allow-empty -m init` in the directory.
- **Python <3.10** → `claude-agent-sdk` requires 3.10+. Check `python3 --version`. If stuck on 3.9, install a newer Python or switch to JS path.
- **No output, just hangs** → check `CLAUDE.md` is in the SAME directory you're running from. The SDK reads `./CLAUDE.md` not `~/.claude/CLAUDE.md`.
- **Output is just generic LLM chatter** → your Constitution is too vague. Re-run Phase 1 with a more specific verifier and incidents that aren't sanitized.
- **`warn: CPU lacks AVX support`** → harmless Bun warning, ignore.

If at the 4-min mark you're not running yet: **post your one-sentence task to the cohort chat** instead. TARS captures it; you finish during the break with Madina async. The lesson lands either way — the colleague greeting is just the visible artifact.

Cost note: a single SDK call is ~$0.05-0.10 on Sonnet 4.6 + Haiku 4.5 on the API. Trivial for one-offs; relevant if you leave a loop running.

---

## After class

This is your S2 starting point. By S2 (May 16) you commit:
- A `colleague-target.md` (the dossier — full 5-field shape from `cohort-agent/dossier.md`)
- ≥5 runs of your colleague captured (use the runner; pipe output to a log file)
- One rule you added to `CLAUDE.md` after a real failure (the error-to-rule ratchet you saw in Block 5.5)

The colleague you wrote in 5 minutes today is the seed. You water it for 14 days.
