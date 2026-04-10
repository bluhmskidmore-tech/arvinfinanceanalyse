from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.app.governance.settings import Settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.pnl import (
    PnlDataPayload,
    PnlDatesPayload,
    PnlFormalFiRow,
    PnlMaterializePayload,
    PnlNonStdBridgeRow,
    PnlOverviewPayload,
    PnlPhase1DisabledResponse,
)
from backend.app.schemas.result_meta import ResultMeta
from backend.app.services.pnl_source_service import (
    load_latest_pnl_refresh_input,
    resolve_pnl_data_input_root,
)
from backend.app.tasks.pnl_materialize import CACHE_KEY, PNL_MATERIALIZE_LOCK, materialize_pnl_facts


DISABLED_DETAIL = "Formal /api/pnl endpoints are planned but disabled in Phase 1."
PNL_CACHE_KEY = "pnl.phase2.materialize"
PNL_CACHE_VERSION = "cv_pnl_dates_data_v1"
PNL_JOB_NAME = "pnl_materialize"
PENDING_SOURCE_VERSION = "sv_pnl_pending"
TWOPLACES = Decimal("0.01")


def pnl_phase1_disabled_payload() -> dict[str, object]:
    return PnlPhase1DisabledResponse(detail=DISABLED_DETAIL).model_dump(mode="json")


def refresh_pnl(settings: Settings, *, report_date: str | None = None) -> dict[str, object]:
    refresh_input = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path,
        data_root=resolve_pnl_data_input_root(),
        report_date=report_date,
    )
    run_id = _build_run_id()
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        CacheBuildRunRecord(
            run_id=run_id,
            job_name=PNL_JOB_NAME,
            status="queued",
            cache_key=CACHE_KEY,
            lock=PNL_MATERIALIZE_LOCK.key,
            source_version=PENDING_SOURCE_VERSION,
            vendor_version="vv_none",
        ).model_dump(),
    )

    actor_kwargs = {
        "report_date": refresh_input.report_date,
        "is_month_end": refresh_input.is_month_end,
        "fi_rows": refresh_input.fi_rows,
        "nonstd_rows_by_type": refresh_input.nonstd_rows_by_type,
        "duckdb_path": str(settings.duckdb_path),
        "governance_dir": str(settings.governance_path),
        "run_id": run_id,
    }
    try:
        materialize_pnl_facts.send(**actor_kwargs)
        return {
            "status": "queued",
            "run_id": run_id,
            "job_name": PNL_JOB_NAME,
            "trigger_mode": "async",
            "cache_key": CACHE_KEY,
            "report_date": refresh_input.report_date,
        }
    except Exception:
        payload = PnlMaterializePayload.model_validate(materialize_pnl_facts.fn(**actor_kwargs))
        return {
            **payload.model_dump(mode="json"),
            "job_name": PNL_JOB_NAME,
            "trigger_mode": "sync-fallback",
        }


def pnl_import_status(settings: Settings, *, run_id: str | None = None) -> dict[str, object]:
    records = _load_refresh_run_records(settings)
    if run_id is not None:
        records = [record for record in records if str(record.get("run_id")) == run_id]
        if not records:
            raise ValueError(f"Unknown pnl refresh run_id={run_id}")
    if not records:
        return {
            "status": "idle",
            "job_name": PNL_JOB_NAME,
            "cache_key": CACHE_KEY,
            "trigger_mode": "idle",
        }

    latest = records[-1]
    status = str(latest.get("status", "unknown"))
    return {
        **latest,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
    }


def pnl_dates_envelope(*, duckdb_path: str, governance_dir: str) -> dict[str, object]:
    repo = PnlRepository(duckdb_path)
    formal_fi_report_dates = repo.list_formal_fi_report_dates()
    nonstd_bridge_report_dates = repo.list_nonstd_bridge_report_dates()
    payload = PnlDatesPayload(
        report_dates=repo.list_union_report_dates(),
        formal_fi_report_dates=formal_fi_report_dates,
        nonstd_bridge_report_dates=nonstd_bridge_report_dates,
    )
    meta = _formal_result_meta(
        governance_dir=governance_dir,
        trace_id="tr_pnl_dates",
        result_kind="pnl.dates",
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def pnl_data_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    repo = PnlRepository(duckdb_path)
    if report_date not in repo.list_union_report_dates():
        raise ValueError(
            f"No pnl data found for report_date={report_date} in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
        )

    payload = PnlDataPayload(
        report_date=report_date,
        formal_fi_rows=[PnlFormalFiRow(**row) for row in repo.fetch_formal_fi_rows(report_date)],
        nonstd_bridge_rows=[PnlNonStdBridgeRow(**row) for row in repo.fetch_nonstd_bridge_rows(report_date)],
    )
    meta = _formal_result_meta(
        governance_dir=governance_dir,
        trace_id=f"tr_pnl_data_{report_date}",
        result_kind="pnl.data",
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def pnl_overview_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    repo = PnlRepository(duckdb_path)
    if report_date not in repo.list_union_report_dates():
        raise ValueError(
            f"No pnl data found for report_date={report_date} in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
        )

    totals = repo.overview_totals(report_date)
    payload = PnlOverviewPayload(
        report_date=report_date,
        formal_fi_row_count=int(totals["formal_fi_row_count"]),
        nonstd_bridge_row_count=int(totals["nonstd_bridge_row_count"]),
        interest_income_514=_quantize_decimal(totals["interest_income_514"]),
        fair_value_change_516=_quantize_decimal(totals["fair_value_change_516"]),
        capital_gain_517=_quantize_decimal(totals["capital_gain_517"]),
        manual_adjustment=_quantize_decimal(totals["manual_adjustment"]),
        total_pnl=_quantize_decimal(totals["total_pnl"]),
    )
    meta = _formal_result_meta(
        governance_dir=governance_dir,
        trace_id=f"tr_pnl_overview_{report_date}",
        result_kind="pnl.overview",
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def _formal_result_meta(*, governance_dir: str, trace_id: str, result_kind: str) -> ResultMeta:
    lineage = _resolve_pnl_manifest_lineage(governance_dir)
    return ResultMeta(
        trace_id=trace_id,
        basis="formal",
        result_kind=result_kind,
        formal_use_allowed=True,
        source_version=str(lineage["source_version"]),
        vendor_version=str(lineage["vendor_version"]),
        rule_version=str(lineage["rule_version"]),
        cache_version=PNL_CACHE_VERSION,
        quality_flag="ok",
        scenario_flag=False,
    )


def _resolve_pnl_manifest_lineage(governance_dir: str) -> dict[str, object]:
    rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_MANIFEST_STREAM)
    matches = [row for row in rows if str(row.get("cache_key")) == PNL_CACHE_KEY]
    if not matches:
        raise RuntimeError(f"Canonical pnl lineage unavailable for cache_key={PNL_CACHE_KEY}.")
    latest = matches[-1]
    required = ("source_version", "vendor_version", "rule_version")
    missing = [key for key in required if key not in latest or latest.get(key) in (None, "")]
    if missing:
        raise RuntimeError(f"Canonical pnl lineage malformed for cache_key={PNL_CACHE_KEY}: missing {', '.join(missing)}.")
    return latest


def _quantize_decimal(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES)


def _build_run_id() -> str:
    return f"{PNL_JOB_NAME}:{datetime.now(timezone.utc).isoformat()}"


def _load_refresh_run_records(settings: Settings) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == CACHE_KEY and str(record.get("job_name")) == PNL_JOB_NAME
    ]
