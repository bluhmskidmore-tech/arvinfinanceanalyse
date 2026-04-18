from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import require_registered_formal_module
from backend.app.governance.locks import acquire_lock
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
    FormalComputeRuntimeLineagePayload,
    FormalComputeRuntimePayload,
    FormalComputeRuntimeRunPayload,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.build_runs import BuildRunRecord

logger = logging.getLogger(__name__)


def run_formal_materialize(
    *,
    descriptor: FormalComputeModuleDescriptor,
    job_name: str,
    report_date: str,
    governance_dir: str,
    lock_base_dir: str,
    execute_materialization: Callable[[], FormalComputeMaterializeResult | dict[str, object]],
    run_id: str | None = None,
) -> dict[str, object]:
    descriptor = require_registered_formal_module(descriptor)
    queued_at = datetime.now(timezone.utc).isoformat()
    governance_path = Path(governance_dir)
    governance_repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(
        job_name=job_name,
        status="queued",
        cache_key=descriptor.cache_key,
    )
    active_run_id = run_id or f"{job_name}:{run.created_at}"
    logger.info("starting %s", job_name, extra={"run_id": active_run_id, "report_date": report_date})
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **_build_run_record_payload(
                descriptor=descriptor,
                run_id=active_run_id,
                job_name=job_name,
                status="queued",
                source_version=descriptor.running_source_version,
            ),
            "report_date": report_date,
            "queued_at": queued_at,
        },
    )
    started_at = datetime.now(timezone.utc).isoformat()
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **_build_run_record_payload(
                descriptor=descriptor,
                run_id=active_run_id,
                job_name=job_name,
                status="running",
                source_version=descriptor.running_source_version,
            ),
            "report_date": report_date,
            "queued_at": queued_at,
            "started_at": started_at,
        },
    )

    try:
        with acquire_lock(descriptor.lock_definition, base_dir=Path(lock_base_dir)):
            result = FormalComputeMaterializeResult.model_validate(
                execute_materialization()
            )
    except FormalComputeMaterializeFailure as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        failure_reason = _failure_reason(exc)
        logger.error("task failed: %s", exc, exc_info=True)
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **_build_run_record_payload(
                    descriptor=descriptor,
                    run_id=active_run_id,
                    job_name=job_name,
                    status="failed",
                    source_version=exc.source_version,
                    vendor_version=exc.vendor_version,
                    include_rule_version=True,
                ),
                "report_date": report_date,
                "queued_at": queued_at,
                "started_at": started_at,
                "finished_at": finished_at,
                "error_message": str(exc),
                "failure_category": "materialize_failure",
                "failure_reason": failure_reason,
            },
        )
        raise
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        failure_reason = _failure_reason(exc)
        logger.error("task failed: %s", exc, exc_info=True)
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **_build_run_record_payload(
                    descriptor=descriptor,
                    run_id=active_run_id,
                    job_name=job_name,
                    status="failed",
                    source_version=descriptor.running_source_version,
                    include_rule_version=True,
                ),
                "report_date": report_date,
                "queued_at": queued_at,
                "started_at": started_at,
                "finished_at": finished_at,
                "error_message": str(exc),
                "failure_category": "system_exception",
                "failure_reason": failure_reason,
            },
        )
        raise

    finished_at = datetime.now(timezone.utc).isoformat()
    lineage_payload = FormalComputeRuntimeLineagePayload(
        cache_key=descriptor.cache_key,
        cache_version=descriptor.stable_output_version,
        source_version=result.source_version,
        vendor_version=result.vendor_version,
        rule_version=descriptor.rule_version,
        basis=descriptor.basis,
        module_name=descriptor.module_name,
        result_kind_family=descriptor.result_kind_family,
        run_id=active_run_id,
        report_date=report_date,
        input_sources=list(descriptor.input_sources),
        fact_tables=list(descriptor.fact_tables),
    )
    governance_repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                CacheManifestRecord(
                    cache_key=descriptor.cache_key,
                    cache_version=descriptor.stable_output_version,
                    source_version=result.source_version,
                    vendor_version=result.vendor_version,
                    rule_version=descriptor.rule_version,
                    basis=descriptor.basis,
                    module_name=descriptor.module_name,
                    result_kind_family=descriptor.result_kind_family,
                    run_id=active_run_id,
                    report_date=report_date,
                    input_sources=list(descriptor.input_sources),
                    fact_tables=list(descriptor.fact_tables),
                    lineage=_manifest_min_lineage(
                        descriptor=descriptor,
                        run_id=active_run_id,
                        report_date=report_date,
                        source_version=result.source_version,
                        vendor_version=result.vendor_version,
                    ),
                ).model_dump(),
            ),
            (
                CACHE_BUILD_RUN_STREAM,
                {
                    **_build_run_record_payload(
                        descriptor=descriptor,
                        run_id=active_run_id,
                        job_name=job_name,
                        status="completed",
                        source_version=result.source_version,
                        vendor_version=result.vendor_version,
                        include_rule_version=True,
                    ),
                    "report_date": report_date,
                    "queued_at": queued_at,
                    "started_at": started_at,
                    "finished_at": finished_at,
                },
            ),
        ]
    )

    payload = FormalComputeRuntimePayload(
        run=FormalComputeRuntimeRunPayload(
            run_id=active_run_id,
            job_name=job_name,
            report_date=report_date,
            status="completed",
            lock=descriptor.lock_key,
            queued_at=queued_at,
            started_at=started_at,
            finished_at=finished_at,
        ),
        lineage=lineage_payload,
        error=None,
        result=result.payload,
    ).model_dump()
    logger.info("completed %s", job_name, extra={"run_id": active_run_id, "report_date": report_date})
    return {
        "status": "completed",
        "cache_key": descriptor.cache_key,
        "cache_version": descriptor.stable_output_version,
        "run_id": active_run_id,
        "report_date": report_date,
        "source_version": result.source_version,
        "rule_version": descriptor.rule_version,
        "vendor_version": result.vendor_version,
        "lock": descriptor.lock_key,
        "payload": payload,
        **result.payload,
    }


def _build_run_record_payload(
    *,
    descriptor: FormalComputeModuleDescriptor,
    run_id: str,
    job_name: str,
    status: str,
    source_version: str,
    vendor_version: str | None = None,
    include_rule_version: bool = False,
) -> dict[str, object]:
    return CacheBuildRunRecord(
        run_id=run_id,
        job_name=job_name,
        status=status,
        cache_key=descriptor.cache_key,
        cache_version=descriptor.stable_output_version,
        lock=descriptor.lock_key,
        source_version=source_version,
        vendor_version=vendor_version or descriptor.vendor_version,
        rule_version=descriptor.rule_version if include_rule_version else None,
    ).model_dump()


def _manifest_min_lineage(
    *,
    descriptor: FormalComputeModuleDescriptor,
    run_id: str,
    report_date: str,
    source_version: str,
    vendor_version: str,
) -> dict[str, object]:
    return {
        "basis": descriptor.basis,
        "module_name": descriptor.module_name,
        "result_kind_family": descriptor.result_kind_family,
        "run_id": run_id,
        "report_date": report_date,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "rule_version": descriptor.rule_version,
        "input_sources": list(descriptor.input_sources),
        "fact_tables": list(descriptor.fact_tables),
    }


def _failure_reason(exc: Exception) -> str:
    reason = str(exc).strip()
    return reason or exc.__class__.__name__
