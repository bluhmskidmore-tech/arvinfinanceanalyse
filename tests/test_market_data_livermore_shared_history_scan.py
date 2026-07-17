"""Golden parity for the shared candidate/trading stock history scan."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import duckdb

from backend.app.services import market_data_livermore_service as service
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness


AS_OF_DATE = "2026-06-30"
HISTORY_WINDOW = service.CHOICE_STOCK_HISTORY_WINDOW


def _seed_adversarial_history(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          turn double,
          amount double,
          volume double,
          tradestatus varchar
        )
        """
    )
    as_of = date.fromisoformat(AS_OF_DATE)
    rows: list[tuple[object, ...]] = []
    for offset in range(136):
        trade_date = (as_of - timedelta(days=offset)).isoformat()
        close_value: float | None = float(1000 + offset)
        turn: float | None = float(10 + offset)
        amount: float | None = float(10000 + offset)
        volume: float | None = float(100000 + offset)
        tradestatus: str | None = "Trading"
        if offset in {3, 7}:
            tradestatus = "Suspended"
        elif offset == 8:
            tradestatus = " Trading "
        elif offset == 9:
            tradestatus = None
        if offset == 2:
            close_value = None
        elif offset == 10:
            close_value = 0.0
        if offset == 4:
            turn = None
        elif offset == 11:
            turn = 0.0
        if offset == 5:
            amount = None
        if offset == 6:
            volume = None
        rows.append(
            (
                trade_date,
                "BOTH",
                close_value,
                turn,
                amount,
                volume,
                tradestatus,
            )
        )

    rows.extend(
        [
            ("2026-07-01", "BOTH", 9999.0, 999.0, 99999.0, 999999.0, "Trading"),
            ("2026-06-29", "CANDIDATE_ONLY", 21.0, 2.1, 210.0, 2100.0, "Trading"),
            ("2026-06-30", "CANDIDATE_ONLY", 22.0, 2.2, 220.0, 2200.0, "Suspended"),
            ("2026-06-29", "TRADING_ONLY", 31.0, 3.1, 310.0, 3100.0, "Trading"),
            ("2026-06-30", "TRADING_ONLY", 32.0, 3.2, 320.0, 3200.0, "Trading"),
        ]
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _candidate_history_oracle(
    conn: duckdb.DuckDBPyConnection,
    stock_codes: list[str],
) -> dict[str, dict[str, list[float]]]:
    placeholders = ",".join("?" for _ in stock_codes)
    rows = conn.execute(
        f"""
        with ranked_history as (
          select
            stock_code,
            close_value,
            turn,
            row_number() over (
              partition by stock_code
              order by cast(trade_date as date) desc
            ) as rn
          from choice_stock_daily_observation
          where stock_code in ({placeholders})
            and cast(trade_date as date) <= cast(? as date)
        )
        select stock_code, close_value, turn
        from ranked_history
        where rn <= ?
        order by stock_code asc, rn desc
        """,
        [*stock_codes, AS_OF_DATE, HISTORY_WINDOW],
    ).fetchall()
    result: dict[str, dict[str, list[float]]] = {}
    for stock_code_raw, close_raw, turn_raw in rows:
        stock_code = str(stock_code_raw or "")
        close_value = service._safe_float(close_raw)
        turn = service._safe_float(turn_raw)
        if not stock_code or close_value is None or turn is None:
            continue
        bucket = result.setdefault(stock_code, {"close": [], "turn": []})
        bucket["close"].append(close_value)
        bucket["turn"].append(turn)
    return result


def _trading_history_oracle(
    conn: duckdb.DuckDBPyConnection,
    stock_codes: list[str],
) -> dict[str, dict[str, list[object]]]:
    placeholders = ",".join("?" for _ in stock_codes)
    rows = conn.execute(
        f"""
        with ranked_history as (
          select
            stock_code,
            close_value,
            amount,
            volume,
            row_number() over (
              partition by stock_code
              order by cast(trade_date as date) desc
            ) as rn
          from choice_stock_daily_observation
          where stock_code in ({placeholders})
            and cast(trade_date as date) <= cast(? as date)
            and trim(coalesce(tradestatus, '')) = 'Trading'
        )
        select stock_code, close_value, amount, volume
        from ranked_history
        where rn <= ?
        order by stock_code asc, rn desc
        """,
        [*stock_codes, AS_OF_DATE, HISTORY_WINDOW],
    ).fetchall()
    result: dict[str, dict[str, list[object]]] = {}
    for stock_code_raw, close_value, amount, volume in rows:
        stock_code = str(stock_code_raw or "")
        if not stock_code:
            continue
        bucket = result.setdefault(
            stock_code,
            {"close": [], "amount": [], "volume": []},
        )
        bucket["close"].append(close_value)
        bucket["amount"].append(amount)
        bucket["volume"].append(volume)
    return result


def test_dual_stock_history_scan_matches_both_legacy_windows() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_adversarial_history(conn)
        candidate_codes = ["BOTH", "CANDIDATE_ONLY"]
        trading_codes = ["BOTH", "TRADING_ONLY"]
        expected_candidate = _candidate_history_oracle(conn, candidate_codes)
        expected_trading = _trading_history_oracle(conn, trading_codes)

        actual = service._load_dual_stock_history_inputs(
            conn=conn,
            as_of_date=AS_OF_DATE,
            candidate_stock_codes=candidate_codes,
            trading_stock_codes=trading_codes,
        )
    finally:
        conn.close()

    assert actual.candidate_history_by_code == expected_candidate
    assert actual.trading_history_by_code == expected_trading
    assert set(actual.candidate_history_by_code) == {"BOTH", "CANDIDATE_ONLY"}
    assert set(actual.trading_history_by_code) == {"BOTH", "TRADING_ONLY"}

    candidate_both = actual.candidate_history_by_code["BOTH"]
    trading_both = actual.trading_history_by_code["BOTH"]
    assert len(candidate_both["close"]) == 126
    assert candidate_both["close"][0] == 1129.0
    assert candidate_both["close"][-1] == 1000.0
    assert len(trading_both["close"]) == 130
    assert trading_both["close"][0] == 1132.0
    assert trading_both["close"][-1] == 1000.0
    assert None in trading_both["close"]
    assert None in trading_both["amount"]
    assert None in trading_both["volume"]
    assert 9999.0 not in candidate_both["close"]
    assert 9999.0 not in trading_both["close"]


class _CountingConnection:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self.history_window_queries = 0

    def execute(self, query: str, parameters=None):
        normalized = " ".join(str(query).lower().split())
        if (
            "choice_stock_daily_observation" in normalized
            and "row_number() over" in normalized
            and "ranked_history" in normalized
        ):
            self.history_window_queries += 1
        if parameters is None:
            return self._conn.execute(query)
        return self._conn.execute(query, parameters)


def _seed_integrated_stock_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_universe (
          as_of_date varchar, stock_code varchar, stock_name varchar,
          source_version varchar, vendor_version varchar
        );
        create table choice_stock_sector_membership (
          as_of_date varchar, stock_code varchar, sw2021code varchar, sw2021 varchar,
          source_version varchar, vendor_version varchar
        );
        create table choice_stock_daily_observation (
          trade_date varchar, stock_code varchar, open_value double, high_value double,
          low_value double, close_value double, turn double, pctchange double,
          amplitude double, highlimit double, lowlimit double, volume double,
          amount double, tradestatus varchar, source_version varchar, vendor_version varchar
        );
        create table choice_stock_limit_quality (
          as_of_date varchar, stock_code varchar, issurgedlimit varchar, hlimitedays integer,
          source_version varchar, vendor_version varchar
        )
        """
    )
    conn.execute(
        "insert into choice_stock_universe values (?, '600000.SH', 'Alpha', 'sv_u', 'vv_u')",
        [AS_OF_DATE],
    )
    conn.execute(
        "insert into choice_stock_sector_membership values (?, '600000.SH', '801780', 'Bank', 'sv_m', 'vv_m')",
        [AS_OF_DATE],
    )
    rows = []
    as_of = date.fromisoformat(AS_OF_DATE)
    for offset in range(136):
        trade_date = (as_of - timedelta(days=offset)).isoformat()
        rows.append(
            (
                trade_date,
                "600000.SH",
                10.0,
                10.5,
                9.5,
                10.2 + offset / 100.0,
                1.2,
                0.5,
                2.0,
                11.2,
                9.2,
                1200.0,
                12000.0,
                "Suspended" if offset in {3, 7} else "Trading",
                "sv_d",
                "vv_d",
            )
        )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute(
        "insert into choice_stock_limit_quality values (?, '600000.SH', '0', 0, 'sv_l', 'vv_l')",
        [AS_OF_DATE],
    )


def test_warm_choice_stock_outputs_use_one_shared_history_window_query(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    db_path = tmp_path / "shared-history.duckdb"
    raw_conn = duckdb.connect(str(db_path))
    _seed_integrated_stock_tables(raw_conn)
    conn = _CountingConnection(raw_conn)
    caplog.set_level("INFO", logger=service.__name__)
    ready_coverage = SimpleNamespace(
        full_coverage=True,
        status="ready",
        message="ready",
        completed_request_items=[],
        missing_request_items=[],
    )
    readiness = ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path="unit-test.json",
        missing_input_families=[],
        message="ready",
    )
    monkeypatch.setattr(
        service,
        "_load_sector_rank_inputs",
        lambda **_kwargs: ([object()], [], [], []),
    )
    monkeypatch.setattr(
        service,
        "compute_sector_rank",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            payload={
                "items": [
                    {"rank": 1, "sector_code": "801780", "sector_name": "Bank"}
                ]
            },
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_factor_screen_rows",
        lambda **_kwargs: service._FactorScreenLoadResult(
            rows=[],
            snapshot_as_of_date=None,
            tables_used=[],
            unavailable_reason="not seeded",
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_theme_breakout_snapshots",
        lambda **_kwargs: ([], [], [], [], service._ThemeBreakoutEvidenceProvenance()),
    )
    monkeypatch.setattr(service, "_load_risk_exit_snapshots", lambda **_kwargs: ([], [], [], []))
    monkeypatch.setattr(service, "_risk_exit_input_block_reason", lambda **_kwargs: "")

    try:
        outputs = service._load_choice_stock_outputs_on_conn(
            conn,
            duckdb_path=str(db_path),
            as_of_date=AS_OF_DATE,
            market_state="WARM",
            stock_readiness=readiness,
            backfill_mode=True,
            stock_candidate_policy="exp3b",
            macro_score=None,
            sector_coverage=ready_coverage,
            stock_coverage=ready_coverage,
        )
        optimized_query_count = conn.history_window_queries
        conn.history_window_queries = 0

        def fail_dual_history(**_kwargs):
            raise duckdb.Error("forced dual history failure")

        monkeypatch.setattr(service, "_load_dual_stock_history_inputs", fail_dual_history)
        fallback_outputs = service._load_choice_stock_outputs_on_conn(
            conn,
            duckdb_path=str(db_path),
            as_of_date=AS_OF_DATE,
            market_state="WARM",
            stock_readiness=readiness,
            backfill_mode=True,
            stock_candidate_policy="exp3b",
            macro_score=None,
            sector_coverage=ready_coverage,
            stock_coverage=ready_coverage,
        )
        fallback_query_count = conn.history_window_queries
    finally:
        raw_conn.close()

    assert outputs.stock_candidates_payload is not None
    assert optimized_query_count == 1
    assert any(
        "livermore_stock_loader_timing stage=dual_stock_history_inputs"
        in record.message
        for record in caplog.records
    )
    assert fallback_outputs.stock_candidates_payload == outputs.stock_candidates_payload
    assert fallback_query_count == 2


def test_candidate_history_loader_none_falls_back_to_legacy_window(tmp_path) -> None:
    db_path = tmp_path / "candidate-fallback.duckdb"
    conn = duckdb.connect(str(db_path))
    _seed_integrated_stock_tables(conn)
    sector_rank_payload = {
        "items": [{"rank": 1, "sector_code": "801780", "sector_name": "Bank"}]
    }
    try:
        expected = service._load_stock_candidate_snapshots(
            duckdb_path=str(db_path),
            as_of_date=AS_OF_DATE,
            sector_rank_payload=sector_rank_payload,
            conn=conn,
        )
        actual = service._load_stock_candidate_snapshots(
            duckdb_path=str(db_path),
            as_of_date=AS_OF_DATE,
            sector_rank_payload=sector_rank_payload,
            history_loader=lambda _stock_codes: None,
            conn=conn,
        )
    finally:
        conn.close()

    assert actual == expected
