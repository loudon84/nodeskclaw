from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
import yaml


def run(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (p.stdout or "").strip() if p.returncode == 0 else ""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def full_sha(value: str | None) -> str | None:
    if value and re.fullmatch(r"[0-9a-fA-F]{40}", value):
        return value
    return None


def artifact_ref(repo: Path, repository_id: str, artifact_id: str, path_value: str | None, artifact_type: str, status: str, source_revision: str) -> dict | None:
    if not path_value:
        return None
    path = repo / path_value
    if not path.is_file():
        return None
    commit = full_sha(run(repo, "log", "-1", "--format=%H", "--", path_value))
    blob_sha = full_sha(run(repo, "hash-object", "--", path_value))
    if not commit or not blob_sha:
        raise SystemExit(f"strong ArtifactRef requires full commit and blob SHA: {path_value}")
    return {
        "repository_id": repository_id,
        "path": path_value.replace("\\", "/"),
        "commit": commit,
        "blob_sha": blob_sha,
        "sha256": sha256_file(path),
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "status": status,
        "source_revision": source_revision,
    }


def kit_pin(repo: Path) -> dict:
    lock_path = repo / ".agents/governance.lock"
    binding_path = repo / ".agents/governance/binding.yaml"
    kit = {}
    central_commit = None
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        kit = {
            "version": lock.get("version"),
            "tag": lock.get("tag"),
            "commit": lock.get("commit"),
            "manifest_sha256": lock.get("manifest_sha256"),
        }
        central_commit = lock.get("commit")
    elif binding_path.exists():
        binding = load_yaml(binding_path)
        kit = dict(binding.get("kit") or {})
        central_commit = kit.get("commit") or (binding.get("central_commit"))
    if not all(kit.get(k) for k in ("version", "tag", "commit", "manifest_sha256")):
        raise SystemExit("receipt v2 requires a canonical kit pin in .agents/governance.lock or binding.yaml")
    if not full_sha(kit.get("commit")):
        raise SystemExit("kit pin commit must be a full 40-char SHA")
    return kit, central_commit


def contract_pins(repo: Path, wp: dict) -> list[dict]:
    pins = []
    local_contracts = repo / ".agents/governance/contracts"
    for item in wp.get("contract_inputs", []) or []:
        cid = item["contract_id"]
        version = item.get("version") or item.get("required_version")
        tag = item.get("tag")
        commit = item.get("commit")
        local = local_contracts / f"{cid}.yaml"
        if local.exists():
            doc = load_yaml(local)
            rel = next((r for r in doc.get("releases", []) if r.get("version") == version), None) or doc.get("current_release") or {}
            tag = tag or rel.get("tag")
            commit = commit or rel.get("peeled_commit") or rel.get("commit")
        lock = ((wp.get("evidence") or {}).get("consumer_lock") or {})
        if lock.get("version") == version:
            tag = tag or lock.get("tag")
            commit = commit or lock.get("commit")
        if not tag or not full_sha(commit):
            raise SystemExit(f"contract pin requires immutable tag and full commit: {cid}@{version}")
        pins.append({"contract_id": cid, "version": version, "tag": tag, "commit": commit})
    return pins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--work-package", required=True, help="synced work package yaml")
    ap.add_argument("--status", required=True)
    ap.add_argument("--acceptance-report")
    ap.add_argument("--output")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    wp = load_yaml(Path(args.work_package))
    head = full_sha(run(repo, "rev-parse", "HEAD"))
    delivery = wp.get("local_delivery") or {}
    source_revision = wp["source_revision"]
    repository_id = wp["repository_id"]

    prds = []
    ref = artifact_ref(repo, repository_id, f"PRD-{wp['work_package_id']}", delivery.get("prd"), "STAGE_PRD", "APPROVED", source_revision)
    if ref:
        prds.append(ref)
    plans = []
    ref = artifact_ref(repo, repository_id, f"PLAN-{wp['work_package_id']}", delivery.get("plan"), "PLAN", "VALIDATED", source_revision)
    if ref:
        plans.append(ref)

    log = run(repo, "log", "--format=%H%x00%B%x00", "-n", "500")
    commits = []
    chunks = log.split("\x00")
    for i in range(0, len(chunks) - 1, 2):
        sha, body = chunks[i].strip(), chunks[i + 1]
        if full_sha(sha) and f"SMC-Work-Package: {wp['work_package_id']}" in body:
            commits.append(sha)
    if args.status in {"REVIEW", "VERIFIED", "DONE"} and not commits:
        if not head:
            raise SystemExit("receipt v2 implementation commit must be a full 40-char SHA")
        commits = [head]

    kit, central_commit = kit_pin(repo)

    acceptance = {"manifest": None, "report": None, "status": "NOT_DEFINED"}
    if args.acceptance_report:
        ar = Path(args.acceptance_report)
        if ar.exists():
            report = json.loads(ar.read_text(encoding="utf-8"))
            acceptance = {
                "manifest": None,
                "report": str(ar).replace("\\", "/"),
                "status": report.get("status", "PARTIAL"),
            }

    receipt = {
        "receipt_version": "2",
        "feature_id": wp["feature_id"],
        "work_package_id": wp["work_package_id"],
        "repository_id": repository_id,
        "source_revision": source_revision,
        "status": args.status,
        "sync": {
            "governance_kit_version": kit["version"],
            "central_commit": central_commit,
            "kit": kit,
            "contract_pins": contract_pins(repo, wp),
        },
        "delivery": {
            "stage_prds": prds,
            "issues": [],
            "bugs": [],
            "plans": plans,
            "pull_requests": [],
            "commits": commits,
            "verification_reports": [],
        },
        "acceptance": acceptance,
        "evidence": wp.get("evidence") or {},
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    output = Path(args.output) if args.output else repo / ".agents/governance/receipts" / f"{wp['work_package_id']}.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(receipt, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
    print(output)

if __name__ == "__main__":
    main()
