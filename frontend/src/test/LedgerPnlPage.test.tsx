import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  LedgerMoneyValue,
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

  return render(
    <Wrapper>
      <LedgerPnlPage />
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
      getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
      getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
        result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
        result: { report_months: [] },
      })),
      getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
    expect(panel).toHaveTextContent("needs_reconciliation 1");

    const formalPendingRow = screen.getByTestId(
      "ledger-pnl-formal-indicator-source-contract-row-group.operating_revenue",
    );
    expect(formalPendingRow).toHaveTextContent("集团营业收入");
    expect(formalPendingRow).toHaveTextContent(/正式展示值\s*未接入/);
    expect(formalPendingRow).toHaveTextContent(/Excel 样本值\s*43.4194731314 亿元/);
    expect(formalPendingRow).toHaveTextContent(/系统候选值\s*-/);

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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
    expect(panel).toHaveTextContent("暂无正式财务指标源契约数据");
  });

  it("puts the functional evidence verdict before monthly analysis and prevents empty ledger evidence from reading as zero", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      quality_flag: "warning",
      source_version: "sv_ledger_pnl_empty",
      evidence_rows: 0,
      next_drill: [
        {
          label: "核对总账报告日",
          detail: "确认请求报告日是否存在于 /api/ledger-pnl/dates 返回列表。",
        },
        {
          label: "核对总账源文件",
          detail: "检查 product_category_source_dir 是否包含对应 YYYYMM 的总账对账工作簿。",
        },
      ],
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const dataMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      quality_flag: "warning",
      source_version: "sv_ledger_pnl_empty",
      evidence_rows: 0,
      next_drill: [
        {
          label: "核对明细证据",
          detail: "补查 2026-05-31 的 canonical 总账事实行，避免把无证据结果解释为真实 0。",
        },
      ],
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
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: summaryMeta,
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_pnl_empty",
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
          result_meta: dataMeta,
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_pnl_empty",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: 0,
            },
            items: [],
          },
        })),
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
      expect(strip).toHaveTextContent("功能性审计");
      expect(strip).toHaveTextContent("总账损益证据缺失");
      expect(strip).toHaveTextContent("不能把总账明细或空汇总解释为真实 PnL 0");
      expect(strip).toHaveTextContent("请求报告日2026-05-31");
      expect(strip).toHaveTextContent("解析报告日2026-05-31");
      expect(strip).toHaveTextContent("汇总证据行0");
      expect(strip).toHaveTextContent("明细证据行0");
      expect(strip).toHaveTextContent("质量汇总预警 / 明细预警");
      expect(strip).toHaveTextContent("来源版本sv_ledger_pnl_empty");
      expect(strip).toHaveTextContent("正式契约缺失，正式值不可用");
      expect(strip).toHaveTextContent("下一步补证");
      expect(strip).toHaveTextContent("核对总账报告日");
      expect(strip).toHaveTextContent("确认请求报告日是否存在于 /api/ledger-pnl/dates 返回列表。");
      expect(strip).toHaveTextContent("核对总账源文件");
      expect(strip).toHaveTextContent("补查 2026-05-31 的 canonical 总账事实行");
    });

    const cards = screen.getByTestId("ledger-pnl-summary-cards");
    const monthlyAnalysis = screen.getByTestId("ledger-pnl-monthly-analysis-panel");
    expect(
      strip.compareDocumentPosition(cards) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      cards.compareDocumentPosition(monthlyAnalysis) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("does not treat non-PnL ledger detail rows as analyzable PnL evidence", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      quality_flag: "warning",
      source_version: "sv_ledger_assets_only",
      evidence_rows: 0,
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const dataMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      quality_flag: "ok",
      source_version: "sv_ledger_assets_only",
      evidence_rows: 2,
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
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary: vi.fn(async () => ({
          result_meta: summaryMeta,
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_assets_only",
            ledger_monthly_pnl_core: money("0.00"),
            ledger_monthly_pnl_all: money("0.00"),
            ledger_total_assets: money("100.00"),
            ledger_total_liabilities: money("80.00"),
            ledger_net_assets: money("20.00"),
            by_currency: [],
            by_account: [],
          },
        })),
        getLedgerPnlData: vi.fn(async () => ({
          result_meta: dataMeta,
          result: {
            report_date: "2026-05-31",
            source_version: "sv_ledger_assets_only",
            summary: {
              total_pnl_cnx: money("0.00"),
              total_pnl_cny: money("0.00"),
              total_pnl: money("0.00"),
              count: 2,
            },
            items: [
              {
                account_code: "10101000001",
                account_name: "现金",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("100.00"),
                monthly_pnl: money("0.00"),
                daily_avg_balance: money("100.00"),
                days_in_period: 31,
              },
              {
                account_code: "23401000001",
                account_name: "应付款",
                currency: "CNY",
                beginning_balance: money("0.00"),
                ending_balance: money("-80.00"),
                monthly_pnl: money("0.00"),
                daily_avg_balance: money("-80.00"),
                days_in_period: 31,
              },
            ],
          },
        })),
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
      expect(strip).toHaveTextContent("总账损益证据缺失");
      expect(strip).toHaveTextContent("汇总证据行0");
      expect(strip).toHaveTextContent("明细证据行2");
      expect(strip).not.toHaveTextContent("总账候选口径可分析");
    });
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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
      expect(strip).toHaveTextContent("需要核对日期清单和源文件登记");
      expect(strip).not.toHaveTextContent("总账损益证据缺失");
      expect(strip).not.toHaveTextContent("总账候选口径可分析");
    });
  });

  it("classifies ledger read permission failures in the first-screen functional verdict", async () => {
    const base = createApiClient({ mode: "mock" });
    const forbidden = new Error("Request failed: /api/ledger-pnl/summary?date=2026-05-31 (403)");

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => {
          throw forbidden;
        }),
        getLedgerPnlSummary: vi.fn(async () => {
          throw forbidden;
        }),
        getLedgerPnlData: vi.fn(async () => {
          throw forbidden;
        }),
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            quality_flag: "warning" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    const strip = await screen.findByTestId("ledger-pnl-functional-audit-strip");
    await waitFor(() => {
      expect(strip).toHaveTextContent("无权限读取总账损益");
      expect(strip).toHaveTextContent("当前用户没有 ledger_pnl 读取权限");
      expect(strip).not.toHaveTextContent("总账链路读取失败本次不能形成总账损益判断；请先恢复接口读取");
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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators,
      },
      "/ledger-pnl",
    );

    const panel = await screen.findByTestId("ledger-pnl-formal-indicator-source-contract-panel");
    expect(panel).toHaveTextContent("等待正式财务指标契约");
    expect(panel).not.toHaveTextContent("正式财务指标契约已读取");
    expect(getLedgerPnlFormalFinancialIndicators).not.toHaveBeenCalled();
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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
    expect(within(cards).getAllByText("--")).toHaveLength(4);
    expect(within(cards).queryByText("0.00 亿元")).not.toBeInTheDocument();

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    expect(panel).toHaveTextContent("口径状态");
    expect(panel).toHaveTextContent("切片可比/数据待补");

    const detailTable = await screen.findByTestId("ledger-pnl-detail-table");
    expect(within(detailTable).getAllByText("--")).toHaveLength(3);
    expect(detailTable).toHaveTextContent("1.00 亿元");
  });

  it("prioritizes missing reconciliation evidence before known residual entry points", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("10000000000.00"),
        ledger_monthly_pnl_all: money("10000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("9900000000.00") }],
        by_account: [],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("10000000000.00"),
          total_pnl: money("10000000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("10000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    const evidenceKpi = Array.from(panel.querySelectorAll(".ledger-pnl-analysis__kpi")).find((node) =>
      node.textContent?.startsWith("补证入口"),
    );
    if (!evidenceKpi) {
      throw new Error("missing evidence KPI");
    }
    expect(panel).toHaveTextContent("最大卡点币种合计差异 1.00 亿元");
    expect(panel).toHaveTextContent("科目层待校验");
    expect(evidenceKpi).toHaveTextContent("补总账与对账口径数据");
    expect(evidenceKpi).not.toHaveTextContent("补币种汇总或确认币种口径");
  });

  it("surfaces empty ledger summary and detail tables instead of leaving blank bodies", async () => {
    const base = createApiClient({ mode: "mock" });

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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(screen.getByTestId("ledger-pnl-summary-cards")).toHaveTextContent("0.00 亿元");
    });

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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    expect(await screen.findByText("币种汇总读取失败")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-account-summary-table")).toHaveTextContent("科目汇总读取失败");
    expect(screen.getByTestId("ledger-pnl-detail-table")).toHaveTextContent("科目明细读取失败");
  });

  it("caps very large ledger tables and keeps the full row count visible", async () => {
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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
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
    expect(accountTable).toHaveTextContent("科目汇总已按金额绝对值展示前 200 条 / 总计 201 条");
    expect(within(accountTable).queryByText(/^account-row-1$/)).not.toBeInTheDocument();

    const detailTable = screen.getByTestId("ledger-pnl-detail-table");
    expect(detailTable).toHaveTextContent("detail-row-201");
    expect(detailTable).toHaveTextContent("科目明细已按金额绝对值展示前 200 条 / 总计 201 条");
    expect(within(detailTable).queryByText(/^detail-row-200$/)).not.toBeInTheDocument();
  });

  it("uses the report_date query for ledger reads while the date list is still loading", async () => {
    const base = createApiClient({ mode: "mock" });
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
        getLedgerPnlDates: vi.fn(() => new Promise<ApiEnvelope<LedgerPnlDatesPayload>>(() => {})),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });
    expect(screen.getByTestId("ledger-pnl-currency-summary-table")).not.toHaveTextContent(
      "暂无币种汇总数据",
    );
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
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
    });
    await screen.findByRole("option", { name: "2026-04-30" });
    await user.selectOptions(screen.getByLabelText("ledger-pnl-report-date"), "2026-04-30");

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-04-30", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-04-30", undefined);
    });
    expect(screen.getByLabelText("ledger-pnl-report-date")).toHaveValue("2026-04-30");
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
    const getQdbGlMonthlyAnalysisDates = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
      result: monthlyAnalysisDatesPayload,
    }));
    const getQdbGlMonthlyAnalysisWorkbook = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
      result: monthlyAnalysisWorkbookPayload,
    }));

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates,
      getLedgerPnlSummary,
      getLedgerPnlData,
      getQdbGlMonthlyAnalysisDates,
      getQdbGlMonthlyAnalysisWorkbook,
    });

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-03-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-03-31", undefined);
      expect(getQdbGlMonthlyAnalysisWorkbook).toHaveBeenCalledWith({ reportMonth: "202603" });
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

  it("turns ledger rows into a first-principles explainability verdict before raw tables", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("9000000000.00"),
        ledger_monthly_pnl_all: money("10000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [
          { currency: "CNX", total_pnl: money("6000000000.00") },
          { currency: "CNY", total_pnl: money("4000000000.00") },
        ],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("3000000000.00"), count: 1 },
          { account_code: "602101", account_name: "存款利息支出", total_pnl: money("1000000000.00"), count: 1 },
          { account_code: "610101", account_name: "公允价值变动收益", total_pnl: money("2000000000.00"), count: 1 },
          { account_code: "611101", account_name: "外汇结售汇损益", total_pnl: money("2000000000.00"), count: 1 },
          { account_code: "612101", account_name: "衍生工具套期损益", total_pnl: money("1000000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("6000000000.00"),
          total_pnl_cny: money("4000000000.00"),
          total_pnl: money("10000000000.00"),
          count: 3,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("3000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
          {
            account_code: "610101",
            account_name: "公允价值变动收益",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("3000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
          {
            account_code: "611101",
            account_name: "外汇结售汇损益",
            currency: "CNX",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("2000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));
    const getLedgerPnlFormalFinancialIndicators = vi.fn(async () => ({
      result_meta: {
        ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
        basis: "ledger" as const,
        quality_flag: "warning" as const,
        as_of_date: "2026-05-31",
        date_basis: "report_month_end",
        formal_use_allowed: false,
      },
      result: buildMissingFormalIndicatorContractPayload(),
    }));

    const { container } = renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators,
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlFormalFinancialIndicators).toHaveBeenCalledWith("202605");
    });

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    expect(panel).toHaveTextContent("损益解释模型");
    expect(panel).toHaveTextContent("分析口径");
    expect(panel).toHaveTextContent("解释链未闭合");
    expect(panel).toHaveTextContent("解释覆盖率");
    expect(panel).toHaveTextContent("80.00%");
    expect(panel).toHaveTextContent("最大卡点");
    expect(panel).toHaveTextContent("明细差异 20.00 亿元");
    expect(panel).toHaveTextContent("补证入口");
    expect(panel).toHaveTextContent("补明细或确认过滤口径");
    expect(panel).toHaveTextContent("币种合计一致");
    expect(panel).toHaveTextContent("科目汇总差异 10.00 亿元");
    expect(panel).toHaveTextContent("未解释残差 20.00 亿元");
    expect(panel).toHaveTextContent("残差诊断表");
    expect(panel).toHaveTextContent("卡点层级");
    expect(panel).toHaveTextContent("总账金额");
    expect(panel).toHaveTextContent("对账金额");
    expect(panel).toHaveTextContent("差异金额");
    expect(panel).toHaveTextContent("诊断判断");
    expect(panel).toHaveTextContent("需要补的证据");
    expect(panel).toHaveTextContent("币种层闭合");
    expect(panel).toHaveTextContent("科目层残差 10.00 亿元");
    expect(panel).toHaveTextContent("明细层残差 20.00 亿元");
    expect(panel).toHaveTextContent("补明细或确认过滤口径");
    expect(panel).toHaveTextContent("明细残差候选科目");
    expect(panel).toHaveTextContent("科目汇总金额");
    expect(panel).toHaveTextContent("明细合计金额");
    expect(panel).toHaveTextContent("602101 存款利息支出");
    expect(panel).toHaveTextContent("缺明细 10.00 亿元");
    expect(panel).toHaveTextContent("610101 公允价值变动收益");
    expect(panel).toHaveTextContent("明细多 10.00 亿元");
    expect(panel).toHaveTextContent("利息收支");
    expect(panel).toHaveTextContent("估值变动");
    expect(panel).toHaveTextContent("衍生品/套保");
    expect(panel).toHaveTextContent("外汇/结售汇");
    expect(panel).toHaveTextContent("正式财务指标未接入");
    expect(panel).toHaveTextContent("正式口径待确认");

    const rawTable = container.querySelector("[data-testid='ledger-pnl-currency-summary-table']");
    expect(rawTable).not.toBeNull();
    expect(
      panel.compareDocumentPosition(rawTable as Element) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("gates the detail-layer residual diagnostic when summary and detail metadata are not comparable", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const detailMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      resolved_report_date: undefined,
      as_of_date: undefined,
      filters_applied: { currency: "ALL" },
    };
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: summaryMeta,
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("10000000000.00"),
        ledger_monthly_pnl_all: money("10000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("10000000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("10000000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: detailMeta,
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("9500000000.00"),
          total_pnl: money("9500000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("9500000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    await waitFor(() => {
      const table = screen.getByTestId("ledger-pnl-residual-diagnostic-table");
      expect(table).toHaveTextContent("明细层可比性待核");
      expect(table).toHaveTextContent("汇总 resolved_report_date=2026-05-31，明细 resolved_report_date=缺失");
      expect(table).not.toHaveTextContent("明细层残差 5.00 亿元");
    });

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    expect(panel).toHaveTextContent("解释链待校验");
    expect(panel).toHaveTextContent("口径状态");
    expect(panel).toHaveTextContent("汇总/明细口径待核");
    expect(panel).toHaveTextContent("解释覆盖率--");
    expect(panel).toHaveTextContent("最大卡点汇总 resolved_report_date=2026-05-31，明细 resolved_report_date=缺失");
    expect(panel).not.toHaveTextContent("最大卡点明细差异 5.00 亿元");
  });

  it("keeps comparable top residuals visible when only detail metadata is not comparable", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const detailMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      resolved_report_date: undefined,
      as_of_date: undefined,
      filters_applied: { currency: "ALL" },
    };
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: summaryMeta,
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("10000000000.00"),
        ledger_monthly_pnl_all: money("10000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("9000000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("10000000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: detailMeta,
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("9500000000.00"),
          total_pnl: money("9500000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("9500000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    expect(panel).toHaveTextContent("解释链未闭合");
    expect(panel).toHaveTextContent("解释覆盖率90.00%");
    expect(panel).toHaveTextContent("最大卡点币种合计差异 10.00 亿元");
    expect(panel).toHaveTextContent("未解释残差 10.00 亿元");
    expect(panel).toHaveTextContent("明细可比性待核");
    expect(panel).not.toHaveTextContent("明细明细可比性待核");
    expect(panel).toHaveTextContent("汇总 resolved_report_date=2026-05-31，明细 resolved_report_date=缺失");
    expect(panel).not.toHaveTextContent("最大卡点明细差异 5.00 亿元");
  });

  it("flags detail-only accounts as reverse residual candidates", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("10000000000.00"),
        ledger_monthly_pnl_all: money("10000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("10000000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("10000000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("10500000000.00"),
          total_pnl: money("10500000000.00"),
          count: 2,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("10000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
          {
            account_code: "599999",
            account_name: "未入汇总科目",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("500000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    expect(panel).toHaveTextContent("明细残差候选科目");
    expect(panel).toHaveTextContent("599999 未入汇总科目");
    expect(panel).toHaveTextContent("0.00 亿元");
    expect(panel).toHaveTextContent("5.00 亿元");
    expect(panel).toHaveTextContent("汇总缺失 5.00 亿元");
  });

  it("gates detail residual account judgments when summary and detail metadata are not comparable", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const detailMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      resolved_report_date: undefined,
      as_of_date: undefined,
      filters_applied: { currency: "ALL" },
    };
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: summaryMeta,
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("10000000000.00"),
        ledger_monthly_pnl_all: money("10000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("10000000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("10000000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: detailMeta,
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("9500000000.00"),
          total_pnl: money("9500000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("9500000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const table = await screen.findByTestId("ledger-pnl-detail-residual-account-table");
    expect(table).toHaveTextContent("601101 贷款利息收入");
    expect(table).toHaveTextContent("可比性待核");
    expect(table).toHaveTextContent("汇总 resolved_report_date=2026-05-31，明细 resolved_report_date=缺失");
    expect(table).not.toHaveTextContent("缺明细 5.00 亿元");
  });

  it("surfaces gross contribution and drag when net PnL hides offsetting accounts", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("500000000.00"),
        ledger_monthly_pnl_all: money("500000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("500000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("3000000000.00"), count: 1 },
          { account_code: "602101", account_name: "存款利息支出", total_pnl: money("-2500000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("500000000.00"),
          total_pnl: money("500000000.00"),
          count: 2,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("3000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
          {
            account_code: "602101",
            account_name: "存款利息支出",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("-2500000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const panel = await screen.findByTestId("ledger-pnl-explainability-panel");
    expect(panel).toHaveTextContent("解释链闭合");
    expect(panel).toHaveTextContent("损益方向拆解");
    expect(panel).toHaveTextContent("毛贡献金额");
    expect(panel).toHaveTextContent("毛拖累金额");
    expect(panel).toHaveTextContent("净额抵消率");
    expect(panel).toHaveTextContent("按总账科目代码和名称启发式归类");
    expect(panel).toHaveTextContent("不是正式产品、策略或管理归因维度");
    expect(panel).toHaveTextContent("利息收支");
    expect(panel).toHaveTextContent("30.00 亿元");
    expect(panel).toHaveTextContent("-25.00 亿元");
    expect(panel).toHaveTextContent("83.33%");
  });

  it("surfaces exposure-time implied annualized intensity for detail rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const detailMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      date_basis: "ledger_report_date",
    };
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("10000000.00"),
        ledger_monthly_pnl_all: money("10000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("10000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("10000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: detailMeta,
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("10000000.00"),
          total_pnl: money("10000000.00"),
          count: 2,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("10000000.00"),
            daily_avg_balance: money("1000000000.00"),
            days_in_period: 30,
          },
          {
            account_code: "602101",
            account_name: "存款利息支出",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("-5000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 30,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const table = await screen.findByTestId("ledger-pnl-exposure-intensity-table");
    expect(table).toHaveTextContent("规模时间强度候选");
    expect(table).toHaveTextContent("明细派生候选");
    expect(table).toHaveTextContent("不是正式收益率或财务指标");
    expect(table).toHaveTextContent(
      "明细切片证据：resolved_report_date=2026-05-31，as_of_date=2026-05-31，date_basis=ledger_report_date",
    );
    expect(table).toHaveTextContent("日均规模");
    expect(table).toHaveTextContent("天数");
    expect(table).toHaveTextContent("候选年化强度");
    expect(table).toHaveTextContent("601101 贷款利息收入");
    expect(table).toHaveTextContent("0.10 亿元");
    expect(table).toHaveTextContent("10.00 亿元");
    expect(table).toHaveTextContent("30");
    expect(table).toHaveTextContent("12.17%");
    expect(table).not.toHaveTextContent("602101 存款利息支出");
  });

  it("identifies currency-level residual candidates before raw currency tables", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("1500000000.00"),
        ledger_monthly_pnl_all: money("1500000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [
          { currency: "CNY", total_pnl: money("1000000000.00") },
          { currency: "CNX", total_pnl: money("500000000.00") },
        ],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("1500000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("1000000000.00"),
          total_pnl: money("1000000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("1000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    const { container } = renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const table = await screen.findByTestId("ledger-pnl-currency-residual-table");
    expect(table).toHaveTextContent("币种残差候选");
    expect(table).toHaveTextContent("币种汇总金额");
    expect(table).toHaveTextContent("明细币种金额");
    expect(table).toHaveTextContent("CNX");
    expect(table).toHaveTextContent("5.00 亿元");
    expect(table).toHaveTextContent("0.00 亿元");
    expect(table).toHaveTextContent("疑似缺明细 5.00 亿元");

    const rawTable = container.querySelector("[data-testid='ledger-pnl-currency-summary-table']");
    expect(rawTable).not.toBeNull();
    expect(
      table.compareDocumentPosition(rawTable as Element) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("keeps detail-only currency candidates visible when offsetting rows net to zero", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("1000000000.00"),
        ledger_monthly_pnl_all: money("1000000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [{ currency: "CNY", total_pnl: money("1000000000.00") }],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("1000000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("1000000000.00"),
          total_pnl: money("1000000000.00"),
          count: 3,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("1000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
          {
            account_code: "509901",
            account_name: "未汇总外币收入",
            currency: "JPY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("600000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
          {
            account_code: "509902",
            account_name: "未汇总外币支出",
            currency: "JPY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("-600000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 31,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const table = await screen.findByTestId("ledger-pnl-currency-residual-table");
    expect(table).toHaveTextContent("JPY");
    expect(table).toHaveTextContent("明细毛活动");
    expect(table).toHaveTextContent("12.00 亿元");
    expect(table).toHaveTextContent("疑似汇总缺失毛活动 12.00 亿元");
  });

  it("gates currency residual judgments when summary and detail metadata are not comparable", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const detailMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-04-30",
      as_of_date: "2026-04-30",
      filters_applied: { report_date: "2026-04-30", currency: "ALL" },
    };
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: summaryMeta,
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("1500000000.00"),
        ledger_monthly_pnl_all: money("1500000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [
          { currency: "CNY", total_pnl: money("1000000000.00") },
          { currency: "CNX", total_pnl: money("500000000.00") },
        ],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("1500000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: detailMeta,
      result: {
        report_date: "2026-04-30",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("1000000000.00"),
          total_pnl: money("1000000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("1000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 30,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const table = await screen.findByTestId("ledger-pnl-currency-residual-table");
    expect(table).toHaveTextContent("CNX");
    expect(table).toHaveTextContent("可比性待核");
    expect(table).toHaveTextContent("汇总 resolved_report_date=2026-05-31，明细 resolved_report_date=2026-04-30");
    expect(table).not.toHaveTextContent("疑似缺明细 5.00 亿元");
  });

  it("gates currency residual judgments when detail metadata is missing comparable dates", async () => {
    const base = createApiClient({ mode: "mock" });
    const summaryMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.summary"),
      requested_report_date: "2026-05-31",
      resolved_report_date: "2026-05-31",
      as_of_date: "2026-05-31",
      filters_applied: { report_date: "2026-05-31", currency: "ALL" },
    };
    const detailMeta: ResultMeta = {
      ...buildLedgerMeta("ledger_pnl.data"),
      resolved_report_date: undefined,
      as_of_date: undefined,
      filters_applied: { currency: "ALL" },
    };
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: summaryMeta,
      result: {
        report_date: "2026-05-31",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("1500000000.00"),
        ledger_monthly_pnl_all: money("1500000000.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [
          { currency: "CNY", total_pnl: money("1000000000.00") },
          { currency: "CNX", total_pnl: money("500000000.00") },
        ],
        by_account: [
          { account_code: "601101", account_name: "贷款利息收入", total_pnl: money("1500000000.00"), count: 1 },
        ],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: detailMeta,
      result: {
        report_date: "2026-05-31",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("1000000000.00"),
          total_pnl: money("1000000000.00"),
          count: 1,
        },
        items: [
          {
            account_code: "601101",
            account_name: "贷款利息收入",
            currency: "CNY",
            beginning_balance: money("0.00"),
            ending_balance: money("0.00"),
            monthly_pnl: money("1000000000.00"),
            daily_avg_balance: money("0.00"),
            days_in_period: 30,
          },
        ],
      },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates: vi.fn(async () => ({
          result_meta: buildMeta("ledger_pnl.dates"),
          result: { dates: ["2026-05-31"] },
        })),
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates: vi.fn(async () => ({
          result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: [] },
        })),
        getQdbGlMonthlyAnalysisWorkbook: vi.fn(),
        getLedgerPnlFormalFinancialIndicators: vi.fn(async () => ({
          result_meta: {
            ...buildAnalyticalMeta("ledger_pnl.formal_financial_indicator_source_contract"),
            basis: "ledger" as const,
            formal_use_allowed: false,
          },
          result: buildMissingFormalIndicatorContractPayload(),
        })),
      },
      "/ledger-pnl?report_date=2026-05-31",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-05-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-05-31", undefined);
    });

    const table = await screen.findByTestId("ledger-pnl-currency-residual-table");
    expect(table).toHaveTextContent("CNX");
    expect(table).toHaveTextContent("可比性待核");
    expect(table).toHaveTextContent("汇总 resolved_report_date=2026-05-31，明细 resolved_report_date=缺失");
    expect(table).not.toHaveTextContent("疑似缺明细 5.00 亿元");
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
    const getQdbGlMonthlyAnalysisDates = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
      result: { report_months: ["202401", "202402"] },
    }));
    const getQdbGlMonthlyAnalysisWorkbook = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
      result: { report_month: "202401", sheets: [] },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates,
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates,
        getQdbGlMonthlyAnalysisWorkbook,
      },
      "/ledger-pnl?report_date=2026-04-30",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-04-30", undefined);
      expect(getQdbGlMonthlyAnalysisDates).toHaveBeenCalled();
    });

    expect(getQdbGlMonthlyAnalysisWorkbook).not.toHaveBeenCalled();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-month")).toHaveTextContent("202604 无匹配");
    expect(await screen.findByTestId("ledger-pnl-monthly-analysis-missing-month")).toHaveTextContent(
      "当前报告日没有对应月度分析工作簿",
    );
  });
});
