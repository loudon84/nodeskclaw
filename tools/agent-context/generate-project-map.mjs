#!/usr/bin/env node
/** Generate a compact project map for agent orientation. */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const map = {
  generatedAt: new Date().toISOString(),
  projects: [
    { name: "desktop", path: "apps/desktop", stack: "electron-npm" },
    { name: "runtime", path: "services/runtime", stack: "fastapi-uv" },
    { name: "contracts", path: "contracts", stack: "generated" },
    { name: "runtime-client-ts", path: "packages/runtime-client-ts", stack: "typescript" },
    { name: "integration-e2e", path: "tools/integration", stack: "smoke" },
  ],
  dependencyDirection: ["runtime", "contracts", "runtime-client-ts", "desktop"],
};

const outDir = join(ROOT, ".agent-context");
mkdirSync(outDir, { recursive: true });
const out = join(outDir, "project-map.json");
writeFileSync(out, `${JSON.stringify(map, null, 2)}\n`);
console.log(`[generate-project-map] wrote ${out}`);
