from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

import duckdb
from backend.app.config.product_category_mapping import resolve_product_category_ftp_rate_pct
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    canonical_json_bytes,
    generation_database_path,
    read_publication_pointer,
    resolve_financial_generation,
    sha256_bytes,
)
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_SCOPE,
    required_pnl_by_business_revision_on_connection,
)
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION, PnlRepository
from backend.app.services.pnl_by_business_adjustments import (
    active_pnl_by_business_manual_adjustments_for_period,
    pnl_by_business_manual_adjustment_source_version,
)
from backend.app.services.pnl_by_business_candidate_insights import (
    FORMAL_RULE_VERSION,
    pnl_by_business_insights_envelope,
)
from backend.app.services.pnl_by_business_publication_service import (
    PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE,
    PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
    require_current_pnl_by_business_governance,
)
from backend.app.services.pnl_service_by_business_support import (
    PnlByBusinessPageDependency,
    pnl_by_business_page_dependencies,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationConflict,
    FinancialPublicationPlan,
    FinancialTablePublicationSpec,
    publish_financial_result,
)
from backend.app.tasks.pnl_by_business_resource_scope import (
    PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
    PnlByBusinessResourceBudgetExceeded,
    PnlByBusinessTaskResourceScope,
    pnl_by_business_dependency_resource_failure,
    pnl_by_business_resource_failure_for_run,
)

PNL_BY_BUSINESS_PAGE_JOB_NAME = "pnl_by_business_page_prepare"
PNL_BY_BUSINESS_PAGE_CACHE_VERSION = "cv_pnl_by_business_page_envelope_v1"
PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION = "pnl_by_business_page_intent/v1"
PNL_BY_BUSINESS_FINANCIAL_PUBLICATION_REQUIRED_STEPS = (
    "formal_balance",
    "bond_analytics",
    "risk_tensor",
    "formal_pnl",
    "product_category_pnl",
    "accounting_asset_movement",
    "source_preview",
    "verify",
    PNL_BY_BUSINESS_PAGE_JOB_NAME,
)
PNL_BY_BUSINESS_PAGE_ONLY_PUBLICATION_REQUIRED_STEPS = (PNL_BY_BUSINESS_PAGE_JOB_NAME,)


class PnlByBusinessPageDependenciesNotReady(RuntimeError):
    pass


class _DependencySnapshot(TypedDict):
    key: str
    year: int
    requested_report_date: str
    resolved_report_date: str
    dependency_revision: int
    source_version: str
    rule_version: str
    ftp_rate_pct: str
    adjustment_version: str
    protocol_version: str


def prepare_pnl_by_business_page_envelope(
    settings: Settings | None = None,
    *,
    report_date: str | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    year: int | None = None,
    as_of_date: str | None = None,
    run_id: str | None = None,
    writer_lock_already_held: bool = False,
    resource_scope: PnlByBusinessTaskResourceScope | None = None,
) -> dict[str, object]:
    """Build and atomically store one complete approved insights envelope."""
    if settings is not None:
        duckdb_path = str(settings.duckdb_path)
        governance_dir = str(settings.governance_path)
        base_ftp_rate_pct = settings.ftp_rate_pct
    else:
        base_ftp_rate_pct = get_settings().ftp_rate_pct
    resolved_date = str(report_date or as_of_date or "")
    if report_date is not None and as_of_date is not None and report_date != as_of_date:
        raise ValueError("report_date and as_of_date must identify the same cutoff.")
    parsed = date.fromisoformat(resolved_date)
    if year is not None and int(year) != parsed.year:
        raise ValueError(f"as_of_date={resolved_date} is outside requested year={int(year)}.")
    year = parsed.year
    as_of_date = parsed.isoformat()
    if not duckdb_path or not governance_dir:
        raise ValueError("duckdb_path and governance_dir are required.")
    dependencies = pnl_by_business_page_dependencies(year=year, as_of_date=as_of_date)
    writer_lock = resolve_duckdb_writer_lock(duckdb_path, ttl_seconds=3600)
    lock_context = (
        nullcontext()
        if writer_lock_already_held
        else acquire_lock(writer_lock, base_dir=Path(duckdb_path).parent)
    )
    with lock_context:
        before = _dependency_snapshot(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            dependencies=dependencies,
            base_ftp_rate_pct=base_ftp_rate_pct,
        )
        envelope = pnl_by_business_insights_envelope(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=year,
            as_of_date=as_of_date,
        )
        after = _dependency_snapshot(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            dependencies=dependencies,
            base_ftp_rate_pct=base_ftp_rate_pct,
        )
        if before != after:
            raise PnlByBusinessPageDependenciesNotReady(
                "Pnl-by-business page dependencies changed while the envelope was prepared."
            )
        result_meta = _validate_prepared_envelope(
            envelope,
            year=year,
            as_of_date=as_of_date,
        )
        prepared_at = datetime.now(UTC).isoformat()
        dependency_versions = _flatten_dependency_versions(after)
        payload_bytes = canonical_json_bytes(envelope)
        payload_sha256 = sha256_bytes(payload_bytes)
        source_version = str(result_meta.get("source_version") or "")
        adjustment_version = _composite_adjustment_version(after)
        if resource_scope is not None:
            resource_scope.assert_within_budget("before_page_envelope_persist")
            resource_scope.bind_database(
                duckdb_path,
                read_only=False,
                label="page_envelope_write",
            )
        _replace_page_envelope(
            duckdb_path=duckdb_path,
            report_date=as_of_date,
            payload_json=payload_bytes.decode("utf-8"),
            payload_sha256=payload_sha256,
            dependency_revision=max(int(item["dependency_revision"]) for item in after),
            dependency_versions=dependency_versions,
            source_version=source_version,
            adjustment_version=adjustment_version,
            prepared_at=prepared_at,
        )
        if resource_scope is not None:
            resource_scope.assert_within_budget("after_page_envelope_persist")
            resource_scope.bind_database(
                duckdb_path,
                read_only=True,
                label="page_plan_read",
            )
    return {
        "status": "completed",
        "run_id": run_id,
        "year": int(year),
        "report_date": as_of_date,
        "records": 1,
        "source_version": source_version,
        "rule_version": FORMAL_RULE_VERSION,
        "adjustment_version": adjustment_version,
        "dependency_versions": dependency_versions,
        "prepared_at": prepared_at,
    }


def build_pnl_by_business_financial_publication_plan(
    settings: Settings,
    *,
    report_date: str,
    run_id: str,
    expected_previous_generation: str | None,
    step_receipts: tuple[Mapping[str, object], ...],
) -> FinancialPublicationPlan:
    """Build a fail-closed publication plan from an already prepared page row."""
    receipt_names = tuple(str(item.get("name") or "") for item in step_receipts)
    if receipt_names != PNL_BY_BUSINESS_FINANCIAL_PUBLICATION_REQUIRED_STEPS:
        raise RuntimeError(
            "Financial publication requires the complete ordered global refresh receipts."
        )
    return _build_pnl_by_business_page_publication_plan(
        settings,
        report_date=report_date,
        run_id=run_id,
        expected_previous_generation=expected_previous_generation,
        required_steps=PNL_BY_BUSINESS_FINANCIAL_PUBLICATION_REQUIRED_STEPS,
        step_receipts=step_receipts,
    )


def build_pnl_by_business_page_only_financial_publication_plan(
    settings: Settings,
    *,
    report_date: str,
    run_id: str,
    expected_previous_generation: str | None,
    prepare_receipt: Mapping[str, object],
) -> FinancialPublicationPlan:
    """Build a page-only plan bound to one real prepare receipt and its source lineage."""
    normalized_date = date.fromisoformat(report_date).isoformat()
    if (
        str(prepare_receipt.get("status") or "").lower() != "completed"
        or str(prepare_receipt.get("report_date") or "") != normalized_date
        or str(prepare_receipt.get("run_id") or "") != run_id
    ):
        raise RuntimeError("Page-only financial publication requires its completed prepare receipt.")
    receipt_dependencies = prepare_receipt.get("dependency_versions")
    if not isinstance(receipt_dependencies, Mapping) or not receipt_dependencies:
        raise RuntimeError("Page-only prepare receipt has no dependency lineage.")
    step_receipts: tuple[Mapping[str, object], ...] = (
        {
            "name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
            "status": "completed",
            "result": prepare_receipt,
        },
    )
    plan = _build_pnl_by_business_page_publication_plan(
        settings,
        report_date=normalized_date,
        run_id=run_id,
        expected_previous_generation=expected_previous_generation,
        required_steps=PNL_BY_BUSINESS_PAGE_ONLY_PUBLICATION_REQUIRED_STEPS,
        step_receipts=step_receipts,
    )
    prepared_dependencies = {
        str(key): str(value) for key, value in receipt_dependencies.items()
    }
    sealed_dependencies = {
        key: value
        for key, value in plan.dependency_versions.items()
        if key != "pnl_by_business_page.payload_sha256"
    }
    if prepared_dependencies != sealed_dependencies:
        raise RuntimeError("Page-only prepare receipt does not match the prepared page lineage.")
    return plan


def _build_pnl_by_business_page_publication_plan(
    settings: Settings,
    *,
    report_date: str,
    run_id: str,
    expected_previous_generation: str | None,
    required_steps: tuple[str, ...],
    step_receipts: tuple[Mapping[str, object], ...],
) -> FinancialPublicationPlan:
    normalized_date = date.fromisoformat(report_date).isoformat()
    row = _read_page_row(str(settings.duckdb_path), report_date=normalized_date)
    if row is None:
        raise PnlByBusinessPageDependenciesNotReady(
            f"No prepared pnl-by-business page envelope exists for report_date={normalized_date}."
        )
    dependency_versions = _json_object(row[0], label="page dependency versions")
    payload_json = str(row[1] or "")
    payload_sha256 = str(row[2] or "")
    if sha256_bytes(payload_json.encode("utf-8")) != payload_sha256:
        raise RuntimeError("Prepared pnl-by-business page payload digest does not match.")
    prepared_envelope = _json_object(payload_json, label="prepared page envelope")
    if canonical_json_bytes(prepared_envelope).decode("utf-8") != payload_json:
        raise RuntimeError("Prepared pnl-by-business page payload is not canonical JSON.")
    _validate_prepared_envelope(
        prepared_envelope,
        year=date.fromisoformat(normalized_date).year,
        as_of_date=normalized_date,
    )
    dependency_versions["pnl_by_business_page.payload_sha256"] = payload_sha256
    if str(row[6] or "") != PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION:
        raise RuntimeError("Prepared pnl-by-business page protocol is incompatible.")
    require_current_pnl_by_business_governance(settings, dependency_versions)
    generation = _publication_generation(report_date=normalized_date, run_id=run_id)
    return FinancialPublicationPlan(
        generation=generation,
        expected_previous_generation=expected_previous_generation,
        tables=(
            FinancialTablePublicationSpec(
                name=PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE,
                date_column="report_date",
                required_dates=(normalized_date,),
                minimum_rows_per_date=1,
                minimum_total_rows=1,
            ),
        ),
        required_steps=required_steps,
        step_receipts=step_receipts,
        required_dependency_keys=tuple(sorted(dependency_versions)),
        dependency_versions={key: str(value) for key, value in dependency_versions.items()},
        coverage_dates={"pnl_by_business_page": (normalized_date,)},
        supported_api_versions=(FINANCIAL_PUBLICATION_API_VERSION,),
        supported_schema_versions=(FINANCIAL_PUBLICATION_SCHEMA_VERSION,),
        quality={
            "status": "passed",
            "checks": (
                {"name": "pnl_by_business_page_envelope", "status": "passed"},
                {"name": "pnl_by_business_dependency_versions", "status": "passed"},
            ),
        },
        source_dependency_validator=_page_source_dependency_validator(
            normalized_date,
            settings=settings,
        ),
    )


def _dependency_snapshot(
    *,
    duckdb_path: str,
    governance_dir: str,
    dependencies: Sequence[PnlByBusinessPageDependency],
    base_ftp_rate_pct: Decimal,
) -> tuple[_DependencySnapshot, ...]:
    repo = PnlRepository(duckdb_path)
    snapshots: list[_DependencySnapshot] = []
    for dependency in dependencies:
        dependency_year = dependency["year"]
        requested_date = str(dependency["requested_report_date"])
        resolved_date = repo.max_formal_or_nonstd_report_date_in_year(
            year=dependency_year,
            as_of_cap=requested_date,
        )
        if resolved_date != requested_date:
            raise PnlByBusinessPageDependenciesNotReady(
                f"Pnl-by-business source cutoff is missing: {dependency['key']}={requested_date}."
            )
        ftp_rate_pct = resolve_product_category_ftp_rate_pct(
            date(dependency_year, 12, 31),
            base_ftp_rate_pct,
        )
        adjustments = active_pnl_by_business_manual_adjustments_for_period(
            governance_dir,
            year=dependency_year,
            period_end=requested_date,
        )
        adjustment_version = pnl_by_business_manual_adjustment_source_version(adjustments)
        state = repo.fetch_pnl_by_business_precompute_state(
            year=dependency_year,
            as_of_date=requested_date,
            effective_ftp_rate_pct=ftp_rate_pct,
            expected_rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
            supplemental_source_version=adjustment_version,
        )
        if not state or not state.get("is_ready"):
            raise PnlByBusinessPageDependenciesNotReady(
                f"Pnl-by-business read model is not ready: {dependency['key']}={requested_date}."
            )
        result_kind = "ytd" if str(dependency["key"]).endswith("ytd") else "monthly"
        if repo.fetch_trusted_pnl_by_business_precompute(
            year=dependency_year,
            as_of_date=requested_date,
            result_kind=result_kind,
            dimension="",
            business_key="",
            effective_ftp_rate_pct=ftp_rate_pct,
            expected_rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
            supplemental_source_version=adjustment_version,
        ) is None:
            raise PnlByBusinessPageDependenciesNotReady(
                f"Pnl-by-business {result_kind} payload is missing: "
                f"{dependency['key']}={requested_date}."
            )
        snapshots.append(
            {
                "key": str(dependency["key"]),
                "year": dependency_year,
                "requested_report_date": requested_date,
                "resolved_report_date": requested_date,
                "dependency_revision": int(state["dependency_revision"]),
                "source_version": str(state["source_version"]),
                "rule_version": str(state["rule_version"]),
                "ftp_rate_pct": str(ftp_rate_pct),
                "adjustment_version": adjustment_version,
                "protocol_version": str(state["protocol_version"]),
            }
        )
    return tuple(snapshots)


def _flatten_dependency_versions(
    dependencies: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    versions = {
        "pnl_by_business_page.protocol": PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
        "pnl_by_business_page.rules": FORMAL_RULE_VERSION,
    }
    for item in dependencies:
        prefix = f"pnl_by_business.{item['key']}"
        for field in (
            "requested_report_date",
            "resolved_report_date",
            "dependency_revision",
            "source_version",
            "rule_version",
            "ftp_rate_pct",
            "adjustment_version",
            "protocol_version",
        ):
            versions[f"{prefix}.{field}"] = str(item[field])
    return versions


def _replace_page_envelope(
    *,
    duckdb_path: str,
    report_date: str,
    payload_json: str,
    payload_sha256: str,
    dependency_revision: int,
    dependency_versions: Mapping[str, str],
    source_version: str,
    adjustment_version: str,
    prepared_at: str,
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute("begin transaction")
        conn.execute(
            f"""
            create table if not exists {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE} (
                report_date date primary key,
                payload_json varchar not null,
                payload_sha256 varchar not null,
                dependency_revision bigint not null,
                dependency_versions_json varchar not null,
                source_version varchar not null,
                rule_version varchar not null,
                adjustment_version varchar not null,
                protocol_version varchar not null,
                prepared_at timestamptz not null
            )
            """
        )
        conn.execute(
            f"delete from {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE} where report_date = ?",
            [report_date],
        )
        conn.execute(
            f"""
            insert into {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report_date,
                payload_json,
                payload_sha256,
                dependency_revision,
                canonical_json_bytes(dependency_versions).decode("utf-8"),
                source_version,
                FORMAL_RULE_VERSION,
                adjustment_version,
                PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
                prepared_at,
            ],
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()


def _read_page_row(duckdb_path: str, *, report_date: str) -> tuple[object, ...] | None:
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        exists = conn.execute(
            "select count(*) from information_schema.tables where table_name = ?",
            [PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE],
        ).fetchone()
        if not exists or int(exists[0]) == 0:
            return None
        return conn.execute(
            f"""
            select dependency_versions_json, payload_json, payload_sha256, source_version,
                   rule_version, adjustment_version, protocol_version
            from {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}
            where report_date = ?
            """,
            [report_date],
        ).fetchone()
    finally:
        conn.close()


def _page_source_dependency_validator(report_date: str, *, settings: Settings):
    def validate(conn: duckdb.DuckDBPyConnection) -> Mapping[str, str]:
        row = conn.execute(
            f"""
            select dependency_versions_json, payload_sha256, protocol_version
            from {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}
            where report_date = ?
            """,
            [report_date],
        ).fetchone()
        if row is None:
            raise RuntimeError(
                f"Prepared pnl-by-business page envelope disappeared for report_date={report_date}."
            )
        if str(row[2] or "") != PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION:
            raise RuntimeError("Prepared pnl-by-business page protocol changed before publication.")
        versions = {
            key: str(value)
            for key, value in _json_object(row[0], label="page dependency versions").items()
        }
        versions["pnl_by_business_page.payload_sha256"] = str(row[1] or "")
        for prefix in sorted(
            key.rsplit(".", 1)[0]
            for key in versions
            if key.startswith("pnl_by_business.") and key.endswith(".requested_report_date")
        ):
            requested_date = str(versions[f"{prefix}.requested_report_date"])
            dependency_year = date.fromisoformat(requested_date).year
            state = conn.execute(
                """
                select required_event_revision, prepared_event_revision, status,
                       source_version, rule_version, effective_ftp_rate_pct,
                       supplemental_source_version, protocol_version
                from fact_pnl_by_business_precompute_cutoff_state
                where scope_key = ? and year = ? and as_of_date = ?
                """,
                [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, dependency_year, requested_date],
            ).fetchone()
            if state is None:
                raise RuntimeError(f"Pnl-by-business dependency state disappeared for {prefix}.")
            expected_revision = int(versions[f"{prefix}.dependency_revision"])
            if (
                int(state[0] or 0) != expected_revision
                or state[1] is None
                or int(state[1]) != expected_revision
                or str(state[2] or "") != "ready"
                or str(state[3] or "") != str(versions[f"{prefix}.source_version"])
                or str(state[4] or "") != str(versions[f"{prefix}.rule_version"])
                or Decimal(str(state[5] or "NaN")) != Decimal(versions[f"{prefix}.ftp_rate_pct"])
                or str(state[6] or "") != str(versions[f"{prefix}.adjustment_version"])
                or str(state[7] or "") != str(versions[f"{prefix}.protocol_version"])
            ):
                raise RuntimeError(f"Pnl-by-business dependency state is stale for {prefix}.")
        require_current_pnl_by_business_governance(settings, versions)
        return versions

    return validate


def _validate_prepared_envelope(
    envelope: Mapping[str, object], *, year: int, as_of_date: str
) -> Mapping[str, object]:
    result = envelope.get("result")
    meta = envelope.get("result_meta")
    if not isinstance(result, Mapping) or not isinstance(meta, Mapping):
        raise RuntimeError("Prepared pnl-by-business envelope shape is invalid.")
    if (
        int(result.get("year") or 0) != int(year)
        or str(result.get("as_of_date") or "") != as_of_date
        or str(meta.get("resolved_report_date") or "") != as_of_date
        or str(meta.get("result_kind") or "") != "pnl.by_business_insights"
        or meta.get("formal_use_allowed") is not True
    ):
        raise RuntimeError("Prepared pnl-by-business envelope identity is invalid.")
    return meta


def _composite_adjustment_version(dependencies: Sequence[Mapping[str, object]]) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                str(item["key"]): str(item["adjustment_version"])
                for item in dependencies
            }
        )
    )


def _publication_generation(*, report_date: str, run_id: str) -> str:
    digest = sha256_bytes(run_id.encode("utf-8"))[:16]
    return f"financial-{report_date.replace('-', '')}-{digest}"


def _json_object(value: object, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} is invalid JSON.") from exc
    if not isinstance(payload, dict) or not payload or any(not str(item) for item in payload.values()):
        raise RuntimeError(f"{label} is incomplete.")
    return payload


def _blocking_page_dependency_resource_failure(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, object] | None:
    repo = PnlRepository(duckdb_path)
    for dependency in pnl_by_business_page_dependencies(
        year=year,
        as_of_date=as_of_date,
    ):
        dependency_year = int(dependency["year"])
        dependency_date = str(dependency["requested_report_date"])
        if connection is None:
            dependency_revision = repo.pnl_by_business_precompute_dependency_revision(
                year=dependency_year,
                as_of_date=dependency_date,
            )
        else:
            dependency_revision = required_pnl_by_business_revision_on_connection(
                connection,
                year=dependency_year,
                as_of_date=dependency_date,
            )
        failure = pnl_by_business_dependency_resource_failure(
            governance_dir,
            year=dependency_year,
            dependency_revision=dependency_revision,
            as_of_date=dependency_date,
        )
        if failure is not None:
            return failure
    return None


def _persist_page_dependency_resource_failure(
    *,
    governance_dir: str,
    run_id: str,
    year: int,
    report_date: str,
    dependency_failure: Mapping[str, object],
) -> dict[str, object]:
    failed_record: dict[str, object] = {
        "run_id": run_id,
        "job_name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_key": PNL_BY_BUSINESS_PAGE_JOB_NAME,
        "cache_version": PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
        "protocol_version": PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        "status": "failed",
        "failure_category": "resource_over_budget",
        "target_year": int(year),
        "report_date": report_date,
        "error_message": "A required pnl-by-business dependency exceeded its resource budget.",
        "finished_at": datetime.now(UTC).isoformat(),
        "dependency_run_id": str(dependency_failure.get("run_id") or ""),
        "resource_limits": dependency_failure.get("resource_limits") or {},
    }
    GovernanceRepository(base_dir=Path(governance_dir)).append(
        CACHE_BUILD_RUN_STREAM,
        failed_record,
    )
    return failed_record


def _prepare_pnl_by_business_page_envelope_actor(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
    expected_previous_generation: str | None,
    run_id: str | None = None,
) -> dict[str, object]:
    normalized_date = date.fromisoformat(as_of_date).isoformat()
    active_run_id = run_id or f"{PNL_BY_BUSINESS_PAGE_JOB_NAME}:{uuid4()}"
    durable_failure = pnl_by_business_resource_failure_for_run(
        governance_dir,
        run_id=active_run_id,
        job_name=PNL_BY_BUSINESS_PAGE_JOB_NAME,
    )
    if durable_failure is not None:
        return durable_failure

    profile = str(os.getenv(PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV) or "").strip()
    if not profile:
        dependency_failure = _blocking_page_dependency_resource_failure(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=year,
            as_of_date=normalized_date,
        )
        if dependency_failure is not None:
            return _persist_page_dependency_resource_failure(
                governance_dir=governance_dir,
                run_id=active_run_id,
                year=year,
                report_date=normalized_date,
                dependency_failure=dependency_failure,
            )
        return _prepare_pnl_by_business_page_envelope_under_resource_scope(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=year,
            as_of_date=normalized_date,
            expected_previous_generation=expected_previous_generation,
            run_id=active_run_id,
            resource_scope=None,
        )
    if profile != PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE:
        raise RuntimeError(f"Unsupported pnl-by-business resource profile: {profile!r}")

    settings = get_settings()
    if Path(duckdb_path).resolve() != Path(settings.duckdb_path).resolve():
        raise RuntimeError("Page publication actor source path does not match active settings.")
    writer_lock = resolve_duckdb_writer_lock(duckdb_path, ttl_seconds=3600)

    def persist_page_resource_failure(resource_limits: dict[str, object]) -> None:
        failed_record: dict[str, object] = {
            "run_id": active_run_id,
            "job_name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
            "cache_key": PNL_BY_BUSINESS_PAGE_JOB_NAME,
            "cache_version": PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
            "protocol_version": PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
            "status": "failed",
            "failure_category": "resource_over_budget",
            "target_year": int(year),
            "report_date": normalized_date,
            "error_message": "PnL-by-business worker process tree exceeded its memory budget.",
            "finished_at": datetime.now(UTC).isoformat(),
            "resource_limits": resource_limits,
        }
        GovernanceRepository(base_dir=Path(governance_dir)).append(
            CACHE_BUILD_RUN_STREAM,
            failed_record,
        )

    resource_scope = PnlByBusinessTaskResourceScope(
        duckdb_path,
        scope_name="pnl_by_business_page_publication",
        max_database_instances=2,
        on_budget_exceeded=persist_page_resource_failure,
    )
    try:
        with acquire_lock(writer_lock, base_dir=Path(duckdb_path).parent), resource_scope:
            resource_scope.bind_database(
                duckdb_path,
                read_only=True,
                label="page_prepare_read",
            )
            dependency_failure = _blocking_page_dependency_resource_failure(
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                year=year,
                as_of_date=normalized_date,
                connection=resource_scope.database_connection(duckdb_path),
            )
            if dependency_failure is not None:
                return _persist_page_dependency_resource_failure(
                    governance_dir=governance_dir,
                    run_id=active_run_id,
                    year=year,
                    report_date=normalized_date,
                    dependency_failure=dependency_failure,
                )
            resource_scope.assert_within_budget("before_page_prepare")
            result = _prepare_pnl_by_business_page_envelope_under_resource_scope(
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                year=year,
                as_of_date=normalized_date,
                expected_previous_generation=expected_previous_generation,
                run_id=active_run_id,
                resource_scope=resource_scope,
            )
            result["resource_limits"] = resource_scope.receipt(
                stage="page_publication_complete"
            )
            return result
    except PnlByBusinessResourceBudgetExceeded as exc:
        durable_failure = pnl_by_business_resource_failure_for_run(
            governance_dir,
            run_id=active_run_id,
            job_name=PNL_BY_BUSINESS_PAGE_JOB_NAME,
        )
        if durable_failure is not None:
            return durable_failure
        failed_record: dict[str, object] = {
            "run_id": active_run_id,
            "job_name": PNL_BY_BUSINESS_PAGE_JOB_NAME,
            "cache_key": PNL_BY_BUSINESS_PAGE_JOB_NAME,
            "cache_version": PNL_BY_BUSINESS_PAGE_CACHE_VERSION,
            "protocol_version": PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
            "status": "failed",
            "failure_category": "resource_over_budget",
            "target_year": int(year),
            "report_date": normalized_date,
            "error_message": str(exc),
            "finished_at": datetime.now(UTC).isoformat(),
            "resource_limits": exc.receipt,
        }
        GovernanceRepository(base_dir=Path(governance_dir)).append(
            CACHE_BUILD_RUN_STREAM,
            failed_record,
        )
        return failed_record


def _prepare_pnl_by_business_page_envelope_under_resource_scope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
    expected_previous_generation: str | None,
    run_id: str | None,
    resource_scope: PnlByBusinessTaskResourceScope | None,
) -> dict[str, object]:
    settings = get_settings()
    normalized_date = date.fromisoformat(as_of_date).isoformat()
    active_run_id = run_id or f"{PNL_BY_BUSINESS_PAGE_JOB_NAME}:{uuid4()}"
    if int(year) != date.fromisoformat(normalized_date).year:
        raise ValueError(f"as_of_date={normalized_date} is outside requested year={int(year)}.")
    if Path(duckdb_path).resolve() != Path(settings.duckdb_path).resolve():
        raise RuntimeError("Page publication actor source path does not match active settings.")
    if Path(governance_dir).resolve() != Path(settings.governance_path).resolve():
        raise RuntimeError("Page publication actor governance path does not match active settings.")
    if not bool(getattr(settings, "financial_publication_enabled", False)):
        raise RuntimeError("Financial publication is disabled.")
    publication_root = str(getattr(settings, "financial_publication_root", "") or "").strip()
    if not publication_root:
        raise RuntimeError("Financial publication root is empty.")

    target_generation = _publication_generation(
        report_date=normalized_date,
        run_id=active_run_id,
    )
    pointer = read_publication_pointer(publication_root, require_valid=False)
    if pointer is not None and str(pointer["generation"]) == target_generation:
        resolved = resolve_financial_generation(
            publication_root,
            generation=target_generation,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
        sealed_payload = resolved.manifest.get("sealed_payload")
        dependency_versions = (
            sealed_payload.get("dependency_versions")
            if isinstance(sealed_payload, Mapping)
            else None
        )
        if not isinstance(dependency_versions, Mapping):
            raise RuntimeError("Committed page publication has no dependency lineage.")
        require_current_pnl_by_business_governance(settings, dependency_versions)
        coverage_dates = (
            sealed_payload.get("coverage_dates") if isinstance(sealed_payload, Mapping) else None
        )
        page_dates = (
            coverage_dates.get("pnl_by_business_page")
            if isinstance(coverage_dates, Mapping)
            else None
        )
        if not isinstance(page_dates, list) or normalized_date not in page_dates:
            raise RuntimeError("Committed page publication does not cover the requested cutoff.")
        return {
            "status": "completed",
            "run_id": active_run_id,
            "year": int(year),
            "report_date": normalized_date,
            "generation": resolved.generation,
            "manifest_sha256": resolved.manifest_sha256,
            "publication_status": "already_published",
            "recovered_after_commit": True,
        }

    current_generation = str(pointer["generation"]) if pointer is not None else None
    if current_generation != expected_previous_generation:
        raise FinancialPublicationConflict(
            "Page publication intent predecessor no longer matches the committed pointer: "
            f"expected={expected_previous_generation!r}, actual={current_generation!r}."
        )
    prepare_receipt = prepare_pnl_by_business_page_envelope(
        settings,
        report_date=normalized_date,
        run_id=active_run_id,
        writer_lock_already_held=resource_scope is not None,
        resource_scope=resource_scope,
    )
    plan = build_pnl_by_business_page_only_financial_publication_plan(
        settings,
        report_date=normalized_date,
        run_id=active_run_id,
        expected_previous_generation=expected_previous_generation,
        prepare_receipt=prepare_receipt,
    )
    final_database_path = generation_database_path(publication_root, target_generation)
    if resource_scope is not None and final_database_path.is_file():
        resource_scope.bind_database(
            final_database_path,
            read_only=True,
            label="page_existing_candidate",
        )

    source_connection: duckdb.DuckDBPyConnection | None = None
    if resource_scope is not None:
        resource_scope.assert_within_budget("before_page_publication")
        resource_scope.bind_database(
            duckdb_path,
            read_only=False,
            label="page_publication_source",
        )
        source_connection = resource_scope.database_connection(duckdb_path)

    def initialize_candidate_connection(
        connection: duckdb.DuckDBPyConnection,
        candidate_path: Path,
        label: str,
    ) -> None:
        assert resource_scope is not None
        resource_scope.configure_connection(
            connection,
            database_path=candidate_path,
            read_only=False,
            label=f"page_{label}",
        )

    def observe_publication_stage(stage: str) -> None:
        assert resource_scope is not None
        if stage == "candidate_sealed":
            resource_scope.bind_database(
                final_database_path,
                read_only=True,
                label="page_sealed_candidate",
            )
        elif stage == "candidate_validated":
            resource_scope.assert_within_budget(stage)
        elif stage == "before_pointer_commit":
            resource_scope.freeze_for_pointer_commit()

    publication = publish_financial_result(
        source_duckdb_path=str(settings.duckdb_path),
        publication_root=publication_root,
        plan=plan,
        writer_lock_already_held=resource_scope is not None,
        source_connection=source_connection,
        candidate_connection_initializer=(
            initialize_candidate_connection if resource_scope is not None else None
        ),
        on_stage=(observe_publication_stage if resource_scope is not None else None),
    )
    return {
        **prepare_receipt,
        "generation": publication.generation,
        "manifest_sha256": publication.manifest_sha256,
        "publication_status": publication.status,
        "recovered_after_commit": publication.recovered_after_commit,
    }


prepare_pnl_by_business_page_envelope_actor = register_actor_once(
    "prepare_pnl_by_business_page_envelope",
    _prepare_pnl_by_business_page_envelope_actor,
    max_retries=8,
    time_limit_ms=3_600_000,
)


def prepare_configured_pnl_by_business_page(
    *, report_date: str, run_id: str | None = None
) -> dict[str, object]:
    settings = get_settings()
    parsed = date.fromisoformat(report_date)
    return prepare_pnl_by_business_page_envelope(
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        year=parsed.year,
        as_of_date=parsed.isoformat(),
        run_id=run_id or f"{PNL_BY_BUSINESS_PAGE_JOB_NAME}:{uuid4()}",
    )
