from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.governance.locks import LockDefinition, acquire_lock
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
from backend.app.tasks.pnl_materialize import (
    CACHE_KEY,
    PNL_MATERIALIZE_LOCK,
    PNL_RESULT_CACHE_VERSION,
    materialize_pnl_facts,
)


DISABLED_DETAIL = "Formal /api/pnl endpoints are planned but disabled in Phase 1."
PNL_CACHE_KEY = CACHE_KEY
PNL_CACHE_VERSION = PNL_RESULT_CACHE_VERSION
PNL_JOB_NAME = "pnl_materialize"
PENDING_SOURCE_VERSION = "sv_pnl_pending"
TWOPLACES = Decimal("0.01")
IN_FLIGHT_STATUSES = {"queued", "running"}
STALE_IN_FLIGHT_AFTER = timedelta(hours=1)
SAFE_SYNC_FALLBACK_MESSAGES = ("queue disabled", "broker unavailable")
SAFE_SYNC_FALLBACK_EXCEPTIONS = (ConnectionError, OSError, TimeoutError)


class PnlRefreshServiceError(RuntimeError):
    pass


class PnlRefreshConflictError(RuntimeError):
    pass


def pnl_phase1_disabled_payload() -> dict[str, object]:
    return PnlPhase1DisabledResponse(detail=DISABLED_DETAIL).model_dump(mode="json")


def refresh_pnl(settings: Settings, *, report_date: str | None = None) -> dict[str, object]:
    refresh_input = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path,
        data_root=resolve_pnl_data_input_root(),
        report_date=report_date,
    )
    try:
        with acquire_lock(
            _refresh_trigger_lock(report_date=refresh_input.report_date),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
            existing = _latest_inflight_refresh(
                settings,
                report_date=refresh_input.report_date,
            )
            if existing is not None:
                raise PnlRefreshConflictError(
                    f"Pnl refresh already in progress for report_date={refresh_input.report_date}."
                )

            run_id = _build_run_id()
            queued_at = datetime.now(timezone.utc).isoformat()
            GovernanceRepository(base_dir=settings.governance_path).append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **CacheBuildRunRecord(
                        run_id=run_id,
                        job_name=PNL_JOB_NAME,
                        status="queued",
                        cache_key=CACHE_KEY,
                        lock=PNL_MATERIALIZE_LOCK.key,
                        source_version=PENDING_SOURCE_VERSION,
                        vendor_version="vv_none",
                    ).model_dump(),
                    "report_date": refresh_input.report_date,
                    "queued_at": queued_at,
                },
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
            except Exception as exc:
                if _should_use_sync_fallback(settings, exc):
                    try:
                        payload = PnlMaterializePayload.model_validate(
                            materialize_pnl_facts.fn(**actor_kwargs)
                        )
                    except Exception as fallback_exc:
                        raise PnlRefreshServiceError(
                            "Pnl refresh failed during sync fallback."
                        ) from fallback_exc
                    return {
                        **payload.model_dump(mode="json"),
                        "job_name": PNL_JOB_NAME,
                        "trigger_mode": "sync-fallback",
                    }

                _record_dispatch_failure(
                    settings=settings,
                    run_id=run_id,
                    report_date=refresh_input.report_date,
                    error_message="Pnl refresh queue dispatch failed.",
                )
                raise PnlRefreshServiceError("Pnl refresh queue dispatch failed.") from exc
    except TimeoutError as exc:
        raise PnlRefreshConflictError(
            f"Pnl refresh already in progress for report_date={refresh_input.report_date}."
        ) from exc


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


def _refresh_trigger_lock(*, report_date: str) -> LockDefinition:
    return LockDefinition(
        key=f"{PNL_MATERIALIZE_LOCK.key}:{report_date}:trigger",
        ttl_seconds=30,
    )


def _load_refresh_run_records(settings: Settings) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == CACHE_KEY and str(record.get("job_name")) == PNL_JOB_NAME
    ]


def _latest_inflight_refresh(
    settings: Settings,
    *,
    report_date: str,
) -> dict[str, object] | None:
    by_run_id: dict[str, dict[str, object]] = {}
    for record in _load_refresh_run_records(settings):
        if str(record.get("report_date")) != report_date:
            continue
        by_run_id[str(record.get("run_id"))] = record
    stale_records: list[dict[str, object]] = []
    for record in reversed(list(by_run_id.values())):
        if str(record.get("status")) in IN_FLIGHT_STATUSES:
            if _is_stale_inflight_record(record):
                stale_records.append(record)
                continue
            return record
    for record in stale_records:
        _mark_stale_inflight_run(
            settings=settings,
            run_id=str(record.get("run_id")),
            report_date=report_date,
            error_message="Marked stale pnl refresh run as failed.",
        )
    return None


def _is_stale_inflight_record(record: dict[str, object]) -> bool:
    for field_name in ("started_at", "queued_at", "created_at"):
        raw_value = str(record.get(field_name) or "").strip()
        if not raw_value:
            continue
        timestamp = _parse_timestamp(raw_value)
        return datetime.now(timezone.utc) - timestamp > STALE_IN_FLIGHT_AFTER
    return False


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mark_stale_inflight_run(
    *,
    settings: Settings,
    run_id: str,
    report_date: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": PNL_JOB_NAME,
            "status": "failed",
            "cache_key": CACHE_KEY,
            "lock": PNL_MATERIALIZE_LOCK.key,
            "source_version": "sv_pnl_stale",
            "vendor_version": "vv_none",
            "report_date": report_date,
            "error_message": error_message,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _should_use_sync_fallback(settings: Settings, exc: Exception) -> bool:
    if str(settings.environment).lower() == "production":
        return False
    if isinstance(exc, SAFE_SYNC_FALLBACK_EXCEPTIONS):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in SAFE_SYNC_FALLBACK_MESSAGES)


def _record_dispatch_failure(
    *,
    settings: Settings,
    run_id: str,
    report_date: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": PNL_JOB_NAME,
            "status": "failed",
            "cache_key": CACHE_KEY,
            "lock": PNL_MATERIALIZE_LOCK.key,
            "source_version": "sv_pnl_failed",
            "vendor_version": "vv_none",
            "report_date": report_date,
            "error_message": error_message,
        },
    )
