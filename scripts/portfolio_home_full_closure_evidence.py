from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB = ROOT / "data" / "moss.duckdb"
DEFAULT_REPORT_DATE = "2026-05-31"

SUPPORTED_KRD_BUCKETS = {"1Y", "3Y", "5Y", "7Y", "10Y", "30Y"}
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


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
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


def _int_value(payload: dict[str, object] | None, key: str) -> int:
    if payload is None:
        return 0
    value = payload.get(key)
    return int(value or 0)


def _decimal_value(payload: dict[str, object] | None, key: str) -> Decimal:
    if payload is None:
        return Decimal("0")
    value = payload.get(key)
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _risk_tensor_evidence(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    row = _fetch_one(
        connection,
        """
        select
          report_date,
          quality_flag,
          portfolio_dv01,
          krd_1y + krd_3y + krd_5y + krd_7y + krd_10y + krd_30y as krd_sum,
          warnings_json,
          source_version,
          upstream_source_version,
          liability_source_version
        from fact_formal_risk_tensor_daily
        where report_date = ?
        limit 1
        """,
        [report_date],
    )
    if row is None:
        return {"exists": False}
    return {"exists": True, **row}


def _bond_maturity_gap(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    """Expose bond-ledger no-maturity rows without treating them as data gaps."""
    return _fetch_one(
        connection,
        """
        select
          count(*) as row_count,
          coalesce(sum(case when maturity_date is null then 1 else 0 end), 0) as no_maturity_rows,
          coalesce(sum(case when maturity_date is null then market_value else 0 end), 0) as no_maturity_market_value,
          cast(0 as bigint) as missing_maturity_rows,
          cast(0 as decimal(38, 8)) as missing_maturity_market_value
        from fact_formal_bond_analytics_daily
        where report_date = ?
        """,
        [report_date],
    ) or {}


def _bond_matured_outstanding(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    return _fetch_one(
        connection,
        """
        with candidates as (
          select
            market_value,
            coalesce(dv01, 0) as dv01,
            try_cast(maturity_date as date) as parsed_maturity_date,
            try_cast(? as date) as requested_report_date
          from fact_formal_bond_analytics_daily
          where report_date = ?
            and maturity_date is not null
            and coalesce(market_value, 0) <> 0
        )
        select
          count(*) filter (where parsed_maturity_date <= requested_report_date) as row_count,
          coalesce(sum(market_value) filter (where parsed_maturity_date <= requested_report_date), 0) as net_market_value,
          coalesce(sum(abs(market_value)) filter (where parsed_maturity_date <= requested_report_date), 0) as absolute_market_value,
          coalesce(sum(dv01) filter (where parsed_maturity_date <= requested_report_date), 0) as dv01_sum,
          cast(min(case when parsed_maturity_date <= requested_report_date then parsed_maturity_date end) as varchar) as earliest_maturity_date,
          cast(max(case when parsed_maturity_date <= requested_report_date then parsed_maturity_date end) as varchar) as latest_maturity_date,
          count(*) filter (where parsed_maturity_date is null) as unparseable_maturity_date_rows,
          coalesce(sum(market_value) filter (where parsed_maturity_date is null), 0) as unparseable_maturity_date_market_value
        from candidates
        """,
        [report_date, report_date],
    ) or {}


def _tyw_maturity_gap(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    *,
    risk_scope: bool,
) -> dict[str, object]:
    scope_clause = ""
    if risk_scope:
        scope_clause = "and position_scope = 'liability' and currency_basis = 'CNY'"
    return _fetch_one(
        connection,
        f"""
        select
          count(*) as row_count,
          coalesce(sum(case when maturity_date is null then 1 else 0 end), 0) as missing_maturity_rows,
          coalesce(sum(case when maturity_date is null then principal_amount else 0 end), 0) as missing_maturity_principal
        from fact_formal_tyw_balance_daily
        where report_date = ?
        {scope_clause}
        """,
        [report_date],
    ) or {}


def _krd_remap_scope(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> list[dict[str, object]]:
    rows = _fetch_all(
        connection,
        """
        select
          tenor_bucket,
          count(*) as row_count,
          coalesce(sum(dv01), 0) as dv01_sum
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and tenor_bucket is not null
          and tenor_bucket not in ('1Y', '3Y', '5Y', '7Y', '10Y', '30Y')
          and coalesce(dv01, 0) <> 0
        group by 1
        order by 1
        """,
        [report_date],
    )
    enriched = []
    for row in rows:
        tenor = str(row.get("tenor_bucket") or "")
        enriched.append(
            {
                **row,
                "mapped_to": KRD_BUCKET_FALLBACK.get(tenor),
                "mapping_status": "mapped" if tenor in KRD_BUCKET_FALLBACK else "unsupported",
            }
        )
    return enriched


def _closure_blockers(evidence: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    risk_tensor = evidence["risk_tensor"]
    assert isinstance(risk_tensor, dict)
    if not risk_tensor.get("exists"):
        blockers.append("risk_tensor_missing")
    else:
        quality = str(risk_tensor.get("quality_flag") or "missing")
        if quality != "ok":
            blockers.append(f"risk_tensor_quality_{quality}")
        if _decimal_value(risk_tensor, "portfolio_dv01") != _decimal_value(risk_tensor, "krd_sum"):
            blockers.append("krd_sum_mismatch")

    remap_rows = evidence["krd_remap_scope"]
    assert isinstance(remap_rows, list)
    if any(row.get("mapping_status") == "mapped" for row in remap_rows if isinstance(row, dict)):
        blockers.append("krd_contract_decision_required")
    if any(row.get("mapping_status") == "unsupported" for row in remap_rows if isinstance(row, dict)):
        blockers.append("unsupported_krd_bucket")

    bond_gap = evidence["bond_maturity_gap"]
    assert isinstance(bond_gap, dict)
    if _int_value(bond_gap, "missing_maturity_rows") > 0:
        blockers.append("bond_maturity_date_remediation_required")

    matured_outstanding = evidence["bond_matured_outstanding"]
    assert isinstance(matured_outstanding, dict)
    if (
        _int_value(matured_outstanding, "row_count") > 0
        or _int_value(matured_outstanding, "unparseable_maturity_date_rows") > 0
    ):
        blockers.append("bond_matured_outstanding_reconciliation_required")

    tyw_scope_gap = evidence["tyw_liability_maturity_gap_risk_scope"]
    assert isinstance(tyw_scope_gap, dict)
    if _int_value(tyw_scope_gap, "missing_maturity_rows") > 0:
        blockers.append("tyw_liability_maturity_date_remediation_required")

    return blockers


def build_evidence(
    *,
    duckdb_path: Path,
    report_date: str,
) -> dict[str, object]:
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        evidence: dict[str, object] = {
            "page_id": "PAGE-PORTFOLIO-HOME-001",
            "page_slug": "portfolio",
            "report_date": report_date,
            "duckdb_path": str(duckdb_path),
            "risk_tensor": _risk_tensor_evidence(connection, report_date),
            "bond_maturity_gap": _bond_maturity_gap(connection, report_date),
            "bond_matured_outstanding": _bond_matured_outstanding(
                connection,
                report_date,
            ),
            "tyw_liability_maturity_gap_risk_scope": _tyw_maturity_gap(
                connection,
                report_date,
                risk_scope=True,
            ),
            "tyw_liability_maturity_gap_full_formal": _tyw_maturity_gap(
                connection,
                report_date,
                risk_scope=False,
            ),
            "krd_remap_scope": _krd_remap_scope(connection, report_date),
        }
    finally:
        connection.close()

    blockers = _closure_blockers(evidence)
    evidence["data_quality_status"] = "clean" if not blockers else "blocked"
    evidence["closure_blockers"] = blockers
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read portfolio-home full-closure data-quality evidence from DuckDB.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless the data-quality evidence has no closure blockers.",
    )
    args = parser.parse_args(argv)

    evidence = build_evidence(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if args.require_clean and evidence["data_quality_status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
