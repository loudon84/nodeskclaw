from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_agent_skills.py"
spec = importlib.util.spec_from_file_location("validate_agent_skills", SCRIPT)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


class ValidateAgentSkillsTest(unittest.TestCase):
    def test_root_relative_documentation_link_is_not_local_asset(self) -> None:
        source = validator.SKILLS / "writing-skills" / "anthropic-best-practices.md"
        self.assertIsNone(
            validator.resolve_local_link(source, "/en/docs/agents-and-tools/agent-skills/overview")
        )

    def test_tree_ignores_python_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text("skill", encoding="utf-8")
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "validator.cpython-312.pyc").write_bytes(b"bytecode")
            self.assertEqual(validator.tree(root), {"SKILL.md": b"skill"})

    def test_local_link_checks_are_limited_to_governed_skills_and_contracts(self) -> None:
        self.assertTrue(validator.should_validate_local_links(validator.SKILLS / "smc-roadmap" / "SKILL.md"))
        self.assertFalse(validator.should_validate_local_links(validator.SKILLS / "chinese-documentation" / "SKILL.md"))
        self.assertTrue(validator.should_validate_local_links(validator.REFERENCES / "prd-contract.md"))


if __name__ == "__main__":
    unittest.main()
