#!/usr/bin/env node
/**
 * Codex SDK colleague starter — Workshop 2.
 *
 * A working programmatic example with:
 *   - A local skill at .codex/skills/my-task/SKILL.md
 *     (auto-discovered by Codex CLI when invoked from this directory)
 *   - A PreToolUse hook at .codex/hooks.json that denies `apply_patch`
 *     (Codex's unified write/edit tool — the "read-only colleague" guard)
 *   - A PostToolUse hook that captures failure context to ~/.codex/rules/
 *     (the error-to-rule ratchet)
 *
 * Delivers Bayram's S1 promise (2026-05-02 09:02), in Codex form:
 *   "выполняется скрипт, который чекает, что ассистент пытается делать
 *   write/edit и блокирует операцию. То есть это делается не инструкцией
 *   (промптом), а кодом."
 *
 * The SDK wraps the codex CLI. The CLI reads .codex/hooks.json from cwd,
 * so the deterministic guard works through the SDK too.
 *
 * Usage:
 *   npm install
 *   export OPENAI_API_KEY=sk-...   # OR `codex auth` for ChatGPT login
 *   node colleague.mjs "What is 2+2?"
 *   node colleague.mjs "Create test.txt with hello"   # should be DENIED
 *
 * Verified against @openai/codex-sdk 0.125.x (per
 * https://developers.openai.com/codex/sdk).
 */

import { Codex } from "@openai/codex-sdk";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main() {
  const prompt = process.argv.slice(2).join(" ").trim();
  if (!prompt) {
    console.error("usage: node colleague.mjs '<prompt>'");
    process.exit(1);
  }

  // The Codex CLI auto-discovers .codex/hooks.json and .codex/skills/<name>/
  // from the working directory. Setting workingDirectory keeps that loading
  // tied to THIS starter, not whatever shell the user invoked from.
  const codex = new Codex({
    // Note: Codex requires the cwd to be a git repo by default. Skip for the
    // starter so it works in any directory; in production, keep the check on.
    config: {},
  });

  const thread = codex.startThread({
    workingDirectory: __dirname,
    skipGitRepoCheck: true,
  });

  console.log(`> ${prompt}`);
  console.log();

  const { events } = await thread.runStreamed(prompt);
  let denied = false;

  for await (const event of events) {
    switch (event.type) {
      case "item.completed": {
        const item = event.item;
        switch (item.type) {
          case "agent_message":
            console.log(`Assistant: ${item.text}`);
            break;
          case "reasoning":
            // Skip reasoning chatter; uncomment if you want to see it
            // console.log(`(reasoning: ${item.text.slice(0, 200)}...)`);
            break;
          case "command_execution": {
            const exitTxt = item.exit_code !== undefined ? ` exit=${item.exit_code}` : "";
            console.log(`[bash] ${item.command} → ${item.status}${exitTxt}`);
            break;
          }
          case "file_change":
            for (const c of item.changes) {
              console.log(`[file] ${c.kind} ${c.path}`);
            }
            break;
        }
        break;
      }
      case "item.updated":
      case "item.started":
        // Quietly track in-flight items; the completion event has the final state
        break;
      case "turn.completed":
        console.log();
        console.log(
          `[usage] in=${event.usage.input_tokens} cached=${event.usage.cached_input_tokens} ` +
          `out=${event.usage.output_tokens} reasoning=${event.usage.reasoning_output_tokens}`
        );
        break;
      case "turn.failed":
        console.error(`[FAILED] ${event.error.message}`);
        if (event.error.message.toLowerCase().includes("deny") ||
            event.error.message.toLowerCase().includes("block")) {
          denied = true;
        }
        break;
    }
  }

  if (denied) {
    console.log("\n[result] tool call was blocked by the readonly-guard hook ✓");
  }
}

main().catch((err) => {
  console.error(`Unexpected error: ${err instanceof Error ? err.message : String(err)}`);
  process.exit(1);
});
