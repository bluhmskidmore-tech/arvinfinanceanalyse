from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from uuid import uuid4

from backend.app.core_finance.field_normalization import is_approved_status
from backend.app.core_finance.pnl import compute_nonstd_signed_ledger_amount
from backend.app.core_finance.reconciliation_checks import pnl_vs_ledger_diff
from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS, match_zqtz_asset_bond_rows
from backend.app.governance.formal_compute_lineage import (
    resolve_completed_formal_build_lineage,
    resolve_formal_manifest_lineage,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.accounting_asset_movement_repo import AccountingAssetMovementRepository
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.pnl import (
    PnlByBusinessPayload,
    PnlByBusinessAnalysisDimension,
    PnlByBusinessAnalysisPayload,
    PnlByBusinessAnalysisRow,
    PnlByBusinessManualAdjustmentListPayload,
    PnlByBusinessManualAdjustmentPayload,
    PnlByBusinessManualAdjustmentRequest,
    PnlByBusinessMonthlyBucket,
    PnlByBusinessMonthlyItem,
    PnlByBusinessMonthlyPayload,
    PnlByBusinessMonthlySummary,
    PnlByBusinessRow,
    PnlByBusinessSummary,
    PnlByBusinessYtdItem,
    PnlByBusinessYtdPayload,
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
from backend.app.services.pnl_source_service import (
    list_pnl_refresh_report_dates,
    load_latest_pnl_refresh_input,
    resolve_pnl_data_input_root,
)
from backend.app.tasks.pnl_materialize import (
    CACHE_KEY,
    PNL_MATERIALIZE_LOCK,
    PNL_RESULT_CACHE_VERSION,
    materialize_pnl_facts,
    run_pnl_materialize_sync,
)

PNL_CACHE_KEY = CACHE_KEY
PNL_CACHE_VERSION = PNL_RESULT_CACHE_VERSION
PNL_JOB_NAME = "pnl_materialize"
PENDING_SOURCE_VERSION = "sv_pnl_pending"
TWOPLACES = Decimal("0.01")
RATIOPLACES = Decimal("0.000001")
FTP_RATE_PCT = Decimal("1.600000")
FTP_RATE_RATIO = Decimal("0.016")
PNL_BY_BUSINESS_PRECOMPUTE_TABLE = "fact_pnl_by_business_precompute"
PNL_BY_BUSINESS_ADJUSTMENT_STREAM = "pnl_by_business_adjustments"
PNL_BY_BUSINESS_PRECOMPUTE_SOURCE_VERSION = "sv_pnl_by_business_precompute_v1"
PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION = "rv_pnl_by_business_precompute_v1"
PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS: tuple[PnlByBusinessAnalysisDimension, ...] = (
    "bond_bucket",
    "bond_bucket_monthly",
)
PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS: tuple[PnlByBusinessAnalysisDimension, ...] = (
    "monthly",
    "portfolio",
    "accounting",
    "cost_center",
    "instrument",
)
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
V1_VAT_DIVISOR = Decimal("1.06")
V1_FI_TAXABLE_BOND_TYPES = (
    "同业存单",
    "存单",
    "短期融资券",
    "短融",
    "中期票据",
    "中票",
    "企业债",
    "资产支持证券",
    "ABS",
    "铁道债",
    "铁道",
)
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


def refresh_pnl(settings: Settings, *, report_date: str | None = None) -> dict[str, object]:
    _clear_pnl_by_business_analysis_cache()
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
    fx_rates = repo.fetch_latest_fx_rates(target_report_date, base_currencies)
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
    repo = PnlRepository(duckdb_path)
    if report_date not in repo.list_formal_fi_report_dates():
        raise ValueError(f"No formal pnl data found for report_date={report_date} in fact_formal_pnl_fi.")

    rows = [PnlByBusinessRow(**_quantized_business_row(row)) for row in repo.fetch_by_business_rows(report_date)]
    untraced_count = repo.count_untraced_formal_fi_rows(report_date)
    payload = PnlByBusinessPayload(
        report_date=report_date,
        source_tables=["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily"],
        summary=PnlByBusinessSummary(
            business_count=len(rows),
            total_pnl=_quantize_decimal(sum((row.total_pnl for row in rows), Decimal("0"))),
            total_scale_amount=_quantize_decimal(sum((row.scale_amount for row in rows), Decimal("0"))),
            traced_pnl_row_count=sum(row.pnl_row_count for row in rows if row.balance_row_count > 0),
            untraced_pnl_row_count=untraced_count,
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


def _build_pnl_by_business_ytd_payload_from_groups(
    *,
    year: int,
    loaded_dates: list[str],
    total_pnl: Decimal,
    groups: dict[str, dict[str, object]],
    duckdb_path: str,
    source_tables: list[str],
) -> PnlByBusinessYtdPayload:
    balance_rows = AccountingAssetMovementRepository(duckdb_path).fetch_zqtz_asset_business_rows(
        report_date=max(loaded_dates),
        currency_basis="CNX",
    )
    balance_by_key = {str(row["row_key"]): row for row in balance_rows}
    items = [
        PnlByBusinessYtdItem(
            row_key=str(group["row_key"]),
            sort_order=int(group["sort_order"]),
            business_type=str(group["business_type"]),
            interest_income=_quantize_decimal(Decimal(str(group["interest_income"]))),
            fair_value_change=_quantize_decimal(Decimal(str(group["fair_value_change"]))),
            capital_gain=_quantize_decimal(Decimal(str(group["capital_gain"]))),
            manual_adjustment=_quantize_decimal(Decimal(str(group.get("manual_adjustment") or "0"))),
            total_pnl=_quantize_decimal(Decimal(str(group["total_pnl"]))),
            current_balance=_quantize_decimal(
                Decimal(str(balance_by_key.get(str(group["row_key"]), {}).get("current_balance") or "0"))
            ),
            balance_yield_pct=_balance_yield_pct(
                Decimal(str(group["total_pnl"])),
                Decimal(str(balance_by_key.get(str(group["row_key"]), {}).get("current_balance") or "0")),
            ),
            source_kind=str(balance_by_key.get(str(group["row_key"]), {}).get("source_kind") or "zqtz"),
            source_note=str(balance_by_key.get(str(group["row_key"]), {}).get("source_note") or group["source_note"]),
            proportion=(
                _quantize_ratio(Decimal(str(group["total_pnl"])) / total_pnl)
                if total_pnl != Decimal("0")
                else None
            ),
            assets_count=len(group["asset_codes"]) if group["asset_codes"] else int(group["row_count"]),
        )
        for group in sorted(groups.values(), key=lambda item: (int(item["sort_order"]), str(item["row_key"])))
    ]
    start_month = min(loaded_dates)[:7]
    end_month = max(loaded_dates)[:7]
    period_start_date = f"{start_month}-01"
    period_end_date = max(loaded_dates)
    return PnlByBusinessYtdPayload(
        year=year,
        period_label=f"{year}年{start_month[-2:]}-{end_month[-2:]}月累计" if start_month != end_month else f"{year}年{end_month[-2:]}月累计",
        period_start_date=period_start_date,
        period_end_date=period_end_date,
        total_pnl=_quantize_decimal(total_pnl),
        source_tables=source_tables,
        items=items,
    )


def _load_pnl_by_business_manual_adjustment_events(settings: Settings) -> list[dict[str, object]]:
    rows = GovernanceRepository(base_dir=settings.governance_path).read_all(PNL_BY_BUSINESS_ADJUSTMENT_STREAM)
    events: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        adjustment_id = str(row.get("adjustment_id") or "").strip() or f"legacy-{index}"
        events.append(
            {
                "adjustment_id": adjustment_id,
                "event_type": str(row.get("event_type") or "legacy"),
                "created_at": str(row.get("created_at") or ""),
                "stream": PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
                "report_date": str(row.get("report_date") or ""),
                "row_key": str(row.get("row_key") or ""),
                "business_type": str(row.get("business_type") or ""),
                "operator": str(row.get("operator") or "DELTA"),
                "approval_status": str(row.get("approval_status") or ""),
                "manual_adjustment": row.get("manual_adjustment") or "0",
                "reason": str(row.get("reason") or ""),
            }
        )
    return events


def _reduce_latest_pnl_by_business_manual_adjustments(events: list[dict[str, object]]) -> list[dict[str, object]]:
    latest_by_id: dict[str, dict[str, object]] = {}
    for event in events:
        adjustment_id = str(event.get("adjustment_id") or "")
        existing = latest_by_id.get(adjustment_id)
        if existing is None or str(event.get("created_at") or "") >= str(existing.get("created_at") or ""):
            latest_by_id[adjustment_id] = event
    return list(latest_by_id.values())


def _active_pnl_by_business_manual_adjustments(settings: Settings, *, report_date: str) -> list[dict[str, object]]:
    return [
        record
        for record in _reduce_latest_pnl_by_business_manual_adjustments(
            _load_pnl_by_business_manual_adjustment_events(settings)
        )
        if str(record.get("report_date") or "") == report_date
        and is_approved_status(str(record.get("approval_status") or ""))
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
    adjustment = _decimal_value(manual_adjustment)
    return {
        "source_kind": "manual_adjustment",
        "report_date": report_date,
        "instrument_code": f"manual::{row_key}",
        "portfolio_name": "manual_adjustment",
        "cost_center": "manual_adjustment",
        "currency_basis": "CNY",
        "invest_type_std": "",
        "accounting_basis": "manual_adjustment",
        "interest_income_514": Decimal("0"),
        "fair_value_change_516": Decimal("0"),
        "capital_gain_517": Decimal("0"),
        "manual_adjustment": adjustment,
        "total_pnl": adjustment,
        "manual_business_row_key": row_key,
        "manual_business_type": business_type,
        "source_note": source_note,
    }


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
) -> Decimal:
    adjusted_total = total_pnl
    for report_date in loaded_dates:
        for adjustment in _active_pnl_by_business_manual_adjustments(settings, report_date=report_date):
            row_def = _manual_adjustment_row_def(adjustment)
            record = {
                "bond_code": f"manual::{adjustment['adjustment_id']}",
                "interest_income": Decimal("0"),
                "fair_value_change": Decimal("0"),
                "capital_gain": Decimal("0"),
                "manual_adjustment": _decimal_value(adjustment.get("manual_adjustment")),
                "total_pnl": _decimal_value(adjustment.get("manual_adjustment")),
            }
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


def _pnl_by_business_ytd_from_formal_facts(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    """年度累计：按 fact_formal_pnl_fi + fact_nonstd_pnl_bridge 汇总至 ``as_of_date``，再按 ZQTZ 桶拆分（与物化正式口径一致）。"""
    if not as_of_date.startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_of_date} is outside requested year={year}.")
    repo = PnlRepository(duckdb_path)
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= as_of_date
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_of_date}.")

    merged: dict[tuple[str, str, str, str, str], dict[str, object]] = {}

    def _norm(value: object) -> str:
        return str(value or "").strip()

    def _accumulate(row: dict[str, object], *, source_kind: str) -> None:
        key = (
            source_kind,
            _norm(row.get("instrument_code")),
            _norm(row.get("portfolio_name")),
            _norm(row.get("cost_center")),
            _norm(row.get("currency_basis")) or "CNY",
        )
        bucket = merged.setdefault(
            key,
            {
                "interest_income_514": Decimal("0"),
                "fair_value_change_516": Decimal("0"),
                "capital_gain_517": Decimal("0"),
                "manual_adjustment": Decimal("0"),
                "total_pnl": Decimal("0"),
                "invest_type_std": "",
                "source_kind": source_kind,
            },
        )
        for col in ("interest_income_514", "fair_value_change_516", "capital_gain_517", "manual_adjustment", "total_pnl"):
            bucket[col] = Decimal(str(bucket[col])) + Decimal(str(row.get(col) or "0"))
        inv = _norm(row.get("invest_type_std"))
        if inv:
            bucket["invest_type_std"] = inv

    for row in repo.fetch_formal_fi_ytd_by_position(year=year, as_of_date=as_of_date):
        _accumulate(row, source_kind="formal_fi")
    for row in repo.fetch_nonstd_bridge_ytd_by_position(year=year, as_of_date=as_of_date):
        _accumulate(row, source_kind="nonstd_bridge")

    if not merged:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={as_of_date}.")

    sub_type_map = repo.fetch_zqtz_sub_type_map(sorted({as_of_date, *loaded_dates}))

    groups: dict[str, dict[str, object]] = {
        str(row_def["row_key"]): _new_balance_movement_pnl_group(row_def) for row_def in ZQTZ_ASSET_BOND_ROWS
    }
    total_pnl = Decimal("0")

    for key in sorted(merged.keys()):
        source_kind, inst, portfolio_name, cost_center, curr = key
        row = merged[key]
        interest = Decimal(str(row["interest_income_514"]))
        fair = Decimal(str(row["fair_value_change_516"]))
        capital = Decimal(str(row["capital_gain_517"]))
        manual_adjustment = Decimal(str(row["manual_adjustment"]))
        total = Decimal(str(row["total_pnl"]))
        invest = str(row.get("invest_type_std") or "").strip()
        sub_type = sub_type_map.get((as_of_date, inst), "") or sub_type_map.get((loaded_dates[-1], inst), "")
        if source_kind == "nonstd_bridge":
            classification = _v1_nonstd_classification_row(
                report_date=as_of_date,
                code=inst,
                sub_type=sub_type,
            )
        else:
            classification = _v1_fi_classification_row(
                report_date=as_of_date,
                row={
                    "instrument_code": inst,
                    "fx_base_currency": curr,
                    "currency_basis": curr,
                    "instrument_name": inst,
                },
                code=inst,
                asset_class=invest or "未分类",
                sub_type=sub_type or invest or "未分类",
            )
        record = {
            "report_date": as_of_date,
            "bond_code": inst,
            "interest_income": interest,
            "fair_value_change": fair,
            "capital_gain": capital,
            "manual_adjustment": manual_adjustment,
            "total_pnl": total,
            "classification_row": classification,
        }
        total_pnl += total
        for row_def in match_zqtz_asset_bond_rows(classification):
            _merge_balance_movement_business_record(groups, row_def, record)

    settings = get_settings()
    total_pnl = _apply_pnl_by_business_manual_adjustments_to_ytd_groups(
        settings=settings,
        groups=groups,
        total_pnl=total_pnl,
        loaded_dates=loaded_dates,
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
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=max(loaded_dates),
        trace_id=f"tr_pnl_by_business_ytd_{year}_{as_of_date}",
        result_kind="pnl.by_business_ytd",
        result_payload=payload.model_dump(mode="json"),
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
        fx_rates = repo.fetch_latest_fx_rates(report_date, base_currencies)
        missing_fx = sorted(currency for currency in base_currencies if currency not in fx_rates)
        if missing_fx:
            raise RuntimeError(f"Missing fx rates for report_date={report_date}: {missing_fx}")

        for record in _iter_v1_compatible_pnl_records(
            report_date=report_date,
            refresh_input=refresh_input,
            sub_type_map=sub_type_map,
            fx_rates=fx_rates,
        ):
            total_pnl += Decimal(str(record["total_pnl"]))
            for row_def in match_zqtz_asset_bond_rows(record.get("classification_row", {})):
                _merge_balance_movement_business_record(groups, row_def, record)

    if not loaded_dates:
        raise ValueError(f"No V1-compatible pnl source bundle found for year={year}.")

    settings = get_settings()
    total_pnl = _apply_pnl_by_business_manual_adjustments_to_ytd_groups(
        settings=settings,
        groups=groups,
        total_pnl=total_pnl,
        loaded_dates=loaded_dates,
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
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=max(loaded_dates),
        trace_id=f"tr_pnl_by_business_ytd_{year}" if not as_of_date else f"tr_pnl_by_business_ytd_{year}_{as_of_date}",
        result_kind="pnl.by_business_ytd",
        result_payload=payload.model_dump(mode="json"),
    )


def pnl_by_business_ytd_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    return _cached_pnl_by_business_ytd_envelope(
        str(duckdb_path),
        str(governance_dir),
        int(year),
        str(as_of_date or ""),
    )


@lru_cache(maxsize=32)
def _cached_pnl_by_business_ytd_envelope(
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date_cache_key: str,
) -> dict[str, object]:
    return _pnl_by_business_ytd_envelope_uncached(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date_cache_key or None,
    )


def clear_pnl_by_business_ytd_cache() -> None:
    _cached_pnl_by_business_ytd_envelope.cache_clear()


def create_pnl_by_business_manual_adjustment(
    settings: Settings,
    payload: PnlByBusinessManualAdjustmentRequest,
) -> dict[str, object]:
    created_at = datetime.now(UTC).isoformat()
    record = PnlByBusinessManualAdjustmentPayload(
        adjustment_id=f"pba-{uuid4()}",
        event_type="created",
        created_at=created_at,
        stream=PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        **payload.model_dump(),
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
    updated = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            **payload.model_dump(),
            "event_type": "edited",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        updated.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    return updated.model_dump(mode="json")


def revoke_pnl_by_business_manual_adjustment(settings: Settings, *, adjustment_id: str) -> dict[str, object]:
    current = _require_pnl_by_business_manual_adjustment(settings, adjustment_id)
    if str(current.get("approval_status") or "") == "rejected":
        return PnlByBusinessManualAdjustmentPayload.model_validate(current).model_dump(mode="json")
    revoked = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "revoked",
            "created_at": datetime.now(UTC).isoformat(),
            "approval_status": "rejected",
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        revoked.model_dump(mode="json"),
    )
    _clear_pnl_by_business_manual_adjustment_caches()
    return revoked.model_dump(mode="json")


def restore_pnl_by_business_manual_adjustment(settings: Settings, *, adjustment_id: str) -> dict[str, object]:
    current = _require_pnl_by_business_manual_adjustment(settings, adjustment_id)
    if str(current.get("approval_status") or "") == "approved":
        return PnlByBusinessManualAdjustmentPayload.model_validate(current).model_dump(mode="json")
    restored = PnlByBusinessManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "restored",
            "created_at": datetime.now(UTC).isoformat(),
            "approval_status": "approved",
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
    repo = PnlRepository(duckdb_path)
    settings = get_settings()
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    use_formal = (
        settings.pnl_by_business_ytd_prefer_formal_facts
        and bool(as_cap)
        and str(as_cap).startswith(f"{year:04d}-")
        and repo.formal_pnl_ytd_has_rows(year=year, as_of_date=str(as_cap))
    )
    if use_formal:
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
    repo: PnlRepository,
    *,
    year: int,
    as_of_date: str,
    result_kind: str,
    dimension: str,
    business_key: str,
) -> dict[str, object] | None:
    fetcher = getattr(repo, "fetch_pnl_by_business_precompute", None)
    if not callable(fetcher):
        return None
    return fetcher(
        year=year,
        as_of_date=as_of_date,
        result_kind=result_kind,
        dimension=dimension,
        business_key=business_key,
    )


def pnl_by_business_analysis_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
    business_key: str | None = None,
    dimension: PnlByBusinessAnalysisDimension = "monthly",
) -> dict[str, object]:
    repo = PnlRepository(duckdb_path)
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    if not as_cap:
        raise ValueError(f"No formal pnl rows found for year={year}.")
    if not str(as_cap).startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_cap} is outside requested year={year}.")

    period_end = repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=str(as_cap))
    if period_end is None:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    precomputed = _fetch_pnl_by_business_precompute(
        repo,
        year=year,
        as_of_date=period_end,
        result_kind="analysis",
        dimension=dimension,
        business_key=str(business_key or "").strip(),
    )
    if precomputed is not None:
        payload = PnlByBusinessAnalysisPayload.model_validate(precomputed)
        return _build_pnl_formal_result_envelope_from_lineage(
            governance_dir=governance_dir,
            report_date=period_end,
            trace_id=f"tr_pnl_by_business_analysis_{year}_{period_end}_{dimension}_precomputed",
            result_kind="pnl.by_business_analysis",
            result_payload=payload.model_dump(mode="json"),
        )
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= period_end
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")

    period_start = f"{min(loaded_dates)[:7]}-01"
    pnl_rows, balance_rows = _cached_pnl_by_business_analysis_inputs(
        duckdb_path,
        year,
        period_start,
        period_end,
    )
    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={period_end}.")

    settings = get_settings()
    loaded_date_list = list(loaded_dates)
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
    payload = PnlByBusinessAnalysisPayload(
        year=year,
        as_of_date=period_end,
        business_key=str(business_key).strip() if business_key else None,
        dimension=dimension,
        period_start_date=period_start,
        period_end_date=period_end,
        source_tables=source_tables,
        rows=_build_pnl_by_business_analysis_rows(
            pnl_rows=list(pnl_rows),
            balance_rows=balance_rows,
            loaded_dates=loaded_date_list,
            period_start=period_start,
            period_end=period_end,
            business_key=str(business_key).strip() if business_key else None,
            dimension=dimension,
        ),
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=period_end,
        trace_id=f"tr_pnl_by_business_analysis_{year}_{period_end}_{dimension}",
        result_kind="pnl.by_business_analysis",
        result_payload=payload.model_dump(mode="json"),
    )


def pnl_by_business_monthly_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    repo = PnlRepository(duckdb_path)
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    if not as_cap:
        raise ValueError(f"No formal pnl rows found for year={year}.")
    if not str(as_cap).startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_cap} is outside requested year={year}.")

    period_end = repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=str(as_cap))
    if period_end is None:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    precomputed = _fetch_pnl_by_business_precompute(
        repo,
        year=year,
        as_of_date=period_end,
        result_kind="monthly",
        dimension="",
        business_key="",
    )
    if precomputed is not None:
        payload = PnlByBusinessMonthlyPayload.model_validate(precomputed)
        return _build_pnl_formal_result_envelope_from_lineage(
            governance_dir=governance_dir,
            report_date=period_end,
            trace_id=f"tr_pnl_by_business_monthly_{year}_{period_end}_precomputed",
            result_kind="pnl.by_business_monthly",
            result_payload=payload.model_dump(mode="json"),
        )
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= period_end
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")

    period_start = f"{min(loaded_dates)[:7]}-01"
    pnl_rows, balance_rows = _cached_pnl_by_business_analysis_inputs(
        duckdb_path,
        year,
        period_start,
        period_end,
    )
    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={period_end}.")

    settings = get_settings()
    loaded_date_list = list(loaded_dates)
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
        ),
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=period_end,
        trace_id=f"tr_pnl_by_business_monthly_{year}_{period_end}",
        result_kind="pnl.by_business_monthly",
        result_payload=payload.model_dump(mode="json"),
    )


def pnl_yearly_summary_envelope(*, duckdb_path: str, governance_dir: str, year: int) -> dict[str, object]:
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


def precompute_pnl_by_business_payloads(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """Materialize the page-local `/pnl-by-business` read model for one cutoff date."""
    _ = governance_dir
    repo = PnlRepository(duckdb_path)
    as_cap = as_of_date or repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=None)
    if not as_cap:
        raise ValueError(f"No formal pnl rows found for year={year}.")
    if not str(as_cap).startswith(f"{year:04d}-"):
        raise ValueError(f"as_of_date={as_cap} is outside requested year={year}.")

    period_end = repo.max_formal_or_nonstd_report_date_in_year(year=year, as_of_cap=str(as_cap))
    if period_end is None:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")
    loaded_dates = sorted(
        d
        for d in repo.list_union_report_dates()
        if str(d).startswith(f"{year:04d}") and str(d) <= period_end
    )
    if not loaded_dates:
        raise ValueError(f"No formal pnl rows found for year={year} through as_of_date={as_cap}.")

    period_start = f"{min(loaded_dates)[:7]}-01"
    _clear_pnl_by_business_analysis_cache()
    pnl_rows = repo.fetch_by_business_analysis_pnl_rows(year=year, as_of_date=period_end)
    balance_rows = repo.fetch_by_business_analysis_balance_rows(
        start_date=period_start,
        end_date=period_end,
    )
    if not pnl_rows:
        raise ValueError(f"No aggregated pnl positions for year={year} through as_of_date={period_end}.")

    source_tables = [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
        "ZQTZ_ASSET_BOND_ROWS",
    ]
    source_version_resolver = getattr(repo, "pnl_by_business_precompute_source_version", None)
    precompute_source_version = (
        source_version_resolver(year=year, as_of_date=period_end)
        if callable(source_version_resolver)
        else PNL_BY_BUSINESS_PRECOMPUTE_SOURCE_VERSION
    )
    generated_at = datetime.now(UTC).isoformat()
    records: list[dict[str, object]] = []

    monthly_payload = PnlByBusinessMonthlyPayload(
        year=year,
        as_of_date=period_end,
        source_tables=source_tables,
        months=_build_pnl_by_business_monthly_buckets(
            pnl_rows=tuple(pnl_rows),
            balance_rows=tuple(balance_rows),
            loaded_dates=loaded_dates,
        ),
    )
    records.append(
        _pnl_by_business_precompute_record(
            year=year,
            as_of_date=period_end,
            result_kind="monthly",
            dimension="",
            business_key="",
            payload=monthly_payload,
            generated_at=generated_at,
            source_version=precompute_source_version,
        )
    )

    analysis_payloads = _build_pnl_by_business_analysis_payloads_for_precompute(
        year=year,
        period_start=period_start,
        period_end=period_end,
        source_tables=source_tables,
        pnl_rows=pnl_rows,
        balance_rows=balance_rows,
        loaded_dates=loaded_dates,
    )
    for payload in analysis_payloads:
        records.append(
            _pnl_by_business_precompute_record(
                year=year,
                as_of_date=period_end,
                result_kind="analysis",
                dimension=payload.dimension,
                business_key=payload.business_key or "",
                payload=payload,
                generated_at=generated_at,
                source_version=precompute_source_version,
            )
        )

    repo.replace_pnl_by_business_precompute(year=year, as_of_date=period_end, records=records)
    _clear_pnl_by_business_analysis_cache()
    return {
        "year": year,
        "as_of_date": period_end,
        "records": len(records),
        "monthly_records": 1,
        "analysis_records": len(records) - 1,
    }


def _pnl_by_business_precompute_record(
    *,
    year: int,
    as_of_date: str,
    result_kind: str,
    dimension: str,
    business_key: str,
    payload: PnlByBusinessMonthlyPayload | PnlByBusinessAnalysisPayload,
    generated_at: str,
    source_version: str,
) -> dict[str, object]:
    return {
        "year": year,
        "as_of_date": as_of_date,
        "result_kind": result_kind,
        "dimension": dimension,
        "business_key": business_key,
        "payload_json": json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
        "source_version": source_version,
        "rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        "generated_at": generated_at,
    }


def _build_pnl_by_business_analysis_payloads_for_precompute(
    *,
    year: int,
    period_start: str,
    period_end: str,
    source_tables: list[str],
    pnl_rows: list[dict[str, object]],
    balance_rows: list[dict[str, object]],
    loaded_dates: list[str],
) -> list[PnlByBusinessAnalysisPayload]:
    balance_lookup = _analysis_balance_lookup(balance_rows)
    sub_type_by_date_code = _analysis_sub_type_by_date_code(balance_rows)
    month_end_by_month: dict[str, str] = {}
    for report_date in sorted(loaded_dates):
        month_end_by_month[str(report_date)[:7]] = str(report_date)

    bucket_maps: dict[tuple[str | None, PnlByBusinessAnalysisDimension], dict[str, dict[str, object]]] = {}
    avg_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal] = {}
    current_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal] = {}
    coverage_dates = {_norm_text(row.get("report_date")) for row in balance_rows if _norm_text(row.get("report_date"))}
    coverage_dates_by_month_key: dict[str, set[str]] = {}
    business_keys = tuple(str(row_def["row_key"]) for row_def in ZQTZ_ASSET_BOND_ROWS)

    def _bucket_map(
        business_key: str | None,
        dimension: PnlByBusinessAnalysisDimension,
    ) -> dict[str, dict[str, object]]:
        map_key = (business_key, dimension)
        if map_key not in bucket_maps:
            bucket_maps[map_key] = {}
            if business_key is None and dimension == "bond_bucket":
                for key, label in ANALYSIS_BOND_BUCKET_LABELS.items():
                    bucket_maps[map_key][key] = _new_analysis_dimension_bucket(key, label)
            elif business_key is None and dimension == "bond_bucket_monthly":
                for month_end in sorted(month_end_by_month.values()):
                    for key, label in ANALYSIS_BOND_BUCKET_LABELS.items():
                        dimension_key = f"{month_end}::{key}"
                        bucket_maps[map_key][dimension_key] = _new_analysis_dimension_bucket(
                            dimension_key,
                            f"{month_end} {label}",
                        )
        return bucket_maps[map_key]

    for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
        _bucket_map(None, dimension)

    def _add_pnl(
        *,
        business_key: str | None,
        dimension: PnlByBusinessAnalysisDimension,
        key_label: tuple[str, str] | None,
        row: dict[str, object],
    ) -> None:
        if key_label is None:
            return
        dimension_key, dimension_label = key_label
        bucket = _bucket_map(business_key, dimension).setdefault(
            dimension_key,
            _new_analysis_dimension_bucket(dimension_key, dimension_label),
        )
        bucket["interest_income"] = Decimal(str(bucket["interest_income"])) + _decimal_value(
            row.get("interest_income_514")
        )
        bucket["fair_value_change"] = Decimal(str(bucket["fair_value_change"])) + _decimal_value(
            row.get("fair_value_change_516")
        )
        bucket["capital_gain"] = Decimal(str(bucket["capital_gain"])) + _decimal_value(row.get("capital_gain_517"))
        bucket["manual_adjustment"] = Decimal(str(bucket["manual_adjustment"])) + _decimal_value(
            row.get("manual_adjustment")
        )
        bucket["total_pnl"] = Decimal(str(bucket["total_pnl"])) + _decimal_value(row.get("total_pnl"))
        code = _norm_text(row.get("instrument_code"))
        if code:
            bucket["asset_codes"].add(code)

    def _add_balance(
        *,
        business_key: str | None,
        dimension: PnlByBusinessAnalysisDimension,
        key_label: tuple[str, str] | None,
        row: dict[str, object],
    ) -> None:
        if key_label is None:
            return
        dimension_key, _dimension_label = key_label
        sum_key = (business_key, dimension, dimension_key)
        avg_sums[sum_key] = avg_sums.get(sum_key, Decimal("0")) + _decimal_value(row.get("avg_amount"))
        report_date = _norm_text(row.get("report_date"))
        dimension_report_date = _analysis_dimension_report_date(dimension_key)
        if (_analysis_is_monthly_dimension(dimension) and report_date == dimension_report_date) or (
            not _analysis_is_monthly_dimension(dimension) and report_date == period_end
        ):
            current_sums[sum_key] = current_sums.get(sum_key, Decimal("0")) + _decimal_value(
                row.get("current_amount")
            )

    for pnl_row in pnl_rows:
        classification = (
            _pnl_by_business_manual_classification(pnl_row)
            if _norm_text(pnl_row.get("source_kind")) == "manual_adjustment"
            else _analysis_classification_for_pnl_row(
                pnl_row=pnl_row,
                balance_lookup=balance_lookup,
                sub_type_by_date_code=sub_type_by_date_code,
                fallback_date=period_end,
            )
        )
        matched_keys = _analysis_matched_business_keys(classification)
        for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
            _add_pnl(
                business_key=None,
                dimension=dimension,
                key_label=_analysis_global_bond_bucket_dimension_for_pnl_row(pnl_row, matched_keys, dimension),
                row=pnl_row,
            )
        for business_key in matched_keys:
            for dimension in PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS:
                _add_pnl(
                    business_key=business_key,
                    dimension=dimension,
                    key_label=_analysis_dimension_for_pnl_row(pnl_row, classification, dimension),
                    row=pnl_row,
                )

    for row in balance_rows:
        report_date = _norm_text(row.get("report_date"))
        month_key = month_end_by_month.get(report_date[:7])
        if month_key:
            coverage_dates_by_month_key.setdefault(month_key, set()).add(report_date)
        classification = _analysis_classification_from_balance_row(row)
        matched_keys = _analysis_matched_business_keys(classification)
        for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
            _add_balance(
                business_key=None,
                dimension=dimension,
                key_label=_analysis_global_bond_bucket_dimension_for_balance_row(
                    row,
                    matched_keys,
                    dimension,
                    month_end_by_month,
                ),
                row=row,
            )
        for business_key in matched_keys:
            for dimension in PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS:
                _add_balance(
                    business_key=business_key,
                    dimension=dimension,
                    key_label=_analysis_dimension_for_balance_row(row, dimension, month_end_by_month),
                    row=row,
                )

    payloads: list[PnlByBusinessAnalysisPayload] = []
    for dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
        payloads.append(
            PnlByBusinessAnalysisPayload(
                year=year,
                as_of_date=period_end,
                business_key=None,
                dimension=dimension,
                period_start_date=period_start,
                period_end_date=period_end,
                source_tables=source_tables,
                rows=_analysis_rows_from_precompute_buckets(
                    bucket_map=_bucket_map(None, dimension),
                    avg_sums=avg_sums,
                    current_sums=current_sums,
                    coverage_dates=coverage_dates,
                    coverage_dates_by_month_key=coverage_dates_by_month_key,
                    period_start=period_start,
                    period_end=period_end,
                    business_key=None,
                    dimension=dimension,
                ),
            )
        )
    for business_key in business_keys:
        for dimension in PNL_BY_BUSINESS_KEYED_ANALYSIS_DIMENSIONS:
            payloads.append(
                PnlByBusinessAnalysisPayload(
                    year=year,
                    as_of_date=period_end,
                    business_key=business_key,
                    dimension=dimension,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    source_tables=source_tables,
                    rows=_analysis_rows_from_precompute_buckets(
                        bucket_map=bucket_maps.get((business_key, dimension), {}),
                        avg_sums=avg_sums,
                        current_sums=current_sums,
                        coverage_dates=coverage_dates,
                        coverage_dates_by_month_key=coverage_dates_by_month_key,
                        period_start=period_start,
                        period_end=period_end,
                        business_key=business_key,
                        dimension=dimension,
                    ),
                )
            )
    return payloads


def _analysis_rows_from_precompute_buckets(
    *,
    bucket_map: dict[str, dict[str, object]],
    avg_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal],
    current_sums: dict[tuple[str | None, PnlByBusinessAnalysisDimension, str], Decimal],
    coverage_dates: set[str],
    coverage_dates_by_month_key: dict[str, set[str]],
    period_start: str,
    period_end: str,
    business_key: str | None,
    dimension: PnlByBusinessAnalysisDimension,
) -> list[PnlByBusinessAnalysisRow]:
    period_calendar_days = _calendar_days(period_start, period_end)
    rows: list[PnlByBusinessAnalysisRow] = []
    for bucket in sorted(bucket_map.values(), key=lambda item: _analysis_dimension_row_sort_key(item, dimension)):
        dimension_key = str(bucket["dimension_key"])
        if _analysis_is_monthly_dimension(dimension):
            month_end_key = _analysis_dimension_report_date(dimension_key)
            denom = len(coverage_dates_by_month_key.get(month_end_key, set()))
            calendar_days = _calendar_days(f"{month_end_key[:7]}-01", month_end_key)
        else:
            denom = len(coverage_dates)
            calendar_days = period_calendar_days
        sum_key = (business_key, dimension, dimension_key)
        avg_balance = (avg_sums.get(sum_key, Decimal("0")) / Decimal(str(denom))) if denom > 0 else Decimal("0")
        current_balance = current_sums.get(sum_key, Decimal("0"))
        total_pnl = Decimal(str(bucket["total_pnl"]))
        annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
        ftp_values = _analysis_ftp_values(
            total_pnl=total_pnl,
            avg_balance=avg_balance,
            annualized_yield_pct=annualized_yield_pct,
            calendar_days=calendar_days,
        )
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
                ftp_rate_pct=FTP_RATE_PCT,
                ftp_cost=ftp_values["ftp_cost"],
                ftp_net_pnl=ftp_values["ftp_net_pnl"],
                ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
                asset_count=len(bucket["asset_codes"]) if bucket["asset_codes"] else 0,
            )
        )
    return rows


def _analysis_dimension_row_sort_key(
    item: dict[str, object],
    dimension: PnlByBusinessAnalysisDimension,
) -> tuple[object, ...]:
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


def _analysis_matched_business_keys(classification: dict[str, object]) -> tuple[str, ...]:
    manual_key = _norm_text(classification.get("manual_business_row_key"))
    if manual_key:
        return (manual_key,)
    return tuple(str(row_def.get("row_key")) for row_def in match_zqtz_asset_bond_rows(classification))


def _analysis_bond_bucket_for_matched_keys(matched_keys: tuple[str, ...]) -> tuple[str, str]:
    matched_set = set(matched_keys)
    for bucket_key, label, row_keys in ANALYSIS_BOND_BUCKETS:
        if matched_set & row_keys:
            return bucket_key, label
    return "other_bond", ANALYSIS_BOND_BUCKET_LABELS["other_bond"]


def _analysis_global_bond_bucket_dimension_for_pnl_row(
    row: dict[str, object],
    matched_keys: tuple[str, ...],
    dimension: PnlByBusinessAnalysisDimension,
) -> tuple[str, str] | None:
    bucket_key, label = _analysis_bond_bucket_for_matched_keys(matched_keys)
    if dimension == "bond_bucket":
        return bucket_key, label
    report_date = _norm_text(row.get("report_date"))
    if not report_date:
        return None
    return f"{report_date}::{bucket_key}", f"{report_date} {label}"


def _analysis_global_bond_bucket_dimension_for_balance_row(
    row: dict[str, object],
    matched_keys: tuple[str, ...],
    dimension: PnlByBusinessAnalysisDimension,
    month_end_by_month: dict[str, str],
) -> tuple[str, str] | None:
    bucket_key, label = _analysis_bond_bucket_for_matched_keys(matched_keys)
    if dimension == "bond_bucket":
        return bucket_key, label
    report_date = _norm_text(row.get("report_date"))
    month_end = month_end_by_month.get(report_date[:7])
    if not month_end:
        return None
    return f"{month_end}::{bucket_key}", f"{month_end} {label}"


def _build_pnl_by_business_analysis_rows(
    *,
    pnl_rows: list[dict[str, object]],
    balance_rows: list[dict[str, object]],
    loaded_dates: list[str],
    period_start: str,
    period_end: str,
    business_key: str | None,
    dimension: PnlByBusinessAnalysisDimension,
) -> list[PnlByBusinessAnalysisRow]:
    balance_lookup = _analysis_balance_lookup(balance_rows)
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
        annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
        ftp_values = _analysis_ftp_values(
            total_pnl=total_pnl,
            avg_balance=avg_balance,
            annualized_yield_pct=annualized_yield_pct,
            calendar_days=calendar_days,
        )
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
                ftp_rate_pct=FTP_RATE_PCT,
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
) -> list[PnlByBusinessMonthlyBucket]:
    balance_lookup = _analysis_balance_lookup(list(balance_rows))
    sub_type_by_date_code = _analysis_sub_type_by_date_code(list(balance_rows))
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

        for pnl_row in pnl_rows:
            if _norm_text(pnl_row.get("report_date"))[:7] != month_key:
                continue
            classification = (
                _pnl_by_business_manual_classification(pnl_row)
                if _norm_text(pnl_row.get("source_kind")) == "manual_adjustment"
                else _analysis_classification_for_pnl_row(
                    pnl_row=pnl_row,
                    balance_lookup=balance_lookup,
                    sub_type_by_date_code=sub_type_by_date_code,
                    fallback_date=month_end,
                )
            )
            for row_def in match_zqtz_asset_bond_rows(classification):
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
            if _is_parent_monthly_business_group(group):
                parent_total += total_pnl
            item_inputs.append((group, avg_balance, current_balance))

        items = [
            _monthly_business_item_from_group(
                group=group,
                avg_balance=avg_balance,
                current_balance=current_balance,
                total_pnl_for_proportion=parent_total,
                calendar_days=calendar_days,
            )
            for group, avg_balance, current_balance in item_inputs
        ]
        summary = _monthly_business_summary_from_items(items, calendar_days)
        buckets.append(
            PnlByBusinessMonthlyBucket(
                month_key=month_key,
                period_start_date=month_start,
                period_end_date=month_end,
                calendar_days=calendar_days,
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
) -> PnlByBusinessMonthlyItem:
    total_pnl = Decimal(str(group["total_pnl"]))
    annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
    ftp_values = _analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
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
        ftp_rate_pct=FTP_RATE_PCT,
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
) -> PnlByBusinessMonthlySummary:
    parent_items = [item for item in items if _is_parent_monthly_business_item(item)]
    interest_income = sum((Decimal(str(item.interest_income)) for item in parent_items), Decimal("0"))
    fair_value_change = sum((Decimal(str(item.fair_value_change)) for item in parent_items), Decimal("0"))
    capital_gain = sum((Decimal(str(item.capital_gain)) for item in parent_items), Decimal("0"))
    manual_adjustment = sum((Decimal(str(item.manual_adjustment)) for item in parent_items), Decimal("0"))
    total_pnl = sum((Decimal(str(item.total_pnl)) for item in parent_items), Decimal("0"))
    avg_balance = sum((Decimal(str(item.avg_balance)) for item in parent_items), Decimal("0"))
    current_balance = sum((Decimal(str(item.current_balance)) for item in parent_items), Decimal("0"))
    annualized_yield_pct = _analysis_annualized_yield_pct(total_pnl, avg_balance, calendar_days)
    ftp_values = _analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
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
        ftp_rate_pct=FTP_RATE_PCT,
        ftp_cost=ftp_values["ftp_cost"],
        ftp_net_pnl=ftp_values["ftp_net_pnl"],
        ftp_net_annualized_yield_pct=ftp_values["ftp_net_annualized_yield_pct"],
        asset_count=sum(item.asset_count for item in parent_items),
    )


def _is_parent_monthly_business_group(group: dict[str, object]) -> bool:
    if "_detail_" in str(group.get("row_key") or ""):
        return False
    business_type = str(group.get("business_type") or "")
    if business_type.startswith("其中"):
        return False
    return "其中项" not in str(group.get("source_note") or "")


def _is_parent_monthly_business_item(item: PnlByBusinessMonthlyItem) -> bool:
    if "_detail_" in item.row_key:
        return False
    if item.business_type.startswith("其中"):
        return False
    return "其中项" not in str(item.source_note or "")


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
) -> dict[str, object]:
    report_date = _norm_text(pnl_row.get("report_date"))
    portfolio_name = _norm_text(pnl_row.get("portfolio_name"))
    cost_center = _norm_text(pnl_row.get("cost_center"))
    currency_basis = _norm_text(pnl_row.get("currency_basis")) or "CNY"
    for code in _instrument_code_variants(pnl_row.get("instrument_code")):
        balance_row = balance_lookup.get((report_date, code, portfolio_name, cost_center, currency_basis))
        if balance_row is not None:
            return _analysis_classification_from_balance_row(balance_row)

    code = _norm_text(pnl_row.get("instrument_code"))
    sub_type = sub_type_by_date_code.get((report_date, code), "") or sub_type_by_date_code.get((fallback_date, code), "")
    if _norm_text(pnl_row.get("source_kind")) == "nonstd_bridge":
        return _v1_nonstd_classification_row(report_date=report_date or fallback_date, code=code, sub_type=sub_type)
    invest = _norm_text(pnl_row.get("invest_type_std")) or "unclassified"
    classification = _v1_fi_classification_row(
        report_date=report_date or fallback_date,
        row={
            "instrument_code": code,
            "currency_basis": currency_basis,
            "currency_code": currency_basis,
            "instrument_name": code,
            "accounting_basis": _norm_text(pnl_row.get("accounting_basis")),
        },
        code=code,
        asset_class=invest,
        sub_type=sub_type or invest,
    )
    classification["accounting_basis"] = _norm_text(pnl_row.get("accounting_basis"))
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
        return _dimension_key_label(row.get("accounting_basis") or classification.get("accounting_basis"), "未填会计分类")
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


def _analysis_annualized_yield_pct(total_pnl: Decimal, avg_balance: Decimal, calendar_days: int) -> Decimal | None:
    if avg_balance <= Decimal("0") or calendar_days <= 0:
        return None
    return _quantize_yield_pct((total_pnl / avg_balance) * Decimal("365") / Decimal(str(calendar_days)) * Decimal("100"))


def _analysis_ftp_values(
    *,
    total_pnl: Decimal,
    avg_balance: Decimal,
    annualized_yield_pct: Decimal | None,
    calendar_days: int,
) -> dict[str, Decimal | None]:
    if avg_balance <= Decimal("0") or calendar_days <= 0 or annualized_yield_pct is None:
        return {
            "ftp_cost": None,
            "ftp_net_pnl": None,
            "ftp_net_annualized_yield_pct": None,
        }
    ftp_cost = avg_balance * FTP_RATE_RATIO * Decimal(str(calendar_days)) / Decimal("365")
    return {
        "ftp_cost": _quantize_decimal(ftp_cost),
        "ftp_net_pnl": _quantize_decimal(total_pnl - ftp_cost),
        "ftp_net_annualized_yield_pct": _quantize_yield_pct(annualized_yield_pct - FTP_RATE_PCT),
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
        interest_income = Decimal(str(row.get("interest_income_514") or "0"))
        if any(taxable in asset_class for taxable in V1_FI_TAXABLE_BOND_TYPES):
            interest_income = interest_income / V1_VAT_DIVISOR
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
            if str(journal_type) == "514" and code_prefix == "JM":
                amount = amount / V1_VAT_DIVISOR
            if code_prefix == "J1":
                amount = amount * _v1_fx_rate("USD", fx_rates)
            if str(journal_type) == "514":
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
        interest_income = Decimal(str(row.get("interest_income_514") or "0"))
        if any(taxable in asset_class for taxable in V1_FI_TAXABLE_BOND_TYPES):
            interest_income = interest_income / V1_VAT_DIVISOR
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
            if str(journal_type) == "514" and code_prefix == "JM":
                amount = amount / V1_VAT_DIVISOR
            if code_prefix == "J1":
                amount = amount * _v1_fx_rate("USD", fx_rates)
            if str(journal_type) == "514":
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


def _build_pnl_formal_result_envelope_from_lineage(
    *,
    governance_dir: str,
    report_date: str | None,
    trace_id: str,
    result_kind: str,
    result_payload: dict[str, object],
    quality_flag: str | None = None,
) -> dict[str, object]:
    lineage = _resolve_pnl_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
    )
    return build_formal_result_envelope_from_lineage_runtime(
        trace_id=trace_id,
        result_kind=result_kind,
        lineage=lineage,
        default_cache_version=PNL_CACHE_VERSION,
        use_lineage_cache_version=False,
        result_payload=result_payload,
        quality_flag=quality_flag,
    )


def _resolve_pnl_lineage(*, governance_dir: str, report_date: str | None) -> dict[str, object]:
    if report_date:
        build_lineage = resolve_completed_formal_build_lineage(
            governance_dir=governance_dir,
            cache_key=PNL_CACHE_KEY,
            job_name=PNL_JOB_NAME,
            report_date=report_date,
        )
        if build_lineage is not None:
            try:
                manifest_lineage = resolve_formal_manifest_lineage(
                    governance_dir=governance_dir,
                    cache_key=PNL_CACHE_KEY,
                )
            except RuntimeError:
                return build_lineage
            return {
                **manifest_lineage,
                **{
                    key: value
                    for key, value in build_lineage.items()
                    if str(value or "").strip()
                },
            }
    return resolve_formal_manifest_lineage(
        governance_dir=governance_dir,
        cache_key=PNL_CACHE_KEY,
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
        pnl_total=float(totals["total_pnl"]),
        ledger_pnl_total=float(component_total),
        threshold_yuan=0.01,
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
