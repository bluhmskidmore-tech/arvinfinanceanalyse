from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.settings import get_settings
from backend.app.repositories.akshare_adapter import (
    VendorAdapter,
    _prepare_curve_points,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize

logger = logging.getLogger(__name__)

YIELD_CURVE_MODULE = ensure_formal_module(
    FormalComputeModuleDescriptor(
        module_name="yield_curve",
        basis="formal",
        input_sources=("akshare_yield_curve", "choice_yield_curve", "choice_macro_snapshot", "chinabond_gkh_yield_curve"),
        fact_tables=("fact_formal_yield_curve_daily",),
        rule_version="rv_yield_curve_formal_materialize_v1",
        result_kind_family="yield-curve",
        supports_standard_queries=True,
        supports_custom_queries=False,
    )
)
CACHE_KEY = YIELD_CURVE_MODULE.cache_key
RULE_VERSION = YIELD_CURVE_MODULE.rule_version
CACHE_VERSION = YIELD_CURVE_MODULE.cache_version

SUPPORTED_CURVE_TYPES = ("treasury", "cdb", "aaa_credit")
# Extended types available on demand (Choice-only): spot rate curves and Shibor.
ALL_CURVE_TYPES = SUPPORTED_CURVE_TYPES + ("treasury_spot", "cdb_spot", "shibor")
MAX_BACKTRACK_DAYS = 40


def _normalize_curve_types(curve_types: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(str(curve_type).strip().lower() for curve_type in curve_types)
    unsupported = sorted({curve_type for curve_type in normalized if curve_type not in ALL_CURVE_TYPES})
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
            # Broad catch is intentional: any vendor fetch error (network, parse,
            # data quality) must be wrapped into FormalComputeMaterializeFailure so
            # the governance runtime can record a structured failure for this date.
            raise FormalComputeMaterializeFailure(
                source_version=f"sv_yield_curve_failed_{trade_date.replace('-', '')}_{curve_type}",
                vendor_version="vv_none",
                message=f"Failed to materialize {curve_type} curve for trade_date={trade_date}: {exc}",
            ) from exc

    with repository_task_write_scope(__name__):
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
                # Broad catch is intentional: if vendor fetch fails but we already have
                # a fallback curve inside the allowed backtrack window, silently
                # continue. Otherwise, re-raise to signal missing data.
                existing = _existing_curve_snapshot_on_or_before(
                    repo=repo,
                    anchor_date=anchor_date,
                    curve_type=curve_type,
                    max_backtrack_days=max_backtrack_days,
                )
                if existing is not None:
                    continue
                raise
            with repository_task_write_scope(__name__):
                repo.replace_curve_snapshots(
                    trade_date=snapshot.trade_date,
                    snapshots=[snapshot],
                    rule_version=RULE_VERSION,
                )


def list_yield_curve_month_end_anchors(
    *,
    duckdb_path: str,
    start_date: str,
    end_date: str,
) -> list[str]:
    """Return last available balance report date per month for governed curve backfills."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date.")

    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = 'zqtz_bond_daily_snapshot'
            limit 1
            """
        ).fetchone()
        if row is None:
            raise RuntimeError("DuckDB is missing table zqtz_bond_daily_snapshot.")

        rows = conn.execute(
            """
            with scoped_dates as (
              select cast(report_date as date) as report_date
              from zqtz_bond_daily_snapshot
              where cast(report_date as date) between ? and ?
            )
            select max(report_date) as month_end
            from scoped_dates
            group by extract(year from report_date), extract(month from report_date)
            order by month_end
            """,
            [start.isoformat(), end.isoformat()],
        ).fetchall()
        return [month_end.isoformat() for (month_end,) in rows if month_end is not None]
    finally:
        conn.close()


def backfill_yield_curve_month_ends(
    *,
    duckdb_path: str,
    start_date: str,
    end_date: str,
    curve_types: tuple[str, ...] = SUPPORTED_CURVE_TYPES,
    max_backtrack_days: int = MAX_BACKTRACK_DAYS,
) -> dict[str, object]:
    """Backfill governed curve snapshots for month-end anchors without relabeling fallback dates."""
    if max_backtrack_days < 0:
        raise ValueError("max_backtrack_days must be non-negative.")
    normalized_curve_types = _normalize_curve_types(curve_types)
    month_end_dates = list_yield_curve_month_end_anchors(
        duckdb_path=duckdb_path,
        start_date=start_date,
        end_date=end_date,
    )
    adapter = VendorAdapter()
    repo = YieldCurveRepository(duckdb_path)
    written = 0
    skipped = 0
    failures: list[dict[str, str]] = []
    resolved_snapshots: set[tuple[str, str, str]] = set()

    for anchor_date in month_end_dates:
        for curve_type in normalized_curve_types:
            try:
                snapshot = _fetch_curve_snapshot_on_or_before(
                    adapter=adapter,
                    curve_type=curve_type,
                    anchor_date=anchor_date,
                    max_backtrack_days=max_backtrack_days,
                )
                existing = repo.fetch_curve_snapshot(snapshot.trade_date, snapshot.curve_type)
                if existing is not None:
                    resolved_snapshots.add((anchor_date, snapshot.curve_type, snapshot.trade_date))
                    skipped += 1
                    continue
                with repository_task_write_scope(__name__):
                    repo.replace_curve_snapshots(
                        trade_date=snapshot.trade_date,
                        snapshots=[snapshot],
                        rule_version=RULE_VERSION,
                    )
                resolved_snapshots.add((anchor_date, snapshot.curve_type, snapshot.trade_date))
                written += 1
            except Exception as exc:
                existing = _existing_curve_snapshot_on_or_before(
                    repo=repo,
                    anchor_date=anchor_date,
                    curve_type=curve_type,
                    max_backtrack_days=max_backtrack_days,
                )
                if existing is not None:
                    resolved_snapshots.add((anchor_date, curve_type, str(existing["trade_date"])))
                    skipped += 1
                    continue
                failures.append(
                    {
                        "anchor_date": anchor_date,
                        "curve_type": curve_type,
                        "message": str(exc),
                    }
                )

    resolved_snapshot_rows = sorted(resolved_snapshots)
    return {
        "status": "failed" if failures else "completed",
        "duckdb_path": duckdb_path,
        "start_date": date.fromisoformat(start_date).isoformat(),
        "end_date": date.fromisoformat(end_date).isoformat(),
        "month_end_dates": month_end_dates,
        "curve_types": list(normalized_curve_types),
        "total_tasks": len(month_end_dates) * len(normalized_curve_types),
        "written": written,
        "skipped": skipped,
        "failed": len(failures),
        "failures": failures,
        "resolved_trade_dates": sorted({trade_date for _anchor_date, _curve_type, trade_date in resolved_snapshot_rows}),
        "resolved_snapshots": [
            {
                "anchor_date": anchor_date,
                "curve_type": curve_type,
                "trade_date": trade_date,
            }
            for anchor_date, curve_type, trade_date in resolved_snapshot_rows
        ],
    }


def _existing_curve_snapshot_on_or_before(
    *,
    repo: YieldCurveRepository,
    anchor_date: str,
    curve_type: str,
    max_backtrack_days: int,
) -> dict[str, object] | None:
    anchor = date.fromisoformat(anchor_date)
    for offset in range(max_backtrack_days + 1):
        candidate_date = (anchor - timedelta(days=offset)).isoformat()
        snapshot = repo.fetch_curve_snapshot(candidate_date, curve_type)
        if snapshot is not None:
            return snapshot
    return None


def _execute_yield_curve_month_end_backfill(
    *,
    duckdb_path: str,
    start_date: str,
    end_date: str,
    curve_types: tuple[str, ...],
    max_backtrack_days: int,
) -> FormalComputeMaterializeResult:
    payload = backfill_yield_curve_month_ends(
        duckdb_path=duckdb_path,
        start_date=start_date,
        end_date=end_date,
        curve_types=curve_types,
        max_backtrack_days=max_backtrack_days,
    )
    if payload["failed"]:
        first_failure = list(payload["failures"])[0]
        raise FormalComputeMaterializeFailure(
            source_version=f"sv_yield_curve_backfill_failed_{end_date.replace('-', '')}",
            vendor_version="vv_none",
            message=f"Yield curve month-end backfill failed: {first_failure}",
        )

    resolved_snapshots = list(payload.get("resolved_snapshots") or [])
    rows = []
    if resolved_snapshots:
        values_sql = ", ".join("(?, ?)" for _item in resolved_snapshots)
        values: list[str] = []
        for item in resolved_snapshots:
            values.extend([str(item["trade_date"]), str(item["curve_type"])])
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            rows = conn.execute(
                f"""
                with resolved(trade_date, curve_type) as (
                    values {values_sql}
                )
                select distinct source_version, vendor_version
                from fact_formal_yield_curve_daily
                inner join resolved using (trade_date, curve_type)
                """,
                values,
            ).fetchall()
        finally:
            conn.close()
    source_version = "__".join(sorted({str(row[0]) for row in rows if row[0]})) or "sv_yield_curve_backfill_noop"
    vendor_version = "__".join(sorted({str(row[1]) for row in rows if row[1]})) or "vv_none"
    return FormalComputeMaterializeResult(
        source_version=source_version,
        vendor_version=vendor_version,
        payload=payload,
    )


def _materialize_yield_curve_month_end_backfill(
    *,
    start_date: str,
    end_date: str,
    curve_types: list[str] | None = None,
    max_backtrack_days: int = MAX_BACKTRACK_DAYS,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    normalized_curve_types = tuple(curve_types or SUPPORTED_CURVE_TYPES)
    report_date = date.fromisoformat(end_date).isoformat()

    return run_formal_materialize(
        descriptor=YIELD_CURVE_MODULE,
        job_name="yield_curve_month_end_backfill",
        report_date=report_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        run_id=run_id,
        execute_materialization=lambda: _execute_yield_curve_month_end_backfill(
            duckdb_path=str(duckdb_file),
            start_date=date.fromisoformat(start_date).isoformat(),
            end_date=report_date,
            curve_types=normalized_curve_types,
            max_backtrack_days=max_backtrack_days,
        ),
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
            # Broad catch is intentional: accumulate the last error across all backtrack
            # attempts so we can re-raise it if no date in the window has data.
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

materialize_yield_curve_month_end_backfill = register_actor_once(
    "materialize_yield_curve_month_end_backfill",
    _materialize_yield_curve_month_end_backfill,
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
            # Broad catch is intentional: snapshot_rows is the primary source; if it
            # fails we fall through to fact_rows as a secondary source before giving up.
            snapshot_error = exc
    if fact_rows:
        try:
            return _build_aaa_credit_snapshot(rows=fact_rows, trade_date=trade_date)
        except Exception as exc:
            # Secondary source also failed; log and fall through so snapshot_error
            # (primary failure) is raised below, or return None if neither had data.
            logger.warning("aaa_credit fact_rows snapshot build failed for trade_date=%s: %s", trade_date, exc)
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
