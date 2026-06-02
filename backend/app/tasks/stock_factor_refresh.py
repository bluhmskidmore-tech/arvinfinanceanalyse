from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import duckdb

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.choice_stock_materialize import (
    _choice_client_default_options,
    _choice_stock_factor_css_options,
    _extract_result_rows,
    _float_or_none,
    _normalize_date,
    _percent_points_to_ratio,
    _positive_float_or_none,
    _text,
    ensure_choice_stock_schema,
)

logger = logging.getLogger(__name__)

SOURCE_VERSION = "factor_refresh_v1"
RULE_VERSION = "rv_stock_factor_refresh_v1"
FACTOR_FIELDS: tuple[str, ...] = ("pe", "pb", "ps", "roe", "gross_margin", "dividend_yield")

CHOICE_CSS_FACTOR_INDICATORS = (
    os.environ.get(
        "MOSS_CHOICE_CSS_FACTOR_INDICATORS",
        "PETTM,PBMRT,PSTTM,ROEWA,GPMARGIN,DIVYIELD",
    ).strip()
    or "PETTM,PBMRT,PSTTM,ROEWA,GPMARGIN,DIVYIELD"
)
CHOICE_CSS_FACTOR_CHUNK_SIZE = max(
    40,
    min(400, int(os.environ.get("MOSS_CHOICE_CSS_FACTOR_CHUNK", "280"))),
)
CHOICE_CSS_FACTOR_MAX_FAILED_CHUNKS = max(
    0,
    int(os.environ.get("MOSS_CHOICE_CSS_FACTOR_MAX_FAILED_CHUNKS", "0")),
)

_INDICATOR_FIELD_MAP: dict[str, str] = {
    "PETTM": "pe",
    "PE": "pe",
    "PETTMRATIO": "pe",
    "PBMRT": "pb",
    "PB": "pb",
    "PBMR": "pb",
    "PSTTM": "ps",
    "PS": "ps",
    "ROEWA": "roe",
    "ROE": "roe",
    "GPMARGIN": "gross_margin",
    "GROSSPROFITMARGIN": "gross_margin",
    "DIVYIELD": "dividend_yield",
    "DIVYIELDTTM": "dividend_yield",
    "DIVRATIO": "dividend_yield",
    "DIVRATIOTTM": "dividend_yield",
}


def refresh_stock_factors(
    *,
    duckdb_path: str,
    as_of_date: str | None = None,
    stock_codes: list[str] | None = None,
    dry_run: bool = False,
    choice_client: object | None = None,
) -> dict[str, Any]:
    """Pull latest fundamental factors from Choice css and upsert choice_stock_factor_snapshot."""
    settings = get_settings()
    resolved_duckdb_path = str(duckdb_path or settings.duckdb_path)
    resolved_date = _normalize_date(as_of_date or date.today().isoformat())
    indicator_tokens = _indicator_tokens()
    fields = list(FACTOR_FIELDS)

    duckdb_file = Path(resolved_duckdb_path)
    if not duckdb_file.exists():
        raise RuntimeError(f"DuckDB file does not exist: {duckdb_file}")

    conn = duckdb.connect(str(duckdb_file), read_only=dry_run)
    try:
        if dry_run:
            _assert_universe_table(conn)
        else:
            ensure_choice_stock_schema(conn)
            _ensure_factor_columns(conn)
        resolved_codes = stock_codes or _load_universe_stock_codes(conn, resolved_date)
        if not resolved_codes:
            raise RuntimeError(
                f"No stock codes found in choice_stock_universe for as_of_date={resolved_date}."
            )

        if dry_run:
            return {
                "status": "dry_run",
                "dry_run": True,
                "as_of_date": resolved_date,
                "stock_code_count": len(resolved_codes),
                "fields": fields,
                "choice_indicators": indicator_tokens,
                "source_version": SOURCE_VERSION,
                "table": "choice_stock_factor_snapshot",
            }

        client = choice_client or ChoiceClient()
        rows, failed_chunk_count, total_chunk_count = _fetch_choice_factor_rows(
            client,
            as_of_date=resolved_date,
            stock_codes=resolved_codes,
            indicator_tokens=indicator_tokens,
        )
        if failed_chunk_count > CHOICE_CSS_FACTOR_MAX_FAILED_CHUNKS:
            raise RuntimeError(
                "Choice css factor refresh aborted: "
                f"{failed_chunk_count}/{total_chunk_count} chunks failed "
                f"(max allowed {CHOICE_CSS_FACTOR_MAX_FAILED_CHUNKS})."
            )
        if not rows:
            raise RuntimeError(
                f"Choice css returned no factor rows for {resolved_date}; "
                f"check indicator entitlement ({','.join(indicator_tokens)})."
            )

        partial = failed_chunk_count > 0
        run_id = f"stock_factor_refresh:{resolved_date}:{uuid.uuid4().hex[:12]}"
        vendor_version = f"vv_choice_factor_refresh_{resolved_date.replace('-', '')}"
        started_at = datetime.now(UTC).isoformat()

        conn.execute("begin transaction")
        _upsert_factor_snapshot_rows(
            conn,
            rows=rows,
            run_id=run_id,
            source_version=SOURCE_VERSION,
            vendor_version=vendor_version,
        )
        conn.execute("commit")
        completed_at = datetime.now(UTC).isoformat()
    except Exception:
        if not dry_run:
            _rollback_quietly(conn)
        raise
    finally:
        conn.close()

    return {
        "status": "completed",
        "dry_run": False,
        "partial": partial,
        "run_id": run_id,
        "as_of_date": resolved_date,
        "stock_code_count": len(resolved_codes),
        "row_count": len(rows),
        "failed_chunk_count": failed_chunk_count,
        "total_chunk_count": total_chunk_count,
        "fields": fields,
        "choice_indicators": indicator_tokens,
        "source_version": SOURCE_VERSION,
        "vendor_version": vendor_version,
        "table": "choice_stock_factor_snapshot",
        "started_at": started_at,
        "completed_at": completed_at,
    }


def _load_universe_stock_codes(conn: duckdb.DuckDBPyConnection, as_of_date: str) -> list[str]:
    row = conn.execute(
        """
        select max(as_of_date)
        from choice_stock_universe
        where cast(as_of_date as date) <= cast(? as date)
        """,
        [as_of_date],
    ).fetchone()
    universe_date = _text(row[0]) if row is not None else ""
    if not universe_date:
        return []

    rows = conn.execute(
        """
        select distinct stock_code
        from choice_stock_universe
        where as_of_date = ?
        order by stock_code
        """,
        [universe_date],
    ).fetchall()
    return [_text(item[0]) for item in rows if _text(item[0])]


def _assert_universe_table(conn: duckdb.DuckDBPyConnection) -> None:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if "choice_stock_universe" not in tables:
        raise RuntimeError("choice_stock_universe is missing; run choice stock materialization first.")


def _indicator_tokens() -> list[str]:
    return [token.strip().upper() for token in CHOICE_CSS_FACTOR_INDICATORS.split(",") if token.strip()]


def _ensure_factor_columns(conn: duckdb.DuckDBPyConnection) -> None:
    existing = {str(row[0]).lower() for row in conn.execute("describe choice_stock_factor_snapshot").fetchall()}
    required_types: dict[str, str] = {
        "as_of_date": "varchar",
        "stock_code": "varchar",
        "pe": "double",
        "pb": "double",
        "ps": "double",
        "roe": "double",
        "gross_margin": "double",
        "dividend_yield": "double",
        "source_version": "varchar",
        "vendor_version": "varchar",
        "rule_version": "varchar",
        "run_id": "varchar",
    }
    for column, column_type in required_types.items():
        if column not in existing:
            conn.execute(f"alter table choice_stock_factor_snapshot add column {column} {column_type}")


def _fetch_choice_factor_rows(
    client: object,
    *,
    as_of_date: str,
    stock_codes: list[str],
    indicator_tokens: list[str],
) -> tuple[list[dict[str, object]], int, int]:
    if not stock_codes or not indicator_tokens:
        return [], 0, 0

    indicators_raw = ",".join(indicator_tokens)
    options = _choice_stock_factor_css_options(
        as_of_date,
        base_options=_choice_client_default_options(client),
    )
    merged: dict[str, dict[str, float | None]] = {
        code: {field: None for field in FACTOR_FIELDS} for code in stock_codes
    }
    chunks = _stock_code_chunks(
        sorted({str(code) for code in stock_codes if str(code)}),
        CHOICE_CSS_FACTOR_CHUNK_SIZE,
    )
    failed_chunk_count = 0

    for chunk in chunks:
        try:
            result = client.css(",".join(chunk), indicators_raw, options=options)
        except Exception:
            logger.exception("Choice css factor chunk raised (%s codes)", len(chunk))
            failed_chunk_count += 1
            continue
        if int(getattr(result, "ErrorCode", 0)) != 0:
            logger.warning(
                "Choice css factor chunk skipped: error=%s %s",
                getattr(result, "ErrorCode", "?"),
                getattr(result, "ErrorMsg", ""),
            )
            failed_chunk_count += 1
            continue

        parsed = _extract_result_rows(result, default_date=as_of_date)
        for row in parsed:
            stock_code = _resolve_stock_code(row)
            if not stock_code or stock_code not in merged:
                continue
            upper = {str(key).upper(): value for key, value in row.items()}
            bucket = merged[stock_code]
            for token in indicator_tokens:
                if token not in upper:
                    continue
                field_name = _INDICATOR_FIELD_MAP.get(token)
                if field_name is None:
                    continue
                bucket[field_name] = _normalize_factor_value(field_name, upper[token])

    rows = [
        {
            "as_of_date": as_of_date,
            "stock_code": stock_code,
            **values,
        }
        for stock_code, values in sorted(merged.items())
        if any(values.get(field) is not None for field in FACTOR_FIELDS)
    ]
    return rows, failed_chunk_count, len(chunks)


def _resolve_stock_code(row: dict[str, object]) -> str:
    return _text(
        row.get("stock_code")
        or row.get("CODE")
        or row.get("SECUCODE")
        or row.get("SECURITYCODE")
        or row.get("STOCK_CODE")
    )


def _normalize_factor_value(field_name: str, value: object) -> float | None:
    if field_name in {"pe", "pb", "ps"}:
        return _positive_float_or_none(value)
    if field_name in {"roe", "gross_margin", "dividend_yield"}:
        return _percent_points_to_ratio(value)
    return _float_or_none(value)


def _stock_code_chunks(stock_codes: list[str], chunk_size: int) -> list[list[str]]:
    normalized_chunk_size = max(1, chunk_size)
    return [
        stock_codes[index : index + normalized_chunk_size]
        for index in range(0, len(stock_codes), normalized_chunk_size)
    ]


def _upsert_factor_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[dict[str, object]],
    run_id: str,
    source_version: str,
    vendor_version: str,
) -> None:
    if not rows:
        return

    as_of_date = str(rows[0]["as_of_date"])
    conn.execute(
        "delete from choice_stock_factor_snapshot where as_of_date = ?",
        [as_of_date],
    )
    conn.executemany(
        """
        insert into choice_stock_factor_snapshot (
          as_of_date,
          stock_code,
          pe,
          pb,
          ps,
          roe,
          gross_margin,
          three_month_return,
          twelve_month_return,
          volatility,
          dividend_yield,
          industry,
          source_version,
          vendor_version,
          rule_version,
          run_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["as_of_date"],
                row["stock_code"],
                row.get("pe"),
                row.get("pb"),
                row.get("ps"),
                row.get("roe"),
                row.get("gross_margin"),
                None,
                None,
                None,
                row.get("dividend_yield"),
                None,
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            )
            for row in rows
        ],
    )


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        return


def _emit_json_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh choice_stock_factor_snapshot from Choice css fundamentals.",
    )
    parser.add_argument("--duckdb-path")
    parser.add_argument("--as-of-date", help="Snapshot date (default: today).")
    parser.add_argument(
        "--stock-codes",
        help="Comma-separated stock codes; default is full choice_stock_universe.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    stock_codes = (
        [code.strip() for code in str(args.stock_codes).split(",") if code.strip()]
        if args.stock_codes
        else None
    )
    payload = refresh_stock_factors(
        duckdb_path=str(args.duckdb_path or settings.duckdb_path),
        as_of_date=args.as_of_date,
        stock_codes=stock_codes,
        dry_run=bool(args.dry_run),
    )
    _emit_json_payload(payload)


def _refresh_stock_factors_task(**kwargs: object) -> dict[str, Any]:
    return refresh_stock_factors(**kwargs)  # type: ignore[arg-type]


refresh_stock_factors_task = register_actor_once(
    "refresh_stock_factors",
    _refresh_stock_factors_task,
)


if __name__ == "__main__":
    main()
