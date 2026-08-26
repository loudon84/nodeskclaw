#!/usr/bin/env node
/**
 * Integration E2E levels (PRD v1.1 §20):
 *   L1 — contract client: status / capabilities / job / error envelope / chat.runtime.v2
 *   L2 — durable chat-runs against Runtime (stub turn worker; Fake Hermes optional)
 *   L3 — Windows real runtime (CI on windows-latest when INTEGRATION_L3=1)
 *
 * Env:
 *   INTEGRATION_LEVEL=l1|l2|all (default all / l1+l2)
 *   INTEGRATION_L3=1 to enable L3 (Windows)
 *   RUNTIME_BASE_URL
 */
import { spawn } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const RUNTIME = join(ROOT, "services/runtime");
const BASE = process.env.RUNTIME_BASE_URL ?? "http://127.0.0.1:8765";
const LEVEL = (process.env.INTEGRATION_LEVEL ?? "all").toLowerCase();

async function waitHealth(timeoutMs = 90000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${BASE}/api/v1/health`);
      if (res.ok) return true;
    } catch {
      /* retry */
    }
    await sleep(1000);
  }
  return false;
}

function startRuntime() {
  const migrate = spawn("uv", ["run", "alembic", "upgrade", "head"], {
    cwd: RUNTIME,
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  migrate.stdout.on("data", (d) => process.stdout.write(`[migrate] ${d}`));
  migrate.stderr.on("data", (d) => process.stderr.write(`[migrate] ${d}`));

  return new Promise((resolve, reject) => {
    migrate.on("exit", (code) => {
      if (code !== 0) {
        reject(new Error(`alembic upgrade failed with code ${code}`));
        return;
      }
      const child = spawn(
        "uv",
        ["run", "uvicorn", "main:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", "8765"],
        {
          cwd: RUNTIME,
          env: {
            ...process.env,
            RUNTIME_REQUIRE_AUTH: process.env.RUNTIME_REQUIRE_AUTH ?? "false",
            COPILOT_REQUIRE_TOKEN: process.env.COPILOT_REQUIRE_TOKEN ?? "false",
          },
          stdio: ["ignore", "pipe", "pipe"],
        },
      );
      child.stdout.on("data", (d) => process.stdout.write(`[runtime] ${d}`));
      child.stderr.on("data", (d) => process.stderr.write(`[runtime] ${d}`));
      resolve(child);
    });
  });
}

async function loadGeneratedClient() {
  // Import package facade (types + createRuntimeClient). Avoid requiring Desktop.
  const clientPath = pathToFileURL(
    join(ROOT, "packages/runtime-client-ts/src/client/create-runtime-client.ts"),
  ).href;
  try {
    return await import(clientPath);
  } catch {
    // Fallback: plain fetch surface when TS module can't load under node without loader.
    return null;
  }
}

async function runL1() {
  console.log("[integration L1] contract surface…");
  const statusRes = await fetch(`${BASE}/api/v1/runtime/status`);
  if (!statusRes.ok) throw new Error(`status HTTP ${statusRes.status}`);
  const status = await statusRes.json();
  if (!status.apiVersion && !status.serviceVersion) {
    throw new Error("status missing apiVersion/serviceVersion");
  }

  const capsRes = await fetch(`${BASE}/api/v1/runtime/capabilities`);
  if (!capsRes.ok) throw new Error(`capabilities HTTP ${capsRes.status}`);
  const caps = await capsRes.json();
  if (!Array.isArray(caps.features)) throw new Error("capabilities.features missing");
  if (!caps.features.includes("chat.runtime.v2")) {
    throw new Error("missing capability chat.runtime.v2");
  }

  const compatRes = await fetch(`${BASE}/api/v1/runtime/compatibility`);
  if (!compatRes.ok) throw new Error(`compatibility HTTP ${compatRes.status}`);

  const jobRes = await fetch(`${BASE}/api/v1/runtime/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ jobType: "doctor", request: {} }),
  });
  if (!jobRes.ok) throw new Error(`create job HTTP ${jobRes.status}: ${await jobRes.text()}`);
  const job = await jobRes.json();
  const jobId = job.jobId || job.id;
  if (!jobId) throw new Error("job id missing");

  // Probe SSE briefly
  const controller = new AbortController();
  const sseTimer = setTimeout(() => controller.abort(), 2500);
  try {
    await fetch(`${BASE}/api/v1/runtime/jobs/${encodeURIComponent(jobId)}/events`, {
      headers: { Accept: "text/event-stream" },
      signal: controller.signal,
    });
  } catch {
    /* abort expected */
  } finally {
    clearTimeout(sseTimer);
  }

  const missing = await fetch(`${BASE}/api/v1/runtime/jobs/does-not-exist`);
  const body = await missing.json().catch(() => null);
  if (!body?.error?.code || !body?.error?.message || !body?.error?.requestId) {
    throw new Error(`error envelope invalid: ${JSON.stringify(body)}`);
  }
  const requestIdHeader = missing.headers.get("X-Request-ID");
  if (!requestIdHeader) {
    throw new Error("missing X-Request-ID response header");
  }

  // Assert generated schema exports chat-runs path symbols exist in schema.d.ts text
  const schemaPath = join(ROOT, "packages/runtime-client-ts/src/generated/schema.d.ts");
  const schemaText = readFileSync(schemaPath, "utf8");
  if (!schemaText.includes("/api/v1/chat-runs")) {
    throw new Error("generated schema missing /api/v1/chat-runs");
  }

  await loadGeneratedClient();
  console.log(`[integration L1] OK apiVersion=${status.apiVersion ?? caps.apiVersion}`);
}

async function runL2() {
  console.log("[integration L2] durable chat-runs…");
  const create = await fetch(`${BASE}/api/v1/chat-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      clientRunId: `integration-run-${Date.now()}`,
      instanceId: "integration-inst",
      sessionId: "integration-session",
      workspaceId: "integration-ws",
    }),
  });
  if (!create.ok) throw new Error(`create run HTTP ${create.status}: ${await create.text()}`);
  const runBody = await create.json();
  const runId = runBody.runId;
  if (!runId) throw new Error("runId missing");

  const turn = await fetch(`${BASE}/api/v1/chat-runs/${encodeURIComponent(runId)}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      clientRunId: runBody.clientRunId ?? runId,
      clientTurnId: `turn-${Date.now()}`,
      instanceId: "integration-inst",
      message: "integration hello",
    }),
  });
  if (!turn.ok) throw new Error(`create turn HTTP ${turn.status}: ${await turn.text()}`);

  let completed = false;
  for (let i = 0; i < 40; i += 1) {
    const eventsRes = await fetch(`${BASE}/api/v1/chat-runs/${encodeURIComponent(runId)}/events`);
    if (!eventsRes.ok) throw new Error(`events HTTP ${eventsRes.status}`);
    const events = await eventsRes.json();
    const types = (Array.isArray(events) ? events : []).map((e) => e.type || e.eventType);
    if (types.includes("turn.completed") || types.includes("agent.message.completed")) {
      completed = true;
      break;
    }
    await sleep(100);
  }
  if (!completed) throw new Error("L2 turn did not complete");

  const queue = await fetch(`${BASE}/api/v1/chat-runs/${encodeURIComponent(runId)}/queue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload: { message: "queued" } }),
  });
  if (!queue.ok) throw new Error(`queue HTTP ${queue.status}`);

  const abort = await fetch(`${BASE}/api/v1/chat-runs/${encodeURIComponent(runId)}/abort`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!abort.ok) throw new Error(`abort HTTP ${abort.status}`);

  const snap = await fetch(`${BASE}/api/v1/chat-runs/${encodeURIComponent(runId)}/snapshot`);
  if (!snap.ok) throw new Error(`snapshot HTTP ${snap.status}`);
  console.log("[integration L2] OK chat-runs turn/queue/abort/snapshot");
}

async function runL3() {
  if (process.env.INTEGRATION_L3 !== "1") {
    console.log("[integration L3] skipped (set INTEGRATION_L3=1 on windows-latest)");
    return;
  }
  if (process.platform !== "win32") {
    console.log("[integration L3] skipped (not Windows)");
    return;
  }
  console.log("[integration L3] Windows package smoke probe…");
  // Health already verified while Runtime is running locally for L1/L2.
  // Full installer smoke is owned by services/runtime package-windows target.
  const health = await fetch(`${BASE}/api/v1/health`);
  if (!health.ok) throw new Error("L3 health failed");
  const artifactsDir = join(ROOT, "artifacts");
  mkdirSync(artifactsDir, { recursive: true });
  const note = {
    level: "L3",
    platform: process.platform,
    checkedAt: new Date().toISOString(),
    health: true,
    note: "Installer MSI smoke delegated to runtime:package-windows in release/nightly jobs",
  };
  writeFileSync(join(artifactsDir, "integration-l3.json"), `${JSON.stringify(note, null, 2)}\n`);
  console.log("[integration L3] OK (health + artifact note)");
}

async function main() {
  const wantL1 = LEVEL === "all" || LEVEL === "l1";
  const wantL2 = LEVEL === "all" || LEVEL === "l2";
  const child = await startRuntime();
  try {
    const ok = await waitHealth();
    if (!ok) throw new Error("Runtime health check timed out");
    if (wantL1) await runL1();
    if (wantL2) await runL2();
    await runL3();
  } finally {
    child.kill("SIGTERM");
    await sleep(1000);
    if (!child.killed) child.kill("SIGKILL");
  }
}

main().catch((err) => {
  console.error("[integration-e2e] FAILED:", err instanceof Error ? err.message : err);
  process.exit(1);
});
