#!/usr/bin/env node
/**
 * PRD v1.2 §19 — Runtime Path Ownership Guard
 *
 * Scans apps/desktop/src/** for hardcoded Runtime `/api/v1/` business paths.
 * Formal owner of Runtime HTTP paths: packages/runtime-client-ts (@smc/runtime-client).
 *
 * ## Whitelist (documented)
 *
 * 1. Bootstrap / transport infrastructure:
 *    - src/main/copilot-runtime-client/** (http client, transport, SSE, pairing, connection,
 *      and domain clients still migrating onto @smc/runtime-client)
 *    - files matching runtime-http-client*, *transport*, runtime-sse*, runtime-connection*,
 *      runtime-pairing*
 *    - src/main/copilot-serve/** and src/main/aios/** when the only `/api/v1/` hit on a line
 *      is `/api/v1/health` (process bootstrap probes)
 * 2. Test fixtures: path segments `tests/` or `__tests__/`
 * 3. Generated files: any path segment "generated/", or "*.generated.ts"
 * 4. Comment / doc lines documenting migration (// or * lines matching
 *    migrat|legacy|forbid|禁止|Phase 5|Phase 6|path ownership|@smc/runtime-client)
 * 5. Non-Runtime backends (ignored): /api/v1/{auth,expert,hermes,desktop,genehub,
 *    nodeskclaw,crm,system,mcp}/...
 *
 * ## Temporary debt allowlist
 *
 * TEMP_DEBT_ALLOWLIST lists production files that still hardcode Runtime business paths
 * during Phase 5/6 cutover. Shrink this set — do not grow it.
 *
 * Usage:
 *   node tools/agent-context/check-runtime-path-ownership.mjs
 *   (from apps/desktop) npm run check:runtime-path-ownership
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "../..");
const DESKTOP_ROOT = join(REPO_ROOT, "apps/desktop");
const DESKTOP_SRC = join(DESKTOP_ROOT, "src");

const API_V1 = /\/api\/v1\//;

/** Portal / Expert / GeneHub / MCP-Skill backends — not Runtime path ownership. */
const NON_RUNTIME =
  /\/api\/v1\/(auth|expert|hermes|desktop|genehub|nodeskclaw|crm|system|mcp)\b/;

/**
 * Runtime business prefixes owned by @smc/runtime-client.
 * `/api/v1/health` is excluded (bootstrap-only).
 */
const RUNTIME_BUSINESS =
  /\/api\/v1\/(chat-runs|instances|pairings|runtime\/|diagnostics|secrets|attachments|approvals|artifacts|endpoint|session-catalog|work-tasks|metrics|workers|workspaces|sync\/)/;

/** Relative to apps/desktop — shrink over Phase 5/6; do not grow. */
const TEMP_DEBT_ALLOWLIST = new Set([
  "src/main/workspace-chat/workspace-chat-client.ts",
  "src/renderer/src/lib/copilot-serve/approval-client.ts",
  "src/renderer/src/lib/copilot-serve/task-client.ts",
  "src/renderer/src/lib/copilot-serve/team-task-client.ts",
  "src/renderer/src/lib/copilot-serve/profile-client.ts",
  "src/renderer/src/screens/Workspaces/pages/Chat/hooks/useWorkspaceOptions.ts",
  "src/renderer/src/screens/Workspaces/pages/Chat/hooks/useChatStream.ts",
  "src/renderer/src/screens/TaskWorkbench/TaskWorkbenchScreen.tsx",
]);

/**
 * @param {string} rel
 */
function isWhitelistedFile(rel) {
  if (rel.includes("/tests/") || rel.startsWith("tests/") || rel.includes("/__tests__/")) {
    return true;
  }
  if (rel.includes("/generated/") || /\.generated\.(ts|tsx|js|mjs)$/.test(rel)) return true;
  if (rel.startsWith("src/main/copilot-runtime-client/")) return true;
  if (
    /runtime-http-client/.test(rel) ||
    /transport/.test(rel) ||
    /runtime-sse/.test(rel) ||
    /runtime-connection/.test(rel) ||
    /runtime-pairing/.test(rel)
  ) {
    return true;
  }
  return false;
}

/**
 * @param {string} rel
 */
function isBootstrapProbeFile(rel) {
  return rel.startsWith("src/main/copilot-serve/") || rel.startsWith("src/main/aios/");
}

/**
 * @param {string} line
 */
function isMigrationComment(line) {
  const t = line.trimStart();
  const comment =
    t.startsWith("//") || t.startsWith("*") || t.startsWith("/*") || t.startsWith("{/*");
  if (!comment) return false;
  return /migrat|legacy|forbid|禁止|Phase\s*[56]|path ownership|@smc\/runtime-client|Runtime Path/i.test(
    line,
  );
}

/**
 * Strip known non-Runtime and health probes; return residual /api/v1/ hits that matter.
 * @param {string} line
 * @param {string} rel
 */
function residualRuntimePaths(line, rel) {
  let rest = line;
  rest = rest.replace(NON_RUNTIME, "");
  if (isBootstrapProbeFile(rel)) {
    rest = rest.replace(/\/api\/v1\/health\b/g, "");
  }
  // Standalone health probes outside bootstrap are also allowed (process status).
  if (/\/api\/v1\/health\b/.test(line) && !RUNTIME_BUSINESS.test(line)) {
    rest = rest.replace(/\/api\/v1\/health\b/g, "");
  }
  return rest;
}

/**
 * @param {string} dir
 * @param {string[]} out
 */
function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === "dist" || name === "out") continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx|js|mjs)$/.test(name)) out.push(full);
  }
  return out;
}

const hits = [];
for (const file of walk(DESKTOP_SRC)) {
  const rel = relative(DESKTOP_ROOT, file).replace(/\\/g, "/");
  if (isWhitelistedFile(rel)) continue;
  if (TEMP_DEBT_ALLOWLIST.has(rel)) continue;

  const text = readFileSync(file, "utf8");
  if (!API_V1.test(text)) continue;
  API_V1.lastIndex = 0;

  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!API_V1.test(line)) continue;
    API_V1.lastIndex = 0;
    if (isMigrationComment(line)) continue;

    const rest = residualRuntimePaths(line, rel);
    if (!API_V1.test(rest)) continue;
    API_V1.lastIndex = 0;

    // Flag Runtime business paths, or any remaining unknown /api/v1/
    hits.push(`${rel}:${i + 1}: ${line.trim().slice(0, 140)}`);
  }
}

if (hits.length) {
  console.error("[check-runtime-path-ownership] hardcoded Runtime /api/v1/ paths found:");
  for (const h of hits.slice(0, 80)) console.error("  ", h);
  if (hits.length > 80) console.error(`  ... and ${hits.length - 80} more`);
  console.error(
    "Use @smc/runtime-client. Whitelist: tools/agent-context/check-runtime-path-ownership.mjs",
  );
  process.exit(1);
}

console.log("[check-runtime-path-ownership] ok");
process.exit(0);
