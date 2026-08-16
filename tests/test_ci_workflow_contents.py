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


def test_ci_workflow_checks_backend_uv_lock_consistency():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    backend_job = workflow.split("\n  backend-full-pytest:", 1)[0].split(
        "\n  backend:", 1
    )[1]

    assert (
        "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"
        in backend_job
    )
    assert 'version: "0.11.32"' in backend_job
    assert "uv lock --check --project backend" in backend_job
    assert "continue-on-error:" not in backend_job
    assert backend_job.index("- name: Set up Python") < backend_job.index(
        "- name: Set up uv"
    )
    assert backend_job.index("- name: Set up uv") < backend_job.index(
        "- name: Check backend uv.lock consistency"
    )
    assert backend_job.index(
        "- name: Check backend uv.lock consistency"
    ) < backend_job.index("- name: Install backend dependencies")


def test_ci_workflow_uses_existing_agent_eval_targets():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "tests/test_agent_eval_runner.py" not in workflow
    assert "tests/test_agent_eval_spec.py" in workflow
    assert "tests/test_agent_eval_reward.py" in workflow


def test_ci_workflow_uses_repo_typecheck_entrypoint():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "npm run typecheck" in workflow
    assert "npx tsc --noEmit" not in workflow


def test_ci_workflow_targets_the_main_branch():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'branches: [main, "codex/**"]' in workflow
    assert "branches: [main]" in workflow
    assert "refs/heads/main" in workflow
    assert "master" not in workflow


def test_ci_workflow_runs_frontend_production_build():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "npm run build" in workflow
