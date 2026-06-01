#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_RELEASE_URL = "https://github.com/NoDeskAI/nodeskclaw/releases"


def check_release_links() -> list[str]:
    errors: list[str] = []
    for rel_path in ("README.md", "README.zh-CN.md"):
        content = (ROOT / rel_path).read_text(encoding="utf-8")
        if EXPECTED_RELEASE_URL not in content:
            errors.append(f"{rel_path}: GitHub Releases 链接不是 {EXPECTED_RELEASE_URL}")
    return errors


def check_portal_readme_versions() -> list[str]:
    errors: list[str] = []
    readme = (ROOT / "nodeskclaw-portal/README.md").read_text(encoding="utf-8")
    package = json.loads((ROOT / "nodeskclaw-portal/package.json").read_text(encoding="utf-8"))

    expected = {
        "Vue": package["dependencies"]["vue"].lstrip("^"),
        "Vite": package["devDependencies"]["vite"].lstrip("^"),
        "TypeScript": package["devDependencies"]["typescript"].lstrip("~^"),
        "Tailwind CSS": package["devDependencies"]["tailwindcss"].lstrip("^"),
        "Pinia": package["dependencies"]["pinia"].lstrip("^"),
        "vue-i18n": package["dependencies"]["vue-i18n"].lstrip("^"),
        "lucide-vue-next": package["dependencies"]["lucide-vue-next"].lstrip("^"),
    }

    for dep, version in expected.items():
        pattern = rf"\|\s*{re.escape(dep)}\s*\|\s*{re.escape(version)}\s*\|"
        if not re.search(pattern, readme):
            errors.append(f"nodeskclaw-portal/README.md: {dep} 版本未同步为 {version}")
    return errors


def main() -> int:
    errors = [*check_release_links(), *check_portal_readme_versions()]
    if errors:
        for error in errors:
            print(error)
        return 1
    print("docs consistency check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
