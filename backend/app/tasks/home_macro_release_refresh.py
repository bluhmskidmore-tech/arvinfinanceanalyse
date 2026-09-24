"""Schedulable orchestration for homepage macro release source refreshes."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.services.home_macro_period_freshness import (
    home_macro_freshness_age_days,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.macro_backfill import backfill_macro_series
from backend.app.tasks.nbs_gdp_release_ingest import run_nbs_gdp_release_ingest_once
from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once

_REQUIRED_SERIES: tuple[tuple[str, str, Literal["monthly", "quarterly"]], ...] = (
    ("tushare.macro.cn_cpi.monthly", "China CPI YoY", "monthly"),
    ("tushare.macro.cn_ppi.monthly", "China PPI YoY", "monthly"),
    ("tushare.macro.cn_gdp.quarterly", "China GDP YoY", "quarterly"),
    ("M0017126", "制造业PMI", "monthly"),
)
_FRESH_DAYS = {"monthly": 45, "quarterly": 100}
_NBS_GDP_SERIES = "nbs.macro.cn_gdp.quarterly"
_TUSHARE_GDP_SERIES = "tushare.macro.cn_gdp.quarterly"
_GDP_CANDIDATES: tuple[tuple[str, str, int], ...] = (
    (_NBS_GDP_SERIES, "NBS official release", 1),
    (_TUSHARE_GDP_SERIES, "Tushare", 2),
)
_READ_SERIES_IDS = tuple(item[0] for item in _REQUIRED_SERIES) + (_NBS_GDP_SERIES,)


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


def _freshness(latest: str | None, *, today: date, cadence: str) -> dict[str, object]:
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


def _select_gdp_candidate(
    latest: dict[str, str],
    *,
    today: date,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for series_id, vendor, priority in _GDP_CANDIDATES:
        observation = latest.get(series_id)
        if observation is None:
            continue
        freshness = _freshness(observation, today=today, cadence="quarterly")
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
    if (
        selected["selected_series_id"] != _NBS_GDP_SERIES
        and selection_status == "ready"
    ):
        selection_status = "fallback"
    return {**selected, "selection_status": selection_status}


def refresh_home_macro_release_sources(
    *,
    today: date | None = None,
    dry_run: bool = False,
    duckdb_path: str | Path | None = None,
) -> dict[str, object]:
    """Refresh governed Tushare macro rows and the Tushare-only PMI overlap."""
    started = time.monotonic()
    effective_today = today or date.today()
    resolved_path = str(duckdb_path or get_settings().duckdb_path)
    run_id = _new_run_id()
    before = _read_latest_observations(resolved_path)
    start_date = (effective_today - timedelta(days=90)).isoformat()
    end_date = effective_today.isoformat()
    pmi_kwargs = {
        "duckdb_path": resolved_path,
        "series_names": ["制造业PMI"],
        "sources_filter": ["tushare_macro"],
        "start_date": start_date,
        "end_date": end_date,
        "dry_run": dry_run,
    }

    if dry_run:
        pmi_plan = backfill_macro_series(**pmi_kwargs)
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
                        else {}
                    ),
                }
                for series_id, label, cadence in _REQUIRED_SERIES
            ],
            "materialized_rows": 0,
            "pmi_plan": pmi_plan,
            "warnings": [
                "Dry-run performs no NBS/Tushare fetch and no DuckDB writes.",
                "PMI remains explicitly scoped to tushare_macro.",
            ],
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }

    ingest_error: str | None = None
    nbs_error: str | None = None
    try:
        nbs_ingest = run_nbs_gdp_release_ingest_once(reference_date=effective_today)
    except Exception as exc:
        nbs_error = str(exc)
        nbs_ingest = {"status": "error", "error": nbs_error, "materialized_rows": 0}

    try:
        ingest = run_tushare_macro_ingest_once()
    except Exception as exc:
        ingest_error = str(exc)
        ingest = {"status": "error", "results": [], "succeeded": [], "failed": []}

    try:
        pmi = backfill_macro_series(**pmi_kwargs)
    except Exception as exc:
        pmi = {
            "status": "failed",
            "total_added": 0,
            "results": {},
            "errors": {"制造业PMI": str(exc)},
            "source_by_series": {},
            "vendor_versions": {},
        }
    after = _read_latest_observations(resolved_path)

    ingest_rows = {
        str(item.get("series_id")): int(item.get("materialized_rows") or 0)
        for item in ingest.get("results", [])
        if isinstance(item, dict)
    }
    failed_ingest_ids = {
        str(item.get("series_id"))
        for item in ingest.get("failed", [])
        if isinstance(item, dict)
    }
    pmi_errors = pmi.get("errors") if isinstance(pmi.get("errors"), dict) else {}
    before_gdp = _select_gdp_candidate(before, today=effective_today)
    after_gdp = _select_gdp_candidate(after, today=effective_today)
    series_results: list[dict[str, object]] = []
    for series_id, label, cadence in _REQUIRED_SERIES:
        if series_id == _TUSHARE_GDP_SERIES:
            selected_series_id = after_gdp["selected_series_id"]
            latest_after = after_gdp["latest_observation"]
            freshness = after_gdp["freshness"]
            if selected_series_id == _NBS_GDP_SERIES:
                materialized_rows = int(nbs_ingest.get("materialized_rows") or 0)
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
        if series_id == "M0017126":
            has_error = bool(pmi_errors) or str(pmi.get("status")) in {
                "failed",
                "blocked",
                "error",
            }
            materialized_rows = int(pmi.get("total_added") or 0)
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
    source_by_series = dict(pmi.get("source_by_series") or {})
    vendor_versions = dict(pmi.get("vendor_versions") or {})
    warnings = [
        "CPI/PPI are refreshed from the Tushare standard macro ingest.",
        (
            f"GDP selected {after_gdp['selected_vendor']} "
            f"({after_gdp['selection_status']})."
        ),
        "PMI remains refreshed from actual vendor tushare_macro.",
    ]
    nbs_issue = nbs_error
    if nbs_issue is None and str(nbs_ingest.get("status")) != "success":
        nbs_issue = str(nbs_ingest.get("error") or nbs_ingest.get("status"))
    if nbs_issue:
        warnings.append(f"NBS GDP ingest issue: {nbs_issue}")
    if ingest_error:
        warnings.append(f"Tushare macro ingest error: {ingest_error}")
    for name, error in pmi_errors.items():
        warnings.append(f"PMI backfill error for {name}: {error}")

    return {
        "status": overall_status,
        "run_id": run_id,
        "ingest_batch_id": ingest.get("ingest_batch_id"),
        "nbs_ingest_batch_id": nbs_ingest.get("ingest_batch_id"),
        "series": series_results,
        "materialized_rows": sum(int(item["materialized_rows"]) for item in series_results),
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
