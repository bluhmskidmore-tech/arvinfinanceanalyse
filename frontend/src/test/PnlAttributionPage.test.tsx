import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, waitFor } from "@testing-library/react";
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
    expect(source).toContain("designTokens.color.neutral[900]");
    expect(source).toContain("designTokens.color.primary[600]");
    expect(source).toContain("designTokens.color.info[600]");
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
    expect(screen.getByTestId("pnl-attribution-formal-lens-card")).toHaveTextContent("含非标桥接");
    expect(screen.getByTestId("pnl-attribution-formal-lens-card")).toHaveTextContent("未扣 FTP");
    const workbenchLead = screen.getByTestId("pnl-attribution-workbench-lead");
    expect(workbenchLead).toBeInTheDocument();
    expect(workbenchLead).toHaveTextContent("/api/pnl-attribution/*");
    expect(workbenchLead).toHaveTextContent("/ui/pnl/product-category");
    expect(workbenchLead).toHaveTextContent("TPL");
    expect(screen.getByTestId("pnl-attribution-current-view-lead")).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-attribution-product-category-tab")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "规模 / 利率效应" }));

    const currentViewMeta = await screen.findByTestId("pnl-attribution-current-view-meta");
    expect(currentViewMeta).toHaveTextContent("2026-03");
    expect(currentViewMeta).toHaveTextContent("2026-04-09");
    expect(currentViewMeta).toHaveTextContent("2026-04-09T10:30:00Z");
    const bridgePanel = screen.getByTestId("volume-rate-bridge-panel");
    expect(bridgePanel).toHaveTextContent("损益变动桥");
    expect(bridgePanel).toHaveTextContent("交叉效应");
    expect(bridgePanel).toHaveTextContent("未解释差额");

    await user.click(screen.getByRole("button", { name: /TPL/i }));
    expect(screen.getByRole("button", { name: /TPL/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Campisi/i }));

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
