from __future__ import annotations

from copy import deepcopy
from typing import Any

SAMPLE_ID = "GS-LEDGER-PNL-FIN-IND-202603-B"
SOURCE_VERSION = "sv_formal_financial_indicators_excel_202603_contract"
RULE_VERSION = "rv_formal_financial_indicators_source_status_v1"
SOURCE_WORKBOOK = "C:/Users/arvin/Desktop/2026年财务指标表-3月最终(1).xlsx"
SOURCE_SHEET = "财务指标-汇总"

STATUS_SEMANTICS = {
    "formal_pending": "Excel has the formal indicator value, but the governed production source is not connected. System value must remain null, not zero.",
    "candidate_qdb_aligned": "QDB analytical value aligns to the Excel value within display precision, but remains analytical until formally approved.",
    "needs_reconciliation": "QDB has a related analytical value, but it does not reconcile to the Excel formal value.",
}

_FORMAL_PENDING_REASON = "正式财务指标来源未接入；系统值必须保持为空，不能用 0 或 QDB 分析值顶替。"
_CANDIDATE_REASON = "正式财务指标来源未接入；QDB 分析值仅作为候选对照，不具备正式使用权限。"
_RECONCILIATION_REASON = "正式财务指标来源未接入；QDB 分析值与 Excel 正式样本存在差异，需先对账。"

_METRICS_202603: tuple[dict[str, Any], ...] = (
    {
        "metric_key": "group.operating_revenue",
        "metric_name": "集团营业收入",
        "scope": "group_consolidated",
        "excel_value": "43.4194731314",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K5 -> 财务指标-计算表!K5",
        "formula": "=4341947313.14/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "parent.operating_revenue.consolidated_basis",
        "metric_name": "母公司营收（并表口径）",
        "scope": "parent_company_consolidated_basis",
        "excel_value": "40.5057623568",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K6 -> 财务指标-计算表!K52",
        "formula": "external/formal calculation table input",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.business_admin_expense",
        "metric_name": "业务及管理费",
        "scope": "group_consolidated",
        "excel_value": "9.7335327322",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K10 -> 财务指标-计算表!K10",
        "formula": "=973353273.22/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.impairment_loss",
        "metric_name": "减值损失",
        "scope": "group_consolidated",
        "excel_value": "13.8794270584",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K15 -> 财务指标-计算表!K15",
        "formula": "=1387942705.84/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.loan_impairment_loss",
        "metric_name": "贷款减值损失",
        "scope": "group_consolidated",
        "excel_value": "13.0832767606",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K17 -> 财务指标-计算表!K55",
        "formula": "=13.0832767606",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.profit_before_tax",
        "metric_name": "利润总额",
        "scope": "group_consolidated",
        "excel_value": "19.3364859160",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K21 -> 财务指标-计算表!K18",
        "formula": "=1933648591.6/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.net_profit",
        "metric_name": "净利润",
        "scope": "group_consolidated",
        "excel_value": "15.7131099579",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K25 -> 财务指标-计算表!K19",
        "formula": "=1571310995.79/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "parent.net_profit",
        "metric_name": "母公司净利润",
        "scope": "parent_company",
        "excel_value": "13.9118472050",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K26 -> 财务指标-计算表!K20",
        "formula": "external/formal calculation table input",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.net_profit_attributable_to_parent",
        "metric_name": "归母净利润",
        "scope": "group_consolidated",
        "excel_value": "15.2421024586",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K30 -> 财务指标-计算表!K24",
        "formula": "=1524210245.86/100000000",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.cost_income_ratio",
        "metric_name": "集团成本收入比",
        "scope": "group_consolidated",
        "excel_value": "22.4174363027",
        "unit": "%",
        "excel_ref": "财务指标-汇总!K31",
        "formula": "财务指标-汇总!K31 = K10 / K5",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.roa",
        "metric_name": "集团ROA",
        "scope": "group_consolidated",
        "excel_value": "0.7622345868",
        "unit": "%",
        "excel_ref": "财务指标-汇总!K32 -> 财务指标-计算表!K26",
        "formula": "=+K19/((K30+L30)/2)*4",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.roe",
        "metric_name": "集团ROE",
        "scope": "group_consolidated",
        "excel_value": "14.6348772016",
        "unit": "%",
        "excel_ref": "财务指标-汇总!K33 -> 财务指标-计算表!K27",
        "formula": "=+(K24/3*12-K38)/(L32-L37+K24/2+K40/2)",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "group.total_assets",
        "metric_name": "集团总资产",
        "scope": "group_consolidated",
        "excel_value": "8342.0254700000",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K35 -> 财务指标-计算表!K30",
        "formula": "=834202547/100000",
        "source_status": "needs_reconciliation",
        "system_metric": "qdb.total_assets_ledger",
        "system_value": "8144.05",
        "reconciliation_gap": "197.97547",
    },
    {
        "metric_key": "parent.loan_balance",
        "metric_name": "贷款余额（母公司）",
        "scope": "parent_company",
        "excel_value": "4189.4674724087",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K39 -> 财务指标-计算表!K76",
        "formula": "external/formal calculation table input",
        "source_status": "candidate_qdb_aligned",
        "system_metric": "qdb.loan_spot",
        "system_value": "4189.47",
        "reconciliation_gap": "0.0025275913",
    },
    {
        "metric_key": "parent.deposit_balance",
        "metric_name": "存款余额（母公司）",
        "scope": "parent_company",
        "excel_value": "5120.6380974646",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K40 -> 财务指标-计算表!K74",
        "formula": "external/formal calculation table input",
        "source_status": "needs_reconciliation",
        "system_metric": "qdb.deposit_spot",
        "system_value": "5115.96",
        "reconciliation_gap": "4.6780974646",
    },
    {
        "metric_key": "asset_quality.loan_loss_provision_balance",
        "metric_name": "贷款减值准备余额",
        "scope": "group_asset_quality",
        "excel_value": "122.7295998170",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K50 -> 财务指标-计算表!K43",
        "formula": "=+K79+K121",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "asset_quality.npl_balance",
        "metric_name": "不良贷款额",
        "scope": "group_asset_quality",
        "excel_value": "40.1588772655",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K52 -> 财务指标-计算表!K42",
        "formula": "external/formal calculation table input",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "asset_quality.loan_balance",
        "metric_name": "贷款余额（集团资产质量口径）",
        "scope": "group_asset_quality",
        "excel_value": "4193.9954022127",
        "unit": "亿元",
        "excel_ref": "财务指标-汇总!K53 -> 财务指标-计算表!K41",
        "formula": "=+K76+K119",
        "source_status": "needs_reconciliation",
        "system_metric": "qdb.loan_spot",
        "system_value": "4189.47",
        "reconciliation_gap": "4.5254022127",
    },
    {
        "metric_key": "asset_quality.npl_ratio",
        "metric_name": "不良贷款率",
        "scope": "group_asset_quality",
        "excel_value": "0.9575326965",
        "unit": "%",
        "excel_ref": "财务指标-汇总!K54 = K52 / K53",
        "formula": "财务指标-汇总!K54 = K52 / K53",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
    {
        "metric_key": "asset_quality.loan_loss_reserve_ratio",
        "metric_name": "拨贷比",
        "scope": "group_asset_quality",
        "excel_value": "2.9263169853",
        "unit": "%",
        "excel_ref": "财务指标-汇总!K55 = K50 / K53",
        "formula": "财务指标-汇总!K55 = K50 / K53",
        "source_status": "needs_reconciliation",
        "system_metric": "qdb.loan_loss_reserve_ratio",
        "system_value": "2.70",
        "reconciliation_gap": "0.2263169853",
    },
    {
        "metric_key": "asset_quality.provision_coverage_ratio",
        "metric_name": "拨备覆盖率",
        "scope": "group_asset_quality",
        "excel_value": "305.6101369706",
        "unit": "%",
        "excel_ref": "财务指标-汇总!K56 = K50 / K52",
        "formula": "财务指标-汇总!K56 = K50 / K52",
        "source_status": "formal_pending",
        "system_metric": None,
        "system_value": None,
    },
)


def build_formal_financial_indicator_contract(*, report_month: str) -> dict[str, Any]:
    normalized_month = str(report_month or "").strip()
    if normalized_month != "202603":
        raise ValueError(f"Unsupported formal financial indicator contract month: {report_month!r}")

    metrics = [_with_contract_fields(metric) for metric in deepcopy(_METRICS_202603)]
    return {
        "sample_id": SAMPLE_ID,
        "sample_status": "contract_fixture",
        "surface": "/ledger-pnl formal financial indicator source contract",
        "report_month": "202603",
        "report_date": "2026-03-31",
        "source_workbook": SOURCE_WORKBOOK,
        "source_sheet": SOURCE_SHEET,
        "source_basis": "Excel 2026-03 formal financial indicator table supplied by user",
        "source_version": SOURCE_VERSION,
        "rule_version": RULE_VERSION,
        "formal_use_allowed": False,
        "contract_note": (
            "This contract freezes the Excel formal-indicator sample and current source status. "
            "It is not approval to promote analytical QDB values to formal financial indicators."
        ),
        "status_semantics": dict(STATUS_SEMANTICS),
        "metrics": metrics,
    }


def _with_contract_fields(metric: dict[str, Any]) -> dict[str, Any]:
    source_status = str(metric["source_status"])
    metric_key = str(metric["metric_key"])
    metric["value"] = None
    metric["basis"] = "formal_financial_indicator_source_contract"
    metric["formal_use_allowed"] = False
    metric["source_version"] = SOURCE_VERSION
    metric["rule_version"] = RULE_VERSION
    metric["consolidation_scope"] = metric["scope"]
    metric["cell_ref"] = metric["excel_ref"]
    metric["golden_sample_ref"] = f"{SAMPLE_ID}#{metric_key}"
    metric["missing_reason"] = _missing_reason(source_status)
    return metric


def _missing_reason(source_status: str) -> str:
    if source_status == "candidate_qdb_aligned":
        return _CANDIDATE_REASON
    if source_status == "needs_reconciliation":
        return _RECONCILIATION_REASON
    return _FORMAL_PENDING_REASON
