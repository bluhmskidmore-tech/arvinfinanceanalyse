/**
 * Mock payloads for the Ledger P&L domain.
 * Extracted from client.ts to reduce monolith size.
 */
import type {
  LedgerMoneyValue,
  LedgerPnlAccountDetailBasisSnapshot,
  LedgerPnlAccountDetailCanonicalEvidenceRow,
  LedgerPnlAccountDetailPayload,
  LedgerPnlAnalysisPayload,
  LedgerPnlCandidateFinancialIndicatorLineage,
  LedgerPnlCandidateFinancialIndicatorPeriodComparison,
  LedgerPnlCandidateFinancialIndicatorsPayload,
  LedgerPnlCandidateFinancialIndicatorsResultMeta,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalIndicatorRuleChecksPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  LedgerPnlDataPayload,
} from "../api/contracts";
import candidateFinancialIndicatorFixture from "./fixtures/ledgerPnlCandidateFinancialIndicators202606.json";

const mockLedgerMoney = (yuan: string) => ({
  yuan,
  yi: (Number(yuan) / 100_000_000).toFixed(2),
  wan: (Number(yuan) / 10_000).toFixed(2),
});

function reportMonthEnd(reportMonth: string): string {
  if (!/^\d{6}$/.test(reportMonth)) return "";
  const year = Number(reportMonth.slice(0, 4));
  const month = Number(reportMonth.slice(4, 6));
  if (month < 1 || month > 12) return "";
  const day = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return `${reportMonth.slice(0, 4)}-${reportMonth.slice(4, 6)}-${String(day).padStart(2, "0")}`;
}

export type MockLedgerPnlCurrencyBasis = "CNX" | "CNY";

export const MOCK_LEDGER_PNL_DEFAULT_CURRENCY_BASIS: MockLedgerPnlCurrencyBasis = "CNX";
export const MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE = "CNX=综本；CNY=人民币账";
export const MOCK_LEDGER_PNL_RULE_VERSION = "rv_ledger_pnl_v2";
export const MOCK_LEDGER_PNL_CACHE_VERSION = "cv_ledger_pnl_v2";
export const MOCK_LEDGER_PNL_ANALYSIS_RULE_VERSION = "rv_ledger_pnl_analysis_v1";
export const MOCK_LEDGER_PNL_ANALYSIS_CACHE_VERSION = "cv_ledger_pnl_analysis_v1";
export const MOCK_LEDGER_PNL_ACCOUNT_DETAIL_RULE_VERSION = "rv_ledger_pnl_account_detail_v1";
export const MOCK_LEDGER_PNL_ACCOUNT_DETAIL_CACHE_VERSION = "cv_ledger_pnl_account_detail_v1";
export const MOCK_LEDGER_PNL_TABLES_USED = [
  "qdb_gl_ledger_reconciliation_workbook",
  "qdb_gl_average_balance_workbook",
];

export const mockLedgerPnlDates: LedgerPnlDatesPayload = {
  dates: ["2025-12-31", "2025-11-30"],
};

export const mockLedgerPnlSummaryByBasis: Record<MockLedgerPnlCurrencyBasis, LedgerPnlSummaryPayload> = {
  CNX: {
    report_date: "2025-12-31",
    source_version: "sv_mock_ledger_v2",
    ledger_total_assets: mockLedgerMoney("1250000000"),
    ledger_total_liabilities: mockLedgerMoney("980000000"),
    ledger_net_assets: mockLedgerMoney("270000000"),
    ledger_monthly_pnl_core: mockLedgerMoney("3520000"),
    ledger_monthly_pnl_all: mockLedgerMoney("4180000"),
    by_currency: [{ currency: "CNX", total_pnl: mockLedgerMoney("4180000") }],
    by_account: [
      {
        account_code: "514100",
        account_name: "利息收入",
        total_pnl: mockLedgerMoney("2120000"),
        count: 18,
      },
      {
        account_code: "516100",
        account_name: "公允价值变动损益",
        total_pnl: mockLedgerMoney("880000"),
        count: 9,
      },
      {
        account_code: "517100",
        account_name: "投资收益",
        total_pnl: mockLedgerMoney("520000"),
        count: 6,
      },
      {
        account_code: "519900",
        account_name: "其他损益",
        total_pnl: mockLedgerMoney("660000"),
        count: 4,
      },
    ],
  },
  CNY: {
    report_date: "2025-12-31",
    source_version: "sv_mock_ledger_v2",
    ledger_total_assets: mockLedgerMoney("1120000000"),
    ledger_total_liabilities: mockLedgerMoney("870000000"),
    ledger_net_assets: mockLedgerMoney("250000000"),
    ledger_monthly_pnl_core: mockLedgerMoney("3000000"),
    ledger_monthly_pnl_all: mockLedgerMoney("3400000"),
    by_currency: [{ currency: "CNY", total_pnl: mockLedgerMoney("3400000") }],
    by_account: [
      {
        account_code: "514100",
        account_name: "利息收入",
        total_pnl: mockLedgerMoney("1900000"),
        count: 15,
      },
      {
        account_code: "516100",
        account_name: "公允价值变动损益",
        total_pnl: mockLedgerMoney("700000"),
        count: 7,
      },
      {
        account_code: "517100",
        account_name: "投资收益",
        total_pnl: mockLedgerMoney("400000"),
        count: 4,
      },
      {
        account_code: "519900",
        account_name: "其他损益",
        total_pnl: mockLedgerMoney("400000"),
        count: 3,
      },
    ],
  },
};

export const mockLedgerPnlDataByBasis: Record<MockLedgerPnlCurrencyBasis, LedgerPnlDataPayload> = {
  CNX: {
    report_date: "2025-12-31",
    items: [
      {
        account_code: "514100",
        account_name: "利息收入",
        currency: "CNX",
        beginning_balance: mockLedgerMoney("101200000"),
        ending_balance: mockLedgerMoney("106500000"),
        monthly_pnl: mockLedgerMoney("2120000"),
        daily_avg_balance: mockLedgerMoney("104100000"),
        days_in_period: 31,
      },
      {
        account_code: "516100",
        account_name: "公允价值变动损益",
        currency: "CNX",
        beginning_balance: mockLedgerMoney("10000000"),
        ending_balance: mockLedgerMoney("11200000"),
        monthly_pnl: mockLedgerMoney("880000"),
        daily_avg_balance: mockLedgerMoney("10600000"),
        days_in_period: 31,
      },
      {
        account_code: "517100",
        account_name: "投资收益",
        currency: "CNX",
        beginning_balance: mockLedgerMoney("22000000"),
        ending_balance: mockLedgerMoney("23500000"),
        monthly_pnl: mockLedgerMoney("520000"),
        daily_avg_balance: mockLedgerMoney("22800000"),
        days_in_period: 31,
      },
      {
        account_code: "519900",
        account_name: "其他损益",
        currency: "CNX",
        beginning_balance: mockLedgerMoney("4000000"),
        ending_balance: mockLedgerMoney("4500000"),
        monthly_pnl: mockLedgerMoney("660000"),
        daily_avg_balance: mockLedgerMoney("4250000"),
        days_in_period: 31,
      },
    ],
    summary: {
      total_pnl_cnx: mockLedgerMoney("4180000"),
      total_pnl_cny: mockLedgerMoney("0"),
      total_pnl: mockLedgerMoney("4180000"),
      count: 4,
    },
  },
  CNY: {
    report_date: "2025-12-31",
    items: [
      {
        account_code: "514100",
        account_name: "利息收入",
        currency: "CNY",
        beginning_balance: mockLedgerMoney("92000000"),
        ending_balance: mockLedgerMoney("96500000"),
        monthly_pnl: mockLedgerMoney("1900000"),
        daily_avg_balance: mockLedgerMoney("94200000"),
        days_in_period: 31,
      },
      {
        account_code: "516100",
        account_name: "公允价值变动损益",
        currency: "CNY",
        beginning_balance: mockLedgerMoney("8000000"),
        ending_balance: mockLedgerMoney("8700000"),
        monthly_pnl: mockLedgerMoney("700000"),
        daily_avg_balance: mockLedgerMoney("8350000"),
        days_in_period: 31,
      },
      {
        account_code: "517100",
        account_name: "投资收益",
        currency: "CNY",
        beginning_balance: mockLedgerMoney("18000000"),
        ending_balance: mockLedgerMoney("18800000"),
        monthly_pnl: mockLedgerMoney("400000"),
        daily_avg_balance: mockLedgerMoney("18400000"),
        days_in_period: 31,
      },
      {
        account_code: "519900",
        account_name: "其他损益",
        currency: "CNY",
        beginning_balance: mockLedgerMoney("3000000"),
        ending_balance: mockLedgerMoney("3400000"),
        monthly_pnl: mockLedgerMoney("400000"),
        daily_avg_balance: mockLedgerMoney("3200000"),
        days_in_period: 31,
      },
    ],
    summary: {
      total_pnl_cnx: mockLedgerMoney("0"),
      total_pnl_cny: mockLedgerMoney("3400000"),
      total_pnl: mockLedgerMoney("3400000"),
      count: 4,
    },
  },
};

const mockLedgerPnlSummary202511ByBasis: Record<
  MockLedgerPnlCurrencyBasis,
  LedgerPnlSummaryPayload
> = {
  CNX: {
    ...mockLedgerPnlSummaryByBasis.CNX,
    report_date: "2025-11-30",
    source_version: "sv_mock_ledger_analysis_v1_previous",
    ledger_total_assets: mockLedgerMoney("1200000000"),
    ledger_total_liabilities: mockLedgerMoney("950000000"),
    ledger_net_assets: mockLedgerMoney("250000000"),
    ledger_monthly_pnl_core: mockLedgerMoney("3100000"),
    ledger_monthly_pnl_all: mockLedgerMoney("3700000"),
    by_currency: [{ currency: "CNX", total_pnl: mockLedgerMoney("3700000") }],
    by_account: [
      {
        ...mockLedgerPnlSummaryByBasis.CNX.by_account[0],
        total_pnl: mockLedgerMoney("1900000"),
        count: 16,
      },
      {
        ...mockLedgerPnlSummaryByBasis.CNX.by_account[1],
        total_pnl: mockLedgerMoney("750000"),
        count: 8,
      },
      {
        ...mockLedgerPnlSummaryByBasis.CNX.by_account[2],
        total_pnl: mockLedgerMoney("450000"),
        count: 5,
      },
      {
        ...mockLedgerPnlSummaryByBasis.CNX.by_account[3],
        total_pnl: mockLedgerMoney("600000"),
        count: 3,
      },
    ],
  },
  CNY: {
    ...mockLedgerPnlSummaryByBasis.CNY,
    report_date: "2025-11-30",
    source_version: "sv_mock_ledger_analysis_v1_previous",
    ledger_total_assets: mockLedgerMoney("1080000000"),
    ledger_total_liabilities: mockLedgerMoney("840000000"),
    ledger_net_assets: mockLedgerMoney("240000000"),
    ledger_monthly_pnl_core: mockLedgerMoney("2800000"),
    ledger_monthly_pnl_all: mockLedgerMoney("3150000"),
    by_currency: [{ currency: "CNY", total_pnl: mockLedgerMoney("3150000") }],
    by_account: [
      {
        ...mockLedgerPnlSummaryByBasis.CNY.by_account[0],
        total_pnl: mockLedgerMoney("1750000"),
        count: 14,
      },
      {
        ...mockLedgerPnlSummaryByBasis.CNY.by_account[1],
        total_pnl: mockLedgerMoney("650000"),
        count: 6,
      },
      {
        ...mockLedgerPnlSummaryByBasis.CNY.by_account[2],
        total_pnl: mockLedgerMoney("400000"),
        count: 4,
      },
      {
        ...mockLedgerPnlSummaryByBasis.CNY.by_account[3],
        total_pnl: mockLedgerMoney("350000"),
        count: 3,
      },
    ],
  },
};

const mockLedgerPnlData202511ByBasis: Record<
  MockLedgerPnlCurrencyBasis,
  LedgerPnlDataPayload
> = {
  CNX: {
    report_date: "2025-11-30",
    items: [
      {
        ...mockLedgerPnlDataByBasis.CNX.items[0],
        beginning_balance: mockLedgerMoney("98200000"),
        ending_balance: mockLedgerMoney("102800000"),
        monthly_pnl: mockLedgerMoney("1900000"),
        daily_avg_balance: mockLedgerMoney("100500000"),
        days_in_period: 30,
      },
      {
        ...mockLedgerPnlDataByBasis.CNX.items[1],
        beginning_balance: mockLedgerMoney("9000000"),
        ending_balance: mockLedgerMoney("9900000"),
        monthly_pnl: mockLedgerMoney("750000"),
        daily_avg_balance: mockLedgerMoney("9450000"),
        days_in_period: 30,
      },
      {
        ...mockLedgerPnlDataByBasis.CNX.items[2],
        beginning_balance: mockLedgerMoney("20500000"),
        ending_balance: mockLedgerMoney("21800000"),
        monthly_pnl: mockLedgerMoney("450000"),
        daily_avg_balance: mockLedgerMoney("21150000"),
        days_in_period: 30,
      },
      {
        ...mockLedgerPnlDataByBasis.CNX.items[3],
        beginning_balance: mockLedgerMoney("3200000"),
        ending_balance: mockLedgerMoney("3900000"),
        monthly_pnl: mockLedgerMoney("600000"),
        daily_avg_balance: mockLedgerMoney("3550000"),
        days_in_period: 30,
      },
    ],
    summary: {
      total_pnl_cnx: mockLedgerMoney("3700000"),
      total_pnl_cny: mockLedgerMoney("0"),
      total_pnl: mockLedgerMoney("3700000"),
      count: 4,
    },
  },
  CNY: {
    report_date: "2025-11-30",
    items: [
      {
        ...mockLedgerPnlDataByBasis.CNY.items[0],
        beginning_balance: mockLedgerMoney("88000000"),
        ending_balance: mockLedgerMoney("92300000"),
        monthly_pnl: mockLedgerMoney("1750000"),
        daily_avg_balance: mockLedgerMoney("90100000"),
        days_in_period: 30,
      },
      {
        ...mockLedgerPnlDataByBasis.CNY.items[1],
        beginning_balance: mockLedgerMoney("7200000"),
        ending_balance: mockLedgerMoney("7950000"),
        monthly_pnl: mockLedgerMoney("650000"),
        daily_avg_balance: mockLedgerMoney("7575000"),
        days_in_period: 30,
      },
      {
        ...mockLedgerPnlDataByBasis.CNY.items[2],
        beginning_balance: mockLedgerMoney("16500000"),
        ending_balance: mockLedgerMoney("17400000"),
        monthly_pnl: mockLedgerMoney("400000"),
        daily_avg_balance: mockLedgerMoney("16950000"),
        days_in_period: 30,
      },
      {
        ...mockLedgerPnlDataByBasis.CNY.items[3],
        beginning_balance: mockLedgerMoney("2400000"),
        ending_balance: mockLedgerMoney("2800000"),
        monthly_pnl: mockLedgerMoney("350000"),
        daily_avg_balance: mockLedgerMoney("2600000"),
        days_in_period: 30,
      },
    ],
    summary: {
      total_pnl_cnx: mockLedgerMoney("0"),
      total_pnl_cny: mockLedgerMoney("3150000"),
      total_pnl: mockLedgerMoney("3150000"),
      count: 4,
    },
  },
};

export const mockLedgerPnlEvidenceRowsByBasis: Record<
  MockLedgerPnlCurrencyBasis,
  { summary: number; data: number }
> = {
  CNX: { summary: 37, data: 4 },
  CNY: { summary: 29, data: 4 },
};

export const mockLedgerPnlSummary = mockLedgerPnlSummaryByBasis.CNX;
export const mockLedgerPnlData = mockLedgerPnlDataByBasis.CNX;

const mockLedgerPnlBasisComparison: LedgerPnlAnalysisPayload["basis_comparison"] = [
  {
    metric_key: "assets",
    metric_name: "总资产",
    cnx: mockLedgerMoney("1250000000"),
    cny: mockLedgerMoney("1120000000"),
    cnx_minus_cny: mockLedgerMoney("130000000"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 1, CNY: 1 },
  },
  {
    metric_key: "liabilities",
    metric_name: "总负债",
    cnx: mockLedgerMoney("980000000"),
    cny: mockLedgerMoney("870000000"),
    cnx_minus_cny: mockLedgerMoney("110000000"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 1, CNY: 1 },
  },
  {
    metric_key: "net_assets",
    metric_name: "净资产",
    cnx: mockLedgerMoney("270000000"),
    cny: mockLedgerMoney("250000000"),
    cnx_minus_cny: mockLedgerMoney("20000000"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 2, CNY: 2 },
  },
  {
    metric_key: "core_pnl",
    metric_name: "核心损益",
    cnx: mockLedgerMoney("3520000"),
    cny: mockLedgerMoney("3000000"),
    cnx_minus_cny: mockLedgerMoney("520000"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 37, CNY: 29 },
  },
  {
    metric_key: "all_pnl",
    metric_name: "全量损益",
    cnx: mockLedgerMoney("4180000"),
    cny: mockLedgerMoney("3400000"),
    cnx_minus_cny: mockLedgerMoney("780000"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 37, CNY: 29 },
  },
  {
    metric_key: "other_5_pnl",
    metric_name: "其他 5* 损益",
    cnx: mockLedgerMoney("660000"),
    cny: mockLedgerMoney("400000"),
    cnx_minus_cny: mockLedgerMoney("260000"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 37, CNY: 29 },
  },
];

const mockLedgerPnlCalculationBasis: LedgerPnlAnalysisPayload["calculation_basis"] = {
  core_pnl_prefixes: ["514", "516", "517"],
  all_pnl_prefixes: ["5"],
  other_5_pnl_formula: "all_pnl - core_pnl",
  other_5_pnl_boundary: "arithmetic residual within 5* accounts; not a formal attribution category",
  basis_difference_formula: "CNX - CNY",
  basis_boundary: "CNX 与 CNY 是重叠账务口径，不可相加；基差不是 FX PnL。",
  basis_availability_boundary:
    "basis_availability reports PnL analyzability only; balance metric availability and evidence are reported per comparison row",
  metric_boundary: "candidate ledger analysis; not formal PnL",
  previous_period_rule: "previous available ledger report date",
};

export const mockLedgerPnlAnalysisByBasis: Record<
  MockLedgerPnlCurrencyBasis,
  LedgerPnlAnalysisPayload
> = {
  CNX: {
    report_date: "2025-12-31",
    source_version: "sv_mock_ledger_v2",
    currency_basis: "CNX",
    basis_availability: { CNX: "ready", CNY: "ready" },
    analysis_status: "ready",
    metric_status: "candidate",
    conclusion: {
      direction: "positive",
      other_effect: "support",
      core_pnl: mockLedgerMoney("3520000"),
      other_5_pnl: mockLedgerMoney("660000"),
      all_pnl: mockLedgerMoney("4180000"),
    },
    pnl_bridge: {
      components: [
        { metric_key: "core_pnl", metric_name: "核心损益", amount: mockLedgerMoney("3520000") },
        { metric_key: "other_5_pnl", metric_name: "其他 5* 损益", amount: mockLedgerMoney("660000") },
      ],
      total: mockLedgerMoney("4180000"),
      residual: mockLedgerMoney("0"),
    },
    basis_comparison: mockLedgerPnlBasisComparison,
    contributors: {
      positive_total: mockLedgerMoney("4180000"),
      negative_total: mockLedgerMoney("0"),
      net_total: mockLedgerMoney("4180000"),
      top_positive: [
        {
          rank: 1,
          account_code: "514100",
          account_name: "利息收入",
          amount: mockLedgerMoney("2120000"),
          count: 18,
        },
        {
          rank: 2,
          account_code: "516100",
          account_name: "公允价值变动损益",
          amount: mockLedgerMoney("880000"),
          count: 9,
        },
        {
          rank: 3,
          account_code: "519900",
          account_name: "其他损益",
          amount: mockLedgerMoney("660000"),
          count: 4,
        },
        {
          rank: 4,
          account_code: "517100",
          account_name: "投资收益",
          amount: mockLedgerMoney("520000"),
          count: 6,
        },
      ],
      top_negative: [],
    },
    period_comparison: {
      status: "available",
      previous_report_date: "2025-11-30",
      previous_source_version: "sv_mock_ledger_analysis_v1_previous",
      rows: [
        {
          metric_key: "core_pnl",
          metric_name: "核心损益",
          current: mockLedgerMoney("3520000"),
          previous: mockLedgerMoney("3100000"),
          change: mockLedgerMoney("420000"),
        },
        {
          metric_key: "other_5_pnl",
          metric_name: "其他 5* 损益",
          current: mockLedgerMoney("660000"),
          previous: mockLedgerMoney("600000"),
          change: mockLedgerMoney("60000"),
        },
        {
          metric_key: "all_pnl",
          metric_name: "全量损益",
          current: mockLedgerMoney("4180000"),
          previous: mockLedgerMoney("3700000"),
          change: mockLedgerMoney("480000"),
        },
      ],
    },
    calculation_basis: mockLedgerPnlCalculationBasis,
  },
  CNY: {
    report_date: "2025-12-31",
    source_version: "sv_mock_ledger_v2",
    currency_basis: "CNY",
    basis_availability: { CNX: "ready", CNY: "ready" },
    analysis_status: "ready",
    metric_status: "candidate",
    conclusion: {
      direction: "positive",
      other_effect: "support",
      core_pnl: mockLedgerMoney("3000000"),
      other_5_pnl: mockLedgerMoney("400000"),
      all_pnl: mockLedgerMoney("3400000"),
    },
    pnl_bridge: {
      components: [
        { metric_key: "core_pnl", metric_name: "核心损益", amount: mockLedgerMoney("3000000") },
        { metric_key: "other_5_pnl", metric_name: "其他 5* 损益", amount: mockLedgerMoney("400000") },
      ],
      total: mockLedgerMoney("3400000"),
      residual: mockLedgerMoney("0"),
    },
    basis_comparison: mockLedgerPnlBasisComparison,
    contributors: {
      positive_total: mockLedgerMoney("3400000"),
      negative_total: mockLedgerMoney("0"),
      net_total: mockLedgerMoney("3400000"),
      top_positive: [
        {
          rank: 1,
          account_code: "514100",
          account_name: "利息收入",
          amount: mockLedgerMoney("1900000"),
          count: 15,
        },
        {
          rank: 2,
          account_code: "516100",
          account_name: "公允价值变动损益",
          amount: mockLedgerMoney("700000"),
          count: 7,
        },
        {
          rank: 3,
          account_code: "517100",
          account_name: "投资收益",
          amount: mockLedgerMoney("400000"),
          count: 4,
        },
        {
          rank: 4,
          account_code: "519900",
          account_name: "其他损益",
          amount: mockLedgerMoney("400000"),
          count: 3,
        },
      ],
      top_negative: [],
    },
    period_comparison: {
      status: "available",
      previous_report_date: "2025-11-30",
      previous_source_version: "sv_mock_ledger_analysis_v1_previous",
      rows: [
        {
          metric_key: "core_pnl",
          metric_name: "核心损益",
          current: mockLedgerMoney("3000000"),
          previous: mockLedgerMoney("2800000"),
          change: mockLedgerMoney("200000"),
        },
        {
          metric_key: "other_5_pnl",
          metric_name: "其他 5* 损益",
          current: mockLedgerMoney("400000"),
          previous: mockLedgerMoney("350000"),
          change: mockLedgerMoney("50000"),
        },
        {
          metric_key: "all_pnl",
          metric_name: "全量损益",
          current: mockLedgerMoney("3400000"),
          previous: mockLedgerMoney("3150000"),
          change: mockLedgerMoney("250000"),
        },
      ],
    },
    calculation_basis: mockLedgerPnlCalculationBasis,
  },
};

type MockLedgerPnlBasisComparisonAmounts = Record<
  LedgerPnlAnalysisPayload["basis_comparison"][number]["metric_key"],
  readonly [cnx: string, cny: string, cnxMinusCny: string]
>;

function buildMockLedgerPnlBasisComparison(
  amounts: MockLedgerPnlBasisComparisonAmounts,
  pnlEvidenceRows?: Record<MockLedgerPnlCurrencyBasis, number>,
): LedgerPnlAnalysisPayload["basis_comparison"] {
  return mockLedgerPnlBasisComparison.map((row) => {
    const [cnx, cny, cnxMinusCny] = amounts[row.metric_key];
    const isPnlMetric =
      row.metric_key === "core_pnl" ||
      row.metric_key === "all_pnl" ||
      row.metric_key === "other_5_pnl";
    return {
      ...row,
      cnx: mockLedgerMoney(cnx),
      cny: mockLedgerMoney(cny),
      cnx_minus_cny: mockLedgerMoney(cnxMinusCny),
      evidence_rows: isPnlMetric && pnlEvidenceRows
        ? pnlEvidenceRows
        : row.evidence_rows,
    };
  });
}

const mockLedgerPnlBasisComparison202511 = buildMockLedgerPnlBasisComparison({
  assets: ["1200000000", "1080000000", "120000000"],
  liabilities: ["950000000", "840000000", "110000000"],
  net_assets: ["250000000", "240000000", "10000000"],
  core_pnl: ["3100000", "2800000", "300000"],
  all_pnl: ["3700000", "3150000", "550000"],
  other_5_pnl: ["600000", "350000", "250000"],
}, { CNX: 32, CNY: 27 });

const mockLedgerPnlAnalysis202511ByBasis: Record<
  MockLedgerPnlCurrencyBasis,
  LedgerPnlAnalysisPayload
> = {
  CNX: {
    ...mockLedgerPnlAnalysisByBasis.CNX,
    report_date: "2025-11-30",
    source_version: "sv_mock_ledger_analysis_v1_previous",
    conclusion: {
      direction: "positive",
      other_effect: "support",
      core_pnl: mockLedgerMoney("3100000"),
      other_5_pnl: mockLedgerMoney("600000"),
      all_pnl: mockLedgerMoney("3700000"),
    },
    pnl_bridge: {
      components: [
        {
          ...mockLedgerPnlAnalysisByBasis.CNX.pnl_bridge.components[0],
          amount: mockLedgerMoney("3100000"),
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNX.pnl_bridge.components[1],
          amount: mockLedgerMoney("600000"),
        },
      ],
      total: mockLedgerMoney("3700000"),
      residual: mockLedgerMoney("0"),
    },
    basis_comparison: mockLedgerPnlBasisComparison202511,
    contributors: {
      positive_total: mockLedgerMoney("3700000"),
      negative_total: mockLedgerMoney("0"),
      net_total: mockLedgerMoney("3700000"),
      top_positive: [
        {
          ...mockLedgerPnlAnalysisByBasis.CNX.contributors.top_positive[0],
          amount: mockLedgerMoney("1900000"),
          count: 16,
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNX.contributors.top_positive[1],
          amount: mockLedgerMoney("750000"),
          count: 8,
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNX.contributors.top_positive[2],
          amount: mockLedgerMoney("600000"),
          count: 3,
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNX.contributors.top_positive[3],
          amount: mockLedgerMoney("450000"),
          count: 5,
        },
      ],
      top_negative: [],
    },
    period_comparison: {
      status: "no_previous_period",
      previous_report_date: null,
      previous_source_version: null,
      rows: [],
    },
  },
  CNY: {
    ...mockLedgerPnlAnalysisByBasis.CNY,
    report_date: "2025-11-30",
    source_version: "sv_mock_ledger_analysis_v1_previous",
    conclusion: {
      direction: "positive",
      other_effect: "support",
      core_pnl: mockLedgerMoney("2800000"),
      other_5_pnl: mockLedgerMoney("350000"),
      all_pnl: mockLedgerMoney("3150000"),
    },
    pnl_bridge: {
      components: [
        {
          ...mockLedgerPnlAnalysisByBasis.CNY.pnl_bridge.components[0],
          amount: mockLedgerMoney("2800000"),
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNY.pnl_bridge.components[1],
          amount: mockLedgerMoney("350000"),
        },
      ],
      total: mockLedgerMoney("3150000"),
      residual: mockLedgerMoney("0"),
    },
    basis_comparison: mockLedgerPnlBasisComparison202511,
    contributors: {
      positive_total: mockLedgerMoney("3150000"),
      negative_total: mockLedgerMoney("0"),
      net_total: mockLedgerMoney("3150000"),
      top_positive: [
        {
          ...mockLedgerPnlAnalysisByBasis.CNY.contributors.top_positive[0],
          amount: mockLedgerMoney("1750000"),
          count: 14,
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNY.contributors.top_positive[1],
          amount: mockLedgerMoney("650000"),
          count: 6,
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNY.contributors.top_positive[2],
          amount: mockLedgerMoney("400000"),
          count: 4,
        },
        {
          ...mockLedgerPnlAnalysisByBasis.CNY.contributors.top_positive[3],
          amount: mockLedgerMoney("350000"),
          count: 3,
        },
      ],
      top_negative: [],
    },
    period_comparison: {
      status: "no_previous_period",
      previous_report_date: null,
      previous_source_version: null,
      rows: [],
    },
  },
};

export const mockLedgerPnlAnalysisByReportDate: Partial<
  Record<string, Record<MockLedgerPnlCurrencyBasis, LedgerPnlAnalysisPayload>>
> = {
  "2025-12-31": mockLedgerPnlAnalysisByBasis,
  "2025-11-30": mockLedgerPnlAnalysis202511ByBasis,
};

export function buildMockLedgerPnlNoDataAnalysis(
  reportDate: string,
  currencyBasis: MockLedgerPnlCurrencyBasis,
): LedgerPnlAnalysisPayload {
  const template = mockLedgerPnlAnalysisByBasis[currencyBasis];
  return {
    ...template,
    report_date: reportDate,
    source_version: "sv_mock_ledger_no_data",
    basis_availability: { CNX: "no_data", CNY: "no_data" },
    analysis_status: "no_data",
    conclusion: {
      direction: "unavailable",
      other_effect: "unavailable",
      core_pnl: null,
      other_5_pnl: null,
      all_pnl: null,
    },
    pnl_bridge: {
      components: template.pnl_bridge.components.map((component) => ({
        ...component,
        amount: null,
      })),
      total: null,
      residual: null,
    },
    basis_comparison: mockLedgerPnlBasisComparison.map((row) => ({
      ...row,
      cnx: null,
      cny: null,
      cnx_minus_cny: null,
      availability: { CNX: "no_data", CNY: "no_data" },
      evidence_rows: { CNX: 0, CNY: 0 },
    })),
    contributors: {
      positive_total: null,
      negative_total: null,
      net_total: null,
      top_positive: [],
      top_negative: [],
    },
    period_comparison: {
      status: "current_basis_no_data",
      previous_report_date: null,
      previous_source_version: null,
      rows: [],
    },
  };
}

export type MockLedgerPnlSnapshot = {
  source_version: string;
  quality_flag: "ok" | "warning";
  evidence_rows: {
    summary: number;
    data: number;
  };
  summary: LedgerPnlSummaryPayload;
  data: LedgerPnlDataPayload;
  analysis: LedgerPnlAnalysisPayload;
};

export const mockLedgerPnlSnapshotByReportDate: Partial<
  Record<string, Record<MockLedgerPnlCurrencyBasis, MockLedgerPnlSnapshot>>
> = {
  "2025-12-31": {
    CNX: {
      source_version: "sv_mock_ledger_v2",
      quality_flag: "ok",
      evidence_rows: { summary: 37, data: 4 },
      summary: mockLedgerPnlSummaryByBasis.CNX,
      data: mockLedgerPnlDataByBasis.CNX,
      analysis: mockLedgerPnlAnalysisByBasis.CNX,
    },
    CNY: {
      source_version: "sv_mock_ledger_v2",
      quality_flag: "ok",
      evidence_rows: { summary: 29, data: 4 },
      summary: mockLedgerPnlSummaryByBasis.CNY,
      data: mockLedgerPnlDataByBasis.CNY,
      analysis: mockLedgerPnlAnalysisByBasis.CNY,
    },
  },
  "2025-11-30": {
    CNX: {
      source_version: "sv_mock_ledger_analysis_v1_previous",
      quality_flag: "ok",
      evidence_rows: { summary: 32, data: 4 },
      summary: mockLedgerPnlSummary202511ByBasis.CNX,
      data: mockLedgerPnlData202511ByBasis.CNX,
      analysis: mockLedgerPnlAnalysis202511ByBasis.CNX,
    },
    CNY: {
      source_version: "sv_mock_ledger_analysis_v1_previous",
      quality_flag: "ok",
      evidence_rows: { summary: 27, data: 4 },
      summary: mockLedgerPnlSummary202511ByBasis.CNY,
      data: mockLedgerPnlData202511ByBasis.CNY,
      analysis: mockLedgerPnlAnalysis202511ByBasis.CNY,
    },
  },
};

function buildMockLedgerPnlNoDataSnapshot(
  reportDate: string,
  currencyBasis: MockLedgerPnlCurrencyBasis,
): MockLedgerPnlSnapshot {
  const zero = mockLedgerMoney("0");
  const sourceVersion = "sv_mock_ledger_no_data";
  return {
    source_version: sourceVersion,
    quality_flag: "warning",
    evidence_rows: { summary: 0, data: 0 },
    summary: {
      report_date: reportDate,
      source_version: sourceVersion,
      ledger_total_assets: zero,
      ledger_total_liabilities: zero,
      ledger_net_assets: zero,
      ledger_monthly_pnl_core: zero,
      ledger_monthly_pnl_all: zero,
      by_currency: [],
      by_account: [],
    },
    data: {
      report_date: reportDate,
      items: [],
      summary: {
        total_pnl_cnx: zero,
        total_pnl_cny: zero,
        total_pnl: zero,
        count: 0,
      },
    },
    analysis: buildMockLedgerPnlNoDataAnalysis(reportDate, currencyBasis),
  };
}

export function getMockLedgerPnlSnapshot(
  reportDate: string,
  currencyBasis: MockLedgerPnlCurrencyBasis,
): MockLedgerPnlSnapshot {
  return mockLedgerPnlSnapshotByReportDate[reportDate]?.[currencyBasis]
    ?? buildMockLedgerPnlNoDataSnapshot(reportDate, currencyBasis);
}

const ACCOUNT_DETAIL_CURRENT_DATE = "2026-06-30";
const ACCOUNT_DETAIL_PREVIOUS_DATE = "2026-05-31";
const ACCOUNT_DETAIL_CURRENT_SOURCE = "sv_product_category_4490cb62d9f5";
const ACCOUNT_DETAIL_PREVIOUS_SOURCE = "sv_product_category_3353b116b9a6";

function accountDetailMoney(yuan: string, yi: string): LedgerMoneyValue {
  return { yuan, yi };
}

const accountDetailZero = accountDetailMoney("0", "0.00");

function readyAccountDetailBasisSnapshot(
  reportDate: string,
  sourceVersion: string,
  amount: LedgerMoneyValue,
): LedgerPnlAccountDetailBasisSnapshot {
  return {
    report_date: reportDate,
    source_version: sourceVersion,
    cnx: amount,
    cny: amount,
    cnx_minus_cny: accountDetailZero,
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 1, CNY: 1 },
  };
}

const accountDetailCalculationBasis: LedgerPnlAccountDetailPayload["calculation_basis"] = {
  account_match: "exact",
  amount_field: "monthly_pnl",
  change_formula: "current_monthly_pnl - previous_monthly_pnl",
  basis_difference_formula: "CNX - CNY",
  basis_boundary: "CNX 与 CNY 是重叠账务口径，不可相加；差额不是 FX PnL。",
  previous_period_rule: "previous available ledger report date",
  evidence_boundary: "canonical normalized ledger evidence; not original vouchers",
  metric_boundary: "candidate ledger account analysis; not formal PnL",
};

const DEMO_ACCOUNT_DETAIL_CURRENT_DATE = "2025-12-31";
const DEMO_ACCOUNT_DETAIL_PREVIOUS_DATE = "2025-11-30";
const DEMO_ACCOUNT_DETAIL_CURRENT_SOURCE = "sv_mock_ledger_v2";
const DEMO_ACCOUNT_DETAIL_PREVIOUS_SOURCE = "sv_mock_ledger_analysis_v1_previous";

const demoAccountDetailFrozenAmounts: Record<string, {
  change: Record<MockLedgerPnlCurrencyBasis, LedgerMoneyValue>;
  current_basis_difference: LedgerMoneyValue;
  previous_basis_difference: LedgerMoneyValue;
}> = {
  "514100": {
    change: {
      CNX: accountDetailMoney("220000", "0.00"),
      CNY: accountDetailMoney("150000", "0.00"),
    },
    current_basis_difference: accountDetailMoney("220000", "0.00"),
    previous_basis_difference: accountDetailMoney("150000", "0.00"),
  },
  "516100": {
    change: {
      CNX: accountDetailMoney("130000", "0.00"),
      CNY: accountDetailMoney("50000", "0.00"),
    },
    current_basis_difference: accountDetailMoney("180000", "0.00"),
    previous_basis_difference: accountDetailMoney("100000", "0.00"),
  },
  "517100": {
    change: {
      CNX: accountDetailMoney("70000", "0.00"),
      CNY: accountDetailMoney("0", "0.00"),
    },
    current_basis_difference: accountDetailMoney("120000", "0.00"),
    previous_basis_difference: accountDetailMoney("50000", "0.00"),
  },
  "519900": {
    change: {
      CNX: accountDetailMoney("60000", "0.00"),
      CNY: accountDetailMoney("50000", "0.00"),
    },
    current_basis_difference: accountDetailMoney("260000", "0.00"),
    previous_basis_difference: accountDetailMoney("250000", "0.00"),
  },
};

function buildDemoAccountDetailEvidenceRow(
  period: "current" | "previous",
  reportDate: string,
  sourceVersion: string,
  currency: MockLedgerPnlCurrencyBasis,
  row: LedgerPnlDataPayload["items"][number],
): LedgerPnlAccountDetailCanonicalEvidenceRow {
  return {
    period,
    report_date: reportDate,
    source_version: sourceVersion,
    account_code: row.account_code,
    account_name: row.account_name,
    currency,
    beginning_balance: row.beginning_balance,
    ending_balance: row.ending_balance,
    monthly_pnl: row.monthly_pnl,
    days_in_period: row.days_in_period,
  };
}

function buildDemoLedgerPnlAccountDetail(
  accountCode: string,
  currencyBasis: MockLedgerPnlCurrencyBasis,
): LedgerPnlAccountDetailPayload | undefined {
  const frozenAmounts = demoAccountDetailFrozenAmounts[accountCode];
  const currentCnx = mockLedgerPnlDataByBasis.CNX.items.find(
    (row) => row.account_code === accountCode,
  );
  const currentCny = mockLedgerPnlDataByBasis.CNY.items.find(
    (row) => row.account_code === accountCode,
  );
  const previousCnx = mockLedgerPnlData202511ByBasis.CNX.items.find(
    (row) => row.account_code === accountCode,
  );
  const previousCny = mockLedgerPnlData202511ByBasis.CNY.items.find(
    (row) => row.account_code === accountCode,
  );
  if (!frozenAmounts || !currentCnx || !currentCny || !previousCnx || !previousCny) {
    return undefined;
  }

  const currentRows = { CNX: currentCnx, CNY: currentCny };
  const previousRows = { CNX: previousCnx, CNY: previousCny };
  return {
    report_date: DEMO_ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: DEMO_ACCOUNT_DETAIL_CURRENT_SOURCE,
    currency_basis: currencyBasis,
    analysis_status: "ready",
    metric_status: "candidate",
    account: {
      account_code: accountCode,
      account_name: currentRows[currencyBasis].account_name,
    },
    period_comparison: {
      status: "available",
      previous_report_date: DEMO_ACCOUNT_DETAIL_PREVIOUS_DATE,
      previous_source_version: DEMO_ACCOUNT_DETAIL_PREVIOUS_SOURCE,
      current_monthly_pnl: currentRows[currencyBasis].monthly_pnl,
      previous_monthly_pnl: previousRows[currencyBasis].monthly_pnl,
      change: frozenAmounts.change[currencyBasis],
      current_evidence_rows: 1,
      previous_evidence_rows: 1,
    },
    basis_comparison: {
      current: {
        report_date: DEMO_ACCOUNT_DETAIL_CURRENT_DATE,
        source_version: DEMO_ACCOUNT_DETAIL_CURRENT_SOURCE,
        cnx: currentCnx.monthly_pnl,
        cny: currentCny.monthly_pnl,
        cnx_minus_cny: frozenAmounts.current_basis_difference,
        availability: { CNX: "ready", CNY: "ready" },
        evidence_rows: { CNX: 1, CNY: 1 },
      },
      previous: {
        report_date: DEMO_ACCOUNT_DETAIL_PREVIOUS_DATE,
        source_version: DEMO_ACCOUNT_DETAIL_PREVIOUS_SOURCE,
        cnx: previousCnx.monthly_pnl,
        cny: previousCny.monthly_pnl,
        cnx_minus_cny: frozenAmounts.previous_basis_difference,
        availability: { CNX: "ready", CNY: "ready" },
        evidence_rows: { CNX: 1, CNY: 1 },
      },
    },
    canonical_evidence_rows: [
      buildDemoAccountDetailEvidenceRow(
        "current",
        DEMO_ACCOUNT_DETAIL_CURRENT_DATE,
        DEMO_ACCOUNT_DETAIL_CURRENT_SOURCE,
        "CNX",
        currentCnx,
      ),
      buildDemoAccountDetailEvidenceRow(
        "current",
        DEMO_ACCOUNT_DETAIL_CURRENT_DATE,
        DEMO_ACCOUNT_DETAIL_CURRENT_SOURCE,
        "CNY",
        currentCny,
      ),
      buildDemoAccountDetailEvidenceRow(
        "previous",
        DEMO_ACCOUNT_DETAIL_PREVIOUS_DATE,
        DEMO_ACCOUNT_DETAIL_PREVIOUS_SOURCE,
        "CNX",
        previousCnx,
      ),
      buildDemoAccountDetailEvidenceRow(
        "previous",
        DEMO_ACCOUNT_DETAIL_PREVIOUS_DATE,
        DEMO_ACCOUNT_DETAIL_PREVIOUS_SOURCE,
        "CNY",
        previousCny,
      ),
    ],
    calculation_basis: accountDetailCalculationBasis,
  };
}

const taxCurrentPnl = accountDetailMoney("-566796492.18", "-5.67");
const taxPreviousPnl = accountDetailMoney("0", "0.00");
const taxCurrentBeginning = accountDetailMoney("427246908.11", "4.27");
const taxCurrentEnding = accountDetailMoney("994043400.29", "9.94");
const taxPreviousBalance = accountDetailMoney("427246908.11", "4.27");

const taxEvidenceRows: LedgerPnlAccountDetailCanonicalEvidenceRow[] = [
  {
    period: "current",
    report_date: ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: ACCOUNT_DETAIL_CURRENT_SOURCE,
    account_code: "55000000001",
    account_name: "当期所得税",
    currency: "CNX",
    beginning_balance: taxCurrentBeginning,
    ending_balance: taxCurrentEnding,
    monthly_pnl: taxCurrentPnl,
    days_in_period: 30,
  },
  {
    period: "current",
    report_date: ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: ACCOUNT_DETAIL_CURRENT_SOURCE,
    account_code: "55000000001",
    account_name: "当期所得税",
    currency: "CNY",
    beginning_balance: taxCurrentBeginning,
    ending_balance: taxCurrentEnding,
    monthly_pnl: taxCurrentPnl,
    days_in_period: 30,
  },
  {
    period: "previous",
    report_date: ACCOUNT_DETAIL_PREVIOUS_DATE,
    source_version: ACCOUNT_DETAIL_PREVIOUS_SOURCE,
    account_code: "55000000001",
    account_name: "当期所得税",
    currency: "CNX",
    beginning_balance: taxPreviousBalance,
    ending_balance: taxPreviousBalance,
    monthly_pnl: taxPreviousPnl,
    days_in_period: 31,
  },
  {
    period: "previous",
    report_date: ACCOUNT_DETAIL_PREVIOUS_DATE,
    source_version: ACCOUNT_DETAIL_PREVIOUS_SOURCE,
    account_code: "55000000001",
    account_name: "当期所得税",
    currency: "CNY",
    beginning_balance: taxPreviousBalance,
    ending_balance: taxPreviousBalance,
    monthly_pnl: taxPreviousPnl,
    days_in_period: 31,
  },
];

const metalCurrentPnl = accountDetailMoney("337860000", "3.38");
const metalPreviousPnl = accountDetailMoney("216270000", "2.16");
const metalChange = accountDetailMoney("121590000", "1.22");
const metalCurrentBeginning = accountDetailMoney("-184650000", "-1.85");
const metalCurrentEnding = accountDetailMoney("-522510000", "-5.23");
const metalPreviousBeginning = accountDetailMoney("31620000", "0.32");
const metalPreviousEnding = accountDetailMoney("-184650000", "-1.85");

const metalEvidenceRows: LedgerPnlAccountDetailCanonicalEvidenceRow[] = [
  {
    period: "current",
    report_date: ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: ACCOUNT_DETAIL_CURRENT_SOURCE,
    account_code: "51603030006",
    account_name: "贵金属-贵金属掉期近端交割公允价值变动-金-自营",
    currency: "CNX",
    beginning_balance: metalCurrentBeginning,
    ending_balance: metalCurrentEnding,
    monthly_pnl: metalCurrentPnl,
    days_in_period: 30,
  },
  {
    period: "current",
    report_date: ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: ACCOUNT_DETAIL_CURRENT_SOURCE,
    account_code: "51603030006",
    account_name: "贵金属-贵金属掉期近端交割公允价值变动-金-自营",
    currency: "CNY",
    beginning_balance: metalCurrentBeginning,
    ending_balance: metalCurrentEnding,
    monthly_pnl: metalCurrentPnl,
    days_in_period: 30,
  },
  {
    period: "previous",
    report_date: ACCOUNT_DETAIL_PREVIOUS_DATE,
    source_version: ACCOUNT_DETAIL_PREVIOUS_SOURCE,
    account_code: "51603030006",
    account_name: "贵金属-贵金属掉期近端交割公允价值变动-金-自营",
    currency: "CNX",
    beginning_balance: metalPreviousBeginning,
    ending_balance: metalPreviousEnding,
    monthly_pnl: metalPreviousPnl,
    days_in_period: 31,
  },
  {
    period: "previous",
    report_date: ACCOUNT_DETAIL_PREVIOUS_DATE,
    source_version: ACCOUNT_DETAIL_PREVIOUS_SOURCE,
    account_code: "51603030006",
    account_name: "贵金属-贵金属掉期近端交割公允价值变动-金-自营",
    currency: "CNY",
    beginning_balance: metalPreviousBeginning,
    ending_balance: metalPreviousEnding,
    monthly_pnl: metalPreviousPnl,
    days_in_period: 31,
  },
];

const accountDetailPayloadByCode: Record<string, LedgerPnlAccountDetailPayload> = {
  "55000000001": {
    report_date: ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: ACCOUNT_DETAIL_CURRENT_SOURCE,
    currency_basis: "CNX",
    analysis_status: "ready",
    metric_status: "candidate",
    account: { account_code: "55000000001", account_name: "当期所得税" },
    period_comparison: {
      status: "available",
      previous_report_date: ACCOUNT_DETAIL_PREVIOUS_DATE,
      previous_source_version: ACCOUNT_DETAIL_PREVIOUS_SOURCE,
      current_monthly_pnl: taxCurrentPnl,
      previous_monthly_pnl: taxPreviousPnl,
      change: taxCurrentPnl,
      current_evidence_rows: 1,
      previous_evidence_rows: 1,
    },
    basis_comparison: {
      current: readyAccountDetailBasisSnapshot(
        ACCOUNT_DETAIL_CURRENT_DATE,
        ACCOUNT_DETAIL_CURRENT_SOURCE,
        taxCurrentPnl,
      ),
      previous: readyAccountDetailBasisSnapshot(
        ACCOUNT_DETAIL_PREVIOUS_DATE,
        ACCOUNT_DETAIL_PREVIOUS_SOURCE,
        taxPreviousPnl,
      ),
    },
    canonical_evidence_rows: taxEvidenceRows,
    calculation_basis: accountDetailCalculationBasis,
  },
  "51603030006": {
    report_date: ACCOUNT_DETAIL_CURRENT_DATE,
    source_version: ACCOUNT_DETAIL_CURRENT_SOURCE,
    currency_basis: "CNX",
    analysis_status: "ready",
    metric_status: "candidate",
    account: {
      account_code: "51603030006",
      account_name: "贵金属-贵金属掉期近端交割公允价值变动-金-自营",
    },
    period_comparison: {
      status: "available",
      previous_report_date: ACCOUNT_DETAIL_PREVIOUS_DATE,
      previous_source_version: ACCOUNT_DETAIL_PREVIOUS_SOURCE,
      current_monthly_pnl: metalCurrentPnl,
      previous_monthly_pnl: metalPreviousPnl,
      change: metalChange,
      current_evidence_rows: 1,
      previous_evidence_rows: 1,
    },
    basis_comparison: {
      current: readyAccountDetailBasisSnapshot(
        ACCOUNT_DETAIL_CURRENT_DATE,
        ACCOUNT_DETAIL_CURRENT_SOURCE,
        metalCurrentPnl,
      ),
      previous: readyAccountDetailBasisSnapshot(
        ACCOUNT_DETAIL_PREVIOUS_DATE,
        ACCOUNT_DETAIL_PREVIOUS_SOURCE,
        metalPreviousPnl,
      ),
    },
    canonical_evidence_rows: metalEvidenceRows,
    calculation_basis: accountDetailCalculationBasis,
  },
};

function noDataAccountDetail(
  reportDate: string,
  accountCode: string,
  currencyBasis: MockLedgerPnlCurrencyBasis,
): LedgerPnlAccountDetailPayload {
  const hasGovernedSourcePair = reportDate === ACCOUNT_DETAIL_CURRENT_DATE;
  const sourceVersion = hasGovernedSourcePair
    ? ACCOUNT_DETAIL_CURRENT_SOURCE
    : "sv_mock_ledger_account_detail_no_data";
  const previousReportDate = hasGovernedSourcePair ? ACCOUNT_DETAIL_PREVIOUS_DATE : null;
  const previousSourceVersion = hasGovernedSourcePair ? ACCOUNT_DETAIL_PREVIOUS_SOURCE : null;
  return {
    report_date: reportDate,
    source_version: sourceVersion,
    currency_basis: currencyBasis,
    analysis_status: "no_data",
    metric_status: "candidate",
    account: { account_code: accountCode, account_name: null },
    period_comparison: {
      status: "current_account_no_data",
      previous_report_date: previousReportDate,
      previous_source_version: previousSourceVersion,
      current_monthly_pnl: null,
      previous_monthly_pnl: null,
      change: null,
      current_evidence_rows: 0,
      previous_evidence_rows: 0,
    },
    basis_comparison: {
      current: {
        report_date: reportDate,
        source_version: sourceVersion,
        cnx: null,
        cny: null,
        cnx_minus_cny: null,
        availability: { CNX: "no_data", CNY: "no_data" },
        evidence_rows: { CNX: 0, CNY: 0 },
      },
      previous: previousReportDate && previousSourceVersion
        ? {
            report_date: previousReportDate,
            source_version: previousSourceVersion,
            cnx: null,
            cny: null,
            cnx_minus_cny: null,
            availability: { CNX: "no_data", CNY: "no_data" },
            evidence_rows: { CNX: 0, CNY: 0 },
          }
        : null,
    },
    canonical_evidence_rows: [],
    calculation_basis: accountDetailCalculationBasis,
  };
}

export function getMockLedgerPnlAccountDetail(
  reportDate: string,
  accountCode: string,
  currencyBasis: MockLedgerPnlCurrencyBasis,
): LedgerPnlAccountDetailPayload {
  const normalizedCode = accountCode.trim();
  if (reportDate === DEMO_ACCOUNT_DETAIL_CURRENT_DATE) {
    const demoFixture = buildDemoLedgerPnlAccountDetail(normalizedCode, currencyBasis);
    if (demoFixture) {
      return demoFixture;
    }
  }
  const fixture = reportDate === ACCOUNT_DETAIL_CURRENT_DATE
    ? accountDetailPayloadByCode[normalizedCode]
    : undefined;
  if (!fixture) {
    return noDataAccountDetail(reportDate, normalizedCode, currencyBasis);
  }
  return { ...fixture, currency_basis: currencyBasis };
}

export const mockLedgerPnlFormalFinancialIndicators: LedgerPnlFormalFinancialIndicatorContractPayload = {
  sample_id: "GS-LEDGER-PNL-FIN-IND-202603-B",
  sample_status: "contract_fixture",
  surface: "/ledger-pnl formal financial indicator source contract",
  report_month: "202603",
  report_date: "2026-03-31",
  source_workbook: "C:/Users/arvin/Desktop/2026年财务指标表-3月最终(1).xlsx",
  source_sheet: "财务指标-汇总",
  source_basis: "Excel 2026-03 formal financial indicator table supplied by user",
  source_version: "sv_formal_financial_indicators_excel_202603_contract",
  rule_version: "rv_formal_financial_indicators_source_status_v1",
  formal_use_allowed: false,
  release_gate: {
    status: "registered_pending_release",
    blocking_reason: "202603 正式财务指标样本契约已登记，但正式生产来源尚未接入，不能放行 formal_use_allowed。",
    required_evidence: [
      "governed production source connected for formal financial indicators",
      "all contract values sourced from the frozen Excel sample",
      "Ledger PnL formal financial indicator golden sample test passes",
    ],
    readback_action: "登记来源接入证据并重新读取契约，确认 formal_use_allowed=false 保持到放行前",
  },
  contract_note:
    "This contract freezes the Excel formal-indicator sample and current source status. It is not approval to promote analytical QDB values to formal financial indicators.",
  status_semantics: {
    formal_pending:
      "Excel has the formal indicator value, but the governed production source is not connected. System value must remain null, not zero.",
    candidate_qdb_aligned:
      "QDB analytical value aligns to the Excel value within display precision, but remains analytical until formally approved.",
    needs_reconciliation:
      "QDB has a related analytical value, but it does not reconcile to the Excel formal value.",
  },
  metrics: [
    {
      metric_key: "group.operating_revenue",
      metric_name: "集团营业收入",
      scope: "group_consolidated",
      excel_value: "43.4194731314",
      unit: "亿元",
      excel_ref: "财务指标-汇总!K5 -> 财务指标-计算表!K5",
      formula: "=4341947313.14/100000000",
      source_status: "formal_pending",
      system_metric: null,
      system_value: null,
      value: null,
      basis: "formal_financial_indicator_source_contract",
      formal_use_allowed: false,
      source_version: "sv_formal_financial_indicators_excel_202603_contract",
      rule_version: "rv_formal_financial_indicators_source_status_v1",
      consolidation_scope: "group_consolidated",
      cell_ref: "财务指标-汇总!K5 -> 财务指标-计算表!K5",
      golden_sample_ref: "GS-LEDGER-PNL-FIN-IND-202603-B#group.operating_revenue",
      missing_reason: "正式财务指标来源未接入；系统值必须保持为空，不能用 0 或 QDB 分析值顶替。",
    },
    {
      metric_key: "parent.loan_balance",
      metric_name: "贷款余额（母公司）",
      scope: "parent_company",
      excel_value: "4189.4674724087",
      unit: "亿元",
      excel_ref: "财务指标-汇总!K39 -> 财务指标-计算表!K76",
      formula: "external/formal calculation table input",
      source_status: "candidate_qdb_aligned",
      system_metric: "qdb.loan_spot",
      system_value: "4189.47",
      reconciliation_gap: "0.0025275913",
      value: null,
      basis: "formal_financial_indicator_source_contract",
      formal_use_allowed: false,
      source_version: "sv_formal_financial_indicators_excel_202603_contract",
      rule_version: "rv_formal_financial_indicators_source_status_v1",
      consolidation_scope: "parent_company",
      cell_ref: "财务指标-汇总!K39 -> 财务指标-计算表!K76",
      golden_sample_ref: "GS-LEDGER-PNL-FIN-IND-202603-B#parent.loan_balance",
      missing_reason: "正式财务指标来源未接入；QDB 分析值仅作为候选对照，不具备正式使用权限。",
    },
    {
      metric_key: "parent.deposit_balance",
      metric_name: "存款余额（母公司）",
      scope: "parent_company",
      excel_value: "5120.6380974646",
      unit: "亿元",
      excel_ref: "财务指标-汇总!K40 -> 财务指标-计算表!K74",
      formula: "external/formal calculation table input",
      source_status: "needs_reconciliation",
      system_metric: "qdb.deposit_spot",
      system_value: "5115.96",
      reconciliation_gap: "4.6780974646",
      value: null,
      basis: "formal_financial_indicator_source_contract",
      formal_use_allowed: false,
      source_version: "sv_formal_financial_indicators_excel_202603_contract",
      rule_version: "rv_formal_financial_indicators_source_status_v1",
      consolidation_scope: "parent_company",
      cell_ref: "财务指标-汇总!K40 -> 财务指标-计算表!K74",
      golden_sample_ref: "GS-LEDGER-PNL-FIN-IND-202603-B#parent.deposit_balance",
      missing_reason: "正式财务指标来源未接入；QDB 分析值与 Excel 正式样本存在差异，需先对账。",
    },
  ],
};

export function getMockLedgerPnlFormalFinancialIndicators(
  reportMonth: string,
): LedgerPnlFormalFinancialIndicatorContractPayload {
  const normalizedReportMonth = reportMonth.trim() || mockLedgerPnlFormalFinancialIndicators.report_month;
  if (normalizedReportMonth === mockLedgerPnlFormalFinancialIndicators.report_month) {
    return mockLedgerPnlFormalFinancialIndicators;
  }
  return {
    sample_id: `GS-LEDGER-PNL-FIN-IND-${normalizedReportMonth}-MISSING`,
    sample_status: "missing_contract",
    surface: "/ledger-pnl formal financial indicator source contract",
    report_month: normalizedReportMonth,
    report_date: reportMonthEnd(normalizedReportMonth),
    source_workbook: "",
    source_sheet: "",
    source_basis: "No frozen formal financial indicator source contract is registered for this month.",
    source_version: "sv_formal_financial_indicators_contract_unavailable",
    rule_version: "rv_formal_financial_indicators_source_status_v1",
    formal_use_allowed: false,
    contract_note: "The requested month has no governed formal indicator contract; candidate values cannot replace it.",
    status_semantics: mockLedgerPnlFormalFinancialIndicators.status_semantics,
    remediation: {
      required: true,
      action_label: `Register ${normalizedReportMonth} formal indicator contract`,
      action_detail: "Freeze the approved workbook, cell references, and reconciliation evidence before readback.",
      required_artifact: `${normalizedReportMonth} approved financial indicator workbook`,
      artifact_status: "missing",
      registration_target: "backend/app/core_finance/formal_financial_indicators.py",
      verification: `python -m pytest tests/test_ledger_pnl_formal_financial_indicators.py -q -k ${normalizedReportMonth}`,
    },
    metrics: [],
  };
}

type CandidateFinancialIndicatorFixture = {
  fixture_kind: string;
  capture_status: "candidate_non_formal";
  report_month: string;
  rule_version: "qdb-finance-2026-v1.0.0";
  rule_hash: string;
  source_hashes: Record<"ledger" | "daily", string>;
  base_idempotency_key: string;
  lineage_idempotency_key: string;
  result_meta: LedgerPnlCandidateFinancialIndicatorsResultMeta;
  result: LedgerPnlCandidateFinancialIndicatorsPayload;
  lineage_by_metric: Record<string, LedgerPnlCandidateFinancialIndicatorLineage[]>;
};

const capturedCandidateFinancialIndicators =
  candidateFinancialIndicatorFixture as unknown as CandidateFinancialIndicatorFixture;
const capturedCandidateResult = capturedCandidateFinancialIndicators.result;
const capturedCandidateMetricIds = new Set(
  capturedCandidateResult.metrics.map((metric) => metric.metric_id),
);
const CANDIDATE_METRIC_ID_PATTERN =
  /^[a-z0-9]+(?:[._][a-z0-9]+)*(?:::(?:point|ytd_average|month_average))?$/;

export const MOCK_LEDGER_PNL_CANDIDATE_RULE_VERSION =
  capturedCandidateFinancialIndicators.rule_version;
export const MOCK_LEDGER_PNL_CANDIDATE_RULE_HASH =
  capturedCandidateFinancialIndicators.rule_hash;
export const MOCK_LEDGER_PNL_CANDIDATE_SOURCE_VERSION =
  capturedCandidateResult.source_version;
export const MOCK_LEDGER_PNL_CANDIDATE_IDEMPOTENCY_KEY =
  capturedCandidateFinancialIndicators.base_idempotency_key;
export const MOCK_LEDGER_PNL_CANDIDATE_CAPTURE_META =
  capturedCandidateFinancialIndicators.result_meta;

function assertCandidateRequest(reportMonth: string, metricId: string | null) {
  if (!/^\d{6}$/.test(reportMonth) || !reportMonthEnd(reportMonth)) {
    throw new Error(`Invalid candidate financial indicator report_month: ${reportMonth || "<empty>"}`);
  }
  if (metricId !== null && (
    !CANDIDATE_METRIC_ID_PATTERN.test(metricId) ||
    !capturedCandidateMetricIds.has(metricId)
  )) {
    throw new Error(`Unknown candidate financial indicator metric_id: ${metricId}`);
  }
}

async function candidateMockRequestKey(input: {
  reportMonth: string;
  includeLineage: boolean;
  metricId: string | null;
  status: "warning" | "no_data";
}) {
  const payload = JSON.stringify({
    fixture_kind: capturedCandidateFinancialIndicators.fixture_kind,
    rule_hash: capturedCandidateFinancialIndicators.rule_hash,
    source_hashes: input.status === "warning"
      ? capturedCandidateFinancialIndicators.source_hashes
      : { ledger: null, daily: null },
    report_month: input.reportMonth,
    include_lineage: input.includeLineage,
    metric_id: input.metricId,
    status: input.status,
  });
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(payload),
  );
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function candidatePromotionEvidenceKey(
  candidateIdempotencyKey: string,
  readiness: Omit<
    LedgerPnlCandidateFinancialIndicatorsPayload["promotion_readiness"],
    "readiness_evidence_key" | "evidence_pack"
  >,
) {
  const payload = JSON.stringify({
    candidate_idempotency_key: candidateIdempotencyKey,
    checks: readiness.checks.map((check) => ({
      check_id: check.check_id,
      evidence_refs: check.evidence_refs,
      status: check.status,
    })),
    formal_contract_status: readiness.formal_contract_status,
    readiness_contract_version: readiness.readiness_contract_version,
  });
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(payload),
  );
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function candidatePromotionEvidencePackKey(
  pack: Omit<
    LedgerPnlCandidateFinancialIndicatorsPayload["promotion_readiness"]["evidence_pack"],
    "evidence_pack_key"
  >,
) {
  const canonicalize = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value as Record<string, unknown>)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([key, child]) => [key, canonicalize(child)]),
      );
    }
    return value;
  };
  const payload = JSON.stringify(canonicalize(pack));
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(payload),
  );
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

function missingCandidateSources(
  reportMonth: string,
): LedgerPnlCandidateFinancialIndicatorsPayload["sources"] {
  return [
    {
      source_kind: "ledger",
      file_name: `总账对账${reportMonth}.xlsx`,
      exists: false,
      sha256: null,
      locked_sha256: null,
      locked_hash_match: null,
      sheets: [],
      periods: [],
    },
    {
      source_kind: "daily",
      file_name: `日均${reportMonth}.xlsx`,
      exists: false,
      sha256: null,
      locked_sha256: null,
      locked_hash_match: null,
      sheets: [],
      periods: [],
    },
  ];
}

async function missingCandidatePromotionReadiness(
  reportMonth: string,
  idempotencyKey: string,
): Promise<LedgerPnlCandidateFinancialIndicatorsPayload["promotion_readiness"]> {
  const formalContract = getMockLedgerPnlFormalFinancialIndicators(reportMonth);
  const formalContractStatus = formalContract.sample_status === "contract_fixture"
    ? "contract_fixture"
    : "missing_contract";
  const formalContractPassed = formalContractStatus === "contract_fixture"
    && formalContract.metrics.length > 0;
  const formalEvidenceRefs = [formalContract.sample_id, formalContract.source_version];
  if (formalContract.release_gate?.status) {
    formalEvidenceRefs.push(`release_gate:${formalContract.release_gate.status}`);
  }
  if (formalContract.remediation?.required_artifact) {
    formalEvidenceRefs.push(formalContract.remediation.required_artifact);
  }
  const readiness: Omit<
    LedgerPnlCandidateFinancialIndicatorsPayload["promotion_readiness"],
    "readiness_evidence_key" | "evidence_pack"
  > = {
    readiness_contract_version: "promotion-readiness-v1" as const,
    status: "blocked",
    blocking_count: formalContractPassed ? 4 : 5,
    check_total: 6,
    candidate_idempotency_key: idempotencyKey,
    formal_contract_status: formalContractStatus,
    formal_use_allowed: false,
    owner_approval_required: true,
    next_action: "补齐当月固定总账与日均来源后重新计算。",
    checks: [
      {
        check_id: "rule_asset",
        label: "规则资产与候选计算",
        status: "passed",
        blocking: false,
        summary: `已加载批准规则 ${MOCK_LEDGER_PNL_CANDIDATE_RULE_VERSION}。`,
        evidence_refs: [MOCK_LEDGER_PNL_CANDIDATE_RULE_VERSION],
        action: "规则资产已通过；保持当前批准版本不变。",
      },
      {
        check_id: "source_evidence",
        label: "来源期间与锁定哈希",
        status: "blocked",
        blocking: true,
        summary: `缺少 ${reportMonth} 固定总账与日均来源。`,
        evidence_refs: [`总账对账${reportMonth}.xlsx`, `日均${reportMonth}.xlsx`],
        action: "补齐当月固定总账与日均来源后重新计算。",
      },
      {
        check_id: "validation_controls",
        label: "控制校验",
        status: "not_evaluated",
        blocking: true,
        summary: "12 项控制尚未执行。",
        evidence_refs: [],
        action: "恢复来源后执行 12 项控制。",
      },
      {
        check_id: "manual_inputs",
        label: "手工调整输入",
        status: "not_evaluated",
        blocking: true,
        summary: "手工调整项尚未评估。",
        evidence_refs: [],
        action: "恢复来源后评估手工调整项。",
      },
      {
        check_id: "account_coverage",
        label: "规则科目覆盖",
        status: "not_evaluated",
        blocking: true,
        summary: "规则科目覆盖尚未评估。",
        evidence_refs: [],
        action: "恢复来源后评估规则科目覆盖。",
      },
      {
        check_id: "formal_contract",
        label: "正式契约登记",
        status: formalContractPassed ? "passed" : "blocked",
        blocking: !formalContractPassed,
        summary: formalContractPassed
          ? `已登记 ${formalContract.metrics.length} 项冻结正式指标契约。`
          : `${reportMonth} 正式财务指标冻结契约尚未登记。`,
        evidence_refs: formalEvidenceRefs,
        action: formalContractPassed
          ? "正式契约已登记；保持冻结样本与来源契约不变。"
          : `补齐 ${reportMonth} 正式财务指标 Excel 冻结样本。`,
      },
    ],
  };
  const readinessEvidenceKey = await candidatePromotionEvidenceKey(idempotencyKey, readiness);
  const ownerRequirements: LedgerPnlCandidateFinancialIndicatorsPayload[
    "promotion_readiness"
  ]["evidence_pack"]["owner_requirements"] = [
    {
      requirement_id: "source_evidence.1",
      category: "source_evidence",
      status: "awaiting_owner_input",
      submitted_value: null,
      evidence_refs: [`总账对账${reportMonth}.xlsx`, `日均${reportMonth}.xlsx`],
      required_evidence: ["批准来源文件、来源期间与 SHA-256 复核记录"],
      action: "补齐当月固定总账与日均来源后重新计算。",
    },
    ...(formalContractPassed ? [] : [{
      requirement_id: "formal_contract.1",
      category: "formal_contract" as const,
      status: "awaiting_owner_input" as const,
      submitted_value: null,
      evidence_refs: formalEvidenceRefs,
      required_evidence: ["正式财务指标 Excel 冻结样本与契约登记记录"],
      action: `补齐 ${reportMonth} 正式财务指标 Excel 冻结样本。`,
    }]),
    {
      requirement_id: "business_owner_approval.1",
      category: "business_owner_approval",
      status: "awaiting_owner_input",
      submitted_value: null,
      evidence_refs: [],
      required_evidence: ["负责人姓名、角色、决定、日期与签名"],
      action: "六项技术门禁通过后，仍须财务与数据治理负责人复核。",
    },
  ];
  const evidencePack: Omit<
    LedgerPnlCandidateFinancialIndicatorsPayload["promotion_readiness"]["evidence_pack"],
    "evidence_pack_key"
  > = {
    contract_version: "candidate-promotion-evidence-v1",
    report_month: reportMonth,
    report_date: reportMonthEnd(reportMonth),
    rule_version: MOCK_LEDGER_PNL_CANDIDATE_RULE_VERSION,
    rule_hash: MOCK_LEDGER_PNL_CANDIDATE_RULE_HASH,
    source_version: `sv_candidate_financial_indicators_no_data_${reportMonth}`,
    source_alignment: "incomplete",
    candidate_idempotency_key: idempotencyKey,
    readiness_contract_version: "promotion-readiness-v1",
    readiness_evidence_key: readinessEvidenceKey,
    metric_status: "candidate",
    formal_use_allowed: false,
    owner_approval_required: true,
    contains_metric_values: false,
    contains_formal_values: false,
    certification_effect: "none",
    blocking_count: readiness.blocking_count,
    check_total: 6,
    formal_contract_status: formalContractStatus,
    formal_sample_id: formalContract.sample_id,
    formal_source_version: formalContract.source_version,
    formal_release_gate_status: formalContract.release_gate?.status ?? null,
    formal_metric_count: formalContract.metrics.length,
    checks: readiness.checks,
    owner_requirement_count: ownerRequirements.length,
    owner_requirements: ownerRequirements,
    outcome_status: "blocked",
  };
  return {
    ...readiness,
    readiness_evidence_key: readinessEvidenceKey,
    evidence_pack: {
      ...evidencePack,
      evidence_pack_key: await candidatePromotionEvidencePackKey(evidencePack),
    },
  };
}

export async function buildMockLedgerPnlCandidateFinancialIndicators(
  reportMonth: string,
  options: { includeLineage?: boolean; metricId?: string } = {},
): Promise<LedgerPnlCandidateFinancialIndicatorsPayload> {
  const normalizedReportMonth = reportMonth.trim();
  const requestedMetricId = options.metricId?.trim() || null;
  const includeLineage = options.includeLineage === true;
  assertCandidateRequest(normalizedReportMonth, requestedMetricId);

  if (normalizedReportMonth !== capturedCandidateFinancialIndicators.report_month) {
    const idempotencyKey = await candidateMockRequestKey({
      reportMonth: normalizedReportMonth,
      includeLineage,
      metricId: requestedMetricId,
      status: "no_data",
    });
    return {
      report_month: normalizedReportMonth,
      report_date: reportMonthEnd(normalizedReportMonth),
      currency: "CNX",
      basis: "ledger",
      metric_status: "candidate",
      formal_use_allowed: false,
      calculation_status: "no_data",
      source_alignment: "incomplete",
      source_version: `sv_candidate_financial_indicators_no_data_${normalizedReportMonth}`,
      rule_version: MOCK_LEDGER_PNL_CANDIDATE_RULE_VERSION,
      rule_hash: MOCK_LEDGER_PNL_CANDIDATE_RULE_HASH,
      idempotency_key: idempotencyKey,
      requested_metric_id: requestedMetricId,
      include_lineage: includeLineage,
      promotion_readiness: await missingCandidatePromotionReadiness(
        normalizedReportMonth,
        idempotencyKey,
      ),
      sources: missingCandidateSources(normalizedReportMonth),
      summary: {
        metric_total: 186,
        metric_evaluated: 0,
        metric_returned: 0,
        ok_count: 0,
        warning_count: 0,
        manual_default_count: 0,
        error_count: 0,
        validation_total: 12,
        validation_evaluated: 0,
        validation_passed: 0,
        validation_warning_failed: 0,
        validation_error_failed: 0,
      },
      metrics: [],
      validations: [],
      gaps: [
        {
          gap_id: "source_missing.ledger",
          severity: "error",
          kind: "source_missing",
          title: "缺少总账源文件",
          detail: `固定来源文件 总账对账${normalizedReportMonth}.xlsx 不存在，未执行候选指标计算。`,
          metric_ids: [],
        },
        {
          gap_id: "source_missing.daily",
          severity: "error",
          kind: "source_missing",
          title: "缺少日均源文件",
          detail: `固定来源文件 日均${normalizedReportMonth}.xlsx 不存在，未执行候选指标计算。`,
          metric_ids: [],
        },
      ],
    };
  }

  const captured = structuredClone(capturedCandidateResult);
  const selectedMetrics = requestedMetricId
    ? captured.metrics.filter((metric) => metric.metric_id === requestedMetricId)
    : captured.metrics;
  const metrics = selectedMetrics.map((metric) => ({
    ...metric,
    lineage: includeLineage
      ? structuredClone(
          capturedCandidateFinancialIndicators.lineage_by_metric[metric.metric_id] ?? [],
        )
      : [],
  }));
  const idempotencyKey = requestedMetricId === null
    ? (
        includeLineage
          ? capturedCandidateFinancialIndicators.lineage_idempotency_key
          : capturedCandidateFinancialIndicators.base_idempotency_key
      )
    : await candidateMockRequestKey({
        reportMonth: normalizedReportMonth,
        includeLineage,
        metricId: requestedMetricId,
        status: "warning",
      });

  const {
    evidence_pack: capturedEvidencePack,
    readiness_evidence_key: _capturedReadinessEvidenceKey,
    ...capturedReadiness
  } = captured.promotion_readiness;
  const promotionReadiness = {
    ...capturedReadiness,
    candidate_idempotency_key: idempotencyKey,
  };
  const readinessEvidenceKey = await candidatePromotionEvidenceKey(
    idempotencyKey,
    promotionReadiness,
  );
  const {
    evidence_pack_key: _capturedEvidencePackKey,
    ...capturedEvidencePackBody
  } = capturedEvidencePack;
  const evidencePack = {
    ...capturedEvidencePackBody,
    candidate_idempotency_key: idempotencyKey,
    readiness_evidence_key: readinessEvidenceKey,
    checks: promotionReadiness.checks,
  };
  return {
    ...captured,
    idempotency_key: idempotencyKey,
    promotion_readiness: {
      ...promotionReadiness,
      readiness_evidence_key: readinessEvidenceKey,
      evidence_pack: {
        ...evidencePack,
        evidence_pack_key: await candidatePromotionEvidencePackKey(evidencePack),
      },
    },
    requested_metric_id: requestedMetricId,
    include_lineage: includeLineage,
    summary: {
      ...captured.summary,
      metric_returned: metrics.length,
    },
    metrics,
  };
}

const RULE_CHECKS_CONTRACT_NOTE =
  "本结果仅对冻结契约值做规则符合性校验，不产生新的正式指标值，" +
  "residual_present/insufficient_inputs 不是错误，是待正式来源接入后需解释或补齐的证据缺口。";

export const mockLedgerPnlFormalIndicatorRuleChecks202603: LedgerPnlFormalIndicatorRuleChecksPayload = {
  report_month: "202603",
  report_date: "2026-03-31",
  basis: "formal_financial_indicator_rule_checks",
  formal_use_allowed: false,
  sample_status: "contract_fixture",
  source_version: "sv_formal_financial_indicators_excel_202603_contract",
  rule_version: "rv_formal_financial_indicator_rule_checks_v1",
  contract_note: RULE_CHECKS_CONTRACT_NOTE,
  ratio_recomputation: [
    {
      check_key: "group.cost_income_ratio",
      metric_name: "成本收入比",
      formula: "group.business_admin_expense / group.operating_revenue × 100",
      numerator_metric_key: "group.business_admin_expense",
      numerator_value: "9.7335327322",
      denominator_metric_key: "group.operating_revenue",
      denominator_value: "43.4194731314",
      recomputed_value: "22.4174363027",
      contract_metric_key: "group.cost_income_ratio",
      contract_value: "22.4174363027",
      diff: "0.0000000000",
      tolerance: "0.0001",
      unit: "%",
      status: "matched",
    },
    {
      check_key: "asset_quality.npl_ratio",
      metric_name: "不良贷款率",
      formula: "asset_quality.npl_balance / asset_quality.loan_balance × 100",
      numerator_metric_key: "asset_quality.npl_balance",
      numerator_value: "40.1588772655",
      denominator_metric_key: "asset_quality.loan_balance",
      denominator_value: "4193.9954022127",
      recomputed_value: "0.9575326965",
      contract_metric_key: "asset_quality.npl_ratio",
      contract_value: "0.9575326965",
      diff: "0.0000000000",
      tolerance: "0.0001",
      unit: "%",
      status: "matched",
    },
    {
      check_key: "asset_quality.loan_loss_reserve_ratio",
      metric_name: "拨贷比",
      formula: "asset_quality.loan_loss_provision_balance / asset_quality.loan_balance × 100",
      numerator_metric_key: "asset_quality.loan_loss_provision_balance",
      numerator_value: "122.7295998170",
      denominator_metric_key: "asset_quality.loan_balance",
      denominator_value: "4193.9954022127",
      recomputed_value: "2.9263169853",
      contract_metric_key: "asset_quality.loan_loss_reserve_ratio",
      contract_value: "2.9263169853",
      diff: "0.0000000000",
      tolerance: "0.0001",
      unit: "%",
      status: "matched",
    },
    {
      check_key: "asset_quality.provision_coverage_ratio",
      metric_name: "拨备覆盖率",
      formula: "asset_quality.loan_loss_provision_balance / asset_quality.npl_balance × 100",
      numerator_metric_key: "asset_quality.loan_loss_provision_balance",
      numerator_value: "122.7295998170",
      denominator_metric_key: "asset_quality.npl_balance",
      denominator_value: "40.1588772655",
      recomputed_value: "305.6101369706",
      contract_metric_key: "asset_quality.provision_coverage_ratio",
      contract_value: "305.6101369706",
      diff: "0.0000000000",
      tolerance: "0.0001",
      unit: "%",
      status: "matched",
    },
    {
      check_key: "group.roa",
      metric_name: "集团ROA",
      contract_metric_key: "group.roa",
      contract_value: "0.7622345868",
      unit: "%",
      status: "insufficient_inputs",
      missing_inputs: ["期初总资产（用于计算期间平均总资产）"],
      note: "集团ROA无法用契约内组件复算：分母需要期初+期末平均总资产，契约只冻结了期末总资产（group.total_assets）。",
    },
    {
      check_key: "group.roe",
      metric_name: "集团ROE",
      contract_metric_key: "group.roe",
      contract_value: "14.6348772016",
      unit: "%",
      status: "insufficient_inputs",
      missing_inputs: ["期初归属母公司权益", "优先股息（年化）"],
      note: "集团ROE无法用契约内组件复算：分母需要期初归属母公司权益，分子需要扣除优先股息，二者均不在契约内。",
    },
  ],
  additivity_checks: [
    {
      check_key: "group.operating_revenue",
      metric_name: "集团营业收入 = 母公司营收 + 三家子公司营收",
      total_metric_key: "group.operating_revenue",
      total_value: "43.4194731314",
      components: [
        { metric_key: "parent.operating_revenue.consolidated_basis", value: "40.5057623568" },
        { metric_key: "subsidiary.jinzu.operating_revenue", value: "1.7633073047" },
        { metric_key: "subsidiary.licai.operating_revenue", value: "1.1233358159" },
        { metric_key: "subsidiary.village_bank.operating_revenue", value: "0.0321492748" },
      ],
      components_sum: "43.4245547522",
      residual: "-0.0050816208",
      unit: "亿元",
      status: "residual_present",
      note: "残差通常为合并抵销/管理调整，需在正式来源接入时解释",
    },
    {
      check_key: "group.business_admin_expense",
      metric_name: "业务及管理费 = 母公司费用 + 三家子公司费用",
      total_metric_key: "group.business_admin_expense",
      total_value: "9.7335327322",
      components: [
        { metric_key: "parent.business_admin_expense", value: "9.2856413190" },
        { metric_key: "subsidiary.jinzu.business_admin_expense", value: "0.1529288536" },
        { metric_key: "subsidiary.licai.business_admin_expense", value: "0.2508577245" },
        { metric_key: "subsidiary.village_bank.business_admin_expense", value: "0.0470170997" },
      ],
      components_sum: "9.7364449968",
      residual: "-0.0029122646",
      unit: "亿元",
      status: "residual_present",
      note: "残差通常为合并抵销/管理调整，需在正式来源接入时解释",
    },
    {
      check_key: "group.impairment_loss",
      metric_name: "减值损失 = 母公司减值损失 + 子公司减值损失",
      total_metric_key: "group.impairment_loss",
      total_value: "13.8794270584",
      components: [
        { metric_key: "parent.impairment_loss", value: "13.8357855232" },
        { metric_key: "subsidiary.impairment_loss", value: "0.0378967223" },
      ],
      components_sum: "13.8736822455",
      residual: "0.0057448129",
      unit: "亿元",
      status: "residual_present",
      note: "残差通常为合并抵销/管理调整，需在正式来源接入时解释",
    },
    {
      check_key: "group.net_profit",
      metric_name: "净利润 = 母公司净利润 + 金租净利润 + 理财净利润 + 村镇净利润",
      total_metric_key: "group.net_profit",
      total_value: "15.7131099579",
      components: [
        { metric_key: "parent.net_profit", value: "13.9118472050" },
        { metric_key: "subsidiary.jinzu.net_profit", value: "1.1775187483" },
        { metric_key: "subsidiary.licai.net_profit", value: "0.6390026754" },
        { metric_key: "subsidiary.village_bank.net_profit", value: "-0.0149530904" },
      ],
      components_sum: "15.7134155383",
      residual: "-0.0003055804",
      unit: "亿元",
      status: "residual_present",
      note: "残差通常为合并抵销/管理调整，需在正式来源接入时解释",
    },
    {
      check_key: "asset_quality.writeoff_total",
      metric_name: "核销合计 = 贷款核销 + 其他资产核销",
      total_metric_key: "asset_quality.writeoff_total",
      total_value: "3.0847286675",
      components: [
        { metric_key: "asset_quality.loan_writeoff", value: "3.0497046763" },
        { metric_key: "asset_quality.other_asset_writeoff", value: "0.0350239912" },
      ],
      components_sum: "3.0847286675",
      residual: "0.0000000000",
      unit: "亿元",
      status: "exact",
    },
    {
      check_key: "asset_quality.recovery_after_writeoff_total",
      metric_name: "核销后收回合计 = 贷款收回 + 其他收回",
      total_metric_key: "asset_quality.recovery_after_writeoff_total",
      total_value: "0.5154111414",
      components: [
        { metric_key: "asset_quality.loan_recovery_after_writeoff", value: "0.5143695576" },
        { metric_key: "asset_quality.other_asset_recovery_after_writeoff", value: "0.0010415838" },
      ],
      components_sum: "0.5154111414",
      residual: "0.0000000000",
      unit: "亿元",
      status: "exact",
    },
    {
      check_key: "asset_quality.provision_balance_total",
      metric_name: "减值准备余额合计 = 贷款减值准备余额 + 其他资产减值准备余额",
      total_metric_key: "asset_quality.provision_balance_total",
      total_value: "192.4598240500",
      components: [
        { metric_key: "asset_quality.loan_loss_provision_balance", value: "122.7295998170" },
        { metric_key: "asset_quality.other_asset_provision_balance", value: "69.7302242330" },
      ],
      components_sum: "192.4598240500",
      residual: "0.0000000000",
      unit: "亿元",
      status: "exact",
    },
  ],
  arrangement_rules: [
    {
      rule_key: "rule_expense_growth_le_revenue_growth",
      rule_name: "费用同比增幅≤营收同比增幅",
      source_ref: "财务指标-汇总!B57",
      status: "insufficient_inputs",
      missing_inputs: ["2025年同期营业收入", "2025年同期业务及管理费"],
      note: "需要上年同期（2025年一季度）营业收入与业务及管理费才能计算同比增幅，契约未冻结上年同期值。",
    },
    {
      rule_key: "rule_npl_ratio_target",
      rule_name: "不良贷款率季末目标（一季末≤1.21%，其余季末≤1.20%）",
      source_ref: "财务指标-汇总!B58",
      status: "pass",
      quarter_end_type: "一季末",
      actual_value: "0.9575326965",
      target_value: "1.21",
      comparator: "actual_value <= target_value",
      unit: "%",
    },
    {
      rule_key: "rule_provision_ratios_not_below_year_start",
      rule_name: "拨贷比、拨备覆盖率不低于年初且逐季提升",
      source_ref: "财务指标-汇总!B59",
      status: "insufficient_inputs",
      missing_inputs: [
        "2025年末拨贷比（年初值）",
        "2025年末拨备覆盖率（年初值）",
        "上季度末拨贷比（用于逐季比较）",
        "上季度末拨备覆盖率（用于逐季比较）",
      ],
      note: "契约只冻结了当期（202603）拨贷比与拨备覆盖率，年初值与上季度值不在契约内，无法校验不低于年初且逐季提升。",
    },
    {
      rule_key: "rule_tax_exempt_income_assumption",
      rule_name: "免税收入按全年预算测算所得税",
      source_ref: "财务指标-汇总!B60",
      status: "informational",
      assumption_value: "28",
      assumption_unit: "亿元",
      note: "该安排属于管理层测算假设（免税收入按全年预算28亿元测算所得税），不是可用契约值校验的勾稽或比率规则，仅作记录。",
    },
    {
      rule_key: "rule_group_equals_parent_plus_subsidiaries",
      rule_name: "集团=母公司+子公司",
      source_ref: "财务指标-汇总!B61-B62",
      status: "summary",
      referenced_additivity_check_keys: [
        "group.operating_revenue",
        "group.business_admin_expense",
        "group.impairment_loss",
        "group.net_profit",
      ],
      exact_count: 0,
      residual_present_count: 4,
      note: "汇总集团=母公司+子公司口径的四条勾稽结果；residual_present 不代表错误，通常为合并抵销/管理调整。",
    },
  ],
  summary: {
    ratio_recomputation: { matched: 4, mismatch: 0, insufficient_inputs: 2, total: 6 },
    additivity_checks: { exact: 3, residual_present: 4, total: 7 },
    arrangement_rules: {
      pass: 1,
      fail: 0,
      insufficient_inputs: 2,
      informational: 1,
      summary: 1,
      total: 5,
    },
    total_checks: 18,
  },
};

export function buildMockLedgerPnlFormalIndicatorRuleChecks(
  reportMonth: string,
): LedgerPnlFormalIndicatorRuleChecksPayload {
  const normalizedReportMonth = reportMonth.trim() || mockLedgerPnlFormalIndicatorRuleChecks202603.report_month;
  if (normalizedReportMonth === mockLedgerPnlFormalIndicatorRuleChecks202603.report_month) {
    return mockLedgerPnlFormalIndicatorRuleChecks202603;
  }
  return {
    report_month: normalizedReportMonth,
    report_date: reportMonthEnd(normalizedReportMonth),
    basis: "formal_financial_indicator_rule_checks",
    formal_use_allowed: false,
    sample_status: "missing_contract",
    source_version: "sv_formal_financial_indicators_not_registered",
    rule_version: "rv_formal_financial_indicator_rule_checks_v1",
    contract_note:
      "未找到该 report_month 对应的正式财务指标冻结契约，规则符合性检查无法执行。请先补齐契约（见 remediation），再重新读取规则检查结果。",
    ratio_recomputation: [],
    additivity_checks: [],
    arrangement_rules: [],
    summary: {
      ratio_recomputation: { matched: 0, mismatch: 0, insufficient_inputs: 0, total: 0 },
      additivity_checks: { exact: 0, residual_present: 0, total: 0 },
      arrangement_rules: {
        pass: 0,
        fail: 0,
        insufficient_inputs: 0,
        informational: 0,
        summary: 0,
        total: 0,
      },
      total_checks: 0,
    },
    remediation: {
      required: true,
      action_label: `登记 ${normalizedReportMonth} 正式财务指标契约`,
      action_detail: "从 Excel 正式样本冻结 source contract，再重新核对规则符合性检查。",
      required_artifact: `${normalizedReportMonth} 正式财务指标 Excel 样本`,
      artifact_status: "missing",
      registration_target: "backend/app/core_finance/formal_financial_indicators.py",
      verification: `python -m pytest tests/test_ledger_pnl_formal_indicator_rule_checks.py -q -k ${normalizedReportMonth}`,
    },
  };
}

function previousSyntheticReportMonth(reportMonth: string): string {
  const year = Number(reportMonth.slice(0, 4));
  const month = Number(reportMonth.slice(4, 6));
  return month === 1
    ? `${year - 1}12`
    : `${year}${String(month - 1).padStart(2, "0")}`;
}

function syntheticComparisonSha(reportMonth: string, salt: string): string {
  return `${reportMonth}${salt}`.padEnd(64, salt).slice(0, 64);
}

export function buildMockLedgerPnlCandidateFinancialIndicatorPeriodComparison(
  reportMonth: string,
): LedgerPnlCandidateFinancialIndicatorPeriodComparison {
  const normalizedReportMonth = reportMonth.trim();
  if (!/^\d{4}(?:0[1-9]|1[0-2])$/.test(normalizedReportMonth)) {
    throw new Error("Candidate period comparison report month must use YYYYMM.");
  }
  const comparisonMonth = previousSyntheticReportMonth(normalizedReportMonth);
  const twoMonthPrior = previousSyntheticReportMonth(comparisonMonth);
  const currentLedgerSha = syntheticComparisonSha(normalizedReportMonth, "a");

  return {
    contract_version: "candidate-financial-indicator-period-comparison-v2",
    report_month: normalizedReportMonth,
    report_date: reportMonthEnd(normalizedReportMonth),
    comparison_month: comparisonMonth,
    two_month_prior: twoMonthPrior,
    comparison_scope: "ledger_only_key_metrics",
    full_scope_status: "unavailable",
    full_scope_reason_code: "missing_required_sheet",
    full_scope_detail: `演示对比：${comparisonMonth} 日均工作簿缺少必需工作表“微贷”，完整 186 项重放不可用。`,
    full_scope_gaps: [{
      reason_code: "missing_required_sheet",
      source_kind: "daily",
      month: comparisonMonth,
      required_sheet: "微贷",
    }],
    overall_status: "partial",
    metric_status: "candidate",
    formal_use_allowed: false,
    certification_effect: "none",
    driver_status: "unclear",
    rule_version: "qdb-finance-2026-v1.0.1",
    rule_hash: "1".repeat(64),
    idempotency_key: syntheticComparisonSha(normalizedReportMonth, "d"),
    source_periods: [
      {
        month: normalizedReportMonth,
        report_date: reportMonthEnd(normalizedReportMonth),
        ledger_file_name: `总账对账${normalizedReportMonth}.xlsx`,
        ledger_sha256: currentLedgerSha,
        locked_sha256: currentLedgerSha,
        lock_status: "locked_match",
      },
      {
        month: comparisonMonth,
        report_date: reportMonthEnd(comparisonMonth),
        ledger_file_name: `总账对账${comparisonMonth}.xlsx`,
        ledger_sha256: syntheticComparisonSha(comparisonMonth, "b"),
        locked_sha256: null,
        lock_status: "unlocked",
      },
      {
        month: twoMonthPrior,
        report_date: reportMonthEnd(twoMonthPrior),
        ledger_file_name: `总账对账${twoMonthPrior}.xlsx`,
        ledger_sha256: syntheticComparisonSha(twoMonthPrior, "c"),
        locked_sha256: null,
        lock_status: "unlocked",
      },
    ],
    net_interest_component_bridge: {
      analysis_kind: "accounting_component_bridge",
      status: "available",
      metric_id: "income.interest.net",
      basis: "calendar_month_from_cumulative",
      method: "finance_metric_component_contribution",
      unit: "亿元",
      quality_status: "degraded_candidate",
      foot_status: "passed",
      net_delta_yi: "2.5000",
      component_contribution_total_yi: "2.5000",
      reconciliation_delta_yi: "0.0000",
      reasons: [],
      components: [
        {
          metric_id: "income.interest.loan.total",
          metric_name: "贷款利息收入",
          formula_weight: 1,
          current_metric_status: "ok",
          previous_metric_status: "ok",
          two_month_prior_metric_status: "ok",
          current_value_yi: "11.0000",
          previous_value_yi: "10.0000",
          current_source_value_yi: "50.0000",
          previous_source_value_yi: "39.0000",
          two_month_prior_source_value_yi: "29.0000",
          component_delta_yi: "1.0000",
          contribution_to_net_delta_yi: "1.0000",
          reasons: [],
        },
        {
          metric_id: "expense.interest.deposit.total",
          metric_name: "存款利息支出",
          formula_weight: -1,
          current_metric_status: "ok",
          previous_metric_status: "ok",
          two_month_prior_metric_status: "ok",
          current_value_yi: "6.0000",
          previous_value_yi: "5.5000",
          current_source_value_yi: "30.0000",
          previous_source_value_yi: "24.0000",
          two_month_prior_source_value_yi: "18.5000",
          component_delta_yi: "0.5000",
          contribution_to_net_delta_yi: "-0.5000",
          reasons: [],
        },
        {
          metric_id: "income.interest.investment",
          metric_name: "金融投资利息收入",
          formula_weight: 1,
          current_metric_status: "ok",
          previous_metric_status: "ok",
          two_month_prior_metric_status: "ok",
          current_value_yi: "6.0000",
          previous_value_yi: "4.5000",
          current_source_value_yi: "25.0000",
          previous_source_value_yi: "19.0000",
          two_month_prior_source_value_yi: "14.5000",
          component_delta_yi: "1.5000",
          contribution_to_net_delta_yi: "1.5000",
          reasons: [],
        },
        {
          metric_id: "income.interest.interbank_net",
          metric_name: "同业资产负债利息净收入",
          formula_weight: 1,
          current_metric_status: "ok",
          previous_metric_status: "ok",
          two_month_prior_metric_status: "ok",
          current_value_yi: "1.5000",
          previous_value_yi: "1.0000",
          current_source_value_yi: "10.0000",
          previous_source_value_yi: "8.5000",
          two_month_prior_source_value_yi: "7.5000",
          component_delta_yi: "0.5000",
          contribution_to_net_delta_yi: "0.5000",
          reasons: [],
        },
      ],
    },
    metrics: [
      {
        metric_id: "income.interest.net",
        metric_name: "利息净收入",
        basis: "calendar_month_from_cumulative",
        method: "finance_metric_cumulative_mom",
        unit: "亿元",
        comparison_status: "comparable",
        current_metric_status: "ok",
        previous_metric_status: "ok",
        two_month_prior_metric_status: "ok",
        current_value_yi: "12.5000",
        previous_value_yi: "10.0000",
        current_source_value_yi: "60.0000",
        previous_source_value_yi: "47.5000",
        two_month_prior_source_value_yi: "37.5000",
        delta_yi: "2.5000",
        change_rate: "0.2500",
        rate_reason: null,
        reasons: [],
        driver_status: "unclear",
        quality_status: "degraded_candidate",
      },
      ...[
        ["income.noninterest.total", "非息净收入合计", "28.0000", "23.0000", "19.0000"],
        ["income.operating.mother_bank", "母公司营业收入（可自动口径）", "88.0000", "75.0000", "61.0000"],
      ].map(([metricId, metricName, currentSourceValue, previousSourceValue, twoMonthPriorSourceValue]) => ({
        metric_id: metricId,
        metric_name: metricName,
        basis: "calendar_month_from_cumulative" as const,
        method: "finance_metric_cumulative_mom" as const,
        unit: "亿元" as const,
        comparison_status: "not_comparable" as const,
        current_metric_status: "warning" as const,
        previous_metric_status: "warning" as const,
        two_month_prior_metric_status: "warning" as const,
        current_value_yi: null,
        previous_value_yi: null,
        current_source_value_yi: currentSourceValue,
        previous_source_value_yi: previousSourceValue,
        two_month_prior_source_value_yi: twoMonthPriorSourceValue,
        delta_yi: null,
        change_rate: null,
        rate_reason: "metric_status_not_ok" as const,
        reasons: [
          "current:status=warning",
          "current:manual_required_not_supplied",
          "previous:status=warning",
          "previous:manual_required_not_supplied",
          "two_month_prior:status=warning",
          "two_month_prior:missing_account:main:cumulative:level1:DEMO_ACCOUNT",
        ],
        driver_status: "unclear" as const,
        quality_status: "not_comparable" as const,
      })),
      ...[
        ["balance.deposit.corporate.total::point", "公司存款合计", "105.0000", "100.0000", "5.0000", "0.0500"],
        ["balance.deposit.retail.total::point", "储蓄存款合计", "82.0000", "80.0000", "2.0000", "0.0250"],
        ["balance.loan.corporate.total::point", "公司贷款合计", "121.0000", "120.0000", "1.0000", "0.0083333333"],
        ["balance.loan.retail.total::point", "个人贷款合计", "49.0000", "50.0000", "-1.0000", "-0.0200"],
      ].map(([metricId, metricName, currentValue, previousValue, delta, rate]) => ({
        metric_id: metricId,
        metric_name: metricName,
        basis: "month_end_point" as const,
        method: "finance_metric_point_to_point" as const,
        unit: "亿元" as const,
        comparison_status: "comparable" as const,
        current_metric_status: "ok" as const,
        previous_metric_status: "ok" as const,
        two_month_prior_metric_status: null,
        current_value_yi: currentValue,
        previous_value_yi: previousValue,
        current_source_value_yi: currentValue,
        previous_source_value_yi: previousValue,
        two_month_prior_source_value_yi: null,
        delta_yi: delta,
        change_rate: rate,
        rate_reason: null,
        reasons: [],
        driver_status: "unclear" as const,
        quality_status: "degraded_candidate" as const,
      })),
    ],
  };
}
