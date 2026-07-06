from __future__ import annotations

import duckdb
import pytest

from tests.helpers import load_module


def _create_candidate_history_fixture(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          candidate_rank integer,
          selection_close double,
          forward_trade_date_1d varchar,
          forward_trade_date_5d varchar,
          forward_trade_date_10d varchar,
          forward_trade_date_20d varchar,
          return_1d double,
          return_5d double,
          return_10d double,
          return_20d double,
          data_status varchar,
          formula_version varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar,
          signal_kind varchar,
          close_strength double,
          abnormal_turnover double,
          gap_norm double,
          market_state varchar,
          signal_evidence_json varchar
        )
        """
    )
    conn.execute(
        """
        insert into livermore_candidate_history (
          snapshot_as_of_date, stock_code, stock_name, candidate_rank, selection_close,
          forward_trade_date_1d, forward_trade_date_5d, forward_trade_date_10d, forward_trade_date_20d,
          return_1d, return_5d, return_10d, return_20d,
          data_status, formula_version, source_version, vendor_version, rule_version, run_id,
          signal_kind, close_strength, abnormal_turnover, gap_norm, market_state, signal_evidence_json
        ) values (
          '2026-01-06', '000001.SZ', 'Ping', 1, 100.0,
          '2026-01-07', null, null, null,
          0.01, null, null, null,
          'pending', 'fv_old', 'sv_old', 'vv_old', 'rv_old', 'run-old',
          'stock_candidate', 0.96, 1.4, 0.02, 'HOT', '{}'
        )
        """
    )


def _create_price_and_factor_fixture(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?)",
        [
            ("2026-01-06", "000001.SZ", 100.0),
            ("2026-01-07", "000001.SZ", 101.0),
        ],
    )
    conn.execute(
        """
        create table stock_adjustment_factor (
          stock_code varchar,
          trade_date varchar,
          adj_factor double,
          source_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        "insert into stock_adjustment_factor values (?, ?, ?, 'sv_adj', 'run-adj')",
        [
            ("000001.SZ", "2026-01-06", 1.0),
            ("000001.SZ", "2026-01-07", 1.2),
        ],
    )


def test_backfill_adjusted_returns_updates_existing_candidate_rows(tmp_path) -> None:
    db_path = tmp_path / "adjusted-backfill.duckdb"
    report_path = tmp_path / "adjusted-report.md"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_candidate_history_fixture(conn)
        _create_price_and_factor_fixture(conn)
    finally:
        conn.close()

    module = load_module("scripts.backfill_adjusted_returns", "scripts/backfill_adjusted_returns.py")
    result = module.backfill_adjusted_returns(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-06",
        report_path=report_path,
    )

    assert result["status"] == "completed"
    assert result["candidate_updated_count"] == 1
    assert report_path.exists()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select return_1d, return_1d_adj, ex_div_in_window, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return_1d, return_1d_adj, ex_div_in_window, signal_evidence_json = row
    assert return_1d == pytest.approx(0.01)
    assert return_1d_adj == pytest.approx((101.0 * 1.2) / (100.0 * 1.0) - 1.0)
    assert ex_div_in_window is True
    assert "partial_missing_adj_factor" not in str(signal_evidence_json)


def test_stock_adjustment_factor_backfill_dry_run_uses_history_coverage_without_fetch(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-dry-run.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?)",
            [
                ("2026-01-06", "000001.SZ"),
                ("2026-01-07", "000002.SZ"),
            ],
        )
    finally:
        conn.close()

    module = load_module("scripts.backfill_stock_adjustment_factor", "scripts/backfill_stock_adjustment_factor.py")
    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-07",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["code_count"] == 2
    assert result["date_count"] == 2
    assert result["would_call_tushare"] is True
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()
    assert "stock_adjustment_factor" not in tables


class _AdjFactorClient:
    def __init__(self, rows_by_date: dict[str, list[dict[str, object]]]) -> None:
        self.rows_by_date = rows_by_date
        self.call_count = 0

    def adj_factor(self, **kwargs: object) -> list[dict[str, object]]:
        self.call_count += 1
        return self.rows_by_date.get(str(kwargs.get("trade_date")), [])


def _create_adjustment_factor_backfill_fixture(db_path) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?)",
            [
                ("2026-01-06", "000001.SZ"),
                ("2026-01-06", "000002.SZ"),
            ],
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, 'sv_old', 'run-old')",
            [
                ("000001.SZ", "2026-01-06", 1.0),
                ("000002.SZ", "2026-01-06", 2.0),
            ],
        )
    finally:
        conn.close()


def test_stock_adjustment_factor_backfill_requires_backup_or_governance_lock(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-guard.duckdb"
    _create_adjustment_factor_backfill_fixture(db_path)
    module = load_module("scripts.backfill_stock_adjustment_factor_guard", "scripts/backfill_stock_adjustment_factor.py")
    client = _AdjFactorClient(
        {
            "20260106": [
                {"ts_code": "000001.SZ", "trade_date": "20260106", "adj_factor": 1.1},
            ]
        }
    )

    with pytest.raises(RuntimeError, match="requires --target-backup-path or --governance-lock"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            start_date="2026-01-06",
            end_date="2026-01-06",
            client=client,
        )
    assert client.call_count == 0


def test_stock_adjustment_factor_backfill_partial_vendor_response_preserves_existing_rows(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-partial.duckdb"
    _create_adjustment_factor_backfill_fixture(db_path)
    module = load_module("scripts.backfill_stock_adjustment_factor_partial", "scripts/backfill_stock_adjustment_factor.py")

    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-06",
        client=_AdjFactorClient(
            {
                "20260106": [
                    {"ts_code": "000001.SZ", "trade_date": "20260106", "adj_factor": 1.1},
                ]
            }
        ),
        governance_lock=True,
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, adj_factor
            from stock_adjustment_factor
            where trade_date = '2026-01-06'
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert result["status"] == "partial_completed"
    assert result["requested_cell_count"] == 2
    assert result["returned_cell_count"] == 1
    assert rows == [("000001.SZ", pytest.approx(1.1)), ("000002.SZ", pytest.approx(2.0))]
    assert result["write_safety"]["status"] == "governance_lock_acknowledged"
