from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

def repo_root() -> Path:
    git = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if git.returncode == 0:
        return Path(git.stdout.strip())
    return Path(".").resolve()

def schema_errors(data, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)
    return [f"{'.'.join(map(str,e.absolute_path)) or '$'}: {e.message}" for e in v.iter_errors(data)]

def git_show_bytes(root: Path, commit: str, path: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=root, capture_output=True)
    return r.stdout if r.returncode == 0 else None

def git_blob_sha(root: Path, commit: str, path: str) -> str | None:
    r = subprocess.run(["git", "rev-parse", f"{commit}:{path}"], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

def commit_exists(root: Path, commit: str) -> bool:
    r = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=root, capture_output=True)
    return r.returncode == 0

def matching_binding(binding: dict, work_package_id: str) -> dict | None:
    return next((f for f in binding.get("features", []) if f.get("work_package_id") == work_package_id), None)

def validate_artifact(root: Path, item: dict) -> list[str]:
    errors = []
    for key in ("repository_id","path","commit","blob_sha","sha256","artifact_type","artifact_id","status","source_revision"):
        if not item.get(key):
            errors.append(f"artifact missing {key}")
    commit = item.get("commit","")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        return errors + [f"artifact commit invalid: {commit}"]
    if not commit_exists(root, commit):
        return errors + [f"artifact commit does not exist locally: {commit}"]
    data = git_show_bytes(root, commit, item["path"])
    if data is None:
        return errors + [f"artifact path missing at commit: {item['path']}@{commit}"]
    actual_blob = git_blob_sha(root, commit, item["path"])
    if actual_blob != item.get("blob_sha"):
        errors.append(f"artifact blob_sha mismatch: {item['path']}")
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != item.get("sha256"):
        errors.append(f"artifact sha256 mismatch: {item['path']}")
    if item["artifact_type"] == "STAGE_PRD" and item["status"] != "APPROVED":
        errors.append("stage PRD must be APPROVED")
    if item["artifact_type"] == "PLAN" and item["status"] not in {"VALIDATED","PASS"}:
        errors.append("plan must be VALIDATED/PASS")
    return errors


def validate_installed_kit(root: Path, gov: Path, binding: dict) -> list[str]:
    errors=[]
    manifest_path=gov/"kit/manifest.json"
    sums_path=gov/"kit/SHA256SUMS"
    if not manifest_path.exists() or not sums_path.exists():
        return ["canonical kit manifest/SHA256SUMS missing"]
    manifest_bytes=manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest()!=(binding.get("kit") or {}).get("manifest_sha256"):
        errors.append("installed kit manifest_sha256 mismatch")
    manifest=json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("kit",{}).get("tag")!=(binding.get("kit") or {}).get("tag"):
        errors.append("installed kit tag mismatch")
    if manifest.get("kit",{}).get("commit")!=(binding.get("kit") or {}).get("commit"):
        errors.append("installed kit commit mismatch")
    sums={}
    raw=sums_path.read_bytes()
    if b"\r" in raw: errors.append("installed kit SHA256SUMS contains CR")
    for line in raw.decode("utf-8").splitlines():
        if not line: continue
        digest,rel=line.split("  ",1);sums[rel]=digest
    if sums.get("manifest.json")!=hashlib.sha256(manifest_bytes).hexdigest():
        errors.append("installed kit SHA256SUMS does not protect manifest")
    for rel,digest in (manifest.get("files") or {}).items():
        target=root/".github"/rel[len("github/"):] if rel.startswith("github/") else gov/rel
        if not target.exists():
            errors.append(f"installed kit file missing: {rel}");continue
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            errors.append(f"installed kit file hash mismatch: {rel}")
    return errors

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semantic", action="store_true", default=True)
    args = ap.parse_args()
    root = repo_root()
    gov = root / ".agents/governance"
    errors = []

    binding_path = gov / "binding.yaml"
    if not binding_path.exists():
        raise SystemExit("LOCAL GOVERNANCE INVALID\n- binding.yaml missing")
    binding = yaml.safe_load(binding_path.read_text(encoding="utf-8"))

    for required in ("version","tag","commit","manifest_sha256"):
        if not (binding.get("kit") or {}).get(required):
            errors.append(f"binding kit.{required} missing")
    errors.extend(validate_installed_kit(root,gov,binding))

    schema_map = {
        "project-status.yaml":"project-report.schema.json",
    }
    for rel,schema in schema_map.items():
        p=gov/rel
        if p.exists():
            data=yaml.safe_load(p.read_text(encoding="utf-8"))
            errors += [f"{p}: {e}" for e in schema_errors(data,gov/"schemas"/schema)]

    for receipt_path in (gov / "receipts").glob("*.yaml"):
        receipt = yaml.safe_load(receipt_path.read_text(encoding="utf-8"))
        errors += [f"{receipt_path}: {e}" for e in schema_errors(receipt, gov/"schemas/delivery-receipt.schema.json")]
        matched = matching_binding(binding, receipt.get("work_package_id"))
        if not matched:
            errors.append(f"{receipt_path}: work package missing from binding")
        elif receipt.get("source_revision") != matched.get("source_revision"):
            errors.append(f"{receipt_path}: source_revision mismatch with binding")
        for key in ("stage_prds","plans","verification_reports"):
            for item in receipt.get("delivery",{}).get(key,[]):
                errors += [f"{receipt_path}: {e}" for e in validate_artifact(root,item)]
        for commit in receipt.get("delivery",{}).get("commits",[]):
            if not re.fullmatch(r"[0-9a-fA-F]{40}",commit):
                errors.append(f"{receipt_path}: invalid commit syntax {commit}")
            elif not commit_exists(root,commit):
                errors.append(f"{receipt_path}: commit does not exist {commit}")

        acceptance = receipt.get("acceptance") or {}
        report_rel = acceptance.get("report")
        if report_rel:
            report_path = root / report_rel
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                commits = receipt.get("delivery",{}).get("commits",[])
                if commits and report.get("repository_commit") not in commits:
                    errors.append(f"{report_path}: repository_commit must match an implementation commit")

    for p in (gov/"acceptance").glob("*.yaml"):
        data=yaml.safe_load(p.read_text(encoding="utf-8"))
        errors += [f"{p}: {e}" for e in schema_errors(data,gov/"schemas/acceptance-manifest.schema.json")]
    for p in (gov/"acceptance").glob("*.report.json"):
        data=json.loads(p.read_text(encoding="utf-8"))
        errors += [f"{p}: {e}" for e in schema_errors(data,gov/"schemas/acceptance-report.schema.json")]

    if errors:
        print("LOCAL GOVERNANCE INVALID")
        for e in errors:
            print("-",e)
        raise SystemExit(1)
    print("LOCAL GOVERNANCE VALID")

if __name__ == "__main__":
    main()
