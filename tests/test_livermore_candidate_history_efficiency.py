from __future__ import annotations

import duckdb

from backend.app.services import livermore_candidate_history_service as service
from backend.app.tasks.livermore_candidate_history_materialize import (
    ensure_livermore_candidate_history_schema,
)


class _CountingRow(dict[str, object]):
    row_scan_count = 0

    def items(self):  # type: ignore[override]
        type(self).row_scan_count += 1
        return super().items()


class _CountingRows(list[dict[str, object]]):
    iteration_count = 0

    def __iter__(self):  # type: ignore[override]
        type(self).iteration_count += 1
        return super().__iter__()


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


def test_strategy_score_reuses_loaded_window_rows_for_backtest_summary(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "strategy-score-single-load.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Trend A", "stock_candidate", 0.01, 0.03, 0.04, '{"market_state":"HOT"}'),
                ("2026-05-02", "000002.SZ", "Trend B", "stock_candidate", 0.02, 0.04, 0.05, '{"market_state":"HOT"}'),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    load_count = 0
    original_load = service._load_backtest_window_rows

    def _counting_load(*args: object, **kwargs: object) -> list[dict[str, object]]:
        nonlocal load_count
        load_count += 1
        return original_load(*args, **kwargs)

    monkeypatch.setattr(service, "_load_backtest_window_rows", _counting_load)

    envelope = service.livermore_candidate_history_strategy_score_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
        current_market_state="HOT",
        min_sample=2,
        primary_horizon="return_5d",
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.strategy_score"
    assert load_count == 1


def test_strategy_optimization_reuses_loaded_window_rows_for_backtest_summary(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "strategy-optimization-single-load.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_strategy_score_rows(
            conn,
            [
                ("2026-05-01", "000001.SZ", "Factor A", "factor_screen", 0.01, 0.03, 0.04, '{"market_state":"HOT"}'),
                ("2026-05-02", "000002.SZ", "Factor B", "factor_screen", 0.02, 0.04, 0.05, '{"market_state":"HOT"}'),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    load_count = 0
    original_load = service._load_backtest_window_rows

    def _counting_load(*args: object, **kwargs: object) -> list[dict[str, object]]:
        nonlocal load_count
        load_count += 1
        return original_load(*args, **kwargs)

    monkeypatch.setattr(service, "_load_backtest_window_rows", _counting_load)

    envelope = service.livermore_candidate_history_strategy_optimization_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
        current_market_state="HOT",
        min_sample=2,
        primary_horizon="return_5d",
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.livermore.strategy_optimization"
    assert load_count == 1


def test_stock_candidate_state_scopes_resolves_market_state_once_per_stock_row(monkeypatch) -> None:
    items = [
        {
            "signal_kind": "stock_candidate",
            "signal_evidence_json": '{"market_state":"WARM","abnormal_turnover":1.2}',
            "return_5d": 0.02,
        },
        {
            "signal_kind": "stock_candidate",
            "signal_evidence_json": '{"market_state":"HOT","abnormal_turnover":1.4}',
            "return_5d": 0.04,
        },
        {
            "signal_kind": "stock_candidate",
            "signal_evidence_json": '{"market_state":"OVERHEAT","abnormal_turnover":1.8}',
            "return_5d": -0.03,
        },
    ]
    call_count = 0
    original_resolver = service._market_state_from_signal_evidence

    def _counting_resolver(item: dict[str, object]) -> str:
        nonlocal call_count
        call_count += 1
        return original_resolver(item)

    monkeypatch.setattr(service, "_market_state_from_signal_evidence", _counting_resolver)

    scopes = service._stock_candidate_state_scopes(items)

    assert scopes["stock_candidate_all_states"]["return_5d"]["available_count"] == 3
    assert scopes["stock_candidate_entry_allowed_states_only"]["return_5d"]["available_count"] == 2
    assert scopes["overheat_ratio"] == 1 / 3
    assert call_count == len(items)


def test_strategy_optimization_slices_parse_signal_evidence_once_per_row(monkeypatch) -> None:
    items = [
        {
            "signal_kind": "stock_candidate",
            "candidate_rank": 1,
            "signal_evidence_json": (
                '{"market_state":"HOT","fundamental_overlay_status":"applied",'
                '"abnormal_turnover":1.5,"gap_norm":0.1,"breakout_extension_norm":0.2}'
            ),
            "return_5d": 0.04,
        },
        {
            "signal_kind": "stock_candidate",
            "candidate_rank": 2,
            "signal_evidence_json": (
                '{"market_state":"WARM","fundamental_overlay_status":"not_applied",'
                '"abnormal_turnover":2.1,"gap_norm":0.3,"breakout_extension_norm":0.32}'
            ),
            "return_5d": 0.02,
        },
    ]
    parse_count = 0
    original_parser = service._parse_signal_evidence_json

    def _counting_parser(value: object) -> dict[str, object]:
        nonlocal parse_count
        parse_count += 1
        return original_parser(value)

    monkeypatch.setattr(service, "_parse_signal_evidence_json", _counting_parser)

    slices = service._build_strategy_optimization_slices(
        items,
        min_sample=1,
        primary_horizon="return_5d",
    )

    assert any(row["slice_key"] == "stock_candidate:market_state:HOT" for row in slices)
    assert any(row["slice_key"] == "stock_candidate:fundamental_overlay:applied" for row in slices)
    assert any(row["slice_key"] == "stock_candidate:gap_norm:0-0.2" for row in slices)
    assert all("_signal_evidence_cache" not in item for item in items)
    assert parse_count == len(items)


def test_horizon_stats_reads_return_fields_once_per_row() -> None:
    rows = [
        _CountingRow({"return_1d": 0.01, "return_5d": 0.05, "return_10d": 0.08, "return_20d": 0.1}),
        _CountingRow({"return_1d": -0.02, "return_5d": None, "return_10d": 0.02, "return_20d": 0.03}),
        _CountingRow({"return_1d": "bad", "return_5d": 0.01, "return_10d": None, "return_20d": -0.01}),
    ]
    _CountingRow.row_scan_count = 0

    stats = service._build_horizon_stats(rows)

    assert stats["return_1d"] == {
        "available_count": 2,
        "missing_count": 1,
        "positive_count": 1,
        "non_positive_count": 1,
        "avg_return": -0.005,
        "win_rate": 0.5,
    }
    assert stats["return_5d"]["available_count"] == 2
    assert stats["return_10d"]["available_count"] == 2
    assert stats["return_20d"]["available_count"] == 3
    assert _CountingRow.row_scan_count == len(rows)


def test_date_weighted_horizon_stats_scan_rows_once() -> None:
    rows = _CountingRows(
        [
            {
                "snapshot_as_of_date": "2026-05-01",
                "return_1d": 0.01,
                "return_5d": 0.05,
                "return_10d": None,
                "return_20d": 0.1,
            },
            {
                "snapshot_as_of_date": "2026-05-01",
                "return_1d": 0.03,
                "return_5d": None,
                "return_10d": 0.02,
                "return_20d": 0.12,
            },
            {
                "snapshot_as_of_date": "2026-05-02",
                "return_1d": -0.02,
                "return_5d": 0.01,
                "return_10d": 0.04,
                "return_20d": None,
            },
        ]
    )
    _CountingRows.iteration_count = 0

    stats = service._build_date_weighted_horizon_stats(rows)

    assert stats["return_1d"] == {
        "available_day_count": 2,
        "candidate_row_count": 3,
        "avg_return": 0.0,
        "positive_day_rate": 0.5,
        "worst_day_return": -0.02,
        "best_day_return": 0.02,
    }
    assert stats["return_5d"]["candidate_row_count"] == 2
    assert stats["return_10d"]["available_day_count"] == 2
    assert stats["return_20d"]["candidate_row_count"] == 2
    assert _CountingRows.iteration_count == 1


def test_tracked_snapshot_stat_reads_snapshot_rows_once() -> None:
    rows = _CountingRows(
        [
            {"return_1d": 0.01, "return_5d": 0.05, "return_10d": 0.08, "return_20d": 0.1},
            {"return_1d": -0.02, "return_5d": None, "return_10d": 0.02, "return_20d": None},
        ]
    )
    _CountingRows.iteration_count = 0

    stat = service._tracked_snapshot_stat("2026-05-01", rows)

    assert stat["snapshot_as_of_date"] == "2026-05-01"
    assert stat["candidate_count"] == 2
    assert stat["horizons"]["return_1d"]["status"] == "complete"
    assert stat["horizons"]["return_5d"]["status"] == "partial"
    assert stat["horizons"]["return_20d"]["status"] == "partial"
    assert _CountingRows.iteration_count == 1


def test_maturity_diagnostics_group_rows_once_for_snapshot_outputs() -> None:
    rows = _CountingRows(
        [
            {
                "snapshot_as_of_date": "2026-05-01",
                "return_1d": 0.01,
                "return_5d": 0.05,
                "return_10d": 0.08,
                "return_20d": 0.1,
            },
            {
                "snapshot_as_of_date": "2026-05-02",
                "return_1d": -0.02,
                "return_5d": None,
                "return_10d": 0.02,
                "return_20d": None,
            },
        ]
    )
    _CountingRows.iteration_count = 0

    diagnostics = service._maturity_diagnostics(
        rows,
        primary_horizon="return_5d",
    )

    assert diagnostics["mature_snapshot_count"] == 1
    assert [row["snapshot_as_of_date"] for row in diagnostics["snapshot_stats"]] == ["2026-05-01"]
    assert [row["snapshot_as_of_date"] for row in diagnostics["tracked_snapshots"]] == [
        "2026-05-01",
        "2026-05-02",
    ]
    assert diagnostics["tracked_snapshots"][1]["horizons"]["return_5d"]["status"] == "pending"
    assert _CountingRows.iteration_count == 1
