from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from backend.app.governance.settings import Settings
from backend.app.repositories.financial_result_publication_repo import canonical_json_bytes, sha256_bytes
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.schemas.pnl import PnlDatesPayload
from backend.app.schemas.result_meta import ResultEnvelope, ResultMeta
from backend.app.services.pnl_by_business_publication_service import (
    list_retained_pnl_by_business_publication_coverage,
)
from backend.app.services.pnl_task_dispatch import CACHE_KEY


def pnl_by_business_page_dates_envelope(settings: Settings) -> dict[str, object]:
    """List selectable page dates without opening the active writer database.

    Completed materialization receipts make a date selectable for preparation;
    only the separate page readiness response grants a published generation.
    This catalog does not assert per-source row coverage or financial readiness.
    """
    records = GovernanceRepository(base_dir=settings.governance_path).read_by_cache_keys(
        CACHE_BUILD_RUN_STREAM,
        (CACHE_KEY,),
    )
    latest_by_run: dict[str, Mapping[str, object]] = {}
    for record in records:
        if record.get("job_name") == "pnl_materialize" and record.get("cache_key") == CACHE_KEY:
            run_id = str(record.get("run_id") or "")
            if run_id:
                latest_by_run[run_id] = record
    completed = [record for record in latest_by_run.values() if record.get("status") == "completed"]
    report_dates = {_iso_date(record.get("report_date")) for record in completed}
    report_dates.discard(None)
    publication_catalog = list_retained_pnl_by_business_publication_coverage(
        settings,
    )
    report_dates.update(
        value
        for item in publication_catalog
        if (value := _iso_date(item.get("report_date"))) is not None
    )
    sorted_dates = sorted(str(value) for value in report_dates)
    identity = {
        "published_generations": sorted(
            (
                str(item.get("generation") or ""),
                str(item.get("manifest_sha256") or ""),
                str(item.get("report_date") or ""),
            )
            for item in publication_catalog
        ),
        "completed_runs": sorted(
            (str(record.get("run_id")), str(record.get("source_version") or ""))
            for record in completed
        ),
        "report_dates": sorted_dates,
    }
    meta = ResultMeta(
        trace_id="tr_pnl_by_business_page_dates",
        basis="analytical",
        result_kind="pnl.dates",
        formal_use_allowed=False,
        source_version=f"sv_pnl_page_dates_{sha256_bytes(canonical_json_bytes(identity))[:24]}",
        rule_version="rv_pnl_page_selectable_dates_v1",
        cache_version="cv_pnl_page_selectable_dates_v1",
        quality_flag="ok" if sorted_dates else "warning",
        source_surface="formal_pnl",
        filters_applied={
            "page": "by_business_insights",
            "catalog_basis": "completed_materialization_or_publication",
            "page_readiness_required": True,
        },
    )
    return ResultEnvelope(
        result_meta=meta.model_dump(mode="json"),
        result=PnlDatesPayload(
            report_dates=sorted_dates, formal_fi_report_dates=[], nonstd_bridge_report_dates=[]
        ).model_dump(mode="json"),
    ).model_dump(mode="json")


def _iso_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed.isoformat() if parsed.isoformat() == value else None
