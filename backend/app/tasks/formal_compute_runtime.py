from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.governance.locks import acquire_lock
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.build_runs import BuildRunRecord


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
    governance_path = Path(governance_dir)
    governance_repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(
        job_name=job_name,
        status="running",
        cache_key=descriptor.cache_key,
    )
    active_run_id = run_id or f"{job_name}:{run.created_at}"
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
            "started_at": run.created_at,
        },
    )

    try:
        with acquire_lock(descriptor.lock_definition, base_dir=Path(lock_base_dir)):
            result = FormalComputeMaterializeResult.model_validate(
                execute_materialization()
            )
    except FormalComputeMaterializeFailure as exc:
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
                "error_message": str(exc),
            },
        )
        raise
    except Exception as exc:
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
                "error_message": str(exc),
            },
        )
        raise

    governance_repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                CacheManifestRecord(
                    cache_key=descriptor.cache_key,
                    cache_version=descriptor.cache_version,
                    source_version=result.source_version,
                    vendor_version=result.vendor_version,
                    rule_version=descriptor.rule_version,
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
                },
            ),
        ]
    )

    return {
        "status": "completed",
        "cache_key": descriptor.cache_key,
        "cache_version": descriptor.cache_version,
        "run_id": active_run_id,
        "report_date": report_date,
        "source_version": result.source_version,
        "rule_version": descriptor.rule_version,
        "vendor_version": result.vendor_version,
        "lock": descriptor.lock_key,
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
        cache_version=descriptor.cache_version,
        lock=descriptor.lock_key,
        source_version=source_version,
        vendor_version=vendor_version or descriptor.vendor_version,
        rule_version=descriptor.rule_version if include_rule_version else None,
    ).model_dump()
