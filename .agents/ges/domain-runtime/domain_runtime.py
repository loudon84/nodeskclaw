#!/usr/bin/env python3
"""GES Domain Pack Framework v1 runtime.

Core intentionally knows only the Domain Contract. Domain ids, file matching rules,
provider skills and plan-extension schemas are data loaded from installed packs.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DOMAIN_CONTRACT = "smc.ges.domain-activation.v1"
PROFILE_SCHEMA = "smc.ges.consumer-profile.v2"
PACK_SCHEMA = "smc.ges.domain-pack.v1"
REGISTRY_SCHEMA = "smc.ges.domain-registry.v1"


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"DOMAIN_CONFIG_MISSING: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"DOMAIN_CONFIG_INVALID_JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"DOMAIN_CONFIG_NOT_OBJECT: {path}")
    return value


def find_repo_root(path: Path) -> Path:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / ".agents").is_dir():
            return candidate
    raise ValueError(f"DOMAIN_REPO_ROOT_NOT_FOUND: {path}")


def installed_ges_root(repo: Path) -> Path:
    return repo / ".agents" / "ges"


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip().strip('"\'')
    return out


def section(text: str, heading: str) -> str | None:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else None


def cells(line: str) -> list[str]:
    return [item.strip() for item in line.strip().strip("|").split("|")]


def markdown_table(body: str | None) -> list[dict[str, str]]:
    if not body:
        return []
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    for index in range(len(lines) - 1):
        header, separator = cells(lines[index]), cells(lines[index + 1])
        if len(header) != len(separator):
            continue
        if not all(re.fullmatch(r":?-{3,}:?", item.replace(" ", "")) for item in separator):
            continue
        rows: list[dict[str, str]] = []
        for raw in lines[index + 2 :]:
            values = cells(raw)
            if len(values) != len(header):
                break
            rows.append(dict(zip(header, values)))
        return rows
    return []


def clean_cell(value: str) -> str:
    return value.strip().strip("`")


def change_rows(plan: Path) -> list[dict[str, str]]:
    text = plan.read_text(encoding="utf-8")
    rows = markdown_table(section(text, "Change Matrix"))
    normalized: list[dict[str, str]] = []
    for row in rows:
        cid = clean_cell(row.get("Change ID", "")).upper()
        file_symbol = clean_cell(row.get("File / Symbol", ""))
        if not cid or not file_symbol:
            continue
        path = file_symbol.split("#", 1)[0].strip()
        normalized.append(
            {
                "change_id": cid,
                "path": path.replace("\\", "/"),
                "kind": clean_cell(row.get("Kind", "")),
                "action": clean_cell(row.get("Action", "")),
                "target_state": clean_cell(row.get("Target State", "")),
            }
        )
    return normalized


def _matches_rule(change: dict[str, str], rules: dict[str, Any]) -> bool:
    path = change["path"]
    lower_path = path.lower()
    excluded = rules.get("exclude_globs", [])
    if any(fnmatch.fnmatch(lower_path, str(pattern).lower()) for pattern in excluded):
        return False

    selectors: list[bool] = []
    globs = [str(x) for x in rules.get("path_globs", [])]
    if globs:
        selectors.append(any(fnmatch.fnmatch(lower_path, pattern.lower()) for pattern in globs))
    extensions = [str(x).lower() for x in rules.get("extensions", [])]
    if extensions:
        selectors.append(any(lower_path.endswith(ext) for ext in extensions))
    kinds = [str(x).lower() for x in rules.get("kinds", [])]
    if kinds:
        selectors.append(change.get("kind", "").lower() in kinds)
    target_tokens = [str(x).lower() for x in rules.get("target_tokens", [])]
    if target_tokens:
        target = change.get("target_state", "").lower()
        selectors.append(any(token in target for token in target_tokens))

    return any(selectors) if selectors else False


def load_context(repo: Path, ges_root: Path | None = None, profile_path: Path | None = None) -> dict[str, Any]:
    ges = ges_root.resolve() if ges_root else installed_ges_root(repo)
    profile_file = profile_path.resolve() if profile_path else ges / "profile.json"
    profile = read_json(profile_file)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"DOMAIN_PROFILE_SCHEMA_INVALID: {profile.get('schema')}")

    registry_file = ges / "domain-packs" / "registry.json"
    registry = read_json(registry_file)
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise ValueError(f"DOMAIN_REGISTRY_SCHEMA_INVALID: {registry.get('schema')}")

    packs: dict[str, dict[str, Any]] = {}
    entries = registry.get("packs", {})
    if not isinstance(entries, dict):
        raise ValueError("DOMAIN_REGISTRY_PACKS_INVALID")
    for domain_id, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"DOMAIN_REGISTRY_ENTRY_INVALID: {domain_id}")
        relative = Path(str(entry.get("path", domain_id + "/pack.json")))
        pack_file = ges / "domain-packs" / relative
        pack = read_json(pack_file)
        if pack.get("schema") != PACK_SCHEMA:
            raise ValueError(f"DOMAIN_PACK_SCHEMA_INVALID: {domain_id}: {pack.get('schema')}")
        if pack.get("id") != domain_id:
            raise ValueError(f"DOMAIN_PACK_ID_MISMATCH: registry={domain_id} pack={pack.get('id')}")
        pack["__file__"] = pack_file.as_posix()
        activation_file = pack_file.parent / str(pack.get("activation_rules", "activation.json"))
        pack["__activation__"] = read_json(activation_file)
        lock_name = pack.get("policy_lock")
        if lock_name:
            pack["__policy_lock__"] = read_json(pack_file.parent / str(lock_name))
        packs[domain_id] = pack

    return {"ges_root": ges, "profile_path": profile_file, "profile": profile, "registry": registry, "packs": packs}


def policy_digest(context: dict[str, Any]) -> str:
    profile = context["profile"]
    enabled = profile.get("domains", {})
    payload: dict[str, Any] = {
        "profile": profile,
        "packs": {},
    }
    for domain_id in sorted(enabled):
        pack = context["packs"].get(domain_id)
        if pack is None:
            raise ValueError(f"DOMAIN_PACK_NOT_INSTALLED: {domain_id}")
        payload["packs"][domain_id] = {
            "manifest": {k: v for k, v in pack.items() if not k.startswith("__")},
            "activation": pack["__activation__"],
            "policy_lock": pack.get("__policy_lock__"),
        }
    return sha256_json(payload)


def resolve(plan: Path, ges_root: Path | None = None, profile_path: Path | None = None) -> dict[str, Any]:
    repo = find_repo_root(plan)
    context = load_context(repo, ges_root=ges_root, profile_path=profile_path)
    changes = change_rows(plan)
    profile_domains = context["profile"].get("domains", {})
    if not isinstance(profile_domains, dict):
        raise ValueError("DOMAIN_PROFILE_DOMAINS_INVALID")

    resolved: list[dict[str, Any]] = []
    for domain_id in sorted(profile_domains):
        config = profile_domains[domain_id]
        if not isinstance(config, dict):
            raise ValueError(f"DOMAIN_PROFILE_ENTRY_INVALID: {domain_id}")
        pack = context["packs"].get(domain_id)
        if pack is None:
            raise ValueError(f"DOMAIN_PACK_NOT_INSTALLED: {domain_id}")
        mode = str(config.get("activation", "auto")).lower()
        if mode not in {"auto", "always", "off"}:
            raise ValueError(f"DOMAIN_ACTIVATION_MODE_INVALID: {domain_id}: {mode}")
        matches = [] if mode == "off" else [c["change_id"] for c in changes if _matches_rule(c, pack["__activation__"])]
        required = mode == "always" or (mode == "auto" and bool(matches))
        capabilities = pack.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError(f"DOMAIN_CAPABILITIES_INVALID: {domain_id}")
        resolved.append(
            {
                "id": domain_id,
                "version": str(pack.get("version", "")),
                "status": "REQUIRED" if required else "NOT_REQUIRED",
                "trigger_changes": matches,
                "capabilities": sorted(capabilities.keys()) if required else [],
            }
        )

    return {
        "schema": DOMAIN_CONTRACT,
        "profile": f"{context['profile'].get('id')}@{context['profile'].get('version')}",
        "policy_digest": policy_digest(context),
        "domains": resolved,
    }


def providers(plan: Path, phase: str, ges_root: Path | None = None, profile_path: Path | None = None) -> list[dict[str, str]]:
    repo = find_repo_root(plan)
    context = load_context(repo, ges_root=ges_root, profile_path=profile_path)
    activation = resolve(plan, ges_root=ges_root, profile_path=profile_path)
    out: list[dict[str, str]] = []
    for domain in activation["domains"]:
        if domain["status"] != "REQUIRED":
            continue
        pack = context["packs"][domain["id"]]
        capability = pack.get("capabilities", {}).get(phase)
        if not capability:
            continue
        if isinstance(capability, str):
            skill = capability
        elif isinstance(capability, dict):
            skill = str(capability.get("skill", ""))
        else:
            raise ValueError(f"DOMAIN_CAPABILITY_INVALID: {domain['id']}:{phase}")
        if not skill:
            raise ValueError(f"DOMAIN_CAPABILITY_SKILL_MISSING: {domain['id']}:{phase}")
        out.append({"domain": domain["id"], "version": domain["version"], "phase": phase, "skill": skill})
    return out


def activation_ledger(activation: dict[str, Any]) -> str:
    lines = [
        "## Domain Activation Ledger",
        "",
        "| Domain | Pack Version | Trigger Changes | Capabilities | Status |",
        "|---|---:|---|---|---|",
    ]
    domains = activation.get("domains", [])
    if not domains:
        return "## Domain Activation Ledger\n\nNone"
    for row in domains:
        changes = ",".join(row.get("trigger_changes", [])) or "-"
        caps = ",".join(row.get("capabilities", [])) or "-"
        lines.append(f"| {row['id']} | {row['version']} | {changes} | {caps} | {row['status']} |")
    return "\n".join(lines)


def _change_lookup(plan: Path) -> dict[str, dict[str, str]]:
    return {row["change_id"]: row for row in change_rows(plan)}


def render_extensions(plan: Path, activation: dict[str, Any], ges_root: Path | None = None, profile_path: Path | None = None) -> str:
    repo = find_repo_root(plan)
    context = load_context(repo, ges_root=ges_root, profile_path=profile_path)
    changes = _change_lookup(plan)
    blocks: list[str] = []
    for domain in activation.get("domains", []):
        if domain.get("status") != "REQUIRED":
            continue
        pack = context["packs"][domain["id"]]
        extension = pack.get("plan_extension")
        if not extension:
            continue
        if not isinstance(extension, dict):
            raise ValueError(f"DOMAIN_PLAN_EXTENSION_INVALID: {domain['id']}")
        section_name = str(extension.get("section", "")).strip()
        columns = extension.get("columns", [])
        defaults = extension.get("defaults", {})
        if not section_name or not isinstance(columns, list) or not columns:
            raise ValueError(f"DOMAIN_PLAN_EXTENSION_SCHEMA_INVALID: {domain['id']}")
        if not isinstance(defaults, dict):
            raise ValueError(f"DOMAIN_PLAN_EXTENSION_DEFAULTS_INVALID: {domain['id']}")
        header = "| " + " | ".join(str(x) for x in columns) + " |"
        separator = "|" + "|".join("---" for _ in columns) + "|"
        rows = []
        for cid in domain.get("trigger_changes", []):
            change = changes.get(cid, {})
            values: list[str] = []
            for column in columns:
                column = str(column)
                if column == "Change ID":
                    value = cid
                elif column == "Surface":
                    value = change.get("path", "<GROUND>")
                else:
                    value = str(defaults.get(column, "<DECIDE>"))
                values.append(value)
            rows.append("| " + " | ".join(values) + " |")
        blocks.append(f"## {section_name}\n\n{header}\n{separator}\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def _parse_activation_ledger(plan: Path) -> list[dict[str, str]]:
    return markdown_table(section(plan.read_text(encoding="utf-8"), "Domain Activation Ledger"))


def validate_plan(plan: Path, ges_root: Path | None = None, profile_path: Path | None = None) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    text = plan.read_text(encoding="utf-8")
    meta = frontmatter(text)
    if meta.get("domain_contract") != DOMAIN_CONTRACT:
        errors.append({"code": "PLAN_DOMAIN_CONTRACT_INVALID", "detail": meta.get("domain_contract", "")})
        return errors
    try:
        expected = resolve(plan, ges_root=ges_root, profile_path=profile_path)
    except ValueError as exc:
        errors.append({"code": str(exc).split(":", 1)[0], "detail": str(exc)})
        return errors

    if meta.get("consumer_profile") != expected["profile"]:
        errors.append({"code": "PLAN_CONSUMER_PROFILE_DRIFT", "detail": f"expected={expected['profile']} actual={meta.get('consumer_profile','')}"})
    if meta.get("domain_policy_digest") != expected["policy_digest"]:
        errors.append({"code": "DOMAIN_POLICY_STALE", "detail": f"expected={expected['policy_digest']} actual={meta.get('domain_policy_digest','')}"})

    actual_rows = _parse_activation_ledger(plan)
    actual = {
        row.get("Domain", ""): {
            "version": row.get("Pack Version", ""),
            "changes": [x for x in row.get("Trigger Changes", "").split(",") if x and x != "-"],
            "caps": [x for x in row.get("Capabilities", "").split(",") if x and x != "-"],
            "status": row.get("Status", ""),
        }
        for row in actual_rows
        if row.get("Domain")
    }
    expected_map = {
        row["id"]: {
            "version": row["version"],
            "changes": row["trigger_changes"],
            "caps": row["capabilities"],
            "status": row["status"],
        }
        for row in expected["domains"]
    }
    if actual != expected_map:
        errors.append({"code": "PLAN_DOMAIN_ACTIVATION_DRIFT", "detail": f"expected={expected_map} actual={actual}"})

    repo = find_repo_root(plan)
    context = load_context(repo, ges_root=ges_root, profile_path=profile_path)
    for domain in expected["domains"]:
        if domain["status"] != "REQUIRED":
            continue
        pack = context["packs"][domain["id"]]
        extension = pack.get("plan_extension")
        if isinstance(extension, dict):
            name = str(extension.get("section", ""))
            rows = markdown_table(section(text, name))
            change_ids = [row.get("Change ID", "") for row in rows]
            if sorted(change_ids) != sorted(domain["trigger_changes"]):
                errors.append({"code": "PLAN_DOMAIN_EXTENSION_COVERAGE_INVALID", "detail": f"domain={domain['id']} expected={domain['trigger_changes']} actual={change_ids}"})

        validator = pack.get("plan_validator")
        if validator:
            validator_path = repo / str(validator)
            if not validator_path.is_file():
                errors.append({"code": "DOMAIN_PLAN_VALIDATOR_MISSING", "detail": f"{domain['id']}: {validator}"})
                continue
            result = subprocess.run(
                [sys.executable, str(validator_path), str(plan), "--json"],
                cwd=repo,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )
            if result.returncode:
                try:
                    payload = json.loads(result.stdout or "{}")
                    child_errors = payload.get("errors", [])
                except json.JSONDecodeError:
                    child_errors = []
                if child_errors:
                    for item in child_errors:
                        errors.append({"code": str(item.get("code", "DOMAIN_PLAN_VALIDATOR_FAILED")), "detail": str(item.get("detail", ""))})
                else:
                    errors.append({"code": "DOMAIN_PLAN_VALIDATOR_FAILED", "detail": f"{domain['id']}: {result.stderr.strip()}"})
    return errors


def assert_policy(plan: Path, ges_root: Path | None = None, profile_path: Path | None = None) -> dict[str, Any]:
    meta = frontmatter(plan.read_text(encoding="utf-8"))
    resolved = resolve(plan, ges_root=ges_root, profile_path=profile_path)
    if meta.get("domain_policy_digest") != resolved["policy_digest"]:
        raise ValueError(f"DOMAIN_POLICY_STALE: expected={resolved['policy_digest']} actual={meta.get('domain_policy_digest','')}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("resolve", "validate-plan", "assert-policy"):
        p = sub.add_parser(name)
        p.add_argument("plan", type=Path)
        p.add_argument("--ges-root", type=Path)
        p.add_argument("--profile", type=Path)
        p.add_argument("--json", action="store_true")
    p = sub.add_parser("providers")
    p.add_argument("plan", type=Path)
    p.add_argument("--phase", required=True, choices=("engineering", "review", "verification"))
    p.add_argument("--ges-root", type=Path)
    p.add_argument("--profile", type=Path)
    p.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "resolve":
            payload = resolve(args.plan.resolve(), args.ges_root, args.profile)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else activation_ledger(payload))
            return 0
        if args.command == "providers":
            payload = providers(args.plan.resolve(), args.phase, args.ges_root, args.profile)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "\n".join(x["skill"] for x in payload))
            return 0
        if args.command == "validate-plan":
            errors = validate_plan(args.plan.resolve(), args.ges_root, args.profile)
            if args.json:
                print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
            elif errors:
                print("\n".join(f"{x['code']}: {x['detail']}" for x in errors), file=sys.stderr)
            else:
                print("Domain plan validation passed")
            return 1 if errors else 0
        payload = assert_policy(args.plan.resolve(), args.ges_root, args.profile)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "Domain policy binding is fresh")
        return 0
    except ValueError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"valid": False, "errors": [{"code": str(exc).split(":", 1)[0], "detail": str(exc)}]}, ensure_ascii=False, indent=2))
        else:
            print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
