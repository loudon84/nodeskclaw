#!/usr/bin/env node
/**
 * Ensure Desktop/Runtime/Contracts versions exist and follow independent tagging policy.
 * Does not auto-bump — fails if contracts/version.json is missing required fields.
 *
 * For tag ↔ SOT equality (desktop-vX.Y.Z == package.json, etc.) see
 * tools/release/verify-release-tags.mjs (wired in .github/workflows/release.yml).
 */
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function readJson(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

function semverOk(v) {
  return typeof v === "string" && /^\d+\.\d+\.\d+/.test(v);
}

const desktop = readJson("apps/desktop/package.json");
const contracts = readJson("contracts/version.json");
const py = readFileSync(join(ROOT, "services/runtime/pyproject.toml"), "utf8");
const runtimeMatch = py.match(/^version\s*=\s*"([^"]+)"/m);

const errors = [];
if (!semverOk(desktop.version)) errors.push(`invalid desktop version: ${desktop.version}`);
if (!runtimeMatch || !semverOk(runtimeMatch[1])) errors.push("invalid runtime version in pyproject.toml");
if (!semverOk(contracts.runtimeApi)) errors.push("invalid contracts.runtimeApi");
if (!semverOk(contracts.runtimeEvents)) errors.push("invalid contracts.runtimeEvents");
if (!semverOk(contracts.bundleVersion ?? "")) {
  errors.push("invalid or missing contracts.bundleVersion");
}
if (!contracts.compatibility?.minimumDesktopVersion) {
  errors.push("missing contracts.compatibility.minimumDesktopVersion");
}
if (!contracts.compatibility?.minimumRuntimeVersion) {
  errors.push("missing contracts.compatibility.minimumRuntimeVersion");
}

if (errors.length) {
  console.error("[verify-version-bumps] failed:");
  for (const e of errors) console.error(`  - ${e}`);
  console.error("Use independent tags: desktop-vX.Y.Z / runtime-vX.Y.Z / contracts-vX.Y.Z");
  process.exit(1);
}

console.log("[verify-version-bumps] ok");
console.log(`  desktop=${desktop.version}`);
console.log(`  runtime=${runtimeMatch[1]}`);
console.log(`  bundleVersion=${contracts.bundleVersion}`);
console.log(`  runtimeApi=${contracts.runtimeApi}`);
console.log(`  runtimeEvents=${contracts.runtimeEvents}`);
