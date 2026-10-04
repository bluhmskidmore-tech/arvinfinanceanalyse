import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  Numeric,
  CampisiFourEffectsPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
  TPLMarketCorrelationPayload,
} from "../api/contracts";
import { ApiClientProvider, createApiClient } from "../api/client";
import PnlAttributionPage from "../features/pnl-attribution/pages/PnlAttributionPage";
import { mockCampisiFourEffectsModelPath } from "../mocks/campisiMocks";

vi.mock("../features/agent/AgentPanel", () => ({
  AgentPanel: (props: {
    pageId: string;
    reportDate?: string | null;
    currentFilters?: Record<string, unknown>;
    contextNote?: string | null;
    defaultQuestion?: string;
  }) => {
    return (
      <div
        data-testid="pnl-attribution-agent-panel-probe"
        data-page-id={props.pageId}
        data-report-date={props.reportDate ?? ""}
        data-default-question={props.defaultQuestion ?? ""}
        data-context-note={props.contextNote ?? ""}
      >
        {JSON.stringify(props.currentFilters ?? {})}
      </div>
    );
  },
}));

const PNL_ATTRIBUTION_THEME_SOURCE_PATHS = [
  "src/features/pnl-attribution/components/AdvancedAttributionChart.tsx",
  "src/features/pnl-attribution/components/AttributionWaterfallChart.tsx",
  "src/features/pnl-attribution/components/CampisiAttributionPanel.tsx",
  "src/features/pnl-attribution/components/CampisiEnhancedPanel.tsx",
  "src/features/pnl-attribution/components/CampisiMaturityBucketPanel.tsx",
  "src/features/pnl-attribution/components/PnlAttributionView.tsx",
  "src/features/pnl-attribution/components/PnLCompositionChart.tsx",
  "src/features/pnl-attribution/components/TPLMarketChart.tsx",
  "src/features/pnl-attribution/components/VolumeRateAnalysisChart.tsx",
].map((path) => resolve(process.cwd(), path));

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-attribution-echarts-stub" />,
}));

afterEach(() => {
  vi.unstubAllEnvs();
});

function buildResultMeta(resultKind: string, traceId = "tr_pnl_attribution_test"): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-02-28",
    generated_at: "2026-04-09T10:30:00Z",
    tables_used: [],
    filters_applied: {},
    evidence_rows: 1,
    next_drill: [],
  };
}

function numeric(raw: number | null, unit: Numeric["unit"] = "yuan", display = ""): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
  };
}

function productCategoryTplRow(reportDate: string, partial: Partial<ProductCategoryPnlRow> = {}): ProductCategoryPnlRow {
  return {
    category_id: "bond_tpl",
    category_name: "TPL",
    side: "asset",
    level: 1,
    view: "monthly",
    report_date: reportDate,
    baseline_ftp_rate_pct: "1.60",
    cnx_scale: "86507000000",
    cny_scale: "86605000000",
    foreign_scale: "-98000000",
    cnx_cash: "211000000",
    cny_cash: "211000000",
    foreign_cash: "0",
    cny_ftp: "114000000",
    foreign_ftp: "0",
    cny_net: "97000000",
    foreign_net: "1000000",
    business_net_income: "98000000",
    weighted_yield: "2.97",
    is_total: false,
    children: [],
    ...partial,
  };
}

function productCategoryPayload(reportDate: string): ProductCategoryPnlPayload {
  const row = productCategoryTplRow(reportDate);
  const total = productCategoryTplRow(reportDate, {
    category_id: "asset_total",
    category_name: "资产合计",
    is_total: true,
  });
  return {
    report_date: reportDate,
    view: "monthly",
    available_views: ["monthly", "ytd"],
    scenario_rate_pct: null,
    rows: [row],
    asset_total: total,
    liability_total: productCategoryTplRow(reportDate, {
      category_id: "liability_total",
      category_name: "负债合计",
      side: "liability",
      is_total: true,
    }),
    grand_total: productCategoryTplRow(reportDate, {
      category_id: "grand_total",
      category_name: "合计",
      is_total: true,
    }),
    interest_spread: {
      all_currency_asset_yield_pct: null,
      all_currency_liability_yield_pct: null,
      all_currency_spread_pct: null,
      cny_asset_yield_pct: null,
      cny_liability_yield_pct: null,
      cny_spread_pct: null,
    },
    interest_earning_spread: {
      all_currency_asset_yield_pct: null,
      all_currency_liability_yield_pct: null,
      all_currency_spread_pct: null,
      cny_asset_yield_pct: null,
      cny_liability_yield_pct: null,
      cny_spread_pct: null,
    },
    liability_cost_decomposition: {
      liability_yield_pct: null,
      liability_yield_ex_cln_pct: null,
      cln_yield_pct: null,
      cln_drag_bp: null,
      cln_scale: null,
    },
  };
}

function tplMarketPayload(): TPLMarketCorrelationPayload {
  return {
    start_period: "2026-02",
    end_period: "2026-03",
    num_periods: 2,
    correlation_coefficient: numeric(-0.62, "ratio"),
    correlation_interpretation: "test",
    total_tpl_fv_change: numeric(42_000_000),
    avg_treasury_10y_change: numeric(-7.5, "bp"),
    treasury_10y_total_change_bp: numeric(-15.0, "bp"),
    analysis_summary: "summary",
    data_points: [
      {
        period: "2026-02",
        period_label: "2026年2月",
        tpl_fair_value_change: numeric(10_000_000),
        tpl_total_pnl: numeric(10_000_000),
        tpl_scale: numeric(1_000_000_000),
        treasury_10y: numeric(0.0235, "pct", "+2.35%"),
        treasury_10y_change: numeric(null, "bp"),
        dr007: numeric(null, "pct"),
      },
      {
        period: "2026-03",
        period_label: "2026年3月",
        tpl_fair_value_change: numeric(32_000_000),
        tpl_total_pnl: numeric(32_000_000),
        tpl_scale: numeric(1_100_000_000),
        treasury_10y: numeric(0.022, "pct", "+2.20%"),
        treasury_10y_change: numeric(-15.0, "bp"),
        dr007: numeric(null, "pct"),
      },
    ],
  } as TPLMarketCorrelationPayload;
}

function PnlAttributionPageWithRouter({ initialEntry = "/" }: { initialEntry?: string }) {
  return <MemoryRouter initialEntries={[initialEntry]}><PnlAttributionPage /></MemoryRouter>;
}

function homeCampisiModelResult(): CampisiFourEffectsPayload {
  return {
    ...mockCampisiFourEffectsModelPath,
    report_date: "2026-08-31",
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    effect_availability: {
      bonds: 1854,
      position_change: {
        status: "partial",
        reason: "principal_change_without_cashflows",
        unavailable_bonds: 259,
        unavailable_market_value_start: 22_202_516_840,
        unavailable_market_value_end: 30_414_358_922,
        covered_bonds: 1595,
      },
      treasury_effect: {
        status: "unavailable",
        reason: "insufficient_shared_positive_tenors",
        unavailable_bonds: 1854,
        unavailable_market_value_start: 342_306_461_394,
        shared_positive_tenors: 0,
        min_required_shared_tenors: 2,
      },
      spread_effect: {
        status: "ok",
        reason: null,
        unavailable_bonds: 0,
        unavailable_market_value_start: 0,
      },
      accrued_interest: {
        status: "partial",
        reason: "accrued_interest_missing",
        unavailable_bonds: 163,
        unavailable_market_value_start: 8_667_755_223,
        basis: "mixed",
      },
    },
    formal_closure: {
      basis: "pnl.bridge.total_actual_pnl",
      report_date: "2026-08-31",
      status: "unavailable",
      campisi_total_return: mockCampisiFourEffectsModelPath.totals.total_return,
      formal_actual_pnl: null,
      residual_to_formal_pnl: null,
      residual_ratio: null,
      bridge_quality_flag: null,
      bridge_vendor_status: null,
      bridge_fallback_mode: null,
      message: "Formal PnL bridge unavailable for this window.",
    },
  };
}

describe("PnlAttributionPage", () => {
  it("opens the formal monthly home bridge and retains an upstream error despite closure", async () => {
    const client = createApiClient({ mode: "mock" });
    const model = homeCampisiModelResult();
    const result: CampisiFourEffectsPayload = {
      ...model,
      basis: "formal_report_pnl_bridge",
      period_start: "2026-07-31",
      effect_availability: {
        bonds: 2,
        treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        roll_down_availability: { status: "partial", applicable_rows: 2, unavailable_rows: 1, reasons: ["roll_window_missing"] },
        treasury_curve_availability: { status: "ok", applicable_rows: 2, unavailable_rows: 0, reasons: [] },
        credit_spread_availability: { status: "not_applicable", applicable_rows: 0, unavailable_rows: 0, reasons: ["not_credit_book"] },
      },
      input_quality: {
        ...model.input_quality,
        formal_bridge_coverage: { source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "ok", bridge_rows: 2, attributed_rows: 2 },
      },
      formal_closure: {
        ...model.formal_closure!,
        status: "closed",
        formal_actual_pnl: model.totals.total_return,
        residual_to_formal_pnl: 0,
        residual_ratio: 0,
        bridge_quality_flag: "error",
      },
    };
    const getFourEffects = vi.fn(async () => ({
      result_meta: { ...buildResultMeta("campisi.four_effects"), quality_flag: "error" as const, as_of_date: "2026-08-31" },
      result,
    }));
    client.getPnlCampisiFourEffects = getFourEffects;
    const getEnhanced = vi.fn(client.getPnlCampisiEnhanced.bind(client));
    client.getPnlCampisiEnhanced = getEnhanced;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter initialEntry="/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-07-31&campisi_end_date=2026-08-31" />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("campisi-bridge-quality-warning")).toHaveTextContent("来源质量");
    const decision = screen.getByTestId("pnl-attribution-decision-strip");
    expect(decision).toHaveTextContent("正式桥四效应");
    expect(decision).toHaveTextContent("正式损益已核对");
    expect(decision.querySelector("[data-quality]")).toHaveAttribute("data-quality", "error");
    expect(decision).not.toHaveTextContent("持仓模型四效应");
    expect(screen.getByTestId("pnl-attribution-home-campisi-window")).toHaveTextContent("当前为正式损益桥归因");
    expect(screen.queryByTestId("pnl-attribution-error-banner")).not.toBeInTheDocument();
    expect(getFourEffects).toHaveBeenCalledWith({ startDate: "2026-07-31", endDate: "2026-08-31", lookbackDays: 30, detail: "full" });
    expect(getEnhanced).not.toHaveBeenCalled();
  });

  it("opens the home interval in Campisi four-effects only and preserves coverage disclosures", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    const getFourEffects = vi.fn(async () => ({
      result_meta: { ...buildResultMeta("campisi.four_effects"), quality_flag: "warning" as const,
        formal_use_allowed: false, as_of_date: "2026-08-31" },
      result: homeCampisiModelResult(),
    }));
    const getEnhanced = vi.fn(client.getPnlCampisiEnhanced.bind(client));
    const getMaturityBuckets = vi.fn(client.getPnlCampisiMaturityBuckets.bind(client));
    const getDecisionGrade = vi.fn(client.getPnlCampisiDecisionGrade.bind(client));
    const getAdvancedSummary = vi.fn(client.getPnlAdvancedAttributionSummary.bind(client));
    client.getPnlCampisiFourEffects = getFourEffects;
    client.getPnlCampisiEnhanced = getEnhanced;
    client.getPnlCampisiMaturityBuckets = getMaturityBuckets;
    client.getPnlCampisiDecisionGrade = getDecisionGrade;
    client.getPnlAdvancedAttributionSummary = getAdvancedSummary;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter initialEntry={
            "/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31"
          } />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(getFourEffects).toHaveBeenCalledWith({
      startDate: "2026-08-01", endDate: "2026-08-31", lookbackDays: 30, detail: "full",
    }));
    expect(screen.getByRole("button", { name: /高级归因 \+ Campisi/ })).toHaveClass("pnl-attribution-tab-button--active");
    expect(screen.getByTestId("pnl-attribution-home-campisi-window"))
      .toHaveTextContent("2026-08-01 至 2026-08-31");
    expect(await screen.findByTestId("campisi-effect-availability-position_change"))
      .toHaveTextContent("259/1854");
    expect(screen.getByTestId("campisi-effect-availability-treasury_effect"))
      .toHaveTextContent("两端共同的有效正收益率期限不足");
    expect(screen.getByTestId("campisi-effect-availability-accrued_interest"))
      .toHaveTextContent("163/1595");
    expect(screen.getByTestId("campisi-formal-closure-warning"))
      .toHaveTextContent("正式损益核对不可用");
    const decisionStrip = screen.getByTestId("pnl-attribution-decision-strip");
    expect(decisionStrip).toHaveTextContent("持仓模型四效应");
    expect(decisionStrip).toHaveTextContent("首页指定区间的 Campisi 持仓模型四效应");
    expect(decisionStrip).toHaveTextContent("/api/pnl-attribution/campisi/four-effects");
    expect(decisionStrip).toHaveTextContent("正式损益核对不可用");
    expect(decisionStrip).toHaveTextContent("未允许正式使用");
    expect(decisionStrip).toHaveTextContent("指定区间");
    await waitFor(() => expect(decisionStrip).toHaveTextContent("核对输入覆盖"));
    expect(decisionStrip).not.toHaveTextContent("正式 FI / Campisi 归因");
    expect(decisionStrip).not.toHaveTextContent("复核 Campisi 决策级");
    expect(decisionStrip).not.toHaveTextContent("口径未闭合");
    expect(decisionStrip).not.toHaveTextContent("环比");
    const currentViewMeta = screen.getByTestId("pnl-attribution-current-view-meta");
    expect(currentViewMeta).toHaveTextContent("正式来源·模型归因");
    expect(currentViewMeta).not.toHaveTextContent("正式口径");
    expect(getEnhanced).not.toHaveBeenCalled();
    expect(getMaturityBuckets).not.toHaveBeenCalled();
    expect(getDecisionGrade).not.toHaveBeenCalled();
    expect(getAdvancedSummary).not.toHaveBeenCalled();
  });

  it("shows an invalid home interval instead of silently loading monthly attribution", async () => {
    const client = createApiClient({ mode: "mock" });
    const getFourEffects = vi.fn(client.getPnlCampisiFourEffects.bind(client));
    const getProductCategory = vi.fn(client.getProductCategoryPnl.bind(client));
    client.getPnlCampisiFourEffects = getFourEffects;
    client.getProductCategoryPnl = getProductCategory;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter initialEntry={
            "/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-09-01&campisi_end_date=2026-08-31"
          } />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-error-banner"))
      .toHaveTextContent("链接日期无效或与报告日不一致");
    expect(getFourEffects).not.toHaveBeenCalled();
    expect(getProductCategory).not.toHaveBeenCalled();
    expect(screen.queryByTestId("pnl-attribution-home-campisi-window")).not.toBeInTheDocument();
  });

  it.each([
    ["mismatched report date", { report_date: "2026-07-31" }],
    ["formal bridge missing source coverage", { basis: "formal_report_pnl_bridge" }],
    ["mismatched interval start", { period_start: "2026-07-31" }],
    ["mismatched interval end", { period_end: "2026-08-30" }],
  ])("rejects a %s returned for a home interval", async (_case, override) => {
    const client = createApiClient({ mode: "mock" });
    const getFourEffects = vi.fn(async () => ({
      result_meta: buildResultMeta("campisi.four_effects"),
      result: { ...homeCampisiModelResult(), ...override } as CampisiFourEffectsPayload,
    }));
    client.getPnlCampisiFourEffects = getFourEffects;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter initialEntry={
            "/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31"
          } />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-error-banner"))
      .toHaveTextContent("区间或归因来源未能核对");
    expect(getFourEffects).toHaveBeenCalledOnce();
    expect(screen.queryByTestId("campisi-effect-availability")).not.toBeInTheDocument();
  });

  it("keeps the ordinary advanced tab on its prior-month-end baseline", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: { report_dates: ["2026-08-31"], formal_fi_report_dates: ["2026-08-31"],
        nonstd_bridge_report_dates: [] },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: { report_dates: ["2026-08-31"] },
    }));
    const getFourEffects = vi.fn(client.getPnlCampisiFourEffects.bind(client));
    client.getPnlCampisiFourEffects = getFourEffects;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter initialEntry="/pnl-attribution?report_date=2026-08-31" />
        </ApiClientProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByTestId("pnl-attribution-product-category-tab")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /高级归因 \+ Campisi/ }));
    await waitFor(() => expect(getFourEffects).toHaveBeenCalledWith({
      startDate: "2026-07-31", endDate: "2026-08-31", lookbackDays: 30,
    }));
    expect(screen.queryByTestId("pnl-attribution-home-campisi-window")).not.toBeInTheDocument();
  });
  it("keeps the pnl review entry fail-closed until the explicit frontend gate is enabled", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
      },
    }));

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-page-title")).toBeInTheDocument();
    expect(screen.queryByTestId("pnl-attribution-agent-open")).not.toBeInTheDocument();
  });

  it("wires the governed pnl review context into the embedded drawer", async () => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-02-28"],
      },
    }));
    client.getProductCategoryAttribution = vi.fn(async (options) => {
      const response = await createApiClient({ mode: "mock" }).getProductCategoryAttribution(options);
      return {
        ...response,
        result_meta: {
          ...response.result_meta,
          formal_use_allowed: true,
        },
      };
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByTestId("pnl-attribution-date-mismatch");
    await screen.findByTestId("pnl-attribution-current-view-meta");
    await user.click(screen.getByTestId("pnl-attribution-agent-open"));

    const panelProbe = await screen.findByTestId("pnl-attribution-agent-panel-probe");
    expect(panelProbe).toHaveAttribute("data-page-id", "pnl-attribution");
    expect(panelProbe).toHaveAttribute("data-report-date", "2026-02-28");
    expect(panelProbe).toHaveAttribute("data-default-question", "/pnl-review");
    expect(panelProbe).toHaveAttribute(
      "data-context-note",
      expect.stringContaining("仅供人工复核"),
    );
    expect(panelProbe).toHaveAttribute(
      "data-context-note",
      expect.stringContaining("不得跨口径汇总或闭合"),
    );

    const filters = JSON.parse(panelProbe.textContent ?? "{}") as Record<string, unknown>;
    expect(filters.active_tab).toBe("product-category");
    expect(filters.compare_type).toBe("mom");
    expect(filters.attribution_lens).toBe("product_category_operating");
    expect(filters.formal_report_date).toBe("2026-03-31");
    expect(filters.product_category_report_date).toBe("2026-02-28");
    expect(filters.dates_aligned).toBe(false);
    expect(filters.source_formal_use_allowed).toBe(true);
    expect(filters.formal_use_allowed).toBe(false);
  });

  it("keeps attribution surfaces on the homepage blue-gray token family", () => {
    const source = PNL_ATTRIBUTION_THEME_SOURCE_PATHS.map((path) =>
      readFileSync(path, "utf8"),
    ).join("\n");

    expect(source).not.toMatch(/designTokens\.color\.warm|moss-color-warm-/);
    expect(source).not.toMatch(/#ded6ca|#ece6dd|#665f58/);
    // 页面挂 Nocturne scope（pnl-attribution）：面色/文字/盈亏/强调着色走
    // --dh-api-* 家族（scope 内解析为 --nct-*），盈亏 tone 走 TONE_DH_CSS_VAR
    // （--ib-* 在路由边界被算成钢蓝字面值故不得引用）；ECharts canvas 读不到
    // CSS 变量，图表色走 nocturneTokens 静态镜像，钢蓝 dhApiTokens 镜像与浅色
    // designTokens.color.*（neutral[900]、primary[600]、info[600] 等）均不得回归。
    expect(source).not.toMatch(/designTokens\.color\./);
    expect(source).not.toContain("dhApiTokens.color.");
    expect(source).toContain("nocturneTokens.color.");
    expect(source).toContain("TONE_DH_CSS_VAR");
    expect(source).not.toMatch(/\bTONE_CSS_VAR\b/);
    expect(source).toContain("var(--dh-api-");
  });

  it("mounts with explicit product-category and formal FI lenses", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
        formal_fi_report_dates: ["2026-03-31", "2026-02-28"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
      },
    }));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-page-title")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-product-category-lens-card")).toHaveTextContent("经营净收入");
    expect(screen.getByTestId("pnl-attribution-product-category-lens-card")).toHaveTextContent("FTP 后");
    expect(screen.getByTestId("pnl-attribution-product-category-lens-card")).toHaveTextContent("证据状态");
    expect(screen.getByTestId("pnl-attribution-product-category-lens-card")).toHaveTextContent("正式读模型已就绪");
    expect(screen.getByTestId("pnl-attribution-formal-lens-card")).toHaveTextContent("含非标桥接");
    expect(screen.getByTestId("pnl-attribution-formal-lens-card")).toHaveTextContent("未扣 FTP");
    expect(screen.getByTestId("pnl-attribution-formal-lens-card")).toHaveTextContent("证据状态");
    expect(screen.getByTestId("pnl-attribution-formal-lens-card")).toHaveTextContent("正式归因口径已就绪");
    const workbenchLead = screen.getByTestId("pnl-attribution-workbench-lead");
    expect(workbenchLead).toBeInTheDocument();
    expect(workbenchLead).toHaveTextContent("/api/pnl-attribution/*");
    expect(workbenchLead).toHaveTextContent("/ui/pnl/product-category");
    expect(workbenchLead).toHaveTextContent("TPL");
    expect(screen.getByTestId("pnl-attribution-current-view-lead")).toBeInTheDocument();
    const decisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    // 治理 token 正文中文化，原 token 作为证据引用收进 title（§6）。
    expect(decisionStrip).toHaveTextContent("候选/待批准");
    expect(decisionStrip).toHaveTextContent("未允许正式使用");
    expect(decisionStrip).toHaveTextContent("待业主批准");
    expect(decisionStrip).toHaveTextContent("口径未闭合");
    expect(decisionStrip).not.toHaveTextContent("candidate_or_pending");
    expect(within(decisionStrip).getByTitle("candidate_or_pending")).toBeInTheDocument();
    expect(within(decisionStrip).getByTitle("formal_use_allowed=false")).toBeInTheDocument();
    expect(within(decisionStrip).getByTitle("owner approval pending")).toBeInTheDocument();
    expect(within(decisionStrip).getByTitle("closure_approved=false")).toBeInTheDocument();
    expect(decisionStrip).toHaveTextContent("产品分类经营归因");
    expect(decisionStrip).toHaveTextContent("/ui/pnl/product-category");
    expect(decisionStrip).toHaveTextContent("共同报告日 2026-03-31");
    expect(await screen.findByTestId("pnl-attribution-product-category-tab")).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-attribution-product-category-attribution-table")).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-attribution-product-category-ytd-table")).toBeInTheDocument();

    const pageTitle = screen.getByTestId("pnl-attribution-page-title");
    const productCategoryLens = screen.getByTestId("pnl-attribution-product-category-lens-card");
    const formalLens = screen.getByTestId("pnl-attribution-formal-lens-card");
    const currentViewLead = screen.getByTestId("pnl-attribution-current-view-lead");
    const productCategoryTab = screen.getByTestId("pnl-attribution-product-category-tab");
    const attributionReadout = within(productCategoryTab).getByTestId(
      "pnl-attribution-product-category-attribution-mobile-readout",
    );
    const attributionRawGrid = within(productCategoryTab).getByTestId(
      "pnl-attribution-product-category-attribution-raw-grid",
    );
    const ytdReadout = within(productCategoryTab).getByTestId(
      "pnl-attribution-product-category-ytd-mobile-readout",
    );
    const ytdRawGrid = within(productCategoryTab).getByTestId(
      "pnl-attribution-product-category-ytd-raw-grid",
    );
    const position = (node: HTMLElement) =>
      Array.from(document.body.querySelectorAll("*")).indexOf(node);
    expect(position(pageTitle)).toBeLessThan(position(decisionStrip));
    expect(position(decisionStrip)).toBeLessThan(position(productCategoryLens));
    expect(position(productCategoryLens)).toBeLessThan(position(formalLens));
    expect(position(formalLens)).toBeLessThan(position(workbenchLead));
    expect(position(workbenchLead)).toBeLessThan(position(currentViewLead));
    expect(position(currentViewLead)).toBeLessThan(position(productCategoryTab));
    expect(position(attributionReadout)).toBeLessThan(position(attributionRawGrid));
    expect(position(ytdReadout)).toBeLessThan(position(ytdRawGrid));

    expect(attributionReadout).toHaveTextContent("移动归因读数");
    expect(attributionReadout).toHaveTextContent("经营变动");
    expect(attributionReadout).toHaveTextContent("最大拆分项");
    expect(attributionReadout).toHaveTextContent("未解释差异");
    expect(attributionReadout).toHaveTextContent("闭合误差");
    expect(attributionReadout).toHaveTextContent("状态");
    expect(ytdReadout).toHaveTextContent("移动YTD读数");
    expect(ytdReadout).toHaveTextContent("累计净营收");
    expect(ytdReadout).toHaveTextContent("累计规模");
    expect(ytdReadout).toHaveTextContent("加权收益率");
    expect(ytdReadout).toHaveTextContent("展示行数");

    await user.click(screen.getByRole("button", { name: "规模 / 利率效应" }));

    const formalDecisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    expect(formalDecisionStrip).toHaveTextContent("正式 FI / 债券归因");
    expect(formalDecisionStrip).toHaveTextContent("/api/pnl-attribution/*");
    const currentViewMeta = await screen.findByTestId("pnl-attribution-current-view-meta");
    expect(currentViewMeta).toHaveTextContent("2026-03");
    // 生成时间收敛为分钟级展示；微秒级 ISO 原值收进 title，不再直出正文。
    expect(currentViewMeta).toHaveTextContent("2026-04-09 10:30");
    expect(currentViewMeta).not.toHaveTextContent("2026-04-09T10:30:00Z");
    expect(
      within(currentViewMeta).getByTitle("2026-04-09T10:30:00Z"),
    ).toBeInTheDocument();
    const bridgePanel = screen.getByTestId("volume-rate-bridge-panel");
    expect(bridgePanel).toHaveTextContent("损益变动桥");
    expect(bridgePanel).toHaveTextContent("交叉效应");
    expect(bridgePanel).toHaveTextContent("未解释差额");

    await user.click(screen.getByRole("button", { name: /TPL/i }));
    expect(screen.getByRole("button", { name: /TPL/i })).toBeInTheDocument();
    const tplDecisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    expect(tplDecisionStrip).toHaveTextContent("TPL 混合口径例外");
    expect(tplDecisionStrip).toHaveTextContent("/api/pnl-attribution/tpl-market");
    expect(tplDecisionStrip).toHaveTextContent("/ui/pnl/product-category");

    await user.click(screen.getByRole("button", { name: /Campisi/i }));
    const campisiDecisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    expect(campisiDecisionStrip).toHaveTextContent("正式 FI / Campisi 归因");

    expect(await screen.findByTestId("campisi-decision-headline")).toHaveTextContent("主要来自");
    expect(screen.getByTestId("campisi-decision-formal-view")).toHaveTextContent("正式 PnL 视图");
    expect(screen.getByTestId("campisi-decision-valuation-view")).toHaveTextContent("估值 / OCI 视图");
    expect(screen.getByText("票息不等于主动能力")).toBeInTheDocument();
    expect(screen.getByText("残差不算能力")).toBeInTheDocument();

    expect(await screen.findByTestId("campisi-formal-closure-warning")).toHaveTextContent("PnL");

    const advancedMeta = screen.getByTestId("pnl-attribution-advanced-view-meta");
    expect(advancedMeta).toHaveTextContent("Carry / Roll-down");
    expect(advancedMeta).toHaveTextContent("Campisi");
  });

  it("converges a shared advanced-tab load failure into one region banner", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
      },
    }));
    // Promise.all 中任一失败即整个页签失败：全部面板同空，此前 5 处逐字重复同一错误。
    client.getPnlCarryRollDown = vi.fn(async () => {
      throw new Error(
        "Request failed: /api/pnl-attribution/carry-rolldown?report_date=2026-03-31 (500)",
      );
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /Campisi/i }));

    // 区级只有一条错误横幅：中文结论正文，接口路径只进 title。
    const banner = await screen.findByTestId("pnl-attribution-error-banner");
    expect(banner).toHaveTextContent("当前视图数据载入失败。");
    expect(banner).toHaveTextContent("后端接口请求失败（HTTP 500）");
    expect(banner).not.toHaveTextContent("Request failed");
    expect(banner).not.toHaveTextContent("/api/pnl-attribution");
    expect(
      within(banner).getByTitle(
        "Request failed: /api/pnl-attribution/carry-rolldown?report_date=2026-03-31 (500)",
      ),
    ).toBeInTheDocument();
    expect(within(banner).getByRole("button", { name: "重试" })).toBeInTheDocument();

    // 各面板收缩为标题 + 一行指引；不再出现逐面板的 data-section-error。
    const collapsed = screen.getAllByTestId("pnl-attribution-collapsed-panel");
    expect(collapsed).toHaveLength(6);
    expect(collapsed[0]).toHaveTextContent("Campisi 决策级解释");
    expect(collapsed[0]).toHaveTextContent("见上方错误说明。");
    expect(collapsed[4]).toHaveTextContent("Carry / 利差 / KRD 高级归因");
    expect(screen.queryAllByTestId("data-section-error")).toHaveLength(0);
    expect(screen.queryByText(/Request failed/)).not.toBeInTheDocument();
  });

  it("keeps legacy Campisi panels visible when decision-grade endpoint is unavailable", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    client.getPnlCampisiDecisionGrade = vi.fn(async () => {
      throw new Error("decision-grade 404");
    });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
        formal_fi_report_dates: ["2026-03-31", "2026-02-28"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
      },
    }));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /Campisi/i }));

    expect(await screen.findByTestId("campisi-formal-closure-warning")).toHaveTextContent("PnL");
    expect(screen.getByText("decision-grade 404")).toBeInTheDocument();
  });

  it("does not let the legacy Campisi endpoint block the governed advanced tab", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    client.getPnlCampisiAttribution = vi.fn(async () => {
      throw new Error("legacy campisi 500");
    });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
        formal_fi_report_dates: ["2026-03-31", "2026-02-28"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
      },
    }));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /Campisi/i }));

    expect(await screen.findByTestId("campisi-formal-closure-warning")).toHaveTextContent("PnL");
    expect(screen.queryByTestId("pnl-attribution-error-banner")).not.toBeInTheDocument();
    expect(client.getPnlCampisiAttribution).not.toHaveBeenCalled();
  });

  it("keeps product-category and formal FI report dates independent", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
        formal_fi_report_dates: ["2026-03-31", "2026-02-28"],
        nonstd_bridge_report_dates: [],
      },
    }));
    const getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-02-28", "2026-01-31"],
      },
    }));
    const getVolumeRateAttribution = vi.fn(client.getVolumeRateAttribution.bind(client));
    const getPnlAttributionAnalysisSummary = vi.fn(client.getPnlAttributionAnalysisSummary.bind(client));
    const getProductCategoryPnl = vi.fn(client.getProductCategoryPnl.bind(client));
    const getProductCategoryAttribution = vi.fn(client.getProductCategoryAttribution.bind(client));
    client.getFormalPnlDates = getFormalPnlDates;
    client.getProductCategoryDates = getProductCategoryDates;
    client.getVolumeRateAttribution = getVolumeRateAttribution;
    client.getPnlAttributionAnalysisSummary = getPnlAttributionAnalysisSummary;
    client.getProductCategoryPnl = getProductCategoryPnl;
    client.getProductCategoryAttribution = getProductCategoryAttribution;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(getProductCategoryAttribution).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        compare: "mom",
      }),
    );
    expect(getProductCategoryPnl).toHaveBeenCalledWith({
      reportDate: "2026-02-28",
      view: "monthly",
    });
    expect(getProductCategoryPnl).toHaveBeenCalledWith({
      reportDate: "2026-02-28",
      view: "ytd",
    });
    expect(screen.getByTestId("pnl-attribution-date-mismatch")).toHaveTextContent("2026-03-31");
    expect(screen.getByTestId("pnl-attribution-date-mismatch")).toHaveTextContent("2026-02-28");
    const decisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    expect(decisionStrip).toHaveTextContent("日期分离");
    expect(decisionStrip).toHaveTextContent("正式 FI 2026-03-31");
    expect(decisionStrip).toHaveTextContent("产品分类 2026-02-28");
    expect(getVolumeRateAttribution).not.toHaveBeenCalled();
    expect(getPnlAttributionAnalysisSummary).not.toHaveBeenCalled();
    expect(await screen.findByTestId("pnl-attribution-product-category-tab")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "规模 / 利率效应" }));

    await waitFor(() =>
      expect(getVolumeRateAttribution).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        compareType: "mom",
      }),
    );
    const formalDecisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    expect(formalDecisionStrip).toHaveTextContent("正式 FI / 债券归因");
    expect(formalDecisionStrip).toHaveTextContent("日期分离");
    expect(getPnlAttributionAnalysisSummary).not.toHaveBeenCalled();
  });

  it("does not block formal FI when product-category dates are missing", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    const getVolumeRateAttribution = vi.fn(client.getVolumeRateAttribution.bind(client));
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: [],
      },
    }));
    client.getVolumeRateAttribution = getVolumeRateAttribution;
    const getProductCategoryAttribution = vi.fn(client.getProductCategoryAttribution.bind(client));
    client.getProductCategoryAttribution = getProductCategoryAttribution;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-source-date-warning")).toHaveTextContent("产品分类");
    const decisionStrip = await screen.findByTestId("pnl-attribution-decision-strip");
    expect(decisionStrip).toHaveTextContent("缺少来源");
    expect(getProductCategoryAttribution).not.toHaveBeenCalled();
    expect(getVolumeRateAttribution).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "规模 / 利率效应" }));

    await waitFor(() =>
      expect(getVolumeRateAttribution).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        compareType: "mom",
      }),
    );
  });

  it("discards stale attribution responses when the compare type switches quickly", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
      },
    }));

    const attributionTemplate = await createApiClient({ mode: "mock" }).getProductCategoryAttribution({
      reportDate: "2026-03-31",
      compare: "mom",
    });
    function deferred<T>() {
      let resolve!: (value: T) => void;
      const promise = new Promise<T>((innerResolve) => {
        resolve = innerResolve;
      });
      return { promise, resolve };
    }
    const staleMomRequest = deferred<typeof attributionTemplate>();
    const freshYoyRequest = deferred<typeof attributionTemplate>();
    const getProductCategoryAttribution = vi.fn(
      (options: Parameters<typeof client.getProductCategoryAttribution>[0]) =>
        options.compare === "yoy" ? freshYoyRequest.promise : staleMomRequest.promise,
    );
    client.getProductCategoryAttribution = getProductCategoryAttribution;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(getProductCategoryAttribution).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        compare: "mom",
      }),
    );

    await user.click(await screen.findByRole("button", { name: "同比" }));

    await waitFor(() =>
      expect(getProductCategoryAttribution).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        compare: "yoy",
      }),
    );

    // 后发（同比）请求先返回：当前视图元信息落到同比 trace。
    freshYoyRequest.resolve({
      ...attributionTemplate,
      result_meta: {
        ...buildResultMeta("product_category_pnl.attribution", "tr_fresh_yoy"),
        as_of_date: "2026-03-31",
      },
    });
    const metaStrip = await screen.findByTestId("pnl-attribution-current-view-meta");
    await waitFor(() => expect(metaStrip).toHaveTextContent("tr_fresh_yoy"));

    // 先发（环比）请求后返回：过期口径必须被丢弃，不得覆盖同比视图。
    staleMomRequest.resolve({
      ...attributionTemplate,
      result_meta: {
        ...buildResultMeta("product_category_pnl.attribution", "tr_stale_mom"),
        as_of_date: "2026-03-31",
      },
    });
    await waitFor(() =>
      expect(screen.getByTestId("pnl-attribution-current-view-meta")).toHaveTextContent(
        "tr_fresh_yoy",
      ),
    );
    expect(screen.getByTestId("pnl-attribution-current-view-meta")).not.toHaveTextContent(
      "tr_stale_mom",
    );
  });

  it("loads product-category monthly TPL rows separately when opening the TPL market tab", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    const getProductCategoryPnl = vi.fn(async (options: Parameters<typeof client.getProductCategoryPnl>[0]) => ({
      result_meta: buildResultMeta("product_category_pnl.detail"),
      result: productCategoryPayload(options.reportDate),
    }));
    const getTplMarketCorrelation = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.tpl_market"),
      result: tplMarketPayload(),
    }));
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
      },
    }));
    client.getProductCategoryPnl = getProductCategoryPnl;
    client.getTplMarketCorrelation = getTplMarketCorrelation;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPageWithRouter />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(getProductCategoryPnl).toHaveBeenCalled());
    getProductCategoryPnl.mockClear();

    await user.click(screen.getByRole("button", { name: /TPL/i }));

    await waitFor(() =>
      expect(getTplMarketCorrelation).toHaveBeenCalledWith({
        months: 12,
        reportDate: "2026-03-31",
      }),
    );
    await waitFor(() =>
      expect(getProductCategoryPnl).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        view: "monthly",
      }),
    );
    expect(getProductCategoryPnl).toHaveBeenCalledWith({
      reportDate: "2026-02-28",
      view: "monthly",
    });
  });
});
