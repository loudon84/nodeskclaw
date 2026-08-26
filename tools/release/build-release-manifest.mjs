#!/usr/bin/env node
/**
 * Build release-manifest.json + SHA256 checksums for component artifacts (PRD v1.1 §21–§22).
 */
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
  copyFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function readJson(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

function readTomlVersion(rel) {
  const text = readFileSync(join(ROOT, rel), "utf8");
  const m = text.match(/^version\s*=\s*"([^"]+)"/m);
  if (!m) throw new Error(`version not found in ${rel}`);
  return m[1];
}

function sha256File(path) {
  const hash = createHash("sha256");
  hash.update(readFileSync(path));
  return hash.digest("hex");
}

function collectArtifacts(dir, patterns) {
  if (!existsSync(dir)) return [];
  const names = readdirSync(dir);
  return names.filter((n) => patterns.some((re) => re.test(n))).map((n) => join(dir, n));
}

const desktop = readJson("apps/desktop/package.json");
const contracts = readJson("contracts/version.json");
const runtimeVersion = readTomlVersion("services/runtime/pyproject.toml");

const outDir = join(ROOT, "artifacts");
mkdirSync(outDir, { recursive: true });

// Contract bundle
const contractBundleDir = join(outDir, "contracts-bundle");
mkdirSync(contractBundleDir, { recursive: true });
copyFileSync(
  join(ROOT, "contracts/runtime-api/openapi.yaml"),
  join(contractBundleDir, "openapi.yaml"),
);
copyFileSync(join(ROOT, "contracts/version.json"), join(contractBundleDir, "version.json"));
for (const name of ["chat-event.schema.json", "job-event.schema.json", "error.schema.json"]) {
  const src = join(ROOT, "contracts/runtime-events", name);
  if (existsSync(src)) copyFileSync(src, join(contractBundleDir, name));
}
const contractBundleName = `contracts-${contracts.bundleVersion ?? contracts.runtimeApi}.zip`;
// Zip-less portable: write a checksum listing of the bundle directory files
const bundleFiles = readdirSync(contractBundleDir).map((n) => join(contractBundleDir, n));

const desktopCandidates = [
  ...collectArtifacts(join(ROOT, "apps/desktop/dist"), [/\.exe$/i, /\.dmg$/i, /\.AppImage$/i]),
  ...collectArtifacts(join(ROOT, "apps/desktop/release"), [/\.exe$/i]),
];
const runtimeCandidates = [
  ...collectArtifacts(join(ROOT, "services/runtime/dist"), [/\.whl$/i, /\.exe$/i, /\.msi$/i]),
  ...collectArtifacts(join(ROOT, "services/runtime/out"), [/\.exe$/i, /\.msi$/i]),
];

function checksumEntries(paths) {
  return paths.map((p) => ({
    path: p.replace(/\\/g, "/").replace(ROOT.replace(/\\/g, "/") + "/", ""),
    sha256: sha256File(p),
  }));
}

const checksums = [
  ...checksumEntries(desktopCandidates),
  ...checksumEntries(runtimeCandidates),
  ...checksumEntries(bundleFiles),
];
writeFileSync(join(outDir, "SHA256SUMS"), checksums.map((c) => `${c.sha256}  ${c.path}`).join("\n") + (checksums.length ? "\n" : ""));

const manifest = {
  generatedAt: new Date().toISOString(),
  bundleVersion: contracts.bundleVersion ?? null,
  desktop: {
    version: desktop.version,
    artifact: `SMC-Copilot-${desktop.version}-setup.exe`,
    foundArtifacts: desktopCandidates.map((p) => p.replace(/\\/g, "/")),
  },
  runtime: {
    version: runtimeVersion,
    artifact: `SMC-Copilot-Runtime-Setup-${runtimeVersion}.exe`,
    foundArtifacts: runtimeCandidates.map((p) => p.replace(/\\/g, "/")),
  },
  contracts: {
    bundleVersion: contracts.bundleVersion,
    runtimeApi: contracts.runtimeApi,
    runtimeEvents: contracts.runtimeEvents,
    compatibility: contracts.compatibility,
    bundleDir: "artifacts/contracts-bundle",
    bundleLabel: contractBundleName,
  },
  checksums,
};

const out = join(outDir, "release-manifest.json");
writeFileSync(out, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`[build-release-manifest] wrote ${out}`);
console.log(`[build-release-manifest] wrote ${join(outDir, "SHA256SUMS")} (${checksums.length} entries)`);
