from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]
WATCH_PATH = ROOT / "scripts" / "balance_movement_freshness_watch.py"
INSTALLER_PATH = ROOT / "scripts" / "install_balance_movement_freshness_timer.ps1"


def _watch_module():
    return load_module(
        "scripts.balance_movement_freshness_watch",
        "scripts/balance_movement_freshness_watch.py",
    )


def _seed_dates(
    duckdb_path: Path,
    *,
    latest_read_model: str | None,
    latest_upstream: str | None,
) -> None:
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date date,
              currency_basis varchar
            )
            """
        )
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date date,
              currency varchar,
              account_code varchar,
              source_version varchar
            )
            """
        )
        if latest_read_model is not None:
            conn.execute(
                "insert into fact_accounting_asset_movement_monthly values (?, 'CNX')",
                [latest_read_model],
            )
        if latest_upstream is not None:
            conn.execute(
                "insert into product_category_pnl_canonical_fact values (?, 'CNX', '1410001', 'sv-control')",
                [latest_upstream],
            )
    finally:
        conn.close()


def _write_manifest(
    governance_dir: Path,
    report_date: str,
    *,
    rule_version: str = "rv_accounting_asset_movement_v3",
    source_version: str = "sv-control",
) -> None:
    governance_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = governance_dir / "cache_manifest.jsonl"
    payload = {
        "cache_key": "accounting_asset_movement.monthly",
        "cache_version": "cv_accounting_asset_movement_v1",
        "rule_version": rule_version,
        "source_version": source_version,
        "report_date": report_date,
        "lineage": {"currency_basis": "CNX"},
    }
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def test_lagging_read_model_is_repaired_to_latest_upstream(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_dates(
        duckdb_path,
        latest_read_model="2026-05-31",
        latest_upstream="2026-06-30",
    )
    governance_dir = tmp_path / "governance"
    _write_manifest(governance_dir, "2026-05-31")
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs):
        calls.append(kwargs)
        conn = duckdb.connect(str(duckdb_path))
        try:
            conn.execute(
                "insert into fact_accounting_asset_movement_monthly values ('2026-06-30', 'CNX')"
            )
        finally:
            conn.close()
        _write_manifest(governance_dir, "2026-06-30")
        return {
            "status": "completed",
            "run_id": "run-latest",
            "payloads_by_date": {"2026-06-30": {"row_count": 3}},
        }

    monkeypatch.setattr(watch, "refresh_accounting_asset_movement_window_sync", fake_refresh)

    result = watch.reconcile_balance_movement_freshness(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        product_category_source_dir=tmp_path / "product-category",
        data_root=tmp_path / "data-input",
        archive_dir=tmp_path / "archive",
    )

    assert result["status"] == "repaired"
    assert result["latest_read_model_before"] == "2026-05-31"
    assert result["latest_read_model_after"] == "2026-06-30"
    assert result["latest_upstream_control_report_date"] == "2026-06-30"
    assert result["row_count"] == 3
    assert result["alert"] is None
    assert calls[0]["report_dates"] == ["2026-06-30"]
    assert calls[0]["anchor_report_date"] == "2026-06-30"
    assert calls[0]["currency_basis"] == "CNX"


def test_fresh_read_model_is_a_noop(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_dates(
        duckdb_path,
        latest_read_model="2026-06-30",
        latest_upstream="2026-06-30",
    )

    governance_dir = tmp_path / "governance"
    _write_manifest(governance_dir, "2026-06-30")

    def unexpected_refresh(**_kwargs):
        raise AssertionError("fresh data must not be materialized again")

    monkeypatch.setattr(
        watch,
        "refresh_accounting_asset_movement_window_sync",
        unexpected_refresh,
    )

    result = watch.reconcile_balance_movement_freshness(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
    )

    assert result["status"] == "fresh"
    assert result["latest_read_model_after"] == "2026-06-30"
    assert result["alert"] is None


def test_refresh_failure_returns_structured_alert(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_dates(
        duckdb_path,
        latest_read_model="2026-05-31",
        latest_upstream="2026-06-30",
    )

    governance_dir = tmp_path / "governance"
    _write_manifest(governance_dir, "2026-05-31")

    def failed_refresh(**_kwargs):
        raise RuntimeError("source workbook unavailable")

    monkeypatch.setattr(
        watch,
        "refresh_accounting_asset_movement_window_sync",
        failed_refresh,
    )

    result = watch.reconcile_balance_movement_freshness(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
    )

    assert result["status"] == "failed"
    assert result["latest_read_model_after"] == "2026-05-31"
    assert result["alert"] == {
        "active": True,
        "code": "balance_movement_refresh_failed",
        "severity": "high",
        "message": "RuntimeError: source workbook unavailable",
    }


def test_interior_gap_is_repaired_even_when_latest_dates_match(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_dates(
        duckdb_path,
        latest_read_model="2026-06-30",
        latest_upstream="2026-06-30",
    )
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.executemany(
            "insert into fact_accounting_asset_movement_monthly values (?, 'CNX')",
            [("2026-04-30",)],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, 'CNX', '1410001', 'sv-control')",
            [("2026-04-30",), ("2026-05-31",)],
        )
    finally:
        conn.close()
    _write_manifest(governance_dir, "2026-04-30")
    _write_manifest(governance_dir, "2026-06-30")
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs):
        calls.append(kwargs)
        conn = duckdb.connect(str(duckdb_path))
        try:
            conn.execute(
                "insert into fact_accounting_asset_movement_monthly values ('2026-05-31', 'CNX')"
            )
        finally:
            conn.close()
        _write_manifest(governance_dir, "2026-05-31")
        return {
            "status": "completed",
            "run_id": "run-interior",
            "payloads_by_date": {"2026-05-31": {"row_count": 3}},
        }

    monkeypatch.setattr(watch, "refresh_accounting_asset_movement_window_sync", fake_refresh)

    result = watch.reconcile_balance_movement_freshness(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
    )

    assert result["status"] == "repaired"
    assert result["missing_report_dates_before"] == ["2026-05-31"]
    assert result["missing_report_dates_after"] == []
    assert result["refreshed_report_dates"] == ["2026-05-31"]
    assert calls[0]["report_dates"] == ["2026-05-31"]


@pytest.mark.parametrize(
    ("manifest_rule", "manifest_source"),
    [
        ("rv-accounting-old", "sv-control"),
        ("rv_accounting_asset_movement_v3", "sv-control-old"),
    ],
)
def test_rule_or_source_drift_is_rematerialized(
    monkeypatch,
    tmp_path,
    manifest_rule: str,
    manifest_source: str,
) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_dates(
        duckdb_path,
        latest_read_model="2026-06-30",
        latest_upstream="2026-06-30",
    )
    _write_manifest(
        governance_dir,
        "2026-06-30",
        rule_version=manifest_rule,
        source_version=manifest_source,
    )

    def fake_refresh(**_kwargs):
        _write_manifest(governance_dir, "2026-06-30")
        return {
            "status": "completed",
            "run_id": "run-drift",
            "payloads_by_date": {"2026-06-30": {"row_count": 3}},
        }

    monkeypatch.setattr(watch, "refresh_accounting_asset_movement_window_sync", fake_refresh)

    result = watch.reconcile_balance_movement_freshness(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
    )

    assert result["status"] == "repaired"
    assert result["missing_report_dates_before"] == []
    assert result["stale_report_dates_before"] == ["2026-06-30"]
    assert result["stale_report_dates_after"] == []
    assert result["refreshed_report_dates"] == ["2026-06-30"]


def test_empty_upstream_activates_a_high_severity_alert(tmp_path) -> None:
    watch = _watch_module()
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_dates(
        duckdb_path,
        latest_read_model=None,
        latest_upstream=None,
    )

    result = watch.reconcile_balance_movement_freshness(
        duckdb_path=duckdb_path,
        governance_dir=tmp_path / "governance",
    )

    assert result["status"] == "no_upstream_data"
    assert result["alert"] == {
        "active": True,
        "code": "balance_movement_upstream_empty",
        "severity": "high",
        "message": (
            "No governed CNX control-account dates were found in "
            "product_category_pnl_canonical_fact."
        ),
    }


def test_cli_treats_no_upstream_data_as_failure(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    receipt_path = tmp_path / "receipt.json"
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
        product_category_source_dir=tmp_path / "product-category",
        data_input_root=tmp_path / "data-input",
        local_archive_path=tmp_path / "archive",
    )
    alert = {
        "active": True,
        "code": "balance_movement_upstream_empty",
        "severity": "high",
        "message": "upstream empty",
    }
    monkeypatch.setattr(watch, "get_settings", lambda: settings)
    monkeypatch.setattr(
        watch,
        "reconcile_balance_movement_freshness",
        lambda **_kwargs: {"status": "no_upstream_data", "alert": alert},
    )

    exit_code = watch.main(["--run-once", "--receipt-path", str(receipt_path)])

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert receipt["status"] == "no_upstream_data"
    assert receipt["exit_code"] == 1
    assert receipt["alert"] == alert


def test_cli_writes_failure_receipt_and_returns_nonzero(monkeypatch, tmp_path) -> None:
    watch = _watch_module()
    receipt_path = tmp_path / "receipt.json"
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
        product_category_source_dir=tmp_path / "product-category",
        data_input_root=tmp_path / "data-input",
        local_archive_path=tmp_path / "archive",
    )
    monkeypatch.setattr(watch, "get_settings", lambda: settings)
    monkeypatch.setattr(
        watch,
        "reconcile_balance_movement_freshness",
        lambda **_kwargs: {
            "status": "failed",
            "alert": {"active": True, "code": "failure", "severity": "high", "message": "boom"},
        },
    )

    exit_code = watch.main(["--run-once", "--receipt-path", str(receipt_path)])

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 1
    assert receipt["alert"]["active"] is True


def test_installer_registers_daily_watch_with_receipt_and_log() -> None:
    assert INSTALLER_PATH.exists(), "balance movement freshness timer installer is missing"
    text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert "MOSS-BalanceMovementFreshness" in text
    assert "balance_movement_freshness_watch.py --run-once" in text
    assert "balance_movement_freshness_receipt.json" in text
    assert "balance_movement_freshness.log" in text
    assert "06:45" in text
    assert "schtasks /Create" in text


def test_installer_allows_laptop_execution_and_catchup() -> None:
    assert INSTALLER_PATH.exists(), "balance movement freshness timer installer is missing"
    text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert "-AllowStartIfOnBatteries" in text
    assert "-DontStopIfGoingOnBatteries" in text
    assert "-StartWhenAvailable" in text
    assert "-RestartCount 3" in text
    assert "-RestartInterval (New-TimeSpan -Minutes 15)" in text


def test_installer_propagates_watch_failure_exit_code() -> None:
    assert INSTALLER_PATH.exists(), "balance movement freshness timer installer is missing"
    text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert 'set "watchExit=%ERRORLEVEL%"' in text
    assert 'if not "%watchExit%"=="0" echo ALERT' in text
    assert "exit /b %watchExit%" in text
