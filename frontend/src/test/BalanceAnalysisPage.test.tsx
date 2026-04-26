import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as ReactRouterDom from "react-router-dom";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type {
  ApiEnvelope,
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisAdvancedAttributionBundlePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDetailRow,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookPayload,
  BalanceAnalysisWorkbookTable,
  ResultMeta,
} from "../api/contracts";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";
import { routerFuture } from "../router/routerFuture";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="balance-analysis-echarts-stub" />,
}));

function renderBalanceAnalysisWithClient(
  client: ReturnType<typeof createApiClient>,
  initialEntries: string[] = ["/balance-analysis"],
) {
  const router = createWorkbenchMemoryRouter(initialEntries);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 0,
        refetchOnWindowFocus: false,
      },
    },
  });

  const renderResult = render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} future={routerFuture} />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
  return { router, queryClient, ...renderResult };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal" as const,
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_balance",
    vendor_version: "vv_none",
    rule_version: "rv_balance",
    cache_version: "cv_balance",
    quality_flag: "ok" as const,
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-11T04:00:00Z",
  };
}

function buildSummaryResponse(offset: number): ApiEnvelope<BalanceAnalysisSummaryTablePayload> {
  const rows: BalanceAnalysisSummaryTablePayload["rows"] =
    offset === 0
      ? [
          {
            row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
            source_family: "zqtz" as const,
            display_name: "240001.IB",
            owner_name: "利率债组合",
            category_name: "交易账户",
            position_scope: "asset" as const,
            currency_basis: "CNY" as const,
            invest_type_std: "A",
            accounting_basis: "FVOCI",
            detail_row_count: 3,
            market_value_amount: "72000000000.00",
            amortized_cost_amount: "64800000000.00",
            accrued_interest_amount: "3600000000.00",
          },
          {
            row_key: "tyw:repo-1:CNY:liability:H:AC",
            source_family: "tyw" as const,
            display_name: "repo-1",
            owner_name: "同业负债池",
            category_name: "卖出回购",
            position_scope: "liability" as const,
            currency_basis: "CNY" as const,
            invest_type_std: "H",
            accounting_basis: "AC",
            detail_row_count: 1,
            market_value_amount: "7200000000.00",
            amortized_cost_amount: "7200000000.00",
            accrued_interest_amount: "1440000000.00",
          },
        ]
      : [
          {
            row_key: "zqtz:240002.IB:portfolio-b:cc-2:CNY:asset:H:AC",
            source_family: "zqtz" as const,
            display_name: "240002.IB",
            owner_name: "高等级组合",
            category_name: "摊余成本",
            position_scope: "asset" as const,
            currency_basis: "CNY" as const,
            invest_type_std: "H",
            accounting_basis: "AC",
            detail_row_count: 2,
            market_value_amount: "41000000000.00",
            amortized_cost_amount: "40300000000.00",
            accrued_interest_amount: "2000000000.00",
          },
        ];

  return {
    result_meta: buildMeta("balance-analysis.summary", `tr_balance_summary_${offset}`),
    result: {
      report_date: "2025-12-31",
      position_scope: "all" as const,
      currency_basis: "CNY" as const,
      limit: 2,
      offset,
      total_rows: 3,
      rows,
    },
  };
}

function buildWorkbookResponse(): ApiEnvelope<BalanceAnalysisWorkbookPayload> {
  const tables: BalanceAnalysisWorkbookTable[] = [
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
          balance_amount: "6482200.00",
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
          balance_amount: "16960854.11",
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
          gap_amount: "4290357.07",
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
          balance_amount: "9933000.00",
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
          balance_amount: "19483961.98",
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
          bond_amount: "9900751.47",
          interbank_asset_amount: "958000.00",
          interbank_liability_amount: "2206085.05",
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
          asset_amount: "120000.00",
          liability_amount: "86079.26",
          net_position_amount: "33920.74",
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
          balance_amount: "32874418.15",
        },
      ],
    },
    {
      key: "liquidity_bucket_metrics",
      title: "流动性桶指标",
      section_kind: "table",
      columns: [
        { key: "bucket", label: "桶" },
        { key: "full_scope_gap_amount", label: "全口径缺口" },
        { key: "net_cashflow_amount", label: "净现金流" },
        { key: "hqla_amount", label: "HQLA" },
      ],
      rows: [
        {
          bucket: "隔夜-7D",
          full_scope_gap_amount: "1234567.89",
          net_cashflow_amount: "2345678.12",
          hqla_amount: "3456789.01",
        },
      ],
    },
  ];
  const operationalSections: BalanceAnalysisWorkbookOperationalSection[] = [
    {
      key: "decision_items",
      title: "决策事项",
      section_kind: "decision_items",
      columns: [
        { key: "title", label: "Title" },
        { key: "severity", label: "Severity" },
      ],
      rows: [
        {
          title: "Review 1-2 year gap positioning",
          action_label: "Review gap",
          severity: "high",
          reason: "Bucket gap is 4290357.07 wan yuan.",
          source_section: "maturity_gap",
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
        { key: "event_date", label: "Event Date" },
        { key: "title", label: "Title" },
      ],
      rows: [
        {
          event_date: "2026-03-05",
          event_type: "bond_maturity",
          title: "240001.IB maturity",
          source: "internal_governed_schedule",
          impact_hint: "asset book / 政策性金融债",
          source_section: "maturity_gap",
        },
        {
          event_date: "2026-03-08",
          event_type: "funding_rollover",
          title: "repo-1 maturity",
          source: "internal_governed_schedule",
          impact_hint: "liability book / 卖出回购",
          source_section: "maturity_gap",
        },
      ],
    },
    {
      key: "risk_alerts",
      title: "风险预警",
      section_kind: "risk_alerts",
      columns: [
        { key: "title", label: "Title" },
        { key: "severity", label: "Severity" },
      ],
      rows: [
        {
          title: "Negative gap in 1-2 year bucket",
          severity: "high",
          reason: "Gap dropped to -128000.00 wan yuan.",
          source_section: "maturity_gap",
          rule_id: "bal_wb_risk_gap_001",
          rule_version: "v1",
        },
        {
          title: "Issuance liabilities outstanding",
          severity: "medium",
          reason: "Issuance book totals 18.00 wan yuan.",
          source_section: "issuance_business_types",
          rule_id: "bal_wb_risk_issuance_001",
          rule_version: "v1",
        },
      ],
    },
  ];
  return {
    result_meta: buildMeta("balance-analysis.workbook", "tr_balance_workbook"),
    result: {
      report_date: "2025-12-31",
      position_scope: "all" as const,
      currency_basis: "CNY" as const,
      cards: [
        {
          key: "bond_assets_excluding_issue",
          label: "债券资产(剔除发行类)",
          value: "32877980.96",
          note: "ZQTZ 资产端剔除发行类后的余额。峰值 99.00 万元（观测口径）。",
        },
        {
          key: "interbank_liabilities",
          label: "同业负债",
          value: "7239682.56",
          note: "TYW 负债端余额。",
        },
      ],
      tables,
      operational_sections: operationalSections,
    },
  };
}

function buildDecisionItemsResponse(
  overrides?: Partial<{
    rows: Array<{
      decision_key: string;
      title: string;
      action_label: string;
      severity: "low" | "medium" | "high";
      reason: string;
      source_section: string;
      rule_id: string;
      rule_version: string;
      latest_status: {
        decision_key: string;
        status: "pending" | "confirmed" | "dismissed";
        updated_at: string | null;
        updated_by: string | null;
        comment: string | null;
      };
    }>;
  }>,
) : ApiEnvelope<BalanceAnalysisDecisionItemsPayload> {
  return {
    result_meta: buildMeta("balance-analysis.decision-items", "tr_balance_decisions"),
    result: {
      report_date: "2025-12-31",
      position_scope: "all" as const,
      currency_basis: "CNY" as const,
      columns: [
        { key: "title", label: "Title" },
        { key: "action_label", label: "Action" },
        { key: "severity", label: "Severity" },
        { key: "reason", label: "Reason" },
        { key: "source_section", label: "Source Section" },
        { key: "rule_id", label: "Rule Id" },
        { key: "rule_version", label: "Rule Version" },
      ],
      rows: overrides?.rows ?? [
        {
          decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
          title: "Review 1-2 year gap positioning",
          action_label: "Review gap",
          severity: "high" as const,
          reason: "Bucket gap is 4290357.07 wan yuan.",
          source_section: "maturity_gap",
          rule_id: "bal_wb_decision_gap_001",
          rule_version: "v1",
          latest_status: {
            decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
            status: "pending" as const,
            updated_at: null,
            updated_by: null,
            comment: null,
          },
        },
      ],
    },
  };
}

function buildCurrentUserResponse(): BalanceAnalysisCurrentUserPayload {
  return {
    user_id: "phase1-dev-user",
    role: "admin",
    identity_source: "fallback" as const,
  };
}

describe("BalanceAnalysisPage", () => {
  it("defers below-fold analytical queries until first-screen balance signals settle", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const overviewDeferred = createDeferred<ApiEnvelope<BalanceAnalysisOverviewPayload>>();
    const workbookDeferred = createDeferred<ApiEnvelope<BalanceAnalysisWorkbookPayload>>();
    const decisionItemsDeferred = createDeferred<ApiEnvelope<BalanceAnalysisDecisionItemsPayload>>();

    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: {
        report_dates: ["2025-12-31"],
      },
    }));
    const getOverviewSpy = vi.fn(() => overviewDeferred.promise);
    const getWorkbookSpy = vi.fn(() => workbookDeferred.promise);
    const getDecisionItemsSpy = vi.fn(() => decisionItemsDeferred.promise);
    const getDetailSpy = vi.fn(async (): Promise<ApiEnvelope<BalanceAnalysisPayload>> => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all",
        currency_basis: "CNY",
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getBasisBreakdownSpy = vi.fn(
      async (): Promise<ApiEnvelope<BalanceAnalysisBasisBreakdownPayload>> => ({
        result_meta: buildMeta("balance-analysis.basis-breakdown", "tr_balance_basis"),
        result: {
          report_date: "2025-12-31",
          position_scope: "all",
          currency_basis: "CNY",
          rows: [],
        },
      }),
    );
    const getAdvancedAttributionSpy = vi.fn(
      async (): Promise<ApiEnvelope<BalanceAnalysisAdvancedAttributionBundlePayload>> => ({
        result_meta: buildMeta("balance-analysis.advanced-attribution", "tr_balance_advanced"),
        result: {
          report_date: "2025-12-31",
          mode: "analytical",
          scenario_name: null,
          scenario_inputs: {},
          upstream_summaries: {},
          status: "not_ready",
          missing_inputs: [],
          blocked_components: [],
          warnings: [],
        },
      }),
    );
    const getAdbComparisonSpy = vi.fn(async () => ({
      report_date: "2025-12-31",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      num_days: 365,
      simulated: false,
      total_spot_assets: 0,
      total_avg_assets: 0,
      total_spot_liabilities: 0,
      total_avg_liabilities: 0,
      asset_yield: null,
      liability_cost: null,
      net_interest_margin: null,
      assets_breakdown: [],
      liabilities_breakdown: [],
    }));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisWorkbook: getWorkbookSpy,
      getBalanceAnalysisDecisionItems: getDecisionItemsSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
      getBalanceAnalysisSummaryByBasis: getBasisBreakdownSpy,
      getBalanceAnalysisAdvancedAttribution: getAdvancedAttributionSpy,
      getAdbComparison: getAdbComparisonSpy,
    });

    await waitFor(() => {
      expect(getOverviewSpy).toHaveBeenCalled();
      expect(getWorkbookSpy).toHaveBeenCalled();
      expect(getDecisionItemsSpy).toHaveBeenCalled();
    });

    expect(getDetailSpy).not.toHaveBeenCalled();
    expect(getSummarySpy).not.toHaveBeenCalled();
    expect(getBasisBreakdownSpy).not.toHaveBeenCalled();
    expect(getAdvancedAttributionSpy).not.toHaveBeenCalled();
    expect(getAdbComparisonSpy).not.toHaveBeenCalled();

    overviewDeferred.resolve({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all",
        currency_basis: "CNY",
        detail_row_count: 0,
        summary_row_count: 0,
        total_market_value_amount: "0.00",
        total_amortized_cost_amount: "0.00",
        total_accrued_interest_amount: "0.00",
      },
    });
    workbookDeferred.resolve(buildWorkbookResponse());
    decisionItemsDeferred.resolve(buildDecisionItemsResponse());

    await waitFor(() => {
      expect(getDetailSpy).toHaveBeenCalled();
      expect(getSummarySpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        limit: 2,
        offset: 0,
      });
      expect(getBasisBreakdownSpy).toHaveBeenCalled();
      expect(getAdvancedAttributionSpy).toHaveBeenCalled();
      expect(getAdbComparisonSpy).toHaveBeenCalledWith("2025-01-01", "2025-12-31");
    });
  });

  it("renders cockpit cards and a paginated summary table from the dedicated summary query", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: {
        report_dates: ["2025-12-31"],
      },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "asset" as const,
        currency_basis: "CNY" as const,
        detail_row_count: 7,
        summary_row_count: 3,
        total_market_value_amount: "99999000000.00",
        total_amortized_cost_amount: "88888000000.00",
        total_accrued_interest_amount: "7777000000.00",
      },
    }));
    const getDetailSpy = vi.fn(async (): Promise<ApiEnvelope<BalanceAnalysisPayload>> => {
      const details: BalanceAnalysisDetailRow[] = [
        {
          source_family: "zqtz",
          report_date: "2025-12-31",
          row_key: "zqtz:detail-1",
          display_name: "240001.IB",
          position_scope: "asset",
          currency_basis: "CNY",
          invest_type_std: "A",
          accounting_basis: "FVOCI",
          market_value_amount: "333925726735.544",
          amortized_cost_amount: "327352769214.272",
          accrued_interest_amount: "25793215.37",
          is_issuance_like: false,
        },
      ];
      return {
        result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
        result: {
          report_date: "2025-12-31",
          position_scope: "all",
          currency_basis: "CNY",
          details,
          summary: [
            {
              source_family: "tyw",
              position_scope: "asset",
              currency_basis: "CNY",
              row_count: 174,
              market_value_amount: "24145782559.52",
              amortized_cost_amount: "24145782559.52",
              accrued_interest_amount: "186447192.86",
            },
            {
              source_family: "tyw",
              position_scope: "liability",
              currency_basis: "CNY",
              row_count: 2125,
              market_value_amount: "64768888887.83",
              amortized_cost_amount: "64768888887.83",
              accrued_interest_amount: "13996586.21",
            },
            {
              source_family: "zqtz",
              position_scope: "asset",
              currency_basis: "CNY",
              row_count: 1711,
              market_value_amount: "333925726735.544",
              amortized_cost_amount: "327352769214.272",
              accrued_interest_amount: "25793215.37",
            },
            {
              source_family: "zqtz",
              position_scope: "liability",
              currency_basis: "CNY",
              row_count: 129,
              market_value_amount: "119804097177.69",
              amortized_cost_amount: "120453500738.43",
              accrued_interest_amount: "0E-8",
            },
          ],
        },
      };
    });
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getWorkbookSpy = vi.fn(async () => buildWorkbookResponse());
    const getAdbComparisonSpy = vi.fn(async () => ({
      report_date: "2025-12-31",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      num_days: 365,
      simulated: false,
      total_spot_assets: 1200000000,
      total_avg_assets: 1100000000,
      total_spot_liabilities: 600000000,
      total_avg_liabilities: 550000000,
      asset_yield: 2.45,
      liability_cost: 1.62,
      net_interest_margin: 0.83,
      assets_breakdown: [],
      liabilities_breakdown: [],
    }));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
      getBalanceAnalysisWorkbook: getWorkbookSpy,
      getBalanceAnalysisDecisionItems: vi.fn(async () => buildDecisionItemsResponse()),
      getAdbComparison: getAdbComparisonSpy,
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();
    expect(screen.getByTestId("balance-analysis-page-title")).toHaveTextContent("资产负债分析");
    expect(screen.getByTestId("balance-analysis-page-subtitle")).toHaveTextContent(
      "formal / analytical",
    );
    expect(screen.getByRole("heading", { name: "正式状态摘要" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前行动信号" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "正式汇总驾驶舱" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "工作簿与治理侧栏" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("资产市值合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("3,580.72");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("负债市值合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("1,845.73");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("资产摊余成本合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("3,514.99");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("负债摊余成本合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("1,852.22");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("资产应计利息合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("2.12");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("负债应计利息合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("0.14");
      expect(screen.getByTestId("balance-analysis-overview-cards")).not.toHaveTextContent("总市值合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).not.toHaveTextContent("999.99");
      expect(screen.getByTestId("balance-analysis-overview-cards")).not.toHaveTextContent("888.88");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("债券资产(剔除发行类)");
      expect(screen.getByTestId("balance-analysis-overview-cards")).not.toHaveTextContent("99.00 万元");
      expect(screen.getByTestId("balance-analysis-overview-cards")).not.toHaveTextContent("市场资产");
      expect(screen.getByTestId("balance-analysis-summary")).toHaveTextContent("3,580.72");
      expect(screen.getByTestId("balance-analysis-summary")).toHaveTextContent("1,845.73");
      expect(screen.getByTestId("balance-analysis-summary")).toHaveTextContent("7");
      expect(screen.getByTestId("balance-analysis-summary")).toHaveTextContent("3");
    });

    expect(screen.getByTestId("balance-analysis-priority-board")).toHaveTextContent(
      "Review 1-2 year gap positioning",
    );
    expect(screen.getByTestId("balance-analysis-priority-board")).toHaveTextContent(
      "Negative gap in 1-2 year bucket",
    );
    expect(screen.getByTestId("balance-analysis-priority-board")).toHaveTextContent(
      "240001.IB maturity",
    );

    expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("利率债组合");
    expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("同业负债池");
    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("规模(亿元)");
      expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("720.00");
      expect(screen.getByTestId("balance-analysis-summary-table")).not.toHaveTextContent(
        "72,000,000,000.00",
      );
      expect(screen.getByTestId("balance-analysis-detail-summary-grid")).toHaveTextContent("市值(亿元)");
      expect(screen.getByTestId("balance-analysis-detail-summary-grid")).toHaveTextContent("241.46");
      expect(screen.getByTestId("balance-analysis-detail-summary-grid")).toHaveTextContent("647.69");
      expect(screen.getByTestId("balance-analysis-detail-summary-grid")).toHaveTextContent("3,339.26");
      expect(screen.getByTestId("balance-analysis-detail-summary-grid")).toHaveTextContent("0.00");
      expect(screen.getByTestId("balance-analysis-detail-summary-grid")).not.toHaveTextContent(
        "24,145,782,559.52",
      );
      expect(screen.getByTestId("balance-analysis-table")).toHaveTextContent("规模(亿元)");
      expect(screen.getByTestId("balance-analysis-table")).toHaveTextContent("3,339.26");
      expect(screen.getByTestId("balance-analysis-table")).not.toHaveTextContent("333,925,726,735.544");
    });
    await waitFor(() => {
      expect(screen.queryByTestId("balance-analysis-workbook-cards")).not.toBeInTheDocument();
      expect(screen.getByTestId("balance-analysis-workbook-primary-grid")).toBeInTheDocument();
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-bond_business_types"),
      ).toHaveTextContent("政策性金融债");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-bond_business_types"),
      ).toHaveTextContent("648.22 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-rating_analysis"),
      ).toHaveTextContent("AAA");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-rating_analysis"),
      ).toHaveTextContent("1,696.09 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-maturity_gap"),
      ).toHaveTextContent("1-2年");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-maturity_gap"),
      ).toHaveTextContent("429.04 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-issuance_business_types"),
      ).toHaveTextContent("同业存单");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-issuance_business_types"),
      ).toHaveTextContent("993.30 亿元");
      expect(screen.getByTestId("balance-analysis-workbook-secondary-panels")).toBeInTheDocument();
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-industry_distribution"),
      ).toHaveTextContent("金融业");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-industry_distribution"),
      ).toHaveTextContent("1,948.40 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-rate_distribution"),
      ).toHaveTextContent("1.5%-2.0%");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-rate_distribution"),
      ).toHaveTextContent("990.08 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-rate_distribution"),
      ).toHaveTextContent("95.80 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-rate_distribution"),
      ).toHaveTextContent("220.61 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-counterparty_types"),
      ).toHaveTextContent("股份制银行");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-counterparty_types"),
      ).toHaveTextContent("资产 12.00 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-counterparty_types"),
      ).toHaveTextContent("负债 8.61 亿元");
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-counterparty_types"),
      ).toHaveTextContent("净头寸 3.39 亿元");
      expect(screen.getByTestId("balance-analysis-workbook-secondary-grid")).toHaveTextContent(
        "计息方式",
      );
      expect(screen.getByTestId("balance-analysis-workbook-secondary-grid")).toHaveTextContent("流动性桶指标");
      expect(screen.getByTestId("balance-analysis-workbook-secondary-grid")).toHaveTextContent("123.46");
      expect(screen.getByTestId("balance-analysis-workbook-secondary-grid")).toHaveTextContent("234.57");
      expect(screen.getByTestId("balance-analysis-workbook-secondary-grid")).toHaveTextContent("345.68");
      expect(screen.getByTestId("balance-analysis-workbook-secondary-grid")).not.toHaveTextContent(
        "1,234,567.89",
      );
      expect(screen.getByTestId("balance-analysis-right-rail")).toBeInTheDocument();
      expect(screen.getByTestId("balance-analysis-right-rail-panel-decision_items")).toHaveTextContent(
        "Review 1-2 year gap positioning",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-decision_items")).toHaveTextContent(
        "Bucket gap is 429.04 亿元.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-event_calendar")).toHaveTextContent(
        "240001.IB maturity",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).toHaveTextContent(
        "Negative gap in 1-2 year bucket",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).toHaveTextContent(
        "Gap dropped to -12.80 亿元.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).toHaveTextContent(
        "Issuance book totals 0.00 亿元.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail")).not.toHaveTextContent("wan yuan");
      expect(
        within(screen.getByTestId("balance-analysis-right-rail-panel-event_calendar")).getByLabelText(
          "balance-event-type-filter",
        ),
      ).toBeInTheDocument();
      expect(
        within(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).getByLabelText(
          "balance-risk-severity-filter",
        ),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("真实数据场景阅读")).toBeInTheDocument();
    expect(screen.queryByText("情景演示与静态参考")).not.toBeInTheDocument();
    expect(screen.getByTestId("balance-analysis-summary-row")).toHaveTextContent(
      "资产端合计 3,287.80 亿元",
    );
    expect(screen.getByTestId("balance-analysis-summary-row")).not.toHaveTextContent(
      "资产以债券投资为主，占市场资产 93.3%",
    );
    expect(screen.getByTestId("balance-analysis-contribution-row")).toHaveTextContent(
      "Review 1-2 year gap positioning",
    );
    expect(screen.getByTestId("balance-analysis-bottom-row")).toHaveTextContent("repo-1 maturity");
    expect(screen.getByText("第 1 / 2 页")).toBeInTheDocument();

    await waitFor(() => {
      expect(getSummarySpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        limit: 2,
        offset: 0,
      });
    });

    await userEvent.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => {
      expect(getSummarySpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        limit: 2,
        offset: 2,
      });
      expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("高等级组合");
      expect(screen.getByText("第 2 / 2 页")).toBeInTheDocument();
    });

    expect(screen.getByTestId("balance-analysis-result-meta-overview")).toHaveTextContent("formal");
    expect(screen.getByTestId("balance-analysis-result-meta-overview")).toHaveTextContent(
      "balance-analysis.overview",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-workbook")).toHaveTextContent(
      "balance-analysis.workbook",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-summary")).toHaveTextContent(
      "balance-analysis.summary",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-summary")).toHaveTextContent(
      "tr_balance_summary_2",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-detail")).toHaveTextContent(
      "balance-analysis.detail",
    );
    expect(screen.getByTestId("balance-analysis-adb-preview")).toHaveTextContent("ADB Analytical Preview");
    expect(screen.getByTestId("balance-analysis-adb-preview")).toHaveTextContent("Spot vs ADB 偏离对比");
    expect(screen.getByTestId("balance-analysis-adb-preview")).toHaveTextContent("ADB 月度结构预览");
    expect(
      within(screen.getByTestId("balance-analysis-adb-preview")).getAllByTestId(
        "balance-analysis-echarts-stub",
      ),
    ).toHaveLength(2);
    expect(
      within(screen.getByTestId("balance-analysis-adb-preview")).getAllByTestId(
        "adb-monthly-breakdown-table",
      ),
    ).toHaveLength(1);
    expect(screen.getByRole("link", { name: "打开 ADB 分析页" })).toHaveAttribute(
      "href",
      "/average-balance?report_date=2025-12-31",
    );
    expect(getAdbComparisonSpy).toHaveBeenCalledWith("2025-01-01", "2025-12-31");
  });

  it("hydrates report filters from query parameters", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates_query"),
      result: {
        report_dates: ["2025-12-31", "2025-11-30"],
      },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview_query"),
      result: {
        report_date: "2025-11-30",
        position_scope: "liability" as const,
        currency_basis: "native" as const,
        detail_row_count: 1,
        summary_row_count: 1,
        total_market_value_amount: "1000000000.00",
        total_amortized_cost_amount: "1000000000.00",
        total_accrued_interest_amount: "100000000.00",
      },
    }));
    const getDetailSpy = vi.fn(async (): Promise<ApiEnvelope<BalanceAnalysisPayload>> => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail_query"),
      result: {
        report_date: "2025-11-30",
        position_scope: "liability",
        currency_basis: "native",
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getWorkbookSpy = vi.fn(async () => buildWorkbookResponse());

    renderBalanceAnalysisWithClient(
      {
        ...baseClient,
        getBalanceAnalysisDates: getDatesSpy,
        getBalanceAnalysisOverview: getOverviewSpy,
        getBalanceAnalysisDetail: getDetailSpy,
        getBalanceAnalysisSummary: getSummarySpy,
        getBalanceAnalysisWorkbook: getWorkbookSpy,
      },
      ["/balance-analysis?report_date=2025-11-30&position_scope=liability&currency_basis=native"],
    );

    await waitFor(() => {
      expect(getOverviewSpy).toHaveBeenCalledWith({
        reportDate: "2025-11-30",
        positionScope: "liability",
        currencyBasis: "native",
      });
    });
  });

  it("reacts to query-string scope and currency updates while mounted", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates_query_update"),
      result: {
        report_dates: ["2025-12-31", "2025-11-30"],
      },
    }));
    const getOverviewSpy = vi.fn(async ({ reportDate, positionScope, currencyBasis }) => ({
      result_meta: buildMeta("balance-analysis.overview", `tr_balance_overview_${reportDate}_${positionScope}_${currencyBasis}`),
      result: {
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
        detail_row_count: 1,
        summary_row_count: 1,
        total_market_value_amount: "1000000000.00",
        total_amortized_cost_amount: "1000000000.00",
        total_accrued_interest_amount: "100000000.00",
      },
    }));
    const getDetailSpy = vi.fn(async ({ reportDate, positionScope, currencyBasis }): Promise<ApiEnvelope<BalanceAnalysisPayload>> => ({
      result_meta: buildMeta("balance-analysis.detail", `tr_balance_detail_${reportDate}_${positionScope}_${currencyBasis}`),
      result: {
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getWorkbookSpy = vi.fn(async () => buildWorkbookResponse());
    let currentSearch = "report_date=2025-11-30&position_scope=liability&currency_basis=native";
    const useSearchParamsSpy = vi
      .spyOn(ReactRouterDom, "useSearchParams")
      .mockImplementation(
        () => [new URLSearchParams(currentSearch), vi.fn()] as ReturnType<typeof ReactRouterDom.useSearchParams>,
      );

    const client = {
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
      getBalanceAnalysisWorkbook: getWorkbookSpy,
    };

    const rendered = renderBalanceAnalysisWithClient(client, ["/balance-analysis"]);

    await waitFor(() => {
      expect(getOverviewSpy).toHaveBeenCalledWith({
        reportDate: "2025-11-30",
        positionScope: "liability",
        currencyBasis: "native",
      });
    });

    currentSearch = "report_date=2025-12-31&position_scope=asset&currency_basis=CNY";
    rendered.rerender(
      <ApiClientProvider client={client}>
        <QueryClientProvider client={rendered.queryClient}>
          <RouterProvider router={rendered.router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    await waitFor(() => {
      expect(getOverviewSpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "asset",
        currencyBasis: "CNY",
      });
      expect(getDetailSpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "asset",
        currencyBasis: "CNY",
      });
    });

    useSearchParamsSpy.mockRestore();
  });

  it("downloads the filtered summary export as csv", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportSpy = vi.fn(async () => ({
      filename: "balance-analysis-summary-2025-12-31-asset-CNY.csv",
      content: "row_key,display_name\nrow-1,240001.IB\n",
    }));
    const createObjectUrl = vi.fn(() => "blob:balance-analysis");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    const originalCreateElement = document.createElement.bind(document);

    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          configurable: true,
          value: clickSpy,
        });
      }
      return element;
    }) as typeof document.createElement);

    try {
      renderBalanceAnalysisWithClient({
        ...baseClient,
        exportBalanceAnalysisSummaryCsv: exportSpy,
      });

      await screen.findByRole("heading", { name: "资产负债分析" });
      await user.selectOptions(screen.getByLabelText("balance-position-scope"), "asset");
      await user.click(screen.getByTestId("balance-analysis-export-button"));

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith({
          reportDate: "2025-12-31",
          positionScope: "asset",
          currencyBasis: "CNY",
        });
        expect(createObjectUrl).toHaveBeenCalledTimes(1);
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(revokeObjectUrl).toHaveBeenCalledWith("blob:balance-analysis");
      });
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
      vi.restoreAllMocks();
    }
  });

  it("downloads the filtered workbook export as xlsx", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookBlob = new Blob(["xlsx-binary"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const exportSpy = vi.fn(async () => ({
      filename: "资产负债分析_2025-12-31.xlsx",
      content: workbookBlob,
    }));
    const createObjectUrl = vi.fn(() => "blob:balance-analysis-workbook");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    const originalCreateElement = document.createElement.bind(document);

    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          configurable: true,
          value: clickSpy,
        });
      }
      return element;
    }) as typeof document.createElement);

    try {
      renderBalanceAnalysisWithClient({
        ...baseClient,
        exportBalanceAnalysisWorkbookXlsx: exportSpy,
      });

      await screen.findByTestId("balance-analysis-workbook-export-button");
      await user.selectOptions(screen.getByLabelText("balance-position-scope"), "asset");
      await user.click(screen.getByTestId("balance-analysis-workbook-export-button"));

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith({
          reportDate: "2025-12-31",
          positionScope: "asset",
          currencyBasis: "CNY",
        });
        expect(createObjectUrl).toHaveBeenCalledWith(workbookBlob);
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(revokeObjectUrl).toHaveBeenCalledWith("blob:balance-analysis-workbook");
      });
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
      vi.restoreAllMocks();
    }
  });

  it("keeps the summary cockpit available when detail drill-down fails", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDetailSpy = vi.fn(async () => {
      throw new Error("detail unavailable");
    });

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisWorkbook: vi.fn(async () => buildWorkbookResponse()),
      getBalanceAnalysisSummary: vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset)),
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("利率债组合");
      expect(screen.getByTestId("balance-analysis-workbook-primary-grid")).toBeInTheDocument();
      expect(screen.getByText("明细下钻暂时不可用，汇总驾驶舱仍可继续使用。")).toBeInTheDocument();
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("市值合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("1,202.00");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("1,123.00");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("70.40");
      expect(screen.getByTestId("balance-analysis-overview-cards")).not.toHaveTextContent("资产市值合计");
    });
  });

  it("shows a contract mismatch warning when workbook primary fields are missing", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const malformedWorkbook = buildWorkbookResponse();
    malformedWorkbook.result.tables[0] = {
      ...malformedWorkbook.result.tables[0],
      rows: [{ bond_type: "政策性金融债" }],
    };

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisWorkbook: vi.fn(async () => malformedWorkbook),
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByTestId("balance-analysis-workbook-panel-bond_business_types"),
      ).toHaveTextContent("Workbook contract mismatch");
    });
  });

  it("shows a contract mismatch warning when right-rail explainability fields are missing", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const malformedDecisionItems = buildDecisionItemsResponse() as {
      result: { rows: Array<Record<string, unknown>> };
    };
    malformedDecisionItems.result.rows = [
      {
        decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
        title: "Review 1-2 year gap positioning",
        action_label: "Review gap",
        severity: "high",
        reason: "Bucket gap is 4290357.07 wan yuan.",
        source_section: "maturity_gap",
        rule_id: "bal_wb_decision_gap_001",
        rule_version: "v1",
      },
    ];

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDecisionItems: vi.fn(async () => malformedDecisionItems as never),
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByTestId("balance-analysis-right-rail-panel-decision_items"),
      ).toHaveTextContent("Workbook contract mismatch");
    });
  });

  it("renders independent right-rail empty states without breaking the workbook cockpit", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const workbook = buildWorkbookResponse();
    workbook.result.tables = workbook.result.tables.map((table) => {
      if (
        table.key === "decision_items" ||
        table.key === "event_calendar" ||
        table.key === "risk_alerts"
      ) {
        return { ...table, rows: [] };
      }
      return table;
    });
    workbook.result.operational_sections = workbook.result.operational_sections.map((table) => {
      if (
        table.key === "decision_items" ||
        table.key === "event_calendar" ||
        table.key === "risk_alerts"
      ) {
        return { ...table, rows: [] };
      }
      return table;
    });
    const emptyDecisionItems = buildDecisionItemsResponse({
      rows: [],
    });

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisWorkbook: vi.fn(async () => workbook),
      getBalanceAnalysisDecisionItems: vi.fn(async () => emptyDecisionItems),
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-panel-decision_items")).toHaveTextContent(
        "No governed items.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-event_calendar")).toHaveTextContent(
        "No governed items.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).toHaveTextContent(
        "No governed items.",
      );
      expect(screen.getByTestId("balance-analysis-workbook-primary-grid")).toBeInTheDocument();
    });
  });

  it("filters event calendar and risk alerts and shows drill-down details", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisWorkbook: vi.fn(async () => buildWorkbookResponse()),
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();

    await user.selectOptions(await screen.findByLabelText("balance-event-type-filter"), "funding_rollover");

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-panel-event_calendar")).toHaveTextContent(
        "repo-1 maturity",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-event_calendar")).not.toHaveTextContent(
        "240001.IB maturity",
      );
    });

    await user.click(screen.getByRole("button", { name: /repo-1 maturity/ }));

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-event")).toHaveTextContent(
        "repo-1 maturity",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-event")).toHaveTextContent(
        "funding_rollover",
      );
    });

    await user.selectOptions(await screen.findByLabelText("balance-risk-severity-filter"), "medium");

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).toHaveTextContent(
        "Issuance liabilities outstanding",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).not.toHaveTextContent(
        "Negative gap in 1-2 year bucket",
      );
    });

    await user.click(screen.getByRole("button", { name: /Issuance liabilities outstanding/ }));

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-risk")).toHaveTextContent(
        "Issuance liabilities outstanding",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-risk")).toHaveTextContent(
        "Issuance book totals 0.00 亿元.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-risk")).toHaveTextContent(
        "bal_wb_risk_issuance_001",
      );
    });
  });

  it("confirms decision items and shows latest governed status in drill-down", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getDecisionItemsSpy = vi
      .fn()
      .mockResolvedValueOnce(buildDecisionItemsResponse())
      .mockResolvedValueOnce(
        buildDecisionItemsResponse({
          rows: [
            {
              decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
              title: "Review 1-2 year gap positioning",
              action_label: "Review gap",
              severity: "high",
              reason: "Bucket gap is 4290357.07 wan yuan.",
              source_section: "maturity_gap",
              rule_id: "bal_wb_decision_gap_001",
              rule_version: "v1",
              latest_status: {
                decision_key:
                  "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
                status: "confirmed",
                updated_at: "2026-04-12T08:00:00Z",
                updated_by: "phase1-dev-user",
                comment: "Reviewed and accepted.",
              },
            },
          ],
        }),
      );
    const updateDecisionSpy = vi.fn(async () => ({
      decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
      status: "confirmed" as const,
      updated_at: "2026-04-12T08:00:00Z",
      updated_by: "phase1-dev-user",
      comment: "Reviewed and accepted.",
    }));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisWorkbook: vi.fn(async () => buildWorkbookResponse()),
      getBalanceAnalysisCurrentUser: vi.fn(async () => buildCurrentUserResponse()),
      getBalanceAnalysisDecisionItems: getDecisionItemsSpy,
      updateBalanceAnalysisDecisionStatus: updateDecisionSpy,
    });

    expect(await screen.findByTestId("balance-analysis-right-rail")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-panel-decision_items")).toHaveTextContent(
        "Review 1-2 year gap positioning",
      );
      expect(screen.getByTestId("balance-analysis-current-user")).toHaveTextContent(
        "phase1-dev-user",
      );
      expect(screen.getByTestId("balance-analysis-decision-view-status-0")).toBeInTheDocument();
      expect(screen.getByTestId("balance-analysis-decision-confirm-0")).toBeInTheDocument();
      expect(screen.getByTestId("balance-analysis-decision-dismiss-0")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("balance-analysis-decision-view-status-0"));

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "Bucket gap is 429.04 亿元.",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "bal_wb_decision_gap_001",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "pending",
      );
    });

    await user.click(screen.getByTestId("balance-analysis-decision-confirm-0"));

    await waitFor(() => {
      expect(updateDecisionSpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        decisionKey: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
        status: "confirmed",
      });
      expect(getDecisionItemsSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "confirmed",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "phase1-dev-user",
      );
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "Reviewed and accepted.",
      );
    });
  });

  it("keeps the governed rail available when current-user lookup fails", async () => {
    const baseClient = createApiClient({ mode: "mock" });

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisCurrentUser: vi.fn(async () => {
        throw new Error("current user unavailable");
      }),
      getBalanceAnalysisWorkbook: vi.fn(async () => buildWorkbookResponse()),
      getBalanceAnalysisDecisionItems: vi.fn(async () => buildDecisionItemsResponse()),
    });

    expect(await screen.findByTestId("balance-analysis-right-rail")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-right-rail-panel-decision_items")).toHaveTextContent(
        "Review 1-2 year gap positioning",
      );
      expect(screen.queryByTestId("balance-analysis-current-user")).not.toBeInTheDocument();
      expect(screen.getByTestId("balance-analysis-right-rail-panel-event_calendar")).toHaveTextContent(
        "240001.IB maturity",
      );
    });
  });

  it("refreshes current-user identity after decision status updates", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getCurrentUserSpy = vi
      .fn()
      .mockResolvedValueOnce({
        user_id: "phase1-dev-user",
        role: "admin",
        identity_source: "fallback" as const,
      })
      .mockResolvedValueOnce({
        user_id: "header-user",
        role: "reviewer",
        identity_source: "header" as const,
      });
    const getDecisionItemsSpy = vi
      .fn()
      .mockResolvedValueOnce(buildDecisionItemsResponse())
      .mockResolvedValueOnce(
        buildDecisionItemsResponse({
          rows: [
            {
              decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
              title: "Review 1-2 year gap positioning",
              action_label: "Review gap",
              severity: "high",
              reason: "Bucket gap is 4290357.07 wan yuan.",
              source_section: "maturity_gap",
              rule_id: "bal_wb_decision_gap_001",
              rule_version: "v1",
              latest_status: {
                decision_key:
                  "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
                status: "confirmed",
                updated_at: "2026-04-12T08:00:00Z",
                updated_by: "header-user",
                comment: "Reviewed and accepted.",
              },
            },
          ],
        }),
      );

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisCurrentUser: getCurrentUserSpy,
      getBalanceAnalysisWorkbook: vi.fn(async () => buildWorkbookResponse()),
      getBalanceAnalysisDecisionItems: getDecisionItemsSpy,
      updateBalanceAnalysisDecisionStatus: vi.fn(async () => ({
        decision_key: "bal_wb_decision_gap_001:maturity_gap:Review 1-2 year gap positioning",
        status: "confirmed" as const,
        updated_at: "2026-04-12T08:00:00Z",
        updated_by: "header-user",
        comment: "Reviewed and accepted.",
      })),
    });

    expect(await screen.findByTestId("balance-analysis-current-user")).toHaveTextContent(
      "phase1-dev-user",
    );

    await user.click(screen.getByTestId("balance-analysis-decision-confirm-0"));

    await waitFor(() => {
      expect(getCurrentUserSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("balance-analysis-current-user")).toHaveTextContent("header-user");
      expect(screen.getByTestId("balance-analysis-right-rail-drilldown-decision")).toHaveTextContent(
        "header-user",
      );
    });
  });

  it("polls refresh status and refetches overview detail and summary after rebuild", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "balance_analysis_materialize:test-run",
      job_name: "balance_analysis_materialize",
      trigger_mode: "async",
      cache_key: "balance_analysis:materialize:formal",
      report_date: "2025-12-31",
    }));
    const statusSpy = vi
      .fn()
      .mockResolvedValueOnce({
        status: "running",
        run_id: "balance_analysis_materialize:test-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "async",
        cache_key: "balance_analysis:materialize:formal",
      })
      .mockResolvedValueOnce({
        status: "completed",
        run_id: "balance_analysis_materialize:test-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "terminal",
        cache_key: "balance_analysis:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_balance",
      });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: {
        report_dates: ["2025-12-31"],
      },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "asset" as const,
        currency_basis: "CNY" as const,
        detail_row_count: 0,
        summary_row_count: 0,
        total_market_value_amount: "0.00",
        total_amortized_cost_amount: "0.00",
        total_accrued_interest_amount: "0.00",
      },
    }));
    const getDetailSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
      result: {
        report_date: "2025-12-31",
        position_scope: "asset" as const,
        currency_basis: "CNY" as const,
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getAdbComparisonSpy = vi.fn(async () => ({
      report_date: "2025-12-31",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      num_days: 365,
      simulated: false,
      total_spot_assets: 1200000000,
      total_avg_assets: 1100000000,
      total_spot_liabilities: 600000000,
      total_avg_liabilities: 550000000,
      asset_yield: 2.45,
      liability_cost: 1.62,
      net_interest_margin: 0.83,
      assets_breakdown: [],
      liabilities_breakdown: [],
    }));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
      getAdbComparison: getAdbComparisonSpy,
      refreshBalanceAnalysis: refreshSpy,
      getBalanceAnalysisRefreshStatus: statusSpy,
    });

    await screen.findByRole("heading", { name: "资产负债分析" });
    await user.click(screen.getByTestId("balance-analysis-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith("2025-12-31");
      expect(statusSpy).toHaveBeenCalledWith("balance_analysis_materialize:test-run");
      expect(screen.getByText(/balance_analysis_materialize:test-run/)).toBeInTheDocument();
      expect(getDatesSpy.mock.calls.length).toBeGreaterThan(1);
      expect(getOverviewSpy.mock.calls.length).toBeGreaterThan(1);
      expect(getDetailSpy.mock.calls.length).toBeGreaterThan(1);
      expect(getSummarySpy.mock.calls.length).toBeGreaterThan(1);
      expect(getAdbComparisonSpy.mock.calls.length).toBeGreaterThan(1);
    });
  });

  it("surfaces invalid overview amounts as text and does not show a minimum-width bar for invalid workbook magnitudes", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: { report_dates: ["2025-12-31"] },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "asset" as const,
        currency_basis: "CNY" as const,
        detail_row_count: 0,
        summary_row_count: 0,
        total_market_value_amount: "NOT_A_NUMERIC_KPI",
        total_amortized_cost_amount: "0.00",
        total_accrued_interest_amount: "0.00",
      },
    }));
    const getDetailSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getWorkbookSpy = vi.fn(async () => {
      const envelope = buildWorkbookResponse();
      const bond = envelope.result.tables.find((t) => t.key === "bond_business_types");
      if (bond) {
        bond.rows = [
          { bond_type: "规模正常", balance_amount: "200" },
          { bond_type: "脏数据", balance_amount: "not-a-magnitude" },
        ];
      }
      return envelope;
    });
    const getAdbComparisonSpy = vi.fn(async () => ({
      report_date: "2025-12-31",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      num_days: 365,
      simulated: false,
      total_spot_assets: 0,
      total_avg_assets: 0,
      total_spot_liabilities: 0,
      total_avg_liabilities: 0,
      asset_yield: 0,
      liability_cost: 0,
      net_interest_margin: 0,
      assets_breakdown: [],
      liabilities_breakdown: [],
    }));

    renderBalanceAnalysisWithClient(
      {
        ...baseClient,
        getBalanceAnalysisDates: getDatesSpy,
        getBalanceAnalysisOverview: getOverviewSpy,
        getBalanceAnalysisDetail: getDetailSpy,
        getBalanceAnalysisSummary: getSummarySpy,
        getBalanceAnalysisWorkbook: getWorkbookSpy,
        getAdbComparison: getAdbComparisonSpy,
      },
      ["/balance-analysis?position_scope=asset"],
    );

    await screen.findByRole("heading", { name: "资产负债分析" });

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("资产市值合计");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("NOT_A_NUMERIC_KPI");
    });

    const panel = await screen.findByTestId("balance-analysis-workbook-panel-bond_business_types");
    expect(panel).toHaveTextContent("not-a-magnitude");
    const bar0 = within(panel).getByTestId("balance-analysis-distribution-bar-bond_business_types-0");
    const bar1 = within(panel).getByTestId("balance-analysis-distribution-bar-bond_business_types-1");
    expect(bar0).toHaveStyle({ width: "100%" });
    expect(bar1).toHaveStyle({ width: "0%" });
  });

  it("shows negative maturity gap amounts in text while bar width uses absolute magnitude", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: { report_dates: ["2025-12-31"] },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        detail_row_count: 0,
        summary_row_count: 0,
        total_market_value_amount: "0.00",
        total_amortized_cost_amount: "0.00",
        total_accrued_interest_amount: "0.00",
      },
    }));
    const getDetailSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));
    const getWorkbookSpy = vi.fn(async () => {
      const envelope = buildWorkbookResponse();
      const gap = envelope.result.tables.find((t) => t.key === "maturity_gap");
      if (gap) {
        gap.rows = [
          { bucket: "正缺口桶", gap_amount: "200" },
          { bucket: "负缺口桶", gap_amount: "-50" },
        ];
      }
      return envelope;
    });
    const getAdbComparisonSpy = vi.fn(async () => ({
      report_date: "2025-12-31",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      num_days: 365,
      simulated: false,
      total_spot_assets: 0,
      total_avg_assets: 0,
      total_spot_liabilities: 0,
      total_avg_liabilities: 0,
      asset_yield: 0,
      liability_cost: 0,
      net_interest_margin: 0,
      assets_breakdown: [],
      liabilities_breakdown: [],
    }));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
      getBalanceAnalysisWorkbook: getWorkbookSpy,
      getAdbComparison: getAdbComparisonSpy,
    });

    await screen.findByRole("heading", { name: "资产负债分析" });

    const panel = await screen.findByTestId("balance-analysis-workbook-panel-maturity_gap");
    expect(panel).toHaveTextContent("-0.01 亿元");
    expect(panel).toHaveTextContent("该期限桶为负缺口");

    const bar0 = within(panel).getByTestId("balance-analysis-maturity-gap-bar-maturity_gap-0");
    const bar1 = within(panel).getByTestId("balance-analysis-maturity-gap-bar-maturity_gap-1");
    expect(bar0).toHaveStyle({ width: "100%" });
    expect(bar1).toHaveStyle({ width: "25%" });
  });
});
