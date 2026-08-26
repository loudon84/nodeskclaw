#!/usr/bin/env node
/**
 * Generate TypeScript types from contracts/runtime-api/openapi.yaml
 * into packages/runtime-client-ts/src/generated/schema.d.ts
 *
 * PRD v1.1 §15.1: openapi-typescript must resolve only from
 * packages/runtime-client-ts/node_modules (not Desktop/root).
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "../..");
const CLIENT_ROOT = join(ROOT, "packages/runtime-client-ts");
const OPENAPI = join(ROOT, "contracts/runtime-api/openapi.yaml");
const OUT_DIR = join(CLIENT_ROOT, "src/generated");
const OUT = join(OUT_DIR, "schema.d.ts");

function resolveOpenapiTypescriptBin() {
  const bin = join(CLIENT_ROOT, "node_modules/openapi-typescript/bin/cli.js");
  if (!existsSync(bin)) {
    throw new Error(
      "openapi-typescript not found under packages/runtime-client-ts/node_modules. " +
        "Run: npx nx run runtime-client-ts:install",
    );
  }
  return bin;
}

function main() {
  if (!existsSync(OPENAPI)) {
    throw new Error(`Missing ${OPENAPI}. Run: npm run contracts:generate`);
  }
  mkdirSync(OUT_DIR, { recursive: true });
  const bin = resolveOpenapiTypescriptBin();
  execFileSync(process.execPath, [bin, OPENAPI, "-o", OUT], {
    cwd: ROOT,
    stdio: "inherit",
  });
  console.log(`[generate_ts_client] wrote packages/runtime-client-ts/src/generated/schema.d.ts`);
}

main();
