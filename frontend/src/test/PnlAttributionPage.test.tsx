import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import type {
  Numeric,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
  TPLMarketCorrelationPayload,
} from "../api/contracts";
import { ApiClientProvider, createApiClient } from "../api/client";
import PnlAttributionPage from "../features/pnl-attribution/pages/PnlAttributionPage";

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

describe("PnlAttributionPage", () => {
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
          <PnlAttributionPage />
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
    expect(decisionStrip).toHaveTextContent("candidate_or_pending");
    expect(decisionStrip).toHaveTextContent("formal_use_allowed=false");
    expect(decisionStrip).toHaveTextContent("owner approval pending");
    expect(decisionStrip).toHaveTextContent("closure_approved=false");
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
          <PnlAttributionPage />
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
          <PnlAttributionPage />
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
          <PnlAttributionPage />
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
          <PnlAttributionPage />
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
          <PnlAttributionPage />
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
          <PnlAttributionPage />
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
          <PnlAttributionPage />
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
