"""总账口径经营指标情况表（对标《2026年经营指标情况表》工作簿汇总结构）。

行结构复刻财务指标工作簿「财务指标-汇总」三大板块（财务指标 / 业务指标 /
资产质量指标）；可计算行的数值全部由 QDB 总账对账工作簿的科目期末余额
确定性组合得出：

- 损益类（累计口径）：总账损益科目年内累计余额组合。已与 2026 年财务指标
  工作簿在 202601 / 202602 / 202603 / 202503 四个期间逐项核对一致
  （营业收入、业务及管理费、减值损失、税金及附加、营业外净收支、
  利润总额、所得税、净利润）。
- 余额类（时点口径）：总账科目组合（QDB 源口径）。贷款余额与工作簿一致；
  存款余额 / 总资产 / 贷款减值准备余额与工作簿报表口径存在已知结构性
  差异，行内以 caliber_note 明示，不冒充报表口径。
- 无系统来源行（子公司、集团合并、不良、核销等）：value 置 None 并给出
  availability="no_system_source" 与原因；缺失不得以 0 值展示。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from backend.app.core_finance.config.classification_rules import (
    LEDGER_PNL_ACCOUNT_PREFIXES,
)

LEDGER_FINANCIAL_INDICATOR_SUMMARY_CONTRACT_VERSION = (
    "ledger-financial-indicator-summary-v1"
)

ZERO = Decimal("0")
ONE_HUNDRED_MILLION = Decimal("100000000")
MONEY_YI_QUANTUM = Decimal("0.0000000001")
PERCENT_QUANTUM = Decimal("0.000001")
IDENTITY_TOLERANCE_YUAN = Decimal("0.01")
# 借贷闭合检查用于发现结构性缺账；源工作簿存在分位级尾差（如 0.04 元），
# 故容差独立放宽到 1 元，不掩盖亿元级缺口。
BALANCE_IDENTITY_TOLERANCE_YUAN = Decimal("1")

# --- 总账科目组合（3 位 / 5 位科目前缀，leaf 口径求和） ---------------------
# A 股利润表口径营业收入：收入类科目贷方余额（负值取负号）扣除
# 利息支出 / 手续费支出类科目借方余额。
REVENUE_INCOME_PREFIXES = (
    "501",  # 贷款利息收入
    "502",  # 存放同业/拆放/回购利息收入
    "511",  # 手续费收入
    "512",  # 汇兑损益
    "513",  # 其他营业收入
    # 金融投资利息收入 / 公允价值变动损益 / 投资收益：引用 canonical 合并口径常量，
    # 不内联科目字面量（caliber subject_514_516_517_merge）。
    *LEDGER_PNL_ACCOUNT_PREFIXES,
    "518",  # 资产处置损益
    "519",  # 其他收益
)
REVENUE_EXPENSE_PREFIXES = (
    "521",  # 存款利息支出
    "522",  # 央行借款/同业/转贴现利息支出
    "523",  # 发行金融债利息支出
    "527",  # 手续费支出
)
OPEX_PREFIXES = ("529", "530")  # 业务及管理费 + 折旧
IMPAIRMENT_PREFIX = "531"
LOAN_IMPAIRMENT_PREFIX = "53101"
TAX_SURCHARGE_PREFIX = "533"
NONOP_INCOME_PREFIX = "515"  # 营业外收入（贷方）
NONOP_EXPENSE_PREFIXES = ("534", "536")  # 其他营业支出 + 营业外支出
INCOME_TAX_PREFIX = "550"
PNL_PREFIX = "5"

ASSET_PREFIX = "1"
# 与 qdb_gl_monthly_analysis 的 QDB 源口径保持同一科目集合。
LOAN_BALANCE_PREFIXES = ("122", "123", "129", "130", "132", "136")
DEPOSIT_BALANCE_PREFIXES = (
    "201", "202", "203", "204", "205", "211", "215",
    "216", "217", "225", "243", "244", "251",
)
LOAN_PROVISION_PREFIX = "131"

_BALANCE_IDENTITY_PREFIXES = ("1", "2", "3", "4", "5")

RowAvailability = Literal["ledger_computed", "no_system_source"]
RowBasis = Literal["flow", "point"]
RowValueKind = Literal["money_yi", "percent"]

_NO_SUBSIDIARY_SOURCE = "子公司（青银金租/青银理财/村镇银行）数据无系统来源，不能由总账推算"
_NO_GROUP_SOURCE = "集团合并口径依赖子公司数据与合并抵消，系统仅有母公司总账"
_NO_NPL_SOURCE = "五级分类（不良）数据不在总账科目中，无系统来源"
_NO_WRITEOFF_SOURCE = "核销/收回发生额属备查台账口径，总账余额无法唯一拆分，无系统来源"


@dataclass(frozen=True, slots=True)
class LedgerAccountBalance:
    """总账单科目期末余额（元，借方为正 / 贷方为负）。"""

    account_code: str
    ending_balance_yuan: Decimal


@dataclass(frozen=True, slots=True)
class _RowDef:
    row_id: str
    section_id: str
    name: str
    indent: int
    basis: RowBasis
    value_kind: RowValueKind
    component_id: str | None = None
    caliber_note: str | None = None
    unavailable_reason: str | None = None
    account_evidence: str | None = None


_SECTION_DEFS: tuple[tuple[str, str, str], ...] = (
    ("financial", "财务指标", "损益类 · 年内累计口径 · 与上年同期比较"),
    ("business", "业务指标", "余额类 · 时点口径 · 与上年末比较"),
    ("asset_quality", "资产质量指标", "核销/收回为累计口径，余额与比率为时点口径"),
)

_REVENUE_EVIDENCE = (
    "总账口径 = -(501+502+511+512+513+514+516+517+518+519 期末累计)"
    " - (521+522+523+527 期末累计)"
)

_ROW_DEFS: tuple[_RowDef, ...] = (
    # ---- 财务指标（损益，累计） ------------------------------------------
    _RowDef("fin.group_revenue", "financial", "一、集团营业收入", 0, "flow",
            "money_yi", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("fin.mother_revenue", "financial", "（一）母公司营收（并表口径）", 1,
            "flow", "money_yi", component_id="revenue",
            account_evidence=_REVENUE_EVIDENCE),
    _RowDef("fin.leasing_revenue", "financial", "（二）青银金租营收", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.wm_revenue", "financial", "（三）青银理财营收", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.village_revenue", "financial", "（四）村镇银行营收", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.group_opex", "financial", "二、业务及管理费", 0, "flow",
            "money_yi", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("fin.mother_opex", "financial", "（一）母公司费用", 1, "flow",
            "money_yi", component_id="opex",
            account_evidence="总账口径 = 529（业务及管理费）+ 530（折旧）期末累计"),
    _RowDef("fin.leasing_opex", "financial", "（二）青银金租费用", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.wm_opex", "financial", "（三）青银理财费用", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.village_opex", "financial", "（四）村镇银行费用", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.group_impairment", "financial", "三、减值损失", 0, "flow",
            "money_yi", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("fin.mother_impairment", "financial", "（一）母公司减值损失", 1,
            "flow", "money_yi", component_id="impairment",
            account_evidence="总账口径 = 531（资产减值损失）期末累计"),
    _RowDef("fin.mother_impairment_loan", "financial", "1.贷款减值损失", 2,
            "flow", "money_yi", component_id="impairment_loan",
            account_evidence="总账口径 = 53101（贷款减值损失）期末累计"),
    _RowDef("fin.mother_impairment_other", "financial", "2.其它资产减值损失", 2,
            "flow", "money_yi", component_id="impairment_other",
            account_evidence="总账口径 = 531 - 53101 期末累计"),
    _RowDef("fin.subsidiary_impairment", "financial", "（二）子公司减值损失", 1,
            "flow", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.village_impairment", "financial", "（三）村镇银行减值损失", 1,
            "flow", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.group_profit_total", "financial", "四、利润总额", 0, "flow",
            "money_yi", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("fin.mother_profit_total", "financial", "（一）母公司利润总额（并表口径）",
            1, "flow", "money_yi", component_id="profit_before_tax",
            account_evidence="总账口径 = 营业收入 - 业务及管理费 - 减值损失 - 税金及附加(533) + 营业外净收支(-(515)-534-536)"),
    _RowDef("fin.leasing_profit_total", "financial", "（二）青银金租利润总额", 1,
            "flow", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.wm_profit_total", "financial", "（三）青银理财利润总额", 1,
            "flow", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.group_net_profit", "financial", "五、净利润", 0, "flow",
            "money_yi", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("fin.mother_net_profit", "financial", "（一）母公司净利润（并表口径）",
            1, "flow", "money_yi", component_id="net_profit",
            account_evidence="总账口径 = 利润总额 - 所得税(550)；与 -(全部 5 类科目余额合计) 恒等校验"),
    _RowDef("fin.leasing_net_profit", "financial", "（二）青银金租净利润", 1,
            "flow", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.wm_net_profit", "financial", "（三）青银理财净利润", 1, "flow",
            "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.village_net_profit", "financial", "（四）村镇银行净利润", 1,
            "flow", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("fin.attributable_net_profit", "financial", "六、归母净利润", 0,
            "flow", "money_yi",
            unavailable_reason="归母净利润依赖合并抵消与少数股东损益，无系统来源"),
    _RowDef("fin.group_cost_income_ratio", "financial", "七、集团成本收入比", 0,
            "flow", "percent", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("fin.mother_cost_income_ratio", "financial", "（一）母公司成本收入比",
            1, "flow", "percent", component_id="cost_income_ratio_pct",
            caliber_note="补充行：工作簿汇总表仅列集团口径；本行按财务指标-计算表口径 = 母公司费用 / 母公司营收",
            account_evidence="总账口径 = (529+530) / 营业收入"),
    _RowDef("fin.group_roa", "financial", "八、集团ROA", 0, "flow", "percent",
            unavailable_reason="集团 ROA 依赖集团总资产与子公司数据，无系统来源"),
    _RowDef("fin.group_roe", "financial", "集团ROE", 0, "flow", "percent",
            unavailable_reason="集团 ROE 依赖集团权益结构（分红/永续债利息），无系统来源"),
    # ---- 业务指标（余额，时点） ------------------------------------------
    _RowDef("biz.group_total_assets", "business", "一、集团总资产", 0, "point",
            "money_yi", unavailable_reason=_NO_GROUP_SOURCE),
    _RowDef("biz.mother_total_assets", "business", "（一）母公司总资产", 1,
            "point", "money_yi", component_id="total_assets",
            caliber_note="总账 1 类科目净额口径；工作簿报表口径含重分类调整，两者存在结构性差异",
            account_evidence="总账口径 = 全部 1 类科目期末余额净额"),
    _RowDef("biz.leasing_total_assets", "business", "（二）青银金租总资产", 1,
            "point", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("biz.wm_total_assets", "business", "（三）青银理财总资产", 1,
            "point", "money_yi", unavailable_reason=_NO_SUBSIDIARY_SOURCE),
    _RowDef("biz.mother_loans", "business", "二、贷款余额（母公司）", 0, "point",
            "money_yi", component_id="loan_balance",
            caliber_note="总账科目组合口径；已与财务指标工作簿贷款余额核对一致",
            account_evidence="总账口径 = 122+123+129+130+132+136 期末余额"),
    _RowDef("biz.mother_deposits", "business", "三、存款余额（母公司）", 0,
            "point", "money_yi", component_id="deposit_balance",
            caliber_note="总账存款科目组合口径；工作簿报表口径含应计利息等调整，两者存在结构性差异",
            account_evidence="总账口径 = |201+202+203+204+205+211+215+216+217+225+243+244+251 期末余额|"),
    # ---- 资产质量指标 ----------------------------------------------------
    _RowDef("aq.writeoff", "asset_quality", "一、核销", 0, "flow", "money_yi",
            unavailable_reason=_NO_WRITEOFF_SOURCE),
    _RowDef("aq.writeoff_loan", "asset_quality", "（一）贷款核销", 1, "flow",
            "money_yi", unavailable_reason=_NO_WRITEOFF_SOURCE),
    _RowDef("aq.writeoff_other", "asset_quality", "（二）其他资产核销", 1, "flow",
            "money_yi", unavailable_reason=_NO_WRITEOFF_SOURCE),
    _RowDef("aq.recovery", "asset_quality", "二、核销后收回", 0, "flow",
            "money_yi", unavailable_reason=_NO_WRITEOFF_SOURCE),
    _RowDef("aq.recovery_loan", "asset_quality", "（一）贷款核销后收回", 1, "flow",
            "money_yi", unavailable_reason=_NO_WRITEOFF_SOURCE),
    _RowDef("aq.recovery_other", "asset_quality", "（二）其他资产核销后收回", 1,
            "flow", "money_yi", unavailable_reason=_NO_WRITEOFF_SOURCE),
    _RowDef("aq.provision_balance", "asset_quality", "三、减值准备余额", 0,
            "point", "money_yi",
            unavailable_reason="合计需其他资产减值准备管理口径，总账无唯一科目组合可复算"),
    _RowDef("aq.provision_loan_balance", "asset_quality", "（一）贷款减值准备余额",
            1, "point", "money_yi", component_id="loan_provision_balance",
            caliber_note="总账 131 科目余额口径；工作簿为管理滚动口径（期初+计提-核销+收回），两者存在口径差异",
            account_evidence="总账口径 = |131（贷款减值准备）期末余额|"),
    _RowDef("aq.provision_other_balance", "asset_quality",
            "（二）其他资产减值准备余额（母公司）", 1, "point", "money_yi",
            unavailable_reason="其他资产减值准备分散于多类备抵科目，无与工作簿一致的唯一总账组合"),
    _RowDef("aq.npl_amount", "asset_quality", "四、不良贷款额", 0, "point",
            "money_yi", unavailable_reason=_NO_NPL_SOURCE),
    _RowDef("aq.group_loans", "asset_quality", "五、贷款余额", 0, "point",
            "money_yi",
            unavailable_reason="工作簿此行为集团口径（含村镇银行），系统仅有母公司总账；母公司口径见业务指标板块"),
    _RowDef("aq.npl_ratio", "asset_quality", "六、不良贷款率", 0, "point",
            "percent", unavailable_reason=_NO_NPL_SOURCE),
    _RowDef("aq.provision_loan_ratio", "asset_quality", "七、拨贷比", 0, "point",
            "percent", component_id="provision_loan_ratio_pct",
            caliber_note="母公司总账口径 = 131 余额 / 母公司贷款余额；工作簿为集团管理口径，两者存在口径差异",
            account_evidence="总账口径 = |131| / (122+123+129+130+132+136)"),
    _RowDef("aq.coverage_ratio", "asset_quality", "八、拨备覆盖率", 0, "point",
            "percent", unavailable_reason=_NO_NPL_SOURCE),
)


def _leaf_balances(rows: Sequence[LedgerAccountBalance]) -> dict[str, Decimal]:
    """展开科目树为叶子科目余额（父科目余额剔除，避免层级双计）。"""
    merged: dict[str, Decimal] = {}
    for row in rows:
        code = str(row.account_code).strip()
        if not code:
            continue
        merged[code] = merged.get(code, ZERO) + row.ending_balance_yuan
    codes = sorted(merged)
    leaf: dict[str, Decimal] = {}
    for index, code in enumerate(codes):
        next_code = codes[index + 1] if index + 1 < len(codes) else None
        if next_code is not None and next_code.startswith(code):
            continue
        leaf[code] = merged[code]
    return leaf


def _sum_prefixes(leaf: Mapping[str, Decimal], prefixes: Sequence[str]) -> Decimal:
    return sum(
        (value for code, value in leaf.items() if code.startswith(tuple(prefixes))),
        ZERO,
    )


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return (numerator / denominator * Decimal("100")).quantize(PERCENT_QUANTUM)


def compute_ledger_indicator_components(
    rows: Sequence[LedgerAccountBalance],
) -> dict[str, Decimal | None]:
    """由总账科目期末余额计算全部可计算指标组件（金额单位：亿元）。"""
    leaf = _leaf_balances(rows)
    income_side = _sum_prefixes(leaf, REVENUE_INCOME_PREFIXES)
    expense_side = _sum_prefixes(leaf, REVENUE_EXPENSE_PREFIXES)
    revenue = -income_side - expense_side
    opex = _sum_prefixes(leaf, OPEX_PREFIXES)
    impairment = _sum_prefixes(leaf, (IMPAIRMENT_PREFIX,))
    impairment_loan = _sum_prefixes(leaf, (LOAN_IMPAIRMENT_PREFIX,))
    impairment_other = impairment - impairment_loan
    tax_surcharge = _sum_prefixes(leaf, (TAX_SURCHARGE_PREFIX,))
    nonop_net = (
        -_sum_prefixes(leaf, (NONOP_INCOME_PREFIX,))
        - _sum_prefixes(leaf, NONOP_EXPENSE_PREFIXES)
    )
    profit_before_tax = revenue - opex - impairment - tax_surcharge + nonop_net
    income_tax = _sum_prefixes(leaf, (INCOME_TAX_PREFIX,))
    net_profit = profit_before_tax - income_tax
    total_assets = _sum_prefixes(leaf, (ASSET_PREFIX,))
    loan_balance = _sum_prefixes(leaf, LOAN_BALANCE_PREFIXES)
    deposit_balance = -_sum_prefixes(leaf, DEPOSIT_BALANCE_PREFIXES)
    loan_provision_balance = -_sum_prefixes(leaf, (LOAN_PROVISION_PREFIX,))

    def yi(value: Decimal) -> Decimal:
        return (value / ONE_HUNDRED_MILLION).quantize(MONEY_YI_QUANTUM)

    components: dict[str, Decimal | None] = {
        "revenue": yi(revenue),
        "opex": yi(opex),
        "impairment": yi(impairment),
        "impairment_loan": yi(impairment_loan),
        "impairment_other": yi(impairment_other),
        "tax_surcharge": yi(tax_surcharge),
        "nonop_net": yi(nonop_net),
        "profit_before_tax": yi(profit_before_tax),
        "income_tax": yi(income_tax),
        "net_profit": yi(net_profit),
        "total_assets": yi(total_assets),
        "loan_balance": yi(loan_balance),
        "deposit_balance": yi(deposit_balance),
        "loan_provision_balance": yi(loan_provision_balance),
        "cost_income_ratio_pct": _percent(opex, revenue),
        "provision_loan_ratio_pct": _percent(loan_provision_balance, loan_balance),
    }
    # 恒等校验用原始"元"精度，避免亿元量化误差干扰容差判断。
    components["_identity_net_profit_gap_yuan"] = (
        -_sum_prefixes(leaf, (PNL_PREFIX,))
    ) - (profit_before_tax - income_tax)
    components["_balance_identity_gap_yuan"] = _sum_prefixes(
        leaf, _BALANCE_IDENTITY_PREFIXES
    )
    return components


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _period_label(year: int, month: int) -> str:
    return f"{year}年1月" if month == 1 else f"{year}年1-{month}月"


def _delta_cells(
    current: Decimal | None,
    compare: Decimal | None,
    value_kind: RowValueKind,
) -> tuple[Decimal | None, Decimal | None]:
    if current is None or compare is None:
        return None, None
    delta = current - compare
    if value_kind == "percent":
        # 比率行的"增减额"为百分点差；增减幅对比率无意义，置空。
        return delta.quantize(PERCENT_QUANTUM), None
    if compare == ZERO:
        return delta, None
    # 与工作簿口径一致：增减幅 = 增减额 / 对比期（直接相除，不取绝对值）。
    return delta, (delta / compare * Decimal("100")).quantize(PERCENT_QUANTUM)


def build_ledger_financial_indicator_summary(
    *,
    report_month: str,
    currency_basis: str,
    balances_by_month: Mapping[str, Sequence[LedgerAccountBalance] | None],
) -> dict[str, Any]:
    """构建经营指标情况表 payload。

    Args:
        report_month: 请求报告月 YYYYMM；期间组覆盖该年 1 月至该月。
        currency_basis: CNX / CNY（科目组合两种口径同构；与工作簿的数值
            核对仅在 CNX 完成）。
        balances_by_month: {YYYYMM: 总账科目余额列表}；缺失月份传 None 或
            不提供，对应期间列展示为空。
    """
    year = int(report_month[:4])
    month = int(report_month[4:6])

    components_by_month: dict[str, dict[str, Decimal | None]] = {}
    for month_key, rows in balances_by_month.items():
        if rows is None:
            continue
        components_by_month[month_key] = compute_ledger_indicator_components(rows)

    periods: list[dict[str, Any]] = []
    for m in range(1, month + 1):
        current_key = f"{year}{m:02d}"
        flow_compare_key = f"{year - 1}{m:02d}"
        point_compare_key = f"{year - 1}12"
        periods.append({
            "period_id": current_key,
            "flow_label": _period_label(year, m),
            "flow_compare_label": _period_label(year - 1, m),
            "point_label": f"{year}年{m}月末",
            "point_compare_label": f"{year - 1}年末",
            "current_month": current_key,
            "flow_compare_month": flow_compare_key,
            "point_compare_month": point_compare_key,
            "current_available": current_key in components_by_month,
            "flow_compare_available": flow_compare_key in components_by_month,
            "point_compare_available": point_compare_key in components_by_month,
        })

    def component_value(month_key: str, component_id: str) -> Decimal | None:
        components = components_by_month.get(month_key)
        if components is None:
            return None
        return components.get(component_id)

    sections: list[dict[str, Any]] = [
        {
            "section_id": section_id,
            "title": title,
            "basis_note": basis_note,
            "rows": [],
        }
        for section_id, title, basis_note in _SECTION_DEFS
    ]
    section_by_id = {section["section_id"]: section for section in sections}

    row_computed = 0
    for row_def in _ROW_DEFS:
        computed = row_def.component_id is not None
        values: list[dict[str, Any]] = []
        for period in periods:
            current: Decimal | None = None
            compare: Decimal | None = None
            if computed:
                compare_key = (
                    period["flow_compare_month"]
                    if row_def.basis == "flow"
                    else period["point_compare_month"]
                )
                current = component_value(
                    period["current_month"], row_def.component_id or ""
                )
                compare = component_value(compare_key, row_def.component_id or "")
            delta, delta_pct = _delta_cells(current, compare, row_def.value_kind)
            values.append({
                "period_id": period["period_id"],
                "current": _fmt(current),
                "compare": _fmt(compare),
                "delta": _fmt(delta),
                "delta_pct": _fmt(delta_pct),
            })
        if computed:
            row_computed += 1
        section_by_id[row_def.section_id]["rows"].append({
            "row_id": row_def.row_id,
            "name": row_def.name,
            "indent": row_def.indent,
            "basis": row_def.basis,
            "value_kind": row_def.value_kind,
            "availability": (
                "ledger_computed" if computed else "no_system_source"
            ),
            "caliber_note": row_def.caliber_note,
            "unavailable_reason": row_def.unavailable_reason,
            "account_evidence": row_def.account_evidence,
            "values": values,
        })

    quality_checks: list[dict[str, Any]] = []
    for month_key in sorted(components_by_month):
        components = components_by_month[month_key]
        identity_gap = components.get("_identity_net_profit_gap_yuan")
        balance_gap = components.get("_balance_identity_gap_yuan")
        quality_checks.append({
            "check_id": "net_profit_identity",
            "month": month_key,
            "passed": identity_gap is not None
            and abs(identity_gap) <= IDENTITY_TOLERANCE_YUAN,
            "gap_yuan": _fmt(identity_gap),
            "message": "净利润(利润总额-所得税)与 -(全部损益科目余额合计) 恒等",
        })
        quality_checks.append({
            "check_id": "balance_identity",
            "month": month_key,
            "passed": balance_gap is not None
            and abs(balance_gap) <= BALANCE_IDENTITY_TOLERANCE_YUAN,
            "gap_yuan": _fmt(balance_gap),
            "message": "资产(1类) = 负债(2类)+权益(3类)+递延(4类)+当期损益(5类) 借贷闭合",
        })

    row_total = len(_ROW_DEFS)
    return {
        "contract_version": LEDGER_FINANCIAL_INDICATOR_SUMMARY_CONTRACT_VERSION,
        "title": f"{year}年经营指标情况表（总账口径）",
        "report_month": report_month,
        "report_year": year,
        "currency_basis": currency_basis,
        "unit": "亿元",
        "data_status": (
            "ready" if f"{year}{month:02d}" in components_by_month else "no_data"
        ),
        "periods": periods,
        "sections": sections,
        "quality_checks": quality_checks,
        "coverage": {
            "row_total": row_total,
            "row_computed": row_computed,
            "row_unavailable": row_total - row_computed,
        },
        "notes": [
            "损益类行按总账损益科目年内累计余额组合计算，已与财务指标工作簿在 CNX 口径逐项核对（202601/202602/202603/202503）。",
            "余额类行为总账科目组合口径（QDB 源口径）；存款余额、总资产、贷款减值准备余额与工作簿报表口径存在已知结构性差异，见行内口径说明。",
            "无系统来源行（子公司、集团合并、不良、核销等）保持空值展示，不以 0 值代替；补数需先登记对应数据源。",
            "CNY 口径按同一科目组合计算，净利润与借贷闭合两项恒等校验在真实总账数据上全部通过（202401/202412/202501-202503/202512/202601-202603）；财务指标工作簿仅提供 CNX 基准，CNY 无工作簿数值可核对。",
        ],
    }
