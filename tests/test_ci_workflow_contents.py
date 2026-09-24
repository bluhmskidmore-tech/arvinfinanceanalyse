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
