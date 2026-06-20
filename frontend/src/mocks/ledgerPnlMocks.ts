/**
 * Mock payloads for the Ledger P&L domain.
 * Extracted from client.ts to reduce monolith size.
 */
import type {
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  LedgerPnlDataPayload,
} from "../api/contracts";

const mockLedgerMoney = (yuan: string) => ({
  yuan,
  yi: (Number(yuan) / 100_000_000).toFixed(2),
  wan: (Number(yuan) / 10_000).toFixed(2),
});

export const mockLedgerPnlDates: LedgerPnlDatesPayload = {
  dates: ["2025-12-31", "2025-11-30"],
};

export const mockLedgerPnlSummary: LedgerPnlSummaryPayload = {
  report_date: "2025-12-31",
  source_version: "sv_mock_ledger",
  ledger_total_assets: mockLedgerMoney("1250000000"),
  ledger_total_liabilities: mockLedgerMoney("980000000"),
  ledger_net_assets: mockLedgerMoney("270000000"),
  ledger_monthly_pnl_core: mockLedgerMoney("3520000"),
  ledger_monthly_pnl_all: mockLedgerMoney("4180000"),
  by_currency: [
    { currency: "CNX", total_pnl: mockLedgerMoney("3010000") },
    { currency: "CNY", total_pnl: mockLedgerMoney("510000") },
  ],
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
  ],
};

export const mockLedgerPnlData: LedgerPnlDataPayload = {
  report_date: "2025-12-31",
  items: [
    {
      account_code: "514100",
      account_name: "利息收入",
      currency: "CNX",
      beginning_balance: mockLedgerMoney("101200000"),
      ending_balance: mockLedgerMoney("106500000"),
      monthly_pnl: mockLedgerMoney("880000"),
      daily_avg_balance: mockLedgerMoney("104100000"),
      days_in_period: 31,
    },
    {
      account_code: "516100",
      account_name: "公允价值变动损益",
      currency: "CNX",
      beginning_balance: mockLedgerMoney("10000000"),
      ending_balance: mockLedgerMoney("11200000"),
      monthly_pnl: mockLedgerMoney("420000"),
      daily_avg_balance: mockLedgerMoney("10600000"),
      days_in_period: 31,
    },
  ],
  summary: {
    total_pnl_cnx: mockLedgerMoney("1300000"),
    total_pnl_cny: mockLedgerMoney("0"),
    total_pnl: mockLedgerMoney("1300000"),
    count: 2,
  },
};

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
