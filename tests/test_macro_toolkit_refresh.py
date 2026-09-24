from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.governance.settings import get_settings
from backend.app.tasks.macro_toolkit_refresh import (
    STEPS,
    MacroToolkitRefreshConflictError,
    run_macro_toolkit_allocation_refresh,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_macro_toolkit,
]

CSI500_REQUIRED_SCRIPTS = {"risk_parity_cn", "backtest_cn", "garch_multi_asset"}
EXECUTABLE_SCRIPTS = tuple(step.script_name for step in STEPS)


def _fake_completed(name: str, *, output_dir, **_kwargs) -> dict[str, object]:
    return {
        "status": "completed",
        "exit_code": 0,
        "stdout": f"{name} ok",
        "stderr": "",
        "output_files": [],
    }


def test_steps_declare_csi500_preflight_requirements() -> None:
    required = {step.script_name: step for step in STEPS if step.required_aliases}
    assert set(required) == CSI500_REQUIRED_SCRIPTS
    for step in required.values():
        assert step.required_aliases[0].alias == "sh000905"
        assert step.required_aliases[0].min_observations == 100


def test_run_order_matches_declared_steps_when_csi500_is_ready() -> None:
    called_order: list[str] = []

    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        called_order.append(name)
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh.run_macro_toolkit_script",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir="/tmp/unused", timeout_seconds=5)

    assert called_order == list(EXECUTABLE_SCRIPTS)
    result_names = [item["script_name"] for item in payload["results"]]
    assert result_names == [step.script_name for step in STEPS]

    for item in payload["results"]:
        assert item["status"] == "success"


def test_missing_csi500_preflight_blocks_only_dependent_scripts() -> None:
    called_order: list[str] = []

    def fake_missing_aliases(step):
        if step.script_name in CSI500_REQUIRED_SCRIPTS:
            return [{"alias": "sh000905", "label": "CSI500", "observed": 0, "required": 100, "error": None}]
        return []

    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        called_order.append(name)
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", side_effect=fake_missing_aliases),
        patch(
            "backend.app.tasks.macro_toolkit_refresh.run_macro_toolkit_script",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir="/tmp/unused", timeout_seconds=5)

    assert called_order == [name for name in EXECUTABLE_SCRIPTS if name not in CSI500_REQUIRED_SCRIPTS]
    by_name = {item["script_name"]: item for item in payload["results"]}
    for name in CSI500_REQUIRED_SCRIPTS:
        assert by_name[name]["status"] == "blocked"
        assert "sh000905" in by_name[name]["reason"]

    assert payload["status_counts"]["blocked"] == len(CSI500_REQUIRED_SCRIPTS)


def test_single_script_failure_does_not_block_remaining_scripts() -> None:
    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        if name == "cta_trend_cn":
            return {
                "status": "failed",
                "exit_code": 1,
                "stdout": "",
                "stderr": "boom\ncsi500 fetch failed",
                "output_files": [],
            }
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh.run_macro_toolkit_script",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir="/tmp/unused", timeout_seconds=5)

    by_name = {item["script_name"]: item for item in payload["results"]}
    assert by_name["cta_trend_cn"]["status"] == "failed"
    assert by_name["cta_trend_cn"]["exit_code"] == 1
    assert "csi500 fetch failed" in by_name["cta_trend_cn"]["reason"]

    # every other executable script still ran and succeeded despite the failure above
    for name in EXECUTABLE_SCRIPTS:
        if name == "cta_trend_cn":
            continue
        assert by_name[name]["status"] == "success"

    assert payload["status_counts"]["failed"] == 1
    assert payload["status_counts"]["success"] == len(EXECUTABLE_SCRIPTS) - 1


def test_unexpected_launch_exception_is_captured_per_script() -> None:
    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        if name == "dcc_garch_cn":
            raise RuntimeError("subprocess spawn exploded")
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh.run_macro_toolkit_script",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir="/tmp/unused", timeout_seconds=5)

    by_name = {item["script_name"]: item for item in payload["results"]}
    assert by_name["dcc_garch_cn"]["status"] == "failed"
    assert "subprocess spawn exploded" in by_name["dcc_garch_cn"]["reason"]
    # scripts after the exploding one in declared order still ran
    assert by_name["crowding_cn"]["status"] == "success"


def test_produced_outputs_are_filtered_to_expected_output_names(tmp_path: Path) -> None:
    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        return {
            "status": "completed",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "output_files": [
                {"name": "performance_results.csv", "path": "x", "size_bytes": 10, "modified_at": "now"},
                {"name": "unrelated_other_script_output.csv", "path": "y", "size_bytes": 1, "modified_at": "now"},
            ],
        }

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh.run_macro_toolkit_script",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    by_name = {item["script_name"]: item for item in payload["results"]}
    produced_names = {entry["name"] for entry in by_name["performance_metrics_cn"]["produced_outputs"]}
    assert produced_names == {"performance_results.csv"}


def test_result_payload_structure(tmp_path: Path) -> None:
    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh.run_macro_toolkit_script",
            side_effect=lambda *, name, argv, timeout_seconds, output_dir: _fake_completed(name, output_dir=output_dir),
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    assert payload["source_version"] == "macro_toolkit_allocation_refresh_v1"
    assert payload["status"] == "completed"
    assert payload["step_count"] == len(STEPS)
    assert payload["output_dir"] == str(tmp_path.resolve())
    assert isinstance(payload["duration_seconds"], float)
    assert set(payload["status_counts"]) <= {"success", "failed", "blocked"}

    for item in payload["results"]:
        assert {
            "script_name",
            "label",
            "status",
            "reason",
            "exit_code",
            "duration_seconds",
            "expected_outputs",
            "produced_outputs",
        }.issubset(item.keys())


def test_concurrent_run_raises_conflict_error_instead_of_racing(tmp_path: Path) -> None:
    with patch(
        "backend.app.tasks.macro_toolkit_refresh.acquire_lock",
        side_effect=TimeoutError("locked"),
    ):
        with pytest.raises(MacroToolkitRefreshConflictError):
            run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)


def test_run_macro_toolkit_allocation_refresh_task_is_registered() -> None:
    from backend.app.tasks import macro_toolkit_refresh as module

    assert module.run_macro_toolkit_allocation_refresh_task.actor_name == "run_macro_toolkit_allocation_refresh"


@pytest.mark.integration
def test_real_performance_metrics_cn_run_against_system_duckdb(tmp_path: Path) -> None:
    """Small real smoke test: runs the fastest automatable script end to end."""
    duckdb_path = Path(get_settings().duckdb_path)
    if not duckdb_path.exists():
        pytest.skip(f"system duckdb not available at {duckdb_path}")

    from backend.app.core_finance.macro.toolkit.runner import get_toolkit_script
    from backend.app.services.macro_toolkit_service import run_macro_toolkit_script

    script = get_toolkit_script("performance_metrics_cn")
    result = run_macro_toolkit_script(
        name="performance_metrics_cn",
        argv=[],
        timeout_seconds=60,
        output_dir=tmp_path,
    )

    assert script.path.exists()
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    output_names = {str(item["name"]) for item in result["output_files"]}
    assert "performance_results.csv" in output_names
