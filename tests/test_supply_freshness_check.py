from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import duckdb

from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    THEME_OVERLAY_CACHE_KEY,
)
from backend.app.services import supply_freshness_service as freshness
from scripts import supply_freshness_check as cli


def _create_supply_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_choice_macro_daily (
          series_id varchar,
          trade_date varchar,
          value_numeric double
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          close_value double
        )
        """
    )
    conn.execute("create table choice_stock_factor_snapshot (as_of_date varchar)")
    conn.execute(
        """
        create table fact_livermore_gate_supplement_daily (
          trade_date varchar,
          breadth_5d double,
          limit_up_quality_ok boolean
        )
        """
    )
    conn.execute("create table livermore_position_snapshot (as_of_date varchar)")


def _write_theme_overlay_manifest(governance_path: Path, report_date: str) -> None:
    governance_path.mkdir(parents=True, exist_ok=True)
    rows = [
        {"cache_key": "unrelated", "report_date": "2099-01-01"},
        {"cache_key": THEME_OVERLAY_CACHE_KEY, "report_date": report_date},
    ]
    (governance_path / "cache_manifest.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def _series_by_name(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["name"]): item
        for item in report["series"]
        if isinstance(item, dict)
    }


def test_supply_freshness_golden_fresh_stale_and_critical(tmp_path: Path) -> None:
    conn = duckdb.connect(":memory:")
    try:
        _create_supply_tables(conn)
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?)",
            [
                ("CA.CSI300", "2026-07-24", 4123.0),
                ("CA.CSI300_PE", "2026-08-12", 13.5),
                ("EMM00166466", "2026-08-10", 1.78),
            ],
        )
        conn.execute("insert into choice_stock_daily_observation values ('2026-08-11', 10.0)")
        conn.execute("insert into choice_stock_factor_snapshot values ('2026-08-07')")
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values "
            "('2026-08-06', 0.52, true)"
        )
        conn.execute("insert into livermore_position_snapshot values ('2026-08-03')")
        governance_path = tmp_path / "governance"
        _write_theme_overlay_manifest(governance_path, "2026-08-12")

        report = freshness.build_supply_freshness_report(
            connection=conn,
            governance_path=governance_path,
            as_of_date="2026-08-12",
        )
    finally:
        conn.close()

    assert report["status"] == "critical"
    assert report["expected_date"] == "2026-08-12"
    assert report["thresholds"] == {
        "stale_after_trading_days": 1,
        "critical_after_trading_days": 5,
    }
    assert report["calendar"]["holiday_aware"] is False

    by_name = _series_by_name(report)
    assert list(by_name) == [
        "csi300_index",
        "csi300_pe",
        "cn10y_yield",
        "choice_stock_daily",
        "choice_stock_factor_snapshot",
        "livermore_gate_supplement",
        "livermore_position_snapshot",
        "stock_analysis_theme_overlay",
    ]
    assert (
        by_name["csi300_index"]["latest_date"],
        by_name["csi300_index"]["lag_trading_days"],
        by_name["csi300_index"]["status"],
    ) == (
        "2026-07-24",
        13,
        "critical",
    )
    assert by_name["csi300_pe"]["status"] == "fresh"
    assert by_name["choice_stock_daily"]["status"] == "fresh"
    assert (by_name["cn10y_yield"]["lag_trading_days"], by_name["cn10y_yield"]["status"]) == (
        2,
        "stale",
    )
    assert (
        by_name["livermore_position_snapshot"]["lag_trading_days"],
        by_name["livermore_position_snapshot"]["status"],
    ) == (7, "critical")
    assert by_name["stock_analysis_theme_overlay"]["status"] == "fresh"


def test_supply_freshness_marks_missing_table_and_series(tmp_path: Path) -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double
            )
            """
        )
        conn.execute(
            "insert into fact_choice_macro_daily values ('CA.CSI300', '2026-08-12', 4100.0)"
        )
        report = freshness.build_supply_freshness_report(
            connection=conn,
            governance_path=tmp_path / "missing-governance",
            as_of_date="2026-08-12",
        )
    finally:
        conn.close()

    by_name = _series_by_name(report)
    assert by_name["csi300_index"]["status"] == "fresh"
    assert by_name["csi300_pe"]["status"] == "missing"
    assert by_name["csi300_pe"]["reason"] == "series_missing"
    assert by_name["choice_stock_daily"]["status"] == "missing"
    assert by_name["choice_stock_daily"]["reason"] == "table_missing"
    assert by_name["stock_analysis_theme_overlay"]["status"] == "missing"
    assert by_name["stock_analysis_theme_overlay"]["reason"] == "governance_manifest_missing"


def test_supply_freshness_duckdb_lock_degrades_without_hiding_governance(
    monkeypatch,
    tmp_path: Path,
) -> None:
    governance_path = tmp_path / "governance"
    _write_theme_overlay_manifest(governance_path, "2026-08-12")
    duckdb_path = tmp_path / "locked.duckdb"
    duckdb_path.write_bytes(b"locked fixture")
    connect_calls: list[dict[str, object]] = []

    def locked_connect(*_args, **kwargs):
        connect_calls.append(kwargs)
        raise duckdb.IOException("File is already open in another process")

    monkeypatch.setattr(freshness.duckdb, "connect", locked_connect)

    report = freshness.build_supply_freshness_report(
        duckdb_path=duckdb_path,
        governance_path=governance_path,
        as_of_date="2026-08-12",
    )

    by_name = _series_by_name(report)
    duckdb_series = [
        item for item in by_name.values() if item["source_kind"] == "duckdb"
    ]
    assert len(duckdb_series) == 7
    assert {
        (item["status"], item["reason"]) for item in duckdb_series
    } == {("unavailable", "duckdb_locked")}
    assert connect_calls == [{"database": str(duckdb_path), "read_only": True}]
    assert by_name["stock_analysis_theme_overlay"]["status"] == "fresh"
    assert report["status"] == "unavailable"


def test_expected_date_skips_weekends_only() -> None:
    assert freshness.resolve_expected_trading_date("2026-08-09") == date(2026, 8, 7)
    assert freshness.resolve_expected_trading_date("2026-08-10") == date(2026, 8, 10)


def test_cli_json_and_fail_on_threshold(monkeypatch, tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
    )
    report = {
        "status": "stale",
        "expected_date": "2026-08-12",
        "thresholds": {
            "stale_after_trading_days": 1,
            "critical_after_trading_days": 5,
        },
        "calendar": {"holiday_aware": False},
        "series": [
            {
                "name": "csi300_index",
                "latest_date": "2026-08-10",
                "expected_date": "2026-08-12",
                "lag_trading_days": 2,
                "status": "stale",
            }
        ],
    }
    calls: list[dict[str, object]] = []

    def fake_report(**kwargs):
        calls.append(kwargs)
        return report

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "build_supply_freshness_report", fake_report)

    assert cli.main(["--json", "--as-of-date", "2026-08-12", "--fail-on", "stale"]) == 1
    assert json.loads(capsys.readouterr().out) == report
    assert cli.main(["--json", "--as-of-date", "2026-08-12", "--fail-on", "critical"]) == 0
    assert json.loads(capsys.readouterr().out) == report
    report["status"] = "critical"
    report["series"][0]["status"] = "critical"
    assert cli.main(["--json", "--as-of-date", "2026-08-12", "--fail-on", "critical"]) == 1
    assert json.loads(capsys.readouterr().out) == report
    assert calls[0]["duckdb_path"] == settings.duckdb_path
    assert calls[0]["governance_path"] == settings.governance_path
