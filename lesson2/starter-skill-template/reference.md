# Reference (progressive-disclosure example)

This file demonstrates the **progressive disclosure** pattern. SKILL.md describes the skill in ~50 tokens of frontmatter + a short body. When Claude needs deeper context, it reads this file on demand.

## Why progressive disclosure matters

- Pre-loading every skill's full body at startup = context bloat
- Pre-loading only `name` + `description` = ~30-50 tokens per skill, scales to dozens of skills
- Body loads when Claude routes TO the skill
- Linked files (this one) load when the body explicitly references them or Claude judges them necessary

## Customize this file for your skill

Replace this content with whatever your skill needs to reference often but doesn't need in every invocation:
- Catalog of patterns / anti-patterns
- API contract details
- Domain glossary
- Examples library

Keep it focused — under 500 lines is the practical ceiling. If you need more, split into multiple reference files (each linked from SKILL.md or from another reference file).

## Example: anti-pattern catalog (delete + replace)

### AP-001: Catching and swallowing exceptions
**Surface:** `try: ... except: pass`
**Why bad:** Hides bugs; surfaces only when unrelated code fails.
**Fix:** Catch specifically; log the exception; re-raise or handle deliberately.

### AP-002: Synchronous I/O in async code
**Surface:** `await some_func()` followed by `time.sleep(...)` or `requests.get(...)`
**Why bad:** Blocks the event loop; latency spikes; concurrency stalls.
**Fix:** Use `await asyncio.sleep(...)` and `aiohttp` (or equivalent async client).

(...etc.)
