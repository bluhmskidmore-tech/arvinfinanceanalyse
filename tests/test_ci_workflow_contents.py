from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_default_release_suite_does_not_read_live_governance():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@v4" in workflow
    assert "python scripts/backend_release_suite.py" in workflow
    assert "governance-lineage-audit.json" not in workflow
    assert "--live-governance-dir" not in workflow
    assert "python scripts/audit_governance_lineage.py --governance-dir data/governance > governance-lineage-audit.json" not in workflow


def test_ci_workflow_uses_bounded_backend_release_suite():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python scripts/backend_release_suite.py" in workflow
    assert "pytest tests/ -x -q --tb=short" not in workflow


def test_ci_workflow_targets_the_main_branch():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'branches: [main, "codex/**"]' in workflow
    assert "branches: [main]" in workflow
    assert "refs/heads/main" in workflow
    assert "master" not in workflow


def test_ci_workflow_runs_frontend_production_build():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "npm run build" in workflow
