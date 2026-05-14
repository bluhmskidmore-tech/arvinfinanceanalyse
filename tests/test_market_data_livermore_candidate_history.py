from __future__ import annotations

import sys
from datetime import date, timedelta
import json

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness
from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_backtest_window_summary,
    livermore_candidate_history_envelope,
)
from backend.app.tasks.livermore_candidate_history_materialize import (
    backfill_livermore_candidate_history,
    ensure_livermore_candidate_history_schema,
    materialize_livermore_candidate_history,
)
from tests.helpers import load_module


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
            "market_gate": {"state": "HOT"},
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
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(tmp_path / "missing-choice-stock-catalog.json"))
    get_settings.cache_clear()
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def _insert_strategy_score_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, str, str, str, float | None, float | None, float | None, str]],
) -> None:
    ensure_livermore_candidate_history_schema(conn)
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
            select selection_close, return_1d, return_5d, return_20d, data_status, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
        assert row is not None
        selection_close, r1, r5, r20, dst, signal_evidence_json = row
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
        expected_r5 = (float(tgt5[-1][0]) - selection_close) / selection_close
        expected_r20 = (float(tgt20[-1][0]) - selection_close) / selection_close
        assert abs(float(r5) - expected_r5) < 1e-9
        assert abs(float(r20) - expected_r20) < 1e-9
        assert dst == "complete"
        assert json.loads(str(signal_evidence_json))["market_state"] == "HOT"
    finally:
        conn.close()


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
                        }
                    ],
                }
            ]
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
              data_status
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


def test_task_materializes_factor_and_mean_reversion_signal_rows(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "other-strategies.duckdb"
    snap = date(2026, 5, 1)
    factor_stock = "000001.SZ"
    reversion_stock = "000002.SZ"
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
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = _fake_payload(as_of_date=snap.isoformat(), items=[])
        payload["factor_screen_candidates"] = {
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
        return payload, meta

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))

    assert out["row_count"] == 2
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
    assert set(by_kind) == {"factor_screen", "mean_reversion"}
    assert by_kind["factor_screen"][1:4] == (factor_stock, "Factor A", 1)
    assert json.loads(by_kind["factor_screen"][7])["score"] == 3.2
    assert abs(float(by_kind["factor_screen"][8]) - 0.1) < 1e-12
    assert by_kind["mean_reversion"][1:4] == (reversion_stock, "Reversion B", 1)
    assert by_kind["mean_reversion"][4:7] == (-0.22, 2.4, 0.72)
    assert json.loads(by_kind["mean_reversion"][7])["drawdown_60d"] == -0.31
    assert abs(float(by_kind["mean_reversion"][8]) - -0.1) < 1e-12


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
    calls: list[tuple[str, str | None]] = []

    def _fake_materialize(path: str, *, as_of_date: str | None = None) -> dict[str, object]:
        calls.append((path, as_of_date))
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

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-03")]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["row_count"] == 2


def test_candidate_history_run_cli_backfill_emits_json(monkeypatch, capsys, tmp_path) -> None:
    run_module = load_module(
        "backend.app.tasks.livermore_candidate_history_run",
        "backend/app/tasks/livermore_candidate_history_run.py",
    )
    calls: list[tuple[str, str, str]] = []

    def _fake_backfill(path: str, *, start_date: str, end_date: str) -> dict[str, object]:
        calls.append((path, start_date, end_date))
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

    assert calls == [(str(tmp_path / "moss.duckdb"), "2026-04-03", "2026-04-04")]
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "partial"
    assert out["processed_date_count"] == 2


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
    assert summary == {
        "row_count": 2,
        "complete_count": 1,
        "pending_count": 1,
        "partial_halt_count": 0,
        "missing_forward_return_count": 1,
        "avg_return_1d": -0.04,
        "avg_return_5d": 0.03,
        "avg_return_20d": 0.04,
        "horizon_stats": {
            "return_1d": {
                "available_count": 2,
                "missing_count": 0,
                "positive_count": 1,
                "non_positive_count": 1,
                "avg_return": -0.04,
                "win_rate": 0.5,
            },
            "return_5d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.03,
                "win_rate": 1.0,
            },
            "return_20d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.04,
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
                    "win_rate": 1.0,
                },
                "return_5d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.03,
                    "win_rate": 1.0,
                },
                "return_20d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.04,
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
                    "win_rate": 0.0,
                },
                "return_5d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "win_rate": None,
                },
                "return_20d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
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
        "included_completed_stats_dates": ["2026-05-06"],
        "excluded_from_completed_stats_dates": ["2026-04-30", "2026-05-07", "2026-05-08"],
        "date_reasons": [
            {
                "trade_date": "2026-04-30",
                "status": "unsupported",
                "reason_code": "missing_daily_limit_flags",
                "message": "daily_limit_flags absent; Livermore strategy replay unsupported for 2026-04-30.",
                "affects_completed_stats": False,
                "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
            },
            {
                "trade_date": "2026-05-06",
                "status": "completed",
                "reason_code": "no_strategy_signals",
                "message": "Full replay coverage produced no Livermore strategy signal rows for 2026-05-06.",
                "affects_completed_stats": True,
                "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
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
            },
        ],
    }


def test_backtest_summary_reports_incomplete_coverage_when_audit_is_missing_but_daily_flags_landed(tmp_path) -> None:
    db_path = tmp_path / "audit-missing.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        ensure_livermore_candidate_history_schema(conn)
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
                    "2026-06-03",
                    0.02,
                    0.10,
                    0.20,
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
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-06")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-08")
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
        "row_count": 1,
        "complete_row_count": 1,
        "pending_row_count": 0,
        "partial_halt_row_count": 0,
        "missing_forward_return_count": 0,
        "avg_return_1d": 0.02,
        "avg_return_5d": 0.1,
        "avg_return_20d": 0.2,
        "win_rate_1d": 1.0,
        "win_rate_5d": 1.0,
        "win_rate_20d": 1.0,
        "by_signal_kind": {"stock_candidate": 1},
        "by_signal_kind_horizon_stats": {
            "stock_candidate": {
                "return_1d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.02,
                    "win_rate": 1.0,
                },
                "return_5d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.1,
                    "win_rate": 1.0,
                },
                "return_20d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.2,
                    "win_rate": 1.0,
                },
            }
        },
        "included_snapshot_dates": ["2026-05-06"],
        "excluded_snapshot_dates": ["2026-05-08"],
    }
    assert summary["horizon_usable_stats"] == {
        "return_1d": {
            "available_count": 2,
            "missing_count": 0,
            "positive_count": 1,
            "non_positive_count": 1,
            "avg_return": 0.005,
            "win_rate": 0.5,
        },
        "return_5d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.1,
            "win_rate": 1.0,
        },
        "return_20d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.2,
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
                "win_rate": 0.5,
            },
            "return_5d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.1,
                "win_rate": 1.0,
            },
            "return_20d": {
                "available_count": 1,
                "missing_count": 1,
                "positive_count": 1,
                "non_positive_count": 0,
                "avg_return": 0.2,
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
                    "win_rate": 1.0,
                },
                "return_5d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.1,
                    "win_rate": 1.0,
                },
                "return_20d": {
                    "available_count": 1,
                    "missing_count": 0,
                    "positive_count": 1,
                    "non_positive_count": 0,
                    "avg_return": 0.2,
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
                    "win_rate": 0.0,
                },
                "return_5d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
                    "win_rate": None,
                },
                "return_20d": {
                    "available_count": 0,
                    "missing_count": 1,
                    "positive_count": 0,
                    "non_positive_count": 0,
                    "avg_return": None,
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
            "win_rate": 0.5,
        },
        "return_5d": {
            "available_count": 1,
            "missing_count": 1,
            "positive_count": 1,
            "non_positive_count": 0,
            "avg_return": 0.1,
            "win_rate": 1.0,
        },
        "return_20d": {
            "available_count": 0,
            "missing_count": 2,
            "positive_count": 0,
            "non_positive_count": 0,
            "avg_return": None,
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
            "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
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
    get_settings.cache_clear()


def test_strategy_score_service_ranks_current_market_state_by_t5_score(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_strategy_score_envelope,
    )

    db_path = tmp_path / "strategy-score.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Factor A", "factor_screen", 0.01, 0.02, 0.03, '{"market_state":"HOT"}'),
                ("2026-05-02", "000002.SZ", "Factor B", "factor_screen", 0.00, 0.01, 0.02, '{"market_state":"HOT"}'),
                ("2026-05-01", "000003.SZ", "Trend A", "stock_candidate", 0.01, 0.10, 0.01, '{"market_state":"HOT"}'),
                ("2026-05-02", "000004.SZ", "Trend B", "stock_candidate", 0.01, -0.02, 0.01, '{"market_state":"HOT"}'),
                ("2026-05-01", "000005.SZ", "Theme A", "theme_breakout", 0.01, 0.20, 0.01, '{"market_state":"HOT"}'),
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
    assert body["min_sample"] == 2
    assert body["current_market_state"] == "HOT"
    current_rows = body["current_market_state_rows"]
    assert [row["signal_kind"] for row in current_rows] == ["factor_screen", "stock_candidate", "theme_breakout"]
    assert current_rows[0]["strategy_label"] == "多因子"
    assert current_rows[0]["sample_status"] == "sufficient"
    assert current_rows[0]["priority_rank"] == 1
    assert current_rows[0]["priority_score"] == 101.5
    assert current_rows[0]["priority_label"] == "优先复核"
    assert current_rows[0]["stats"]["return_5d"] == {
        "available_count": 2,
        "missing_count": 0,
        "positive_count": 2,
        "non_positive_count": 0,
        "avg_return": 0.015,
        "win_rate": 1.0,
    }
    assert current_rows[1]["priority_score"] == 54.0
    assert current_rows[2]["sample_status"] == "insufficient"
    assert current_rows[2]["priority_score"] is None
    assert "样本不足" in current_rows[2]["reason"]
    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.strategy_score"
    assert "livermore_candidate_history" in envelope["result_meta"]["tables_used"]


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
            for index in range(1, 3)
        ]
        _insert_strategy_score_rows(conn, factor_rows + trend_rows)
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
    assert maturity["worst_snapshot"]["win_rate"] == 1.0
    tail_bucket = next(bucket for bucket in factor_diagnostics["rank_buckets"] if bucket["label"] == "11-20")
    assert tail_bucket["included_in_priority"] is False
    assert tail_bucket["priority_label"] == "降权观察"
    assert tail_bucket["stats"]["return_5d"]["available_count"] == 10
    assert tail_bucket["stats"]["return_5d"]["avg_return"] == -0.02
    assert "rank > 10" in tail_bucket["reason"]

    trend = next(row for row in rows if row["signal_kind"] == "stock_candidate")
    risk_flags = trend["diagnostics"]["risk_flags"]
    assert risk_flags[0]["kind"] == "long_window_risk"
    assert risk_flags[0]["horizon"] == "return_20d"
    assert "T+20" in risk_flags[0]["reason"]
    assert risk_flags[0]["stats"]["avg_return"] == -0.03


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
    assert len(current_rows) == 4
    assert {row["signal_kind"] for row in current_rows} == {
        "stock_candidate",
        "factor_screen",
        "theme_breakout",
        "mean_reversion",
    }
    assert all(row["sample_status"] == "insufficient" for row in current_rows)
    assert all(row["priority_score"] is None for row in current_rows)
    assert all("当前状态样本不足" in row["reason"] for row in current_rows)


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

    assert (
        client.get("/ui/market-data/livermore/strategy-score", params={"snapshot_from": "not-a-date"}).status_code
        == 422
    )
    assert client.get("/ui/market-data/livermore/strategy-score", params={"min_sample": 0}).status_code == 422
    assert (
        client.get(
            "/ui/market-data/livermore/strategy-score",
            params={"primary_horizon": "return_10d"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()
