"""Claude Agent SDK colleague starter — Workshop 2.

A working programmatic example with:
  - A local skill (auto-discovered from .claude/skills/)
  - A PreToolUse hook that denies Edit/Write/NotebookEdit
    (the "read-only colleague" / deterministic guard)
  - A PostToolUse hook that captures failure context to disk
    (the error-to-rule ratchet)

Delivers Bayram's S1 promise (2026-05-02 09:02):
  "выполняется скрипт, который чекает, что ассистент пытается делать
  write/edit и блокирует операцию. То есть это делается не инструкцией
  (промптом), а кодом."

Usage:
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  export ANTHROPIC_API_KEY=sk-ant-...
  python colleague.py                          # interactive: try asking it to read code
  python colleague.py --prompt "What is 2+2?"  # one-shot
  python colleague.py --prompt "Create test.txt with 'hello'"  # should be DENIED

Verified against claude-agent-sdk == 0.1.x (the canonical pattern from
https://github.com/anthropics/claude-agent-sdk-python).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

# ---------------------------------------------------------------- hooks

# Claude Code's write-class tools — block ALL of them to make the colleague
# truly read-only. Codex's equivalent (apply_patch) is a different runtime.
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")

# Where the error-to-rule ratchet stages captured failures. Override via env.
RULES_DIR = Path(os.environ.get("CLAUDE_RULES_DIR") or
                 Path.home() / ".claude" / "rules")


async def readonly_guard(
    input_data: HookInput, tool_use_id: str | None, context: HookContext,
) -> HookJSONOutput:
    """PreToolUse hook — deterministic deny on write-class tools.

    Returns a deny decision per the Claude Code hooks spec:
    https://code.claude.com/docs/en/hooks#decision-control
    """
    _ = (tool_use_id, context)  # unused, satisfy linters
    # HookInput is a Union over all event types; PreToolUse always has tool_name.
    tool_name = input_data.get("tool_name", "")  # type: ignore[union-attr]
    if tool_name in WRITE_TOOLS:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Read-only colleague — {tool_name} blocked by readonly_guard. "
                    f"Remove the hook from ClaudeAgentOptions to re-enable writes."
                ),
            }
        }
    # Default: don't override — return empty dict and let other rules decide.
    return {}


async def capture_failure(
    input_data: HookInput, tool_use_id: str | None, context: HookContext,
) -> HookJSONOutput:
    """PostToolUse hook — write failure context to ~/.claude/rules/.

    The error-to-rule ratchet (Mitchell Hashimoto, Feb 2026 (mitchellh.com)): every failure
    should produce a harness improvement, not just a fix.

    NOTE: PostToolUse fires after ANY tool call, success or failure. Inspect
    tool_result for an error signal. Claude Agent SDK doesn't separate
    PostToolUseFailure as Claude Code CLI does.
    """
    _ = (tool_use_id, context)
    tool_result = input_data.get("tool_result", {}) or {}  # type: ignore[union-attr]
    # Heuristic: result text contains "error" or is_error flag set
    text = ""
    if isinstance(tool_result, dict):
        text = (str(tool_result.get("text") or "") + " "
                + str(tool_result.get("error") or ""))
    elif isinstance(tool_result, str):
        text = tool_result

    if "error" not in text.lower() and not (
        isinstance(tool_result, dict) and tool_result.get("is_error")
    ):
        return {}  # not a failure, ignore

    RULES_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    tool_name = input_data.get("tool_name", "unknown")
    slug = tool_name.lower().replace("_", "-")[:32]
    out_path = RULES_DIR / f"{ts[:10]}-{ts[11:]}-{slug}.md"
    out_path.write_text(
        f"---\ncaptured_at: {ts}\ntool: {tool_name}\nsession: {tool_use_id}\n---\n\n"
        f"# Failure capture: {tool_name}\n\n"
        f"## Tool input\n```json\n{json.dumps(input_data.get('tool_input', {}), indent=2)}\n```\n\n"
        f"## Tool result\n```json\n{json.dumps(tool_result, indent=2, default=str)}\n```\n\n"
        f"## Proposed rule (TODO)\nAdd a rule to your CLAUDE.md so this doesn't happen again.\n"
    )
    # PostToolUse doesn't accept permissionDecision. Just return empty.
    return {}


# ---------------------------------------------------------------- agent

async def run(prompt: str | None) -> int:
    """Run one query (or interactive REPL if prompt is None).

    Skills are auto-discovered from .claude/skills/ in the current working
    directory thanks to setting_sources=["project"]. The starter skill at
    .claude/skills/my-task/SKILL.md will load when its description matches
    the user's question.
    """
    options = ClaudeAgentOptions(
        # Read-only colleague: only allow read-class tools + Bash for grep/find.
        # The PreToolUse hook is the deterministic guard; allowed_tools is the
        # advisory layer (the sandwich's other slice — defense in depth).
        allowed_tools=["Read", "Glob", "Grep", "Bash"],
        # Plus the system prompt anchors the read-only contract in voice too.
        system_prompt=(
            "You are a read-only code review colleague. You can read files, "
            "search across the codebase, and analyze patterns. You CANNOT "
            "create, edit, or delete files — a hook will block any attempt. "
            "When asked to change code, propose the change as a diff in your "
            "reply; do not call Edit/Write tools."
        ),
        # Hooks: the deterministic guard + the error-to-rule capture.
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="|".join(WRITE_TOOLS),
                    hooks=[readonly_guard],
                ),
            ],
            "PostToolUse": [
                HookMatcher(matcher=None, hooks=[capture_failure]),
            ],
        },
        # Auto-discover skills from .claude/skills/ in cwd + parent dirs.
        setting_sources=["project"],
        max_turns=5,
        cwd=str(Path.cwd()),
    )

    async with ClaudeSDKClient(options=options) as client:
        if prompt:
            await client.query(prompt)
            await _print_stream(client)
        else:
            # Interactive REPL
            print("Read-only colleague ready. Ctrl-D to exit.")
            while True:
                try:
                    p = input("> ").strip()
                except EOFError:
                    print()
                    break
                if not p:
                    continue
                await client.query(p)
                await _print_stream(client)
    return 0


async def _print_stream(client) -> None:
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}({json.dumps(block.input)})")
        elif isinstance(msg, ResultMessage):
            cost = getattr(msg, "total_cost_usd", None)
            if cost is not None:
                print(f"[cost ${cost:.4f}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prompt", default=None, help="One-shot prompt (otherwise REPL)")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: set ANTHROPIC_API_KEY", file=sys.stderr)
        return 1

    return asyncio.run(run(args.prompt))


if __name__ == "__main__":
    sys.exit(main())
