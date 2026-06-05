from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import uuid

from backend.app.core_finance.credit_spread_analysis import (
    BondSpreadRow,
    build_spread_term_structure,
    compute_bond_spreads,
    compute_spread_historical_context,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.yield_curve_repo import (
    YIELD_CURVE_LATEST_FALLBACK_PREFIX,
    YieldCurveRepository,
    resolve_curve_snapshot,
)
from backend.app.schemas.credit_spread_analysis import CreditSpreadAnalysisResponse
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)

ZERO = Decimal("0")
Q8 = Decimal("0.00000001")
CACHE_VERSION = "cv_credit_spread_analysis_formal_v1"
RULE_VERSION = "rv_credit_spread_analysis_formal_v1"
EMPTY_SOURCE_VERSION = "sv_credit_spread_analysis_empty"
EMPTY_WARNING = "Credit spread analysis facts not yet populated for requested report_date."


def get_credit_spread_analysis(report_date: date) -> dict:
    repo = BondAnalyticsRepository(str(get_settings().duckdb_path))
    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))

    credit_rows = repo.fetch_bond_analytics_rows(
        report_date=report_date.isoformat(),
        asset_class="credit",
    )
    curve_snapshot, curve_warning = resolve_curve_snapshot(
        curve_repo,
        requested_trade_date=report_date.isoformat(),
        curve_type="treasury",
    )
    spread_rows = compute_bond_spreads(
        credit_rows,
        curve_snapshot["curve"] if curve_snapshot else {},
    )
    weighted_avg_spread = _weighted_avg_spread(spread_rows)
    historical_spreads = _build_historical_spreads(
        repo=repo,
        curve_repo=curve_repo,
        requested_report_date=report_date,
    )
    historical_context = compute_spread_historical_context(weighted_avg_spread, historical_spreads)

    meta = build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind="credit_spread_analysis.detail",
        cache_version=CACHE_VERSION,
        source_version=_merge_values(
            *[str(row.get("source_version") or "").strip() for row in credit_rows],
            str((curve_snapshot or {}).get("source_version") or "").strip(),
        )
        or EMPTY_SOURCE_VERSION,
        rule_version=_merge_values(
            RULE_VERSION,
            *[str(row.get("rule_version") or "").strip() for row in credit_rows],
            str((curve_snapshot or {}).get("rule_version") or "").strip(),
        )
        or RULE_VERSION,
        vendor_version=str((curve_snapshot or {}).get("vendor_version") or "vv_none"),
    )
    if curve_snapshot is None and credit_rows:
        meta = meta.model_copy(
            update={
                "vendor_status": "vendor_unavailable",
                "fallback_mode": "none",
            }
        )
    elif curve_warning and YIELD_CURVE_LATEST_FALLBACK_PREFIX in curve_warning:
        meta = meta.model_copy(
            update={
                "vendor_status": "vendor_stale",
                "fallback_mode": "latest_snapshot",
            }
        )

    warnings: list[str] = []
    if not credit_rows:
        warnings.append(EMPTY_WARNING)
    if curve_warning:
        warnings.append(curve_warning)

    payload = CreditSpreadAnalysisResponse(
        report_date=report_date,
        credit_bond_count=len(spread_rows),
        total_credit_market_value=_text(sum((row.market_value for row in spread_rows), ZERO)),
        weighted_avg_spread_bps=_text(weighted_avg_spread),
        spread_term_structure=[asdict(point) for point in build_spread_term_structure(spread_rows)],
        top_spread_bonds=[asdict(row) for row in _sorted_spread_rows(spread_rows, reverse=True)[:10]],
        bottom_spread_bonds=[asdict(row) for row in _sorted_spread_rows(spread_rows, reverse=False)[:10]],
        historical_context=asdict(historical_context),
        warnings=warnings,
        computed_at=meta.generated_at.isoformat(),
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _build_historical_spreads(
    *,
    repo: BondAnalyticsRepository,
    curve_repo: YieldCurveRepository,
    requested_report_date: date,
) -> list[tuple[date, Decimal]]:
    historical: list[tuple[date, Decimal]] = []
    for report_date_text in repo.list_report_dates():
        try:
            point_date = date.fromisoformat(report_date_text)
        except ValueError:
            continue
        if point_date > requested_report_date:
            continue
        rows = repo.fetch_bond_analytics_rows(report_date=report_date_text, asset_class="credit")
        if not rows:
            continue
        curve_snapshot = curve_repo.fetch_curve_snapshot(report_date_text, "treasury")
        if curve_snapshot is None:
            if curve_repo.fetch_curve(report_date_text, "treasury"):
                raise RuntimeError(
                    f"Corrupt or inconsistent treasury curve snapshot lineage for trade_date={report_date_text}."
                )
            continue
        spread_rows = compute_bond_spreads(rows, curve_snapshot["curve"])
        if not spread_rows:
            continue
        historical.append((point_date, _weighted_avg_spread(spread_rows)))
    return sorted(historical, key=lambda item: item[0])


def _weighted_avg_spread(rows: list[BondSpreadRow]) -> Decimal:
    total_market_value = sum((row.market_value for row in rows), ZERO)
    if total_market_value == ZERO:
        return ZERO
    return _q8(
        sum((row.credit_spread * row.market_value for row in rows), ZERO) / total_market_value
    )


def _sorted_spread_rows(rows: list[BondSpreadRow], *, reverse: bool) -> list[BondSpreadRow]:
    if reverse:
        return sorted(rows, key=lambda row: (-row.credit_spread, row.instrument_code))
    return sorted(rows, key=lambda row: (row.credit_spread, row.instrument_code))


def _merge_values(*values: str) -> str:
    return "__".join(sorted({value for value in values if value}))


def _text(value: Decimal) -> str:
    return format(_q8(value), "f")


def _q8(value: Decimal) -> Decimal:
    return value.quantize(Q8, rounding=ROUND_HALF_UP)


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"
