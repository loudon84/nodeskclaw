#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import stat
from pathlib import Path

from common import find_repo_root, git

DEFAULT_EXCLUDES = (".smc/", "docs_agent/evidence/")


def should_exclude(rel: str, excludes: tuple[str, ...]) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel == x.rstrip("/") or rel.startswith(x.rstrip("/") + "/") for x in excludes)


def fingerprint(root: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES) -> str:
    result = git(root, "ls-files", "-co", "--exclude-standard", "-z", text=False)
    raw = result.stdout
    paths = sorted({p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p})
    digest = hashlib.sha256()
    for rel in paths:
        rel_norm = rel.replace("\\", "/")
        if should_exclude(rel_norm, excludes):
            continue
        path = root / rel
        digest.update(rel_norm.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        if not path.exists() and not path.is_symlink():
            digest.update(b"<DELETED>\0")
            continue
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            digest.update(b"L\0")
            digest.update(os.readlink(path).encode("utf-8", "surrogateescape"))
        elif stat.S_ISREG(st.st_mode):
            digest.update(b"F+x\0" if (st.st_mode & stat.S_IXUSR) else b"F\0")
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"O\0")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args()
    root = find_repo_root(Path(args.path))
    excludes = tuple(DEFAULT_EXCLUDES) + tuple(args.exclude)
    print(fingerprint(root, excludes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
