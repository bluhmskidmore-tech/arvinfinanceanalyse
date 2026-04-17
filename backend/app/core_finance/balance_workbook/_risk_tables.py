"""Risk table builders for balance analysis workbook."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.balance_analysis import (
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.balance_workbook._utils import (
    _ZERO,
    _group_rows,
    _sum_decimal,
    _weighted_average,
    _remaining_years,
    _safe_ratio,
    _to_wanyuan,
    _decimal_value,
    _section,
    _table,
)
from backend.app.core_finance.balance_workbook._bond_tables import (
    _build_maturity_gap_table,
    _build_issuance_business_type_table,
)
from backend.app.core_finance.balance_workbook._analysis_tables import (
    _build_rating_table,
)


def _regulatory_metric_status(current: Decimal | None, threshold: Decimal, *, lower_is_better: bool = True) -> str:
    if current is None:
        return "unknown"
    if lower_is_better:
        return "pass" if current <= threshold else "review"
    return "pass" if current >= threshold else "review"


def _build_regulatory_limits_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    bond_assets = [row for row in zqtz_rows if row.position_scope == "asset"]
    interbank_assets = [row for row in tyw_rows if row.position_scope == "asset"]
    interbank_liabilities = [row for row in tyw_rows if row.position_scope == "liability"]
    bond_asset_total = _sum_decimal(bond_assets, lambda row: row.face_value_amount)
    interbank_asset_total = _sum_decimal(interbank_assets, lambda row: row.principal_amount)
    interbank_liability_total = _sum_decimal(interbank_liabilities, lambda row: row.principal_amount)
    asset_denominator = bond_asset_total + interbank_asset_total

    issuer_groups = _group_rows(bond_assets, lambda row: row.issuer_name or "未分类")
    top1_share = _ZERO
    for entries in issuer_groups.values():
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        top1_share = max(top1_share, _safe_ratio(balance_amount, bond_asset_total))

    interbank_ratio = _safe_ratio(interbank_liability_total, asset_denominator) if asset_denominator > _ZERO else _ZERO

    usd_amount = _sum_decimal(
        [row for row in bond_assets if str(row.currency_code or "").upper() in {"USD", "美元"}],
        lambda row: row.face_value_amount,
    )
    usd_ratio = _safe_ratio(usd_amount, bond_asset_total) if bond_asset_total > _ZERO else _ZERO

    duration_weights: list[tuple[Decimal, Decimal]] = []
    for row in bond_assets:
        years = _remaining_years(report_date, row.maturity_date)
        duration_weights.append((row.face_value_amount, years))
    for row in interbank_assets:
        years = _remaining_years(report_date, row.maturity_date)
        duration_weights.append((row.principal_amount, years))
    duration_numerator = _ZERO
    duration_denominator = _ZERO
    for weight, years in duration_weights:
        duration_numerator += weight * years
        duration_denominator += weight
    duration_proxy = duration_numerator / duration_denominator if duration_denominator > _ZERO else None

    thresholds = {
        "top1_concentration": Decimal("0.15"),
        "interbank_liability_ratio": Decimal("0.25"),
        "usd_exposure_ratio": Decimal("0.05"),
        "portfolio_modified_duration": Decimal("5.0"),
    }

    rows = [
        {
            "metric_key": "top1_concentration",
            "metric_name": "最大单一发行人占比(债券资产)",
            "current_value": top1_share,
            "threshold_value": thresholds["top1_concentration"],
            "status": _regulatory_metric_status(top1_share, thresholds["top1_concentration"]),
            "calculation_note": "来自正式 fact 资产端按 issuer_name 分组后的最大 face_value 占比。",
        },
        {
            "metric_key": "interbank_liability_ratio",
            "metric_name": "同业负债 / (债券资产+同业资产)",
            "current_value": interbank_ratio,
            "threshold_value": thresholds["interbank_liability_ratio"],
            "status": _regulatory_metric_status(interbank_ratio, thresholds["interbank_liability_ratio"]),
            "calculation_note": "TYW 负债本金合计除以 ZQTZ 资产+TYW 资产面值合计；参考阈值表，非完整监管引擎。",
        },
        {
            "metric_key": "usd_exposure_ratio",
            "metric_name": "美元债券资产占比",
            "current_value": usd_ratio,
            "threshold_value": thresholds["usd_exposure_ratio"],
            "status": _regulatory_metric_status(usd_ratio, thresholds["usd_exposure_ratio"]),
            "calculation_note": "ZQTZ 资产端 USD 口径 face_value 合计 / 债券资产合计。",
        },
        {
            "metric_key": "portfolio_modified_duration",
            "metric_name": "组合剩余期限 proxy(年)",
            "current_value": duration_proxy,
            "threshold_value": thresholds["portfolio_modified_duration"],
            "status": _regulatory_metric_status(duration_proxy, thresholds["portfolio_modified_duration"]),
            "calculation_note": "以剩余年限加权的 proxy，不等同风险张量修正久期；无曲线与期权调整。",
        },
    ]

    return _table(
        "regulatory_limits",
        "监管参考阈值(初版)",
        [
            ("metric_key", "指标键"),
            ("metric_name", "指标名称"),
            ("current_value", "当前值"),
            ("threshold_value", "参考阈值"),
            ("status", "状态"),
            ("calculation_note", "口径说明"),
        ],
        rows,
    )


def _build_overdue_credit_quality_detail_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    overdue_rows = [
        row
        for row in asset_rows
        if row.overdue_principal_days > 0 or row.overdue_interest_days > 0
    ]
    rows = []
    for row in sorted(overdue_rows, key=lambda r: (r.instrument_code, r.portfolio_name)):
        rows.append(
            {
                "instrument_code": row.instrument_code,
                "instrument_name": row.instrument_name,
                "bond_type": row.bond_type,
                "rating": row.rating,
                "overdue_principal_days": row.overdue_principal_days,
                "overdue_interest_days": row.overdue_interest_days,
                "balance_amount": _to_wanyuan(row.face_value_amount),
            }
        )
    return _table(
        "overdue_credit_quality",
        "逾期与信用质量(明细)",
        [
            ("instrument_code", "代码"),
            ("instrument_name", "名称"),
            ("bond_type", "业务种类"),
            ("rating", "评级"),
            ("overdue_principal_days", "本金逾期天数"),
            ("overdue_interest_days", "利息逾期天数"),
            ("balance_amount", "面值/余额"),
        ],
        rows,
    )


def _build_overdue_credit_quality_rating_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    overdue_rows = [
        row
        for row in asset_rows
        if row.overdue_principal_days > 0 or row.overdue_interest_days > 0
    ]
    grouped = _group_rows(overdue_rows, lambda row: row.rating or "未评级/空")
    rows = []
    for rating_label, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "rating": rating_label,
                "row_count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
            }
        )
    return _table(
        "overdue_credit_quality_ratings",
        "逾期持仓评级汇总",
        [
            ("rating", "评级"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("weighted_rate_pct", "加权利率(%)"),
        ],
        rows,
    )


def _build_risk_alerts_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    maturity_gap = _build_maturity_gap_table(report_date, zqtz_rows, tyw_rows)
    negative_gap_rows = [row for row in maturity_gap["rows"] if _decimal_value(row.get("gap_amount")) < _ZERO]
    if negative_gap_rows:
        tightest_gap = min(negative_gap_rows, key=lambda row: _decimal_value(row.get("gap_amount")))
        rows.append(
            {
                "title": f"Negative gap in {tightest_gap['bucket']}",
                "severity": "high",
                "reason": f"Gap dropped to {tightest_gap['gap_amount']} wan yuan.",
                "source_section": "maturity_gap",
                "rule_id": "bal_wb_risk_gap_001",
                "rule_version": "v1",
            }
        )

    issuance_total = _sum_decimal(
        [row for row in zqtz_rows if row.position_scope == "liability"],
        lambda row: row.face_value_amount,
    )
    if issuance_total > _ZERO:
        rows.append(
            {
                "title": "Issuance liabilities outstanding",
                "severity": "medium",
                "reason": f"Issuance book totals {_to_wanyuan(issuance_total)} wan yuan.",
                "source_section": "issuance_business_types",
                "rule_id": "bal_wb_risk_issuance_001",
                "rule_version": "v1",
            }
        )

    rating_table = _build_rating_table(zqtz_rows)
    if rating_table["rows"]:
        top_rating = max(rating_table["rows"], key=lambda row: _decimal_value(row.get("share")))
        top_share = _decimal_value(top_rating.get("share"))
        if top_share >= Decimal("0.60"):
            rows.append(
                {
                    "title": f"{top_rating['rating']} concentration watch",
                    "severity": "medium" if top_share < Decimal("0.75") else "high",
                    "reason": f"Top rating bucket share reached {top_share:.4f}.",
                    "source_section": "rating_analysis",
                    "rule_id": "bal_wb_risk_rating_001",
                    "rule_version": "v1",
                }
            )

    return _section(
        "risk_alerts",
        "风险预警",
        "risk_alerts",
        [
            ("title", "Title"),
            ("severity", "Severity"),
            ("reason", "Reason"),
            ("source_section", "Source Section"),
            ("rule_id", "Rule Id"),
            ("rule_version", "Rule Version"),
        ],
        rows,
    )
