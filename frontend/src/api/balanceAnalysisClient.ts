/**
 * Balance Analysis domain client slice.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatus,
  BalanceAnalysisDecisionStatusRecord,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisDatesPayload,
  BalanceCurrencyBasis,
  BalanceAnalysisAdvancedAttributionBundlePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisWorkbookPayload,
  BalancePositionScope,
  BalanceAnalysisRefreshPayload,
  BalanceAnalysisSummaryExportPayload,
  BalanceAnalysisWorkbookExportPayload,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisTableRow,
} from "./contracts";

export type BalanceAnalysisClientMethods = {
  getBalanceAnalysisDates: () => Promise<ApiEnvelope<BalanceAnalysisDatesPayload>>;
  getBalanceAnalysisOverview: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisOverviewPayload>>;
  getBalanceAnalysisSummary: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<BalanceAnalysisSummaryTablePayload>>;
  getBalanceAnalysisWorkbook: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisWorkbookPayload>>;
  getBalanceAnalysisCurrentUser: () => Promise<BalanceAnalysisCurrentUserPayload>;
  getBalanceAnalysisDecisionItems: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisDecisionItemsPayload>>;
  updateBalanceAnalysisDecisionStatus: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    decisionKey: string;
    status: BalanceAnalysisDecisionStatus;
    comment?: string;
  }) => Promise<BalanceAnalysisDecisionStatusRecord>;
  getBalanceAnalysisDetail: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisPayload>>;
  getBalanceAnalysisSummaryByBasis: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisBasisBreakdownPayload>>;
  getBalanceAnalysisAdvancedAttribution: (options: {
    reportDate: string;
    scenarioName?: string;
    treasuryShiftBp?: number;
    spreadShiftBp?: number;
  }) => Promise<ApiEnvelope<BalanceAnalysisAdvancedAttributionBundlePayload>>;
  exportBalanceAnalysisSummaryCsv: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<BalanceAnalysisSummaryExportPayload>;
  exportBalanceAnalysisWorkbookXlsx: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<BalanceAnalysisWorkbookExportPayload>;
  refreshBalanceAnalysis: (reportDate: string) => Promise<BalanceAnalysisRefreshPayload>;
  getBalanceAnalysisRefreshStatus: (
    runId: string,
  ) => Promise<BalanceAnalysisRefreshPayload>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type BalanceAnalysisMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureBalanceAnalysisMockBundle = () => Promise<BalanceAnalysisMockBundle>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

type RequestActionJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
) => Promise<T>;

type RequestText = (
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename?: string,
) => Promise<{ content: string; filename: string }>;

type RequestBlob = (
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename?: string,
) => Promise<{ content: Blob; filename: string }>;

export type BalanceAnalysisClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  requestActionJson: RequestActionJson;
  requestText: RequestText;
  requestBlob: RequestBlob;
};

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

function parseBalanceAmount(raw: BalanceAnalysisTableRow[BalanceAnalysisAmountField]): number {
  const parsed = Number.parseFloat(String(raw));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatBalanceAmountDecimal(value: number): string {
  return value.toFixed(2);
}

function sumBalanceAmount(
  rows: readonly BalanceAnalysisTableRow[],
  field: BalanceAnalysisAmountField,
): number {
  return rows.reduce((sum, row) => sum + parseBalanceAmount(row[field]), 0);
}

function divideBalanceAmount(
  row: BalanceAnalysisTableRow,
  field: BalanceAnalysisAmountField,
): string {
  const divisor = Math.max(1, row.detail_row_count);
  return formatBalanceAmountDecimal(parseBalanceAmount(row[field]) / divisor);
}

function buildBalanceAnalysisOverviewPayload(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisOverviewPayload {
  const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const assetRows = rows.filter((row) => row.position_scope === "asset");
  const liabilityRows = rows.filter((row) => row.position_scope === "liability");
  return {
    report_date: reportDate,
    position_scope: positionScope,
    currency_basis: currencyBasis,
    detail_row_count: rows.reduce((sum, row) => sum + row.detail_row_count, 0),
    summary_row_count: rows.length,
    total_market_value_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(rows, "market_value_amount"),
    ),
    total_amortized_cost_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(rows, "amortized_cost_amount"),
    ),
    total_accrued_interest_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(rows, "accrued_interest_amount"),
    ),
    asset_total_market_value_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(assetRows, "market_value_amount"),
    ),
    liability_total_market_value_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(liabilityRows, "market_value_amount"),
    ),
    asset_total_amortized_cost_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(assetRows, "amortized_cost_amount"),
    ),
    liability_total_amortized_cost_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(liabilityRows, "amortized_cost_amount"),
    ),
    asset_total_accrued_interest_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(assetRows, "accrued_interest_amount"),
    ),
    liability_total_accrued_interest_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(liabilityRows, "accrued_interest_amount"),
    ),
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
  const wrap = (await import("../mocks/mockApiEnvelope")).buildMockApiEnvelope;
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
  const wrap = (await import("../mocks/mockApiEnvelope")).buildMockApiEnvelope;
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
          label: "净头寸",
          value: "648.00",
          note: "资产端合计 - 同业负债。",
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
            { key: "gap_amount", label: "缺口" },
          ],
          rows: [
            {
              bucket: "1-2年",
              gap_amount: "648.00",
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
              balance_amount: "180.00",
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
              reason: "期限桶缺口为 648.00 万元。",
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
  const wrap = (await import("../mocks/mockApiEnvelope")).buildMockApiEnvelope;
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
          reason: "期限桶缺口为 648.00 万元。",
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

export function createRealBalanceAnalysisClient(
  options: BalanceAnalysisClientFactoryOptions,
): BalanceAnalysisClientMethods {
  const { fetchImpl, baseUrl, requestJson, requestActionJson, requestText, requestBlob } = options;

  return {
    getBalanceAnalysisDates: () =>
      requestJson<BalanceAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/dates",
      ),
    getBalanceAnalysisOverview: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/overview?${params.toString()}`,
      );
    },
    getBalanceAnalysisSummary: ({
      reportDate,
      positionScope,
      currencyBasis,
      limit,
      offset,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
        limit: String(limit),
        offset: String(offset),
      });
      return requestJson<BalanceAnalysisSummaryTablePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary?${params.toString()}`,
      );
    },
    getBalanceAnalysisWorkbook: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook?${params.toString()}`,
      );
    },
    getBalanceAnalysisCurrentUser: () =>
      requestActionJson<BalanceAnalysisCurrentUserPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/current-user",
      ),
    getBalanceAnalysisDecisionItems: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisDecisionItemsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/decision-items?${params.toString()}`,
      );
    },
    updateBalanceAnalysisDecisionStatus: ({
      reportDate,
      positionScope,
      currencyBasis,
      decisionKey,
      status,
      comment,
    }) =>
      requestActionJson<BalanceAnalysisDecisionStatusRecord>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/decision-items/status",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            report_date: reportDate,
            position_scope: positionScope,
            currency_basis: currencyBasis,
            decision_key: decisionKey,
            status,
            comment,
          }),
        },
      ),
    getBalanceAnalysisDetail: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis?${params.toString()}`,
      );
    },
    getBalanceAnalysisSummaryByBasis: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisBasisBreakdownPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary-by-basis?${params.toString()}`,
      );
    },
    getBalanceAnalysisAdvancedAttribution: ({
      reportDate,
      scenarioName,
      treasuryShiftBp,
      spreadShiftBp,
    }) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (scenarioName) {
        params.set("scenario_name", scenarioName);
      }
      if (treasuryShiftBp !== undefined) {
        params.set("treasury_shift_bp", String(treasuryShiftBp));
      }
      if (spreadShiftBp !== undefined) {
        params.set("spread_shift_bp", String(spreadShiftBp));
      }
      return requestJson<BalanceAnalysisAdvancedAttributionBundlePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/advanced-attribution?${params.toString()}`,
      );
    },
    exportBalanceAnalysisSummaryCsv: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary/export?${params.toString()}`,
        "balance-analysis-summary.csv",
      );
    },
    exportBalanceAnalysisWorkbookXlsx: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestBlob(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook/export?${params.toString()}`,
        "balance-analysis-workbook.xlsx",
      );
    },
    refreshBalanceAnalysis: (reportDate: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBalanceAnalysisRefreshStatus: (runId: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),  };
}
