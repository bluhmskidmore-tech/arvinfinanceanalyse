"""Formal read-only term-structure of materialized yield curves (1Y–30Y ladder)."""
from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.yield_curve_repo import (
    YIELD_CURVE_LATEST_FALLBACK_PREFIX,
    YieldCurveRepository,
)
from backend.app.schemas.common_numeric import numeric_from_raw
from backend.app.schemas.yield_curve_term_structure import (
    YieldCurveTermPoint,
    YieldCurveTermStructureCurve,
    YieldCurveTermStructureResponse,
)
from backend.app.services.formal_result_runtime import build_formal_result_envelope, build_formal_result_meta
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache

# Display axis only — must match tenor strings in `fact_formal_yield_curve_daily` / `yield_curve_daily`.
YIELD_CURVE_TERM_STRUCTURE_TENORS: tuple[str, ...] = (
    "1Y",
    "2Y",
    "3Y",
    "5Y",
    "7Y",
    "10Y",
    "20Y",
    "30Y",
)

# Aligns with `backend.app.tasks.yield_curve_materialize.SUPPORTED_CURVE_TYPES` (no task import to avoid side effects).
SUPPORTED_YIELD_CURVE_TYPES_FOR_TERM_STRUCTURE: tuple[str, ...] = ("treasury", "cdb", "aaa_credit")

CACHE_VERSION = "cv_yield_curve_term_structure_formal_v1"
RULE_VERSION_STABLE = "rv_yield_curve_term_structure_read_v1"
EMPTY_SOURCE_VERSION = "sv_yield_curve_term_structure_empty"
RESULT_KIND = "bond_analytics.yield_curve_term_structure"
FACT_TABLE = "fact_formal_yield_curve_daily"

_TERM_STRUCTURE_CACHE_TTL_SECONDS = 300.0
_TermStructureCacheKey = tuple[object, ...]
_TERM_STRUCTURE_CACHE: InMemoryTTLCache[_TermStructureCacheKey, dict] = get_runtime_cache(
    "yield_curve.term_structure",
    ttl_seconds=_TERM_STRUCTURE_CACHE_TTL_SECONDS,
)


def _term_structure_cache_key(
    duckdb_path: str,
    report_date: date,
    curve_types: tuple[str, ...],
) -> _TermStructureCacheKey | None:
    """Cache key bound to the DuckDB file identity; returns None when uncacheable.

    Folds the WAL mtime in (like duckdb_repo.catalog_presence_cached) so
    un-checkpointed writes invalidate the entry before the next checkpoint.
    """
    path = Path(duckdb_path)
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
        size = stat.st_size
        resolved = str(path.resolve())
    except OSError:
        return None
    try:
        mtime_ns = max(mtime_ns, Path(f"{duckdb_path}.wal").stat().st_mtime_ns)
    except OSError:
        pass
    return (
        RESULT_KIND,
        CACHE_VERSION,
        resolved,
        mtime_ns,
        size,
        report_date.isoformat(),
        curve_types,
    )


def _with_fresh_trace(envelope: dict) -> dict:
    response = deepcopy(envelope)
    meta = response.get("result_meta")
    if isinstance(meta, dict):
        meta["trace_id"] = _trace_id()
    return response


def _trace_id() -> str:
    return str(uuid.uuid4())


def _merge_lineage_str(*values: str) -> str:
    return "__".join(sorted({v.strip() for v in values if v and v.strip()}))


def get_yield_curve_term_structure(*, report_date: date, curve_types: tuple[str, ...]) -> dict:
    path = str(get_settings().duckdb_path)
    cache_key = _term_structure_cache_key(path, report_date, curve_types)
    if cache_key is None:
        return _compute_yield_curve_term_structure(path=path, report_date=report_date, curve_types=curve_types)
    envelope = _TERM_STRUCTURE_CACHE.get_or_set(
        cache_key,
        lambda: _compute_yield_curve_term_structure(
            path=path,
            report_date=report_date,
            curve_types=curve_types,
        ),
    )
    return _with_fresh_trace(envelope)


def _compute_yield_curve_term_structure(
    *,
    path: str,
    report_date: date,
    curve_types: tuple[str, ...],
) -> dict:
    repo = YieldCurveRepository(path)
    requested = report_date.isoformat()
    snapshot_results = repo.resolve_curve_snapshots_many(
        [(requested, curve_type) for curve_type in curve_types]
    )
    prior_date_requests: list[tuple[str, str]] = []
    for curve_type in curve_types:
        snapshot, _warning = snapshot_results.get((requested, curve_type), (None, None))
        if snapshot is None:
            continue
        td_resolved = str(snapshot.get("trade_date") or "")
        if td_resolved:
            prior_date_requests.append((curve_type, td_resolved))
    prior_dates = repo.fetch_prior_trade_dates_many(prior_date_requests)
    prior_snapshot_keys = [
        (prior_date, curve_type)
        for (curve_type, _trade_date), prior_date in prior_dates.items()
        if prior_date
    ]
    prior_snapshots = repo.fetch_curve_snapshots_many(prior_snapshot_keys)
    warnings: list[str] = []
    curves_out: list[YieldCurveTermStructureCurve] = []
    source_parts: list[str] = []
    rule_parts: list[str] = []
    vendor_parts: list[str] = []
    any_fallback = False
    all_missing = True

    for curve_type in curve_types:
        snapshot, w_curve = snapshot_results.get(
            (requested, curve_type),
            (None, f"No {curve_type} curve available for requested trade_date={requested}."),
        )
        if w_curve:
            warnings.append(w_curve)
        if w_curve and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w_curve:
            any_fallback = True

        prev_snap: dict[str, object] | None = None
        if snapshot is not None:
            all_missing = False
            td_resolved = str(snapshot.get("trade_date") or "")
            source_parts.append(str(snapshot.get("source_version") or ""))
            rule_parts.append(str(snapshot.get("rule_version") or ""))
            vendor_parts.append(str(snapshot.get("vendor_version") or ""))
            prior_td = prior_dates.get((curve_type, td_resolved)) if td_resolved else None
            if prior_td is not None:
                prev_snap = prior_snapshots.get((prior_td, curve_type))
        else:
            td_resolved = None

        curve_map: dict[str, Decimal] = (
            dict(snapshot["curve"])  # type: ignore[arg-type]
            if snapshot and isinstance(snapshot.get("curve"), dict)
            else {}
        )
        prev_map: dict[str, Decimal] = (
            dict(prev_snap["curve"])  # type: ignore[arg-type]
            if prev_snap and isinstance(prev_snap.get("curve"), dict)
            else {}
        )

        points: list[YieldCurveTermPoint] = []
        for tenor in YIELD_CURVE_TERM_STRUCTURE_TENORS:
            y_now = curve_map.get(tenor)
            y_prev = prev_map.get(tenor) if prev_map else None
            yld = None
            if y_now is not None:
                # `rate_pct` is percent-points (2.15 == 2.15%); declare it so
                # sub-1% yields are not misread as decimal ratios.
                yld = numeric_from_raw(
                    raw=float(y_now),
                    unit="pct",
                    precision=2,
                    sign_aware=True,
                    raw_scale="percent",
                )
            delta = None
            if y_now is not None and y_prev is not None:
                d = (y_now - y_prev) * Decimal("100")
                delta = numeric_from_raw(
                    raw=float(d),
                    unit="bp",
                    precision=2,
                    sign_aware=True,
                )
            points.append(
                YieldCurveTermPoint(
                    tenor=tenor,
                    yield_pct=yld,
                    delta_bp_prev=delta,
                )
            )

        curves_out.append(
            YieldCurveTermStructureCurve(
                curve_type=curve_type,
                trade_date_requested=requested,
                trade_date_resolved=td_resolved or None,
                points=points,
                source_version=str((snapshot or {}).get("source_version") or "") if snapshot else "",
                rule_version=str((snapshot or {}).get("rule_version") or "") if snapshot else "",
                vendor_name=str((snapshot or {}).get("vendor_name") or "") if snapshot else "",
                vendor_version=str((snapshot or {}).get("vendor_version") or "") if snapshot else "",
            )
        )
    if all_missing and curve_types:
        warnings.append("No yield curve snapshots available for the requested report_date and curve types.")

    meta = build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=_merge_lineage_str(*source_parts) or EMPTY_SOURCE_VERSION,
        rule_version=_merge_lineage_str(RULE_VERSION_STABLE, *rule_parts) or RULE_VERSION_STABLE,
        vendor_version=_merge_lineage_str(*vendor_parts) or "vv_none",
        quality_flag="warning" if warnings else "ok",
        vendor_status="vendor_stale" if any_fallback else ("vendor_unavailable" if all_missing else "ok"),
        fallback_mode="latest_snapshot" if any_fallback else "none",
        tables_used=[FACT_TABLE],
        filters_applied={"report_date": requested, "curve_types": list(curve_types)},
        source_surface="bond_analytics",
    )
    if any_fallback:
        meta = meta.model_copy(
            update={
                "quality_flag": "stale",
            }
        )

    payload = YieldCurveTermStructureResponse(
        report_date=report_date,
        curves=curves_out,
        warnings=warnings,
        computed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def parse_curve_types_param(raw: str) -> tuple[str, ...]:
    items = [p.strip().lower() for p in raw.split(",") if p.strip()]
    if not items:
        return ("treasury", "cdb")
    unknown = sorted({x for x in items if x not in SUPPORTED_YIELD_CURVE_TYPES_FOR_TERM_STRUCTURE})
    if unknown:
        raise ValueError(f"Unsupported curve_type(s): {', '.join(unknown)}")
    return tuple(items)
