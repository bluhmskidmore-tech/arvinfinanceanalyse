from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks import macro_toolkit_freshness_refresh as freshness


def _assert_receipt_metadata(receipt: dict[str, object]) -> None:
    started_at = datetime.fromisoformat(str(receipt["started_at"]))
    finished_at = datetime.fromisoformat(str(receipt["finished_at"]))
    assert finished_at >= started_at
    assert float(receipt["duration_seconds"]) >= 0.0
    assert int(receipt["attempt_count"]) >= 0
    assert "result" in receipt or "reason" in receipt


@pytest.fixture
def live_refresh_dependencies(monkeypatch, tmp_path) -> dict[str, object]:
    calls: list[str] = []
    duckdb_path = tmp_path / "moss.duckdb"

    def fake_commodity(**_kwargs):
        calls.append("commodity")
        return {"status": "completed", "row_count": 12, "product_count": 2}

    def fake_headlines(**_kwargs):
        calls.append("headlines")
        return {
            "status": "completed",
            "row_count": 100,
            "series_count": 10,
            "run_id": "public-1",
            "warnings": [],
        }

    def fake_ncd(**_kwargs):
        calls.append("ncd")
        return {
            "status": "completed",
            "row_count": 35,
            "series_count": 5,
            "run_id": "ncd-1",
        }

    def fake_policy_rate(**_kwargs):
        calls.append("policy_rate")
        return {
            "status": "completed",
            "row_count": 21,
            "series_id": "EMM00088132",
            "run_id": "policy-rate-1",
        }

    def fake_cffex(**_kwargs):
        calls.append("cffex")
        return {"row_count": 42}

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", fake_commodity)
    monkeypatch.setattr(freshness, "refresh_public_cross_asset_headlines", fake_headlines)
    monkeypatch.setattr(freshness, "_refresh_choice_policy_rate_7d", fake_policy_rate)
    monkeypatch.setattr(freshness, "refresh_tushare_ncd_shibor_proxy", fake_ncd)
    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", fake_cffex)
    monkeypatch.setattr(
        freshness,
        "_read_latest_observation_dates",
        lambda _path, **_kwargs: {"CA.CSI300": "2026-07-17"},
    )
    monkeypatch.setattr(
        freshness,
        "get_settings",
        lambda: type("S", (), {"duckdb_path": str(duckdb_path)})(),
    )
    monkeypatch.setattr(freshness, "DUCKDB_WRITE_RETRY_SLEEP_SECONDS", 0.0)
    return {"calls": calls, "duckdb_path": duckdb_path}


def test_latest_weekday_skips_weekend() -> None:
    assert freshness._latest_weekday_on_or_before(date(2026, 7, 19)) == date(2026, 7, 17)
    assert freshness._latest_weekday_on_or_before(date(2026, 7, 17)) == date(2026, 7, 17)


def test_refresh_macro_toolkit_freshness_dry_run(monkeypatch) -> None:
    calls: list[str] = []

    def fake_commodity(**kwargs):
        calls.append("commodity")
        assert kwargs["dry_run"] is True
        return {"status": "dry_run", "row_count": 0, "product_count": 3}

    def boom(*_args, **_kwargs):
        raise AssertionError("live writers must not run during dry-run")

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", fake_commodity)
    monkeypatch.setattr(freshness, "refresh_public_cross_asset_headlines", boom)
    monkeypatch.setattr(freshness, "_refresh_choice_policy_rate_7d", boom)
    monkeypatch.setattr(freshness, "refresh_tushare_ncd_shibor_proxy", boom)
    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", boom)
    monkeypatch.setattr(freshness, "get_settings", lambda: type("S", (), {"duckdb_path": "F:/tmp/moss.duckdb"})())
    monkeypatch.setattr(
        freshness,
        "_read_latest_observation_dates",
        lambda _path, **_kwargs: {},
    )

    result = freshness.refresh_macro_toolkit_freshness(
        dry_run=True,
        today=date(2026, 7, 20),
        commodity_products=("CU", "NHCI"),
    )
    assert result["status"] == "dry_run"
    assert calls == ["commodity"]
    assert [step["step"] for step in result["steps"]] == [
        "commodity_daily_ingest",
        "public_cross_asset_headlines",
        "choice_policy_rate_7d",
        "tushare_ncd_shibor",
        "cffex_member_rank",
    ]
    for receipt in result["steps"]:
        _assert_receipt_metadata(receipt)


def test_dry_run_commodity_plan_failure_sets_top_level_failed(monkeypatch) -> None:
    def fail_commodity(**_kwargs):
        raise RuntimeError("dry-run plan unavailable")

    def boom(*_args, **_kwargs):
        raise AssertionError("live writers must not run during dry-run")

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", fail_commodity)
    monkeypatch.setattr(freshness, "refresh_public_cross_asset_headlines", boom)
    monkeypatch.setattr(freshness, "_refresh_choice_policy_rate_7d", boom)
    monkeypatch.setattr(freshness, "refresh_tushare_ncd_shibor_proxy", boom)
    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", boom)
    monkeypatch.setattr(
        freshness,
        "get_settings",
        lambda: type("S", (), {"duckdb_path": "F:/tmp/moss.duckdb"})(),
    )
    monkeypatch.setattr(
        freshness,
        "_read_latest_observation_dates",
        lambda _path, **_kwargs: {},
    )

    result = freshness.refresh_macro_toolkit_freshness(
        dry_run=True,
        today=date(2026, 7, 20),
    )

    assert result["status"] == "failed"
    assert [step["status"] for step in result["steps"]] == [
        "failed",
        "dry_run",
        "dry_run",
        "dry_run",
        "dry_run",
    ]
    assert "RuntimeError: dry-run plan unavailable" in str(result["steps"][0]["reason"])
    for receipt in result["steps"]:
        _assert_receipt_metadata(receipt)


def test_required_failure_continues_remaining_steps_and_fails_run(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    calls = live_refresh_dependencies["calls"]

    def fail_commodity(**_kwargs):
        calls.append("commodity")
        raise RuntimeError("commodity vendor unavailable")

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", fail_commodity)

    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )

    assert result["status"] == "failed"
    assert calls == ["commodity", "headlines", "policy_rate", "ncd", "cffex"]
    assert [step["status"] for step in result["steps"]] == [
        "failed",
        "success",
        "success",
        "success",
        "success",
    ]
    assert "RuntimeError: commodity vendor unavailable" in str(result["steps"][0]["reason"])
    for receipt in result["steps"]:
        _assert_receipt_metadata(receipt)


def test_required_failure_detection_uses_explicit_step_names() -> None:
    shuffled_steps = [
        {"step": "cffex_member_rank", "status": "success"},
        {"step": "commodity_daily_ingest", "status": "success"},
        {"step": "tushare_ncd_shibor", "status": "failed"},
        {"step": "choice_policy_rate_7d", "status": "success"},
        {"step": "public_cross_asset_headlines", "status": "success"},
    ]

    assert freshness._has_required_step_failure(shuffled_steps) is True
    shuffled_steps[2]["status"] = "success"
    assert freshness._has_required_step_failure(shuffled_steps) is False


def test_policy_rate_no_rows_fails_required_freshness_step(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    monkeypatch.setattr(
        freshness,
        "_refresh_choice_policy_rate_7d",
        lambda **_kwargs: {"status": "no_rows", "row_count": 0, "series_id": "EMM00088132"},
    )

    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )

    policy_rate = next(step for step in result["steps"] if step["step"] == "choice_policy_rate_7d")
    assert result["status"] == "failed"
    assert policy_rate["status"] == "failed"
    assert "no_rows" in str(policy_rate["reason"])


def test_required_step_receipt_counts_duckdb_lock_retries(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    calls = {"n": 0}

    class _Busy(duckdb.Error):
        pass

    def flaky() -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Busy("File is already open")
        return {"status": "completed", "row_count": 12, "product_count": 2}

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", lambda **_kwargs: flaky())
    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )
    commodity = result["steps"][0]

    assert result["status"] == "success"
    assert calls["n"] == 3
    assert commodity["status"] == "success"
    assert commodity["attempt_count"] == 3


def test_required_step_does_not_retry_non_lock_error(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    calls = {"n": 0}

    def broken(**_kwargs):
        calls["n"] += 1
        raise duckdb.Error("Catalog Error: missing table")

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", broken)
    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )
    commodity = result["steps"][0]

    assert result["status"] == "failed"
    assert calls["n"] == 1
    assert commodity["status"] == "failed"
    assert commodity["attempt_count"] == 1


def test_call_with_duckdb_retry_stops_after_six_lock_attempts(monkeypatch) -> None:
    calls = {"n": 0}

    class _Busy(duckdb.Error):
        pass

    def always_busy() -> None:
        calls["n"] += 1
        raise _Busy("database is locked")

    monkeypatch.setattr(freshness, "DUCKDB_WRITE_RETRY_SLEEP_SECONDS", 0.0)
    with pytest.raises(_Busy, match="locked"):
        freshness._call_with_duckdb_retry("unit", always_busy)
    assert calls["n"] == freshness.DUCKDB_WRITE_RETRY_ATTEMPTS == 6


def test_latest_observation_dates_includes_all_ncd_shibor_tenors(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("create table fact_choice_macro_daily (series_id varchar, trade_date varchar)")
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('NCD.SHIBOR.1M', '2026-07-17'),
              ('NCD.SHIBOR.3M', '2026-07-16'),
              ('NCD.SHIBOR.3M', '2026-07-17'),
              ('NCD.SHIBOR.6M', '2026-07-15'),
              ('NCD.SHIBOR.9M', '2026-07-14'),
              ('NCD.SHIBOR.1Y', '2026-07-13'),
              ('EMM00088132', '2026-07-20')
            """
        )
    finally:
        conn.close()

    result = freshness._read_latest_observation_dates(duckdb_path)
    assert {key: result[key] for key in freshness.NCD_SHIBOR_SERIES_IDS} == {
        "NCD.SHIBOR.1M": "2026-07-17",
        "NCD.SHIBOR.3M": "2026-07-17",
        "NCD.SHIBOR.6M": "2026-07-15",
        "NCD.SHIBOR.9M": "2026-07-14",
        "NCD.SHIBOR.1Y": "2026-07-13",
    }
    assert result[freshness.POLICY_RATE_SERIES_ID] == "2026-07-20"


def test_refresh_macro_toolkit_freshness_cffex_falls_back_on_zero_rows(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    calls: list[str] = []

    def fake_cffex(**kwargs):
        trade_date = str(kwargs["trade_date"])
        calls.append(trade_date)
        if trade_date == "2026-07-20":
            return {"row_count": 0, "trade_date": trade_date}
        return {"row_count": 42, "trade_date": trade_date}

    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", fake_cffex)

    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )
    assert calls == ["2026-07-20", "2026-07-17"]
    assert result["status"] == "success"
    cffex = next(step for step in result["steps"] if step["step"] == "cffex_member_rank")
    assert cffex["status"] == "success"
    assert cffex["trade_date"] == "2026-07-17"
    assert cffex["result"]["row_count"] == 42
    assert cffex["attempt_count"] == 2


def test_cffex_zero_rows_exhausts_ten_workdays_and_degrades_run(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    calls: list[str] = []

    def unavailable(**kwargs):
        calls.append(str(kwargs["trade_date"]))
        return {"row_count": 0}

    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", unavailable)
    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )
    cffex = next(step for step in result["steps"] if step["step"] == "cffex_member_rank")

    assert calls == [
        "2026-07-20",
        "2026-07-17",
        "2026-07-16",
        "2026-07-15",
        "2026-07-14",
        "2026-07-13",
        "2026-07-10",
        "2026-07-09",
        "2026-07-08",
        "2026-07-07",
    ]
    assert result["status"] == "degraded"
    assert cffex["status"] == "degraded"
    assert cffex["attempt_count"] == 10
    assert len(cffex["result"]["attempts"]) == 10
    assert "10" in str(cffex["reason"])


def test_cffex_exception_stops_after_first_candidate_and_degrades(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    calls: list[str] = []

    def unavailable(**kwargs):
        calls.append(str(kwargs["trade_date"]))
        raise RuntimeError("vendor offline")

    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", unavailable)
    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )
    cffex = next(step for step in result["steps"] if step["step"] == "cffex_member_rank")

    assert calls == ["2026-07-20"]
    assert result["status"] == "degraded"
    assert cffex["status"] == "degraded"
    assert cffex["attempt_count"] == 1
    assert "RuntimeError: vendor offline" in str(cffex["reason"])
    assert len(cffex["result"]["attempts"]) == 1


def test_disabled_cffex_is_recorded_as_skipped(
    live_refresh_dependencies,
) -> None:
    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
        include_cffex=False,
    )

    assert result["status"] == "success"
    assert live_refresh_dependencies["calls"] == ["commodity", "headlines", "policy_rate", "ncd"]
    assert result["steps"][-1]["step"] == "cffex_member_rank"
    assert result["steps"][-1]["status"] == "skipped"
    _assert_receipt_metadata(result["steps"][-1])


def test_evidence_reader_failure_preserves_completed_steps_and_warns(
    monkeypatch,
    live_refresh_dependencies,
) -> None:
    def fail_evidence(_path: str | Path, **_kwargs):
        raise duckdb.Error("evidence database unavailable")

    monkeypatch.setattr(freshness, "_read_latest_observation_dates", fail_evidence)
    result = freshness.refresh_macro_toolkit_freshness(
        today=date(2026, 7, 20),
        duckdb_path=live_refresh_dependencies["duckdb_path"],
    )

    assert result["status"] == "success"
    assert [step["status"] for step in result["steps"]] == [
        "success",
        "success",
        "success",
        "success",
        "success",
    ]
    assert result["latest_observation_dates"] == {}
    assert any("evidence database unavailable" in warning for warning in result["warnings"])


def test_evidence_reader_returns_partial_dates_with_warning(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("create table fact_cffex_member_rank_daily (wrong_column varchar)")
        conn.execute("create table fact_choice_macro_daily (series_id varchar, trade_date varchar)")
        conn.execute(
            "insert into fact_choice_macro_daily values ('NCD.SHIBOR.3M', '2026-07-17')"
        )
    finally:
        conn.close()

    warnings: list[str] = []
    result = freshness._read_latest_observation_dates(duckdb_path, warnings=warnings)

    assert result["fact_cffex_member_rank_daily"] is None
    assert result["NCD.SHIBOR.3M"] == "2026-07-17"
    assert any("fact_cffex_member_rank_daily" in warning for warning in warnings)


def test_actor_registered() -> None:
    assert freshness.refresh_macro_toolkit_freshness_actor.actor_name == (
        "refresh_macro_toolkit_freshness"
    )


def test_cli_modes(monkeypatch, capsys) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Message:
        message_id = "m-1"

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def send(self, **kwargs):
            assert kwargs.get("include_cffex") is True
            return _Message()

        def fn(self, **kwargs):
            return {"status": "success", "run_id": "r-1", "steps": [], **kwargs}

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(
        cli,
        "refresh_macro_toolkit_freshness",
        lambda **kwargs: {"status": "dry_run", "run_id": "d-1", "steps": [], **kwargs},
    )

    assert cli.main(["--dry-run"]) == 0
    assert cli.main(["--enqueue"]) == 0
    assert cli.main(["--run-once"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 3


def test_cli_writes_atomic_structured_scheduled_receipt(monkeypatch, tmp_path) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    result = {
        "status": "success",
        "run_id": "scheduled-1",
        "source_version": "macro_toolkit_freshness_refresh_v3",
        "steps": [],
        "latest_observation_dates": {},
    }

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **kwargs):
            assert kwargs == {"include_cffex": True}
            return result

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(
        cli,
        "_resolve_commit_sha",
        lambda: ("0123456789abcdef", None),
        raising=False,
    )
    original_replace = Path.replace
    replace_calls: list[tuple[Path, Path]] = []

    def tracked_replace(source: Path, target: str | Path) -> Path:
        target_path = Path(target)
        assert source.parent == target_path.parent
        assert source != target_path
        assert source.is_file()
        replace_calls.append((source, target_path))
        return original_replace(source, target_path)

    monkeypatch.setattr(Path, "replace", tracked_replace)
    receipt_path = tmp_path / "scheduled-receipt.json"

    exit_code = cli.main(
        [
            "--run-once",
            "--run-kind",
            "scheduled",
            "--receipt-path",
            str(receipt_path),
        ]
    )

    assert exit_code == 0
    assert len(replace_calls) == 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == {
        "schema_version": 1,
        "generated_at": receipt["generated_at"],
        "run_kind": "scheduled",
        "invocation_mode": "run_once",
        "task_name": "refresh_macro_toolkit_freshness",
        "commit_sha": "0123456789abcdef",
        "source_version": "macro_toolkit_freshness_refresh_v3",
        "status": "success",
        "exit_code": 0,
        "result": result,
        "warnings": [],
    }
    datetime.fromisoformat(receipt["generated_at"])
    assert list(tmp_path.iterdir()) == [receipt_path]


@pytest.mark.parametrize(
    ("status", "expected_exit_code"),
    [("success", 0), ("degraded", 0), ("failed", 1)],
)
def test_cli_receipt_exit_code_matches_main(
    monkeypatch,
    tmp_path,
    status,
    expected_exit_code,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs):
            return {
                "status": status,
                "source_version": "macro_toolkit_freshness_refresh_v3",
            }

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(
        cli,
        "_resolve_commit_sha",
        lambda: (None, "commit SHA unavailable"),
        raising=False,
    )
    receipt_path = tmp_path / f"{status}.json"

    actual_exit_code = cli.main(
        ["--run-once", "--receipt-path", str(receipt_path)]
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert actual_exit_code == expected_exit_code
    assert receipt["exit_code"] == actual_exit_code
    assert receipt["commit_sha"] is None
    assert receipt["warnings"] == ["commit SHA unavailable"]


def test_cli_enqueue_receipt_is_only_queued_acknowledgement(monkeypatch, tmp_path) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Message:
        message_id = "queued-1"

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def send(self, **kwargs):
            assert kwargs == {"include_cffex": True}
            return _Message()

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(
        cli,
        "_resolve_commit_sha",
        lambda: ("0123456789abcdef", None),
        raising=False,
    )
    receipt_path = tmp_path / "queued.json"

    assert (
        cli.main(
            [
                "--enqueue",
                "--run-kind",
                "scheduled",
                "--receipt-path",
                str(receipt_path),
            ]
        )
        == 0
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["invocation_mode"] == "enqueue"
    assert receipt["status"] == "queued"
    assert receipt["result"] == {
        "status": "queued",
        "actor": "refresh_macro_toolkit_freshness",
        "message_id": "queued-1",
    }


def test_cli_receipt_write_failure_is_nonzero_and_safe(monkeypatch, tmp_path, capsys) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs):
            return {
                "status": "success",
                "source_version": "macro_toolkit_freshness_refresh_v3",
            }

    def fail_write(_path, _receipt) -> None:
        raise OSError("simulated receipt write failure")

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(
        cli,
        "_resolve_commit_sha",
        lambda: ("0123456789abcdef", None),
        raising=False,
    )
    monkeypatch.setattr(cli, "_write_receipt_atomic", fail_write, raising=False)

    assert (
        cli.main(["--run-once", "--receipt-path", str(tmp_path / "receipt.json")])
        == 1
    )
    captured = capsys.readouterr()
    assert "receipt" in captured.err.lower()
    assert "traceback" not in captured.err.lower()


def test_skip_cffex_help_names_all_remaining_steps() -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    help_text = cli._parser().format_help().lower()
    skip_line = next(line for line in help_text.splitlines() if "skip cffex" in line)
    assert "commodity" in skip_line
    assert "headlines" in skip_line
    assert "ncd" in skip_line
