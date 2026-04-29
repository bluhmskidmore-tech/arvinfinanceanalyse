from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_runs_governance_lineage_audit():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@v4" in workflow
    assert "governance-lineage-audit.json" in workflow
    assert "python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json" in workflow
    assert "python scripts/audit_governance_lineage.py --governance-dir data/governance > governance-lineage-audit.json" not in workflow


def test_ci_workflow_uses_bounded_backend_release_suite():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json" in workflow
    assert "pytest tests/ -x -q --tb=short" not in workflow


def test_ci_workflow_keeps_frontend_quality_gates():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "npx tsc --noEmit" in workflow
    assert "npx vitest run" in workflow
    assert "npm run debt:audit" in workflow
    assert "node scripts/check_surface_naming.mjs" in workflow
    assert "npx eslint ." in workflow
