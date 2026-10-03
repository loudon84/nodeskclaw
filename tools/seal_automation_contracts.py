from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(
    root: Path,
    *,
    contract_name: str,
    provider: str,
    consumer: str,
    head: str,
) -> None:
    root = root.resolve()
    files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"SHA256SUMS", "manifest.json"}
    )
    artifacts = {rel: sha256_file(root / rel) for rel in files}
    schema_ids: list[str] = []
    for rel in files:
        if rel.startswith("schemas/") and rel.endswith(".json"):
            data = json.loads((root / rel).read_text(encoding="utf-8"))
            schema_id = data.get("$id")
            if isinstance(schema_id, str):
                schema_ids.append(schema_id)
    manifest = {
        "contractName": contract_name,
        "contractVersion": "1.0.0",
        "bundleFormatVersion": "1",
        "provider": provider,
        "consumer": consumer,
        "implementationHeadSha": head,
        "releaseCommitSha": head,
        "acp": "unsupported",
        "production_gate": "unpassed",
        "schemaIds": sorted(schema_ids),
        "artifacts": artifacts,
        "bundleDigest": "pending",
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    all_files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    lines = [f"{sha256_file(root / rel)}  {rel}" for rel in all_files]
    sums_path = root / "SHA256SUMS"
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    manifest["bundleDigest"] = sha256_file(sums_path)
    # Keep bundleDigest out of a recursive rehash loop: store digest of previous SHA256SUMS
    # then rewrite SHA256SUMS once with updated manifest that includes that digest.
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [f"{sha256_file(root / rel)}  {rel}" for rel in all_files]
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"sealed {root}")


def main() -> None:
    head = Path(".git/HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1]
        head = Path(".git")
        for part in ref.split("/"):
            head = head / part
        head = head.read_text(encoding="utf-8").strip()
    seal(
        Path("nodeskclaw-backend/contracts/remote-agent-automation/v1.0.0"),
        contract_name="REMOTE-AGENT-AUTOMATION-CONTRACT",
        provider="nodeskclaw-backend",
        consumer="nodeskclaw-task",
        head=head,
    )
    seal(
        Path("nodeskclaw-task/contracts/agent-automation/v1.0.0"),
        contract_name="AGENT-AUTOMATION-CONTRACT",
        provider="nodeskclaw-task",
        consumer="smc-copilot/apps/work",
        head=head,
    )


if __name__ == "__main__":
    main()
