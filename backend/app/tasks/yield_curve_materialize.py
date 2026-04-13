from __future__ import annotations

from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path

import duckdb

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.settings import get_settings
from backend.app.repositories.akshare_adapter import (
    VendorAdapter,
    _prepare_curve_points,
)
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize


YIELD_CURVE_MODULE = ensure_formal_module(
    FormalComputeModuleDescriptor(
        module_name="yield_curve",
        basis="formal",
        input_sources=("akshare_yield_curve", "choice_yield_curve", "choice_macro_snapshot", "chinabond_gkh_yield_curve"),
        fact_tables=("fact_formal_yield_curve_daily",),
        rule_version="rv_yield_curve_formal_materialize_v1",
        cache_key_prefix="yield_curve:materialize",
        lock_key_prefix="lock:duckdb:{basis}:yield-curve:materialize",
        cache_version_prefix="cv_yield_curve",
        result_kind_family="yield-curve",
        supports_standard_queries=True,
        supports_custom_queries=False,
    )
)
CACHE_KEY = YIELD_CURVE_MODULE.cache_key
RULE_VERSION = YIELD_CURVE_MODULE.rule_version
CACHE_VERSION = YIELD_CURVE_MODULE.cache_version

SUPPORTED_CURVE_TYPES = ("treasury", "cdb", "aaa_credit")
MAX_BACKTRACK_DAYS = 40


def _normalize_curve_types(curve_types: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(str(curve_type).strip().lower() for curve_type in curve_types)
    unsupported = sorted({curve_type for curve_type in normalized if curve_type not in SUPPORTED_CURVE_TYPES})
    if unsupported:
        joined = ", ".join(unsupported)
        raise FormalComputeMaterializeFailure(
            source_version=f"sv_yield_curve_failed_unsupported_{joined.replace(',', '_').replace(' ', '')}",
            vendor_version="vv_none",
            message=f"Unsupported curve_type(s) for yield-curve / curve-effects stream: {joined}",
        )
    return normalized


def _execute_yield_curve_materialization(
    *,
    trade_date: str,
    curve_types: tuple[str, ...],
    duckdb_file: Path,
) -> FormalComputeMaterializeResult:
    curve_types = _normalize_curve_types(curve_types)
    adapter = VendorAdapter()
    repo = YieldCurveRepository(str(duckdb_file))

    snapshots = []
    for curve_type in curve_types:
        try:
            if curve_type == "aaa_credit":
                # Choice primary: landed DuckDB macro first, then live Choice EDB, then exact-family AkShare only.
                snapshot = _load_aaa_credit_curve_from_choice_snapshot(
                    duckdb_path=str(duckdb_file),
                    trade_date=trade_date,
                )
                if snapshot is None:
                    snapshot = adapter._fetch_choice_curve(curve_type="aaa_credit", trade_date=trade_date)
                if snapshot is None:
                    snapshot = adapter._fetch_akshare_curve(curve_type=curve_type, trade_date=trade_date)
                    if snapshot is None:
                        raise RuntimeError(
                            "No aaa_credit curve: Choice (landed or live) and AkShare enterprise-AAA family both unavailable."
                        )
                snapshots.append(snapshot)
            else:
                snapshots.append(adapter.fetch_yield_curve(curve_type=curve_type, trade_date=trade_date))
        except Exception as exc:
            raise FormalComputeMaterializeFailure(
                source_version=f"sv_yield_curve_failed_{trade_date.replace('-', '')}_{curve_type}",
                vendor_version="vv_none",
                message=f"Failed to materialize {curve_type} curve for trade_date={trade_date}: {exc}",
            ) from exc

    repo.replace_curve_snapshots(
        trade_date=trade_date,
        snapshots=snapshots,
        rule_version=RULE_VERSION,
    )

    source_version = "__".join(sorted({snapshot.source_version for snapshot in snapshots})) or "sv_yield_curve_empty"
    vendor_version = "__".join(sorted({snapshot.vendor_version for snapshot in snapshots})) or "vv_none"
    payload = {
        "curve_types": list(curve_types),
        "point_count": sum(len(snapshot.points) for snapshot in snapshots),
    }
    return FormalComputeMaterializeResult(
        source_version=source_version,
        vendor_version=vendor_version,
        payload=payload,
    )


def ensure_yield_curve_inputs_on_or_before(
    *,
    anchor_dates: tuple[str, ...],
    duckdb_path: str,
    curve_types: tuple[str, ...] = SUPPORTED_CURVE_TYPES,
    max_backtrack_days: int = MAX_BACKTRACK_DAYS,
) -> None:
    normalized_anchor_dates = tuple(sorted({str(value).strip() for value in anchor_dates if str(value).strip()}))
    normalized_curve_types = _normalize_curve_types(curve_types)
    if not normalized_anchor_dates or not normalized_curve_types:
        return

    adapter = VendorAdapter()
    repo = YieldCurveRepository(duckdb_path)
    for anchor_date in normalized_anchor_dates:
        for curve_type in normalized_curve_types:
            if repo.fetch_curve_snapshot(anchor_date, curve_type) is not None:
                continue
            try:
                snapshot = _fetch_curve_snapshot_on_or_before(
                    adapter=adapter,
                    curve_type=curve_type,
                    anchor_date=anchor_date,
                    max_backtrack_days=max_backtrack_days,
                )
            except Exception:
                if repo.fetch_latest_trade_date_on_or_before(curve_type, anchor_date) is not None:
                    continue
                raise
            repo.replace_curve_snapshots(
                trade_date=snapshot.trade_date,
                snapshots=[snapshot],
                rule_version=RULE_VERSION,
            )


def _fetch_curve_snapshot_on_or_before(
    *,
    adapter: VendorAdapter,
    curve_type: str,
    anchor_date: str,
    max_backtrack_days: int,
) -> YieldCurveSnapshot:
    anchor = date.fromisoformat(anchor_date)
    last_error: Exception | None = None
    for offset in range(max_backtrack_days + 1):
        candidate_date = (anchor - timedelta(days=offset)).isoformat()
        try:
            return adapter.fetch_yield_curve(curve_type=curve_type, trade_date=candidate_date)
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"No {curve_type} curve snapshot found on or before {anchor_date}.")


def _materialize_yield_curve(
    *,
    trade_date: str,
    curve_types: list[str] | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    normalized_curve_types = tuple(curve_types or SUPPORTED_CURVE_TYPES)

    return run_formal_materialize(
        descriptor=YIELD_CURVE_MODULE,
        job_name="yield_curve_materialize",
        report_date=trade_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        run_id=run_id,
        execute_materialization=lambda: _execute_yield_curve_materialization(
            trade_date=trade_date,
            curve_types=normalized_curve_types,
            duckdb_file=duckdb_file,
        ),
    )


materialize_yield_curve = register_actor_once(
    "materialize_yield_curve",
    _materialize_yield_curve,
)


AAA_CREDIT_CHOICE_PREFIX = "中债企业债到期收益率(AAA):"
AAA_CREDIT_TENOR_MAP = {
    "6个月": "6M",
    "1年": "1Y",
    "2年": "2Y",
    "3年": "3Y",
    "4年": "4Y",
    "5年": "5Y",
    "6年": "6Y",
    "10年": "10Y",
}


def _load_aaa_credit_curve_from_choice_snapshot(
    *,
    duckdb_path: str,
    trade_date: str,
) -> object | None:
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
    except duckdb.Error:
        return None
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "phase1_macro_vendor_catalog" not in tables:
            return None
        snapshot_rows = []
        fact_rows = []
        if "choice_market_snapshot" in tables:
            snapshot_rows = conn.execute(
                """
                select
                  cat.series_name,
                  snap.value_numeric,
                  snap.vendor_name,
                  snap.vendor_version,
                  snap.source_version
                from choice_market_snapshot as snap
                inner join phase1_macro_vendor_catalog as cat
                  on cat.series_id = snap.series_id
                where snap.trade_date = ?
                  and cat.series_name like ?
                order by cat.series_name
                """,
                [trade_date, f"{AAA_CREDIT_CHOICE_PREFIX}%"],
            ).fetchall()
        if "fact_choice_macro_daily" in tables:
            fact_rows = conn.execute(
                """
                select
                  cat.series_name,
                  fact.value_numeric,
                  cat.vendor_name,
                  fact.vendor_version,
                  fact.source_version
                from fact_choice_macro_daily as fact
                inner join phase1_macro_vendor_catalog as cat
                  on cat.series_id = fact.series_id
                where fact.trade_date = ?
                  and cat.series_name like ?
                order by cat.series_name
                """,
                [trade_date, f"{AAA_CREDIT_CHOICE_PREFIX}%"],
            ).fetchall()
    finally:
        conn.close()

    snapshot_error: Exception | None = None
    if snapshot_rows:
        try:
            return _build_aaa_credit_snapshot(rows=snapshot_rows, trade_date=trade_date)
        except Exception as exc:
            snapshot_error = exc
    if fact_rows:
        try:
            return _build_aaa_credit_snapshot(rows=fact_rows, trade_date=trade_date)
        except Exception:
            pass
    if snapshot_error is not None:
        raise snapshot_error
    return None


def _build_aaa_credit_snapshot(
    *,
    rows: list[tuple[object, ...]],
    trade_date: str,
) -> YieldCurveSnapshot | None:
    if not rows:
        return None

    vendor_names = {str(row[2] or "").strip() for row in rows}
    vendor_versions = {str(row[3] or "").strip() for row in rows}
    source_versions = {str(row[4] or "").strip() for row in rows}
    if len(vendor_names) != 1 or len(vendor_versions) != 1 or len(source_versions) != 1:
        raise RuntimeError("Choice aaa_credit snapshot lineage is inconsistent across tenors.")

    points: list[YieldCurvePoint] = []
    for series_name, value_numeric, _vendor_name, _vendor_version, _source_version in rows:
        suffix = str(series_name).split(":", 1)[-1].strip()
        tenor = AAA_CREDIT_TENOR_MAP.get(suffix)
        if tenor is None:
            continue
        points.append(
            YieldCurvePoint(
                tenor=tenor,
                rate_pct=Decimal(str(value_numeric)),
            )
        )
    if not points:
        return None

    points = _prepare_curve_points(curve_type="aaa_credit", points=points)
    return YieldCurveSnapshot(
        curve_type="aaa_credit",
        trade_date=trade_date,
        points=points,
        vendor_name=next(iter(vendor_names)) or "choice",
        vendor_version=next(iter(vendor_versions)) or "vv_none",
        source_version=next(iter(source_versions)) or "sv_choice_macro_missing",
    )
