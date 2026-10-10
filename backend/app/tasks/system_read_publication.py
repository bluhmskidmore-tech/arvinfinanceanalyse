from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import duckdb
from backend.app.core_finance.accounting_asset_movement import AccountingAssetMovementRow
from backend.app.core_finance.balance_analysis import TywSnapshotRow, ZqtzSnapshotRow
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.data_update_repo import latest_runs
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes,
    read_publication_pointer,
    resolve_financial_generation,
    validate_sealed_financial_generation,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.system_read_publication_repo import (
    active_system_read_scope,
    system_read_publication_root,
)
from backend.app.services.pretrade_qualification import (
    normalize_pretrade_qualification,
    qualify_pretrade_read_view,
    unavailable_pretrade_qualification,
)
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationInvalid,
    FinancialPublicationPlan,
    FinancialPublicationReceipt,
    FinancialTablePublicationSpec,
    publish_financial_result,
)
from backend.app.tasks.pnl_by_business_resource_scope import (
    PnlByBusinessTaskResourceScope,
)

SYSTEM_READ_PUBLICATION_API_VERSION = "system-read-api/v1"
SYSTEM_READ_PUBLICATION_SCHEMA_VERSION = "system-read-schema/v1"
SYSTEM_READ_BUNDLE_PROTOCOL_VERSION = 2
SYSTEM_READ_PUBLICATION_STEP_NAME = "system_read_publish"
SYSTEM_READ_GOVERNANCE_STREAMS = (CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM)
SYSTEM_READ_CORE_REQUIRED_STEPS = (
    "formal_balance",
    "bond_analytics",
    "risk_tensor",
    "formal_pnl",
    "product_category_pnl",
    "accounting_asset_movement",
    "source_preview",
    "verify",
    "pnl_by_business_page_prepare",
    "publish",
)
_TERMINAL_VERSION_FIELDS = (
    "cache_version",
    "source_version",
    "vendor_version",
    "rule_version",
)
_SPECIAL_FACT_TABLES_BY_CACHE_KEY = {
    "product_category_pnl.formal": frozenset(
        {
            "product_category_pnl_canonical_fact",
            "product_category_pnl_formal_read_model",
        }
    ),
    "source_preview.foundation": frozenset({"phase1_source_preview_summary"}),
}
_BOOTSTRAP_RESULT_CACHE_KEYS = (
    "balance_analysis:materialize:formal",
    "bond_analytics:materialize:formal",
    "risk_tensor:materialize:formal",
    "pnl:phase2:materialize:formal",
    "product_category_pnl.formal",
    "accounting_asset_movement.monthly",
    "source_preview.foundation",
)
_REQUIRED_CACHE_KEY_BY_CORE_STEP = dict(
    zip(SYSTEM_READ_CORE_REQUIRED_STEPS[:7], _BOOTSTRAP_RESULT_CACHE_KEYS, strict=True)
)
_PRESERVED_SYSTEM_READ_WORKFLOWS = frozenset({"balance_daily", "market_daily"})
_BALANCE_DAILY_CHANGED_CACHE_KEYS = (
    "balance_analysis:materialize:formal",
    "bond_analytics:materialize:formal",
    "risk_tensor:materialize:formal",
    "source_preview.foundation",
)
_BALANCE_DAILY_CHANGED_TABLES = (
    ("zqtz_bond_daily_snapshot", "report_date", 1),
    ("tyw_interbank_daily_snapshot", "report_date", 1),
    ("fact_formal_zqtz_balance_daily", "report_date", 1),
    ("fact_formal_tyw_balance_daily", "report_date", 1),
    ("fx_daily_mid", "report_date", 1),
    ("fact_formal_bond_analytics_daily", "report_date", 1),
    ("fact_formal_risk_tensor_daily", "report_date", 1),
)


def _strict_pretrade_availability(value: object) -> dict[str, object]:
    normalized = normalize_pretrade_qualification(value)
    if not isinstance(value, Mapping) or canonical_json_bytes(normalized) != canonical_json_bytes(
        dict(value)
    ):
        raise FinancialPublicationInvalid(
            "System read pretrade availability does not match the normalized qualification contract."
        )
    return normalized


def _bundle_pretrade_availability(bundle: Mapping[str, object]) -> dict[str, object]:
    protocol_version = bundle.get("protocol_version")
    if protocol_version == 1:
        return unavailable_pretrade_qualification(
            "legacy_system_read_bundle_has_no_pretrade_qualification"
        )
    if protocol_version != SYSTEM_READ_BUNDLE_PROTOCOL_VERSION:
        raise FinancialPublicationInvalid(
            "Current system generation has an unsupported bundle protocol."
        )
    return _strict_pretrade_availability(bundle.get("pretrade_availability"))


def _current_system_bundle(
    system_root: Path,
) -> tuple[Mapping[str, object] | None, tuple[str, str] | None]:
    pointer = read_publication_pointer(system_root, require_valid=True)
    if pointer is None:
        return None, None
    generation = _required_text(pointer.get("generation"), "current generation")
    manifest_sha256 = _required_text(
        pointer.get("manifest_sha256"), "current manifest_sha256"
    )
    current = resolve_financial_generation(
        system_root,
        generation=generation,
        reader_api_version=SYSTEM_READ_PUBLICATION_API_VERSION,
        reader_schema_version=SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,
    )
    if current.manifest_sha256 != manifest_sha256:
        raise FinancialPublicationInvalid(
            "Current system pointer does not match its sealed manifest."
        )
    sealed_payload = current.manifest.get("sealed_payload")
    bundle = (
        sealed_payload.get("system_read_bundle")
        if isinstance(sealed_payload, Mapping)
        else None
    )
    if not isinstance(bundle, Mapping):
        raise FinancialPublicationInvalid("Current system generation has no sealed bundle.")
    return bundle, (generation, manifest_sha256)


def _sealed_system_table_dependencies(
    system_root: Path,
    *,
    generation: str,
    manifest_sha256: str,
) -> dict[str, str]:
    resolved = resolve_financial_generation(
        system_root,
        generation=generation,
        reader_api_version=SYSTEM_READ_PUBLICATION_API_VERSION,
        reader_schema_version=SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,
    )
    if resolved.manifest_sha256 != manifest_sha256:
        raise FinancialPublicationInvalid(
            "Current system pointer does not match its sealed manifest."
        )
    sealed_payload = resolved.manifest.get("sealed_payload")
    raw_dependencies = (
        sealed_payload.get("dependency_versions")
        if isinstance(sealed_payload, Mapping)
        else None
    )
    if not isinstance(raw_dependencies, Mapping):
        return {}
    return {
        str(key)[len("table.") :]: str(value)
        for key, value in raw_dependencies.items()
        if str(key).startswith("table.")
    }


def _pretrade_dependency_snapshot(
    conn: duckdb.DuckDBPyConnection,
    evidence: Mapping[str, object],
) -> dict[str, str]:
    normalized = _strict_pretrade_availability(evidence)
    status = str(normalized.get("status") or "")
    if status in {"ready", "ready_empty"}:
        qualified = qualify_pretrade_read_view(
            conn,
            evidence=normalized,
            target_date=_required_text(normalized.get("target_date"), "pretrade target_date"),
            stock_candidate_policy=_required_text(
                normalized.get("stock_candidate_policy"),
                "pretrade stock candidate policy",
            ),
        )
        if canonical_json_bytes(qualified) != canonical_json_bytes(normalized):
            raise FinancialPublicationInvalid(
                "Pretrade qualification no longer matches the active source cut."
            )
    return {
        "pretrade_availability_sha256": hashlib.sha256(
            canonical_json_bytes(normalized)
        ).hexdigest()
    }


def publish_system_read_generation(
    settings,
    *,
    report_date: str,
    data_update_run_id: str,
    global_run_id: str,
    step_receipts: tuple[Mapping[str, object], ...],
    pnl_generation: str,
    pnl_manifest_sha256: str,
    required_date_tables: Sequence[tuple[str, str, int]],
    workflow: str = "core_financial",
    require_completed_data_update: bool = False,
) -> FinancialPublicationReceipt:
    """Seal one complete read pack without replaying any financial calculation."""

    normalized_date = date.fromisoformat(report_date).isoformat()
    normalized_data_update_run_id = _required_text(data_update_run_id, "data_update_run_id")
    normalized_global_run_id = _required_text(global_run_id, "global_run_id")
    normalized_workflow = _required_text(workflow, "workflow")
    if normalized_workflow != "core_financial":
        raise FinancialPublicationInvalid(
            "System read publication currently supports only core_financial workflow."
        )
    source_path = Path(settings.duckdb_path).resolve()
    governance_path = Path(settings.governance_path).resolve()
    system_root = system_read_publication_root(settings)
    current_bundle, expected_current_system = _current_system_bundle(system_root)
    pretrade_availability = (
        _bundle_pretrade_availability(current_bundle)
        if current_bundle is not None
        else unavailable_pretrade_qualification(
            "no_prior_system_read_pretrade_qualification"
        )
    )
    financial_root = Path(settings.financial_publication_root).resolve()
    if system_root == financial_root:
        raise FinancialPublicationInvalid(
            "System read publication root must be distinct from the PnL publication root."
        )
    if require_completed_data_update:
        _require_completed_data_update_run(
            settings,
            data_update_run_id=normalized_data_update_run_id,
            global_run_id=normalized_global_run_id,
            report_date=normalized_date,
            workflow=normalized_workflow,
        )
    _validate_core_step_receipts(step_receipts, report_date=normalized_date)
    _validate_pnl_reference(
        financial_root,
        generation=pnl_generation,
        manifest_sha256=pnl_manifest_sha256,
    )
    return _publish_system_read_evidence(
        settings,
        source_path=source_path,
        governance_path=governance_path,
        system_root=system_root,
        report_date=normalized_date,
        data_update_run_id=normalized_data_update_run_id,
        global_run_id=normalized_global_run_id,
        writer_run_id=normalized_data_update_run_id,
        writer_receipt_sha256=hashlib.sha256(
            canonical_json_bytes(step_receipts)
        ).hexdigest(),
        workflow=normalized_workflow,
        step_receipts=step_receipts,
        required_steps=SYSTEM_READ_CORE_REQUIRED_STEPS,
        lineage_references=_collect_lineage_references(step_receipts),
        lineage_reference_dates={},
        pnl_generation=pnl_generation,
        pnl_manifest_sha256=pnl_manifest_sha256,
        pnl_report_date=normalized_date,
        required_date_tables=required_date_tables,
        required_table_coverage=(),
        externally_qualified_tables=frozenset(),
        preserved_table_dependencies={},
        qualification_check="exact_persisted_result_lineage",
        require_current_pnl_pointer=True,
        expected_current_system=expected_current_system,
        require_expected_system_pointer=True,
        pretrade_availability=pretrade_availability,
    )


def publish_qualified_balance_daily_system_read_generation(
    settings,
    *,
    data_update_run_id: str,
    report_date: str,
    writer_receipt: Mapping[str, object],
) -> FinancialPublicationReceipt:
    """Publish one balance-day cut while preserving independently qualified domains."""

    normalized_date = date.fromisoformat(report_date).isoformat()
    references = _collect_lineage_references(
        ({"name": "balance_daily", "status": "completed", "result": writer_receipt},)
    )
    changed_by_cache: dict[str, list[str]] = {
        cache_key: [] for cache_key in _BALANCE_DAILY_CHANGED_CACHE_KEYS
    }
    for run_id, cache_key in references:
        if cache_key in changed_by_cache:
            changed_by_cache[cache_key].append(run_id)
    missing_or_ambiguous = {
        cache_key: run_ids
        for cache_key, run_ids in changed_by_cache.items()
        if len(set(run_ids)) != 1
    }
    if missing_or_ambiguous:
        raise FinancialPublicationInvalid(
            "Balance daily publication requires one exact completed terminal for each "
            "balance, bond analytics, risk tensor, and source preview domain."
        )
    preview_run_id = next(iter(set(changed_by_cache["source_preview.foundation"])))
    preview_report_dates = _terminal_report_dates(
        writer_receipt,
        run_id=preview_run_id,
        cache_key="source_preview.foundation",
    )
    if not preview_report_dates:
        raise FinancialPublicationInvalid(
            "Balance daily source-preview terminal has no real report-date coverage."
        )
    preview_reference_date = max(preview_report_dates)
    return publish_preserved_system_read_generation(
        settings,
        writer_run_id=data_update_run_id,
        workflow="balance_daily",
        report_date=normalized_date,
        writer_receipt=writer_receipt,
        changed_table_coverage=(
            *(
                (table_name, date_column, normalized_date, minimum_rows)
                for table_name, date_column, minimum_rows in _BALANCE_DAILY_CHANGED_TABLES
            ),
            (
                "phase1_source_preview_summary",
                "report_date",
                preview_reference_date,
                1,
            ),
        ),
        changed_terminal_references=tuple(
            (
                next(iter(set(changed_by_cache[cache_key]))),
                cache_key,
                (
                    preview_reference_date
                    if cache_key == "source_preview.foundation"
                    else normalized_date
                ),
            )
            for cache_key in _BALANCE_DAILY_CHANGED_CACHE_KEYS
        ),
        data_update_run_id=data_update_run_id,
    )


def _terminal_report_dates(
    receipt: Mapping[str, object],
    *,
    run_id: str,
    cache_key: str,
) -> tuple[str, ...]:
    matched_dates: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            if (
                str(value.get("run_id") or "") == run_id
                and str(value.get("cache_key") or "") == cache_key
                and str(value.get("status") or "completed").lower() == "completed"
            ):
                raw_dates = value.get("report_dates")
                if isinstance(raw_dates, Sequence) and not isinstance(
                    raw_dates, (str, bytes, bytearray)
                ):
                    for raw_date in raw_dates:
                        matched_dates.add(date.fromisoformat(str(raw_date)).isoformat())
                raw_date = str(value.get("report_date") or "").strip()
                if raw_date:
                    matched_dates.add(date.fromisoformat(raw_date).isoformat())
            for nested in value.values():
                visit(nested)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for nested in value:
                visit(nested)

    visit(receipt)
    return tuple(sorted(matched_dates))


def publish_preserved_system_read_generation(
    settings,
    *,
    writer_run_id: str,
    workflow: str,
    report_date: str,
    writer_receipt: Mapping[str, object],
    changed_table_coverage: Sequence[tuple[str, str, str, int]],
    changed_terminal_references: Sequence[tuple[str, str, str]] = (),
    data_update_run_id: str | None = None,
    changed_source_validator: (
        Callable[[duckdb.DuckDBPyConnection], Mapping[str, str]] | None
    ) = None,
    pretrade_availability: Mapping[str, object] | None = None,
) -> FinancialPublicationReceipt:
    """Publish a full cut from one verified writer while preserving sealed domains."""

    normalized_writer_run_id = _required_text(writer_run_id, "writer_run_id")
    normalized_workflow = _required_text(workflow, "workflow")
    normalized_date = date.fromisoformat(report_date).isoformat()
    if normalized_workflow not in _PRESERVED_SYSTEM_READ_WORKFLOWS:
        raise FinancialPublicationInvalid(
            "Preserved-domain system read publication supports only balance_daily or market_daily."
        )
    normalized_data_update_run_id = (
        _required_text(data_update_run_id, "data_update_run_id")
        if data_update_run_id is not None
        else None
    )
    if normalized_workflow == "balance_daily" and (
        normalized_data_update_run_id != normalized_writer_run_id
    ):
        raise FinancialPublicationInvalid(
            "Balance daily publication requires its real data-update run as writer identity."
        )
    if normalized_workflow == "market_daily" and normalized_data_update_run_id is not None:
        raise FinancialPublicationInvalid(
            "Market daily publication must not claim a data-update parent identity."
        )
    if normalized_workflow == "market_daily" and changed_source_validator is None:
        raise FinancialPublicationInvalid(
            "Market daily publication requires an under-lock changed-source validator."
        )
    if not isinstance(writer_receipt, Mapping):
        raise FinancialPublicationInvalid("Writer receipt must be an immutable mapping payload.")
    expected_receipt_identity = {
        "status": "completed",
        "run_id": normalized_writer_run_id,
        "workflow": normalized_workflow,
        "report_date": normalized_date,
    }
    if any(
        str(writer_receipt.get(field_name) or "") != expected_value
        for field_name, expected_value in expected_receipt_identity.items()
    ):
        raise FinancialPublicationInvalid(
            "Writer receipt does not match its completed publication identity."
        )
    normalized_changed_coverage = _normalize_table_coverage(changed_table_coverage)
    normalized_changed_references = _normalize_terminal_references(
        changed_terminal_references
    )
    if not normalized_changed_coverage:
        raise FinancialPublicationInvalid(
            "Preserved-domain publication requires explicit changed-table coverage."
        )

    system_root = system_read_publication_root(settings)
    current_bundle, expected_current_system = _current_system_bundle(system_root)
    if current_bundle is None or expected_current_system is None:
        raise FinancialPublicationInvalid(
            "Preserved-domain publication requires a current sealed system generation."
        )
    current_generation, current_manifest_sha256 = expected_current_system
    current_table_dependencies = _sealed_system_table_dependencies(
        system_root,
        generation=current_generation,
        manifest_sha256=current_manifest_sha256,
    )
    if normalized_workflow == "market_daily":
        if pretrade_availability is None:
            raise FinancialPublicationInvalid(
                "Market daily publication requires explicit pretrade availability."
            )
        next_pretrade_availability = _strict_pretrade_availability(
            pretrade_availability
        )
    else:
        if pretrade_availability is not None:
            raise FinancialPublicationInvalid(
                "Balance daily publication must preserve sealed pretrade availability."
            )
        next_pretrade_availability = _bundle_pretrade_availability(current_bundle)
    preserved_references = _bundle_terminal_references(current_bundle)
    preserved_coverage = _bundle_required_table_coverage(current_bundle)
    preserved_cache_keys = {cache_key for _run_id, cache_key, _date in preserved_references}
    missing_preserved_domains = sorted(
        set(_BOOTSTRAP_RESULT_CACHE_KEYS) - preserved_cache_keys
    )
    if missing_preserved_domains:
        raise FinancialPublicationInvalid(
            "Current system generation is missing preserved terminal domains: "
            + ", ".join(missing_preserved_domains)
        )
    merged_references = _merge_terminal_references(
        preserved_references,
        normalized_changed_references,
    )
    merged_coverage = _merge_table_coverage(
        preserved_coverage,
        normalized_changed_coverage,
    )
    changed_table_names = {item[0] for item in normalized_changed_coverage}
    preserved_table_dependencies: dict[str, str] = {}
    for table_name, _date_column, _coverage_date, _minimum_rows in preserved_coverage:
        if table_name in changed_table_names:
            continue
        dependency_sha256 = current_table_dependencies.get(table_name)
        if dependency_sha256 is None:
            raise FinancialPublicationInvalid(
                f"Current sealed system generation has no source-cut identity for {table_name!r}."
            )
        preserved_table_dependencies[table_name] = _required_sha256(
            dependency_sha256,
            f"sealed source-cut identity for {table_name}",
        )
    pnl_reference_date = next(
        (
            reference_date
            for _run_id, cache_key, reference_date in merged_references
            if cache_key == "pnl:phase2:materialize:formal"
        ),
        None,
    )
    if pnl_reference_date is None:
        raise FinancialPublicationInvalid(
            "Current system generation has no exact preserved PnL terminal reference."
        )
    pnl_generation = _required_text(
        current_bundle.get("pnl_generation"), "pnl_generation"
    )
    pnl_manifest_sha256 = _required_text(
        current_bundle.get("pnl_manifest_sha256"), "pnl_manifest_sha256"
    )
    writer_receipt_payload = dict(writer_receipt)
    writer_receipt_sha256 = hashlib.sha256(
        canonical_json_bytes(writer_receipt_payload)
    ).hexdigest()
    writer_step = {
        "name": "writer_qualification",
        "status": "completed",
        "result": writer_receipt_payload,
    }
    source_path = Path(settings.duckdb_path).resolve()
    governance_path = Path(settings.governance_path).resolve()
    financial_root = Path(settings.financial_publication_root).resolve()
    if system_root == financial_root:
        raise FinancialPublicationInvalid(
            "System read publication root must be distinct from the PnL publication root."
        )
    _validate_pnl_reference(
        financial_root,
        generation=pnl_generation,
        manifest_sha256=pnl_manifest_sha256,
        require_current_pointer=True,
    )
    return _publish_system_read_evidence(
        settings,
        source_path=source_path,
        governance_path=governance_path,
        system_root=system_root,
        report_date=normalized_date,
        data_update_run_id=normalized_data_update_run_id,
        global_run_id=None,
        writer_run_id=normalized_writer_run_id,
        writer_receipt_sha256=writer_receipt_sha256,
        workflow=normalized_workflow,
        step_receipts=(writer_step,),
        required_steps=("writer_qualification",),
        lineage_references=tuple(
            (run_id, cache_key) for run_id, cache_key, _reference_date in merged_references
        ),
        lineage_reference_dates={
            cache_key: reference_date
            for _run_id, cache_key, reference_date in merged_references
        },
        pnl_generation=pnl_generation,
        pnl_manifest_sha256=pnl_manifest_sha256,
        pnl_report_date=pnl_reference_date,
        required_date_tables=(),
        required_table_coverage=merged_coverage,
        externally_qualified_tables=(
            frozenset(item[0] for item in normalized_changed_coverage)
            if normalized_workflow == "market_daily"
            else frozenset()
        ),
        preserved_table_dependencies=preserved_table_dependencies,
        qualification_check="preserved_domain_writer_qualification",
        require_current_pnl_pointer=True,
        expected_current_system=(current_generation, current_manifest_sha256),
        require_expected_system_pointer=True,
        changed_source_validator=changed_source_validator,
        pretrade_availability=next_pretrade_availability,
    )


def publish_qualified_system_read_bootstrap(
    settings,
    *,
    data_update_run_id: str,
    required_date_tables: Sequence[tuple[str, str, int]],
) -> FinancialPublicationReceipt:
    """Publish a separately qualified existing-state snapshot without financial replay."""

    qualification = qualify_existing_system_read_bootstrap(
        settings,
        data_update_run_id=data_update_run_id,
        required_date_tables=required_date_tables,
    )
    lineage_references = _qualification_lineage_references(qualification)
    qualification_receipt: Mapping[str, object] = {
        "name": "bootstrap_qualification",
        "status": "completed",
        "result": qualification,
    }
    with active_system_read_scope():
        report_date = _required_text(qualification.get("report_date"), "report_date")
        workflow = _required_text(qualification.get("workflow"), "workflow")
        global_run_id = _required_text(
            qualification.get("global_run_id"), "global_run_id"
        )
        pnl_generation = _required_text(
            qualification.get("pnl_generation"), "pnl_generation"
        )
        pnl_manifest_sha256 = _required_text(
            qualification.get("pnl_manifest_sha256"), "pnl_manifest_sha256"
        )
        source_path = Path(settings.duckdb_path).resolve()
        governance_path = Path(settings.governance_path).resolve()
        system_root = system_read_publication_root(settings)
        current_bundle, expected_current_system = _current_system_bundle(system_root)
        pretrade_availability = (
            _bundle_pretrade_availability(current_bundle)
            if current_bundle is not None
            else unavailable_pretrade_qualification(
                "bootstrap_has_no_pretrade_qualification"
            )
        )
        return _publish_system_read_evidence(
            settings,
            source_path=source_path,
            governance_path=governance_path,
            system_root=system_root,
            report_date=report_date,
            data_update_run_id=_required_text(
                qualification.get("data_update_run_id"), "data_update_run_id"
            ),
            global_run_id=global_run_id,
            writer_run_id=_required_text(
                qualification.get("data_update_run_id"), "data_update_run_id"
            ),
            writer_receipt_sha256=hashlib.sha256(
                canonical_json_bytes(qualification_receipt)
            ).hexdigest(),
            workflow=workflow,
            step_receipts=(qualification_receipt,),
            required_steps=("bootstrap_qualification",),
            lineage_references=lineage_references,
            lineage_reference_dates={},
            pnl_generation=pnl_generation,
            pnl_manifest_sha256=pnl_manifest_sha256,
            pnl_report_date=report_date,
            required_date_tables=required_date_tables,
            required_table_coverage=(),
            externally_qualified_tables=frozenset(),
            preserved_table_dependencies={},
            qualification_check="existing_state_bootstrap_qualification",
            require_current_pnl_pointer=False,
            expected_current_system=expected_current_system,
            require_expected_system_pointer=True,
            pretrade_availability=pretrade_availability,
        )


def qualify_existing_system_read_bootstrap(
    settings,
    *,
    data_update_run_id: str,
    required_date_tables: Sequence[tuple[str, str, int]],
) -> dict[str, object]:
    """Read-only preflight for a persisted completed run; never copies or commits."""

    with active_system_read_scope():
        run = _completed_data_update_run(settings, data_update_run_id=data_update_run_id)
        report_date = date.fromisoformat(str(run.get("report_date") or "")).isoformat()
        workflow = _required_text(run.get("workflow"), "workflow")
        if workflow != "core_financial":
            raise FinancialPublicationInvalid(
                "System read bootstrap currently supports only core_financial workflow."
            )
        global_run_id = _required_text(run.get("global_run_id"), "global_run_id")
        persisted_steps = _bootstrap_persisted_steps(run)
        pnl_result = persisted_steps[-1].get("result")
        if not isinstance(pnl_result, Mapping):
            raise FinancialPublicationInvalid(
                "System read bootstrap has no persisted PnL publication result."
            )
        pnl_generation = _required_text(pnl_result.get("generation"), "pnl_generation")
        pnl_manifest_sha256 = _required_text(
            pnl_result.get("manifest_sha256"), "pnl_manifest_sha256"
        )
        financial_root = Path(settings.financial_publication_root).resolve()
        _validate_pnl_reference(
            financial_root,
            generation=pnl_generation,
            manifest_sha256=pnl_manifest_sha256,
            require_current_pointer=False,
        )
        source_path = Path(settings.duckdb_path).resolve()
        governance_path = Path(settings.governance_path).resolve()
        system_root = system_read_publication_root(settings)
        if system_root == financial_root:
            raise FinancialPublicationInvalid(
                "System read publication root must be distinct from the PnL publication root."
            )
        governance_repo = GovernanceRepository(base_dir=governance_path)
        table_specs = _required_table_specs(
            required_date_tables,
            report_date=report_date,
        )
        writer_lock = resolve_duckdb_writer_lock(source_path, ttl_seconds=7200)
        with acquire_lock(writer_lock, base_dir=source_path.parent):
            source_connection = duckdb.connect(str(source_path), read_only=True)
            try:
                source_manifest_rows = _read_source_preview_manifest_rows(
                    settings,
                    governance_path=governance_path,
                )
                lineage_references = _select_bootstrap_lineage_references(
                    governance_repo,
                    report_date=report_date,
                    source_connection=source_connection,
                    table_specs=table_specs,
                    source_manifest_rows=source_manifest_rows,
                    source_preview_archive_root=getattr(
                        settings,
                        "local_archive_path",
                        None,
                    ),
                )
                frozen_governance = _freeze_result_lineage(
                    governance_repo,
                    lineage_references=lineage_references,
                    report_date=report_date,
                )
                source_cut = _source_cut_snapshot(
                    source_connection,
                    table_specs=table_specs,
                    governance_streams=frozen_governance,
                    lineage_references=lineage_references,
                    report_date=report_date,
                    source_manifest_rows=source_manifest_rows,
                )
                source_cut.update(
                    _pnl_source_dependency_snapshot(
                        settings,
                        source_connection,
                        report_date=report_date,
                        generation=pnl_generation,
                        manifest_sha256=pnl_manifest_sha256,
                        require_current_pointer=False,
                    )
                )
            finally:
                source_connection.close()
        return {
            "status": "completed",
            "qualification_mode": "existing_state_v1",
            "original_child_run_ids_recovered": False,
            "persisted_data_update_receipt_sha256": hashlib.sha256(
                canonical_json_bytes(run)
            ).hexdigest(),
            "persisted_step_status_sha256": hashlib.sha256(
                canonical_json_bytes(persisted_steps)
            ).hexdigest(),
            "qualified_terminal_references": [
                {"run_id": run_id, "cache_key": cache_key}
                for run_id, cache_key in lineage_references
            ],
            "source_cut_sha256": hashlib.sha256(
                canonical_json_bytes(source_cut)
            ).hexdigest(),
            "data_update_run_id": _required_text(
                run.get("run_id"), "data_update_run_id"
            ),
            "global_run_id": global_run_id,
            "workflow": workflow,
            "report_date": report_date,
            "pnl_generation": pnl_generation,
            "pnl_manifest_sha256": pnl_manifest_sha256,
        }


def _qualification_lineage_references(
    qualification: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    raw_references = qualification.get("qualified_terminal_references")
    if not isinstance(raw_references, Sequence) or isinstance(
        raw_references, (str, bytes, bytearray)
    ):
        raise FinancialPublicationInvalid(
            "System read bootstrap qualification has no terminal references."
        )
    references = tuple(
        (
            _required_text(item.get("run_id"), "qualified run_id"),
            _required_text(item.get("cache_key"), "qualified cache_key"),
        )
        for item in raw_references
        if isinstance(item, Mapping)
    )
    if len(references) != len(raw_references) or not references:
        raise FinancialPublicationInvalid(
            "System read bootstrap qualification has invalid terminal references."
        )
    return references


def _publish_system_read_evidence(
    settings,
    *,
    source_path: Path,
    governance_path: Path,
    system_root: Path,
    report_date: str,
    data_update_run_id: str | None,
    global_run_id: str | None,
    writer_run_id: str,
    writer_receipt_sha256: str,
    workflow: str,
    step_receipts: tuple[Mapping[str, object], ...],
    required_steps: tuple[str, ...],
    lineage_references: tuple[tuple[str, str], ...],
    lineage_reference_dates: Mapping[str, str],
    pnl_generation: str,
    pnl_manifest_sha256: str,
    pnl_report_date: str,
    required_date_tables: Sequence[tuple[str, str, int]],
    required_table_coverage: Sequence[tuple[str, str, str, int]],
    externally_qualified_tables: frozenset[str],
    preserved_table_dependencies: Mapping[str, str],
    qualification_check: str,
    require_current_pnl_pointer: bool,
    expected_current_system: tuple[str, str] | None,
    require_expected_system_pointer: bool,
    pretrade_availability: Mapping[str, object],
    changed_source_validator: (
        Callable[[duckdb.DuckDBPyConnection], Mapping[str, str]] | None
    ) = None,
) -> FinancialPublicationReceipt:
    pointer = read_publication_pointer(system_root, require_valid=False)
    expected_previous_generation = (
        str(pointer["generation"]) if pointer is not None else None
    )
    writer_lock = resolve_duckdb_writer_lock(source_path, ttl_seconds=7200)
    resource_scope = PnlByBusinessTaskResourceScope(
        source_path,
        scope_name="system_read_publication",
        max_database_instances=2,
    )
    with acquire_lock(writer_lock, base_dir=source_path.parent), resource_scope:
        if require_expected_system_pointer:
            current_pointer = read_publication_pointer(system_root, require_valid=True)
            current_identity = (
                (
                    str(current_pointer.get("generation") or ""),
                    str(current_pointer.get("manifest_sha256") or ""),
                )
                if current_pointer is not None
                else None
            )
            if current_identity != expected_current_system:
                raise FinancialPublicationInvalid(
                    "Current system generation changed before publication."
                )
        resource_scope.bind_database(
            source_path,
            read_only=True,
            label="system_read_source",
        )
        source_connection = resource_scope.database_connection(source_path)
        try:
            governance_repo = GovernanceRepository(base_dir=governance_path)
            frozen_source_manifests = _read_source_preview_manifest_rows(
                settings,
                governance_path=governance_path,
            )
            frozen_governance = _freeze_result_lineage(
                governance_repo,
                lineage_references=lineage_references,
                report_date=report_date,
                lineage_reference_dates=lineage_reference_dates,
            )
            table_specs = _required_table_specs(
                required_date_tables,
                report_date=report_date,
                required_table_coverage=required_table_coverage,
            )
            normalized_pretrade_availability = _strict_pretrade_availability(
                pretrade_availability
            )
            bundle: dict[str, object] = {
                "protocol_version": SYSTEM_READ_BUNDLE_PROTOCOL_VERSION,
                "active_database_identity": str(source_path),
                "full_database": True,
                "governance_base_identity": str(governance_path),
                "governance_streams": frozen_governance,
                "pnl_generation": _required_text(pnl_generation, "pnl_generation"),
                "pnl_manifest_sha256": _required_text(
                    pnl_manifest_sha256, "pnl_manifest_sha256"
                ),
                "data_update_run_id": data_update_run_id,
                "global_run_id": global_run_id,
                "writer_run_id": _required_text(writer_run_id, "writer_run_id"),
                "writer_receipt_sha256": _required_sha256(
                    writer_receipt_sha256,
                    "writer_receipt_sha256",
                ),
                "workflow": workflow,
                "report_date": report_date,
                "terminal_references": [
                    {
                        "run_id": run_id,
                        "cache_key": cache_key,
                        "report_date": lineage_reference_dates.get(cache_key, report_date),
                    }
                    for run_id, cache_key in lineage_references
                ],
                "required_table_coverage": [
                    {
                        "table_name": spec.name,
                        "date_column": spec.date_column,
                        "coverage_date": spec.required_dates[0],
                        "minimum_rows": spec.minimum_rows_per_date,
                    }
                    for spec in table_specs
                ],
                "pretrade_availability": normalized_pretrade_availability,
            }
            writer_dependencies = (
                _writer_dependency_snapshot(
                    changed_source_validator(source_connection)
                )
                if changed_source_validator is not None
                else {}
            )
            dependency_versions = _source_cut_snapshot(
                source_connection,
                table_specs=table_specs,
                governance_streams=frozen_governance,
                lineage_references=lineage_references,
                report_date=report_date,
                lineage_reference_dates=lineage_reference_dates,
                source_manifest_rows=frozen_source_manifests,
                source_preview_archive_root=getattr(
                    settings,
                    "local_archive_path",
                    None,
                ),
                externally_qualified_tables=externally_qualified_tables,
                preserved_table_dependencies=preserved_table_dependencies,
            )
            dependency_versions.update(
                _pnl_source_dependency_snapshot(
                    settings,
                    source_connection,
                    report_date=pnl_report_date,
                    generation=str(bundle["pnl_generation"]),
                    manifest_sha256=str(bundle["pnl_manifest_sha256"]),
                    require_current_pointer=require_current_pnl_pointer,
                )
            )
            dependency_versions.update(writer_dependencies)
            pretrade_dependencies = _pretrade_dependency_snapshot(
                source_connection,
                normalized_pretrade_availability,
            )
            dependency_versions.update(pretrade_dependencies)

            def validate_source_cut(conn: duckdb.DuckDBPyConnection) -> Mapping[str, str]:
                current_governance = _freeze_result_lineage(
                    governance_repo,
                    lineage_references=lineage_references,
                    report_date=report_date,
                    lineage_reference_dates=lineage_reference_dates,
                )
                if canonical_json_bytes(current_governance) != canonical_json_bytes(
                    frozen_governance
                ):
                    raise FinancialPublicationInvalid(
                        "Authoritative result-lineage rows changed during system publication."
                    )
                current_source_manifests = _read_source_preview_manifest_rows(
                    settings,
                    governance_path=governance_path,
                )
                if canonical_json_bytes(current_source_manifests) != canonical_json_bytes(
                    frozen_source_manifests
                ):
                    raise FinancialPublicationInvalid(
                        "Authoritative source-manifest rows changed during system publication."
                    )
                current_snapshot = _source_cut_snapshot(
                    conn,
                    table_specs=table_specs,
                    governance_streams=current_governance,
                    lineage_references=lineage_references,
                    report_date=report_date,
                    lineage_reference_dates=lineage_reference_dates,
                    source_manifest_rows=current_source_manifests,
                    source_preview_archive_root=getattr(
                        settings,
                        "local_archive_path",
                        None,
                    ),
                    externally_qualified_tables=externally_qualified_tables,
                    preserved_table_dependencies=preserved_table_dependencies,
                )
                current_snapshot.update(
                    _pnl_source_dependency_snapshot(
                        settings,
                        conn,
                        report_date=pnl_report_date,
                        generation=str(bundle["pnl_generation"]),
                        manifest_sha256=str(bundle["pnl_manifest_sha256"]),
                        require_current_pointer=require_current_pnl_pointer,
                    )
                )
                if changed_source_validator is not None:
                    current_writer_dependencies = _writer_dependency_snapshot(
                        changed_source_validator(conn)
                    )
                    if current_writer_dependencies != writer_dependencies:
                        raise FinancialPublicationInvalid(
                            "Writer-qualified source cut changed during system publication."
                        )
                    current_snapshot.update(current_writer_dependencies)
                current_pretrade_dependencies = _pretrade_dependency_snapshot(
                    conn,
                    normalized_pretrade_availability,
                )
                if current_pretrade_dependencies != pretrade_dependencies:
                    raise FinancialPublicationInvalid(
                        "Pretrade qualification changed during system publication."
                    )
                current_snapshot.update(current_pretrade_dependencies)
                return current_snapshot

            generation = _system_generation(
                report_date=report_date,
                data_update_run_id=data_update_run_id or writer_run_id,
                global_run_id=global_run_id or writer_receipt_sha256,
                pnl_generation=str(bundle["pnl_generation"]),
                pnl_manifest_sha256=str(bundle["pnl_manifest_sha256"]),
            )
            plan = FinancialPublicationPlan(
                generation=generation,
                expected_previous_generation=expected_previous_generation,
                tables=table_specs,
                required_steps=required_steps,
                step_receipts=step_receipts,
                required_dependency_keys=tuple(sorted(dependency_versions)),
                dependency_versions=dependency_versions,
                coverage_dates={spec.name: spec.required_dates for spec in table_specs},
                supported_api_versions=(SYSTEM_READ_PUBLICATION_API_VERSION,),
                supported_schema_versions=(SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,),
                quality={
                    "status": "passed",
                    "checks": (
                        {"name": qualification_check, "status": "passed"},
                        {"name": "required_domain_date_coverage", "status": "passed"},
                        {"name": "pnl_generation_reference", "status": "passed"},
                    ),
                },
                source_dependency_validator=validate_source_cut,
                estimated_candidate_bytes=source_path.stat().st_size,
                full_database=True,
                system_read_bundle=bundle,
            )
            final_database_path = system_root / "generations" / f"{generation}.duckdb"

            def initialize_candidate_connection(
                connection: duckdb.DuckDBPyConnection,
                candidate_path: Path,
                label: str,
            ) -> None:
                resource_scope.configure_connection(
                    connection,
                    database_path=candidate_path,
                    read_only=False,
                    label=f"system_read_{label}",
                )

            def observe_publication_stage(stage: str) -> None:
                if stage == "candidate_sealed":
                    resource_scope.bind_database(
                        final_database_path,
                        read_only=True,
                        label="system_read_sealed_candidate",
                    )
                elif stage == "candidate_validated":
                    resource_scope.assert_within_budget(stage)
                elif stage == "before_pointer_commit":
                    resource_scope.freeze_for_pointer_commit()

            publication = publish_financial_result(
                source_duckdb_path=source_path,
                publication_root=system_root,
                plan=plan,
                writer_lock_already_held=True,
                source_connection=None,
                candidate_connection_initializer=initialize_candidate_connection,
                on_stage=observe_publication_stage,
            )
            resource_scope.complete("system_read_publication_complete")
            return replace(
                publication,
                resource_limits=resource_scope.receipt(
                    stage="system_read_publication_complete"
                ),
            )
        finally:
            # The resource scope owns and closes the source anchor.
            pass


def _required_table_specs(
    required_date_tables: Sequence[tuple[str, str, int]],
    *,
    report_date: str,
    required_table_coverage: Sequence[tuple[str, str, str, int]] = (),
) -> tuple[FinancialTablePublicationSpec, ...]:
    if required_date_tables and required_table_coverage:
        raise FinancialPublicationInvalid(
            "System read publication table coverage must use one contract shape."
        )
    normalized_coverage = (
        _normalize_table_coverage(required_table_coverage)
        if required_table_coverage
        else tuple(
            (table_name, date_column, report_date, minimum_rows)
            for table_name, date_column, minimum_rows in required_date_tables
        )
    )
    specs = tuple(
        FinancialTablePublicationSpec(
            name=table_name,
            date_column=date_column,
            required_dates=(coverage_date,),
            minimum_rows_per_date=minimum_rows,
            minimum_total_rows=minimum_rows,
        )
        for table_name, date_column, coverage_date, minimum_rows in normalized_coverage
    )
    if not specs:
        raise FinancialPublicationInvalid(
            "System read publication requires explicit domain table coverage."
        )
    return specs


def _normalize_table_coverage(
    coverage: Sequence[tuple[str, str, str, int]],
) -> tuple[tuple[str, str, str, int], ...]:
    normalized: list[tuple[str, str, str, int]] = []
    seen: set[str] = set()
    for table_name, date_column, coverage_date, minimum_rows in coverage:
        normalized_table = _required_text(table_name, "table_name")
        if normalized_table in seen:
            raise FinancialPublicationInvalid(
                f"System read table coverage is duplicated for {normalized_table!r}."
            )
        seen.add(normalized_table)
        if not isinstance(minimum_rows, int) or isinstance(minimum_rows, bool) or minimum_rows < 1:
            raise FinancialPublicationInvalid(
                "System read table coverage minimum_rows must be a positive integer."
            )
        normalized.append(
            (
                normalized_table,
                _required_text(date_column, "date_column"),
                date.fromisoformat(coverage_date).isoformat(),
                minimum_rows,
            )
        )
    return tuple(normalized)


def _normalize_terminal_references(
    references: Sequence[tuple[str, str, str]],
) -> tuple[tuple[str, str, str], ...]:
    normalized: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for run_id, cache_key, reference_date in references:
        normalized_cache_key = _required_text(cache_key, "terminal cache_key")
        if normalized_cache_key in seen:
            raise FinancialPublicationInvalid(
                f"System read terminal reference is duplicated for {normalized_cache_key!r}."
            )
        seen.add(normalized_cache_key)
        normalized.append(
            (
                _required_text(run_id, "terminal run_id"),
                normalized_cache_key,
                date.fromisoformat(reference_date).isoformat(),
            )
        )
    return tuple(normalized)


def _bundle_terminal_references(
    bundle: Mapping[str, object],
) -> tuple[tuple[str, str, str], ...]:
    raw = bundle.get("terminal_references")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise FinancialPublicationInvalid(
            "Current system generation has no explicit terminal references."
        )
    try:
        values = tuple(
            (
                str(item.get("run_id") or ""),
                str(item.get("cache_key") or ""),
                str(item.get("report_date") or ""),
            )
            for item in raw
            if isinstance(item, Mapping)
        )
    except (TypeError, ValueError) as exc:
        raise FinancialPublicationInvalid(
            "Current system terminal references are invalid."
        ) from exc
    if len(values) != len(raw):
        raise FinancialPublicationInvalid(
            "Current system terminal references are invalid."
        )
    return _normalize_terminal_references(values)


def _bundle_required_table_coverage(
    bundle: Mapping[str, object],
) -> tuple[tuple[str, str, str, int], ...]:
    raw = bundle.get("required_table_coverage")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise FinancialPublicationInvalid(
            "Current system generation has no explicit table coverage."
        )
    values: list[tuple[str, str, str, int]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise FinancialPublicationInvalid(
                "Current system table coverage is invalid."
            )
        minimum_rows = item.get("minimum_rows")
        if not isinstance(minimum_rows, int) or isinstance(minimum_rows, bool):
            raise FinancialPublicationInvalid(
                "Current system table coverage is invalid."
            )
        values.append(
            (
                str(item.get("table_name") or ""),
                str(item.get("date_column") or ""),
                str(item.get("coverage_date") or ""),
                minimum_rows,
            )
        )
    return _normalize_table_coverage(tuple(values))


def _merge_terminal_references(
    preserved: Sequence[tuple[str, str, str]],
    changed: Sequence[tuple[str, str, str]],
) -> tuple[tuple[str, str, str], ...]:
    changed_by_cache = {item[1]: item for item in changed}
    merged = [changed_by_cache.pop(item[1], item) for item in preserved]
    merged.extend(changed_by_cache.values())
    return _normalize_terminal_references(tuple(merged))


def _merge_table_coverage(
    preserved: Sequence[tuple[str, str, str, int]],
    changed: Sequence[tuple[str, str, str, int]],
) -> tuple[tuple[str, str, str, int], ...]:
    changed_by_table = {item[0]: item for item in changed}
    merged = [changed_by_table.pop(item[0], item) for item in preserved]
    merged.extend(changed_by_table.values())
    return _normalize_table_coverage(tuple(merged))


def _completed_data_update_run(settings, *, data_update_run_id: str) -> Mapping[str, object]:
    normalized_run_id = _required_text(data_update_run_id, "data_update_run_id")
    matching = next(
        (
            row
            for row in latest_runs(settings.governance_path)
            if str(row.get("run_id") or "") == normalized_run_id
        ),
        None,
    )
    if matching is None or str(matching.get("status") or "") != "completed":
        raise FinancialPublicationInvalid(
            "System read bootstrap requires a persisted completed data-update run."
        )
    return matching


def _bootstrap_persisted_steps(
    run: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    raw_steps = run.get("steps")
    if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, (str, bytes)):
        raise FinancialPublicationInvalid(
            "System read bootstrap requires persisted data-update step receipts."
        )
    steps = tuple(step for step in raw_steps if isinstance(step, Mapping))
    names = tuple(str(step.get("key") or step.get("name") or "") for step in steps)
    if names != SYSTEM_READ_CORE_REQUIRED_STEPS:
        raise FinancialPublicationInvalid(
            "System read bootstrap requires the persisted ordered ten-step core receipt."
        )
    for step in steps:
        if str(step.get("status") or "") != "completed":
            raise FinancialPublicationInvalid(
                "System read bootstrap contains a non-completed persisted step."
            )
        for field_name in ("started_at", "finished_at", "elapsed_seconds"):
            if step.get(field_name) in (None, ""):
                raise FinancialPublicationInvalid(
                    f"System read bootstrap step {step.get('key')!r} lacks {field_name}."
                )
    publish_result = steps[-1].get("result")
    if (
        not isinstance(publish_result, Mapping)
        or str(publish_result.get("status") or "") != "completed"
    ):
        raise FinancialPublicationInvalid(
            "System read bootstrap requires the exact persisted PnL publication result."
        )
    return steps


def _select_bootstrap_lineage_references(
    governance_repo: GovernanceRepository,
    *,
    report_date: str,
    source_connection: duckdb.DuckDBPyConnection | None = None,
    table_specs: tuple[FinancialTablePublicationSpec, ...] = (),
    source_manifest_rows: Sequence[Mapping[str, object]] = (),
    source_preview_archive_root: str | Path | None = None,
) -> tuple[tuple[str, str], ...]:
    runs = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    manifests = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    references: list[tuple[str, str]] = []
    semantic_match_cache: dict[tuple[str, str, str], bool | None] = {}
    for cache_key in _BOOTSTRAP_RESULT_CACHE_KEYS:
        candidates: list[
            tuple[str, str, Mapping[str, object], Mapping[str, object]]
        ] = []
        for run in runs:
            if (
                str(run.get("cache_key") or "") != cache_key
                or str(run.get("status") or "").lower() != "completed"
            ):
                continue
            matching_manifests = [
                manifest
                for manifest in manifests
                if str(manifest.get("cache_key") or "") == cache_key
                and _manifest_matches_run(manifest, run)
                    and (
                        _row_explicitly_covers_report_date(run, report_date)
                        or _contains_report_date(manifest, report_date)
                        or (
                            cache_key == "product_category_pnl.formal"
                            and _has_product_category_stored_state(manifest)
                        )
                    )
            ]
            run_id = str(run.get("run_id") or "").strip()
            if run_id and matching_manifests:
                candidates.append((run_id, cache_key, matching_manifests[-1], run))
        if source_connection is not None and candidates:
            evaluated = [
                (
                    candidate,
                    _manifest_matches_current_facts(
                    source_connection,
                        manifest=candidate[2],
                        table_specs=table_specs,
                        report_date=report_date,
                        semantic_match_cache=semantic_match_cache,
                        terminal_run=candidate[3],
                        source_manifest_rows=source_manifest_rows,
                        source_preview_archive_root=source_preview_archive_root,
                    ),
                )
                for candidate in candidates
            ]
            current_matches = [candidate for candidate, match in evaluated if match is True]
            if current_matches:
                semantic_identities = {
                    _terminal_semantic_identity(candidate[2])
                    for candidate in current_matches
                }
                candidates = (
                    [current_matches[-1]]
                    if len(semantic_identities) == 1
                    else current_matches
                )
            else:
                candidates = []
        unique = tuple(
            dict.fromkeys(
                (run_id, candidate_cache_key)
                for run_id, candidate_cache_key, _manifest, _run in candidates
            )
        )
        if len(unique) != 1:
            raise FinancialPublicationInvalid(
                "System read bootstrap could not uniquely qualify current result lineage for "
                f"cache_key={cache_key!r}; candidates={len(unique)}."
            )
        references.append(unique[0])
    return tuple(references)


def _manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
    semantic_match_cache: dict[tuple[str, str, str], bool | None] | None = None,
    terminal_run: Mapping[str, object] | None = None,
    source_manifest_rows: Sequence[Mapping[str, object]] = (),
    source_preview_archive_root: str | Path | None = None,
) -> bool | None:
    fact_tables = manifest.get("fact_tables")
    declared_facts = (
        {str(value) for value in fact_tables}
        if isinstance(fact_tables, Sequence) and not isinstance(fact_tables, (str, bytes))
        else set()
    )
    declared_facts.update(
        _SPECIAL_FACT_TABLES_BY_CACHE_KEY.get(str(manifest.get("cache_key") or ""), ())
    )
    cache_key = str(manifest.get("cache_key") or "")
    match_cache_key = (
        cache_key,
        _terminal_semantic_identity(manifest),
        str(terminal_run.get("ingest_batch_id") or "")
        if isinstance(terminal_run, Mapping)
        else "",
    )
    if semantic_match_cache is not None and match_cache_key in semantic_match_cache:
        return semantic_match_cache[match_cache_key]
    balance_fact_tables = {
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    }
    if cache_key == "balance_analysis:materialize:formal" and balance_fact_tables.issubset(
        declared_facts
    ):
        result = _balance_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=table_specs,
            report_date=report_date,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if (
        cache_key == "bond_analytics:materialize:formal"
        and "fact_formal_bond_analytics_daily" in declared_facts
    ):
        result = _bond_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=table_specs,
            report_date=report_date,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if (
        cache_key == "risk_tensor:materialize:formal"
        and "fact_formal_risk_tensor_daily" in declared_facts
    ):
        result = _risk_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=table_specs,
            report_date=report_date,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if cache_key == "pnl:phase2:materialize:formal" and {
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
    }.issubset(declared_facts):
        result = _pnl_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=table_specs,
            report_date=report_date,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if cache_key == "product_category_pnl.formal":
        result = _product_category_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=table_specs,
            report_date=report_date,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if (
        cache_key == "accounting_asset_movement.monthly"
        and "fact_accounting_asset_movement_monthly" in declared_facts
    ):
        result = _accounting_asset_movement_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=table_specs,
            report_date=report_date,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if (
        cache_key == "source_preview.foundation"
        and isinstance(terminal_run, Mapping)
    ):
        result = _source_preview_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            terminal_run=terminal_run,
            table_specs=table_specs,
            source_manifest_rows=source_manifest_rows,
            source_preview_archive_root=source_preview_archive_root,
        )
        if semantic_match_cache is not None:
            semantic_match_cache[match_cache_key] = result
        return result
    if cache_key in _BOOTSTRAP_RESULT_CACHE_KEYS:
        return None
    checked = False
    for spec in table_specs:
        if spec.name not in declared_facts:
            continue
        if spec.date_column is None:
            return None
        columns = {
            str(row[1])
            for row in conn.execute(
                f"PRAGMA table_info({_quote_sql_literal(spec.name)})"
            ).fetchall()
        }
        for field_name in _TERMINAL_VERSION_FIELDS:
            expected = str(manifest.get(field_name) or "").strip()
            if not expected or field_name not in columns:
                continue
            checked = True
            observed = {
                str(row[0])
                for row in conn.execute(
                    f"SELECT DISTINCT cast({_quote_identifier(field_name)} as varchar) "
                    f"FROM {_quote_identifier(spec.name)} "
                    f"WHERE cast({_quote_identifier(spec.date_column)} as date) = ? "
                    f"AND {_quote_identifier(field_name)} IS NOT NULL",
                    [report_date],
                ).fetchall()
            }
            if observed != {expected}:
                return False
    return True if checked else None


def _balance_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
) -> bool | None:
    from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
    from backend.app.tasks.balance_analysis_materialize import (
        compose_balance_analysis_source_version,
    )

    specs = {spec.name: spec for spec in table_specs}
    required_tables = (
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fx_daily_mid",
    )
    if any(table_name not in specs for table_name in required_tables):
        return None
    if any(specs[table_name].date_column is None for table_name in required_tables[:2]):
        return None
    expected = str(manifest.get("source_version") or "").strip()
    if not expected:
        return None
    source_path = _source_database_path(conn)
    if source_path is None:
        return None
    repo = BalanceAnalysisRepository(source_path)
    source_versions: set[str] = set()
    snapshot_rows: list[ZqtzSnapshotRow | TywSnapshotRow] = []
    for table_name in required_tables[:2]:
        spec = specs[table_name]
        if spec.date_column is None:
            return None
        source_versions.update(
            str(row[0])
            for row in conn.execute(
                f"SELECT DISTINCT cast(source_version as varchar) "
                f"FROM {_quote_identifier(table_name)} "
                f"WHERE cast({_quote_identifier(spec.date_column)} as date) = ? "
                "AND source_version IS NOT NULL",
                [report_date],
            ).fetchall()
        )
        batch_rows = conn.execute(
            f"SELECT DISTINCT cast(ingest_batch_id as varchar) "
            f"FROM {_quote_identifier(table_name)} "
            f"WHERE cast({_quote_identifier(spec.date_column)} as date) = ? "
            "AND ingest_batch_id IS NOT NULL ORDER BY 1",
            [report_date],
        ).fetchall()
        if len(batch_rows) > 1:
            return False
        ingest_batch_id = str(batch_rows[0][0]) if batch_rows else None
        if table_name == "fact_formal_zqtz_balance_daily":
            snapshot_rows.extend(
                repo.load_zqtz_snapshot_rows(
                    report_date,
                    ingest_batch_id=ingest_batch_id,
                )
            )
        else:
            snapshot_rows.extend(
                repo.load_tyw_snapshot_rows(
                    report_date,
                    ingest_batch_id=ingest_batch_id,
                )
            )
    fx_source_versions: set[str] = set()
    for currency_code in {
        str(row.currency_code) for row in snapshot_rows
    }:
        lookup = repo.lookup_formal_fx_rate(
            report_date=report_date,
            base_currency=currency_code,
        )
        if lookup.source_version and lookup.source_version != "sv_fx_identity":
            fx_source_versions.add(lookup.source_version)
    return (
        compose_balance_analysis_source_version(
            source_versions,
            fx_source_versions,
        )
        == expected
    )


def _bond_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
) -> bool | None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    from backend.app.tasks.bond_analytics_materialize import _combine_source_versions

    required_tables = {
        "zqtz_bond_daily_snapshot",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_bond_analytics_daily",
    }
    if not required_tables.issubset({spec.name for spec in table_specs}):
        return None
    expected = str(manifest.get("source_version") or "").strip()
    if not expected:
        return None
    source_path = _source_database_path(conn)
    if source_path is None:
        return None
    snapshot_rows = BondAnalyticsRepository(source_path).load_snapshot_rows(report_date)
    return _combine_source_versions(snapshot_rows) == expected


def _source_database_path(conn: duckdb.DuckDBPyConnection) -> str | None:
    return next(
        (
            str(row[2])
            for row in conn.execute("PRAGMA database_list").fetchall()
            if len(row) >= 3 and str(row[2]).strip()
        ),
        None,
    )


def _risk_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
) -> bool | None:
    spec = next(
        (
            item
            for item in table_specs
            if item.name == "fact_formal_risk_tensor_daily"
        ),
        None,
    )
    if spec is None or spec.date_column is None:
        return None
    checked = False
    for field_name in ("cache_version", "source_version", "rule_version"):
        expected = str(manifest.get(field_name) or "").strip()
        if not expected:
            return None
        checked = True
        observed = {
            str(row[0])
            for row in conn.execute(
                f"SELECT DISTINCT cast({_quote_identifier(field_name)} as varchar) "
                "FROM fact_formal_risk_tensor_daily "
                f"WHERE cast({_quote_identifier(spec.date_column)} as date) = ? "
                f"AND {_quote_identifier(field_name)} IS NOT NULL",
                [report_date],
            ).fetchall()
        }
        if observed != {expected}:
            return False
    return True if checked else None


def _pnl_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
) -> bool | None:
    from backend.app.tasks.pnl_materialize import compose_formal_pnl_source_version

    spec = next(
        (item for item in table_specs if item.name == "fact_formal_pnl_fi"),
        None,
    )
    if spec is None or spec.date_column is None:
        return None
    date_column = spec.date_column
    existing_tables = {
        str(row[0]) for row in conn.execute("SHOW TABLES").fetchall()
    }
    required_tables = {"fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"}
    if not required_tables.issubset(existing_tables):
        return None
    expected = str(manifest.get("source_version") or "").strip()
    expected_rule = str(manifest.get("rule_version") or "").strip()
    if not expected or not expected_rule:
        return None

    def source_rows(table_name: str) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(source_version=row[0])
            for row in conn.execute(
                f"SELECT source_version FROM {_quote_identifier(table_name)} "
                f"WHERE cast({_quote_identifier(date_column)} as date) = ?",
                [report_date],
            ).fetchall()
        ]

    source_matches = compose_formal_pnl_source_version(
            source_rows("fact_formal_pnl_fi"),
            source_rows("fact_nonstd_pnl_bridge"),
        ) == expected
    if not source_matches:
        return False
    for table_name in required_tables:
        columns = {
            str(row[1])
            for row in conn.execute(
                f"PRAGMA table_info({_quote_sql_literal(table_name)})"
            ).fetchall()
        }
        if "rule_version" not in columns:
            return None
        observed_rules = {
            str(row[0])
            for row in conn.execute(
                f"SELECT DISTINCT cast(rule_version as varchar) "
                f"FROM {_quote_identifier(table_name)} "
                f"WHERE cast({_quote_identifier(date_column)} as date) = ? "
                "AND rule_version IS NOT NULL",
                [report_date],
            ).fetchall()
        }
        if observed_rules and observed_rules != {expected_rule}:
            return False
    return True


def _has_product_category_stored_state(manifest: Mapping[str, object]) -> bool:
    lineage = manifest.get("lineage")
    state = lineage.get("product_category_refresh") if isinstance(lineage, Mapping) else None
    stored = state.get("stored") if isinstance(state, Mapping) else None
    return isinstance(stored, Mapping) and isinstance(stored.get("years"), Mapping)


def _product_category_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
) -> bool | None:
    from backend.app.tasks.product_category_refresh_state import stored_state

    if not _has_product_category_stored_state(manifest):
        return None
    required_tables = {
        "product_category_pnl_canonical_fact",
        "product_category_pnl_formal_read_model",
    }
    specs = {spec.name: spec for spec in table_specs}
    if not required_tables.issubset(specs):
        return None
    for table_name in required_tables:
        spec = specs[table_name]
        if spec.date_column is None:
            return None
        count_row = conn.execute(
            f"SELECT count(*) FROM {_quote_identifier(table_name)} "
            f"WHERE cast({_quote_identifier(spec.date_column)} as date) = ?",
            [report_date],
        ).fetchone()
        if count_row is None:
            return False
        count = int(count_row[0])
        if count < spec.minimum_rows_per_date:
            return False
    lineage = manifest["lineage"]
    assert isinstance(lineage, Mapping)
    state = lineage["product_category_refresh"]
    assert isinstance(state, Mapping)
    expected = state["stored"]
    assert isinstance(expected, Mapping)
    years_payload = expected.get("years")
    assert isinstance(years_payload, Mapping)
    return stored_state(conn, tuple(sorted(str(year) for year in years_payload))) == expected


def _accounting_asset_movement_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    report_date: str,
) -> bool | None:
    from backend.app.tasks.accounting_asset_movement import _rows_source_version

    spec = next(
        (
            item
            for item in table_specs
            if item.name == "fact_accounting_asset_movement_monthly"
        ),
        None,
    )
    expected_source = str(manifest.get("source_version") or "").strip()
    expected_rule = str(manifest.get("rule_version") or "").strip()
    if spec is None or spec.date_column is None or not expected_source or not expected_rule:
        return None
    lineage = manifest.get("lineage")
    currency_basis = (
        str(lineage.get("currency_basis") or "").strip()
        if isinstance(lineage, Mapping)
        else ""
    )
    if not currency_basis:
        return None
    rows = conn.execute(
        "SELECT source_version, rule_version "
        "FROM fact_accounting_asset_movement_monthly "
        f"WHERE cast({_quote_identifier(spec.date_column)} as date) = ? "
        "AND currency_basis = ?",
        [report_date, currency_basis],
    ).fetchall()
    if len(rows) < spec.minimum_rows_per_date:
        return False
    # The shared composer reads only source_version from these lightweight rows.
    if _rows_source_version(
        cast(list[AccountingAssetMovementRow], [SimpleNamespace(source_version=row[0]) for row in rows])
    ) != expected_source:
        return False
    return all(str(row[1] or "").startswith(f"{expected_rule}__") for row in rows)


def _source_preview_manifest_matches_current_facts(
    conn: duckdb.DuckDBPyConnection,
    *,
    manifest: Mapping[str, object],
    terminal_run: Mapping[str, object] | None,
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    source_manifest_rows: Sequence[Mapping[str, object]],
    source_preview_archive_root: str | Path | None = None,
) -> bool | None:
    from backend.app.repositories.source_preview_repo import _select_manifest_rows
    from backend.app.tasks.source_preview_refresh import (
        SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES,
        _join_source_versions,
    )

    if not isinstance(terminal_run, Mapping):
        return None
    ingest_batch_id = str(terminal_run.get("ingest_batch_id") or "").strip()
    expected_source = str(manifest.get("source_version") or "").strip()
    expected_rule = str(manifest.get("rule_version") or "").strip()
    if not expected_source or not expected_rule:
        return None
    spec = next(
        (item for item in table_specs if item.name == "phase1_source_preview_summary"),
        None,
    )
    if spec is None or not source_manifest_rows:
        return None
    try:
        selected = _select_manifest_rows(
            [dict(row) for row in source_manifest_rows],
            ingest_batch_id=ingest_batch_id or None,
            source_families=list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES),
            archive_root=(
                str(Path(source_preview_archive_root).resolve())
                if source_preview_archive_root is not None
                else None
            ),
        )
    except ValueError:
        return False
    if not selected:
        return False
    selected_identity = [
        (
            str(row.get("source_file") or ""),
            str(row.get("source_version") or ""),
        )
        for row in selected
    ]
    current_read_rows = conn.execute(
        "WITH ranked AS ("
        "SELECT source_file, source_version, rule_version, source_family, "
        "row_number() OVER (PARTITION BY source_family "
        "ORDER BY batch_created_at DESC, ingest_batch_id DESC) AS rn "
        "FROM phase1_source_preview_summary "
        "WHERE source_family IN (SELECT unnest(?))) "
        "SELECT source_file, source_version, rule_version, source_family "
        "FROM ranked WHERE rn = 1",
        [list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES)],
    ).fetchall()
    summary_rows = (
        conn.execute(
            "SELECT source_file, source_version, rule_version, source_family "
            "FROM phase1_source_preview_summary WHERE ingest_batch_id = ? "
            "AND source_family IN (SELECT unnest(?))",
            [ingest_batch_id, list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES)],
        ).fetchall()
        if ingest_batch_id
        else current_read_rows
    )
    summary_by_identity = {
        (str(row[0] or ""), str(row[1] or "")): str(row[2] or "")
        for row in summary_rows
    }
    if len(summary_rows) < spec.minimum_rows_per_date or set(selected_identity) != set(
        summary_by_identity
    ):
        return False
    if any(summary_by_identity[identity] != expected_rule for identity in selected_identity):
        return False
    current_read_identity = {
        (str(row[0] or ""), str(row[1] or "")) for row in current_read_rows
    }
    if set(selected_identity) != current_read_identity:
        return False
    return _join_source_versions(version for _source_file, version in selected_identity) == expected_source


def _read_source_preview_manifest_rows(
    settings,
    *,
    governance_path: Path,
) -> list[dict[str, object]]:
    from backend.app.tasks.source_preview_refresh import _governance_repo

    repo = _governance_repo(
        settings=settings,
        governance_path=governance_path,
    )
    return [dict(row) for row in repo.read_all(SOURCE_MANIFEST_STREAM)]


def _terminal_semantic_identity(manifest: Mapping[str, object]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                field_name: manifest.get(field_name)
                for field_name in (
                    "cache_key",
                    "cache_version",
                    "source_version",
                    "vendor_version",
                    "rule_version",
                    "report_date",
                    "fact_tables",
                    "input_sources",
                )
            }
        )
    ).hexdigest()


def _contains_report_date(value: object, report_date: str) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_report_date(item, report_date) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_report_date(item, report_date) for item in value)
    return str(value or "") == report_date


def recover_committed_system_read_publication(
    settings,
    *,
    data_update_run_id: str | None = None,
    writer_run_id: str | None = None,
    report_date: str,
    workflow: str,
) -> dict[str, object] | None:
    """Recover an exact queue run from the validated committed retention window."""

    from backend.app.repositories.financial_result_publication_repo import (
        FinancialPublicationError,
        FinancialPublicationUnavailable,
    )

    if not bool(getattr(settings, "system_read_publication_enabled", False)):
        return None
    root = system_read_publication_root(settings)
    pointer = read_publication_pointer(root, require_valid=False)
    if pointer is None:
        return None
    normalized_data_update_run_id = (
        _required_text(data_update_run_id, "data_update_run_id")
        if data_update_run_id is not None
        else None
    )
    normalized_writer_run_id = (
        _required_text(writer_run_id, "writer_run_id")
        if writer_run_id is not None
        else normalized_data_update_run_id
    )
    if normalized_writer_run_id is None:
        raise FinancialPublicationInvalid(
            "System read recovery requires an exact writer identity."
        )
    normalized_report_date = date.fromisoformat(report_date).isoformat()
    normalized_workflow = _required_text(workflow, "workflow")
    retained = pointer["retained_generations"]
    validity = pointer["validity"]
    assert isinstance(retained, list)
    assert isinstance(validity, Mapping)
    validation_error: FinancialPublicationError | None = None
    for entry in retained:
        assert isinstance(entry, Mapping)
        # The resolver enforces retention, digest, compatibility and revocation;
        # a sealed candidate that was never committed cannot restore a receipt.
        try:
            if entry["generation"] == pointer["generation"] and validity.get("state") != "valid":
                raise FinancialPublicationUnavailable("Current financial publication is not valid.")
            if (
                entry["generation"] == pointer["generation"]
                and entry["manifest_sha256"] != pointer["manifest_sha256"]
            ):
                raise FinancialPublicationInvalid("Current pointer manifest digests disagree.")
            resolved = resolve_financial_generation(
                root,
                generation=str(entry["generation"]),
                reader_api_version=SYSTEM_READ_PUBLICATION_API_VERSION,
                reader_schema_version=SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,
            )
        except FinancialPublicationError as exc:
            # An unrelated failed generation must not hide a still-valid commit.
            validation_error = exc
            continue
        sealed_payload = resolved.manifest.get("sealed_payload")
        if not isinstance(sealed_payload, Mapping):
            continue
        bundle = sealed_payload.get("system_read_bundle")
        if not isinstance(bundle, Mapping):
            continue
        bundle_writer_run_id = str(
            bundle.get("writer_run_id") or bundle.get("data_update_run_id") or ""
        )
        if (
            bundle_writer_run_id != normalized_writer_run_id
            or str(bundle.get("report_date") or "") != normalized_report_date
            or str(bundle.get("workflow") or "") != normalized_workflow
            or (
                normalized_data_update_run_id is not None
                and str(bundle.get("data_update_run_id") or "")
                != normalized_data_update_run_id
            )
        ):
            continue
        result: dict[str, object] = {
            "status": "completed",
            "generation": resolved.generation,
            "manifest_sha256": resolved.manifest_sha256,
            "recovered_after_commit": True,
            "writer_run_id": bundle_writer_run_id,
        }
        bundle_data_update_run_id = bundle.get("data_update_run_id")
        bundle_global_run_id = bundle.get("global_run_id")
        if isinstance(bundle_data_update_run_id, str) and bundle_data_update_run_id:
            result["data_update_run_id"] = bundle_data_update_run_id
        if isinstance(bundle_global_run_id, str) and bundle_global_run_id:
            result["global_run_id"] = bundle_global_run_id
        return result
    if validation_error is not None:
        raise validation_error
    return None


def _require_completed_data_update_run(
    settings,
    *,
    data_update_run_id: str,
    global_run_id: str,
    report_date: str,
    workflow: str,
) -> None:
    matching = next(
        (
            row
            for row in reversed(latest_runs(settings.governance_path))
            if str(row.get("run_id") or "") == data_update_run_id
        ),
        None,
    )
    if matching is None or str(matching.get("status") or "") != "completed":
        raise FinancialPublicationInvalid(
            "System read bootstrap requires a persisted completed data-update run."
        )
    if (
        str(matching.get("global_run_id") or "") != global_run_id
        or str(matching.get("report_date") or "") != report_date
        or str(matching.get("workflow") or "") != workflow
    ):
        raise FinancialPublicationInvalid(
            "System read bootstrap does not match the completed data-update identity."
        )


def _validate_core_step_receipts(
    step_receipts: tuple[Mapping[str, object], ...],
    *,
    report_date: str,
) -> None:
    names = tuple(str(receipt.get("name") or "") for receipt in step_receipts)
    if names != SYSTEM_READ_CORE_REQUIRED_STEPS:
        raise FinancialPublicationInvalid(
            "System read publication requires the complete ordered core-financial receipts."
        )
    for receipt in step_receipts:
        if str(receipt.get("status") or "").lower() != "completed":
            raise FinancialPublicationInvalid("System read publication contains a failed step.")
        result = receipt.get("result")
        if not isinstance(result, Mapping) or str(result.get("status") or "").lower() != "completed":
            raise FinancialPublicationInvalid(
                f"System read publication step {receipt.get('name')!r} has no completed result."
            )
        result_date = str(result.get("report_date") or "").strip()
        if result_date and result_date != report_date:
            raise FinancialPublicationInvalid(
                f"System read publication step {receipt.get('name')!r} has a different report date."
            )


def _validate_pnl_reference(
    publication_root: Path,
    *,
    generation: str,
    manifest_sha256: str,
    require_current_pointer: bool = True,
):
    from backend.app.tasks.pnl_by_business_page_publication import (
        FINANCIAL_PUBLICATION_API_VERSION,
        FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )

    if require_current_pointer:
        pointer = read_publication_pointer(publication_root, require_valid=True)
        if (
            pointer is None
            or str(pointer.get("generation") or "") != generation
            or str(pointer.get("manifest_sha256") or "") != manifest_sha256
        ):
            raise FinancialPublicationInvalid(
                "System read publication must reference the current committed PnL generation."
            )
    return validate_sealed_financial_generation(
        publication_root,
        generation=generation,
        expected_manifest_sha256=manifest_sha256,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )


def _pnl_source_dependency_snapshot(
    settings,
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    generation: str,
    manifest_sha256: str,
    require_current_pointer: bool,
) -> dict[str, str]:
    from backend.app.tasks.pnl_by_business_page_publication import (
        _page_source_dependency_validator,
    )

    resolved = _validate_pnl_reference(
        Path(settings.financial_publication_root).resolve(),
        generation=generation,
        manifest_sha256=manifest_sha256,
        require_current_pointer=require_current_pointer,
    )
    sealed_payload = resolved.manifest.get("sealed_payload")
    sealed_dependencies = (
        sealed_payload.get("dependency_versions")
        if isinstance(sealed_payload, Mapping)
        else None
    )
    if not isinstance(sealed_dependencies, Mapping) or not sealed_dependencies:
        raise FinancialPublicationInvalid(
            "Pinned PnL generation has no sealed dependency lineage."
        )
    expected = {str(key): str(value) for key, value in sealed_dependencies.items()}
    current = {
        str(key): str(value)
        for key, value in _page_source_dependency_validator(
            report_date,
            settings=settings,
        )(conn).items()
    }
    if current != expected:
        raise FinancialPublicationInvalid(
            "Pinned PnL dependency lineage does not match the current source cut."
        )
    return {
        "pnl.manifest_sha256": manifest_sha256,
        **{
            f"pnl.dependency.{key}": value
            for key, value in sorted(expected.items())
        },
    }


def _collect_lineage_references(
    step_receipts: tuple[Mapping[str, object], ...],
) -> tuple[tuple[str, str], ...]:
    references: set[tuple[str, str]] = set()

    def visit(value: object, destination: set[tuple[str, str]]) -> None:
        if isinstance(value, Mapping):
            run_id = str(value.get("run_id") or "").strip()
            cache_key = str(value.get("cache_key") or "").strip()
            status = str(value.get("status") or "completed").lower()
            if run_id and cache_key and status == "completed":
                destination.add((run_id, cache_key))
            run_payload = value.get("run")
            lineage_payload = value.get("lineage")
            if isinstance(run_payload, Mapping) and isinstance(lineage_payload, Mapping):
                nested_run_id = str(run_payload.get("run_id") or "").strip()
                nested_cache_key = str(lineage_payload.get("cache_key") or "").strip()
                if nested_run_id and nested_cache_key:
                    destination.add((nested_run_id, nested_cache_key))
            for nested in value.values():
                visit(nested, destination)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for nested in value:
                visit(nested, destination)

    for receipt in step_receipts:
        step_name = str(receipt.get("name") or "")
        step_references: set[tuple[str, str]] = set()
        visit(receipt.get("result"), step_references)
        required_cache_key = _REQUIRED_CACHE_KEY_BY_CORE_STEP.get(step_name)
        if required_cache_key is not None and not any(
            cache_key == required_cache_key for _run_id, cache_key in step_references
        ):
            raise FinancialPublicationInvalid(
                "System read publication step "
                f"{step_name!r} has no exact {required_cache_key!r} terminal reference."
            )
        references.update(step_references)
    if not references:
        raise FinancialPublicationInvalid(
            "System read publication receipts contain no exact result-lineage references."
        )
    return tuple(sorted(references))


def _freeze_result_lineage(
    governance_repo: GovernanceRepository,
    *,
    lineage_references: tuple[tuple[str, str], ...],
    report_date: str,
    lineage_reference_dates: Mapping[str, str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    all_runs = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    all_manifests = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    for run_id, cache_key in lineage_references:
        reference_date = (
            str(lineage_reference_dates.get(cache_key) or report_date)
            if lineage_reference_dates is not None
            else report_date
        )
        matches = [
            row
            for row in all_runs
            if str(row.get("run_id") or "") == run_id
            and str(row.get("cache_key") or "") == cache_key
            and str(row.get("status") or "").lower() == "completed"
            and _row_covers_report_date(row, reference_date)
        ]
        if not matches:
            raise FinancialPublicationInvalid(
                f"Persisted completed terminal is missing for run_id={run_id!r}, cache_key={cache_key!r}."
            )
        run_row = dict(matches[-1])
        manifest_matches = [
            row
            for row in all_manifests
            if str(row.get("cache_key") or "") == cache_key
            and _manifest_matches_run(row, run_row)
        ]
        if not manifest_matches:
            raise FinancialPublicationInvalid(
                f"Persisted cache manifest is missing for run_id={run_id!r}, cache_key={cache_key!r}."
            )
    return {
        CACHE_BUILD_RUN_STREAM: [dict(row) for row in all_runs],
        CACHE_MANIFEST_STREAM: [dict(row) for row in all_manifests],
    }


def _row_covers_report_date(row: Mapping[str, object], report_date: str) -> bool:
    if _row_explicitly_covers_report_date(row, report_date):
        return True
    direct = str(row.get("report_date") or "").strip()
    dates = row.get("report_dates")
    return not direct and not (
        isinstance(dates, Sequence) and not isinstance(dates, (str, bytes)) and dates
    )


def _row_explicitly_covers_report_date(
    row: Mapping[str, object], report_date: str
) -> bool:
    direct = str(row.get("report_date") or "").strip()
    if direct:
        return direct == report_date
    dates = row.get("report_dates")
    return (
        isinstance(dates, Sequence)
        and not isinstance(dates, (str, bytes))
        and report_date in {str(value) for value in dates}
    )


def _manifest_matches_run(
    manifest: Mapping[str, object],
    run_row: Mapping[str, object],
) -> bool:
    for field_name in _TERMINAL_VERSION_FIELDS:
        terminal_value = str(run_row.get(field_name) or "").strip()
        manifest_value = str(manifest.get(field_name) or "").strip()
        if terminal_value and manifest_value != terminal_value:
            return False
    manifest_run_id = str(manifest.get("run_id") or "").strip()
    return not manifest_run_id or manifest_run_id == str(run_row.get("run_id") or "")


def _source_cut_snapshot(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_specs: tuple[FinancialTablePublicationSpec, ...],
    governance_streams: Mapping[str, object],
    lineage_references: tuple[tuple[str, str], ...],
    report_date: str,
    lineage_reference_dates: Mapping[str, str] | None = None,
    source_manifest_rows: Sequence[Mapping[str, object]] = (),
    source_preview_archive_root: str | Path | None = None,
    externally_qualified_tables: frozenset[str] = frozenset(),
    preserved_table_dependencies: Mapping[str, str] | None = None,
) -> dict[str, str]:
    snapshot: dict[str, str] = {
        "governance.result_lineage": hashlib.sha256(
            canonical_json_bytes(governance_streams)
        ).hexdigest()
    }
    table_profiles: dict[str, Mapping[str, object]] = {}
    for spec in table_specs:
        columns = conn.execute(
            "SELECT column_name, data_type, is_nullable, ordinal_position "
            "FROM information_schema.columns WHERE table_schema = 'main' AND table_name = ? "
            "ORDER BY ordinal_position",
            [spec.name],
        ).fetchall()
        if not columns:
            raise FinancialPublicationInvalid(
                f"System read source table {spec.name!r} is missing."
            )
        column_names = {str(row[0]) for row in columns}
        if spec.date_column not in column_names:
            raise FinancialPublicationInvalid(
                f"System read source table {spec.name!r} has no coverage column."
            )
        coverage_date = spec.required_dates[0]
        where_sql = f"try_cast({_quote_identifier(str(spec.date_column))} as date) = cast(? as date)"
        hash_arguments = ", ".join(
            _quote_identifier(str(row[0])) for row in columns
        )
        content_row = conn.execute(
            f"SELECT count(*), bit_xor(hash({hash_arguments})), "
            f"sum(cast(hash({hash_arguments}) as hugeint)) "
            f"FROM {_quote_identifier(spec.name)} "
            f"WHERE {where_sql}",
            [coverage_date],
        ).fetchone()
        assert content_row is not None
        row_count = int(content_row[0])
        if row_count < spec.minimum_rows_per_date:
            raise FinancialPublicationInvalid(
                f"System read source table {spec.name!r} has insufficient report-date coverage."
            )
        lineage_values: dict[str, list[str]] = {}
        for field_name in (*_TERMINAL_VERSION_FIELDS, "run_id"):
            if field_name not in column_names:
                continue
            values = conn.execute(
                f"SELECT DISTINCT cast({_quote_identifier(field_name)} as varchar) "
                f"FROM {_quote_identifier(spec.name)} WHERE {where_sql} "
                f"AND {_quote_identifier(field_name)} IS NOT NULL ORDER BY 1",
                [coverage_date],
            ).fetchall()
            lineage_values[field_name] = [str(row[0]) for row in values]
        profile = {
            "row_count": row_count,
            "content_hash_xor": str(content_row[1]),
            "content_hash_sum": str(content_row[2]),
            "schema": [list(row) for row in columns],
            "lineage_values": lineage_values,
        }
        table_profiles[spec.name] = profile
        snapshot[f"table.{spec.name}"] = hashlib.sha256(
            canonical_json_bytes(profile)
        ).hexdigest()
    _require_terminal_fact_link(
        governance_streams,
        conn=conn,
        table_specs=table_specs,
        table_profiles=table_profiles,
        lineage_references=lineage_references,
        report_date=report_date,
        lineage_reference_dates=lineage_reference_dates,
        source_manifest_rows=source_manifest_rows,
        source_preview_archive_root=source_preview_archive_root,
        externally_qualified_tables=externally_qualified_tables,
        preserved_table_dependencies=preserved_table_dependencies,
    )
    return snapshot


def _require_terminal_fact_link(
    governance_streams: Mapping[str, object],
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
    table_specs: tuple[FinancialTablePublicationSpec, ...] = (),
    table_profiles: Mapping[str, Mapping[str, object]],
    lineage_references: tuple[tuple[str, str], ...],
    report_date: str,
    lineage_reference_dates: Mapping[str, str] | None = None,
    source_manifest_rows: Sequence[Mapping[str, object]] = (),
    source_preview_archive_root: str | Path | None = None,
    externally_qualified_tables: frozenset[str] = frozenset(),
    preserved_table_dependencies: Mapping[str, str] | None = None,
) -> None:
    manifests = _exact_manifests_from_frozen_streams(
        governance_streams,
        lineage_references=lineage_references,
        report_date=report_date,
        lineage_reference_dates=lineage_reference_dates,
    )
    if not externally_qualified_tables.issubset(table_profiles):
        raise FinancialPublicationInvalid(
            "Writer receipt qualifies a table outside the required publication coverage."
        )
    normalized_preserved_dependencies = dict(preserved_table_dependencies or {})
    if not set(normalized_preserved_dependencies).issubset(table_profiles):
        raise FinancialPublicationInvalid(
            "Preserved sealed source-cut identity is outside the required publication coverage."
        )
    linked_tables: set[str] = set(externally_qualified_tables)
    for table_name, expected_sha256 in normalized_preserved_dependencies.items():
        observed_sha256 = hashlib.sha256(
            canonical_json_bytes(table_profiles[table_name])
        ).hexdigest()
        if observed_sha256 != _required_sha256(
            expected_sha256,
            f"preserved source-cut identity for {table_name}",
        ):
            raise FinancialPublicationInvalid(
                f"Preserved sealed source cut changed for {table_name!r}."
            )
        linked_tables.add(table_name)
    for manifest in manifests:
        manifest_report_date = str(
            manifest.get("__system_reference_date") or report_date
        )
        fact_tables = manifest.get("fact_tables")
        declared_facts = (
            {str(value) for value in fact_tables}
            if isinstance(fact_tables, Sequence) and not isinstance(fact_tables, (str, bytes))
            else set()
        )
        input_sources = manifest.get("input_sources")
        declared_inputs = (
            {str(value) for value in input_sources}
            if isinstance(input_sources, Sequence) and not isinstance(input_sources, (str, bytes))
            else set()
        )
        cache_key = str(manifest.get("cache_key") or "")
        declared_facts.update(_SPECIAL_FACT_TABLES_BY_CACHE_KEY.get(cache_key, ()))
        balance_fact_tables = {
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        }
        balance_semantics = (
            cache_key == "balance_analysis:materialize:formal"
            and balance_fact_tables.issubset(declared_facts)
        )
        bond_semantics = (
            cache_key == "bond_analytics:materialize:formal"
            and "fact_formal_bond_analytics_daily" in declared_facts
        )
        pnl_semantics = cache_key == "pnl:phase2:materialize:formal" and {
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
        }.issubset(declared_facts)
        product_category_semantics = (
            cache_key == "product_category_pnl.formal"
            and _has_product_category_stored_state(manifest)
        )
        accounting_semantics = (
            cache_key == "accounting_asset_movement.monthly"
            and "fact_accounting_asset_movement_monthly" in declared_facts
        )
        terminal_run = manifest.get("__system_terminal_run")
        source_preview_semantics = (
            cache_key == "source_preview.foundation"
            and isinstance(terminal_run, Mapping)
        )
        producer_partition_semantics = (
            balance_semantics
            or bond_semantics
            or pnl_semantics
            or product_category_semantics
            or accounting_semantics
            or source_preview_semantics
        )
        if producer_partition_semantics:
            if conn is None or _manifest_matches_current_facts(
                conn,
                manifest=manifest,
                table_specs=table_specs,
                report_date=manifest_report_date,
                terminal_run=terminal_run if isinstance(terminal_run, Mapping) else None,
                source_manifest_rows=source_manifest_rows,
                source_preview_archive_root=source_preview_archive_root,
            ) is not True:
                raise FinancialPublicationInvalid(
                    f"Frozen {cache_key} terminal source version does not match current facts."
                )
        for table_name_value in declared_facts | declared_inputs:
            table_name = str(table_name_value)
            profile = table_profiles.get(table_name)
            if profile is None:
                continue
            linked_tables.add(table_name)
            if table_name in declared_inputs and table_name not in declared_facts:
                continue
            if producer_partition_semantics:
                continue
            lineage_values = profile.get("lineage_values")
            if not isinstance(lineage_values, Mapping):
                continue
            for field_name in _TERMINAL_VERSION_FIELDS:
                expected = str(manifest.get(field_name) or "").strip()
                observed = lineage_values.get(field_name)
                if expected and isinstance(observed, Sequence) and set(observed) != {expected}:
                    raise FinancialPublicationInvalid(
                        f"Frozen terminal {field_name} does not match source facts for {table_name!r}."
                    )
    missing_links = sorted(set(table_profiles) - linked_tables)
    if missing_links:
        raise FinancialPublicationInvalid(
            "Frozen exact result-lineage does not cover required source tables: "
            + ", ".join(missing_links)
        )


def _exact_manifests_from_frozen_streams(
    governance_streams: Mapping[str, object],
    *,
    lineage_references: tuple[tuple[str, str], ...],
    report_date: str,
    lineage_reference_dates: Mapping[str, str] | None = None,
) -> list[Mapping[str, object]]:
    runs = governance_streams.get(CACHE_BUILD_RUN_STREAM)
    manifests = governance_streams.get(CACHE_MANIFEST_STREAM)
    if (
        not isinstance(runs, Sequence)
        or isinstance(runs, (str, bytes))
        or not isinstance(manifests, Sequence)
        or isinstance(manifests, (str, bytes))
    ):
        raise FinancialPublicationInvalid("Frozen result-lineage streams are unavailable.")
    exact: list[Mapping[str, object]] = []
    for run_id, cache_key in lineage_references:
        reference_date = (
            str(lineage_reference_dates.get(cache_key) or report_date)
            if lineage_reference_dates is not None
            else report_date
        )
        run_matches = [
            row
            for row in runs
            if isinstance(row, Mapping)
            and str(row.get("run_id") or "") == run_id
            and str(row.get("cache_key") or "") == cache_key
            and str(row.get("status") or "").lower() == "completed"
            and _row_covers_report_date(row, reference_date)
        ]
        if not run_matches:
            raise FinancialPublicationInvalid(
                f"Frozen completed terminal is missing for run_id={run_id!r}, cache_key={cache_key!r}."
            )
        manifest_matches = [
            row
            for row in manifests
            if isinstance(row, Mapping)
            and str(row.get("cache_key") or "") == cache_key
            and _manifest_matches_run(row, run_matches[-1])
        ]
        if not manifest_matches:
            raise FinancialPublicationInvalid(
                f"Frozen cache manifest is missing for run_id={run_id!r}, cache_key={cache_key!r}."
            )
        exact_manifest = dict(manifest_matches[-1])
        exact_manifest["__system_terminal_run"] = dict(run_matches[-1])
        exact_manifest["__system_reference_date"] = reference_date
        exact.append(exact_manifest)
    return exact


def _system_generation(
    *,
    report_date: str,
    data_update_run_id: str,
    global_run_id: str,
    pnl_generation: str,
    pnl_manifest_sha256: str,
) -> str:
    digest = hashlib.sha256(
        canonical_json_bytes(
            {
                "report_date": report_date,
                "data_update_run_id": data_update_run_id,
                "global_run_id": global_run_id,
                "pnl_generation": pnl_generation,
                "pnl_manifest_sha256": pnl_manifest_sha256,
            }
        )
    ).hexdigest()[:20]
    return f"system-read-{report_date}-{digest}"


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinancialPublicationInvalid(f"{label} must be a non-empty string.")
    return value.strip()


def _required_sha256(value: object, label: str) -> str:
    normalized = _required_text(value, label)
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise FinancialPublicationInvalid(f"{label} must be a lowercase SHA-256 digest.")
    return normalized


def _writer_dependency_snapshot(values: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(values, Mapping) or not values:
        raise FinancialPublicationInvalid(
            "Changed-source validator returned no immutable dependency evidence."
        )
    normalized: dict[str, str] = {}
    for key, value in values.items():
        normalized_key = _required_text(key, "writer dependency key")
        normalized_value = _required_text(value, "writer dependency value")
        normalized[f"writer.dependency.{normalized_key}"] = normalized_value
    return normalized


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
