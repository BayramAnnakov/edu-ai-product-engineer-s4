# Workshop 2 — Harness Engineering Source Canon

Curated research dump for Lesson 2 (Skill + Harness Engineering). Sources verified 2026-05-15.
Use this file as: (a) the citation pool for slides, (b) the homework reading list for students, (c) the fact base for the design doc + dossiers.

---

## 1. The terms — who coined what

| Term | Author | Year | Anchor source |
|---|---|---|---|
| **"Harness engineering"** | **Anthropic engineering** (productized) + **OpenAI Codex team** (Feb 2026 article) | 2026 | Both vendors publish under this exact phrase |
| **"Agent = Model + Harness"** | **Mitchell Hashimoto** (HashiCorp / Ghostty), reused by Anthropic | 2025 | Anthropic blog repeatedly returns to it |
| **"Context engineering"** | **Andrej Karpathy** | 2025 | Distinct from harness engineering; subset/adjacent |
| **"Error-to-rule ratchet" / "harness engineering"** | **Mitchell Hashimoto** (mitchellh.com, Feb 2026; reinforced via Pragmatic Engineer YouTube Feb 25 2026) | 2026 | NOT Yoshua — common misattribution. Mitchell's actual phrasing: *"build a test harness, validation script, or linting rule that the agent can invoke to self-check"* — the harness improvement can be a hook, a test, a validator, a skill, OR a CLAUDE.md rule. |
| **"Sandwich / swiss-cheese model"** for permissions | Anthropic (engineering blog) | 2025-2026 | Bayram cites this directly in webinar3 |
| **Agent Skills standard** (`agentskills.io`, SKILL.md) | Anthropic (open standard, Dec 18 2025) | 2025-12-18 | https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills |
| **"Stanford meta-harness"** (model+harness beats model) | Stanford research group (paper March 30) | 2026-03 | Cited in Bayram's webinar3 line 203-206 |

Two CORRECTIONS to early Workshop 2 drafts:
- Hashimoto is **Mitchell**, not Yoshua
- Mitchell's blog post is **Feb 2026** (mitchellh.com), not Feb 5 2025 (earlier draft error throughout this canon)
- Mitchell's pattern is **broader** than "write the failure to ~/.claude/rules/<date>.md and review weekly" — that's a specific implementation choice, not what Mitchell wrote. His actual recommendation is to build agent-invokable tooling (test/validator/lint/hook/skill) and update CLAUDE.md or agents.md. A hook itself IS a valid ratchet outcome.
- "Harness engineering" is **Anthropic + OpenAI**, not Karpathy (Karpathy = context engineering)

---

## 2. Canonical URLs (priority order — fetch these first if doing further work)

### Anthropic — primary canon
1. **https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents** — load-bearing components: initializer agent, feature list file, progress tracking, testing infrastructure. Production example: claude.ai clone built across sessions.
2. **https://www.anthropic.com/engineering/harness-design-long-running-apps** — Planner / Generator / Evaluator agent decomposition. Sprint contracts. Structured artifacts as handoff state.
3. **https://www.anthropic.com/engineering/managed-agents** — Managed Agents launch (Apr 8 2026). "Decouple brain from hands." Session event log as interrogatable state. **NO hooks**; closest analog = session event log.
4. **https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills** — Skills launch (Dec 18 2025). SKILL.md format. Cross-tool standard.
5. **https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents** — Sept 29 2025. Karpathy-adjacent.
6. **https://www.anthropic.com/engineering/building-effective-agents** — Dec 2024 reference architecture piece.

### OpenAI — Codex / harness counterpart
7. **https://openai.com/index/harness-engineering/** — "Harness engineering: leveraging Codex in an agent-first world" (Feb 13 2026). "Every line of code written by Codex." "1/10th the time." "Designing environments, specifying intent, building feedback loops."
8. **https://openai.com/index/unrolling-the-codex-agent-loop/** — Codex harness internals.
9. **https://openai.com/index/open-source-codex-orchestration-symphony/** — Symphony orchestration spec.

### Tool docs — what students will install
10. **https://code.claude.com/docs/en/hooks** — Claude Code hooks reference. 29 event names. Five handler types: command/http/mcp_tool/prompt/agent.
11. **https://developers.openai.com/codex/hooks** — Codex CLI hooks. Same 5 core events (PreToolUse, PostToolUse, PermissionRequest, UserPromptSubmit, Stop). Config in `hooks.json` or `config.toml`.
12. **https://code.claude.com/docs/en/skills** — Claude Code Skills reference.
13. **https://developers.openai.com/codex/skills** — Codex Skills support (SKILL.md works unchanged from Claude Code).
14. **https://developers.openai.com/codex/guides/agents-md** — AGENTS.md spec (Codex equivalent of CLAUDE.md).

### Local authoritative source
15. **`/Users/bayramannakov/GH/claude-code-webinar-2026/webinar3-transcript.txt`** — Bayram's 3.5h Russian walkthrough of leaked Claude Code source. 720 lines. **The most TARS-aligned reference we have.** Quotes extracted below.

---

## 3. Verified facts — hooks

### Claude Code hooks (29 event names — selected list for S2)

| Event | What it fires on | S2 demo value |
|---|---|---|
| `PreToolUse` | Before any tool call | **PRIMARY** — block Edit/Write for read-only colleague; deterministic guard |
| `PostToolUse` | After a tool call succeeds | **PRIMARY** — error-to-rule capture, lint check, test run |
| `PostToolUseFailure` | After a tool call fails | **S2 fit** — auto-write failure to `~/.claude/rules/` |
| `UserPromptSubmit` | Before Claude processes a prompt | Optional — preflight checks |
| `Stop` | When Claude finishes responding | Optional — session-end metrics |
| `SessionStart` | Session begin/resume | Out of S2 scope |
| `InstructionsLoaded` | When CLAUDE.md / rules load | Interesting but tangential |
| `PreCompact` / `PostCompact` | Context compaction | S3-S4 territory |
| `SubagentStart` / `SubagentStop` | Subagent lifecycle | S3-S4 territory |

**Five handler types** (Claude Code):
- `command` — shell script, the canonical type
- `http` — POST to a URL (perfect for cohort-4-rules ingestion endpoint!)
- `mcp_tool` — call an MCP server
- `prompt` — invoke a fast model to decide
- `agent` — invoke a subagent

**PreToolUse decision API:**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny|allow|ask|defer",
    "permissionDecisionReason": "..."
  }
}
```
Exit code 2 also blocks; exit 0 allows. Can also `updatedInput` to modify the tool call.

**Config locations:**
- `~/.claude/settings.json` (user-wide)
- `.claude/settings.json` (project, shared)
- `.claude/settings.local.json` (project, gitignored)
- Plugin `hooks/hooks.json`

**What hooks CANNOT do:**
- Modify tool input on most events (only PreToolUse + PermissionRequest)
- Access the model directly / make Claude API calls
- Guarantee ordering (parallel execution)
- Block on `SessionEnd`, `FileChanged`, `Notification`, etc.

### Codex CLI hooks — confirmed parity

Same five core events: `PreToolUse`, `PostToolUse`, `PermissionRequest`, `UserPromptSubmit`, `Stop`.
Config: `hooks.json` or `config.toml` inline `[hooks]` table.
Locations: `~/.codex/hooks.json` or `.codex/hooks.json` at repo level.
Limitations: `agent` and `prompt` handler types parsed but **skipped** (only command/http/mcp_tool work).
PreToolUse is **defensive, not enforcement** — doesn't intercept all shell calls yet.

### Anthropic Managed Agents — NO hooks

Confirmed via Apr 8 2026 launch article and memory store docs. Extension points are:
- Skills (via `skills` field on `POST /v1/agents`, beta `skills-2025-10-02`). Uploaded via `client.beta.skills.create(display_title=..., files=[(path, bytes, mime), ...])` — verified pattern from `~/GH/onsa-robin/scripts/upload_skill.py` and now mirrored in `cohort-agent/scripts/upload_skill.py`.
- Memory stores (`/mnt/memory/<store>/`) — **mounted as filesystems inside the agent's bash tool**. The agent uses `grep`, `cat`, `ls` to interact with them. This is the canonical pattern, verified in `anthropic/types/beta/sessions/beta_managed_agents_memory_store_resource.py:41`.
- MCP servers (OAuth + custom tools)
- Sandboxes / execution environments
- **Session event log** (`emitEvent()` / `getEvents()` / `getSession()`) — **closest hook analog but for STATE, not callbacks**

**For Workshop 2:** TARS gets skills, not hooks. Students get both because their colleagues run on local Claude Code / Codex CLI.

**Common misunderstanding to avoid:** *"Skill files should be uploaded to a memory store under `/skills/` prefix."* — NO. Skills are first-class resources via the dedicated Skills API; memory stores are for STATE (transcripts, roster, dossiers). They're separate concepts. The TARS `cohort-search` skill USES bash to grep `/mnt/memory/cohort-knowledge/` because that's where the agent's reading material is mounted — but the skill itself is uploaded via the Skills API and referenced by ID from `agents[].skills[]`.

---

## 4. Verified facts — skills

### Cross-runtime standard (agentskills.io, Dec 18 2025)

A Skill is "a directory containing a SKILL.md file that contains organized folders of instructions, scripts, and resources that give agents additional capabilities."

**Frontmatter (mandatory):**
```yaml
---
name: skill-name-here
description: One-line summary — used for routing
---
```

**Body:** Detailed instructions. Can reference bundled files (`reference.md`, `forms.md`, `scripts/foo.py`, etc.) that Claude loads on-demand (progressive disclosure).

**Discovery:** At startup, Claude pre-loads only `name` + `description` (~30-50 tokens each). When relevant, reads full SKILL.md. When deeper detail needed, reads referenced files.

**Cross-tool support:** Claude.ai, Claude Code, Claude Agent SDK, Claude Developer Platform, **Codex CLI (within 48h of launch)**, ChatGPT, Cursor (varying).

### Locations
- Claude Code project: `.claude/skills/<name>/SKILL.md`
- Claude Code user: `~/.claude/skills/<name>/SKILL.md`
- Codex CLI: similar `.codex/skills/<name>/SKILL.md` (verify in docs)
- Managed Agents: uploaded via `POST /v1/skills` and referenced in `agents[].skills[]`

---

## 5. Bayram's own framing (webinar3 transcript) — load-bearing quotes

These are the verbatim Russian quotes Bayram has already used in front of his own audience. Workshop 2 should echo them so cohort 4 students recognize the through-line.

### The chair metaphor (Lines 116-128) — central image of the whole webinar
> *"если бы я сидел на скамейки, то если я слишком много выпью, я могу легко с нее упасть. Если же я сижу на стуле с спинкой, мне очень тяжело, потому что есть подпорки, есть вот эти связки, да, которые меня удержат от падения назад… вот это мое понимание Harness."*

> *"если есть система, которая не позволяет мне упасть в кавычках, то я не упаду… вот для меня Harness, вот все эти обвязки, которые мы будем сегодня обсуждать вокруг модели, это как раз вот этот стул."*

### Three failure modes a harness must prevent (Lines 131-149)
1. *"Они отвлекаются от цели"* — distraction as context fills
2. *"Чтобы он не сделал то, что ему или не положено"* — destructive / out-of-scope
3. *"Мы обеспечиваем механизмы обратной связи… которые позволяют агенту учиться на… своих ошибках"* — feedback loops for self-correction

**Workshop 2 frame:** Skills + hooks = "tools to fix failure mode #2 and #3." Map each starter template to a failure mode.

### Sandwich/swiss-cheese permissions (Lines 176-182)
> *"если я реализую несколько систем защиты, то я повышаю вот эту устойчивость. И мы увидим сегодня, что в кладкоде именно такая многоступенчатая система проверок."*

Citing Anthropic. This is the lens for explaining the F1 audience-boundary fix (two-layer defense: upload filter + Constitution).

### Agent loop one-liner (Lines 321-323)
> *"Описывать state и как можно быстрее обрабатывать результат"*

Best one-liner definition of agent engineering in the transcript.

### Skills as crystallized repetition (Lines 513-527)
> *"Если он хорошо предсказывает наш следующий шаг, это, возможно, повторяющийся… А если это повторяющийся, то это претендент на skill."*

> *"скиллы будут динамически создаваться, автодримом в плюс, подтверждением, что какой-то speculation… угадал."*

**Workshop 2 framing for students:** "What in your colleague's last 2 weeks did you copy-paste from one session to the next? That's the skill candidate."

### Don't over-engineer (Lines 455-463)
> *"если у вас… не так много контекста собирается в агенте, может быть вам и не нужно. Вообще тут очень важно не переинженировать… Premature Optimization is the root of all evil."*

**Workshop 2 frame:** name this as a rule. Students will instinct toward "add a hook for everything." Cap them at one hook + one skill in S2.

### Harness has a shelf life (Lines 416-424)
> *"каждая новая версия модели инвалидирует кучу Harness'а… просто эти логи попадают обратно. И мы уже знаем, что, конечно же, Harness, на Harness'е тоже учатся."*

**Workshop 2 frame:** "the rules you write today might be unnecessary in 6 months when the next model lands. Write them with future-pruning in mind."

### Hooks canonical use case (Lines 244-248)
> *"распространенный hook, который разработчики добавляют. Это если вдруг отредактировался, в рамках tool calls редактировался какой-то файл, то проверить, компилируется ли этот файл перед тем, как заканчивать работу."*

This is exactly the PostToolUse-on-Edit pattern. Workshop 2 starter-hook-template should ship this as the demo case.

---

## 6. The S1 promise — what S2 must deliver

These are messages from the cohort group on 2026-05-02 (during Workshop 1). Bayram **explicitly promised** harness mechanisms for S2-S4. **S2 must fulfill at least the first promise.**

### A cohort 4 student → Bayram (2026-05-02 morning):
> Student: *"есть ли еще возможность дать на read доступ для агента, чтобы он мог читать материалы пространства?"*
>
> Bayram: *"да, можно — сходу 3 способа:
> 1) запуск основного агента только с read или субагента с read пермиссиями…
> 2) **сделать tool — мы поговорим про это на 2й встрече — в котором вы программно контролируете что read-only**
> 3) сделать harness — чтобы когда он пытался редактировать, его били по рукам — 3-4 встреча"*

### Another cohort 4 student → Bayram (2026-05-02 morning):
> Student: *"если harness у нас это те же инструкции не делать что-то или делать что-то, но он их так же может проигнорировать, то никакой детерминированности не достичь или тут в игру вступают слайсы сыра?"*
>
> Bayram: *"не совсем — **я покажу как harness делать детерминированный (условно, выполняется скрипт, который чекает, что ассистент пытается делать write/edit и блокирует операцию)**"*
>
> *"то есть это делается не инструкцией (промптом), а кодом. он может даже ходить во внешние системы и что-то проверять, e.g. что у юзера есть такой доступ или нет"*

### What this commits S2 to demonstrate

1. **PreToolUse hook on Edit|Write that blocks via `permissionDecision: "deny"`** — the "битьем по рукам" deterministic guard. Direct fulfillment of Bayram's S1 promise.
2. **Code-not-prompt enforcement** — the demo must show the SAME prompt producing different behavior with/without the hook installed. Reuses the S1 stochasticity demo's reveal pattern.
3. **External system check (HTTP hook type)** — "ходить во внешние системы и проверять, e.g. что у юзера есть такой доступ или нет." Workshop 2 starter-hook-template should ship a stub for this (HTTP POST → check ACL → allow/deny). The cohort-4-rules ingestion endpoint can BE this example.
4. **Read-only sub-agent / tool with programmatic control** — promised for S2 ("сделать tool — мы поговорим про это на 2й встрече"). This is the **skill** side of the demo: a SKILL.md that wraps read access. Pair with the hook on the write side.

**Implication for Workshop 2 design:** the "skill + hook" pairing isn't arbitrary — it's the **specific shape Bayram already promised the cohort**. Skill = read-side. Hook = write-side. Together = deterministic read-only colleague. This is a STRONGER pedagogical spine than "install one skill + one hook because they're S2 topics."

---

## 7. OpenAI's Codex harness story (Feb 13 2026 article — paraphrased; URL 403s on fetch)

Key claims from the article that should land in Workshop 2:

- *"Every line of code—application logic, tests, CI configuration, documentation, observability, and internal tooling—has been written by Codex"*
- *"1/10th the time it would have taken to write by hand"*
- *"The engineering team's primary job became designing environments, specifying intent, and building feedback loops that allow Codex agents to do reliable work"*
- Codex has a "core agent loop and execution logic underlying all Codex experiences"
- Symphony: open-source spec for Codex orchestration (paired with Linear etc.)

**Workshop 2 use:** quote the third bullet at the Concept block (Block 5) as the cross-vendor convergence point. Both Anthropic and OpenAI now name the same job as the engineering work. Use it to frame "harness engineering = the job, regardless of which model you ship on."

---

## 8. Architectural-asymmetry table (REVISED — all earlier drafts are wrong)

The original draft claimed Codex has no hooks. **That is wrong as of Feb 2026.** Updated table for handout + slides:

| | TARS (Managed Agents) | Claude Code | Codex CLI | Cursor |
|---|---|---|---|---|
| Runtime | Anthropic hosted | Local | Local | Local |
| System prompt | Constitution → `instructions` field | `CLAUDE.md` | `AGENTS.md` | `.cursorrules` |
| Skills (cross-runtime SKILL.md) | YES — via Skills API | YES — `.claude/skills/` | YES — `.codex/skills/` | Partial |
| Hooks | **NO** | YES — 29 events | YES — 5 core events | No |
| State / memory | Memory stores (`/mnt/memory/<name>/`) | Files + sliding window | Files + sliding window | Files |
| Closest hook analog | Session event log (read-only) | n/a (native) | n/a (native) | n/a |
| Error-to-rule pattern | Constitution edit + seed file + re-provision | PostToolUse hook + CLAUDE.md edit | PostToolUse hook + AGENTS.md edit | Manual `.cursorrules` edit |
| Audit trail | Memory store version history (30d) | Local git + transcript JSONL | Local git + transcript | None |

**Key teaching beat:** Skills are **portable**. Hooks are **harness-specific**. Same SKILL.md works in Claude Code, Codex, ChatGPT, Cursor. Hook JSON is mostly portable between Claude Code and Codex but breaks for Cursor and breaks entirely for Managed Agents.

---

## 9. Slide quotes (verified, ≤140 chars each)

For the deck — use as title cards / pull-quotes:

1. *"Model + Harness beats Model."* — Stanford meta-harness paper, March 2026 (cited in Bayram webinar3)
2. *"Every component in a harness encodes an assumption about what the model can't do."* — Anthropic, harness-design-long-running-apps
3. *"The space of interesting harness combinations doesn't shrink as models improve."* — Anthropic, ibid.
4. *"Harnesses encode assumptions that go stale as models improve."* — Anthropic, Managed Agents launch
5. *"Designing environments, specifying intent, building feedback loops."* — OpenAI, harness-engineering (the new engineering job)
6. *"Separating the agent doing the work from the agent judging it proves to be a strong lever."* — Anthropic, harness-design-long-running-apps
7. *"Make each component cattle, not pets."* — Anthropic, Managed Agents launch
8. *"Описывать state и как можно быстрее обрабатывать результат."* — Bayram, webinar3 (one-line agent engineering)
9. *"Скиллы — претендент на повторяющийся путь экономии энергии."* — Bayram, webinar3 (skill candidate test)
10. *"Premature Optimization is the root of all evil."* — Knuth, via Bayram webinar3 (don't over-engineer the harness)

---

## 10. Homework reading for students (3-source minimum)

Pick three for the post-S2 Telegram drop:

1. **Anthropic — Effective harnesses for long-running agents** (canonical framing): https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
2. **Anthropic — Agent Skills launch** (the standard students just built on): https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
3. **One of:** Claude Code hooks reference https://code.claude.com/docs/en/hooks **OR** Codex hooks reference https://developers.openai.com/codex/hooks (point at the one matching their tool)
4. **Bonus:** OpenAI — Harness engineering (cross-vendor confirmation that this IS the job now): https://openai.com/index/harness-engineering/

---

## 11. Harness optimizations beyond skills + hooks

These are *adjacent* harness moves — not the main S2 teaching beats, but worth surfacing as "here's where harness engineering goes next" plants for S3+.

### Cache pre-warming

**Pattern:** send the system prompt to the model *before* the user types their message. Prompt cache pre-populates; when the user message arrives, time-to-first-token drops dramatically (cache hit on the prefix).

**Source:** [@claudedevs on X](https://x.com/claudedevs/status/2055069548672631218?s=46) (direct fetch returned 402 — see Bayram for verbatim).

**Why it matters for Workshop 2:**
- Demonstrates that **harness engineering is also about latency**, not just safety/correctness. The chair metaphor extends: a good harness keeps you from falling AND lets you stand up faster.
- Concrete production analog for TARS: the Telegram bot could pre-warm Claude's cache by sending the Constitution as a heartbeat ping before any user message arrives. Sub-200ms first-token would feel instantaneous in the group.
- Maps cleanly to Bayram's webinar3 line about cache-safe-params (Lines 262-268) — variable params in the cached prefix silently break the cache. Pre-warm assumes a clean cache prefix.

**Workshop 2 surfacing:** mention briefly in Block 5 (Concept) as a Plant for S3. Don't deep-dive — S3 is "Tools / MCP" and latency is part of that story.

### Speculation / pre-compute (per webinar3)

**Pattern:** while the model is responding, predict the most likely next tool call and start executing it in parallel. If the prediction was right, the result is already ready when the next turn starts.

**Source:** webinar3 Lines 484-527 — "Kairos" — speculation engine + proactive heartbeat agent.

**Why it matters:** another latency move; also a teaching beat about "the harness anticipates, not just reacts."

### Autodream (background memory consolidation)

**Pattern:** background process reads recent conversations, identifies patterns worth remembering, and updates memory durably — *while the user is asleep*.

**Source:** webinar3 Lines 470-482.

**Why it matters:** this is the *automated* form of the error-to-rule ratchet. Students manually ratchet rules in S2; by S5 they could have an Autodream-style daemon doing it for them.

---

## 12. Open items / what's still unverified

- **Mitchell Hashimoto's original error-to-rule blog post URL.** Research agent found Feb 2026 (mitchellh.com) references but not the canonical URL. Likely on his personal blog (mitchellh.com or similar).
- **Managed Agents `outcomes` API.** Research agent mentioned this as a self-grading loop, but the official Managed Agents article doesn't surface it. Verify against latest Anthropic docs before claiming it in the lesson.
- **Codex CLI native-Windows hook support.** Codex docs don't mention OS variants; verify before workshop or note as "WSL only" in handout.
- **Cursor skills support.** Stated as "partial" — verify what subset works.
- **Twitter/X @claudedevs cache pre-warm tweet content.** Fetch failed (auth required). Get verbatim from Bayram or paste from a logged-in browser session.
