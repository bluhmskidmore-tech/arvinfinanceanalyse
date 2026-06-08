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
DEFAULT_REPORT_DATE = "2026-05-31"
DEFAULT_LIMIT = 25

MATURITY_CANDIDATE_SCOPE = {
    "read_only": True,
    "writes_database": False,
    "fills_maturity_date": False,
    "approves_metric_or_page": False,
    "changes_remediation_status": False,
    "certification_effect": "none",
}

MATURITY_REMEDIATION_ACTIONS: dict[str, dict[str, str]] = {
    "bond_maturity_queue_not_empty": {
        "owner": "data_owner",
        "next_action": "Fill missing bond maturity_date values at source or capture a signed scoped exclusion.",
        "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "exit_criteria": "Bond missing-maturity queue is empty or signed exclusion evidence is captured and surfaced as a boundary.",
    },
    "tyw_liability_maturity_queue_not_empty": {
        "owner": "data_owner",
        "next_action": "Fill missing TYW liability maturity_date values at source or capture a signed scoped exclusion.",
        "evidence_command": "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty",
        "exit_criteria": "TYW liability missing-maturity queue is empty or signed exclusion evidence is captured and surfaced as a boundary.",
    },
}


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _row_to_dict(description: Any, row: tuple[Any, ...] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        column[0]: _json_value(value)
        for column, value in zip(description, row, strict=True)
    }


def _fetch_one(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    params: list[object],
) -> dict[str, object] | None:
    cursor = connection.execute(query, params)
    return _row_to_dict(cursor.description, cursor.fetchone())


def _fetch_all(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    params: list[object],
) -> list[dict[str, object]]:
    cursor = connection.execute(query, params)
    rows = cursor.fetchall()
    return [
        {
            column[0]: _json_value(value)
            for column, value in zip(cursor.description, row, strict=True)
        }
        for row in rows
    ]


def _int_value(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return int(value or 0)


def _table_columns(connection: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = connection.execute(
        """
        select lower(column_name)
        from information_schema.columns
        where table_schema = 'main'
          and lower(table_name) = lower(?)
        """,
        [table_name],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _source_availability(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    required_columns: set[str],
) -> dict[str, object]:
    columns = _table_columns(connection, table_name)
    if not columns:
        return {
            "source_status": "source_unavailable",
            "blockers": [f"{table_name}_missing"],
        }
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        return {
            "source_status": "source_unavailable",
            "blockers": [f"{table_name}_missing_columns"],
            "missing_columns": missing_columns,
        }
    return {"source_status": "available", "blockers": []}


def _bond_missing_maturity_summary(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    return _fetch_one(
        connection,
        """
        select
          count(*) as row_count,
          coalesce(sum(case when maturity_date is null then 1 else 0 end), 0) as missing_maturity_rows,
          coalesce(sum(case when maturity_date is null then market_value else 0 end), 0) as missing_maturity_market_value
        from fact_formal_bond_analytics_daily
        where report_date = ?
        """,
        [report_date],
    ) or {
        "row_count": 0,
        "missing_maturity_rows": 0,
        "missing_maturity_market_value": "0",
    }


def _bond_missing_maturity_rows(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> list[dict[str, object]]:
    return _fetch_all(
        connection,
        """
        select
          report_date,
          instrument_code,
          instrument_name,
          portfolio_name,
          cost_center,
          market_value,
          dv01,
          tenor_bucket,
          source_version,
          rule_version,
          ingest_batch_id,
          trace_id
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and maturity_date is null
        order by coalesce(market_value, 0) desc, instrument_code
        limit ?
        """,
        [report_date, limit],
    )


def _bond_zqtz_candidate_source(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> dict[str, object]:
    source: dict[str, object] = {
        "source_table": "zqtz_bond_daily_snapshot",
        "target_queue": "bond_missing_maturity_rows",
        "match_key": [
            "report_date",
            "instrument_code",
            "portfolio_name",
            "cost_center",
        ],
    }
    availability = _source_availability(
        connection,
        "zqtz_bond_daily_snapshot",
        {
            "report_date",
            "instrument_code",
            "portfolio_name",
            "cost_center",
            "maturity_date",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
        },
    )
    source.update(availability)
    if availability["source_status"] != "available":
        source["status"] = "source_unavailable"
        return source

    summary = _fetch_one(
        connection,
        """
        with missing as (
          select
            row_number() over (
              order by coalesce(market_value, 0) desc, instrument_code, portfolio_name, cost_center
            ) as missing_row_id,
            report_date,
            instrument_code,
            portfolio_name,
            cost_center,
            market_value
          from fact_formal_bond_analytics_daily
          where report_date = ?
            and maturity_date is null
        ),
        candidates as (
          select
            cast(report_date as varchar) as report_date,
            instrument_code,
            portfolio_name,
            cost_center,
            cast(maturity_date as varchar) as candidate_maturity_date
          from zqtz_bond_daily_snapshot
          where cast(report_date as varchar) = ?
            and coalesce(trim(cast(maturity_date as varchar)), '') <> ''
        ),
        per_missing as (
          select
            missing.missing_row_id,
            max(missing.market_value) as missing_market_value,
            count(candidates.candidate_maturity_date) as candidate_row_count,
            count(distinct candidates.candidate_maturity_date) as distinct_candidate_dates
          from missing
          left join candidates
            on candidates.report_date = missing.report_date
           and candidates.instrument_code = missing.instrument_code
           and candidates.portfolio_name = missing.portfolio_name
           and candidates.cost_center = missing.cost_center
          group by missing.missing_row_id
        )
        select
          count(*) as missing_rows,
          coalesce(sum(case when candidate_row_count > 0 then 1 else 0 end), 0) as matched_missing_rows,
          coalesce(sum(candidate_row_count), 0) as candidate_rows,
          coalesce(sum(case when distinct_candidate_dates > 1 then 1 else 0 end), 0) as ambiguous_key_count,
          coalesce(sum(case when candidate_row_count > 0 then missing_market_value else 0 end), 0) as candidate_market_value
        from per_missing
        """,
        [report_date, report_date],
    ) or {}
    sample_candidates = _fetch_all(
        connection,
        """
        with missing as (
          select
            report_date,
            instrument_code,
            instrument_name,
            portfolio_name,
            cost_center,
            market_value,
            trace_id
          from fact_formal_bond_analytics_daily
          where report_date = ?
            and maturity_date is null
        ),
        candidates as (
          select
            cast(report_date as varchar) as report_date,
            instrument_code,
            portfolio_name,
            cost_center,
            cast(maturity_date as varchar) as candidate_maturity_date,
            source_version as candidate_source_version,
            rule_version as candidate_rule_version,
            ingest_batch_id as candidate_ingest_batch_id,
            trace_id as candidate_trace_id
          from zqtz_bond_daily_snapshot
          where cast(report_date as varchar) = ?
            and coalesce(trim(cast(maturity_date as varchar)), '') <> ''
        )
        select
          missing.instrument_code,
          missing.instrument_name,
          missing.portfolio_name,
          missing.cost_center,
          missing.market_value,
          missing.trace_id,
          candidates.candidate_maturity_date,
          candidates.candidate_source_version,
          candidates.candidate_rule_version,
          candidates.candidate_ingest_batch_id,
          candidates.candidate_trace_id
        from missing
        join candidates
          on candidates.report_date = missing.report_date
         and candidates.instrument_code = missing.instrument_code
         and candidates.portfolio_name = missing.portfolio_name
         and candidates.cost_center = missing.cost_center
        order by coalesce(missing.market_value, 0) desc, missing.instrument_code
        limit ?
        """,
        [report_date, report_date, limit],
    )
    source["summary"] = summary
    source["sample_candidates"] = sample_candidates
    source["status"] = _candidate_source_status(summary)
    return source


def _bond_position_snapshot_candidate_source(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> dict[str, object]:
    source: dict[str, object] = {
        "source_table": "position_snapshot",
        "target_queue": "bond_missing_maturity_rows",
        "match_key": ["as_of_date", "bond_code"],
    }
    availability = _source_availability(
        connection,
        "position_snapshot",
        {"as_of_date", "bond_code", "bond_name", "maturity_date", "source_version", "rule_version"},
    )
    source.update(availability)
    if availability["source_status"] != "available":
        source["status"] = "source_unavailable"
        return source

    summary = _fetch_one(
        connection,
        """
        with missing as (
          select
            row_number() over (
              order by coalesce(market_value, 0) desc, instrument_code, portfolio_name, cost_center
            ) as missing_row_id,
            report_date,
            instrument_code,
            market_value
          from fact_formal_bond_analytics_daily
          where report_date = ?
            and maturity_date is null
        ),
        candidates as (
          select
            cast(as_of_date as varchar) as report_date,
            bond_code as instrument_code,
            cast(maturity_date as varchar) as candidate_maturity_date
          from position_snapshot
          where cast(as_of_date as varchar) = ?
            and coalesce(trim(cast(maturity_date as varchar)), '') <> ''
        ),
        per_missing as (
          select
            missing.missing_row_id,
            max(missing.market_value) as missing_market_value,
            count(candidates.candidate_maturity_date) as candidate_row_count,
            count(distinct candidates.candidate_maturity_date) as distinct_candidate_dates
          from missing
          left join candidates
            on candidates.report_date = missing.report_date
           and candidates.instrument_code = missing.instrument_code
          group by missing.missing_row_id
        )
        select
          count(*) as missing_rows,
          coalesce(sum(case when candidate_row_count > 0 then 1 else 0 end), 0) as matched_missing_rows,
          coalesce(sum(candidate_row_count), 0) as candidate_rows,
          coalesce(sum(case when distinct_candidate_dates > 1 then 1 else 0 end), 0) as ambiguous_key_count,
          coalesce(sum(case when candidate_row_count > 0 then missing_market_value else 0 end), 0) as candidate_market_value
        from per_missing
        """,
        [report_date, report_date],
    ) or {}
    sample_candidates = _fetch_all(
        connection,
        """
        with missing as (
          select
            report_date,
            instrument_code,
            instrument_name,
            portfolio_name,
            cost_center,
            market_value,
            trace_id
          from fact_formal_bond_analytics_daily
          where report_date = ?
            and maturity_date is null
        ),
        candidates as (
          select
            cast(as_of_date as varchar) as report_date,
            bond_code as instrument_code,
            bond_name as candidate_instrument_name,
            cast(maturity_date as varchar) as candidate_maturity_date,
            source_version as candidate_source_version,
            rule_version as candidate_rule_version
          from position_snapshot
          where cast(as_of_date as varchar) = ?
            and coalesce(trim(cast(maturity_date as varchar)), '') <> ''
        )
        select
          missing.instrument_code,
          missing.instrument_name,
          missing.portfolio_name,
          missing.cost_center,
          missing.market_value,
          missing.trace_id,
          candidates.candidate_instrument_name,
          candidates.candidate_maturity_date,
          candidates.candidate_source_version,
          candidates.candidate_rule_version
        from missing
        join candidates
          on candidates.report_date = missing.report_date
         and candidates.instrument_code = missing.instrument_code
        order by coalesce(missing.market_value, 0) desc, missing.instrument_code
        limit ?
        """,
        [report_date, report_date, limit],
    )
    source["summary"] = summary
    source["sample_candidates"] = sample_candidates
    source["status"] = _candidate_source_status(summary)
    return source


def _tyw_liability_missing_maturity_summary(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    return _fetch_one(
        connection,
        """
        select
          count(*) as row_count,
          coalesce(sum(case when maturity_date is null then 1 else 0 end), 0) as missing_maturity_rows,
          coalesce(sum(case when maturity_date is null then principal_amount else 0 end), 0) as missing_maturity_principal
        from fact_formal_tyw_balance_daily
        where report_date = ?
          and position_scope = 'liability'
          and currency_basis = 'CNY'
        """,
        [report_date],
    ) or {
        "row_count": 0,
        "missing_maturity_rows": 0,
        "missing_maturity_principal": "0",
    }


def _tyw_liability_missing_maturity_rows(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> list[dict[str, object]]:
    return _fetch_all(
        connection,
        """
        select
          report_date,
          position_id,
          product_type,
          position_side,
          counterparty_name,
          position_scope,
          currency_basis,
          principal_amount,
          funding_cost_rate,
          source_version,
          rule_version,
          ingest_batch_id,
          trace_id
        from fact_formal_tyw_balance_daily
        where report_date = ?
          and position_scope = 'liability'
          and currency_basis = 'CNY'
          and maturity_date is null
        order by coalesce(principal_amount, 0) desc, position_id
        limit ?
        """,
        [report_date, limit],
    )


def _tyw_interbank_candidate_source(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> dict[str, object]:
    source: dict[str, object] = {
        "source_table": "tyw_interbank_daily_snapshot",
        "target_queue": "tyw_liability_missing_maturity_rows",
        "match_key": [
            "report_date",
            "position_id",
            "product_type",
            "position_side",
            "counterparty_name",
        ],
    }
    availability = _source_availability(
        connection,
        "tyw_interbank_daily_snapshot",
        {
            "report_date",
            "position_id",
            "product_type",
            "position_side",
            "counterparty_name",
            "maturity_date",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
        },
    )
    source.update(availability)
    if availability["source_status"] != "available":
        source["status"] = "source_unavailable"
        return source

    summary = _fetch_one(
        connection,
        """
        with missing as (
          select
            row_number() over (
              order by coalesce(principal_amount, 0) desc, position_id
            ) as missing_row_id,
            report_date,
            position_id,
            product_type,
            position_side,
            counterparty_name,
            principal_amount
          from fact_formal_tyw_balance_daily
          where report_date = ?
            and position_scope = 'liability'
            and currency_basis = 'CNY'
            and maturity_date is null
        ),
        candidates as (
          select
            cast(report_date as varchar) as report_date,
            position_id,
            product_type,
            position_side,
            counterparty_name,
            cast(maturity_date as varchar) as candidate_maturity_date
          from tyw_interbank_daily_snapshot
          where cast(report_date as varchar) = ?
            and coalesce(trim(cast(maturity_date as varchar)), '') <> ''
        ),
        per_missing as (
          select
            missing.missing_row_id,
            max(missing.principal_amount) as missing_principal_amount,
            count(candidates.candidate_maturity_date) as candidate_row_count,
            count(distinct candidates.candidate_maturity_date) as distinct_candidate_dates
          from missing
          left join candidates
            on candidates.report_date = missing.report_date
           and candidates.position_id = missing.position_id
           and candidates.product_type = missing.product_type
           and candidates.position_side = missing.position_side
           and candidates.counterparty_name = missing.counterparty_name
          group by missing.missing_row_id
        )
        select
          count(*) as missing_rows,
          coalesce(sum(case when candidate_row_count > 0 then 1 else 0 end), 0) as matched_missing_rows,
          coalesce(sum(candidate_row_count), 0) as candidate_rows,
          coalesce(sum(case when distinct_candidate_dates > 1 then 1 else 0 end), 0) as ambiguous_key_count,
          coalesce(sum(case when candidate_row_count > 0 then missing_principal_amount else 0 end), 0) as candidate_principal
        from per_missing
        """,
        [report_date, report_date],
    ) or {}
    sample_candidates = _fetch_all(
        connection,
        """
        with missing as (
          select
            report_date,
            position_id,
            product_type,
            position_side,
            counterparty_name,
            principal_amount,
            trace_id
          from fact_formal_tyw_balance_daily
          where report_date = ?
            and position_scope = 'liability'
            and currency_basis = 'CNY'
            and maturity_date is null
        ),
        candidates as (
          select
            cast(report_date as varchar) as report_date,
            position_id,
            product_type,
            position_side,
            counterparty_name,
            cast(maturity_date as varchar) as candidate_maturity_date,
            source_version as candidate_source_version,
            rule_version as candidate_rule_version,
            ingest_batch_id as candidate_ingest_batch_id,
            trace_id as candidate_trace_id
          from tyw_interbank_daily_snapshot
          where cast(report_date as varchar) = ?
            and coalesce(trim(cast(maturity_date as varchar)), '') <> ''
        )
        select
          missing.position_id,
          missing.product_type,
          missing.position_side,
          missing.counterparty_name,
          missing.principal_amount,
          missing.trace_id,
          candidates.candidate_maturity_date,
          candidates.candidate_source_version,
          candidates.candidate_rule_version,
          candidates.candidate_ingest_batch_id,
          candidates.candidate_trace_id
        from missing
        join candidates
          on candidates.report_date = missing.report_date
         and candidates.position_id = missing.position_id
         and candidates.product_type = missing.product_type
         and candidates.position_side = missing.position_side
         and candidates.counterparty_name = missing.counterparty_name
        order by coalesce(missing.principal_amount, 0) desc, missing.position_id
        limit ?
        """,
        [report_date, report_date, limit],
    )
    source["summary"] = summary
    source["sample_candidates"] = sample_candidates
    source["status"] = _candidate_source_status(summary)
    return source


def _candidate_source_status(summary: dict[str, object]) -> str:
    if _int_value(summary, "ambiguous_key_count") > 0:
        return "conflicting_candidates"
    if _int_value(summary, "matched_missing_rows") > 0:
        return "candidate_found"
    return "no_candidates"


def _candidate_evidence_status(candidate_sources: list[dict[str, object]]) -> str:
    statuses = {str(source.get("status") or "") for source in candidate_sources}
    if "conflicting_candidates" in statuses:
        return "conflicting_candidates"
    if "candidate_found" in statuses:
        return "candidate_found"
    if all(status == "source_unavailable" for status in statuses):
        return "source_unavailable"
    return "no_candidates"


def _maturity_candidate_evidence(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> dict[str, object]:
    candidate_sources = [
        _bond_zqtz_candidate_source(connection, report_date, limit),
        _bond_position_snapshot_candidate_source(connection, report_date, limit),
        _tyw_interbank_candidate_source(connection, report_date, limit),
    ]
    return {
        "status": _candidate_evidence_status(candidate_sources),
        "evidence_scope": MATURITY_CANDIDATE_SCOPE,
        "candidate_sources": candidate_sources,
        "strict_gate_effect": "none",
        "next_action": (
            "Use candidate rows only for data-owner review; strict closure still requires "
            "source remediation or signed scoped exclusion evidence."
        ),
    }


def _remediation_blockers(queue: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    bond_summary = queue["bond_missing_maturity_summary"]
    assert isinstance(bond_summary, dict)
    if _int_value(bond_summary, "missing_maturity_rows") > 0:
        blockers.append("bond_maturity_queue_not_empty")

    tyw_summary = queue["tyw_liability_missing_maturity_summary"]
    assert isinstance(tyw_summary, dict)
    if _int_value(tyw_summary, "missing_maturity_rows") > 0:
        blockers.append("tyw_liability_maturity_queue_not_empty")
    return blockers


def _remediation_actions(blockers: list[str]) -> list[dict[str, str]]:
    return [
        {"blocker": blocker, **MATURITY_REMEDIATION_ACTIONS[blocker]}
        for blocker in blockers
        if blocker in MATURITY_REMEDIATION_ACTIONS
    ]


def build_queue(
    *,
    duckdb_path: Path,
    report_date: str,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="maturity remediation limit",
    )
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        queue: dict[str, object] = {
            "page_id": "PAGE-PORTFOLIO-HOME-001",
            "page_slug": "portfolio",
            "report_date": report_date,
            "duckdb_path": str(duckdb_path),
            "sample_limit": limit,
            "remediation_scope": {
                "bond_queue": "fact_formal_bond_analytics_daily rows where maturity_date is null",
                "tyw_liability_queue": "fact_formal_tyw_balance_daily liability CNY rows where maturity_date is null",
            },
            "bond_missing_maturity_summary": _bond_missing_maturity_summary(connection, report_date),
            "tyw_liability_missing_maturity_summary": _tyw_liability_missing_maturity_summary(
                connection,
                report_date,
            ),
            "bond_missing_maturity_rows": _bond_missing_maturity_rows(connection, report_date, limit),
            "tyw_liability_missing_maturity_rows": _tyw_liability_missing_maturity_rows(
                connection,
                report_date,
                limit,
            ),
            "maturity_candidate_evidence": _maturity_candidate_evidence(
                connection,
                report_date,
                limit,
            ),
        }
    finally:
        connection.close()

    blockers = _remediation_blockers(queue)
    queue["remediation_status"] = "clean" if not blockers else "blocked"
    queue["remediation_blockers"] = blockers
    queue["remediation_actions"] = _remediation_actions(blockers)
    return queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read row-level portfolio-home maturity remediation queues from DuckDB.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="maturity remediation limit",
        ),
        default=DEFAULT_LIMIT,
    )
    parser.add_argument(
        "--require-empty",
        action="store_true",
        help="Return non-zero unless both maturity remediation queues are empty.",
    )
    args = parser.parse_args(argv)

    queue = build_queue(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        limit=int(args.limit),
    )
    print(json.dumps(queue, ensure_ascii=False, indent=2))
    if args.require_empty and queue["remediation_status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
