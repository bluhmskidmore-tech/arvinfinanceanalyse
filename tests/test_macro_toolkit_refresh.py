from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.governance.settings import get_settings
from backend.app.services.macro_toolkit_service import run_macro_toolkit_script as _REAL_SCRIPT_ENTRY
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


@pytest.fixture(autouse=True)
def _forbid_unmocked_refresh_subprocess(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return
    from backend.app.services import macro_toolkit_service as service

    def forbidden(*args, **kwargs):
        raise AssertionError("isolated refresh tests must never launch a toolkit subprocess")

    monkeypatch.setattr(service.subprocess, "run", forbidden)


@pytest.mark.parametrize("competing_entry", ["allocation", "script", "chain"])
def test_artifact_capture_keeps_all_writer_entries_excluded(tmp_path, monkeypatch, competing_entry):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.services import macro_toolkit_service as service
    from backend.app.tasks import macro_toolkit_refresh as refresh

    output = tmp_path / "output"
    output.mkdir()
    captured = threading.Event()
    release = threading.Event()
    original_capture = refresh._capture_run_artifact_snapshot
    step = refresh.MacroToolkitRefreshStep("risk_parity_cn", "test", ("risk_parity_results.csv",))
    monkeypatch.setattr(refresh, "STEPS", (step,))

    def write_script(*, name, output_dir, **kwargs):
        path = Path(output_dir) / "risk_parity_results.csv"
        path.write_text(threading.current_thread().name, encoding="utf-8")
        return {"status": "completed", "exit_code": 0, "output_files": [{"name": path.name, "path": str(path)}]}

    monkeypatch.setattr(refresh, "_run_macro_toolkit_script_unlocked", write_script)
    monkeypatch.setattr(service, "_run_macro_toolkit_script_unlocked", write_script)

    def pause_capture(**kwargs):
        if threading.current_thread().name.startswith("first-run"):
            captured.set()
            assert release.wait(5)
        return original_capture(**kwargs)

    monkeypatch.setattr(refresh, "_capture_run_artifact_snapshot", pause_capture)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="first-run") as pool:
        first = pool.submit(refresh.run_macro_toolkit_allocation_refresh, output_dir=output, governance_path=tmp_path / "governance-a")
        assert captured.wait(5)
        try:
            if competing_entry == "allocation":
                with pytest.raises(refresh.MacroToolkitRefreshConflictError):
                    refresh.run_macro_toolkit_allocation_refresh(output_dir=output, governance_path=tmp_path / "governance-b")
            elif competing_entry == "script":
                # Call the real public wrapper, with only its execution mocked.
                with pytest.raises(service.MacroToolkitConflictError):
                    _REAL_SCRIPT_ENTRY(name="risk_parity_cn", argv=[], timeout_seconds=1, output_dir=output)
            else:
                with pytest.raises(service.MacroToolkitConflictError):
                    service.run_macro_toolkit_chain(dry_run=False, timeout_seconds=1, output_dir=output, governance_path=tmp_path / "governance-b")
        finally:
            release.set()
        payload = first.result(timeout=5)
    manifest = json.loads(Path(payload["artifact_snapshot"]["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["run_id"] == payload["run_id"]
    copied = Path(payload["artifact_snapshot"]["run_dir"]) / "risk_parity_cn" / "risk_parity_results.csv"
    assert copied.read_text(encoding="utf-8").startswith("first-run")
    pointer = json.loads((output / "_allocation_refresh_runs" / "latest_manifest.json").read_text(encoding="utf-8"))
    assert pointer["run_id"] == payload["run_id"]
    original_bytes = Path(payload["artifact_snapshot"]["manifest_path"]).read_bytes()
    monkeypatch.setattr(refresh, "_capture_run_artifact_snapshot", original_capture)
    second = refresh.run_macro_toolkit_allocation_refresh(output_dir=output)
    pointer = json.loads((output / "_allocation_refresh_runs" / "latest_manifest.json").read_text(encoding="utf-8"))
    assert pointer["run_id"] == second["run_id"]
    assert Path(payload["artifact_snapshot"]["manifest_path"]).read_bytes() == original_bytes


@pytest.mark.parametrize("failure_phase", ["capture", "publish"])
def test_failed_snapshot_keeps_previous_pointer_and_holds_writer_lock(tmp_path, monkeypatch, failure_phase):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.services import macro_toolkit_service as service
    from backend.app.tasks import macro_toolkit_refresh as refresh

    output = tmp_path / "output"
    output.mkdir()
    step = refresh.MacroToolkitRefreshStep("risk_parity_cn", "test", ("risk_parity_results.csv",))
    monkeypatch.setattr(refresh, "STEPS", (step,))
    counter = 0

    def write(*, output_dir, **kwargs):
        nonlocal counter
        counter += 1
        path = Path(output_dir) / "risk_parity_results.csv"
        path.write_text(str(counter), encoding="utf-8")
        return {"status": "completed", "exit_code": 0, "output_files": [{"name": path.name, "path": str(path)}]}

    monkeypatch.setattr(refresh, "_run_macro_toolkit_script_unlocked", write)
    first = refresh.run_macro_toolkit_allocation_refresh(output_dir=output)
    pointer_path = Path(first["artifact_snapshot"]["latest_pointer_path"])
    previous = pointer_path.read_bytes()
    paused, release = threading.Event(), threading.Event()

    def fail(*args, **kwargs):
        paused.set()
        assert release.wait(5)
        raise OSError("isolated snapshot failure")

    if failure_phase == "capture":
        monkeypatch.setattr(refresh.shutil, "copy2", fail)
    else:
        monkeypatch.setattr(refresh, "_publish_current_run_pointer", fail)
    with ThreadPoolExecutor(max_workers=1) as pool:
        failed = pool.submit(refresh.run_macro_toolkit_allocation_refresh, output_dir=output)
        assert paused.wait(5)
        try:
            with pytest.raises(service.MacroToolkitConflictError):
                service.run_macro_toolkit_script(name="risk_parity_cn", argv=[], timeout_seconds=1, output_dir=output)
        finally:
            release.set()
        result = failed.result(timeout=5)
    assert pointer_path.read_bytes() == previous
    assert result["artifact_snapshot"]["latest_pointer_status"] == ("unavailable" if failure_phase == "capture" else "unchanged")




def _file_sha256(path: Path) -> str:
    digest = sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _fake_completed(name: str, *, output_dir, **_kwargs) -> dict[str, object]:
    return {
        "status": "completed",
        "exit_code": 0,
        "stdout": f"{name} ok",
        "stderr": "",
        "output_files": [],
    }


def _fake_completed_with_all_expected_outputs(name: str, *, output_dir, **_kwargs) -> dict[str, object]:
    step = next(item for item in STEPS if item.script_name == name)
    output_files = []
    for artifact_name in step.expected_outputs:
        artifact_path = Path(output_dir) / artifact_name
        artifact_path.write_text(f"{name}:{artifact_name}", encoding="utf-8")
        output_files.append(
            {
                "name": artifact_name,
                "path": str(artifact_path),
                "size_bytes": artifact_path.stat().st_size,
                "modified_at": "2026-08-24T09:00:00+00:00",
            }
        )
    return {
        "status": "completed",
        "exit_code": 0,
        "stdout": f"{name} ok",
        "stderr": "",
        "output_files": output_files,
    }


def test_steps_declare_csi500_preflight_requirements() -> None:
    required = {step.script_name: step for step in STEPS if step.required_aliases}
    assert set(required) == CSI500_REQUIRED_SCRIPTS
    for step in required.values():
        assert step.required_aliases[0].alias == "sh000905"
        assert step.required_aliases[0].min_observations == 100

    backtest = next(step for step in STEPS if step.script_name == "backtest_cn")
    assert "backtest_run_manifest.json" in backtest.expected_outputs


def test_run_order_matches_declared_steps_when_csi500_is_ready() -> None:
    called_order: list[str] = []

    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        called_order.append(name)
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
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
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
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
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
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
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
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
    expected_path = tmp_path / "performance_results.csv"

    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        expected_path.write_text(f"fresh artifact:{name}", encoding="utf-8")
        return {
            "status": "completed",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "output_files": [
                {
                    "name": "performance_results.csv",
                    "path": str(expected_path),
                    "size_bytes": expected_path.stat().st_size,
                    "modified_at": "now",
                },
                {"name": "unrelated_other_script_output.csv", "path": "y", "size_bytes": 1, "modified_at": "now"},
            ],
        }

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    by_name = {item["script_name"]: item for item in payload["results"]}
    produced_names = {entry["name"] for entry in by_name["performance_metrics_cn"]["produced_outputs"]}
    assert produced_names == {"performance_results.csv"}


def test_run_manifest_excludes_unchanged_shared_outputs_from_new_run_artifacts(tmp_path: Path) -> None:
    stale_path = tmp_path / "performance_results.csv"
    stale_path.write_text("stale artifact", encoding="utf-8")

    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        if name == "performance_metrics_cn":
            return {
                "status": "completed",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "output_files": [
                    {
                        "name": "performance_results.csv",
                        "path": str(stale_path),
                        "size_bytes": stale_path.stat().st_size,
                        "modified_at": "2026-08-24T09:00:00+00:00",
                    }
                ],
            }
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    performance = next(item for item in payload["results"] if item["script_name"] == "performance_metrics_cn")
    assert performance["status"] == "success"
    assert performance["artifact_status"] == "partial"
    assert performance["produced_outputs"] == []
    assert [item["name"] for item in performance["unchanged_outputs"]] == ["performance_results.csv"]
    snapshot = payload["artifact_snapshot"]
    assert snapshot["status"] == "partial"
    assert snapshot["stale_files"] == ["performance_metrics_cn:performance_results.csv"]
    manifest = json.loads(Path(snapshot["manifest_path"]).read_text(encoding="utf-8"))
    latest_pointer = json.loads(Path(snapshot["latest_pointer_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["stale_files"] == ["performance_metrics_cn:performance_results.csv"]
    assert latest_pointer["run_status"] == "completed"
    assert latest_pointer["snapshot_status"] == "partial"
    assert all(
        item["relative_path"] != "performance_metrics_cn/performance_results.csv"
        for item in manifest["artifacts"]
    )


def test_result_payload_structure(tmp_path: Path) -> None:
    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
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
    assert payload["artifact_snapshot"]["status"] in {"captured", "partial", "unavailable"}
    latest_pointer_path = payload["artifact_snapshot"]["latest_pointer_path"]
    if latest_pointer_path is not None:
        latest_pointer = json.loads(Path(latest_pointer_path).read_text(encoding="utf-8"))
        safe_run_dir_name = payload["run_id"].replace(":", "__")
        assert latest_pointer["run_id"] == payload["run_id"]
        assert latest_pointer["manifest_path"] == payload["artifact_snapshot"]["manifest_path"]
        assert latest_pointer["manifest_relative_path"] == f"{safe_run_dir_name}/run_manifest.json"
        assert latest_pointer["run_dir"] == payload["artifact_snapshot"]["run_dir"]
        assert latest_pointer["run_relative_path"] == safe_run_dir_name
        assert latest_pointer["manifest_sha256"] == payload["artifact_snapshot"]["manifest_sha256"]
        assert latest_pointer["source_version"] == payload["source_version"]
        assert latest_pointer["run_status"] == payload["status"]
        assert latest_pointer["snapshot_status"] == payload["artifact_snapshot"]["status"]
        assert payload["artifact_snapshot"]["latest_pointer_status"] == "published"
        assert payload["artifact_snapshot"]["latest_pointer_sha256"] == _file_sha256(Path(latest_pointer_path))
        assert payload["artifact_snapshot"]["current_pointer_path"] == latest_pointer_path
        assert payload["artifact_snapshot"]["stale_files"] == []

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


def test_published_changed_run_invalidates_market_home_cache(tmp_path: Path, monkeypatch) -> None:
    invalidations: list[str] = []
    monkeypatch.setattr(
        "backend.app.tasks.macro_toolkit_refresh._invalidate_allocation_refresh_caches",
        lambda: invalidations.append("invalidated"),
    )

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed_with_all_expected_outputs,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    assert payload["artifact_snapshot"]["latest_pointer_status"] == "published"
    assert payload["artifact_snapshot"]["copied_file_count"] > 0
    assert invalidations == ["invalidated"]


def test_partial_semantic_change_without_copied_files_invalidates_market_home_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    invalidations: list[str] = []
    monkeypatch.setattr(
        "backend.app.tasks.macro_toolkit_refresh._invalidate_allocation_refresh_caches",
        lambda: invalidations.append("invalidated"),
    )

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed_with_all_expected_outputs,
        ),
    ):
        first = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    invalidations.clear()

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed,
        ),
    ):
        second = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    assert first["artifact_snapshot"]["status"] == "captured"
    assert second["artifact_snapshot"]["latest_pointer_status"] == "published"
    assert second["artifact_snapshot"]["status"] == "partial"
    assert second["artifact_snapshot"]["copied_file_count"] == 0
    assert invalidations == ["invalidated"]


def test_no_change_run_does_not_invalidate_market_home_cache(tmp_path: Path, monkeypatch) -> None:
    invalidations: list[str] = []
    monkeypatch.setattr(
        "backend.app.tasks.macro_toolkit_refresh._invalidate_allocation_refresh_caches",
        lambda: invalidations.append("invalidated"),
    )

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed,
        ),
    ):
        first = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    invalidations.clear()

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed,
        ),
    ):
        second = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    assert first["artifact_snapshot"]["status"] == "partial"
    assert second["artifact_snapshot"]["latest_pointer_status"] == "published"
    assert second["artifact_snapshot"]["status"] == "partial"
    assert second["artifact_snapshot"]["copied_file_count"] == 0
    assert invalidations == []


def test_run_captures_atomic_run_snapshot_bundle(tmp_path: Path) -> None:
    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed_with_all_expected_outputs,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    snapshot = payload["artifact_snapshot"]
    assert snapshot["status"] == "captured"
    run_dir = Path(snapshot["run_dir"])
    manifest_path = Path(snapshot["manifest_path"])
    latest_pointer_path = Path(snapshot["latest_pointer_path"])
    assert run_dir.is_dir()
    assert manifest_path.is_file()
    assert latest_pointer_path.is_file()
    assert latest_pointer_path.name == "latest_manifest.json"
    assert not (tmp_path / "_allocation_refresh_runs" / f".{payload['run_id']}.tmp").exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    latest_pointer = json.loads(latest_pointer_path.read_text(encoding="utf-8"))
    performance_artifact = next(
        item for item in manifest["artifacts"] if item["relative_path"] == "performance_metrics_cn/performance_results.csv"
    )
    assert manifest["run_id"] == payload["run_id"]
    assert manifest["schema_version"] == "macro_toolkit_allocation_refresh_run_manifest.v1"
    assert manifest["status"] == "captured"
    assert manifest["formal_use_allowed"] is False
    assert manifest["observation_only"] is True
    assert manifest["status_counts"] == payload["status_counts"]
    assert any(path.endswith("performance_metrics_cn/performance_results.csv") for path in manifest["copied_files"])
    assert performance_artifact["size_bytes"] > 0
    assert len(performance_artifact["sha256"]) == 64
    assert performance_artifact["modified_at"]
    assert snapshot["manifest_sha256"] == _file_sha256(manifest_path)
    assert latest_pointer["run_id"] == payload["run_id"]
    assert latest_pointer["manifest_path"] == str(manifest_path)
    assert latest_pointer["manifest_relative_path"] == f"{payload['run_id'].replace(':', '__')}/run_manifest.json"
    assert latest_pointer["manifest_sha256"] == snapshot["manifest_sha256"]
    assert latest_pointer["run_dir"] == str(run_dir)
    assert latest_pointer["run_status"] == "completed"
    assert latest_pointer["snapshot_status"] == "captured"
    assert latest_pointer["published_at"] == payload["finished_at"]


def test_second_run_repoints_current_snapshot_without_rewriting_first_manifest(tmp_path: Path) -> None:
    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=fake_run,
        ),
    ):
        first = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)
        second = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    first_manifest_path = Path(first["artifact_snapshot"]["manifest_path"])
    second_manifest_path = Path(second["artifact_snapshot"]["manifest_path"])
    latest_pointer_path = Path(second["artifact_snapshot"]["latest_pointer_path"])
    latest_pointer = json.loads(latest_pointer_path.read_text(encoding="utf-8"))

    assert first["run_id"] != second["run_id"]
    assert first_manifest_path.is_file()
    assert second_manifest_path.is_file()
    assert latest_pointer["run_id"] == second["run_id"]
    assert latest_pointer["manifest_path"] == str(second_manifest_path)
    assert latest_pointer["manifest_sha256"] == second["artifact_snapshot"]["manifest_sha256"]
    assert latest_pointer["snapshot_status"] == second["artifact_snapshot"]["status"]
    assert json.loads(first_manifest_path.read_text(encoding="utf-8"))["run_id"] == first["run_id"]
    assert json.loads(second_manifest_path.read_text(encoding="utf-8"))["run_id"] == second["run_id"]


def test_pointer_publish_failure_run_itself_does_not_invalidate_market_home_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    invalidations: list[str] = []
    monkeypatch.setattr(
        "backend.app.tasks.macro_toolkit_refresh._invalidate_allocation_refresh_caches",
        lambda: invalidations.append("invalidated"),
    )

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed_with_all_expected_outputs,
        ),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._publish_current_run_pointer",
            side_effect=RuntimeError("pointer replace exploded"),
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    assert payload["artifact_snapshot"]["latest_pointer_status"] == "unchanged"
    assert payload["artifact_snapshot"]["copied_file_count"] > 0
    assert invalidations == []


def test_pointer_publish_failure_keeps_previous_latest_pointer(tmp_path: Path) -> None:
    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed_with_all_expected_outputs,
        ),
    ):
        first = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    latest_pointer_path = Path(first["artifact_snapshot"]["latest_pointer_path"])
    previous_pointer = json.loads(latest_pointer_path.read_text(encoding="utf-8"))

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=_fake_completed_with_all_expected_outputs,
        ),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._publish_current_run_pointer",
            side_effect=RuntimeError("pointer replace exploded"),
        ),
    ):
        second = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    second_snapshot = second["artifact_snapshot"]
    assert second_snapshot["status"] == "captured"
    assert second_snapshot["latest_pointer_status"] == "unchanged"
    assert second_snapshot["latest_pointer_path"] == str(latest_pointer_path)
    assert second_snapshot["latest_pointer_sha256"] is None
    assert "pointer replace exploded" in second_snapshot["reason"]
    assert Path(second_snapshot["manifest_path"]).is_file()
    assert json.loads(latest_pointer_path.read_text(encoding="utf-8")) == previous_pointer


def test_result_output_path_outside_output_dir_is_not_admitted_to_run_artifacts(tmp_path: Path) -> None:
    outside_dir = tmp_path.parent / "outside"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_path = outside_dir / "performance_results.csv"
    outside_path.write_text("outside artifact", encoding="utf-8")

    def fake_run(*, name: str, argv, timeout_seconds, output_dir):
        if name == "performance_metrics_cn":
            return {
                "status": "completed",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "output_files": [
                    {
                        "name": "performance_results.csv",
                        "path": str(outside_path),
                        "size_bytes": outside_path.stat().st_size,
                        "modified_at": "2026-08-24T09:00:00+00:00",
                    }
                ],
            }
        return _fake_completed(name, output_dir=output_dir)

    with (
        patch("backend.app.tasks.macro_toolkit_refresh._missing_required_aliases", return_value=[]),
        patch(
            "backend.app.tasks.macro_toolkit_refresh._run_macro_toolkit_script_unlocked",
            side_effect=fake_run,
        ),
    ):
        payload = run_macro_toolkit_allocation_refresh(output_dir=tmp_path, timeout_seconds=5)

    performance = next(item for item in payload["results"] if item["script_name"] == "performance_metrics_cn")
    assert performance["produced_outputs"] == []
    assert "performance_results.csv" in performance["missing_expected_outputs"]
    assert "performance.png" in performance["missing_expected_outputs"]
    assert performance["artifact_status"] == "partial"
    snapshot = payload["artifact_snapshot"]
    assert snapshot["status"] == "partial"
    assert "performance_metrics_cn:performance_results.csv" in snapshot["missing_files"]
    manifest = json.loads(Path(snapshot["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert "performance_metrics_cn:performance_results.csv" in manifest["missing_files"]
    assert all(
        item["relative_path"] != "performance_metrics_cn/performance_results.csv"
        for item in manifest["artifacts"]
    )


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
