"""Narrow repair for the two matured stock-outcome gaps identified on 2026-09-17."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NotRequired, SupportsFloat, SupportsIndex, TypedDict, cast

import duckdb
from backend.app.core_finance.adjusted_returns import STOCK_ADJUSTMENT_FACTOR_TABLE
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks.choice_stock_materialize import (
    assert_known_choice_stock_daily_vendor_version,
    run_choice_stock_daily_observation_dq_checks,
)
from backend.app.tasks.livermore_candidate_outcome_maturity import (
    OUTCOME_CONTRACT_VERSION,
    OUTCOME_FORMULA_VERSION,
    _candidate_outcome_updates,
    _empty_observation_window,
    _horizon_summary,
    _load_adjustment_factors,
    _load_candidate_observation_windows,
    _load_candidates,
    _required_factor_keys,
    _update_candidate_outcomes,
)


class _SourceEvidence(TypedDict):
    inputs: dict[str, dict[str, object]]
    bj_rows: list[dict[str, object]]
    bj_rows_sha256: str
    suspension_records: list[dict[str, object]]
    suspension_records_sha256: str
    factor_rows: list[dict[str, object]]
    factor_rows_sha256: str


class _RepairPlan(TypedDict):
    schema: str
    input_payload_sha256: dict[str, str]
    bj_insert_rows: list[dict[str, object]]
    suspension_updates: list[dict[str, str]]
    suspension_before_rows: list[dict[str, object]]
    factor_insert_rows: list[dict[str, object]]
    factor_existing_same_count: int
    candidate_before_rows: list[dict[str, Any]]
    plan_sha256: NotRequired[str]


OBSERVATION_TABLE = "choice_stock_daily_observation"
REPAIR_SCHEMA = "choice_stock_matured_bar_repair/v1"
REPAIR_RULE_VERSION = "rv_choice_stock_matured_bar_repair_v1"
BJ_CODES = (
    "920207.BJ",
    "920260.BJ",
    "920493.BJ",
    "920717.BJ",
    "920765.BJ",
    "920856.BJ",
)
BJ_START_DATE = "2026-07-22"
BJ_END_DATE = "2026-08-18"
SUSPENDED_CODE = "002870.SZ"
SUSPENDED_DATES = (
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
)
FACTOR_DATES = (
    "2026-07-21",
    "2026-07-22",
    "2026-07-28",
    "2026-08-04",
    "2026-08-18",
)
EVALUATION_AS_OF_DATE = "2026-09-16"
REPAIR_CANDIDATE_KEYS = (
    *(("2026-07-21", code) for code in BJ_CODES),
    ("2026-08-18", SUSPENDED_CODE),
)
OBSERVATION_COLUMNS = (
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
EMPTY_PRICE_COLUMNS = (
    "open_value",
    "high_value",
    "low_value",
    "close_value",
    "volume",
    "amount",
    "pctchange",
    "turn",
    "amplitude",
)


def repair_choice_stock_matured_missing_bars(
    duckdb_path: str | Path,
    *,
    bars_receipt_path: str | Path,
    suspension_receipt_path: str | Path,
    factor_receipt_path: str | Path,
    receipt_path: str | Path,
    apply_changes: bool = False,
    expected_plan_sha256: str | None = None,
    target_backup_path: str | Path | None = None,
) -> dict[str, object]:
    """Preview or apply the exact 120-bar, 10-status, and factor-cell repair."""

    started_at = datetime.now(UTC)
    write_committed = False
    target_path = Path(duckdb_path).resolve(strict=True)
    resolved_receipt_path = Path(receipt_path).resolve()
    try:
        source_evidence = _load_source_evidence(
            bars_receipt_path=bars_receipt_path,
            suspension_receipt_path=suspension_receipt_path,
            factor_receipt_path=factor_receipt_path,
        )
        if not apply_changes:
            with duckdb.connect(str(target_path), read_only=True) as conn:
                plan = _build_plan(conn, source_evidence=source_evidence)
            result = _build_result(
                status="dry_run",
                target_path=target_path,
                plan=plan,
                source_evidence=source_evidence,
            )
            result.update(_timing_fields(started_at))
            _write_json_atomic(resolved_receipt_path, result)
            return result

        expected_plan = _normalize_sha256(
            expected_plan_sha256,
            field_name="expected_plan_sha256",
        )
        backup_evidence = _verify_byte_identical_backup(
            target_path,
            target_backup_path=target_backup_path,
        )
        writer_lock = resolve_duckdb_writer_lock(target_path, ttl_seconds=900)
        with acquire_lock(writer_lock, base_dir=target_path.parent, timeout_seconds=30):
            _verify_target_unchanged(
                target_path,
                expected_sha256=str(backup_evidence["backup_sha256"]),
            )
            with duckdb.connect(str(target_path), read_only=False) as conn:
                plan = _build_plan(conn, source_evidence=source_evidence)
                if plan["plan_sha256"] != expected_plan:
                    raise RuntimeError(
                        "repair plan changed after dry-run; rerun dry-run and review the new plan_sha256"
                    )
                write_metadata = _apply_plan(conn, plan=plan)
                write_committed = True

        result = _build_result(
            status="completed",
            target_path=target_path,
            plan=plan,
            source_evidence=source_evidence,
        )
        result.update(backup_evidence)
        result.update(write_metadata)
        result.update(_timing_fields(started_at))
        _write_json_atomic(resolved_receipt_path, result)
        return result
    except Exception as exc:
        failure = {
            "schema": REPAIR_SCHEMA,
            "status": "failed",
            "duckdb_path": str(target_path),
            "duckdb_written": write_committed,
            "production_duckdb_written": (
                write_committed and _is_production_target(target_path)
            ),
            "no_changes_committed": not write_committed,
            "error_type": type(exc).__name__,
            "error": " ".join(str(exc).split())[:1000],
            **_timing_fields(started_at),
        }
        try:
            _write_json_atomic(resolved_receipt_path, failure)
        except OSError:
            pass
        raise


def _load_source_evidence(
    *,
    bars_receipt_path: str | Path,
    suspension_receipt_path: str | Path,
    factor_receipt_path: str | Path,
) -> _SourceEvidence:
    bars = _load_verified_receipt(
        bars_receipt_path,
        schema="tushare_missing_bars_staging/v1",
    )
    suspension = _load_verified_receipt(
        suspension_receipt_path,
        schema="tushare_suspension_staging/v1",
    )
    factors = _load_verified_receipt(
        factor_receipt_path,
        schema="tushare_bj_adjustment_factor_staging/v1",
    )
    bj_rows, bj_rows_sha256 = _validate_bj_rows(bars)
    suspension_records = _validate_suspension_records(suspension)
    factor_rows, factor_rows_sha256 = _validate_factor_rows(factors)
    return {
        "inputs": {
            "bars": _receipt_reference(bars_receipt_path, bars),
            "suspension": _receipt_reference(suspension_receipt_path, suspension),
            "factors": _receipt_reference(factor_receipt_path, factors),
        },
        "bj_rows": bj_rows,
        "bj_rows_sha256": bj_rows_sha256,
        "suspension_records": suspension_records,
        "suspension_records_sha256": _canonical_sha256(suspension_records),
        "factor_rows": factor_rows,
        "factor_rows_sha256": factor_rows_sha256,
    }


def _load_verified_receipt(path_value: str | Path, *, schema: str) -> dict[str, object]:
    path = Path(path_value).resolve(strict=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"receipt is not a JSON object: {path}")
    if payload.get("schema") != schema or payload.get("status") != "completed":
        raise ValueError(f"receipt is not a completed {schema}: {path}")
    if payload.get("vendor") != "tushare" or payload.get("production_duckdb_written") is not False:
        raise ValueError(f"receipt has an unexpected vendor or write state: {path}")
    claimed = _normalize_sha256(payload.get("payload_sha256"), field_name="payload_sha256")
    unsigned = dict(payload)
    unsigned.pop("payload_sha256", None)
    if _canonical_sha256(unsigned) != claimed:
        raise ValueError(f"receipt payload_sha256 mismatch: {path}")
    return payload


def _validate_bj_rows(payload: dict[str, object]) -> tuple[list[dict[str, object]], str]:
    scopes = payload.get("scopes")
    if not isinstance(scopes, list):
        raise ValueError("bars receipt scopes must be a list")
    matches = [item for item in scopes if isinstance(item, dict) and item.get("scope") == "bj_matured_missing_bars"]
    if len(matches) != 1:
        raise ValueError("bars receipt must contain exactly one BJ repair scope")
    scope = matches[0]
    if tuple(scope.get("codes") or ()) != BJ_CODES:
        raise ValueError("BJ repair codes do not match the approved scope")
    if scope.get("start_date") != BJ_START_DATE or scope.get("end_date") != BJ_END_DATE:
        raise ValueError("BJ repair date range does not match the approved scope")
    rows = scope.get("rows")
    if not isinstance(rows, list) or len(rows) != 120 or scope.get("row_count") != 120:
        raise ValueError("BJ repair scope must contain exactly 120 rows")
    claimed = _normalize_sha256(scope.get("rows_sha256"), field_name="rows_sha256")
    if _canonical_sha256(rows) != claimed:
        raise ValueError("BJ repair rows_sha256 mismatch")
    normalized: list[dict[str, object]] = []
    keys: set[tuple[str, str]] = set()
    rows_by_code: dict[str, int] = {code: 0 for code in BJ_CODES}
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ValueError(f"BJ row {index} is not an object")
        stock_code = str(raw.get("stock_code") or "").strip().upper()
        trade_date = str(raw.get("trade_date") or "").strip()
        if stock_code not in BJ_CODES or not (BJ_START_DATE <= trade_date <= BJ_END_DATE):
            raise ValueError(f"BJ row {index} is outside the approved scope")
        key = (stock_code, trade_date)
        if key in keys:
            raise ValueError(f"duplicate BJ row {stock_code}@{trade_date}")
        keys.add(key)
        rows_by_code[stock_code] += 1
        numeric = {
            name: _finite_float(raw.get(name), field_name=f"BJ row {index}.{name}")
            for name in (
                "open_value",
                "high_value",
                "low_value",
                "close_value",
                "volume",
                "amount",
                "pctchange",
                "turn",
                "amplitude",
                "highlimit",
                "lowlimit",
            )
        }
        if min(
            numeric["open_value"],
            numeric["high_value"],
            numeric["low_value"],
            numeric["close_value"],
            numeric["volume"],
            numeric["amount"],
        ) <= 0:
            raise ValueError(f"BJ row {index} has a nonpositive price, volume, or amount")
        if numeric["high_value"] < max(numeric["open_value"], numeric["low_value"], numeric["close_value"]):
            raise ValueError(f"BJ row {index} has an invalid OHLC high")
        if numeric["low_value"] > min(numeric["open_value"], numeric["high_value"], numeric["close_value"]):
            raise ValueError(f"BJ row {index} has an invalid OHLC low")
        field_keys = raw.get("field_keys")
        if not isinstance(field_keys, list) or sorted(str(item) for item in field_keys) != [
            "daily_limit_flags",
            "daily_ohlcv_amount",
            "daily_return_turnover_amplitude",
            "daily_trade_status",
        ]:
            raise ValueError(f"BJ row {index} has unexpected field keys")
        normalized.append(
            {
                "trade_date": trade_date,
                "stock_code": stock_code,
                **numeric,
                "tradestatus": "Trading",
                "field_keys_json": json.dumps(field_keys, ensure_ascii=False, separators=(",", ":")),
            }
        )
    if set(rows_by_code.values()) != {20}:
        raise ValueError(f"BJ repair rows must contain 20 rows per code: {rows_by_code}")
    return sorted(normalized, key=lambda row: (str(row["stock_code"]), str(row["trade_date"]))), claimed


def _validate_suspension_records(payload: dict[str, object]) -> list[dict[str, object]]:
    request = payload.get("request")
    if not isinstance(request, dict) or request.get("endpoint") != "suspend_d" or request.get("ts_code") != SUSPENDED_CODE:
        raise ValueError("suspension receipt request is outside the approved scope")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("suspension receipt records must be a list")
    selected: dict[str, dict[str, object]] = {}
    resumed_seen = False
    for index, raw in enumerate(records):
        if not isinstance(raw, dict) or str(raw.get("ts_code") or "").strip().upper() != SUSPENDED_CODE:
            raise ValueError(f"suspension record {index} has an unexpected stock code")
        raw_date = str(raw.get("trade_date") or "").strip()
        if len(raw_date) != 8 or not raw_date.isdigit():
            raise ValueError(f"suspension record {index} has an invalid date")
        trade_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        suspend_type = str(raw.get("suspend_type") or "").strip().upper()
        if trade_date in SUSPENDED_DATES and suspend_type == "S":
            selected[trade_date] = dict(raw)
        if trade_date == "2026-09-15" and suspend_type == "R":
            resumed_seen = True
    if set(selected) != set(SUSPENDED_DATES) or not resumed_seen:
        raise ValueError("suspension receipt does not prove the ten suspensions and 2026-09-15 resumption")
    return [selected[trade_date] for trade_date in SUSPENDED_DATES]


def _validate_factor_rows(payload: dict[str, object]) -> tuple[list[dict[str, object]], str]:
    if tuple(cast(Iterable[object], payload.get("required_dates") or ())) != FACTOR_DATES:
        raise ValueError("factor receipt dates do not match the approved scope")
    code_results = payload.get("code_results")
    if not isinstance(code_results, list) or len(code_results) != len(BJ_CODES):
        raise ValueError("factor receipt must contain all six BJ codes")
    rows: list[dict[str, object]] = []
    for result in code_results:
        if not isinstance(result, dict) or result.get("stock_code") not in BJ_CODES:
            raise ValueError("factor receipt contains an unexpected code result")
        required_rows = result.get("required_rows")
        if not isinstance(required_rows, list):
            raise ValueError("factor code result has no required rows")
        rows.extend(required_rows)
    claimed = _normalize_sha256(payload.get("required_rows_sha256"), field_name="required_rows_sha256")
    if payload.get("required_row_count") != 30 or len(rows) != 30 or _canonical_sha256(rows) != claimed:
        raise ValueError("factor receipt required-row identity mismatch")
    normalized: list[dict[str, object]] = []
    keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ValueError(f"factor row {index} is not an object")
        stock_code = str(raw.get("ts_code") or "").strip().upper()
        trade_date = str(raw.get("trade_date") or "").strip()
        factor = _finite_float(raw.get("adj_factor"), field_name=f"factor row {index}.adj_factor")
        key = (stock_code, trade_date)
        if stock_code not in BJ_CODES or trade_date not in FACTOR_DATES or factor <= 0 or key in keys:
            raise ValueError(f"factor row {index} is invalid or duplicated")
        keys.add(key)
        normalized.append({"stock_code": stock_code, "trade_date": trade_date, "adj_factor": factor})
    expected_keys = {(code, trade_date) for code in BJ_CODES for trade_date in FACTOR_DATES}
    if keys != expected_keys:
        raise ValueError("factor receipt does not cover the exact 30 required cells")
    return sorted(normalized, key=lambda row: (str(row["stock_code"]), str(row["trade_date"]))), claimed


def _build_plan(
    conn: duckdb.DuckDBPyConnection,
    *,
    source_evidence: _SourceEvidence,
) -> _RepairPlan:
    _assert_required_schema(conn)
    bj_rows = list(source_evidence["bj_rows"])
    existing_bj = _load_observation_rows(conn, stock_codes=BJ_CODES, start_date=BJ_START_DATE, end_date=BJ_END_DATE)
    bj_keys = {(str(row["stock_code"]), str(row["trade_date"])) for row in bj_rows}
    conflicts = [row for row in existing_bj if (str(row["stock_code"]), str(row["trade_date"])) in bj_keys]
    if conflicts:
        raise RuntimeError(f"approved BJ insert keys already exist: {len(conflicts)}")

    suspension_before = _load_observation_rows(
        conn,
        stock_codes=(SUSPENDED_CODE,),
        start_date=min(SUSPENDED_DATES),
        end_date=max(SUSPENDED_DATES),
    )
    by_date = {str(row["trade_date"]): row for row in suspension_before if str(row["trade_date"]) in SUSPENDED_DATES}
    if set(by_date) != set(SUSPENDED_DATES) or len(suspension_before) != 10:
        raise RuntimeError("002870 suspension repair requires exactly ten existing natural-key rows")
    for trade_date in SUSPENDED_DATES:
        row = by_date[trade_date]
        nonempty = [name for name in EMPTY_PRICE_COLUMNS if row.get(name) is not None]
        if nonempty:
            raise RuntimeError(f"002870@{trade_date} is not a limit-only row; nonempty={nonempty}")
        if str(row.get("tradestatus") or "").strip():
            raise RuntimeError(f"002870@{trade_date} already has a trade status")
        assert_known_choice_stock_daily_vendor_version(str(row.get("vendor_version") or ""))

    factor_rows = list(source_evidence["factor_rows"])
    existing_factors = _load_factor_rows(conn)
    factor_inserts: list[dict[str, object]] = []
    factor_existing_same = 0
    for row in factor_rows:
        key = (str(row["stock_code"]), str(row["trade_date"]))
        existing = existing_factors.get(key)
        if existing is None:
            factor_inserts.append(row)
        elif math.isclose(
            float(cast(float, existing["adj_factor"])), float(cast(float, row["adj_factor"])),
            rel_tol=0.0, abs_tol=1e-12,
        ):
            factor_existing_same += 1
        else:
            raise RuntimeError(
                f"conflicting existing adjustment factor for {key[0]}@{key[1]}"
            )

    candidate_before_rows = _load_scoped_candidates(conn)

    plan_body: _RepairPlan = {
        "schema": REPAIR_SCHEMA,
        "input_payload_sha256": {
            key: str(value["payload_sha256"])
            for key, value in dict(source_evidence["inputs"]).items()
        },
        "bj_insert_rows": bj_rows,
        "suspension_updates": [
            {"stock_code": SUSPENDED_CODE, "trade_date": trade_date, "tradestatus": "Suspended"}
            for trade_date in SUSPENDED_DATES
        ],
        "suspension_before_rows": [by_date[trade_date] for trade_date in SUSPENDED_DATES],
        "factor_insert_rows": factor_inserts,
        "factor_existing_same_count": factor_existing_same,
        "candidate_before_rows": candidate_before_rows,
    }
    plan_body["plan_sha256"] = _canonical_sha256(plan_body)
    return plan_body


def _apply_plan(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _RepairPlan,
) -> dict[str, object]:
    plan_sha256 = str(plan["plan_sha256"])
    bars_hash = _canonical_sha256(plan["bj_insert_rows"])
    factor_hash = _canonical_sha256(plan["factor_insert_rows"])
    source_version = f"sv_choice_stock_{bars_hash[:12]}"
    vendor_version = f"vv_choice_tushare_stock_{BJ_END_DATE.replace('-', '')}_{bars_hash[:12]}"
    assert_known_choice_stock_daily_vendor_version(vendor_version)
    run_id = f"choice_stock_matured_bar_repair:{plan_sha256[:12]}"
    factor_source_version = f"sv_stock_adjustment_factor_{factor_hash[:12]}"
    factor_run_id = f"stock_adjustment_factor_matured_bar_repair:{plan_sha256[:12]}"
    insert_columns = ", ".join(OBSERVATION_COLUMNS)
    placeholders = ", ".join("?" for _ in OBSERVATION_COLUMNS)
    with repository_task_write_scope(__name__):
        conn.execute("begin transaction")
        try:
            conn.executemany(
                f"insert into {OBSERVATION_TABLE} ({insert_columns}) values ({placeholders})",
                [
                    (
                        row["trade_date"],
                        row["stock_code"],
                        row["open_value"],
                        row["high_value"],
                        row["low_value"],
                        row["close_value"],
                        row["volume"],
                        row["amount"],
                        row["pctchange"],
                        row["turn"],
                        row["amplitude"],
                        row["tradestatus"],
                        row["highlimit"],
                        row["lowlimit"],
                        row["field_keys_json"],
                        source_version,
                        vendor_version,
                        REPAIR_RULE_VERSION,
                        run_id,
                    )
                    for row in plan["bj_insert_rows"]
                ],
            )
            for update in plan["suspension_updates"]:
                conn.execute(
                    f"""
                    update {OBSERVATION_TABLE}
                    set tradestatus = ?
                    where upper(trim(cast(stock_code as varchar))) = ?
                      and cast(trade_date as varchar) = ?
                      and trim(coalesce(cast(tradestatus as varchar), '')) = ''
                    """,
                    [update["tradestatus"], update["stock_code"], update["trade_date"]],
                )
            if plan["factor_insert_rows"]:
                conn.executemany(
                    f"""
                    insert into {STOCK_ADJUSTMENT_FACTOR_TABLE}
                    (stock_code, trade_date, adj_factor, source_version, run_id)
                    values (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row["stock_code"],
                            row["trade_date"],
                            row["adj_factor"],
                            factor_source_version,
                            factor_run_id,
                        )
                        for row in plan["factor_insert_rows"]
                    ],
                )
            maturity = _refresh_scoped_candidate_outcomes(conn, plan=plan)
            _assert_post_write_scope(conn, plan=plan, run_id=run_id)
            dq = run_choice_stock_daily_observation_dq_checks(
                conn,
                run_id=run_id,
                expected_vendor_version=vendor_version,
            )
            if dq.get("status") != "passed":
                raise RuntimeError(f"BJ repair DQ failed: {dq.get('issues')}")
            conn.execute("commit")
        except Exception:
            _rollback_quietly(conn)
            raise
    return {
        "bj_inserted_count": len(plan["bj_insert_rows"]),
        "suspension_updated_count": len(plan["suspension_updates"]),
        "factor_inserted_count": len(plan["factor_insert_rows"]),
        "factor_existing_same_count": plan["factor_existing_same_count"],
        "candidate_outcome_refresh": maturity,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "rule_version": REPAIR_RULE_VERSION,
        "run_id": run_id,
        "factor_source_version": factor_source_version,
        "factor_run_id": factor_run_id,
        "dq": dq,
        "choice_stock_request_audit_written": False,
    }


def _assert_post_write_scope(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _RepairPlan,
    run_id: str,
) -> None:
    inserted = conn.execute(
        f"select count(*) from {OBSERVATION_TABLE} where run_id = ?",
        [run_id],
    ).fetchone()
    if inserted is None or int(inserted[0]) != 120:
        raise RuntimeError("post-write BJ row count mismatch")
    status_rows = conn.execute(
        f"""
        select cast(trade_date as varchar), tradestatus
        from {OBSERVATION_TABLE}
        where upper(trim(cast(stock_code as varchar))) = ?
          and cast(trade_date as varchar) in ({", ".join("?" for _ in SUSPENDED_DATES)})
        order by trade_date
        """,
        [SUSPENDED_CODE, *SUSPENDED_DATES],
    ).fetchall()
    if status_rows != [(trade_date, "Suspended") for trade_date in SUSPENDED_DATES]:
        raise RuntimeError("post-write 002870 suspension status mismatch")
    factor_count = conn.execute(
        f"select count(*) from {STOCK_ADJUSTMENT_FACTOR_TABLE} where run_id = ?",
        [f"stock_adjustment_factor_matured_bar_repair:{plan['plan_sha256'][:12]}"],
    ).fetchone()
    if factor_count is None or int(factor_count[0]) != len(plan["factor_insert_rows"]):
        raise RuntimeError("post-write adjustment-factor row count mismatch")
    _assert_candidate_selection_evidence_preserved(conn, plan=plan)


def _assert_required_schema(conn: duckdb.DuckDBPyConnection) -> None:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    missing_tables = sorted(
        {OBSERVATION_TABLE, STOCK_ADJUSTMENT_FACTOR_TABLE, "livermore_candidate_history"}
        - tables
    )
    if missing_tables:
        raise RuntimeError(f"repair requires existing tables: {','.join(missing_tables)}")
    observation_columns = {str(row[1]) for row in conn.execute(f"pragma table_info('{OBSERVATION_TABLE}')").fetchall()}
    missing_columns = sorted(set(OBSERVATION_COLUMNS) - observation_columns)
    if missing_columns:
        raise RuntimeError(f"observation table missing columns: {','.join(missing_columns)}")


def _load_observation_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_codes: tuple[str, ...],
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    placeholders = ", ".join("?" for _ in stock_codes)
    cursor = conn.execute(
        f"""
        select {", ".join(OBSERVATION_COLUMNS)}
        from {OBSERVATION_TABLE}
        where upper(trim(cast(stock_code as varchar))) in ({placeholders})
          and cast(trade_date as varchar) between ? and ?
        order by stock_code, trade_date
        """,
        [*stock_codes, start_date, end_date],
    )
    return [dict(zip(OBSERVATION_COLUMNS, row, strict=True)) for row in cursor.fetchall()]


def _load_factor_rows(conn: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], dict[str, object]]:
    code_placeholders = ", ".join("?" for _ in BJ_CODES)
    date_placeholders = ", ".join("?" for _ in FACTOR_DATES)
    cursor = conn.execute(
        f"""
        select stock_code, cast(trade_date as varchar) as trade_date,
               adj_factor, source_version, run_id
        from {STOCK_ADJUSTMENT_FACTOR_TABLE}
        where upper(trim(cast(stock_code as varchar))) in ({code_placeholders})
          and cast(trade_date as varchar) in ({date_placeholders})
        order by stock_code, trade_date
        """,
        [*BJ_CODES, *FACTOR_DATES],
    )
    columns = ("stock_code", "trade_date", "adj_factor", "source_version", "run_id")
    result: dict[tuple[str, str], dict[str, object]] = {}
    for values in cursor.fetchall():
        row = dict(zip(columns, values, strict=True))
        key = (str(row["stock_code"]), str(row["trade_date"]))
        if key in result:
            raise RuntimeError(f"duplicate existing factor key {key[0]}@{key[1]}")
        result[key] = row
    return result


def _build_result(
    *,
    status: str,
    target_path: Path,
    plan: _RepairPlan,
    source_evidence: _SourceEvidence,
) -> dict[str, object]:
    return {
        "schema": REPAIR_SCHEMA,
        "status": status,
        "duckdb_path": str(target_path),
        "duckdb_written": status == "completed",
        "production_duckdb_written": (
            status == "completed" and _is_production_target(target_path)
        ),
        "plan_sha256": plan["plan_sha256"],
        "inputs": source_evidence["inputs"],
        "write_scope": {
            "bj_insert_count": len(plan["bj_insert_rows"]),
            "suspension_update_count": len(plan["suspension_updates"]),
            "factor_insert_count": len(plan["factor_insert_rows"]),
            "factor_existing_same_count": plan["factor_existing_same_count"],
            "choice_stock_request_audit": "no_write",
        },
        "suspension_before_rows_sha256": _canonical_sha256(plan["suspension_before_rows"]),
        "candidate_before_rows_sha256": _canonical_sha256(plan["candidate_before_rows"]),
        "suspension_source_records_sha256": source_evidence["suspension_records_sha256"],
        "suspension_changes": _suspension_change_evidence(
            before_rows=plan["suspension_before_rows"],
            source_records=source_evidence["suspension_records"],
        ),
        "approved_scope": {
            "bj_codes": list(BJ_CODES),
            "bj_date_range": [BJ_START_DATE, BJ_END_DATE],
            "suspended_code": SUSPENDED_CODE,
            "suspended_dates": list(SUSPENDED_DATES),
            "factor_dates": list(FACTOR_DATES),
            "candidate_keys": [list(key) for key in REPAIR_CANDIDATE_KEYS],
            "candidate_evaluation_as_of_date": EVALUATION_AS_OF_DATE,
        },
    }


def _load_scoped_candidates(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    approved = set(REPAIR_CANDIDATE_KEYS)
    candidates = [
        row
        for row in _load_candidates(conn, evaluation_as_of_date=EVALUATION_AS_OF_DATE)
        if (
            str(row.get("snapshot_as_of_date") or "")[:10],
            str(row.get("stock_code") or "").strip().upper(),
        )
        in approved
    ]
    actual = {
        (
            str(row.get("snapshot_as_of_date") or "")[:10],
            str(row.get("stock_code") or "").strip().upper(),
        )
        for row in candidates
    }
    if actual != approved or len(candidates) != len(approved):
        raise RuntimeError(
            "candidate outcome repair requires exactly one existing row for each approved key"
        )
    return sorted(
        candidates,
        key=lambda row: (
            str(row.get("snapshot_as_of_date") or ""),
            str(row.get("stock_code") or ""),
        ),
    )


def _refresh_scoped_candidate_outcomes(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _RepairPlan,
) -> dict[str, object]:
    candidates = _load_scoped_candidates(conn)
    if _canonical_sha256(candidates) != _canonical_sha256(plan["candidate_before_rows"]):
        raise RuntimeError("approved candidate rows changed after repair planning")
    observation_columns = {
        str(row[1])
        for row in conn.execute(f"pragma table_info('{OBSERVATION_TABLE}')").fetchall()
    }
    observation_windows, market_dates, loaded_observation_row_count = (
        _load_candidate_observation_windows(
            conn,
            candidates=candidates,
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            minimum_snapshot_date=min(
                str(row["snapshot_as_of_date"])[:10] for row in candidates
            ),
            observation_columns=observation_columns,
        )
    )
    required_factor_keys = _required_factor_keys(
        candidates,
        observation_windows=observation_windows,
    )
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    factors, loaded_factor_row_count = _load_adjustment_factors(
        conn,
        tables=tables,
        factor_keys=required_factor_keys,
    )
    maturity_run_id = (
        f"livermore_candidate_outcome_maturity_repair:{EVALUATION_AS_OF_DATE}:"
        f"{plan['plan_sha256'][:12]}"
    )
    horizon_items: dict[str, list[dict[str, Any]]] = {horizon: [] for horizon in ("1d", "5d", "10d", "20d")}
    updated_rowids: list[int] = []
    blocked_rows: list[dict[str, object]] = []
    issues: list[str] = []
    for candidate in candidates:
        updates, maturity, row_issues, blocked_issue, _arbitrations = (
            _candidate_outcome_updates(
                candidate,
                observation_window=observation_windows.get(
                    int(candidate["_rowid"]),
                    _empty_observation_window(),
                ),
                market_dates=market_dates,
                factors=factors,
                evaluation_as_of_date=EVALUATION_AS_OF_DATE,
                run_id=maturity_run_id,
                table_present=[
                    "livermore_candidate_history",
                    OBSERVATION_TABLE,
                    STOCK_ADJUSTMENT_FACTOR_TABLE,
                ],
                arbitrate_conflicts=False,
            )
        )
        issues.extend(row_issues)
        if blocked_issue:
            blocked_rows.append(
                {"rowid": int(candidate["_rowid"]), "issue": blocked_issue}
            )
        for horizon, item in maturity.items():
            horizon_items[horizon].append(item)
        if updates:
            _update_candidate_outcomes(
                conn,
                row_id=int(candidate["_rowid"]),
                updates=updates,
            )
            updated_rowids.append(int(candidate["_rowid"]))
    summary = _horizon_summary(horizon_items)
    unsafe_statuses = {
        status
        for horizon in summary.values()
        for status, count in dict(horizon["counts"]).items()
        if count and status in {"matured_missing_bar", "raw_matured_adjustment_missing"}
    }
    if blocked_rows or unsafe_statuses:
        raise RuntimeError(
            "scoped candidate outcome refresh remains blocked: "
            f"blocked_rows={blocked_rows}, statuses={sorted(unsafe_statuses)}"
        )
    return {
        "status": "completed",
        "evaluation_as_of_date": EVALUATION_AS_OF_DATE,
        "candidate_row_count": len(candidates),
        "updated_row_count": len(updated_rowids),
        "updated_rowids": updated_rowids,
        "loaded_observation_row_count": loaded_observation_row_count,
        "loaded_market_date_count": len(market_dates),
        "requested_factor_key_count": len(required_factor_keys),
        "loaded_factor_row_count": loaded_factor_row_count,
        "run_id": maturity_run_id,
        "formula_version": OUTCOME_FORMULA_VERSION,
        "contract_version": OUTCOME_CONTRACT_VERSION,
        "horizons": summary,
        "issues": sorted(set(issues)),
        "selection_evidence_before_sha256": _selection_evidence_scope_sha256(
            plan["candidate_before_rows"]
        ),
        "selection_evidence_after_sha256": _selection_evidence_scope_sha256(
            _load_scoped_candidates(conn)
        ),
    }


def _assert_candidate_selection_evidence_preserved(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _RepairPlan,
) -> None:
    before_rows = {
        int(row["_rowid"]): row
        for row in plan["candidate_before_rows"]
    }
    after_rows = {
        int(row["_rowid"]): row
        for row in _load_scoped_candidates(conn)
    }
    if set(before_rows) != set(after_rows):
        raise RuntimeError("candidate natural-key identity changed during outcome refresh")
    for rowid, before in before_rows.items():
        after = after_rows[rowid]
        before_evidence = _selection_evidence_without_maturity_audit(
            before.get("signal_evidence_json")
        )
        after_evidence = _selection_evidence_without_maturity_audit(
            after.get("signal_evidence_json")
        )
        if before_evidence != after_evidence:
            raise RuntimeError(
                f"candidate selection evidence changed during outcome refresh: rowid={rowid}"
            )


def _selection_evidence_without_maturity_audit(value: object) -> object:
    try:
        payload = json.loads(str(value or ""))
    except json.JSONDecodeError as exc:
        raise RuntimeError("candidate signal_evidence_json is invalid") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("candidate signal_evidence_json is not an object")
    payload.pop("outcome_maturity_audit", None)
    return payload


def _selection_evidence_scope_sha256(rows: object) -> str:
    if not isinstance(rows, list):
        raise RuntimeError("candidate rows must be a list")
    scope = [
        {
            "snapshot_as_of_date": str(row.get("snapshot_as_of_date") or "")[:10],
            "stock_code": str(row.get("stock_code") or "").strip().upper(),
            "selection_evidence": _selection_evidence_without_maturity_audit(
                row.get("signal_evidence_json")
            ),
        }
        for row in rows
    ]
    return _canonical_sha256(scope)


def _suspension_change_evidence(
    *,
    before_rows: object,
    source_records: object,
) -> list[dict[str, object]]:
    if not isinstance(before_rows, list) or not isinstance(source_records, list):
        raise RuntimeError("suspension evidence must be a list")
    rows_by_date = {str(row["trade_date"]): row for row in before_rows}
    records_by_date = {
        f"{str(record['trade_date'])[:4]}-{str(record['trade_date'])[4:6]}-{str(record['trade_date'])[6:]}": record
        for record in source_records
    }
    result: list[dict[str, object]] = []
    for trade_date in SUSPENDED_DATES:
        before = rows_by_date[trade_date]
        record = records_by_date[trade_date]
        result.append(
            {
                "stock_code": SUSPENDED_CODE,
                "trade_date": trade_date,
                "old_tradestatus": before.get("tradestatus"),
                "new_tradestatus": "Suspended",
                "suspend_d_source_record_sha256": _canonical_sha256(record),
                "original_lineage": {
                    field: before.get(field)
                    for field in (
                        "source_version",
                        "vendor_version",
                        "rule_version",
                        "run_id",
                    )
                },
                "original_field_keys_json": before.get("field_keys_json"),
                "price_fields_before": {
                    field: before.get(field) for field in EMPTY_PRICE_COLUMNS
                },
            }
        )
    return result


def _verify_byte_identical_backup(
    target_path: Path,
    *,
    target_backup_path: str | Path | None,
) -> dict[str, object]:
    if target_backup_path is None:
        raise ValueError("target_backup_path is required for apply")
    backup_path = Path(target_backup_path).resolve(strict=True)
    if target_path == backup_path or target_path.samefile(backup_path):
        raise ValueError("backup must be a different file from the target DuckDB")
    target_sha256 = _sha256_file(target_path)
    backup_sha256 = _sha256_file(backup_path)
    if target_sha256 != backup_sha256:
        raise ValueError("backup content hash does not match target DuckDB")
    return {
        "target_backup_path": str(backup_path),
        "backup_verified": True,
        "target_sha256_before": target_sha256,
        "backup_sha256": backup_sha256,
    }


def _verify_target_unchanged(target_path: Path, *, expected_sha256: str) -> None:
    if _sha256_file(target_path) != expected_sha256:
        raise RuntimeError("target DuckDB changed after backup verification")


def _is_production_target(target_path: Path) -> bool:
    return target_path == (Path.cwd() / "data" / "moss.duckdb").resolve()


def _timing_fields(started_at: datetime) -> dict[str, str]:
    return {
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }


def _receipt_reference(path_value: str | Path, payload: dict[str, object]) -> dict[str, object]:
    return {
        "path": str(Path(path_value).resolve()),
        "schema": payload["schema"],
        "payload_sha256": payload["payload_sha256"],
    }


def _finite_float(value: object, *, field_name: str) -> float:
    try:
        normalized = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


def _normalize_sha256(value: object, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return normalized


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        pass


__all__ = ["repair_choice_stock_matured_missing_bars"]
