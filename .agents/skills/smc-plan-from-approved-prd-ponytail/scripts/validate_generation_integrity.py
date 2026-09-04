#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

GROUNDING_COLUMNS = (
    "Change ID",
    "Target",
    "Baseline State",
    "Symbol / Entry Resolution",
    "Caller / Callee Evidence",
    "Existing Reuse Search",
    "Result",
)
MATRIX_COLUMNS = (
    "Change ID",
    "File / Symbol",
    "Kind",
    "Action",
    "Existing Owner",
    "Todo Owner",
    "Target State",
    "PRD Capability",
    "New File?",
)


@dataclass(frozen=True)
class IntegrityError:
    code: str
    message: str


BaselineReader = Callable[[str, str], str | None]
CommitExists = Callable[[str], bool]


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if not match:
        return {}
    values: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def section(text: str, name: str) -> str | None:
    match = re.search(rf"^##\s+{re.escape(name)}\s*$\n?(.*?)(?=^##\s+|\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


def cells(line: str) -> list[str]:
    return [value.strip() for value in line.strip().strip("|").split("|")]


def table(body: str | None, expected: tuple[str, ...]) -> list[dict[str, str]] | None:
    if body is None:
        return None
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    for index in range(len(lines) - 1):
        header = cells(lines[index])
        separator = cells(lines[index + 1])
        if tuple(header) != expected:
            continue
        if len(separator) != len(header) or not all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in separator):
            continue
        rows: list[dict[str, str]] = []
        for raw in lines[index + 2 :]:
            values = cells(raw)
            if len(values) != len(header):
                break
            rows.append(dict(zip(header, values)))
        return rows
    return []


def target_parts(value: str) -> tuple[str, str | None]:
    normalized = value.strip().strip("`")
    path, separator, symbol = normalized.partition("#")
    return path.replace("\\", "/"), symbol if separator else None


def python_node_has_name(nodes: list[ast.stmt], name: str) -> bool:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return True
    return False


def symbol_resolves(path: str, symbol: str, content: str) -> bool:
    parts = symbol.split("#")
    if Path(path).suffix.lower() == ".py":
        try:
            module = ast.parse(content)
        except SyntaxError:
            return False
        if len(parts) == 1:
            return python_node_has_name(module.body, parts[0])
        owner = next((node for node in module.body if isinstance(node, ast.ClassDef) and node.name == parts[0]), None)
        return owner is not None and python_node_has_name(owner.body, parts[1])

    def has_definition(name: str) -> bool:
        patterns = (
            rf"\b(?:async\s+)?function\s+{re.escape(name)}\b",
            rf"\b(?:const|let|var|class|interface|type|enum)\s+{re.escape(name)}\b",
            rf"(?:^|\n)\s*(?:async\s+)?{re.escape(name)}\s*\(",
        )
        return any(re.search(pattern, content) for pattern in patterns)

    return all(has_definition(part) for part in parts)


def validate(
    text: str,
    baseline_reader: BaselineReader | None = None,
    commit_exists: CommitExists | None = None,
) -> list[IntegrityError]:
    errors: list[IntegrityError] = []
    metadata = frontmatter(text)
    grounding_source = metadata.get("grounding_source", "")
    fingerprint = metadata.get("working_tree_fingerprint", "")
    if grounding_source not in {"committed_baseline", "working_tree"}:
        errors.append(IntegrityError("GROUNDING_SOURCE_INVALID", "grounding_source must be committed_baseline or working_tree"))
    if grounding_source == "working_tree" and (not fingerprint or fingerprint in {"<GROUND>", "TBD", "<TBD>"}):
        errors.append(IntegrityError("GROUNDING_WORKTREE_FINGERPRINT_INVALID", "working_tree grounding requires a concrete fingerprint"))
    grounding_body = section(text, "Grounding Evidence Ledger")
    boundary_body = section(text, "Contract / Data Flow Closure Matrix")
    generated_body = section(text, "Generated Outputs Ledger")

    if grounding_body is None:
        errors.append(IntegrityError("PLAN_GROUNDING_LEDGER_MISSING", "Grounding Evidence Ledger is required"))
    if boundary_body is None:
        errors.append(IntegrityError("PLAN_BOUNDARY_CLOSURE_MISSING", "Contract / Data Flow Closure Matrix is required"))
    if generated_body is None:
        errors.append(IntegrityError("PLAN_GENERATED_OUTPUTS_LEDGER_MISSING", "Generated Outputs Ledger is required"))

    matrix_rows = table(section(text, "Change Matrix"), MATRIX_COLUMNS)
    grounding_rows = table(grounding_body, GROUNDING_COLUMNS)
    if matrix_rows is None or grounding_rows is None:
        return errors
    if matrix_rows == []:
        errors.append(IntegrityError("PLAN_CHANGE_MATRIX_INVALID", "Change Matrix schema is invalid or empty"))
        return errors
    if grounding_rows == []:
        errors.append(IntegrityError("PLAN_GROUNDING_LEDGER_INVALID", "Grounding Evidence Ledger schema is invalid or empty"))
        return errors

    required_changes = {
        row["Change ID"]
        for row in matrix_rows
        if row["Action"].strip().upper() != "KEEP"
    }
    grounding_by_change = {row["Change ID"]: row for row in grounding_rows}
    for change_id in sorted(required_changes - set(grounding_by_change)):
        errors.append(IntegrityError("PLAN_GROUNDING_CHANGE_MISSING", f"{change_id} has no grounding evidence"))
    for change_id in sorted(required_changes & set(grounding_by_change)):
        if grounding_by_change[change_id]["Result"].strip().upper() != "PASS":
            errors.append(IntegrityError("PLAN_GROUNDING_RESULT_INVALID", f"{change_id} grounding result must be PASS"))

    if baseline_reader is not None:
        grounded_commit = metadata.get("grounded_commit", "")
        if commit_exists is not None and not commit_exists(grounded_commit):
            errors.append(IntegrityError("GROUNDING_COMMIT_INVALID", f"grounded_commit {grounded_commit or '<missing>'} is not a resolvable commit"))
            return errors
        checked_targets: set[str] = set()
        for row in matrix_rows:
            action = row["Action"].strip().upper()
            if action == "KEEP":
                continue
            path, symbol = target_parts(row["File / Symbol"])
            key = f"{path}#{symbol or ''}"
            if key in checked_targets:
                continue
            checked_targets.add(key)
            content = baseline_reader(grounded_commit, path)
            is_new = action == "ADD" or row["New File?"].strip().lower() == "yes"
            if is_new and content is not None:
                errors.append(IntegrityError("PLAN_NEW_TARGET_ALREADY_EXISTS", f"{row['Change ID']} target {path} already exists at {grounded_commit}"))
                continue
            if not is_new and content is None:
                errors.append(IntegrityError("GROUNDING_TARGET_NOT_FOUND", f"{row['Change ID']} target {path} is absent at {grounded_commit}"))
                continue
            if not is_new and symbol and content is not None and not symbol_resolves(path, symbol, content):
                errors.append(IntegrityError("GROUNDING_SYMBOL_NOT_FOUND", f"{row['Change ID']} symbol {symbol} is absent in {path} at {grounded_commit}"))
    return errors


def git_baseline_reader(repo_root: Path) -> BaselineReader:
    def read(commit: str, path: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    return read


def git_commit_exists(repo_root: Path) -> CommitExists:
    def exists(commit: str) -> bool:
        if not commit:
            return False
        result = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    return exists


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo = subprocess.run(
        ["git", "-C", str(args.plan.resolve().parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if repo.returncode != 0:
        errors = [IntegrityError("GROUNDING_REPOSITORY_NOT_FOUND", "plan is not inside a Git repository")]
    else:
        reader = git_baseline_reader(Path(repo.stdout.strip()))
        commit_checker = git_commit_exists(Path(repo.stdout.strip()))
        errors = validate(
            args.plan.read_text(encoding="utf-8"),
            baseline_reader=reader,
            commit_exists=commit_checker,
        )
    if args.json:
        print(json.dumps([asdict(error) for error in errors], ensure_ascii=False, indent=2))
    elif errors:
        for error in errors:
            print(f"{error.code}: {error.message}")
    else:
        print("PASS")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
