"""Read-only reconciliation between system operating PnL and formal product-category PnL."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Literal, cast

from backend.app.core_finance.pnl_basis_bridge import (
    PnlBasisBridgeComponentCalculation,
    calculate_pnl_basis_bridge,
)
from backend.app.schemas.pnl_basis_bridge import (
    PnlBasisBridgeComponent,
    PnlBasisBridgeInputs,
    PnlBasisBridgePath,
    PnlBasisBridgePayload,
    PnlBasisBridgePeriod,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.pnl_service import (
    pnl_by_business_monthly_envelope,
    pnl_overview_envelope,
)
from backend.app.services.product_category_pnl_service import (
    ProductCategoryReadModelNotFoundError,
    product_category_pnl_envelope,
)

BASIS_BRIDGE_RULE_VERSION = "rv_pnl_basis_bridge_v1"
BASIS_BRIDGE_CACHE_VERSION = "cv_pnl_basis_bridge_v1"

_COMPONENT_COPY: dict[str, tuple[str, str]] = {
    "remove_system_manual_adjustment": (
        "剔除系统经营分析手工补录",
        "直接取系统经营分析 manual_adjustment，产品正式口径不纳入该补录。",
    ),
    "restore_unallocated_formal_pnl": (
        "恢复未分配正式损益",
        "直接取 by-business 月桶 unallocated_pnl，使分类经营分析回到完整正式损益范围。",
    ),
    "rounding_alignment": (
        "分位舍入对齐",
        "对齐逐项两位小数量化与正式总额；金额必须不超过分位级容差。",
    ),
    "formal_to_product_gross_scope_mapping_residual": (
        "正式损益至产品现金口径范围/映射残差",
        "算术可复算，但在产品—科目—业务种类交叉表获批前不得解释为单一业务原因。",
    ),
    "ftp_method_and_denominator_difference": (
        "FTP方法与分母差异",
        "系统FTP成本减产品正式FTP成本；尚未拆分为利率、天数、日均分母和产品映射子项。",
    ),
}


def pnl_basis_bridge_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
) -> dict[str, object]:
    parsed_report_date = _parse_report_date(report_date)
    try:
        monthly_product_envelope = product_category_pnl_envelope(
            duckdb_path,
            report_date=report_date,
            view="monthly",
        )
        ytd_product_envelope = product_category_pnl_envelope(
            duckdb_path,
            report_date=report_date,
            view="ytd",
        )
    except ProductCategoryReadModelNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    system_envelope = pnl_by_business_monthly_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=parsed_report_date.year,
        as_of_date=report_date,
    )
    overview_envelope = pnl_overview_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
    )

    monthly_product = _result_mapping(monthly_product_envelope, "monthly product-category")
    ytd_product = _result_mapping(ytd_product_envelope, "YTD product-category")
    system_payload = _result_mapping(system_envelope, "system by-business monthly")
    overview_payload = _result_mapping(overview_envelope, "formal PnL overview")
    _require_payload_identity(monthly_product, report_date=report_date, view="monthly")
    _require_payload_identity(ytd_product, report_date=report_date, view="ytd")
    if str(system_payload.get("as_of_date") or "") != report_date:
        raise RuntimeError(
            "PnL basis bridge date mismatch: "
            f"system as_of_date={system_payload.get('as_of_date')!r}, report_date={report_date!r}."
        )
    if str(overview_payload.get("report_date") or "") != report_date:
        raise RuntimeError(
            "PnL basis bridge date mismatch: "
            f"overview report_date={overview_payload.get('report_date')!r}, report_date={report_date!r}."
        )

    months = _mapping_list(system_payload.get("months"), "system months")
    current_month = next(
        (bucket for bucket in months if str(bucket.get("period_end_date") or "") == report_date),
        None,
    )
    if current_month is None:
        raise ValueError(f"No system monthly PnL bucket found for report_date={report_date}.")

    monthly_system = _aggregate_system_buckets([current_month])
    ytd_system = _aggregate_system_buckets(months)
    formal_monthly = _decimal_field(overview_payload, "total_pnl", "formal overview")
    if abs(formal_monthly - monthly_system["formal_recognized_pnl"]) > Decimal("0.01"):
        raise RuntimeError(
            "PnL basis bridge formal monthly source mismatch: "
            f"overview={formal_monthly}, by_business_source={monthly_system['formal_recognized_pnl']}."
        )
    monthly_system["formal_recognized_pnl"] = formal_monthly

    monthly_period = _build_period(
        period="monthly",
        period_start_date=str(current_month.get("period_start_date") or ""),
        period_end_date=report_date,
        system=monthly_system,
        product=_product_totals(monthly_product),
    )
    ytd_period = _build_period(
        period="ytd",
        period_start_date=str(months[0].get("period_start_date") or ""),
        period_end_date=report_date,
        system=ytd_system,
        product=_product_totals(ytd_product),
    )
    payload = PnlBasisBridgePayload(
        report_date=report_date,
        periods=[monthly_period, ytd_period],
        pending_mapping=[
            "formal_pnl_to_product_cash_scope_crosswalk",
            "product_account_business_type_crosswalk",
            "ftp_method_rate_days_denominator_split",
        ],
    )

    upstream_envelopes = (
        monthly_product_envelope,
        ytd_product_envelope,
        system_envelope,
        overview_envelope,
    )
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_pnl_basis_bridge_{report_date}",
        result_kind="pnl.basis_bridge",
        cache_version=BASIS_BRIDGE_CACHE_VERSION,
        source_version=_merge_meta_values(upstream_envelopes, "source_version", "sv_basis_bridge"),
        rule_version=_merge_rule_versions(upstream_envelopes),
        result_payload=payload.model_dump(mode="json"),
        quality_flag="warning",
        filters_applied={"report_date": report_date},
        tables_used=_merge_tables(upstream_envelopes),
        next_drill=[
            "/api/pnl/overview",
            "/api/pnl/by-business-monthly",
            "/ui/pnl/product-category?view=monthly",
            "/ui/pnl/product-category?view=ytd",
        ],
        source_surface="pnl_bridge",
        requested_report_date=report_date,
        resolved_report_date=report_date,
        as_of_date=report_date,
        date_basis="monthly_and_ytd_through_report_date",
    )


def _parse_report_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("report_date must be YYYY-MM-DD.") from exc
    if parsed.isoformat() != str(value):
        raise ValueError("report_date must be YYYY-MM-DD.")
    return parsed


def _result_mapping(envelope: object, label: str) -> Mapping[str, object]:
    if not isinstance(envelope, Mapping) or not isinstance(envelope.get("result"), Mapping):
        raise RuntimeError(f"PnL basis bridge {label} result is unavailable.")
    return envelope["result"]


def _mapping_list(value: object, label: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list) or not value or not all(isinstance(item, Mapping) for item in value):
        raise RuntimeError(f"PnL basis bridge {label} are unavailable.")
    return list(value)


def _require_payload_identity(payload: Mapping[str, object], *, report_date: str, view: str) -> None:
    if str(payload.get("report_date") or "") != report_date or str(payload.get("view") or "") != view:
        raise RuntimeError(
            "PnL basis bridge product payload mismatch: "
            f"expected report_date={report_date!r}, view={view!r}; "
            f"got report_date={payload.get('report_date')!r}, view={payload.get('view')!r}."
        )


def _decimal_field(payload: Mapping[str, object], key: str, label: str) -> Decimal:
    value = payload.get(key)
    if value is None:
        raise RuntimeError(f"PnL basis bridge missing {label}.{key}.")
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise RuntimeError(f"PnL basis bridge invalid {label}.{key}={value!r}.") from exc


def _aggregate_system_buckets(buckets: list[Mapping[str, object]]) -> dict[str, Decimal]:
    totals = {
        "system_gross_pnl": Decimal("0"),
        "system_manual_adjustment": Decimal("0"),
        "system_unallocated_pnl": Decimal("0"),
        "system_ftp_cost": Decimal("0"),
        "system_ftp_net_pnl": Decimal("0"),
        "formal_recognized_pnl": Decimal("0"),
    }
    for bucket in buckets:
        summary = bucket.get("summary")
        if not isinstance(summary, Mapping):
            raise RuntimeError("PnL basis bridge system month summary is unavailable.")
        gross = _decimal_field(summary, "total_pnl", "system summary")
        manual = _decimal_field(summary, "manual_adjustment", "system summary")
        source_total = _decimal_field(bucket, "source_total_pnl", "system month")
        totals["system_gross_pnl"] += gross
        totals["system_manual_adjustment"] += manual
        totals["system_unallocated_pnl"] += _decimal_field(
            bucket, "unallocated_pnl", "system month"
        )
        totals["system_ftp_cost"] += _decimal_field(summary, "ftp_cost", "system summary")
        totals["system_ftp_net_pnl"] += _decimal_field(
            summary, "ftp_net_pnl", "system summary"
        )
        totals["formal_recognized_pnl"] += source_total - manual
    return totals


def _product_totals(payload: Mapping[str, object]) -> dict[str, Decimal]:
    grand_total = payload.get("grand_total")
    if not isinstance(grand_total, Mapping):
        raise RuntimeError("PnL basis bridge product grand_total is unavailable.")
    return {
        "product_gross_cash_income": _decimal_field(
            grand_total, "cnx_cash", "product grand_total"
        ),
        "product_ftp_cost": _decimal_field(grand_total, "cny_ftp", "product grand_total")
        + _decimal_field(grand_total, "foreign_ftp", "product grand_total"),
        "product_ftp_net_income": _decimal_field(
            grand_total, "business_net_income", "product grand_total"
        ),
    }


def _build_period(
    *,
    period: Literal["monthly", "ytd"],
    period_start_date: str,
    period_end_date: str,
    system: Mapping[str, Decimal],
    product: Mapping[str, Decimal],
) -> PnlBasisBridgePeriod:
    try:
        calculation = calculate_pnl_basis_bridge(**system, **product)
    except ValueError as exc:
        raise RuntimeError(f"PnL basis bridge closure failed for period={period}: {exc}") from exc
    inputs = PnlBasisBridgeInputs(
        **system,
        **product,
        system_identity_residual=calculation.system_identity_residual,
        product_identity_residual=calculation.product_identity_residual,
    )
    return PnlBasisBridgePeriod(
        period=period,
        period_start_date=period_start_date,
        period_end_date=period_end_date,
        inputs=inputs,
        system_to_formal_gross=_path(
            start_code="system_operating_gross_pnl",
            start_value=system["system_gross_pnl"],
            components=calculation.gross_components,
            end_code="formal_recognized_pnl",
            end_value=system["formal_recognized_pnl"],
            closure_residual=calculation.gross_closure_residual,
            mapping_status="not_required",
        ),
        system_to_product_ftp_net=_path(
            start_code="system_operating_ftp_net_pnl",
            start_value=system["system_ftp_net_pnl"],
            components=calculation.net_components,
            end_code="formal_product_ftp_net_income",
            end_value=product["product_ftp_net_income"],
            closure_residual=calculation.net_closure_residual,
            mapping_status="pending_crosswalk",
        ),
    )


def _path(
    *,
    start_code: str,
    start_value: Decimal,
    components: tuple[PnlBasisBridgeComponentCalculation, ...],
    end_code: str,
    end_value: Decimal,
    closure_residual: Decimal,
    mapping_status: Literal["not_required", "pending_crosswalk"],
) -> PnlBasisBridgePath:
    return PnlBasisBridgePath(
        start_code=start_code,
        start_value=start_value,
        components=[_component(item) for item in components],
        end_code=end_code,
        end_value=end_value,
        closure_residual=closure_residual,
        arithmetic_status="closed",
        mapping_status=mapping_status,
    )


def _component(item: PnlBasisBridgeComponentCalculation) -> PnlBasisBridgeComponent:
    label, note = _COMPONENT_COPY[item.code]
    return PnlBasisBridgeComponent(
        code=item.code,
        label=label,
        amount=item.amount,
        evidence_status=cast(
            Literal["source_traced", "rounding_control", "source_derived", "mapping_pending"],
            item.evidence_status,
        ),
        note=note,
    )


def _meta_mapping(envelope: object) -> Mapping[str, object]:
    if isinstance(envelope, Mapping) and isinstance(envelope.get("result_meta"), Mapping):
        return envelope["result_meta"]
    return {}


def _merge_meta_values(
    envelopes: tuple[object, ...],
    field_name: str,
    default: str,
) -> str:
    values = sorted(
        {
            str(_meta_mapping(envelope).get(field_name) or "").strip()
            for envelope in envelopes
            if str(_meta_mapping(envelope).get(field_name) or "").strip()
        }
    )
    return "__".join(values) or default


def _merge_rule_versions(envelopes: tuple[object, ...]) -> str:
    upstream = _merge_meta_values(envelopes, "rule_version", "")
    return "__".join(value for value in (BASIS_BRIDGE_RULE_VERSION, upstream) if value)


def _merge_tables(envelopes: tuple[object, ...]) -> list[str]:
    tables = {"product_category_pnl_formal_read_model"}
    for envelope in envelopes:
        raw_tables = _meta_mapping(envelope).get("tables_used")
        if isinstance(raw_tables, list):
            tables.update(str(value) for value in raw_tables if str(value).strip())
    return sorted(tables)
