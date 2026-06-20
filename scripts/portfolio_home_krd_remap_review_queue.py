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

SUPPORTED_KRD_BUCKETS = ("1Y", "3Y", "5Y", "7Y", "10Y", "30Y")
KRD_BUCKET_FALLBACK = {
    "6M": "krd_1y",
    "2Y": "krd_3y",
    "4Y": "krd_5y",
    "6Y": "krd_7y",
    "8Y": "krd_10y",
    "9Y": "krd_10y",
    "15Y": "krd_10y",
    "20Y": "krd_30y",
    "25Y": "krd_30y",
}

KRD_REVIEW_ACTIONS: dict[str, dict[str, str]] = {
    "krd_contract_decision_required": {
        "owner": "risk_owner",
        "next_action": "Approve current nearest-bucket KRD mapping or require exact tenor buckets before full closure.",
        "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
        "exit_criteria": "Approved metric contract covers every mapped non-standard tenor or no non-standard tenor carries non-zero DV01.",
    },
    "unsupported_krd_bucket": {
        "owner": "risk_owner",
        "next_action": "Map the unsupported tenor in the metric contract or reject the current KRD tensor for full closure.",
        "evidence_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
        "exit_criteria": "No unsupported tenor carries non-zero DV01 under the formal risk-tensor contract.",
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


def _mapping_fields(tenor_bucket: object) -> dict[str, object]:
    tenor = str(tenor_bucket or "")
    mapped_to = KRD_BUCKET_FALLBACK.get(tenor)
    return {
        "mapped_to": mapped_to,
        "mapping_status": "mapped" if mapped_to is not None else "unsupported",
    }


def _krd_remap_summary(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> list[dict[str, object]]:
    rows = _fetch_all(
        connection,
        """
        select
          tenor_bucket,
          count(*) as all_rows,
          coalesce(sum(case when coalesce(dv01, 0) <> 0 then 1 else 0 end), 0) as nonzero_dv01_rows,
          coalesce(sum(market_value), 0) as all_market_value,
          coalesce(sum(case when coalesce(dv01, 0) <> 0 then market_value else 0 end), 0) as nonzero_dv01_market_value,
          coalesce(sum(case when coalesce(dv01, 0) <> 0 then dv01 else 0 end), 0) as dv01_sum
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and tenor_bucket is not null
          and tenor_bucket not in ('1Y', '3Y', '5Y', '7Y', '10Y', '30Y')
        group by 1
        order by 1
        """,
        [report_date],
    )
    return [{**row, **_mapping_fields(row.get("tenor_bucket"))} for row in rows]


def _krd_remap_rows(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    limit: int,
) -> list[dict[str, object]]:
    rows = _fetch_all(
        connection,
        """
        select
          report_date,
          instrument_code,
          instrument_name,
          portfolio_name,
          cost_center,
          market_value,
          maturity_date,
          tenor_bucket,
          dv01,
          source_version,
          rule_version,
          ingest_batch_id,
          trace_id
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and tenor_bucket is not null
          and tenor_bucket not in ('1Y', '3Y', '5Y', '7Y', '10Y', '30Y')
          and coalesce(dv01, 0) <> 0
        order by abs(coalesce(dv01, 0)) desc, coalesce(market_value, 0) desc, instrument_code
        limit ?
        """,
        [report_date, limit],
    )
    return [{**row, **_mapping_fields(row.get("tenor_bucket"))} for row in rows]


def _int_value(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return int(value or 0)


def _review_blockers(queue: dict[str, object]) -> list[str]:
    summary = queue["krd_remap_summary"]
    assert isinstance(summary, list)
    blockers: list[str] = []
    has_mapped = any(
        isinstance(row, dict)
        and row.get("mapping_status") == "mapped"
        and _int_value(row, "nonzero_dv01_rows") > 0
        for row in summary
    )
    has_unsupported = any(
        isinstance(row, dict)
        and row.get("mapping_status") == "unsupported"
        and _int_value(row, "nonzero_dv01_rows") > 0
        for row in summary
    )
    if has_mapped:
        blockers.append("krd_contract_decision_required")
    if has_unsupported:
        blockers.append("unsupported_krd_bucket")
    return blockers


def _review_actions(blockers: list[str]) -> list[dict[str, str]]:
    return [
        {"blocker": blocker, **KRD_REVIEW_ACTIONS[blocker]}
        for blocker in blockers
        if blocker in KRD_REVIEW_ACTIONS
    ]


def build_queue(
    *,
    duckdb_path: Path,
    report_date: str,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(limit, label="KRD review limit")
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        queue: dict[str, object] = {
            "page_id": "PAGE-PORTFOLIO-HOME-001",
            "page_slug": "portfolio",
            "report_date": report_date,
            "duckdb_path": str(duckdb_path),
            "sample_limit": limit,
            "supported_krd_buckets": list(SUPPORTED_KRD_BUCKETS),
            "nearest_bucket_map": dict(KRD_BUCKET_FALLBACK),
            "decision_options": [
                "approve_nearest_bucket",
                "require_exact_bucket_schema",
                "reject",
            ],
            "krd_remap_summary": _krd_remap_summary(connection, report_date),
            "krd_remap_rows": _krd_remap_rows(connection, report_date, limit),
        }
    finally:
        connection.close()

    blockers = _review_blockers(queue)
    queue["review_status"] = "clean" if not blockers else "decision_required"
    queue["review_blockers"] = blockers
    queue["review_actions"] = _review_actions(blockers)
    return queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read row-level portfolio-home KRD remap review evidence from DuckDB.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="KRD review limit",
        ),
        default=DEFAULT_LIMIT,
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless no KRD contract decision is pending.",
    )
    args = parser.parse_args(argv)

    queue = build_queue(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        limit=int(args.limit),
    )
    print(json.dumps(queue, ensure_ascii=False, indent=2))
    if args.require_clean and queue["review_status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
