import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  LedgerMoneyValue,
  LedgerPnlAnalysisPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlSummaryPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  ResultMeta,
} from "../api/contracts";
import LedgerPnlPage from "../features/ledger-pnl/pages/LedgerPnlPage";

function renderLedgerPnlPage(client: ApiClient, initialEntry = "/ledger-pnl?report_date=2026-03-31") {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>
    );
  }

  const analysisClient: ApiClient = {
    ...client,
    getLedgerPnlAnalysis: async (reportDate, currency = "CNX") =>
      buildLedgerAnalysisEnvelope(reportDate, currency === "CNY" ? "CNY" : "CNX"),
  };

  return render(
    <Wrapper>
      <ApiClientProvider client={analysisClient}>
        <LedgerPnlPage />
      </ApiClientProvider>
    </Wrapper>,
  );
}

function buildMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "ledger",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_ledger_test",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_test",
    cache_version: "cv_ledger_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
    tables_used: ["qdb_general_ledger_workbook"],
  };
}

function buildAnalyticalMeta(resultKind: string): ResultMeta {
  return {
    ...buildMeta(resultKind),
    basis: "analytical",
    formal_use_allowed: false,
    trace_id: `tr_${resultKind}`,
    source_version: "sv_qdb_gl_monthly_analysis_test",
    rule_version: "rv_qdb_gl_monthly_analysis_test",
    cache_version: "cv_qdb_gl_monthly_analysis_test",
  };
}

function buildLedgerMeta(resultKind: string): ResultMeta {
  return {
    ...buildMeta(resultKind),
    basis: "ledger",
    formal_use_allowed: false,
    trace_id: `tr_${resultKind}`,
    source_version: "sv_ledger_test",
    rule_version: "rv_ledger_test",
    cache_version: "cv_ledger_test",
    requested_report_date: "2026-03-31",
    resolved_report_date: "2026-03-31",
    as_of_date: "2026-03-31",
    date_basis: "ledger_report_date",
    evidence_rows: 1,
    tables_used: ["qdb_general_ledger_workbook"],
    filters_applied: { report_date: "2026-03-31", currency: "ALL" },
  };
}

function money(yuan: string, wan = "999.99"): LedgerMoneyValue {
  return {
    yuan,
    yi: (Number(yuan) / 100_000_000).toFixed(2),
    ...(wan === "" ? {} : { wan }),
  } as LedgerMoneyValue;
}

function buildLedgerAnalysisEnvelope(
  reportDate: string,
  currencyBasis: "CNX" | "CNY",
): ApiEnvelope<LedgerPnlAnalysisPayload> {
  const zero = money("0", "");
  const total = money("10", "");
  return {
    result_meta: {
      ...buildLedgerMeta("ledger_pnl.analysis"),
      requested_report_date: reportDate,
      resolved_report_date: reportDate,
      as_of_date: reportDate,
      evidence_rows: 1,
      filters_applied: {
        report_date: reportDate,
        currency: currencyBasis,
        currency_basis: currencyBasis,
      },
    },
    result: {
      report_date: reportDate,
      source_version: "sv_ledger_test",
      currency_basis: currencyBasis,
      basis_availability: { CNX: "ready", CNY: "ready" },
      analysis_status: "ready",
      metric_status: "candidate",
      conclusion: {
        direction: "positive",
        other_effect: "neutral",
        core_pnl: total,
        other_5_pnl: zero,
        all_pnl: total,
      },
      pnl_bridge: {
        components: [
          { metric_key: "core_pnl", metric_name: "核心损益", amount: total },
          { metric_key: "other_5_pnl", metric_name: "其他 5* 损益", amount: zero },
        ],
        total,
        residual: zero,
      },
      basis_comparison: [],
      contributors: {
        positive_total: total,
        negative_total: zero,
        net_total: total,
        top_positive: [
          {
            rank: 1,
            account_code: "514100",
            account_name: "利息收入",
            amount: total,
            count: 1,
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
      calculation_basis: {
        core_pnl_prefixes: ["514", "516", "517"],
        all_pnl_prefixes: ["5"],
        other_5_pnl_formula: "all_pnl - core_pnl",
        other_5_pnl_boundary: "candidate arithmetic residual",
        basis_difference_formula: "CNX - CNY",
        basis_boundary: "overlapping accounting bases; not FX PnL",
        basis_availability_boundary: "each metric follows its own evidence; missing values stay unavailable",
        metric_boundary: "candidate ledger analysis",
        previous_period_rule: "previous available report date",
      },
    },
  };
}

function buildFormalIndicatorContractPayload(): LedgerPnlFormalFinancialIndicatorContractPayload {
  return {
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
      "This contract freezes the Excel formal-indicator sample and current source status.",
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
    status_semantics: {
      formal_pending:
        "Excel has the formal indicator value, but the governed production source is not connected.",
      candidate_qdb_aligned:
        "QDB analytical value aligns to the Excel value within display precision, but remains analytical.",
      needs_reconciliation:
        "QDB has a related analytical value, but it does not reconcile to the Excel formal value.",
    },
    metrics: [
      {
        metric_key: "group.total_assets",
        metric_name: "集团总资产",
        scope: "group_consolidated",
        excel_value: "8342.0254700000",
        unit: "亿元",
        excel_ref: "财务指标-汇总!K35 -> 财务指标-计算表!K30",
        formula: "external/formal calculation table input",
        source_status: "needs_reconciliation",
        system_metric: "qdb.total_assets",
        system_value: "8144.05",
        reconciliation_gap: "197.97547",
        value: null,
        basis: "formal_financial_indicator_source_contract",
        formal_use_allowed: false,
        source_version: "sv_formal_financial_indicators_excel_202603_contract",
        rule_version: "rv_formal_financial_indicators_source_status_v1",
        consolidation_scope: "group_consolidated",
        cell_ref: "财务指标-汇总!K35 -> 财务指标-计算表!K30",
        golden_sample_ref: "GS-LEDGER-PNL-FIN-IND-202603-B#group.total_assets",
        missing_reason: "正式财务指标来源未接入；QDB 分析值与 Excel 正式样本存在差异，需先对账。",
      },
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
      {
        metric_key: "group.asset_quality_loan_balance",
        metric_name: "贷款余额（集团资产质量口径）",
        scope: "group_consolidated",
        excel_value: "4193.9954022127",
        unit: "亿元",
        excel_ref: "财务指标-汇总!K53 -> 财务指标-计算表!K41",
        formula: "external/formal calculation table input",
        source_status: "needs_reconciliation",
        system_metric: "qdb.loan_spot",
        system_value: "4189.47",
        reconciliation_gap: "4.5254022127",
        value: null,
        basis: "formal_financial_indicator_source_contract",
        formal_use_allowed: false,
        source_version: "sv_formal_financial_indicators_excel_202603_contract",
        rule_version: "rv_formal_financial_indicators_source_status_v1",
        consolidation_scope: "group_consolidated",
        cell_ref: "财务指标-汇总!K53 -> 财务指标-计算表!K41",
        golden_sample_ref: "GS-LEDGER-PNL-FIN-IND-202603-B#group.asset_quality_loan_balance",
        missing_reason: "正式财务指标来源未接入；QDB 分析值与 Excel 正式样本存在差异，需先对账。",
      },
      {
        metric_key: "group.allowance_to_loan_ratio",
        metric_name: "拨贷比",
        scope: "group_consolidated",
        excel_value: "2.9263169853",
        unit: "%",
        excel_ref: "财务指标-汇总!K55 = K50 / K53",
        formula: "K50 / K53",
        source_status: "needs_reconciliation",
        system_metric: "qdb.allowance_to_loan_ratio",
        system_value: "2.70",
        reconciliation_gap: "0.2263169853",
        value: null,
        basis: "formal_financial_indicator_source_contract",
        formal_use_allowed: false,
        source_version: "sv_formal_financial_indicators_excel_202603_contract",
        rule_version: "rv_formal_financial_indicators_source_status_v1",
        consolidation_scope: "group_consolidated",
        cell_ref: "财务指标-汇总!K55 = K50 / K53",
        golden_sample_ref: "GS-LEDGER-PNL-FIN-IND-202603-B#group.allowance_to_loan_ratio",
        missing_reason: "正式财务指标来源未接入；QDB 分析值与 Excel 正式样本存在差异，需先对账。",
      },
    ],
  };
}

function buildReleasedFormalIndicatorContractPayload(): LedgerPnlFormalFinancialIndicatorContractPayload {
  const base = buildFormalIndicatorContractPayload();
  return {
    ...base,
    sample_status: "formal_contract",
    formal_use_allowed: true,
    release_gate: undefined,
    contract_note: "Formal financial indicator values are approved for display.",
    metrics: base.metrics.slice(0, 2).map((metric) => ({
      ...metric,
      source_status: "formal_pending",
      system_value: null,
      reconciliation_gap: null,
      value: metric.excel_value,
      formal_use_allowed: true,
      missing_reason: "正式财务指标来源已放行；展示值来自后端契约 value。",
    })),
  };
}

function buildEmptyFormalIndicatorContractPayload(): LedgerPnlFormalFinancialIndicatorContractPayload {
  return {
    ...buildFormalIndicatorContractPayload(),
    sample_id: "GS-LEDGER-PNL-FIN-IND-202603-EMPTY",
    metrics: [],
    release_gate: undefined,
    contract_note:
      "Formal financial indicator contract header exists but no metric rows were returned.",
  };
}

function buildMissingFormalIndicatorContractPayload(): LedgerPnlFormalFinancialIndicatorContractPayload {
  return {
    sample_id: "GS-LEDGER-PNL-FIN-IND-202605-MISSING",
    sample_status: "missing_contract",
    surface: "/ledger-pnl formal financial indicator source contract",
    report_month: "202605",
    report_date: "2026-05-31",
    source_workbook: "",
    source_sheet: "",
    source_basis: "No frozen formal financial indicator contract is registered for requested report_month.",
    source_version: "sv_formal_financial_indicators_contract_unavailable",
    rule_version: "rv_formal_financial_indicators_source_status_v1",
    formal_use_allowed: false,
    contract_note:
      "No frozen formal financial indicator contract is registered for requested report_month. Formal values remain unavailable and must not be backfilled from analytical candidates.",
    remediation: {
      required: true,
      action_label: "补齐 202605 正式财务指标 Excel 冻结样本",
      action_detail: "先取得并冻结 202605 正式财务指标 Excel 样本，再登记 source contract 并重新核对 QDB 候选值。",
      required_artifact: "202605 正式财务指标 Excel 冻结样本",
      artifact_status: "missing",
      blocking_reason: "未找到 202605 正式财务指标 Excel 冻结样本，不能登记正式契约或用 QDB 候选值回填。",
      acceptance_criteria: [
        "样本必须来自 202605 正式财务指标 Excel 冻结版本",
        "样本必须包含财务指标-汇总表及单元格引用",
        "样本值必须按亿元/%等原始单位冻结，不得由 QDB 候选值反推",
        "登记后必须重新运行 Ledger PnL 正式财务指标金样本测试",
      ],
      registration_package: {
        fixture_target:
          "tests/fixtures/formal_financial_indicators/ledger_pnl_202605_financial_indicator_golden.json",
        registry_target: "backend/app/core_finance/formal_financial_indicators.py::_METRICS_202605",
        contract_builder: "build_formal_financial_indicator_contract(report_month='202605')",
        release_gate: "formal_use_allowed 只能在契约 value 均来自冻结样本且金样本测试通过后放行",
      },
      registration_package_guard: {
        status: "ready",
        required_fields: ["fixture_target", "registry_target", "contract_builder", "release_gate"],
        missing_fields: [],
        blocking_rule: "登记包四项齐备前不得登记正式契约或放行 formal_use_allowed",
      },
      readback_acceptance: {
        label: "登记后回读验收",
        readback_query: "report_month=202605 必须返回已登记契约",
        target_state: "sample_status=contract_fixture，metrics 不得为空",
        release_state: "若正式生产来源尚未接入，release_gate.status 必须为 registered_pending_release",
        formal_use_guard: "formal_use_allowed 必须保持 false，直到正式来源接入且放行证据齐备",
        source_guard: "契约值必须来自冻结 Excel 样本；QDB 候选值只能保留在 system_value/reconciliation_gap",
        verification: "python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py -q",
      },
      registration_target: "backend/app/core_finance/formal_financial_indicators.py",
      verification: "python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py -q",
    },
    status_semantics: {
      formal_pending:
        "Excel has the formal indicator value, but the governed production source is not connected.",
      candidate_qdb_aligned:
        "QDB analytical value aligns to the Excel value within display precision, but remains analytical.",
      needs_reconciliation:
        "QDB has a related analytical value, but it does not reconcile to the Excel formal value.",
    },
    metrics: [],
  };
}

function buildBlockedRegistrationPackageContractPayload(): LedgerPnlFormalFinancialIndicatorContractPayload {
  const contract = buildMissingFormalIndicatorContractPayload();
  return {
    ...contract,
    remediation: contract.remediation
      ? {
          ...contract.remediation,
          artifact_status: "available",
          blocking_reason: "已找到 202605 正式财务指标 Excel 冻结样本，但登记包缺少放行条件。",
          registration_package: {
            ...contract.remediation.registration_package,
            release_gate: "",
          },
          registration_package_guard: {
            status: "blocked",
            required_fields: ["fixture_target", "registry_target", "contract_builder", "release_gate"],
            missing_fields: ["release_gate"],
            blocking_rule: "登记包四项齐备前不得登记正式契约或放行 formal_use_allowed",
          },
        }
      : undefined,
  };
}

describe("LedgerPnlPage", () => {
  it("renders ledger summary and detail metadata as non-formal ledger basis", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: buildLedgerMeta("ledger_pnl.summary"),
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("10.00"),
          ledger_monthly_pnl_all: money("10.00"),
          ledger_total_assets: money("100.00"),
          ledger_total_liabilities: money("50.00"),
          ledger_net_assets: money("50.00"),
          by_currency: [{ currency: "CNX", total_pnl: money("10.00") }],
          by_account: [
            {
              account_code: "51401000001",
              account_name: "利息收入",
              total_pnl: money("10.00"),
              count: 1,
            },
          ],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: buildLedgerMeta("ledger_pnl.data"),
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("10.00"),
            total_pnl_cny: money("0.00"),
            total_pnl: money("10.00"),
            count: 1,
          },
          items: [
            {
              account_code: "51401000001",
              account_name: "利息收入",
              currency: "CNX",
              beginning_balance: money("0.00"),
              ending_balance: money("0.00"),
              monthly_pnl: money("10.00"),
              daily_avg_balance: money("0.00"),
              days_in_period: 31,
            },
          ],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
        result_meta: {
          ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          basis: "ledger" as const,
          formal_use_allowed: false,
        },
        result: buildFormalIndicatorContractPayload(),
      })),
    });

    const resultMetaPanel = await screen.findByTestId("ledger-pnl-result-meta-panel");
    const summaryMeta = await within(resultMetaPanel).findByTestId("ledger-pnl-result-meta-panel-summary");
    const dataMeta = await within(resultMetaPanel).findByTestId("ledger-pnl-result-meta-panel-data");
    const cards = await screen.findByTestId("ledger-pnl-summary-cards");

    expect(cards).toHaveTextContent("核心损益");
    expect(cards).toHaveTextContent("全量损益");
    expect(cards).toHaveTextContent("净资产");
    expect(cards).toHaveTextContent("MTR-LPN-001");
    expect(cards).toHaveTextContent("MTR-LPN-002");
    expect(cards).toHaveTextContent("MTR-LPN-003");
    expect(cards).toHaveTextContent("pending_confirmation=true");
    expect(cards).toHaveTextContent("不能替代正式 PnL 或产品分类 PnL");

    expect(summaryMeta).toHaveTextContent("Ledger 汇总");
    expect(summaryMeta).toHaveTextContent("台账口径");
    expect(summaryMeta).toHaveTextContent("正式可用");
    expect(summaryMeta).toHaveTextContent("否");
    expect(summaryMeta).toHaveTextContent("ledger_report_date");
    expect(summaryMeta).toHaveTextContent("qdb_general_ledger_workbook");

    expect(dataMeta).toHaveTextContent("Ledger 明细");
    expect(dataMeta).toHaveTextContent("台账口径");
    expect(dataMeta).toHaveTextContent("正式可用");
    expect(dataMeta).toHaveTextContent("否");
    expect(dataMeta).toHaveTextContent("ledger_report_date");
    expect(dataMeta).toHaveTextContent("qdb_general_ledger_workbook");
  });

  it("renders the formal financial indicator source contract without promoting candidate values", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => ({
      result_meta: {
        ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
        basis: "ledger" as const,
        quality_flag: "warning" as const,
        as_of_date: "2026-03-31",
        date_basis: "report_month_end",
        formal_use_allowed: false,
      },
      result: buildFormalIndicatorContractPayload(),
    }));

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.summary"),
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("0.00"),
          ledger_monthly_pnl_all: money("0.00"),
          ledger_total_assets: money("0.00"),
          ledger_total_liabilities: money("0.00"),
          ledger_net_assets: money("0.00"),
          by_currency: [],
          by_account: [],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.data"),
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("0.00"),
            total_pnl_cny: money("0.00"),
            total_pnl: money("0.00"),
            count: 0,
          },
          items: [],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators,
    });

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202603");
    });

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    expect(panel).toHaveTextContent("正式财务指标源契约");
    expect(panel).toHaveTextContent("report_month 202603");
    expect(panel).toHaveTextContent("formal_use_allowed=false");
    expect(panel).toHaveTextContent("formal_pending 1");
    expect(panel).toHaveTextContent("candidate_qdb_aligned 1");
    expect(panel).toHaveTextContent("needs_reconciliation 4");

    const strip = screen.getByTestId("ledger-pnl-functional-audit-strip");
    expect(strip).toHaveTextContent("正式契约缺口");
    expect(strip).toHaveTextContent("正式待接入 1");
    expect(strip).toHaveTextContent("QDB候选 1");
    expect(strip).toHaveTextContent("需对账 4");

    const decisionPath = screen.getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("正式状态正式契约已登记，待放行");
    expect(decisionPath).toHaveTextContent("正式补证结论正式契约已登记待放行；补齐放行证据后再回读确认");
    expect(decisionPath).toHaveTextContent("执行状态已登记待放行");
    expect(decisionPath).toHaveTextContent(
      "回读动作登记来源接入证据并重新读取契约，确认 formal_use_allowed=false 保持到放行前",
    );
    expect(decisionPath).not.toHaveTextContent("待登记正式契约");
    expect(decisionPath).not.toHaveTextContent("补证材料待补 0/3");

    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollTargets: HTMLElement[] = [];
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement) {
      scrollTargets.push(this);
    });

    try {
      const releaseGate = await screen.findByTestId(
        "ledger-pnl-formal-indicator-source-contract-release-gate",
      );
      const formalPathButton = within(decisionPath).getByRole("button", {
        name: "正式补证路径 登记来源接入证据并重新读取契约，确认 formal_use_allowed=false 保持到放行前",
      });

      await userEvent.click(formalPathButton);

      expect(scrollTargets).toEqual([releaseGate]);
      expect(releaseGate).toHaveFocus();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }

    const decision = screen.getByTestId("ledger-pnl-formal-indicator-source-contract-decision");
    expect(decision).toHaveTextContent("正式财务指标已登记待放行");
    expect(decision).toHaveTextContent(
      "202603 正式财务指标样本契约已登记，但正式生产来源尚未接入，不能放行 formal_use_allowed。",
    );
    expect(panel).toHaveTextContent("release_gate registered_pending_release");
    expect(panel).toHaveTextContent("governed production source connected for formal financial indicators");
    expect(panel).toHaveTextContent("Ledger PnL formal financial indicator golden sample test passes");
    expect(panel).toHaveTextContent(
      "登记来源接入证据并重新读取契约，确认 formal_use_allowed=false 保持到放行前",
    );
    expect(panel).not.toHaveTextContent("本月未登记正式财务指标契约");
    expect(panel).not.toHaveTextContent("正式财务指标可用");

    const formalPendingRow = screen.getByTestId(
      "ledger-pnl-formal-indicator-source-contract-row-group.operating_revenue",
    );
    expect(formalPendingRow).toHaveTextContent("集团营业收入");
    expect(formalPendingRow).toHaveTextContent(/正式展示值\s*未接入/);
    expect(formalPendingRow).toHaveTextContent(/Excel 样本值\s*43.4194731314 亿元/);
    expect(formalPendingRow).toHaveTextContent(/系统候选值\s*—/);

    const qdbCandidateRow = screen.getByTestId(
      "ledger-pnl-formal-indicator-source-contract-row-parent.loan_balance",
    );
    expect(qdbCandidateRow).toHaveTextContent("贷款余额（母公司）");
    expect(qdbCandidateRow).toHaveTextContent(/正式展示值\s*未接入/);
    expect(qdbCandidateRow).toHaveTextContent(/系统候选值\s*4189.47 亿元/);
    expect(qdbCandidateRow).toHaveTextContent("候选对照，不具备正式使用权限");

    const reconciliationRow = screen.getByTestId(
      "ledger-pnl-formal-indicator-source-contract-row-parent.deposit_balance",
    );
    expect(reconciliationRow).toHaveTextContent("存款余额（母公司）");
    expect(reconciliationRow).toHaveTextContent("对账差异 4.6780974646");
    expect(reconciliationRow).toHaveTextContent("需先对账");
  });

  it("marks formal contract materials as pending while the contract is still loading", async () => {
    const base = createApiClient({ mode: "mock" });
    type FormalContractResult = Awaited<ReturnType<typeof base.getLedgerPnlFormalFinancialIndicators>>;
    let resolveFormalContract: ((value: FormalContractResult) => void) | undefined;
    const formalContractRequest = new Promise<FormalContractResult>((resolve) => {
      resolveFormalContract = resolve;
    });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(() => formalContractRequest);

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("ledger_pnl.summary"),
          evidence_rows: 1,
        },
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("1.00"),
          ledger_monthly_pnl_all: money("1.00"),
          ledger_total_assets: money("0.00"),
          ledger_total_liabilities: money("0.00"),
          ledger_net_assets: money("0.00"),
          by_currency: [{ currency: "CNY", total_pnl: money("1.00") }],
          by_account: [
            {
              account_code: "50101000001",
              account_name: "短期信用贷款利息收入",
              total_pnl: money("1.00"),
              count: 1,
            },
          ],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("ledger_pnl.data"),
          evidence_rows: 1,
        },
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("0.00"),
            total_pnl_cny: money("1.00"),
            total_pnl: money("1.00"),
            count: 1,
          },
          items: [
            {
              account_code: "50101000001",
              account_name: "短期信用贷款利息收入",
              currency: "CNY",
              beginning_balance: money("0.00"),
              ending_balance: money("1.00"),
              monthly_pnl: money("1.00"),
              daily_avg_balance: money("0.00"),
              days_in_period: 31,
            },
          ],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators,
    });

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202603");
    });

    const strip = screen.getByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，正式契约读取中");
      expect(strip).toHaveTextContent("分析证据行1");
      expect(strip).toHaveTextContent("候选分析状态可用 · 候选口径");
      expect(strip).toHaveTextContent("候选分析证据ledger_pnl.analysis · evidence 1");
    });

    const decisionPath = screen.getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("材料完整性等待正式契约读取");
    expect(decisionPath).toHaveTextContent("正式补证结论等待正式契约读取后再判断补证闭环");
    expect(decisionPath).toHaveTextContent("执行状态读取正式契约中");
    expect(decisionPath).not.toHaveTextContent("无缺契约补证材料");

    resolveFormalContract?.({
      result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
      result: buildFormalIndicatorContractPayload(),
    });
  });

  it("surfaces released formal financial indicator contracts as formal values, not candidate work", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => ({
      result_meta: {
        ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
        basis: "ledger" as const,
        quality_flag: "ok" as const,
        as_of_date: "2026-03-31",
        date_basis: "report_month_end",
        formal_use_allowed: true,
      },
      result: buildReleasedFormalIndicatorContractPayload(),
    }));

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("ledger_pnl.summary"),
          evidence_rows: 12,
          quality_flag: "ok" as const,
        },
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("1.00"),
          ledger_monthly_pnl_all: money("1.00"),
          ledger_total_assets: money("0.00"),
          ledger_total_liabilities: money("0.00"),
          ledger_net_assets: money("0.00"),
          by_currency: [],
          by_account: [],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("ledger_pnl.data"),
          evidence_rows: 12,
          quality_flag: "ok" as const,
        },
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("0.00"),
            total_pnl_cny: money("1.00"),
            total_pnl: money("1.00"),
            count: 12,
          },
          items: [],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators,
    });

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202603");
    });

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    await waitFor(() => {
      expect(panel).toHaveTextContent("formal_use_allowed=true");
    });

    const strip = screen.getByTestId("ledger-pnl-functional-audit-strip");
    expect(strip).toHaveTextContent("正式财务指标可用");
    expect(strip).toHaveTextContent("正式值可用");
    expect(strip).not.toHaveTextContent("正式 PnL 与正式财务指标仍需单独放行");

    const decisionPath = screen.getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("正式状态正式值可用");
    expect(decisionPath).toHaveTextContent("正式补证结论正式契约已放行；无需正式补证");
    expect(decisionPath).toHaveTextContent("材料完整性无缺契约补证材料");
    expect(decisionPath).toHaveTextContent("执行状态已读取正式契约");
    expect(decisionPath).toHaveTextContent("回读动作已完成正式契约回读");
    expect(decisionPath).not.toHaveTextContent("待登记正式契约");
    expect(decisionPath).not.toHaveTextContent("重新读取正式契约并复核 formal_use_allowed");
    expect(within(decisionPath).queryByRole("button", { name: /正式补证路径/ })).not.toBeInTheDocument();

    expect(panel).toHaveTextContent("formal_use_allowed=true");
    expect(panel).toHaveTextContent("正式财务指标契约已读取");
    expect(panel).toHaveTextContent("按后端契约返回的正式值展示");
    expect(panel).not.toHaveTextContent("下一步核账队列");
    expect(panel).not.toHaveTextContent("候选对照，不具备正式使用权限");
    expect(panel).not.toHaveTextContent("正式展示值未接入");

    const revenueRow = screen.getByTestId(
      "ledger-pnl-formal-indicator-source-contract-row-group.operating_revenue",
    );
    expect(revenueRow).toHaveTextContent("集团营业收入");
    expect(revenueRow).toHaveTextContent(/正式展示值\s*43.4194731314 亿元/);
    expect(revenueRow).toHaveTextContent(/Excel 样本值\s*43.4194731314 亿元/);
    expect(revenueRow).toHaveTextContent(/系统候选值\s*—/);
  });

  it("treats registered formal contracts with no metric rows as missing formal detail", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => ({
      result_meta: {
        ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
        basis: "ledger" as const,
        quality_flag: "warning" as const,
        as_of_date: "2026-03-31",
        date_basis: "report_month_end",
        formal_use_allowed: false,
        evidence_rows: 0,
      },
      result: buildEmptyFormalIndicatorContractPayload(),
    }));

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("ledger_pnl.summary"),
          evidence_rows: 12,
          quality_flag: "ok" as const,
        },
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("1.00"),
          ledger_monthly_pnl_all: money("1.00"),
          ledger_total_assets: money("0.00"),
          ledger_total_liabilities: money("0.00"),
          ledger_net_assets: money("0.00"),
          by_currency: [{ currency: "CNY", total_pnl: money("1.00") }],
          by_account: [
            {
              account_code: "50101000001",
              account_name: "短期信用贷款利息收入",
              total_pnl: money("1.00"),
              count: 1,
            },
          ],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("ledger_pnl.data"),
          evidence_rows: 12,
          quality_flag: "ok" as const,
        },
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("0.00"),
            total_pnl_cny: money("1.00"),
            total_pnl: money("1.00"),
            count: 12,
          },
          items: [
            {
              account_code: "50101000001",
              account_name: "短期信用贷款利息收入",
              currency: "CNY",
              beginning_balance: money("0.00"),
              ending_balance: money("1.00"),
              monthly_pnl: money("1.00"),
              daily_avg_balance: money("0.00"),
              days_in_period: 31,
            },
          ],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators,
    });

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202603");
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，正式契约明细缺失");
      expect(strip).toHaveTextContent("正式契约缺口无正式契约明细");
      expect(strip).toHaveTextContent("候选分析状态可用 · 候选口径");
    });

    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("正式状态正式契约明细缺失，正式值不可用");
    expect(decisionPath).toHaveTextContent("材料完整性正式契约明细缺失");
    expect(decisionPath).toHaveTextContent("正式补证结论正式契约已读取但没有指标明细；先恢复明细生成，再回读正式契约");
    expect(decisionPath).not.toHaveTextContent("正式状态正式值不可用，仅作候选核对");

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    expect(panel).toHaveTextContent("正式财务指标契约明细缺失");
    expect(panel).toHaveTextContent("契约头已返回，但没有任何指标明细；正式值不可用于展示。");
    expect(panel).toHaveTextContent("暂无正式财务指标源契约数据");
    expect(panel).not.toHaveTextContent("正式财务指标尚未放行");
  });

  it("ranks formal contract gaps into an actionable reconciliation queue", async () => {
    const base = createApiClient({ mode: "mock" });
    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.summary"),
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("1.00"),
          ledger_monthly_pnl_all: money("1.00"),
          ledger_total_assets: money("0.00"),
          ledger_total_liabilities: money("0.00"),
          ledger_net_assets: money("0.00"),
          by_currency: [],
          by_account: [
            {
              account_code: "50101000001",
              account_name: "短期信用贷款利息收入",
              total_pnl: money("1.00"),
              count: 1,
            },
          ],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.data"),
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("0.00"),
            total_pnl_cny: money("1.00"),
            total_pnl: money("1.00"),
            count: 1,
          },
          items: [],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
        result_meta: {
          ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          basis: "ledger" as const,
          quality_flag: "warning" as const,
          formal_use_allowed: false,
        },
        result: buildFormalIndicatorContractPayload(),
      })),
    });

    const queue = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-action-queue");
    expect(queue).toHaveTextContent("下一步核账队列");
    expect(queue).toHaveTextContent("先处理有系统候选但未对齐的项目，再补正式来源。");

    const items = within(queue).getAllByTestId(
      /^ledger-pnl-formal-indicator-source-contract-action-item-/,
    );
    expect(items).toHaveLength(6);
    expect(items[0]).toHaveTextContent("1");
    expect(items[0]).toHaveTextContent("集团总资产");
    expect(items[0]).toHaveTextContent("先对账 QDB 候选与 Excel 样本");
    expect(items[0]).toHaveTextContent("对账差异 197.97547 亿元");
    expect(items[0]).toHaveTextContent("财务指标-汇总!K35 -> 财务指标-计算表!K30");

    expect(items[1]).toHaveTextContent("存款余额（母公司）");
    expect(items[1]).toHaveTextContent("对账差异 4.6780974646 亿元");

    expect(items[2]).toHaveTextContent("贷款余额（集团资产质量口径）");
    expect(items[3]).toHaveTextContent("拨贷比");

    expect(items[4]).toHaveTextContent("贷款余额（母公司）");
    expect(items[4]).toHaveTextContent("候选已对齐，等待正式来源放行");

    expect(items[5]).toHaveTextContent("集团营业收入");
    expect(items[5]).toHaveTextContent("补正式财务指标来源");
    expect(items[5]).toHaveTextContent("系统候选值 —");
  });

  it("surfaces missing formal financial indicator contracts as unavailable instead of empty success", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => ({
      result_meta: {
        ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
        basis: "ledger" as const,
        quality_flag: "warning" as const,
        as_of_date: "2026-05-31",
        date_basis: "report_month_end",
        evidence_rows: 0,
        formal_use_allowed: false,
        source_version: "sv_formal_financial_indicators_contract_unavailable",
      },
      result: buildMissingFormalIndicatorContractPayload(),
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.summary"),
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("0.00"),
            ledger_monthly_pnl_all: money("0.00"),
            ledger_total_assets: money("0.00"),
            ledger_total_liabilities: money("0.00"),
            ledger_net_assets: money("0.00"),
            by_currency: [],
            by_account: [],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.data"),
          result: {
            report_date: "2026-05-31",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: 0,
            },
            items: [],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators,
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202605");
    });

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    expect(panel).toHaveTextContent("report_month 202605");
    expect(panel).toHaveTextContent("sample_status missing_contract");
    expect(panel).toHaveTextContent("formal_use_allowed=false");
    expect(panel).toHaveTextContent("本月未登记正式财务指标契约");
    expect(panel).toHaveTextContent("正式值不可用于展示，分析候选值不会回填");
    expect(panel).toHaveTextContent("后台未登记本月正式财务指标契约");
    expect(panel).not.toHaveTextContent("No frozen formal financial indicator contract is registered");
    expect(panel).not.toHaveTextContent("暂无正式财务指标源契约数据");
    expect(panel).toHaveTextContent("缺契约补证动作");
    expect(panel).toHaveTextContent("补齐 202605 正式财务指标 Excel 冻结样本");
    expect(panel).toHaveTextContent(
      "先取得并冻结 202605 正式财务指标 Excel 样本，再登记 source contract 并重新核对 QDB 候选值。",
    );
    const checklist = within(panel).getByTestId("ledger-pnl-formal-indicator-source-contract-material-checklist");
    expect(checklist).toHaveTextContent("正式样本缺失 0/1");
    expect(checklist).toHaveTextContent("物料202605 正式财务指标 Excel 冻结样本");
    expect(checklist).toHaveTextContent(
      "阻断未找到 202605 正式财务指标 Excel 冻结样本，不能登记正式契约或用 QDB 候选值回填。",
    );
    expect(checklist).toHaveTextContent("验收样本必须来自 202605 正式财务指标 Excel 冻结版本");
    expect(checklist).toHaveTextContent("样本必须包含财务指标-汇总表及单元格引用");
    expect(checklist).toHaveTextContent("样本值必须按亿元/%等原始单位冻结，不得由 QDB 候选值反推");
    expect(checklist).toHaveTextContent("登记后必须重新运行 Ledger PnL 正式财务指标金样本测试");
    expect(checklist).toHaveTextContent(
      "样本落盘tests/fixtures/formal_financial_indicators/ledger_pnl_202605_financial_indicator_golden.json",
    );
    expect(checklist).toHaveTextContent(
      "契约登记backend/app/core_finance/formal_financial_indicators.py::_METRICS_202605",
    );
    expect(checklist).toHaveTextContent(
      "构建入口build_formal_financial_indicator_contract(report_month='202605')",
    );
    expect(checklist).toHaveTextContent(
      "放行条件formal_use_allowed 只能在契约 value 均来自冻结样本且金样本测试通过后放行",
    );
    expect(checklist).toHaveTextContent("登记包守卫ready");
    expect(checklist).toHaveTextContent("必备字段fixture_target；registry_target；contract_builder；release_gate");
    expect(checklist).toHaveTextContent("缺失字段无");
    expect(checklist).toHaveTextContent("守卫规则登记包四项齐备前不得登记正式契约或放行 formal_use_allowed");
    expect(checklist).toHaveTextContent("登记后回读验收report_month=202605 必须返回已登记契约");
    expect(checklist).toHaveTextContent("目标状态sample_status=contract_fixture，metrics 不得为空");
    expect(checklist).toHaveTextContent(
      "待放行状态若正式生产来源尚未接入，release_gate.status 必须为 registered_pending_release",
    );
    expect(checklist).toHaveTextContent(
      "不得放行formal_use_allowed 必须保持 false，直到正式来源接入且放行证据齐备",
    );
    expect(checklist).toHaveTextContent(
      "来源守卫契约值必须来自冻结 Excel 样本；QDB 候选值只能保留在 system_value/reconciliation_gap",
    );
    expect(checklist).toHaveTextContent(
      "回读验证python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py -q",
    );
    expect(checklist).toHaveTextContent("登记backend/app/core_finance/formal_financial_indicators.py");
    expect(checklist).toHaveTextContent(
      "验证python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py -q",
    );
    expect(checklist).toHaveTextContent("执行状态待补齐正式样本");
    expect(checklist).toHaveTextContent("回读动作补齐样本并登记后刷新页面或重新查询正式契约接口");

    const strip = screen.getByTestId("ledger-pnl-functional-audit-strip");
    expect(strip).toHaveTextContent("正式契约缺口");
    expect(strip).toHaveTextContent("202605 正式契约样本缺失");
    expect(strip).not.toHaveTextContent("无正式契约明细");
    expect(strip).not.toHaveTextContent("正式待接入 0 / QDB候选 0 / 需对账 0");
  });

  it("blocks formal registration when the local registration package is incomplete", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => ({
      result_meta: {
        ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
        basis: "ledger" as const,
        quality_flag: "warning" as const,
        as_of_date: "2026-05-31",
        date_basis: "report_month_end",
        evidence_rows: 0,
        formal_use_allowed: false,
        source_version: "sv_formal_financial_indicators_contract_unavailable",
      },
      result: buildBlockedRegistrationPackageContractPayload(),
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.summary"),
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("0.00"),
            ledger_monthly_pnl_all: money("0.00"),
            ledger_total_assets: money("0.00"),
            ledger_total_liabilities: money("0.00"),
            ledger_net_assets: money("0.00"),
            by_currency: [],
            by_account: [],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.data"),
          result: {
            report_date: "2026-05-31",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: 0,
            },
            items: [],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators,
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202605");
    });

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    const checklist = within(panel).getByTestId("ledger-pnl-formal-indicator-source-contract-material-checklist");

    expect(checklist).toHaveTextContent("补证材料待补");
    expect(checklist).toHaveTextContent("登记包守卫blocked");
    expect(checklist).toHaveTextContent("缺失字段release_gate");
    expect(checklist).toHaveTextContent("执行状态待补齐登记包");
    expect(checklist).toHaveTextContent("回读动作补齐登记包后再登记正式契约");
    expect(checklist).not.toHaveTextContent("执行状态待登记正式契约");
    expect(checklist).not.toHaveTextContent("回读动作登记后刷新页面或重新查询正式契约接口");
  });

  it("states the first-screen business conclusion when ledger evidence exists but the formal contract is missing", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildLedgerMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.summary"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 665,
            quality_flag: "ok" as const,
            next_drill: [
              {
                label: "补科目汇总或确认科目范围",
                detail: "旧候选补证动作不应覆盖已闭合候选链路或正式契约补证路径。",
              },
            ],
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("123456789.00"),
            ledger_monthly_pnl_all: money("123456789.00"),
            ledger_total_assets: money("814405000000.00"),
            ledger_total_liabilities: money("700000000000.00"),
            ledger_net_assets: money("114405000000.00"),
            by_currency: [{ currency: "CNY", total_pnl: money("123456789.00") }],
            by_account: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                total_pnl: money("123456789.00"),
                count: 665,
              },
            ],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.data"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 7751,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("123456789.00"),
              total_pnl: money("123456789.00"),
              count: 7751,
            },
            items: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("123456789.00"),
                monthly_pnl: money("123456789.00"),
                daily_avg_balance: money("0.00"),
                days_in_period: 31,
              },
            ],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: ["202605"] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
          result: {
            report_month: "202605",
            sheets: [],
          },
        })),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            quality_flag: "warning" as const,
            as_of_date: "2026-05-31",
            date_basis: "report_month_end",
            evidence_rows: 0,
            formal_use_allowed: false,
            source_version: "sv_formal_financial_indicators_contract_unavailable",
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，正式指标不可判定");
      expect(strip).toHaveTextContent("正式财务指标契约缺失");
      expect(strip).toHaveTextContent("补齐 202605 正式财务指标 Excel 冻结样本");
      expect(strip).toHaveTextContent("分析证据行1");
      expect(strip).toHaveTextContent("候选分析状态可用 · 候选口径");
      expect(strip).toHaveTextContent("候选分析证据ledger_pnl.analysis · evidence 1");
      expect(strip).toHaveTextContent("来源状态来源正常");
      expect(strip).toHaveTextContent("候选补证入口 候选分析证据完整");
    });

    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("候选分析状态可用 · 候选口径");
    expect(decisionPath).toHaveTextContent("候选补证路径候选分析证据完整");
    expect(decisionPath).toHaveTextContent("分析证据处理路径使用后端分析 DTO");
    expect(decisionPath).toHaveTextContent("来源处理路径来源状态正常");
    expect(decisionPath).toHaveTextContent("正式补证路径补齐 202605 正式财务指标 Excel 冻结样本");
    expect(decisionPath).toHaveTextContent(
      "正式补证结论202605 正式样本缺失；先补齐样本，再登记 source contract、回读正式契约并核对 QDB 候选值",
    );
    expect(decisionPath).not.toHaveTextContent("正式补证路径补科目汇总或确认科目范围");
    expect(
      within(decisionPath).queryByRole("button", { name: /候选补证路径/ }),
    ).not.toBeInTheDocument();
    expect(within(strip).queryByRole("button", { name: /定位证据/ })).not.toBeInTheDocument();

    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollTargets: HTMLElement[] = [];
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement) {
      scrollTargets.push(this);
    });

    try {
      const formalChecklist = await screen.findByTestId(
        "ledger-pnl-formal-indicator-source-contract-material-checklist",
      );
      const drillButton = within(strip).getByRole("button", {
        name: "下一步补证 补齐 202605 正式财务指标 Excel 冻结样本",
      });

      await userEvent.click(drillButton);

      expect(scrollTargets).toEqual([formalChecklist]);
      expect(formalChecklist).toHaveFocus();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("surfaces a missing monthly analysis workbook in the first-screen verdict", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildLedgerMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.summary"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 665,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("123456789.00"),
            ledger_monthly_pnl_all: money("123456789.00"),
            ledger_total_assets: money("0.00"),
            ledger_total_liabilities: money("0.00"),
            ledger_net_assets: money("0.00"),
            by_currency: [{ currency: "CNY", total_pnl: money("123456789.00") }],
            by_account: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                total_pnl: money("123456789.00"),
                count: 665,
              },
            ],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.data"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 7751,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("123456789.00"),
              total_pnl: money("123456789.00"),
              count: 7751,
            },
            items: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("123456789.00"),
                monthly_pnl: money("123456789.00"),
                daily_avg_balance: money("0.00"),
                days_in_period: 31,
              },
            ],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            quality_flag: "warning" as const,
            as_of_date: "2026-05-31",
            date_basis: "report_month_end",
            evidence_rows: 0,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，月度工作簿缺失");
      expect(strip).toHaveTextContent("202605 月度分析工作簿未匹配");
      expect(strip).toHaveTextContent("月度工作簿202605 无匹配");
      expect(strip).not.toHaveTextContent("候选分析可用，正式指标不可判定");
    });

    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("月度分析工作簿202605 无匹配");
    expect(decisionPath).toHaveTextContent("月度补证路径补齐 202605 QDB 月度分析工作簿");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-missing-month")).toHaveTextContent(
      "当前报告日没有对应月度分析工作簿",
    );
  });

  function renderMonthlyWorkbookAuditCase(options: {
    workbookReportMonth?: string;
    workbookMeta?: ResultMeta | null;
    workbookSheets?: QdbGlMonthlyAnalysisWorkbookPayload["sheets"];
    formalContract?: LedgerPnlFormalFinancialIndicatorContractPayload;
  } = {}) {
    const base = createApiClient({ mode: "mock" });
    const workbookMeta = Object.prototype.hasOwnProperty.call(options, "workbookMeta")
      ? options.workbookMeta
      : buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook");
    const formalContract = options.formalContract ?? buildMissingFormalIndicatorContractPayload();

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildLedgerMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.summary"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 665,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("123456789.00"),
            ledger_monthly_pnl_all: money("123456789.00"),
            ledger_total_assets: money("814405000000.00"),
            ledger_total_liabilities: money("700000000000.00"),
            ledger_net_assets: money("114405000000.00"),
            by_currency: [{ currency: "CNY", total_pnl: money("123456789.00") }],
            by_account: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                total_pnl: money("123456789.00"),
                count: 665,
              },
            ],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.data"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 7751,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("123456789.00"),
              total_pnl: money("123456789.00"),
              count: 7751,
            },
            items: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("123456789.00"),
                monthly_pnl: money("123456789.00"),
                daily_avg_balance: money("0.00"),
                days_in_period: 31,
              },
            ],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: ["202605"] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(async () => ({
          result_meta: workbookMeta,
          result: {
            report_month: options.workbookReportMonth ?? "202605",
            sheets: options.workbookSheets ?? [],
          },
        }) as unknown as ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload>),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: formalContract.formal_use_allowed,
          },
          result: formalContract,
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );
  }

  it("blocks monthly analysis use when the workbook resolves to a different report month", async () => {
    renderMonthlyWorkbookAuditCase({ workbookReportMonth: "202604" });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，月度工作簿不可信");
      expect(strip).toHaveTextContent("月度工作簿请求 202605，返回 202604");
      expect(strip).toHaveTextContent("月度工作簿202605/202604 不一致");
    });

    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("月度补证路径重新读取 202605 月度分析工作簿");
  });

  it("hides monthly analysis workbook sheets when the workbook report month is untrusted", async () => {
    renderMonthlyWorkbookAuditCase({
      workbookReportMonth: "202604",
      workbookSheets: [
        {
          key: "overview",
          title: "经营概览",
          columns: ["指标", "当前值"],
          rows: [{ 指标: "错月总资产", 当前值: "9999.99" }],
        },
        {
          key: "summary_3d",
          title: "3位科目总览",
          columns: ["科目", "当前值"],
          rows: [{ 科目: "错月科目", 当前值: "8888.88" }],
        },
      ],
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，月度工作簿不可信");
    });

    expect(screen.getByTestId("ledger-pnl-monthly-analysis-trust-warning")).toHaveTextContent(
      "月度工作簿请求 202605，返回 202604",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-overview")).not.toHaveTextContent("错月总资产");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-summary-3d")).not.toHaveTextContent("错月科目");
  });

  it("blocks monthly analysis use when workbook source evidence metadata is incomplete", async () => {
    renderMonthlyWorkbookAuditCase({
      workbookMeta: {
        ...buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
        rule_version: "",
        tables_used: [],
      },
      workbookSheets: [
        {
          key: "overview",
          title: "经营概览",
          columns: ["指标", "当前值"],
          rows: [{ 指标: "缺证总资产", 当前值: "7777.77" }],
        },
      ],
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，月度工作簿不可信");
      expect(strip).toHaveTextContent("月度工作簿 rule_version 缺失；月度工作簿 tables_used 缺失");
      expect(strip).toHaveTextContent("月度工作簿月度工作簿来源证据不完整");
    });

    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("月度补证路径补齐月度工作簿来源版本、规则版本、缓存版本和表清单");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-trust-warning")).toHaveTextContent(
      "月度工作簿 rule_version 缺失；月度工作簿 tables_used 缺失",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-overview")).not.toHaveTextContent("缺证总资产");
  });

  it("blocks monthly analysis use when workbook result metadata is missing", async () => {
    renderMonthlyWorkbookAuditCase({
      workbookMeta: null,
      workbookSheets: [
        {
          key: "overview",
          title: "经营概览",
          columns: ["指标", "当前值"],
          rows: [{ 指标: "缺元数据总资产", 当前值: "6666.66" }],
        },
      ],
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，月度工作簿不可信");
      expect(strip).toHaveTextContent("月度工作簿 result_meta 缺失");
      expect(strip).toHaveTextContent("月度工作簿月度工作簿 result_meta 缺失");
    });

    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("月度补证路径补齐月度工作簿来源版本、规则版本、缓存版本和表清单");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-trust-warning")).toHaveTextContent(
      "月度工作簿 result_meta 缺失",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-overview")).not.toHaveTextContent("缺元数据总资产");
  });

  it("renders monthly analysis workbook sheets when the workbook provenance is trusted", async () => {
    renderMonthlyWorkbookAuditCase({
      workbookSheets: [
        {
          key: "overview",
          title: "经营概览",
          columns: ["指标", "当前值"],
          rows: [{ 指标: "可信总资产", 当前值: "5555.55" }],
        },
        {
          key: "summary_3d",
          title: "3位科目总览",
          columns: ["科目", "当前值"],
          rows: [{ 科目: "可信科目", 当前值: "4444.44" }],
        },
      ],
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).not.toHaveTextContent("月度分析工作簿不可信");
    });

    await waitFor(() => {
      expect(screen.getByTestId("ledger-pnl-monthly-analysis-overview")).toHaveTextContent("可信总资产");
      expect(screen.getByTestId("ledger-pnl-monthly-analysis-summary-3d")).toHaveTextContent("可信科目");
    });
    expect(screen.queryByTestId("ledger-pnl-monthly-analysis-trust-warning")).not.toBeInTheDocument();
  });

  it("does not let workbook trust warnings override released formal indicators", async () => {
    renderMonthlyWorkbookAuditCase({
      workbookReportMonth: "202604",
      formalContract: {
        ...buildReleasedFormalIndicatorContractPayload(),
        report_month: "202605",
        report_date: "2026-05-31",
      },
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("正式财务指标可用");
      expect(strip).toHaveTextContent("月度工作簿202605/202604 不一致");
      expect(strip).not.toHaveTextContent("月度分析工作簿不可信");
      expect(strip).not.toHaveTextContent("本次不能复核 QDB 月度分析或正式指标落地状态");
    });
  });

  it("does not treat monthly analysis dates read failures as missing workbooks", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildLedgerMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.summary"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 665,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("123456789.00"),
            ledger_monthly_pnl_all: money("123456789.00"),
            ledger_total_assets: money("0.00"),
            ledger_total_liabilities: money("0.00"),
            ledger_net_assets: money("0.00"),
            by_currency: [{ currency: "CNY", total_pnl: money("123456789.00") }],
            by_account: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                total_pnl: money("123456789.00"),
                count: 665,
              },
            ],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.data"),
            requested_report_date: "2026-05-31",
            resolved_report_date: "2026-05-31",
            as_of_date: "2026-05-31",
            evidence_rows: 7751,
            quality_flag: "ok" as const,
          },
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("123456789.00"),
              total_pnl: money("123456789.00"),
              count: 7751,
            },
            items: [
              {
                account_code: "50101000001",
                account_name: "短期信用贷款利息收入",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("123456789.00"),
                monthly_pnl: money("123456789.00"),
                daily_avg_balance: money("0.00"),
                days_in_period: 31,
              },
            ],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => {
          throw new Error("monthly analysis dates unavailable");
        }),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            quality_flag: "warning" as const,
            as_of_date: "2026-05-31",
            date_basis: "report_month_end",
            evidence_rows: 0,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("月度工作簿月度月份读取失败");
      expect(strip).toHaveTextContent("月度分析工作簿月度月份读取失败");
      expect(strip).toHaveTextContent("月度补证路径恢复月度分析月份读取");
      expect(strip).not.toHaveTextContent("月度工作簿202605 无匹配");
      expect(strip).not.toHaveTextContent("月度补证路径补齐 202605 QDB 月度分析工作簿");
      expect(strip).not.toHaveTextContent("候选分析可用，月度工作簿缺失");
    });

    expect(screen.getByTestId("ledger-pnl-monthly-analysis-month")).toHaveTextContent("月份读取失败");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-error")).toHaveTextContent("月度分析月份读取失败");
    expect(screen.queryByTestId("ledger-pnl-monthly-analysis-missing-month")).not.toBeInTheDocument();
  });

  it("keeps the first-screen contract gap as read failure when formal contract lookup fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => {
      throw new Error("Request failed: /api/ledger-pnl/formal-financial-indicators?report_month=202603 (502)");
    });

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.dates"),
        result: { dates: ["2026-03-31"] },
      })),
      getLedgerPnlSummary: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.summary"),
        result: {
          report_date: "2026-03-31",
          source_version: "sv_ledger_test",
          ledger_monthly_pnl_core: money("1.00"),
          ledger_monthly_pnl_all: money("1.00"),
          ledger_total_assets: money("0.00"),
          ledger_total_liabilities: money("0.00"),
          ledger_net_assets: money("0.00"),
          by_currency: [],
          by_account: [
            {
              account_code: "50101000001",
              account_name: "短期信用贷款利息收入",
              total_pnl: money("1.00"),
              count: 1,
            },
          ],
        },
      })),
      getLedgerPnlData: vi.fn(async () => ({
        result_meta: buildMeta("ledger_pnl.data"),
        result: {
          report_date: "2026-03-31",
          summary: {
            total_pnl_cnx: money("0.00"),
            total_pnl_cny: money("1.00"),
            total_pnl: money("1.00"),
            count: 1,
          },
          items: [],
        },
      })),
      getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
      getLedgerPnlFormalFinancialIndicators,
    });

    await waitFor(() => {
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202603");
    });

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析可用，正式契约读取失败");
      expect(strip).toHaveTextContent("正式契约缺口");
      expect(strip).toHaveTextContent("正式契约读取失败");
      expect(strip).toHaveTextContent("候选分析状态可用 · 候选口径");
    });
    const decisionPath = within(strip).getByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("正式状态正式契约读取失败");
    expect(decisionPath).not.toHaveTextContent("正式状态正式值不可用，仅作候选核对");
    expect(decisionPath).toHaveTextContent("正式补证路径恢复读取后重新查询正式契约");
    expect(decisionPath).toHaveTextContent("正式补证结论正式契约读取失败；先恢复读取，再复核正式契约");
    expect(decisionPath).not.toHaveTextContent("正式补证路径无正式契约补证路径");
    expect(strip).not.toHaveTextContent("无正式契约明细");
    expect(strip).not.toHaveTextContent("正式待接入 0 / QDB候选 0 / 需对账 0");
  });

  it("prioritizes a report date missing from discovered dates before missing PnL evidence", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      source_version: "sv_ledger_manual_date",
      evidence_rows: 0,
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const dataMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      source_version: "sv_ledger_manual_date",
      evidence_rows: 1,
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: {
            ...buildLedgerMeta("ledger_pnl.dates"),
            requested_report_date: undefined,
            resolved_report_date: undefined,
            evidence_rows: 1,
          },
          result: { dates: ["2026-04-30"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: summaryMeta,
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_manual_date",
            ledger_monthly_pnl_core: money("0.00"),
            ledger_monthly_pnl_all: money("0.00"),
            ledger_total_assets: money("1000.00"),
            ledger_total_liabilities: money("500.00"),
            ledger_net_assets: money("500.00"),
            by_currency: [],
            by_account: [],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: dataMeta,
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_manual_date",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: 1,
            },
            items: [
              {
                account_code: "10101000001",
                account_name: "现金",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("1000.00"),
                monthly_pnl: money("0.00"),
                daily_avg_balance: money("1000.00"),
                days_in_period: 31,
              },
            ],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            quality_flag: "warning" as const,
            evidence_rows: 0,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("报告日未列入可选清单");
      expect(strip).toHaveTextContent("请核对日期清单和源文件登记");
      expect(strip).toHaveTextContent("候选分析状态可用 · 候选口径");
    });
  });

  it("does not mark the formal financial indicator contract as read before a report month exists", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlFormalFinancialIndicators = vi.fn();

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: [] },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators,
      },
      "/ledger-pnl",
    );

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    expect(panel).toHaveTextContent("等待正式财务指标契约");
    expect(panel).not.toHaveTextContent("正式财务指标契约已读取");
    const decisionPath = await screen.findByTestId("ledger-pnl-decision-path");
    expect(decisionPath).toHaveTextContent("正式状态等待报告月份");
    expect(decisionPath).toHaveTextContent("正式补证路径先选择报告日生成 report_month");
    expect(decisionPath).not.toHaveTextContent("正式状态正式值不可用，仅作候选核对");
    expect(decisionPath).not.toHaveTextContent("正式补证路径重新读取正式契约并复核 formal_use_allowed");
    expect(getLedgerPnlFormalFinancialIndicators).not.toHaveBeenCalled();

    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollTargets: HTMLElement[] = [];
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement) {
      scrollTargets.push(this);
    });

    try {
      const reportDateSelect = screen.getByTestId("ledger-pnl-report-date-control");
      const formalPathButton = within(decisionPath).getByRole("button", {
        name: "正式补证路径 先选择报告日生成 report_month",
      });

      await userEvent.click(formalPathButton);

      expect(scrollTargets).toEqual([reportDateSelect]);
      expect(reportDateSelect).toHaveFocus();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("shows dates-level remediation drills when no ledger report dates are available", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: {
            ...buildMeta("ledger_pnl.dates"),
            quality_flag: "warning" as const,
            evidence_rows: 0,
            next_drill: [
              {
                label: "核对总账源文件",
                detail: "检查 product_category_source_dir 是否包含对应 YYYYMM 的总账对账工作簿。",
              },
            ],
          },
          result: { dates: [] },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(),
      },
      "/ledger-pnl",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("没有可选报告日");
      expect(strip).toHaveTextContent("下一步补证");
      expect(strip).toHaveTextContent("核对总账源文件");
      expect(strip).toHaveTextContent("product_category_source_dir");
    });
  });

  it("keeps missing ledger money values visibly unavailable instead of rendering zero", async () => {
    const base = createApiClient({ mode: "mock" });
    const missingMoney = null as unknown as LedgerMoneyValue;
    const undefinedMoney = undefined as unknown as LedgerMoneyValue;
    const blankMoney = { yuan: "", yi: "" } as LedgerMoneyValue;
    const invalidMoney = { yuan: "not-a-number", yi: "" } as LedgerMoneyValue;

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.summary"),
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: missingMoney,
            ledger_monthly_pnl_all: undefinedMoney,
            ledger_total_assets: blankMoney,
            ledger_total_liabilities: invalidMoney,
            ledger_net_assets: money("500000000.00"),
            by_currency: [{ currency: "CNX", total_pnl: missingMoney }],
            by_account: [
              {
                account_code: "514",
                account_name: "interest income",
                total_pnl: undefinedMoney,
                count: 1,
              },
            ],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.data"),
          result: {
            report_date: "2026-05-31",
            summary: {
              total_pnl_cnx: missingMoney,
              total_pnl_cny: undefinedMoney,
              total_pnl: blankMoney,
              count: 1,
            },
            items: [
              {
                account_code: "514",
                account_name: "interest income",
                currency: "CNX",
                beginning_balance: missingMoney,
                ending_balance: blankMoney,
                monthly_pnl: money("100000000.00"),
                daily_avg_balance: invalidMoney,
                days_in_period: 31,
              },
            ],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const cards = await screen.findByTestId("ledger-pnl-summary-cards");
    await waitFor(() => {
      expect(cards).toHaveTextContent("5.00 亿元");
    });
    expect(within(cards).getAllByText("—")).toHaveLength(4);
    expect(within(cards).queryByText("0.00 亿元")).not.toBeInTheDocument();

    expect(screen.queryByTestId("ledger-pnl-explainability-panel")).not.toBeInTheDocument();
    expect(await screen.findByTestId("ledger-pnl-analysis-workbench")).toHaveAttribute("data-state", "ready");
    expect(screen.getByTestId("ledger-pnl-functional-audit-strip")).toHaveTextContent(
      "候选分析状态可用 · 候选口径",
    );

    const detailTable = await screen.findByTestId("ledger-pnl-detail-table");
    expect(within(detailTable).getAllByText("—")).toHaveLength(3);
    expect(detailTable).toHaveTextContent("1.00 亿元");
  });

  it("surfaces empty ledger summary and detail tables instead of leaving blank bodies", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(
      {
        ...base,
        mode: "real",
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.summary"),
          result: {
            data_status: "no_data" as const,
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("0.00"),
            ledger_monthly_pnl_all: money("0.00"),
            ledger_total_assets: money("0.00"),
            ledger_total_liabilities: money("0.00"),
            ledger_net_assets: money("0.00"),
            by_currency: [],
            by_account: [],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.data"),
          result: {
            data_status: "no_data" as const,
            report_date: "2026-05-31",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: 0,
            },
            items: [],
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(screen.getByTestId("ledger-pnl-currency-summary-table")).toHaveTextContent("暂无币种汇总数据");
    });
    const summaryCards = screen.getByTestId("ledger-pnl-summary-cards");
    expect(within(summaryCards).getAllByText("—")).toHaveLength(5);
    expect(summaryCards).not.toHaveTextContent("0.00 亿元");
    expect(screen.getByText("真实 API 只读链路 · 非正式口径")).toBeInTheDocument();

    expect(screen.getByTestId("ledger-pnl-currency-summary-table")).toHaveTextContent("暂无币种汇总数据");
    expect(screen.getByTestId("ledger-pnl-account-summary-table")).toHaveTextContent("暂无科目汇总数据");
    expect(screen.getByTestId("ledger-pnl-detail-table")).toHaveTextContent("暂无科目明细数据");
  });

  it("surfaces ledger summary and detail loading failures in the table bodies", async () => {
    const base = createApiClient({ mode: "mock" });

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => {
          throw new Error("summary unavailable");
        }),
        getLedgerPnlData: vi.fn(async () => {
          throw new Error("detail unavailable");
        }),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("候选分析状态可用 · 候选口径");
      expect(strip).toHaveTextContent("候选分析证据ledger_pnl.analysis · evidence 1");
    });
    expect(await screen.findByText("币种汇总读取失败")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-account-summary-table")).toHaveTextContent("科目汇总读取失败");
    expect(screen.getByTestId("ledger-pnl-detail-table")).toHaveTextContent("科目明细读取失败");
  });

  it("opens a contributor drill-through and filters the lower detail table only after locate", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const accountDetail = await base.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = scrollIntoView;

    try {
      renderLedgerPnlPage(
        {
          ...base,
          getLedgerPnlDates: vi.fn(async () => ({
            result_meta: buildMeta("ledger_pnl.dates"),
            result: { dates: ["2026-03-31"] },
          })),
          getLedgerPnlData: vi.fn(async () => ({
            result_meta: buildLedgerMeta("ledger_pnl.data"),
            result: {
              report_date: "2026-03-31",
              items: [
                {
                  account_code: "514100",
                  account_name: "利息收入",
                  currency: "CNX",
                  beginning_balance: money("100"),
                  ending_balance: money("110"),
                  monthly_pnl: money("10"),
                  daily_avg_balance: money("0"),
                  days_in_period: 31,
                },
                {
                  account_code: "519900",
                  account_name: "其他损益",
                  currency: "CNX",
                  beginning_balance: money("200"),
                  ending_balance: money("220"),
                  monthly_pnl: money("20"),
                  daily_avg_balance: money("0"),
                  days_in_period: 31,
                },
              ],
              summary: {
                total_pnl_cnx: money("30"),
                total_pnl_cny: money("0"),
                total_pnl: money("30"),
                count: 2,
              },
            },
          })),
          getLedgerPnlAccountDetail: vi.fn(async () => ({
            ...accountDetail,
            result: {
              ...accountDetail.result,
              report_date: "2026-03-31",
              currency_basis: "CNX" as const,
              account: { account_code: "514100", account_name: "利息收入" },
              canonical_evidence_rows: accountDetail.result.canonical_evidence_rows.map((row) => ({
                ...row,
                account_code: "514100",
                account_name: "利息收入",
              })),
            },
          })),
        },
        "/ledger-pnl?report_date=2026-03-31&currency=CNX",
      );

      const detailTable = await screen.findByTestId("ledger-pnl-detail-table");
      await waitFor(() => {
        expect(detailTable).toHaveTextContent("514100");
        expect(detailTable).toHaveTextContent("519900");
      });

      await user.click(await screen.findByRole("button", {
        name: "查看科目穿透 514100 利息收入",
      }));
      const drawer = await screen.findByTestId("ledger-pnl-account-detail-drawer");
      expect(drawer).toHaveTextContent("514100 利息收入");
      expect(detailTable).toHaveTextContent("519900");

      await user.click(within(drawer).getByRole("button", { name: "定位下方科目明细" }));

      const filter = await screen.findByTestId("ledger-pnl-detail-account-filter");
      expect(filter).toHaveTextContent("当前仅显示 514100 利息收入");
      expect(filter).toHaveTextContent(
        "月日均不参与本次账户损益穿透；0 可能来自日均源缺行，不能解释为已观测真实零",
      );
      expect(detailTable).toHaveTextContent("514100");
      expect(detailTable).not.toHaveTextContent("519900");
      expect(scrollIntoView).toHaveBeenCalled();
      expect(screen.getByTestId("ledger-pnl-detail-table-anchor")).toHaveFocus();

      await user.click(within(filter).getByRole("button", { name: "清除科目筛选" }));
      expect(screen.queryByTestId("ledger-pnl-detail-account-filter")).not.toBeInTheDocument();
      expect(detailTable).toHaveTextContent("519900");
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("paginates very large ledger tables and keeps every row reachable", async () => {
    const base = createApiClient({ mode: "mock" });
    const byAccount = Array.from({ length: 201 }, (_, index) => {
      const rowNumber = index + 1;
      return {
        account_code: `514${String(rowNumber).padStart(3, "0")}`,
        account_name: `account-row-${rowNumber}`,
        total_pnl: money(String(rowNumber * 100_000_000)),
        count: 1,
      };
    });
    const detailItems = Array.from({ length: 201 }, (_, index) => {
      const rowNumber = index + 1;
      return {
        account_code: `612${String(rowNumber).padStart(3, "0")}`,
        account_name: `detail-row-${rowNumber}`,
        currency: "CNX",
        beginning_balance: money("100000000.00"),
        ending_balance: money("200000000.00"),
        monthly_pnl: money(rowNumber === 201 ? "90000000000.00" : "300000000.00"),
        daily_avg_balance: money("400000000.00"),
        days_in_period: 31,
      };
    });

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.summary"),
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_test",
            ledger_monthly_pnl_core: money("0.00"),
            ledger_monthly_pnl_all: money("0.00"),
            ledger_total_assets: money("0.00"),
            ledger_total_liabilities: money("0.00"),
            ledger_net_assets: money("0.00"),
            by_currency: [{ currency: "CNX", total_pnl: money("0.00") }],
            by_account: byAccount,
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.data"),
          result: {
            report_date: "2026-05-31",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: detailItems.length,
            },
            items: detailItems,
          },
        })),
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const accountTable = await screen.findByTestId("ledger-pnl-account-summary-table");
    await waitFor(() => {
      expect(accountTable).toHaveTextContent("account-row-201");
    });
    expect(
      within(accountTable).getByTestId("ledger-pnl-account-summary-table-range"),
    ).toHaveTextContent("第 1-25 条 / 共 201 条");
    expect(within(accountTable).queryByText(/^account-row-1$/)).not.toBeInTheDocument();

    const detailTable = screen.getByTestId("ledger-pnl-detail-table");
    expect(detailTable).toHaveTextContent("detail-row-201");
    expect(within(detailTable).getByTestId("ledger-pnl-detail-table-range")).toHaveTextContent(
      "第 1-25 条 / 共 201 条",
    );
    expect(within(detailTable).queryByText(/^detail-row-200$/)).not.toBeInTheDocument();

    // 被分页隐去的行仍然可达：这是从"只渲染前 200 条"改为分页后的关键保证。
    await userEvent.click(
      within(accountTable).getByTestId("ledger-pnl-account-summary-table-next"),
    );
    expect(
      within(accountTable).getByTestId("ledger-pnl-account-summary-table-range"),
    ).toHaveTextContent("第 26-50 条 / 共 201 条");
    expect(within(accountTable).getByText("account-row-176")).toBeInTheDocument();
  });

  it("uses the report_date query for ledger reads while the date list is still loading", async () => {
    const base = createApiClient({ mode: "mock" });
    let resolveDates: ((value: ApiEnvelope<LedgerPnlDatesPayload>) => void) | undefined;
    const datesRequest = new Promise<ApiEnvelope<LedgerPnlDatesPayload>>((resolve) => {
      resolveDates = resolve;
    });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("100000000.00"),
        ledger_monthly_pnl_all: money("0.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNX", total_pnl: money("100000000.00") }],
        by_account: [],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("100000000.00"),
          total_pnl_cny: money("0.00"),
          total_pnl: money("100000000.00"),
          count: 0,
        },
        items: [],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(() => datesRequest),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", "CNX");
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", "CNX");
    });
    expect(screen.getByTestId("ledger-pnl-currency-summary-table")).not.toHaveTextContent(
      "暂无币种汇总数据",
    );
    resolveDates?.({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: { dates: ["2026-05-31"] },
    });
  });

  it("keeps a manually selected report date instead of reverting to the initial query date", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: reportDate,
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("100000000.00"),
        ledger_monthly_pnl_all: money("0.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNX", total_pnl: money("100000000.00") }],
        by_account: [],
      },
    }));
    const getLedgerPnlData = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: reportDate,
        summary: {
          total_pnl_cnx: money("100000000.00"),
          total_pnl_cny: money("0.00"),
          total_pnl: money("100000000.00"),
          count: 0,
        },
        items: [],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31", "2026-04-30"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", "CNX");
    });
    await screen.findByRole("option", { name: "2026-04-30" });
    await user.selectOptions(screen.getByTestId("ledger-pnl-report-date-control"), "2026-04-30");

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-04-30", "CNX");
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-04-30", "CNX");
    });
    expect(screen.getByTestId("ledger-pnl-report-date-control")).toHaveValue("2026-04-30");
  });

  it("renders all ledger money fields in yi units", async () => {
    const base = createApiClient({ mode: "mock" });
    const datesPayload: LedgerPnlDatesPayload = {
      dates: ["2026-03-31"],
    };
    const summaryPayload: LedgerPnlSummaryPayload = {
      report_date: "2026-03-31",
      source_version: "sv_ledger_test",
      ledger_monthly_pnl_core: money("100000000.00", ""),
      ledger_monthly_pnl_all: money("-200000000.00"),
      ledger_total_assets: money("300000000.00"),
      ledger_total_liabilities: money("-400000000.00"),
      ledger_net_assets: money("500000000.00"),
      by_currency: [
        {
          currency: "CNY",
          total_pnl: money("600000000.00"),
        },
      ],
      by_account: [
        {
          account_code: "514",
          account_name: "interest income",
          total_pnl: money("700000000.00"),
          count: 1,
        },
      ],
    };
    const dataPayload: LedgerPnlDataPayload = {
      report_date: "2026-03-31",
      summary: {
        total_pnl_cnx: money("0.00"),
        total_pnl_cny: money("0.00"),
        total_pnl: money("0.00"),
        count: 1,
      },
      items: [
        {
          account_code: "514",
          account_name: "interest income",
          currency: "CNY",
          beginning_balance: money("800000000.00"),
          ending_balance: money("900000000.00"),
          monthly_pnl: money("1100000000.00"),
          daily_avg_balance: money("1200000000.00"),
          days_in_period: 31,
        },
      ],
    };
    const monthlyAnalysisDatesPayload: QdbGlMonthlyAnalysisDatesPayload = {
      report_months: ["202603"],
    };
    const monthlyAnalysisWorkbookPayload: QdbGlMonthlyAnalysisWorkbookPayload = {
      report_month: "202603",
      sheets: [
        {
          key: "overview",
          title: "经营概览",
          columns: ["指标", "值"],
          rows: [
            { 指标: "总资产(亿)", 值: 1200 },
            { 指标: "存贷比%", 值: 79.69 },
          ],
        },
        {
          key: "financial_indicator_status",
          title: "财务指标落地状态",
          columns: ["指标", "当前值", "单位", "口径状态", "口径来源"],
          rows: [
            {
              指标: "贷款总额（QDB源）",
              当前值: 4189.47,
              单位: "亿元",
              口径状态: "QDB源可复算",
              口径来源: "QDB源分析：总账对账+日均可复算",
            },
            {
              指标: "集团营业收入",
              当前值: null,
              单位: "待确认",
              口径状态: "正式口径待接入",
              口径来源: "formal_pending: 正式财务指标依赖合并范围、拨备/核销/收回、子公司抵消或管理层调整来源，当前未接入",
            },
          ],
        },
        {
          key: "summary_3d",
          title: "3位科目总览",
          columns: ["科目代码", "名称", "期末余额", "月日均", "年日均", "偏离额", "偏离%", "趋势额"],
          rows: [{ 科目代码: "123", 名称: "公司贷款", 期末余额: 3044.84, 月日均: 3009.19, 年日均: 2969.67, 偏离额: 35.65, "偏离%": 1.18, 趋势额: 39.52 }],
        },
        {
          key: "top_11d",
          title: "11位偏离TOP",
          columns: ["科目代码", "科目名称", "偏离额"],
          rows: [{ 科目代码: "14001000001", 科目名称: "买入返售", 偏离额: 230 }],
        },
        {
          key: "alerts",
          title: "异动预警",
          columns: ["科目代码", "科目名称", "预警级别"],
          rows: [{ 科目代码: "14001000001", 科目名称: "买入返售", 预警级别: "alert" }],
        },
        {
          key: "segment_base_scale",
          title: "分部基础规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "微贷中心",
              时点余额: null,
              年日均: null,
              月日均: null,
              口径来源: "source_missing: 标准日均源不含80297微贷金融支行专段",
            },
          ],
        },
        {
          key: "segment_scale_compare",
          title: "分部规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "公司贷款合计",
              口径: "时点环比",
              本期: 3458.61,
              对比期: 3339.26,
              增减额: 119.35,
              "增减幅%": 3.57,
              口径来源: "月度分析-分部情况：总账对账+日均同源历史月重建",
            },
            {
              指标: "微贷中心",
              口径: "月日均环比",
              本期: null,
              对比期: null,
              增减额: null,
              "增减幅%": null,
              口径来源: "source_missing: 标准日均源不含80297微贷金融支行专段",
            },
          ],
        },
        {
          key: "financial_market_scale",
          title: "金融市场规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "生息债券投资",
              时点余额: 2541.38,
              年日均: 2458.66,
              月日均: 2522.26,
              口径来源: "金融市场规模：总账对账+日均同源科目重建",
            },
          ],
        },
        {
          key: "foreign_currency",
          title: "外币分析",
          columns: ["科目代码", "科目名称", "期末余额_综本", "期末余额_人民币", "外币部分", "外币占比%"],
          rows: [
            {
              科目代码: "14201000001",
              科目名称: "AC债券投资",
              期末余额_综本: 150,
              期末余额_人民币: 100,
              外币部分: 50,
              "外币占比%": 33.33,
            },
          ],
        },
        {
          key: "company_scale",
          title: "公司规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "公司存款-活期",
              时点余额: 923.15,
              年日均: 935.21,
              月日均: 920.29,
              口径来源: "公司规模：总账对账+日均同源科目重建",
            },
          ],
        },
        {
          key: "company_scale_compare",
          title: "公司规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "公司贷款-票据",
              口径: "月日均环比",
              本期: 230.53,
              对比期: 228.03,
              增减额: 2.5,
              "增减幅%": 1.1,
              口径来源: "月度分析-公司板块：总账对账+日均同源历史月重建",
            },
          ],
        },
        {
          key: "retail_scale",
          title: "零售规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "零售存款-活期",
              时点余额: 327.8,
              年日均: 318.83,
              月日均: 315.56,
              口径来源: "零售规模：总账对账+日均同源科目重建",
            },
          ],
        },
        {
          key: "retail_scale_compare",
          title: "零售规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "零售存款合计",
              口径: "时点环比",
              本期: 2604.03,
              对比期: 2566.14,
              增减额: 37.88,
              "增减幅%": 1.48,
              口径来源: "月度分析-零售板块：总账对账+日均同源历史月重建",
            },
            {
              指标: "零售贷款-分支行个贷",
              口径: "月日均环比",
              本期: null,
              对比期: null,
              增减额: null,
              "增减幅%": null,
              口径来源: "source_missing: 零售分支行个贷依赖80297微贷金融支行专段",
            },
          ],
        },
        {
          key: "financial_market_scale_compare",
          title: "金融市场规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "同业负债",
              口径: "月日均环比",
              本期: 1756.73,
              对比期: 1710.07,
              增减额: 46.66,
              "增减幅%": 2.73,
              口径来源: "月度分析-金融市场：总账对账+日均同源历史月重建",
            },
          ],
        },
        {
          key: "income_rate_analysis",
          title: "收益率分析（总账可复算）",
          columns: ["指标", "板块", "收益类别", "年日均规模", "总账收益/支出", "年化收益率/付息率%", "口径来源"],
          rows: [
            {
              指标: "公司贷款利息收入",
              板块: "公司板块",
              收益类别: "贷款利息收入",
              年日均规模: 3339.26,
              "总账收益/支出": 32.4,
              "年化收益率/付息率%": 3.93,
              口径来源: "收益率分析：总账收益科目+日均规模重建",
            },
            {
              指标: "个人贷款利息收入",
              板块: "参考：个人贷款总量",
              收益类别: "贷款利息收入",
              年日均规模: null,
              "总账收益/支出": 6.53,
              "年化收益率/付息率%": null,
              口径来源: "source_missing: 个人贷款收益率分母依赖信用卡生息规模/80297微贷拆分，当前总账+日均闭环未确认",
            },
            {
              指标: "金融投资利息收入",
              板块: "金融市场",
              收益类别: "金融投资利息收入",
              年日均规模: null,
              "总账收益/支出": null,
              "年化收益率/付息率%": null,
              口径来源: "source_missing: 财务指标表该项依赖外部营收分项/FTP/收益率来源，当前总账+日均闭环未确认",
            },
          ],
        },
        {
          key: "income_rate_attribution",
          title: "收益量价归因（年累计同比）",
          columns: ["指标", "板块", "本期收益/支出", "对比期收益/支出", "增减额", "规模贡献", "利率贡献", "校验差异", "口径来源"],
          rows: [
            {
              指标: "公司贷款利息收入",
              板块: "公司板块",
              "本期收益/支出": 32.4,
              "对比期收益/支出": 29.15,
              增减额: 3.24,
              规模贡献: 6.12,
              利率贡献: -2.88,
              校验差异: 0,
              口径来源: "收益量价归因：总账收益科目+日均规模按年累计同比拆解",
            },
            {
              指标: "个人贷款利息收入",
              板块: "参考：个人贷款总量",
              "本期收益/支出": 6.53,
              "对比期收益/支出": 7.68,
              增减额: -1.15,
              规模贡献: null,
              利率贡献: null,
              校验差异: null,
              口径来源: "source_missing: 个人贷款收益率分母依赖信用卡生息规模/80297微贷拆分，当前总账+日均闭环未确认",
            },
          ],
        },
        {
          key: "deposit_interest_split",
          title: "存款利息拆分",
          columns: ["指标", "板块", "本期年日均", "年累计利息支出", "年化付息率%", "同比增减额", "本月月日均", "本月利息支出", "本月付息率%", "环比增减额", "口径来源"],
          rows: [
            {
              指标: "公司存款",
              板块: "公司板块",
              本期年日均: 2518.24,
              年累计利息支出: 7.67,
              "年化付息率%": 1.24,
              同比增减额: -0.41,
              本月月日均: 2497.6,
              本月利息支出: 2.67,
              "本月付息率%": 1.26,
              环比增减额: 0.29,
              口径来源: "存款利息拆分：总账521利息支出+日均存款规模重建",
            },
          ],
        },
        {
          key: "parent_company_revenue_components",
          title: "母公司营收分项",
          columns: ["指标", "类别", "同比本期", "同比对比期", "同比增减额", "同比增减幅%", "环比本月", "环比上月", "环比增减额", "环比增减幅%", "口径来源"],
          rows: [
            {
              指标: "贷款利息收入",
              类别: "利息净收入",
              同比本期: 39.01,
              同比对比期: 36.96,
              同比增减额: 2.05,
              "同比增减幅%": 5.55,
              环比本月: 13.68,
              环比上月: 12.76,
              环比增减额: 0.92,
              "环比增减幅%": 7.21,
              口径来源: "母公司营收分项：总账损益科目可复算部分",
            },
            {
              指标: "金融投资利息收入",
              类别: "利息净收入",
              同比本期: null,
              同比对比期: null,
              同比增减额: null,
              "同比增减幅%": null,
              环比本月: null,
              环比上月: null,
              环比增减额: null,
              "环比增减幅%": null,
              口径来源: "source_missing: 母公司营收分项该行依赖外部营收分项/FTP/非息明细来源，当前总账+日均闭环未确认",
            },
          ],
        },
        {
          key: "industry_gap",
          title: "行业存贷差",
          columns: ["行业", "存贷差_时点"],
          rows: [{ 行业: "农林牧渔", 存贷差_时点: -600 }],
        },
      ],
    };

    const getLedgerPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: datesPayload,
    }));
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: summaryPayload,
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: dataPayload,
    }));
    const getLedgerPnlMonthlyAnalysisDates = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
      result: monthlyAnalysisDatesPayload,
    }));
    const getLedgerPnlMonthlyAnalysisWorkbook = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
      result: monthlyAnalysisWorkbookPayload,
    }));

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates,
      getLedgerPnlSummary,
      getLedgerPnlData,
      getLedgerPnlMonthlyAnalysisDates,
      getLedgerPnlMonthlyAnalysisWorkbook,
    });

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-03-31", "CNX");
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-03-31", "CNX");
      expect(getLedgerPnlMonthlyAnalysisWorkbook).toHaveBeenCalledWith({ reportMonth: "202603" });
    });

    for (const expected of [
      "1.00 亿元",
      "-2.00 亿元",
      "3.00 亿元",
      "-4.00 亿元",
      "5.00 亿元",
      "6.00 亿元",
      "7.00 亿元",
      "8.00 亿元",
      "9.00 亿元",
      "11.00 亿元",
      "12.00 亿元",
    ]) {
      expect((await screen.findAllByText(expected)).length).toBeGreaterThan(0);
    }

    expect(screen.queryByText("100000000.00")).not.toBeInTheDocument();
    expect(screen.queryByText("999.99 万元")).not.toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-panel")).toHaveTextContent("总账对账 + 日均分析");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-month")).toHaveTextContent("202603");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-overview")).toHaveTextContent("总资产(亿)");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-indicator-status")).toHaveTextContent(
      "贷款总额（QDB源）",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-indicator-status")).toHaveTextContent(
      "正式口径待接入",
    );
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("正式财务指标状态");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("QDB 可复算");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("正式待接入");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("贷款总额（QDB源）");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("4,189.47");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("集团营业收入");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("未接入");
    expect(screen.getByTestId("ledger-pnl-formal-indicator-status-panel")).toHaveTextContent("formal_pending");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-summary-3d")).toHaveTextContent("公司贷款");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-alerts")).toHaveTextContent("14001000001");

    await userEvent.click(screen.getByTestId("ledger-pnl-workbook-tables-tab-segment"));
    expect(screen.getByText("分部基础规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-base-scale")).toHaveTextContent("微贷中心");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-base-scale")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByText("分部规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-scale-compare")).toHaveTextContent(
      "公司贷款合计",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-scale-compare")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByText("公司规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-company-scale")).toHaveTextContent("公司存款-活期");
    expect(screen.getByText("公司规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-company-scale-compare")).toHaveTextContent(
      "公司贷款-票据",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-company-scale-compare")).toHaveTextContent(
      "月度分析-公司板块",
    );
    expect(screen.getByText("零售规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-retail-scale")).toHaveTextContent("零售存款-活期");
    expect(screen.getByText("零售规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-retail-scale-compare")).toHaveTextContent(
      "零售存款合计",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-retail-scale-compare")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByText("金融市场规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-market-scale")).toHaveTextContent(
      "生息债券投资",
    );
    expect(screen.getByText("金融市场规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-market-scale-compare")).toHaveTextContent(
      "同业负债",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-market-scale-compare")).toHaveTextContent(
      "月度分析-金融市场",
    );
    await userEvent.click(screen.getByTestId("ledger-pnl-workbook-tables-tab-income"));
    expect(screen.getByText("收益率分析（总账可复算）")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent(
      "公司贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent(
      "个人贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent(
      "信用卡生息规模",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent("source_missing");
    expect(screen.getByText("收益量价归因（年累计同比）")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate-attribution")).toHaveTextContent(
      "规模贡献",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate-attribution")).toHaveTextContent(
      "公司贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate-attribution")).toHaveTextContent(
      "个人贷款利息收入",
    );
    expect(screen.getByText("存款利息拆分")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-deposit-interest-split")).toHaveTextContent(
      "公司存款",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-deposit-interest-split")).toHaveTextContent(
      "7.67",
    );
    expect(screen.getByText("母公司营收分项")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-parent-company-revenue")).toHaveTextContent(
      "贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-parent-company-revenue")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-foreign-currency")).toHaveTextContent("AC债券投资");
  });

  it("does not fall back to an unrelated monthly analysis workbook", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: { dates: ["2026-04-30"] },
    }));
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-04-30",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("0.00"),
        ledger_monthly_pnl_all: money("0.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [],
        by_account: [],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-04-30",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("0.00"),
          total_pnl: money("0.00"),
          count: 0,
        },
        items: [],
      },
    }));
    const getLedgerPnlMonthlyAnalysisDates = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
      result: { report_months: ["202401", "202402"] },
    }));
    const getLedgerPnlMonthlyAnalysisWorkbook = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
      result: { report_month: "202401", sheets: [] },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates,
        getLedgerPnlSummary,
        getLedgerPnlData,
        getLedgerPnlMonthlyAnalysisDates,
        getLedgerPnlMonthlyAnalysisWorkbook,
      },
      "/ledger-pnl?report_date=2026-04-30",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-04-30", "CNX");
      expect(getLedgerPnlMonthlyAnalysisDates).toHaveBeenCalled();
    });

    expect(getLedgerPnlMonthlyAnalysisWorkbook).not.toHaveBeenCalled();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-month")).toHaveTextContent("202604 无匹配");
    expect(await screen.findByTestId("ledger-pnl-monthly-analysis-missing-month")).toHaveTextContent(
      "当前报告日没有对应月度分析工作簿",
    );
  });

  it("places the 202606 candidate panel after summary cards and keeps its request CNX-only", async () => {
    const base = createApiClient({ mode: "mock" });
    const candidateRead = vi.fn(base.getLedgerPnlCandidateFinancialIndicators);

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlCandidateFinancialIndicators: candidateRead,
      },
      "/ledger-pnl?report_date=2026-06-30&currency=CNY",
    );

    const panel = await screen.findByTestId("candidate-financial-indicators-panel");
    expect(panel).toHaveTextContent("候选财务指标");
    expect(panel).toHaveTextContent("仅支持 CNX 综合本口径");
    expect(candidateRead).toHaveBeenCalledWith("202606", { includeLineage: false });
    expect(candidateRead.mock.calls[0]).toHaveLength(2);

    const summaryCards = screen.getByTestId("ledger-pnl-summary-cards");
    const indicatorSummaryPanel = screen.getByTestId(
      "ledger-pnl-financial-indicator-summary-panel",
    );
    const monthlyPanel = screen.getByTestId("ledger-pnl-monthly-analysis-panel");
    const precedes = (earlier: Element, later: Element) =>
      Boolean(
        earlier.compareDocumentPosition(later) & Node.DOCUMENT_POSITION_FOLLOWING,
      );
    expect(precedes(summaryCards, indicatorSummaryPanel)).toBe(true);
    expect(precedes(indicatorSummaryPanel, panel)).toBe(true);
    expect(precedes(panel, monthlyPanel)).toBe(true);
  });

  describe("viewport-gated sections", () => {
    class ControlledIntersectionObserver {
      static instances: ControlledIntersectionObserver[] = [];

      static reset() {
        ControlledIntersectionObserver.instances = [];
      }

      static intersectAll() {
        for (const instance of [...ControlledIntersectionObserver.instances]) {
          const entries = [...instance.elements].map((element) => ({
            isIntersecting: true,
            target: element,
          }));
          if (entries.length > 0) {
            instance.callback(entries);
          }
        }
      }

      elements = new Set<Element>();

      constructor(
        private readonly callback: (
          entries: Array<{ isIntersecting: boolean; target: Element }>,
        ) => void,
      ) {
        ControlledIntersectionObserver.instances.push(this);
      }

      observe = (element: Element) => {
        this.elements.add(element);
      };

      unobserve = (element: Element) => {
        this.elements.delete(element);
      };

      disconnect = () => {
        this.elements.clear();
      };
    }

    function buildGatedClient() {
      const base = createApiClient({ mode: "mock" });
      const spies = {
        candidate: vi.fn(base.getLedgerPnlCandidateFinancialIndicators),
        indicatorSummary: vi.fn(base.getLedgerPnlFinancialIndicatorSummary),
        formalContract: vi.fn(base.getLedgerPnlFormalFinancialIndicators),
        ruleChecks: vi.fn(base.getLedgerPnlFormalIndicatorRuleChecks),
        workbook: vi.fn(base.getLedgerPnlMonthlyAnalysisWorkbook),
      };
      const client: ApiClient = {
        ...base,
        getLedgerPnlCandidateFinancialIndicators: spies.candidate,
        getLedgerPnlFinancialIndicatorSummary: spies.indicatorSummary,
        getLedgerPnlFormalFinancialIndicators: spies.formalContract,
        getLedgerPnlFormalIndicatorRuleChecks: spies.ruleChecks,
        getLedgerPnlMonthlyAnalysisWorkbook: spies.workbook,
      };
      return { client, spies };
    }

    beforeEach(() => {
      ControlledIntersectionObserver.reset();
      vi.stubGlobal("IntersectionObserver", ControlledIntersectionObserver);
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("does not fire gated queries until their sections enter the viewport", async () => {
      const { client, spies } = buildGatedClient();

      renderLedgerPnlPage(client, "/ledger-pnl?report_date=2025-12-31");

      await screen.findByTestId("ledger-pnl-analysis-conclusion");

      expect(screen.getByTestId("ledger-pnl-indicators-skeleton")).toBeInTheDocument();
      expect(screen.getByTestId("ledger-pnl-candidate-skeleton")).toBeInTheDocument();
      expect(screen.getByTestId("ledger-pnl-reconciliation-skeleton")).toBeInTheDocument();
      expect(spies.candidate).not.toHaveBeenCalled();
      expect(spies.indicatorSummary).not.toHaveBeenCalled();
      expect(spies.formalContract).not.toHaveBeenCalled();
      expect(spies.ruleChecks).not.toHaveBeenCalled();
      expect(spies.workbook).not.toHaveBeenCalled();

      const strip = screen.getByTestId("ledger-pnl-functional-audit-strip");
      await waitFor(() => {
        expect(strip).toHaveTextContent("候选分析可用，对账区待加载");
      });
      expect(strip).toHaveTextContent("对账区块未加载");
      expect(strip).not.toHaveTextContent("正式契约读取失败");

      act(() => {
        ControlledIntersectionObserver.intersectAll();
      });

      await waitFor(() => {
        expect(spies.candidate).toHaveBeenCalled();
        expect(spies.indicatorSummary).toHaveBeenCalled();
        expect(spies.formalContract).toHaveBeenCalled();
        expect(spies.ruleChecks).toHaveBeenCalled();
      });
      expect(screen.queryByTestId("ledger-pnl-indicators-skeleton")).not.toBeInTheDocument();
      expect(screen.queryByTestId("ledger-pnl-candidate-skeleton")).not.toBeInTheDocument();
      expect(screen.queryByTestId("ledger-pnl-reconciliation-skeleton")).not.toBeInTheDocument();
    });

    it("wakes the target and every gated section above it when navigating from the section nav", async () => {
      const { client, spies } = buildGatedClient();
      const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
      HTMLElement.prototype.scrollIntoView = vi.fn();

      try {
        renderLedgerPnlPage(client, "/ledger-pnl?report_date=2025-12-31");

        await screen.findByTestId("ledger-pnl-analysis-conclusion");
        expect(spies.candidate).not.toHaveBeenCalled();

        await userEvent.click(
          screen.getByTestId(
            "ledger-pnl-section-nav-item-ledger-pnl-section-reconciliation",
          ),
        );

        await waitFor(() => {
          expect(spies.indicatorSummary).toHaveBeenCalled();
          expect(spies.candidate).toHaveBeenCalled();
          expect(spies.formalContract).toHaveBeenCalled();
          expect(spies.ruleChecks).toHaveBeenCalled();
        });
        expect(
          screen.queryByTestId("ledger-pnl-indicators-skeleton"),
        ).not.toBeInTheDocument();
        expect(
          screen.queryByTestId("ledger-pnl-candidate-skeleton"),
        ).not.toBeInTheDocument();
        expect(
          screen.queryByTestId("ledger-pnl-reconciliation-skeleton"),
        ).not.toBeInTheDocument();
      } finally {
        HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
      }
    });
  });
});
