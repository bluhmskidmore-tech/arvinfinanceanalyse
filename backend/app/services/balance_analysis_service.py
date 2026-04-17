from __future__ import annotations

"""
Balance-analysis read surfaces: DuckDB access only via `BalanceAnalysisRepository` and other read repositories.

Formal fact writes (`replace_formal_balance_rows`, snapshot tables) are restricted to `backend/app/tasks/` workers.
"""

import importlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from backend.app.core_finance.module_registry import get_formal_module_by_fact_table
from backend.app.governance.formal_compute_lineage import (
    resolve_completed_formal_build_lineage,
    resolve_formal_manifest_lineage,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.balance_analysis_decision_repo import BalanceAnalysisDecisionRepository
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.balance_analysis import (
    BalanceAnalysisBasisBreakdownPayload,
    BalanceAnalysisBasisBreakdownRow,
    BalanceAnalysisDecisionItemRow,
    BalanceAnalysisDecisionItemStatusRow,
    BalanceAnalysisDecisionItemsSection,
    BalanceAnalysisDecisionItemsPayload,
    BalanceAnalysisDecisionStatusRecord,
    BalanceAnalysisDecisionStatusUpdateRequest,
    BalanceAnalysisDatesPayload,
    BalanceAnalysisDetailRow,
    BalanceAnalysisEventCalendarRow,
    BalanceAnalysisEventCalendarSection,
    BalanceAnalysisPayload,
    BalanceAnalysisRiskAlertRow,
    BalanceAnalysisRiskAlertsSection,
    BalanceAnalysisSummaryRow,
    BalanceAnalysisSummaryTablePayload,
    BalanceAnalysisWorkbookCard,
    BalanceAnalysisWorkbookColumn,
    BalanceAnalysisWorkbookPayload,
    BalanceAnalysisWorkbookTable,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.services import balance_analysis_summary_export_service
from backend.app.services import balance_analysis_workbook_service
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage,
)
from backend.app.tasks.balance_analysis_materialize import (
    materialize_balance_analysis_facts,
)

BALANCE_ANALYSIS_PRIMARY_FACT_TABLE = "fact_formal_zqtz_balance_daily"
BALANCE_ANALYSIS_MODULE = get_formal_module_by_fact_table(BALANCE_ANALYSIS_PRIMARY_FACT_TABLE)
BALANCE_ANALYSIS_SECONDARY_FACT_TABLE = "fact_formal_tyw_balance_daily"
if BALANCE_ANALYSIS_SECONDARY_FACT_TABLE not in BALANCE_ANALYSIS_MODULE.fact_tables:
    raise RuntimeError(
        "Balance-analysis module registration mismatch: expected secondary fact table "
        f"{BALANCE_ANALYSIS_SECONDARY_FACT_TABLE!r} in module {BALANCE_ANALYSIS_MODULE.module_name!r}."
    )

CACHE_KEY = BALANCE_ANALYSIS_MODULE.cache_key
CACHE_VERSION = BALANCE_ANALYSIS_MODULE.cache_version
RULE_VERSION = BALANCE_ANALYSIS_MODULE.rule_version
BALANCE_ANALYSIS_LOCK = BALANCE_ANALYSIS_MODULE.lock_definition

BALANCE_ANALYSIS_JOB_NAME = "balance_analysis_materialize"
PENDING_SOURCE_VERSION = "sv_balance_analysis_pending"
ALLOWED_BALANCE_POSITION_SCOPES = frozenset({"asset", "liability", "all"})
ALLOWED_BALANCE_CURRENCY_BASES = frozenset({"native", "CNY"})
IN_FLIGHT_STATUSES = {"queued", "running"}
STALE_IN_FLIGHT_AFTER = timedelta(hours=1)
DEFAULT_BALANCE_DECISION_UPDATED_BY = "balance-analysis-ui"


class BalanceAnalysisRefreshServiceError(RuntimeError):
    pass


class BalanceAnalysisRefreshConflictError(RuntimeError):
    pass


def refresh_balance_analysis(settings: Settings, *, report_date: str) -> dict[str, object]:
    try:
        with acquire_lock(
            _refresh_trigger_lock(report_date=report_date),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
            existing = _latest_inflight_refresh(settings, report_date=report_date)
            if existing is not None:
                raise BalanceAnalysisRefreshConflictError(
                    f"Balance-analysis refresh already in progress for report_date={report_date}."
                )

            run_id = _build_run_id()
            queued_at = datetime.now(timezone.utc).isoformat()
            GovernanceRepository(base_dir=settings.governance_path).append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **CacheBuildRunRecord(
                        run_id=run_id,
                        job_name=BALANCE_ANALYSIS_JOB_NAME,
                        status="queued",
                        cache_key=CACHE_KEY,
                        cache_version=CACHE_VERSION,
                        lock=BALANCE_ANALYSIS_LOCK.key,
                        source_version=PENDING_SOURCE_VERSION,
                        vendor_version="vv_none",
                    ).model_dump(),
                    "report_date": report_date,
                    "queued_at": queued_at,
                },
            )
            try:
                materialize_balance_analysis_facts.send(
                    report_date=report_date,
                    duckdb_path=str(settings.duckdb_path),
                    governance_dir=str(settings.governance_path),
                    run_id=run_id,
                )
            except Exception as exc:
                _record_dispatch_failure(
                    settings=settings,
                    run_id=run_id,
                    report_date=report_date,
                    error_message="Balance-analysis refresh queue dispatch failed.",
                )
                raise BalanceAnalysisRefreshServiceError(
                    "Balance-analysis refresh queue dispatch failed."
                ) from exc

            return {
                "status": "queued",
                "run_id": run_id,
                "job_name": BALANCE_ANALYSIS_JOB_NAME,
                "trigger_mode": "async",
                "cache_key": CACHE_KEY,
                "report_date": report_date,
            }
    except TimeoutError as exc:
        raise BalanceAnalysisRefreshConflictError(
            f"Balance-analysis refresh already in progress for report_date={report_date}."
        ) from exc


def balance_analysis_refresh_status(settings: Settings, *, run_id: str) -> dict[str, object]:
    records = [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == CACHE_KEY
        and str(record.get("job_name")) == BALANCE_ANALYSIS_JOB_NAME
        and str(record.get("run_id")) == run_id
    ]
    if not records:
        raise ValueError(f"Unknown balance-analysis refresh run_id={run_id}")
    latest = records[-1]
    status = str(latest.get("status", "unknown"))
    return {
        **latest,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
    }


def balance_analysis_dates_envelope(*, duckdb_path: str, governance_dir: str) -> dict[str, object]:
    repo = BalanceAnalysisRepository(duckdb_path)
    payload = BalanceAnalysisDatesPayload(report_dates=repo.list_report_dates())
    lineage = resolve_formal_manifest_lineage(
        governance_dir=governance_dir,
        cache_key=CACHE_KEY,
    )
    return build_formal_result_envelope_from_lineage(
        trace_id="tr_balance_analysis_dates",
        result_kind="balance-analysis.dates",
        lineage=lineage,
        default_cache_version=CACHE_VERSION,
        result_payload=payload.model_dump(mode="json"),
    )


def balance_analysis_overview_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> dict[str, object]:
    _validate_balance_overview_filters(
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    repo = BalanceAnalysisRepository(duckdb_path)
    if report_date not in repo.list_report_dates():
        raise ValueError(f"No balance-analysis data found for report_date={report_date}.")

    overview = repo.fetch_formal_overview(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    build_lineage = resolve_completed_formal_build_lineage(
        governance_dir=governance_dir,
        cache_key=CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        report_date=report_date,
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=f"tr_balance_analysis_overview_{report_date}_{position_scope}_{currency_basis}",
        result_kind="balance-analysis.overview",
        lineage=build_lineage,
        default_cache_version=CACHE_VERSION,
        rule_version=overview.get("rule_version"),
        missing_field_message=lambda field_name: _balance_lineage_missing_message(
            field_name=field_name,
            report_date=report_date,
        ),
        result_payload={
            "report_date": str(overview["report_date"]),
            "position_scope": str(overview["position_scope"]),
            "currency_basis": str(overview["currency_basis"]),
            "detail_row_count": int(overview["detail_row_count"]),
            "summary_row_count": int(overview["summary_row_count"]),
            "total_market_value_amount": _as_decimal(overview["total_market_value_amount"]),
            "total_amortized_cost_amount": _as_decimal(overview["total_amortized_cost_amount"]),
            "total_accrued_interest_amount": _as_decimal(overview["total_accrued_interest_amount"]),
        },
    )


def balance_analysis_summary_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    _validate_balance_overview_filters(
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    repo = BalanceAnalysisRepository(duckdb_path)
    if report_date not in repo.list_report_dates():
        raise ValueError(f"No balance-analysis data found for report_date={report_date}.")

    table = repo.fetch_formal_summary_table(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
        limit=limit,
        offset=offset,
    )
    build_lineage = resolve_completed_formal_build_lineage(
        governance_dir=governance_dir,
        cache_key=CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        report_date=report_date,
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=f"tr_balance_analysis_summary_{report_date}_{position_scope}_{currency_basis}_{offset}_{limit}",
        result_kind="balance-analysis.summary",
        lineage=build_lineage,
        default_cache_version=CACHE_VERSION,
        missing_field_message=lambda field_name: _balance_lineage_missing_message(
            field_name=field_name,
            report_date=report_date,
        ),
        result_payload=BalanceAnalysisSummaryTablePayload(
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
            limit=limit,
            offset=offset,
            total_rows=int(table["total_rows"]),
            rows=[
                _to_summary_table_row(row).model_dump(mode="json")
                for row in table["rows"]
            ],
        ).model_dump(mode="json"),
    )


def balance_analysis_basis_breakdown_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> dict[str, object]:
    _validate_balance_overview_filters(
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    repo = BalanceAnalysisRepository(duckdb_path)
    if report_date not in repo.list_report_dates():
        raise ValueError(f"No balance-analysis data found for report_date={report_date}.")

    breakdown_rows = repo.fetch_formal_basis_breakdown(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    build_lineage = resolve_completed_formal_build_lineage(
        governance_dir=governance_dir,
        cache_key=CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        report_date=report_date,
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=f"tr_balance_analysis_basis_breakdown_{report_date}_{position_scope}_{currency_basis}",
        result_kind="balance-analysis.basis-breakdown",
        lineage=build_lineage,
        default_cache_version=CACHE_VERSION,
        missing_field_message=lambda field_name: _balance_lineage_missing_message(
            field_name=field_name,
            report_date=report_date,
        ),
        result_payload=BalanceAnalysisBasisBreakdownPayload(
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
            rows=[_to_basis_breakdown_row(row) for row in breakdown_rows],
        ).model_dump(mode="json"),
    )


def export_balance_analysis_summary_csv(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> tuple[str, str]:
    return balance_analysis_summary_export_service.export_balance_analysis_summary_csv(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
        cache_key=CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        validate_filters_fn=_validate_balance_overview_filters,
        require_lineage_value_fn=_require_balance_lineage_value,
        resolve_completed_formal_build_lineage_fn=resolve_completed_formal_build_lineage,
        repo_cls=BalanceAnalysisRepository,
    )


def export_balance_analysis_workbook_xlsx(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> tuple[str, bytes]:
    workbook_payload = balance_analysis_workbook_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )["result"]
    filename = f"资产负债分析_{report_date}.xlsx"
    return filename, _build_balance_analysis_workbook_xlsx_bytes(workbook_payload)


def balance_analysis_detail_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> dict[str, object]:
    repo = BalanceAnalysisRepository(duckdb_path)
    if report_date not in repo.list_report_dates():
        raise ValueError(f"No balance-analysis data found for report_date={report_date}.")

    zqtz_rows = repo.fetch_formal_zqtz_rows(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    tyw_rows = repo.fetch_formal_tyw_rows(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )

    details = [
        *[_to_zqtz_detail_row(row) for row in zqtz_rows],
        *[_to_tyw_detail_row(row) for row in tyw_rows],
    ]
    summary = _build_summary_rows(details)
    build_lineage = resolve_completed_formal_build_lineage(
        governance_dir=governance_dir,
        cache_key=CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        report_date=report_date,
    )

    return build_formal_result_envelope_from_lineage(
        trace_id=f"tr_balance_analysis_detail_{report_date}_{position_scope}_{currency_basis}",
        result_kind="balance-analysis.detail",
        lineage=build_lineage,
        default_cache_version=CACHE_VERSION,
        source_version=_combine_lineage_values([*zqtz_rows, *tyw_rows], "source_version"),
        rule_version=_combine_lineage_values([*zqtz_rows, *tyw_rows], "rule_version") or RULE_VERSION,
        missing_field_message=lambda field_name: _balance_lineage_missing_message(
            field_name=field_name,
            report_date=report_date,
        ),
        result_payload=BalanceAnalysisPayload(
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
            details=details,
            summary=summary,
        ).model_dump(mode="json"),
    )


def balance_analysis_workbook_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> dict[str, object]:
    _validate_balance_overview_filters(
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    workbook, build_lineage = _build_balance_workbook_payload(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=f"tr_balance_analysis_workbook_{report_date}_{position_scope}_{currency_basis}",
        result_kind="balance-analysis.workbook",
        lineage=build_lineage,
        default_cache_version=CACHE_VERSION,
        missing_field_message=lambda field_name: _balance_lineage_missing_message(
            field_name=field_name,
            report_date=report_date,
        ),
        result_payload=BalanceAnalysisWorkbookPayload(
            report_date=workbook["report_date"],
            position_scope=workbook["position_scope"],
            currency_basis=workbook["currency_basis"],
            cards=[
                BalanceAnalysisWorkbookCard(**card)
                for card in workbook["cards"]
            ],
            tables=[
                BalanceAnalysisWorkbookTable(
                    key=table["key"],
                    title=table["title"],
                    section_kind=table["section_kind"],
                    columns=[BalanceAnalysisWorkbookColumn(**column) for column in table["columns"]],
                    rows=table["rows"],
                )
                for table in workbook["tables"]
                if str(table.get("section_kind")) == "table"
            ],
            operational_sections=[
                *[
                    BalanceAnalysisDecisionItemsSection(
                        key="decision_items",
                        title=str(section["title"]),
                        section_kind="decision_items",
                        columns=[BalanceAnalysisWorkbookColumn(**column) for column in section["columns"]],
                        rows=[BalanceAnalysisDecisionItemRow(**row) for row in section["rows"]],
                    )
                    for section in workbook["tables"]
                    if str(section.get("section_kind")) == "decision_items"
                ],
                *[
                    BalanceAnalysisEventCalendarSection(
                        key="event_calendar",
                        title=str(section["title"]),
                        section_kind="event_calendar",
                        columns=[BalanceAnalysisWorkbookColumn(**column) for column in section["columns"]],
                        rows=[BalanceAnalysisEventCalendarRow(**row) for row in section["rows"]],
                    )
                    for section in workbook["tables"]
                    if str(section.get("section_kind")) == "event_calendar"
                ],
                *[
                    BalanceAnalysisRiskAlertsSection(
                        key="risk_alerts",
                        title=str(section["title"]),
                        section_kind="risk_alerts",
                        columns=[BalanceAnalysisWorkbookColumn(**column) for column in section["columns"]],
                        rows=[BalanceAnalysisRiskAlertRow(**row) for row in section["rows"]],
                    )
                    for section in workbook["tables"]
                    if str(section.get("section_kind")) == "risk_alerts"
                ],
            ],
        ).model_dump(mode="json"),
    )


def balance_analysis_decision_items_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"] = "all",
    currency_basis: Literal["native", "CNY"] = "CNY",
) -> dict[str, object]:
    _validate_balance_overview_filters(
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    workbook, build_lineage = _build_balance_workbook_payload(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    decision_section = _extract_generated_decision_section(workbook)
    latest_statuses = BalanceAnalysisDecisionRepository(governance_dir).list_latest_statuses(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=f"tr_balance_analysis_decision_items_{report_date}_{position_scope}_{currency_basis}",
        result_kind="balance-analysis.decision-items",
        lineage=build_lineage,
        default_cache_version=CACHE_VERSION,
        missing_field_message=lambda field_name: _balance_lineage_missing_message(
            field_name=field_name,
            report_date=report_date,
        ),
        result_payload=BalanceAnalysisDecisionItemsPayload(
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
            columns=[
                BalanceAnalysisWorkbookColumn(**column)
                for column in decision_section.get("columns", [])
            ],
            rows=[
                _to_decision_item_status_row(row, latest_statuses)
                for row in decision_section.get("rows", [])
            ],
        ).model_dump(mode="json"),
    )


def update_balance_analysis_decision_status(
    *,
    duckdb_path: str,
    governance_dir: str,
    update: BalanceAnalysisDecisionStatusUpdateRequest,
    updated_by: str,
) -> BalanceAnalysisDecisionStatusRecord:
    workbook, _build_lineage = _build_balance_workbook_payload(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=update.report_date,
        position_scope=update.position_scope,
        currency_basis=update.currency_basis,
    )
    valid_decision_keys = {
        _build_decision_key(row)
        for row in _extract_generated_decision_section(workbook).get("rows", [])
        if isinstance(row, dict)
    }
    if update.decision_key not in valid_decision_keys:
        raise ValueError(
            "Unknown balance-analysis decision_key for the requested report_date and filters."
        )

    record = BalanceAnalysisDecisionStatusRecord(
        decision_key=update.decision_key,
        status=update.status,
        updated_at=datetime.now(timezone.utc).isoformat(),
        updated_by=(updated_by or DEFAULT_BALANCE_DECISION_UPDATED_BY).strip()
        or DEFAULT_BALANCE_DECISION_UPDATED_BY,
        comment=update.comment,
    )
    BalanceAnalysisDecisionRepository(governance_dir).append_status(
        {
            "report_date": update.report_date,
            "position_scope": update.position_scope,
            "currency_basis": update.currency_basis,
            **record.model_dump(mode="json"),
        }
    )
    return record


def _to_zqtz_detail_row(row: dict[str, object]) -> BalanceAnalysisDetailRow:
    instrument_code = str(row["instrument_code"])
    return BalanceAnalysisDetailRow(
        source_family="zqtz",
        report_date=str(row["report_date"]),
        row_key=f"zqtz:{instrument_code}:{row['currency_basis']}:{row['position_scope']}",
        display_name=instrument_code,
        position_scope=str(row["position_scope"]),
        currency_basis=str(row["currency_basis"]),
        invest_type_std=str(row["invest_type_std"]),
        accounting_basis=str(row["accounting_basis"]),
        market_value_amount=_as_decimal(row["market_value_amount"]),
        amortized_cost_amount=_as_decimal(row["amortized_cost_amount"]),
        accrued_interest_amount=_as_decimal(row["accrued_interest_amount"]),
        is_issuance_like=bool(row["is_issuance_like"]),
    )


def _to_tyw_detail_row(row: dict[str, object]) -> BalanceAnalysisDetailRow:
    position_id = str(row["position_id"])
    principal = _as_decimal(row["principal_amount"])
    accrued = _as_decimal(row["accrued_interest_amount"])
    return BalanceAnalysisDetailRow(
        source_family="tyw",
        report_date=str(row["report_date"]),
        row_key=f"tyw:{position_id}:{row['currency_basis']}:{row['position_scope']}",
        display_name=position_id,
        position_scope=str(row["position_scope"]),
        currency_basis=str(row["currency_basis"]),
        invest_type_std=str(row["invest_type_std"]),
        accounting_basis=str(row["accounting_basis"]),
        market_value_amount=principal,
        amortized_cost_amount=principal,
        accrued_interest_amount=accrued,
        is_issuance_like=None,
    )


def _to_basis_breakdown_row(row: dict[str, object]) -> BalanceAnalysisBasisBreakdownRow:
    return BalanceAnalysisBasisBreakdownRow(
        source_family=str(row["source_family"]),  # type: ignore[arg-type]
        invest_type_std=str(row["invest_type_std"]),
        accounting_basis=str(row["accounting_basis"]),
        position_scope=str(row["position_scope"]),  # type: ignore[arg-type]
        currency_basis=str(row["currency_basis"]),  # type: ignore[arg-type]
        detail_row_count=int(row["detail_row_count"]),
        market_value_amount=_as_decimal(row["market_value_amount"]),
        amortized_cost_amount=_as_decimal(row["amortized_cost_amount"]),
        accrued_interest_amount=_as_decimal(row["accrued_interest_amount"]),
    )


def _build_balance_workbook_payload(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"],
    currency_basis: Literal["native", "CNY"],
) -> tuple[dict[str, Any], dict[str, object] | None]:
    return balance_analysis_workbook_service._build_balance_workbook_payload(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
        cache_key=CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        resolve_completed_formal_build_lineage_fn=resolve_completed_formal_build_lineage,
        repo_cls=BalanceAnalysisRepository,
        import_module_fn=importlib.import_module,
        reload_module_fn=importlib.reload,
    )


def _extract_generated_decision_section(workbook: dict[str, Any]) -> dict[str, Any]:
    return balance_analysis_workbook_service._extract_generated_decision_section(workbook)


def _build_decision_key(row: dict[str, object]) -> str:
    return "::".join(
        [
            str(row.get("rule_id") or "").strip(),
            str(row.get("source_section") or "").strip(),
            str(row.get("title") or "").strip(),
        ]
    )


def _default_pending_decision_status(decision_key: str) -> BalanceAnalysisDecisionStatusRecord:
    return BalanceAnalysisDecisionStatusRecord(
        decision_key=decision_key,
        status="pending",
        updated_at=None,
        updated_by=None,
        comment=None,
    )


def _to_decision_item_status_row(
    row: dict[str, object],
    latest_statuses: dict[str, dict[str, object]],
) -> BalanceAnalysisDecisionItemStatusRow:
    decision_key = _build_decision_key(row)
    latest_status = latest_statuses.get(decision_key)
    return BalanceAnalysisDecisionItemStatusRow(
        decision_key=decision_key,
        title=str(row["title"]),
        action_label=str(row["action_label"]),
        severity=str(row["severity"]),
        reason=str(row["reason"]),
        source_section=str(row["source_section"]),
        rule_id=str(row["rule_id"]),
        rule_version=str(row["rule_version"]),
        latest_status=(
            BalanceAnalysisDecisionStatusRecord(**latest_status)
            if latest_status is not None
            else _default_pending_decision_status(decision_key)
        ),
    )

def _build_summary_rows(details: list[BalanceAnalysisDetailRow]) -> list[BalanceAnalysisSummaryRow]:
    grouped: dict[tuple[str, str, str], dict[str, Decimal | int]] = {}
    for row in details:
        key = (row.source_family, row.position_scope, row.currency_basis)
        bucket = grouped.setdefault(
            key,
            {
                "row_count": 0,
                "market_value_amount": Decimal("0"),
                "amortized_cost_amount": Decimal("0"),
                "accrued_interest_amount": Decimal("0"),
            },
        )
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["market_value_amount"] = _as_decimal(bucket["market_value_amount"]) + row.market_value_amount
        bucket["amortized_cost_amount"] = _as_decimal(bucket["amortized_cost_amount"]) + row.amortized_cost_amount
        bucket["accrued_interest_amount"] = _as_decimal(bucket["accrued_interest_amount"]) + row.accrued_interest_amount

    return [
        BalanceAnalysisSummaryRow(
            source_family=source_family,
            position_scope=position_scope,
            currency_basis=currency_basis,
            row_count=int(values["row_count"]),
            market_value_amount=_as_decimal(values["market_value_amount"]),
            amortized_cost_amount=_as_decimal(values["amortized_cost_amount"]),
            accrued_interest_amount=_as_decimal(values["accrued_interest_amount"]),
        )
        for (source_family, position_scope, currency_basis), values in sorted(grouped.items())
    ]


def _to_summary_table_row(row: dict[str, object]):
    return balance_analysis_summary_export_service._to_summary_table_row(row)


def _combine_lineage_values(rows: list[dict[str, object]], field_name: str) -> str:
    values = sorted(
        {
            str(row.get(field_name) or "").strip()
            for row in rows
            if str(row.get(field_name) or "").strip()
        }
    )
    return "__".join(values) or "sv_balance_analysis_empty"


def _build_balance_analysis_workbook_xlsx_bytes(payload: dict[str, Any]) -> bytes:
    return balance_analysis_workbook_service._build_balance_analysis_workbook_xlsx_bytes(payload)

def _balance_lineage_missing_message(*, field_name: str, report_date: str) -> str:
    return f"Canonical balance-analysis {field_name} unavailable for report_date={report_date}."


def _validate_balance_overview_filters(*, position_scope: str, currency_basis: str) -> None:
    if position_scope not in ALLOWED_BALANCE_POSITION_SCOPES:
        raise ValueError(
            f"Unsupported balance-analysis position_scope={position_scope}. "
            f"Expected one of {sorted(ALLOWED_BALANCE_POSITION_SCOPES)}."
        )
    if currency_basis not in ALLOWED_BALANCE_CURRENCY_BASES:
        raise ValueError(
            f"Unsupported balance-analysis currency_basis={currency_basis}. "
            f"Expected one of {sorted(ALLOWED_BALANCE_CURRENCY_BASES)}."
        )


def _require_balance_lineage_value(value: object, *, report_date: str, field_name: str) -> str:
    resolved = str(value or "").strip()
    if not resolved:
        raise RuntimeError(
            f"Canonical balance-analysis {field_name} unavailable for report_date={report_date}."
        )
    return resolved


def _refresh_trigger_lock(*, report_date: str) -> LockDefinition:
    return LockDefinition(
        key=f"{BALANCE_ANALYSIS_LOCK.key}:{report_date}:trigger",
        ttl_seconds=30,
    )


def _load_refresh_run_records(settings: Settings) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == CACHE_KEY
        and str(record.get("job_name")) == BALANCE_ANALYSIS_JOB_NAME
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
            error_message="Marked stale balance-analysis refresh run as failed.",
        )
    return None


def _is_stale_inflight_record(record: dict[str, object]) -> bool:
    for field_name in ("started_at", "queued_at", "created_at"):
        raw_value = str(record.get(field_name) or "").strip()
        if not raw_value:
            continue
        timestamp = _parse_timestamp(raw_value)
        return datetime.now(timezone.utc) - timestamp > STALE_IN_FLIGHT_AFTER
    return True


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
            "job_name": BALANCE_ANALYSIS_JOB_NAME,
            "status": "failed",
            "cache_key": CACHE_KEY,
            "lock": BALANCE_ANALYSIS_LOCK.key,
            "source_version": "sv_balance_analysis_failed",
            "vendor_version": "vv_none",
            "report_date": report_date,
            "error_message": error_message,
        },
    )


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
            "job_name": BALANCE_ANALYSIS_JOB_NAME,
            "status": "failed",
            "cache_key": CACHE_KEY,
            "lock": BALANCE_ANALYSIS_LOCK.key,
            "source_version": "sv_balance_analysis_stale",
            "vendor_version": "vv_none",
            "report_date": report_date,
            "error_message": error_message,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _build_run_id() -> str:
    return f"{BALANCE_ANALYSIS_JOB_NAME}:{datetime.now(timezone.utc).isoformat()}"


def _as_decimal(value: object) -> Decimal:
    return balance_analysis_workbook_service._as_decimal(value)
