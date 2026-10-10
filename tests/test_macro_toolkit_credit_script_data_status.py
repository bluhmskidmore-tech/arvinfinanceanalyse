"""Credit toolkit scripts must not present sample/empty data as real system output.

- ``credit_bond_monitor.py`` builds alerts from hardcoded sample inputs
  (fixed-income-plus redemption history, province risk scores, spread floors).
  Its CSV outputs must carry an explicit sample-data marker column.
- ``credit_bond_data.py`` must not claim "mock data" when the system source is
  unavailable; it writes an empty output and must say so explicitly.
"""

from __future__ import annotations

import importlib.util

import pandas as pd
import pytest

from backend.app.core_finance.macro.toolkit.runner import get_toolkit_script

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _load_script_module(name: str, module_alias: str):
    script = get_toolkit_script(name)
    spec = importlib.util.spec_from_file_location(module_alias, script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_credit_monitor_outputs_carry_explicit_sample_data_marker(tmp_path, monkeypatch, capsys) -> None:
    legacy = _load_script_module("credit_bond_monitor", "_legacy_credit_bond_monitor")

    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    pd.DataFrame(
        [
            {"日期": "2026-07-17", "指标类型": "信用利差", "品种": "利差_城投_AA_3Y", "最新值": 38.0, "单位": "bp"},
            {"日期": "2026-07-17", "指标类型": "收益率", "品种": "城投_AA_3Y", "最新值": 2.45, "单位": "%"},
        ]
    ).to_csv(output_dir / "credit_bond_latest.csv", index=False, encoding="utf-8-sig")
    monkeypatch.setattr(legacy.paths, "OUTPUT_DIR", output_dir)

    legacy.generate_monitor_report()

    alerts = pd.read_csv(output_dir / "risk_alert.csv", encoding="utf-8-sig")
    assert "数据状态" in alerts.columns
    assert not alerts["数据状态"].isna().any()
    fi_plus_rows = alerts[alerts["指标"] == "固收+申赎强度MA5"]
    assert (fi_plus_rows["数据状态"].str.contains("示例数据")).all()
    province_rows = alerts[alerts["指标"] == "城投区域风险"]
    assert (province_rows["数据状态"].str.contains("示例数据")).all()

    snapshot = pd.read_csv(output_dir / "credit_monitor.csv", encoding="utf-8-sig")
    assert "数据状态" in snapshot.columns
    assert "示例数据" in str(snapshot["数据状态"].iloc[0])
    assert "区间最小值为示例数据" in str(snapshot["数据状态"].iloc[0])


def test_spread_floor_skips_nan_latest_values(tmp_path, monkeypatch) -> None:
    legacy = _load_script_module("credit_bond_monitor", "_legacy_credit_bond_monitor_nan")

    frame = pd.DataFrame(
        [
            {"日期": "2026-07-17", "指标类型": "信用利差", "品种": "利差_城投_AA_3Y", "最新值": float("nan"), "单位": "bp"},
            {"日期": "2026-07-17", "指标类型": "信用利差", "品种": "利差_中短票_AAA_3Y", "最新值": 25.0, "单位": "bp"},
        ]
    )

    result = legacy.monitor_spread_floor(frame)

    assert result["品种"].tolist() == ["中短票_AAA_3Y"]


def test_credit_monitor_handles_spread_rows_without_floor_reference(tmp_path, monkeypatch, capsys) -> None:
    legacy = _load_script_module("credit_bond_monitor", "_legacy_credit_bond_monitor_no_floor")

    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    pd.DataFrame(
        [
            {"日期": "2026-07-17", "指标类型": "信用利差", "品种": "利差_二永债_大行二级资本债_2Y", "最新值": 25.0, "单位": "bp"},
        ]
    ).to_csv(output_dir / "credit_bond_latest.csv", index=False, encoding="utf-8-sig")
    monkeypatch.setattr(legacy.paths, "OUTPUT_DIR", output_dir)

    legacy.generate_monitor_report()

    snapshot = pd.read_csv(output_dir / "credit_monitor.csv", encoding="utf-8-sig")
    assert int(snapshot["利差极低品种数"].iloc[0]) == 0


def test_credit_monitor_missing_input_message_does_not_claim_mock_data(tmp_path, monkeypatch, capsys) -> None:
    legacy = _load_script_module("credit_bond_monitor", "_legacy_credit_bond_monitor_missing_input")

    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    monkeypatch.setattr(legacy.paths, "OUTPUT_DIR", output_dir)

    legacy.generate_monitor_report()

    captured = capsys.readouterr().out
    assert "mock data" not in captured
    assert "credit_bond_latest.csv not found" in captured


def test_credit_bond_data_reports_empty_output_when_system_source_unavailable(tmp_path, monkeypatch, capsys) -> None:
    legacy = _load_script_module("credit_bond_data", "_legacy_credit_bond_data")

    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    monkeypatch.setattr(legacy, "WIND_AVAILABLE", False)
    monkeypatch.setattr(legacy.paths, "OUTPUT_DIR", output_dir)

    frame = legacy.fetch_credit_bond_data()

    captured = capsys.readouterr().out
    assert frame.empty
    assert "mock data" not in captured
    assert "[WARNING]" in captured
    assert "empty" in captured


def test_credit_bond_data_source_unavailable_message_does_not_claim_mock_data() -> None:
    script = get_toolkit_script("credit_bond_data")
    source = script.path.read_text(encoding="utf-8")
    assert "using mock data" not in source
