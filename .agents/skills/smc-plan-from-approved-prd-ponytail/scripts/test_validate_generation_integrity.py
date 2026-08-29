import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate_generation_integrity.py")
SPEC = importlib.util.spec_from_file_location("validate_generation_integrity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def plan_text(include_second_grounding: bool = True) -> str:
    second = "| C02 | `b.py#g` | absent | new entry | `a.py#f -> b.py#g` | no reusable owner | PASS |\n" if include_second_grounding else ""
    return f"""---
grounded_commit: abc123
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

## Grounding Evidence Ledger
| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `a.py#f` | exists | resolved | `caller -> a.py#f` | existing owner | PASS |
{second}
## Contract / Data Flow Closure Matrix
None

## Change Matrix
| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `a.py#f` | PROD | MODIFY | A | T1 | changed | capability | no |
| C02 | `b.py#g` | PROD | ADD | B | T1 | added | capability | yes |

## Generated Outputs Ledger
None
"""


def test_accepts_complete_integrity_sections() -> None:
    assert MODULE.validate(plan_text()) == []


def test_rejects_missing_grounding_change() -> None:
    errors = MODULE.validate(plan_text(include_second_grounding=False))
    assert any(error.code == "PLAN_GROUNDING_CHANGE_MISSING" for error in errors)


def test_rejects_missing_integrity_section() -> None:
    errors = MODULE.validate(plan_text().replace("## Generated Outputs Ledger\nNone\n", ""))
    assert any(error.code == "PLAN_GENERATED_OUTPUTS_LEDGER_MISSING" for error in errors)


def test_rejects_non_pass_grounding_result() -> None:
    errors = MODULE.validate(plan_text().replace("existing owner | PASS", "existing owner | FAIL"))
    assert any(error.code == "PLAN_GROUNDING_RESULT_INVALID" for error in errors)


def test_rejects_existing_target_missing_at_baseline() -> None:
    errors = MODULE.validate(plan_text(), baseline_reader=lambda commit, path: None)
    assert any(error.code == "GROUNDING_TARGET_NOT_FOUND" for error in errors)


def test_rejects_symbol_missing_at_baseline() -> None:
    def baseline_reader(commit: str, path: str) -> str | None:
        if path == "a.py":
            return "def other():\n    pass\n"
        return None

    errors = MODULE.validate(plan_text(), baseline_reader=baseline_reader)
    assert any(error.code == "GROUNDING_SYMBOL_NOT_FOUND" for error in errors)


def test_rejects_symbol_that_is_only_referenced() -> None:
    def baseline_reader(commit: str, path: str) -> str | None:
        if path == "a.py":
            return "def other():\n    return f()\n"
        return None

    errors = MODULE.validate(plan_text(), baseline_reader=baseline_reader)
    assert any(error.code == "GROUNDING_SYMBOL_NOT_FOUND" for error in errors)


def test_resolves_python_class_method() -> None:
    text = plan_text().replace("a.py#f", "a.py#Owner#f")

    def baseline_reader(commit: str, path: str) -> str | None:
        if path == "a.py":
            return "class Owner:\n    def f(self):\n        return None\n"
        return None

    errors = MODULE.validate(text, baseline_reader=baseline_reader)
    assert not any(error.code == "GROUNDING_SYMBOL_NOT_FOUND" for error in errors)


def test_rejects_add_target_that_exists_at_baseline() -> None:
    def baseline_reader(commit: str, path: str) -> str | None:
        if path == "a.py":
            return "def f():\n    return None\n"
        if path == "b.py":
            return "def g():\n    return None\n"
        return None

    errors = MODULE.validate(plan_text(), baseline_reader=baseline_reader)
    assert any(error.code == "PLAN_NEW_TARGET_ALREADY_EXISTS" for error in errors)


def test_rejects_invalid_grounded_commit() -> None:
    errors = MODULE.validate(
        plan_text(),
        baseline_reader=lambda commit, path: None,
        commit_exists=lambda commit: False,
    )
    assert any(error.code == "GROUNDING_COMMIT_INVALID" for error in errors)


def test_rejects_working_tree_without_fingerprint() -> None:
    text = plan_text().replace("grounding_source: committed_baseline", "grounding_source: working_tree").replace("working_tree_fingerprint: clean", "working_tree_fingerprint: <GROUND>")
    errors = MODULE.validate(text)
    assert any(error.code == "GROUNDING_WORKTREE_FINGERPRINT_INVALID" for error in errors)
