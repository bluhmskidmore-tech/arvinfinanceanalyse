from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB = ROOT / "data" / "moss.duckdb"
DEFAULT_REPORT_DATE = "2026-05-31"
SUPPORTED_KRD_BUCKETS = ("1Y", "3Y", "5Y", "7Y", "10Y", "30Y")
DECIMAL_8 = Decimal("0.00000001")
EVIDENCE_SCOPE = {
    "checks_warning_consistency": True,
    "checks_risk_tensor_clean_state": True,
    "captures_risk_owner_decision": False,
    "remediates_source_data": False,
    "approves_metric_or_page": False,
    "writes_governance_records": False,
    "captures_business_owner_approval": False,
    "proves_full_score_closure": False,
    "certification_effect": "none",
}
RESOLUTION_SCOPE = {
    "captures_owner_decision": False,
    "remediates_source_data": False,
    "approves_metric_or_page": False,
    "certification_effect": "none",
}


def _resolution_row(
    *,
    warning_key: str,
    owner: str,
    parsed: object,
    recomputed: object,
    evidence_command: str,
    exit_criteria: str,
) -> dict[str, object]:
    return {
        "warning_key": warning_key,
        "owner": owner,
        "current_status": "clean" if parsed == recomputed and not _has_resolution_gap(parsed) else "blocked",
        "current_evidence": {
            "parsed": parsed,
            "recomputed": recomputed,
        },
        "evidence_command": evidence_command,
        "exit_criteria": exit_criteria,
        "evidence_scope": dict(RESOLUTION_SCOPE),
    }


def _has_resolution_gap(value: object) -> bool:
    if isinstance(value, dict):
        for item in value.values():
            if _has_resolution_gap(item):
                return True
        return False
    if isinstance(value, list):
        return bool(value)
    try:
        return Decimal(str(value or "0")) != 0
    except Exception:
        return bool(value)


def _warning_resolution_matrix(
    *,
    parsed: dict[str, object],
    recomputed: dict[str, object],
) -> list[dict[str, object]]:
    maturity_command = "python scripts/portfolio_home_maturity_remediation_queue.py --require-empty"
    return [
        _resolution_row(
            warning_key="krd_bucket_remap",
            owner="risk_owner",
            parsed=parsed["krd_buckets"],
            recomputed=recomputed["krd_buckets"],
            evidence_command="python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
            exit_criteria=(
                "Risk owner approves nearest-bucket KRD mapping or supplies exact-bucket "
                "schema evidence; KRD review queue exits 0."
            ),
        ),
        _resolution_row(
            warning_key="duration_denominator_exclusion",
            owner="data_owner",
            parsed=parsed["duration_exclusion"],
            recomputed=recomputed["duration_exclusion"],
            evidence_command=maturity_command,
            exit_criteria=(
                "Data owner remediates missing maturity dates or captures signed scoped "
                "exclusion; maturity remediation queue exits 0."
            ),
        ),
        _resolution_row(
            warning_key="bond_liquidity_gap_missing_maturity",
            owner="data_owner",
            parsed=parsed["bond_liquidity_gap"],
            recomputed=recomputed["bond_liquidity_gap"],
            evidence_command=maturity_command,
            exit_criteria=(
                "Bond missing maturity rows are remediated or signed scoped exclusion "
                "evidence is captured; maturity remediation queue exits 0."
            ),
        ),
        _resolution_row(
            warning_key="tyw_liability_gap_missing_maturity",
            owner="data_owner",
            parsed=parsed["tyw_liability_liquidity_gap"],
            recomputed=recomputed["tyw_liability_liquidity_gap"],
            evidence_command=maturity_command,
            exit_criteria=(
                "TYW liability missing maturity rows are remediated or signed scoped "
                "exclusion evidence is captured; maturity remediation queue exits 0."
            ),
        ),
    ]


def _decimal_text(value: object) -> str:
    return format(Decimal(str(value or "0")).quantize(DECIMAL_8), "f")


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, datetime):
        return value.isoformat()
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


def _table_columns(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(f"pragma table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _decimal_delta(recomputed: object, parsed: object) -> str:
    return _decimal_text(Decimal(str(recomputed or "0")) - Decimal(str(parsed or "0")))


def _integer_delta(recomputed: object, parsed: object) -> int:
    return int(recomputed or 0) - int(parsed or 0)


def _duration_exclusion_breakdown(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> list[dict[str, object]]:
    return _fetch_all(
        connection,
        """
        select
          case
            when maturity_date is null then 'missing_maturity'
            else 'nonpositive_duration'
          end as exclusion_reason,
          count(*) as row_count,
          coalesce(sum(market_value), 0)::decimal(24, 8) as market_value_sum,
          coalesce(sum(dv01), 0)::decimal(24, 8) as dv01_sum
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and coalesce(market_value, 0) <> 0
          and (maturity_date is null or coalesce(modified_duration, 0) <= 0)
        group by 1
        order by 1
        """,
        [report_date],
    )


def _optional_text_field(columns: set[str], field: str) -> str:
    if field in columns:
        return field
    return f"cast(null as varchar) as {field}"


def _duration_exclusion_warning_text(warnings: list[str]) -> str | None:
    for warning in warnings:
        if "portfolio duration denominator" in warning:
            return warning
    return None


def _format_duration_exclusion_warning(duration: dict[str, object]) -> str:
    return (
        f"{duration.get('row_count')} rows carry "
        f"market_value={duration.get('market_value_sum')} and are excluded from "
        "portfolio duration denominator: "
        f"{duration.get('missing_maturity_rows')} without maturity_date; "
        f"{duration.get('nonpositive_duration_rows')} with non-positive "
        "modified_duration. DV01 totals remain sourced from row dv01; duration "
        "metrics ignore these rows until inputs are remediated."
    )


def _preview_warnings_from_recomputed(recomputed: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    krd_buckets = recomputed.get("krd_buckets", [])
    if isinstance(krd_buckets, list) and krd_buckets:
        warnings.append(
            "Non-standard tenor buckets remapped to nearest KRD bucket: "
            + ", ".join(str(bucket) for bucket in krd_buckets)
        )

    duration = recomputed.get("duration_exclusion", {})
    if isinstance(duration, dict) and int(duration.get("row_count") or 0) > 0:
        warnings.append(_format_duration_exclusion_warning(duration))

    bond_gap = recomputed.get("bond_liquidity_gap", {})
    if isinstance(bond_gap, dict) and int(bond_gap.get("missing_maturity_rows") or 0) > 0:
        warnings.append(
            f"Excluded {bond_gap.get('missing_maturity_rows')} rows without "
            "maturity_date from liquidity gap calculation."
        )

    tyw_gap = recomputed.get("tyw_liability_liquidity_gap", {})
    if isinstance(tyw_gap, dict) and int(tyw_gap.get("missing_maturity_rows") or 0) > 0:
        warnings.append(
            f"Excluded {tyw_gap.get('missing_maturity_rows')} liability rows without "
            "maturity_date from liquidity gap calculation."
        )
    return warnings


def _duration_exclusion_sample_rows(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    columns = _table_columns(connection, "fact_formal_bond_analytics_daily")
    optional_fields = [
        "instrument_code",
        "instrument_name",
        "portfolio_name",
        "cost_center",
        "source_version",
        "trace_id",
    ]
    select_fields = [
        _optional_text_field(columns, field)
        for field in optional_fields
    ]
    order_suffix = ", instrument_code" if "instrument_code" in columns else ""
    return _fetch_all(
        connection,
        f"""
        select
          case
            when maturity_date is null then 'missing_maturity'
            else 'nonpositive_duration'
          end as exclusion_reason,
          {", ".join(select_fields)},
          market_value::decimal(24, 8) as market_value,
          maturity_date,
          modified_duration::decimal(18, 8) as modified_duration,
          dv01::decimal(24, 8) as dv01
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and coalesce(market_value, 0) <> 0
          and (maturity_date is null or coalesce(modified_duration, 0) <= 0)
        order by market_value desc{order_suffix}
        limit ?
        """,
        [report_date, limit],
    )


def _duration_exclusion_delta_detail(
    *,
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
    raw_warnings: list[str],
    parsed: dict[str, object],
    recomputed: dict[str, object],
) -> dict[str, object]:
    parsed_duration = parsed.get("duration_exclusion", {})
    recomputed_duration = recomputed.get("duration_exclusion", {})
    assert isinstance(parsed_duration, dict)
    assert isinstance(recomputed_duration, dict)
    delta = {
        "row_count": _integer_delta(
            recomputed_duration.get("row_count"),
            parsed_duration.get("row_count"),
        ),
        "market_value_sum": _decimal_delta(
            recomputed_duration.get("market_value_sum"),
            parsed_duration.get("market_value_sum"),
        ),
        "missing_maturity_rows": _integer_delta(
            recomputed_duration.get("missing_maturity_rows"),
            parsed_duration.get("missing_maturity_rows"),
        ),
        "nonpositive_duration_rows": _integer_delta(
            recomputed_duration.get("nonpositive_duration_rows"),
            parsed_duration.get("nonpositive_duration_rows"),
        ),
    }
    mismatch_fields = [
        field
        for field, value in delta.items()
        if (Decimal(value) if isinstance(value, str) else Decimal(value)) != 0
    ]
    parsed_warning_text = _duration_exclusion_warning_text(raw_warnings)
    expected_warning_text = _format_duration_exclusion_warning(recomputed_duration)
    return {
        "status": "matched" if not mismatch_fields else "mismatch",
        "delta_basis": "recomputed_minus_parsed",
        "owner_reconciliation_hint": (
            "Recompute or rematerialize risk tensor warnings so parsed warning "
            "numbers match fact_formal_bond_analytics_daily evidence."
            if mismatch_fields
            else "Parsed risk tensor warning matches recomputed duration exclusion evidence."
        ),
        "mismatch_fields": mismatch_fields,
        "delta": delta,
        "parsed_warning_text": parsed_warning_text,
        "expected_warning_text_from_recomputed": expected_warning_text,
        "recomputed_breakdown_by_reason": _duration_exclusion_breakdown(
            connection,
            report_date,
        ),
        "top_recomputed_rows_by_market_value": _duration_exclusion_sample_rows(
            connection,
            report_date,
        ),
    }


def _risk_tensor_row(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    columns = _table_columns(connection, "fact_formal_risk_tensor_daily")
    lineage_fields = [
        "source_version",
        "upstream_source_version",
        "liability_source_version",
        "rule_version",
        "cache_version",
        "trace_id",
    ]
    optional_fields = [
        _optional_text_field(columns, field)
        for field in lineage_fields
    ]
    row = _fetch_one(
        connection,
        f"""
        select report_date, quality_flag, warnings_json, {", ".join(optional_fields)}
        from fact_formal_risk_tensor_daily
        where report_date = ?
        limit 1
        """,
        [report_date],
    )
    if row is None:
        return {"exists": False, "warnings": []}

    raw_warnings = row.get("warnings_json")
    warnings: list[str] = []
    if isinstance(raw_warnings, str) and raw_warnings.strip():
        parsed = json.loads(raw_warnings)
        if isinstance(parsed, list):
            warnings = [str(item) for item in parsed]
    return {"exists": True, **row, "warnings": warnings}


def _risk_tensor_lineage(risk_tensor: dict[str, object]) -> dict[str, object]:
    return {
        "source_version": risk_tensor.get("source_version"),
        "upstream_source_version": risk_tensor.get("upstream_source_version"),
        "liability_source_version": risk_tensor.get("liability_source_version"),
        "rule_version": risk_tensor.get("rule_version"),
        "cache_version": risk_tensor.get("cache_version"),
        "trace_id": risk_tensor.get("trace_id"),
    }


def _empty_duration_exclusion() -> dict[str, object]:
    return {
        "row_count": 0,
        "market_value_sum": "0.00000000",
        "missing_maturity_rows": 0,
        "nonpositive_duration_rows": 0,
    }


def _parse_warnings(warnings: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {
        "krd_buckets": [],
        "duration_exclusion": _empty_duration_exclusion(),
        "bond_liquidity_gap": {"missing_maturity_rows": 0},
        "tyw_liability_liquidity_gap": {"missing_maturity_rows": 0},
    }

    for warning in warnings:
        krd_match = re.search(
            r"Non-standard tenor buckets remapped to nearest KRD bucket:\s*(.+)$",
            warning,
        )
        if krd_match:
            parsed["krd_buckets"] = [
                bucket.strip()
                for bucket in krd_match.group(1).split(",")
                if bucket.strip()
            ]
            continue

        duration_match = re.search(
            r"(\d+) rows carry market_value=([0-9.]+) and are excluded from portfolio duration denominator: "
            r"(\d+) without maturity_date; (\d+) with non-positive modified_duration",
            warning,
        )
        if duration_match:
            parsed["duration_exclusion"] = {
                "row_count": int(duration_match.group(1)),
                "market_value_sum": _decimal_text(duration_match.group(2)),
                "missing_maturity_rows": int(duration_match.group(3)),
                "nonpositive_duration_rows": int(duration_match.group(4)),
            }
            continue

        tyw_match = re.search(
            r"Excluded (\d+) liability rows without maturity_date from liquidity gap calculation\.",
            warning,
        )
        if tyw_match:
            parsed["tyw_liability_liquidity_gap"] = {
                "missing_maturity_rows": int(tyw_match.group(1)),
            }
            continue

        bond_match = re.search(
            r"Excluded (\d+) rows without maturity_date from liquidity gap calculation\.",
            warning,
        )
        if bond_match:
            parsed["bond_liquidity_gap"] = {
                "missing_maturity_rows": int(bond_match.group(1)),
            }
    return parsed


def _recomputed_krd_buckets(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> list[str]:
    rows = _fetch_all(
        connection,
        """
        select tenor_bucket
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
    return [str(row["tenor_bucket"]) for row in rows]


def _recomputed_duration_exclusion(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    row = _fetch_one(
        connection,
        """
        select
          count(*) as row_count,
          coalesce(sum(market_value), 0)::decimal(24, 8) as market_value_sum,
          coalesce(sum(case when maturity_date is null then 1 else 0 end), 0) as missing_maturity_rows,
          coalesce(sum(
            case when maturity_date is not null and coalesce(modified_duration, 0) <= 0 then 1 else 0 end
          ), 0) as nonpositive_duration_rows
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and coalesce(market_value, 0) <> 0
          and (maturity_date is null or coalesce(modified_duration, 0) <= 0)
        """,
        [report_date],
    ) or _empty_duration_exclusion()
    row["market_value_sum"] = _decimal_text(row.get("market_value_sum"))
    return row


def _recomputed_bond_liquidity_gap(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    return _fetch_one(
        connection,
        """
        select count(*) as missing_maturity_rows
        from fact_formal_bond_analytics_daily
        where report_date = ?
          and maturity_date is null
        """,
        [report_date],
    ) or {"missing_maturity_rows": 0}


def _recomputed_tyw_liability_gap(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    return _fetch_one(
        connection,
        """
        select count(*) as missing_maturity_rows
        from fact_formal_tyw_balance_daily
        where report_date = ?
          and position_scope = 'liability'
          and currency_basis = 'CNY'
          and maturity_date is null
        """,
        [report_date],
    ) or {"missing_maturity_rows": 0}


def _recompute_warnings(
    connection: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    return {
        "krd_buckets": _recomputed_krd_buckets(connection, report_date),
        "duration_exclusion": _recomputed_duration_exclusion(connection, report_date),
        "bond_liquidity_gap": _recomputed_bond_liquidity_gap(connection, report_date),
        "tyw_liability_liquidity_gap": _recomputed_tyw_liability_gap(connection, report_date),
    }


def _consistency_blockers(
    parsed: dict[str, object],
    recomputed: dict[str, object],
) -> list[str]:
    blockers: list[str] = []
    if parsed["krd_buckets"] != recomputed["krd_buckets"]:
        blockers.append("krd_bucket_warning_mismatch")
    if parsed["duration_exclusion"] != recomputed["duration_exclusion"]:
        blockers.append("duration_exclusion_warning_mismatch")
    if parsed["bond_liquidity_gap"] != recomputed["bond_liquidity_gap"]:
        blockers.append("bond_liquidity_gap_warning_mismatch")
    if parsed["tyw_liability_liquidity_gap"] != recomputed["tyw_liability_liquidity_gap"]:
        blockers.append("tyw_liability_gap_warning_mismatch")
    return blockers


def _decision_blockers(
    risk_tensor: dict[str, object],
    consistency_blockers: list[str],
) -> list[str]:
    blockers: list[str] = []
    if not risk_tensor.get("exists"):
        return ["risk_tensor_missing"]

    quality = str(risk_tensor.get("quality_flag") or "missing")
    warnings = risk_tensor.get("warnings")
    assert isinstance(warnings, list)
    if quality != "ok":
        blockers.append(f"risk_tensor_quality_{quality}")
    elif warnings:
        blockers.append("risk_tensor_warning_present")
    if consistency_blockers:
        blockers.append("risk_tensor_warning_mismatch")
    return blockers


def _risk_tensor_rematerialization_preview(
    *,
    risk_tensor: dict[str, object],
    consistency_blockers: list[str],
    recomputed: dict[str, object],
) -> dict[str, object]:
    if not risk_tensor.get("exists"):
        return {
            "status": "not_available",
            "preview_basis": "current_formal_facts_read_only",
            "writes_database": False,
            "approves_metric_or_page": False,
            "certification_effect": "none",
            "blockers": ["risk_tensor_missing"],
        }

    preview_warnings = _preview_warnings_from_recomputed(recomputed)
    preview_parsed = _parse_warnings(preview_warnings)
    preview_consistency_blockers = _consistency_blockers(preview_parsed, recomputed)
    preview_quality_flag = "warning" if preview_warnings else "ok"
    preview_decision_blockers = _decision_blockers(
        {
            "exists": True,
            "quality_flag": preview_quality_flag,
            "warnings": preview_warnings,
        },
        preview_consistency_blockers,
    )
    cleared_blockers = [
        blocker
        for blocker in consistency_blockers
        if blocker not in preview_consistency_blockers
    ]
    return {
        "status": "would_remain_blocked" if preview_decision_blockers else "would_be_clean",
        "preview_basis": "current_formal_facts_read_only",
        "writes_database": False,
        "approves_metric_or_page": False,
        "certification_effect": "none",
        "current_consistency_blockers": consistency_blockers,
        "would_clear_consistency_blockers": cleared_blockers,
        "preview_consistency_status": (
            "consistent" if not preview_consistency_blockers else "mismatch"
        ),
        "preview_consistency_blockers": preview_consistency_blockers,
        "preview_quality_flag": preview_quality_flag,
        "preview_decision_status": (
            "clean" if not preview_decision_blockers else "blocked"
        ),
        "preview_decision_blockers": preview_decision_blockers,
        "preview_warnings": preview_warnings,
    }


def build_evidence(
    *,
    duckdb_path: Path,
    report_date: str,
) -> dict[str, object]:
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        risk_tensor = _risk_tensor_row(connection, report_date)
        warnings = risk_tensor.get("warnings")
        assert isinstance(warnings, list)
        parsed = _parse_warnings(warnings)
        recomputed = _recompute_warnings(connection, report_date)
        duration_delta_detail = _duration_exclusion_delta_detail(
            connection=connection,
            report_date=report_date,
            raw_warnings=warnings,
            parsed=parsed,
            recomputed=recomputed,
        )
    finally:
        connection.close()

    consistency_blockers = [] if risk_tensor.get("exists") else ["risk_tensor_missing"]
    if risk_tensor.get("exists"):
        consistency_blockers = _consistency_blockers(parsed, recomputed)
    decision_blockers = _decision_blockers(risk_tensor, consistency_blockers)
    rematerialization_preview = _risk_tensor_rematerialization_preview(
        risk_tensor=risk_tensor,
        consistency_blockers=consistency_blockers,
        recomputed=recomputed,
    )
    return {
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "risk_tensor": risk_tensor,
        "risk_tensor_lineage": _risk_tensor_lineage(risk_tensor),
        "parsed_warnings": parsed,
        "recomputed_warnings": recomputed,
        "duration_exclusion_delta_detail": duration_delta_detail,
        "risk_tensor_rematerialization_preview": rematerialization_preview,
        "warning_resolution_matrix": _warning_resolution_matrix(
            parsed=parsed,
            recomputed=recomputed,
        ),
        "warning_consistency_status": "consistent" if not consistency_blockers else "mismatch",
        "consistency_blockers": consistency_blockers,
        "decision_status": "clean" if not decision_blockers else "blocked",
        "decision_blockers": decision_blockers,
        "evidence_scope": dict(EVIDENCE_SCOPE),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-check portfolio-home risk tensor warnings against DuckDB facts.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument(
        "--require-consistent",
        action="store_true",
        help="Return non-zero unless warning text matches recomputed fact evidence.",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless risk tensor warning evidence is decision-clean.",
    )
    args = parser.parse_args(argv)

    evidence = build_evidence(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if args.require_consistent and evidence["warning_consistency_status"] != "consistent":
        return 1
    if args.require_clean and evidence["decision_status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
