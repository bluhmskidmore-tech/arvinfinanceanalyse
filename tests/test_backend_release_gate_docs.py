from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_release_gate_is_documented_as_canonical_backend_gate():
    authority = (ROOT / "docs" / "DOCUMENT_AUTHORITY.md").read_text(encoding="utf-8")
    cutoff = (ROOT / "docs" / "V3_CUTOFF_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "docs" / "acceptance_tests.md").read_text(encoding="utf-8")
    cutover = (ROOT / "docs" / "REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md").read_text(encoding="utf-8")
    boundary = (ROOT / "docs" / "CURRENT_BOUNDARY_HANDOFF_2026-04-10.md").read_text(encoding="utf-8")
    go_live = (ROOT / "docs" / "GOVERNED_PHASE2_GO_LIVE_CHECKLIST.md").read_text(encoding="utf-8")

    expected = "python scripts/backend_release_suite.py"

    assert expected in authority
    assert expected in cutoff
    assert expected in acceptance
    assert expected in cutover
    assert expected in boundary
    assert expected in go_live


def test_repo_wide_cutover_doc_no_longer_claims_full_backend_pytest_is_green():
    cutover = (ROOT / "docs" / "REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md").read_text(encoding="utf-8")
    assert "backend `pytest tests -q` is green" not in cutover


def test_boundary_handoff_no_longer_uses_pytest_tests_q_as_current_backend_gate():
    boundary = (ROOT / "docs" / "CURRENT_BOUNDARY_HANDOFF_2026-04-10.md").read_text(encoding="utf-8")
    assert "pytest tests -q" not in boundary


def test_go_live_checklist_no_longer_uses_full_pytest_as_hard_gate():
    go_live = (ROOT / "docs" / "GOVERNED_PHASE2_GO_LIVE_CHECKLIST.md").read_text(encoding="utf-8")
    assert "python -m pytest tests -q" not in go_live
    assert "python scripts/backend_release_suite.py" in go_live


def test_cutoff_declaration_template_exists_and_uses_canonical_backend_gate():
    template = (ROOT / "docs" / "V3_CUTOFF_DECLARATION_TEMPLATE.md").read_text(encoding="utf-8")
    assert "python scripts/backend_release_suite.py" in template
    assert "executive-consumer cutover v1" in template
    assert "excluded surfaces remain excluded" in template


def test_current_cutoff_declaration_records_live_preflight_blocker():
    declaration = (ROOT / "docs" / "V3_CUTOFF_DECLARATION_2026-04-17.md").read_text(encoding="utf-8")
    cutoff = (ROOT / "docs" / "V3_CUTOFF_EXIT_CRITERIA.md").read_text(encoding="utf-8")

    assert "python scripts/backend_release_suite.py" in declaration
    assert "python scripts/governed_phase2_preflight.py" in declaration
    assert "release decision: `GO`" in declaration
    assert "/ui/risk/overview" in declaration
    assert "/api/cube/dimensions/bond_analytics" in declaration
    assert "current repo status: `accepted at cutoff for the included scope`" in cutoff
    assert "docs/V3_CUTOFF_DECLARATION_2026-04-17.md" in cutoff
