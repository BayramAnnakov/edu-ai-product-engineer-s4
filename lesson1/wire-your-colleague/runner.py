"""Wire-your-colleague runner — Python / Claude Agent SDK.

Pre-reqs:
    pip install claude-agent-sdk
    export ANTHROPIC_API_KEY=sk-ant-...

Run from a directory containing your Constitution at ./CLAUDE.md:
    python runner.py
"""

import asyncio
import sys

from claude_agent_sdk import ClaudeAgentOptions, query


async def main(prompt: str) -> None:
    async for msg in query(
        prompt=prompt,
        options=ClaudeAgentOptions(setting_sources=["project"]),
    ):
        print(msg)


if __name__ == "__main__":
    example_input = sys.argv[1] if len(sys.argv) > 1 else (
        "Run my colleague's task on this input: <PASTE ONE EXAMPLE>"
    )
    asyncio.run(main(example_input))
