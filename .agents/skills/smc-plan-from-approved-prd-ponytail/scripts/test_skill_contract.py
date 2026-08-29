from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SKILL = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")


def test_description_is_trigger_only() -> None:
    description = next(line for line in SKILL.splitlines() if line.startswith("description:"))
    assert description.startswith("description: Use when ")
    assert "最后交给" not in description
    assert "auditing" in description


def test_audit_mode_is_read_only_and_precedes_generation() -> None:
    mode_gate = SKILL.index("## Mode Gate")
    approved_gate = SKILL.index("## Gate 0 — APPROVED PRD")
    assert mode_gate < approved_gate
    assert "`AUDIT`" in SKILL
    assert "禁止读取、生成、修改、验证或执行任何 Plan" in SKILL
    assert "读取 PRD 或 Plan 前" in SKILL
    assert "后续 Gate 0 至 Exit 仅适用于 `CREATE` / `REVISE`" in SKILL
    assert "### AUDIT Exit" in SKILL


def test_revision_requires_explicit_authorization() -> None:
    assert "`REVISE`" in SKILL
    assert "PLAN_ALREADY_EXISTS" in SKILL
    assert "不得使用 `--force`" in SKILL


def test_ponytail_core_order_is_preserved() -> None:
    grounding = SKILL.index("## Gate 1 — Implementation Grounding")
    minimality = SKILL.index("## Gate 2 — Ponytail Minimality Decision")
    ownership = SKILL.index("## Gate 4 — 先建立写所有权，再切 Todo")
    slicing = SKILL.index("## Gate 10 — Todo Slice")
    assert grounding < minimality < ownership < slicing
    assert "`Cnn.m`" in SKILL


def test_grounding_requires_resolvable_evidence() -> None:
    assert "Grounding Evidence Ledger" in SKILL
    assert "GROUNDING_TARGET_NOT_FOUND" in SKILL
    assert "VERIFICATION_COMMAND_INVALID" in SKILL


def test_cross_boundary_changes_require_closure() -> None:
    assert "Contract / Data Flow Closure Matrix" in SKILL
    assert "CROSS_BOUNDARY_SOURCE_MISSING" in SKILL


def test_semantic_review_assessment_is_an_execution_gate() -> None:
    integrity = SKILL.index("validate_generation_integrity.py")
    validator = SKILL.index("validate_plan.py")
    assert integrity < validator
    assert "assess_plan_review.py" in SKILL
    assert "SEMANTIC_REVIEW_REQUIRED" in SKILL
    assert "smc-plan-review" in SKILL
    assert "Contract / Data Flow Closure Matrix` 不是 `None`" in SKILL


def test_source_basis_is_required_reading() -> None:
    required = SKILL[SKILL.index("## 必读 references") : SKILL.index("## Mode Gate")]
    assert "references/source-basis.md" in required
