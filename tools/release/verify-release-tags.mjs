#!/usr/bin/env node
/**
 * PRD v1.2 §23 — Release tag ↔ source version gate.
 *
 * Validates that a release tag matches the corresponding version SOT:
 *   desktop-vX.Y.Z   == apps/desktop/package.json version
 *   runtime-vX.Y.Z   == services/runtime/pyproject.toml version
 *   contracts-vX.Y.Z == contracts/version.json bundleVersion
 *
 * Tag source (first match):
 *   1. CLI arg: node tools/release/verify-release-tags.mjs desktop-v0.1.9
 *   2. env RELEASE_TAG
 *   3. env GITHUB_REF_NAME (GitHub Actions tag push)
 *   4. If none: verify all three SOTs exist/semver-ok (no tag compare) — still useful in CI dispatch
 *
 * Wired from .github/workflows/release.yml (manifest job).
 */
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function readJson(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

function semverOk(v) {
  return typeof v === "string" && /^\d+\.\d+\.\d+(?:[-+][\w.]+)?$/.test(v);
}

function runtimeVersion() {
  const py = readFileSync(join(ROOT, "services/runtime/pyproject.toml"), "utf8");
  const m = py.match(/^version\s*=\s*"([^"]+)"/m);
  return m?.[1] ?? null;
}

function parseTag(tag) {
  const m = String(tag).match(/^(desktop|runtime|contracts)-v(\d+\.\d+\.\d+(?:[-+][\w.]+)?)$/);
  if (!m) return null;
  return { component: m[1], version: m[2] };
}

const desktop = readJson("apps/desktop/package.json");
const contracts = readJson("contracts/version.json");
const runtime = runtimeVersion();

const sources = {
  desktop: desktop.version,
  runtime,
  contracts: contracts.bundleVersion,
};

const errors = [];
for (const [k, v] of Object.entries(sources)) {
  if (!semverOk(v)) errors.push(`invalid ${k} version SOT: ${v}`);
}

const tag =
  process.argv[2] ||
  process.env.RELEASE_TAG ||
  (process.env.GITHUB_REF_TYPE === "tag" ? process.env.GITHUB_REF_NAME : "") ||
  process.env.GITHUB_REF_NAME ||
  "";

if (tag && /^(desktop|runtime|contracts)-v/.test(tag)) {
  const parsed = parseTag(tag);
  if (!parsed) {
    errors.push(`unrecognized release tag format: ${tag}`);
  } else {
    const expected = sources[parsed.component];
    if (expected !== parsed.version) {
      errors.push(
        `tag ${tag} does not match ${parsed.component} SOT version ${expected}`,
      );
    } else {
      console.log(`[verify-release-tags] tag ${tag} matches ${parsed.component}=${expected}`);
    }
  }
} else if (tag && process.env.GITHUB_EVENT_NAME === "push") {
  // Tag push that doesn't match component pattern
  if (String(process.env.GITHUB_REF || "").startsWith("refs/tags/")) {
    errors.push(`release tag must be desktop-vX.Y.Z | runtime-vX.Y.Z | contracts-vX.Y.Z (got ${tag})`);
  } else {
    console.log(`[verify-release-tags] no component tag to compare (ref=${tag || "none"})`);
  }
} else {
  console.log("[verify-release-tags] no release tag supplied; validated SOT fields only");
}

if (errors.length) {
  console.error("[verify-release-tags] failed:");
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}

console.log("[verify-release-tags] ok");
console.log(`  desktop=${sources.desktop}`);
console.log(`  runtime=${sources.runtime}`);
console.log(`  contracts.bundleVersion=${sources.contracts}`);
