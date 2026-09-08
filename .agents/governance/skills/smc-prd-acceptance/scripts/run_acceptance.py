from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_text(text: str) -> str:
    return sha_bytes(text.encode("utf-8", errors="replace"))

def git_head(repo: Path) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("repository_commit unavailable")
    return r.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--output", required=True)
    ap.add_argument("--attestation-output")
    ap.add_argument("--repository-id")
    ap.add_argument("--artifact-name")
    ap.add_argument("--allow-manual", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    manifest_path = Path(args.manifest).resolve()
    manifest_bytes = manifest_path.read_bytes()
    doc = yaml.safe_load(manifest_bytes.decode("utf-8"))
    results = []
    overall = "PASS"

    for v in doc["verifications"]:
        if v["type"] == "manual" and not args.allow_manual:
            results.append({
                "verification_id":v["id"], "status":"SKIPPED", "exit_code":None,
                "duration_ms":0, "stdout_sha256":None, "stderr_sha256":None
            })
            if v.get("blocking", True):
                overall = "PARTIAL"
            continue
        cwd = repo / v.get("cwd", ".")
        started = time.monotonic()
        try:
            r = subprocess.run(
                v["command"], cwd=cwd, shell=True, capture_output=True, text=True,
                timeout=v.get("timeout_seconds", 600),
            )
            dur = int((time.monotonic()-started)*1000)
            status = "PASS" if r.returncode == 0 else "FAIL"
            if status == "FAIL" and v.get("blocking", True):
                overall = "FAIL"
            results.append({
                "verification_id":v["id"], "status":status, "exit_code":r.returncode,
                "duration_ms":dur, "stdout_sha256":sha_text(r.stdout), "stderr_sha256":sha_text(r.stderr)
            })
        except subprocess.TimeoutExpired as e:
            dur = int((time.monotonic()-started)*1000)
            if v.get("blocking", True):
                overall = "FAIL"
            results.append({
                "verification_id":v["id"], "status":"FAIL", "exit_code":124,
                "duration_ms":dur, "stdout_sha256":sha_text(e.stdout or ""), "stderr_sha256":sha_text(e.stderr or "")
            })

    commit = git_head(repo)
    report = {
        "report_version":"2",
        "feature_id":doc["feature_id"],
        "work_package_id":doc["work_package_id"],
        "source_revision":doc["prd"]["source_revision"],
        "repository_commit":commit,
        "status":overall,
        "results":results,
        "generated_at":datetime.now(timezone.utc).isoformat(),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    report_bytes = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    out.write_bytes(report_bytes)

    if args.attestation_output:
        repository = os.getenv("GITHUB_REPOSITORY")
        run_id = os.getenv("GITHUB_RUN_ID")
        if not repository or not run_id:
            raise SystemExit("attestation output requires GitHub Actions environment")
        repository_id = args.repository_id or os.getenv("SMC_REPOSITORY_ID")
        artifact_name = args.artifact_name or os.getenv("SMC_ACCEPTANCE_ARTIFACT_NAME")
        if not repository_id or not artifact_name:
            raise SystemExit("repository-id and artifact-name are required for attestation")
        attestation = {
            "attestation_version":"1",
            "provider":"github-actions",
            "repository":repository,
            "repository_id":repository_id,
            "commit":commit,
            "workflow":os.getenv("GITHUB_WORKFLOW",""),
            "workflow_sha":os.getenv("GITHUB_WORKFLOW_SHA") or None,
            "run_id":run_id,
            "job_id":os.getenv("GITHUB_JOB") or None,
            "actor":os.getenv("GITHUB_ACTOR") or None,
            "artifact_name":artifact_name,
            "report_sha256":sha_bytes(report_bytes),
            "manifest_sha256":sha_bytes(manifest_bytes),
            "generated_at":datetime.now(timezone.utc).isoformat(),
        }
        att = Path(args.attestation_output)
        att.parent.mkdir(parents=True, exist_ok=True)
        att.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"ACCEPTANCE {overall}: {out}")
    raise SystemExit(0 if overall == "PASS" else 2)

if __name__ == "__main__":
    main()
