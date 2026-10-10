"""Schedulable orchestration for homepage macro release source refreshes."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, SupportsIndex, SupportsInt, TypedDict

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.services.home_macro_period_freshness import (
    home_macro_freshness_age_days,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.macro_backfill import backfill_macro_series
from backend.app.tasks.nbs_gdp_release_ingest import run_nbs_gdp_release_ingest_once
from backend.app.tasks.nbs_inflation_release_ingest import (
    run_nbs_inflation_release_ingest_once,
)
from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once

_REQUIRED_SERIES: tuple[tuple[str, str, Literal["monthly", "quarterly"]], ...] = (
    ("tushare.macro.cn_cpi.monthly", "China CPI YoY", "monthly"),
    ("tushare.macro.cn_ppi.monthly", "China PPI YoY", "monthly"),
    ("tushare.macro.cn_gdp.quarterly", "China GDP YoY", "quarterly"),
    ("M0017126", "制造业PMI", "monthly"),
    ("M5525763", "社会融资规模存量:同比", "monthly"),
    ("M0001385", "M2:同比", "monthly"),
)
_CYCLE_BACKFILL_SERIES: tuple[tuple[str, str], ...] = (
    ("M0017126", "制造业PMI"),
    ("M5525763", "社会融资规模存量:同比"),
    ("M0001385", "M2:同比"),
)
_CYCLE_BACKFILL_IDS = frozenset(series_id for series_id, _label in _CYCLE_BACKFILL_SERIES)
_FRESH_DAYS = {"monthly": 45, "quarterly": 100}
_NBS_GDP_SERIES = "nbs.macro.cn_gdp.quarterly"
_TUSHARE_GDP_SERIES = "tushare.macro.cn_gdp.quarterly"
_NBS_CPI_SERIES = "nbs.macro.cn_cpi.monthly"
_NBS_PPI_SERIES = "nbs.macro.cn_ppi.monthly"
_TUSHARE_CPI_SERIES = "tushare.macro.cn_cpi.monthly"
_TUSHARE_PPI_SERIES = "tushare.macro.cn_ppi.monthly"
_GDP_CANDIDATES: tuple[tuple[str, str, int], ...] = (
    (_NBS_GDP_SERIES, "NBS official release", 1),
    (_TUSHARE_GDP_SERIES, "Tushare", 2),
)
_INFLATION_CANDIDATES: dict[str, tuple[tuple[str, str, int], ...]] = {
    _TUSHARE_CPI_SERIES: (
        (_NBS_CPI_SERIES, "NBS official release", 1),
        (_TUSHARE_CPI_SERIES, "Tushare", 2),
    ),
    _TUSHARE_PPI_SERIES: (
        (_NBS_PPI_SERIES, "NBS official release", 1),
        (_TUSHARE_PPI_SERIES, "Tushare", 2),
    ),
}
_READ_SERIES_IDS = tuple(item[0] for item in _REQUIRED_SERIES) + (
    _NBS_GDP_SERIES,
    _NBS_CPI_SERIES,
    _NBS_PPI_SERIES,
)


class _Freshness(TypedDict):
    status: str
    age_days: int | None


class _SeriesCandidate(TypedDict):
    selected_series_id: str
    selected_vendor: str
    priority: int
    latest_observation: str
    freshness: _Freshness


class _CycleBackfillArgs(TypedDict):
    duckdb_path: str
    series_names: list[str]
    start_date: str
    end_date: str
    dry_run: bool


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"home-macro-release-{stamp}-{uuid.uuid4().hex[:8]}"


def _read_latest_observations(duckdb_path: str | Path) -> dict[str, str]:
    path = Path(duckdb_path)
    if not path.exists():
        return {}
    conn = duckdb.connect(str(path), read_only=True)
    try:
        latest: dict[str, str] = {}
        for table, series_column in (
            ("std_external_macro_daily", "series_id"),
            ("fact_choice_macro_daily", "series_id"),
        ):
            exists = conn.execute(
                "select count(*) from information_schema.tables where table_name = ?",
                [table],
            ).fetchone()
            if not exists or int(exists[0]) == 0:
                continue
            rows = conn.execute(
                f"""
                select {series_column}, max(try_cast(trade_date as date))
                from {table}
                where {series_column} in ({','.join('?' for _ in _READ_SERIES_IDS)})
                group by {series_column}
                """,
                list(_READ_SERIES_IDS),
            ).fetchall()
            for series_id, observation_date in rows:
                if observation_date is not None:
                    latest[str(series_id)] = observation_date.isoformat()
        return latest
    finally:
        conn.close()


def _freshness(
    latest: str | None, *, today: date, cadence: Literal["monthly", "quarterly"]
) -> _Freshness:
    if latest is None:
        return {"status": "missing", "age_days": None}
    age_days = home_macro_freshness_age_days(
        date.fromisoformat(latest),
        today,
        cadence=cadence,
    )
    return {
        "status": "ready" if age_days <= _FRESH_DAYS[cadence] else "stale",
        "age_days": age_days,
    }


def _select_series_candidate(
    latest: dict[str, str],
    *,
    today: date,
    cadence: Literal["monthly", "quarterly"],
    candidates_config: tuple[tuple[str, str, int], ...],
) -> dict[str, object]:
    candidates: list[_SeriesCandidate] = []
    for series_id, vendor, priority in candidates_config:
        observation = latest.get(series_id)
        if observation is None:
            continue
        freshness = _freshness(observation, today=today, cadence=cadence)
        candidates.append(
            {
                "selected_series_id": series_id,
                "selected_vendor": vendor,
                "priority": priority,
                "latest_observation": observation,
                "freshness": freshness,
            }
        )
    if not candidates:
        return {
            "selected_series_id": None,
            "selected_vendor": None,
            "latest_observation": None,
            "freshness": {"status": "missing", "age_days": None},
            "selection_status": "missing",
        }
    selected = max(
        candidates,
        key=lambda item: (
            item["freshness"]["status"] != "stale",
            str(item["latest_observation"]),
            -int(item["priority"]),
        ),
    )
    selection_status = str(selected["freshness"]["status"])
    primary_series_id = min(candidates_config, key=lambda item: item[2])[0]
    if selected["selected_series_id"] != primary_series_id and selection_status == "ready":
        selection_status = "fallback"
    return {**selected, "selection_status": selection_status}


def _select_gdp_candidate(
    latest: dict[str, str],
    *,
    today: date,
) -> dict[str, object]:
    return _select_series_candidate(
        latest,
        today=today,
        cadence="quarterly",
        candidates_config=_GDP_CANDIDATES,
    )


def _select_inflation_candidate(
    latest: dict[str, str],
    *,
    today: date,
    tushare_series_id: str,
) -> dict[str, object]:
    return _select_series_candidate(
        latest,
        today=today,
        cadence="monthly",
        candidates_config=_INFLATION_CANDIDATES[tushare_series_id],
    )


def _mapping_rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("macro ingest rows must be a sequence")
    return [item for item in value if isinstance(item, dict)]


def _required_int(value: object) -> int:
    if not isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)):
        raise TypeError("macro materialized row count is not convertible to int")
    return int(value)


def refresh_home_macro_release_sources(
    *,
    today: date | None = None,
    dry_run: bool = False,
    duckdb_path: str | Path | None = None,
    nbs_inflation_source_ip: str | None = None,
) -> dict[str, object]:
    """Refresh governed macro rows, including the cycle PMI/credit inputs."""
    started = time.monotonic()
    effective_today = today or date.today()
    resolved_path = str(duckdb_path or get_settings().duckdb_path)
    run_id = _new_run_id()
    before = _read_latest_observations(resolved_path)
    start_date = (effective_today - timedelta(days=90)).isoformat()
    end_date = effective_today.isoformat()
    cycle_kwargs: _CycleBackfillArgs = {
        "duckdb_path": resolved_path,
        "series_names": [label for _series_id, label in _CYCLE_BACKFILL_SERIES],
        "start_date": start_date,
        "end_date": end_date,
        "dry_run": dry_run,
    }
    if dry_run:
        cycle_plan = backfill_macro_series(**cycle_kwargs)
        return {
            "status": "dry_run",
            "run_id": run_id,
            "series": [
                {
                    "series_id": series_id,
                    "label": label,
                    "status": "planned",
                    "latest_observation": before.get(series_id),
                    "materialized_rows": 0,
                    "freshness": _freshness(before.get(series_id), today=effective_today, cadence=cadence),
                    **(
                        {
                            "source_candidates": [
                                _NBS_GDP_SERIES,
                                _TUSHARE_GDP_SERIES,
                            ]
                        }
                        if series_id == _TUSHARE_GDP_SERIES
                        else {
                            "source_candidates": [
                                candidate[0]
                                for candidate in _INFLATION_CANDIDATES[series_id]
                            ]
                        }
                        if series_id in _INFLATION_CANDIDATES
                        else {}
                    ),
                }
                for series_id, label, cadence in _REQUIRED_SERIES
            ],
            "materialized_rows": 0,
            "cycle_plan": cycle_plan,
            "warnings": [
                "Dry-run performs no NBS/Tushare fetch and no DuckDB writes.",
                "PMI and credit proxy inputs use the governed official-first backfill plan with Tushare fallback.",
            ],
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }

    ingest_error: str | None = None
    nbs_error: str | None = None
    nbs_inflation_error: str | None = None
    try:
        nbs_ingest = run_nbs_gdp_release_ingest_once(reference_date=effective_today)
    except Exception as exc:  # noqa: BLE001 - GDP provider failure must not block independent inflation and fallback sources.
        nbs_error = f"NBS GDP ingest failed (error_type={type(exc).__name__})."
        nbs_ingest = {"status": "error", "error": nbs_error, "materialized_rows": 0}

    try:
        nbs_inflation_ingest = run_nbs_inflation_release_ingest_once(
            reference_date=effective_today,
            source_ip=nbs_inflation_source_ip,
        )
    except Exception as exc:  # noqa: BLE001 - NBS failure must remain a failed receipt while independent macro sources continue.
        nbs_inflation_error = f"NBS inflation ingest failed (error_type={type(exc).__name__})."
        nbs_inflation_ingest = {
            "status": "error",
            "error": nbs_inflation_error,
            "results": [],
            "materialized_rows": 0,
        }

    try:
        ingest = run_tushare_macro_ingest_once()
    except Exception as exc:  # noqa: BLE001 - Tushare failures must preserve usable official releases and still run cycle backfill.
        ingest_error = f"Tushare macro ingest failed (error_type={type(exc).__name__})."
        ingest = {"status": "error", "results": [], "succeeded": [], "failed": []}

    try:
        cycle = backfill_macro_series(**cycle_kwargs)
    except Exception as exc:  # noqa: BLE001 - Cycle backfill failure must return failed per-series receipts alongside other source results.
        cycle = {
            "status": "failed",
            "total_added": 0,
            "results": {label: 0 for _series_id, label in _CYCLE_BACKFILL_SERIES},
            "errors": {"cycle_macro_batch": f"Cycle macro backfill failed (error_type={type(exc).__name__})."},
            "source_by_series": {},
            "vendor_versions": {},
        }
    after = _read_latest_observations(resolved_path)

    ingest_rows = {
        str(item.get("series_id")): _required_int(item.get("materialized_rows") or 0)
        for item in _mapping_rows(ingest.get("results", []))
    }
    failed_ingest_ids = {
        str(item.get("series_id"))
        for item in _mapping_rows(ingest.get("failed", []))
    }
    cycle_errors_value = cycle.get("errors")
    cycle_errors = cycle_errors_value if isinstance(cycle_errors_value, dict) else {}
    cycle_results_value = cycle.get("results")
    cycle_results = cycle_results_value if isinstance(cycle_results_value, dict) else {}
    before_gdp = _select_gdp_candidate(before, today=effective_today)
    after_gdp = _select_gdp_candidate(after, today=effective_today)
    before_inflation = {
        series_id: _select_inflation_candidate(
            before,
            today=effective_today,
            tushare_series_id=series_id,
        )
        for series_id in _INFLATION_CANDIDATES
    }
    after_inflation = {
        series_id: _select_inflation_candidate(
            after,
            today=effective_today,
            tushare_series_id=series_id,
        )
        for series_id in _INFLATION_CANDIDATES
    }
    nbs_inflation_rows = {
        str(item.get("series_id")): _required_int(item.get("materialized_rows") or 0)
        for item in _mapping_rows(nbs_inflation_ingest.get("results", []))
    }
    series_results: list[dict[str, object]] = []
    for series_id, label, cadence in _REQUIRED_SERIES:
        if series_id in _INFLATION_CANDIDATES:
            selected_before = before_inflation[series_id]
            selected_after = after_inflation[series_id]
            selected_series_id = selected_after["selected_series_id"]
            latest_after = selected_after["latest_observation"]
            freshness = selected_after["freshness"]
            if selected_series_id in {_NBS_CPI_SERIES, _NBS_PPI_SERIES}:
                materialized_rows = nbs_inflation_rows.get(str(selected_series_id), 0)
            else:
                materialized_rows = ingest_rows.get(series_id, 0)
            if latest_after is None:
                status = "error"
            elif selected_after["selection_status"] == "stale":
                status = "partial"
            else:
                status = "success"
            series_results.append(
                {
                    "series_id": series_id,
                    "label": label,
                    "status": status,
                    "previous_observation": selected_before["latest_observation"],
                    "latest_observation": latest_after,
                    "materialized_rows": materialized_rows,
                    "freshness": freshness,
                    "selected_series_id": selected_series_id,
                    "selected_vendor": selected_after["selected_vendor"],
                    "selection_status": selected_after["selection_status"],
                }
            )
            continue

        if series_id == _TUSHARE_GDP_SERIES:
            selected_series_id = after_gdp["selected_series_id"]
            latest_after = after_gdp["latest_observation"]
            freshness = after_gdp["freshness"]
            if selected_series_id == _NBS_GDP_SERIES:
                materialized_rows = _required_int(nbs_ingest.get("materialized_rows") or 0)
            else:
                materialized_rows = ingest_rows.get(_TUSHARE_GDP_SERIES, 0)
            if latest_after is None:
                status = "error"
            elif after_gdp["selection_status"] == "stale":
                status = "partial"
            else:
                status = "success"
            series_results.append(
                {
                    "series_id": series_id,
                    "label": label,
                    "status": status,
                    "previous_observation": before_gdp["latest_observation"],
                    "latest_observation": latest_after,
                    "materialized_rows": materialized_rows,
                    "freshness": freshness,
                    "selected_series_id": selected_series_id,
                    "selected_vendor": after_gdp["selected_vendor"],
                    "selection_status": after_gdp["selection_status"],
                }
            )
            continue

        latest_before = before.get(series_id)
        latest_after = after.get(series_id)
        if series_id in _CYCLE_BACKFILL_IDS:
            has_error = bool(cycle_errors) or str(cycle.get("status")) in {
                "failed",
                "blocked",
                "error",
            }
            materialized_rows = _required_int(cycle_results.get(label) or 0)
        else:
            has_error = ingest_error is not None or series_id in failed_ingest_ids
            materialized_rows = ingest_rows.get(series_id, 0)
        freshness = _freshness(latest_after, today=effective_today, cadence=cadence)
        if has_error or latest_after is None:
            status = "error"
        elif freshness["status"] == "stale":
            status = "partial"
        else:
            status = "success"
        series_results.append(
            {
                "series_id": series_id,
                "label": label,
                "status": status,
                "previous_observation": latest_before,
                "latest_observation": latest_after,
                "materialized_rows": materialized_rows,
                "freshness": freshness,
            }
        )

    statuses = {str(item["status"]) for item in series_results}
    if statuses == {"success"}:
        overall_status = "success"
    elif statuses == {"error"}:
        overall_status = "error"
    else:
        overall_status = "partial"
    source_by_series_value = cycle.get("source_by_series")
    source_by_series = dict(source_by_series_value) if isinstance(source_by_series_value, dict) else {}
    vendor_versions_value = cycle.get("vendor_versions")
    vendor_versions = dict(vendor_versions_value) if isinstance(vendor_versions_value, dict) else {}
    warnings = [
        "CPI/PPI select the freshest NBS official release with Tushare fallback.",
        (
            f"GDP selected {after_gdp['selected_vendor']} "
            f"({after_gdp['selection_status']})."
        ),
        "PMI and credit proxy inputs are refreshed through the governed official-first backfill plan with Tushare fallback.",
    ]
    if source_by_series:
        selected_sources = ", ".join(
            f"{series_id}={source_by_series.get(series_id, 'unknown')}"
            for series_id, _label in _CYCLE_BACKFILL_SERIES
        )
        warnings.append(f"Cycle macro selected sources: {selected_sources}.")
    nbs_issue = nbs_error
    if nbs_issue is None and str(nbs_ingest.get("status")) != "success":
        nbs_issue = str(nbs_ingest.get("error") or nbs_ingest.get("status"))
    if nbs_issue:
        warnings.append(f"NBS GDP ingest issue: {nbs_issue}")
    inflation_issue = nbs_inflation_error
    if inflation_issue is None and str(nbs_inflation_ingest.get("status")) != "success":
        inflation_issue = str(
            nbs_inflation_ingest.get("error") or nbs_inflation_ingest.get("status")
        )
    if inflation_issue:
        warnings.append(f"NBS inflation ingest issue: {inflation_issue}")
    if ingest_error:
        warnings.append(f"Tushare macro ingest error: {ingest_error}")
    for name, error in cycle_errors.items():
        warnings.append(f"Cycle macro backfill error for {name}: {error}")

    return {
        "status": overall_status,
        "run_id": run_id,
        "ingest_batch_id": ingest.get("ingest_batch_id"),
        "nbs_ingest_batch_id": nbs_ingest.get("ingest_batch_id"),
        "nbs_inflation_ingest_batch_id": nbs_inflation_ingest.get("ingest_batch_id"),
        "series": series_results,
        "materialized_rows": sum(_required_int(item["materialized_rows"]) for item in series_results),
        "source_by_series": source_by_series,
        "vendor_versions": vendor_versions,
        "warnings": warnings,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


refresh_home_macro_release_sources_actor = register_actor_once(
    "refresh_home_macro_release_sources",
    refresh_home_macro_release_sources,
    time_limit_ms=3_600_000,
)
