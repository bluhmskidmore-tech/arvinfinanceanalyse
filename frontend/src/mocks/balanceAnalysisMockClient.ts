/**
 * Demo/mock BalanceAnalysis client.
 * Loaded only by mock composition paths and tests.
 */
import type {
  ApiEnvelope,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisMetricDefinition,
  BalanceCurrencyBasis,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisWorkbookPayload,
  BalancePositionScope,
  BalanceAnalysisSummaryExportPayload,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisTableRow,
} from "../api/contracts";
import type { BalanceAnalysisClientMethods } from "../api/balanceAnalysisClient";
type Delay = () => Promise<void>;

type BalanceAnalysisMockBundle = Pick<
  typeof import("./mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureBalanceAnalysisMockBundle = () => Promise<BalanceAnalysisMockBundle>;

function buildBalanceAnalysisTableRows(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisTableRow[] {
  const rows: BalanceAnalysisTableRow[] = [
    {
      row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
      source_family: "zqtz",
      display_name: "240001.IB",
      owner_name: "利率债组合",
      category_name: "交易账户",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "A",
      accounting_basis: "FVOCI",
      detail_row_count: 3,
      market_value_amount: "72000000000.00",
      amortized_cost_amount: "64800000000.00",
      accrued_interest_amount: "3600000000.00",
    },
    {
      row_key: "tyw:repo-1:CNY:liability:H:AC",
      source_family: "tyw",
      display_name: "repo-1",
      owner_name: "同业负债池",
      category_name: "卖出回购",
      position_scope: "liability",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 1,
      market_value_amount: "7200000000.00",
      amortized_cost_amount: "7200000000.00",
      accrued_interest_amount: "1440000000.00",
    },
    {
      row_key: "zqtz:240002.IB:portfolio-b:cc-2:CNY:asset:H:AC",
      source_family: "zqtz",
      display_name: "240002.IB",
      owner_name: "高等级组合",
      category_name: "摊余成本",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 2,
      market_value_amount: "41000000000.00",
      amortized_cost_amount: "40300000000.00",
      accrued_interest_amount: "2000000000.00",
    },
  ];
  return rows.filter((row) => {
    const matchesScope = positionScope === "all" || row.position_scope === positionScope;
    const matchesBasis = row.currency_basis === currencyBasis;
    return matchesScope && matchesBasis;
  });
}

type BalanceAnalysisAmountField =
  | "market_value_amount"
  | "amortized_cost_amount"
  | "accrued_interest_amount";

export function parseBalanceAmount(
  raw: BalanceAnalysisTableRow[BalanceAnalysisAmountField],
): number {
  const normalized = String(raw).trim();
  const parsed = Number(normalized);
  if (normalized === "" || !Number.isFinite(parsed)) {
    throw new Error(`Invalid mock balance amount: ${String(raw)}`);
  }
  return parsed;
}

function formatBalanceAmountDecimal(value: number): string {
  return value.toFixed(2);
}

function divideBalanceAmount(
  row: BalanceAnalysisTableRow,
  field: BalanceAnalysisAmountField,
): string {
  const divisor = Math.max(1, row.detail_row_count);
  return formatBalanceAmountDecimal(parseBalanceAmount(row[field]) / divisor);
}

type BalanceAnalysisOverviewTotals = Omit<
  BalanceAnalysisOverviewPayload,
  "report_date" | "position_scope" | "currency_basis" | "metric_definitions"
>;

/**
 * 与后端 `_balance_analysis_metric_definitions`（balance_analysis_service.py）逐项对照的
 * 演示口径元数据；后端此字段恒返回，Demo 客户端固定复用同一份定义描述。
 */
export const BALANCE_ANALYSIS_METRIC_DEFINITIONS: BalanceAnalysisMetricDefinition[] = [
  {
    key: "asset_total_market_value_amount",
    label: "资产市值合计",
    source_field: "market_value_amount",
    raw_unit: "yuan",
    display_unit: "yi_yuan",
    basis: "formal",
    source_surface: "formal_balance",
    applies_to: ["overview", "summary", "detail"],
    description: "正式资产头寸市值金额合计；后端返回元，页面按亿元展示。",
  },
  {
    key: "asset_total_amortized_cost_amount",
    label: "资产摊余成本合计",
    source_field: "amortized_cost_amount",
    raw_unit: "yuan",
    display_unit: "yi_yuan",
    basis: "formal",
    source_surface: "formal_balance",
    applies_to: ["overview", "summary", "detail"],
    description: "正式资产头寸摊余成本金额合计；后端返回元，页面按亿元展示。",
  },
  {
    key: "asset_total_accrued_interest_amount",
    label: "资产应计利息合计",
    source_field: "accrued_interest_amount",
    raw_unit: "yuan",
    display_unit: "yi_yuan",
    basis: "formal",
    source_surface: "formal_balance",
    applies_to: ["overview", "summary", "detail"],
    description: "正式资产头寸应计利息金额合计；后端返回元，页面按亿元展示。",
  },
  {
    key: "liability_total_market_value_amount",
    label: "负债市值合计",
    source_field: "market_value_amount",
    raw_unit: "yuan",
    display_unit: "yi_yuan",
    basis: "formal",
    source_surface: "formal_balance",
    applies_to: ["overview", "summary", "detail"],
    description: "正式负债头寸市值金额合计；后端返回元，页面按亿元展示。",
  },
  {
    key: "liability_total_amortized_cost_amount",
    label: "负债摊余成本合计",
    source_field: "amortized_cost_amount",
    raw_unit: "yuan",
    display_unit: "yi_yuan",
    basis: "formal",
    source_surface: "formal_balance",
    applies_to: ["overview", "summary", "detail"],
    description: "正式负债头寸摊余成本金额合计；后端返回元，页面按亿元展示。",
  },
  {
    key: "liability_total_accrued_interest_amount",
    label: "负债应计利息合计",
    source_field: "accrued_interest_amount",
    raw_unit: "yuan",
    display_unit: "yi_yuan",
    basis: "formal",
    source_surface: "formal_balance",
    applies_to: ["overview", "summary", "detail"],
    description: "正式负债头寸应计利息金额合计；后端返回元，页面按亿元展示。",
  },
];

const ZERO_BALANCE_ANALYSIS_OVERVIEW_TOTALS: BalanceAnalysisOverviewTotals = {
  detail_row_count: 0,
  summary_row_count: 0,
  total_market_value_amount: "0.00",
  total_amortized_cost_amount: "0.00",
  total_accrued_interest_amount: "0.00",
  asset_total_market_value_amount: "0.00",
  liability_total_market_value_amount: "0.00",
  asset_total_amortized_cost_amount: "0.00",
  liability_total_amortized_cost_amount: "0.00",
  asset_total_accrued_interest_amount: "0.00",
  liability_total_accrued_interest_amount: "0.00",
};

/**
 * Demo 专用固定总账口径：数值对照 `buildBalanceAnalysisTableRows` 的静态样例行手工核算
 * 一次性得出，不在前端按 position_scope/currency_basis 对行数据做 reduce 重新聚合
 * （正式汇总口径只归后端 core_finance 所有）。样例行的 currency_basis 均为 "CNY"，
 * 故 "native" 口径下无匹配行，总计为 0。
 */
const BALANCE_ANALYSIS_OVERVIEW_FIXTURES: Record<
  BalanceCurrencyBasis,
  Record<BalancePositionScope, BalanceAnalysisOverviewTotals>
> = {
  CNY: {
    all: {
      detail_row_count: 6,
      summary_row_count: 3,
      total_market_value_amount: "120200000000.00",
      total_amortized_cost_amount: "112300000000.00",
      total_accrued_interest_amount: "7040000000.00",
      asset_total_market_value_amount: "113000000000.00",
      liability_total_market_value_amount: "7200000000.00",
      asset_total_amortized_cost_amount: "105100000000.00",
      liability_total_amortized_cost_amount: "7200000000.00",
      asset_total_accrued_interest_amount: "5600000000.00",
      liability_total_accrued_interest_amount: "1440000000.00",
    },
    asset: {
      detail_row_count: 5,
      summary_row_count: 2,
      total_market_value_amount: "113000000000.00",
      total_amortized_cost_amount: "105100000000.00",
      total_accrued_interest_amount: "5600000000.00",
      asset_total_market_value_amount: "113000000000.00",
      liability_total_market_value_amount: "0.00",
      asset_total_amortized_cost_amount: "105100000000.00",
      liability_total_amortized_cost_amount: "0.00",
      asset_total_accrued_interest_amount: "5600000000.00",
      liability_total_accrued_interest_amount: "0.00",
    },
    liability: {
      detail_row_count: 1,
      summary_row_count: 1,
      total_market_value_amount: "7200000000.00",
      total_amortized_cost_amount: "7200000000.00",
      total_accrued_interest_amount: "1440000000.00",
      asset_total_market_value_amount: "0.00",
      liability_total_market_value_amount: "7200000000.00",
      asset_total_amortized_cost_amount: "0.00",
      liability_total_amortized_cost_amount: "7200000000.00",
      asset_total_accrued_interest_amount: "0.00",
      liability_total_accrued_interest_amount: "1440000000.00",
    },
  },
  native: {
    all: ZERO_BALANCE_ANALYSIS_OVERVIEW_TOTALS,
    asset: ZERO_BALANCE_ANALYSIS_OVERVIEW_TOTALS,
    liability: ZERO_BALANCE_ANALYSIS_OVERVIEW_TOTALS,
  },
};

function buildBalanceAnalysisOverviewPayload(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisOverviewPayload {
  return {
    report_date: reportDate,
    position_scope: positionScope,
    currency_basis: currencyBasis,
    metric_definitions: BALANCE_ANALYSIS_METRIC_DEFINITIONS,
    ...BALANCE_ANALYSIS_OVERVIEW_FIXTURES[currencyBasis][positionScope],
  };
}

function buildBalanceAnalysisDetailRows(
  reportDate: string,
  rows: readonly BalanceAnalysisTableRow[],
): BalanceAnalysisPayload["details"] {
  return rows.flatMap((row) => {
    const count = Math.max(1, row.detail_row_count);
    return Array.from({ length: count }, (_, index) => ({
      source_family: row.source_family,
      report_date: reportDate,
      row_key: `${row.row_key}:detail-${index + 1}`,
      display_name: count === 1 ? row.display_name : `${row.display_name} #${index + 1}`,
      position_scope: row.position_scope,
      currency_basis: row.currency_basis,
      invest_type_std: row.invest_type_std,
      accounting_basis: row.accounting_basis,
      market_value_amount: divideBalanceAmount(row, "market_value_amount"),
      amortized_cost_amount: divideBalanceAmount(row, "amortized_cost_amount"),
      accrued_interest_amount: divideBalanceAmount(row, "accrued_interest_amount"),
      is_issuance_like: row.source_family === "zqtz" ? false : null,
    }));
  });
}

function buildBalanceAnalysisDetailSummary(
  rows: readonly BalanceAnalysisTableRow[],
): BalanceAnalysisPayload["summary"] {
  return rows.map((row) => ({
    source_family: row.source_family,
    position_scope: row.position_scope,
    currency_basis: row.currency_basis,
    row_count: row.detail_row_count,
    market_value_amount: row.market_value_amount,
    amortized_cost_amount: row.amortized_cost_amount,
    accrued_interest_amount: row.accrued_interest_amount,
  }));
}

function buildBalanceAnalysisBasisRows(
  rows: readonly BalanceAnalysisTableRow[],
): BalanceAnalysisBasisBreakdownPayload["rows"] {
  return rows.map((row) => ({
    source_family: row.source_family,
    invest_type_std: row.invest_type_std,
    accounting_basis: row.accounting_basis,
    position_scope: row.position_scope,
    currency_basis: row.currency_basis,
    detail_row_count: row.detail_row_count,
    market_value_amount: row.market_value_amount,
    amortized_cost_amount: row.amortized_cost_amount,
    accrued_interest_amount: row.accrued_interest_amount,
  }));
}

async function buildMockBalanceAnalysisSummaryTable(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
  limit: number,
  offset: number,
): Promise<ApiEnvelope<BalanceAnalysisSummaryTablePayload>> {
  const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const wrap = (await import("./mockApiEnvelope")).buildMockApiEnvelope;
  return wrap(
    "balance-analysis.summary",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      limit,
      offset,
      total_rows: rows.length,
      rows: rows.slice(offset, offset + limit),
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

function buildMockBalanceAnalysisSummaryCsv(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisSummaryExportPayload {
  const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const headers = [
    "row_key",
    "source_family",
    "display_name",
    "owner_name",
    "category_name",
    "position_scope",
    "currency_basis",
    "invest_type_std",
    "accounting_basis",
    "detail_row_count",
    "market_value_amount",
    "amortized_cost_amount",
    "accrued_interest_amount",
    "report_date",
    "source_version",
    "rule_version",
  ];
  const lines = rows.map((row) =>
    [
      row.row_key,
      row.source_family,
      row.display_name,
      row.owner_name,
      row.category_name,
      row.position_scope,
      row.currency_basis,
      row.invest_type_std,
      row.accounting_basis,
      String(row.detail_row_count),
      String(row.market_value_amount),
      String(row.amortized_cost_amount),
      String(row.accrued_interest_amount),
      reportDate,
      "sv_balance_mock",
      "rv_balance_analysis_formal_materialize_v1",
    ].join(","),
  );
  return {
    filename: `balance-analysis-summary-${reportDate}-${positionScope}-${currencyBasis}.csv`,
    content: [headers.join(","), ...lines].join("\n"),
  };
}

async function buildMockBalanceAnalysisWorkbook(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): Promise<ApiEnvelope<BalanceAnalysisWorkbookPayload>> {
  const wrap = (await import("./mockApiEnvelope")).buildMockApiEnvelope;
  return wrap(
    "balance-analysis.workbook",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      cards: [
        {
          key: "bond_assets_excluding_issue",
          label: "债券资产(剔除发行类)",
          value: "720.00",
          note: "ZQTZ 资产端剔除发行类后的余额。",
        },
        {
          key: "interbank_assets",
          label: "同业资产",
          value: "36.00",
          note: "TYW 资产端余额。",
        },
        {
          key: "interbank_liabilities",
          label: "同业负债",
          value: "72.00",
          note: "TYW 负债端余额。",
        },
        {
          key: "issuance_liabilities",
          label: "发行类负债",
          value: "18.00",
          note: "ZQTZ 发行类单列余额。",
        },
        {
          key: "net_position",
          label: "全口径余额净头寸",
          value: "666.00",
          note: "资产端合计 - 全口径负债（发行类 + 同业负债）。",
        },
      ],
      tables: [
        {
          key: "bond_business_types",
          title: "债券业务种类",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              bond_type: "政策性金融债",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "maturity_gap",
          title: "期限缺口分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "期限分类" },
            { key: "bond_assets_amount", label: "债券资产" },
            { key: "interbank_assets_amount", label: "同业资产" },
            { key: "asset_total_amount", label: "资产合计" },
            { key: "issuance_amount", label: "发行类" },
            { key: "interbank_liabilities_amount", label: "同业负债" },
            { key: "full_scope_liability_amount", label: "全口径负债" },
            { key: "gap_amount", label: "缺口" },
            { key: "full_scope_gap_amount", label: "全口径缺口" },
          ],
          rows: [
            {
              bucket: "1-2年",
              bond_assets_amount: "720.00",
              interbank_assets_amount: "36.00",
              asset_total_amount: "756.00",
              issuance_amount: "18.00",
              interbank_liabilities_amount: "72.00",
              full_scope_liability_amount: "90.00",
              gap_amount: "684.00",
              full_scope_gap_amount: "666.00",
            },
          ],
        },
        {
          key: "rating_analysis",
          title: "信用评级分析",
          section_kind: "table",
          columns: [
            { key: "rating", label: "评级" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              rating: "AAA",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "issuance_business_types",
          title: "发行类分析",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "金额" },
          ],
          rows: [
            {
              bond_type: "同业存单",
              balance_amount: "18.00",
            },
          ],
        },
        {
          key: "industry_distribution",
          title: "行业分布",
          section_kind: "table",
          columns: [
            { key: "industry_name", label: "行业" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              industry_name: "金融业",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "rate_distribution",
          title: "利率分布分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "利率区间" },
            { key: "bond_amount", label: "债券面值" },
            { key: "interbank_asset_amount", label: "同业资产" },
            { key: "interbank_liability_amount", label: "同业负债" },
          ],
          rows: [
            {
              bucket: "1.5%-2.0%",
              bond_amount: "9900.75",
              interbank_asset_amount: "958.00",
              interbank_liability_amount: "2206.08",
            },
          ],
        },
        {
          key: "counterparty_types",
          title: "对手方类型",
          section_kind: "table",
          columns: [
            { key: "counterparty_type", label: "对手方类型" },
            { key: "asset_amount", label: "资产金额" },
            { key: "liability_amount", label: "负债金额" },
            { key: "net_position_amount", label: "净头寸" },
          ],
          rows: [
            {
              counterparty_type: "股份制银行",
              asset_amount: "120.00",
              liability_amount: "86.08",
              net_position_amount: "33.92",
            },
          ],
        },
        {
          key: "interest_modes",
          title: "计息方式",
          section_kind: "table",
          columns: [
            { key: "interest_mode", label: "计息方式" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              interest_mode: "固定",
              balance_amount: "32874.42",
            },
          ],
        },
      ],
      operational_sections: [
        {
          key: "decision_items",
          title: "决策事项",
          section_kind: "decision_items",
          columns: [
            { key: "title", label: "标题" },
            { key: "action_label", label: "动作" },
            { key: "severity", label: "等级" },
            { key: "reason", label: "原因" },
          ],
          rows: [
            {
              title: "复核 1-2 年期限缺口配置",
              action_label: "复核缺口",
              severity: "high",
              reason: "全口径期限桶缺口为 666.00 万元。",
              source_section: "期限缺口",
              rule_id: "bal_wb_decision_gap_001",
              rule_version: "v1",
            },
          ],
        },
        {
          key: "event_calendar",
          title: "事件日历",
          section_kind: "event_calendar",
          columns: [
            { key: "event_date", label: "事件日期" },
            { key: "event_type", label: "事件类型" },
            { key: "title", label: "标题" },
            { key: "impact_hint", label: "影响提示" },
          ],
          rows: [
            {
              event_date: "2026-01-31",
              event_type: "asset_maturity",
              title: "资产一到期",
              source: "内部治理日程",
              impact_hint: "资产账簿 / 拆放同业",
              source_section: "期限缺口",
            },
            {
              event_date: "2026-02-05",
              event_type: "funding_rollover",
              title: "回购一到期",
              source: "内部治理日程",
              impact_hint: "负债账簿 / 卖出回购",
              source_section: "期限缺口",
            },
          ],
        },
        {
          key: "risk_alerts",
          title: "风险预警",
          section_kind: "risk_alerts",
          columns: [
            { key: "title", label: "标题" },
            { key: "severity", label: "等级" },
            { key: "reason", label: "原因" },
          ],
          rows: [
            {
              title: "发行负债余额仍在账",
              severity: "medium",
              reason: "发行账簿合计 18.00 万元。",
              source_section: "发行类业务",
              rule_id: "bal_wb_risk_issuance_001",
              rule_version: "v1",
            },
            {
              title: "1-2 年期限桶为负缺口",
              severity: "high",
              reason: "缺口降至 -128.00 万元。",
              source_section: "期限缺口",
              rule_id: "bal_wb_risk_gap_001",
              rule_version: "v1",
            },
          ],
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

async function buildMockBalanceAnalysisDecisionItems(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): Promise<ApiEnvelope<BalanceAnalysisDecisionItemsPayload>> {
  const wrap = (await import("./mockApiEnvelope")).buildMockApiEnvelope;
  return wrap(
    "balance-analysis.decision-items",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      columns: [
        { key: "title", label: "标题" },
        { key: "action_label", label: "动作" },
        { key: "severity", label: "等级" },
        { key: "reason", label: "原因" },
        { key: "source_section", label: "来源区块" },
        { key: "rule_id", label: "规则编号" },
        { key: "rule_version", label: "规则版本" },
      ],
      rows: [
        {
          decision_key: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
          title: "复核 1-2 年期限缺口配置",
          action_label: "复核缺口",
          severity: "high",
          reason: "全口径期限桶缺口为 666.00 万元。",
          source_section: "期限缺口",
          rule_id: "bal_wb_decision_gap_001",
          rule_version: "v1",
          latest_status: {
            decision_key:
              "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
            status: "pending",
            updated_at: null,
            updated_by: null,
            comment: null,
          },
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

export function createDemoBalanceAnalysisClient(
  delay: Delay,
  ensureMockClientBundle: EnsureBalanceAnalysisMockBundle,
): BalanceAnalysisClientMethods {
  return {
    async getBalanceAnalysisDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.dates",
        {
          report_dates: ["2025-12-31"],
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisPublicationStatus() {
      await delay();
      return {
        enabled: false,
        available: false,
        generation: null,
        report_dates: [],
        manifest_sha256: null,
        quality_flag: "stale",
        reason: "Balance-analysis publication reads are disabled.",
      };
    },
    async getBalanceAnalysisOverview({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.overview",
        buildBalanceAnalysisOverviewPayload(reportDate, positionScope, currencyBasis),
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisDetail({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
      const baseDetails = buildBalanceAnalysisDetailRows(reportDate, rows);
      const summary = buildBalanceAnalysisDetailSummary(rows);
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.detail",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          details: baseDetails,
          summary,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisSummaryByBasis({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const rows = buildBalanceAnalysisBasisRows(
        buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis),
      );
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.basis_breakdown",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          rows,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisAdvancedAttribution({ reportDate }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.advanced_attribution_bundle",
        {
          report_date: reportDate,
          mode: "analytical",
          scenario_name: null,
          scenario_inputs: {},
          upstream_summaries: {},
          status: "not_ready",
          missing_inputs: ["phase3_yield_curves_aligned_to_instruments"],
          blocked_components: ["roll_down", "rate_effect"],
          warnings: [
            "债券分析三期：骑乘与利率效应需要三期曲线和交易数据",
            "资产负债高级归因包：状态未就绪；未返回归因数值",
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          source_version: "sv_advanced_attribution_not_ready",
          rule_version: "rv_advanced_attribution_bundle_v0",
          cache_version: "cv_advanced_attribution_v0",
        },
      );
    },
    async getBalanceAnalysisSummary({ reportDate, positionScope, currencyBasis, limit, offset }) {
      await delay();
      return await buildMockBalanceAnalysisSummaryTable(
        reportDate,
        positionScope,
        currencyBasis,
        limit,
        offset,
      );
    },
    async getBalanceAnalysisWorkbook({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return await buildMockBalanceAnalysisWorkbook(reportDate, positionScope, currencyBasis);
    },
    async getBalanceAnalysisCurrentUser() {
      await delay();
      return {
        user_id: "phase1-dev-user",
        role: "admin",
        identity_source: "fallback",
        can_write_decision_status: true,
      };
    },
    async getBalanceAnalysisDecisionItems({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return await buildMockBalanceAnalysisDecisionItems(reportDate, positionScope, currencyBasis);
    },
    async updateBalanceAnalysisDecisionStatus({
      decisionKey,
      status,
      comment,
    }) {
      await delay();
      return {
        decision_key: decisionKey,
        status,
        updated_at: "2026-04-12T08:00:00Z",
        updated_by: "phase1-dev-user",
        comment: comment ?? null,
      };
    },
    async exportBalanceAnalysisSummaryCsv({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisSummaryCsv(reportDate, positionScope, currencyBasis);
    },
    async exportBalanceAnalysisWorkbookXlsx({ reportDate }) {
      await delay();
      return {
        filename: `资产负债分析_${reportDate}.xlsx`,
        content: new Blob(["mock-workbook"], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      };
    },
    async refreshBalanceAnalysis(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "balance_analysis_materialize:mock-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "async",
        cache_key: "balance_analysis:materialize:formal",
        report_date: reportDate,
      };
    },
    async getBalanceAnalysisRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "balance_analysis_materialize",
        trigger_mode: "terminal",
        cache_key: "balance_analysis:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_balance_mock",
        rule_version: "rv_balance_analysis_formal_materialize_v1",
      };
    },
  };
}
