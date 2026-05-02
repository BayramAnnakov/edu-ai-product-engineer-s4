// Wire-your-colleague runner — JS / Codex SDK.
//
// Pre-reqs:
//   npm i @openai/codex-sdk
//   codex login  (ChatGPT Pro / Plus subscription)
//   git init && git commit --allow-empty -m init  (Codex requires a git repo)
//
// Run from a directory containing your Constitution at ./AGENTS.md:
//   node runner.mjs "your example input"

import { Codex } from "@openai/codex-sdk";

const exampleInput = process.argv[2] ?? "Run my colleague's task on this input: <PASTE ONE EXAMPLE>";

const codex = new Codex();
const result = await codex.startThread().run(exampleInput);
console.log(result.finalResponse);
