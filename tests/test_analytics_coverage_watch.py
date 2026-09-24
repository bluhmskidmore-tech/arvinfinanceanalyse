from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb

from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]
WATCH_PATH = ROOT / "scripts" / "analytics_coverage_watch.py"
INSTALLER_PATH = ROOT / "scripts" / "install_analytics_coverage_timer.ps1"


def _watch_module():
    return load_module(
        "scripts.analytics_coverage_watch",
        "scripts/analytics_coverage_watch.py",
    )


def _seed(
    duckdb_path: Path,
    *,
    snapshot_dates: list[str],
    analytics_dates: list[str],
    risk_tensor_dates: list[str],
    curve_dates: list[str],
) -> None:
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date date, bond_code varchar)")
        conn.execute("create table fact_formal_bond_analytics_daily (report_date date, bond_code varchar)")
        conn.execute("create table fact_formal_risk_tensor_daily (report_date date, bond_count integer)")
        conn.execute("create table fact_formal_yield_curve_daily (trade_date date, tenor varchar)")
        for statement, values in (
            ("insert into zqtz_bond_daily_snapshot values (?, 'X')", snapshot_dates),
            ("insert into fact_formal_bond_analytics_daily values (?, 'X')", analytics_dates),
            ("insert into fact_formal_risk_tensor_daily values (?, 1)", risk_tensor_dates),
            ("insert into fact_formal_yield_curve_daily values (?, '1Y')", curve_dates),
        ):
            if values:
                conn.executemany(statement, [(value,) for value in values])
    finally:
        conn.close()


def _month_days(year: int, month: int, days: int) -> list[str]:
    return [f"{year:04d}-{month:02d}-{day:02d}" for day in range(1, days + 1)]


def test_replays_the_2026_analytics_gap_incident(tmp_path) -> None:
    """The 59-date June/July gap must produce an active, itemized alert."""
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    june = _month_days(2026, 6, 30)
    july = _month_days(2026, 7, 31)
    snapshot_dates = june + july
    # The incident state: only the two month-ends were ever materialized downstream.
    materialized = ["2026-06-30", "2026-07-31"]
    _seed(
        duckdb_path,
        snapshot_dates=snapshot_dates,
        analytics_dates=materialized,
        risk_tensor_dates=materialized,
        curve_dates=["2026-06-30", "2026-07-31"],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    analytics = result["daily"]["fact_formal_bond_analytics_daily"]
    risk_tensor = result["daily"]["fact_formal_risk_tensor_daily"]
    assert result["status"] == "gap_detected"
    assert analytics["missing_count"] == 59
    assert risk_tensor["missing_count"] == 59
    assert analytics["missing_report_dates"][0] == "2026-06-01"
    assert analytics["missing_report_dates_truncated"] is True
    assert result["alert"]["active"] is True
    assert result["alert"]["code"] == "analytics_daily_coverage_gap"
    assert result["alert"]["severity"] == "high"
    assert "fact_formal_bond_analytics_daily missing 59" in result["alert"]["message"]
    assert result["month_end"]["missing_count"] == 0


def test_full_coverage_is_a_silent_pass(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=dates,
        curve_dates=["2026-06-29"],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "covered"
    assert result["alert"] is None
    assert result["daily"]["fact_formal_bond_analytics_daily"]["missing_count"] == 0
    assert result["daily"]["fact_formal_risk_tensor_daily"]["missing_count"] == 0
    assert result["month_end"]["missing_count"] == 0
    assert result["latest_upstream_report_date"] == "2026-06-30"


def test_risk_tensor_gap_is_reported_independently_of_analytics(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=[value for value in dates if value != "2026-06-15"],
        curve_dates=["2026-06-30"],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "gap_detected"
    assert result["daily"]["fact_formal_bond_analytics_daily"]["missing_count"] == 0
    assert result["daily"]["fact_formal_risk_tensor_daily"]["missing_report_dates"] == ["2026-06-15"]


def test_missing_month_end_curve_is_reported_with_its_expected_date(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30) + _month_days(2026, 7, 31)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=dates,
        curve_dates=["2026-06-30"],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "gap_detected"
    assert result["alert"]["code"] == "yield_curve_month_end_gap"
    assert result["month_end"]["missing_months"] == [
        {"month": "2026-07", "expected_month_end_report_date": "2026-07-31"}
    ]
    assert result["month_end"]["latest_trade_date"] == "2026-06-30"


def test_curve_observation_anywhere_in_the_month_satisfies_the_month_end_check(tmp_path) -> None:
    """The curve trade_date is not always the calendar month end (e.g. 2026-05-29)."""
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 5, 31) + _month_days(2026, 6, 30)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=dates,
        curve_dates=["2026-05-29", "2026-06-26"],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "covered"
    assert result["month_end"]["missing_months"] == []


def test_in_progress_latest_month_is_not_flagged_as_a_curve_gap(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30) + _month_days(2026, 7, 10)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=dates,
        curve_dates=["2026-06-30"],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "covered"
    assert "2026-07" not in result["month_end"]["checked_months"]


def test_curve_lookback_window_bounds_the_month_end_check(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = ["2024-01-31"] + _month_days(2026, 6, 30) + _month_days(2026, 7, 31)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=dates,
        curve_dates=["2026-06-30", "2026-07-31"],
    )

    windowed = watch.check_analytics_coverage(duckdb_path=duckdb_path, curve_lookback_months=2)
    assert windowed["status"] == "covered"
    assert windowed["month_end"]["checked_months"] == ["2026-06", "2026-07"]

    unbounded = watch.check_analytics_coverage(duckdb_path=duckdb_path, curve_lookback_months=36)
    assert unbounded["status"] == "gap_detected"
    assert unbounded["month_end"]["missing_months"] == [
        {"month": "2024-01", "expected_month_end_report_date": "2024-01-31"}
    ]


def test_missing_fact_table_counts_every_upstream_date_as_a_gap(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date date, bond_code varchar)")
        conn.execute("insert into zqtz_bond_daily_snapshot values ('2026-06-30', 'X')")
    finally:
        conn.close()

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "gap_detected"
    assert result["daily"]["fact_formal_bond_analytics_daily"]["missing_report_dates"] == ["2026-06-30"]
    assert result["daily"]["fact_formal_risk_tensor_daily"]["missing_report_dates"] == ["2026-06-30"]


def test_empty_upstream_activates_a_high_severity_alert(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    _seed(
        duckdb_path,
        snapshot_dates=[],
        analytics_dates=[],
        risk_tensor_dates=[],
        curve_dates=[],
    )

    result = watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert result["status"] == "no_upstream_data"
    assert result["alert"]["code"] == "analytics_coverage_upstream_empty"
    assert result["alert"]["severity"] == "high"


def test_unreadable_database_returns_a_structured_failure(tmp_path) -> None:
    watch = _watch_module()
    broken = tmp_path / "not-a-duckdb.db"
    broken.write_bytes(b"this is not a duckdb file")

    result = watch.check_analytics_coverage(duckdb_path=broken)

    assert result["status"] == "failed"
    assert result["alert"]["code"] == "analytics_coverage_check_failed"


def test_cli_writes_receipt_and_returns_nonzero_on_a_gap(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    receipt_path = tmp_path / "receipt.json"
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=["2026-06-30"],
        risk_tensor_dates=["2026-06-30"],
        curve_dates=["2026-06-30"],
    )
    monkeypatch.setattr(watch, "get_settings", lambda: SimpleNamespace(duckdb_path=duckdb_path))

    exit_code = watch.main(
        ["--run-once", "--run-kind", "scheduled", "--receipt-path", str(receipt_path)]
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert receipt["status"] == "gap_detected"
    assert receipt["exit_code"] == 1
    assert receipt["task_name"] == "analytics_coverage_watch"
    assert receipt["run_kind"] == "scheduled"
    assert receipt["alert"]["active"] is True


def test_cli_returns_zero_when_coverage_is_complete(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    receipt_path = tmp_path / "receipt.json"
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=dates,
        risk_tensor_dates=dates,
        curve_dates=["2026-06-30"],
    )
    monkeypatch.setattr(watch, "get_settings", lambda: SimpleNamespace(duckdb_path=duckdb_path))

    exit_code = watch.main(["--run-once", "--receipt-path", str(receipt_path)])

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert receipt["status"] == "covered"
    assert receipt["alert"] is None


def test_watch_never_writes_duckdb(tmp_path) -> None:
    """The guard is alert-only; a read-only connection must not mutate the file."""
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    dates = _month_days(2026, 6, 30)
    _seed(
        duckdb_path,
        snapshot_dates=dates,
        analytics_dates=["2026-06-30"],
        risk_tensor_dates=["2026-06-30"],
        curve_dates=["2026-06-30"],
    )
    before = duckdb_path.read_bytes()

    watch.check_analytics_coverage(duckdb_path=duckdb_path)

    assert duckdb_path.read_bytes() == before


def test_watch_source_does_not_import_materialize_tasks() -> None:
    text = WATCH_PATH.read_text(encoding="utf-8")
    assert "materialize_bond_analytics_facts" not in text
    assert "materialize_risk_tensor_facts" not in text
    assert "duckdb.connect(" not in text
    assert "read_only_connection" in text


def test_installer_registers_daily_watch_with_receipt_and_log() -> None:
    assert INSTALLER_PATH.exists(), "analytics coverage timer installer is missing"
    text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert "MOSS-AnalyticsCoverage" in text
    assert "analytics_coverage_watch.py --run-once" in text
    assert "analytics_coverage_receipt.json" in text
    assert "analytics_coverage.log" in text
    assert "schtasks /Create" in text


def test_installer_allows_laptop_execution_and_propagates_failures() -> None:
    text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert "-AllowStartIfOnBatteries" in text
    assert "-DontStopIfGoingOnBatteries" in text
    assert "-StartWhenAvailable" in text
    assert 'set "watchExit=%ERRORLEVEL%"' in text
    assert 'if not "%watchExit%"=="0" echo ALERT' in text
    assert "exit /b %watchExit%" in text
