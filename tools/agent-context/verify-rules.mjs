#!/usr/bin/env node
/** Verify required Cursor rules / ignore files exist. */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const required = [
  "AGENTS.md",
  ".cursorignore",
  ".cursorindexingignore",
  ".cursor/rules/repository-routing.mdc",
  ".cursor/rules/desktop-boundary.mdc",
  ".cursor/rules/runtime-boundary.mdc",
  ".cursor/rules/contract-boundary.mdc",
  "apps/desktop/AGENTS.md",
  "services/runtime/AGENTS.md",
];

const missing = required.filter((rel) => !existsSync(join(ROOT, rel)));
if (missing.length) {
  console.error("[verify-rules] missing:");
  for (const m of missing) console.error(`  - ${m}`);
  process.exit(1);
}
console.log("[verify-rules] ok");

// Also run Runtime path ownership guard when present (PRD v1.2 §19).
const ownership = join(ROOT, "tools/agent-context/check-runtime-path-ownership.mjs");
if (existsSync(ownership)) {
  const r = spawnSync(process.execPath, [ownership], { stdio: "inherit", cwd: ROOT });
  if (r.status !== 0) process.exit(r.status ?? 1);
}
