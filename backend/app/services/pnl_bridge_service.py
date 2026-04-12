from __future__ import annotations

from decimal import Decimal

import duckdb

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.core_finance.pnl_bridge import PnlBridgeRow, build_pnl_bridge_rows
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.pnl_bridge import (
    PnlBridgePayload,
    PnlBridgeRowSchema,
    PnlBridgeSummarySchema,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)
from backend.app.tasks.pnl_materialize import CACHE_KEY as PNL_CACHE_KEY
from backend.app.tasks.pnl_materialize import PNL_RESULT_CACHE_VERSION
from backend.app.tasks.balance_analysis_materialize import (
    CACHE_KEY as BALANCE_ANALYSIS_CACHE_KEY,
    CACHE_VERSION as BALANCE_ANALYSIS_CACHE_VERSION,
    RULE_VERSION as BALANCE_ANALYSIS_RULE_VERSION,
)


PHASE3_WARNING = (
    "Phase 3 required: roll_down / treasury_curve / credit_spread / fx_translation are fixed at 0 in the start pack."
)
BRIDGE_CACHE_VERSION = (
    f"cv_pnl_bridge_start_pack_v1__{PNL_RESULT_CACHE_VERSION}__{BALANCE_ANALYSIS_CACHE_VERSION}"
)
ZERO = Decimal("0")

_BALANCE_COLUMNS = [
    "report_date", "instrument_code", "instrument_name", "portfolio_name",
    "cost_center", "asset_class", "bond_type", "issuer_name", "industry_name",
    "rating", "invest_type_std", "accounting_basis", "position_scope",
    "currency_basis", "currency_code", "face_value_amount", "market_value_amount",
    "amortized_cost_amount", "accrued_interest_amount", "coupon_rate", "ytm_value",
    "maturity_date", "interest_mode", "is_issuance_like", "source_version",
    "rule_version", "ingest_batch_id", "trace_id",
]


def pnl_bridge_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    pnl_repo = PnlRepository(duckdb_path)
    if report_date not in pnl_repo.list_formal_fi_report_dates():
        raise ValueError(f"No pnl bridge data found for report_date={report_date} in fact_formal_pnl_fi.")

    pnl_fi_rows = pnl_repo.fetch_formal_fi_rows(report_date)
    current_balance_rows = _load_balance_rows_direct(duckdb_path, report_date)
    prior_date = _resolve_prior_report_date_direct(duckdb_path, report_date)
    prior_balance_rows = _load_balance_rows_direct(duckdb_path, prior_date) if prior_date else []

    rows = build_pnl_bridge_rows(
        pnl_fi_rows=pnl_fi_rows,
        balance_rows_current=current_balance_rows,
        balance_rows_prior=prior_balance_rows,
    )
    summary = _build_summary(rows)
    lineage, lineage_warnings = _resolve_bridge_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
        prior_report_date=prior_date,
        current_balance_rows=current_balance_rows,
        prior_balance_rows=prior_balance_rows,
    )
    payload = PnlBridgePayload(
        report_date=report_date,
        rows=[PnlBridgeRowSchema.model_validate(row) for row in rows],
        summary=summary,
        warnings=_build_warnings(
            current_balance_rows=current_balance_rows,
            prior_balance_rows=prior_balance_rows,
            prior_report_date=prior_date,
        )
        + lineage_warnings,
    )
    result_meta = build_formal_result_meta(
        trace_id=f"tr_pnl_bridge_{report_date}",
        result_kind="pnl.bridge",
        cache_version=BRIDGE_CACHE_VERSION,
        source_version=str(lineage["source_version"]),
        rule_version=str(lineage["rule_version"]),
        vendor_version=str(lineage["vendor_version"]),
    ).model_copy(update={"quality_flag": summary.quality_flag})
    return build_formal_result_envelope(
        result_meta=result_meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _load_balance_rows_direct(duckdb_path: str, report_date: str) -> list[dict[str, object]]:
    """Read balance rows directly from DuckDB without importing BalanceAnalysisRepository."""
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            if not _table_exists(conn, "fact_formal_zqtz_balance_daily"):
                return []
            raw = conn.execute(
                f"""
                select {", ".join(_BALANCE_COLUMNS)}
                from fact_formal_zqtz_balance_daily
                where report_date = ?
                  and position_scope = 'asset'
                  and currency_basis = 'CNY'
                order by instrument_code, portfolio_name, cost_center
                """,
                [report_date],
            ).fetchall()
        finally:
            conn.close()
    except OSError as exc:
        raise RuntimeError("Formal balance storage is unavailable for pnl.bridge.") from exc
    except duckdb.Error as exc:
        raise RuntimeError("Formal balance query failed for pnl.bridge.") from exc
    return [dict(zip(_BALANCE_COLUMNS, row, strict=True)) for row in raw]


def _resolve_prior_report_date_direct(duckdb_path: str, report_date: str) -> str | None:
    """Find the most recent balance report_date before the given date."""
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            if not _table_exists(conn, "fact_formal_zqtz_balance_daily"):
                return None
            rows = conn.execute(
                """
                select distinct cast(report_date as varchar) as rd
                from fact_formal_zqtz_balance_daily
                where cast(report_date as varchar) < ?
                  and position_scope = 'asset'
                  and currency_basis = 'CNY'
                order by rd desc
                limit 1
                """,
                [report_date],
            ).fetchall()
        finally:
            conn.close()
    except OSError as exc:
        raise RuntimeError("Formal balance storage is unavailable for pnl.bridge.") from exc
    except duckdb.Error as exc:
        raise RuntimeError("Formal balance query failed for pnl.bridge.") from exc
    return str(rows[0][0]) if rows else None


def _build_summary(rows: list[PnlBridgeRow]) -> PnlBridgeSummarySchema:
    ok_count = sum(1 for row in rows if row.quality_flag == "ok")
    warning_count = sum(1 for row in rows if row.quality_flag == "warning")
    error_count = sum(1 for row in rows if row.quality_flag == "error")
    worst_quality = "ok"
    if any(row.quality_flag == "error" for row in rows):
        worst_quality = "error"
    elif any(row.quality_flag == "warning" for row in rows):
        worst_quality = "warning"

    return PnlBridgeSummarySchema(
        row_count=len(rows),
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
        total_beginning_dirty_mv=sum((row.beginning_dirty_mv for row in rows), ZERO),
        total_ending_dirty_mv=sum((row.ending_dirty_mv for row in rows), ZERO),
        total_carry=sum((row.carry for row in rows), ZERO),
        total_roll_down=sum((row.roll_down for row in rows), ZERO),
        total_treasury_curve=sum((row.treasury_curve for row in rows), ZERO),
        total_credit_spread=sum((row.credit_spread for row in rows), ZERO),
        total_fx_translation=sum((row.fx_translation for row in rows), ZERO),
        total_realized_trading=sum((row.realized_trading for row in rows), ZERO),
        total_unrealized_fv=sum((row.unrealized_fv for row in rows), ZERO),
        total_manual_adjustment=sum((row.manual_adjustment for row in rows), ZERO),
        total_explained_pnl=sum((row.explained_pnl for row in rows), ZERO),
        total_actual_pnl=sum((row.actual_pnl for row in rows), ZERO),
        total_residual=sum((row.residual for row in rows), ZERO),
        quality_flag=worst_quality,
    )


def _build_warnings(
    *,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
    prior_report_date: str | None,
) -> list[str]:
    warnings = [PHASE3_WARNING]
    if not current_balance_rows:
        warnings.append(
            "Current balance rows unavailable; ending_dirty_mv defaults to 0 where balance data is missing."
        )
    if prior_report_date is None:
        warnings.append(
            "No prior balance report date found; beginning_dirty_mv defaults to 0 where prior balance data is missing."
        )
    elif not prior_balance_rows:
        warnings.append(
            f"Prior balance rows unavailable for report_date={prior_report_date}; beginning_dirty_mv defaults to 0 where prior balance data is missing."
        )
    return warnings


def _resolve_bridge_lineage(
    *,
    governance_dir: str,
    report_date: str,
    prior_report_date: str | None,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
) -> tuple[dict[str, str], list[str]]:
    pnl_lineage = _resolve_pnl_manifest_lineage(governance_dir)
    current_build = _resolve_balance_build_lineage(governance_dir, report_date=report_date)
    prior_build = (
        _resolve_balance_build_lineage(governance_dir, report_date=prior_report_date)
        if prior_report_date is not None
        else None
    )

    warnings: list[str] = []
    current_balance_lineage, used_current_fallback = _resolve_balance_lineage_component(
        build_lineage=current_build,
        balance_rows=current_balance_rows,
    )
    prior_balance_lineage, used_prior_fallback = _resolve_balance_lineage_component(
        build_lineage=prior_build,
        balance_rows=prior_balance_rows,
    )

    if used_current_fallback:
        warnings.append(
            f"Balance lineage fallback used for report_date={report_date}; completed balance-analysis build record unavailable."
        )
    if used_prior_fallback and prior_report_date is not None:
        warnings.append(
            f"Balance lineage fallback used for prior_report_date={prior_report_date}; completed balance-analysis build record unavailable."
        )

    return (
        {
            "source_version": _merge_lineage_values(
                str(pnl_lineage["source_version"]),
                current_balance_lineage["source_version"],
                prior_balance_lineage["source_version"],
            ),
            "rule_version": _merge_lineage_values(
                str(pnl_lineage["rule_version"]),
                current_balance_lineage["rule_version"],
                prior_balance_lineage["rule_version"],
            ),
            "vendor_version": _merge_lineage_values(
                str(pnl_lineage["vendor_version"]),
                current_balance_lineage["vendor_version"],
                prior_balance_lineage["vendor_version"],
            )
            or "vv_none",
        },
        warnings,
    )


def _resolve_balance_build_lineage(
    governance_dir: str,
    *,
    report_date: str,
) -> dict[str, object] | None:
    rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    matches = [
        row
        for row in rows
        if str(row.get("cache_key")) == BALANCE_ANALYSIS_CACHE_KEY
        and str(row.get("job_name")) == "balance_analysis_materialize"
        and str(row.get("status")) == "completed"
        and str(row.get("report_date")) == report_date
    ]
    return matches[-1] if matches else None


def _resolve_balance_lineage_component(
    *,
    build_lineage: dict[str, object] | None,
    balance_rows: list[dict[str, object]],
) -> tuple[dict[str, str], bool]:
    if build_lineage is not None:
        return (
            {
                "source_version": str(build_lineage.get("source_version") or ""),
                "rule_version": str(build_lineage.get("rule_version") or BALANCE_ANALYSIS_RULE_VERSION),
                "vendor_version": str(build_lineage.get("vendor_version") or "vv_none"),
            },
            False,
        )

    source_version = _merge_lineage_values(
        *[
            str(row.get("source_version") or "").strip()
            for row in balance_rows
            if str(row.get("source_version") or "").strip()
        ]
    )
    rule_version = _merge_lineage_values(
        *[
            str(row.get("rule_version") or "").strip()
            for row in balance_rows
            if str(row.get("rule_version") or "").strip()
        ]
    ) or BALANCE_ANALYSIS_RULE_VERSION
    if not balance_rows:
        return {"source_version": "", "rule_version": "", "vendor_version": ""}, False
    return (
        {
            "source_version": source_version,
            "rule_version": rule_version,
            "vendor_version": "vv_none",
        },
        True,
    )


def _merge_lineage_values(*values: str) -> str:
    merged = sorted({value.strip() for value in values if value and value.strip()})
    return "__".join(merged)


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None


def _resolve_pnl_manifest_lineage(governance_dir: str) -> dict[str, object]:
    rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_MANIFEST_STREAM)
    matches = [row for row in rows if str(row.get("cache_key")) == PNL_CACHE_KEY]
    if not matches:
        raise RuntimeError(f"Canonical pnl lineage unavailable for cache_key={PNL_CACHE_KEY}.")
    latest = matches[-1]
    required = ("source_version", "vendor_version", "rule_version")
    missing = [key for key in required if key not in latest or latest.get(key) in (None, "")]
    if missing:
        raise RuntimeError(
            f"Canonical pnl lineage malformed for cache_key={PNL_CACHE_KEY}: missing {', '.join(missing)}."
        )
    return latest
