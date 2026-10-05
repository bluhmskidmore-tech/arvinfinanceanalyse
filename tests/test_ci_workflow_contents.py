import json
import re
import textwrap
from pathlib import Path

import pytest

from scripts import backend_release_suite

ROOT = Path(__file__).resolve().parents[1]


def _pytest_test_targets(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"tests/test_[a-z0-9_]+\.py", text))


def _workflow_step(workflow: str, step_name: str) -> str:
    return workflow.split(f"\n      - name: {step_name}", 1)[1].split(
        "\n      - name:", 1
    )[0]


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


def test_ci_workflow_has_release_control_structure_only_job():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  agent-eval-replay:", 1)[0].split(
        "\n  release-control-structure:", 1
    )[1]

    assert "name: Release Control Structure (not approval)" in job
    assert "python scripts/check_release_approval_registry.py" in job
    assert "--execute-evidence" not in job
    assert "structure-only.json" in job
    assert 'assert payload["structure_only"] is True, payload' in job
    assert 'assert payload["gate_scope"] == "structure_only", payload' in job
    assert 'assert payload["approval_decision"] == "not_evaluated", payload' in job
    assert 'assert payload["release_gate_eligible"] is False, payload' in job


def test_ci_workflow_release_control_structure_job_runs_only_structural_suite():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  agent-eval-replay:", 1)[0].split(
        "\n  release-control-structure:", 1
    )[1]

    assert "tests/test_release_control_schema.py" in job
    assert "tests/test_release_control_state_machine.py" in job
    assert "tests/test_release_control_repo.py" in job
    assert "tests/test_release_control_cli.py" in job
    assert "tests/test_release_approval_registry.py" in job
    assert "tests/test_bond_risk_shadow_candidate.py" in job
    assert "tests/test_fixed_income_version_set.py" in job
    assert "tests/test_bond_risk_shadow_batch.py" in job
    assert "tests/test_release_approval_evidence_gate.py" not in job


def test_ci_release_control_job_requires_real_postgres_cas_concurrency_proof():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  agent-eval-replay:", 1)[0].split(
        "\n  release-control-structure:", 1
    )[1]

    assert "image: postgres:16" in job
    assert "POSTGRES_HOST_AUTH_METHOD: trust" in job
    assert "POSTGRES_PASSWORD" not in job
    assert "POSTGRES_DB: moss_release_control_test" in job
    assert (
        "MOSS_TEST_POSTGRES_DSN: "
        "postgresql+psycopg://moss_test@127.0.0.1:5432/"
        "moss_release_control_test"
    ) in job
    assert 'MOSS_REQUIRE_POSTGRES_CONCURRENCY_TEST: "1"' in job
    assert "python -m alembic -c backend/alembic.ini upgrade head" in job
    assert "tests/test_release_control_postgres_concurrency.py" in job
    assert "postgres-cas-junit.xml" in job
    assert 'for key in ("tests", "failures", "errors", "skipped")' in job
    assert '"tests": 2' in job
    assert '"skipped": 0' in job
    assert "production" not in job.lower()


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


def test_agent_harness_documentation_matches_ci_step_targets():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    documentation = (ROOT / "docs" / "ci-release-suite.md").read_text(encoding="utf-8")
    documented_harness = documentation.split("agent harness +", 1)[1].split("；", 1)[0]

    assert _pytest_test_targets(documented_harness) == _pytest_test_targets(
        _workflow_step(workflow, "Run agent harness tests")
    )


def test_release_suite_documentation_has_no_missing_or_stale_test_targets():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    documentation = (ROOT / "docs" / "ci-release-suite.md").read_text(encoding="utf-8")
    suite_targets = {
        *backend_release_suite.RELEASE_SUITE_TESTS,
        *backend_release_suite.GOVERNANCE_MCP_FAST_SUITE_TESTS,
        *backend_release_suite.GOVERNANCE_MCP_FULL_SUITE_TESTS,
    }
    harness_targets = set(
        _pytest_test_targets(_workflow_step(workflow, "Run agent harness tests"))
    )
    documented_targets = set(_pytest_test_targets(documentation))

    assert not suite_targets - documented_targets
    assert not documented_targets - suite_targets - harness_targets


def test_ci_workflow_runs_its_configuration_and_path_gate_checks():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    backend_job = workflow.split("\n  backend-caliber:", 1)[0].split(
        "\n  backend:", 1
    )[1]
    caliber_job = workflow.split("\n  backend-caliber:", 1)[1].split(
        "\n  release-control-structure:", 1
    )[0]

    assert "tests/test_ci_workflow_contents.py" in backend_job
    assert "tests/test_caliber_gate_mapping.py" in backend_job
    assert "scripts/check_caliber_gate.py" not in backend_job
    assert "timeout-minutes: 20" in backend_job
    assert "if: github.event_name == 'pull_request'" in caliber_job
    assert "timeout-minutes: 20" in caliber_job
    assert "needs:" not in caliber_job
    assert "continue-on-error:" not in caliber_job
    assert "fetch-depth: 0" in caliber_job
    assert "uv lock --check --project backend" in caliber_job
    assert "uv sync --frozen --project backend --extra dev --python 3.11" in caliber_job
    assert 'git fetch origin "${{ github.base_ref }}"' in caliber_job
    assert 'python scripts/check_caliber_gate.py --base-ref "origin/${{ github.base_ref }}"' in caliber_job
    assert '--base-ref "origin/${{ github.base_ref }}" --dry-run > .codex-tmp/caliber-selection.json' in caliber_job
    assert "- name: Report caliber selection scope\n        if: always()" in caliber_job
    assert "html.escape(path)" in caliber_job
    assert "Selection report unavailable or invalid:" in caliber_job
    assert "this selection report does not record that job or any test result" in caliber_job


@pytest.mark.parametrize("report_content", [None, "{bad-json", '{"mapped_files": null}', '{"mapped_files": [], "unmapped_files": [], "matched_tests": [], "selection_scope": 42, "selection_note": "note"}'])
def test_caliber_ci_summary_discloses_missing_or_invalid_report(tmp_path, monkeypatch, report_content):
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    step = _workflow_step(workflow, "Report caliber selection scope")
    source = textwrap.dedent(step.split("python - <<'PY'\n", 1)[1].rsplit("          PY", 1)[0])
    monkeypatch.chdir(tmp_path)
    summary = tmp_path / "summary.md"
    summary.write_text("Original gate failed.\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    if report_content is not None:
        (tmp_path / ".codex-tmp").mkdir()
        (tmp_path / ".codex-tmp/caliber-selection.json").write_text(report_content, encoding="utf-8")
    exec(compile(source, "<caliber-ci-summary>", "exec"), {})
    output = summary.read_text(encoding="utf-8")
    assert output.startswith("Original gate failed.\n")
    assert "Selection report unavailable or invalid:" in output
    assert "No empty-selection or coverage conclusion can be drawn" in output
    assert "Paths not mapped by this gate: 0" not in output


def test_caliber_ci_summary_escapes_paths_and_keeps_selection_distinct_from_execution(tmp_path, monkeypatch):
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    step = _workflow_step(workflow, "Report caliber selection scope")
    source = textwrap.dedent(step.split("python - <<'PY'\n", 1)[1].rsplit("          PY", 1)[0])
    monkeypatch.chdir(tmp_path)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    (tmp_path / ".codex-tmp").mkdir()
    report = {
        "mapped_files": ["backend/app/mapped.py"],
        "unmapped_files": ["backend/app/<script>&unknown.py"],
        "matched_tests": ["tests/test_mapped.py"],
        "selection_scope": "Registered financial scope only.",
        "selection_note": "Unmapped does not mean untested or verified.",
    }
    (tmp_path / ".codex-tmp/caliber-selection.json").write_text(json.dumps(report), encoding="utf-8")
    exec(compile(source, "<caliber-ci-summary>", "exec"), {})
    output = summary.read_text(encoding="utf-8")
    assert "Paths not mapped by this gate: 1" in output
    assert "<code>backend/app/&lt;script&gt;&amp;unknown.py</code>" in output
    assert "<script>" not in output
    assert "Unmapped does not mean untested or verified" in output
    assert "this selection report does not record that job or any test result" in output


def test_ci_workflow_uses_repo_typecheck_entrypoint():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "npm run typecheck" in workflow
    assert "npx tsc --noEmit" not in workflow


def test_ci_workflow_keeps_main_pr_and_codex_push_checks():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'branches: [main, "codex/**"]' in workflow
    assert 'pull_request:\n    branches: [main]' in workflow
    assert 'pull_request:\n    branches: [main, "codex/V1"]' not in workflow
    assert "tests/test_ci_workflow_contents.py" in workflow
    assert "refs/heads/main" in workflow
    assert "master" not in workflow


def test_caliber_pr_workflow_always_checks_map_before_merge_diff_gate():
    workflow = (
        ROOT / ".github" / "workflows" / "caliber-pr-gate.yml"
    ).read_text(encoding="utf-8")

    assert 'pull_request:\n    branches: ["codex/V1"]' in workflow
    assert "pull_request_target:" not in workflow
    assert "\n  push:" not in workflow
    assert "fetch-depth: 0" in workflow
    assert 'git fetch origin "${{ github.base_ref }}"' in workflow
    assert "uv sync --frozen --project backend --extra dev --python 3.11" in workflow
    assert "--dry-run" not in workflow
    unconditional_gate = workflow.split("\n      - name: Select formal release suite", 1)[0]
    assert "\n        if:" not in unconditional_gate
    guard_command = (
        "backend/.venv/bin/python -m pytest -q "
        "tests/test_caliber_gate_mapping.py tests/test_ci_workflow_contents.py"
    )
    assert guard_command in workflow
    gate_command = (
        'backend/.venv/bin/python scripts/check_caliber_gate.py '
        '--base-ref "origin/${{ github.base_ref }}"'
    )
    assert gate_command in workflow
    assert workflow.index("uv sync --frozen") < workflow.index(guard_command)
    assert workflow.index(guard_command) < workflow.index(gate_command)


def test_v1_pr_formal_scope_runs_canonical_release_suite_when_selected() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "caliber-pr-gate.yml"
    ).read_text(encoding="utf-8")
    caliber_job = workflow.split("\n  frontend-pr-slice:", 1)[0]

    assert '--base-ref "origin/$BASE_REF" --release-scope' in caliber_job
    assert 'selected="$(backend/.venv/bin/python scripts/check_caliber_gate.py' in caliber_job
    assert "if: steps.release_scope.outputs.selected == 'true'" in caliber_job
    assert "backend/.venv/bin/python scripts/backend_release_suite.py" in caliber_job
    assert "continue-on-error:" not in caliber_job


def test_v1_pr_scheduler_uses_windows_when_a_script_or_test_changes() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "caliber-pr-gate.yml"
    ).read_text(encoding="utf-8")
    selector = workflow.split("\n  caliber-pr-gate:", 1)[1].split(
        "\n  scheduler-windows:", 1
    )[0]
    windows_job = workflow.split("\n  scheduler-windows:", 1)[1].split(
        "\n  frontend-pr-slice:", 1
    )[0]

    assert "scheduler_scope: ${{ steps.scheduler_scope.outputs.selected }}" in selector
    assert '--base-ref "origin/$BASE_REF" --scheduler-scope' in selector
    assert "needs: caliber-pr-gate" in windows_job
    assert "if: always() && needs.caliber-pr-gate.outputs.scheduler_scope == 'true'" in windows_job
    assert "runs-on: windows-latest" in windows_job
    assert 'python -m pip install "pytest==9.0.3"' in windows_job
    assert "shutil.which('powershell.exe')" in windows_job
    assert "python -m pytest --noconftest -q" in windows_job
    assert "tests/test_data_update_queue_launcher_logging.py" in windows_job
    assert "tests/test_install_data_update_queue.py" in windows_job
    assert "continue-on-error:" not in windows_job


def test_v1_pr_frontend_slice_uses_fail_closed_path_selection() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "caliber-pr-gate.yml"
    ).read_text(encoding="utf-8")
    frontend_job = workflow.split("\n  frontend-pr-slice:", 1)[1].split(
        "\n  agent-eval-replay:", 1
    )[0]

    assert 'git fetch origin "$BASE_REF"' in frontend_job
    assert '--base-ref "origin/$BASE_REF" --frontend-scope' in frontend_job
    assert 'selected="$(python scripts/check_caliber_gate.py' in frontend_job
    assert 'echo "selected=$selected" >> "$GITHUB_OUTPUT"' in frontend_job
    assert frontend_job.count(
        "if: steps.frontend_scope.outputs.selected == 'true'"
    ) == 8
    assert "npm ci" in frontend_job
    assert "npm run typecheck" in frontend_job
    assert "npm run test --" in frontend_job
    assert "dataUpdatesClient" in frontend_job
    assert "BalanceAnalysisPage" in frontend_job
    assert "--no-file-parallelism" in frontend_job
    assert "Run balance analysis page contract" in frontend_job
    assert "Run balance movement request boundary" in frontend_job
    assert "VITE_DATA_SOURCE=real npm run build" in frontend_job
    assert "continue-on-error:" not in frontend_job


def test_v1_pr_browser_contract_installs_chromium_only_for_daily_balance_paths() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "caliber-pr-gate.yml"
    ).read_text(encoding="utf-8")
    frontend_job = workflow.split("\n  frontend-pr-slice:", 1)[1].split(
        "\n  agent-eval-replay:", 1
    )[0]

    assert '--base-ref "origin/$BASE_REF" --data-update-browser-scope' in frontend_job
    assert frontend_job.count(
        "if: steps.data_update_browser_scope.outputs.selected == 'true'"
    ) == 2
    assert "npx playwright install --with-deps chromium" in frontend_job
    assert "tests/playwright/data-update-center-balance-daily.spec.mjs" in frontend_job
    assert 'MOSS_PLAYWRIGHT_USE_WEB_SERVER: "1"' in frontend_job
    assert "--workers=1 --retries=0" in frontend_job
    assert "Upload daily-balance browser evidence" in frontend_job
    assert "continue-on-error:" not in frontend_job


def test_v1_pr_agent_eval_replay_preserves_preflight_and_archive() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "caliber-pr-gate.yml"
    ).read_text(encoding="utf-8")
    eval_job = workflow.split("\n  agent-eval-replay:", 1)[1]

    assert 'python scripts/agent_eval/pr_replay.py --base-ref "origin/${{ github.base_ref }}"' in eval_job
    assert '--preflight >> "$GITHUB_OUTPUT"' in eval_job
    assert eval_job.count(
        "if: steps.agent_eval_preflight.outputs.needs_dependency_setup != 'false'"
    ) == 5
    assert "--out-md .codex-tmp/agent-eval/pr-replay/summary.md" in eval_job
    assert "Publish step summary" in eval_job
    assert "actions/upload-artifact@v4" in eval_job
    assert "continue-on-error:" not in eval_job


def test_ci_workflow_runs_frontend_production_build():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "npm run build" in workflow


def test_mypy_identity_gate_blocks_regressions_and_tests_the_checker():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  mypy-ratchet:", 1)[1].split("\n  frontend:", 1)[0]

    assert "continue-on-error:" not in job
    assert "tests/test_check_mypy_baseline.py" in job
    assert "tests/test_backend_debt_gate.py" in job
    assert "tests/test_mypy_import_boundary.py" in job
    assert "python -m pytest -p _pytest_duckdb_guard -q" in job
    assert "python scripts/check_mypy_baseline.py" in job
    assert "--update-baseline" not in job


def test_frontend_checks_keep_reporting_after_an_independent_check_fails():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  frontend-a11y-smoke-shard:", 1)[0].split(
        "\n  frontend:", 1
    )[1]

    assert (
        "- name: Install dependencies\n"
        "        id: frontend_dependencies\n"
        "        run: npm ci"
    ) in job
    assert "continue-on-error:" not in job
    for name, command in {
        "TypeScript type check": "npm run typecheck",
        "Frontend debt audit": "npm run debt:audit",
        "Production build": "VITE_DATA_SOURCE=real npm run build",
    }.items():
        assert (
            f"- name: {name}\n"
            "        if: ${{ !cancelled() && "
            "steps.frontend_dependencies.outcome == 'success' }}\n"
            f"        run: {command}\n"
        ) in job, name
    assert (
        "- name: Run Vitest\n"
        "        if: ${{ !cancelled() && steps.frontend_dependencies.outcome == 'success' }}\n"
        "        run: |\n"
    ) in job
    assert '"${{ github.event_name }}" = "schedule"' in job
    assert '"${{ github.ref }}" = "refs/heads/main"' in job
    assert "npm test -- --coverage" in job
    assert "            npm test\n" in job
    assert "path: frontend/coverage/" in job
