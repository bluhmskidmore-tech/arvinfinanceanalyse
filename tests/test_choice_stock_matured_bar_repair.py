from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.adjusted_returns import ensure_stock_adjustment_factor_schema
from backend.app.tasks import choice_stock_matured_bar_repair as repair_module
from backend.app.tasks.choice_stock_matured_bar_repair import (
    BJ_CODES,
    FACTOR_DATES,
    SUSPENDED_DATES,
    repair_choice_stock_matured_missing_bars,
)
from backend.app.tasks.livermore_candidate_history_materialize import (
    ensure_livermore_candidate_history_schema,
)


BJ_DATES = (
    "2026-07-22",
    "2026-07-23",
    "2026-07-24",
    "2026-07-27",
    "2026-07-28",
    "2026-07-29",
    "2026-07-30",
    "2026-07-31",
    "2026-08-03",
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
)
MARKET_DATES_AFTER_AUG18 = (
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-07",
    "2026-09-08",
    "2026-09-09",
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-16",
)
SZ_VALID_DATES = MARKET_DATES_AFTER_AUG18[:9] + MARKET_DATES_AFTER_AUG18[-2:]
OBS_COLUMNS = (
    "trade_date",
    "stock_code",
    "open_value",
    "high_value",
    "low_value",
    "close_value",
    "volume",
    "amount",
    "pctchange",
    "turn",
    "amplitude",
    "tradestatus",
    "highlimit",
    "lowlimit",
    "field_keys_json",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
)


def _write_receipt(path: Path, payload: dict[str, object]) -> Path:
    payload["payload_sha256"] = repair_module._canonical_sha256(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _staging_receipts(tmp_path: Path) -> tuple[Path, Path, Path]:
    rows: list[dict[str, object]] = []
    for code_index, stock_code in enumerate(BJ_CODES):
        for date_index, trade_date in enumerate(BJ_DATES):
            close = 10.0 + code_index + date_index / 10
            rows.append(
                {
                    "trade_date": trade_date,
                    "stock_code": stock_code,
                    "open_value": close - 0.1,
                    "high_value": close + 0.2,
                    "low_value": close - 0.2,
                    "close_value": close,
                    "volume": 1000.0,
                    "amount": close * 100.0,
                    "pctchange": 0.5,
                    "turn": 2.0,
                    "amplitude": 4.0,
                    "tradestatus": "Trading",
                    "highlimit": close * 1.3,
                    "lowlimit": close * 0.7,
                    "field_keys": [
                        "daily_limit_flags",
                        "daily_ohlcv_amount",
                        "daily_return_turnover_amplitude",
                        "daily_trade_status",
                    ],
                }
            )
    bars = {
        "schema": "tushare_missing_bars_staging/v1",
        "status": "completed",
        "vendor": "tushare",
        "production_duckdb_written": False,
        "scopes": [
            {
                "scope": "bj_matured_missing_bars",
                "codes": list(BJ_CODES),
                "start_date": BJ_DATES[0],
                "end_date": BJ_DATES[-1],
                "row_count": len(rows),
                "rows_sha256": repair_module._canonical_sha256(rows),
                "rows": rows,
            }
        ],
    }
    suspension_records = [
        {
            "ts_code": "002870.SZ",
            "trade_date": trade_date.replace("-", ""),
            "suspend_timing": None,
            "suspend_type": "S",
        }
        for trade_date in SUSPENDED_DATES
    ] + [
        {
            "ts_code": "002870.SZ",
            "trade_date": "20260915",
            "suspend_timing": None,
            "suspend_type": "R",
        }
    ]
    suspension = {
        "schema": "tushare_suspension_staging/v1",
        "status": "completed",
        "vendor": "tushare",
        "production_duckdb_written": False,
        "request": {
            "endpoint": "suspend_d",
            "ts_code": "002870.SZ",
            "start_date": "2026-09-01",
            "end_date": "2026-09-15",
        },
        "records": suspension_records,
    }
    factors = [
        {"ts_code": stock_code, "trade_date": trade_date, "adj_factor": 1.0 + index / 10}
        for index, stock_code in enumerate(BJ_CODES)
        for trade_date in FACTOR_DATES
    ]
    code_results = [
        {
            "stock_code": stock_code,
            "required_rows": [row for row in factors if row["ts_code"] == stock_code],
        }
        for stock_code in BJ_CODES
    ]
    factor_payload = {
        "schema": "tushare_bj_adjustment_factor_staging/v1",
        "status": "completed",
        "vendor": "tushare",
        "production_duckdb_written": False,
        "required_dates": list(FACTOR_DATES),
        "code_results": code_results,
        "required_row_count": len(factors),
        "required_rows_sha256": repair_module._canonical_sha256(factors),
    }
    return (
        _write_receipt(tmp_path / "bars.json", bars),
        _write_receipt(tmp_path / "suspension.json", suspension),
        _write_receipt(tmp_path / "factors.json", factor_payload),
    )


def _insert_observation(conn: duckdb.DuckDBPyConnection, values: tuple[object, ...]) -> None:
    conn.execute(
        f"insert into choice_stock_daily_observation ({', '.join(OBS_COLUMNS)}) "
        f"values ({', '.join('?' for _ in OBS_COLUMNS)})",
        list(values),
    )


def _build_database(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar, stock_code varchar,
              open_value double, high_value double, low_value double, close_value double,
              volume double, amount double, pctchange double, turn double, amplitude double,
              tradestatus varchar, highlimit double, lowlimit double,
              field_keys_json varchar, source_version varchar, vendor_version varchar,
              rule_version varchar, run_id varchar
            )
            """
        )
        ensure_stock_adjustment_factor_schema(conn)
        ensure_livermore_candidate_history_schema(conn)
        conn.execute(
            "create table choice_stock_request_audit (audit_key varchar, status varchar)"
        )
        conn.execute("insert into choice_stock_request_audit values ('keep', 'completed')")
        for index, trade_date in enumerate(SUSPENDED_DATES):
            _insert_observation(
                conn,
                (
                    trade_date,
                    "002870.SZ",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    55.0,
                    45.0,
                    '["daily_limit_flags"]',
                    f"sv_original_{index}",
                    f"vv_choice_tushare_stock_202609{index + 1:02d}_{index:012x}",
                    "rv_original",
                    f"run:original:{index}",
                ),
            )
        for trade_date in SZ_VALID_DATES:
            _insert_observation(
                conn,
                (
                    trade_date,
                    "002870.SZ",
                    50.0,
                    51.0,
                    49.0,
                    50.0,
                    1000.0,
                    5000.0,
                    0.0,
                    1.0,
                    4.0,
                    "Trading",
                    55.0,
                    45.0,
                    '["daily_ohlcv_amount","daily_trade_status"]',
                    "sv_existing",
                    "vv_choice_tushare_stock_20260916_aaaaaaaaaaaa",
                    "rv_existing",
                    "run:existing",
                ),
            )
        for trade_date in MARKET_DATES_AFTER_AUG18:
            _insert_observation(
                conn,
                (
                    trade_date,
                    "000001.SZ",
                    10.0,
                    10.1,
                    9.9,
                    10.0,
                    1000.0,
                    1000.0,
                    0.0,
                    1.0,
                    2.0,
                    "Trading",
                    11.0,
                    9.0,
                    '["daily_ohlcv_amount","daily_trade_status"]',
                    "sv_unrelated",
                    "vv_choice_tushare_stock_20260916_bbbbbbbbbbbb",
                    "rv_unrelated",
                    "run:unrelated",
                ),
            )
        _insert_observation(
            conn,
            (
                "2026-07-22",
                "000001.SZ",
                10.0,
                10.1,
                9.9,
                10.0,
                1000.0,
                1000.0,
                0.0,
                1.0,
                2.0,
                "Trading",
                11.0,
                9.0,
                '["daily_ohlcv_amount","daily_trade_status"]',
                "sv_unrelated",
                "vv_choice_tushare_stock_20260916_bbbbbbbbbbbb",
                "rv_unrelated",
                "run:unrelated",
            ),
        )
        candidate_rows = [
            ("2026-07-21", stock_code, 10.0 + index, None, None, None, None, None, None, None, None)
            for index, stock_code in enumerate(BJ_CODES)
        ] + [
            (
                "2026-08-18",
                "002870.SZ",
                48.77,
                "2026-08-19",
                "2026-08-25",
                "2026-09-15",
                None,
                -0.01,
                -0.02,
                -0.03,
                None,
            )
        ] + [
            (
                "2026-06-01",
                "300001.SZ",
                20.0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        ]
        for index, row in enumerate(candidate_rows):
            conn.execute(
                """
                insert into livermore_candidate_history (
                  snapshot_as_of_date, stock_code, selection_close,
                  forward_trade_date_1d, forward_trade_date_5d,
                  forward_trade_date_10d, forward_trade_date_20d,
                  return_1d, return_5d, return_10d, return_20d,
                  return_1d_adj, return_5d_adj, return_10d_adj, return_20d_adj,
                  ex_div_in_window, data_status, formula_version,
                  source_version, vendor_version, rule_version, run_id,
                  signal_kind, signal_evidence_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    *row,
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    None,
                    "pending",
                    "fv_original",
                    "sv_candidate",
                    "vv_candidate",
                    "rv_candidate",
                    f"candidate:{index}",
                    "stock_candidate",
                    json.dumps({"selection": {"rank": index + 1}}),
                ],
            )
        factors = [
            (stock_code, trade_date, 1.0 + index / 10, "sv_existing_factor", "run:factor")
            for index, stock_code in enumerate(BJ_CODES)
            for trade_date in ("2026-07-21", "2026-08-18")
        ]
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
            factors,
        )
        conn.execute(
            "insert into stock_adjustment_factor values "
            "('300001.SZ', '2026-01-01', 2.0, 'sv_unrelated_factor', 'run:unrelated_factor')"
        )
    finally:
        conn.close()


def _run_dry_run(tmp_path: Path, db_path: Path) -> tuple[dict[str, object], tuple[Path, Path, Path]]:
    receipts = _staging_receipts(tmp_path)
    result = repair_choice_stock_matured_missing_bars(
        db_path,
        bars_receipt_path=receipts[0],
        suspension_receipt_path=receipts[1],
        factor_receipt_path=receipts[2],
        receipt_path=tmp_path / "dry-run-receipt.json",
    )
    return result, receipts


def test_repair_applies_exact_scope_and_preserves_original_suspension_lineage(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "moss.duckdb"
    _build_database(db_path)
    dry_run, receipts = _run_dry_run(tmp_path, db_path)
    assert dry_run["status"] == "dry_run"
    assert dry_run["write_scope"] == {
        "bj_insert_count": 120,
        "suspension_update_count": 10,
        "factor_insert_count": 18,
        "factor_existing_same_count": 12,
        "choice_stock_request_audit": "no_write",
    }
    backup_path = tmp_path / "moss-before.duckdb"
    shutil.copy2(db_path, backup_path)

    result = repair_choice_stock_matured_missing_bars(
        db_path,
        bars_receipt_path=receipts[0],
        suspension_receipt_path=receipts[1],
        factor_receipt_path=receipts[2],
        receipt_path=tmp_path / "apply-receipt.json",
        apply_changes=True,
        expected_plan_sha256=str(dry_run["plan_sha256"]),
        target_backup_path=backup_path,
    )

    assert result["status"] == "completed"
    assert result["bj_inserted_count"] == 120
    assert result["suspension_updated_count"] == 10
    assert result["factor_inserted_count"] == 18
    assert result["dq"]["status"] == "passed"
    assert result["candidate_outcome_refresh"]["candidate_row_count"] == 7
    assert result["candidate_outcome_refresh"]["selection_evidence_before_sha256"] == result[
        "candidate_outcome_refresh"
    ]["selection_evidence_after_sha256"]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        suspension_rows = conn.execute(
            """
            select trade_date, open_value, close_value, volume, amount, tradestatus,
                   source_version, vendor_version, rule_version, run_id
            from choice_stock_daily_observation
            where stock_code = '002870.SZ'
              and trade_date between '2026-09-01' and '2026-09-14'
            order by trade_date
            """
        ).fetchall()
        assert len(suspension_rows) == 10
        assert all(row[1:5] == (None, None, None, None) for row in suspension_rows)
        assert all(row[5] == "Suspended" for row in suspension_rows)
        assert [row[6:] for row in suspension_rows] == [
            (
                f"sv_original_{index}",
                f"vv_choice_tushare_stock_202609{index + 1:02d}_{index:012x}",
                "rv_original",
                f"run:original:{index}",
            )
            for index in range(10)
        ]
        assert conn.execute("select * from choice_stock_request_audit").fetchall() == [
            ("keep", "completed")
        ]
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where run_id = ?",
            [result["run_id"]],
        ).fetchone()[0] == 120
        assert conn.execute("select count(*) from stock_adjustment_factor").fetchone()[0] == 31
        assert conn.execute(
            "select * from stock_adjustment_factor where stock_code = '300001.SZ'"
        ).fetchall() == [
            ("300001.SZ", "2026-01-01", 2.0, "sv_unrelated_factor", "run:unrelated_factor")
        ]
        assert conn.execute(
            "select data_status, signal_evidence_json from livermore_candidate_history "
            "where stock_code = '300001.SZ'"
        ).fetchall() == [("pending", '{"selection": {"rank": 8}}')]
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where stock_code = '000001.SZ'"
        ).fetchone()[0] == len(MARKET_DATES_AFTER_AUG18) + 1
    finally:
        conn.close()


def test_repair_conflict_fails_before_any_write(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    _build_database(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _insert_observation(
            conn,
            (
                BJ_DATES[0],
                BJ_CODES[0],
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                0.0,
                1.0,
                0.0,
                "Trading",
                1.1,
                0.9,
                "[]",
                "sv_conflict",
                "vv_choice_tushare_stock_20260818_cccccccccccc",
                "rv_conflict",
                "run:conflict",
            ),
        )
    finally:
        conn.close()
    receipts = _staging_receipts(tmp_path)

    with pytest.raises(RuntimeError, match="already exist"):
        repair_choice_stock_matured_missing_bars(
            db_path,
            bars_receipt_path=receipts[0],
            suspension_receipt_path=receipts[1],
            factor_receipt_path=receipts[2],
            receipt_path=tmp_path / "dry-run.json",
        )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where stock_code like '920%'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where tradestatus = 'Suspended'"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_repair_dq_failure_rolls_back_all_three_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "moss.duckdb"
    _build_database(db_path)
    dry_run, receipts = _run_dry_run(tmp_path, db_path)
    backup_path = tmp_path / "moss-before.duckdb"
    shutil.copy2(db_path, backup_path)
    monkeypatch.setattr(
        repair_module,
        "run_choice_stock_daily_observation_dq_checks",
        lambda *_args, **_kwargs: {"status": "warning", "issues": ["forced"]},
    )

    with pytest.raises(RuntimeError, match="DQ failed"):
        repair_choice_stock_matured_missing_bars(
            db_path,
            bars_receipt_path=receipts[0],
            suspension_receipt_path=receipts[1],
            factor_receipt_path=receipts[2],
            receipt_path=tmp_path / "apply.json",
            apply_changes=True,
            expected_plan_sha256=str(dry_run["plan_sha256"]),
            target_backup_path=backup_path,
        )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where stock_code like '920%'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where tradestatus = 'Suspended'"
        ).fetchone()[0] == 0
        assert conn.execute("select count(*) from stock_adjustment_factor").fetchone()[0] == 13
        assert conn.execute(
            "select count(*) from livermore_candidate_history where data_status <> 'pending'"
        ).fetchone()[0] == 0
        assert conn.execute("select * from choice_stock_request_audit").fetchall() == [
            ("keep", "completed")
        ]
    finally:
        conn.close()
    failure_receipt = json.loads((tmp_path / "apply.json").read_text(encoding="utf-8"))
    assert failure_receipt["status"] == "failed"
    assert failure_receipt["duckdb_written"] is False
    assert failure_receipt["no_changes_committed"] is True
