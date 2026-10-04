from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from backend.app.services import macro_toolkit_service_model_chain as model_chain
from backend.app.services.macro_toolkit_service_model_chain import (
    build_model_chain_results,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


_TARGET_LAYOUT = {
    "dcc_latest.csv": "dcc_garch_cn/dcc_latest.csv",
    "dcc_results.csv": "dcc_garch_cn/dcc_results.csv",
    "regime_results.csv": "regime_switch_cn/regime_results.csv",
    "cta_results.csv": "cta_trend_cn/cta_results.csv",
    "risk_parity_results.csv": "risk_parity_cn/risk_parity_results.csv",
    "rebalance_results.csv": "rebalance_cn/rebalance_results.csv",
    "performance_results.csv": "performance_metrics_cn/performance_results.csv",
    "backtest_results.csv": "backtest_cn/backtest_results.csv",
    "backtest_run_manifest.json": "backtest_cn/backtest_run_manifest.json",
}


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _artifact_payloads(marker: str) -> dict[str, str]:
    return {
        "dcc_latest.csv": (
            "日期,平均相关系数,预警状态,hs300_gold\n"
            f"2026-08-01,0.{marker},正常,0.{marker}\n"
        ),
        "dcc_results.csv": (
            "date,avg_corr\n"
            f"2026-08-01,0.{marker}\n"
            f"2026-08-02,0.{marker}1\n"
        ),
        "regime_results.csv": (
            "资产,当前状态,策略建议,年化波动率%\n"
            f"沪深300,{marker}状态,{marker}建议,10\n"
        ),
        "cta_results.csv": (
            "资产,合成信号,趋势强度,操作建议,策略年化收益%,策略夏普比率,止损次数,减仓天数\n"
            f"铜,1,强趋势,{marker}建议,1,1,0,0\n"
        ),
        "risk_parity_results.csv": (
            "资产,风险平价权重%,风险预算权重%,年化波动率%\n"
            f"{marker}资产,40,40,10\n"
        ),
        "rebalance_results.csv": (
            "策略,年化收益%,年化波动%,夏普比率,再平衡次数,累计收益%\n"
            f"{marker}策略,1,1,1,1,1\n"
        ),
        "performance_results.csv": f"资产,夏普比率\n{marker}资产,1\n",
        "backtest_results.csv": (
            "策略,年化收益%,夏普比率,最大回撤%,胜率%,累计收益%\n"
            f"{marker}回测,1,1,-1,50,1\n"
        ),
        "backtest_run_manifest.json": json.dumps(
            {
                "status": "not_admitted",
                "admission_status": None,
                "observation_only": True,
                "formal_use_allowed": False,
                "sample": {
                    "price_start_date": "2025-01-01",
                    "price_end_date": f"2026-08-0{marker}",
                    "price_observation_days": 400,
                    "return_start_date": "2025-01-02",
                    "return_end_date": f"2026-08-0{marker}",
                    "return_trading_days": 399,
                    "declared_window_years": 5,
                },
                "asset_coverage": {
                    "configured_asset_count": 8,
                    "used_asset_count": 8,
                    "used_assets": [],
                    "missing_assets": [],
                    "complete": True,
                },
                "pit_gate": {
                    "status": "blocked",
                    "reason_code": f"snapshot_{marker}",
                    "required_fields": ["release_at", "available_at", "vintage", "revision"],
                    "available_fields": [],
                    "missing_fields": ["release_at", "available_at", "vintage", "revision"],
                    "completeness_pct": 0.0,
                    "decision_rule": "available_at <= decision_at",
                },
                "warnings": [f"SNAPSHOT_{marker}"],
            },
            ensure_ascii=False,
        ),
    }


def _publish_snapshot(
    output_dir: Path,
    *,
    run_id: str,
    marker: str,
    omitted: set[str] | None = None,
    corrupt_hash_for: str | None = None,
    publish: bool = True,
) -> Path:
    omitted = omitted or set()
    runs_root = output_dir / "_allocation_refresh_runs"
    run_dir = runs_root / run_id
    entries: list[dict[str, object]] = []
    payloads = _artifact_payloads(marker)
    for artifact_name, relative_path in _TARGET_LAYOUT.items():
        if artifact_name in omitted:
            continue
        artifact_path = run_dir / relative_path
        _write_text(artifact_path, payloads[artifact_name])
        entries.append(
            {
                "relative_path": relative_path,
                "size_bytes": artifact_path.stat().st_size,
                "sha256": (
                    "0" * 64 if artifact_name == corrupt_hash_for else _sha256(artifact_path)
                ),
            }
        )
    manifest_path = run_dir / "run_manifest.json"
    _write_text(
        manifest_path,
        json.dumps(
            {
                "schema_version": "macro_toolkit_allocation_refresh_run_manifest.v1",
                "run_id": run_id,
                "status": "captured" if not omitted else "partial",
                "observation_only": True,
                "formal_use_allowed": False,
                "artifacts": entries,
            },
            ensure_ascii=False,
        ),
    )
    if publish:
        _publish_pointer(output_dir, run_id=run_id, manifest_path=manifest_path)
    return manifest_path


def _publish_pointer(output_dir: Path, *, run_id: str, manifest_path: Path) -> None:
    runs_root = output_dir / "_allocation_refresh_runs"
    pointer_path = runs_root / "latest_manifest.json"
    _write_text(
        pointer_path,
        json.dumps(
            {
                "schema_version": "macro_toolkit_allocation_refresh_latest_pointer.v1",
                "run_id": run_id,
                "manifest_relative_path": manifest_path.relative_to(runs_root).as_posix(),
                "manifest_sha256": _sha256(manifest_path),
            },
            ensure_ascii=False,
        ),
    )


def _write_live_artifacts(output_dir: Path, marker: str) -> None:
    for artifact_name, content in _artifact_payloads(marker).items():
        _write_text(output_dir / artifact_name, content)


def _models_by_id(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(model["id"]): model
        for step in result["steps"]
        for model in step["models"]
    }


def test_complete_snapshot_reads_only_one_verified_run(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "9")
    _publish_snapshot(tmp_path, run_id="run-a", marker="1")

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["status"] == "ready"
    assert result["artifact_snapshot"]["read_status"] == "ready"
    assert result["artifact_snapshot"]["mode"] == "snapshot"
    assert result["artifact_snapshot"]["run_id"] == "run-a"
    assert result["artifact_snapshot"]["snapshot_status"] == "captured"
    assert result["artifact_snapshot"]["writer_status"] == "captured"
    assert models["risk_parity"]["rows"][0][0] == "1资产"
    assert models["risk_parity"]["artifact_provenance"]["status"] == "verified"
    assert models["risk_parity"]["artifact_provenance"]["run_id"] == "run-a"
    assert models["dcc_garch"]["trend"]["series"][0]["points"][-1][1] == 0.11
    assert models["dcc_garch"]["artifact_provenance"]["trend"]["run_id"] == "run-a"


def test_partial_snapshot_does_not_fill_missing_target_from_flat_residual(
    tmp_path: Path,
) -> None:
    # 平面目录仍残留上一轮 A；最新 B 缺件时不得拿 A 补齐。
    _write_live_artifacts(tmp_path, "1")
    _publish_snapshot(
        tmp_path,
        run_id="run-b",
        marker="2",
        omitted={"risk_parity_results.csv"},
    )

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["status"] == "partial"
    assert result["artifact_snapshot"]["read_status"] == "partial"
    assert result["artifact_snapshot"]["writer_status"] == "partial"
    assert models["risk_parity"]["artifact_status"] == "missing"
    assert models["risk_parity"]["rows"] == []
    assert models["risk_parity"]["artifact_provenance"]["status"] == "blocked"
    assert (
        models["risk_parity"]["artifact_provenance"]["reason_code"]
        == "snapshot_artifact_missing"
    )


def test_snapshot_hash_mismatch_fails_closed_instead_of_reading_flat_file(
    tmp_path: Path,
) -> None:
    _write_live_artifacts(tmp_path, "9")
    _publish_snapshot(
        tmp_path,
        run_id="run-bad-hash",
        marker="3",
        corrupt_hash_for="regime_results.csv",
    )

    model = _models_by_id(build_model_chain_results(tmp_path))["regime"]

    assert model["artifact_status"] == "missing"
    assert model["artifact_provenance"]["status"] == "blocked"
    assert model["artifact_provenance"]["reason_code"] == "snapshot_artifact_hash_mismatch"


def test_corrupt_pointer_fails_closed_for_covered_models_only(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "9")
    pointer_path = tmp_path / "_allocation_refresh_runs" / "latest_manifest.json"
    _write_text(pointer_path, "{invalid")
    _write_text(tmp_path / "merrill_clock_latest.csv", "日期,传统象限,bond_direction\n2026-08,复苏,多\n")

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["status"] == "invalid"
    assert models["risk_parity"]["artifact_status"] == "missing"
    assert models["risk_parity"]["artifact_provenance"]["status"] == "blocked"
    assert models["merrill_clock"]["artifact_status"] == "ok"
    assert models["merrill_clock"]["artifact_provenance"]["mode"] == "live_unverified"


def test_manifest_pointer_cannot_escape_allocation_runs_root(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "9")
    outside_manifest = tmp_path / "outside" / "run_manifest.json"
    _write_text(outside_manifest, "{}")
    pointer_path = tmp_path / "_allocation_refresh_runs" / "latest_manifest.json"
    _write_text(
        pointer_path,
        json.dumps(
            {
                "schema_version": "macro_toolkit_allocation_refresh_latest_pointer.v1",
                "run_id": "escaped-run",
                "manifest_relative_path": "../outside/run_manifest.json",
                "manifest_sha256": _sha256(outside_manifest),
            }
        ),
    )

    result = build_model_chain_results(tmp_path)
    risk_parity = _models_by_id(result)["risk_parity"]

    assert result["artifact_snapshot"]["status"] == "invalid"
    assert result["artifact_snapshot"]["warnings"] == ["snapshot_manifest_path_invalid"]
    assert risk_parity["artifact_status"] == "missing"
    assert risk_parity["artifact_provenance"]["status"] == "blocked"


def test_manifest_hash_mismatch_blocks_all_covered_artifacts(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "9")
    _publish_snapshot(tmp_path, run_id="run-a", marker="1")
    pointer_path = tmp_path / "_allocation_refresh_runs" / "latest_manifest.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["manifest_sha256"] = "0" * 64
    _write_text(pointer_path, json.dumps(pointer))

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["status"] == "invalid"
    assert result["artifact_snapshot"]["warnings"] == ["snapshot_manifest_hash_mismatch"]
    assert models["risk_parity"]["artifact_status"] == "missing"
    assert models["dcc_garch"]["trend"] is None
    assert models["merrill_clock"]["artifact_provenance"]["mode"] == "live_unverified"


def test_unknown_writer_manifest_status_fails_closed(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "9")
    manifest_path = _publish_snapshot(tmp_path, run_id="run-unknown-status", marker="1")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "completed"
    _write_text(manifest_path, json.dumps(manifest))
    _publish_pointer(
        tmp_path,
        run_id="run-unknown-status",
        manifest_path=manifest_path,
    )

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["status"] == "invalid"
    assert result["artifact_snapshot"]["read_status"] == "invalid"
    assert result["artifact_snapshot"]["writer_status"] is None
    assert result["artifact_snapshot"]["warnings"] == [
        "snapshot_manifest_status_invalid"
    ]
    assert models["risk_parity"]["artifact_status"] == "missing"
    assert models["risk_parity"]["artifact_provenance"]["status"] == "blocked"


def test_pointer_change_mid_build_keeps_first_loaded_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_a = _publish_snapshot(tmp_path, run_id="run-a", marker="1")
    manifest_b = _publish_snapshot(tmp_path, run_id="run-b", marker="2", publish=False)
    _publish_pointer(tmp_path, run_id="run-a", manifest_path=manifest_a)
    _write_text(tmp_path / "merrill_clock_latest.csv", "日期,传统象限,bond_direction\n2026-08,复苏,多\n")
    original_loader = model_chain._load_model_chain_frame
    changed = False

    def _switch_pointer_once(path: Path):
        nonlocal changed
        if not changed:
            changed = True
            _publish_pointer(tmp_path, run_id="run-b", manifest_path=manifest_b)
        return original_loader(path)

    monkeypatch.setattr(model_chain, "_load_model_chain_frame", _switch_pointer_once)

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["run_id"] == "run-a"
    assert models["risk_parity"]["rows"][0][0] == "1资产"
    assert models["dcc_garch"]["artifact_provenance"]["run_id"] == "run-a"


def test_backtest_csv_and_pit_manifest_are_resolved_from_same_snapshot(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "9")
    _publish_snapshot(tmp_path, run_id="run-a", marker="1")

    backtest = _models_by_id(build_model_chain_results(tmp_path))["backtest"]

    assert backtest["rows"][0][0] == "1回测"
    assert backtest["as_of"] == "2026-08-01"
    assert backtest["backtest_context"]["pit_gate"]["reason_code"] == "snapshot_1"
    assert backtest["artifact_provenance"]["run_id"] == "run-a"
    assert backtest["artifact_provenance"]["backtest_manifest"]["run_id"] == "run-a"


def test_missing_pointer_preserves_live_reads_but_marks_them_unverified(tmp_path: Path) -> None:
    _write_live_artifacts(tmp_path, "4")

    result = build_model_chain_results(tmp_path)
    models = _models_by_id(result)

    assert result["artifact_snapshot"]["status"] == "missing"
    assert result["artifact_snapshot"]["read_status"] == "missing"
    assert result["artifact_snapshot"]["mode"] == "live_unverified"
    assert result["artifact_snapshot"]["writer_status"] is None
    assert models["risk_parity"]["artifact_status"] == "ok"
    assert models["risk_parity"]["rows"][0][0] == "4资产"
    assert models["risk_parity"]["artifact_provenance"]["status"] == "unverified"
    assert models["dcc_garch"]["artifact_provenance"]["trend"]["mode"] == "live_unverified"
