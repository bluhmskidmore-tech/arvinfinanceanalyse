from __future__ import annotations

import math
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.core_finance.livermore_sector_rank import (
    SectorRankConstituent,
    compute_sector_rank,
)
from backend.app.repositories.livermore_market_read_repo import (
    LIVERMORE_STRATEGY_READS,
    RELATION_CHOICE_STOCK_UNIVERSE,
    TABLE_MEMBERSHIP,
    TABLE_OBS,
    LivermoreMarketReadRepository,
)
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RESULT_KIND = "market_data.stock_analysis.heavyweight_trends"
RULE_VERSION = "rv_stock_heavyweight_trend_v1"
CACHE_VERSION = "cv_stock_heavyweight_trend_v1"
EMPTY_SOURCE_VERSION = "sv_stock_heavyweight_trend_empty"
EMPTY_VENDOR_VERSION = "vv_none"

DEFAULT_WINDOW_DAYS = 20
DEFAULT_SECTOR_LIMIT = 8
DEFAULT_STOCKS_PER_SECTOR = 3

# cum_pct_changes[i] = (close[i] / close[0] - 1) * 100 over the stock's own
# observed sessions inside the window. It is a display-only normalization of
# the same close series that ships in close_values; it is not a formal return.
SERIES_BASIS = "cum_pct_from_first_close"
METRIC_NOTES = (
    "cum_pct_change: (close / first_close - 1) * 100 over the stock's observed sessions in the window; "
    "not compounded across suspensions and not a formal return metric",
    "suspended sessions are omitted from the stock series instead of being interpolated; "
    "compare point_count against window_trade_dates to size the gap",
)


def stock_heavyweight_trend_envelope(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    sector_limit: int = DEFAULT_SECTOR_LIMIT,
    stocks_per_sector: int = DEFAULT_STOCKS_PER_SECTOR,
) -> dict[str, object]:
    """Read-only close trends for the leader constituents of the ranked sectors.

    Reuses the workbench sector-rank inputs and ``compute_sector_rank`` so the
    returned stocks are the same leader constituents the workbench snapshot
    shows; only the close series is new. DuckDB access is SELECT-only.
    """
    requested_iso = None if as_of_date is None else as_of_date.isoformat()
    context = _EnvelopeContext(
        requested_as_of_date=requested_iso,
        window_days=window_days,
        sector_limit=sector_limit,
        stocks_per_sector=stocks_per_sector,
    )

    if not Path(duckdb_path).is_file():
        return _missing_envelope(context, reason_code="duckdb_missing")

    repo = LivermoreMarketReadRepository(duckdb_path, guard_path_exists=True)
    try:
        with repo.scoped_connection() as conn:
            if conn is None:
                return _missing_envelope(context, reason_code="duckdb_unavailable")

            tables = repo.list_table_names(conn=conn)
            if not {TABLE_MEMBERSHIP, TABLE_OBS}.issubset(tables):
                return _missing_envelope(context, reason_code="source_table_unavailable")

            end_bound = repo.resolve_global_end_trade_date(as_of_date=as_of_date, conn=conn)
            if end_bound is None:
                return _missing_envelope(context, reason_code="no_trade_date_available")
            context.resolved_as_of_date = end_bound.isoformat()

            constituents, source_versions, vendor_versions, tables_used = _load_sector_constituents(
                conn=conn,
                as_of_iso=end_bound.isoformat(),
                has_universe=RELATION_CHOICE_STOCK_UNIVERSE in tables,
            )
            if not constituents:
                return _missing_envelope(context, reason_code="sector_membership_missing")

            rank_result = compute_sector_rank(
                as_of_date=end_bound.isoformat(),
                rows=constituents,
                leader_constituents_per_sector=stocks_per_sector,
            )
            if not rank_result.ready or rank_result.payload is None:
                return _missing_envelope(context, reason_code="sector_rank_not_rankable")

            ranked_items = rank_result.payload.get("items")
            if not isinstance(ranked_items, list) or not ranked_items:
                return _missing_envelope(context, reason_code="sector_rank_not_rankable")

            selected = cast(list[dict[str, Any]], ranked_items)[: max(1, sector_limit)]
            stock_codes = _distinct_leader_codes(selected)
            if not stock_codes:
                return _missing_envelope(context, reason_code="leader_constituents_missing")

            # The 1.6x calendar buffer covers weekends plus a short holiday; a longer
            # break simply yields fewer sessions, which is reported as a shortfall.
            calendar_span = int(math.ceil(max(1, window_days) * 1.6)) + 7
            window_dates = repo.fetch_trade_dates_in_range(
                end_inclusive=end_bound,
                start_inclusive=end_bound - timedelta(days=calendar_span),
                limit_last_n=max(1, window_days),
                conn=conn,
            )
            if not window_dates:
                return _missing_envelope(context, reason_code="no_trade_date_available")

            history_rows = LIVERMORE_STRATEGY_READS.fetch_dated_close_history_rows(
                stock_codes=stock_codes,
                start_trade_date=window_dates[0].isoformat(),
                end_trade_date=end_bound.isoformat(),
                conn=conn,
            )
    except (OSError, duckdb.Error):
        # A writer holding the file or a schema drift must degrade to an empty
        # card, never a 500 on a read-only analytical surface.
        return _missing_envelope(context, reason_code="duckdb_read_failed")

    window_iso = [day.isoformat() for day in window_dates]
    window_iso_set = set(window_iso)
    history_by_code = _group_history_by_code(history_rows, allowed_dates=window_iso_set)
    for row in history_rows:
        if row[4]:
            source_versions.append(str(row[4]))
        if row[5]:
            vendor_versions.append(str(row[5]))

    sectors: list[dict[str, object]] = []
    stock_count = 0
    stock_with_series_count = 0
    for item in selected:
        leaders = item.get("leader_constituents")
        leader_rows = leaders if isinstance(leaders, list) else []
        stocks: list[dict[str, object]] = []
        for leader in cast(list[dict[str, Any]], leader_rows):
            stock_code = str(leader.get("stock_code") or "").strip()
            if not stock_code:
                continue
            stock_count += 1
            series = _build_stock_series(
                points=history_by_code.get(stock_code, []),
                window_size=len(window_iso),
            )
            if series["trend_state"] != "missing":
                stock_with_series_count += 1
            stocks.append(
                {
                    "rank": _optional_int(leader.get("rank")),
                    "stock_code": stock_code,
                    "stock_name": str(leader.get("stock_name") or "").strip() or stock_code,
                    "pctchange": _optional_float(leader.get("pctchange")),
                    "turn": _optional_float(leader.get("turn")),
                    **series,
                }
            )
        sectors.append(
            {
                "sector_code": str(item.get("sector_code") or "").strip(),
                "sector_name": str(item.get("sector_name") or "").strip(),
                "sector_rank": _optional_int(item.get("rank")),
                "stocks": stocks,
            }
        )

    warnings: list[str] = []
    if len(window_iso) < window_days:
        warnings.append(
            f"window_shortfall: only {len(window_iso)} trade dates available within the "
            f"{calendar_span}-calendar-day lookback buffer; requested window_days={window_days}"
        )
    missing_series_count = stock_count - stock_with_series_count
    if missing_series_count > 0:
        warnings.append(
            f"stock_series_missing: {missing_series_count} of {stock_count} heavyweight stocks "
            "have no tradable close inside the window"
        )

    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": "ok",
        "contract_status": "observational_only",
        "formal_use_allowed": False,
        "requested_as_of_date": requested_iso,
        "as_of_date": end_bound.isoformat(),
        "window_days": window_days,
        "sector_limit": sector_limit,
        "stocks_per_sector": stocks_per_sector,
        "series_basis": SERIES_BASIS,
        "window_trade_dates": window_iso,
        "sectors": sectors,
        "coverage": {
            "sector_count": len(sectors),
            "stock_count": stock_count,
            "stock_with_series_count": stock_with_series_count,
            "stock_missing_series_count": missing_series_count,
            "window_trade_date_count": len(window_iso),
        },
        "metric_notes": list(METRIC_NOTES),
        "warnings": warnings,
    }

    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_heavyweight_trend_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=_aggregate_lineage(source_versions, empty_value=EMPTY_SOURCE_VERSION),
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning" if warnings else "ok"),
        vendor_version=_aggregate_lineage(vendor_versions, empty_value=EMPTY_VENDOR_VERSION),
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": requested_iso,
            "as_of_date": end_bound.isoformat(),
            "window_days": window_days,
            "sector_limit": sector_limit,
            "stocks_per_sector": stocks_per_sector,
        },
        tables_used=tables_used,
        evidence_rows=len(history_rows),
        result_payload=result_payload,
    )


class _EnvelopeContext:
    """Request-scoped echo fields shared by the ok and missing envelopes."""

    def __init__(
        self,
        *,
        requested_as_of_date: str | None,
        window_days: int,
        sector_limit: int,
        stocks_per_sector: int,
    ) -> None:
        self.requested_as_of_date = requested_as_of_date
        self.window_days = window_days
        self.sector_limit = sector_limit
        self.stocks_per_sector = stocks_per_sector
        self.resolved_as_of_date: str | None = None


def _missing_envelope(context: _EnvelopeContext, *, reason_code: str) -> dict[str, object]:
    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": "missing",
        "contract_status": "observational_only",
        "formal_use_allowed": False,
        "requested_as_of_date": context.requested_as_of_date,
        "as_of_date": context.resolved_as_of_date,
        "window_days": context.window_days,
        "sector_limit": context.sector_limit,
        "stocks_per_sector": context.stocks_per_sector,
        "series_basis": SERIES_BASIS,
        "window_trade_dates": [],
        "sectors": [],
        "coverage": {
            "sector_count": 0,
            "stock_count": 0,
            "stock_with_series_count": 0,
            "stock_missing_series_count": 0,
            "window_trade_date_count": 0,
        },
        "metric_notes": list(METRIC_NOTES),
        "warnings": [reason_code],
        "reason_code": reason_code,
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_heavyweight_trend_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": context.requested_as_of_date,
            "as_of_date": context.resolved_as_of_date,
            "window_days": context.window_days,
            "sector_limit": context.sector_limit,
            "stocks_per_sector": context.stocks_per_sector,
        },
        tables_used=[TABLE_MEMBERSHIP, TABLE_OBS],
        evidence_rows=0,
        result_payload=result_payload,
    )


def _load_sector_constituents(
    *,
    conn: Any,
    as_of_iso: str,
    has_universe: bool,
) -> tuple[list[SectorRankConstituent], list[str], list[str], list[str]]:
    membership_snapshot_date = LIVERMORE_STRATEGY_READS.latest_snapshot_date_on_or_before(
        table_name=TABLE_MEMBERSHIP,
        column_name="as_of_date",
        as_of_date=as_of_iso,
        conn=conn,
    )
    if membership_snapshot_date is None:
        return [], [], [], [TABLE_MEMBERSHIP, TABLE_OBS]

    universe_snapshot_date = None
    if has_universe:
        universe_snapshot_date = LIVERMORE_STRATEGY_READS.latest_snapshot_date_on_or_before(
            table_name=RELATION_CHOICE_STOCK_UNIVERSE,
            column_name="as_of_date",
            as_of_date=as_of_iso,
            conn=conn,
        )

    rows = LIVERMORE_STRATEGY_READS.fetch_sector_rank_input_rows(
        as_of_date=as_of_iso,
        membership_snapshot_date=membership_snapshot_date,
        universe_snapshot_date=universe_snapshot_date,
        conn=conn,
    )
    constituents = [
        SectorRankConstituent(
            stock_code=str(row[0] or ""),
            sector_code=str(row[2] or ""),
            sector_name=str(row[3] or ""),
            pctchange=row[4],
            turn=row[5],
            amplitude=row[6],
            stock_name=str(row[1] or ""),
        )
        for row in rows
    ]
    source_versions = [str(value) for row in rows for value in (row[7], row[9]) if value]
    vendor_versions = [str(value) for row in rows for value in (row[8], row[10]) if value]
    tables_used = [TABLE_MEMBERSHIP, TABLE_OBS]
    if universe_snapshot_date is not None:
        tables_used.append(RELATION_CHOICE_STOCK_UNIVERSE)
    return constituents, source_versions, vendor_versions, tables_used


def _distinct_leader_codes(items: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for item in items:
        leaders = item.get("leader_constituents")
        if not isinstance(leaders, list):
            continue
        for leader in cast(list[dict[str, Any]], leaders):
            code = str(leader.get("stock_code") or "").strip()
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


def _group_history_by_code(
    rows: list[tuple[Any, ...]],
    *,
    allowed_dates: set[str],
) -> dict[str, list[tuple[str, float]]]:
    grouped: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        code = str(row[0] or "").strip()
        if not code:
            continue
        trade_date = _iso_date(row[1])
        if trade_date is None or trade_date not in allowed_dates:
            continue
        close_value = _optional_float(row[2])
        if close_value is None:
            continue
        grouped.setdefault(code, []).append((trade_date, close_value))
    for series in grouped.values():
        series.sort(key=lambda point: point[0])
    return grouped


def _build_stock_series(
    *,
    points: list[tuple[str, float]],
    window_size: int,
) -> dict[str, object]:
    if not points:
        return {
            "trade_dates": [],
            "close_values": [],
            "cum_pct_changes": [],
            "point_count": 0,
            "missing_point_count": window_size,
            "trend_state": "missing",
            "trend_note": "no_tradable_close_in_window",
            "window_return_pct": None,
        }

    base_close = points[0][1]
    if base_close <= 0:
        return {
            "trade_dates": [point[0] for point in points],
            "close_values": [round(point[1], 6) for point in points],
            "cum_pct_changes": [],
            "point_count": len(points),
            "missing_point_count": max(0, window_size - len(points)),
            "trend_state": "missing",
            "trend_note": "non_positive_base_close",
            "window_return_pct": None,
        }

    cum_pct = [round((point[1] / base_close - 1.0) * 100.0, 4) for point in points]
    missing = max(0, window_size - len(points))
    if len(points) < 2:
        trend_state = "insufficient"
        trend_note = "single_session_only"
    elif missing > 0:
        trend_state = "partial"
        trend_note = f"missing_{missing}_sessions"
    else:
        trend_state = "ok"
        trend_note = None
    return {
        "trade_dates": [point[0] for point in points],
        "close_values": [round(point[1], 6) for point in points],
        "cum_pct_changes": cum_pct,
        "point_count": len(points),
        "missing_point_count": missing,
        "trend_state": trend_state,
        "trend_note": trend_note,
        "window_return_pct": cum_pct[-1],
    }


def _iso_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_int(value: object) -> int | None:
    number = _optional_float(value)
    return None if number is None else int(number)


def _aggregate_lineage(values: list[str], *, empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)
