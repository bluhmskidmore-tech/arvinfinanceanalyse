from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import TypedDict
from uuid import uuid4

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.financial_result_publication_repo import read_publication_pointer
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.services.pnl_by_business_page_readiness import (
    pnl_by_business_published_page_status,
)
from backend.app.services.pnl_service_by_business_support import (
    _normalize_pnl_by_business_precompute_as_of_date,
    _normalize_pnl_by_business_precompute_year,
    pnl_by_business_page_dependencies,
)
from backend.app.tasks.pnl_by_business_page_publication import (
    PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
    PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
    PNL_BY_BUSINESS_PAGE_JOB_NAME,
    _publication_generation,
    prepare_pnl_by_business_page_envelope_actor,
)
from backend.app.tasks.pnl_by_business_resource_scope import (
    pnl_by_business_resource_failure_for_run,
)

PNL_BY_BUSINESS_PAGE_DISPATCH_LOCK = LockDefinition(
    key="lock:pnl:by-business:page-dispatch",
    ttl_seconds=30,
)
PNL_BY_BUSINESS_PAGE_INFLIGHT_STATUSES = frozenset({"queued", "running"})
PNL_BY_BUSINESS_PAGE_STALE_AFTER = timedelta(hours=2)

QueueRefresh = Callable[..., dict[str, object] | None]


class _DependencyBatch(TypedDict):
    year: int
    dependency_revision: int
    target_as_of_dates: list[str]


def request_pnl_by_business_page_rebuild(
    settings: Settings,
    *,
    year: int,
    as_of_date: str,
    queue_refresh: QueueRefresh,
    repository_cls: type[PnlRepository] = PnlRepository,
) -> dict[str, object]:
    """Persist and dispatch every exact cutoff required by one published page."""
    if not bool(getattr(settings, "financial_publication_enabled", False)):
        raise RuntimeError("Financial publication is disabled.")
    publication_root = str(
        getattr(settings, "financial_publication_root", "") or ""
    ).strip()
    if not publication_root:
        raise RuntimeError("Financial publication root is not configured.")
    normalized_year = _normalize_pnl_by_business_precompute_year(year)
    normalized_date = _normalize_pnl_by_business_precompute_as_of_date(
        year=normalized_year,
        as_of_date=as_of_date,
    )
    assert normalized_date is not None
    dependencies = pnl_by_business_page_dependencies(
        year=normalized_year,
        as_of_date=normalized_date,
    )
    page_run_id = f"{PNL_BY_BUSINESS_PAGE_JOB_NAME}:{uuid4()}"
    queued_at = datetime.now(UTC).isoformat()
    repo = repository_cls(str(settings.duckdb_path))
    batches: dict[tuple[int, int], set[str]] = {}
    missing_dependencies: list[dict[str, object]] = []
    for dependency in dependencies:
        dependency_year = dependency["year"]
        requested_date = str(dependency["requested_report_date"])
        resolved_date = repo.max_formal_or_nonstd_report_date_in_year(
            year=dependency_year,
            as_of_cap=requested_date,
        )
        if resolved_date != requested_date:
            missing_dependencies.append(dict(dependency))
            continue
        revision = repo.pnl_by_business_precompute_dependency_revision(
            year=dependency_year,
            as_of_date=requested_date,
        )
        batches.setdefault((dependency_year, revision), set()).add(requested_date)

    pointer = read_publication_pointer(publication_root, require_valid=False)
    expected_previous_generation = (
        str(pointer["generation"]) if pointer is not None else None
    )
    dependency_batches: list[_DependencyBatch] = [
        {
            "year": batch_year,
            "dependency_revision": revision,
            "target_as_of_dates": sorted(target_dates),
        }
        for (batch_year, revision), target_dates in sorted(batches.items())
    ]
    target_dates = sorted(
        {str(item["requested_report_date"]) for item in dependencies}
    )
    intent = {
        "run_id": page_run_id,
        "job_name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_key": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_version": PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
        "status": "queued",
        "target_year": normalized_year,
        "report_date": normalized_date,
        "target_as_of_dates": target_dates,
        "target_count": len(target_dates),
        "dependency_batches": dependency_batches,
        "dependency_requirements": [dict(item) for item in dependencies],
        "trigger_reason": "page_dependency_prepare",
        "scope": "page_dependencies",
        "queued_at": queued_at,
        "expected_previous_generation": expected_previous_generation,
        "protocol_version": PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
    }
    if missing_dependencies:
        missing_message = "PnL by-business page source cutoffs are missing: " + ", ".join(
            f"{item['key']}={item['requested_report_date']}"
            for item in missing_dependencies
        )
        intent.update(
            status="failed",
            error_message=missing_message,
            failure_category="source_missing",
            missing_dependency_keys=[str(item["key"]) for item in missing_dependencies],
        )
    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    with acquire_lock(
        PNL_BY_BUSINESS_PAGE_DISPATCH_LOCK,
        base_dir=settings.governance_path,
        timeout_seconds=2.0,
    ):
        governance_repo.append(CACHE_BUILD_RUN_STREAM, intent)
        if missing_dependencies:
            raise ValueError(missing_message)
        dependency_runs: list[dict[str, object]] = []
        try:
            for batch in dependency_batches:
                queued = queue_refresh(
                    settings,
                    year=batch["year"],
                    as_of_date=None,
                    trigger_reason="page_dependency_prepare",
                    raise_on_dispatch_failure=True,
                    raise_on_duplicate=False,
                    as_of_dates=batch["target_as_of_dates"],
                    scope="page_dependencies",
                    dependency_revision=batch["dependency_revision"],
                )
                if queued is not None:
                    dependency_runs.append(
                        {
                            "run_id": queued.get("run_id"),
                            "year": batch["year"],
                            "dependency_revision": batch["dependency_revision"],
                            "target_as_of_dates": batch["target_as_of_dates"],
                            "reused": bool(queued.get("reused")),
                        }
                    )
            prepare_pnl_by_business_page_envelope_actor.send(
                duckdb_path=str(settings.duckdb_path),
                governance_dir=str(settings.governance_path),
                year=normalized_year,
                as_of_date=normalized_date,
                run_id=page_run_id,
                expected_previous_generation=expected_previous_generation,
            )
        except Exception as exc:
            governance_repo.append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **intent,
                    "status": "failed",
                    "error_message": f"PnL page dispatch failed (error_type={type(exc).__name__}).",
                    "failure_category": "page_dispatch_failure",
                    "last_progress_at": datetime.now(UTC).isoformat(),
                },
            )
            raise

    payload = pnl_by_business_published_page_status(
        settings,
        year=normalized_year,
        as_of_date=normalized_date,
    )
    payload.update(
        {
            "status": "queued",
            "readiness": "pending",
            "generation": None,
            "serving_mode": "unavailable",
            "is_current": False,
            "run_id": page_run_id,
            "page_run_id": page_run_id,
            "dependency_runs": dependency_runs,
            "last_progress_at": queued_at,
        }
    )
    return payload


def recover_pending_pnl_by_business_page_rebuilds(settings: Settings) -> dict[str, object]:
    """Recover durable page intents after cutoff work or a dispatch-process crash."""
    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    latest_by_run: dict[str, dict[str, object]] = {}
    for record in governance_repo.read_all(CACHE_BUILD_RUN_STREAM):
        if (
            str(record.get("job_name") or "") == PNL_BY_BUSINESS_PAGE_JOB_NAME
            and str(record.get("protocol_version") or "")
            == PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION
        ):
            latest_by_run[str(record.get("run_id") or "")] = dict(record)
    pending = [
        record
        for run_id, record in latest_by_run.items()
        if run_id and str(record.get("status") or "") != "completed"
    ]
    items: list[dict[str, object]] = []
    with acquire_lock(
        PNL_BY_BUSINESS_PAGE_DISPATCH_LOCK,
        base_dir=settings.governance_path,
        timeout_seconds=2.0,
    ):
        for record in pending:
            run_id = str(record["run_id"])
            report_date = date.fromisoformat(str(record["report_date"])).isoformat()
            try:
                durable_resource_failure = pnl_by_business_resource_failure_for_run(
                    settings.governance_path,
                    run_id=run_id,
                    job_name=PNL_BY_BUSINESS_PAGE_JOB_NAME,
                )
                if durable_resource_failure is not None:
                    items.append(
                        {
                            "run_id": run_id,
                            "status": "failed",
                            "error_message": str(
                                durable_resource_failure.get("error_message") or ""
                            ),
                            "resource_limits": durable_resource_failure.get(
                                "resource_limits"
                            ),
                        }
                    )
                    continue
                publication = _completed_publication_for_intent(
                    settings,
                    report_date=report_date,
                    run_id=run_id,
                )
                if publication is not None:
                    completed = {
                        **record,
                        "status": "completed",
                        "finished_at": datetime.now(UTC).isoformat(),
                        "generation": publication["generation"],
                        "prepared_at": publication["prepared_at"],
                    }
                    governance_repo.append(CACHE_BUILD_RUN_STREAM, completed)
                    items.append(
                        {"run_id": run_id, "status": "completed", "reused": True}
                    )
                    continue
                if _page_intent_is_active(record):
                    items.append(
                        {"run_id": run_id, "status": "active", "reused": True}
                    )
                    continue
                dependency_runs = _dispatch_persisted_dependency_batches(
                    settings,
                    record=record,
                )
                prepare_pnl_by_business_page_envelope_actor.send(
                    duckdb_path=str(settings.duckdb_path),
                    governance_dir=str(settings.governance_path),
                    year=_strict_int(record.get("target_year"), label="target_year"),
                    as_of_date=report_date,
                    run_id=run_id,
                    expected_previous_generation=(
                        str(record["expected_previous_generation"])
                        if record.get("expected_previous_generation") is not None
                        else None
                    ),
                )
                items.append(
                    {
                        "run_id": run_id,
                        "status": "queued",
                        "reused": True,
                        "dependency_runs": dependency_runs,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - Persist a failed intent for arbitrary dispatch errors, then recover independent intents.
                error_message = f"PnL page recovery failed (error_type={type(exc).__name__})."
                governance_repo.append(
                    CACHE_BUILD_RUN_STREAM,
                    {
                        **record,
                        "status": "failed",
                        "error_message": error_message,
                        "failure_category": "page_recovery_failure",
                        "last_progress_at": datetime.now(UTC).isoformat(),
                    },
                )
                items.append(
                    {"run_id": run_id, "status": "failed", "error_message": error_message}
                )
    failed_count = sum(item["status"] == "failed" for item in items)
    return {
        "status": "partial_failure" if failed_count else "completed",
        "pending_count": len(pending),
        "dispatched_count": sum(item["status"] == "queued" for item in items),
        "active_count": sum(item["status"] == "active" for item in items),
        "completed_count": sum(item["status"] == "completed" for item in items),
        "failed_count": failed_count,
        "items": items,
    }


def _page_intent_is_active(
    record: Mapping[str, object],
    *,
    now: datetime | None = None,
) -> bool:
    if str(record.get("status") or "") not in PNL_BY_BUSINESS_PAGE_INFLIGHT_STATUSES:
        return False
    timestamp = str(
        record.get("last_progress_at")
        or record.get("started_at")
        or record.get("queued_at")
        or ""
    ).strip()
    if not timestamp:
        return False
    try:
        observed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return current - observed_at.astimezone(UTC) <= PNL_BY_BUSINESS_PAGE_STALE_AFTER


def _dispatch_persisted_dependency_batches(
    settings: Settings,
    *,
    record: Mapping[str, object],
) -> list[dict[str, object]]:
    from backend.app.services import pnl_service

    batches = _normalize_dependency_batches(record.get("dependency_batches"))
    covered = {
        (batch["year"], value)
        for batch in batches
        for value in batch["target_as_of_dates"]
    }
    requirements = record.get("dependency_requirements")
    if isinstance(requirements, list):
        repo = PnlRepository(str(settings.duckdb_path))
        resolved_batches: dict[tuple[int, int], set[str]] = {}
        for requirement in requirements:
            if not isinstance(requirement, Mapping):
                raise RuntimeError("Pending page intent has an invalid dependency requirement.")
            dependency_year = _strict_int(requirement.get("year"), label="dependency year")
            requested_date = date.fromisoformat(
                str(requirement["requested_report_date"])
            ).isoformat()
            if (dependency_year, requested_date) in covered:
                continue
            if (
                repo.max_formal_or_nonstd_report_date_in_year(
                    year=dependency_year,
                    as_of_cap=requested_date,
                )
                != requested_date
            ):
                raise RuntimeError(
                    f"PnL by-business page source cutoff is still missing: {requested_date}."
                )
            revision = repo.pnl_by_business_precompute_dependency_revision(
                year=dependency_year,
                as_of_date=requested_date,
            )
            resolved_batches.setdefault((dependency_year, revision), set()).add(
                requested_date
            )
        batches.extend(
            {
                "year": batch_year,
                "dependency_revision": revision,
                "target_as_of_dates": sorted(target_dates),
            }
            for (batch_year, revision), target_dates in sorted(resolved_batches.items())
        )
        if resolved_batches:
            GovernanceRepository(base_dir=settings.governance_path).append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **dict(record),
                    "status": "queued",
                    "dependency_batches": batches,
                    "missing_dependency_keys": [],
                    "error_message": "",
                    "failure_category": "",
                    "last_progress_at": datetime.now(UTC).isoformat(),
                },
            )
    dispatched: list[dict[str, object]] = []
    for raw_batch in batches:
        target_dates = raw_batch["target_as_of_dates"]
        queued = pnl_service._queue_pnl_by_business_precompute_refresh(
            settings,
            year=raw_batch["year"],
            as_of_date=None,
            trigger_reason="page_dependency_recovery",
            raise_on_dispatch_failure=True,
            raise_on_duplicate=False,
            as_of_dates=[date.fromisoformat(str(value)).isoformat() for value in target_dates],
            scope="page_dependencies",
            dependency_revision=raw_batch["dependency_revision"],
        )
        dispatched.append(
            {
                "run_id": queued.get("run_id") if queued else None,
                "year": raw_batch["year"],
                "dependency_revision": raw_batch["dependency_revision"],
                "target_as_of_dates": list(target_dates),
                "reused": bool(queued and queued.get("reused")),
            }
        )
    return dispatched


def _normalize_dependency_batches(value: object) -> list[_DependencyBatch]:
    if not isinstance(value, list):
        raise RuntimeError("Pending page intent has no dependency batches.")
    batches: list[_DependencyBatch] = []
    for raw_batch in value:
        if not isinstance(raw_batch, Mapping):
            raise RuntimeError("Pending page intent has an invalid dependency batch.")
        raw_dates = raw_batch.get("target_as_of_dates")
        if not isinstance(raw_dates, list) or not raw_dates:
            raise RuntimeError("Pending page intent dependency dates are missing.")
        batches.append(
            {
                "year": _strict_int(raw_batch.get("year"), label="dependency year"),
                "dependency_revision": _strict_int(
                    raw_batch.get("dependency_revision"),
                    label="dependency revision",
                ),
                "target_as_of_dates": [
                    date.fromisoformat(str(item)).isoformat() for item in raw_dates
                ],
            }
        )
    return batches


def _strict_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"Pending page intent has an invalid {label}.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise RuntimeError(
                f"Pending page intent has an invalid {label}."
            ) from exc
    raise RuntimeError(f"Pending page intent has an invalid {label}.")


def _completed_publication_for_intent(
    settings: Settings,
    *,
    report_date: str,
    run_id: str,
) -> Mapping[str, object] | None:
    from backend.app.services.pnl_by_business_publication_service import (
        read_published_pnl_by_business_insights,
    )

    expected_generation = _publication_generation(report_date=report_date, run_id=run_id)
    try:
        envelope = read_published_pnl_by_business_insights(
            settings,
            year=date.fromisoformat(report_date).year,
            as_of_date=report_date,
            generation=expected_generation,
        )
    except RuntimeError:
        return None
    result = envelope.get("result")
    result_meta = envelope.get("result_meta")
    if not isinstance(result, Mapping) or not isinstance(result_meta, Mapping):
        return None
    if str(result.get("generation") or "") != expected_generation:
        return None
    prepared_at = str(result_meta.get("generated_at") or "")
    if not prepared_at:
        return None
    return {"generation": expected_generation, "prepared_at": prepared_at}
