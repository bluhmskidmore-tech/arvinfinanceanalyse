"""Backfill sparse rows in ``fact_choice_macro_daily`` from Choice / Tushare."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import duckdb  # noqa: E402
import requests  # noqa: E402
import xlrd  # noqa: E402
from backend.app.core_finance.macro.toolkit.system_sources import (  # noqa: E402
    normalize_macro_source_names,
)
from backend.app.governance.locks import LockDefinition, acquire_lock  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.choice_client import ChoiceClient  # noqa: E402
from backend.app.repositories.duckdb_migrations import (  # noqa: E402
    apply_pending_migrations_on_connection,
    ensure_choice_macro_schema_if_missing,
)
from backend.app.repositories.tushare_adapter import (  # noqa: E402
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from bs4 import BeautifulSoup  # noqa: E402

logger = logging.getLogger(__name__)

SOURCE_VERSION = "backfill_macro_v1"
RULE_VERSION = "rv_backfill_macro_v1"
MIN_ROW_THRESHOLD = 10
FETCH_MAX_ATTEMPTS = 3
FETCH_RETRY_DELAY_SECONDS = 1.0
CYCLE_ROTATION_MACRO_CONFIG_PATH = _REPO_ROOT / "config" / "cycle_rotation_macro_series.json"
CYCLE_ROTATION_MACRO_OFFICIAL_RELEASES_PATH = (
    _REPO_ROOT / "config" / "cycle_rotation_macro_official_releases.json"
)
LOCK = LockDefinition(key="lock:duckdb:macro-series-backfill", ttl_seconds=900)


class BackfillSource(StrEnum):
    CHOICE_SNAPSHOT = "choice_snapshot"
    CHOICE_EDB = "choice_edb"
    TUSHARE_MACRO = "tushare_macro"
    NBS_PMI_RELEASE = "nbs_pmi_release"
    PBC_FINANCIAL_STATISTICS_RELEASE = "pbc_financial_statistics_release"


@dataclass(frozen=True)
class IncompleteSeries:
    series_id: str
    series_name: str
    row_count: int
    frequency: str
    unit: str
    vendor_series_code: str


@dataclass(frozen=True)
class BackfillRow:
    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str


@dataclass(frozen=True)
class SeriesBackfillPlan:
    series_id: str
    series_name: str
    existing_rows: int
    start_date: str
    end_date: str
    frequency: str
    unit: str
    sources: tuple[BackfillSource, ...]
    snapshot_rows_in_range: int
    notes: str


@dataclass(frozen=True)
class FetchOutcome:
    source: BackfillSource | None
    rows: tuple[BackfillRow, ...]
    attempted_sources: tuple[BackfillSource, ...]
    provenance: dict[str, str] | None = None


def backfill_macro_series(
    *,
    duckdb_path: str,
    series_names: list[str] | None = None,
    start_date: str = "2024-01-01",
    end_date: str | None = None,
    dry_run: bool = False,
    fetch_preview: bool = False,
    sources_filter: list[str] | None = None,
) -> dict:
    """Backfill macro series with fewer than ``MIN_ROW_THRESHOLD`` rows in DuckDB."""
    if dry_run and fetch_preview:
        raise ValueError("dry_run and fetch_preview are mutually exclusive.")
    normalized_sources = _normalize_sources_filter(sources_filter)
    resolved_end = end_date or date.today().isoformat()
    _validate_iso_date(start_date, field_name="start_date")
    _validate_iso_date(resolved_end, field_name="end_date")
    if resolved_end < start_date:
        raise ValueError("end_date must be on or after start_date.")

    db_path = Path(duckdb_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {db_path}")

    incomplete = _load_incomplete_series(db_path, series_names=series_names)
    plans = [_build_plan(conn_path=db_path, item=item, start_date=start_date, end_date=resolved_end) for item in incomplete]
    allowed_sources: set[str] | None = None
    if normalized_sources:
        allowed_sources = set(normalized_sources)
        incompatible = [
            plan
            for plan in plans
            if not any(source.value in allowed_sources for source in plan.sources)
        ]
        if series_names and incompatible:
            incompatible_ids = ", ".join(plan.series_id for plan in incompatible)
            raise ValueError(
                f"Requested sources {','.join(normalized_sources)} are not supported "
                f"for requested series {incompatible_ids}"
            )
        filtered = [
            (item, plan)
            for item, plan in zip(incomplete, plans, strict=True)
            if plan.sources and any(source.value in allowed_sources for source in plan.sources)
        ]
        if filtered:
            incomplete, plans = map(list, zip(*filtered, strict=True))
        else:
            incomplete = []
            plans = []

    if dry_run:
        allocation: dict[str, int] = {}
        for plan in plans:
            display_sources = _filter_plan_sources(plan.sources, allowed_sources)
            primary = display_sources[0].value if display_sources else "unclassified"
            allocation[primary] = allocation.get(primary, 0) + 1
        return {
            "status": "planned",
            "dry_run": True,
            "fetch_preview": False,
            "duckdb_path": str(db_path),
            "start_date": start_date,
            "end_date": resolved_end,
            "incomplete_count": len(plans),
            "source_allocation": allocation,
            "series_plans": [
                {
                    "series_name": plan.series_name,
                    "series_id": plan.series_id,
                    "existing_rows": plan.existing_rows,
                    "start_date": plan.start_date,
                    "end_date": plan.end_date,
                    "frequency": plan.frequency,
                    "sources": [source.value for source in _filter_plan_sources(plan.sources, allowed_sources)],
                    "snapshot_rows_in_range": plan.snapshot_rows_in_range,
                    "notes": plan.notes,
                }
                for plan in plans
            ],
        }

    fetched: list[tuple[IncompleteSeries, SeriesBackfillPlan, FetchOutcome]] = []
    errors: dict[str, str] = {}
    for item, plan in zip(incomplete, plans, strict=True):
        outcome = _fetch_rows_for_plan(
            plan,
            duckdb_path=db_path,
            vendor_series_code=item.vendor_series_code,
            start_date=start_date,
            end_date=resolved_end,
            sources_filter=normalized_sources,
        )
        fetched.append((item, plan, outcome))
        if not outcome.rows:
            attempted = ",".join(source.value for source in outcome.attempted_sources) or "none"
            errors[item.series_name] = (
                f"no rows fetched for series_id={item.series_id} from sources={attempted}"
            )
            continue
        row_issue = _fetch_outcome_issue(
            plan=plan,
            outcome=outcome,
            start_date=start_date,
            end_date=resolved_end,
        )
        if row_issue is not None:
            errors[item.series_name] = row_issue

    valid_series_ids = {
        item.series_id
        for item, _plan, outcome in fetched
        if outcome.rows and item.series_name not in errors
    }

    source_by_series = {
        item.series_id: outcome.source.value
        for item, _plan, outcome in fetched
        if item.series_id in valid_series_ids and outcome.source is not None
    }
    previews = {
        item.series_id: _fetch_preview_payload(plan=plan, outcome=outcome)
        for item, plan, outcome in fetched
        if item.series_id in valid_series_ids and outcome.source is not None
    }
    vendor_versions = {
        item.series_id: _vendor_version_for_rows(
            source=outcome.source,
            end_date=resolved_end,
            rows=outcome.rows,
            provenance=outcome.provenance,
        )
        for item, _plan, outcome in fetched
        if item.series_id in valid_series_ids and outcome.source is not None
    }
    total_fetched = sum(len(outcome.rows) for _item, _plan, outcome in fetched)

    if errors:
        return {
            "status": "blocked",
            "dry_run": False,
            "fetch_preview": fetch_preview,
            "duckdb_path": str(db_path),
            "start_date": start_date,
            "end_date": resolved_end,
            "processed_count": len(incomplete),
            "total_fetched": total_fetched,
            "total_added": 0,
            "results": {item.series_name: 0 for item in incomplete},
            "errors": errors,
            "source_by_series": source_by_series,
            "vendor_versions": vendor_versions,
            "previews": previews,
        }

    if fetch_preview:
        return {
            "status": "preview_ready",
            "dry_run": False,
            "fetch_preview": True,
            "duckdb_path": str(db_path),
            "start_date": start_date,
            "end_date": resolved_end,
            "processed_count": len(incomplete),
            "total_fetched": total_fetched,
            "total_added": 0,
            "results": {item.series_name: 0 for item in incomplete},
            "errors": {},
            "source_by_series": source_by_series,
            "vendor_versions": vendor_versions,
            "previews": previews,
        }

    results: dict[str, int] = {}
    run_id = _materialization_run_id()

    with acquire_lock(LOCK, base_dir=db_path.parent):
        conn = duckdb.connect(str(db_path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            ensure_choice_macro_schema_if_missing(conn)
            batch_results: dict[str, int] = {}
            failed_series_name: str | None = None
            conn.execute("begin transaction")
            try:
                for item, _plan, outcome in fetched:
                    failed_series_name = item.series_name
                    added = _insert_rows(
                        conn,
                        rows=list(outcome.rows),
                        source_version=SOURCE_VERSION,
                        vendor_version=vendor_versions[item.series_id],
                        run_id=run_id,
                    )
                    batch_results[item.series_name] = added
                failed_series_name = None
                conn.execute("commit")
                results = batch_results
            except Exception as exc:
                conn.execute("rollback")
                error_key = failed_series_name or "batch"
                logger.exception(
                    "macro backfill batch rolled back series=%s error=%s",
                    error_key,
                    exc,
                )
                errors[error_key] = str(exc)
                results = {item.series_name: 0 for item, _plan, _outcome in fetched}
        finally:
            conn.close()

    return {
        "status": "failed" if errors else "completed",
        "dry_run": False,
        "fetch_preview": False,
        "duckdb_path": str(db_path),
        "start_date": start_date,
        "end_date": resolved_end,
        "processed_count": len(incomplete),
        "total_fetched": total_fetched,
        "total_added": sum(results.values()),
        "results": results,
        "errors": errors,
        "run_id": run_id,
        "source_by_series": source_by_series,
        "vendor_versions": vendor_versions,
        "previews": previews,
    }


def _load_incomplete_series(db_path: Path, *, series_names: list[str] | None) -> list[IncompleteSeries]:
    config = json.loads(CYCLE_ROTATION_MACRO_CONFIG_PATH.read_text(encoding="utf-8"))
    configured: dict[str, tuple[IncompleteSeries, set[str]]] = {}
    for row in config.get("series", []):
        if not isinstance(row, dict):
            continue
        series_id = str(row.get("series_id") or "").strip()
        series_name = str(row.get("series_name") or "").strip()
        if not series_id or not series_name:
            continue
        aliases = {
            str(alias).strip()
            for alias in row.get("backfill_series_name_aliases", [])
            if str(alias).strip()
        }
        aliases.update({series_id, series_name})
        configured[series_id] = (
            IncompleteSeries(
                series_id=series_id,
                series_name=series_name,
                row_count=0,
                frequency=str(row.get("frequency") or "unknown"),
                unit=str(row.get("unit") or "unknown"),
                vendor_series_code=series_id,
            ),
            aliases,
        )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        has_catalog = _relation_exists(conn, "phase1_macro_vendor_catalog")
        if has_catalog:
            catalog_columns = _table_columns(conn, "phase1_macro_vendor_catalog")
            catalog_name_expr = "cat.series_name" if "series_name" in catalog_columns else "f.series_name"
            catalog_frequency_expr = "cat.frequency" if "frequency" in catalog_columns else "'unknown'"
            catalog_unit_expr = "cat.unit" if "unit" in catalog_columns else "'unknown'"
            catalog_vendor_code_expr = (
                "cat.vendor_series_code" if "vendor_series_code" in catalog_columns else "cat.series_id"
            )
            params: list[object] = []
            query = f"""
                with fact_counts as (
                  select series_id, max(series_name) as series_name, count(*) as row_count
                  from fact_choice_macro_daily
                  group by series_id
                ),
                catalog_series as (
                  select
                    cat.series_id,
                    coalesce(nullif({catalog_name_expr}, ''), f.series_name, cat.series_id) as series_name,
                    coalesce(f.row_count, 0) as row_count,
                    coalesce({catalog_frequency_expr}, 'unknown') as frequency,
                    coalesce({catalog_unit_expr}, 'unknown') as unit,
                    coalesce({catalog_vendor_code_expr}, cat.series_id) as vendor_series_code
                  from phase1_macro_vendor_catalog cat
                  left join fact_counts f on f.series_id = cat.series_id
                ),
                fact_only_series as (
                  select
                    f.series_id,
                    f.series_name,
                    f.row_count,
                    'unknown' as frequency,
                    'unknown' as unit,
                    f.series_id as vendor_series_code
                  from fact_counts f
                  left join phase1_macro_vendor_catalog cat on cat.series_id = f.series_id
                  where cat.series_id is null
                ),
                all_series as (
                  select * from catalog_series
                  union all
                  select * from fact_only_series
                )
                select series_id, series_name, row_count, frequency, unit, vendor_series_code
                from all_series
                order by series_name
            """
        else:
            params = []
            query = """
                with counts as (
                  select series_id, max(series_name) as series_name, count(*) as row_count
                  from fact_choice_macro_daily
                  group by series_id
                )
                select
                  series_id,
                  series_name,
                  row_count,
                  'unknown' as frequency,
                  'unknown' as unit,
                  series_id as vendor_series_code
                from counts
                order by series_name
            """
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    incomplete = [
        IncompleteSeries(
            series_id=str(row[0]),
            series_name=str(row[1]),
            row_count=int(row[2]),
            frequency=str(row[3]),
            unit=str(row[4]),
            vendor_series_code=str(row[5]),
        )
        for row in rows
    ]
    by_id = {item.series_id: item for item in incomplete}
    for series_id, (target, _aliases) in configured.items():
        observed = by_id.get(series_id)
        if observed is None:
            by_id[series_id] = target
            continue
        by_id[series_id] = IncompleteSeries(
            series_id=series_id,
            series_name=target.series_name,
            row_count=observed.row_count,
            frequency=target.frequency,
            unit=target.unit,
            vendor_series_code=observed.vendor_series_code or target.vendor_series_code,
        )

    requested = {str(name).strip() for name in series_names or [] if str(name).strip()}
    if requested:
        by_id = {
            series_id: item
            for series_id, item in by_id.items()
            if requested
            & configured.get(series_id, (item, {item.series_id, item.series_name}))[1]
        }
    if not requested:
        by_id = {
            series_id: item
            for series_id, item in by_id.items()
            if item.row_count < MIN_ROW_THRESHOLD
        }
    return sorted(by_id.values(), key=lambda item: item.series_name)


def _build_plan(
    *,
    conn_path: Path,
    item: IncompleteSeries,
    start_date: str,
    end_date: str,
) -> SeriesBackfillPlan:
    snapshot_rows = _count_snapshot_rows(
        conn_path,
        series_id=item.series_id,
        start_date=start_date,
        end_date=end_date,
    )
    sources = _resolve_sources(item.series_name, item.series_id, snapshot_rows=snapshot_rows)
    notes = _plan_notes(item.series_name, sources)
    frequency = _infer_frequency(item.series_name, item.frequency)
    return SeriesBackfillPlan(
        series_id=item.series_id,
        series_name=item.series_name,
        existing_rows=item.row_count,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        unit=item.unit,
        sources=sources,
        snapshot_rows_in_range=snapshot_rows,
        notes=notes,
    )


def _resolve_sources(series_name: str, series_id: str, *, snapshot_rows: int) -> tuple[BackfillSource, ...]:
    name = series_name.upper()

    if _is_commodity_series(series_name):
        return (BackfillSource.TUSHARE_MACRO, BackfillSource.CHOICE_EDB)

    if _is_tushare_macro_series(series_name):
        cycle_config = json.loads(CYCLE_ROTATION_MACRO_CONFIG_PATH.read_text(encoding="utf-8"))
        cycle_series_ids = {
            str(row.get("series_id") or "").strip()
            for row in cycle_config.get("series", [])
            if isinstance(row, dict)
        }
        if series_id in cycle_series_ids:
            if series_id == "M0017126":
                return (BackfillSource.NBS_PMI_RELEASE, BackfillSource.TUSHARE_MACRO)
            if series_id in {"M5525763", "M0001385"}:
                return (BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE, BackfillSource.TUSHARE_MACRO)
            return (BackfillSource.TUSHARE_MACRO,)
        return (BackfillSource.TUSHARE_MACRO, BackfillSource.CHOICE_EDB)

    if _is_spread_series(series_name):
        return (BackfillSource.CHOICE_EDB,)

    if _is_daily_rate_series(series_name, series_id):
        sources: list[BackfillSource] = []
        if snapshot_rows > 0:
            sources.append(BackfillSource.CHOICE_SNAPSHOT)
        sources.append(BackfillSource.CHOICE_EDB)
        if "SHIBOR" in name or series_id.startswith("NCD.SHIBOR."):
            sources.insert(1 if sources and sources[0] == BackfillSource.CHOICE_SNAPSHOT else 0, BackfillSource.TUSHARE_MACRO)
        return tuple(_dedupe_sources(sources))

    if series_id.startswith("EMM") or series_id.startswith("NCD."):
        return (BackfillSource.CHOICE_EDB, BackfillSource.TUSHARE_MACRO)

    return (BackfillSource.CHOICE_EDB,)


def _plan_notes(series_name: str, sources: tuple[BackfillSource, ...]) -> str:
    if BackfillSource.NBS_PMI_RELEASE in sources:
        return "Pinned NBS PMI release artifact with Tushare fallback."
    if BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE in sources:
        return "Pinned PBC financial-statistics releases with Tushare fallback."
    if BackfillSource.TUSHARE_MACRO in sources and not _tushare_token_configured():
        return "MOSS_TUSHARE_TOKEN missing; Tushare leg may be skipped."
    if BackfillSource.CHOICE_EDB in sources:
        return "Choice EDB historical window backfill."
    return "Backfill plan resolved from series name/id."


def _fetch_rows_for_plan(
    plan: SeriesBackfillPlan,
    *,
    duckdb_path: Path,
    vendor_series_code: str,
    start_date: str,
    end_date: str,
    sources_filter: list[str] | None = None,
) -> FetchOutcome:
    allowed = {source.strip() for source in sources_filter} if sources_filter else None
    sources = plan.sources
    if allowed:
        sources = tuple(source for source in plan.sources if source.value in allowed)
    attempted_sources: list[BackfillSource] = []
    for source in sources:
        attempted_sources.append(source)
        rows: list[BackfillRow] = []
        for attempt in range(1, FETCH_MAX_ATTEMPTS + 1):
            try:
                rows = _fetch_by_source(
                    source,
                    duckdb_path=duckdb_path,
                    series_id=plan.series_id,
                    series_name=plan.series_name,
                    vendor_series_code=vendor_series_code,
                    frequency=plan.frequency,
                    unit=plan.unit,
                    start_date=start_date,
                    end_date=end_date,
                )
                break
            except Exception as exc:
                logger.warning(
                    "macro backfill fetch failed series=%s source=%s attempt=%d/%d error=%s",
                    plan.series_name,
                    source.value,
                    attempt,
                    FETCH_MAX_ATTEMPTS,
                    exc,
                )
                if attempt < FETCH_MAX_ATTEMPTS:
                    time.sleep(FETCH_RETRY_DELAY_SECONDS)
        if rows:
            provenance = None
            if source == BackfillSource.NBS_PMI_RELEASE:
                provenance = _nbs_pmi_release_manifest(
                    series_id=plan.series_id,
                    end_date=end_date,
                )
            elif source == BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE:
                provenance = _pbc_financial_statistics_release_provenance(
                    series_id=plan.series_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            return FetchOutcome(
                source=source,
                rows=tuple(rows),
                attempted_sources=tuple(attempted_sources),
                provenance=provenance,
            )
    return FetchOutcome(
        source=None,
        rows=(),
        attempted_sources=tuple(attempted_sources),
    )


def _normalize_sources_filter(sources_filter: list[str] | None) -> list[str] | None:
    if not sources_filter:
        return None
    normalized = list(normalize_macro_source_names(sources_filter))
    supported = {source.value for source in BackfillSource}
    unknown = sorted(set(normalized) - supported)
    if unknown:
        raise ValueError(f"Unsupported macro backfill source(s): {', '.join(unknown)}")
    return normalized or None


def _normalize_source_arg(value: str) -> str:
    normalized = normalize_macro_source_names([value])
    if not normalized:
        raise ValueError("macro backfill source cannot be blank")
    return normalized[0]


def _fetch_outcome_issue(
    *,
    plan: SeriesBackfillPlan,
    outcome: FetchOutcome,
    start_date: str,
    end_date: str,
) -> str | None:
    rows = outcome.rows
    wrong_series = sorted({row.series_id for row in rows if row.series_id != plan.series_id})
    if wrong_series:
        return f"{plan.series_id} series mismatch: got {', '.join(wrong_series)}"

    expected_frequency = plan.frequency.strip().lower()
    observed_frequencies = sorted({row.frequency.strip().lower() for row in rows})
    if expected_frequency not in {"", "unknown"} and observed_frequencies != [expected_frequency]:
        return (
            f"{plan.series_id} frequency mismatch: expected {plan.frequency}, "
            f"got {','.join(observed_frequencies) or 'blank'}"
        )

    expected_unit = plan.unit.strip().lower()
    observed_units = sorted({row.unit.strip().lower() for row in rows})
    if expected_unit not in {"", "unknown"} and observed_units != [expected_unit]:
        return (
            f"{plan.series_id} unit mismatch: expected {plan.unit}, "
            f"got {','.join(observed_units) or 'blank'}"
        )

    dates = [row.trade_date for row in rows]
    invalid_dates: set[str] = set()
    for trade_date in dates:
        try:
            parsed_date = date.fromisoformat(trade_date)
        except ValueError:
            invalid_dates.add(trade_date)
            continue
        if parsed_date.isoformat() != trade_date or trade_date < start_date or trade_date > end_date:
            invalid_dates.add(trade_date)
    if invalid_dates:
        return f"{plan.series_id} invalid trade_date or outside preview window: {', '.join(sorted(invalid_dates))}"
    seen_dates: set[str] = set()
    duplicate_dates: set[str] = set()
    for trade_date in dates:
        if trade_date in seen_dates:
            duplicate_dates.add(trade_date)
        seen_dates.add(trade_date)
    if duplicate_dates:
        return f"{plan.series_id} duplicate trade_date rows: {', '.join(sorted(duplicate_dates))}"
    if any(not math.isfinite(row.value_numeric) for row in rows):
        return f"{plan.series_id} contains non-finite values"
    return None


def _fetch_preview_payload(
    *,
    plan: SeriesBackfillPlan,
    outcome: FetchOutcome,
) -> dict[str, object]:
    if outcome.source is None or not outcome.rows:
        raise ValueError("fetch preview requires a non-empty source outcome")
    rows = sorted(outcome.rows, key=lambda row: (row.trade_date, row.series_id))
    values = [row.value_numeric for row in rows]
    payload: dict[str, object] = {
        "series_name": plan.series_name,
        "source": outcome.source.value,
        "row_count": len(rows),
        "first_trade_date": rows[0].trade_date,
        "last_trade_date": rows[-1].trade_date,
        "first_value": rows[0].value_numeric,
        "last_value": rows[-1].value_numeric,
        "min_value": min(values),
        "max_value": max(values),
        "frequency": rows[0].frequency,
        "unit": rows[0].unit,
    }
    if outcome.provenance:
        for key in (
            "release_url",
            "published_at",
            "artifact_sha256",
            "artifact_count",
            "artifact_set_sha256",
            "artifacts_json",
        ):
            value = outcome.provenance.get(key)
            if value:
                payload[key] = value
    return payload


def _materialization_run_id() -> str:
    return f"backfill_macro_v1:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _vendor_version_for_rows(
    *,
    source: BackfillSource,
    end_date: str,
    rows: tuple[BackfillRow, ...],
    provenance: dict[str, str] | None = None,
) -> str:
    canonical_rows = [
        {
            "series_id": row.series_id,
            "series_name": row.series_name,
            "trade_date": row.trade_date,
            "value_numeric": row.value_numeric,
            "frequency": row.frequency,
            "unit": row.unit,
        }
        for row in sorted(rows, key=lambda item: (item.series_id, item.trade_date, item.series_name))
    ]
    content_hash = hashlib.sha256(
        json.dumps(
            canonical_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    artifact_hash = str(
        (provenance or {}).get("artifact_set_sha256")
        or (provenance or {}).get("artifact_sha256")
        or ""
    )[:16]
    artifact_token = f"_{artifact_hash}" if artifact_hash else ""
    return f"vv_backfill_macro_{source.value}_{end_date.replace('-', '')}{artifact_token}_{content_hash}"


def _filter_plan_sources(
    sources: tuple[BackfillSource, ...],
    allowed_sources: set[str] | None,
) -> tuple[BackfillSource, ...]:
    if allowed_sources is None:
        return sources
    return tuple(source for source in sources if source.value in allowed_sources)


def _fetch_by_source(
    source: BackfillSource,
    *,
    duckdb_path: Path,
    series_id: str,
    series_name: str,
    vendor_series_code: str,
    frequency: str,
    unit: str,
    start_date: str,
    end_date: str,
) -> list[BackfillRow]:
    if source == BackfillSource.CHOICE_SNAPSHOT:
        return _fetch_from_choice_snapshot(
            duckdb_path=duckdb_path,
            series_id=series_id,
            series_name=series_name,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    if source == BackfillSource.CHOICE_EDB:
        return _fetch_from_choice_edb(
            series_id=series_id,
            series_name=series_name,
            vendor_series_code=vendor_series_code,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    if source == BackfillSource.TUSHARE_MACRO:
        return _fetch_from_tushare(series_id=series_id, series_name=series_name, start_date=start_date, end_date=end_date, frequency=frequency, unit=unit)
    if source == BackfillSource.NBS_PMI_RELEASE:
        return _fetch_from_nbs_pmi_release(
            series_id=series_id,
            series_name=series_name,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    if source == BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE:
        return _fetch_from_pbc_financial_statistics_releases(
            series_id=series_id,
            series_name=series_name,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    return []


def _nbs_pmi_release_manifest(*, series_id: str, end_date: str) -> dict[str, str] | None:
    if series_id != "M0017126" or not CYCLE_ROTATION_MACRO_OFFICIAL_RELEASES_PATH.exists():
        return None
    payload = json.loads(CYCLE_ROTATION_MACRO_OFFICIAL_RELEASES_PATH.read_text(encoding="utf-8"))
    candidates: list[dict[str, str]] = []
    for raw in payload.get("releases", []):
        if not isinstance(raw, dict):
            continue
        row = {str(key): str(value) for key, value in raw.items() if value is not None}
        if row.get("source") != BackfillSource.NBS_PMI_RELEASE.value or row.get("series_id") != series_id:
            continue
        published_at = _parse_published_at(row.get("published_at"))
        if published_at is None or published_at.date() > date.fromisoformat(end_date):
            continue
        candidates.append(row)
    if not candidates:
        return None
    return max(candidates, key=lambda row: str(row["published_at"]))


def _fetch_from_nbs_pmi_release(
    *,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    manifest = _nbs_pmi_release_manifest(series_id=series_id, end_date=end_date)
    if manifest is None:
        return []
    artifact_url = manifest.get("artifact_url", "")
    if not _is_trusted_nbs_url(artifact_url):
        return []
    response = requests.get(
        artifact_url,
        headers={"User-Agent": "MOSS macro backfill/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    return _map_nbs_pmi_release_xls(
        response.content,
        manifest=manifest,
        series_id=series_id,
        series_name=series_name,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        unit=unit,
    )


def _map_nbs_pmi_release_xls(
    artifact_bytes: bytes,
    *,
    manifest: dict[str, str],
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    if series_id != "M0017126" or frequency.lower() != "monthly" or unit != "index":
        return []
    if not _is_trusted_nbs_url(manifest.get("release_url", "")) or not _is_trusted_nbs_url(
        manifest.get("artifact_url", "")
    ):
        return []
    published_at = _parse_published_at(manifest.get("published_at"))
    if published_at is None or published_at.date() > date.fromisoformat(end_date):
        return []
    if manifest.get("source_unit") != "%":
        return []
    if manifest.get("target_unit") != "index":
        return []
    if manifest.get("value_transform") != "identity_percentage_points_to_index_points":
        return []
    expected_hash = str(manifest.get("artifact_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        return []
    if hashlib.sha256(artifact_bytes).hexdigest() != expected_hash:
        return []

    try:
        workbook = xlrd.open_workbook(file_contents=artifact_bytes)
        if hasattr(workbook, "sheet_names"):
            sheet_names = workbook.sheet_names()
            expected_sheet = str(manifest.get("sheet_name") or "制造业")
            if not sheet_names or str(sheet_names[0]) != expected_sheet:
                return []
        sheet = workbook.sheet_by_index(0)
        table_rows = [sheet.row_values(row_index) for row_index in range(sheet.nrows)]
    except (AttributeError, IndexError, OSError, TypeError, ValueError, xlrd.XLRDError):
        return []
    if not table_rows or "制造业" not in str(table_rows[0][0] if table_rows[0] else ""):
        return []

    expected_header = str(manifest.get("value_header") or "PMI")
    header_matches = [
        (row_index, column_index)
        for row_index, row in enumerate(table_rows)
        for column_index, value in enumerate(row)
        if str(value).strip() == expected_header
    ]
    if len(header_matches) != 1:
        return []
    header_row, value_column = header_matches[0]
    datemode = int(getattr(workbook, "datemode", 0))
    rows: list[BackfillRow] = []
    seen_dates: set[str] = set()
    for raw_row in table_rows[header_row + 1 :]:
        if not raw_row or value_column >= len(raw_row):
            continue
        trade_date = _nbs_pmi_month(raw_row[0], datemode=datemode)
        value = _coerce_float(raw_row[value_column])
        if trade_date is None or value is None:
            continue
        if trade_date in seen_dates or not 0 <= value <= 100:
            return []
        seen_dates.add(trade_date)
        if start_date <= trade_date <= end_date:
            rows.append(
                BackfillRow(
                    series_id=series_id,
                    series_name=series_name,
                    trade_date=trade_date,
                    value_numeric=value,
                    frequency=frequency,
                    unit=unit,
                )
            )
    if not rows:
        return []
    latest_period = str(manifest.get("latest_period") or "")
    if latest_period and latest_period not in seen_dates:
        return []
    return sorted(rows, key=lambda row: row.trade_date)


def _parse_published_at(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _is_trusted_nbs_url(value: object) -> bool:
    parsed = urlsplit(str(value or ""))
    return parsed.scheme == "https" and parsed.hostname in {"stats.gov.cn", "www.stats.gov.cn"}


def _nbs_pmi_month(value: object, *, datemode: int) -> str | None:
    if isinstance(value, datetime):
        return value.date().replace(day=1).isoformat()
    if isinstance(value, date):
        return value.replace(day=1).isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = xlrd.xldate_as_datetime(float(value), datemode)
        except (OverflowError, ValueError, xlrd.XLDateError):
            return None
        return parsed.date().replace(day=1).isoformat()
    match = re.fullmatch(r"\s*(\d{4})\D+(\d{1,2})\D*\s*", str(value or ""))
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), 1).isoformat()
    except ValueError:
        return None


def _pbc_financial_statistics_release_manifests(
    *,
    series_id: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    if series_id not in {"M5525763", "M0001385"} or not CYCLE_ROTATION_MACRO_OFFICIAL_RELEASES_PATH.exists():
        return []
    payload = json.loads(CYCLE_ROTATION_MACRO_OFFICIAL_RELEASES_PATH.read_text(encoding="utf-8"))
    manifests: list[dict[str, object]] = []
    for raw in payload.get("releases", []):
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE.value:
            continue
        if str(raw.get("series_id") or "") != series_id:
            continue
        report_month = str(raw.get("report_month") or "")
        if re.fullmatch(r"\d{4}-\d{2}", report_month) is None:
            continue
        trade_date = f"{report_month}-01"
        available_at = _parse_published_at(raw.get("available_at") or raw.get("published_at"))
        if available_at is None or available_at.date() > date.fromisoformat(end_date):
            continue
        if start_date <= trade_date <= end_date:
            manifests.append(dict(raw))
    return sorted(manifests, key=lambda row: str(row.get("report_month") or ""))


def _pbc_financial_statistics_release_provenance(
    *,
    series_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, str] | None:
    manifests = _pbc_financial_statistics_release_manifests(
        series_id=series_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not manifests:
        return None
    artifacts = [
        {
            "report_month": str(row.get("report_month") or ""),
            "release_url": str(row.get("release_url") or ""),
            "published_at": str(row.get("published_at") or ""),
            "available_at": str(row.get("available_at") or row.get("published_at") or ""),
            "artifact_sha256": str(row.get("artifact_sha256") or ""),
        }
        for row in manifests
    ]
    artifacts_json = json.dumps(artifacts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    latest = artifacts[-1]
    return {
        "release_url": latest["release_url"],
        "published_at": latest["published_at"],
        "available_at": latest["available_at"],
        "artifact_sha256": latest["artifact_sha256"],
        "artifact_count": str(len(artifacts)),
        "artifact_set_sha256": hashlib.sha256(artifacts_json.encode("utf-8")).hexdigest(),
        "artifacts_json": artifacts_json,
    }


def _fetch_from_pbc_financial_statistics_releases(
    *,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    manifests = _pbc_financial_statistics_release_manifests(
        series_id=series_id,
        start_date=start_date,
        end_date=end_date,
    )
    rows_by_date: dict[str, BackfillRow] = {}
    for manifest in manifests:
        artifact_url = str(manifest.get("artifact_url") or manifest.get("release_url") or "")
        if not _is_trusted_pbc_url(artifact_url):
            return []
        response = requests.get(
            artifact_url,
            headers={"User-Agent": "MOSS macro backfill/1.0"},
            timeout=20,
        )
        response.raise_for_status()
        mapped = _map_pbc_financial_statistics_release_html(
            response.content,
            manifest=manifest,
            series_id=series_id,
            series_name=series_name,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
        if len(mapped) != 1:
            return []
        row = mapped[0]
        existing = rows_by_date.get(row.trade_date)
        if existing is not None and existing != row:
            return []
        rows_by_date[row.trade_date] = row
    return [rows_by_date[key] for key in sorted(rows_by_date)]


def _map_pbc_financial_statistics_release_html(
    artifact_bytes: bytes,
    *,
    manifest: dict[str, object],
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    if series_id not in {"M5525763", "M0001385"} or frequency.lower() != "monthly" or unit != "%":
        return []
    release_url = str(manifest.get("release_url") or "")
    artifact_url = str(manifest.get("artifact_url") or release_url)
    if not _is_trusted_pbc_url(release_url) or not _is_trusted_pbc_url(artifact_url):
        return []
    published_at = _parse_published_at(manifest.get("published_at"))
    available_at = _parse_published_at(manifest.get("available_at") or manifest.get("published_at"))
    if published_at is None or available_at is None or available_at.date() > date.fromisoformat(end_date):
        return []
    expected_hash = str(manifest.get("artifact_sha256") or "").lower()
    if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        return []
    if hashlib.sha256(artifact_bytes).hexdigest() != expected_hash:
        return []
    if manifest.get("source_unit") != "%" or manifest.get("target_unit") != "%":
        return []
    if manifest.get("value_transform") != "identity_percentage_points":
        return []
    expected_mappings = {
        "M5525763": "社会融资规模存量:同比",
        "M0001385": "广义货币M2:同比",
    }
    mappings = manifest.get("field_mappings")
    if not isinstance(mappings, dict) or mappings.get(series_id) != expected_mappings[series_id]:
        return []
    report_month = str(manifest.get("report_month") or "")
    match = re.fullmatch(r"(\d{4})-(\d{2})", report_month)
    if match is None:
        return []
    year, month = int(match.group(1)), int(match.group(2))
    try:
        trade_date = date(year, month, 1).isoformat()
    except ValueError:
        return []
    if not start_date <= trade_date <= end_date:
        return []
    allowed_titles = {f"{year}年{month}月金融统计数据报告"}
    if month == 6:
        allowed_titles.add(f"{year}年上半年金融统计数据报告")
    release_title = manifest.get("release_title")
    if not isinstance(release_title, str) or release_title not in allowed_titles:
        return []
    try:
        html = artifact_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return []
    soup = BeautifulSoup(html, "html.parser")
    if soup.title is None or soup.title.get_text(strip=True) != release_title:
        return []
    zooms = soup.select("div#zoom")
    if len(zooms) != 1:
        return []
    paragraphs = [
        " ".join(paragraph.get_text(" ", strip=True).split())
        for paragraph in zooms[0].find_all("p", recursive=False)
    ]
    value = _pbc_financial_statistics_value(
        paragraphs,
        series_id=series_id,
        year=year,
        month=month,
    )
    if value is None or not -100 <= value <= 100:
        return []
    return [
        BackfillRow(
            series_id=series_id,
            series_name=series_name,
            trade_date=trade_date,
            value_numeric=value,
            frequency=frequency,
            unit=unit,
        )
    ]


def _pbc_financial_statistics_value(
    paragraphs: list[str],
    *,
    series_id: str,
    year: int,
    month: int,
) -> float | None:
    number = r"([+-]?\d+(?:\.\d+)?)"
    if series_id == "M5525763":
        heading = re.compile(rf"^一、社会融资规模存量同比增长{number}%$")
        detail = re.compile(
            rf"^初步统计，{year}年{month}月末社会融资规模存量为\d+(?:\.\d+)?万亿元，同比增长{number}%。"
        )
    else:
        heading = re.compile(rf"^三、广义货币增长{number}%$")
        detail = re.compile(
            rf"^{month}月末，广义货币[（(]M2[）)]余额\d+(?:\.\d+)?万亿元[,，]同比增长{number}%。"
        )
    heading_matches = [(index, match) for index, text in enumerate(paragraphs) if (match := heading.match(text))]
    if len(heading_matches) != 1:
        return None
    index, heading_match = heading_matches[0]
    if index + 1 >= len(paragraphs):
        return None
    detail_match = detail.match(paragraphs[index + 1])
    if detail_match is None:
        return None
    heading_value = _coerce_float(heading_match.group(1))
    detail_value = _coerce_float(detail_match.group(1))
    if heading_value is None or detail_value is None or heading_value != detail_value:
        return None
    return detail_value


def _is_trusted_pbc_url(value: object) -> bool:
    parsed = urlsplit(str(value or ""))
    return parsed.scheme == "https" and parsed.hostname in {"pbc.gov.cn", "www.pbc.gov.cn"}


def _fetch_from_choice_snapshot(
    *,
    duckdb_path: Path,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        if not _relation_exists(conn, "choice_market_snapshot"):
            return []
        result = conn.execute(
            """
            select trade_date, value_numeric, frequency, unit
            from choice_market_snapshot
            where series_id = ? and trade_date between ? and ?
            order by trade_date
            """,
            [series_id, start_date, end_date],
        ).fetchall()
    finally:
        conn.close()
    rows: list[BackfillRow] = []
    for trade_date, value_numeric, row_frequency, row_unit in result:
        value = _coerce_float(value_numeric)
        normalized_date = normalize_trade_date(trade_date)
        if value is None or normalized_date is None:
            continue
        rows.append(
            BackfillRow(
                series_id=series_id,
                series_name=series_name,
                trade_date=normalized_date,
                value_numeric=value,
                frequency=str(row_frequency or frequency or "daily"),
                unit=str(row_unit or unit or "unknown"),
            )
        )
    return rows


def _fetch_from_choice_edb(
    *,
    series_id: str,
    series_name: str,
    vendor_series_code: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    config = json.loads(CYCLE_ROTATION_MACRO_CONFIG_PATH.read_text(encoding="utf-8"))
    for target in config.get("series", []):
        if not isinstance(target, dict) or str(target.get("series_id") or "") != series_id:
            continue
        excluded_ids = {str(item).strip() for item in target.get("excluded_series_ids", [])}
        if vendor_series_code in excluded_ids:
            logger.warning(
                "macro backfill rejected excluded vendor code target=%s vendor=%s",
                series_id,
                vendor_series_code,
            )
            return []

    from backend.scripts.backfill_cross_asset_macro_environment import (  # noqa: PLC0415
        SeriesMeta,
        choice_edb_rows,
    )

    client = ChoiceClient()
    request_options = f"IsLatest=0,StartDate={start_date},EndDate={end_date},Ispandas=1,RECVtimeout=20"
    result = client.edb([vendor_series_code], request_options)
    meta = SeriesMeta(
        series_id=series_id,
        series_name=series_name,
        vendor_name="choice",
        vendor_series_code=vendor_series_code,
        frequency=frequency,
        unit=unit,
        theme="macro_backfill",
        tags=("backfill",),
        refresh_tier="stable",
        request_options=request_options,
        fetch_mode="date_slice",
        fetch_granularity="batch",
        policy_note="macro_backfill choice edb",
    )
    parsed = choice_edb_rows(result, {vendor_series_code: meta})
    return [
        BackfillRow(
            series_id=str(row["series_id"]),
            series_name=str(row["series_name"]),
            trade_date=str(row["trade_date"]),
            value_numeric=float(row["value_numeric"]),
            frequency=str(row.get("frequency") or frequency),
            unit=str(row.get("unit") or unit),
        )
        for row in parsed
        if start_date <= str(row["trade_date"]) <= end_date
    ]


def _fetch_from_tushare(
    *,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    token = resolve_tushare_token_with_settings_fallback(get_settings())
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured.")

    ts = import_tushare_pro()
    pro = ts.pro_api(token)
    name = series_name

    if series_id.startswith("NCD.SHIBOR.") or "SHIBOR" in name.upper():
        time.sleep(0.3)
        return _tushare_shibor_rows(pro, series_id=series_id, series_name=series_name, start_date=start_date, end_date=end_date)

    tushare_api = _resolve_tushare_api(name)
    if tushare_api is None:
        return []

    request_start = _tushare_request_start_month(tushare_api, name, start_date)
    time.sleep(0.3)
    frame = {
        "cn_cpi": pro.cn_cpi,
        "cn_gdp": pro.cn_gdp,
        "cn_m": lambda: pro.cn_m(start_m=request_start, end_m=end_date[:7].replace("-", "")),
        "cn_pmi": lambda: pro.cn_pmi(start_m=request_start, end_m=end_date[:7].replace("-", "")),
        "sf_month": lambda: pro.sf_month(start_m=request_start, end_m=end_date[:7].replace("-", "")),
    }[tushare_api]()
    records = _records_from_frame(frame)
    mapped = _map_tushare_records(tushare_api, records, series_name=series_name)
    return [
        BackfillRow(
            series_id=series_id,
            series_name=series_name,
            trade_date=row["trade_date"],
            value_numeric=float(row["value"]),
            frequency=frequency,
            unit=unit,
        )
        for row in mapped
        if start_date <= row["trade_date"] <= end_date
    ]


def _tushare_shibor_rows(pro: Any, *, series_id: str, series_name: str, start_date: str, end_date: str) -> list[BackfillRow]:
    column_by_id = {
        "NCD.SHIBOR.1M": "1m",
        "NCD.SHIBOR.3M": "3m",
        "NCD.SHIBOR.6M": "6m",
        "NCD.SHIBOR.9M": "9m",
        "NCD.SHIBOR.1Y": "1y",
    }
    column = column_by_id.get(series_id)
    if column is None:
        match = re.search(r"SHIBOR:(\S+)", series_name, flags=re.IGNORECASE)
        column = {"1M": "1m", "3M": "3m", "6M": "6m", "9M": "9m", "1Y": "1y"}.get((match.group(1) if match else "").upper())
    if column is None:
        return []

    frame = pro.shibor(start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
    rows: list[BackfillRow] = []
    for record in _records_from_frame(frame):
        trade_date = normalize_trade_date(record.get("date"))
        value = _coerce_float(record.get(column))
        if trade_date is None or value is None:
            continue
        rows.append(
            BackfillRow(
                series_id=series_id,
                series_name=series_name,
                trade_date=trade_date,
                value_numeric=value,
                frequency="daily",
                unit="%",
            )
        )
    return rows


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[BackfillRow],
    source_version: str,
    vendor_version: str,
    run_id: str,
) -> int:
    if not rows:
        return 0
    # Keep the first occurrence per key, matching the previous row-by-row semantics.
    deduped: list[BackfillRow] = []
    seen_keys: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.series_id, row.trade_date)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(row)

    conn.execute(
        """
        create or replace temp table _macro_backfill_stage (
          series_id varchar,
          series_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar
        )
        """
    )
    try:
        conn.executemany(
            "insert into _macro_backfill_stage values (?, ?, ?, ?, ?, ?)",
            [
                (
                    row.series_id,
                    row.series_name,
                    row.trade_date,
                    row.value_numeric,
                    row.frequency,
                    row.unit,
                )
                for row in deduped
            ],
        )
        inserted = conn.execute(
            """
            insert into fact_choice_macro_daily (
              series_id,
              series_name,
              trade_date,
              value_numeric,
              frequency,
              unit,
              source_version,
              vendor_version,
              rule_version,
              quality_flag,
              run_id
            )
            select
              s.series_id,
              s.series_name,
              s.trade_date,
              s.value_numeric,
              s.frequency,
              s.unit,
              ?,
              ?,
              ?,
              'ok',
              ?
            from _macro_backfill_stage s
            where not exists (
              select 1
              from fact_choice_macro_daily f
              where f.series_id = s.series_id and f.trade_date = s.trade_date
            )
            """,
            [source_version, vendor_version, RULE_VERSION, run_id],
        ).fetchone()
    finally:
        conn.execute("drop table if exists _macro_backfill_stage")
    return int(inserted[0]) if inserted else 0


def _count_snapshot_rows(conn_path: Path, *, series_id: str, start_date: str, end_date: str) -> int:
    conn = duckdb.connect(str(conn_path), read_only=True)
    try:
        if not _relation_exists(conn, "choice_market_snapshot"):
            return 0
        row = conn.execute(
            """
            select count(*)
            from choice_market_snapshot
            where series_id = ? and trade_date between ? and ?
            """,
            [series_id, start_date, end_date],
        ).fetchone()
    finally:
        conn.close()
    return int(row[0] if row else 0)


def _relation_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select count(*)
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [table_name],
    ).fetchone()
    return bool(row and int(row[0]) > 0)


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _map_tushare_records(api: str, records: list[dict[str, object]], *, series_name: str) -> list[dict[str, object]]:
    if api == "sf_month" and _is_social_financing_stock_yoy_series(series_name):
        return _social_financing_stock_yoy_records(records)

    rows: list[dict[str, object]] = []
    for record in records:
        if api == "cn_cpi":
            trade_date = _month_to_trade_date(str(record.get("month") or ""))
            value = _pick_tushare_value(record, series_name, {"当月同比": "nt_yoy", "CPI": "nt_yoy"})
        elif api == "cn_gdp":
            trade_date = _quarter_to_trade_date(str(record.get("quarter") or ""))
            value = _pick_tushare_value(record, series_name, {"当季值": "gdp", "GDP": "gdp_yoy", "同比": "gdp_yoy"})
        elif api == "cn_m":
            trade_date = _month_to_trade_date(str(record.get("month") or ""))
            if "M1-M2" in series_name:
                m1_yoy = _coerce_float(record.get("m1_yoy"))
                m2_yoy = _coerce_float(record.get("m2_yoy"))
                value = (m1_yoy - m2_yoy) if m1_yoy is not None and m2_yoy is not None else None
            else:
                value = _pick_tushare_value(
                    record,
                    series_name,
                    {
                        "M0:环比": "m0_mom",
                        "M1:环比": "m1_mom",
                        "M2:环比": "m2_mom",
                        "M0:同比": "m0_yoy",
                        "M1:同比": "m1_yoy",
                        "M2:同比": "m2_yoy",
                        "M0": "m0",
                        "M1": "m1",
                        "M2": "m2",
                    },
                )
        elif api == "cn_pmi":
            trade_date = _month_to_trade_date(str(record.get("month") or record.get("MONTH") or ""))
            value = _pick_tushare_value(record, series_name, {"PMI": "pmi", "制造业": "pmi"})
        elif api == "sf_month":
            trade_date = _month_to_trade_date(str(record.get("month") or ""))
            value = _pick_tushare_value(record, series_name, {"社融": "inc_month", "社会融资": "inc_month"})
        else:
            continue
        if trade_date and value is not None:
            rows.append({"trade_date": trade_date, "value": float(value)})
    return rows


def _social_financing_stock_yoy_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    stock_by_month: dict[str, float] = {}
    for record in records:
        month = str(record.get("month") or "").strip()
        if len(month) != 6 or not month.isdigit():
            continue
        value = _coerce_float(record.get("stk_endval"))
        if value is None:
            continue
        stock_by_month[month] = value

    rows: list[dict[str, object]] = []
    for month in sorted(stock_by_month):
        previous_month = f"{int(month[:4]) - 1}{month[4:]}"
        previous_value = stock_by_month.get(previous_month)
        if previous_value is None or previous_value == 0:
            continue
        rows.append(
            {
                "trade_date": _month_to_trade_date(month),
                "value": (stock_by_month[month] / previous_value - 1) * 100,
            }
        )
    return rows


def _is_social_financing_stock_yoy_series(series_name: str) -> bool:
    key = str(series_name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if "social_financing_stock_yoy" in key or "sf_stock_yoy" in key:
        return True
    return "社会融资规模存量" in series_name and "同比" in series_name


def _tushare_request_start_month(api: str, series_name: str, start_date: str) -> str:
    start_month = start_date[:7].replace("-", "")
    if api == "sf_month" and _is_social_financing_stock_yoy_series(series_name):
        return f"{int(start_month[:4]) - 1}{start_month[4:]}"
    return start_month


def _pick_tushare_value(record: dict[str, object], series_name: str, mapping: dict[str, str]) -> float | None:
    if "pmi" in mapping.values():
        key = str(series_name or "").strip().lower().replace("-", "_").replace(" ", "_")
        if "new_orders" in key or "new_order" in key or "新订单" in series_name or "pmi010500" in key:
            return _coerce_float(record.get("pmi010500") or record.get("PMI010500"))
        return _coerce_float(record.get("pmi010000") or record.get("PMI010000") or record.get("pmi"))

    for needle, field in mapping.items():
        if needle in series_name:
            if field == "pmi":
                field = "PMI010500" if "新订单" in series_name else "PMI010000"
            return _coerce_float(record.get(field))
    first_field = next(iter(mapping.values()), None)
    if first_field == "pmi":
        first_field = "PMI010500" if "新订单" in series_name else "PMI010000"
    return _coerce_float(record.get(first_field)) if first_field else None


def _resolve_tushare_api(series_name: str) -> str | None:
    name = series_name
    key = str(series_name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if "social_financing_stock_yoy" in key or "sf_stock_yoy" in key:
        return "sf_month"
    if "CPI" in name:
        return "cn_cpi"
    if "GDP" in name:
        return "cn_gdp"
    if "广义货币M2/" in name:
        return None
    if re.search(r"^(M[012](:|$)|M[012]:|M1-M2)", name):
        return "cn_m"
    if "PMI" in name:
        return "cn_pmi"
    if "社融" in name or "社会融资" in name:
        return "sf_month"
    return None


def _is_commodity_series(series_name: str) -> bool:
    return any(token in series_name for token in ("现货", "螺纹", "Brent", "原油", "黄金", "铜", "商品"))


def _is_tushare_macro_series(series_name: str) -> bool:
    return _resolve_tushare_api(series_name) is not None


def _is_spread_series(series_name: str) -> bool:
    return "利差" in series_name


def _is_daily_rate_series(series_name: str, series_id: str) -> bool:
    upper = series_name.upper()
    if "SHIBOR" in upper or "DR007" in upper:
        return True
    if "国债" in series_name and "收益率" in series_name:
        return True
    if series_id in {"CA.DR007", "E1000180", "EMM00166466"}:
        return True
    return False


def _infer_frequency(series_name: str, catalog_frequency: str) -> str:
    if catalog_frequency and catalog_frequency != "unknown":
        return catalog_frequency
    if _resolve_tushare_api(series_name) == "cn_gdp":
        return "quarterly"
    if _resolve_tushare_api(series_name) in {"cn_cpi", "cn_m", "cn_pmi", "sf_month"}:
        return "monthly"
    if _is_daily_rate_series(series_name, ""):
        return "daily"
    return "unknown"


def _tushare_token_configured() -> bool:
    return bool(resolve_tushare_token_with_settings_fallback(get_settings()))


def _dedupe_sources(sources: list[BackfillSource]) -> list[BackfillSource]:
    seen: set[BackfillSource] = set()
    ordered: list[BackfillSource] = []
    for source in sources:
        if source in seen:
            continue
        seen.add(source)
        ordered.append(source)
    return ordered


def _validate_iso_date(value: str, *, field_name: str) -> None:
    date.fromisoformat(value)


def _month_to_trade_date(month: str) -> str | None:
    text = str(month or "").strip()
    if len(text) == 6 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-01"
    return normalize_trade_date(text)


def _quarter_to_trade_date(quarter: str) -> str | None:
    q = str(quarter or "").strip().upper()
    if len(q) >= 6 and "Q" in q:
        year = int(q[:4])
        qn = q[5:6]
        ends = {"1": "-03-31", "2": "-06-30", "3": "-09-30", "4": "-12-31"}
        if qn in ends:
            return f"{year}{ends[qn]}"
    return normalize_trade_date(q)


def normalize_trade_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    normalized = text.replace("/", "-")
    if len(normalized) >= 10 and normalized[4] == "-" and normalized[7] == "-":
        return normalized[:10]
    return normalized


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    converted = float(text)
    return converted if math.isfinite(converted) else None


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill sparse macro series in DuckDB.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan only; do not fetch or insert.")
    mode.add_argument(
        "--fetch-preview",
        action="store_true",
        help="Fetch real upstream rows and report lineage without opening DuckDB for writes.",
    )
    parser.add_argument("--start-date", default="2024-01-01", help="Backfill window start (YYYY-MM-DD).")
    parser.add_argument("--end-date", default=None, help="Backfill window end (YYYY-MM-DD); defaults to today.")
    parser.add_argument(
        "--series-names",
        nargs="+",
        default=None,
        help="Optional series_name filter; omit to scan all sparse series.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        type=_normalize_source_arg,
        choices=[source.value for source in BackfillSource],
        default=None,
        help="Explicit source allow-list; configured plan order remains authoritative.",
    )
    parser.add_argument(
        "--duckdb-path",
        default=str(_REPO_ROOT / "data" / "moss.duckdb"),
        help="Path to DuckDB file.",
    )
    args = parser.parse_args()
    payload = backfill_macro_series(
        duckdb_path=args.duckdb_path,
        series_names=args.series_names,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        fetch_preview=args.fetch_preview,
        sources_filter=args.sources,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload.get("errors"):
        raise SystemExit(2)
