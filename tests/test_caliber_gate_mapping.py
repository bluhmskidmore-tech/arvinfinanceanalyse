"""Guard tests for the caliber path-trigger gate (scripts/check_caliber_gate.py).

Covers three surfaces:

1. ``CALIBER_GATE_MAP`` integrity: every mapped source and test path exists,
   and the map covers every ``tests/test_caliber_rule_*.py`` file on disk (so
   a future caliber test cannot silently stay outside the gate).
2. Pure matching semantics of ``resolve_required_tests`` (exact path, prefix,
   dedup, deterministic ordering).
3. CLI + git diff behavior against a temporary git repository with an
   injected small gate map: mapped change -> matched tests in dry-run JSON,
   unrelated change -> empty match, invalid base ref -> fail-closed non-zero
   exit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import check_caliber_gate as gate

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CALIBER_TESTS = {
    "tests/test_caliber_rule_accounting_basis.py",
    "tests/test_caliber_rule_formal_scenario_gate.py",
    "tests/test_caliber_rule_fx_mid_conversion.py",
    "tests/test_caliber_rule_hat_mapping.py",
    "tests/test_caliber_rule_issuance_exclusion.py",
    "tests/test_caliber_rule_subject_514_516_517_merge.py",
}


def test_every_mapped_source_path_exists_in_repo() -> None:
    for source in gate.CALIBER_GATE_MAP:
        target = REPO_ROOT / source
        if source.endswith("/"):
            assert target.is_dir(), f"mapped prefix does not exist: {source}"
        else:
            assert target.is_file(), f"mapped source file does not exist: {source}"


def test_map_covers_every_caliber_rule_test_file() -> None:
    mapped_tests = {
        test_file
        for test_files in gate.CALIBER_GATE_MAP.values()
        for test_file in test_files
    }
    on_disk = {
        f"tests/{path.name}"
        for path in (REPO_ROOT / "tests").glob("test_caliber_rule_*.py")
    }
    # Guard the guard: the six known red-line tests must be on disk, so the
    # coverage assertion below cannot pass vacuously against an empty glob.
    assert EXPECTED_CALIBER_TESTS <= on_disk
    assert on_disk <= mapped_tests, (
        "CALIBER_GATE_MAP must cover every caliber rule test on disk; "
        "update scripts/check_caliber_gate.py when adding a caliber test"
    )
    for test_file in mapped_tests:
        assert (REPO_ROOT / test_file).is_file(), (
            f"mapped test does not exist: {test_file}"
        )


def test_curve_and_pnl_bridge_source_changes_select_existing_goldens() -> None:
    assert gate.resolve_required_tests(
        ["backend/app/core_finance/curve_engine/interpolation.py"]
    ) == ["tests/test_curve_engine_golden.py", "tests/test_pnl_bridge_golden.py"]
    assert gate.resolve_required_tests(
        ["backend/app/core_finance/pnl_bridge.py"]
    ) == [
        "tests/test_pnl_bridge_golden.py",
        "tests/test_pnl_bridge_modified_duration.py",
    ]


def test_data_update_and_balance_paths_select_first_scope_regressions() -> None:
    assert gate.resolve_required_tests(
        ["backend/app/services/data_health_service.py"]
    ) == [
        "tests/test_data_health.py",
        "tests/test_data_health_schtasks_query.py",
        "tests/test_data_updates.py",
    ]
    assert gate.resolve_required_tests(
        ["tests/test_data_health_schtasks_query.py"]
    ) == ["tests/test_data_health_schtasks_query.py"]
    assert gate.resolve_required_tests(
        ["backend/app/api/routes/balance_analysis.py"]
    ) == ["tests/test_balance_analysis_api.py"]
    assert gate.resolve_required_tests(
        ["docs/unrelated-note.md"]
    ) == []


@pytest.mark.parametrize(
    "source",
    [
        "backend/app/api/__init__.py",
        "backend/app/api/routes/data_updates.py",
        "backend/app/repositories/data_update_repo.py",
        "backend/app/schemas/data_updates.py",
        "backend/app/services/data_update_service.py",
        "backend/app/tasks/data_update_center.py",
    ],
)
def test_data_update_source_selects_same_date_integration(source: str) -> None:
    assert gate.resolve_required_tests([source]) == [
        "tests/test_data_update_balance_integration.py",
        "tests/test_data_updates.py",
    ]


def test_queue_scheduler_and_test_changes_select_focused_regressions() -> None:
    assert gate.resolve_required_tests(
        ["scripts/scheduling/drain_data_updates.ps1"]
    ) == [
        "tests/test_data_update_queue_launcher_logging.py",
        "tests/test_install_data_update_queue.py",
    ]
    assert gate.resolve_required_tests(
        ["scripts/scheduling/install_data_update_queue.ps1"]
    ) == ["tests/test_install_data_update_queue.py"]
    for test_file in (
        "tests/test_data_update_balance_integration.py",
        "tests/test_data_update_queue_launcher_logging.py",
        "tests/test_install_data_update_queue.py",
    ):
        assert gate.resolve_required_tests([test_file]) == [test_file]
    assert gate.resolve_required_tests(["scripts/scheduling/unrelated.ps1"]) == []


def test_windows_scheduler_scope_is_limited_to_two_scripts_and_tests() -> None:
    assert gate.selects_scheduler_windows_scope(
        ["scripts/scheduling/drain_data_updates.ps1"]
    )
    assert gate.selects_scheduler_windows_scope(
        ["tests/test_install_data_update_queue.py"]
    )
    assert not gate.selects_scheduler_windows_scope(
        ["backend/app/tasks/data_update_center.py", "docs/note.md"]
    )


def test_frontend_first_scope_selection_is_bounded() -> None:
    assert gate.selects_frontend_first_scope(
        ["frontend/src/api/dataUpdatesClient.ts"]
    )
    assert gate.selects_frontend_first_scope(
        ["frontend\\src\\features\\balance-analysis\\pages\\BalanceAnalysisPage.tsx"]
    )
    assert not gate.selects_frontend_first_scope(
        ["frontend/src/features/risk-tensor/RiskTensorPage.tsx", "docs/note.md"]
    )


def test_data_update_browser_scope_only_selects_the_daily_balance_path() -> None:
    assert set(gate.DATA_UPDATE_BROWSER_PATHS) <= set(gate.FRONTEND_FIRST_SCOPE_PATHS)
    assert gate.selects_data_update_browser_scope(
        ["frontend/src/features/platform-config/DataUpdateCenter.tsx"]
    )
    assert gate.selects_data_update_browser_scope(
        ["frontend/tests/playwright/data-update-center-balance-daily.spec.mjs"]
    )
    assert not gate.selects_data_update_browser_scope(
        ["frontend/src/api/balanceMovementClient.ts", "docs/note.md"]
    )


def test_formal_release_scope_uses_canonical_boundary() -> None:
    assert gate.selects_formal_release_scope(
        ["backend/app/core_finance/balance_analysis.py"]
    )
    assert gate.selects_formal_release_scope(
        ["backend/app/tasks/formal_balance_pipeline.py"]
    )
    assert not gate.selects_formal_release_scope(
        ["backend/app/tasks/data_update_center.py", "docs/note.md"]
    )


def test_resolve_required_tests_exact_prefix_dedup_and_order() -> None:
    small_map = {
        "src/exact.py": ("tests/test_b.py",),
        "pkg/": ("tests/test_a.py", "tests/test_b.py"),
    }
    matched = gate.resolve_required_tests(
        ["src/exact.py", "pkg\\inner\\mod.py", "unrelated.md"],
        gate_map=small_map,
    )
    assert matched == ["tests/test_a.py", "tests/test_b.py"]
    assert gate.resolve_required_tests(["unrelated.md"], gate_map=small_map) == []
    assert gate.resolve_required_tests([], gate_map=small_map) == []


def _run_git(repo: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, f"git {args} failed: {completed.stderr}"


@pytest.fixture()
def gate_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary git repo with one gated file, one unrelated file, tag 'base'.

    Also points the gate script at this repo and injects a small gate map, so
    the tests below exercise diff matching without rebuilding the real
    core_finance tree.
    """
    empty_config = tmp_path / "empty-gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "-c", "init.defaultBranch=main", "init", "--quiet")
    _run_git(repo, "config", "user.email", "caliber-gate@example.invalid")
    _run_git(repo, "config", "user.name", "Caliber Gate Test")
    (repo / "src").mkdir()
    (repo / "src" / "gated_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("base\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "--quiet", "-m", "base")
    _run_git(repo, "tag", "base")

    monkeypatch.setattr(gate, "ROOT", repo)
    monkeypatch.setattr(
        gate,
        "CALIBER_GATE_MAP",
        {"src/gated_module.py": ("tests/test_caliber_rule_hat_mapping.py",)},
    )
    return repo


def test_dry_run_reports_matched_tests_for_gated_change(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch gated module")

    exit_code = gate.main(["--base-ref", "base", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["base_ref"] == "base"
    assert payload["changed_files"] == ["src/gated_module.py"]
    assert payload["matched_tests"] == ["tests/test_caliber_rule_hat_mapping.py"]


def test_dry_run_reports_no_tests_for_unrelated_change(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch unrelated file")

    exit_code = gate.main(["--base-ref", "base", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["changed_files"] == ["unrelated.txt"]
    assert payload["matched_tests"] == []


def test_invalid_base_ref_fails_closed(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = gate.main(["--base-ref", "no-such-ref", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "FAIL-CLOSED" in captured.err
    assert "no-such-ref" in captured.err


def test_frontend_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        gate, "FRONTEND_FIRST_SCOPE_PATHS", ("src/gated_module.py",)
    )
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--frontend-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "affected")
    assert gate.main(["--base-ref", "base", "--frontend-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_release_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "FORMAL_RELEASE_PATHS", ("src/gated_module.py",))
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--release-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "formal source")
    assert gate.main(["--base-ref", "base", "--release-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_browser_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "DATA_UPDATE_BROWSER_PATHS", ("src/gated_module.py",))
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--data-update-browser-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "browser source")
    assert gate.main(["--base-ref", "base", "--data-update-browser-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_scheduler_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "SCHEDULER_WINDOWS_PATHS", ("src/gated_module.py",))
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--scheduler-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "scheduler source")
    assert gate.main(["--base-ref", "base", "--scheduler-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_selected_pytest_failure_propagates_nonzero(
    gate_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_test = gate_repo / "tests" / "test_data_update_balance_integration.py"
    selected_test.parent.mkdir()
    selected_test.write_text("def test_red():\n    assert False\n", encoding="utf-8")
    changed_source = gate_repo / "backend" / "app" / "api" / "routes" / "data_updates.py"
    changed_source.parent.mkdir(parents=True)
    changed_source.write_text("VALUE = 2\n", encoding="utf-8")
    monkeypatch.setattr(
        gate,
        "CALIBER_GATE_MAP",
        {
            "backend/app/api/routes/data_updates.py": (
                "tests/test_data_update_balance_integration.py",
            ),
        },
    )
    _run_git(gate_repo, "add", ".")
    _run_git(gate_repo, "commit", "--quiet", "-m", "selected failing regression")

    assert gate.main(["--base-ref", "base"]) == 1
