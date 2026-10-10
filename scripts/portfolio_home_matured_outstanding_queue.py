from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)


DEFAULT_DUCKDB = ROOT / "data" / "moss.duckdb"
DEFAULT_REPORT_DATE = "2026-06-30"
DEFAULT_LIMIT = 100
BLOCKER = "bond_matured_outstanding_reconciliation_required"

EVIDENCE_SCOPE = {
    "read_only": True,
    "writes_database": False,
    "changes_reconciliation_status": False,
    "approves_metric_or_page": False,
    "certification_effect": "none",
}


def _validated_report_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid report date {value!r}; expected YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(
            f"invalid report date {value!r}; expected YYYY-MM-DD"
        )
    return value


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _row_to_dict(description: Any, row: tuple[Any, ...]) -> dict[str, object]:
    return {
        column[0]: _json_value(value)
        for column, value in zip(description, row, strict=True)
    }


def _table_columns(connection: duckdb.DuckDBPyConnection) -> set[str]:
    rows = connection.execute(
        """
        select lower(column_name)
        from information_schema.columns
        where table_schema = 'main'
          and lower(table_name) = 'fact_formal_bond_analytics_daily'
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def _select_expression(columns: set[str], column: str, cast_type: str = "varchar") -> str:
    if column in columns:
        return column
    return f"cast(null as {cast_type}) as {column}"


def build_queue(
    *,
    duckdb_path: Path,
    report_date: str,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, object]:
    report_date = _validated_report_date(report_date)
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="matured outstanding limit",
    )
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        columns = _table_columns(connection)
        required = {"report_date", "maturity_date", "market_value"}
        missing = sorted(required - columns)
        if missing:
            return {
                "page_id": "PAGE-PORTFOLIO-HOME-001",
                "page_slug": "portfolio",
                "report_date": report_date,
                "duckdb_path": str(duckdb_path),
                "sample_limit": limit,
                "evidence_scope": EVIDENCE_SCOPE,
                "source_status": "source_unavailable",
                "missing_columns": missing,
                "summary": {
                    "row_count": 0,
                    "net_market_value": "0",
                    "absolute_market_value": "0",
                    "dv01_sum": "0",
                    "earliest_maturity_date": None,
                    "latest_maturity_date": None,
                    "unparseable_maturity_date_rows": 0,
                    "unparseable_maturity_date_market_value": "0",
                },
                "rows": [],
                "reconciliation_status": "blocked",
                "reconciliation_blockers": ["bond_analytics_source_unavailable"],
            }

        dv01 = "coalesce(dv01, 0)" if "dv01" in columns else "cast(0 as decimal(24, 8))"
        summary_cursor = connection.execute(
            f"""
            with candidates as (
              select
                market_value,
                {dv01} as dv01,
                try_cast(maturity_date as date) as parsed_maturity_date,
                try_cast(? as date) as requested_report_date
              from fact_formal_bond_analytics_daily
              where cast(report_date as varchar) = ?
                and maturity_date is not null
                and coalesce(market_value, 0) <> 0
            )
            select
              count(*) filter (where parsed_maturity_date <= requested_report_date) as row_count,
              coalesce(sum(market_value) filter (where parsed_maturity_date <= requested_report_date), 0) as net_market_value,
              coalesce(sum(abs(market_value)) filter (where parsed_maturity_date <= requested_report_date), 0) as absolute_market_value,
              coalesce(sum(dv01) filter (where parsed_maturity_date <= requested_report_date), 0) as dv01_sum,
              min(parsed_maturity_date) filter (where parsed_maturity_date <= requested_report_date) as earliest_maturity_date,
              max(parsed_maturity_date) filter (where parsed_maturity_date <= requested_report_date) as latest_maturity_date,
              count(*) filter (where parsed_maturity_date is null) as unparseable_maturity_date_rows,
              coalesce(sum(market_value) filter (where parsed_maturity_date is null), 0) as unparseable_maturity_date_market_value
            from candidates
            """,
            [report_date, report_date],
        )
        summary = _row_to_dict(summary_cursor.description, summary_cursor.fetchone())

        row_cursor = connection.execute(
            f"""
            select
              {_select_expression(columns, 'instrument_code')},
              {_select_expression(columns, 'instrument_name')},
              {_select_expression(columns, 'portfolio_name')},
              {_select_expression(columns, 'cost_center')},
              cast(maturity_date as varchar) as maturity_date,
              try_cast(maturity_date as date) as parsed_maturity_date,
              case
                when try_cast(maturity_date as date) is null then 'unparseable'
                else 'matured'
              end as maturity_date_status,
              date_diff('day', try_cast(maturity_date as date), try_cast(? as date)) as days_past_maturity,
              market_value,
              {_select_expression(columns, 'modified_duration', 'decimal(18, 8)')},
              {dv01} as dv01,
              {_select_expression(columns, 'source_version')},
              {_select_expression(columns, 'trace_id')}
            from fact_formal_bond_analytics_daily
            where cast(report_date as varchar) = ?
              and maturity_date is not null
              and coalesce(market_value, 0) <> 0
              and (
                try_cast(maturity_date as date) <= try_cast(? as date)
                or try_cast(maturity_date as date) is null
              )
            order by abs(market_value) desc, instrument_code
            limit ?
            """,
            [report_date, report_date, report_date, limit],
        )
        rows = [
            _row_to_dict(row_cursor.description, row)
            for row in row_cursor.fetchall()
        ]
    finally:
        connection.close()

    blocked = (
        int(summary["row_count"] or 0) > 0
        or int(summary["unparseable_maturity_date_rows"] or 0) > 0
    )
    return {
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "sample_limit": limit,
        "queue_definition": (
            "report_date matches and market_value is non-zero; rows are queued when "
            "maturity_date is on or before report_date or is non-null and unparseable. "
            "NULL maturity_date remains the contractual no-maturity classification."
        ),
        "evidence_scope": EVIDENCE_SCOPE,
        "source_status": "available",
        "summary": summary,
        "rows": rows,
        "reconciliation_status": "blocked" if blocked else "clean",
        "reconciliation_blockers": [BLOCKER] if blocked else [],
        "next_action": (
            "Reconcile every queued non-zero row at source. Non-null unparseable "
            "maturity_date values must be corrected at source; no replacement maturity date "
            "or duration may be inferred."
            if blocked
            else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the portfolio-home matured, non-zero bond reconciliation queue.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument(
        "--report-date",
        type=_validated_report_date,
        default=DEFAULT_REPORT_DATE,
    )
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="matured outstanding limit",
        ),
        default=DEFAULT_LIMIT,
    )
    parser.add_argument(
        "--require-empty",
        action="store_true",
        help="Return non-zero unless the matured outstanding reconciliation queue is empty.",
    )
    args = parser.parse_args(argv)

    queue = build_queue(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        limit=int(args.limit),
    )
    print(json.dumps(queue, ensure_ascii=False, indent=2))
    if args.require_empty and queue["reconciliation_status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
