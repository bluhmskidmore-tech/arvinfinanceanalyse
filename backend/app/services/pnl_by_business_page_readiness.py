from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from backend.app.governance.settings import Settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION, PnlRepository
from backend.app.services.pnl_by_business_adjustment_handoff import (
    pnl_by_business_adjustment_handoff_status,
)
from backend.app.services.pnl_by_business_publication_service import (
    list_retained_pnl_by_business_publications,
)
from backend.app.services.pnl_service_by_business_support import (
    PnlByBusinessPageDependency,
    _normalize_pnl_by_business_precompute_as_of_date,
    _normalize_pnl_by_business_precompute_year,
    pnl_by_business_page_dependencies,
)
from backend.app.services.pnl_task_dispatch import (
    PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
    PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
    rebuild_pnl_by_business_precompute,
)

_INFLIGHT = frozenset({"queued", "running"})
_STALE_AFTER = timedelta(hours=2)
_PNL_BY_BUSINESS_PAGE_CACHE_KEY = "pnl_by_business_page_prepare"


def pnl_by_business_published_page_status(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None,
    repository_cls: type[PnlRepository] = PnlRepository,
) -> dict[str, object]:
    normalized_year = _normalize_pnl_by_business_precompute_year(year)
    normalized_date = _normalize_pnl_by_business_precompute_as_of_date(
        year=normalized_year,
        as_of_date=as_of_date,
    )
    # Keep this compatibility argument for callers/tests that inject the legacy
    # repository class.  The enabled path must never open the active DuckDB.
    del repository_cls
    publication_catalog = list_retained_pnl_by_business_publications(
        settings,
        year=normalized_year,
        as_of_date=normalized_date,
    )
    published_dates = tuple(
        str(item.get("report_date") or "")
        for item in publication_catalog
        if item.get("report_date")
    )
    latest_available = max(published_dates, default=None)
    requested_date = normalized_date or latest_available
    if requested_date is None:
        return _empty_status(year=normalized_year, latest_available=None)

    dependencies = pnl_by_business_page_dependencies(
        year=normalized_year,
        as_of_date=requested_date,
    )
    publication: Mapping[str, object] | None = next(
        (
            item
            for item in publication_catalog
            if str(item.get("report_date") or "") == requested_date
        ),
        None,
    )
    raw_published_versions = (
        publication.get("dependency_versions") if publication else None
    )
    published_versions: Mapping[str, object] = (
        raw_published_versions if isinstance(raw_published_versions, Mapping) else {}
    )
    governance_records = _governance_run_records(settings)
    run_records = [
        record
        for record in governance_records
        if str(record.get("cache_key") or "") == PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY
        and str(record.get("job_name") or "") == PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME
    ]
    page_record = _latest_page_run_record(governance_records, report_date=requested_date)
    dependency_payloads = [
        _dependency_status(
            dependency=dependency,
            published_generation=str(publication.get("generation") or "") if publication else "",
            published_versions=published_versions,
            published_prepared_at=publication.get("prepared_at") if publication else None,
            run_records=run_records,
        )
        for dependency in dependencies
    ]
    raw_missing_dependency_keys = (
        page_record.get("missing_dependency_keys") if page_record else None
    )
    missing_dependency_keys = {
        str(value)
        for value in (
            raw_missing_dependency_keys
            if isinstance(raw_missing_dependency_keys, list)
            else []
        )
    }
    page_error_message = (
        str(page_record.get("error_message") or "") or None if page_record else None
    )
    for item in dependency_payloads:
        if str(item["key"]) in missing_dependency_keys:
            item["readiness"] = "source_missing"
            item["error_message"] = page_error_message
    handoff = _adjustment_handoff_status(settings, dependency_payloads)
    if handoff.get("pending"):
        for item in dependency_payloads:
            if item["readiness"] == "ready":
                item["readiness"] = "stale"
                item["generation"] = None
                item["error_message"] = str(handoff.get("error_message") or "") or None

    readiness = _page_readiness(dependency_payloads)
    page_record_status, page_worker_stalled = _effective_record_status(page_record)
    page_publication_completed = bool(
        publication
        and page_record
        and str(publication.get("prepared_at") or "")
        >= str(page_record.get("queued_at") or "")
    )
    if (
        readiness != "ready"
        and page_record
        and not page_publication_completed
        and str(page_record.get("failure_category") or "") != "source_missing"
    ):
        if page_record_status in _INFLIGHT and not page_worker_stalled:
            readiness = "pending"
        elif page_record_status == "failed" or page_worker_stalled:
            readiness = "failed"
    generation = (
        str(publication.get("generation") or "") or None
        if readiness == "ready" and publication
        else None
    )
    latest_record = (
        page_record
        if page_record and not page_publication_completed
        else _latest_dependency_record(dependency_payloads)
    )
    last_progress_at = _latest_timestamp(
        [item.get("last_progress_at") for item in dependency_payloads]
        + [
            handoff.get("last_event_at"),
            page_record.get("last_progress_at") if page_record else None,
            page_record.get("queued_at") if page_record else None,
        ]
    )
    worker_stalled = page_worker_stalled or any(
        bool(item.get("worker_stalled")) for item in dependency_payloads
    )
    legacy_status = _legacy_status(readiness, dependency_payloads)
    if page_record and not page_publication_completed:
        legacy_status = page_record_status or legacy_status
    error_message = next(
        (
            str(value)
            for value in [
                page_record.get("error_message") if page_record else None,
                *(item.get("error_message") for item in dependency_payloads),
            ]
            if value
        ),
        None,
    )
    return {
        "year": normalized_year,
        "status": legacy_status,
        "serving_mode": "published" if readiness == "ready" else "unavailable",
        "is_current": readiness == "ready",
        "run_id": latest_record.get("run_id") if latest_record else None,
        "report_date": requested_date,
        "latest_available_as_of_date": latest_available,
        "source_version": publication.get("source_version") if publication else None,
        "rule_version": publication.get("rule_version") if publication else PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        "queued_at": latest_record.get("queued_at") if latest_record else None,
        "started_at": latest_record.get("started_at") if latest_record else None,
        "finished_at": latest_record.get("finished_at") if latest_record else None,
        "generated_at": publication.get("prepared_at") if publication else None,
        "record_count": 1 if generation else None,
        "error_message": error_message,
        "failure_category": latest_record.get("failure_category") if latest_record else None,
        "trigger_reason": latest_record.get("trigger_reason") if latest_record else None,
        "retry_attempt": (
            _strict_int(latest_record.get("retry_attempt"), label="retry_attempt")
            if latest_record
            else 0
        ),
        "retry_policy": _retry_policy(),
        "refresh_status": legacy_status,
        "refresh_error_message": error_message,
        "refresh_failure_category": (
            latest_record.get("failure_category") if latest_record else None
        ),
        "readiness": readiness,
        "generation": generation,
        "dependencies": [
            {key: value for key, value in item.items() if not key.startswith("_") and key != "worker_stalled"}
            for item in dependency_payloads
        ],
        "last_progress_at": last_progress_at,
        "worker_stalled": worker_stalled,
        "recovery_hint": _recovery_hint(readiness=readiness, worker_stalled=worker_stalled),
    }


def _dependency_status(
    *,
    dependency: PnlByBusinessPageDependency,
    published_generation: str,
    published_versions: Mapping[str, object],
    published_prepared_at: object,
    run_records: list[dict[str, object]],
) -> dict[str, object]:
    key = str(dependency["key"])
    dependency_year = dependency["year"]
    requested_date = str(dependency["requested_report_date"])
    record = _latest_run_record(run_records, year=dependency_year, report_date=requested_date)
    record_status, worker_stalled = _effective_record_status(record)
    error_message = str(record.get("error_message") or "") or None if record else None
    prefix = f"pnl_by_business.{key}"
    published_matches = bool(
        published_generation
        and str(published_versions.get(f"{prefix}.requested_report_date") or "") == requested_date
        and str(published_versions.get(f"{prefix}.resolved_report_date") or "") == requested_date
    )
    if published_matches:
        readiness = "ready"
    elif record_status in _INFLIGHT and not worker_stalled:
        readiness = "pending"
    elif record_status == "failed":
        readiness = "failed"
    else:
        readiness = "stale"
    last_progress_at = _latest_timestamp(
        [
            record.get("finished_at") if record else None,
            record.get("started_at") if record else None,
            record.get("queued_at") if record else None,
            published_prepared_at,
        ]
    )
    return {
        "key": key,
        "requested_report_date": requested_date,
        "resolved_report_date": requested_date if published_matches else None,
        "readiness": readiness,
        "generation": published_generation if published_matches else None,
        "run_id": str(record.get("run_id") or "") or None if record else None,
        "last_progress_at": last_progress_at,
        "error_message": error_message,
        "worker_stalled": worker_stalled,
        "_record": record,
    }


def _governance_run_records(settings: Settings) -> list[dict[str, object]]:
    return [
        dict(record)
        for record in GovernanceRepository(base_dir=settings.governance_path).read_by_cache_keys(
            CACHE_BUILD_RUN_STREAM,
            (
                PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
                _PNL_BY_BUSINESS_PAGE_CACHE_KEY,
            ),
        )
    ]


def _latest_page_run_record(
    run_records: list[dict[str, object]], *, report_date: str
) -> dict[str, object] | None:
    latest_by_run: dict[str, dict[str, object]] = {}
    for index, record in enumerate(run_records):
        if (
            str(record.get("job_name") or "") == _PNL_BY_BUSINESS_PAGE_CACHE_KEY
            and str(record.get("report_date") or "") == report_date
            and str(record.get("protocol_version") or "")
            == "pnl_by_business_page_intent/v1"
        ):
            latest_by_run[str(record.get("run_id") or f"missing:{index}")] = record
    return list(latest_by_run.values())[-1] if latest_by_run else None


def _latest_run_record(
    run_records: list[dict[str, object]], *, year: int, report_date: str
) -> dict[str, object] | None:
    records = [
        record
        for record in run_records
        if (
            str(record.get("report_date") or "") == report_date
            or report_date
            in _record_target_dates(record)
        )
        and (
            _strict_int(
                record.get("target_year", year),
                label="target_year",
            )
            == year
            or str(record.get("report_date") or "").startswith(f"{year:04d}-")
        )
    ]
    if not records:
        return None
    latest_by_run: dict[str, dict[str, object]] = {}
    for index, record in enumerate(records):
        latest_by_run[str(record.get("run_id") or f"missing:{index}")] = dict(record)
    return list(latest_by_run.values())[-1]


def _effective_record_status(record: Mapping[str, object] | None) -> tuple[str, bool]:
    if not record:
        return "idle", False
    status = str(record.get("status") or "")
    if status not in _INFLIGHT:
        return status, False
    timestamp = str(record.get("started_at") or record.get("queued_at") or "")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
    except ValueError:
        return "failed", True
    if datetime.now(UTC) - parsed > _STALE_AFTER:
        return "failed", True
    return status, False


def _latest_dependency_record(dependencies: list[dict[str, object]]) -> dict[str, object] | None:
    records: list[dict[str, object]] = []
    for item in dependencies:
        record = item.get("_record")
        if isinstance(record, dict):
            records.append(record)
    return (
        max(
            records,
            key=lambda record: str(
                record.get("finished_at")
                or record.get("started_at")
                or record.get("queued_at")
                or ""
            ),
        )
        if records
        else None
    )


def _page_readiness(dependencies: list[dict[str, object]]) -> str:
    states = {str(item["readiness"]) for item in dependencies}
    for state in ("source_missing", "failed", "pending", "stale"):
        if state in states:
            return state
    return "ready"


def _legacy_status(readiness: str, dependencies: list[dict[str, object]]) -> str:
    record_statuses: set[str] = set()
    for item in dependencies:
        record = item.get("_record")
        if isinstance(record, dict):
            record_statuses.add(str(record.get("status") or ""))
    if "running" in record_statuses:
        return "running"
    if "queued" in record_statuses or readiness == "pending":
        return "queued"
    if "failed" in record_statuses:
        return "failed"
    if readiness == "failed":
        return "failed"
    if readiness == "ready":
        return "completed"
    return "idle"


def _retry_policy() -> dict[str, int]:
    options = getattr(rebuild_pnl_by_business_precompute, "options", {})
    return {
        "max_retries": int(options.get("max_retries", 3)),
        "min_backoff_seconds": int(options.get("min_backoff", 15_000)) // 1000,
    }


def _latest_timestamp(values: list[object]) -> str | None:
    normalized = [str(value) for value in values if value]
    return max(normalized) if normalized else None


def _adjustment_handoff_status(
    settings: Settings, dependencies: list[dict[str, object]]
) -> Mapping[str, object]:
    return pnl_by_business_adjustment_handoff_status(
        settings.governance_path,
        dependency_dates=tuple(str(item["requested_report_date"]) for item in dependencies),
    )


def _record_target_dates(record: Mapping[str, object]) -> set[str]:
    raw_dates = record.get("target_as_of_dates")
    if not isinstance(raw_dates, (list, tuple)):
        return set()
    return {str(value) for value in raw_dates}


def _strict_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"Invalid {label} in PnL page governance record.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid {label} in PnL page governance record."
            ) from exc
    if value is None:
        return 0
    raise RuntimeError(f"Invalid {label} in PnL page governance record.")


def _recovery_hint(*, readiness: str, worker_stalled: bool) -> str | None:
    if worker_stalled:
        return "后台任务长时间无进展，请检查工作进程与队列后重新准备。"
    if readiness == "source_missing":
        return "所选页面依赖的正式来源日期不完整，请先补齐来源。"
    if readiness == "failed":
        return "页面准备失败，请检查后台回执后重新准备。"
    if readiness in {"pending", "stale"}:
        return "页面依赖尚未完成发布，可由有权限人员发起整页准备。"
    return None


def _empty_status(*, year: int, latest_available: str | None) -> dict[str, object]:
    return {
        "year": year,
        "status": "idle",
        "serving_mode": "unavailable",
        "is_current": False,
        "run_id": None,
        "report_date": None,
        "latest_available_as_of_date": latest_available,
        "source_version": None,
        "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        "queued_at": None,
        "started_at": None,
        "finished_at": None,
        "generated_at": None,
        "record_count": None,
        "error_message": None,
        "failure_category": None,
        "trigger_reason": None,
        "retry_attempt": 0,
        "retry_policy": _retry_policy(),
        "refresh_status": "idle",
        "refresh_error_message": None,
        "refresh_failure_category": None,
        "readiness": "source_missing",
        "generation": None,
        "dependencies": [],
        "last_progress_at": None,
        "worker_stalled": False,
        "recovery_hint": "当前年份没有可用的正式损益来源日期。",
    }
