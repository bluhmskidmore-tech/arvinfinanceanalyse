from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.governance.formal_compute_lineage import (
    resolve_completed_formal_build_lineage,
    resolve_formal_manifest_lineage,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings
from backend.app.core_finance.pnl import compute_nonstd_signed_ledger_amount
from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS, match_zqtz_asset_bond_rows
from backend.app.core_finance.reconciliation_checks import pnl_vs_ledger_diff
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.accounting_asset_movement_repo import AccountingAssetMovementRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.pnl import (
    PnlByBusinessPayload,
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


def pnl_by_business_ytd_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None = None,
) -> dict[str, object]:
    """业务种类「年度累计」：V1 兼容口径（刷新包），非 formal 事实表单日 by-business。

    - 对每个当年 ``report_date`` 取 ``load_latest_pnl_refresh_input``，经 ``_iter_v1_compatible_pnl_records`` 得到
      逐资产/凭证聚合记录；``result["total_pnl"]`` = 这些记录的 ``total_pnl`` 之和（每条记录只计一次）。
    - ``items``：按 ``match_zqtz_asset_bond_rows`` 将同一记录并入多行 ZQTZ 桶时，各 ``item["total_pnl"]`` 可重叠，
      故 **各行 ``total_pnl`` 简单相加不必等于** ``result["total_pnl"]``。
    """
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
    payload = PnlByBusinessYtdPayload(
        year=year,
        period_label=f"{year}年{start_month[-2:]}-{end_month[-2:]}月累计" if start_month != end_month else f"{year}年{end_month[-2:]}月累计",
        total_pnl=_quantize_decimal(total_pnl),
        source_tables=[
            "data_input/pnl",
            "data_input/pnl_514",
            "data_input/pnl_516",
            "data_input/pnl_517",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
            "fx_daily_mid",
        ],
        items=items,
    )
    return _build_pnl_formal_result_envelope_from_lineage(
        governance_dir=governance_dir,
        report_date=max(loaded_dates),
        trace_id=f"tr_pnl_by_business_ytd_{year}" if not as_of_date else f"tr_pnl_by_business_ytd_{year}_{as_of_date}",
        result_kind="pnl.by_business_ytd",
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
    for key in ("interest_income", "fair_value_change", "capital_gain", "total_pnl"):
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
