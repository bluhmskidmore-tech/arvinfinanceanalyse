from __future__ import annotations

import json
import socket
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import duckdb
import pytest

from scripts import choice_stock_daily_refresh as cli


class _FakeDate(date):
    fixed: date = date(2026, 8, 11)

    @classmethod
    def today(cls) -> date:
        return cls.fixed


@pytest.fixture
def cli_settings(monkeypatch, tmp_path) -> SimpleNamespace:
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
        choice_stock_catalog_file=tmp_path / "choice_stock_catalog.json",
        local_archive_path=tmp_path / "archive",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "_resolve_commit_sha", lambda: ("test-sha", None))
    monkeypatch.setattr(cli, "latest_choice_stock_inflight_refresh", lambda *_a, **_k: None)
    monkeypatch.setattr(
        cli,
        "choice_stock_refresh_status",
        lambda _path: {"status": "completed", "run_id": "r-latest"},
    )
    monkeypatch.setattr(
        cli,
        "compute_and_materialize_gate_supplement",
        lambda **_kwargs: {"status": "completed", "basis": "market_breadth", "computed_rows": 1},
    )
    monkeypatch.setattr(
        cli,
        "sync_livermore_position_snapshot",
        lambda **_kwargs: {
            "status": "completed",
            "source_as_of_date": "2026-08-10",
            "target_as_of_date": "2026-08-11",
            "risk_exit_input_status": "ready",
        },
    )
    monkeypatch.setattr(
        cli,
        "build_supply_freshness_report",
        lambda **_kwargs: {
            "status": "fresh",
            "expected_date": "2026-08-11",
            "thresholds": {
                "stale_after_trading_days": 1,
                "critical_after_trading_days": 5,
            },
            "calendar": {"holiday_aware": False},
            "series": [],
        },
    )
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    return settings


def test_dry_run_reports_plan_without_running_refresh(monkeypatch, cli_settings, capsys) -> None:
    def boom(**_kwargs):
        raise AssertionError("dry-run must not run the refresh job")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", boom)
    monkeypatch.setattr(cli, "default_choice_stock_refresh_as_of_date", lambda _path: "2026-07-24")

    assert cli.main(["--dry-run", "--as-of-date", "2026-08-11"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "dry_run"
    assert payload["as_of_date"] == "2026-08-11"
    assert payload["duckdb_latest_as_of"] == "2026-07-24"
    assert payload["latest_refresh"]["run_id"] == "r-latest"
    assert payload["would_run"]["refresh_history"] is True
    assert payload["would_run"]["refresh_factors"] is True
    assert payload["would_run"]["theme_overlay_mode"] == "archive"


def test_run_once_scheduled_writes_running_then_final_receipt(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs):
        running = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert running["status"] == "running"
        assert running["exit_code"] is None
        assert running["run_kind"] == "scheduled"
        calls.append(kwargs)

    monkeypatch.setattr(cli, "run_choice_stock_refresh", fake_run)

    exit_code = cli.main(
        [
            "--run-once",
            "--run-kind",
            "scheduled",
            "--as-of-date",
            "2026-08-11",
            "--receipt-path",
            str(receipt_path),
        ]
    )

    assert exit_code == 0
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["as_of_date"] == "2026-08-11"
    assert kwargs["duckdb_path"] == str(cli_settings.duckdb_path)
    assert kwargs["governance_path"] == str(cli_settings.governance_path)
    assert kwargs["refresh_history"] is True
    assert kwargs["refresh_factors"] is True
    assert kwargs["theme_overlay_mode"] == "archive"
    assert str(kwargs["run_id"]).startswith("choice_stock_refresh:2026-08-11:")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == {
        "schema_version": 1,
        "generated_at": receipt["generated_at"],
        "run_kind": "scheduled",
        "invocation_mode": "run_once",
        "task_name": "run_choice_stock_refresh",
        "commit_sha": "test-sha",
        "source_version": "choice_stock_daily_refresh_v1",
        "status": "success",
        "exit_code": 0,
        "result": receipt["result"],
        "warnings": [],
    }
    assert receipt["result"]["status"] == "success"
    assert receipt["result"]["refresh"] == {"status": "completed", "run_id": "r-latest"}


def test_run_once_appends_supply_freshness_and_warns_stale_items(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"
    calls: list[dict[str, object]] = []
    freshness_report = {
        "status": "critical",
        "expected_date": "2026-08-11",
        "thresholds": {
            "stale_after_trading_days": 1,
            "critical_after_trading_days": 5,
        },
        "calendar": {"holiday_aware": False},
        "series": [
            {
                "name": "csi300_index",
                "latest_date": "2026-07-24",
                "expected_date": "2026-08-11",
                "lag_trading_days": 12,
                "status": "critical",
            },
            {
                "name": "cn10y_yield",
                "latest_date": "2026-08-07",
                "expected_date": "2026-08-11",
                "lag_trading_days": 2,
                "status": "stale",
            },
            {
                "name": "choice_stock_daily",
                "latest_date": None,
                "expected_date": "2026-08-11",
                "lag_trading_days": None,
                "status": "unavailable",
                "reason": "duckdb_locked",
            },
        ],
    }

    def fake_freshness(**kwargs):
        calls.append(kwargs)
        return freshness_report

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "build_supply_freshness_report", fake_freshness)

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    assert calls == [
        {
            "duckdb_path": str(cli_settings.duckdb_path),
            "governance_path": str(cli_settings.governance_path),
            "as_of_date": "2026-08-11",
        }
    ]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["result"]["supply_freshness"] == freshness_report
    assert receipt["warnings"] == [
        (
            "supply freshness critical: csi300_index latest_date=2026-07-24 "
            "expected_date=2026-08-11 lag_trading_days=12"
        ),
        (
            "supply freshness stale: cn10y_yield latest_date=2026-08-07 "
            "expected_date=2026-08-11 lag_trading_days=2"
        ),
    ]


def test_run_once_theme_overlay_mode_off_override(monkeypatch, cli_settings) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(cli, "run_choice_stock_refresh", fake_run)

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--theme-overlay-mode", "off"]
    )

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["theme_overlay_mode"] == "off"


def test_run_once_success_refreshes_gate_supplement(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"
    gate_calls: list[dict[str, object]] = []

    def fake_gate(**kwargs):
        gate_calls.append(kwargs)
        return {"status": "completed", "basis": "market_breadth", "computed_rows": 3}

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "compute_and_materialize_gate_supplement", fake_gate)

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    assert gate_calls == [
        {"duckdb_path": str(cli_settings.duckdb_path), "as_of_date": date(2026, 8, 11)}
    ]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "success"
    assert receipt["warnings"] == []
    assert receipt["result"]["gate_supplement"] == {
        "status": "completed",
        "basis": "market_breadth",
        "computed_rows": 3,
    }


def test_gate_supplement_failure_degrades_to_receipt_warning(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"

    def boom(**_kwargs):
        raise RuntimeError("gate supplement duckdb busy")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "compute_and_materialize_gate_supplement", boom)

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "success"
    assert receipt["result"]["gate_supplement"]["status"] == "failed"
    assert "gate supplement duckdb busy" in str(receipt["result"]["gate_supplement"]["error"])
    assert receipt["warnings"] == [
        "gate supplement refresh failed: RuntimeError: gate supplement duckdb busy"
    ]


def test_gate_supplement_non_completed_status_is_warned(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "compute_and_materialize_gate_supplement",
        lambda **_kwargs: {"status": "insufficient_data", "computed_rows": 0},
    )

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "success"
    assert receipt["warnings"] == [
        "gate supplement refresh returned status=insufficient_data"
    ]


def test_run_once_success_rolls_forward_position_snapshot(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"
    position_calls: list[dict[str, object]] = []

    def fake_sync(**kwargs):
        position_calls.append(kwargs)
        return {
            "status": "completed",
            "source_as_of_date": "2026-08-10",
            "target_as_of_date": "2026-08-11",
            "trading_day_delta": 1,
            "risk_exit_input_status": "ready",
        }

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "sync_livermore_position_snapshot", fake_sync)

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    assert position_calls == [
        {"duckdb_path": str(cli_settings.duckdb_path), "target_as_of": "2026-08-11"}
    ]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "success"
    assert receipt["warnings"] == []
    assert receipt["result"]["position_snapshot_rollforward"] == {
        "status": "completed",
        "source_as_of_date": "2026-08-10",
        "target_as_of_date": "2026-08-11",
        "trading_day_delta": 1,
        "risk_exit_input_status": "ready",
    }


def test_position_snapshot_rollforward_failure_degrades_to_receipt_warning(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"

    def boom(**_kwargs):
        raise RuntimeError("position snapshot roll-forward boom")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "sync_livermore_position_snapshot", boom)

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "success"
    assert receipt["result"]["position_snapshot_rollforward"]["status"] == "failed"
    assert "position snapshot roll-forward boom" in str(
        receipt["result"]["position_snapshot_rollforward"]["error"]
    )
    assert receipt["warnings"] == [
        "position snapshot roll-forward failed: RuntimeError: position snapshot roll-forward boom"
    ]
    # gate supplement (an independent step) must still have run and succeeded.
    assert receipt["result"]["gate_supplement"]["status"] == "completed"


def test_position_snapshot_rollforward_non_completed_status_is_warned(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "sync_livermore_position_snapshot",
        lambda **_kwargs: {
            "status": "blocked",
            "reason": "No ACTIVE livermore_position_snapshot rows to roll forward.",
        },
    )

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "success"
    assert receipt["warnings"] == [
        "position snapshot roll-forward returned status=blocked"
    ]


def test_position_snapshot_rollforward_retries_on_duckdb_writer_contention_then_succeeds(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"
    attempts: list[int] = []
    sleeps: list[float] = []

    def flaky_sync(**_kwargs):
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise duckdb.IOException("Could not set lock on file: moss.duckdb")
        return {"status": "completed"}

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "sync_livermore_position_snapshot", flaky_sync)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: sleeps.append(seconds))

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    assert len(attempts) == 3
    assert sleeps == [15.0, 15.0]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["warnings"] == []
    assert receipt["result"]["position_snapshot_rollforward"] == {"status": "completed"}


def test_position_snapshot_rollforward_exhausts_retries_and_warns(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"
    attempts: list[int] = []
    sleeps: list[float] = []

    def always_locked(**_kwargs):
        attempts.append(len(attempts) + 1)
        raise duckdb.IOException("database is locked")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "sync_livermore_position_snapshot", always_locked)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: sleeps.append(seconds))

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 0
    assert len(attempts) == cli.POSITION_SNAPSHOT_ROLLFORWARD_RETRY_ATTEMPTS
    assert len(sleeps) == cli.POSITION_SNAPSHOT_ROLLFORWARD_RETRY_ATTEMPTS - 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["result"]["position_snapshot_rollforward"]["status"] == "failed"
    assert receipt["warnings"] == [
        "position snapshot roll-forward failed: IOException: database is locked"
    ]


def test_is_duckdb_writer_contention_detects_lock_messages() -> None:
    assert cli._is_duckdb_writer_contention(
        duckdb.IOException("Could not set lock on file: moss.duckdb")
    )
    assert cli._is_duckdb_writer_contention(duckdb.IOException("database is locked"))
    assert not cli._is_duckdb_writer_contention(RuntimeError("database is locked"))
    assert not cli._is_duckdb_writer_contention(duckdb.IOException("file not found"))


def test_run_once_failure_writes_failed_receipt_and_exit_1(
    monkeypatch, cli_settings, tmp_path
) -> None:
    receipt_path = tmp_path / "receipt.json"

    def fake_run(**_kwargs):
        raise RuntimeError("vendor unavailable")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", fake_run)

    exit_code = cli.main(
        [
            "--run-once",
            "--as-of-date",
            "2026-08-11",
            "--receipt-path",
            str(receipt_path),
        ]
    )

    assert exit_code == 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 1
    assert "RuntimeError: vendor unavailable" in str(receipt["result"]["error"])
    assert receipt["result"]["refresh"] == {"status": "completed", "run_id": "r-latest"}


def test_default_weekend_date_is_skipped(monkeypatch, cli_settings, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli, "date", _FakeDate)
    _FakeDate.fixed = date(2026, 8, 9)  # Sunday

    def boom(**_kwargs):
        raise AssertionError("weekend default must not run the refresh job")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", boom)
    receipt_path = tmp_path / "receipt.json"

    exit_code = cli.main(["--run-once", "--receipt-path", str(receipt_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "skipped_non_trading_day"
    assert payload["as_of_date"] == "2026-08-09"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "skipped_non_trading_day"
    assert receipt["exit_code"] == 0


def test_explicit_weekend_as_of_date_still_runs(monkeypatch, cli_settings) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        cli,
        "run_choice_stock_refresh",
        lambda **kwargs: calls.append(str(kwargs["as_of_date"])),
    )

    assert cli.main(["--run-once", "--as-of-date", "2026-08-09"]) == 0
    assert calls == ["2026-08-09"]


def test_inflight_conflict_exits_nonzero_without_running(
    monkeypatch, cli_settings, tmp_path, capsys
) -> None:
    monkeypatch.setattr(
        cli,
        "latest_choice_stock_inflight_refresh",
        lambda *_a, **_k: {"run_id": "r-inflight", "status": "running"},
    )

    def boom(**_kwargs):
        raise AssertionError("conflict must not run the refresh job")

    monkeypatch.setattr(cli, "run_choice_stock_refresh", boom)
    receipt_path = tmp_path / "receipt.json"

    exit_code = cli.main(
        ["--run-once", "--as-of-date", "2026-08-11", "--receipt-path", str(receipt_path)]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "conflict"
    assert payload["inflight_run_id"] == "r-inflight"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "conflict"
    assert receipt["exit_code"] == 1


def test_vendor_source_ip_requires_run_once(cli_settings, capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--dry-run", "--vendor-source-ip", "10.0.0.9"])
    assert excinfo.value.code == 2
    assert "--vendor-source-ip requires --run-once" in capsys.readouterr().err


def test_vendor_source_network_binds_sockets_and_restores(monkeypatch) -> None:
    import urllib3.util.connection as urllib3_connection

    recorded: list[dict[str, object]] = []
    urllib3_recorded: list[dict[str, object]] = []

    def recorder(address, *args, **kwargs):
        recorded.append({"address": address, "args": args, "kwargs": kwargs})
        return "sentinel-socket"

    def urllib3_recorder(address, *args, **kwargs):
        urllib3_recorded.append({"address": address, "args": args, "kwargs": kwargs})
        return "sentinel-urllib3-socket"

    monkeypatch.setattr(socket, "create_connection", recorder)
    monkeypatch.setattr(urllib3_connection, "create_connection", urllib3_recorder)
    monkeypatch.delenv("CHOICE_MACRO_SOCKS5_PROXY_HOST", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_SOCKS5_PROXY_PORT", raising=False)

    @contextmanager
    def fake_proxy(*, source_ip):
        assert source_ip == "10.0.0.9"
        yield SimpleNamespace(host="127.0.0.1", port=1080)

    monkeypatch.setattr(cli, "source_bound_socks_proxy", fake_proxy)

    import os

    with cli._vendor_source_network("10.0.0.9"):
        assert os.environ["CHOICE_MACRO_SOCKS5_PROXY_HOST"] == "127.0.0.1"
        assert os.environ["CHOICE_MACRO_SOCKS5_PROXY_PORT"] == "1080"
        assert socket.create_connection(("example.com", 443)) == "sentinel-socket"
        assert recorded[-1]["kwargs"]["source_address"] == ("10.0.0.9", 0)
        pinned = socket.create_connection(
            ("example.com", 443), 5.0, ("192.0.2.1", 0)
        )
        assert pinned == "sentinel-socket"
        assert recorded[-1]["args"] == (5.0, ("192.0.2.1", 0))
        # urllib3 (requests -> Tushare) has its own create_connection entry point.
        result = urllib3_connection.create_connection(("api.tushare.pro", 443))
        assert result == "sentinel-urllib3-socket"
        assert urllib3_recorded[-1]["kwargs"]["source_address"] == ("10.0.0.9", 0)

    assert socket.create_connection is recorder
    assert urllib3_connection.create_connection is urllib3_recorder
    assert "CHOICE_MACRO_SOCKS5_PROXY_HOST" not in os.environ
    assert "CHOICE_MACRO_SOCKS5_PROXY_PORT" not in os.environ
