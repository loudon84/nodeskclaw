#!/usr/bin/env python3
"""Create an implementation commit after Plan Review + Verification.

Avoids Cursor Shell injecting Co-authored-by by using git commit-tree plumbing.
Author is always SMC-Copilot <smc-copilot@smart-core.com>.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AUTHOR_NAME = "SMC-Copilot"
AUTHOR_EMAIL = "smc-copilot@smart-core.com"
AUTHOR = f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>"
COAUTHOR_RE = re.compile(r"(?im)^Co-authored-by:\s*.+$")
MSG_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|chore|build|revert)"
    r"(\([a-z0-9][a-z0-9/_-]*\))?: .+\S$"
)

DEFAULT_DENY_GLOBS = (
    ".cursor/plans/",
    ".env",
    ".env.",
    "node_modules/",
    ".venv/",
    "__pycache__/",
)


def find_git() -> str:
    candidates = [
        shutil.which("git"),
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("git executable not found")


def run(
    git: str,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [git, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise SystemExit(f"git {' '.join(args)} failed ({completed.returncode}): {detail}")
    return completed


def repo_root(git: str) -> Path:
    out = run(git, ["rev-parse", "--show-toplevel"]).stdout.strip()
    return Path(out)


def normalize_rel(path: str, root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise SystemExit(f"path outside repo: {path}") from exc
        return rel.as_posix()
    posix = p.as_posix()
    while posix.startswith("./"):
        posix = posix[2:]
    return posix


def denied(rel: str) -> str | None:
    posix = rel.replace("\\", "/")
    name = Path(posix).name
    if name in {".env", ".env.local"} or name.startswith(".env."):
        return "env/secret file"
    for prefix in DEFAULT_DENY_GLOBS:
        if posix.startswith(prefix) or f"/{prefix}" in f"/{posix}":
            return f"denied prefix {prefix}"
    if posix.endswith(".plan.md") or "/.cursor/plans/" in f"/{posix}":
        return "plan file (keep out of implementation commit)"
    return None


def validate_message(message: str) -> str:
    text = message.replace("\r\n", "\n").strip() + "\n"
    subject = text.splitlines()[0] if text.splitlines() else ""
    if not MSG_RE.match(subject):
        raise SystemExit(
            "message subject must match "
            "`type(scope): 中文说明` (Conventional Commits + Chinese subject)"
        )
    if COAUTHOR_RE.search(text):
        raise SystemExit("message must not contain Co-authored-by")
    return text


def stage_files(git: str, root: Path, files: list[str]) -> list[str]:
    if not files:
        raise SystemExit("no files provided; pass paths after --")
    rels: list[str] = []
    for raw in files:
        rel = normalize_rel(raw, root)
        reason = denied(rel)
        if reason:
            raise SystemExit(f"refusing to stage {rel}: {reason}")
        target = root / rel
        if not target.exists() and run(git, ["ls-files", "--error-unmatch", rel], check=False).returncode != 0:
            raise SystemExit(f"missing path: {rel}")
        rels.append(rel)
    run(git, ["add", "--", *rels])
    staged = run(git, ["diff", "--cached", "--name-only"]).stdout.splitlines()
    if not staged:
        raise SystemExit("nothing staged after git add")
    return staged


def create_commit(git: str, root: Path, message: str) -> str:
    os.chdir(root)
    tree = run(git, ["write-tree"]).stdout.strip()
    head = run(git, ["rev-parse", "HEAD"], check=False)
    parents: list[str] = []
    if head.returncode == 0 and head.stdout.strip():
        parents = ["-p", head.stdout.strip()]

    env = os.environ.copy()
    env.pop("GIT_AUTHOR_DATE", None)
    env.pop("GIT_COMMITTER_DATE", None)
    env["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as handle:
        handle.write(message)
        msg_path = handle.name
    try:
        new = run(git, ["commit-tree", tree, *parents, "-F", msg_path], env=env).stdout.strip()
    finally:
        Path(msg_path).unlink(missing_ok=True)

    if not re.fullmatch(r"[0-9a-f]{40}", new):
        raise SystemExit(f"commit-tree did not return a SHA: {new!r}")
    run(git, ["update-ref", "HEAD", new])
    return new


def verify_head(git: str) -> None:
    author = run(git, ["log", "-1", "--format=%an <%ae>"]).stdout.strip()
    if author != AUTHOR:
        raise SystemExit(f"author mismatch: {author!r} != {AUTHOR!r}")
    body = run(git, ["log", "-1", "--format=%B"]).stdout
    if COAUTHOR_RE.search(body):
        raise SystemExit("HEAD message still contains Co-authored-by")
    subject = body.splitlines()[0] if body.splitlines() else ""
    print(f"OK {run(git, ['rev-parse', 'HEAD']).stdout.strip()}")
    print(f"AUTHOR {author}")
    print(f"SUBJECT {subject}")


def rewrite_clean_head(git: str, root: Path) -> str:
    """Rewrite current HEAD tree/message without Co-authored-by (unpushed only)."""
    os.chdir(root)
    ahead = run(
        git,
        ["rev-list", "--count", "@{upstream}..HEAD"],
        check=False,
    )
    if ahead.returncode != 0:
        print("warning: no upstream; proceeding with local rewrite", file=sys.stderr)
    elif ahead.stdout.strip() == "0":
        raise SystemExit("refusing rewrite: HEAD is not ahead of upstream (may be pushed)")

    tree = run(git, ["rev-parse", "HEAD^{tree}"]).stdout.strip()
    parent = run(git, ["rev-parse", "HEAD^"], check=False)
    parents: list[str] = []
    if parent.returncode == 0 and parent.stdout.strip():
        parents = ["-p", parent.stdout.strip()]
    body = run(git, ["log", "-1", "--format=%B"]).stdout
    cleaned = COAUTHOR_RE.sub("", body)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"
    cleaned = validate_message(cleaned)

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    env["GIT_AUTHOR_DATE"] = run(git, ["log", "-1", "--format=%aD"]).stdout.strip()
    env["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as handle:
        handle.write(cleaned)
        msg_path = handle.name
    try:
        new = run(git, ["commit-tree", tree, *parents, "-F", msg_path], env=env).stdout.strip()
    finally:
        Path(msg_path).unlink(missing_ok=True)
    run(git, ["update-ref", "HEAD", new])
    return new


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", "-m", help="commit subject/body (UTF-8)")
    parser.add_argument("--message-file", help="UTF-8 file containing commit message")
    parser.add_argument(
        "--rewrite-clean-head",
        action="store_true",
        help="rewrite current unpushed HEAD to drop Co-authored-by",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate inputs and print staged file plan without committing",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="paths to include (explicit only; never git add -A)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    git = find_git()
    root = repo_root(git)

    if args.rewrite_clean_head:
        sha = rewrite_clean_head(git, root)
        verify_head(git)
        print(f"rewrote HEAD to {sha}")
        return 0

    if bool(args.message) == bool(args.message_file):
        raise SystemExit("provide exactly one of --message or --message-file")
    if args.message_file:
        message = Path(args.message_file).read_text(encoding="utf-8")
    else:
        message = args.message or ""
    message = validate_message(message)

    if args.dry_run:
        rels = [normalize_rel(item, root) for item in args.files]
        for rel in rels:
            reason = denied(rel)
            if reason:
                raise SystemExit(f"refusing {rel}: {reason}")
        print("DRY_RUN message:")
        print(message, end="")
        print("DRY_RUN files:")
        for rel in rels:
            print(rel)
        return 0

    staged = stage_files(git, root, args.files)
    print("STAGED:")
    for rel in staged:
        print(rel)
    sha = create_commit(git, root, message)
    verify_head(git)
    print(f"committed {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
