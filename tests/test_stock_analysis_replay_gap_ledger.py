from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _load_module():
    return load_module(
        "scripts.stock_analysis_replay_gap_ledger",
        "scripts/stock_analysis_replay_gap_ledger.py",
    )


def _create_db(path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          tradestatus varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_request_audit (
          run_id varchar,
          as_of_date varchar,
          input_family varchar,
          field_key varchar,
          call varchar,
          vendor_indicator varchar,
          request_arguments_json varchar,
          request_options_json varchar,
          status varchar,
          row_count integer,
          error_code integer,
          error_msg varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar
        )
        """
    )
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          signal_kind varchar,
          theme_source_kind varchar,
          forward_trade_date_1d varchar,
          forward_trade_date_5d varchar,
          forward_trade_date_10d varchar,
          forward_trade_date_20d varchar,
          return_1d double,
          return_5d double,
          return_10d double,
          return_20d double,
          return_1d_adj double,
          return_5d_adj double,
          return_10d_adj double,
          return_20d_adj double,
          data_status varchar,
          formula_version varchar,
          rule_version varchar,
          run_id varchar,
          signal_evidence_json varchar
        )
        """
    )
    conn.execute(
        """
        create table livermore_candidate_execution_history (
          signal_date varchar,
          stock_code varchar,
          signal_kind varchar,
          entry_executable boolean,
          entry_date varchar,
          exit_date_5d varchar,
          exit_date_20d varchar,
          return_5d_net_adj double,
          return_20d_net_adj double,
          formula_version varchar,
          run_id varchar
        )
        """
    )
    conn.execute(
        """
        create table livermore_matched_baseline_history (
          signal_date varchar,
          candidate_stock_code varchar,
          signal_kind varchar,
          control_stock_code varchar,
          control_group varchar,
          seed varchar,
          control_entry_executable boolean,
          control_return_5d_net_adj double,
          control_return_20d_net_adj double,
          formula_version varchar,
          run_id varchar
        )
        """
    )
    return conn


def _seed_trade_dates(conn: duckdb.DuckDBPyConnection) -> None:
    stock_codes = (
        "000001.SZ",
        "000002.SZ",
        "000003.SZ",
        "000004.SZ",
        "000005.SZ",
        "000010.SZ",
        "000012.SZ",
    )
    rows = [
        (f"2026-05-{day:02d}", stock_code, 10.0 + day, "交易")
        for day in range(1, 32)
        for stock_code in stock_codes
    ]
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?)",
        rows,
    )
    required_items = [
        ("stock_universe", "a_share_universe_sector_001004"),
        ("sector_membership", "sw2021_industry_membership"),
        ("sector_strength", "daily_return_turnover_amplitude"),
        ("stock_ohlcv", "daily_ohlcv_amount"),
        ("stock_status", "daily_trade_status"),
        ("limit_up_quality", "daily_limit_flags"),
        ("limit_up_quality", "point_in_time_limit_streaks"),
    ]
    audit_rows: list[tuple[str, str, str, str, str, str, str, str, int, int | None, str | None, str, str, str, str]] = []
    for day in range(1, 32):
        trade_date = f"2026-05-{day:02d}"
        for input_family, field_key in required_items:
            status = "completed"
            run_id = "run-main"
            source_version = "sv-main"
            rule_version = "rv-main"
            if trade_date == "2026-05-10" and field_key == "daily_ohlcv_amount":
                status = "completed_tushare_fallback"
                run_id = "run-fallback"
                source_version = "sv-fallback"
                rule_version = "rv-fallback"
            if trade_date == "2026-05-12" and field_key == "daily_trade_status":
                run_id = "run-mixed"
                source_version = "sv-mixed"
                rule_version = "rv-mixed"
            audit_rows.append(
                (
                    run_id,
                    trade_date,
                    input_family,
                    field_key,
                    "css",
                    field_key,
                    "[]",
                    "{}",
                    status,
                    1,
                    None,
                    None,
                    source_version,
                    "vv-test",
                    rule_version,
                )
            )
    audit_rows.append(
        (
            "run-fallback",
            "2026-05-11",
            "stock_ohlcv",
            "daily_ohlcv_amount",
            "css",
            "daily_ohlcv_amount",
            "[]",
            "{}",
            "completed_tushare_fallback",
            1,
            None,
            None,
            "sv-fallback",
            "vv-test",
            "rv-fallback",
        )
    )
    conn.executemany(
        "insert into choice_stock_request_audit values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        audit_rows,
    )


def _seed_candidate_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
    stock_code: str,
    signal_kind: str = "stock_candidate",
    data_status: str = "complete",
    formula_version: str = "fv_candidate_task",
    rule_version: str = "rv_candidate_history_current",
    run_id: str = "run-current",
    selection_formula_version: str | None = "rv_stock_candidate_current",
    selection_policy: str | None = "exp3b",
    theme_source_kind: str | None = None,
) -> None:
    evidence: dict[str, object] = {}
    if selection_formula_version is not None:
        evidence["selection_formula_version"] = selection_formula_version
    if selection_policy is not None:
        evidence["selection_policy"] = selection_policy
    if theme_source_kind is not None:
        evidence["theme_source_kind"] = theme_source_kind
    trade_day = date.fromisoformat(trade_date)
    forward_trade_date_1d = trade_day + timedelta(days=1)
    forward_trade_date_5d = trade_day + timedelta(days=5)
    forward_trade_date_10d = trade_day + timedelta(days=10)
    forward_trade_date_20d = trade_day + timedelta(days=20)
    conn.execute(
        """
        insert into livermore_candidate_history (
          snapshot_as_of_date,
          stock_code,
          signal_kind,
          theme_source_kind,
          forward_trade_date_1d,
          forward_trade_date_5d,
          forward_trade_date_10d,
          forward_trade_date_20d,
          return_1d,
          return_5d,
          return_10d,
          return_20d,
          return_1d_adj,
          return_5d_adj,
          return_10d_adj,
          return_20d_adj,
          data_status,
          formula_version,
          rule_version,
          run_id,
          signal_evidence_json
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            trade_date,
            stock_code,
            signal_kind,
            theme_source_kind,
            forward_trade_date_1d.isoformat(),
            forward_trade_date_5d.isoformat(),
            forward_trade_date_10d.isoformat(),
            forward_trade_date_20d.isoformat(),
            0.01,
            0.03,
            0.05,
            0.08,
            0.01,
            0.03,
            0.05,
            0.08,
            data_status,
            formula_version,
            rule_version,
            run_id,
            json.dumps(evidence, ensure_ascii=False),
        ],
    )


def _seed_execution_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_date: str,
    stock_code: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
    formula_version: str = "fv_execution_current",
    run_id: str = "run-exec-current",
    return_5d: float | None = 0.03,
    return_20d: float | None = 0.08,
    entry_executable: bool = True,
) -> None:
    conn.execute(
        "insert into livermore_candidate_execution_history values (?, ?, 'stock_candidate', ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            signal_date,
            stock_code,
            entry_executable,
            entry_date,
            exit_date_5d,
            exit_date_20d,
            return_5d,
            return_20d,
            formula_version,
            run_id,
        ],
    )


def _seed_baseline_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_date: str,
    stock_code: str,
    control_stock_code: str = "399001.SZ",
    control_group: str = "same_sector",
    seed: str = "seed-1",
    formula_version: str = "fv_baseline_current",
    run_id: str = "run-baseline-current",
    return_5d: float | None = 0.01,
    return_20d: float | None = 0.02,
    entry_executable: bool = True,
) -> None:
    conn.execute(
        "insert into livermore_matched_baseline_history values (?, ?, 'stock_candidate', ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            signal_date,
            stock_code,
            control_stock_code,
            control_group,
            seed,
            entry_executable,
            return_5d,
            return_20d,
            formula_version,
            run_id,
        ],
    )


def _coverage_loader():
    coverage_by_date = {
        "2026-05-04": SimpleNamespace(
            full_coverage=False,
            missing_request_items=["stock_universe:required"],
            status="missing",
        ),
        "2026-05-05": SimpleNamespace(
            full_coverage=False,
            missing_request_items=["stock_universe:required"],
            status="missing",
        ),
    }

    def _load(**kwargs):
        as_of_date = kwargs["as_of_date"]
        return coverage_by_date.get(
            as_of_date,
            SimpleNamespace(full_coverage=True, missing_request_items=[], status="ready"),
        )

    return _load


def _current_rule_contract() -> dict[str, object]:
    return {
        "signal_kind": "stock_candidate",
        "metric_basis": "net_next_open_adj",
        "candidate_history_rule_version": "rv_candidate_history_current",
        "candidate_history_formula_version": "fv_candidate_task",
        "stock_candidate_formula_version": "rv_stock_candidate_current",
        "selection_policy": "exp3b",
        "execution_formula_version": "fv_execution_current",
        "matched_baseline_formula_version": "fv_baseline_current",
        "stock_candidate_formula_resolution": "signal_evidence.selection_formula_version -> row.formula_version",
        "macro_series": {
            "pmi_series_id": "M0017126",
            "credit_proxy_series_id": "M5525763",
            "degraded_display_proxy_series_id": "M0001385",
        },
    }


def _seed_main_fixture(conn: duckdb.DuckDBPyConnection) -> None:
    _seed_trade_dates(conn)
    _seed_candidate_row(
        conn,
        trade_date="2026-05-02",
        stock_code="000001.SZ",
    )
    _seed_execution_row(
        conn,
        signal_date="2026-05-02",
        stock_code="000001.SZ",
        entry_date="2026-05-03",
        exit_date_5d="2026-05-08",
        exit_date_20d="2026-05-22",
    )
    _seed_baseline_row(conn, signal_date="2026-05-02", stock_code="000001.SZ")

    _seed_candidate_row(
        conn,
        trade_date="2026-05-03",
        stock_code="000002.SZ",
        rule_version="rv_candidate_history_legacy",
        run_id="run-legacy",
        selection_formula_version="rv_stock_candidate_legacy",
    )
    _seed_execution_row(
        conn,
        signal_date="2026-05-03",
        stock_code="000002.SZ",
        entry_date="2026-05-04",
        exit_date_5d="2026-05-09",
        exit_date_20d="2026-06-05",
        formula_version="fv_execution_legacy",
        run_id="run-exec-legacy",
    )
    _seed_baseline_row(
        conn,
        signal_date="2026-05-03",
        stock_code="000002.SZ",
        formula_version="fv_baseline_legacy",
        run_id="run-baseline-legacy",
    )

    _seed_candidate_row(
        conn,
        trade_date="2026-05-04",
        stock_code="000003.SZ",
    )

    _seed_candidate_row(
        conn,
        trade_date="2026-05-10",
        stock_code="000010.SZ",
    )
    _seed_execution_row(
        conn,
        signal_date="2026-05-10",
        stock_code="000010.SZ",
        entry_date="2026-05-11",
        exit_date_5d="2026-05-16",
        exit_date_20d="2026-05-30",
    )
    _seed_baseline_row(conn, signal_date="2026-05-10", stock_code="000010.SZ")

    _seed_candidate_row(
        conn,
        trade_date="2026-05-12",
        stock_code="000012.SZ",
    )
    _seed_execution_row(
        conn,
        signal_date="2026-05-12",
        stock_code="000012.SZ",
        entry_date="2026-05-13",
        exit_date_5d="2026-05-18",
        exit_date_20d="2026-05-31",
    )
    _seed_baseline_row(conn, signal_date="2026-05-12", stock_code="000012.SZ")

    _seed_candidate_row(
        conn,
        trade_date="2026-05-06",
        stock_code="000004.SZ",
        signal_kind="theme_breakout",
        selection_formula_version=None,
        theme_source_kind="proxy",
    )

    _seed_candidate_row(
        conn,
        trade_date="2026-05-30",
        stock_code="000005.SZ",
        data_status="pending",
    )


def test_gap_ledger_uses_read_only_duckdb_connect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_trade_dates(conn)
        conn.execute("drop table choice_stock_request_audit")
    finally:
        conn.close()

    original_connect = module.duckdb.connect
    captured: dict[str, object] = {}
    loader_calls: list[dict[str, object]] = []

    def _capturing_connect(*args, **kwargs):
        captured["read_only"] = kwargs.get("read_only")
        captured["connect_count"] = int(captured.get("connect_count", 0)) + 1
        return original_connect(*args, **kwargs)

    def _loader(**kwargs):
        loader_calls.append(kwargs)
        return SimpleNamespace(full_coverage=True, missing_request_items=[], status="ready")

    monkeypatch.setattr(module.duckdb, "connect", _capturing_connect)
    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", _loader)

    module.build_stock_analysis_replay_gap_ledger(
        duckdb_path=db_path,
        evaluation_date="2026-05-31",
        current_rule_contract=_current_rule_contract(),
    )

    assert captured["read_only"] is True
    assert captured["connect_count"] == 1
    assert loader_calls
    assert all("conn" in call and call["conn"] is not None for call in loader_calls)


def test_trade_dates_fall_back_to_candidate_history_when_observation_table_is_missing(
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              signal_kind varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?, ?)",
            [
                ("2026-05-03", "000003.SZ", "stock_candidate"),
                ("2026-05-01", "000001.SZ", "stock_candidate"),
                ("2026-05-02", "000002.SZ", "stock_candidate"),
            ],
        )
        tables = module._table_names(conn)
        bundle = module._load_trade_dates(
            conn,
            tables=tables,
            requested_start="2026-05-01",
            evaluation_date="2026-05-03",
        )
    finally:
        conn.close()

    assert bundle["trade_dates"] == ["2026-05-01", "2026-05-02", "2026-05-03"]
    assert bundle["calendar_authority"] == "candidate_history_fallback"
    assert bundle["calendar_verifiable"] is False
    assert "not an official trading calendar" in bundle["calendar_residual_risk"]


def test_trade_dates_report_unavailable_when_no_observed_calendar_source_exists(
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table unrelated_table (id integer)")
        bundle = module._load_trade_dates(
            conn,
            tables=module._table_names(conn),
            requested_start="2026-05-01",
            evaluation_date="2026-05-03",
        )
    finally:
        conn.close()

    assert bundle["trade_dates"] == []
    assert bundle["calendar_authority"] == "unavailable"
    assert bundle["calendar_verifiable"] is False
    assert bundle["calendar_residual_risk"] == "no observed trade-date authority is available"


@pytest.mark.parametrize("audit_window_months", [0, 25])
def test_gap_ledger_rejects_audit_windows_outside_prd_boundary(
    tmp_path: Path,
    audit_window_months: int,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    conn.close()

    with pytest.raises(ValueError, match="between 1 and 24"):
        module.build_stock_analysis_replay_gap_ledger(
            duckdb_path=db_path,
            evaluation_date="2026-05-31",
            audit_window_months=audit_window_months,
            current_rule_contract=_current_rule_contract(),
        )


def test_gap_ledger_tracks_versions_and_certifiable_capacity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_main_fixture(conn)
    finally:
        conn.close()

    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", _coverage_loader())
    report = module.build_stock_analysis_replay_gap_ledger(
        duckdb_path=db_path,
        evaluation_date="2026-05-31",
        current_rule_contract=_current_rule_contract(),
    )

    counts = report["date_state_summary"]["counts"]
    assert report["date_state_summary"]["scope"] == (
        "observational_as_produced_all_signal_kinds_and_versions"
    )
    assert report["date_state_summary"]["formal_use_allowed"] is False
    assert counts["completed_with_signals"] == 3
    assert counts["completed_no_strategy_signals"] == 0
    assert counts["unsupported"] == 25
    assert counts["proxy_only"] == 1
    assert counts["pending_tail"] == 2
    assert counts["blocking_pending"] == 0

    unsupported_signal_dates = report["date_state_summary"]["unsupported_signal_dates"]
    unsupported_no_signal_dates = report["date_state_summary"]["unsupported_no_signal_dates"]
    assert [item["trade_date"] for item in unsupported_signal_dates] == ["2026-05-04"]
    assert len(unsupported_no_signal_dates) == 24
    missing_receipt_dates = [
        item for item in unsupported_no_signal_dates
        if item["reason_code"] == "missing_candidate_history_receipt"
    ]
    assert len(missing_receipt_dates) == 23
    assert all(item["date_state"] == "unsupported" for item in missing_receipt_dates)
    assert next(
        item for item in unsupported_no_signal_dates if item["trade_date"] == "2026-05-05"
    )["reason_code"] == "missing_required_source_table"

    stale = report["stale_versions"]
    assert stale["candidate_history_rule_stale_row_count"] == 1
    assert stale["candidate_history_formula_stale_row_count"] == 0
    assert stale["stock_candidate_selection_formula_stale_row_count"] == 1
    assert stale["execution_formula_stale_row_count"] == 1
    assert stale["matched_baseline_formula_stale_row_count"] == 1

    coverage_views = report["coverage_views"]
    strict_view = coverage_views["strict_completed_only"]
    fallback_view = coverage_views["completed_plus_fallback"]
    assert strict_view["earliest_full_coverage_date"] == "2026-05-01"
    assert strict_view["longest_continuous_eligible_streak"] == 21
    assert strict_view["fallback_covered_date_count"] == 0
    assert "2026-05-10" not in strict_view["eligible_dates"]
    assert strict_view["coverage_lineage_verifiable"] is True
    assert strict_view["continuity_certifiable"] is False
    assert strict_view["mixed_lineage_dates"] == ["2026-05-10", "2026-05-12"]
    assert strict_view["incomplete_lineage_dates"] == []
    assert fallback_view["earliest_full_coverage_date"] == "2026-05-01"
    assert fallback_view["longest_continuous_eligible_streak"] == 31
    assert fallback_view["fallback_covered_date_count"] == 1
    assert fallback_view["fallback_covered_dates"] == ["2026-05-10"]
    assert "2026-05-11" in strict_view["eligible_dates"]
    detail_0510 = next(item for item in report["date_state_summary"]["dates"] if item["trade_date"] == "2026-05-10")
    assert detail_0510["coverage_views"] == {
        "strict_completed_only": False,
        "completed_plus_fallback": True,
        "fallback_covered": True,
    }
    detail_0512 = next(item for item in report["date_state_summary"]["dates"] if item["trade_date"] == "2026-05-12")
    assert detail_0512["raw_status"] == "pending"
    assert detail_0512["reason_code"] == "forward_returns_pending"
    assert detail_0512["coverage_views"] == {
        "strict_completed_only": True,
        "completed_plus_fallback": True,
        "fallback_covered": False,
    }

    duplicate_audit = report["duplicate_audit"]
    assert duplicate_audit["candidate_history"]["as_produced"]["duplicate_key_count"] == 0
    assert duplicate_audit["candidate_history"]["current_rule_strict_window"]["duplicate_key_count"] == 0
    assert duplicate_audit["execution_history"]["as_produced"]["duplicate_key_count"] == 0
    assert duplicate_audit["execution_history"]["current_rule_strict_window"]["duplicate_key_count"] == 0
    assert duplicate_audit["matched_baseline_history"]["as_produced"]["duplicate_key_count"] == 0
    assert duplicate_audit["matched_baseline_history"]["current_rule_strict_window"]["duplicate_key_count"] == 0

    capacity = report["current_rule_certifiable_capacity"]
    assert capacity["pit_verifiability"]["matched_baseline"] == "unavailable_missing_exit_dates"
    assert capacity["potential_matched_entry_count"] == 0
    assert capacity["potential_current_rule_signal_dates"] == []
    assert capacity["matched_entry_count"] == 0
    assert capacity["current_rule_certifiable_signal_dates"] == []
    assert capacity["completed_date_capacity"] == 0
    assert capacity["potential_completed_date_capacity_including_no_signal"] == 0
    assert capacity["strict_coverage_only"] is True
    assert capacity["estimated_materialization"] == {
        "status": "unavailable",
        "replay_fact_row_count": None,
        "date_certificate_row_count": None,
        "reason": "current_rule_replay_plan_and_authoritative_calendar_required",
    }
    assert "current_rule_certified_cohort_not_materialized" in capacity["blockers"]
    assert "matched_baseline_pit_proof_unavailable" in capacity["blockers"]
    assert "zero_signal_receipt_not_persisted" in capacity["blockers"]
    assert "insufficient_potential_completed_dates" in capacity["blockers"]
    assert "insufficient_potential_matched_entries" in capacity["blockers"]
    assert "calendar_authority_unavailable" in capacity["blockers"]
    assert "mixed_run_or_lineage_dates_present" in capacity["blockers"]


def test_gap_ledger_marks_unknown_eligible_lineage_unverifiable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_trade_dates(conn)
        conn.execute(
            """
            update choice_stock_request_audit
            set source_version = null
            where as_of_date = '2026-05-13'
              and input_family = 'stock_status'
              and field_key = 'daily_trade_status'
            """
        )
    finally:
        conn.close()

    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", _coverage_loader())
    report = module.build_stock_analysis_replay_gap_ledger(
        duckdb_path=db_path,
        evaluation_date="2026-05-31",
        current_rule_contract=_current_rule_contract(),
    )

    strict_view = report["coverage_views"]["strict_completed_only"]
    fallback_view = report["coverage_views"]["completed_plus_fallback"]
    assert strict_view["coverage_lineage_verifiable"] is False
    assert fallback_view["coverage_lineage_verifiable"] is False
    assert strict_view["incomplete_lineage_dates"] == ["2026-05-13"]
    assert fallback_view["incomplete_lineage_dates"] == ["2026-05-13"]


def test_wrong_policy_and_other_signal_kind_do_not_enter_current_capacity() -> None:
    module = _load_module()
    contract = _current_rule_contract()
    coverage_views = {
        "strict_completed_only": {
            "eligible_dates": ["2026-05-02", "2026-05-03", "2026-05-04"],
            "coverage_lineage_verifiable": True,
            "mixed_lineage_dates": [],
        },
        "completed_plus_fallback": {"eligible_dates": []},
    }
    wrong_policy_candidate = {
        "snapshot_as_of_date": "2026-05-02",
        "stock_code": "000001.SZ",
        "signal_kind": "stock_candidate",
        "formula_version": "fv_candidate_task",
        "rule_version": "rv_candidate_history_current",
        "signal_evidence_json": {
            "selection_formula_version": "rv_stock_candidate_current",
            "selection_policy": "default",
        },
    }
    candidate_rows = [
        wrong_policy_candidate,
        dict(wrong_policy_candidate),
        {
            "snapshot_as_of_date": "2026-05-03",
            "stock_code": "000002.SZ",
            "signal_kind": "theme_breakout",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_current",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_current",
                "selection_policy": "exp3b",
            },
        },
        {
            "snapshot_as_of_date": "2026-05-04",
            "stock_code": "000003.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_current",
            "selection_policy": "default",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_current",
                "selection_policy": "exp3b",
            },
        },
    ]
    execution_rows = [
        {
            "signal_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-03",
            "exit_date_5d": "2026-05-08",
            "exit_date_20d": "2026-05-22",
            "return_5d_net_adj": 0.03,
            "return_20d_net_adj": 0.08,
        },
        {
            "signal_date": "2026-05-03",
            "stock_code": "000002.SZ",
            "signal_kind": "theme_breakout",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-04",
            "exit_date_5d": "2026-05-09",
            "exit_date_20d": "2026-05-23",
            "return_5d_net_adj": 0.03,
            "return_20d_net_adj": 0.08,
        },
        {
            "signal_date": "2026-05-04",
            "stock_code": "000003.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-05",
            "exit_date_5d": "2026-05-10",
            "exit_date_20d": "2026-05-24",
            "return_5d_net_adj": 0.03,
            "return_20d_net_adj": 0.08,
        },
    ]
    duplicate_audit = module._build_duplicate_audit(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=[],
        contract=contract,
        coverage_views=coverage_views,
    )

    assert duplicate_audit["candidate_history"]["as_produced"]["duplicate_key_count"] == 1
    assert (
        duplicate_audit["candidate_history"]["current_rule_strict_window"][
            "duplicate_key_count"
        ]
        == 0
    )

    capacity = module._build_current_rule_capacity(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=[],
        date_detail={
            "dates": [
                {"trade_date": "2026-05-02", "date_state": "completed_with_signals"},
                {"trade_date": "2026-05-03", "date_state": "completed_with_signals"},
                {
                    "trade_date": "2026-05-04",
                    "date_state": "completed_no_strategy_signals",
                },
            ]
        },
        evaluation_date="2026-05-31",
        contract=contract,
        coverage_views=coverage_views,
        duplicate_audit=duplicate_audit,
        calendar_verifiable=True,
    )["current_rule_certifiable_capacity"]

    assert capacity["current_rule_candidate_row_count"] == 0
    assert capacity["potential_matched_entry_count"] == 0
    assert capacity["potential_current_rule_signal_dates"] == []
    assert capacity["potential_completed_no_strategy_signal_date_count"] == 0


def test_mature_current_candidate_execution_contributes_without_baseline() -> None:
    module = _load_module()
    contract = _current_rule_contract()
    coverage_views = {
        "strict_completed_only": {
            "eligible_dates": ["2026-05-02"],
            "coverage_lineage_verifiable": True,
            "mixed_lineage_dates": [],
        },
        "completed_plus_fallback": {"eligible_dates": []},
    }
    candidate_rows = [
        {
            "snapshot_as_of_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_current",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_current",
                "selection_policy": "exp3b",
            },
        }
    ]
    execution_rows = [
        {
            "signal_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-03",
            "exit_date_5d": "2026-05-08",
            "exit_date_20d": "2026-05-22",
            "return_5d_net_adj": 0.03,
            "return_20d_net_adj": 0.08,
        }
    ]
    duplicate_audit = module._build_duplicate_audit(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=[],
        contract=contract,
        coverage_views=coverage_views,
    )
    capacity = module._build_current_rule_capacity(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=[],
        date_detail={"dates": [{"trade_date": "2026-05-02", "date_state": "unsupported"}]},
        evaluation_date="2026-05-31",
        contract=contract,
        coverage_views=coverage_views,
        duplicate_audit=duplicate_audit,
        calendar_verifiable=True,
    )["current_rule_certifiable_capacity"]

    assert capacity["current_rule_matched_baseline_row_count"] == 0
    assert capacity["potential_matched_entry_count"] == 1
    assert capacity["potential_current_rule_signal_dates"] == ["2026-05-02"]
    assert capacity["potential_completed_date_capacity_including_no_signal"] == 1
    assert capacity["threshold_progress"]["completed_dates_potential"] == 1
    assert capacity["threshold_progress"]["matched_entries_potential"] == 1
    assert capacity["matched_entry_count"] == 0
    assert capacity["completed_date_capacity"] == 0
    assert "matched_baseline_pit_proof_unavailable" in capacity["blockers"]
    assert "zero_signal_receipt_not_persisted" in capacity["blockers"]


def test_unmatched_candidate_and_execution_duplicates_do_not_block_current_tuple() -> None:
    module = _load_module()
    contract = _current_rule_contract()
    coverage_views = {
        "strict_completed_only": {
            "eligible_dates": ["2026-05-02"],
            "coverage_lineage_verifiable": True,
            "mixed_lineage_dates": [],
        },
        "completed_plus_fallback": {"eligible_dates": []},
    }
    candidate_rows = [
        {
            "snapshot_as_of_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_current",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_current",
                "selection_policy": "exp3b",
            },
        },
        {
            "snapshot_as_of_date": "2026-05-01",
            "stock_code": "000009.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_legacy",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_legacy",
                "selection_policy": "default",
            },
        },
        {
            "snapshot_as_of_date": "2026-05-01",
            "stock_code": "000009.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_legacy",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_legacy",
                "selection_policy": "default",
            },
        },
    ]
    execution_rows = [
        {
            "signal_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-03",
            "exit_date_5d": "2026-05-08",
            "exit_date_20d": "2026-05-22",
            "return_5d_net_adj": 0.03,
            "return_20d_net_adj": 0.08,
        },
        {
            "signal_date": "2026-05-02",
            "stock_code": "000009.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-03",
            "exit_date_5d": "2026-05-08",
            "exit_date_20d": "2026-05-22",
            "return_5d_net_adj": 0.01,
            "return_20d_net_adj": 0.02,
        },
        {
            "signal_date": "2026-05-02",
            "stock_code": "000009.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-03",
            "exit_date_5d": "2026-05-08",
            "exit_date_20d": "2026-05-22",
            "return_5d_net_adj": 0.01,
            "return_20d_net_adj": 0.02,
        },
    ]
    baseline_rows = [
        {
            "signal_date": "2026-05-02",
            "candidate_stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "control_stock_code": "399001.SZ",
            "control_group": "same_sector",
            "seed": "seed-1",
            "formula_version": "fv_baseline_current",
            "control_entry_executable": True,
            "control_return_5d_net_adj": 0.01,
            "control_return_20d_net_adj": 0.02,
        }
    ]
    duplicate_audit = module._build_duplicate_audit(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        contract=contract,
        coverage_views=coverage_views,
    )

    assert duplicate_audit["candidate_history"]["as_produced"]["duplicate_key_count"] == 1
    assert duplicate_audit["candidate_history"]["current_rule_strict_window"]["duplicate_key_count"] == 0
    assert duplicate_audit["execution_history"]["as_produced"]["duplicate_key_count"] == 1
    assert duplicate_audit["execution_history"]["current_rule_strict_window"]["duplicate_key_count"] == 0

    capacity = module._build_current_rule_capacity(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        date_detail={"dates": [{"trade_date": "2026-05-02", "date_state": "completed_with_signals"}]},
        evaluation_date="2026-05-31",
        contract=contract,
        coverage_views=coverage_views,
        duplicate_audit=duplicate_audit,
        calendar_verifiable=True,
    )

    assert "duplicate_keys:candidate_history" not in capacity["current_rule_certifiable_capacity"]["blockers"]
    assert "duplicate_keys:execution_history" not in capacity["current_rule_certifiable_capacity"]["blockers"]
    assert capacity["current_rule_certifiable_capacity"]["potential_matched_entry_count"] == 1


def test_current_tuple_candidate_duplicates_block_current_potential() -> None:
    module = _load_module()
    contract = _current_rule_contract()
    coverage_views = {
        "strict_completed_only": {
            "eligible_dates": ["2026-05-02"],
            "coverage_lineage_verifiable": True,
            "mixed_lineage_dates": [],
        },
        "completed_plus_fallback": {"eligible_dates": []},
    }
    candidate_rows = [
        {
            "snapshot_as_of_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_current",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_current",
                "selection_policy": "exp3b",
            },
        },
        {
            "snapshot_as_of_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_candidate_task",
            "rule_version": "rv_candidate_history_current",
            "signal_evidence_json": {
                "selection_formula_version": "rv_stock_candidate_current",
                "selection_policy": "exp3b",
            },
        },
    ]
    execution_rows = [
        {
            "signal_date": "2026-05-02",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "formula_version": "fv_execution_current",
            "entry_executable": True,
            "entry_date": "2026-05-03",
            "exit_date_5d": "2026-05-08",
            "exit_date_20d": "2026-05-22",
            "return_5d_net_adj": 0.03,
            "return_20d_net_adj": 0.08,
        }
    ]
    baseline_rows = [
        {
            "signal_date": "2026-05-02",
            "candidate_stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "control_stock_code": "399001.SZ",
            "control_group": "same_sector",
            "seed": "seed-1",
            "formula_version": "fv_baseline_current",
            "control_entry_executable": True,
            "control_return_5d_net_adj": 0.01,
            "control_return_20d_net_adj": 0.02,
        }
    ]
    duplicate_audit = module._build_duplicate_audit(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        contract=contract,
        coverage_views=coverage_views,
    )

    assert duplicate_audit["candidate_history"]["current_rule_strict_window"]["duplicate_key_count"] == 1

    capacity = module._build_current_rule_capacity(
        candidate_rows=candidate_rows,
        execution_rows=execution_rows,
        baseline_rows=baseline_rows,
        date_detail={"dates": [{"trade_date": "2026-05-02", "date_state": "completed_with_signals"}]},
        evaluation_date="2026-05-31",
        contract=contract,
        coverage_views=coverage_views,
        duplicate_audit=duplicate_audit,
        calendar_verifiable=True,
    )

    assert "duplicate_keys:candidate_history" in capacity["current_rule_certifiable_capacity"]["blockers"]
    assert capacity["current_rule_certifiable_capacity"]["potential_matched_entry_count"] == 0


def test_gap_ledger_masks_lookahead_complete_rows_to_pending(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_trade_dates(conn)
        _seed_candidate_row(
            conn,
            trade_date="2026-05-20",
            stock_code="000001.SZ",
            data_status="complete",
        )
    finally:
        conn.close()

    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", _coverage_loader())
    report = module.build_stock_analysis_replay_gap_ledger(
        duckdb_path=db_path,
        evaluation_date="2026-05-31",
        current_rule_contract=_current_rule_contract(),
    )

    detail = next(item for item in report["date_state_summary"]["dates"] if item["trade_date"] == "2026-05-20")
    assert detail["row_count"] == 1
    assert detail["raw_status"] == "pending"
    assert detail["date_state"] == "pending_tail"
    assert detail["reason_code"] == "forward_returns_pending"


def test_gap_ledger_pit_capacity_excludes_future_exit_dates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_trade_dates(conn)
        _seed_candidate_row(conn, trade_date="2026-05-02", stock_code="000001.SZ")
        _seed_candidate_row(conn, trade_date="2026-05-03", stock_code="000002.SZ")
        _seed_execution_row(
            conn,
            signal_date="2026-05-02",
            stock_code="000001.SZ",
            entry_date="2026-05-03",
            exit_date_5d="2026-05-08",
            exit_date_20d="2026-05-22",
        )
        _seed_execution_row(
            conn,
            signal_date="2026-05-03",
            stock_code="000002.SZ",
            entry_date="2026-05-04",
            exit_date_5d="2026-05-09",
            exit_date_20d="2026-06-05",
        )
        _seed_baseline_row(conn, signal_date="2026-05-02", stock_code="000001.SZ")
        _seed_baseline_row(conn, signal_date="2026-05-03", stock_code="000002.SZ")
    finally:
        conn.close()

    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", _coverage_loader())
    report = module.build_stock_analysis_replay_gap_ledger(
        duckdb_path=db_path,
        evaluation_date="2026-05-31",
        current_rule_contract=_current_rule_contract(),
    )

    pit_capacity = report["pit_capacity"]
    assert pit_capacity["stock_candidate_dual_horizon_row_count"] == 1
    assert pit_capacity["stock_candidate_current_formula_dual_horizon_row_count"] == 1


def test_gap_ledger_cli_supports_json_and_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_trade_dates(conn)
    finally:
        conn.close()

    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", _coverage_loader())

    json_exit = module.main(
        [
            "--duckdb-path",
            str(db_path),
            "--evaluation-date",
            "2026-05-31",
            "--format",
            "json",
        ]
    )
    json_output = capsys.readouterr().out
    assert json_exit == 0
    assert '"page_route": "/stock-analysis"' in json_output

    markdown_exit = module.main(
        [
            "--duckdb-path",
            str(db_path),
            "--evaluation-date",
            "2026-05-31",
            "--format",
            "markdown",
        ]
    )
    markdown_output = capsys.readouterr().out
    assert markdown_exit == 0
    assert "# Stock Analysis Replay Gap Ledger Summary" in markdown_output
    assert "Use JSON output for the complete per-date evidence ledger" in markdown_output
    assert "## Current Rule Capacity" in markdown_output
    assert "Estimated materialization: unavailable" in markdown_output
    assert "Blockers: current_rule_certified_cohort_not_materialized" in markdown_output
