from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from backend.app.config.product_category_mapping import resolve_product_category_ftp_rate_pct
from backend.app.core_finance.config.classification_rules import LEDGER_PNL_ACCOUNT_PREFIXES
from backend.app.core_finance.field_normalization import original_asset_currency_from_instrument_code
from backend.app.core_finance.pnl import (
    FI_514_VAT_DIVISOR,
    PnlByBusinessMonthlyMeasure,
    compute_nonstd_signed_ledger_amount,
    compute_pnl_by_business_monthly_change,
    compute_pnl_by_business_yield_and_ftp,
    normalize_fi_interest_income_514,
    normalize_nonstd_interest_income_514,
)
from backend.app.core_finance.reconciliation_checks import pnl_vs_ledger_diff
from backend.app.core_finance.zqtz_asset_bond_category import (
    ZQTZ_ASSET_BOND_ROWS,
    is_parent_zqtz_business_row,
    match_zqtz_asset_bond_rows,
)
from backend.app.governance.formal_compute_lineage import (
    resolve_formal_manifest_lineage_with_completed_build,
)
from backend.app.governance.locks import LockDefinition, acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.accounting_asset_movement_repo import AccountingAssetMovementRepository
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION, PnlRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.pnl import (
    PnlByBusinessAnalysisDimension,
    PnlByBusinessAnalysisPayload,
    PnlByBusinessAnalysisRow,
    PnlByBusinessManualAdjustmentListPayload,
    PnlByBusinessManualAdjustmentPayload,
    PnlByBusinessManualAdjustmentRequest,
    PnlByBusinessMonthlyBucket,
    PnlByBusinessMonthlyChangeMetrics,
    PnlByBusinessMonthlyChangeRow,
    PnlByBusinessMonthlyItem,
    PnlByBusinessMonthlyManagementChange,
    PnlByBusinessMonthlyPayload,
    PnlByBusinessMonthlySummary,
    PnlByBusinessPayload,
    PnlByBusinessRow,
    PnlByBusinessUntracedBreakdownRow,
    PnlByBusinessYtdItem,
    PnlByBusinessYtdPayload,
    PnlByBusinessYtdSummary,
    PnlByBusinessYtdUnallocatedBreakdownRow,
    PnlByBusinessYtdUnallocatedItem,
    PnlDataPayload,
    PnlDatesPayload,
    PnlFormalFiRow,
    PnlMaterializePayload,
    PnlNonStdBridgeRow,
    PnlOverviewPayload,
    PnlV1DataPayload,
    PnlV1DetailRow,
    PnlYearlyBusinessSummaryPayload,
    PnlYearlyBusinessSummaryRow,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage as build_formal_result_envelope_from_lineage_runtime,
)
from backend.app.services.pnl_bond_bucket_merge import attach_bond_bucket_merged_rows
from backend.app.services.pnl_by_business_adjustments import (
    PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
    active_pnl_by_business_manual_adjustments_for_period,
    load_pnl_by_business_manual_adjustment_events,
    pnl_by_business_manual_adjustment_row,
    pnl_by_business_manual_adjustment_source_version,
    reduce_latest_pnl_by_business_manual_adjustments,
)
from backend.app.services.pnl_by_business_summary import build_pnl_by_business_summary
from backend.app.services.pnl_by_business_unallocated import (
    normalize_pnl_by_business_unallocated_item,
    pnl_by_business_unallocated_breakdown,
    pnl_by_business_unallocated_item,
    pnl_by_business_unallocated_reason,
)
from backend.app.services.pnl_source_service import (
    list_pnl_refresh_report_dates,
    load_latest_pnl_refresh_input,
    resolve_pnl_data_input_root,
)
from backend.app.services.pnl_task_dispatch import (
    CACHE_KEY,
    PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
    PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
    PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
    PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION,
    PNL_MATERIALIZE_LOCK,
    PNL_RESULT_CACHE_VERSION,
    materialize_pnl_facts,
    rebuild_pnl_by_business_precompute,
    run_pnl_materialize_sync,
)

logger = logging.getLogger(__name__)

PNL_CACHE_KEY = CACHE_KEY
PNL_CACHE_VERSION = PNL_RESULT_CACHE_VERSION
PNL_JOB_NAME = "pnl_materialize"
PENDING_SOURCE_VERSION = "sv_pnl_pending"
PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES = frozenset({"queued", "running"})
PNL_BY_BUSINESS_PRECOMPUTE_STALE_AFTER = timedelta(hours=2)
PNL_BY_BUSINESS_PRECOMPUTE_DISPATCH_LOCK = LockDefinition(
    key="lock:pnl:by-business:precompute-dispatch",
    ttl_seconds=30,
)
_REAL_PNL_REPOSITORY = PnlRepository
TWOPLACES = Decimal("0.01")
RATIOPLACES = Decimal("0.000001")
V1_INTEREST_INCOME_JOURNAL_TYPE = LEDGER_PNL_ACCOUNT_PREFIXES[0]
PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS: tuple[PnlByBusinessAnalysisDimension, ...] = (
    "bond_bucket",
    "bond_bucket_monthly",
)
PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS: tuple[PnlByBusinessAnalysisDimension, ...] = (
    "monthly",
    "portfolio",
    "accounting",
    "currency",
    "cost_center",
    "instrument",
)


class PnlByBusinessPrecomputeConflictError(RuntimeError):
    pass


class PnlByBusinessPrecomputeDispatchError(RuntimeError):
    pass


def _ensure_formal_pnl_storage_available(duckdb_path: str) -> None:
    if PnlRepository is not _REAL_PNL_REPOSITORY:
        return
    if str(duckdb_path) == ":memory:":
        return
    if not Path(str(duckdb_path)).exists():
        raise RuntimeError("Formal pnl storage is unavailable.")


ANALYSIS_BOND_BUCKETS: tuple[tuple[str, str, frozenset[str]], ...] = (
    (
        "rate_bond",
        "利率债",
        frozenset(
            {
                "asset_zqtz_central_bank_bill",
                "asset_zqtz_treasury_bond",
                "asset_zqtz_local_government_bond",
                "asset_zqtz_policy_financial_bond",
                "asset_zqtz_railway_bond",
            }
        ),
    ),
    (
        "credit_bond",
        "信用债",
        frozenset({"asset_zqtz_nonfinancial_enterprise_bond", "asset_zqtz_abs"}),
    ),
    (
        "financial_bond",
        "金融债",
        frozenset({"asset_zqtz_commercial_financial_bond", "asset_zqtz_interbank_cd"}),
    ),
    (
        "other_bond",
        "其它债券",
        frozenset(
            {
                "asset_zqtz_foreign_bond",
                "asset_zqtz_public_fund",
                "asset_zqtz_non_bottom_investment",
                "asset_zqtz_detail_trust_plan",
                "asset_zqtz_detail_securities_asset_management_plan",
                "asset_zqtz_detail_structured_finance_broker",
                "asset_zqtz_detail_foreign_currency_delegated",
                "asset_zqtz_detail_local_currency_delegated_market_value",
                "asset_zqtz_detail_local_currency_special_account_cost",
                "asset_zqtz_other_debt_financing",
            }
        ),
    ),
)
ANALYSIS_BOND_BUCKET_SORT = {key: index for index, (key, _label, _row_keys) in enumerate(ANALYSIS_BOND_BUCKETS)}
ANALYSIS_BOND_BUCKET_LABELS = {key: label for key, label, _row_keys in ANALYSIS_BOND_BUCKETS}
IN_FLIGHT_STATUSES = {"queued", "running"}
STALE_IN_FLIGHT_AFTER = timedelta(hours=1)
SAFE_SYNC_FALLBACK_MESSAGES = ("queue disabled", "broker unavailable")
SAFE_SYNC_FALLBACK_EXCEPTIONS = (ConnectionError, OSError, TimeoutError)
V1_VAT_DIVISOR = FI_514_VAT_DIVISOR
V1_ZQTZ_PREFIX_MAP = {
    "SA": "公募基金",
    "J0": "人民币资管产品",
    "J1": "美元委外产品",
    "J4": "结构化产业基金",
    "JM": "债权投资",
    "G0": "信托结构化产品",
    "G2": "信托产品",
}
V1_BUSINESS_NAME_NORMALIZATION = {
    "存单": "同业存单",
    "次级债": "次级债券",
    "美元委外": "美元委外产品",
    "结构化融资": "信托结构化产品",
    "结构化产品": "结构化产业基金",
    "债券-其他": "其他债券",
    "未分类": "其他债券",
    "大额存单": "同业存单",
    "凭证式国债": "国债",
}


class PnlRefreshServiceError(RuntimeError):
    pass


class PnlRefreshConflictError(RuntimeError):
    pass


def refresh_pnl(
    settings: Settings,
    *,
    report_date: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    _clear_pnl_by_business_analysis_cache()
    refresh_input = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path,
        data_root=resolve_pnl_data_input_root(),
        report_date=report_date,
    )
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    try:
        with acquire_lock(
            _refresh_trigger_lock(report_date=refresh_input.report_date),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
            if normalized_idempotency_key is not None:
                existing_idempotent_run = _latest_refresh_for_idempotency_key(
                    settings,
                    report_date=refresh_input.report_date,
                    idempotency_key=normalized_idempotency_key,
                )
                if existing_idempotent_run is not None:
                    return _idempotent_refresh_response(existing_idempotent_run)

            existing = _latest_inflight_refresh(
                settings,
                report_date=refresh_input.report_date,
            )
            if existing is not None:
                raise PnlRefreshConflictError(
                    f"Pnl refresh already in progress for report_date={refresh_input.report_date}."
                )

            run_id = _build_run_id()
            queued_at = datetime.now(UTC).isoformat()
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
                    "idempotency_key": normalized_idempotency_key,
                },
            )

            actor_kwargs = {
                "report_date": refresh_input.report_date,
                "is_month_end": refresh_input.is_month_end,
                "fi_rows": _json_safe_payload(refresh_input.fi_rows),
                "nonstd_rows_by_type": _json_safe_payload(refresh_input.nonstd_rows_by_type),
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
                    "idempotency_key": normalized_idempotency_key,
                    "idempotency_replay": False,
                }
            except Exception as exc:
                if _should_use_sync_fallback(settings, exc):
                    try:
                        payload = PnlMaterializePayload.model_validate(
                            run_pnl_materialize_sync(**actor_kwargs)
                        )
                    except Exception as fallback_exc:
                        raise PnlRefreshServiceError(
                            "Pnl refresh failed during sync fallback."
                        ) from fallback_exc
                    return {
                        **payload.model_dump(mode="json"),
                        "job_name": PNL_JOB_NAME,
                        "trigger_mode": "sync-fallback",
                        "idempotency_key": normalized_idempotency_key,
                        "idempotency_replay": False,
                    }

                _record_dispatch_failure(
                    settings=settings,
                    run_id=run_id,
                    report_date=refresh_input.report_date,
                    exc=exc,
                )
                raise PnlRefreshServiceError(_dispatch_failure_message(exc)) from exc
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
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    formal_fi_report_dates = repo.list_formal_fi_report_dates()
    nonstd_bridge_report_dates = repo.list_nonstd_bridge_report_dates()
    payload = PnlDatesPayload(
        report_dates=repo.list_union_report_dates(),
        formal_fi_report_dates=formal_fi_report_dates,
        nonstd_bridge_report_dates=nonstd_bridge_report_dates,
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=None,
        trace_id="tr_pnl_dates",
        result_kind="pnl.dates",
        result_payload=payload.model_dump(mode="json"),
    )


def pnl_data_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
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
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
        trace_id=f"tr_pnl_data_{report_date}",
        result_kind="pnl.data",
        result_payload=payload.model_dump(mode="json"),
    )


def pnl_overview_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    if report_date not in repo.list_union_report_dates():
        raise ValueError(
            f"No pnl data found for report_date={report_date} in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
        )

    totals = repo.overview_totals(report_date)
    reconciliation = _pnl_overview_reconciliation_check(totals)
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
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
        trace_id=f"tr_pnl_overview_{report_date}",
        result_kind="pnl.overview",
        result_payload=payload.model_dump(mode="json"),
        quality_flag="warning" if reconciliation["breached"] else None,
    )


def pnl_v1_data_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    source_root = resolve_pnl_data_input_root()
    refresh_input = load_latest_pnl_refresh_input(
        governance_dir=governance_dir,
        data_root=source_root,
        report_date=report_date,
    )
    target_report_date = str(refresh_input.report_date)

    sub_type_dates = {target_report_date}
    for rows in refresh_input.nonstd_rows_by_type.values():
        sub_type_dates.update(str(row.get("voucher_date") or "").strip() for row in rows if row.get("voucher_date"))
    sub_type_map = repo.fetch_zqtz_sub_type_map(sorted(sub_type_dates))

    base_currencies = {
        str(row.get("fx_base_currency") or "").strip().upper()
        for row in refresh_input.fi_rows
        if str(row.get("fx_base_currency") or "").strip()
    }
    if any(
        str(row.get("asset_code") or "").strip().upper().startswith("J1")
        for rows in refresh_input.nonstd_rows_by_type.values()
        for row in rows
    ):
        base_currencies.add("USD")
    fx_rates = repo.fetch_formal_fx_rates(target_report_date, base_currencies)
    missing_fx = sorted(currency for currency in base_currencies if currency not in fx_rates)
    if missing_fx:
        raise RuntimeError(f"Missing fx rates for report_date={target_report_date}: {missing_fx}")

    payload = PnlV1DataPayload(
        report_date=target_report_date,
        source_tables=[
            "data_input/pnl",
            "data_input/pnl_514",
            "data_input/pnl_516",
            "data_input/pnl_517",
            "fact_formal_zqtz_balance_daily",
            "fx_daily_mid",
        ],
        rows=_build_v1_detail_rows(
            report_date=target_report_date,
            refresh_input=refresh_input,
            sub_type_map=sub_type_map,
            fx_rates=fx_rates,
        ),
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=target_report_date,
        trace_id=f"tr_pnl_v1_data_{target_report_date}",
        result_kind="pnl.v1_data",
        result_payload=payload.model_dump(mode="json"),
    )


def pnl_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    repo.require_current_formal_pnl_rule_version(
        year=int(report_date[:4]),
        as_of_date=report_date,
    )
    if report_date not in repo.list_formal_fi_report_dates():
        raise ValueError(f"No formal pnl data found for report_date={report_date} in fact_formal_pnl_fi.")

    rows = [PnlByBusinessRow(**_quantized_business_row(row)) for row in repo.fetch_by_business_rows(report_date)]
    untraced_count = repo.count_untraced_formal_fi_rows(report_date)
    untraced_breakdown = [
        PnlByBusinessUntracedBreakdownRow(
            reason_code=str(row["reason_code"]),
            invest_type_std=str(row["invest_type_std"]),
            pnl_row_count=int(row["pnl_row_count"]),
            total_pnl=_quantize_decimal(Decimal(str(row["total_pnl"] or "0"))),
            abs_pnl=_quantize_decimal(Decimal(str(row["abs_pnl"] or "0"))),
            interest_income_514=_quantize_decimal(Decimal(str(row["interest_income_514"] or "0"))),
            fair_value_change_516=_quantize_decimal(Decimal(str(row["fair_value_change_516"] or "0"))),
            capital_gain_517=_quantize_decimal(Decimal(str(row["capital_gain_517"] or "0"))),
            manual_adjustment=_quantize_decimal(Decimal(str(row["manual_adjustment"] or "0"))),
        )
        for row in repo.fetch_untraced_formal_fi_breakdown(report_date)
    ]
    payload = PnlByBusinessPayload(
        report_date=report_date,
        source_tables=["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily"],
        summary=build_pnl_by_business_summary(
            rows=rows,
            untraced_pnl_row_count=untraced_count,
            untraced_breakdown=untraced_breakdown,
        ),
        rows=rows,
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
        trace_id=f"tr_pnl_by_business_{report_date}",
        result_kind="pnl.by_business",
        result_payload=payload.model_dump(mode="json"),
        quality_flag="warning" if untraced_count else None,
    )


def _pnl_by_business_ytd_unallocated_reason(
    matched_rows: list[dict[str, object]],
) -> str:
    return pnl_by_business_unallocated_reason(matched_rows)


def _pnl_by_business_ytd_unallocated_item(
    *,
    record: dict[str, object],
    classification: dict[str, object],
    reason_code: str,
    default_source_kind: str,
) -> PnlByBusinessYtdUnallocatedItem:
    return pnl_by_business_unallocated_item(
        record=record,
        classification=classification,
        reason_code=reason_code,
        default_source_kind=default_source_kind,
    )


def _normalize_pnl_by_business_unallocated_item(
    item: PnlByBusinessYtdUnallocatedItem,
) -> PnlByBusinessYtdUnallocatedItem:
    return normalize_pnl_by_business_unallocated_item(item)


def _pnl_by_business_ytd_unallocated_breakdown(
    items: list[PnlByBusinessYtdUnallocatedItem],
) -> list[PnlByBusinessYtdUnallocatedBreakdownRow]:
    return pnl_by_business_unallocated_breakdown(items)


def _build_pnl_by_business_ytd_payload_from_groups(
    *,
    year: int,
    loaded_dates: list[str],
    total_pnl: Decimal,
    groups: dict[str, dict[str, object]],
    duckdb_path: str,
    source_tables: list[str],
    ftp_rate_pct: Decimal,
    balance_rows: list[dict[str, object]] | None = None,
    unallocated_items: list[PnlByBusinessYtdUnallocatedItem | dict[str, object]] | None = None,
) -> PnlByBusinessYtdPayload:
    ytd_balance_rows = balance_rows
    if ytd_balance_rows is None:
        ytd_balance_rows = AccountingAssetMovementRepository(duckdb_path).fetch_zqtz_asset_business_rows(
            report_date=max(loaded_dates),
            currency_basis="CNX",
        )
        current_balance_rows = ytd_balance_rows
        balance_by_key = {str(row["row_key"]): row for row in current_balance_rows}
    else:
        balance_by_key = _ytd_business_balance_rows_by_key(ytd_balance_rows, period_end=max(loaded_dates))
    avg_balance_by_key, current_balance_by_key = _ytd_business_balance_amounts(
        ytd_balance_rows,
        period_end=max(loaded_dates),
    )
    calendar_days = _calendar_days(f"{min(loaded_dates)[:7]}-01", max(loaded_dates))
    items = [
        _ytd_business_item_from_group(
            group=group,
            total_pnl_for_proportion=total_pnl,
            balance_row=balance_by_key.get(str(group["row_key"]), {}),
            avg_balance=avg_balance_by_key.get(str(group["row_key"]), Decimal("0")),
            current_balance=current_balance_by_key.get(
                str(group["row_key"]),
                Decimal(str(balance_by_key.get(str(group["row_key"]), {}).get("current_balance") or "0")),
            ),
            calendar_days=calendar_days,
            ftp_rate_pct=ftp_rate_pct,
        )
        for group in sorted(groups.values(), key=lambda item: (int(item["sort_order"]), str(item["row_key"])))
    ]
    start_month = min(loaded_dates)[:7]
    end_month = max(loaded_dates)[:7]
    period_start_date = f"{start_month}-01"
    period_end_date = max(loaded_dates)
    coverage_days, expected_days, sample_filled, sample_fill_method = _balance_coverage_diagnostics(
        ytd_balance_rows,
        period_start=period_start_date,
        period_end=period_end_date,
    )
    precise_classified_parent_total_pnl = sum(
        (
            Decimal(str(group["total_pnl"]))
            for group in groups.values()
            if is_parent_zqtz_business_row(
                str(group["row_key"]),
                str(group["business_type"]),
                group.get("source_note"),
            )
        ),
        Decimal("0"),
    )
    source_total_pnl = _quantize_decimal(total_pnl)
    classified_parent_total_pnl = _quantize_decimal(precise_classified_parent_total_pnl)
    summary = _pnl_by_business_ytd_summary_from_items(
        items,
        groups=groups,
        source_total_pnl=total_pnl,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    precise_unallocated_items = [
        item
        if isinstance(item, PnlByBusinessYtdUnallocatedItem)
        else PnlByBusinessYtdUnallocatedItem.model_validate(item)
        for item in (unallocated_items or [])
    ]
    precise_unallocated_items = [
        item.model_copy(update={"abs_pnl": abs(item.total_pnl)}) for item in precise_unallocated_items
    ]
    precise_unallocated_items = sorted(
        precise_unallocated_items,
        key=lambda item: (
            -item.abs_pnl,
            item.report_date,
            item.source_kind,
            item.instrument_code,
            item.portfolio_name,
            item.cost_center,
        ),
    )
    normalized_unallocated_items = [
        _normalize_pnl_by_business_unallocated_item(item) for item in precise_unallocated_items
    ]
    unallocated_pnl = _quantize_decimal(
        sum((item.total_pnl for item in precise_unallocated_items), Decimal("0"))
    )
    unallocated_abs_pnl = _quantize_decimal(
        sum((item.abs_pnl for item in precise_unallocated_items), Decimal("0"))
    )
    precise_unallocated_pnl = sum((item.total_pnl for item in precise_unallocated_items), Decimal("0"))
    reconciliation_delta = total_pnl - precise_classified_parent_total_pnl - precise_unallocated_pnl
    return PnlByBusinessYtdPayload(
        year=year,
        period_label=f"{year}年{start_month[-2:]}-{end_month[-2:]}月累计" if start_month != end_month else f"{year}年{end_month[-2:]}月累计",
        period_start_date=period_start_date,
        period_end_date=period_end_date,
        total_pnl=source_total_pnl,
        coverage_days=coverage_days,
        expected_days=expected_days,
        sample_filled=sample_filled,
        sample_fill_method=sample_fill_method,
        classified_parent_total_pnl=classified_parent_total_pnl,
        summary=summary,
        unallocated_pnl=unallocated_pnl,
        unallocated_abs_pnl=unallocated_abs_pnl,
        unallocated_row_count=len(normalized_unallocated_items),
        reconciliation_delta=_quantize_decimal(reconciliation_delta),
        unallocated_breakdown=_pnl_by_business_ytd_unallocated_breakdown(precise_unallocated_items),
        unallocated_items=normalized_unallocated_items,
        source_tables=source_tables,
        items=items,
    )


def _balance_coverage_diagnostics(
    balance_rows: list[dict[str, object]] | tuple[dict[str, object], ...],
    *,
    period_start: str,
    period_end: str,
) -> tuple[int, int, bool, str | None]:
    coverage_dates = {
        report_date
        for row in balance_rows
        if (report_date := _norm_text(row.get("report_date"))) and period_start <= report_date <= period_end
    }
    coverage_days = len(coverage_dates)
    expected_days = _calendar_days(period_start, period_end)
    sample_filled = 0 < coverage_days < expected_days
    sample_fill_method = "observed_days_scaled_to_calendar" if sample_filled else None
    return coverage_days, expected_days, sample_filled, sample_fill_method


def _ytd_business_item_from_group(
    *,
    group: dict[str, object],
    total_pnl_for_proportion: Decimal,
    balance_row: dict[str, object],
    avg_balance: Decimal,
    current_balance: Decimal,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> PnlByBusinessYtdItem:
    total_pnl = Decimal(str(group["total_pnl"]))
    yield_ftp = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    return PnlByBusinessYtdItem(
        row_key=str(group["row_key"]),
        sort_order=int(group["sort_order"]),
        business_type=str(group["business_type"]),
        interest_income=_quantize_decimal(Decimal(str(group["interest_income"]))),
        fair_value_change=_quantize_decimal(Decimal(str(group["fair_value_change"]))),
        capital_gain=_quantize_decimal(Decimal(str(group["capital_gain"]))),
        manual_adjustment=_quantize_decimal(Decimal(str(group.get("manual_adjustment") or "0"))),
        total_pnl=_quantize_decimal(total_pnl),
        avg_balance=_quantize_decimal(avg_balance),
        current_balance=_quantize_decimal(current_balance),
        balance_yield_pct=_balance_yield_pct(total_pnl, current_balance),
        annualized_yield_pct=yield_ftp.annualized_yield_pct,
        ftp_rate_pct=yield_ftp.ftp_rate_pct,
        ftp_cost=yield_ftp.ftp_cost,
        ftp_net_pnl=yield_ftp.ftp_net_pnl,
        ftp_net_annualized_yield_pct=yield_ftp.ftp_net_annualized_yield_pct,
        source_kind=str(balance_row.get("source_kind") or "zqtz"),
        source_note=str(balance_row.get("source_note") or group["source_note"]),
        proportion=(
            _quantize_ratio(total_pnl / total_pnl_for_proportion)
            if total_pnl_for_proportion != Decimal("0")
            else None
        ),
        assets_count=len(group["asset_codes"]) if group["asset_codes"] else int(group["row_count"]),
    )


def _pnl_by_business_ytd_summary_from_items(
    items: list[PnlByBusinessYtdItem],
    *,
    groups: dict[str, dict[str, object]],
    source_total_pnl: Decimal,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> PnlByBusinessYtdSummary:
    parent_items = [
        item
        for item in items
        if is_parent_zqtz_business_row(item.row_key, item.business_type, item.source_note)
    ]
    parent_groups = [
        group
        for group in groups.values()
        if is_parent_zqtz_business_row(
            str(group["row_key"]),
            str(group["business_type"]),
            group.get("source_note"),
        )
    ]
    interest_income = sum(
        (Decimal(str(group.get("interest_income") or "0")) for group in parent_groups),
        Decimal("0"),
    )
    fair_value_change = sum(
        (Decimal(str(group.get("fair_value_change") or "0")) for group in parent_groups),
        Decimal("0"),
    )
    capital_gain = sum(
        (Decimal(str(group.get("capital_gain") or "0")) for group in parent_groups),
        Decimal("0"),
    )
    manual_adjustment = sum(
        (Decimal(str(group.get("manual_adjustment") or "0")) for group in parent_groups),
        Decimal("0"),
    )
    total_pnl = sum(
        (Decimal(str(group.get("total_pnl") or "0")) for group in parent_groups),
        Decimal("0"),
    )
    avg_balance = sum((item.avg_balance for item in parent_items), Decimal("0"))
    current_balance = sum((item.current_balance for item in parent_items), Decimal("0"))
    yield_ftp = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    return PnlByBusinessYtdSummary(
        interest_income=_quantize_decimal(interest_income),
        fair_value_change=_quantize_decimal(fair_value_change),
        capital_gain=_quantize_decimal(capital_gain),
        manual_adjustment=_quantize_decimal(manual_adjustment),
        total_pnl=_quantize_decimal(total_pnl),
        avg_balance=_quantize_decimal(avg_balance),
        current_balance=_quantize_decimal(current_balance),
        annualized_yield_pct=yield_ftp.annualized_yield_pct,
        ftp_rate_pct=yield_ftp.ftp_rate_pct,
        ftp_cost=yield_ftp.ftp_cost,
        ftp_net_pnl=yield_ftp.ftp_net_pnl,
        ftp_net_annualized_yield_pct=yield_ftp.ftp_net_annualized_yield_pct,
        proportion=(
            _quantize_ratio(total_pnl / source_total_pnl)
            if source_total_pnl != Decimal("0")
            else None
        ),
        assets_count=sum(item.assets_count for item in parent_items),
    )


def _ytd_business_balance_rows_by_key(
    balance_rows: list[dict[str, object]],
    *,
    period_end: str,
) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for row in balance_rows:
        if _norm_text(row.get("report_date")) != period_end:
            continue
        classification = _analysis_classification_from_balance_row(row)
        for row_def in match_zqtz_asset_bond_rows(classification):
            row_key = str(row_def["row_key"])
            existing = out.setdefault(
                row_key,
                {
                    "row_key": row_key,
                    "current_balance": Decimal("0"),
                    "source_kind": "zqtz",
                    "source_note": str(row_def.get("source_note") or "ZQTZ_ASSET_BOND_ROWS"),
                },
            )
            existing["current_balance"] = Decimal(str(existing["current_balance"])) + _decimal_value(
                row.get("current_amount")
            )
    return out


def _ytd_business_balance_amounts(
    balance_rows: list[dict[str, object]],
    *,
    period_end: str,
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    avg_sums: dict[str, Decimal] = {}
    current_sums: dict[str, Decimal] = {}
    coverage_dates = {str(row.get("report_date")) for row in balance_rows if _norm_text(row.get("report_date"))}
    denom = Decimal(str(len(coverage_dates))) if coverage_dates else Decimal("0")
    for row in balance_rows:
        classification = _analysis_classification_from_balance_row(row)
        for row_def in match_zqtz_asset_bond_rows(classification):
            row_key = str(row_def["row_key"])
            avg_sums[row_key] = avg_sums.get(row_key, Decimal("0")) + _decimal_value(row.get("avg_amount"))
            if _norm_text(row.get("report_date")) == period_end:
                current_sums[row_key] = current_sums.get(row_key, Decimal("0")) + _decimal_value(
                    row.get("current_amount")
                )
    avg_by_key = {
        row_key: (value / denom if denom > Decimal("0") else Decimal("0"))
        for row_key, value in avg_sums.items()
    }
    return avg_by_key, current_sums


def _load_pnl_by_business_manual_adjustment_events(settings: Settings) -> list[dict[str, object]]:
    return load_pnl_by_business_manual_adjustment_events(settings.governance_path)


def _reduce_latest_pnl_by_business_manual_adjustments(events: list[dict[str, object]]) -> list[dict[str, object]]:
    return reduce_latest_pnl_by_business_manual_adjustments(events)


def _active_pnl_by_business_manual_adjustments(settings: Settings, *, report_date: str) -> list[dict[str, object]]:
    return [
        record
        for record in active_pnl_by_business_manual_adjustments_for_period(
            settings.governance_path,
            year=int(report_date[:4]),
            period_end=report_date,
        )
        if str(record.get("report_date") or "") == report_date
    ]


def _require_pnl_by_business_manual_adjustment(settings: Settings, adjustment_id: str) -> dict[str, object]:
    records = _reduce_latest_pnl_by_business_manual_adjustments(
        _load_pnl_by_business_manual_adjustment_events(settings)
    )
    for record in records:
        if str(record.get("adjustment_id") or "") == adjustment_id:
            return record
    raise ValueError(f"Unknown pnl-by-business adjustment_id={adjustment_id}")


def _pnl_by_business_adjustment_record(
    *,
    report_date: str,
    row_key: str,
    business_type: str,
    manual_adjustment: object,
    source_note: str,
) -> dict[str, object]:
    row = pnl_by_business_manual_adjustment_row(
        {
            "report_date": report_date,
            "row_key": row_key,
            "business_type": business_type,
            "manual_adjustment": manual_adjustment,
        }
    )
    row["source_note"] = source_note
    return row


def _manual_adjustment_row_def(record: dict[str, object]) -> dict[str, object]:
    row_key = str(record.get("manual_business_row_key") or record.get("row_key") or "").strip()
    for row_def in ZQTZ_ASSET_BOND_ROWS:
        if str(row_def.get("row_key") or "") == row_key:
            return row_def
    return {
        "row_key": row_key or "manual_unclassified",
        "sort_order": 999,
        "row_label": str(record.get("manual_business_type") or record.get("business_type") or row_key or "手工调整"),
        "source_note": str(record.get("source_note") or "pnl_by_business_adjustments"),
    }


def _pnl_by_business_manual_classification(record: dict[str, object]) -> dict[str, object]:
    row_def = _manual_adjustment_row_def(record)
    label = str(row_def.get("row_label") or record.get("manual_business_type") or "")
    return {
        "report_date": _norm_text(record.get("report_date")),
        "instrument_code": _norm_text(record.get("instrument_code")),
        "instrument_name": label,
        "account_category": "manual_adjustment",
        "asset_class": label,
        "bond_type": label,
        "sub_type": label,
        "business_type_primary": label,
        "business_type_final": label,
        "invest_type_std": "",
        "accounting_basis": "manual_adjustment",
        "currency_code": "CNY",
        "manual_business_row_key": str(row_def.get("row_key") or ""),
    }


def _apply_pnl_by_business_manual_adjustments_to_ytd_groups(
    *,
    settings: Settings,
    groups: dict[str, dict[str, object]],
    total_pnl: Decimal,
    loaded_dates: list[str],
    unallocated_items: list[PnlByBusinessYtdUnallocatedItem],
) -> Decimal:
    adjusted_total = total_pnl
    for report_date in loaded_dates:
        for adjustment in _active_pnl_by_business_manual_adjustments(settings, report_date=report_date):
            row_def = _manual_adjustment_row_def(adjustment)
            source_record = _pnl_by_business_adjustment_record(
                report_date=report_date,
                row_key=str(adjustment.get("row_key") or ""),
                business_type=str(adjustment.get("business_type") or ""),
                manual_adjustment=adjustment.get("manual_adjustment"),
                source_note=f"{PNL_BY_BUSINESS_ADJUSTMENT_STREAM}:{adjustment.get('adjustment_id')}",
            )
            record = {
                "bond_code": f"manual::{adjustment['adjustment_id']}",
                "interest_income": Decimal("0"),
                "fair_value_change": Decimal("0"),
                "capital_gain": Decimal("0"),
                "manual_adjustment": _decimal_value(adjustment.get("manual_adjustment")),
                "total_pnl": _decimal_value(adjustment.get("manual_adjustment")),
            }
            if not is_parent_zqtz_business_row(
                str(row_def["row_key"]),
                str(row_def["row_label"]),
                row_def.get("source_note"),
            ):
                unallocated_items.append(
                    _pnl_by_business_ytd_unallocated_item(
                        record=source_record,
                        classification=_pnl_by_business_manual_classification(source_record),
                        reason_code=_pnl_by_business_ytd_unallocated_reason([row_def]),
                        default_source_kind="manual_adjustment",
                    )
                )
            _merge_balance_movement_business_record(groups, row_def, record)
            adjusted_total += _decimal_value(adjustment.get("manual_adjustment"))
    return adjusted_total


def _append_pnl_by_business_manual_adjustments_to_rows(
    *,
    settings: Settings,
    pnl_rows: tuple[dict[str, object], ...],
    loaded_dates: list[str],
) -> tuple[dict[str, object], ...]:
    appended = list(pnl_rows)
    for report_date in loaded_dates:
        for adjustment in _active_pnl_by_business_manual_adjustments(settings, report_date=report_date):
            appended.append(
                _pnl_by_business_adjustment_record(
                    report_date=report_date,
                    row_key=str(adjustment.get("row_key") or ""),
                    business_type=str(adjustment.get("business_type") or ""),
                    manual_adjustment=adjustment.get("manual_adjustment"),
                    source_note=f"{PNL_BY_BUSINESS_ADJUSTMENT_STREAM}:{adjustment.get('adjustment_id')}",
                )
            )
    return tuple(appended)


def _source_tables_with_manual_adjustments(source_tables: list[str], *, settings: Settings, loaded_dates: list[str]) -> list[str]:
    for report_date in loaded_dates:
        if _active_pnl_by_business_manual_adjustments(settings, report_date=report_date):
            if PNL_BY_BUSINESS_ADJUSTMENT_STREAM not in source_tables:
                return [*source_tables, PNL_BY_BUSINESS_ADJUSTMENT_STREAM]
            return source_tables
    return source_tables


def _parse_created_at(value: str) -> datetime:
    raw_value = str(value or "").strip()
    if not raw_value:
        return datetime.min.replace(tzinfo=UTC)
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _pnl_by_business_ytd_payload_from_formal_facts(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> tuple[PnlByBusinessYtdPayload, str]:
    """计算正式事实 YTD 载荷；不依赖稍后才落盘的正式血缘清单。"""
    if not as_of_date.startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_of_date} is outside requested year={year}.")
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= as_of_date
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_of_date}.")

    resolved_report_date = max(loaded_dates)
    period_start = f"{min(loaded_dates)[:7]}-01"
    pnl_rows = repo.fetch_by_business_analysis_pnl_rows(year=year, as_of_date=resolved_report_date)
    balance_rows = repo.fetch_by_business_analysis_balance_rows(
        start_date=period_start,
        end_date=resolved_report_date,
    )

    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={as_of_date}.")

    balance_lookup = _analysis_balance_lookup(balance_rows)
    historical_balance_lookup = _analysis_historical_balance_lookup(balance_rows)
    sub_type_by_date_code = _analysis_sub_type_by_date_code(balance_rows)

    groups: dict[str, dict[str, object]] = {
        str(row_def["row_key"]): _new_balance_movement_pnl_group(row_def) for row_def in ZQTZ_ASSET_BOND_ROWS
    }
    total_pnl = Decimal("0")
    unallocated_items: list[PnlByBusinessYtdUnallocatedItem] = []

    for row in pnl_rows:
        classification = _analysis_classification_for_pnl_row(
            pnl_row=row,
            balance_lookup=balance_lookup,
            historical_balance_lookup=historical_balance_lookup,
            sub_type_by_date_code=sub_type_by_date_code,
            fallback_date=_norm_text(row.get("report_date")) or resolved_report_date,
        )
        interest = _decimal_value(row.get("interest_income_514"))
        fair = _decimal_value(row.get("fair_value_change_516"))
        capital = _decimal_value(row.get("capital_gain_517"))
        manual_adjustment = _decimal_value(row.get("manual_adjustment"))
        total = _decimal_value(row.get("total_pnl"))
        record = {
            "report_date": _norm_text(row.get("report_date")) or as_of_date,
            "bond_code": _norm_text(row.get("instrument_code")),
            "interest_income": interest,
            "fair_value_change": fair,
            "capital_gain": capital,
            "manual_adjustment": manual_adjustment,
            "total_pnl": total,
            "classification_row": classification,
        }
        total_pnl += total
        matched_rows = match_zqtz_asset_bond_rows(classification)
        if not any(
            is_parent_zqtz_business_row(
                str(row_def["row_key"]),
                str(row_def["row_label"]),
                row_def.get("source_note"),
            )
            for row_def in matched_rows
        ):
            unallocated_items.append(
                _pnl_by_business_ytd_unallocated_item(
                    record=row,
                    classification=classification,
                    reason_code=_pnl_by_business_ytd_unallocated_reason(matched_rows),
                    default_source_kind="formal_fact",
                )
            )
        for row_def in matched_rows:
            _merge_balance_movement_business_record(groups, row_def, record)

    settings = get_settings().model_copy(
        update={"governance_path": Path(governance_dir)}
    )
    ftp_rate_pct = resolve_product_category_ftp_rate_pct(date(year, 12, 31), settings.ftp_rate_pct)
    total_pnl = _apply_pnl_by_business_manual_adjustments_to_ytd_groups(
        settings=settings,
        groups=groups,
        total_pnl=total_pnl,
        loaded_dates=loaded_dates,
        unallocated_items=unallocated_items,
    )
    source_tables = _source_tables_with_manual_adjustments(
        [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
        ],
        settings=settings,
        loaded_dates=loaded_dates,
    )
    payload = _build_pnl_by_business_ytd_payload_from_groups(
        year=year,
        loaded_dates=loaded_dates,
        total_pnl=total_pnl,
        groups=groups,
        duckdb_path=duckdb_path,
        source_tables=source_tables,
        ftp_rate_pct=ftp_rate_pct,
        balance_rows=list(balance_rows),
        unallocated_items=unallocated_items,
    )
    return payload, resolved_report_date


def _pnl_by_business_ytd_from_formal_facts(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    """年度累计：复用权威载荷计算，并附加正式血缘与质量元数据。"""
    payload, resolved_report_date = _pnl_by_business_ytd_payload_from_formal_facts(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    quality_flag = _pnl_by_business_ytd_quality_flag(payload)
    return _build_pnl_by_business_analytical_result_envelope(
        governance_dir=governance_dir,
        requested_report_date=as_of_date,
        resolved_report_date=resolved_report_date,
        trace_id=f"tr_pnl_by_business_ytd_{year}_{as_of_date}",
        result_kind="pnl.by_business_ytd",
        result_payload=payload.model_dump(mode="json"),
        quality_flag=quality_flag,
        filters_applied={"year": year, "as_of_date": as_of_date},
    )


def _pnl_by_business_ytd_from_refresh_bundles(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """年度累计：刷新包 + ``_iter_v1_compatible_pnl_records``（与早期 V1 导入变换一致；无 formal 时回退）。"""
    repo = PnlRepository(duckdb_path)
    source_root = resolve_pnl_data_input_root()
    candidate_report_dates = list_pnl_refresh_report_dates(
        governance_dir=governance_dir,
        data_root=source_root,
    ) or repo.list_union_report_dates()
    report_dates = [date for date in candidate_report_dates if str(date).startswith(f"{year:04d}")]
    if not report_dates:
        raise ValueError(f"No V1-compatible pnl data found for year={year}.")
    if as_of_date:
        if not as_of_date.startswith(f"{year:04d}-"):
            raise ValueError(f"as_of_date={as_of_date} is outside requested year={year}.")
        report_dates = [date for date in report_dates if str(date) <= as_of_date]
        if not report_dates:
            raise ValueError(f"No V1-compatible pnl data found for year={year} as_of_date={as_of_date}.")

    refresh_inputs: list[tuple[str, object]] = []
    sub_type_dates = set(report_dates)
    groups: dict[str, dict[str, object]] = {
        str(row_def["row_key"]): _new_balance_movement_pnl_group(row_def) for row_def in ZQTZ_ASSET_BOND_ROWS
    }
    loaded_dates: list[str] = []
    total_pnl = Decimal("0")
    unallocated_items: list[PnlByBusinessYtdUnallocatedItem] = []

    for report_date in sorted(report_dates):
        refresh_input = load_latest_pnl_refresh_input(
            governance_dir=governance_dir,
            data_root=source_root,
            report_date=report_date,
        )
        refresh_inputs.append((report_date, refresh_input))
        loaded_dates.append(report_date)
        for rows in refresh_input.nonstd_rows_by_type.values():
            sub_type_dates.update(str(row.get("voucher_date") or "").strip() for row in rows if row.get("voucher_date"))

    sub_type_map = repo.fetch_zqtz_sub_type_map(sorted(sub_type_dates))

    for report_date, refresh_input in refresh_inputs:
        base_currencies = {
            str(row.get("fx_base_currency") or "").strip().upper()
            for row in refresh_input.fi_rows
            if str(row.get("fx_base_currency") or "").strip()
        }
        if any(str(row.get("asset_code") or "").strip().upper().startswith("J1") for rows in refresh_input.nonstd_rows_by_type.values() for row in rows):
            base_currencies.add("USD")
        fx_rates = repo.fetch_formal_fx_rates(report_date, base_currencies)
        missing_fx = sorted(currency for currency in base_currencies if currency not in fx_rates)
        if missing_fx:
            raise RuntimeError(f"Missing fx rates for report_date={report_date}: {missing_fx}")

        for record in _iter_v1_compatible_pnl_records(
            report_date=report_date,
            refresh_input=refresh_input,
            sub_type_map=sub_type_map,
            fx_rates=fx_rates,
        ):
            record_total = Decimal(str(record["total_pnl"]))
            total_pnl += record_total
            matched_rows = match_zqtz_asset_bond_rows(record.get("classification_row", {}))
            if not any(
                is_parent_zqtz_business_row(
                    str(row_def["row_key"]),
                    str(row_def["row_label"]),
                    row_def.get("source_note"),
                )
                for row_def in matched_rows
            ):
                unallocated_items.append(
                    _pnl_by_business_ytd_unallocated_item(
                        record=record,
                        classification=dict(record.get("classification_row") or {}),
                        reason_code=_pnl_by_business_ytd_unallocated_reason(matched_rows),
                        default_source_kind="refresh_bundle",
                    )
                )
            for row_def in matched_rows:
                _merge_balance_movement_business_record(groups, row_def, record)

    if not loaded_dates:
        raise ValueError(f"No V1-compatible pnl source bundle found for year={year}.")

    period_start = f"{min(loaded_dates)[:7]}-01"
    balance_rows = repo.fetch_by_business_analysis_balance_rows(
        start_date=period_start,
        end_date=max(loaded_dates),
    )
    settings = get_settings()
    ftp_rate_pct = resolve_product_category_ftp_rate_pct(date(year, 12, 31), settings.ftp_rate_pct)
    total_pnl = _apply_pnl_by_business_manual_adjustments_to_ytd_groups(
        settings=settings,
        groups=groups,
        total_pnl=total_pnl,
        loaded_dates=loaded_dates,
        unallocated_items=unallocated_items,
    )
    source_tables = _source_tables_with_manual_adjustments(
        [
            "data_input/pnl",
            "data_input/pnl_514",
            "data_input/pnl_516",
            "data_input/pnl_517",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
            "fx_daily_mid",
        ],
        settings=settings,
        loaded_dates=loaded_dates,
    )
    payload = _build_pnl_by_business_ytd_payload_from_groups(
        year=year,
        loaded_dates=loaded_dates,
        total_pnl=total_pnl,
        groups=groups,
        duckdb_path=duckdb_path,
        source_tables=source_tables,
        ftp_rate_pct=ftp_rate_pct,
        balance_rows=balance_rows,
        unallocated_items=unallocated_items,
    )
    quality_flag = _pnl_by_business_ytd_quality_flag(payload)
    return _build_pnl_by_business_analytical_result_envelope(
        governance_dir=governance_dir,
        requested_report_date=as_of_date,
        resolved_report_date=max(loaded_dates),
        trace_id=f"tr_pnl_by_business_ytd_{year}" if not as_of_date else f"tr_pnl_by_business_ytd_{year}_{as_of_date}",
        result_kind="pnl.by_business_ytd",
        result_payload=payload.model_dump(mode="json"),
        quality_flag=quality_flag,
        filters_applied={"year": year, "as_of_date": as_of_date},
    )


def pnl_by_business_ytd_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    return _pnl_by_business_ytd_envelope_uncached(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        year=int(year),
        as_of_date=as_of_date,
    )


def clear_pnl_by_business_ytd_cache() -> None:
    """Compatibility hook; YTD freshness is now verified against durable precompute on every read."""


def create_pnl_by_business_manual_adjustment(
    settings: Settings,
    payload: PnlByBusinessManualAdjustmentRequest,
    *,
    created_by: str = "",
) -> dict[str, object]:
    created_at = datetime.now(UTC).isoformat()
    payload_data = payload.model_dump()
    payload_data["approval_status"] = "pending"
    record = PnlByBusinessManualAdjustmentPayload(
        adjustment_id=f"pba-{uuid4()}",
        event_type="created",
        created_at=created_at,
        stream=PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        **payload_data,
        created_by=str(created_by or ""),
        approved_by="",
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        record.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    return record.model_dump(mode="json")


def update_pnl_by_business_manual_adjustment(
    settings: Settings,
    *,
    adjustment_id: str,
    payload: PnlByBusinessManualAdjustmentRequest,
) -> dict[str, object]:
    current = _require_pnl_by_business_manual_adjustment(settings, adjustment_id)
    approved_report_date = (
        str(current.get("report_date") or "")
        if str(current.get("approval_status") or "") == "approved"
        else ""
    )
    payload_data = payload.model_dump()
    updated = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            **payload_data,
            "event_type": "edited",
            "created_at": datetime.now(UTC).isoformat(),
            "approval_status": "pending",
            "approved_by": "",
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        updated.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    if approved_report_date:
        _enqueue_pnl_by_business_precompute_refresh(settings, report_date=approved_report_date)
    return updated.model_dump(mode="json")


def _require_available_pnl_by_business_adjustment_cutoff(
    settings: Settings,
    *,
    report_date: str,
) -> None:
    try:
        parsed = date.fromisoformat(str(report_date))
    except ValueError as exc:
        raise ValueError("report_date must be a real calendar date in YYYY-MM-DD format") from exc
    available_cutoffs = _available_pnl_by_business_precompute_cutoffs(
        PnlRepository(str(settings.duckdb_path)),
        year=parsed.year,
    )
    if parsed.isoformat() not in available_cutoffs:
        raise ValueError(
            f"report_date={parsed.isoformat()} is not an available month-end cutoff."
        )


def approve_pnl_by_business_manual_adjustment(
    settings: Settings,
    *,
    adjustment_id: str,
    approved_by: str,
) -> dict[str, object]:
    current = _require_pnl_by_business_manual_adjustment(settings, adjustment_id)
    checker = str(approved_by or "").strip()
    maker = str(current.get("created_by") or "").strip()
    if not maker:
        raise PermissionError(
            "PnL by-business adjustment is missing created_by; cannot verify maker-checker separation."
        )
    if not checker:
        raise PermissionError("Approver identity is required to approve a PnL by-business adjustment.")
    if maker == checker:
        raise PermissionError("PnL by-business adjustment creator cannot approve the same adjustment.")
    if str(current.get("approval_status") or "") == "approved":
        return PnlByBusinessManualAdjustmentPayload.model_validate(current).model_dump(mode="json")
    _require_available_pnl_by_business_adjustment_cutoff(
        settings,
        report_date=str(current.get("report_date") or ""),
    )
    approved = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "approved",
            "created_at": datetime.now(UTC).isoformat(),
            "approval_status": "approved",
            "approved_by": checker,
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        approved.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    _enqueue_pnl_by_business_precompute_refresh(
        settings,
        report_date=str(approved.report_date),
    )
    return approved.model_dump(mode="json")


def revoke_pnl_by_business_manual_adjustment(settings: Settings, *, adjustment_id: str) -> dict[str, object]:
    current = _require_pnl_by_business_manual_adjustment(settings, adjustment_id)
    if str(current.get("approval_status") or "") == "rejected":
        return PnlByBusinessManualAdjustmentPayload.model_validate(current).model_dump(mode="json")
    approved_report_date = (
        str(current.get("report_date") or "")
        if str(current.get("approval_status") or "") == "approved"
        else ""
    )
    revoked = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "revoked",
            "created_at": datetime.now(UTC).isoformat(),
            "approval_status": "rejected",
            "approved_by": "",
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        revoked.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    if approved_report_date:
        _enqueue_pnl_by_business_precompute_refresh(settings, report_date=approved_report_date)
    return revoked.model_dump(mode="json")


def restore_pnl_by_business_manual_adjustment(settings: Settings, *, adjustment_id: str) -> dict[str, object]:
    current = _require_pnl_by_business_manual_adjustment(settings, adjustment_id)
    if str(current.get("approval_status") or "") in {"approved", "pending"}:
        return PnlByBusinessManualAdjustmentPayload.model_validate(current).model_dump(mode="json")
    restored = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "restored",
            "created_at": datetime.now(UTC).isoformat(),
            "approval_status": "pending",
            "approved_by": "",
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        restored.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    return restored.model_dump(mode="json")


def list_pnl_by_business_manual_adjustments(settings: Settings, *, report_date: str) -> dict[str, object]:
    events = [
        PnlByBusinessManualAdjustmentPayload.model_validate(record)
        for record in _load_pnl_by_business_manual_adjustment_events(settings)
        if str(record.get("report_date") or "") == report_date
    ]
    adjustments = [
        PnlByBusinessManualAdjustmentPayload.model_validate(record)
        for record in _reduce_latest_pnl_by_business_manual_adjustments([event.model_dump(mode="json") for event in events])
    ]
    adjustments = sorted(adjustments, key=lambda item: _parse_created_at(item.created_at), reverse=True)
    events = sorted(events, key=lambda item: _parse_created_at(item.created_at), reverse=True)
    return PnlByBusinessManualAdjustmentListPayload(
        report_date=report_date,
        adjustment_count=len(adjustments),
        event_total=len(events),
        adjustments=adjustments,
        events=events,
    ).model_dump(mode="json")


def _pnl_by_business_ytd_envelope_uncached(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """业务种类「年度累计」：默认用 formal 事实表按日汇总至 ``as_of`` 再拆 ZQTZ；无 formal 或配置关闭时回退刷新包路径。

    - **formal 路径**（默认）：``fact_formal_pnl_fi`` + ``fact_nonstd_pnl_bridge`` 在 ``year`` 年内且 ``<= as_of`` 的金额按持仓汇总，
      与物化口径一致；``result["total_pnl"]`` 为各持仓 ``total_pnl`` 之和（每条持仓只计一次）。
    - **刷新包路径**（``MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS=false`` 或当年无 formal 行）：对每个 ``report_date`` 调 ``load_latest_pnl_refresh_input`` + ``_iter_v1_compatible_pnl_records``。
    - ``items``：ZQTZ 多桶命中时各行 ``total_pnl`` 可重叠，**行加总不必等于** ``result["total_pnl"]``。
    """
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    settings = get_settings()
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    prefer_fact_path = (
        settings.pnl_by_business_ytd_prefer_formal_facts
        and bool(as_cap)
        and str(as_cap).startswith(f"{year:04d}-")
        and repo.formal_pnl_ytd_has_rows(year=year, as_of_date=str(as_cap))
    )
    if prefer_fact_path:
        period_end = repo.max_formal_or_nonstd_report_date_in_year(
            year=year,
            as_of_cap=str(as_cap),
        )
        if period_end is None:
            raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
        repo.require_current_formal_pnl_rule_version(
            year=year,
            as_of_date=period_end,
        )
        effective_ftp_rate_pct = resolve_product_category_ftp_rate_pct(date(year, 12, 31), settings.ftp_rate_pct)
        precomputed = _fetch_pnl_by_business_precompute(
            repo, governance_dir=governance_dir, year=year, as_of_date=period_end, result_kind="ytd", dimension="", business_key="", effective_ftp_rate_pct=effective_ftp_rate_pct
        )
        if (
            precomputed is not None
            and _pnl_by_business_precompute_has_required_diagnostics(precomputed, result_kind="ytd")
        ):
            payload = PnlByBusinessYtdPayload.model_validate(precomputed)
            return _build_pnl_by_business_analytical_result_envelope(
                governance_dir=governance_dir,
                requested_report_date=as_of_date,
                resolved_report_date=period_end,
                trace_id=f"tr_pnl_by_business_ytd_{year}_{period_end}_precomputed",
                result_kind="pnl.by_business_ytd",
                result_payload=payload.model_dump(mode="json"),
                quality_flag=_pnl_by_business_ytd_quality_flag(payload),
                filters_applied={"year": year, "as_of_date": as_of_date},
            )
        return _pnl_by_business_ytd_from_formal_facts(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=year,
            as_of_date=str(as_cap),
        )
    return _pnl_by_business_ytd_from_refresh_bundles(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )


def _fetch_pnl_by_business_precompute(
    repo: PnlRepository, *, governance_dir: str, year: int, as_of_date: str, result_kind: str, dimension: str, business_key: str, effective_ftp_rate_pct: Decimal
) -> dict[str, object] | None:
    fetcher = getattr(repo, "fetch_pnl_by_business_precompute", None)
    if not callable(fetcher):
        return None
    active_adjustments = active_pnl_by_business_manual_adjustments_for_period(
        governance_dir,
        year=year,
        period_end=as_of_date,
    )
    return fetcher(
        year=year,
        as_of_date=as_of_date,
        result_kind=result_kind,
        dimension=dimension,
        business_key=business_key,
        effective_ftp_rate_pct=effective_ftp_rate_pct,
        expected_rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        supplemental_source_version=pnl_by_business_manual_adjustment_source_version(active_adjustments),
    )


def _pnl_by_business_precompute_has_required_diagnostics(
    payload: dict[str, object],
    *,
    result_kind: str,
) -> bool:
    coverage_fields = {
        "coverage_days",
        "expected_days",
        "sample_filled",
        "sample_fill_method",
    }
    if result_kind == "analysis":
        return coverage_fields.issubset(payload)
    if result_kind == "monthly":
        monthly_fields = coverage_fields | {
            "source_total_pnl",
            "classified_parent_total_pnl",
            "unallocated_pnl",
            "unallocated_abs_pnl",
            "unallocated_row_count",
            "reconciliation_delta",
            "unallocated_breakdown",
            "unallocated_items",
            "unallocated_evidence_complete",
        }
        months = payload.get("months")
        return isinstance(months, list) and bool(months) and all(
            isinstance(month, dict)
            and monthly_fields.issubset(month)
            and month.get("unallocated_evidence_complete") is True
            for month in months
        )
    if result_kind == "ytd":
        ytd_fields = coverage_fields | {
            "total_pnl",
            "classified_parent_total_pnl",
            "unallocated_pnl",
            "unallocated_abs_pnl",
            "unallocated_row_count",
            "reconciliation_delta",
            "unallocated_breakdown",
            "unallocated_items",
            "summary",
            "items",
        }
        return ytd_fields.issubset(payload)
    return False


def pnl_by_business_analysis_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
    business_key: str | None = None,
    dimension: PnlByBusinessAnalysisDimension = "monthly",
) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    if not as_cap:
        raise ValueError(f"No formal pnl rows found for year={year}.")
    if not str(as_cap).startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_cap} is outside requested year={year}.")

    period_end = repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=str(as_cap))
    if period_end is None:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    repo.require_current_formal_pnl_rule_version(year=year, as_of_date=period_end)
    settings = get_settings()
    ftp_rate_pct = resolve_product_category_ftp_rate_pct(date(year, 12, 31), settings.ftp_rate_pct)
    precomputed = _fetch_pnl_by_business_precompute(
        repo, governance_dir=governance_dir, year=year, as_of_date=period_end, result_kind="analysis", dimension=dimension, business_key=str(business_key or "").strip(), effective_ftp_rate_pct=ftp_rate_pct
    )
    if (
        precomputed is not None
        and _pnl_by_business_precompute_has_required_diagnostics(precomputed, result_kind="analysis")
    ):
        payload = attach_bond_bucket_merged_rows(PnlByBusinessAnalysisPayload.model_validate(precomputed))
        return _build_pnl_by_business_analytical_result_envelope(
            governance_dir=governance_dir,
            requested_report_date=as_of_date,
            resolved_report_date=period_end,
            trace_id=f"tr_pnl_by_business_analysis_{year}_{period_end}_{dimension}_precomputed",
            result_kind="pnl.by_business_analysis",
            result_payload=payload.model_dump(mode="json"),
            quality_flag=_coverage_quality_flag(payload.coverage_days, payload.expected_days),
            filters_applied={
                "year": year,
                "as_of_date": as_of_date,
                "business_key": business_key,
                "dimension": dimension,
            },
        )
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= period_end
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    loaded_date_list = list(loaded_dates)

    period_start = f"{min(loaded_dates)[:7]}-01"
    pnl_rows, balance_rows = _cached_pnl_by_business_analysis_inputs(
        duckdb_path,
        year,
        period_start,
        period_end,
    )
    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={period_end}.")

    pnl_rows = _append_pnl_by_business_manual_adjustments_to_rows(
        settings=settings,
        pnl_rows=tuple(pnl_rows),
        loaded_dates=loaded_date_list,
    )
    source_tables = _source_tables_with_manual_adjustments(
        [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
        ],
        settings=settings,
        loaded_dates=loaded_date_list,
    )
    coverage_days, expected_days, sample_filled, sample_fill_method = _balance_coverage_diagnostics(
        balance_rows,
        period_start=period_start,
        period_end=period_end,
    )
    payload = PnlByBusinessAnalysisPayload(
        year=year,
        as_of_date=period_end,
        business_key=str(business_key).strip() if business_key else None,
        dimension=dimension,
        period_start_date=period_start,
        period_end_date=period_end,
        coverage_days=coverage_days,
        expected_days=expected_days,
        sample_filled=sample_filled,
        sample_fill_method=sample_fill_method,
        source_tables=source_tables,
        rows=_build_pnl_by_business_analysis_rows(
            pnl_rows=list(pnl_rows),
            balance_rows=balance_rows,
            loaded_dates=loaded_date_list,
            period_start=period_start,
            period_end=period_end,
            business_key=str(business_key).strip() if business_key else None,
            dimension=dimension,
            ftp_rate_pct=ftp_rate_pct,
        ),
    )
    payload = attach_bond_bucket_merged_rows(payload)
    return _build_pnl_by_business_analytical_result_envelope(
        governance_dir=governance_dir,
        requested_report_date=as_of_date,
        resolved_report_date=period_end,
        trace_id=f"tr_pnl_by_business_analysis_{year}_{period_end}_{dimension}",
        result_kind="pnl.by_business_analysis",
        result_payload=payload.model_dump(mode="json"),
        quality_flag=_coverage_quality_flag(coverage_days, expected_days),
        filters_applied={
            "year": year,
            "as_of_date": as_of_date,
            "business_key": business_key,
            "dimension": dimension,
        },
    )


def pnl_by_business_monthly_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    if not as_cap:
        raise ValueError(f"No formal pnl rows found for year={year}.")
    if not str(as_cap).startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_cap} is outside requested year={year}.")

    period_end = repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=str(as_cap))
    if period_end is None:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    repo.require_current_formal_pnl_rule_version(year=year, as_of_date=period_end)
    settings = get_settings()
    ftp_rate_pct = resolve_product_category_ftp_rate_pct(date(year, 12, 31), settings.ftp_rate_pct)
    precomputed = _fetch_pnl_by_business_precompute(
        repo, governance_dir=governance_dir, year=year, as_of_date=period_end, result_kind="monthly", dimension="", business_key="", effective_ftp_rate_pct=ftp_rate_pct
    )
    if (
        precomputed is not None
        and _pnl_by_business_precompute_has_required_diagnostics(precomputed, result_kind="monthly")
    ):
        payload = _pnl_by_business_monthly_with_management_change(
            PnlByBusinessMonthlyPayload.model_validate(precomputed)
        )
        return _build_pnl_by_business_analytical_result_envelope(
            governance_dir=governance_dir,
            requested_report_date=as_of_date,
            resolved_report_date=period_end,
            trace_id=f"tr_pnl_by_business_monthly_{year}_{period_end}_precomputed",
            result_kind="pnl.by_business_monthly",
            result_payload=payload.model_dump(mode="json"),
            quality_flag=_pnl_by_business_monthly_quality_flag(payload),
            filters_applied={"year": year, "as_of_date": as_of_date},
        )
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= period_end
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    loaded_date_list = list(loaded_dates)

    period_start = f"{min(loaded_dates)[:7]}-01"
    pnl_rows, balance_rows = _cached_pnl_by_business_analysis_inputs(
        duckdb_path,
        year,
        period_start,
        period_end,
    )
    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={period_end}.")

    pnl_rows = _append_pnl_by_business_manual_adjustments_to_rows(
        settings=settings,
        pnl_rows=tuple(pnl_rows),
        loaded_dates=loaded_date_list,
    )
    source_tables = _source_tables_with_manual_adjustments(
        [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
        ],
        settings=settings,
        loaded_dates=loaded_date_list,
    )
    payload = PnlByBusinessMonthlyPayload(
        year=year,
        as_of_date=period_end,
        source_tables=source_tables,
        months=_build_pnl_by_business_monthly_buckets(
            pnl_rows=pnl_rows,
            balance_rows=balance_rows,
            loaded_dates=loaded_date_list,
            ftp_rate_pct=ftp_rate_pct,
        ),
    )
    payload = _pnl_by_business_monthly_with_management_change(payload)
    return _build_pnl_by_business_analytical_result_envelope(
        governance_dir=governance_dir,
        requested_report_date=as_of_date,
        resolved_report_date=period_end,
        trace_id=f"tr_pnl_by_business_monthly_{year}_{period_end}",
        result_kind="pnl.by_business_monthly",
        result_payload=payload.model_dump(mode="json"),
        quality_flag=_pnl_by_business_monthly_quality_flag(payload),
        filters_applied={"year": year, "as_of_date": as_of_date},
    )


def pnl_yearly_summary_envelope(*, duckdb_path: str, governance_dir: str, year: int) -> dict[str, object]:
    _ensure_formal_pnl_storage_available(duckdb_path)
    repo = PnlRepository(duckdb_path)
    rows = [
        PnlYearlyBusinessSummaryRow(
            year=year,
            report_month=str(row["report_date"])[:7],
            report_date=str(row["report_date"]),
            business_type_primary=str(row["business_type_primary"]),
            business_type=str(row["business_type"]),
            currency_basis=str(row["currency_basis"]),
            total_pnl=_quantize_decimal(Decimal(str(row["total_pnl"] or "0"))),
            scale_amount=_quantize_decimal(Decimal(str(row["scale_amount"] or "0"))),
            yield_pct=_quantize_yield_pct(row.get("yield_pct")),
            pnl_row_count=int(row["pnl_row_count"] or 0),
        )
        for row in repo.fetch_yearly_business_rows(year)
    ]
    if not rows:
        raise ValueError(f"No formal pnl business summary found for year={year}.")
    payload = PnlYearlyBusinessSummaryPayload(
        year=year,
        source_tables=["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily"],
        rows=rows,
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=None,
        trace_id=f"tr_pnl_yearly_summary_{year}",
        result_kind="pnl.yearly_summary",
        result_payload=payload.model_dump(mode="json"),
    )


@lru_cache(maxsize=16)
def _cached_pnl_by_business_analysis_inputs(
    duckdb_path: str,
    year: int,
    period_start: str,
    period_end: str,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    repo = PnlRepository(duckdb_path)
    pnl_rows = repo.fetch_by_business_analysis_pnl_rows(year=year, as_of_date=period_end)
    balance_rows = repo.fetch_by_business_analysis_balance_rows(
        start_date=period_start,
        end_date=period_end,
    )
    return tuple(pnl_rows), tuple(balance_rows)


def _clear_pnl_by_business_analysis_cache() -> None:
    _cached_pnl_by_business_analysis_inputs.cache_clear()


def _clear_pnl_by_business_manual_adjustment_caches() -> None:
    clear_pnl_by_business_ytd_cache()
    _clear_pnl_by_business_analysis_cache()


def request_pnl_by_business_precompute_rebuild(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None = None,
    scope: str = "selected",
) -> dict[str, object]:
    """Queue an operator-requested rebuild, rejecting duplicate in-flight work."""
    normalized_year = _normalize_pnl_by_business_precompute_year(year)
    normalized_scope = str(scope or "selected").strip().lower()
    if normalized_scope not in {"selected", "all_available"}:
        raise ValueError("scope must be selected or all_available.")
    normalized_as_of_date = _normalize_pnl_by_business_precompute_as_of_date(
        year=normalized_year,
        as_of_date=as_of_date,
    )
    target_as_of_dates: list[str] | None = None
    if normalized_scope == "all_available":
        if normalized_as_of_date is not None:
            raise ValueError("as_of_date cannot be combined with scope=all_available.")
        target_as_of_dates = _available_pnl_by_business_precompute_cutoffs(
            PnlRepository(str(settings.duckdb_path)),
            year=normalized_year,
        )
    queued = _queue_pnl_by_business_precompute_refresh(
        settings,
        year=normalized_year,
        as_of_date=normalized_as_of_date,
        trigger_reason=(
            "manual_retry_all_available"
            if normalized_scope == "all_available"
            else "manual_retry"
        ),
        raise_on_dispatch_failure=True,
        raise_on_duplicate=True,
        as_of_dates=target_as_of_dates,
        scope=normalized_scope,
    )
    assert queued is not None
    return queued


def pnl_by_business_precompute_status(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """Return task lifecycle evidence plus the read path currently serving the page."""
    normalized_year = _normalize_pnl_by_business_precompute_year(year)
    normalized_as_of_date = _normalize_pnl_by_business_precompute_as_of_date(
        year=normalized_year,
        as_of_date=as_of_date,
    )
    run_records = _pnl_by_business_precompute_run_records(settings, year=normalized_year)
    pnl_repo = PnlRepository(str(settings.duckdb_path))
    latest_available_as_of_date = pnl_repo.max_formal_or_nonstd_report_date_in_year(
        year=normalized_year,
        as_of_cap=None,
    )
    period_end = pnl_repo.max_formal_or_nonstd_report_date_in_year(
        year=normalized_year,
        as_of_cap=normalized_as_of_date,
    )
    latest = _pnl_by_business_precompute_status_record(
        run_records,
        period_end=period_end,
        latest_available_as_of_date=latest_available_as_of_date,
    )
    if (
        latest is not None
        and period_end is not None
        and not str(latest.get("report_date") or "")
        and period_end in _pnl_by_business_precompute_record_target_dates(latest)
    ):
        latest = {**latest, "report_date": period_end}
        cutoff_result = _pnl_by_business_precompute_cutoff_result(
            latest,
            period_end=period_end,
        )
        if cutoff_result is not None:
            latest.update(
                source_version=str(cutoff_result.get("source_version") or ""),
                generated_at=str(cutoff_result.get("generated_at") or "") or None,
                record_count=int(cutoff_result.get("records") or 0),
            )
    status = str(latest.get("status") or "") if latest else "idle"
    inflight = status in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES
    metadata: dict[str, object] | None = None
    if period_end:
        active_adjustments = active_pnl_by_business_manual_adjustments_for_period(
            settings.governance_path,
            year=normalized_year,
            period_end=period_end,
        )
        metadata = pnl_repo.fetch_pnl_by_business_precompute_metadata(
            year=normalized_year,
            as_of_date=period_end,
            effective_ftp_rate_pct=resolve_product_category_ftp_rate_pct(
                date(normalized_year, 12, 31), settings.ftp_rate_pct
            ),
            supplemental_source_version=pnl_by_business_manual_adjustment_source_version(active_adjustments),
            verify_current=not inflight,
        )
    is_current = bool(metadata and metadata.get("is_current"))
    if latest is None and is_current:
        status = "completed"
    return _pnl_by_business_precompute_status_payload(
        year=normalized_year,
        status=status,
        record=latest,
        metadata=metadata,
        latest_available_as_of_date=latest_available_as_of_date,
        is_current=is_current,
    )


def _enqueue_pnl_by_business_precompute_refresh(settings: Settings, *, report_date: str) -> bool:
    """Queue a page read-model rebuild without making the committed adjustment fail."""
    try:
        year = date.fromisoformat(str(report_date)).year
    except ValueError:
        logger.warning(
            "skipped pnl_by_business precompute refresh for invalid report_date=%s",
            report_date,
        )
        return False
    return (
        _queue_pnl_by_business_precompute_refresh(
            settings,
            year=year,
            as_of_date=None,
            trigger_reason="manual_adjustment_state_change",
            raise_on_dispatch_failure=False,
            raise_on_duplicate=False,
        )
        is not None
    )


def _queue_pnl_by_business_precompute_refresh(
    settings: Settings,
    *,
    year: int,
    as_of_date: str | None,
    trigger_reason: str,
    raise_on_dispatch_failure: bool,
    raise_on_duplicate: bool,
    as_of_dates: list[str] | None = None,
    scope: str = "selected",
) -> dict[str, object] | None:
    run_id = f"{PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME}:{uuid4()}"
    queued_at = datetime.now(UTC).isoformat()
    writer_lock = resolve_duckdb_writer_lock(
        settings.duckdb_path,
        ttl_seconds=PNL_MATERIALIZE_LOCK.ttl_seconds,
    )
    record = CacheBuildRunRecord(
        run_id=run_id,
        job_name=PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        status="queued",
        cache_key=PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
        cache_version=PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION,
        lock=writer_lock.key,
        source_version=PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION,
        vendor_version="vv_none",
        rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        report_date=as_of_date,
        queued_at=queued_at,
    ).model_dump()
    record["target_year"] = int(year)
    record["trigger_reason"] = trigger_reason
    record["scope"] = scope
    if as_of_dates is not None:
        record["target_as_of_dates"] = list(as_of_dates)
        record["target_count"] = len(as_of_dates)
    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    try:
        with acquire_lock(
            PNL_BY_BUSINESS_PRECOMPUTE_DISPATCH_LOCK,
            base_dir=settings.governance_path,
            timeout_seconds=2.0,
        ):
            inflight_records = _inflight_pnl_by_business_precompute_runs(settings, year=int(year))
            if inflight_records and raise_on_duplicate:
                raise PnlByBusinessPrecomputeConflictError(
                    f"PnL by-business precompute already in progress for year={int(year)}."
                )
            if any(str(item.get("status") or "") == "queued" for item in inflight_records):
                return None
            governance_repo.append(CACHE_BUILD_RUN_STREAM, record)
            try:
                task_kwargs: dict[str, object] = {
                    "duckdb_path": str(settings.duckdb_path),
                    "governance_dir": str(settings.governance_path),
                    "year": int(year),
                    "as_of_date": as_of_date,
                    "run_id": run_id,
                    "queued_at": queued_at,
                    "trigger_reason": trigger_reason,
                }
                if as_of_dates is not None:
                    task_kwargs["as_of_dates"] = list(as_of_dates)
                rebuild_pnl_by_business_precompute.send(**task_kwargs)
            except Exception as exc:  # page keeps its fingerprinted real-time fallback
                failed_record = {
                    **record,
                    "status": "failed",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "error_message": str(exc),
                    "failure_category": "queue_dispatch_failure",
                    "failure_reason": str(exc),
                }
                governance_repo.append(CACHE_BUILD_RUN_STREAM, failed_record)
                logger.warning(
                    "failed to enqueue pnl_by_business precompute refresh for year=%s: %s",
                    year,
                    exc,
                )
                if raise_on_dispatch_failure:
                    raise PnlByBusinessPrecomputeDispatchError(
                        "PnL by-business precompute queue dispatch failed."
                    ) from exc
                return None
    except TimeoutError as exc:
        if raise_on_duplicate:
            raise PnlByBusinessPrecomputeConflictError(
                f"PnL by-business precompute dispatch is busy for year={int(year)}."
            ) from exc
        logger.info("skipped duplicate pnl_by_business precompute dispatch for year=%s", year)
        return None
    payload = _pnl_by_business_precompute_status_payload(
        year=int(year),
        status="queued",
        record=record,
        metadata=None,
        latest_available_as_of_date=None,
        is_current=False,
    )
    payload["scope"] = scope
    if as_of_dates is not None:
        payload["target_as_of_dates"] = list(as_of_dates)
        payload["target_count"] = len(as_of_dates)
    return payload


def _pnl_by_business_precompute_run_records(settings: Settings, *, year: int) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key") or "") == PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY
        and str(record.get("job_name") or "") == PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME
        and (
            _safe_int(record.get("target_year")) == year
            or str(record.get("report_date") or "").startswith(f"{year:04d}-")
        )
    ]


def _latest_inflight_pnl_by_business_precompute(
    settings: Settings,
    *,
    year: int,
) -> dict[str, object] | None:
    inflight_records = _inflight_pnl_by_business_precompute_runs(settings, year=year)
    return inflight_records[-1] if inflight_records else None


def _inflight_pnl_by_business_precompute_runs(
    settings: Settings,
    *,
    year: int,
) -> list[dict[str, object]]:
    effective_records = _effective_pnl_by_business_precompute_run_records(
        _pnl_by_business_precompute_run_records(settings, year=year)
    )
    return [
        record
        for record in effective_records
        if str(record.get("status") or "") in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES
    ]


def _normalize_pnl_by_business_precompute_year(year: int) -> int:
    normalized_year = int(year)
    if not 2000 <= normalized_year <= 2100:
        raise ValueError("year must be between 2000 and 2100.")
    return normalized_year


def _normalize_pnl_by_business_precompute_as_of_date(*, year: int, as_of_date: str | None) -> str | None:
    if as_of_date is None:
        return None
    raw_value = str(as_of_date)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value) is None:
        raise ValueError("as_of_date must use YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("as_of_date must use YYYY-MM-DD format.") from exc
    if parsed.year != int(year):
        raise ValueError(f"as_of_date={parsed.isoformat()} is outside requested year={int(year)}.")
    return parsed.isoformat()


def _available_pnl_by_business_precompute_cutoffs(
    repo: PnlRepository,
    *,
    year: int,
) -> list[str]:
    cutoffs: set[str] = set()
    for raw_date in repo.list_union_report_dates():
        raw_value = str(raw_date)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value) is None:
            continue
        try:
            parsed = date.fromisoformat(raw_value)
        except ValueError:
            continue
        if parsed.year != int(year) or parsed.day != monthrange(parsed.year, parsed.month)[1]:
            continue
        cutoffs.add(parsed.isoformat())
    if not cutoffs:
        raise ValueError(f"No available month-end cutoffs found for year={int(year)}.")
    return sorted(cutoffs)


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _effective_pnl_by_business_precompute_run_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    records_by_run_id: dict[str, list[dict[str, object]]] = {}
    latest_event_index: dict[str, int] = {}
    for index, record in enumerate(records):
        run_id = str(record.get("run_id") or f"missing-run-id:{index}")
        marked_record = dict(record)
        marked_record["_effective_run_id"] = run_id
        records_by_run_id.setdefault(run_id, []).append(marked_record)
        latest_event_index[run_id] = index
    effective = [
        _effective_pnl_by_business_precompute_run_record(run_records)
        for run_records in records_by_run_id.values()
    ]
    return sorted(effective, key=lambda record: latest_event_index[str(record["_effective_run_id"])])


def _effective_pnl_by_business_precompute_run_record(
    run_records: list[dict[str, object]],
) -> dict[str, object]:
    latest = dict(run_records[-1])
    status = str(latest.get("status") or "")
    failure_category = str(latest.get("failure_category") or "")
    failure_count = sum(1 for record in run_records if str(record.get("status") or "") == "failed")
    max_retries = int(getattr(rebuild_pnl_by_business_precompute, "options", {}).get("max_retries", 3))
    if status == "failed" and failure_category != "queue_dispatch_failure" and failure_count <= max_retries:
        latest["status"] = "queued"
        latest["failure_category"] = "automatic_retry_pending"
    if str(latest.get("status") or "") in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES:
        timestamp = str(
            latest.get("finished_at")
            or latest.get("started_at")
            or latest.get("queued_at")
            or ""
        ).strip()
        if not timestamp or datetime.now(UTC) - _parse_created_at(timestamp) > PNL_BY_BUSINESS_PRECOMPUTE_STALE_AFTER:
            latest["status"] = "failed"
            latest["failure_category"] = "stale_inflight"
            latest["error_message"] = "Precompute worker progress timed out."
    latest["retry_attempt"] = failure_count
    return latest


def _pnl_by_business_precompute_status_record(
    records: list[dict[str, object]],
    *,
    period_end: str | None,
    latest_available_as_of_date: str | None,
) -> dict[str, object] | None:
    relevant = [
        record
        for record in _effective_pnl_by_business_precompute_run_records(records)
        if (
            (
                period_end is not None
                and str(record.get("report_date") or "") == period_end
            )
            or (
                period_end is not None
                and period_end in _pnl_by_business_precompute_record_target_dates(record)
            )
            or (
                not str(record.get("report_date") or "")
                and not _pnl_by_business_precompute_record_target_dates(record)
                and period_end == latest_available_as_of_date
            )
        )
    ]
    if not relevant:
        return None
    inflight = [
        record
        for record in relevant
        if str(record.get("status") or "") in PNL_BY_BUSINESS_PRECOMPUTE_INFLIGHT_STATUSES
    ]
    return (inflight or relevant)[-1]


def _pnl_by_business_precompute_record_target_dates(record: dict[str, object]) -> set[str]:
    raw_dates = record.get("target_as_of_dates")
    if not isinstance(raw_dates, (list, tuple, set)):
        return set()
    return {str(item) for item in raw_dates if str(item)}


def _pnl_by_business_precompute_cutoff_result(
    record: dict[str, object],
    *,
    period_end: str,
) -> dict[str, object] | None:
    raw_results = record.get("cutoff_results")
    if not isinstance(raw_results, list):
        return None
    for item in raw_results:
        if isinstance(item, dict) and str(item.get("as_of_date") or "") == period_end:
            return item
    return None


def _pnl_by_business_precompute_status_payload(
    *,
    year: int,
    status: str,
    record: dict[str, object] | None,
    metadata: dict[str, object] | None,
    latest_available_as_of_date: str | None,
    is_current: bool,
) -> dict[str, object]:
    actor_options = getattr(rebuild_pnl_by_business_precompute, "options", {})
    failure_category = str(record.get("failure_category") or "") if record else ""
    safe_error_message = _safe_pnl_by_business_precompute_error_message(
        status=status,
        failure_category=failure_category,
    )
    return {
        "year": year,
        "status": status,
        "serving_mode": "precomputed" if is_current else "live_fallback",
        "is_current": is_current,
        "run_id": (str(record.get("run_id") or "") or None) if record else None,
        "report_date": (
            str(metadata.get("as_of_date") or "") or None
            if metadata
            else (str(record.get("report_date") or "") or None if record else None)
        ),
        "latest_available_as_of_date": latest_available_as_of_date,
        "source_version": (
            str(metadata.get("source_version") or "") or None
            if metadata
            else (str(record.get("source_version") or "") or None if record else None)
        ),
        "rule_version": (
            str(metadata.get("rule_version") or "") or None
            if metadata
            else PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
        ),
        "queued_at": (str(record.get("queued_at") or "") or None) if record else None,
        "started_at": (str(record.get("started_at") or "") or None) if record else None,
        "finished_at": (str(record.get("finished_at") or "") or None) if record else None,
        "generated_at": (
            str(metadata.get("generated_at") or "") or None
            if metadata
            else (str(record.get("generated_at") or "") or None if record else None)
        ),
        "record_count": (
            int(metadata.get("record_count") or 0)
            if metadata
            else (int(record.get("record_count") or 0) if record and record.get("record_count") is not None else None)
        ),
        "error_message": safe_error_message,
        "failure_category": failure_category or None,
        "trigger_reason": (str(record.get("trigger_reason") or "") or None) if record else None,
        "retry_attempt": int(record.get("retry_attempt") or 0) if record else 0,
        "retry_policy": {
            "max_retries": int(actor_options.get("max_retries", 3)),
            "min_backoff_seconds": int(actor_options.get("min_backoff", 15_000)) // 1000,
        },
    }


def _safe_pnl_by_business_precompute_error_message(*, status: str, failure_category: str) -> str | None:
    if failure_category == "automatic_retry_pending":
        return "上一次预计算未完成，后台正在按策略自动重试。"
    if status != "failed":
        return None
    if failure_category == "queue_dispatch_failure":
        return "预计算任务分发失败，请检查后台队列后重试。"
    if failure_category == "stale_inflight":
        return "预计算任务长时间未更新，已解除占用，可重新生成。"
    if failure_category == "lock_timeout":
        return "预计算暂未取得数据写入锁，自动重试已结束。"
    return "预计算执行失败，自动重试已结束，请查看后台运行日志。"


def _build_pnl_by_business_analysis_rows(
    *,
    pnl_rows: list[dict[str, object]],
    balance_rows: list[dict[str, object]],
    loaded_dates: list[str],
    period_start: str,
    period_end: str,
    business_key: str | None,
    dimension: PnlByBusinessAnalysisDimension,
    ftp_rate_pct: Decimal,
) -> list[PnlByBusinessAnalysisRow]:
    balance_lookup = _analysis_balance_lookup(balance_rows)
    historical_balance_lookup = _analysis_historical_balance_lookup(balance_rows)
    sub_type_by_date_code = _analysis_sub_type_by_date_code(balance_rows)
    month_end_by_month: dict[str, str] = {}
    for report_date in sorted(loaded_dates):
        month_end_by_month[str(report_date)[:7]] = str(report_date)

    buckets: dict[str, dict[str, object]] = {}
    if dimension == "bond_bucket":
        for key, label in ANALYSIS_BOND_BUCKET_LABELS.items():
            buckets[key] = _new_analysis_dimension_bucket(key, label)
    elif dimension == "bond_bucket_monthly":
        for month_end in sorted(month_end_by_month.values()):
            for key, label in ANALYSIS_BOND_BUCKET_LABELS.items():
                dimension_key = f"{month_end}::{key}"
                buckets[dimension_key] = _new_analysis_dimension_bucket(dimension_key, f"{month_end} {label}")
    for pnl_row in pnl_rows:
        classification = (
            _pnl_by_business_manual_classification(pnl_row)
            if _norm_text(pnl_row.get("source_kind")) == "manual_adjustment"
            else _analysis_classification_for_pnl_row(
                pnl_row=pnl_row,
                balance_lookup=balance_lookup,
                historical_balance_lookup=historical_balance_lookup,
                sub_type_by_date_code=sub_type_by_date_code,
                fallback_date=period_end,
            )
        )
        if not _analysis_matches_business_key(classification, business_key):
            continue
        key_label = _analysis_dimension_for_pnl_row(pnl_row, classification, dimension)
        if key_label is None:
            continue
        dimension_key, dimension_label = key_label
        bucket = buckets.setdefault(dimension_key, _new_analysis_dimension_bucket(dimension_key, dimension_label))
        if _norm_text(pnl_row.get("source_kind")) != "manual_adjustment":
            bucket["has_non_manual_pnl"] = True
        bucket["interest_income"] = Decimal(str(bucket["interest_income"])) + _decimal_value(pnl_row.get("interest_income_514"))
        bucket["fair_value_change"] = Decimal(str(bucket["fair_value_change"])) + _decimal_value(pnl_row.get("fair_value_change_516"))
        bucket["capital_gain"] = Decimal(str(bucket["capital_gain"])) + _decimal_value(pnl_row.get("capital_gain_517"))
        bucket["manual_adjustment"] = Decimal(str(bucket["manual_adjustment"])) + _decimal_value(pnl_row.get("manual_adjustment"))
        bucket["total_pnl"] = Decimal(str(bucket["total_pnl"])) + _decimal_value(pnl_row.get("total_pnl"))
        code = _norm_text(pnl_row.get("instrument_code"))
        if code:
            bucket["asset_codes"].add(code)

    avg_sums: dict[str, Decimal] = {}
    current_sums: dict[str, Decimal] = {}
    coverage_dates = {str(row.get("report_date")) for row in balance_rows if _norm_text(row.get("report_date"))}
    coverage_dates_by_month_key: dict[str, set[str]] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        month_key = month_end_by_month.get(report_date[:7])
        if month_key:
            coverage_dates_by_month_key.setdefault(month_key, set()).add(report_date)
        classification = _analysis_classification_from_balance_row(row)
        if not _analysis_matches_business_key(classification, business_key):
            continue
        key_label = _analysis_dimension_for_balance_row(row, dimension, month_end_by_month)
        if key_label is None:
            continue
        dimension_key, _dimension_label = key_label
        avg_sums[dimension_key] = avg_sums.get(dimension_key, Decimal("0")) + _decimal_value(row.get("avg_amount"))
        dimension_report_date = _analysis_dimension_report_date(dimension_key)
        if (_analysis_is_monthly_dimension(dimension) and report_date == dimension_report_date) or (
            not _analysis_is_monthly_dimension(dimension) and report_date == period_end
        ):
            current_sums[dimension_key] = current_sums.get(dimension_key, Decimal("0")) + _decimal_value(
                row.get("current_amount")
            )

    period_calendar_days = _calendar_days(period_start, period_end)

    def _row_sort_key(item: dict[str, object]) -> tuple[object, ...]:
        if dimension == "monthly":
            return (str(item["dimension_key"]),)
        if dimension == "bond_bucket_monthly":
            dimension_key = str(item["dimension_key"])
            report_date = _analysis_dimension_report_date(dimension_key)
            bucket_key = dimension_key.split("::", 1)[1] if "::" in dimension_key else ""
            return (report_date, ANALYSIS_BOND_BUCKET_SORT.get(bucket_key, 99))
        if dimension == "bond_bucket":
            return (ANALYSIS_BOND_BUCKET_SORT.get(str(item["dimension_key"]), 99),)
        return (-abs(Decimal(str(item["total_pnl"]))), str(item["dimension_label"]))

    rows: list[PnlByBusinessAnalysisRow] = []
    for bucket in sorted(buckets.values(), key=_row_sort_key):
        dimension_key = str(bucket["dimension_key"])
        if _analysis_is_monthly_dimension(dimension):
            month_end_key = _analysis_dimension_report_date(dimension_key)
            denom = len(coverage_dates_by_month_key.get(month_end_key, set()))
            calendar_days = _calendar_days(f"{month_end_key[:7]}-01", month_end_key)
        else:
            denom = len(coverage_dates)
            calendar_days = period_calendar_days
        avg_balance = (avg_sums.get(dimension_key, Decimal("0")) / Decimal(str(denom))) if denom > 0 else Decimal("0")
        current_balance = current_sums.get(dimension_key, Decimal("0"))
        total_pnl = Decimal(str(bucket["total_pnl"]))
        annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days, ftp_rate_pct)
        ftp_values = _analysis_ftp_values(
            total_pnl=total_pnl,
            avg_balance=avg_balance,
            annualized_yield_pct=annualized_yield_pct,
            calendar_days=calendar_days,
            ftp_rate_pct=ftp_rate_pct,
        )
        is_manual_adjustment_only = (
            not bool(bucket.get("has_non_manual_pnl"))
            and Decimal(str(bucket["manual_adjustment"])) == total_pnl
        )
        if is_manual_adjustment_only:
            ftp_values["ftp_cost"] = _quantize_decimal(Decimal("0"))
            ftp_values["ftp_net_pnl"] = _quantize_decimal(total_pnl)
        rows.append(
            PnlByBusinessAnalysisRow(
                dimension_key=dimension_key,
                dimension_label=str(bucket["dimension_label"]),
                interest_income=_quantize_decimal(Decimal(str(bucket["interest_income"]))),
                fair_value_change=_quantize_decimal(Decimal(str(bucket["fair_value_change"]))),
                capital_gain=_quantize_decimal(Decimal(str(bucket["capital_gain"]))),
                manual_adjustment=_quantize_decimal(Decimal(str(bucket["manual_adjustment"]))),
                total_pnl=_quantize_decimal(total_pnl),
                avg_balance=_quantize_decimal(avg_balance),
                current_balance=_quantize_decimal(current_balance),
                annualized_yield_pct=annualized_yield_pct,
                ftp_rate_pct=ftp_values["ftp_rate_pct"],
                ftp_cost=ftp_values["ftp_cost"],
                ftp_net_pnl=ftp_values["ftp_net_pnl"],
                ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
                asset_count=len(bucket["asset_codes"]) if bucket["asset_codes"] else 0,
            )
        )
    return rows


def _build_pnl_by_business_monthly_buckets(
    *,
    pnl_rows: tuple[dict[str, object], ...],
    balance_rows: tuple[dict[str, object], ...],
    loaded_dates: list[str],
    ftp_rate_pct: Decimal,
) -> list[PnlByBusinessMonthlyBucket]:
    balance_rows_list = list(balance_rows)
    balance_lookup = _analysis_balance_lookup(balance_rows_list)
    historical_balance_lookup = _analysis_historical_balance_lookup(balance_rows_list)
    sub_type_by_date_code = _analysis_sub_type_by_date_code(balance_rows_list)
    month_end_by_month: dict[str, str] = {}
    for report_date in sorted(loaded_dates):
        month_end_by_month[str(report_date)[:7]] = str(report_date)

    buckets: list[PnlByBusinessMonthlyBucket] = []
    for month_key, month_end in sorted(month_end_by_month.items()):
        month_start = f"{month_key}-01"
        calendar_days = _calendar_days(month_start, month_end)
        groups: dict[str, dict[str, object]] = {
            str(row_def["row_key"]): _new_monthly_business_group(row_def) for row_def in ZQTZ_ASSET_BOND_ROWS
        }
        source_total_pnl = Decimal("0")
        unallocated_items: list[PnlByBusinessYtdUnallocatedItem] = []

        for pnl_row in pnl_rows:
            if _norm_text(pnl_row.get("report_date"))[:7] != month_key:
                continue
            row_total_pnl = _decimal_value(pnl_row.get("total_pnl"))
            source_total_pnl += row_total_pnl
            is_manual_adjustment = _norm_text(pnl_row.get("source_kind")) == "manual_adjustment"
            classification = (
                _pnl_by_business_manual_classification(pnl_row)
                if is_manual_adjustment
                else _analysis_classification_for_pnl_row(
                    pnl_row=pnl_row,
                    balance_lookup=balance_lookup,
                    historical_balance_lookup=historical_balance_lookup,
                    sub_type_by_date_code=sub_type_by_date_code,
                    fallback_date=month_end,
                )
            )
            matched_rows = (
                [_manual_adjustment_row_def(pnl_row)]
                if is_manual_adjustment
                else list(match_zqtz_asset_bond_rows(classification))
            )
            if not any(
                is_parent_zqtz_business_row(
                    str(row_def["row_key"]),
                    str(row_def["row_label"]),
                    row_def.get("source_note"),
                )
                for row_def in matched_rows
            ):
                unallocated_items.append(
                    _pnl_by_business_ytd_unallocated_item(
                        record=pnl_row,
                        classification=classification,
                        reason_code=_pnl_by_business_ytd_unallocated_reason(matched_rows),
                        default_source_kind="formal_fact",
                    )
                )
            for row_def in matched_rows:
                _merge_monthly_business_pnl_row(groups, row_def, pnl_row)

        avg_sums: dict[str, Decimal] = {}
        current_sums: dict[str, Decimal] = {}
        coverage_dates: set[str] = set()
        for row in balance_rows:
            report_date = _norm_text(row.get("report_date"))
            if report_date[:7] != month_key:
                continue
            coverage_dates.add(report_date)
            classification = _analysis_classification_from_balance_row(row)
            for row_def in match_zqtz_asset_bond_rows(classification):
                row_key = str(row_def["row_key"])
                avg_sums[row_key] = avg_sums.get(row_key, Decimal("0")) + _decimal_value(row.get("avg_amount"))
                if report_date == month_end:
                    current_sums[row_key] = current_sums.get(row_key, Decimal("0")) + _decimal_value(
                        row.get("current_amount")
                    )

        denom = len(coverage_dates)
        item_inputs: list[tuple[dict[str, object], Decimal, Decimal]] = []
        parent_total = Decimal("0")
        for group in sorted(groups.values(), key=lambda item: (int(item["sort_order"]), str(item["row_key"]))):
            row_key = str(group["row_key"])
            if denom > 0:
                avg_balance = avg_sums.get(row_key, Decimal("0")) / Decimal(str(denom))
            else:
                avg_balance = Decimal("0")
            current_balance = current_sums.get(row_key, Decimal("0"))
            total_pnl = Decimal(str(group["total_pnl"]))
            if is_parent_zqtz_business_row(row_key, str(group["business_type"]), group.get("source_note")):
                parent_total += total_pnl
            item_inputs.append((group, avg_balance, current_balance))

        items = [
            _monthly_business_item_from_group(
                group=group,
                avg_balance=avg_balance,
                current_balance=current_balance,
                total_pnl_for_proportion=parent_total,
                calendar_days=calendar_days,
                ftp_rate_pct=ftp_rate_pct,
            )
            for group, avg_balance, current_balance in item_inputs
        ]
        summary = _monthly_business_summary_from_items(items, calendar_days, ftp_rate_pct)
        precise_source_total_pnl = source_total_pnl
        precise_parent_total = parent_total
        source_total_pnl = _quantize_decimal(precise_source_total_pnl)
        parent_total = _quantize_decimal(precise_parent_total)
        precise_unallocated_items = sorted(
            unallocated_items,
            key=lambda item: (
                -item.abs_pnl,
                item.report_date,
                item.source_kind,
                item.instrument_code,
                item.portfolio_name,
                item.cost_center,
            ),
        )
        unallocated_pnl = _quantize_decimal(
            sum((item.total_pnl for item in precise_unallocated_items), Decimal("0"))
        )
        unallocated_abs_pnl = _quantize_decimal(
            sum((item.abs_pnl for item in precise_unallocated_items), Decimal("0"))
        )
        normalized_unallocated_items = [
            _normalize_pnl_by_business_unallocated_item(item) for item in precise_unallocated_items
        ]
        precise_unallocated_pnl = sum(
            (item.total_pnl for item in precise_unallocated_items),
            Decimal("0"),
        )
        reconciliation_delta = _quantize_decimal(
            precise_source_total_pnl - precise_parent_total - precise_unallocated_pnl
        )
        sample_filled = 0 < denom < calendar_days
        buckets.append(
            PnlByBusinessMonthlyBucket(
                month_key=month_key,
                period_start_date=month_start,
                period_end_date=month_end,
                calendar_days=calendar_days,
                coverage_days=denom,
                expected_days=calendar_days,
                sample_filled=sample_filled,
                sample_fill_method="observed_days_scaled_to_calendar" if sample_filled else None,
                source_total_pnl=source_total_pnl,
                classified_parent_total_pnl=parent_total,
                unallocated_pnl=unallocated_pnl,
                unallocated_abs_pnl=unallocated_abs_pnl,
                unallocated_row_count=len(precise_unallocated_items),
                reconciliation_delta=reconciliation_delta,
                unallocated_breakdown=_pnl_by_business_ytd_unallocated_breakdown(precise_unallocated_items),
                unallocated_items=normalized_unallocated_items,
                unallocated_evidence_complete=True,
                summary=summary,
                items=items,
            )
        )
    return buckets


def _new_monthly_business_group(row_def: dict[str, object]) -> dict[str, object]:
    return {
        "row_key": str(row_def["row_key"]),
        "sort_order": int(row_def["sort_order"]),
        "business_type": str(row_def["row_label"]),
        "source_note": str(row_def.get("source_note") or "ZQTZ_ASSET_BOND_ROWS"),
        "interest_income": Decimal("0"),
        "fair_value_change": Decimal("0"),
        "capital_gain": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0"),
        "asset_codes": set(),
        "row_count": 0,
    }


def _merge_monthly_business_pnl_row(
    groups: dict[str, dict[str, object]],
    row_def: dict[str, object],
    row: dict[str, object],
) -> None:
    row_key = str(row_def["row_key"])
    group = groups.setdefault(row_key, _new_monthly_business_group(row_def))
    group["interest_income"] = Decimal(str(group["interest_income"])) + _decimal_value(row.get("interest_income_514"))
    group["fair_value_change"] = Decimal(str(group["fair_value_change"])) + _decimal_value(row.get("fair_value_change_516"))
    group["capital_gain"] = Decimal(str(group["capital_gain"])) + _decimal_value(row.get("capital_gain_517"))
    group["manual_adjustment"] = Decimal(str(group["manual_adjustment"])) + _decimal_value(row.get("manual_adjustment"))
    group["total_pnl"] = Decimal(str(group["total_pnl"])) + _decimal_value(row.get("total_pnl"))
    code = _norm_text(row.get("instrument_code"))
    if code:
        group["asset_codes"].add(code)
    group["row_count"] = int(group["row_count"]) + 1


def _monthly_business_item_from_group(
    *,
    group: dict[str, object],
    avg_balance: Decimal,
    current_balance: Decimal,
    total_pnl_for_proportion: Decimal,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> PnlByBusinessMonthlyItem:
    total_pnl = Decimal(str(group["total_pnl"]))
    annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days, ftp_rate_pct)
    ftp_values = _analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    return PnlByBusinessMonthlyItem(
        row_key=str(group["row_key"]),
        sort_order=int(group["sort_order"]),
        business_type=str(group["business_type"]),
        interest_income=_quantize_decimal(Decimal(str(group["interest_income"]))),
        fair_value_change=_quantize_decimal(Decimal(str(group["fair_value_change"]))),
        capital_gain=_quantize_decimal(Decimal(str(group["capital_gain"]))),
        manual_adjustment=_quantize_decimal(Decimal(str(group["manual_adjustment"]))),
        total_pnl=_quantize_decimal(total_pnl),
        avg_balance=_quantize_decimal(avg_balance),
        current_balance=_quantize_decimal(current_balance),
        annualized_yield_pct=annualized_yield_pct,
        ftp_rate_pct=ftp_values["ftp_rate_pct"],
        ftp_cost=ftp_values["ftp_cost"],
        ftp_net_pnl=ftp_values["ftp_net_pnl"],
        ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
        proportion=(
            _quantize_ratio(total_pnl / total_pnl_for_proportion)
            if total_pnl_for_proportion != Decimal("0")
            else None
        ),
        asset_count=len(group["asset_codes"]) if group["asset_codes"] else int(group["row_count"]),
        source_note=str(group.get("source_note") or "ZQTZ_ASSET_BOND_ROWS"),
    )


def _monthly_business_summary_from_items(
    items: list[PnlByBusinessMonthlyItem],
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> PnlByBusinessMonthlySummary:
    parent_items = [item for item in items if _is_parent_monthly_business_item(item)]
    interest_income = sum((Decimal(str(item.interest_income)) for item in parent_items), Decimal("0"))
    fair_value_change = sum((Decimal(str(item.fair_value_change)) for item in parent_items), Decimal("0"))
    capital_gain = sum((Decimal(str(item.capital_gain)) for item in parent_items), Decimal("0"))
    manual_adjustment = sum((Decimal(str(item.manual_adjustment)) for item in parent_items), Decimal("0"))
    total_pnl = sum((Decimal(str(item.total_pnl)) for item in parent_items), Decimal("0"))
    avg_balance = sum((Decimal(str(item.avg_balance)) for item in parent_items), Decimal("0"))
    current_balance = sum((Decimal(str(item.current_balance)) for item in parent_items), Decimal("0"))
    annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days, ftp_rate_pct)
    ftp_values = _analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    return PnlByBusinessMonthlySummary(
        interest_income=_quantize_decimal(interest_income),
        fair_value_change=_quantize_decimal(fair_value_change),
        capital_gain=_quantize_decimal(capital_gain),
        manual_adjustment=_quantize_decimal(manual_adjustment),
        total_pnl=_quantize_decimal(total_pnl),
        avg_balance=_quantize_decimal(avg_balance),
        current_balance=_quantize_decimal(current_balance),
        annualized_yield_pct=annualized_yield_pct,
        ftp_rate_pct=ftp_values["ftp_rate_pct"],
        ftp_cost=ftp_values["ftp_cost"],
        ftp_net_pnl=ftp_values["ftp_net_pnl"],
        ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
        asset_count=sum(item.asset_count for item in parent_items),
    )


def _is_parent_monthly_business_item(item: PnlByBusinessMonthlyItem) -> bool:
    return is_parent_zqtz_business_row(item.row_key, item.business_type, item.source_note)


def _pnl_by_business_monthly_with_management_change(
    payload: PnlByBusinessMonthlyPayload,
) -> PnlByBusinessMonthlyPayload:
    current_month_key = payload.as_of_date[:7]
    current_month_start = date.fromisoformat(f"{current_month_key}-01")
    previous_month_key = (current_month_start - timedelta(days=1)).isoformat()[:7]
    buckets_by_key = {bucket.month_key: bucket for bucket in payload.months}
    current_bucket = buckets_by_key.get(current_month_key)
    previous_bucket = buckets_by_key.get(previous_month_key)

    if current_bucket is None:
        management_change = PnlByBusinessMonthlyManagementChange(
            comparison_basis="latest_month_vs_previous_calendar_month",
            comparison_scope="requested_year",
            comparison_status="current_month_missing",
            comparison_available=False,
            current_month_key=current_month_key,
            previous_month_key=previous_month_key,
            coverage_warning_months=[],
            reconciliation_warning_months=[],
            incomplete_months=[],
            summary=None,
            rows=[],
        )
        return payload.model_copy(update={"management_change": management_change})

    if not previous_month_key.startswith(f"{payload.year:04d}-"):
        management_change = PnlByBusinessMonthlyManagementChange(
            comparison_basis="latest_month_vs_previous_calendar_month",
            comparison_scope="requested_year",
            comparison_status="previous_month_outside_request_scope",
            comparison_available=False,
            current_month_key=current_month_key,
            previous_month_key=previous_month_key,
            coverage_warning_months=[],
            reconciliation_warning_months=[],
            incomplete_months=[],
            summary=None,
            rows=[],
        )
        return payload.model_copy(update={"management_change": management_change})

    if previous_bucket is None:
        management_change = PnlByBusinessMonthlyManagementChange(
            comparison_basis="latest_month_vs_previous_calendar_month",
            comparison_scope="requested_year",
            comparison_status="previous_month_missing",
            comparison_available=False,
            current_month_key=current_month_key,
            previous_month_key=previous_month_key,
            coverage_warning_months=[],
            reconciliation_warning_months=[],
            incomplete_months=[],
            summary=None,
            rows=[],
        )
        return payload.model_copy(update={"management_change": management_change})

    warning_months = sorted(
        bucket.month_key
        for bucket in (previous_bucket, current_bucket)
        if bucket.sample_filled or _coverage_quality_flag(bucket.coverage_days, bucket.expected_days)
    )
    reconciliation_warning_months = sorted(
        bucket.month_key
        for bucket in (previous_bucket, current_bucket)
        if bucket.unallocated_row_count > 0
        or bucket.reconciliation_delta != Decimal("0")
        or not bucket.unallocated_evidence_complete
    )
    incomplete_months = sorted(
        bucket.month_key
        for bucket in (previous_bucket, current_bucket)
        if not _is_calendar_month_end(bucket.period_end_date)
    )
    if incomplete_months:
        management_change = PnlByBusinessMonthlyManagementChange(
            comparison_basis="latest_month_vs_previous_calendar_month",
            comparison_scope="requested_year",
            comparison_status="period_incomplete",
            comparison_available=False,
            current_month_key=current_month_key,
            previous_month_key=previous_month_key,
            coverage_warning_months=warning_months,
            reconciliation_warning_months=reconciliation_warning_months,
            incomplete_months=incomplete_months,
            summary=None,
            rows=[],
        )
        return payload.model_copy(update={"management_change": management_change})

    balance_comparable = current_bucket.coverage_days > 0 and previous_bucket.coverage_days > 0
    current_items = {
        item.row_key: item for item in current_bucket.items if _is_parent_monthly_business_item(item)
    }
    previous_items = {
        item.row_key: item for item in previous_bucket.items if _is_parent_monthly_business_item(item)
    }
    rows: list[PnlByBusinessMonthlyChangeRow] = []
    for row_key in sorted(
        current_items.keys() | previous_items.keys(),
        key=lambda key: (
            (current_items.get(key) or previous_items[key]).sort_order,
            key,
        ),
    ):
        current_item = current_items.get(row_key)
        previous_item = previous_items.get(row_key)
        reference_item = current_item or previous_item
        if reference_item is None:  # pragma: no cover - union guarantees a reference row
            continue
        if current_item is None or previous_item is None:
            rows.append(
                PnlByBusinessMonthlyChangeRow(
                    row_key=row_key,
                    sort_order=reference_item.sort_order,
                    business_type=reference_item.business_type,
                    comparison_available=False,
                    comparison_reason=("current_row_missing" if current_item is None else "previous_row_missing"),
                )
            )
            continue
        rows.append(
            PnlByBusinessMonthlyChangeRow(
                row_key=row_key,
                sort_order=current_item.sort_order,
                business_type=current_item.business_type,
                comparison_available=True,
                comparison_reason="available",
                **_pnl_by_business_monthly_change_metrics(
                    current_item,
                    previous_item,
                    balance_comparable=balance_comparable,
                ).model_dump(),
            )
        )

    management_change = PnlByBusinessMonthlyManagementChange(
        comparison_basis="latest_month_vs_previous_calendar_month",
        comparison_scope="requested_year",
        comparison_status=(
            "data_quality_warning"
            if warning_months or reconciliation_warning_months
            else "available"
        ),
        comparison_available=True,
        current_month_key=current_month_key,
        previous_month_key=previous_month_key,
        coverage_warning_months=warning_months,
        reconciliation_warning_months=reconciliation_warning_months,
        incomplete_months=[],
        summary=_pnl_by_business_monthly_change_metrics(
            current_bucket.summary,
            previous_bucket.summary,
            balance_comparable=balance_comparable,
        ),
        rows=rows,
    )
    return payload.model_copy(update={"management_change": management_change})


def _pnl_by_business_monthly_change_metrics(
    current: PnlByBusinessMonthlyItem | PnlByBusinessMonthlySummary,
    previous: PnlByBusinessMonthlyItem | PnlByBusinessMonthlySummary,
    *,
    balance_comparable: bool = True,
) -> PnlByBusinessMonthlyChangeMetrics:
    change = compute_pnl_by_business_monthly_change(
        current=_pnl_by_business_monthly_measure(current),
        previous=_pnl_by_business_monthly_measure(previous),
    )
    metrics = PnlByBusinessMonthlyChangeMetrics(**{
        field_name: getattr(change, field_name)
        for field_name in PnlByBusinessMonthlyChangeMetrics.model_fields
    })
    if balance_comparable:
        return metrics
    return metrics.model_copy(
        update={
            "avg_balance_delta": None,
            "current_balance_delta": None,
            "annualized_yield_delta_bp": None,
            "ftp_cost_delta": None,
            "ftp_net_pnl_delta": None,
            "ftp_net_annualized_yield_delta_bp": None,
        }
    )


def _pnl_by_business_monthly_measure(
    value: PnlByBusinessMonthlyItem | PnlByBusinessMonthlySummary,
) -> PnlByBusinessMonthlyMeasure:
    return PnlByBusinessMonthlyMeasure(
        interest_income=value.interest_income,
        fair_value_change=value.fair_value_change,
        capital_gain=value.capital_gain,
        manual_adjustment=value.manual_adjustment,
        total_pnl=value.total_pnl,
        avg_balance=value.avg_balance,
        current_balance=value.current_balance,
        annualized_yield_pct=value.annualized_yield_pct,
        ftp_cost=value.ftp_cost,
        ftp_net_pnl=value.ftp_net_pnl,
        ftp_net_annualized_yield_pct=value.ftp_net_annualized_yield_pct,
    )


def _is_calendar_month_end(value: str) -> bool:
    period_end = date.fromisoformat(value)
    return (period_end + timedelta(days=1)).day == 1


def _new_analysis_dimension_bucket(dimension_key: str, dimension_label: str) -> dict[str, object]:
    return {
        "dimension_key": dimension_key,
        "dimension_label": dimension_label,
        "interest_income": Decimal("0"),
        "fair_value_change": Decimal("0"),
        "capital_gain": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0"),
        "asset_codes": set(),
    }


def _analysis_balance_lookup(balance_rows: list[dict[str, object]]) -> dict[tuple[str, str, str, str, str], dict[str, object]]:
    lookup: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        portfolio_name = _norm_text(row.get("portfolio_name"))
        cost_center = _norm_text(row.get("cost_center"))
        currency_basis = _norm_text(row.get("currency_basis")) or "CNY"
        for code in _instrument_code_variants(row.get("instrument_code")):
            lookup.setdefault((report_date, code, portfolio_name, cost_center, currency_basis), row)
    return lookup


def _analysis_historical_balance_lookup(
    balance_rows: list[dict[str, object]],
) -> dict[tuple[str, str, str, str], list[dict[str, object]]]:
    lookup: dict[tuple[str, str, str, str], list[dict[str, object]]] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        portfolio_name = _norm_text(row.get("portfolio_name"))
        cost_center = _norm_text(row.get("cost_center"))
        currency_basis = _norm_text(row.get("currency_basis")) or "CNY"
        if not report_date:
            continue
        for code in _instrument_code_variants(row.get("instrument_code")):
            lookup.setdefault((code, portfolio_name, cost_center, currency_basis), []).append(row)
    for rows in lookup.values():
        rows.sort(key=lambda item: _norm_text(item.get("report_date")))
    return lookup


def _analysis_latest_balance_before_or_on(
    lookup: dict[tuple[str, str, str, str], list[dict[str, object]]],
    key: tuple[str, str, str, str],
    report_date: str,
) -> dict[str, object] | None:
    rows = lookup.get(key)
    if not rows or not report_date:
        return None
    latest: dict[str, object] | None = None
    for row in rows:
        row_date = _norm_text(row.get("report_date"))
        if row_date > report_date:
            break
        latest = row
    return latest


def _analysis_sub_type_by_date_code(balance_rows: list[dict[str, object]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        sub_type = _norm_text(row.get("sub_type")) or _norm_text(row.get("business_type_primary"))
        if not report_date or not sub_type:
            continue
        for code in _instrument_code_variants(row.get("instrument_code")):
            out.setdefault((report_date, code), sub_type)
    return out


def _analysis_classification_for_pnl_row(
    *,
    pnl_row: dict[str, object],
    balance_lookup: dict[tuple[str, str, str, str, str], dict[str, object]],
    sub_type_by_date_code: dict[tuple[str, str], str],
    fallback_date: str,
    historical_balance_lookup: dict[tuple[str, str, str, str], list[dict[str, object]]] | None = None,
) -> dict[str, object]:
    report_date = _norm_text(pnl_row.get("report_date"))
    portfolio_name = _norm_text(pnl_row.get("portfolio_name"))
    cost_center = _norm_text(pnl_row.get("cost_center"))
    currency_basis = _norm_text(pnl_row.get("currency_basis")) or "CNY"
    for code in _instrument_code_variants(pnl_row.get("instrument_code")):
        balance_row = balance_lookup.get((report_date, code, portfolio_name, cost_center, currency_basis))
        if balance_row is not None:
            return _analysis_classification_from_balance_row(balance_row)

    if historical_balance_lookup is not None:
        classification_date = report_date or fallback_date
        for code in _instrument_code_variants(pnl_row.get("instrument_code")):
            balance_row = _analysis_latest_balance_before_or_on(
                historical_balance_lookup,
                (code, portfolio_name, cost_center, currency_basis),
                classification_date,
            )
            if balance_row is not None:
                return _analysis_classification_from_balance_row(balance_row)

    code = _norm_text(pnl_row.get("instrument_code"))
    sub_type = sub_type_by_date_code.get((report_date, code), "") or sub_type_by_date_code.get((fallback_date, code), "")
    if _norm_text(pnl_row.get("source_kind")) == "nonstd_bridge":
        return _v1_nonstd_classification_row(report_date=report_date or fallback_date, code=code, sub_type=sub_type)
    invest = _norm_text(pnl_row.get("invest_type_std")) or "unclassified"
    source_asset_class = _norm_text(pnl_row.get("asset_class"))
    source_instrument_name = _norm_text(pnl_row.get("instrument_name"))
    classification = _v1_fi_classification_row(
        report_date=report_date or fallback_date,
        row={
            "instrument_code": code,
            "currency_basis": currency_basis,
            "currency_code": currency_basis,
            "instrument_name": source_instrument_name or code,
            "accounting_basis": _norm_text(pnl_row.get("accounting_basis")),
        },
        code=code,
        asset_class=source_asset_class or invest,
        sub_type=sub_type or source_asset_class or invest,
    )
    classification["accounting_basis"] = _norm_text(pnl_row.get("accounting_basis"))
    classification["currency_code"] = _norm_text(
        pnl_row.get("fx_base_currency") or pnl_row.get("currency_code")
    )
    return classification


def _analysis_classification_from_balance_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "report_date": _norm_text(row.get("report_date")),
        "instrument_code": _norm_text(row.get("instrument_code")),
        "instrument_name": _norm_text(row.get("instrument_name")),
        "account_category": _norm_text(row.get("account_category")),
        "asset_class": _norm_text(row.get("asset_class")),
        "bond_type": _norm_text(row.get("bond_type")),
        "sub_type": _norm_text(row.get("sub_type")),
        "business_type_primary": _norm_text(row.get("business_type_primary")),
        "business_type_final": _norm_text(row.get("business_type_final")),
        "invest_type_std": _norm_text(row.get("invest_type_std")),
        "accounting_basis": _norm_text(row.get("accounting_basis")),
        "currency_code": _norm_text(row.get("currency_code")),
    }


def _analysis_matches_business_key(classification: dict[str, object], business_key: str | None) -> bool:
    if not business_key:
        return True
    manual_key = _norm_text(classification.get("manual_business_row_key"))
    if manual_key:
        return manual_key == business_key
    return any(str(row_def.get("row_key")) == business_key for row_def in match_zqtz_asset_bond_rows(classification))


def _analysis_original_currency_dimension(
    instrument_code: object,
    currency_code: object = None,
) -> tuple[str, str]:
    if original_asset_currency_from_instrument_code(instrument_code, currency_code) == "USD":
        return "USD", "美元（折人民币）"
    return "CNY", "人民币"


def _analysis_dimension_for_pnl_row(
    row: dict[str, object],
    classification: dict[str, object],
    dimension: PnlByBusinessAnalysisDimension,
) -> tuple[str, str] | None:
    if dimension == "monthly":
        report_date = _norm_text(row.get("report_date"))
        return (report_date, report_date) if report_date else None
    if dimension == "portfolio":
        return _dimension_key_label(row.get("portfolio_name"), "未填组合")
    if dimension == "accounting":
        accounting = row.get("accounting_basis") or classification.get("accounting_basis")
        if _norm_text(accounting) == "manual_adjustment":
            return "manual_adjustment", "手工调整"
        return _dimension_key_label(accounting, "未填会计分类")
    if dimension == "currency":
        currency_code = (
            classification.get("currency_code")
            or row.get("fx_base_currency")
            or row.get("currency_code")
        )
        return _analysis_original_currency_dimension(row.get("instrument_code"), currency_code)
    if dimension == "cost_center":
        return _dimension_key_label(row.get("cost_center"), "未填成本中心")
    if dimension == "bond_bucket":
        return _analysis_bond_bucket_for_classification(classification)
    if dimension == "bond_bucket_monthly":
        report_date = _norm_text(row.get("report_date"))
        if not report_date:
            return None
        bucket_key, label = _analysis_bond_bucket_for_classification(classification)
        return f"{report_date}::{bucket_key}", f"{report_date} {label}"
    return _instrument_key_label(row.get("instrument_code"), classification.get("instrument_name"))


def _analysis_dimension_for_balance_row(
    row: dict[str, object],
    dimension: PnlByBusinessAnalysisDimension,
    month_end_by_month: dict[str, str],
) -> tuple[str, str] | None:
    if dimension == "monthly":
        report_date = _norm_text(row.get("report_date"))
        month_end = month_end_by_month.get(report_date[:7])
        return (month_end, month_end) if month_end else None
    if dimension == "portfolio":
        return _dimension_key_label(row.get("portfolio_name"), "未填组合")
    if dimension == "accounting":
        return _dimension_key_label(row.get("accounting_basis"), "未填会计分类")
    if dimension == "currency":
        currency_code = row.get("currency_code") or row.get("fx_base_currency")
        return _analysis_original_currency_dimension(row.get("instrument_code"), currency_code)
    if dimension == "cost_center":
        return _dimension_key_label(row.get("cost_center"), "未填成本中心")
    if dimension == "bond_bucket":
        return _analysis_bond_bucket_for_classification(_analysis_classification_from_balance_row(row))
    if dimension == "bond_bucket_monthly":
        report_date = _norm_text(row.get("report_date"))
        month_end = month_end_by_month.get(report_date[:7])
        if not month_end:
            return None
        bucket_key, label = _analysis_bond_bucket_for_classification(_analysis_classification_from_balance_row(row))
        return f"{month_end}::{bucket_key}", f"{month_end} {label}"
    return _instrument_key_label(row.get("instrument_code"), row.get("instrument_name"))


def _dimension_key_label(value: object, blank_label: str) -> tuple[str, str]:
    text = _norm_text(value)
    if text:
        return text, text
    return f"__blank__{blank_label}", blank_label


def _analysis_bond_bucket_for_classification(classification: dict[str, object]) -> tuple[str, str]:
    matched_keys = {str(row_def.get("row_key")) for row_def in match_zqtz_asset_bond_rows(classification)}
    for bucket_key, label, row_keys in ANALYSIS_BOND_BUCKETS:
        if matched_keys & row_keys:
            return bucket_key, label
    return "other_bond", ANALYSIS_BOND_BUCKET_LABELS["other_bond"]


def _analysis_is_monthly_dimension(dimension: PnlByBusinessAnalysisDimension) -> bool:
    return dimension in {"monthly", "bond_bucket_monthly"}


def _analysis_dimension_report_date(dimension_key: str) -> str:
    return dimension_key.split("::", 1)[0]


def _instrument_key_label(code_value: object, name_value: object) -> tuple[str, str]:
    code = _norm_text(code_value)
    name = _norm_text(name_value)
    key = code or "__blank__instrument"
    if code and name and name != code:
        return key, f"{code} {name}"
    return key, code or name or "未填资产"


def _instrument_code_variants(value: object) -> tuple[str, ...]:
    code = _norm_text(value)
    if not code:
        return tuple()
    variants = {code}
    if code.startswith("BOND-"):
        variants.add(code[5:])
    else:
        variants.add(f"BOND-{code}")
    return tuple(sorted(variants))


def _analysis_annualized_yield_pct(
    total_pnl: Decimal,
    avg_balance: Decimal,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> Decimal | None:
    return compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    ).annualized_yield_pct


def _analysis_ftp_values(
    *,
    total_pnl: Decimal,
    avg_balance: Decimal,
    annualized_yield_pct: Decimal | None,
    calendar_days: int,
    ftp_rate_pct: Decimal,
) -> dict[str, Decimal | None]:
    yield_ftp = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )
    return {
        "ftp_rate_pct": yield_ftp.ftp_rate_pct,
        "ftp_cost": yield_ftp.ftp_cost,
        "ftp_net_pnl": yield_ftp.ftp_net_pnl,
        "ftp_net_annualized_yield_pct": yield_ftp.ftp_net_annualized_yield_pct,
    }


def _calendar_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return max((end - start).days + 1, 0)


def _decimal_value(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def _norm_text(value: object) -> str:
    return str(value or "").strip()


def _build_v1_detail_rows(
    *,
    report_date: str,
    refresh_input,
    sub_type_map: dict[tuple[str, str], str],
    fx_rates: dict[str, Decimal],
) -> list[PnlV1DetailRow]:
    rows: list[PnlV1DetailRow] = []

    for row in refresh_input.fi_rows:
        code = str(row.get("instrument_code") or "").strip()
        if not code:
            continue
        asset_class = str(row.get("asset_class") or "").strip()
        fx_rate = _v1_fx_rate(row.get("fx_base_currency"), fx_rates)
        interest_income = normalize_fi_interest_income_514(
            raw_amount=row.get("interest_income_514") or "0",
            asset_class=asset_class,
            report_date=report_date,
        )
        fair_value_change = Decimal(str(row.get("fair_value_change_516") or "0"))
        capital_gain = Decimal(str(row.get("capital_gain_517") or "0")) * Decimal("-1") / V1_VAT_DIVISOR
        interest_income *= fx_rate
        fair_value_change *= fx_rate
        capital_gain *= fx_rate
        business_type = _v1_normalize_business_type(
            sub_type_map.get((report_date, code)) or asset_class,
            code,
        )
        rows.append(
            PnlV1DetailRow(
                report_date=report_date,
                source="FI",
                asset_code=code,
                bond_name=str(row.get("instrument_name") or code),
                portfolio=str(row.get("portfolio_name") or ""),
                asset_type=business_type,
                asset_class=asset_class or business_type,
                market_value=Decimal(str(row.get("market_value") or row.get("position_amount") or "0")),
                interest_income=interest_income,
                fair_value_change=fair_value_change,
                capital_gain=capital_gain,
                total_pnl=interest_income + fair_value_change + capital_gain,
                source_version=str(row.get("source_version") or ""),
                trace_id=str(row.get("trace_id") or f"v1-fi:{code}"),
            )
        )

    nonstd_groups: dict[str, dict[str, object]] = {}
    for journal_type, source_rows in refresh_input.nonstd_rows_by_type.items():
        for row in source_rows:
            voucher_date = str(row.get("voucher_date") or "").strip()
            code = str(row.get("asset_code") or "").strip()
            if not voucher_date or not code:
                continue
            if not refresh_input.is_month_end and voucher_date != report_date:
                continue
            group = nonstd_groups.setdefault(
                code,
                {
                    "interest_income": Decimal("0"),
                    "fair_value_change": Decimal("0"),
                    "capital_gain": Decimal("0"),
                    "portfolio": str(row.get("portfolio_name") or ""),
                    "source_version": "",
                    "trace_id": "",
                },
            )
            amount = compute_nonstd_signed_ledger_amount(
                raw_amount=row.get("raw_amount"),
                dc_flag=row.get("dc_flag"),
                journal_type=str(journal_type),
            )
            code_prefix = code[:2].upper()
            if str(journal_type) == V1_INTEREST_INCOME_JOURNAL_TYPE:
                amount = normalize_nonstd_interest_income_514(
                    raw_amount=amount,
                    asset_code=code,
                    voucher_date=voucher_date,
                )
            if code_prefix == "J1":
                amount = amount * _v1_fx_rate("USD", fx_rates)
            if str(journal_type) == V1_INTEREST_INCOME_JOURNAL_TYPE:
                group["interest_income"] = Decimal(str(group["interest_income"])) + amount
            elif str(journal_type) == "516":
                group["fair_value_change"] = Decimal(str(group["fair_value_change"])) + amount
            elif str(journal_type) == "517":
                group["capital_gain"] = Decimal(str(group["capital_gain"])) + amount
            _append_unique_value(group, "source_version", str(row.get("source_version") or ""))
            _append_unique_value(group, "trace_id", str(row.get("trace_id") or ""))

    for code, group in sorted(nonstd_groups.items()):
        interest_income = Decimal(str(group["interest_income"]))
        fair_value_change = Decimal(str(group["fair_value_change"]))
        capital_gain = Decimal(str(group["capital_gain"]))
        asset_class = sub_type_map.get((report_date, code)) or _v1_nonstd_display_name(code)
        rows.append(
            PnlV1DetailRow(
                report_date=report_date,
                source="NonStd",
                asset_code=code,
                bond_name=code,
                portfolio=str(group.get("portfolio") or ""),
                asset_type="H" if interest_income > Decimal("0") else "T",
                asset_class=asset_class,
                market_value=Decimal("0"),
                interest_income=interest_income,
                fair_value_change=fair_value_change,
                capital_gain=capital_gain,
                total_pnl=interest_income + fair_value_change + capital_gain,
                source_version=str(group.get("source_version") or ""),
                trace_id=str(group.get("trace_id") or f"v1-nonstd:{code}"),
            )
        )

    return rows


def _iter_v1_compatible_pnl_records(
    *,
    report_date: str,
    refresh_input,
    sub_type_map: dict[tuple[str, str], str],
    fx_rates: dict[str, Decimal],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in refresh_input.fi_rows:
        code = str(row.get("instrument_code") or "").strip()
        if not code:
            continue
        asset_class = str(row.get("asset_class") or "")
        fx_rate = _v1_fx_rate(row.get("fx_base_currency"), fx_rates)
        interest_income = normalize_fi_interest_income_514(
            raw_amount=row.get("interest_income_514") or "0",
            asset_class=asset_class,
            report_date=report_date,
        )
        fair_value_change = Decimal(str(row.get("fair_value_change_516") or "0"))
        capital_gain = Decimal(str(row.get("capital_gain_517") or "0")) * Decimal("-1") / V1_VAT_DIVISOR
        sub_type = sub_type_map.get((report_date, code)) or ""
        records.append(
            _v1_record(
                report_date=report_date,
                bond_code=code,
                raw_business_type=sub_type_map.get((report_date, code)) or asset_class or "未分类",
                interest_income=interest_income * fx_rate,
                fair_value_change=fair_value_change * fx_rate,
                capital_gain=capital_gain * fx_rate,
                source_version=str(row.get("source_version") or ""),
                classification_row=_v1_fi_classification_row(
                    report_date=report_date,
                    row=row,
                    code=code,
                    asset_class=asset_class,
                    sub_type=sub_type,
                ),
            )
        )

    nonstd_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for journal_type, rows in refresh_input.nonstd_rows_by_type.items():
        for row in rows:
            voucher_date = str(row.get("voucher_date") or "").strip()
            code = str(row.get("asset_code") or "").strip()
            if not voucher_date or not code:
                continue
            key = (voucher_date, code)
            bucket = nonstd_by_key.setdefault(
                key,
                {
                    "interest_income": Decimal("0"),
                    "fair_value_change": Decimal("0"),
                    "capital_gain": Decimal("0"),
                    "source_version": "",
                },
            )
            amount = compute_nonstd_signed_ledger_amount(
                raw_amount=row.get("raw_amount"),
                dc_flag=row.get("dc_flag"),
                journal_type=str(journal_type),
            )
            code_prefix = code[:2].upper()
            if str(journal_type) == V1_INTEREST_INCOME_JOURNAL_TYPE:
                amount = normalize_nonstd_interest_income_514(
                    raw_amount=amount,
                    asset_code=code,
                    voucher_date=voucher_date,
                )
            if code_prefix == "J1":
                amount = amount * _v1_fx_rate("USD", fx_rates)
            if str(journal_type) == V1_INTEREST_INCOME_JOURNAL_TYPE:
                bucket["interest_income"] = Decimal(str(bucket["interest_income"])) + amount
            elif str(journal_type) == "516":
                bucket["fair_value_change"] = Decimal(str(bucket["fair_value_change"])) + amount
            elif str(journal_type) == "517":
                bucket["capital_gain"] = Decimal(str(bucket["capital_gain"])) + amount
            _append_unique_value(bucket, "source_version", str(row.get("source_version") or ""))

    for (voucher_date, code), row in nonstd_by_key.items():
        records.append(
            _v1_record(
                report_date=voucher_date,
                bond_code=code,
                raw_business_type=sub_type_map.get((voucher_date, code)) or _v1_nonstd_display_name(code),
                interest_income=Decimal(str(row["interest_income"])),
                fair_value_change=Decimal(str(row["fair_value_change"])),
                capital_gain=Decimal(str(row["capital_gain"])),
                source_version=str(row["source_version"]),
                classification_row=_v1_nonstd_classification_row(
                    report_date=voucher_date,
                    code=code,
                    sub_type=sub_type_map.get((voucher_date, code)) or "",
                ),
            )
        )
    return records


def _v1_record(
    *,
    report_date: str,
    bond_code: str,
    raw_business_type: str,
    interest_income: Decimal,
    fair_value_change: Decimal,
    capital_gain: Decimal,
    source_version: str,
    classification_row: dict[str, object],
) -> dict[str, object]:
    return {
        "report_date": report_date,
        "business_type": _v1_normalize_business_type(raw_business_type, bond_code),
        "bond_code": bond_code,
        "interest_income": interest_income,
        "fair_value_change": fair_value_change,
        "capital_gain": capital_gain,
        "manual_adjustment": Decimal("0"),
        "total_pnl": interest_income + fair_value_change + capital_gain,
        "source_version": source_version,
        "classification_row": classification_row,
    }


def _new_balance_movement_pnl_group(row_def: dict[str, object]) -> dict[str, object]:
    return {
        "row_key": str(row_def["row_key"]),
        "sort_order": int(row_def["sort_order"]),
        "business_type": str(row_def["row_label"]),
        "source_note": str(row_def.get("source_note") or "ZQTZ_ASSET_BOND_ROWS"),
        "interest_income": Decimal("0"),
        "fair_value_change": Decimal("0"),
        "capital_gain": Decimal("0"),
        "manual_adjustment": Decimal("0"),
        "total_pnl": Decimal("0"),
        "asset_codes": set(),
        "row_count": 0,
    }


def _merge_balance_movement_business_record(
    groups: dict[str, dict[str, object]],
    row_def: dict[str, object],
    record: dict[str, object],
) -> None:
    row_key = str(row_def["row_key"])
    group = groups.setdefault(row_key, _new_balance_movement_pnl_group(row_def))
    for key in ("interest_income", "fair_value_change", "capital_gain", "manual_adjustment", "total_pnl"):
        group[key] = Decimal(str(group[key])) + Decimal(str(record[key]))
    code = str(record.get("bond_code") or "").strip()
    if code:
        group["asset_codes"].add(code)
    group["row_count"] = int(group["row_count"]) + 1


def _merge_v1_business_record(groups: dict[str, dict[str, object]], record: dict[str, object]) -> None:
    business_type = str(record["business_type"])
    group = groups.setdefault(
        business_type,
        {
            "interest_income": Decimal("0"),
            "fair_value_change": Decimal("0"),
            "capital_gain": Decimal("0"),
            "total_pnl": Decimal("0"),
            "asset_codes": set(),
            "row_count": 0,
        },
    )
    for key in ("interest_income", "fair_value_change", "capital_gain", "total_pnl"):
        group[key] = Decimal(str(group[key])) + Decimal(str(record[key]))
    code = str(record.get("bond_code") or "").strip()
    if code:
        group["asset_codes"].add(code)
    group["row_count"] = int(group["row_count"]) + 1


def _v1_fi_classification_row(
    *,
    report_date: str,
    row: dict[str, object],
    code: str,
    asset_class: str,
    sub_type: str,
) -> dict[str, object]:
    currency_code = str(row.get("fx_base_currency") or row.get("currency_code") or row.get("currency_basis") or "CNY")
    return {
        "report_date": report_date,
        "instrument_code": code,
        "sub_type": sub_type,
        "business_type_final": sub_type,
        "business_type_primary": sub_type or asset_class,
        "bond_type": asset_class or sub_type,
        "instrument_name": str(row.get("instrument_name") or row.get("bond_name") or code),
        "asset_class": asset_class,
        "currency_code": currency_code.strip().upper() or "CNY",
    }


def _v1_nonstd_classification_row(*, report_date: str, code: str, sub_type: str) -> dict[str, object]:
    bond_type = _zqtz_other_bond_type()
    code_u = code.upper()
    return {
        "report_date": report_date,
        "instrument_code": code,
        "sub_type": sub_type,
        "business_type_final": sub_type,
        "business_type_primary": bond_type,
        "bond_type": bond_type,
        "instrument_name": code,
        "asset_class": sub_type or bond_type,
        "currency_code": "USD" if code_u.startswith("J1") else "CNY",
    }


def _zqtz_other_bond_type() -> str:
    for row_def in ZQTZ_ASSET_BOND_ROWS:
        if row_def.get("row_key") == "asset_zqtz_non_bottom_investment":
            bond_types = tuple(str(value) for value in row_def.get("bond_types", ()))
            if bond_types:
                return bond_types[0]
    return "其他"


def _balance_yield_pct(total_pnl: Decimal, current_balance: Decimal) -> Decimal | None:
    if current_balance == Decimal("0"):
        return None
    return _quantize_yield_pct((total_pnl / current_balance) * Decimal("100"))


def _v1_normalize_business_type(raw_business_type: object, bond_code: object) -> str:
    normalized = V1_BUSINESS_NAME_NORMALIZATION.get(
        str(raw_business_type or "").strip(),
        str(raw_business_type or "").strip() or "其他债券",
    )
    if normalized != "其他债券":
        return normalized
    code = str(bond_code or "").strip().upper()
    if len(code) >= 2:
        return V1_ZQTZ_PREFIX_MAP.get(code[:2], "其他债券")
    return "其他债券"


def _v1_nonstd_display_name(asset_code: object) -> str:
    code = str(asset_code or "").strip()
    if not code or code.lower() in {"nan", "none"}:
        return "未标注"
    for prefix, name in (
        ("J0", "人民币资管产品"),
        ("JM", "债权投资"),
        ("J4", "结构化产业基金"),
        ("J1", "美元委外"),
        ("SA", "公募基金"),
        ("G0", "结构化融资"),
        ("G2", "信托产品"),
    ):
        if code.startswith(prefix):
            return name
    return "其他"


def _v1_fx_rate(base_currency: object, fx_rates: dict[str, Decimal]) -> Decimal:
    key = str(base_currency or "").strip().upper()
    if not key:
        return Decimal("1")
    return fx_rates[key]


def _append_unique_value(bucket: dict[str, object], key: str, value: str) -> None:
    if not value:
        return
    existing = str(bucket.get(key) or "")
    values = [part for part in existing.split("__") if part]
    if value not in values:
        values.append(value)
    bucket[key] = "__".join(values)


def _coverage_quality_flag(coverage_days: int, expected_days: int) -> str | None:
    if expected_days > 0 and coverage_days < expected_days:
        return "warning"
    return None


def _pnl_by_business_ytd_quality_flag(payload: PnlByBusinessYtdPayload) -> str | None:
    if _coverage_quality_flag(payload.coverage_days, payload.expected_days):
        return "warning"
    if payload.unallocated_row_count > 0 or payload.reconciliation_delta != Decimal("0"):
        return "warning"
    return None


def _pnl_by_business_monthly_quality_flag(payload: PnlByBusinessMonthlyPayload) -> str | None:
    for bucket in payload.months:
        if _coverage_quality_flag(bucket.coverage_days, bucket.expected_days):
            return "warning"
        if bucket.unallocated_row_count > 0 or bucket.reconciliation_delta != Decimal("0"):
            return "warning"
    return None


def _build_pnl_by_business_analytical_result_envelope(
    *,
    governance_dir: str,
    requested_report_date: str | None,
    resolved_report_date: str,
    trace_id: str,
    result_kind: str,
    result_payload: dict[str, object],
    quality_flag: str | None = None,
    filters_applied: dict[str, object] | None = None,
) -> dict[str, object]:
    fallback_used = bool(requested_report_date and requested_report_date != resolved_report_date)
    effective_quality_flag = quality_flag
    if fallback_used and effective_quality_flag != "error":
        effective_quality_flag = "warning"
    envelope = _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=resolved_report_date,
        trace_id=trace_id,
        result_kind=result_kind,
        result_payload=result_payload,
        quality_flag=effective_quality_flag,
    )
    meta = envelope.get("result_meta")
    if not isinstance(meta, dict):
        meta = {}
        envelope["result_meta"] = meta
    lineage_fallback_mode = meta.get("fallback_mode", "none")
    lineage_fallback_date = meta.get("fallback_date")
    source_tables = result_payload.get("source_tables")
    meta.update(
        {
            "basis": "analytical",
            "formal_use_allowed": False,
            "requested_report_date": requested_report_date or resolved_report_date,
            "resolved_report_date": resolved_report_date,
            "as_of_date": resolved_report_date,
            "fallback_date": resolved_report_date if fallback_used else lineage_fallback_date,
            "fallback_mode": "latest_snapshot" if fallback_used else lineage_fallback_mode,
            "date_basis": "formal_report_date_cutoff",
            "filters_applied": filters_applied or {},
            "tables_used": list(source_tables) if isinstance(source_tables, list) else [],
            "source_surface": "formal_pnl",
        }
    )
    return envelope


def _build_pnl_formal_result_envelope_from_lineage(
    *,
    governance_dir: str,
    report_date: str | None,
    trace_id: str,
    result_kind: str,
    result_payload: dict[str, object],
    quality_flag: str | None = None,
) -> dict[str, object]:
    lineage = resolve_formal_manifest_lineage_with_completed_build(
        governance_dir=governance_dir,
        cache_key=PNL_CACHE_KEY,
        job_name=PNL_JOB_NAME,
        report_date=report_date,
    )
    lineage_fallback = lineage.get("_lineage_fallback_mode") == "latest_snapshot"
    effective_quality_flag = quality_flag
    if lineage_fallback and effective_quality_flag != "error":
        effective_quality_flag = "stale"
    fallback_date = None
    if lineage_fallback:
        fallback_date = str(lineage.get("_lineage_fallback_date") or "").strip() or None
    return build_formal_result_envelope_from_lineage_runtime(
        trace_id=trace_id,
        result_kind=result_kind,
        lineage=lineage,
        default_cache_version=PNL_CACHE_VERSION,
        use_lineage_cache_version=False,
        result_payload=result_payload,
        quality_flag=effective_quality_flag,
        fallback_mode="latest_snapshot" if lineage_fallback else "none",
        requested_report_date=report_date,
        resolved_report_date=report_date,
        as_of_date=report_date,
        fallback_date=fallback_date,
    )


def _quantize_decimal(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES)


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIOPLACES)


def _quantize_yield_pct(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"))


def _quantized_business_row(row: dict[str, object]) -> dict[str, object]:
    out = dict(row)
    for key in (
        "interest_income_514",
        "fair_value_change_516",
        "capital_gain_517",
        "manual_adjustment",
        "total_pnl",
        "scale_amount",
    ):
        out[key] = _quantize_decimal(Decimal(str(out.get(key) or "0")))
    out["yield_pct"] = _quantize_yield_pct(out.get("yield_pct"))
    out["pnl_row_count"] = int(out.get("pnl_row_count") or 0)
    out["balance_row_count"] = int(out.get("balance_row_count") or 0)
    return out


def _json_safe_payload(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_payload(item) for key, item in value.items()}
    return value


def _pnl_overview_reconciliation_check(totals: dict[str, Decimal]) -> dict[str, object]:
    component_total = (
        totals["interest_income_514"]
        + totals["fair_value_change_516"]
        + totals["capital_gain_517"]
        + totals["manual_adjustment"]
    )
    return pnl_vs_ledger_diff(
        pnl_total=totals["total_pnl"],
        ledger_pnl_total=component_total,
        threshold_yuan=Decimal("0.01"),
    )


def _build_run_id() -> str:
    return f"{PNL_JOB_NAME}:{datetime.now(UTC).isoformat()}"


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


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _latest_refresh_for_idempotency_key(
    settings: Settings,
    *,
    report_date: str,
    idempotency_key: str,
) -> dict[str, object] | None:
    for record in reversed(_load_refresh_run_records(settings)):
        if str(record.get("report_date")) != report_date:
            continue
        if str(record.get("idempotency_key") or "").strip() != idempotency_key:
            continue
        if str(record.get("status")) in IN_FLIGHT_STATUSES and _is_stale_inflight_record(record):
            _mark_stale_inflight_run(
                settings=settings,
                run_id=str(record.get("run_id")),
                report_date=report_date,
                error_message="Marked stale pnl idempotent refresh run as failed.",
            )
            return None
        return record
    return None


def _idempotent_refresh_response(record: dict[str, object]) -> dict[str, object]:
    status = str(record.get("status") or "queued")
    return {
        **record,
        "status": status,
        "run_id": str(record.get("run_id") or ""),
        "job_name": PNL_JOB_NAME,
        "trigger_mode": "async" if status in IN_FLIGHT_STATUSES else "terminal",
        "cache_key": CACHE_KEY,
        "idempotency_replay": True,
    }


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
        return datetime.now(UTC) - timestamp > STALE_IN_FLIGHT_AFTER
    return False


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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
            "finished_at": datetime.now(UTC).isoformat(),
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
    exc: Exception,
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
            "error_message": _dispatch_failure_message(exc),
            "failure_category": type(exc).__name__,
            "failure_reason": str(exc),
        },
    )


def _dispatch_failure_message(exc: Exception) -> str:
    return f"Pnl refresh queue dispatch failed: {type(exc).__name__}: {exc}"
