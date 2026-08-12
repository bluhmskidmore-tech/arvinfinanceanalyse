from __future__ import annotations

import importlib
import json
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from typing import cast

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.candidate_history_proxy_backtest import (
    CYCLE_PROXY_ENTRY_PRICE_WARNING,
    PORTFOLIO_PROXY_ENTRY_PRICE_WARNING,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_backtest_window_summary,
    livermore_candidate_history_cycle_proxy_backtest_envelope,
    livermore_candidate_history_envelope,
    livermore_candidate_history_portfolio_backtest_envelope,
)
from backend.app.tasks.livermore_candidate_history_materialize import (
    backfill_livermore_candidate_execution_history,
    backfill_livermore_candidate_history,
    ensure_livermore_candidate_history_schema,
    materialize_livermore_candidate_history,
)
from tests.helpers import load_module

_LIVERMORE_CANDIDATE_HISTORY_TASK_MODULE = sys.modules[materialize_livermore_candidate_history.__module__]


def _ensure_livermore_candidate_history_test_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Test schema bootstrap: production registry omits universe_history on fresh DBs."""
    conn.execute(
        """
        create table if not exists livermore_stock_candidate_universe_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          sector_code varchar,
          sector_name varchar,
          sector_rank integer,
          selection_close double,
          close_strength double,
          gap_norm double,
          breakout_extension_norm double,
          abnormal_turnover double,
          breakout_level double,
          ema10 double,
          ma20 double,
          ma60 double,
          ma120 double,
          old_rank integer,
          new_rank integer,
          eligible_before_truncation boolean,
          selected_old_top6 boolean,
          selected_new_top6 boolean,
          forward_trade_date_1d varchar,
          forward_trade_date_5d varchar,
          forward_trade_date_10d varchar,
          forward_trade_date_20d varchar,
          return_1d double,
          return_5d double,
          return_10d double,
          return_20d double,
          market_state varchar,
          data_status varchar,
          formula_version varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar,
          evidence_json varchar
        )
        """
    )
    ensure_livermore_candidate_history_schema(conn)


@pytest.fixture(autouse=True)
def _patch_livermore_candidate_history_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "backend.app.tasks.livermore_candidate_history_materialize",
        _LIVERMORE_CANDIDATE_HISTORY_TASK_MODULE,
    )
    tasks_package = sys.modules.get("backend.app.tasks")
    if tasks_package is not None:
        monkeypatch.setattr(
            tasks_package,
            "livermore_candidate_history_materialize",
            _LIVERMORE_CANDIDATE_HISTORY_TASK_MODULE,
            raising=False,
        )
    monkeypatch.setitem(
        _LIVERMORE_CANDIDATE_HISTORY_TASK_MODULE.__dict__,
        "ensure_livermore_candidate_history_schema",
        _ensure_livermore_candidate_history_test_schema,
    )


def _minimal_observation_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double
        )
        """
    )


def _ensure_stock_adjustment_factor_test_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists stock_adjustment_factor (
          stock_code varchar,
          trade_date varchar,
          adj_factor double,
          source_version varchar,
          run_id varchar
        )
        """
    )


def _seed_stock_adjustment_factors(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, str, float | None]],
) -> None:
    _ensure_stock_adjustment_factor_test_schema(conn)
    conn.executemany(
        """
        insert into stock_adjustment_factor
        (trade_date, stock_code, adj_factor, source_version, run_id)
        values (?, ?, ?, 'sv_test_adj', 'run-test-adj')
        """,
        rows,
    )


def _fake_payload(
    *,
    as_of_date: str,
    items: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "as_of_date": as_of_date,
            "requested_as_of_date": as_of_date,
            "stock_candidates": {"items": items},
            "market_gate": {"state": "HOT", "exposure": 0.5},
        },
        {
            "source_version": "sv_test_candidate_meta",
            "vendor_version": "vv_test_candidate_meta",
            "quality_flag": "ok",
        },
    )


def _seed_calendar_observations(
    duckdb_path: str,
    *,
    stock_code: str,
    start: date,
    days: int,
    base_close: float = 100.0,
    step: float = 0.1,
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        _minimal_observation_schema(conn)
        rows = []
        for i in range(days):
            d = (start + timedelta(days=i)).isoformat()
            rows.append((d, stock_code, base_close + step * i))
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def _seed_choice_stock_replay_coverage(conn: duckdb.DuckDBPyConnection, *, trade_date: str) -> None:
    conn.execute(
        """
        create table if not exists choice_stock_request_audit (
          as_of_date varchar,
          input_family varchar,
          field_key varchar,
          status varchar,
          row_count integer
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_universe (
          as_of_date varchar,
          stock_code varchar,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_sector_membership (
          as_of_date varchar,
          stock_code varchar,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_limit_quality (
          as_of_date varchar,
          stock_code varchar,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          field_keys_json varchar,
          pctchange double,
          turn double,
          amplitude double,
          open_value double,
          high_value double,
          low_value double,
          close_value double,
          volume double,
          amount double,
          tradestatus varchar,
          highlimit double,
          lowlimit double
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_request_audit values (?, ?, ?, ?, ?)",
        [
            (trade_date, "stock_universe", "a_share_universe_sector_001004", "completed", 1),
            (trade_date, "sector_membership", "sw2021_industry_membership", "completed", 1),
            (trade_date, "sector_strength", "daily_return_turnover_amplitude", "completed", 1),
            (trade_date, "stock_ohlcv", "daily_ohlcv_amount", "completed", 1),
            (trade_date, "stock_status", "daily_trade_status", "completed", 1),
            (trade_date, "limit_up_quality", "daily_limit_flags", "completed", 1),
            (trade_date, "limit_up_quality", "point_in_time_limit_streaks", "completed", 1),
        ],
    )
    conn.execute(
        "insert into choice_stock_universe values (?, ?, ?)",
        [trade_date, "000001.SZ", "a_share_universe_sector_001004"],
    )
    conn.execute(
        "insert into choice_stock_sector_membership values (?, ?, ?)",
        [trade_date, "000001.SZ", "sw2021_industry_membership"],
    )
    conn.execute(
        "insert into choice_stock_limit_quality values (?, ?, ?)",
        [trade_date, "000001.SZ", "point_in_time_limit_streaks"],
    )
    conn.execute(
        """
        insert into choice_stock_daily_observation values
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            trade_date,
            "000001.SZ",
            '["daily_return_turnover_amplitude","daily_ohlcv_amount","daily_trade_status","daily_limit_flags"]',
            0.01,
            1.2,
            0.8,
            10.0,
            10.5,
            9.8,
            10.2,
            1000.0,
            10000.0,
            "trading",
            11.0,
            9.0,
        ],
    )


def _build_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(tmp_path / "missing-choice-stock-catalog.json"))
    get_settings.cache_clear()
    from backend.app.repositories.user_scope_repo import UserScopeRepository

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="market_data.livermore",
        action="read",
    )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update({"X-User-Id": "livermore-read-user", "X-User-Role": "viewer"})
    return client


def _insert_strategy_score_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, str, str, str, float | None, float | None, float | None, str]],
) -> None:
    _ensure_livermore_candidate_history_test_schema(conn)
    conn.executemany(
        """
        insert into livermore_candidate_history (
          snapshot_as_of_date,
          stock_code,
          stock_name,
          candidate_rank,
          selection_close,
          forward_trade_date_1d,
          forward_trade_date_5d,
          forward_trade_date_20d,
          return_1d,
          return_5d,
          return_20d,
          data_status,
          formula_version,
          source_version,
          vendor_version,
          rule_version,
          run_id,
          signal_kind,
          signal_evidence_json
        ) values (?, ?, ?, ?, 10.0, ?, ?, ?, ?, ?, ?, 'complete', 'fv1', 'sv_score', 'vv_score', 'rv_score', ?, ?, ?)
        """,
        [
            (
                snapshot_date,
                stock_code,
                stock_name,
                index,
                snapshot_date,
                snapshot_date,
                snapshot_date,
                return_1d,
                return_5d,
                return_20d,
                f"run-{index}",
                signal_kind,
                signal_evidence_json,
            )
            for index, (
                snapshot_date,
                stock_code,
                stock_name,
                signal_kind,
                return_1d,
                return_5d,
                return_20d,
                signal_evidence_json,
            ) in enumerate(rows, start=1)
        ],
    )


def _macro_context_v1_fixture(*, data_state: str = "ready") -> dict[str, object]:
    return {
        "macro_context_id": "macroctx_unit",
        "macro_contract_version": "rv_macro_context_v1",
        "asof_date": "2026-05-01",
        "report_date": "2026-05-01",
        "data_state": data_state,
        "coverage_ratio": 1.0,
        "freshness_score": 1.0,
        "confidence_score": 1.0 if data_state == "ready" else 0.5333,
        "fallback_mode": "none",
        "dimension_scores": {
            "rate_direction_score": 0.1,
            "liquidity_score": 0.2,
            "growth_score": 0.3,
            "inflation_score": -0.1,
            "composite_score": 0.15,
        },
        "readiness_reasons": [] if data_state == "ready" else ["MACRO_WARNINGS_PRESENT"],
        "quality_flag": "ok" if data_state == "ready" else "warning",
        "vendor_status": "ok",
        "source_version": "sv_macro",
        "vendor_version": "vv_macro",
        "rule_version": "rv_macro",
        "cache_version": "cv_macro",
        "evidence_rows": 30,
        "warning_count": 0 if data_state == "ready" else 1,
    }


def _seed_csi300_benchmark(conn: duckdb.DuckDBPyConnection, rows: list[tuple[str, float]]) -> None:
    conn.execute(
        """
        create table if not exists fact_choice_macro_daily (
          series_id varchar,
          series_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          quality_flag varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into fact_choice_macro_daily values
        ('CA.CSI300', 'CSI300', ?, ?, 'D', 'point', 'sv_benchmark', 'vv_benchmark', 'rv_benchmark', 'ok', 'run-benchmark')
        """,
        rows,
    )


def _seed_csi300_snapshot_benchmark(conn: duckdb.DuckDBPyConnection, rows: list[tuple[str, float]]) -> None:
    conn.execute(
        """
        create table if not exists choice_market_snapshot (
          series_id varchar,
          series_name varchar,
          vendor_series_code varchar,
          vendor_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into choice_market_snapshot values
        ('CA.CSI300', 'CSI300', '000300.SH', 'Choice', ?, ?, 'D', 'point', 'sv_snapshot', 'vv_snapshot', 'rv_snapshot', 'run-snapshot')
        """,
        rows,
    )


def test_task_happy_path_forward_returns(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "hist.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=35)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "银行"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))
    assert out["status"] == "ok"
    assert out["row_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select selection_close, return_1d, return_5d, return_10d, return_20d, data_status, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
        assert row is not None
        selection_close, r1, r5, r10, r20, dst, signal_evidence_json = row
        assert selection_close == 100.0
        # bar 2026-01-07 closes at 100.1
        assert abs(float(r1) - 0.001) < 1e-9
        tgt5 = conn.execute(
            """
            select close_value from choice_stock_daily_observation
            where stock_code = ? and trade_date > ? order by trade_date limit 5
            """,
            [stock, snap.isoformat()],
        ).fetchall()
        tgt20 = conn.execute(
            """
            select close_value from choice_stock_daily_observation
            where stock_code = ? and trade_date > ? order by trade_date limit 20
            """,
            [stock, snap.isoformat()],
        ).fetchall()
        tgt10 = conn.execute(
            """
            select close_value from choice_stock_daily_observation
            where stock_code = ? and trade_date > ? order by trade_date limit 10
            """,
            [stock, snap.isoformat()],
        ).fetchall()
        expected_r5 = (float(tgt5[-1][0]) - selection_close) / selection_close
        expected_r10 = (float(tgt10[-1][0]) - selection_close) / selection_close
        expected_r20 = (float(tgt20[-1][0]) - selection_close) / selection_close
        assert abs(float(r5) - expected_r5) < 1e-9
        assert abs(float(r10) - expected_r10) < 1e-9
        assert abs(float(r20) - expected_r20) < 1e-9
        assert dst == "complete"
        signal_evidence = json.loads(str(signal_evidence_json))
        assert signal_evidence["market_state"] == "HOT"
        assert signal_evidence["market_gate_exposure"] == 0.5
    finally:
        conn.close()


def test_task_writes_adjusted_forward_returns_using_adj_factor_ratio(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "adjusted-forward.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        rows = [((snap + timedelta(days=i)).isoformat(), stock, 100.0 + i) for i in range(22)]
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            rows,
        )
        _seed_stock_adjustment_factors(
            conn,
            [((snap + timedelta(days=i)).isoformat(), stock, 1.0 if i == 0 else 1.2) for i in range(22)],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "Bank"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))
    assert out["row_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select selection_close, return_1d, return_1d_adj, ex_div_in_window,
                   formula_version, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    selection_close, return_1d, return_1d_adj, ex_div_in_window, formula_version, signal_evidence_json = row
    assert selection_close == 100.0
    assert abs(float(return_1d) - 0.01) < 1e-9
    expected_adj = (101.0 * 1.2) / (100.0 * 1.0) - 1.0
    assert abs(float(return_1d_adj) - expected_adj) < 1e-9
    assert ex_div_in_window is True
    assert formula_version == "fv_livermore_candidate_forward_close_dual_adjust_v2"
    evidence = json.loads(str(signal_evidence_json))["adjustment_evidence"]
    assert evidence["price_adjustment_mode"] == "adj_factor_ratio"
    assert evidence["adj_factor_missing"] is False
    assert evidence["ex_div_in_window"] is True


def test_task_leaves_adjusted_return_null_when_adj_factor_missing_and_sets_evidence_flag(
    monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "adjusted-forward-missing.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 100.0),
                ((snap + timedelta(days=1)).isoformat(), stock, 101.0),
            ],
        )
        _seed_stock_adjustment_factors(conn, [(snap.isoformat(), stock, 1.0)])
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "Bank"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select return_1d, return_1d_adj, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return_1d, return_1d_adj, signal_evidence_json = row
    assert abs(float(return_1d) - 0.01) < 1e-9
    assert return_1d_adj is None
    evidence = json.loads(str(signal_evidence_json))["adjustment_evidence"]
    assert evidence["adj_factor_missing"] is True
    assert evidence["adj_factor_missing_horizons"] == ["1d"]
    assert evidence["adjusted_returns_status"] == "partial_missing_adj_factor"


def test_task_writes_execution_history_with_next_open_and_net_returns(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "execution.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        rows = []
        for i in range(7):
            day = (snap + timedelta(days=i)).isoformat()
            rows.append((day, stock, 100.0 + i, 100.0 + i * 2, "交易", 120.0 + i, 80.0))
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)", rows)
        _seed_stock_adjustment_factors(
            conn,
            [((snap + timedelta(days=i)).isoformat(), stock, 1.0) for i in range(7)],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "银行"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))
    assert out["execution_row_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select signal_close, entry_date, entry_price, entry_price_kind,
                   exit_price_1d, return_1d_gross, return_1d_net,
                   return_1d_gross_adj, return_1d_net_adj, entry_ex_div,
                   price_adjustment_mode, data_status, evidence_json
            from livermore_candidate_execution_history
            """
        ).fetchone()
        assert row is not None
        (
            signal_close,
            entry_date,
            entry_price,
            entry_kind,
            exit_1d,
            gross_1d,
            net_1d,
            gross_1d_adj,
            net_1d_adj,
            entry_ex_div,
            price_adjustment_mode,
            status,
            evidence_json,
        ) = row
        assert signal_close == 100.0
        assert entry_date == "2026-01-07"
        assert entry_price == 101.0
        assert entry_kind == "next_open"
        assert exit_1d == 102.0
        expected_gross = 102.0 / 101.0 - 1.0
        # return_1d_net and return_1d_net_adj both use multiplicative cost
        # netting ((1+r)*(1-c)-1); v4 aligned the unadjusted net column.
        round_trip_cost = 0.0008 + 0.0013 + 2 * 0.0010
        expected_net = (1.0 + expected_gross) * (1.0 - round_trip_cost) - 1.0
        expected_net_adj = expected_net
        assert abs(float(gross_1d) - expected_gross) < 1e-9
        assert abs(float(net_1d) - expected_net) < 1e-9
        assert abs(float(gross_1d_adj) - expected_gross) < 1e-9
        assert abs(float(net_1d_adj) - expected_net_adj) < 1e-9
        assert entry_ex_div is False
        assert price_adjustment_mode == "adj_factor_ratio"
        assert status == "pending"
        assert json.loads(str(evidence_json))["price_adjustment_mode"] == "adj_factor_ratio"
    finally:
        conn.close()


def test_task_execution_write_same_date_replay_keeps_one_logical_row(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "execution-daily-replay.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=3)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "Ping",
                    "sector_code": "S1",
                    "sector_name": "Bank",
                }
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    first = materialize_livermore_candidate_history(str(db_path), as_of_date=snap.isoformat())
    second = materialize_livermore_candidate_history(str(db_path), as_of_date=snap.isoformat())

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select signal_date, stock_code, signal_kind, run_id
            from livermore_candidate_execution_history
            """
        ).fetchall()
    finally:
        conn.close()

    assert first["execution_row_count"] == 1
    assert second["execution_row_count"] == 1
    assert first["run_id"] != second["run_id"]
    assert rows == [
        (
            snap.isoformat(),
            stock,
            "stock_candidate",
            second["run_id"],
        )
    ]


def test_task_marks_execution_entry_ex_div_when_entry_adj_factor_differs_from_signal(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "execution-entry-ex-div.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        rows = []
        for i in range(7):
            day = (snap + timedelta(days=i)).isoformat()
            rows.append((day, stock, 100.0 + i, 100.0 + i * 2, "浜ゆ槗", 120.0 + i, 80.0))
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)", rows)
        _seed_stock_adjustment_factors(
            conn,
            [
                (snap.isoformat(), stock, 1.0),
                ((snap + timedelta(days=1)).isoformat(), stock, 1.1),
                ((snap + timedelta(days=2)).isoformat(), stock, 1.1),
                ((snap + timedelta(days=3)).isoformat(), stock, 1.1),
                ((snap + timedelta(days=4)).isoformat(), stock, 1.1),
                ((snap + timedelta(days=5)).isoformat(), stock, 1.1),
                ((snap + timedelta(days=6)).isoformat(), stock, 1.1),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "Bank"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select entry_date, entry_price_kind, entry_ex_div, price_adjustment_mode, evidence_json
            from livermore_candidate_execution_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    entry_date, entry_kind, entry_ex_div, mode, evidence_json = row
    assert entry_date == "2026-01-07"
    assert entry_kind == "next_open"
    assert entry_ex_div is True
    assert mode == "adj_factor_ratio"
    evidence = json.loads(str(evidence_json))
    assert evidence["entry_adj_factor_signal"] == 1.0
    assert evidence["entry_adj_factor"] == 1.1
    assert evidence["entry_adj_factor_ratio"] == pytest.approx(1.1)


def test_task_marks_execution_entry_blocked_on_limit_up_open(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "execution-block.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                (snap.isoformat(), stock, 100.0, 100.0, "交易", 110.0, 90.0),
                ((snap + timedelta(days=1)).isoformat(), stock, 110.0, 110.0, "交易", 110.0, 90.0),
                ((snap + timedelta(days=2)).isoformat(), stock, 111.0, 111.0, "交易", 122.0, 100.0),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "银行"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select entry_executable, entry_block_reason, return_1d_net, data_status
            from livermore_candidate_execution_history
            """
        ).fetchone()
        assert row == (False, "entry_limit_up_or_one_line", None, "entry_blocked")
    finally:
        conn.close()


def test_execution_only_backfill_rebuilds_execution_history_from_existing_candidate_rows_and_is_idempotent(
    monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "execution-only.duckdb"
    snap = date(2026, 1, 6)
    valid_stock = "000001.SZ"
    skipped_stock = "000002.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        rows = []
        for stock_code, offset in ((valid_stock, 0.0), (skipped_stock, 10.0)):
            for i in range(7):
                day = (snap + timedelta(days=i)).isoformat()
                price = 100.0 + offset + i
                rows.append((day, stock_code, price, price + 0.5, "trading", price + 20.0, price - 20.0))
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)", rows)
        _seed_stock_adjustment_factors(
            conn,
            [
                ((snap + timedelta(days=i)).isoformat(), stock_code, 1.0)
                for stock_code in (valid_stock, skipped_stock)
                for i in range(7)
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": valid_stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "Bank"},
                {
                    "rank": 2,
                    "stock_code": skipped_stock,
                    "stock_name": "Skip",
                    "sector_code": "S2",
                    "sector_name": "Broker",
                },
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path), as_of_date=snap.isoformat())
    assert out["row_count"] == 2
    assert out["execution_row_count"] == 2

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        candidate_count_before = conn.execute(
            "select count(*)::integer from livermore_candidate_history where snapshot_as_of_date = ?",
            [snap.isoformat()],
        ).fetchone()
        conn.execute("delete from livermore_candidate_execution_history")
        conn.execute(
            "delete from choice_stock_daily_observation where trade_date = ? and stock_code = ?",
            [snap.isoformat(), skipped_stock],
        )
    finally:
        conn.close()

    assert candidate_count_before == (2,)

    first = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=snap.isoformat(),
        end_date=snap.isoformat(),
    )

    assert first["status"] == "partial"
    assert first["start_date"] == snap.isoformat()
    assert first["end_date"] == snap.isoformat()
    assert first["processed_date_count"] == 1
    assert first["source_candidate_row_count"] == 2
    assert first["execution_row_count"] == 1
    assert first["skipped_count"] == 1
    assert first["partial_date_count"] == 1
    assert first["formula_version"] == "fv_livermore_candidate_execution_dual_adjust_v5"
    assert isinstance(first["run_id"], str) and first["run_id"]
    assert first["dates"] == [
        {
            "as_of_date": snap.isoformat(),
            "status": "partial",
            "source_candidate_row_count": 2,
            "execution_row_count": 1,
            "skipped_count": 1,
            "skipped": [f"{snap.isoformat()}:{skipped_stock}:missing_execution_payload"],
        }
    ]

    second = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=snap.isoformat(),
        end_date=snap.isoformat(),
    )
    assert second["execution_row_count"] == 1
    assert second["source_candidate_row_count"] == 2
    assert second["skipped_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        candidate_count_after = conn.execute(
            "select count(*)::integer from livermore_candidate_history where snapshot_as_of_date = ?",
            [snap.isoformat()],
        ).fetchone()
        execution_rows = conn.execute(
            """
            select signal_date, stock_code, formula_version
            from livermore_candidate_execution_history
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert candidate_count_after == candidate_count_before
    assert execution_rows == [
        (snap.isoformat(), valid_stock, "fv_livermore_candidate_execution_dual_adjust_v5"),
    ]


def test_execution_only_backfill_deduplicates_policy_variant_source_rows_and_replay(tmp_path) -> None:
    db_path = tmp_path / "execution-only-policy-variants.duckdb"
    snap = date(2026, 3, 18)
    stock = "300042.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                (snap.isoformat(), stock, 100.0, 100.0, "trading", 120.0, 80.0),
                ((snap + timedelta(days=1)).isoformat(), stock, 101.0, 102.0, "trading", 121.0, 81.0),
            ],
        )
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.executemany(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date,
              stock_code,
              stock_name,
              candidate_rank,
              signal_kind,
              market_state,
              run_id
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snap.isoformat(),
                    stock,
                    "Policy Candidate",
                    1,
                    "hybrid_fusion",
                    "WARM",
                    "livermore_candidate_history:2026-03-18:exp3b:run-a",
                ),
                (
                    snap.isoformat(),
                    stock,
                    "Policy Candidate",
                    2,
                    "hybrid_fusion",
                    "WARM",
                    "livermore_candidate_history:2026-03-18:exp3c_shadow:run-b",
                ),
            ],
        )
    finally:
        conn.close()

    first = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=snap.isoformat(),
        end_date=snap.isoformat(),
    )
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        first_rows = conn.execute(
            """
            select signal_date, stock_code, signal_kind, candidate_rank
            from livermore_candidate_execution_history
            """
        ).fetchall()
    finally:
        conn.close()

    second = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=snap.isoformat(),
        end_date=snap.isoformat(),
    )
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        second_rows = conn.execute(
            """
            select signal_date, stock_code, signal_kind, candidate_rank
            from livermore_candidate_execution_history
            """
        ).fetchall()
    finally:
        conn.close()

    assert first["source_candidate_row_count"] == 2
    assert second["source_candidate_row_count"] == 2
    assert first["execution_row_count"] == 1
    assert second["execution_row_count"] == 1
    expected_rows = [(snap.isoformat(), stock, "hybrid_fusion", 1)]
    assert first_rows == expected_rows
    assert second_rows == expected_rows


def test_execution_only_backfill_empty_source_range_preserves_existing_execution_rows(tmp_path) -> None:
    db_path = tmp_path / "execution-only-empty-source.duckdb"
    start_date = date(2026, 2, 3)
    end_date = date(2026, 2, 4)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                (start_date.isoformat(), "000001.SZ", 100.0, 100.5, "trading", 120.0, 80.0),
                (end_date.isoformat(), "000001.SZ", 101.0, 101.5, "trading", 121.0, 81.0),
            ],
        )
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.executemany(
            """
            insert into livermore_candidate_execution_history (
              signal_date,
              stock_code,
              stock_name,
              signal_kind,
              candidate_rank,
              market_state,
              signal_close,
              entry_date,
              entry_price,
              entry_price_kind,
              entry_executable,
              entry_block_reason,
              entry_ex_div,
              data_status,
              formula_version,
              run_id,
              evidence_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    start_date.isoformat(),
                    "000001.SZ",
                    "Keep A",
                    "stock_candidate",
                    1,
                    "HOT",
                    100.0,
                    start_date.isoformat(),
                    100.0,
                    "next_open",
                    True,
                    None,
                    False,
                    "complete",
                    "fv_existing",
                    "keep-start",
                    "{}",
                ),
                (
                    end_date.isoformat(),
                    "000002.SZ",
                    "Keep B",
                    "stock_candidate",
                    1,
                    "HOT",
                    101.0,
                    end_date.isoformat(),
                    101.0,
                    "next_open",
                    True,
                    None,
                    False,
                    "complete",
                    "fv_existing",
                    "keep-end",
                    "{}",
                ),
            ],
        )
    finally:
        conn.close()

    out = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    assert out["status"] == "partial"
    assert out["processed_date_count"] == 2
    assert out["source_candidate_row_count"] == 0
    assert out["execution_row_count"] == 0
    assert out["partial_date_count"] == 2
    assert "missing_source_candidate_rows" in cast(list[str], out["skipped"])
    assert out["dates"] == [
        {
            "as_of_date": start_date.isoformat(),
            "status": "partial",
            "source_candidate_row_count": 0,
            "execution_row_count": 0,
            "skipped_count": 1,
            "skipped": [f"{start_date.isoformat()}:missing_source_candidate_rows"],
        },
        {
            "as_of_date": end_date.isoformat(),
            "status": "partial",
            "source_candidate_row_count": 0,
            "execution_row_count": 0,
            "skipped_count": 1,
            "skipped": [f"{end_date.isoformat()}:missing_source_candidate_rows"],
        },
    ]

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        execution_rows = conn.execute(
            """
            select signal_date, stock_code, run_id
            from livermore_candidate_execution_history
            order by signal_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert execution_rows == [
        (start_date.isoformat(), "000001.SZ", "keep-start"),
        (end_date.isoformat(), "000002.SZ", "keep-end"),
    ]


def test_execution_only_backfill_sparse_range_rebuilds_only_source_dates_and_preserves_missing_source_rows(
    tmp_path,
) -> None:
    db_path = tmp_path / "execution-only-sparse-range.duckdb"
    source_date = date(2026, 3, 2)
    missing_source_date = date(2026, 3, 3)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                (source_date.isoformat(), "000001.SZ", 100.0, 100.0, "trading", 120.0, 80.0),
                (missing_source_date.isoformat(), "000001.SZ", 101.0, 101.5, "trading", 121.0, 81.0),
                ((missing_source_date + timedelta(days=1)).isoformat(), "000001.SZ", 102.0, 102.5, "trading", 122.0, 82.0),
            ],
        )
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.execute(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date,
              stock_code,
              stock_name,
              candidate_rank,
              signal_kind,
              market_state
            ) values (?, ?, ?, ?, ?, ?)
            """,
            [
                source_date.isoformat(),
                "000001.SZ",
                "Rebuild Me",
                1,
                "stock_candidate",
                "HOT",
            ],
        )
        conn.executemany(
            """
            insert into livermore_candidate_execution_history (
              signal_date,
              stock_code,
              stock_name,
              signal_kind,
              candidate_rank,
              market_state,
              signal_close,
              entry_date,
              entry_price,
              entry_price_kind,
              entry_executable,
              entry_block_reason,
              entry_ex_div,
              data_status,
              formula_version,
              run_id,
              evidence_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    source_date.isoformat(),
                    "000001.SZ",
                    "Stale Source",
                    "stock_candidate",
                    1,
                    "HOT",
                    100.0,
                    source_date.isoformat(),
                    100.0,
                    "next_open",
                    True,
                    None,
                    False,
                    "complete",
                    "fv_existing",
                    "stale-source",
                    "{}",
                ),
                (
                    missing_source_date.isoformat(),
                    "000009.SZ",
                    "Keep Missing",
                    "stock_candidate",
                    1,
                    "HOT",
                    110.0,
                    missing_source_date.isoformat(),
                    110.0,
                    "next_open",
                    True,
                    None,
                    False,
                    "complete",
                    "fv_existing",
                    "keep-missing",
                    "{}",
                ),
            ],
        )
    finally:
        conn.close()

    out = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=source_date.isoformat(),
        end_date=missing_source_date.isoformat(),
    )

    assert out["status"] == "partial"
    assert out["processed_date_count"] == 2
    assert out["source_candidate_row_count"] == 1
    assert out["execution_row_count"] == 1
    assert out["partial_date_count"] == 1
    assert cast(list[dict[str, object]], out["dates"]) == [
        {
            "as_of_date": source_date.isoformat(),
            "status": "ok",
            "source_candidate_row_count": 1,
            "execution_row_count": 1,
            "skipped_count": 0,
            "skipped": [],
        },
        {
            "as_of_date": missing_source_date.isoformat(),
            "status": "partial",
            "source_candidate_row_count": 0,
            "execution_row_count": 0,
            "skipped_count": 1,
            "skipped": [f"{missing_source_date.isoformat()}:missing_source_candidate_rows"],
        },
    ]

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        execution_rows = conn.execute(
            """
            select signal_date, stock_code, run_id, formula_version
            from livermore_candidate_execution_history
            order by signal_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert execution_rows[0][0] == source_date.isoformat()
    assert execution_rows[0][1] == "000001.SZ"
    assert execution_rows[0][2] != "stale-source"
    assert execution_rows[0][3] == "fv_livermore_candidate_execution_dual_adjust_v5"
    assert execution_rows[1] == (
        missing_source_date.isoformat(),
        "000009.SZ",
        "keep-missing",
        "fv_existing",
    )


def test_stock_candidate_history_persists_breakout_evidence_fields(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "stock-evidence.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=35)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "Ping",
                    "sector_code": "S1",
                    "sector_name": "银行",
                    "sector_rank": 2,
                    "close_strength": 0.97,
                    "abnormal_turnover": 1.75,
                    "gap_norm": 0.12,
                    "breakout_extension_norm": 0.22,
                    "breakout_level": 99.5,
                    "ema10": 98.1,
                    "ma20": 97.2,
                    "ma60": 95.3,
                    "ma120": 90.4,
                    "pe": 12.3,
                    "pb": 1.4,
                    "ps": 2.1,
                    "roe": 0.18,
                    "gross_margin": 0.36,
                    "factor_score": 1.2345,
                    "factor_overlay_rank": 1,
                },
            ],
        )
        payload["stock_candidates"]["formula_version"] = "rv_livermore_stock_candidates_bundle_v9"
        payload["stock_candidates"]["fundamental_overlay"] = {
            "status": "applied",
            "input_candidate_count": 2,
            "valid_factor_count": 2,
            "selected_factor_count": 1,
            "top_fraction": 0.5,
        }
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))
    assert out["row_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select market_state, abnormal_turnover, gap_norm, breakout_extension_norm,
                   breakout_level, ema10, ma20, ma60, ma120, strength_turn,
                   signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[:10] == ("HOT", 1.75, 0.12, 0.22, 99.5, 98.1, 97.2, 95.3, 90.4, 1.75)
    evidence = json.loads(str(row[10]))
    adjustment_evidence = evidence.pop("adjustment_evidence")
    assert adjustment_evidence["price_adjustment_mode"] == "adj_factor_ratio"
    assert adjustment_evidence["adj_factor_missing"] is True
    assert evidence == {
        "abnormal_turnover": 1.75,
        "breakout_extension_norm": 0.22,
        "breakout_level": 99.5,
        "close_strength": 0.97,
        "ema10": 98.1,
        "factor_overlay_rank": 1,
        "factor_score": 1.2345,
        "fundamental_overlay_status": "applied",
        "gap_norm": 0.12,
        "gross_margin": 0.36,
        "ma120": 90.4,
            "ma20": 97.2,
            "ma60": 95.3,
            "market_gate_exposure": 0.5,
            "market_state": "HOT",
        "pb": 1.4,
        "pe": 12.3,
        "ps": 2.1,
        "rank": 1,
        "roe": 0.18,
        "sector_code": "S1",
        "sector_rank": 2,
        "selection_formula_version": "rv_livermore_stock_candidates_bundle_v9",
        "signal_kind": "stock_candidate",
        "stock_code": stock,
    }


def test_stock_candidate_history_passes_policy_to_strategy_loader_and_persists_policy_evidence(
    monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "stock-policy.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=35)
    seen_policies: list[str | None] = []

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        seen_policies.append(kwargs.get("stock_candidate_policy"))
        payload, meta = _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "Ping",
                    "sector_code": "S1",
                    "sector_name": "閾惰",
                    "sector_rank": 2,
                    "close_strength": 0.995,
                    "abnormal_turnover": 1.8,
                    "gap_norm": 0.12,
                    "selection_policy": "exp3b",
                },
            ],
        )
        stock_candidates = payload["stock_candidates"]
        assert isinstance(stock_candidates, dict)
        payload["stock_candidates"] = {
            "items": stock_candidates["items"],
            "selection_policy": "exp3b",
        }
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path), stock_candidate_policy="exp3b")
    assert out["row_count"] == 1
    assert seen_policies == ["exp3b"]

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute("select signal_evidence_json from livermore_candidate_history").fetchone()
    finally:
        conn.close()

    assert row is not None
    evidence = json.loads(str(row[0]))
    assert evidence["selection_policy"] == "exp3b"


def test_stock_candidate_universe_history_keeps_pre_truncation_rows(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "stock-universe.duckdb"
    snap = date(2026, 1, 6)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        rows = []
        for stock_index in range(1, 9):
            stock_code = f"00000{stock_index}.SZ"
            for day_index in range(35):
                rows.append(
                    (
                        (snap + timedelta(days=day_index)).isoformat(),
                        stock_code,
                        100.0 + stock_index + day_index * 0.1,
                    )
                )
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            rows,
        )
    finally:
        conn.close()

    universe_items = [
        {
            "new_rank": index,
            "eligible_before_truncation": True,
            "selected_new_top6": index <= 6,
            "old_rank": 9 - index,
            "selected_old_top6": index >= 3,
            "stock_code": f"00000{index}.SZ",
            "stock_name": f"Stock {index}",
            "sector_code": "S1",
            "sector_name": "银行",
            "sector_rank": 1,
            "close": 100.0 + index,
            "close_strength": 0.95 + index / 1000,
            "abnormal_turnover": 1.0 + index / 10,
            "gap_norm": 0.1,
            "breakout_extension_norm": 0.2,
            "breakout_level": 99.0,
            "ema10": 98.0,
            "ma20": 97.0,
            "ma60": 95.0,
            "ma120": 90.0,
        }
        for index in range(1, 9)
    ]

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(as_of_date=snap.isoformat(), items=universe_items[:6])
        payload["stock_candidates"] = {"items": universe_items[:6], "universe_items": universe_items}
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))
    assert out["row_count"] == 6
    assert out["universe_row_count"] == 8

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, new_rank, old_rank, selected_new_top6, selected_old_top6,
                   return_10d, market_state
            from livermore_stock_candidate_universe_history
            order by new_rank
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 8
    assert [row[1] for row in rows] == list(range(1, 9))
    assert [bool(row[3]) for row in rows] == [True] * 6 + [False, False]
    assert rows[0][2] == 8
    assert rows[-1][2] == 1
    assert rows[0][5] is not None
    assert {row[6] for row in rows} == {"HOT"}


def test_task_partial_halt_long_gap(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "halt.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    snap = date(2026, 3, 2)
    stock = "600000.SH"
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 10.0),
                ((snap + timedelta(days=10)).isoformat(), stock, 11.0),
                ((snap + timedelta(days=11)).isoformat(), stock, 11.05),
                ((snap + timedelta(days=12)).isoformat(), stock, 11.1),
                ((snap + timedelta(days=13)).isoformat(), stock, 11.15),
                ((snap + timedelta(days=14)).isoformat(), stock, 11.2),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "GapCo", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )
    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute("select data_status, return_1d, forward_trade_date_1d from livermore_candidate_history").fetchone()
        assert row is not None
        assert row[0] == "partial_halt"
        assert row[1] is not None
        assert str(row[2])[:10] == (snap + timedelta(days=10)).isoformat()
    finally:
        conn.close()


def test_task_does_not_mark_exchange_holiday_gap_as_partial_halt(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "holiday-gap.duckdb"
    snap = date(2026, 4, 30)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 10.0),
                ("2026-05-06", stock, 10.1),
                ("2026-05-07", stock, 10.2),
                ("2026-05-08", stock, 10.3),
                ("2026-05-11", stock, 10.4),
                ("2026-05-12", stock, 10.5),
                ("2026-05-13", stock, 10.6),
                ("2026-05-14", stock, 10.7),
                ("2026-05-15", stock, 10.8),
                ("2026-05-18", stock, 10.9),
                ("2026-05-19", stock, 11.0),
                ("2026-05-20", stock, 11.1),
                ("2026-05-21", stock, 11.2),
                ("2026-05-22", stock, 11.3),
                ("2026-05-25", stock, 11.4),
                ("2026-05-26", stock, 11.5),
                ("2026-05-27", stock, 11.6),
                ("2026-05-28", stock, 11.7),
                ("2026-05-29", stock, 11.8),
                ("2026-06-01", stock, 11.9),
                ("2026-06-02", stock, 12.0),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Holiday", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute("select data_status, forward_trade_date_1d from livermore_candidate_history").fetchone()
        assert row is not None
        assert row[0] == "complete"
        assert str(row[1])[:10] == "2026-05-06"
    finally:
        conn.close()


def test_task_treats_holiday_gap_with_incomplete_forward_window_as_pending(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "holiday-gap-pending.duckdb"
    snap = date(2026, 4, 28)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 10.0),
                ("2026-04-29", stock, 10.1),
                ("2026-04-30", stock, 10.2),
                ("2026-05-06", stock, 10.3),
                ("2026-05-07", stock, 10.4),
                ("2026-05-08", stock, 10.5),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "HolidayPending", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            "select data_status, forward_trade_date_5d, return_20d from livermore_candidate_history"
        ).fetchone()
        assert row is not None
        assert row[0] == "pending"
        assert str(row[1])[:10] == "2026-05-08"
        assert row[2] is None
    finally:
        conn.close()


def test_task_pending_insufficient_forward_bars(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "pend.duckdb"
    snap = date(2026, 5, 1)
    stock = "000002.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=12)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Beta", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )
    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            "select return_20d, forward_trade_date_20d, data_status from livermore_candidate_history"
        ).fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] is None
        assert row[2] == "pending"
    finally:
        conn.close()


def test_task_uses_configured_choice_stock_readiness(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "ready.duckdb"
    snap = date(2026, 5, 1)
    stock = "000004.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=25)
    expected_catalog = tmp_path / "choice_catalog.json"
    ready = ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path=str(expected_catalog),
        missing_input_families=[],
        message="ready for test",
    )
    seen: dict[str, object] = {}

    class _Settings:
        choice_stock_catalog_file = str(expected_catalog)

    def _mock_readiness(path: object) -> ChoiceStockReadiness:
        seen["catalog_path"] = str(path)
        return ready

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        seen["stock_readiness"] = kwargs.get("stock_readiness")
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Ready", "sector_code": "S1", "sector_name": "Sec"}],
        )

    monkeypatch.setattr("backend.app.tasks.livermore_candidate_history_materialize.get_settings", lambda: _Settings())
    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_choice_stock_readiness",
        _mock_readiness,
    )
    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 1
    assert seen["catalog_path"] == str(expected_catalog)
    assert seen["stock_readiness"] is ready


def test_task_loads_strategy_before_opening_write_connection(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "lock.duckdb"
    snap = date(2026, 5, 1)
    stock = "000005.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=25)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        probe = duckdb.connect(str(db_path), read_only=True)
        probe.close()
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Lock", "sector_code": "S1", "sector_name": "Sec"}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 1


def test_materialize_holds_candidate_history_lock_during_write(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "lock-hold.duckdb"
    snap = date(2026, 5, 1)
    stock = "000006.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=25)

    locks_mod = importlib.import_module("backend.app.governance.locks")
    task_mod = importlib.import_module("backend.app.tasks.livermore_candidate_history_materialize")
    observed = {"contention_checked": False}
    original_acquire_lock = locks_mod.acquire_lock

    @contextmanager
    def tracking_acquire_lock(definition, base_dir, timeout_seconds=1.0, **kwargs):
        with original_acquire_lock(
            definition,
            base_dir=base_dir,
            timeout_seconds=timeout_seconds,
            **kwargs,
        ) as lock_path:
            if definition.key == task_mod.LIVERMORE_CANDIDATE_HISTORY_LOCK.key:
                with pytest.raises(TimeoutError):
                    with original_acquire_lock(
                        definition,
                        base_dir=base_dir,
                        timeout_seconds=0.01,
                    ):
                        pass
                observed["contention_checked"] = True
            yield lock_path

    monkeypatch.setattr(task_mod, "acquire_lock", tracking_acquire_lock)
    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        lambda *args, **kwargs: _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "LockHold",
                    "sector_code": "S1",
                    "sector_name": "Sec",
                }
            ],
        ),
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 1
    assert observed["contention_checked"] is True


def test_execution_backfill_holds_candidate_history_lock_during_write(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "execution-lock-hold.duckdb"
    snap = date(2026, 5, 1)
    stock = "000007.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=25)

    locks_mod = importlib.import_module("backend.app.governance.locks")
    task_mod = importlib.import_module("backend.app.tasks.livermore_candidate_history_materialize")
    observed = {"contention_checked": False}
    original_acquire_lock = locks_mod.acquire_lock

    @contextmanager
    def tracking_acquire_lock(definition, base_dir, timeout_seconds=1.0, **kwargs):
        with original_acquire_lock(
            definition,
            base_dir=base_dir,
            timeout_seconds=timeout_seconds,
            **kwargs,
        ) as lock_path:
            if definition.key == task_mod.LIVERMORE_CANDIDATE_HISTORY_LOCK.key:
                with pytest.raises(TimeoutError):
                    with original_acquire_lock(
                        definition,
                        base_dir=base_dir,
                        timeout_seconds=0.01,
                    ):
                        pass
                observed["contention_checked"] = True
            yield lock_path

    monkeypatch.setattr(task_mod, "acquire_lock", tracking_acquire_lock)
    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        lambda *args, **kwargs: _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "ExecLock",
                    "sector_code": "S1",
                    "sector_name": "Sec",
                }
            ],
        ),
    )
    materialize_livermore_candidate_history(str(db_path))

    out = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=snap.isoformat(),
        end_date=snap.isoformat(),
    )

    assert out["execution_row_count"] == 1
    assert observed["contention_checked"] is True


def test_task_materializes_theme_breakout_signal_rows_with_review_evidence_and_no_lookahead(
    monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "theme.duckdb"
    snap = date(2026, 5, 1)
    stock = "688001.SH"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 100.0),
                ((snap + timedelta(days=1)).isoformat(), stock, 90.0),
                ((snap + timedelta(days=2)).isoformat(), stock, 150.0),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(as_of_date=snap.isoformat(), items=[])
        payload["theme_breakout"] = {
            "items": [
                {
                    "rank": 1,
                    "theme_key": "concept:C001",
                    "theme_name": "Chiplet",
                    "source_kind": "real_concept",
                    "parent_sector_rank": 9,
                    "strong_stock_count": 3,
                    "limit_stock_count": 2,
                    "avg_pctchange": 9.5,
                    "avg_turn": 5.2,
                    "movement_event_count": 4,
                    "latest_event_title": "Chiplet intraday surge",
                    "latest_event_time": "2026-05-01 10:15:00",
                    "items": [
                        {
                            "stock_code": stock,
                            "stock_name": "Alpha Semiconductor",
                            "sector_code": "801080",
                            "sector_name": "Electronic",
                            "sector_rank": 9,
                            "pctchange": 12.1,
                            "turn": 4.2,
                            "amplitude": 7.0,
                            "close_strength": 0.86,
                            "closed_up_limit": True,
                            "movement_event_count": 2,
                            "latest_event_title": "Alpha Semiconductor intraday surge",
                            "latest_event_time": "2026-05-01 10:15:00",
                        }
                    ],
                }
            ],
            "evidence_state": {
                "intraday_movement": {
                    "state": "matched_rows",
                    "matched_row_count": 2,
                }
            },
        }
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 1
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select
              snapshot_as_of_date,
              stock_code,
              stock_name,
              signal_kind,
              theme_key,
              theme_name,
              theme_source_kind,
              theme_rank,
              stock_rank_in_theme,
              sector_rank,
              strength_pctchange,
              strength_turn,
              strength_amplitude,
              close_strength,
              closed_up_limit,
              forward_trade_date_1d,
              return_1d,
              forward_trade_date_5d,
              return_5d,
              data_status,
              signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == snap.isoformat()
    assert row[1] == stock
    assert row[2] == "Alpha Semiconductor"
    assert row[3] == "theme_breakout"
    assert row[4] == "concept:C001"
    assert row[5] == "Chiplet"
    assert row[6] == "real_concept"
    assert row[7] == 1
    assert row[8] == 1
    assert row[9] == 9
    assert row[10] == 12.1
    assert row[11] == 4.2
    assert row[12] == 7.0
    assert row[13] == 0.86
    assert row[14] is True
    assert row[15] == (snap + timedelta(days=1)).isoformat()
    assert abs(float(row[16]) - -0.1) < 1e-12
    assert row[17] is None
    assert row[18] is None
    assert row[19] == "pending"
    evidence = json.loads(row[20])
    assert evidence["movement_event_count"] == 4
    assert evidence["stock_movement_event_count"] == 2
    assert evidence["latest_event_title"] == "Chiplet intraday surge"
    assert evidence["stock_latest_event_title"] == "Alpha Semiconductor intraday surge"
    assert evidence["evidence_state"]["intraday_movement"]["state"] == "matched_rows"


def test_task_materializes_factor_uptrend_and_mean_reversion_signal_rows(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "other-strategies.duckdb"
    snap = date(2026, 5, 1)
    factor_stock = "000001.SZ"
    reversion_stock = "000002.SZ"
    uptrend_stock = "000003.SZ"
    fresh_stock = "300001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), factor_stock, 10.0),
                ((snap + timedelta(days=1)).isoformat(), factor_stock, 11.0),
                (snap.isoformat(), reversion_stock, 20.0),
                ((snap + timedelta(days=1)).isoformat(), reversion_stock, 18.0),
                (snap.isoformat(), uptrend_stock, 30.0),
                ((snap + timedelta(days=1)).isoformat(), uptrend_stock, 33.0),
                (snap.isoformat(), fresh_stock, 40.0),
                ((snap + timedelta(days=1)).isoformat(), fresh_stock, 44.0),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(as_of_date=snap.isoformat(), items=[])
        payload["factor_screen_candidates"] = {
            "formula_version": "rv_factor_screen_candidates_v4",
            "items": [
                {
                    "rank": 1,
                    "stock_code": factor_stock,
                    "stock_name": "Factor A",
                    "sector_code": "S1",
                    "sector_name": "Sector",
                    "industry": "Sector",
                    "score": 3.2,
                    "pe": 9.1,
                    "pb": 1.1,
                    "roe": 0.15,
                    "gross_margin": 0.3,
                    "avg_amount_20d": 240_000_000.0,
                    "formula_version": "rv_factor_screen_candidates_v4",
                }
            ]
        }
        payload["mean_reversion_candidates"] = {
            "items": [
                {
                    "rank": 1,
                    "stock_code": reversion_stock,
                    "stock_name": "Reversion B",
                    "sector_code": "S2",
                    "sector_name": "Other",
                    "drawdown_20d": -0.22,
                    "drawdown_60d": -0.31,
                    "ma5": 18.8,
                    "ma10": 18.1,
                    "close_strength": 0.72,
                    "vol_ratio": 2.4,
                    "score": 0.65,
                }
            ]
        }
        payload["uptrend_momentum_candidates"] = {
            "items": [
                {
                    "rank": 1,
                    "stock_code": uptrend_stock,
                    "stock_name": "Trend C",
                    "sector_code": "S3",
                    "sector_name": "Trend",
                    "score": 1.25,
                    "close": 30.0,
                    "return_20d": 0.08,
                    "return_60d": 0.18,
                    "return_120d": 0.32,
                    "ma20": 28.4,
                    "ma60": 25.2,
                    "ma120": 21.1,
                    "amount_ratio": 1.4,
                    "close_to_ma20": 0.056338,
                    "pctchange": 0.025,
                    "turn": 1.7,
                    "amplitude": 3.5,
                    "formula_version": "rv_uptrend_momentum_candidates_v2",
                }
            ]
        }
        payload["fresh_trend_watchlist"] = {
            "formula_version": "rv_fresh_trend_watchlist_candidates_v2",
            "items": [
                {
                    "rank": 1,
                    "stock_code": fresh_stock,
                    "stock_name": "Fresh D",
                    "sector_code": "S4",
                    "sector_name": "Fresh Tech",
                    "concepts": ["Chiplet", "AI hardware"],
                    "score": 1.52,
                    "close": 40.0,
                    "return_20d": 0.28,
                    "return_60d": 0.68,
                    "return_120d": 1.2,
                    "ma20": 36.1,
                    "ma60": 30.2,
                    "ma120": 25.1,
                    "amount_ratio": 1.8,
                    "close_to_ma20": 0.108033,
                    "pctchange": 0.045,
                    "turn": 12.4,
                    "amplitude": 7.2,
                    "hlimitedays": 0,
                }
            ]
        }
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 4
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select signal_kind, stock_code, stock_name, candidate_rank,
                   strength_pctchange, strength_turn, close_strength, signal_evidence_json, return_1d
            from livermore_candidate_history
            order by signal_kind asc
            """
        ).fetchall()
    finally:
        conn.close()

    by_kind = {row[0]: row for row in rows}
    assert set(by_kind) == {"factor_screen", "fresh_trend_watchlist", "mean_reversion", "uptrend_momentum"}
    assert by_kind["factor_screen"][1:4] == (factor_stock, "Factor A", 1)
    factor_evidence = json.loads(by_kind["factor_screen"][7])
    assert factor_evidence["score"] == 3.2
    # v3 引入的治理字段在 v4 门控断代后仍须落 signal_evidence_json。
    assert factor_evidence["formula_version"] == "rv_factor_screen_candidates_v4"
    assert factor_evidence["avg_amount_20d"] == 240_000_000.0
    assert abs(float(by_kind["factor_screen"][8]) - 0.1) < 1e-12
    assert by_kind["fresh_trend_watchlist"][1:4] == (fresh_stock, "Fresh D", 1)
    assert by_kind["fresh_trend_watchlist"][4:7] == (0.045, 1.8, None)
    fresh_evidence = json.loads(by_kind["fresh_trend_watchlist"][7])
    assert fresh_evidence["return_120d"] == 1.2
    assert fresh_evidence["concepts"] == ["Chiplet", "AI hardware"]
    assert fresh_evidence["formula_version"] == "rv_fresh_trend_watchlist_candidates_v2"
    assert abs(float(by_kind["fresh_trend_watchlist"][8]) - 0.1) < 1e-12
    assert by_kind["mean_reversion"][1:4] == (reversion_stock, "Reversion B", 1)
    assert by_kind["mean_reversion"][4:7] == (-0.22, 2.4, 0.72)
    assert json.loads(by_kind["mean_reversion"][7])["drawdown_60d"] == -0.31
    assert abs(float(by_kind["mean_reversion"][8]) - -0.1) < 1e-12
    assert by_kind["uptrend_momentum"][1:4] == (uptrend_stock, "Trend C", 1)
    assert by_kind["uptrend_momentum"][4:7] == (0.025, 1.4, None)
    uptrend_evidence = json.loads(by_kind["uptrend_momentum"][7])
    assert uptrend_evidence["return_60d"] == 0.18
    assert uptrend_evidence["ma20"] == 28.4
    assert uptrend_evidence["close_to_ma20"] == 0.056338
    assert uptrend_evidence["formula_version"] == "rv_uptrend_momentum_candidates_v2"
    assert abs(float(by_kind["uptrend_momentum"][8]) - 0.1) < 1e-12


def test_task_materializes_hybrid_fusion_signal_rows_with_core_scores(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "hybrid-fusion.duckdb"
    snap = date(2026, 5, 1)
    stock = "000003.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 10.0),
                ((snap + timedelta(days=1)).isoformat(), stock, 11.0),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(as_of_date=snap.isoformat(), items=[])
        payload["hybrid_fusion_candidates"] = {
            "formula_version": "rv_hybrid_fusion_candidates_v1",
            "observation_only": True,
            "items": [
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "Hybrid C",
                    "sector_code": "S3",
                    "sector_name": "Fusion Sector",
                    "fusion_score": 0.812345,
                    "cycle_score": 0.7,
                    "lifecourt_proxy_score": 0.6,
                    "attention_score": 0.55,
                    "price_confirm_score": 0.8,
                    "crowding_penalty": 0.1,
                    "confidence": "medium",
                    "reason": "Fusion observation-only candidate",
                    "evidence": {
                        "source_kinds": ["factor_screen", "theme_breakout"],
                        "sector_rank": 1,
                    },
                }
            ],
        }
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 1
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select signal_kind, stock_code, stock_name, candidate_rank,
                   close_strength, signal_evidence_json, return_1d, vendor_version
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[:5] == ("hybrid_fusion", stock, "Hybrid C", 1, 0.8)
    evidence = json.loads(row[5])
    assert evidence["signal_kind"] == "hybrid_fusion"
    assert evidence["formula_version"] == "rv_hybrid_fusion_candidates_v1"
    assert evidence["fusion_score"] == 0.812345
    assert evidence["cycle_score"] == 0.7
    assert evidence["lifecourt_proxy_score"] == 0.6
    assert evidence["attention_score"] == 0.55
    assert evidence["price_confirm_score"] == 0.8
    assert evidence["crowding_penalty"] == 0.1
    assert evidence["confidence"] == "medium"
    assert evidence["source_kinds"] == ["factor_screen", "theme_breakout"]
    assert abs(float(row[6]) - 0.1) < 1e-12
    assert row[7].startswith("vv_livermore_candidate_history_")


def test_task_reports_no_strategy_signals_when_payload_has_no_candidates(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "empty-signals.duckdb"
    snap = date(2026, 5, 1)
    _seed_calendar_observations(str(db_path), stock_code="000007.SZ", start=snap, days=25)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(as_of_date=snap.isoformat(), items=[])
        payload["theme_breakout"] = {"items": []}
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["status"] == "partial"
    assert out["row_count"] == 0
    assert out["skipped_count"] == 1
    assert out["skipped"] == ["no_strategy_signals"]


def test_task_dedupe_second_run(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "ded.duckdb"
    snap = date(2026, 2, 2)
    stock = "000003.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=30)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Ded", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))
    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        n = conn.execute(
            "select count(*)::integer from livermore_candidate_history where snapshot_as_of_date = ?",
            [snap.isoformat()],
        ).fetchone()
        assert n is not None and int(n[0]) == 1
    finally:
        conn.close()


def test_backfill_materializes_available_trade_dates_and_summarizes_results(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "backfill.duckdb"
    stock = "000006.SZ"
    start = date(2026, 4, 1)
    _seed_calendar_observations(str(db_path), stock_code=stock, start=start, days=30)
    seen_dates: list[str] = []

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        as_of = kwargs.get("as_of_date")
        assert isinstance(as_of, date)
        seen_dates.append(as_of.isoformat())
        return _fake_payload(
            as_of_date=as_of.isoformat(),
            items=[
                {
                    "rank": 1,
                    "stock_code": stock,
                    "stock_name": "Backfill",
                    "sector_code": "S1",
                    "sector_name": "Sec",
                }
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = backfill_livermore_candidate_history(
        str(db_path),
        start_date="2026-04-03",
        end_date="2026-04-05",
    )

    assert out["status"] == "ok"
    assert out["processed_date_count"] == 3
    assert out["row_count"] == 3
    assert seen_dates == ["2026-04-03", "2026-04-04", "2026-04-05"]
    assert out["dates"] == [
        {"as_of_date": "2026-04-03", "status": "ok", "row_count": 1, "skipped_count": 0, "skipped": []},
        {"as_of_date": "2026-04-04", "status": "ok", "row_count": 1, "skipped_count": 0, "skipped": []},
        {"as_of_date": "2026-04-05", "status": "ok", "row_count": 1, "skipped_count": 0, "skipped": []},
    ]

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        count = conn.execute("select count(*)::integer from livermore_candidate_history").fetchone()
        complete = conn.execute(
            "select count(*)::integer from livermore_candidate_history where data_status = 'complete'"
        ).fetchone()
    finally:
        conn.close()
    assert count is not None and count[0] == 3
    assert complete is not None and complete[0] == 3


def test_candidate_history_run_cli_single_date_emits_json(monkeypatch, capsys, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    calls: list[tuple[str, str | None, str | None]] = []

    def _fake_materialize(
        path: str,
        *,
        as_of_date: str | None = None,
        stock_candidate_policy: str | None = None,
    ) -> dict[str, object]:
        calls.append((path, as_of_date, stock_candidate_policy))
        return {"status": "ok", "row_count": 2, "snapshot_as_of_date": as_of_date}

    monkeypatch.setattr(run_module, "materialize_livermore_candidate_history", _fake_materialize)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_candidate_history_run",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--as-of-date",
            "2026-04-03",
        ],
    )

    run_module.main()

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-03", None)]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["row_count"] == 2


def test_candidate_history_run_cli_backfill_emits_json(monkeypatch, capsys, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    calls: list[tuple[str, str, str, str | None]] = []

    def _fake_backfill(
        path: str,
        *,
        start_date: str,
        end_date: str,
        stock_candidate_policy: str | None = None,
    ) -> dict[str, object]:
        calls.append((path, start_date, end_date, stock_candidate_policy))
        return {"status": "partial", "processed_date_count": 2}

    monkeypatch.setattr(run_module, "backfill_livermore_candidate_history", _fake_backfill)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_candidate_history_run",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--start-date",
            "2026-04-03",
            "--end-date",
            "2026-04-04",
        ],
    )

    run_module.main()

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-03", "2026-04-04", None)]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "partial"
    assert out["processed_date_count"] == 2


def test_candidate_history_run_cli_backfill_passes_stock_candidate_policy(monkeypatch, capsys, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    calls: list[tuple[str, str, str, str | None]] = []

    def _fake_backfill(
        path: str,
        *,
        start_date: str,
        end_date: str,
        stock_candidate_policy: str | None = None,
    ) -> dict[str, object]:
        calls.append((path, start_date, end_date, stock_candidate_policy))
        return {"status": "ok", "processed_date_count": 2}

    monkeypatch.setattr(run_module, "backfill_livermore_candidate_history", _fake_backfill)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_candidate_history_run",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--start-date",
            "2026-04-03",
            "--end-date",
            "2026-04-04",
            "--stock-candidate-policy",
            "exp3b",
        ],
    )

    run_module.main()

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-03", "2026-04-04", "exp3b")]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["processed_date_count"] == 2


def test_candidate_history_run_cli_execution_only_single_date_emits_json(monkeypatch, capsys, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    calls: list[tuple[str, str, str]] = []

    def _fake_backfill_execution(
        path: str,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, object]:
        calls.append((path, start_date, end_date))
        return {"status": "ok", "execution_row_count": 3, "start_date": start_date, "end_date": end_date}

    monkeypatch.setattr(
        run_module,
        "backfill_livermore_candidate_execution_history",
        _fake_backfill_execution,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_candidate_history_run",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--execution-only",
            "--as-of-date",
            "2026-04-03",
        ],
    )

    run_module.main()

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-03", "2026-04-03")]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["execution_row_count"] == 3
    assert out["start_date"] == "2026-04-03"
    assert out["end_date"] == "2026-04-03"


def test_candidate_history_run_cli_execution_only_range_emits_json(monkeypatch, capsys, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    calls: list[tuple[str, str, str]] = []

    def _fake_backfill_execution(
        path: str,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, object]:
        calls.append((path, start_date, end_date))
        return {"status": "partial", "execution_row_count": 5, "start_date": start_date, "end_date": end_date}

    monkeypatch.setattr(
        run_module,
        "backfill_livermore_candidate_execution_history",
        _fake_backfill_execution,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_candidate_history_run",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--execution-only",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-04-03",
        ],
    )

    run_module.main()

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-01", "2026-04-03")]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "partial"
    assert out["execution_row_count"] == 5
    assert out["start_date"] == "2026-04-01"
    assert out["end_date"] == "2026-04-03"


def test_candidate_history_run_cli_rejects_mixed_single_date_and_backfill(monkeypatch, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_candidate_history_run",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--as-of-date",
            "2026-04-03",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-04-04",
        ],
    )

    try:
        run_module.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse SystemExit")


def test_service_summary_counts_signal_kinds_and_excludes_missing_forward_returns(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              return_1d_adj double,
              return_5d_adj double,
              return_10d_adj double,
              return_20d_adj double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar,
              signal_kind varchar,
              theme_key varchar,
              theme_name varchar,
              theme_source_kind varchar,
              theme_rank integer,
              stock_rank_in_theme integer,
              sector_rank integer,
              strength_pctchange double,
              strength_turn double,
              strength_amplitude double,
              close_strength double,
              closed_up_limit boolean,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-05-01",
                    "688001.SH",
                    "A",
                    1,
                    "801080",
                    "Electronic",
                    100.0,
                    "2026-05-02",
                    None,
                    None,
                    -0.1,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                    "theme_breakout",
                    "concept:C001",
                    "Chiplet",
                    "real_concept",
                    1,
                    1,
                    9,
                    12.1,
                    4.2,
                    7.0,
                    0.86,
                    True,
                    '{"market_state":"HOT"}',
                ),
                (
                    "2026-05-01",
                    "000001.SZ",
                    "B",
                    2,
                    "801780",
                    "Bank",
                    10.0,
                    "2026-05-02",
                    "2026-05-08",
                    "2026-05-28",
                    0.02,
                    0.03,
                    0.04,
                    None,
                    None,
                    None,
                    None,
                    "complete",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    None,
                    None,
                    2,
                    None,
                    None,
                    None,
                    0.75,
                    False,
                    "not-json",
                ),
            ],
        )
        _minimal_observation_schema(conn)
        stock_b_dates = [
            "2026-05-02",
            "2026-05-03",
            "2026-05-04",
            "2026-05-05",
            "2026-05-08",
            *[f"2026-05-{day:02d}" for day in range(9, 23)],
            "2026-05-28",
        ]
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [("2026-05-02", "688001.SH", 101.0)]
            + [(trade_date, "000001.SZ", 10.0 + index) for index, trade_date in enumerate(stock_b_dates)],
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        limit=10,
    )

    result = envelope["result"]
    assert isinstance(result, dict)
    summary = result["summary"]
    forward_maturity = summary.pop("forward_maturity")
    assert forward_maturity["evaluation_as_of_date"] == "2026-05-28"
    assert all(
        horizon["row_count"] == 2
        for horizon in forward_maturity["horizons"].values()
    )
    assert summary == {
        "row_count": 2,
        "complete_count": 1,
        "pending_count": 1,
        "partial_halt_count": 0,
        "forward_coverage_counts": {"complete": 1, "pending": 1, "missing_bar": 0, "partial_halt": 0},
        "missing_forward_return_count": 1,
        "avg_return_1d": -0.04,
        "avg_return_5d": 0.03,
        "avg_return_10d": None,
        "avg_return_20d": 0.04,
        "horizon_stats": {
            "return_1d": {
                "available_count": 2,
                "missing_count": 0,
                "positive_count": 1,
                "non_positive_count": 1,
                "avg_return": -0.04,
                "median_return": -0.04,
                "win_rate": 0.5,
            },
            "return_5d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.03,
                "median_return": 0.03,
                "win_rate": 1.0,
            },
            "return_10d": {
                "available_count": 0,
                "missing_count": 2,
                "positive_count": 0,
                "non_positive_count": 0,
                "avg_return": None,
                "median_return": None,
                "win_rate": None,
            },
            "return_20d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.04,
                "median_return": 0.04,
                "win_rate": 1.0,
            },
        },
        "by_signal_kind": {"stock_candidate": 1, "theme_breakout": 1},
        "by_signal_kind_horizon_stats": {
            "stock_candidate": {
                "return_1d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.02,
                    "median_return": 0.02,
                    "win_rate": 1.0,
                },
                "return_5d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.03,
                    "median_return": 0.03,
                    "win_rate": 1.0,
                },
                "return_10d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
                "return_20d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.04,
                    "median_return": 0.04,
                    "win_rate": 1.0,
                },
            },
            "theme_breakout": {
                "return_1d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 0,
                    "non_positive_count": 1,
                    "avg_return": -0.1,
                    "median_return": -0.1,
                    "win_rate": 0.0,
                },
                "return_5d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
                "return_10d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
                "return_20d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
            },
        },
    }


def test_service_adds_backtest_window_summary_with_unsupported_pending_completed_and_proxy_only_dates(tmp_path) -> None:
    db_path = tmp_path / "replay-window.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              return_1d_adj double,
              return_5d_adj double,
              return_10d_adj double,
              return_20d_adj double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar,
              signal_kind varchar,
              theme_key varchar,
              theme_name varchar,
              theme_source_kind varchar,
              theme_rank integer,
              stock_rank_in_theme integer,
              sector_rank integer,
              strength_pctchange double,
              strength_turn double,
              strength_amplitude double,
              close_strength double,
              closed_up_limit boolean,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-05-07",
                    "688001.SH",
                    "Proxy Theme",
                    1,
                    "801080",
                    "Electronic",
                    100.0,
                    "2026-05-08",
                    "2026-05-14",
                    "2026-06-05",
                    0.01,
                    0.03,
                    0.08,
                    None,
                    None,
                    None,
                    None,
                    "complete",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                    "theme_breakout",
                    "proxy:C001",
                    "Proxy Chiplet",
                    "proxy",
                    1,
                    1,
                    9,
                    8.1,
                    4.0,
                    6.5,
                    0.82,
                    True,
                    '{"market_state":"HOT"}',
                ),
                (
                    "2026-05-08",
                    "000001.SZ",
                    "Pending Candidate",
                    1,
                    "801780",
                    "Bank",
                    10.0,
                    "2026-05-09",
                    None,
                    None,
                    0.02,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r2",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    None,
                    None,
                    2,
                    None,
                    None,
                    None,
                    0.75,
                    False,
                    "not-json",
                ),
            ],
        )
        conn.execute("alter table livermore_candidate_history add column forward_trade_date_10d varchar")
        conn.execute("alter table livermore_candidate_history add column return_10d double")
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_10d = '2026-05-21',
                return_10d = 0.05,
                return_1d_adj = 0.01,
                return_5d_adj = 0.03,
                return_10d_adj = 0.05,
                return_20d_adj = 0.08
            where stock_code = '688001.SH'
            """
        )
        conn.execute(
            """
            create table choice_stock_request_audit (
              as_of_date varchar,
              input_family varchar,
              field_key varchar,
              status varchar,
              row_count integer
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              field_key varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              field_key varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              as_of_date varchar,
              stock_code varchar,
              field_key varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              field_keys_json varchar,
              pctchange double,
              turn double,
              amplitude double,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        for trade_date in ("2026-04-30", "2026-05-06", "2026-05-07", "2026-05-08"):
            conn.executemany(
                "insert into choice_stock_request_audit values (?, ?, ?, ?, ?)",
                [
                    (trade_date, "stock_universe", "a_share_universe_sector_001004", "completed", 1),
                    (trade_date, "sector_membership", "sw2021_industry_membership", "completed", 1),
                    (trade_date, "sector_strength", "daily_return_turnover_amplitude", "completed", 1),
                    (trade_date, "stock_ohlcv", "daily_ohlcv_amount", "completed", 1),
                    (trade_date, "stock_status", "daily_trade_status", "completed", 1),
                    (
                        trade_date,
                        "limit_up_quality",
                        "daily_limit_flags",
                        "completed" if trade_date != "2026-04-30" else "partial",
                        1 if trade_date != "2026-04-30" else 0,
                    ),
                    (trade_date, "limit_up_quality", "point_in_time_limit_streaks", "completed", 1),
                ],
            )
            conn.execute(
                "insert into choice_stock_universe values (?, ?, ?)",
                [trade_date, "000001.SZ", "a_share_universe_sector_001004"],
            )
            conn.execute(
                "insert into choice_stock_sector_membership values (?, ?, ?)",
                [trade_date, "000001.SZ", "sw2021_industry_membership"],
            )
            conn.execute(
                "insert into choice_stock_limit_quality values (?, ?, ?)",
                [trade_date, "000001.SZ", "point_in_time_limit_streaks"],
            )
            field_keys = [
                "daily_return_turnover_amplitude",
                "daily_ohlcv_amount",
                "daily_trade_status",
            ]
            highlimit = None
            lowlimit = None
            if trade_date != "2026-04-30":
                field_keys.append("daily_limit_flags")
                highlimit = 11.0
                lowlimit = 9.0
            conn.execute(
                """
                insert into choice_stock_daily_observation values
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trade_date,
                    "000001.SZ",
                    str(field_keys).replace("'", '"'),
                    0.01,
                    1.2,
                    0.8,
                    10.0,
                    10.5,
                    9.8,
                    10.2,
                    1000.0,
                    10000.0,
                    "交易",
                    highlimit,
                    lowlimit,
                ],
            )
        proxy_dates = [
            "2026-05-08",
            "2026-05-11",
            "2026-05-12",
            "2026-05-13",
            "2026-05-14",
            "2026-05-15",
            "2026-05-18",
            "2026-05-19",
            "2026-05-20",
            "2026-05-21",
            "2026-05-22",
            "2026-05-25",
            "2026-05-26",
            "2026-05-27",
            "2026-05-28",
            "2026-05-29",
            "2026-06-01",
            "2026-06-02",
            "2026-06-03",
            "2026-06-05",
        ]
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            (trade_date, stock_code, close_value, tradestatus)
            values (?, '688001.SH', ?, 'Trading')
            """,
            [(trade_date, 100.0 + index) for index, trade_date in enumerate(proxy_dates)],
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-04-30",
        snapshot_to="2026-05-08",
        limit=20,
    )

    result = envelope["result"]
    assert isinstance(result, dict)
    assert result["backtest_window_summary"] == {
        "status": "partial",
        "snapshot_from": "2026-04-30",
        "snapshot_to": "2026-05-08",
        "replay_dates_total": 4,
        "replay_dates_completed": 1,
        "replay_dates_pending": 1,
        "replay_dates_unsupported": 1,
        "replay_dates_proxy_only": 1,
        "completed_rows": 0,
        "pending_rows": 1,
        "unsupported_rows": 0,
        "proxy_only_rows": 1,
            "forward_coverage_row_counts": {"complete": 1, "pending": 1, "missing_bar": 0, "partial_halt": 0},
            "outcome_evaluation_as_of_date": "2026-06-05",
        "included_completed_stats_dates": ["2026-05-06"],
        "excluded_from_completed_stats_dates": ["2026-04-30", "2026-05-07", "2026-05-08"],
        "date_reasons": [
            {
                "trade_date": "2026-04-30",
                "status": "unsupported",
                "reason_code": "missing_daily_limit_flags",
                "message": "daily_limit_flags absent; Livermore strategy replay unsupported for 2026-04-30.",
                "affects_completed_stats": False,
                "signal_kinds": ["hybrid_fusion", "stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
            },
            {
                "trade_date": "2026-05-06",
                "status": "completed",
                "reason_code": "no_strategy_signals",
                "message": "Full replay coverage produced no Livermore strategy signal rows for 2026-05-06.",
                "affects_completed_stats": True,
                "signal_kinds": ["hybrid_fusion", "stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
            },
            {
                "trade_date": "2026-05-07",
                "status": "proxy_only",
                "reason_code": "proxy_theme_only",
                "message": "Theme breakout replay for 2026-05-07 relies on proxy-only theme evidence.",
                "affects_completed_stats": False,
                "signal_kinds": ["theme_breakout"],
            },
            {
                "trade_date": "2026-05-08",
                "status": "pending",
                "reason_code": "forward_returns_pending",
                "message": "Forward return bars are not available yet; exclude 2026-05-08 from completed forward-return statistics.",
                "affects_completed_stats": False,
                "signal_kinds": ["stock_candidate"],
                "missing_bar_row_count": 0,
            },
        ],
    }


def test_backtest_summary_reports_incomplete_coverage_when_audit_is_missing_but_daily_flags_landed(tmp_path) -> None:
    db_path = tmp_path / "audit-missing.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.execute(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date, stock_code, data_status, signal_kind
            ) values ('2026-05-06', '000001.SZ', 'pending', 'stock_candidate')
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-06")
        conn.execute("delete from choice_stock_request_audit where as_of_date = '2026-05-06'")
    finally:
        conn.close()

    summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-05-06",
        snapshot_to="2026-05-06",
    )

    reason = summary["date_reasons"][0]
    assert summary["status"] == "unsupported"
    assert reason["reason_code"] == "missing_required_source_table"
    assert "Required source coverage is incomplete for 2026-05-06" in reason["message"]
    assert "daily_limit_flags absent" not in reason["message"]


def test_historical_evaluation_masks_later_complete_rows_from_backtest_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from backend.app.services import livermore_candidate_history_service as service

    def fail_legacy_calendar_read(*args, **kwargs) -> None:
        pytest.fail("historical replay must not load the unbounded legacy observation calendar")

    monkeypatch.setattr(service, "_load_observation_trade_dates", fail_legacy_calendar_read)
    db_path = tmp_path / "historical-replay-cutoff.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.execute(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date,
              stock_code,
              stock_name,
              candidate_rank,
              selection_close,
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
              source_version,
              vendor_version,
              rule_version,
              run_id,
              signal_kind
            ) values (
              '2026-05-01',
              '000001.SZ',
              'Later Complete',
              1,
              10.0,
              '2026-05-02',
              '2026-05-06',
              '2026-05-11',
              '2026-05-21',
              0.01,
              0.05,
              0.10,
              0.20,
              0.01,
              0.05,
              0.10,
              0.20,
              'complete',
              'fv1',
              'sv1',
              'vv1',
              'rv1',
              'run-later-complete',
              'stock_candidate'
            )
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        conn.executemany(
            """
            insert into choice_stock_daily_observation values
            (?, '000001.SZ', '[]', 0.01, 1.2, 0.8, 10.0, 10.5, 9.8, ?, 1000.0, 10000.0, 'trading', 11.0, 9.0)
            """,
            [
                ((date(2026, 5, 2) + timedelta(days=offset)).isoformat(), 10.3 + offset * 0.1)
                for offset in range(20)
            ],
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-31",
        limit=10,
        evaluation_as_of_date="2026-05-01",
    )

    result = cast(dict[str, object], envelope["result"])
    summary = cast(dict[str, object], result["backtest_window_summary"])
    assert result["effective_snapshot_to"] == "2026-05-01"
    assert summary["snapshot_to"] == "2026-05-01"
    assert summary["replay_dates_completed"] == 0
    assert summary["replay_dates_pending"] == 1
    assert summary["included_completed_stats_dates"] == []
    assert summary["excluded_from_completed_stats_dates"] == ["2026-05-01"]
    assert summary["date_reasons"] == [
        {
            "trade_date": "2026-05-01",
            "status": "pending",
            "reason_code": "forward_returns_pending",
            "message": "Forward return bars are not available yet; exclude 2026-05-01 from completed forward-return statistics.",
            "affects_completed_stats": False,
            "signal_kinds": ["stock_candidate"],
            "missing_bar_row_count": 0,
        }
    ]


def test_service_reports_decision_usable_mature_return_stats_for_completed_dates_only(tmp_path) -> None:
    db_path = tmp_path / "mature-stats.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              return_1d_adj double,
              return_5d_adj double,
              return_10d_adj double,
              return_20d_adj double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar,
              signal_kind varchar,
              theme_key varchar,
              theme_name varchar,
              theme_source_kind varchar,
              theme_rank integer,
              stock_rank_in_theme integer,
              sector_rank integer,
              strength_pctchange double,
              strength_turn double,
              strength_amplitude double,
              close_strength double,
              closed_up_limit boolean,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-05-06",
                    "000001.SZ",
                    "Winner",
                    1,
                    "S1",
                    "Sector",
                    10.0,
                    "2026-05-07",
                    "2026-05-13",
                    "2026-06-03",
                    0.02,
                    0.10,
                    0.20,
                    0.03,
                    0.12,
                    None,
                    0.22,
                    "complete",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    None,
                    None,
                    None,
                    0.9,
                    False,
                    '{"market_state":"HOT"}',
                ),
                (
                    "2026-05-08",
                    "000002.SZ",
                    "Pending",
                    2,
                    "S1",
                    "Sector",
                    20.0,
                    "2026-05-11",
                    None,
                    None,
                    -0.01,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r2",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    None,
                    None,
                    None,
                    0.8,
                    False,
                    "not-json",
                ),
            ],
        )
        conn.execute("alter table livermore_candidate_history add column forward_trade_date_10d varchar")
        conn.execute("alter table livermore_candidate_history add column return_10d double")
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_10d = '2026-05-18',
                return_10d = 0.15,
                return_10d_adj = 0.15
            where stock_code = '000001.SZ'
            """
        )
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              signal_kind varchar,
              market_state varchar,
              entry_executable boolean,
              entry_block_reason varchar,
              return_1d_net_adj double,
              return_5d_net_adj double,
              return_10d_net_adj double,
              return_20d_net_adj double
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_execution_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-05-06",
                    "000001.SZ",
                    "stock_candidate",
                    "HOT",
                    True,
                    None,
                    0.01,
                    0.08,
                    None,
                    0.12,
                ),
                (
                    "2026-05-06",
                    "000003.SZ",
                    "theme_breakout",
                    "HOT",
                    False,
                    "entry_limit_up_or_one_line",
                    None,
                    None,
                    None,
                    None,
                ),
                (
                    "2026-05-08",
                    "000002.SZ",
                    "stock_candidate",
                    "HOT",
                    True,
                    None,
                    0.99,
                    0.99,
                    0.99,
                    0.99,
                ),
            ],
        )
        conn.execute(
            """
            create table livermore_matched_baseline_history (
              signal_date varchar,
              candidate_stock_code varchar,
              signal_kind varchar,
              control_stock_code varchar,
              control_group varchar,
              control_return_1d_net_adj double,
              control_return_5d_net_adj double,
              control_return_10d_net_adj double,
              control_return_20d_net_adj double,
              control_entry_executable boolean,
              seed varchar,
              formula_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_matched_baseline_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-05-06",
                    "000001.SZ",
                    "stock_candidate",
                    "000101.SZ",
                    "same_sector",
                    0.0,
                    0.02,
                    None,
                    0.04,
                    True,
                    "seed-a",
                    "fv_test",
                    "run-test",
                ),
                (
                    "2026-05-06",
                    "000001.SZ",
                    "stock_candidate",
                    "000102.SZ",
                    "same_sector",
                    0.0,
                    0.04,
                    None,
                    0.08,
                    True,
                    "seed-a",
                    "fv_test",
                    "run-test",
                ),
                (
                    "2026-05-08",
                    "000002.SZ",
                    "stock_candidate",
                    "000103.SZ",
                    "same_sector",
                    0.0,
                    0.01,
                    0.01,
                    0.01,
                    True,
                    "seed-b",
                    "fv_test",
                    "run-test",
                ),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-06")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-08")
        winner_dates = [
            "2026-05-07",
            "2026-05-08",
            "2026-05-11",
            "2026-05-12",
            "2026-05-13",
            *[f"2026-05-{day:02d}" for day in range(14, 28)],
            "2026-06-03",
        ]
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            (trade_date, stock_code, close_value, tradestatus)
            values (?, '000001.SZ', ?, 'Trading')
            """,
            [(trade_date, 10.0 + index) for index, trade_date in enumerate(winner_dates)],
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation
            (trade_date, stock_code, close_value, tradestatus)
            values ('2026-05-11', '000002.SZ', 19.8, 'Trading')
            """
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-05-06",
        snapshot_to="2026-05-08",
        limit=20,
    )

    result = envelope["result"]
    assert isinstance(result, dict)
    summary = result["summary"]
    assert summary["row_count"] == 2
    assert summary["avg_return_1d"] == 0.005
    assert summary["by_signal_kind"] == {"stock_candidate": 2}
    assert summary["decision_usable_stats"] == {
        "metric_basis": "adjusted_close_return",
        "adj_coverage_count": 1,
        "adj_coverage_total": 1,
        "adj_coverage_ratio": 1.0,
        "row_count": 1,
        "complete_row_count": 1,
        "pending_row_count": 0,
        "partial_halt_row_count": 0,
        "missing_forward_return_count": 0,
        "avg_return_1d": 0.03,
        "avg_return_5d": 0.12,
        "avg_return_10d": 0.15,
        "avg_return_20d": 0.22,
        "win_rate_1d": 1.0,
        "win_rate_5d": 1.0,
        "win_rate_10d": 1.0,
        "win_rate_20d": 1.0,
        "by_signal_kind": {"stock_candidate": 1},
        "by_signal_kind_horizon_stats": {
            "stock_candidate": {
                "return_1d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.03,
                    "median_return": 0.03,
                    "win_rate": 1.0,
                },
                "return_5d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.12,
                    "median_return": 0.12,
                    "win_rate": 1.0,
                },
                "return_10d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.15,
                    "median_return": 0.15,
                    "win_rate": 1.0,
                },
                "return_20d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.22,
                    "median_return": 0.22,
                    "win_rate": 1.0,
                },
            }
        },
        "included_snapshot_dates": ["2026-05-06"],
        "excluded_snapshot_dates": ["2026-05-08"],
    }
    execution_stats = summary["execution_usable_stats"]
    assert execution_stats["metric_basis"] == "net_next_open_adj"
    assert execution_stats["row_count"] == 1
    assert execution_stats["execution_row_count"] == 2
    assert execution_stats["horizon_usable_stats"]["return_5d"]["avg_return"] == 0.08
    assert execution_stats["horizon_usable_stats"]["return_10d"]["adj_missing_n"] == 1
    assert execution_stats["by_signal_kind_horizon_usable_stats"]["stock_candidate"]["return_20d"]["p90"] == 0.12
    assert summary["by_market_state_signal_kind_execution_stats"]["HOT"]["stock_candidate"]["return_5d"][
        "avg_return"
    ] == 0.08
    assert summary["entry_blocked_stats"]["blocked_row_count"] == 1
    assert summary["entry_blocked_stats"]["by_reason"]["entry_limit_up_or_one_line"] == {
        "count": 1,
        "share": 0.5,
    }
    matched_t5 = summary["matched_baseline_stats"]["stock_candidate"]["return_5d"]
    assert matched_t5["n"] == 1
    assert matched_t5["paired_alpha_avg"] == 0.05
    assert matched_t5["paired_alpha_median"] == 0.05
    assert matched_t5["bootstrap_ci_95"]["low"] == 0.05
    assert matched_t5["bootstrap_ci_95"]["high"] == 0.05
    assert summary["horizon_usable_stats"] == {
        "return_1d": {
            "available_count": 2,
            "missing_count": 0,
            "positive_count": 1,
            "non_positive_count": 1,
            "avg_return": 0.005,
            "median_return": 0.005,
            "win_rate": 0.5,
        },
        "return_5d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.1,
            "median_return": 0.1,
            "win_rate": 1.0,
        },
        "return_10d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.15,
            "median_return": 0.15,
            "win_rate": 1.0,
        },
        "return_20d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.2,
            "median_return": 0.2,
            "win_rate": 1.0,
        },
    }
    assert summary["by_signal_kind_horizon_usable_stats"] == {
        "stock_candidate": {
            "return_1d": {
                "available_count": 2,
                "missing_count": 0,
                "positive_count": 1,
                "non_positive_count": 1,
                "avg_return": 0.005,
                "median_return": 0.005,
                "win_rate": 0.5,
            },
            "return_5d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.1,
                "median_return": 0.1,
                "win_rate": 1.0,
            },
            "return_10d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.15,
                "median_return": 0.15,
                "win_rate": 1.0,
            },
            "return_20d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.2,
                "median_return": 0.2,
                "win_rate": 1.0,
            },
        }
    }
    assert summary["by_market_state_signal_kind_horizon_stats"] == {
        "HOT": {
            "stock_candidate": {
                "return_1d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.02,
                    "median_return": 0.02,
                    "win_rate": 1.0,
                },
                "return_5d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.1,
                    "median_return": 0.1,
                    "win_rate": 1.0,
                },
                "return_10d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.15,
                    "median_return": 0.15,
                    "win_rate": 1.0,
                },
                "return_20d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.2,
                    "median_return": 0.2,
                    "win_rate": 1.0,
                },
            }
        },
        "unknown": {
            "stock_candidate": {
                "return_1d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 0,
                    "non_positive_count": 1,
                    "avg_return": -0.01,
                    "median_return": -0.01,
                    "win_rate": 0.0,
                },
                "return_5d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
                "return_10d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
                "return_20d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "median_return": None,
                    "win_rate": None,
                },
            }
        },
    }


def test_service_reports_horizon_success_stats_for_mature_forward_returns(tmp_path) -> None:
    db_path = tmp_path / "horizon-stats.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar,
              signal_kind varchar,
              theme_key varchar,
              theme_name varchar,
              theme_source_kind varchar,
              theme_rank integer,
              stock_rank_in_theme integer,
              sector_rank integer,
              strength_pctchange double,
              strength_turn double,
              strength_amplitude double,
              close_strength double,
              closed_up_limit boolean,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-05-06",
                    "000001.SZ",
                    "Winner",
                    1,
                    "S1",
                    "Sector",
                    10.0,
                    "2026-05-07",
                    "2026-05-13",
                    None,
                    0.02,
                    0.10,
                    None,
                    "pending",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    None,
                    None,
                    None,
                    0.9,
                    False,
                    "{}",
                ),
                (
                    "2026-05-07",
                    "000002.SZ",
                    "Loser",
                    2,
                    "S1",
                    "Sector",
                    20.0,
                    "2026-05-08",
                    None,
                    None,
                    -0.01,
                    None,
                    None,
                    "pending",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r2",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    None,
                    None,
                    None,
                    0.8,
                    False,
                    "{}",
                ),
            ],
        )
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [
                ("2026-05-07", "000001.SZ", 10.2),
                ("2026-05-08", "000001.SZ", 10.3),
                ("2026-05-11", "000001.SZ", 10.4),
                ("2026-05-12", "000001.SZ", 10.5),
                ("2026-05-13", "000001.SZ", 11.0),
                ("2026-05-08", "000002.SZ", 19.8),
            ],
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-05-06",
        snapshot_to="2026-05-07",
        limit=20,
    )

    result = envelope["result"]
    assert isinstance(result, dict)
    summary = result["summary"]
    assert summary["horizon_stats"] == {
        "return_1d": {
            "available_count": 2,
            "missing_count": 0,
            "positive_count": 1,
            "non_positive_count": 1,
            "avg_return": 0.005,
            "median_return": 0.005,
            "win_rate": 0.5,
        },
        "return_5d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.1,
            "median_return": 0.1,
            "win_rate": 1.0,
        },
        "return_10d": {
            "available_count": 0,
            "missing_count": 2,
            "positive_count": 0,
            "non_positive_count": 0,
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
        },
        "return_20d": {
            "available_count": 0,
            "missing_count": 2,
            "positive_count": 0,
            "non_positive_count": 0,
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
        },
    }


def test_backtest_window_does_not_treat_missing_history_table_as_zero_signal_date(tmp_path) -> None:
    db_path = tmp_path / "missing-history.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_request_audit (
              as_of_date varchar,
              input_family varchar,
              field_key varchar,
              status varchar,
              row_count integer
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              field_key varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              field_key varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              as_of_date varchar,
              stock_code varchar,
              field_key varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              field_keys_json varchar,
              pctchange double,
              turn double,
              amplitude double,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        trade_date = "2026-05-06"
        conn.executemany(
            "insert into choice_stock_request_audit values (?, ?, ?, ?, ?)",
            [
                (trade_date, "stock_universe", "a_share_universe_sector_001004", "completed", 1),
                (trade_date, "sector_membership", "sw2021_industry_membership", "completed", 1),
                (trade_date, "sector_strength", "daily_return_turnover_amplitude", "completed", 1),
                (trade_date, "stock_ohlcv", "daily_ohlcv_amount", "completed", 1),
                (trade_date, "stock_status", "daily_trade_status", "completed", 1),
                (trade_date, "limit_up_quality", "daily_limit_flags", "completed", 1),
                (trade_date, "limit_up_quality", "point_in_time_limit_streaks", "completed", 1),
            ],
        )
        conn.execute(
            "insert into choice_stock_universe values (?, ?, ?)",
            [trade_date, "000001.SZ", "a_share_universe_sector_001004"],
        )
        conn.execute(
            "insert into choice_stock_sector_membership values (?, ?, ?)",
            [trade_date, "000001.SZ", "sw2021_industry_membership"],
        )
        conn.executemany(
            "insert into choice_stock_limit_quality values (?, ?, ?)",
            [
                (trade_date, "000001.SZ", "daily_limit_flags"),
                (trade_date, "000001.SZ", "point_in_time_limit_streaks"),
            ],
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                trade_date,
                "000001.SZ",
                '["daily_return_turnover_amplitude","daily_ohlcv_amount","daily_trade_status","daily_limit_flags"]',
                0.01,
                1.2,
                0.8,
                10.0,
                10.5,
                9.8,
                10.2,
                1000.0,
                10000.0,
                "交易",
                11.0,
                9.0,
            ],
        )
    finally:
        conn.close()

    summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-05-06",
        snapshot_to="2026-05-06",
    )

    assert summary["status"] == "unsupported"
    assert summary["replay_dates_completed"] == 0
    assert summary["included_completed_stats_dates"] == []
    assert summary["date_reasons"] == [
        {
            "trade_date": "2026-05-06",
            "status": "unsupported",
            "reason_code": "missing_required_source_table",
            "message": "livermore_candidate_history table absent; cannot distinguish no-signal dates from missing candidate-history materialization for 2026-05-06.",
            "affects_completed_stats": False,
            "signal_kinds": ["hybrid_fusion", "stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
        }
    ]


def test_api_happy_and_filters(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-04-01",
                    "000001.SZ",
                    "A",
                    1,
                    "S",
                    "Sec",
                    10.0,
                    "2026-04-02",
                    "2026-04-08",
                    "2026-04-28",
                    0.01,
                    0.02,
                    0.03,
                    "complete",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                ),
                (
                    "2026-03-15",
                    "000001.SZ",
                    "A",
                    1,
                    None,
                    None,
                    9.5,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    "fv1",
                    "sv2",
                    "vv2",
                    "rv1",
                    "r2",
                ),
            ],
        )
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    r = client.get(
        "/ui/market-data/livermore/candidate-history",
        params={"stock_code": "000001.SZ", "snapshot_from": "2026-04-01", "snapshot_to": "2026-04-30", "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["rule_version"] == "rv_livermore_candidate_history_v1"
    assert "livermore_candidate_history" in body["result_meta"]["tables_used"]
    assert len(body["result"]["items"]) == 1

    cutoff_one = client.get(
        "/ui/market-data/livermore/candidate-history",
        params={
            "stock_code": "000001.SZ",
            "snapshot_from": "2026-04-01",
            "snapshot_to": "2026-04-30",
            "evaluation_as_of_date": "2026-04-01",
            "limit": 9,
        },
    )
    cutoff_two = client.get(
        "/ui/market-data/livermore/candidate-history",
        params={
            "stock_code": "000001.SZ",
            "snapshot_from": "2026-04-01",
            "snapshot_to": "2026-04-30",
            "evaluation_as_of_date": "2026-04-02",
            "limit": 9,
        },
    )
    assert cutoff_one.status_code == cutoff_two.status_code == 200
    assert cutoff_one.json()["result"]["evaluation_as_of_date"] == "2026-04-01"
    assert cutoff_two.json()["result"]["evaluation_as_of_date"] == "2026-04-02"

    r2 = client.get(
        "/ui/market-data/livermore/candidate-history",
        params={"stock_code": "000001.SZ"},
    )
    assert r2.status_code == 200
    assert len(r2.json()["result"]["items"]) == 2
    get_settings.cache_clear()


def test_api_empty_table(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    r = client.get("/ui/market-data/livermore/candidate-history")
    assert r.status_code == 200
    assert r.json()["result"]["items"] == []
    get_settings.cache_clear()


def test_api_limit_validation(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn_tbl = duckdb.connect(str(db_path), read_only=False)
    try:
        conn_tbl.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn_tbl.close()

    client = _build_client(tmp_path, monkeypatch)
    assert client.get("/ui/market-data/livermore/candidate-history", params={"limit": 0}).status_code == 422
    assert client.get("/ui/market-data/livermore/candidate-history", params={"limit": 501}).status_code == 422
    assert (
        client.get(
            "/ui/market-data/livermore/candidate-history",
            params={"evaluation_as_of_date": "2026-02-30"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()


def test_strategy_score_service_ranks_current_market_state_by_t5_score(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        factor_rows = [
            (
                "2026-05-01" if index <= 15 else "2026-05-02",
                f"000{index:03d}.SZ",
                f"Factor {index}",
                "factor_screen",
                0.01,
                0.025,
                0.03,
                '{"market_state":"HOT"}',
            )
            for index in range(1, 31)
        ]
        trend_rows = [
            (
                "2026-05-01" if index <= 15 else "2026-05-02",
                f"300{index:03d}.SZ",
                f"Trend {index}",
                "stock_candidate",
                0.01,
                0.018 if index <= 16 else -0.002,
                0.02,
                '{"market_state":"HOT"}',
            )
            for index in range(1, 31)
        ]
        _insert_strategy_score_rows(
            conn,
            [
                *factor_rows,
                *trend_rows,
                ("2026-05-01", "000999.SZ", "Theme A", "theme_breakout", 0.01, 0.20, 0.21, '{"market_state":"HOT"}'),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
        current_market_state="HOT",
        min_sample=2,
        primary_horizon="return_5d",
    )

    body = envelope["result"]
    assert isinstance(body, dict)
    assert body["primary_horizon"] == "return_5d"
    assert body["min_sample"] == 30
    assert body["review_thresholds"]["mature_min_sample"] == 30
    assert body["review_thresholds"]["official_t5_avg_return_band"] == {"lower": 0.012, "upper": 0.024}
    assert body["current_market_state"] == "HOT"
    assert "family_summaries" not in body
    current_rows = body["current_market_state_rows"]
    assert [row["signal_kind"] for row in current_rows] == ["factor_screen", "stock_candidate", "theme_breakout"]
    assert current_rows[0]["family_key"] == "factor_screen"
    assert current_rows[0]["family_contract_version"] == "rv_livermore_strategy_family_contract_v1"
    assert current_rows[0]["primary_sample_size"] == current_rows[0]["stats"]["return_5d"]["available_count"]
    assert current_rows[1]["family_key"] == "trend_core"
    assert current_rows[2]["family_key"] == "theme_breakout"
    assert current_rows[0]["strategy_label"] == "多因子"
    assert current_rows[0]["sample_status"] == "sufficient"
    assert current_rows[0]["priority_rank"] == 1
    assert current_rows[0]["priority_score"] == 102.5
    assert current_rows[0]["priority_label"] == "优先复核"
    assert current_rows[0]["stats"]["return_5d"] == {
        "available_count": 30,
        "missing_count": 0,
        "positive_count": 30,
        "non_positive_count": 0,
        "avg_return": 0.025,
        "median_return": 0.025,
        "win_rate": 1.0,
    }
    assert current_rows[1]["priority_label"] == "降权观察"
    assert current_rows[1]["priority_rank"] is None
    assert current_rows[2]["sample_status"] == "insufficient"
    assert current_rows[2]["priority_score"] is None
    assert "样本不足" in current_rows[2]["reason"]
    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.strategy_score"
    assert "livermore_candidate_history" in envelope["result_meta"]["tables_used"]


def test_strategy_score_service_labels_hybrid_fusion_rows(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score-hybrid.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2026-05-01" if index <= 15 else "2026-05-02",
                    f"000{index + 10:03d}.SZ",
                    f"Hybrid {index}",
                    "hybrid_fusion",
                    0.01,
                    0.03,
                    0.04,
                    '{"market_state":"HOT","fusion_score":0.81}',
                )
                for index in range(1, 31)
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
        current_market_state="HOT",
        min_sample=2,
        primary_horizon="return_5d",
    )

    body = envelope["result"]
    hybrid = next(row for row in body["current_market_state_rows"] if row["signal_kind"] == "hybrid_fusion")
    assert hybrid["strategy_label"] == "融合策略"
    assert hybrid["sample_status"] == "sufficient"
    assert hybrid["priority_label"] == "优先复核"


def test_strategy_score_service_accepts_return_10d_primary_horizon(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score-10d.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.executemany(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date,
              stock_code,
              stock_name,
              candidate_rank,
              selection_close,
              forward_trade_date_1d,
              forward_trade_date_5d,
              forward_trade_date_10d,
              forward_trade_date_20d,
              return_1d,
              return_5d,
              return_10d,
              return_20d,
              data_status,
              formula_version,
              source_version,
              vendor_version,
              rule_version,
              run_id,
              signal_kind,
              signal_evidence_json
            ) values (?, ?, ?, ?, 10.0, ?, ?, ?, ?, ?, ?, ?, ?, 'complete', 'fv1', 'sv_score', 'vv_score', 'rv_score', ?, 'stock_candidate', ?)
            """,
            [
                (
                    "2026-05-01" if index <= 15 else "2026-05-02",
                    f"{index:06d}.SZ",
                    f"Trend {index}",
                    index,
                    "2026-05-02",
                    "2026-05-08",
                    "2026-05-15",
                    "2026-05-29",
                    0.01,
                    0.02,
                    0.11 if index <= 15 else 0.03,
                    0.03,
                    f"r{index}",
                    '{"market_state":"HOT"}',
                )
                for index in range(1, 31)
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
        current_market_state="HOT",
        min_sample=2,
        primary_horizon="return_10d",
    )

    body = envelope["result"]
    assert isinstance(body, dict)
    assert body["primary_horizon"] == "return_10d"
    assert body["min_sample"] == 30
    row = body["current_market_state_rows"][0]
    assert row["signal_kind"] == "stock_candidate"
    assert row["stats"]["return_10d"] == {
        "available_count": 30,
        "missing_count": 0,
        "positive_count": 30,
        "non_positive_count": 0,
        "avg_return": 0.07,
        "median_return": 0.07,
        "win_rate": 1.0,
    }
    assert row["priority_score"] == 102.0
    assert "T+5" in row["reason"]


def test_strategy_score_splits_stock_candidate_entry_allowed_scope(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score-entry-scope.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Warm", "stock_candidate", 0.01, 0.03, 0.04, '{"market_state":"WARM"}'),
                ("2026-05-01", "000002.SZ", "Hot", "stock_candidate", 0.01, 0.05, 0.06, '{"market_state":"HOT"}'),
                (
                    "2026-05-01",
                    "000003.SZ",
                    "Overheat",
                    "stock_candidate",
                    -0.01,
                    -0.08,
                    -0.10,
                    '{"market_state":"OVERHEAT"}',
                ),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=1,
        primary_horizon="return_5d",
    )

    body = envelope["result"]
    assert isinstance(body, dict)
    scopes = body["stock_candidate_state_scopes"]
    assert scopes["stock_candidate_all_states"]["return_5d"]["available_count"] == 3
    assert scopes["stock_candidate_all_states"]["return_5d"]["avg_return"] == 0.0
    assert scopes["stock_candidate_entry_allowed_states_only"]["return_5d"]["available_count"] == 2
    assert scopes["stock_candidate_entry_allowed_states_only"]["return_5d"]["avg_return"] == 0.04
    assert scopes["overheat_ratio"] == 1 / 3


def test_strategy_score_service_reports_overheat_rank_scope_and_long_window_risk(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score-diagnostics.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        factor_rows = [
            (
                "2026-05-01",
                f"{index:06d}.SZ",
                f"Factor {index}",
                "factor_screen",
                0.01,
                -0.02 if index > 10 else 0.03,
                None,
                '{"market_state":"OVERHEAT"}',
            )
            for index in range(1, 26)
        ]
        trend_rows = [
            (
                "2026-05-01",
                f"30000{index}.SZ",
                f"Trend {index}",
                "stock_candidate",
                0.01,
                0.04,
                -0.03,
                '{"market_state":"OVERHEAT"}',
            )
            for index in range(1, 31)
        ]
        _insert_strategy_score_rows(conn, factor_rows + trend_rows)
        conn.executemany(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date,
              stock_code,
              stock_name,
              candidate_rank,
              selection_close,
              forward_trade_date_1d,
              forward_trade_date_5d,
              forward_trade_date_20d,
              return_1d,
              return_5d,
              return_20d,
              data_status,
              formula_version,
              source_version,
              vendor_version,
              rule_version,
              run_id,
              signal_kind,
              signal_evidence_json
            ) values (?, ?, ?, ?, 10.0, ?, null, null, ?, null, null, 'pending', 'fv1', 'sv_score', 'vv_score', 'rv_score', ?, 'factor_screen', '{"market_state":"OVERHEAT"}')
            """,
            [
                (
                    "2026-05-02",
                    f"10000{index}.SZ",
                    f"Pending Factor {index}",
                    index,
                    "2026-05-02",
                    0.01,
                    f"pending-run-{index}",
                )
                for index in range(1, 11)
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
        current_market_state="OVERHEAT",
        min_sample=2,
        primary_horizon="return_5d",
    )

    rows = envelope["result"]["current_market_state_rows"]
    factor = next(row for row in rows if row["signal_kind"] == "factor_screen")
    factor_diagnostics = factor["diagnostics"]
    assert factor_diagnostics["priority_scope"] == "rank<=10"
    assert factor_diagnostics["priority_scope_label"] == "前10名优先复核"
    assert factor_diagnostics["priority_scope_stats"]["return_5d"]["available_count"] == 10
    assert factor_diagnostics["priority_scope_stats"]["return_5d"]["avg_return"] == 0.03
    maturity = factor_diagnostics["maturity"]
    assert maturity["status"] == "narrow"
    assert maturity["label"] == "样本偏窄"
    assert maturity["mature_snapshot_count"] == 1
    assert maturity["min_mature_snapshot_count"] == 4
    assert maturity["snapshot_stats"][0]["snapshot_as_of_date"] == "2026-05-01"
    assert maturity["snapshot_stats"][0]["available_count"] == 10
    assert [row["snapshot_as_of_date"] for row in maturity["tracked_snapshots"]] == [
        "2026-05-01",
        "2026-05-02",
    ]
    assert maturity["tracked_snapshots"][0]["candidate_count"] == 10
    assert maturity["tracked_snapshots"][0]["horizons"]["return_1d"]["status"] == "complete"
    assert maturity["tracked_snapshots"][0]["horizons"]["return_5d"]["status"] == "complete"
    assert maturity["tracked_snapshots"][1]["candidate_count"] == 10
    assert maturity["tracked_snapshots"][1]["horizons"]["return_1d"]["status"] == "complete"
    assert maturity["tracked_snapshots"][1]["horizons"]["return_5d"]["status"] == "pending"
    assert maturity["tracked_snapshots"][1]["horizons"]["return_5d"]["available_count"] == 0
    assert maturity["worst_snapshot"]["win_rate"] == 1.0
    tail_bucket = next(bucket for bucket in factor_diagnostics["rank_buckets"] if bucket["label"] == "11-20")
    assert tail_bucket["included_in_priority"] is False
    assert tail_bucket["priority_label"] == "样本不足"
    assert tail_bucket["stats"]["return_5d"]["available_count"] == 10
    assert tail_bucket["stats"]["return_5d"]["avg_return"] == -0.02
    assert "样本不足" in tail_bucket["reason"]

    trend = next(row for row in rows if row["signal_kind"] == "stock_candidate")
    risk_flags = trend["diagnostics"]["risk_flags"]
    assert risk_flags[0]["kind"] == "long_window_median_worse"
    assert risk_flags[0]["horizon"] == "return_20d"
    assert "T+20" in risk_flags[0]["reason"]
    assert risk_flags[0]["stats"]["median_return"] == -0.03


def test_strategy_score_service_keeps_old_rows_as_unknown_and_reports_current_state_insufficient(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score-unknown.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Old A", "stock_candidate", 0.01, 0.03, None, "{}"),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="OVERHEAT",
        min_sample=2,
        primary_horizon="return_5d",
    )

    body = envelope["result"]
    assert isinstance(body, dict)
    assert [row["market_state"] for row in body["rows"]] == ["unknown"]
    assert body["rows"][0]["sample_status"] == "insufficient"
    current_rows = body["current_market_state_rows"]
    assert len(current_rows) == 5
    assert {row["signal_kind"] for row in current_rows} == {
        "hybrid_fusion",
        "stock_candidate",
        "factor_screen",
        "theme_breakout",
        "mean_reversion",
    }
    assert all(row["sample_status"] == "insufficient" for row in current_rows)
    assert all(row["priority_score"] is None for row in current_rows)
    assert all("当前状态样本不足" in row["reason"] for row in current_rows)


def test_strategy_score_family_metadata_keeps_non_priority_rows_null() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    payload = service._build_strategy_score_payload(
        items=[
            {
                "snapshot_as_of_date": "2026-05-01",
                "stock_code": "000001.SZ",
                "stock_name": "Fresh Trend",
                "candidate_rank": 1,
                "signal_kind": "fresh_trend_watchlist",
                "signal_evidence_json": '{"market_state":"HOT"}',
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.03,
            }
        ],
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=1,
        primary_horizon="return_5d",
        backtest_window_summary={},
    )

    row = next(row for row in payload["current_market_state_rows"] if row["signal_kind"] == "fresh_trend_watchlist")
    assert row["family_key"] is None
    assert row["family_label"] is None
    assert row["family_contract_version"] is None
    assert row["primary_sample_size"] is None
    assert row["family_readiness"] is None


def test_strategy_score_family_readiness_attaches_macro_context_without_changing_score_scope() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    payload = service._build_strategy_score_payload(
        items=[
            {
                "snapshot_as_of_date": "2026-05-01",
                "stock_code": "000001.SZ",
                "stock_name": "Trend",
                "candidate_rank": 1,
                "signal_kind": "stock_candidate",
                "signal_evidence_json": '{"market_state":"HOT"}',
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.03,
            },
            {
                "snapshot_as_of_date": "2026-05-01",
                "stock_code": "000002.SZ",
                "stock_name": "Fresh Trend",
                "candidate_rank": 2,
                "signal_kind": "fresh_trend_watchlist",
                "signal_evidence_json": '{"market_state":"HOT"}',
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.03,
            },
        ],
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=1,
        primary_horizon="return_5d",
        backtest_window_summary={},
        macro_context=_macro_context_v1_fixture(),
    )

    assert payload["macro_context"]["macro_context_id"] == "macroctx_unit"
    trend_row = next(row for row in payload["current_market_state_rows"] if row["signal_kind"] == "stock_candidate")
    readiness = trend_row["family_readiness"]
    assert readiness["readiness_contract_version"] == "rv_livermore_strategy_family_readiness_v1"
    assert readiness["macro_context_id"] == "macroctx_unit"
    assert readiness["readiness_state"] == "degraded_observation"
    assert readiness["macro_compatibility"] == "compatible"
    assert readiness["data_readiness"] == "ready"
    assert readiness["sample_maturity"] == "insufficient"
    assert readiness["observational_only"] is True
    assert readiness["formal_use_allowed"] is False
    assert "OBSERVATION_ONLY_BOUNDARY" in readiness["readiness_reasons"]
    assert "SAMPLE_MATURITY_INSUFFICIENT" in readiness["readiness_reasons"]

    fresh_row = next(row for row in payload["current_market_state_rows"] if row["signal_kind"] == "fresh_trend_watchlist")
    assert fresh_row["family_key"] is None
    assert fresh_row["family_readiness"] is None


def test_macro_context_v1_stabilizes_lineage_and_missing_state() -> None:
    from backend.app.services import macro_bond_linkage_service as svc

    macro_payload = {
        "report_date": "2026-05-01",
        "environment_score": {
            "report_date": "2026-05-01",
            "rate_direction_score": 0.1,
            "liquidity_score": 0.2,
            "growth_score": 0.3,
            "inflation_score": -0.1,
            "composite_score": 0.15,
        },
        "warnings": [],
        "computed_at": "2026-05-01T10:00:00+00:00",
    }
    macro_meta = {
        "source_version": "sv_macro",
        "vendor_version": "vv_macro",
        "rule_version": "rv_macro",
        "cache_version": "cv_macro",
        "quality_flag": "ok",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "evidence_rows": 30,
    }

    context = svc.build_macro_context_v1(
        as_of_date="2026-05-01",
        macro_payload=macro_payload,
        macro_meta=macro_meta,
    )
    same_context = svc.build_macro_context_v1(
        as_of_date="2026-05-01",
        macro_payload={**macro_payload, "computed_at": "2026-05-01T11:00:00+00:00"},
        macro_meta=macro_meta,
    )

    assert context["macro_contract_version"] == "rv_macro_context_v1"
    assert context["macro_context_id"] == same_context["macro_context_id"]
    assert context["data_state"] == "ready"
    assert context["coverage_ratio"] == 1.0
    assert context["confidence_score"] == 1.0
    assert context["dimension_scores"]["composite_score"] == 0.15
    assert context["score_polarity"]["liquidity_score"] == "positive=liquidity_easing"
    assert context["score_polarity"]["composite_score"] == "positive=bond_unfavorable_restrictive_macro_pressure"
    assert "- 0.3*liquidity_score" in context["composite_formula"]
    assert context["composite_formula_version"] == "macro_env_composite_v2_liquidity_inverted"
    assert context["readiness_reasons"] == []

    warned = svc.build_macro_context_v1(
        as_of_date="2026-05-01",
        macro_payload={**macro_payload, "warnings": ["macro warning"]},
        macro_meta=macro_meta,
    )

    assert warned["data_state"] == "degraded"
    assert warned["coverage_ratio"] == 1.0
    assert warned["confidence_score"] == 0.8667
    assert warned["readiness_reasons"] == ["MACRO_WARNINGS_PRESENT"]
    assert warned["warning_count"] == 1

    quality_warning = svc.build_macro_context_v1(
        as_of_date="2026-05-01",
        macro_payload=macro_payload,
        macro_meta={**macro_meta, "quality_flag": "warning"},
    )

    assert quality_warning["data_state"] == "degraded"
    assert quality_warning["coverage_ratio"] == 1.0
    assert quality_warning["confidence_score"] == 0.8667
    assert quality_warning["readiness_reasons"] == ["MACRO_QUALITY_WARNING"]
    assert quality_warning["warning_count"] == 0

    missing = svc.build_macro_context_v1(
        as_of_date="2026-05-01",
        macro_payload={"report_date": "2026-05-01", "environment_score": {}, "warnings": ["missing"]},
        macro_meta={**macro_meta, "quality_flag": "warning", "vendor_status": "vendor_unavailable", "evidence_rows": 0},
    )

    assert missing["data_state"] == "no_data"
    assert missing["coverage_ratio"] == 0.0
    assert "MACRO_SCORE_MISSING" in missing["readiness_reasons"]
    assert "MACRO_COVERAGE_INSUFFICIENT" in missing["readiness_reasons"]
    assert "MACRO_WARNINGS_PRESENT" in missing["readiness_reasons"]


def test_livermore_macro_context_wrapper_uses_service_normalizer(monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route

    captured_report_dates: list[date] = []

    def fake_macro_environment_context(report_date: date) -> dict[str, object]:
        captured_report_dates.append(report_date)
        return {
            "result": {
                "report_date": "2026-05-01",
                "environment_score": {
                    "report_date": "2026-05-01",
                    "rate_direction_score": 0.1,
                    "liquidity_score": 0.2,
                    "growth_score": 0.3,
                    "inflation_score": -0.1,
                    "composite_score": 0.15,
                },
                "warnings": [],
                "computed_at": "2026-05-01T10:00:00+00:00",
            },
            "result_meta": {
                "source_version": "sv_macro",
                "vendor_version": "vv_macro",
                "rule_version": "rv_macro",
                "cache_version": "cv_macro",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "evidence_rows": 30,
            },
        }

    # Patch the namespace the route-bound function actually dereferences:
    # tests.helpers.load_module can fork backend.app.services.macro_bond_linkage_service
    # in sys.modules, so patching a module handle resolved via import may miss the
    # instance whose get_macro_context_v1 the route bound at its own import time.
    monkeypatch.setitem(
        route.get_macro_context_v1.__globals__,
        "get_macro_environment_context",
        fake_macro_environment_context,
    )

    context = route._livermore_macro_context_v1_for_date("2026-05-01T15:30:00+08:00")

    assert captured_report_dates == [date(2026, 5, 1)]
    assert context is not None
    assert context["macro_contract_version"] == "rv_macro_context_v1"
    assert context["asof_date"] == "2026-05-01"
    assert context["data_state"] == "ready"
    assert context["dimension_scores"]["composite_score"] == 0.15


def test_strategy_optimization_service_reports_t5_recommendations_and_rank_slices(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_optimization_envelope,
    )

    db_path = tmp_path / "strategy-optimization.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        factor_rows = [
            (
                "2026-05-01",
                f"{index:06d}.SZ",
                f"Factor {index}",
                "factor_screen",
                0.01,
                0.04 if index <= 10 else 0.05 if index <= 20 else -0.02,
                0.045,
                '{"market_state":"HOT"}',
            )
            for index in range(1, 31)
        ]
        _insert_strategy_score_rows(conn, factor_rows)
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_optimization_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=10,
        primary_horizon="return_5d",
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.strategy_optimization"
    assert envelope["result_meta"]["rule_version"] == "rv_livermore_strategy_optimization_v1"
    body = envelope["result"]
    assert isinstance(body, dict)
    assert body["primary_horizon"] == "return_5d"
    assert body["min_sample"] == 30
    assert "family_summaries" not in body

    factor = next(row for row in body["strategy_summaries"] if row["signal_kind"] == "factor_screen")
    assert factor["family_key"] == "factor_screen"
    assert factor["family_contract_version"] == "rv_livermore_strategy_family_contract_v1"
    assert factor["primary_sample_size"] == 30
    assert factor["recommendation"]["action"] == "promote"
    assert factor["stats"]["return_5d"]["available_count"] == 30
    assert factor["date_weighted_stats"]["return_5d"]["available_day_count"] == 1
    assert factor["date_weighted_stats"]["return_5d"]["candidate_row_count"] == 30

    weak_slice = next(row for row in body["slices"] if row["slice_key"] == "factor_screen:rank:21-30")
    assert weak_slice["family_key"] == "factor_screen"
    assert weak_slice["primary_sample_size"] == 10
    assert weak_slice["label"] == "rank 21-30"
    assert weak_slice["recommendation"]["action"] == "pending_more_history"
    assert weak_slice["recommendation"]["priority_label"] == "样本不足"
    assert weak_slice["stats"]["return_5d"]["available_count"] == 10
    assert weak_slice["stats"]["return_5d"]["avg_return"] == -0.02
    factor_recommendation = next(row for row in body["recommendations"] if row["target_key"] == factor["summary_key"])
    assert factor_recommendation["target_type"] == "strategy"
    assert factor_recommendation["family_key"] == factor["family_key"]
    assert factor_recommendation["primary_sample_size"] == factor["primary_sample_size"]
    slice_recommendation = next(row for row in body["recommendations"] if row["target_key"] == weak_slice["slice_key"])
    assert slice_recommendation["target_type"] == "slice"
    assert slice_recommendation["family_key"] == weak_slice["family_key"]
    assert slice_recommendation["primary_sample_size"] == weak_slice["primary_sample_size"]


def test_strategy_optimization_family_metadata_covers_replay_signal_kinds() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    expected_family_keys = {
        "stock_candidate": "trend_core",
        "hybrid_fusion": "hybrid_fusion",
        "theme_breakout": "theme_breakout",
        "factor_screen": "factor_screen",
        "mean_reversion": "mean_reversion",
        "fresh_trend_watchlist": "fresh_trend_watchlist",
        "uptrend_momentum": "uptrend_momentum_observation",
    }
    items = [
        {
            "snapshot_as_of_date": "2026-05-01",
            "stock_code": f"{index:06d}.SZ",
            "stock_name": signal_kind,
            "candidate_rank": index,
            "signal_kind": signal_kind,
            "signal_evidence_json": '{"market_state":"HOT"}',
            "return_1d": 0.01,
            "return_5d": 0.02,
            "return_20d": 0.03,
        }
        for index, signal_kind in enumerate(expected_family_keys, start=1)
    ]

    payload = service._build_strategy_optimization_payload(
        items=items,
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=1,
        primary_horizon="return_5d",
        backtest_window_summary={},
        macro_context=_macro_context_v1_fixture(),
    )

    summaries = {row["signal_kind"]: row for row in payload["strategy_summaries"]}
    assert {signal_kind: row["family_key"] for signal_kind, row in summaries.items()} == expected_family_keys
    assert all(row["primary_sample_size"] == 1 for row in summaries.values())
    assert all(row["family_readiness"]["macro_context_id"] == "macroctx_unit" for row in summaries.values())
    assert all(row["family_readiness"]["formal_use_allowed"] is False for row in summaries.values())
    summary_recommendation = next(
        row for row in payload["recommendations"] if row["target_type"] == "strategy" and row["target_key"] == "strategy:stock_candidate"
    )
    assert summary_recommendation["family_readiness"]["macro_context_id"] == "macroctx_unit"
    assert (
        service._strategy_family_metadata_for_recommendation_target(
            target_type="strategy",
            target_key="missing",
            family_by_target={},
        )
        == {
            "family_key": None,
            "family_label": None,
            "family_contract_version": None,
            "primary_sample_size": None,
        }
    )


def test_strategy_family_metadata_contract_handles_alias_boundaries_and_sample_size_edges() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    expected_family_keys = {
        "stock_candidate": "trend_core",
        "hybrid_fusion": "hybrid_fusion",
        "theme_breakout": "theme_breakout",
        "factor_screen": "factor_screen",
        "mean_reversion": "mean_reversion",
        "fresh_trend_watchlist": "fresh_trend_watchlist",
        "uptrend_momentum": "uptrend_momentum_observation",
    }
    stats = {"return_5d": {"available_count": 17}}

    for signal_kind, family_key in expected_family_keys.items():
        metadata = service._strategy_family_metadata(
            signal_kind=signal_kind,
            stats=stats,
            primary_horizon="return_5d",
            score_priority_only=False,
        )
        assert metadata["family_key"] == family_key
        assert metadata["family_label"]
        assert metadata["family_contract_version"] == "rv_livermore_strategy_family_contract_v1"
        assert metadata["primary_sample_size"] == 17

    for output_key in (
        "stock_candidates",
        "hybrid_fusion_candidates",
        "factor_screen_candidates",
        "mean_reversion_candidates",
        "uptrend_momentum_candidates",
    ):
        metadata = service._strategy_family_metadata(
            signal_kind=output_key,
            stats=stats,
            primary_horizon="return_5d",
            score_priority_only=False,
        )
        assert metadata == {
            "family_key": None,
            "family_label": None,
            "family_contract_version": None,
            "primary_sample_size": None,
        }

    assert service._strategy_primary_sample_size(stats={}, primary_horizon="return_5d") is None
    assert service._strategy_primary_sample_size(stats={"return_1d": {"available_count": 5}}, primary_horizon="return_5d") is None
    assert service._strategy_primary_sample_size(stats={"return_5d": {}}, primary_horizon="return_5d") is None
    assert service._strategy_primary_sample_size(stats={"return_5d": {"available_count": None}}, primary_horizon="return_5d") is None
    assert service._strategy_primary_sample_size(stats={"return_5d": {"available_count": 0}}, primary_horizon="return_5d") == 0
    assert service._strategy_primary_sample_size(stats={"return_5d": {"available_count": "17"}}, primary_horizon="return_5d") == 17


def test_strategy_family_metadata_stays_consistent_between_score_and_optimization() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    for signal_kind in ("stock_candidate", "hybrid_fusion", "theme_breakout", "factor_screen", "mean_reversion"):
        items = [
            {
                "snapshot_as_of_date": "2026-05-01",
                "stock_code": "000001.SZ",
                "stock_name": signal_kind,
                "candidate_rank": 1,
                "signal_kind": signal_kind,
                "signal_evidence_json": '{"market_state":"HOT"}',
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.03,
            }
        ]
        score_row = service._strategy_score_row(
            market_state="HOT",
            signal_kind=signal_kind,
            items=items,
            min_sample=1,
            primary_horizon="return_5d",
        )
        optimization_summary = service._strategy_optimization_summary(
            signal_kind=signal_kind,
            items=items,
            min_sample=1,
            primary_horizon="return_5d",
        )
        for field in ("family_key", "family_label", "family_contract_version"):
            assert score_row[field] == optimization_summary[field]


def test_strategy_family_metadata_returns_fresh_dicts_without_sample_leakage() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    first = service._strategy_family_metadata(
        signal_kind="stock_candidate",
        stats={"return_5d": {"available_count": 3}},
        primary_horizon="return_5d",
        score_priority_only=False,
    )
    second = service._strategy_family_metadata(
        signal_kind="stock_candidate",
        stats={"return_5d": {"available_count": 19}},
        primary_horizon="return_5d",
        score_priority_only=False,
    )
    unknown = service._strategy_family_metadata(
        signal_kind="unknown_vendor_signal",
        stats={"return_5d": {"available_count": 99}},
        primary_horizon="return_5d",
        score_priority_only=False,
    )

    assert first["family_key"] == "trend_core"
    assert first["primary_sample_size"] == 3
    assert second["family_key"] == "trend_core"
    assert second["primary_sample_size"] == 19
    assert unknown == {
        "family_key": None,
        "family_label": None,
        "family_contract_version": None,
        "primary_sample_size": None,
    }


def test_strategy_optimization_recommendation_family_metadata_uses_target_namespace_and_unique_key() -> None:
    from backend.app.services import livermore_candidate_history_service as service

    recommendation = {
        "action": "observe",
        "priority_label": "observe",
        "reason": "review",
        "primary_horizon": "return_5d",
        "available_count": 1,
        "min_sample": 1,
        "avg_return": 0.01,
        "win_rate": 1.0,
        "score": 1,
    }
    shared_strategy = {
        "summary_key": "shared",
        "signal_kind": "stock_candidate",
        "strategy_label": "stock_candidate",
        "family_key": "trend_core",
        "family_label": "Trend core",
        "family_contract_version": "rv_livermore_strategy_family_contract_v1",
        "primary_sample_size": 10,
        "family_readiness": {
            "readiness_contract_version": "rv_livermore_strategy_family_readiness_v1",
            "macro_context_id": "macroctx_strategy",
            "formal_use_allowed": False,
        },
        "recommendation": recommendation,
    }
    shared_slice = {
        "slice_key": "shared",
        "signal_kind": "factor_screen",
        "label": "factor shared",
        "family_key": "factor_screen",
        "family_label": "Factor screen",
        "family_contract_version": "rv_livermore_strategy_family_contract_v1",
        "primary_sample_size": 20,
        "family_readiness": {
            "readiness_contract_version": "rv_livermore_strategy_family_readiness_v1",
            "macro_context_id": "macroctx_slice",
            "formal_use_allowed": False,
        },
        "recommendation": recommendation,
    }
    shared_recommendations = service._strategy_optimization_recommendations(
        strategy_summaries=[shared_strategy],
        slices=[shared_slice],
    )
    strategy_recommendation = next(row for row in shared_recommendations if row["target_type"] == "strategy")
    slice_recommendation = next(row for row in shared_recommendations if row["target_type"] == "slice")
    assert strategy_recommendation["target_key"] == "shared"
    assert strategy_recommendation["family_key"] == "trend_core"
    assert strategy_recommendation["primary_sample_size"] == 10
    assert strategy_recommendation["family_readiness"]["macro_context_id"] == "macroctx_strategy"
    assert slice_recommendation["target_key"] == "shared"
    assert slice_recommendation["family_key"] == "factor_screen"
    assert slice_recommendation["primary_sample_size"] == 20
    assert slice_recommendation["family_readiness"]["macro_context_id"] == "macroctx_slice"

    duplicate_summaries = [
        {
            "summary_key": "strategy:duplicate",
            "signal_kind": "stock_candidate",
            "strategy_label": "stock_candidate",
            "family_key": "trend_core",
            "family_label": "Trend core",
            "family_contract_version": "rv_livermore_strategy_family_contract_v1",
            "primary_sample_size": 10,
            "recommendation": recommendation,
        },
        {
            "summary_key": "strategy:duplicate",
            "signal_kind": "factor_screen",
            "strategy_label": "factor_screen",
            "family_key": "factor_screen",
            "family_label": "Factor screen",
            "family_contract_version": "rv_livermore_strategy_family_contract_v1",
            "primary_sample_size": 20,
            "recommendation": recommendation,
        },
    ]

    recommendations = service._strategy_optimization_recommendations(
        strategy_summaries=duplicate_summaries,
        slices=[],
    )

    assert len(recommendations) == 2
    assert all(row["target_key"] == "strategy:duplicate" for row in recommendations)
    assert all(row["family_key"] is None for row in recommendations)
    assert all(row["primary_sample_size"] is None for row in recommendations)
    assert all(row["family_readiness"] is None for row in recommendations)

    duplicate_slices = [
        {
            **shared_slice,
            "slice_key": "slice:duplicate",
            "family_key": "factor_screen",
            "primary_sample_size": 30,
        },
        {
            **shared_slice,
            "slice_key": "slice:duplicate",
            "family_key": "theme_breakout",
            "primary_sample_size": 40,
        },
    ]
    recommendations = service._strategy_optimization_recommendations(
        strategy_summaries=[],
        slices=duplicate_slices,
    )

    assert len(recommendations) == 2
    assert all(row["target_type"] == "slice" for row in recommendations)
    assert all(row["target_key"] == "slice:duplicate" for row in recommendations)
    assert all(row["family_key"] is None for row in recommendations)
    assert all(row["primary_sample_size"] is None for row in recommendations)
    assert all(row["family_readiness"] is None for row in recommendations)


def test_strategy_optimization_downgrades_when_t20_median_worsens(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_optimization_envelope,
    )

    db_path = tmp_path / "strategy-optimization-t20-worse.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2026-05-01",
                    f"{index:06d}.SZ",
                    f"Factor {index}",
                    "factor_screen",
                    0.01,
                    0.03,
                    0.01,
                    '{"market_state":"HOT"}',
                )
                for index in range(1, 31)
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_optimization_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=30,
        primary_horizon="return_5d",
    )

    body = envelope["result"]
    factor = next(row for row in body["strategy_summaries"] if row["signal_kind"] == "factor_screen")
    assert factor["recommendation"]["action"] == "downgrade"
    assert factor["recommendation"]["priority_label"] == "降权观察"
    assert factor["recommendation"]["available_count"] == 30
    assert factor["recommendation"]["median_return"] == 0.03
    assert factor["recommendation"]["t20_median_return"] == 0.01
    assert "T+20" in factor["recommendation"]["reason"]

def test_strategy_optimization_marks_sample_insufficient_without_false_promote(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_optimization_envelope,
    )

    db_path = tmp_path / "strategy-optimization-pending.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2026-05-01",
                    "000001.SZ",
                    "Theme A",
                    "theme_breakout",
                    0.01,
                    0.08,
                    None,
                    '{"market_state":"HOT","theme_rank":1,"stock_rank_in_theme":1,"movement_event_count":3}',
                ),
                (
                    "2026-05-01",
                    "000002.SZ",
                    "Theme B",
                    "theme_breakout",
                    0.01,
                    0.05,
                    None,
                    '{"market_state":"HOT","theme_rank":2,"stock_rank_in_theme":2,"movement_event_count":4}',
                ),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_optimization_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=5,
        primary_horizon="return_5d",
    )

    body = envelope["result"]
    assert isinstance(body, dict)
    theme = next(row for row in body["strategy_summaries"] if row["signal_kind"] == "theme_breakout")
    assert theme["stats"]["return_5d"]["available_count"] == 2
    assert theme["recommendation"]["action"] == "pending_more_history"
    assert theme["recommendation"]["priority_label"] == "样本不足"
    assert "优先复核" not in theme["recommendation"]["reason"]


def test_strategy_optimization_api_happy_path_and_query_validation(monkeypatch, tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_optimization_envelope,
    )

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Factor A", "factor_screen", 0.01, 0.02, 0.03, '{"market_state":"HOT"}'),
                ("2026-05-01", "000002.SZ", "Factor B", "factor_screen", 0.01, 0.03, 0.03, '{"market_state":"HOT"}'),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_strategy_optimization_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
        current_market_state="HOT",
        min_sample=2,
        primary_horizon="return_5d",
    )
    assert envelope["result_meta"]["rule_version"] == "rv_livermore_strategy_optimization_v1"
    assert "livermore_candidate_history" in envelope["result_meta"]["tables_used"]
    assert envelope["result"]["strategy_summaries"][0]["signal_kind"] == "factor_screen"

    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route

    monkeypatch.setattr(
        route,
        "_livermore_macro_context_v1_for_date",
        lambda as_of_date: _macro_context_v1_fixture(),
    )
    response = client.get(
        "/ui/market-data/livermore/strategy-optimization",
        params={
            "snapshot_from": "2026-05-01",
            "snapshot_to": "2026-05-01",
            "current_market_state": "HOT",
            "min_sample": 2,
            "primary_horizon": "return_5d",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["rule_version"] == "rv_livermore_strategy_optimization_v1"
    assert "livermore_candidate_history" in body["result_meta"]["tables_used"]
    assert body["result"]["strategy_summaries"][0]["signal_kind"] == "factor_screen"
    assert body["result"]["macro_context"]["macro_context_id"] == "macroctx_unit"
    assert body["result"]["macro_context"]["macro_contract_version"] == "rv_macro_context_v1"
    readiness = body["result"]["strategy_summaries"][0]["family_readiness"]
    assert readiness["readiness_contract_version"] == "rv_livermore_strategy_family_readiness_v1"
    assert readiness["macro_context_id"] == "macroctx_unit"
    assert readiness["data_readiness"] == "ready"
    assert readiness["macro_compatibility"] == "compatible"
    assert "OBSERVATION_ONLY_BOUNDARY" in readiness["readiness_reasons"]

    response_10d = client.get(
        "/ui/market-data/livermore/strategy-optimization",
        params={
            "snapshot_from": "2026-05-01",
            "snapshot_to": "2026-05-01",
            "current_market_state": "HOT",
            "min_sample": 2,
            "primary_horizon": "return_10d",
        },
    )
    assert response_10d.status_code == 422
    assert response_10d.json()["detail"] == "Invalid primary_horizon. Expected return_1d, return_5d, or return_20d."

    assert (
        client.get(
            "/ui/market-data/livermore/strategy-optimization",
            params={"snapshot_from": "not-a-date"},
        ).status_code
        == 422
    )
    assert client.get("/ui/market-data/livermore/strategy-optimization", params={"min_sample": 0}).status_code == 422
    get_settings.cache_clear()


def test_strategy_score_api_happy_path_and_query_validation(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Factor A", "factor_screen", 0.01, 0.02, 0.03, '{"market_state":"HOT"}'),
                ("2026-05-02", "000002.SZ", "Factor B", "factor_screen", 0.00, 0.01, 0.02, '{"market_state":"HOT"}'),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route

    monkeypatch.setattr(
        route,
        "_livermore_macro_context_v1_for_date",
        lambda as_of_date: _macro_context_v1_fixture(),
    )
    response = client.get(
        "/ui/market-data/livermore/strategy-score",
        params={
            "snapshot_from": "2026-05-01",
            "snapshot_to": "2026-05-02",
            "current_market_state": "HOT",
            "min_sample": 2,
            "primary_horizon": "return_5d",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["rule_version"] == "rv_livermore_strategy_score_v1"
    assert "livermore_candidate_history" in body["result_meta"]["tables_used"]
    assert body["result"]["current_market_state_rows"][0]["signal_kind"] == "factor_screen"
    assert body["result"]["macro_context"]["macro_context_id"] == "macroctx_unit"
    assert body["result"]["macro_context"]["macro_contract_version"] == "rv_macro_context_v1"
    readiness = body["result"]["current_market_state_rows"][0]["family_readiness"]
    assert readiness["readiness_contract_version"] == "rv_livermore_strategy_family_readiness_v1"
    assert readiness["macro_context_id"] == "macroctx_unit"
    assert readiness["data_readiness"] == "ready"
    assert readiness["macro_compatibility"] == "compatible"
    assert "OBSERVATION_ONLY_BOUNDARY" in readiness["readiness_reasons"]

    response_10d = client.get(
        "/ui/market-data/livermore/strategy-score",
        params={
            "snapshot_from": "2026-05-01",
            "snapshot_to": "2026-05-02",
            "current_market_state": "HOT",
            "min_sample": 2,
            "primary_horizon": "return_10d",
        },
    )
    assert response_10d.status_code == 422
    assert response_10d.json()["detail"] == "Invalid primary_horizon. Expected return_1d, return_5d, or return_20d."

    assert (
        client.get("/ui/market-data/livermore/strategy-score", params={"snapshot_from": "not-a-date"}).status_code
        == 422
    )
    assert client.get("/ui/market-data/livermore/strategy-score", params={"min_sample": 0}).status_code == 422
    assert (
        client.get(
            "/ui/market-data/livermore/strategy-score",
            params={"primary_horizon": "return_30d"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()


def test_cycle_proxy_backtest_reports_nav_gain_and_drawdown_intervals(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Proxy A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
                ("2026-05-02", "000002.SZ", "Proxy B", "stock_candidate", 0.20, 0.18, 0.10, '{"market_state":"HOT"}'),
                ("2026-05-03", "000003.SZ", "Proxy C", "stock_candidate", -0.25, -0.20, -0.10, '{"market_state":"HOT"}'),
                ("2026-05-04", "000004.SZ", "Proxy D", "stock_candidate", 0.125, 0.08, 0.05, '{"market_state":"HOT"}'),
            ],
        )
        conn.executemany(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = ?
            where snapshot_as_of_date = ?
            """,
            [
                ("2026-05-08", "2026-05-01"),
                ("2026-05-09", "2026-05-02"),
                ("2026-05-10", "2026-05-03"),
                ("2026-05-11", "2026-05-04"),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-03")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-04")
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-04",
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.cycle_proxy_backtest"
    body = envelope["result"]
    assert body["status"] == "proxy"
    assert body["full_strategy_status"] == "blocked_missing_inputs"
    assert body["proxy_signal_kind"] == "stock_candidate"
    assert body["summary"]["sample_days"] == 1
    # net of formal round-trip cost (multiplicative): (1 + 0.12) * (1 - 0.0041) - 1 = 0.115408
    assert body["summary"]["cumulative_return"] == 0.115408
    # v4 prefers executable next-open net returns; these fixtures exercise the
    # second fallback because neither execution nor adjusted returns are landed.
    assert body["summary"]["return_field_used"] == "return_5d_net_adj"
    assert body["summary"]["return_field_fallback"] == "return_5d_adj"
    assert body["summary"]["return_field_second_fallback"] == "return_5d"
    assert body["summary"]["return_rows_execution_net_adjusted"] == 0
    assert body["summary"]["return_rows_adjusted"] == 0
    assert body["summary"]["return_rows_adjusted_fallback"] == 0
    assert body["summary"]["return_rows_gross_fallback"] == 4
    assert body["summary"]["cost_basis"]["round_trip_cost_rate"] == 0.0041
    # single basket: annualization would explode, must be suppressed
    assert body["summary"]["annualized_return"] is None
    assert body["summary"]["annualization_status"] == "insufficient_sample"
    assert body["summary"]["max_gain"]["return"] == 0.115408
    assert body["summary"]["max_gain"]["start_date"] == "2026-05-01"
    assert body["summary"]["max_gain"]["end_date"] == "2026-05-08"
    assert body["summary"]["max_drawdown"]["return"] == 0.0
    assert body["summary"]["max_drawdown"]["peak_date"] == "2026-05-01"
    assert body["summary"]["max_drawdown"]["trough_date"] == "2026-05-01"
    assert [row["date"] for row in body["nav_series"]] == [
        "2026-05-01",
    ]
    assert body["nav_series"][-1]["nav"] == 1.115408
    assert "PMI" in body["missing_full_strategy_inputs"]


def test_cycle_proxy_backtest_nets_formal_costs_and_annualizes_with_actual_span(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy-annualization.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-01-05", "000001.SZ", "Proxy A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
                ("2026-12-21", "000002.SZ", "Proxy B", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"HOT"}'),
            ],
        )
        conn.executemany(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = ?
            where snapshot_as_of_date = ?
            """,
            [
                ("2026-01-12", "2026-01-05"),
                ("2026-12-28", "2026-12-21"),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-01-05")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-12-21")
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-01-05",
        snapshot_to="2026-12-21",
    )

    body = envelope["result"]
    # net basket return (multiplicative): (1 + 0.12) * (1 - 0.0041) - 1 = 0.115408 per basket
    assert body["nav_series"][0]["period_return"] == 0.115408
    assert body["nav_series"][0]["period_return_gross"] == 0.12
    # terminal nav 1.115408 ** 2 = 1.244135 (rounded)
    assert body["nav_series"][-1]["nav"] == 1.244135
    summary = body["summary"]
    assert summary["return_field_used"] == "return_5d_net_adj"
    assert summary["return_field_fallback"] == "return_5d_adj"
    assert summary["return_field_second_fallback"] == "return_5d"
    assert summary["cost_basis"] == {
        "source": "core_finance.strategy_policy.POLICY",
        "buy_cost_rate": 0.0008,
        "sell_cost_rate": 0.0013,
        "slippage_rate": 0.001,
        "round_trip_cost_rate": 0.0041,
    }
    assert summary["cumulative_return"] == 0.244135
    # actual span 2026-01-05 -> 2026-12-28 = 357 calendar days,
    # annualized = 1.244135 ** (365 / 357) - 1 = 0.25024
    assert summary["annualization_span_calendar_days"] == 357
    assert summary["annualization_status"] == "ok"
    assert summary["annualized_return"] == 0.25024
    assert any("already includes formal transaction costs" in warning for warning in body["warnings"])
    assert any("not produced by the formal path backtest engine" in warning for warning in body["warnings"])
    # MEDIUM-1: same-day close entry assumption must be disclosed
    assert any(
        "signal-day close" in warning
        and "fallback" in warning
        and "same-day execution" in warning
        and "livermore_candidate_execution_history" in warning
        for warning in body["warnings"]
    )


def test_cycle_proxy_backtest_prefers_adjusted_returns_and_reports_formula_version(tmp_path) -> None:
    """v2 口径：篮子收益优先 return_5d_adj（复权口径，与正式引擎一致），缺失时回退 gross return_5d。"""
    db_path = tmp_path / "cycle-proxy-adjusted.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Adj A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
            ],
        )
        # gross return_5d is inflated by an ex-dividend gap; the adjusted return is 0.10
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08',
                return_5d_adj = 0.10
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    body = envelope["result"]
    assert body["formula_version"] == "fv_livermore_cycle_proxy_backtest_execution_first_v4"
    # v2 (return_5d_adj first) 口径: 0.10 - 0.0041 = 0.0959
    # v3 (multiplicative cost netting) 口径: (1 + 0.10) * (1 - 0.0041) - 1 = 0.09549
    assert body["nav_series"][0]["period_return"] == 0.09549
    assert body["nav_series"][0]["period_return_gross"] == 0.1
    assert body["summary"]["cumulative_return"] == 0.09549
    assert body["summary"]["return_rows_execution_net_adjusted"] == 0
    assert body["summary"]["return_rows_adjusted"] == 1
    assert body["summary"]["return_rows_adjusted_fallback"] == 1
    assert body["summary"]["return_rows_gross_fallback"] == 0


def test_cycle_proxy_backtest_prefers_next_open_execution_net_return(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy-execution-first.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2026-05-01",
                    "000001.SZ",
                    "Execution A",
                    "stock_candidate",
                    0.10,
                    0.12,
                    0.20,
                    '{"market_state":"WARM"}',
                ),
            ],
        )
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08',
                return_5d_adj = 0.10
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history (
              signal_date,
              stock_code,
              signal_kind,
              market_state,
              entry_executable,
              entry_block_reason,
              entry_date,
              exit_date_5d,
              return_5d_gross_adj,
              return_5d_net_adj
            ) values (
              '2026-05-01',
              '000001.SZ',
              'stock_candidate',
              'WARM',
              true,
              '',
              '2026-05-04',
              '2026-05-11',
              0.085,
              0.08
            )
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    body = envelope["result"]
    assert body["formula_version"] == "fv_livermore_cycle_proxy_backtest_execution_first_v4"
    assert body["nav_series"][0]["period_return"] == 0.08
    assert body["nav_series"][0]["period_return_gross"] == 0.085
    assert body["nav_series"][0]["date"] == "2026-05-04"
    assert body["nav_series"][0]["exit_date"] == "2026-05-11"
    assert body["summary"]["return_field_used"] == "return_5d_net_adj"
    assert body["summary"]["return_rows_execution_net_adjusted"] == 1
    assert body["summary"]["return_rows_adjusted_fallback"] == 0
    assert body["summary"]["return_rows_gross_fallback"] == 0
    assert body["execution_blocked_rows_in_window"] == 0
    assert envelope["result_meta"]["tables_used"] == [
        "livermore_candidate_history",
        "livermore_candidate_execution_history",
    ]
    assert any("next-open" in warning and "preferred" in warning for warning in body["warnings"])


def test_cycle_proxy_backtest_excludes_execution_blocked_entries(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy-execution-blocked.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2026-05-01",
                    "000001.SZ",
                    "Blocked A",
                    "stock_candidate",
                    0.10,
                    0.12,
                    0.20,
                    '{"market_state":"WARM"}',
                ),
            ],
        )
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08',
                return_5d_adj = 0.10
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history (
              signal_date,
              stock_code,
              signal_kind,
              market_state,
              entry_executable,
              entry_block_reason
            ) values (
              '2026-05-01',
              '000001.SZ',
              'stock_candidate',
              'WARM',
              false,
              'limit_up_open'
            )
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    body = envelope["result"]
    assert body["status"] == "unsupported"
    assert body["summary"] is None
    assert body["nav_series"] == []
    assert body["execution_blocked_rows_in_window"] == 1
    assert envelope["result_meta"]["tables_used"] == [
        "livermore_candidate_history",
        "livermore_candidate_execution_history",
    ]


def test_candidate_history_portfolio_backtest_reports_formula_version(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio-formula.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-02", "000001.SZ", 110.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
    )

    body = envelope["result"]
    assert body["formula_version"] == "fv_livermore_candidate_history_portfolio_adj_mtm_v2"


def test_candidate_history_portfolio_backtest_uses_adjusted_mtm_and_reports_fallback_rows(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio-adjusted-mtm.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-01", "000002.SZ", 100.0),
                # 000001.SZ has an ex-dividend raw close gap; adjusted close stays flat at 100.
                ("2026-05-02", "000001.SZ", 50.0),
                ("2026-05-02", "000002.SZ", 110.0),
            ],
        )
        _seed_stock_adjustment_factors(
            conn,
            [
                ("2026-05-01", "000001.SZ", 1.0),
                ("2026-05-02", "000001.SZ", 2.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "ExDiv", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
                ("2026-05-01", "000002.SZ", "RawFallback", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
    )

    body = envelope["result"]
    assert envelope["result_meta"]["tables_used"] == [
        "livermore_candidate_history",
        "choice_stock_daily_observation",
        "stock_adjustment_factor",
    ]
    assert body["formula_version"] == "fv_livermore_candidate_history_portfolio_adj_mtm_v2"
    assert [row["nav"] for row in body["nav_series"]] == [0.9982, 1.04811]
    summary = body["summary"]
    assert summary["price_field_used"] == "adj_close_value"
    assert summary["price_field_fallback"] == "close_value"
    assert summary["price_rows_adjusted"] == 2
    assert summary["price_rows_raw_fallback"] == 2
    assert any("daily adjusted-close mark-to-market" in warning for warning in body["warnings"])


def test_cycle_proxy_backtest_compares_proxy_nav_to_csi300_benchmark(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy-benchmark.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Proxy A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08'
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_csi300_benchmark(conn, [("2026-05-01", 100.0), ("2026-05-08", 105.0)])
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    summary = envelope["result"]["summary"]
    assert envelope["result_meta"]["tables_used"] == ["livermore_candidate_history", "fact_choice_macro_daily"]
    assert summary["benchmark"]["series_id"] == "CA.CSI300"
    assert summary["benchmark"]["coverage_status"] == "complete"
    assert summary["benchmark"]["requested_start_date"] == "2026-05-01"
    assert summary["benchmark"]["requested_end_date"] == "2026-05-08"
    assert summary["benchmark"]["start_date"] == "2026-05-01"
    assert summary["benchmark"]["end_date"] == "2026-05-08"
    assert summary["benchmark"]["cumulative_return"] == 0.05
    # strategy net return 0.115408 minus benchmark 0.05
    assert summary["benchmark"]["relative_cumulative_return"] == 0.065408


def test_cycle_proxy_backtest_unions_csi300_benchmark_sources_for_coverage(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy-benchmark-union.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Proxy A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08'
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_csi300_snapshot_benchmark(conn, [("2026-05-01", 100.0)])
        _seed_csi300_benchmark(conn, [("2026-05-08", 105.0)])
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    summary = envelope["result"]["summary"]
    assert envelope["result_meta"]["tables_used"] == [
        "livermore_candidate_history",
        "fact_choice_macro_daily",
        "choice_market_snapshot",
    ]
    assert summary["benchmark"]["coverage_status"] == "complete"
    assert summary["benchmark"]["start_date"] == "2026-05-01"
    assert summary["benchmark"]["end_date"] == "2026-05-08"
    assert summary["benchmark"]["cumulative_return"] == 0.05


def test_cycle_proxy_backtest_marks_unsupported_when_no_completed_proxy_rows(tmp_path) -> None:
    db_path = tmp_path / "cycle-proxy-empty.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Pending A", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    body = envelope["result"]
    assert body["status"] == "unsupported"
    assert body["summary"] is None
    assert body["nav_series"] == []
    assert body["caliber_disclosure"] is None


def test_cycle_proxy_backtest_api_happy_path_and_query_validation(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Proxy A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08'
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/market-data/livermore/cycle-proxy-backtest",
        params={"snapshot_from": "2026-05-01", "snapshot_to": "2026-05-01"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["rule_version"] == "rv_livermore_cycle_proxy_backtest_v1"
    assert body["result"]["status"] == "proxy"
    assert body["result"]["summary"]["cumulative_return"] == 0.115408
    assert (
        client.get(
            "/ui/market-data/livermore/cycle-proxy-backtest",
            params={"snapshot_from": "not-a-date"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()


def test_cycle_proxy_backtest_api_exposes_caliber_disclosure(monkeypatch, tmp_path) -> None:
    """Endpoint chain: caliber_disclosure presence, semantics, and null when the backtest is unavailable."""
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2025-12-01",
                    "000001.SZ",
                    "Tushare Era",
                    "stock_candidate",
                    0.10,
                    0.12,
                    0.20,
                    '{"market_state":"WARM"}',
                ),
                (
                    "2026-05-01",
                    "000002.SZ",
                    "Native Era",
                    "stock_candidate",
                    0.05,
                    0.06,
                    0.10,
                    '{"market_state":"WARM"}',
                ),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/market-data/livermore/cycle-proxy-backtest",
        params={"snapshot_from": "2025-12-01", "snapshot_to": "2026-05-01"},
    )

    assert response.status_code == 200
    body = response.json()["result"]
    assert body["status"] == "proxy"
    disclosure = body["caliber_disclosure"]
    assert disclosure["entry_price_warning"] == CYCLE_PROXY_ENTRY_PRICE_WARNING
    assert disclosure["return_field_stats"] == {
        "return_rows_execution_net_adjusted": 0,
        "return_rows_adjusted": 0,
        "return_rows_adjusted_fallback": 0,
        "return_rows_gross_fallback": 2,
    }
    # signal_date < 2026-01-05 counts as tushare era, >= counts as Choice native era.
    assert disclosure["sample_generation"] == {"tushare_era_rows": 1, "native_era_rows": 1}
    assert CYCLE_PROXY_ENTRY_PRICE_WARNING in disclosure["basis_notes"]
    assert any("2026-01-05" in note for note in disclosure["basis_notes"])

    unavailable = client.get(
        "/ui/market-data/livermore/cycle-proxy-backtest",
        params={"snapshot_from": "2024-01-01", "snapshot_to": "2024-01-31"},
    )
    assert unavailable.status_code == 200
    unavailable_body = unavailable.json()["result"]
    assert unavailable_body["status"] == "unsupported"
    assert "caliber_disclosure" in unavailable_body
    assert unavailable_body["caliber_disclosure"] is None
    get_settings.cache_clear()


def test_candidate_history_portfolio_backtest_api_exposes_caliber_disclosure(monkeypatch, tmp_path) -> None:
    """Endpoint chain: portfolio-proxy caliber_disclosure semantics and null when unavailable."""
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2025-12-01", "000001.SZ", 100.0),
                ("2025-12-02", "000001.SZ", 105.0),
                ("2026-05-04", "000001.SZ", 110.0),
                ("2026-05-05", "000001.SZ", 112.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                (
                    "2025-12-01",
                    "000001.SZ",
                    "Tushare Era",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    '{"market_state":"WARM"}',
                ),
                (
                    "2026-05-04",
                    "000001.SZ",
                    "Native Era",
                    "stock_candidate",
                    None,
                    None,
                    None,
                    '{"market_state":"WARM"}',
                ),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/market-data/livermore/candidate-history-portfolio-backtest",
        params={"snapshot_from": "2025-12-01", "snapshot_to": "2026-05-05"},
    )

    assert response.status_code == 200
    body = response.json()["result"]
    assert body["status"] == "portfolio_proxy"
    disclosure = body["caliber_disclosure"]
    assert disclosure["entry_price_warning"] == PORTFOLIO_PROXY_ENTRY_PRICE_WARNING
    # The monthly proxy has no per-row return-field selection; its return
    # caliber is the mark-to-market price-source split (no adj factors seeded).
    assert disclosure["return_field_stats"] == {
        "price_rows_adjusted": 0,
        "price_rows_raw_fallback": 4,
    }
    assert disclosure["sample_generation"] == {"tushare_era_rows": 1, "native_era_rows": 1}
    assert PORTFOLIO_PROXY_ENTRY_PRICE_WARNING in disclosure["basis_notes"]
    assert any("2026-01-05" in note for note in disclosure["basis_notes"])

    unavailable = client.get(
        "/ui/market-data/livermore/candidate-history-portfolio-backtest",
        params={"snapshot_from": "2024-01-01", "snapshot_to": "2024-01-31"},
    )
    assert unavailable.status_code == 200
    unavailable_body = unavailable.json()["result"]
    assert unavailable_body["status"] == "unsupported"
    assert "caliber_disclosure" in unavailable_body
    assert unavailable_body["caliber_disclosure"] is None
    get_settings.cache_clear()


def test_candidate_history_portfolio_backtest_marks_to_market_with_monthly_cash_gate_and_costs(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-01", "000002.SZ", 100.0),
                ("2026-05-02", "000001.SZ", 110.0),
                ("2026-05-02", "000002.SZ", 100.0),
                ("2026-06-01", "000001.SZ", 90.0),
                ("2026-06-01", "000002.SZ", 80.0),
                ("2026-07-01", "000003.SZ", 100.0),
                ("2026-07-02", "000003.SZ", 110.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
                ("2026-05-01", "000002.SZ", "Beta", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
                ("2026-06-01", "000099.SZ", "Gate Off", "stock_candidate", None, None, None, '{"market_state":"OVERHEAT"}'),
                ("2026-07-01", "000003.SZ", "Gamma", "stock_candidate", None, None, None, '{"market_state":"HOT"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-07-02",
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.candidate_history_portfolio_backtest"
    body = envelope["result"]
    assert body["status"] == "portfolio_proxy"
    assert body["full_strategy_status"] == "blocked_missing_inputs"
    assert body["rebalance_rule"] == "first_available_monthly_snapshot"
    assert body["summary"]["rebalance_count"] == 3
    assert body["summary"]["invested_rebalance_count"] == 2
    assert body["summary"]["cash_rebalance_count"] == 1
    assert body["summary"]["candidate_rows"] == 3
    assert body["summary"]["gross_turnover"] == 3.0
    # per-side cost now includes slippage: buy 0.0008+0.0010, sell 0.0013+0.0010
    assert body["summary"]["cost_drag"] == 0.005275
    assert body["summary"]["cost_basis"]["slippage_rate"] == 0.001
    assert body["summary"]["sample_days"] == 4
    assert body["summary"]["cumulative_return"] == -0.070506
    assert body["summary"]["max_gain"]["return"] == 0.099999
    assert body["summary"]["max_gain"]["start_date"] == "2026-07-01"
    assert body["summary"]["max_gain"]["end_date"] == "2026-07-02"
    assert body["summary"]["max_drawdown"]["peak_date"] == "2026-05-02"
    assert body["summary"]["max_drawdown"]["trough_date"] == "2026-07-01"
    assert [row["date"] for row in body["nav_series"]] == [
        "2026-05-01",
        "2026-05-02",
        "2026-06-01",
        "2026-07-01",
        "2026-07-02",
    ]
    assert body["rebalance_log"][1]["market_state"] == "OVERHEAT"
    assert body["rebalance_log"][1]["target_count"] == 0
    assert body["rebalance_log"][1]["sell_turnover"] == 1.0
    assert "equal-weight top-6 replay rows" in body["warnings"][1]
    # MEDIUM-1: same-day close entry assumption must be disclosed
    assert any(
        "snapshot-day close" in warning
        and "same-day execution" in warning
        and "livermore_candidate_execution_history" in warning
        for warning in body["warnings"]
    )


def test_candidate_history_portfolio_backtest_forward_fills_missing_closes(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio-forward-fill.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-01", "000002.SZ", 100.0),
                # 000001.SZ has no close on 2026-05-02 (e.g. halted) and reprices on 2026-05-03
                ("2026-05-02", "000002.SZ", 110.0),
                ("2026-05-03", "000001.SZ", 104.0),
                ("2026-05-03", "000002.SZ", 110.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
                ("2026-05-01", "000002.SZ", "Beta", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-03",
    )

    body = envelope["result"]
    # 2026-05-02: 000001.SZ marked at its last known close 100.0 (forward-fill),
    # not zero: nav = 0.4991 + 0.4991 * 1.1 = 1.04811 (entry cost 0.0018 on day 1)
    assert [row["nav"] for row in body["nav_series"]] == [0.9982, 1.04811, 1.068074]
    assert body["nav_series"][1]["holding_count"] == 2
    # the stock repriced within the period, so no stale-price warning is emitted
    assert not any("forward-fill" in warning for warning in body["warnings"])


def test_candidate_history_portfolio_backtest_flags_stocks_without_fresh_prices(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio-stale.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-01", "000002.SZ", 100.0),
                # 000001.SZ never reprices again after the rebalance date
                ("2026-05-02", "000002.SZ", 110.0),
                ("2026-05-03", "000002.SZ", 112.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
                ("2026-05-01", "000002.SZ", "Beta", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-03",
    )

    body = envelope["result"]
    # 000001.SZ stays valued at 100.0: nav = 0.4991 + 0.4991 * 1.12 = 1.058092
    assert body["nav_series"][-1]["nav"] == 1.058092
    stale_warnings = [warning for warning in body["warnings"] if "forward-fill" in warning]
    assert len(stale_warnings) == 1
    assert "000001.SZ" in stale_warnings[0]


def test_candidate_history_portfolio_backtest_compares_nav_to_csi300_benchmark(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio-benchmark.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-02", "000001.SZ", 110.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
        _seed_csi300_benchmark(conn, [("2026-05-01", 100.0), ("2026-05-02", 120.0)])
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
    )

    summary = envelope["result"]["summary"]
    assert envelope["result_meta"]["tables_used"] == [
        "livermore_candidate_history",
        "choice_stock_daily_observation",
        "stock_adjustment_factor",
        "fact_choice_macro_daily",
    ]
    assert summary["benchmark"]["series_id"] == "CA.CSI300"
    assert summary["benchmark"]["coverage_status"] == "complete"
    assert summary["benchmark"]["requested_start_date"] == "2026-05-01"
    assert summary["benchmark"]["requested_end_date"] == "2026-05-02"
    assert summary["benchmark"]["cumulative_return"] == 0.2
    # strategy net return 0.09802 (costs incl. slippage) minus benchmark 0.2
    assert summary["benchmark"]["relative_cumulative_return"] == -0.10198


def test_candidate_history_portfolio_backtest_marks_unsupported_without_replay_rows(tmp_path) -> None:
    db_path = tmp_path / "candidate-history-portfolio-empty.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-31",
    )

    body = envelope["result"]
    assert body["status"] == "unsupported"
    assert body["summary"] is None
    assert body["nav_series"] == []
    assert body["caliber_disclosure"] is None


def test_candidate_history_portfolio_backtest_api_happy_path_and_query_validation(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-02", "000001.SZ", 112.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/market-data/livermore/candidate-history-portfolio-backtest",
        params={"snapshot_from": "2026-05-01", "snapshot_to": "2026-05-02"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["rule_version"] == "rv_livermore_candidate_history_portfolio_backtest_v1"
    assert body["result"]["status"] == "portfolio_proxy"
    assert body["result"]["summary"]["sample_days"] == 1
    assert (
        client.get(
            "/ui/market-data/livermore/candidate-history-portfolio-backtest",
            params={"snapshot_to": "not-a-date"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()


def test_cycle_proxy_backtest_payload_structure_characterization(tmp_path) -> None:
    """Lock the payload keys consumed by the frontend candidate-history page."""
    db_path = tmp_path / "cycle-proxy-structure.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Proxy A", "stock_candidate", 0.10, 0.12, 0.20, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-05-08'
            where snapshot_as_of_date = '2026-05-01'
            """
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_csi300_benchmark(conn, [("2026-05-01", 100.0), ("2026-05-08", 105.0)])
    finally:
        conn.close()

    envelope = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-01",
    )

    body = envelope["result"]
    required_payload_keys = {
        "status",
        "full_strategy_status",
        "proxy_signal_kind",
        "proxy_rule",
        "snapshot_from",
        "snapshot_to",
        "missing_full_strategy_inputs",
        "warnings",
        "caliber_disclosure",
        "summary",
        "nav_series",
    }
    assert required_payload_keys <= set(body)
    assert set(body["caliber_disclosure"]) == {
        "entry_price_warning",
        "return_field_stats",
        "sample_generation",
        "basis_notes",
    }
    assert set(body["caliber_disclosure"]["sample_generation"]) == {
        "tushare_era_rows",
        "native_era_rows",
    }
    required_summary_keys = {
        "sample_days",
        "candidate_rows",
        "cumulative_return",
        "annualized_return",
        "max_gain",
        "max_drawdown",
    }
    assert required_summary_keys <= set(body["summary"])
    assert {"return", "start_date", "end_date"} <= set(body["summary"]["max_gain"])
    assert {"return", "peak_date", "trough_date"} <= set(body["summary"]["max_drawdown"])
    assert {"series_id", "coverage_status", "cumulative_return", "relative_cumulative_return"} <= set(
        body["summary"]["benchmark"]
    )
    required_nav_keys = {"date", "exit_date", "period_return", "nav", "candidate_count"}
    assert required_nav_keys <= set(body["nav_series"][0])


def test_candidate_history_portfolio_backtest_payload_structure_characterization(tmp_path) -> None:
    """Lock the payload keys consumed by the frontend candidate-history page."""
    db_path = tmp_path / "candidate-history-portfolio-structure.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-02", "000001.SZ", 110.0),
            ],
        )
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Alpha", "stock_candidate", None, None, None, '{"market_state":"WARM"}'),
            ],
        )
        conn.execute("update livermore_candidate_history set data_status = 'pending'")
        _seed_csi300_benchmark(conn, [("2026-05-01", 100.0), ("2026-05-02", 120.0)])
    finally:
        conn.close()

    envelope = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
    )

    body = envelope["result"]
    required_payload_keys = {
        "status",
        "full_strategy_status",
        "signal_kind",
        "rebalance_rule",
        "weighting_rule",
        "snapshot_from",
        "snapshot_to",
        "missing_full_strategy_inputs",
        "warnings",
        "caliber_disclosure",
        "summary",
        "nav_series",
        "rebalance_log",
    }
    assert required_payload_keys <= set(body)
    assert set(body["caliber_disclosure"]) == {
        "entry_price_warning",
        "return_field_stats",
        "sample_generation",
        "basis_notes",
    }
    assert set(body["caliber_disclosure"]["sample_generation"]) == {
        "tushare_era_rows",
        "native_era_rows",
    }
    required_summary_keys = {
        "sample_days",
        "candidate_rows",
        "rebalance_count",
        "invested_rebalance_count",
        "cash_rebalance_count",
        "gross_turnover",
        "cost_drag",
        "cumulative_return",
        "annualized_return",
        "max_gain",
        "max_drawdown",
    }
    assert required_summary_keys <= set(body["summary"])
    required_nav_keys = {"date", "nav", "cash_weight", "holding_count"}
    assert required_nav_keys <= set(body["nav_series"][0])
    required_rebalance_keys = {
        "date",
        "market_state",
        "target_count",
        "buy_turnover",
        "sell_turnover",
        "transaction_cost",
    }
    assert required_rebalance_keys <= set(body["rebalance_log"][0])
    assert {"series_id", "coverage_status", "cumulative_return", "relative_cumulative_return"} <= set(
        body["summary"]["benchmark"]
    )
