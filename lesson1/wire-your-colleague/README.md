# Wire your colleague — 5 min exercise

You leave Lesson 1 with a colleague that runs against one input. MVP. Not pretty. Not complete. Running.

The architecture is **Constitution + runtime = colleague**. You'll write the Constitution with help from your existing AI assistant, then point a 4-line SDK runtime at it. That's the whole shape of the S5 capstone.

---

## Pre-flight (do this BEFORE Block 7.5 starts)

Pick one runtime. You only need ONE of these working:

- **Python (Claude Agent SDK)** — `pip install claude-agent-sdk` and `export ANTHROPIC_API_KEY=sk-ant-...`
- **JS (Codex SDK)** — `npm i @openai/codex-sdk` and `codex login` (ChatGPT Pro / Plus subscription)

Have ready:
- Your AI assistant of choice running (Claude Code, Codex CLI, Cursor, JetBrains AI, or anything that reads `CLAUDE.md`/`AGENTS.md`)
- One sentence describing the recurring coding task you want a colleague to take over
- One sentence describing what would prove the colleague did it right (the "verifier")

If you don't have a task in mind, pick one from the [fallback tasks](#fallback-tasks-pick-one) at the bottom.

---

## The exercise

### Phase 1 — Generate your Constitution (90 sec)

Open your AI assistant. Paste this exact prompt (replace the two bracketed lines):

```
Read this dossier as a shape reference:
https://github.com/BayramAnnakov/edu-ai-product-engineer-s4/blob/master/cohort-agent/dossier.md

My recurring task: [ONE SENTENCE]
My verifier (what proves the colleague did it right): [ONE SENTENCE]

Generate a starter colleague Constitution as a Markdown file with:
- Persona settings (honesty %, brevity expectation)
- Voice rules (terse / formal / language-matched / etc.)
- 3-5 rules SPECIFIC to my task (not generic "be helpful")
- A "what NOT to do" section with at least 3 entries
- An "Identity" section (only when asked)

Output the file content only. No commentary. I'll save it as ./CLAUDE.md.
```

Save the output to `./CLAUDE.md` in any local directory.

Apply Slide 33's lesson — make it dual-runtime in 5 seconds:

```bash
ln -s CLAUDE.md AGENTS.md
```

Now Codex / Cursor / Gemini / JetBrains read the same Constitution as Claude Code.

### Phase 2 — Tweak (60 sec)

Read what your AI wrote. Change **one** rule. Add a personal opinion, tighten a hedge, raise the honesty %, whatever. Make it yours. Don't over-think — you have 60 seconds.

### Phase 3 — Run (90 sec)

Pick your runtime. Copy-paste-run.

**Python:**

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

- `./CLAUDE.md` — your starter Constitution (3-5 task-specific rules)
- `./AGENTS.md` — symlink to the same file
- `runner.py` or `runner.mjs` — 4-line SDK invocation
- One real output from your colleague, posted to the cohort chat

This is the architecture. Everything S2-S5 adds (skills, hooks, MCPs, evals, voice) layers on this same shape. **You shipped the colleague's first version today.**

---

## Fallback tasks (pick one if you don't have a task in mind)

These are the universal-domain colleague targets — pick the one closest to your actual day:

1. **PR review.** Read a diff, flag the things you'd flag in a code review (style violations, missing tests, security smells, scope creep).
2. **Bug investigation.** Read a stack trace + recent commits, propose the 3 most likely root causes ranked by evidence.
3. **Log triage.** Read a 200-line server log, surface the 3 anomalies that would page on-call.
4. **Customer email triage.** Read 10 support emails, classify by urgency (P0/P1/P2) and route by domain (billing / auth / data / feature-request).
5. **Design QA.** Read a Figma description (or one paragraph of design intent), flag the accessibility issues and the 3 weakest UX choices.

Drop the example input into Phase 3's `<EXAMPLE INPUT>` slot. You can paste raw text — the colleague is just an LLM with a Constitution.

---

## Troubleshooting (Madina + Sasha pinned in cohort chat during Block 7.5)

- **`ModuleNotFoundError: claude_agent_sdk`** → `pip install claude-agent-sdk` (uppercase Python pkg, lowercase import).
- **`401 unauthorized`** → `export ANTHROPIC_API_KEY=sk-ant-...` for Python. For JS: `codex login` and confirm subscription is active.
- **Codex SDK requires git repo** → `git init && git commit --allow-empty -m init` in the directory.
- **Python <3.10** → `claude-agent-sdk` requires 3.10+. If stuck on 3.9, switch to JS path.
- **No output, just hangs** → check `CLAUDE.md` is in the SAME directory you're running from. The SDK reads `./CLAUDE.md` not `~/.claude/CLAUDE.md`.
- **Output is just generic LLM chatter** → your Constitution is too vague. Re-run Phase 1 with a more specific verifier.

If at the 4-min mark you're not running yet: **post your one-sentence task to the cohort chat** instead. TARS captures it; you finish during the break with Madina async. The lesson lands either way — the colleague greeting is just the visible artifact.

---

## After class

This is your S2 starting point. By S2 (May 16) you commit:
- A `colleague-target.md` (the dossier — full 5-field shape from `cohort-agent/dossier.md`)
- ≥5 runs of your colleague captured (use the runner; pipe output to a log file)
- One rule you added to `CLAUDE.md` after a real failure (the error-to-rule ratchet you saw in Block 5.5)

The colleague you wrote in 5 minutes today is the seed. You water it for 14 days.
