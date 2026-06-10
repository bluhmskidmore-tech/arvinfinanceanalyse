import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, vi } from "vitest";

import { ActionRequestError, createApiClient } from "../api/client";
import { PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY } from "../features/product-category-pnl/pages/productCategoryPnlPageModel";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: ({
    option,
    onEvents,
  }: {
    option?: unknown;
    onEvents?: { click?: (params: { dataIndex: number; seriesIndex?: number }) => void };
  }) => (
    <div data-testid="product-category-echarts-stub">
      <span data-testid="product-category-echarts-option">{JSON.stringify(option ?? null)}</span>
      {Array.from({ length: 12 }, (_, index) => (
        <button
          key={index}
          data-testid={`product-category-echarts-click-index-${index}`}
          type="button"
          onClick={() => onEvents?.click?.({ dataIndex: index, seriesIndex: 1 })}
        >
          click {index}
        </button>
      ))}
    </div>
  ),
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("product-category-pnl");
}, 20_000);

function renderWorkbenchAppWithClient(client: ReturnType<typeof createApiClient>) {
  return renderWorkbenchApp(["/product-category-pnl"], { client });
}

function yuan(yi: number): string {
  return String(yi * 100_000_000);
}

function fixtureCashAmount(scaleYi: number, ratePct: number, days: number): string {
  return String(scaleYi * 1000 + ratePct * 100 + days);
}

function withEmptyInterestSpread<T extends { result: object }>(envelope: T): T {
  const result = { ...envelope.result } as Record<string, unknown>;
  result.interest_spread = {
    all_currency_asset_yield_pct: null,
    all_currency_liability_yield_pct: null,
    all_currency_spread_pct: null,
    cny_asset_yield_pct: null,
    cny_liability_yield_pct: null,
    cny_spread_pct: null,
  };
  return { ...envelope, result: result as T["result"] };
}

function readChartOption(panelTestId: string) {
  const panel = screen.getByTestId(panelTestId);
  return JSON.parse(
    within(panel).getByTestId("product-category-echarts-option").textContent ?? "null",
  ) as {
    legend?: { data?: string[] };
    xAxis?: { data?: string[] } | Array<{ data?: string[] }>;
    yAxis?: { min?: number; max?: number; scale?: boolean } | Array<{ min?: number; max?: number; scale?: boolean }>;
    series?: Array<{
      name?: string;
      type?: string;
      data?: unknown[];
      yAxisIndex?: number;
      symbolSize?: number;
      lineStyle?: { width?: number };
      label?: { show?: boolean };
      endLabel?: { show?: boolean };
    }>;
  };
}

async function waitForTrendDiagnosticsAutoLoad() {
  await screen.findByTestId("product-category-diagnostics-surface");
  await waitFor(() => {
    expect(screen.getByTestId("product-category-operating-action-backtest")).not.toHaveTextContent(
      "选择报表日期后",
    );
  });
}

function buildMockAttributionEnvelope(reportDate: string, compare: "mom" | "yoy" = "mom") {
  const priorReportDate = compare === "yoy" ? "2025-02-28" : "2026-01-31";
  const effect = {
    day_effect: yuan(-0.04),
    scale_effect: yuan(0.3),
    rate_effect: yuan(0.18),
    ftp_effect: yuan(0.02),
    direct_effect: yuan(0),
    unexplained_effect: yuan(0),
    explained_effect: yuan(0.46),
    delta_business_net_income: yuan(0.46),
    closure_error: yuan(0),
  };
  const point = {
    report_date: reportDate,
    days: 28,
    scale: yuan(110),
    yield_pct: "2.60",
    cash: yuan(0.66),
    ftp: yuan(0.2),
    business_net_income: yuan(0.46),
  };
  const priorPoint = {
    report_date: priorReportDate,
    days: 31,
    scale: yuan(100),
    yield_pct: "2.40",
    cash: yuan(0.4),
    ftp: yuan(0.14),
    business_net_income: yuan(0.26),
  };
  const total = {
    category_id: "asset_total",
    category_name: "资产端合计",
    side: "asset",
    level: 0,
    state: "complete",
    current: point,
    prior: priorPoint,
    effects: effect,
  };

  return buildMockApiEnvelope("product_category_pnl.attribution", {
    report_date: reportDate,
    compare,
    current_report_date: reportDate,
    prior_report_date: priorReportDate,
    state: "complete",
    reason: null,
    rows: [
      {
        category_id: "interbank_lending_assets",
        category_name: "拆放同业",
        side: "asset",
        level: 0,
        state: "complete",
        current: point,
        prior: priorPoint,
        effects: effect,
      },
    ],
    totals: {
      asset_total: total,
      liability_total: { ...total, category_id: "liability_total", category_name: "负债端合计", side: "liability" },
      grand_total: { ...total, category_id: "grand_total", category_name: "grand_total", side: "all" },
    },
  });
}

function renderWorkbenchAppWithTwoMonthLiabilityTrend() {
  const baseClient = createApiClient({ mode: "mock" });
  renderWorkbenchAppWithClient({
    ...baseClient,
    getProductCategoryDates: vi.fn(async () =>
      buildMockApiEnvelope("product_category_pnl.dates", {
        report_dates: ["2026-02-28", "2026-01-31"],
      }),
    ),
    getProductCategoryPnl: vi.fn(async (options) => {
      const env = buildMockProductCategoryPnlEnvelope(options);
      if (options.reportDate !== "2026-01-31") {
        return env;
      }
      return {
        ...env,
        result: {
          ...env.result,
          liability_total: {
            ...env.result.liability_total,
            weighted_yield: "1.58",
          },
        },
      };
    }),
  });
}

describe("ProductCategoryPnlPage", () => {
  it("renders the page shell, summary, and table structure", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const table = await screen.findByTestId("product-category-table");
    expect(table).toHaveTextContent("人民币净收入");
    expect(table).toHaveTextContent("外币净收入");
    expect(table).toHaveTextContent("营业净收入");
    expect(table).not.toHaveTextContent("人民币减收入");
    expect(table).not.toHaveTextContent("外币减收入");
    expect(table).not.toHaveTextContent("营业减收入");
    expect(screen.getByTestId("product-category-page")).toHaveClass("product-category-page-shell");
    expect(screen.getByTestId("product-category-contract-hero")).toHaveClass(
      "product-category-contract-hero",
    );
    expect(screen.getByTestId("product-category-page-title")).toHaveTextContent("产品分类损益");
    expect(screen.getByTestId("product-category-page-subtitle")).toHaveTextContent(
      "按业务分类查看损益、FTP 和净收入",
    );
    expect(screen.getByTestId("product-category-role-badge")).toHaveTextContent("系统层");
    expect(screen.getByTestId("product-category-boundary-copy")).toHaveTextContent("系统层经营口径");
    const heroOwnerStatus = screen.getByTestId("product-category-owner-signable-status");
    const productCategoryBranch = screen.getByTestId("product-category-branch-product-category-pnl");
    expect(
      heroOwnerStatus.compareDocumentPosition(productCategoryBranch) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(heroOwnerStatus).toHaveTextContent("Owner-signable=false");
    expect(heroOwnerStatus).toHaveTextContent("Certified=false");
    expect(heroOwnerStatus).toHaveTextContent("Owner approval pending");
    expect(heroOwnerStatus).toHaveTextContent("Golden sample awaiting approval");
    expect(heroOwnerStatus).toHaveTextContent("Manual audit partial units=10");
    expect(screen.getByTestId("product-category-formal-readiness-band")).toHaveTextContent(
      "正式主链首屏摘要",
    );
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "report_date=2026-02-28",
    );
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "view=monthly",
    );
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "quality=ok",
    );
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "fallback=none",
    );
    const certificationBlockers = screen.getByTestId("product-category-certification-blockers");
    expect(certificationBlockers).toHaveTextContent("Owner approval pending");
    expect(certificationBlockers).toHaveTextContent("Golden sample awaiting approval");
    expect(certificationBlockers).toHaveTextContent("Manual audit partial units=10");
    expect(certificationBlockers).toHaveTextContent("Fresh pre-signature rerun required");
    expect(certificationBlockers).toHaveTextContent("Unit=亿元");
    expect(certificationBlockers).toHaveTextContent("Date basis=report_date");
    expect(certificationBlockers).toHaveTextContent("Source=formal read model");
    expect(screen.getByTestId("product-category-formal-headline-totals")).toHaveTextContent(
      "MTR-PCP-001",
    );
    expect(screen.getByTestId("product-category-formal-headline-totals")).toHaveTextContent(
      "MTR-PCP-002",
    );
    expect(screen.getByTestId("product-category-formal-headline-totals")).toHaveTextContent(
      "MTR-PCP-003",
    );
    expect(screen.getByTestId("product-category-first-screen-category-rows")).toHaveTextContent(
      "买入返售",
    );
    expect(screen.getByTestId("product-category-adjustment-lead")).toHaveTextContent(
      "手工调整与审计",
    );
    expect(screen.getByTestId("product-category-scenario-lead")).toHaveTextContent(
      "情景查询",
    );
    expect(screen.getByTestId("product-category-formal-table-lead")).toHaveTextContent(
      "正式产品类别损益表",
    );
    expect(screen.getByTestId("product-category-diagnostics-lead")).toHaveTextContent(
      "受治理诊断面板",
    );
    expect(screen.getByTestId("product-category-diagnostics-surface")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-diagnostics-matrix")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-diagnostics-watchlist")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-diagnostics-spread")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-operating-analysis")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-operating-profit-rank")).toHaveTextContent("1.45");
    await waitFor(() => {
      expect(screen.getByTestId("product-category-operating-movement")).toHaveTextContent("0.02");
    });
    expect(screen.getByTestId("product-category-operating-quadrant")).toHaveTextContent("2.57");
    expect(screen.getByTestId("product-category-operating-action-queue")).toHaveTextContent("动作优先级队列");
    expect(screen.getByTestId("product-category-operating-action-queue")).toHaveTextContent("选择性扩张");
    expect(screen.getByTestId("product-category-operating-action-queue")).toHaveTextContent("重定价/提效");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("动作队列次月命中率");
    await waitFor(() => {
      expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("动作类型表现");
    });
    expect(screen.getByTestId("product-category-financial-analysis")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("FTP 情景敏感度");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("加载矩阵");
    expect(screen.getByTestId("product-category-attribution-waterfall")).toHaveTextContent("经营差异瀑布");
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent("产品差异根因拆解台");
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent("主导原因");
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent("规模因素");
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent("未解释");
    expect(screen.getByTestId("product-category-decision-focus")).toHaveTextContent("本期决策焦点");
    expect(screen.getByTestId("product-category-liability-side-trend")).toHaveTextContent("负债端趋势分析");
    expect(screen.getByTestId("product-category-liability-side-trend")).toHaveTextContent("负债侧产品类别口径");
    expect(screen.queryByText("同业负债")).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-diagnostics-summary")).toHaveTextContent("2.85");
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent("1.75");
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent("合计：");
    expect(screen.getByTestId("product-category-footer-total")).toHaveTextContent(
      "全部市场科目 + 投资收益合计：",
    );
    const metaPanel = screen.getByTestId("product-category-result-meta-baseline");
    expect(metaPanel).toHaveTextContent("product_category_pnl.detail");
    expect(metaPanel).toHaveTextContent("mock_product_category_pnl.detail");
    expect(screen.getByTestId("product-category-governance-strip")).toBeInTheDocument();
    const asOfGap = screen.getByTestId("product-category-as-of-date-gap");
    expect(asOfGap).toHaveTextContent(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY);
    expect(asOfGap.textContent).not.toContain("2026-02-28");
    expect(
      screen.queryByTestId("product-category-governance-notice-fallback_mode"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-formal-scenario-meta-distinct"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-audit-link")).toHaveAttribute(
      "href",
      "/product-category-pnl/audit",
    );
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      "/ledger-pnl?report_date=2026-02-28",
    );
    expect(within(table).getAllByRole("row")).toHaveLength(20);
  });

  it("keeps the formal decision chain before adjustment, analysis, and the full table", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const page = screen.getByTestId("product-category-page");
    const order = [
      "product-category-contract-hero",
      "product-category-data-status-strip",
      "product-category-scenario-lead",
      "product-category-formal-readiness-band",
      "product-category-adjustment-lead",
      "product-category-financial-analysis",
      "product-category-operating-analysis",
      "product-category-formal-table-lead",
      "product-category-formal-table-mobile-readout",
      "product-category-formal-table-raw-grid",
      "product-category-table",
      "product-category-result-meta",
    ].map((testId) =>
      Array.from(page.querySelectorAll("[data-testid]")).findIndex(
        (node) => node.getAttribute("data-testid") === testId,
      ),
    );

    expect(order.every((index) => index >= 0)).toBe(true);
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("places a mobile formal table readout before the raw formal grid", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const readout = screen.getByTestId("product-category-formal-table-mobile-readout");
    const rawGrid = screen.getByTestId("product-category-formal-table-raw-grid");

    expect(readout.compareDocumentPosition(rawGrid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(readout).toHaveTextContent("移动正式表读数");
    expect(readout).toHaveTextContent("报告日");
    expect(readout).toHaveTextContent("视图");
    expect(readout).toHaveTextContent("合计经营净收入");
    expect(readout).toHaveTextContent("资产端经营净收入");
    expect(readout).toHaveTextContent("负债端经营净收入");
    expect(readout).toHaveTextContent("首个业务行");
    expect(readout).toHaveTextContent("规模日均");
    expect(readout).toHaveTextContent("加权收益率");
    expect(readout).toHaveTextContent("展示行数");
    expect(within(rawGrid).getByTestId("product-category-table")).toBeInTheDocument();
  });

  it("opens an action queue closure drawer from an operating action row", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const queue = await screen.findByTestId("product-category-operating-action-queue");
    await user.click(await within(queue).findByRole("button", { name: /查看 买入返售 动作详情/ }));

    const drawer = screen.getByTestId("product-category-operating-action-drawer");
    expect(drawer).toHaveTextContent("动作闭环详情");
    expect(drawer).toHaveTextContent("买入返售");
    expect(drawer).toHaveTextContent("压降或限额复核");
    expect(drawer).toHaveTextContent("核对正式表净营收、规模、收益率与归因变动");
    expect(drawer).toHaveTextContent("净营收 -0.05 亿元");

    await user.click(within(drawer).getByRole("button", { name: "关闭动作详情" }));
    expect(screen.queryByTestId("product-category-operating-action-drawer")).not.toBeInTheDocument();
  });

  it("renders monthly MoM operating attribution from the formal baseline", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
      buildMockAttributionEnvelope(options.reportDate, options.compare),
    );
    const client = {
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryAttribution: attributionSpy,
    } as ReturnType<typeof createApiClient> & {
      getProductCategoryAttribution: typeof attributionSpy;
    };
    renderWorkbenchAppWithClient(client);

    await waitFor(() => {
      expect(attributionSpy).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        compare: "mom",
      });
    });
    const attribution = await screen.findByTestId("product-category-attribution");
    await waitFor(() => {
      expect(attribution).toHaveTextContent("拆放同业");
    });
    expect(attribution).toHaveTextContent("经营差异归因");
    expect(attribution).toHaveTextContent("正式基线");
    expect(attribution).toHaveTextContent("拆放同业");
    expect(attribution).toHaveTextContent("规模因素");
    expect(attribution).toHaveTextContent("本期净营收");
    expect(attribution).toHaveTextContent("对比期净营收");
    expect(attribution).toHaveTextContent("0.30");
    expect(attribution).toHaveTextContent("0.18");
    const comparison = screen.getByTestId("product-category-attribution-comparison-table");
    expect(comparison).toHaveTextContent("规模因素");
    expect(comparison).toHaveTextContent("利率因素");
    const grandTotalRow = screen.getByTestId("product-category-attribution-comparison-row-grand_total");
    expect(grandTotalRow).toHaveTextContent("全表合计");
    const pointDetails = screen.getByTestId("product-category-attribution-detail-table");
    expect(within(pointDetails).queryByText("grand_total")).not.toBeInTheDocument();
    expect(pointDetails).toHaveTextContent("全表合计");
    expect(pointDetails).toHaveTextContent("110.00");
    expect(pointDetails).toHaveTextContent("100.00");
    expect(pointDetails).toHaveTextContent("2.60%");
    expect(pointDetails).toHaveTextContent("2.40%");
    const detailRow = screen.getByTestId(
      "product-category-attribution-comparison-row-interbank_lending_assets",
    );
    expect(detailRow).toHaveTextContent("0.30");
    expect(detailRow).toHaveTextContent("0.18");
    expect(pointDetails).toHaveTextContent("0.20");
  });

  it("places a mobile attribution comparison readout before the raw comparison table", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
      buildMockAttributionEnvelope(options.reportDate, options.compare),
    );
    const client = {
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryAttribution: attributionSpy,
    } as ReturnType<typeof createApiClient> & {
      getProductCategoryAttribution: typeof attributionSpy;
    };
    renderWorkbenchAppWithClient(client);

    const rawTable = await screen.findByTestId("product-category-attribution-comparison-table");
    const readout = screen.getByTestId("product-category-attribution-comparison-mobile-readout");

    expect(readout.compareDocumentPosition(rawTable) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(readout).toHaveTextContent("0.46");
    expect(readout).toHaveTextContent("0.30");
    expect(readout).toHaveTextContent("0.00");
    expect(readout).toHaveTextContent("complete");
  });

  it("places a mobile attribution detail readout before the raw detail table", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
      buildMockAttributionEnvelope(options.reportDate, options.compare),
    );
    const client = {
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryAttribution: attributionSpy,
    } as ReturnType<typeof createApiClient> & {
      getProductCategoryAttribution: typeof attributionSpy;
    };
    renderWorkbenchAppWithClient(client);

    const rawTable = await screen.findByTestId("product-category-attribution-detail-table");
    const readout = screen.getByTestId("product-category-attribution-detail-mobile-readout");

    expect(readout.compareDocumentPosition(rawTable) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(readout).toHaveTextContent("2026");
    expect(readout).toHaveTextContent("2026");
    expect(readout).toHaveTextContent("0.46");
    expect(readout).toHaveTextContent("0.26");
    expect(readout).toHaveTextContent("110.00");
    expect(readout).toHaveTextContent("100.00");
    expect(readout).toHaveTextContent("2.60%");
    expect(readout).toHaveTextContent("2.40%");
  });

  it("switches product-category attribution to year-over-year comparison", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
      buildMockAttributionEnvelope(options.reportDate, options.compare),
    );
    const client = {
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryAttribution: attributionSpy,
    } as ReturnType<typeof createApiClient> & {
      getProductCategoryAttribution: typeof attributionSpy;
    };
    renderWorkbenchAppWithClient(client);

    const attribution = await screen.findByTestId("product-category-attribution");
    await waitFor(() => {
      expect(attribution).toHaveTextContent("拆放同业");
    });
    attributionSpy.mockClear();
    await user.click(within(attribution).getByRole("button", { name: "同比" }));

    await waitFor(() => {
      expect(attributionSpy).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        compare: "yoy",
      });
    });
    expect(attribution).toHaveTextContent("同比正式基线归因");
    expect(attribution).toHaveTextContent("去年同期 2025年02月");
    expect(screen.getByTestId("product-category-attribution-detail-table")).toHaveTextContent("2025年02月");
  });

  it("does not request product-category attribution outside the monthly view", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
      buildMockAttributionEnvelope(options.reportDate, options.compare),
    );
    const client = {
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryAttribution: attributionSpy,
    } as ReturnType<typeof createApiClient> & {
      getProductCategoryAttribution: typeof attributionSpy;
    };
    renderWorkbenchAppWithClient(client);

    const attribution = await screen.findByTestId("product-category-attribution");
    await waitFor(() => {
      expect(attribution).toHaveTextContent("拆放同业");
    });
    attributionSpy.mockClear();
    const viewButtons = within(screen.getByRole("group", { name: "视图模式" })).getAllByRole("button");
    await user.click(viewButtons[1]!);

    const ineligible = await screen.findByTestId("product-category-attribution-ineligible");
    expect(ineligible).toHaveTextContent("仅支持月度视图");
    expect(attributionSpy).not.toHaveBeenCalled();
  });

  it("Unit 1: first report_dates entry drives baseline PnL, manual adjustments list, and ledger link", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const firstDate = "2026-03-31";
    const pnlSpy = vi.fn((options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
      baseClient.getProductCategoryPnl(options),
    );
    const adjSpy = vi.fn(
      (reportDate: string, opts?: Parameters<typeof baseClient.getProductCategoryManualAdjustments>[1]) =>
        baseClient.getProductCategoryManualAdjustments(reportDate, opts),
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [firstDate, "2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryPnl: pnlSpy,
      getProductCategoryManualAdjustments: adjSpy,
    });
    await screen.findByTestId("product-category-table");
    await waitFor(() => {
      expect(pnlSpy).toHaveBeenCalled();
      expect(adjSpy).toHaveBeenCalled();
    });
    expect(pnlSpy.mock.calls.map((call) => call[0]!.reportDate)).toEqual(
      expect.arrayContaining([firstDate, "2026-02-28", "2026-01-31"]),
    );
    expect(pnlSpy.mock.calls[0]![0]).toMatchObject({ reportDate: firstDate, view: "monthly" });
    expect(adjSpy.mock.calls.every((call) => call[0] === firstDate)).toBe(true);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      "/ledger-pnl?report_date=2026-03-31",
    );
  });

  it("loads product-category scenario sensitivity only when requested", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn((options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
      baseClient.getProductCategoryPnl(options),
    );

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl,
    });

    await screen.findByTestId("product-category-table");
    expect(getProductCategoryPnl.mock.calls.every((call) => call[0]?.scenarioRatePct === undefined)).toBe(true);

    await user.click(within(screen.getByTestId("product-category-scenario-sensitivity")).getByRole("button"));

    await waitFor(() => {
      const scenarioRates = getProductCategoryPnl.mock.calls
        .map((call) => call[0]?.scenarioRatePct)
        .filter(Boolean)
        .sort();
      expect(scenarioRates).toEqual(["1.50", "1.60", "1.75", "2.00"]);
    });
    await waitFor(() => {
      expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("总净营收");
    });
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("情景解读");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("关键变动行排行");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("每 1bp");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("FTP 压力路径");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("压力复核包");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("临界 FTP");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("资产/负债冲抵");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("复核顺序");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("管理动作");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("产品行热力条");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("多情景对比");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("仅承压");
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("仅改善");
    const closure = screen.getByTestId("product-category-scenario-action-closure");
    expect(closure).toHaveTextContent("情景动作闭环");
    expect(closure).toHaveTextContent("本期经营动作清单");
    expect(closure).toHaveTextContent("待处理");
    expect(closure).toHaveTextContent("建议动作");
    expect(within(closure).queryByTestId("product-category-scenario-action-memo")).not.toBeInTheDocument();
    await user.click(within(closure).getAllByRole("button", { name: "复核中" })[0]!);
    expect(closure).toHaveTextContent("复核中 1");
    expect(within(closure).queryByTestId("product-category-scenario-action-memo")).not.toBeInTheDocument();
    await user.click(within(closure).getAllByRole("button", { name: "生成复核备忘" })[0]!);
    const memo = within(closure).getByTestId("product-category-scenario-action-memo");
    expect(memo).toHaveTextContent("复核备忘");
    expect(memo).toHaveTextContent("状态：复核中");

    await user.click(screen.getByRole("button", { name: "仅改善" }));
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent(
      "当前筛选下暂无可比较产品行。",
    );
    await user.click(screen.getByRole("button", { name: "仅承压" }));
    expect(screen.getByTestId("product-category-scenario-sensitivity")).toHaveTextContent("生息资产");
    await user.click(screen.getByRole("button", { name: /生息资产 多情景对比/ }));
    expect(screen.getByTestId("product-category-scenario-explanation")).toHaveTextContent("生息资产");

    await user.click(screen.getByRole("button", { name: /复核 1/ }));
    const explanation = screen.getByTestId("product-category-scenario-explanation");
    expect(explanation).toHaveTextContent("复核解释包");
    expect(explanation).toHaveTextContent("生息资产");
    expect(explanation).toHaveTextContent("正式归因");
    expect(explanation).toHaveTextContent("FTP因素");
    expect(explanation).toHaveTextContent("-0.62");
    expect(explanation).toHaveTextContent("未解释");
    expect(explanation).toHaveTextContent("口径桥");
    expect(explanation).toHaveTextContent("情景压力");
    expect(explanation).toHaveTextContent("正式归因合计");
    expect(explanation).toHaveTextContent("复核动作");
    expect(explanation).toHaveTextContent("核对正式归因期间口径");
    expect(explanation).toHaveTextContent("重点追踪 FTP因素");
    expect(within(explanation).getAllByRole("button", { name: "待核对" })).toHaveLength(3);

    await user.click(within(explanation).getAllByRole("button", { name: "已确认" })[0]!);
    expect(within(explanation).getAllByRole("button", { name: "已确认" })[0]).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(within(explanation).getAllByRole("button", { name: "有差异" })[0]!);
    expect(within(explanation).getAllByRole("button", { name: "有差异" })[0]).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(explanation).toHaveTextContent("复核结论台");
    expect(explanation).toHaveTextContent("待核对 2");
    expect(explanation).toHaveTextContent("已确认 0");
    expect(explanation).toHaveTextContent("有差异 1");

    await user.click(within(explanation).getByRole("button", { name: "全部确认" }));
    expect(within(explanation).getAllByRole("button", { name: "已确认" })).toHaveLength(3);
    expect(explanation).toHaveTextContent("已确认 3");
    expect(explanation).toHaveTextContent("复核结论：生息资产动作已全部确认，可进入留痕归档。");

    await user.click(within(explanation).getAllByRole("button", { name: "有差异" })[1]!);
    await user.click(within(explanation).getByRole("button", { name: "FTP 驱动异常" }));
    expect(within(explanation).getByRole("button", { name: "FTP 驱动异常" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(explanation).toHaveTextContent("差异原因：FTP 驱动异常");
    expect(explanation).toHaveTextContent("复核备忘");
    expect(explanation).toHaveTextContent("当前产品：生息资产");

    await user.click(within(explanation).getAllByRole("button", { name: "已确认" })[1]!);
    expect(explanation).toHaveTextContent("差异原因：未选择");

    await user.click(within(explanation).getByRole("button", { name: "重置复核" }));
    expect(explanation).toHaveTextContent("待核对 3");
    expect(within(explanation).getAllByRole("button", { name: "待核对" })[0]).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("Unit 1: empty report_dates skips PnL and adjustments fetches; ledger stays bare; as_of gap does not inject meta dates", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const guard = () => Promise.reject(new Error("unexpected product-category dependent fetch"));
    const pnlSpy = vi.fn(guard);
    const adjSpy = vi.fn(guard);
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope(
          "product_category_pnl.dates",
          { report_dates: [] },
          { generated_at: "2026-05-01T12:00:00Z" },
        ),
      ),
      getProductCategoryPnl: pnlSpy,
      getProductCategoryManualAdjustments: adjSpy,
    });
    await screen.findByTestId("product-category-governance-strip");
    await waitFor(() => {
      expect(pnlSpy).not.toHaveBeenCalled();
      expect(adjSpy).not.toHaveBeenCalled();
    });
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute("href", "/ledger-pnl");
    const gap = screen.getByTestId("product-category-as-of-date-gap");
    expect(gap.textContent).toBe(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY);
    expect(gap.textContent).not.toContain("2026-05-01");
    const monthSelect = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    expect(monthSelect.options).toHaveLength(0);
  });

  it("Unit 1: disappeared selected date is kept and uses the existing visible error path instead of silently switching", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const selectedDate = "2026-02-28";
    const replacementDate = "2026-03-31";
    let staleSelectedDateShouldFail = false;
    const datesSpy = vi
      .fn()
      .mockResolvedValueOnce(
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [selectedDate, "2026-01-31"],
        }),
      )
      .mockResolvedValue(
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [replacementDate, "2026-01-31"],
        }),
      );
    const pnlSpy = vi.fn(async (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) => {
      if (staleSelectedDateShouldFail && options.reportDate === selectedDate) {
        throw new Error("unit1-selected-date-disappeared");
      }
      return baseClient.getProductCategoryPnl(options);
    });
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:unit1-date-disappeared",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: [replacementDate, "2026-01-31"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: datesSpy,
      getProductCategoryPnl: pnlSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-report-date-slot")).toHaveTextContent(selectedDate);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      `/ledger-pnl?report_date=${selectedDate}`,
    );

    staleSelectedDateShouldFail = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => expect(datesSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      expect(
        pnlSpy.mock.calls.some((call) => call[0]?.reportDate === selectedDate && call[0]?.view === "monthly"),
      ).toBe(true);
    });
    expect(pnlSpy.mock.calls.some((call) => call[0]?.reportDate === replacementDate)).toBe(false);
    expect(screen.getByTestId("product-category-report-date-slot")).toHaveTextContent(selectedDate);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      `/ledger-pnl?report_date=${selectedDate}`,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("product-category-table")).not.toBeInTheDocument();
    });
    expect(
      screen
        .getAllByRole("button")
        .some((button) => button.textContent === "\u91cd\u8bd5" || button.textContent === "閲嶈瘯"),
    ).toBe(true);
  });

  it("shows report date choices as months while keeping month-end values for the API", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const monthSelect = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    expect(monthSelect.value).toBe("2026-02-28");
    expect(Array.from(monthSelect.options).slice(0, 2).map((option) => [option.value, option.textContent])).toEqual([
      ["2026-02-28", "2026年02月"],
      ["2026-01-31", "2026年01月"],
    ]);
  });

  it("renders the governed diagnostics matrix and negative watchlist from existing payload rows", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-diagnostics-matrix");
    expect(screen.getByTestId("product-category-diagnostics-watchlist")).toBeInTheDocument();
  });

  it("keeps spread movement attribution incomplete without backend spread fields", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        if (options.reportDate !== "2026-01-31") {
          return env;
        }
        return {
          ...env,
          result: {
            ...env.result,
            asset_total: {
              ...env.result.asset_total,
              weighted_yield: "2.55",
            },
            liability_total: {
              ...env.result.liability_total,
              weighted_yield: "1.60",
            },
            rows: env.result.rows.map((row) => {
              if (row.category_id === "interest_earning_assets") {
                return {
                  ...row,
                  cnx_scale: yuan(2800),
                  business_net_income: yuan(1.2),
                  weighted_yield: "2.35",
                };
              }
              if (row.category_id === "interbank_lending_assets") {
                return {
                  ...row,
                  cnx_scale: yuan(160),
                  cny_scale: yuan(150),
                  foreign_scale: yuan(10),
                  business_net_income: yuan(0.08),
                  weighted_yield: "2.45",
                };
              }
              if (row.category_id === "bond_tpl") {
                return {
                  ...row,
                  cnx_scale: yuan(820),
                  business_net_income: yuan(0.3),
                  weighted_yield: "2.20",
                };
              }
              return row;
            }),
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    const spread = await screen.findByTestId("product-category-diagnostics-spread");
    await waitFor(() => {
      expect(spread).toHaveTextContent("缺少完整收益率对比");
    });
    expect(spread).toHaveTextContent("2026年02月");
    expect(spread).toHaveTextContent("2026年01月");
    expect(spread).toHaveTextContent("后端未返回资产端或负债端收益率字段，无法展示利差归因。");
  });

  it("shows explicit diagnostics fallback copy when rows or spread inputs are incomplete", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const envelope = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const assetTotal = { ...envelope.result.asset_total, weighted_yield: null };
        const liabilityTotal = {
          ...envelope.result.liability_total,
          cnx_scale: "not_available",
          weighted_yield: null,
        };
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: [assetTotal, liabilityTotal, envelope.result.grand_total],
            asset_total: assetTotal,
            liability_total: liabilityTotal,
          },
        };
      }),
    });

    await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-diagnostics-matrix-empty")).toHaveTextContent(
      "当前 payload 未返回可诊断的产品行。",
    );
    expect(screen.getByTestId("product-category-diagnostics-watchlist-empty")).toHaveTextContent(
      "当前 payload 未返回可诊断的产品行。",
    );
    expect(screen.getByTestId("product-category-diagnostics-spread-incomplete")).toHaveTextContent(
      "后端未返回资产端或负债端收益率字段，无法展示利差归因。",
    );
    await waitForTrendDiagnosticsAutoLoad();
    const liabilityOption = readChartOption("product-category-liability-side-trend");
    expect(liabilityOption.xAxis).toMatchObject({ data: ["2026年02月"] });
    expect(liabilityOption.series?.[0]?.data).toEqual([null]);
    expect(liabilityOption.series?.[1]?.data).toEqual([null]);
    expect(screen.getByTestId("product-category-liability-side-trend-incomplete")).toHaveTextContent(
      "2026年02月负债端日均额缺失",
    );
  });

  it("keeps liability-side trend panel visible when aggregate chart inputs are incomplete", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const envelope = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            liability_total: {
              ...envelope.result.liability_total,
              cnx_scale: "not_available",
              weighted_yield: null,
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    await screen.findByTestId("product-category-liability-side-detail-credit_linked_notes");
    const liabilityOption = readChartOption("product-category-liability-side-trend");
    expect(liabilityOption.xAxis).toMatchObject({ data: ["2026年02月"] });
    expect(liabilityOption.series?.[0]?.data).toEqual([null]);
    expect(liabilityOption.series?.[1]?.data).toEqual([null]);
    expect(screen.queryByTestId("product-category-liability-side-trend-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-liability-side-trend-incomplete")).toHaveTextContent(
      "2026年02月负债端日均额缺失",
    );
    expect(screen.getByTestId("product-category-liability-side-detail-credit_linked_notes")).toBeInTheDocument();
  });

  it("renders the requested derived chart panels with chart stubs", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    expect(await screen.findByTestId("product-category-derived-chart-tpl-scale-yield")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-currency-net-income")).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-derived-chart-interest-earning-income-scale"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-interest-spread")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-interest-spread-yoy")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-interest-spread-yoy-cny")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-intermediate-business-income-yoy")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("动作类型表现");
    });
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("样本覆盖");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("等待下一期 2026-03-31 payload 验证");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("已回测");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("最新月待观察");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("归因覆盖");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("回测闸口");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("样本不足");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("补样本任务");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("补 2 个月");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("需补月份：2026-03-31、2026-04-30");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("最早复核：2026-04-30 后");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("复核工作量");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("规则处置");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("收紧 3");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("回测校准建议");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("收紧触发条件");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("低置信");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("最新信号校准复核");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("补样本后复核");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("P3 低样本复核");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("历史均值");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("当前证据");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("规模 1013.32 亿元");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("观察月份");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("观察口径");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("判定缺口");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("确认最新收益率改善证据");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("放行条件");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("未命中诊断");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("收益率未改善");
    expect(screen.getByTestId("product-category-operating-action-backtest")).toHaveTextContent("典型样本");
    expect(screen.getAllByTestId("product-category-echarts-stub")).toHaveLength(8);
  });

  it("builds chart series from bond_tpl, grand_total, interest_earning_assets, and liability_total fields", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const withGrandTotal = {
          ...env,
          result: {
            ...env.result,
            grand_total: {
              ...env.result.grand_total,
              cny_net: yuan(options.reportDate === "2026-01-31" ? 2.12 : 2.71),
              foreign_net: yuan(options.reportDate === "2026-01-31" ? 0.18 : 0.14),
            },
          },
        };
        if (options.reportDate !== "2026-01-31") {
          return withGrandTotal;
        }
        return {
          ...withGrandTotal,
          result: {
            ...withGrandTotal.result,
            liability_total: {
              ...env.result.liability_total,
              weighted_yield: "1.58",
            },
            rows: env.result.rows.map((row) => {
              if (row.category_id === "bond_tpl") {
                return {
                  ...row,
                  cny_scale: yuan(810),
                  foreign_scale: yuan(12),
                  cny_net: yuan(0.22),
                  foreign_net: yuan(0.04),
                  weighted_yield: "2.18",
                };
              }
              if (row.category_id === "interest_earning_assets") {
                return {
                  ...row,
                  cnx_scale: yuan(2800),
                  business_net_income: yuan(1.2),
                  weighted_yield: "2.35",
                };
              }
              return row;
            }),
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    await screen.findByTestId("product-category-derived-chart-tpl-scale-yield");

    const tplOption = readChartOption("product-category-derived-chart-tpl-scale-yield");
    expect(tplOption.legend?.data).toEqual([
      "人民币规模（亿元）",
      "外币规模（亿元）",
      "收益率（%）",
    ]);
    expect(tplOption.xAxis).toMatchObject({
      data: [
        "2026年01月",
        "2026年02月",
      ],
    });
    expect(tplOption.series?.map((series) => series.name)).toEqual([
      "人民币规模（亿元）",
      "外币规模（亿元）",
      "收益率（%）",
    ]);
    expect(tplOption.series?.map((series) => series.type)).toEqual(["bar", "bar", "line"]);
    expect(tplOption.series?.[0]?.data).toEqual([810, 865.79]);
    expect(tplOption.series?.[1]?.data).toEqual([12, -0.8]);
    expect(tplOption.series?.[2]?.data).toEqual([2.18, 2.31]);

    const netIncomeOption = readChartOption("product-category-derived-chart-currency-net-income");
    expect(netIncomeOption.legend?.data).toEqual([
      "人民币净收入（亿元）",
      "外币净收入（亿元）",
    ]);
    expect(netIncomeOption.series?.map((series) => series.name)).toEqual([
      "人民币净收入（亿元）",
      "外币净收入（亿元）",
    ]);
    expect(netIncomeOption.series?.[0]?.data).toEqual([2.12, 2.71]);
    expect(netIncomeOption.series?.[1]?.data).toEqual([0.18, 0.14]);

    const interestOption = readChartOption(
      "product-category-derived-chart-interest-earning-income-scale",
    );
    expect(interestOption.legend?.data).toEqual([
      "生息资产规模（亿元）",
      "生息资产收入（亿元）",
    ]);
    expect(interestOption.series?.map((series) => series.name)).toEqual([
      "生息资产规模（亿元）",
      "生息资产收入（亿元）",
    ]);
    expect(interestOption.series?.[0]?.data).toEqual([2800, 2898.5]);
    expect(interestOption.series?.[1]?.data).toEqual([1.2, 1.45]);

    expect(screen.queryByTestId("product-category-derived-chart-interest-spread")).not.toBeInTheDocument();

    const liabilityOption = readChartOption("product-category-liability-side-trend");
    expect(liabilityOption.legend?.data).toEqual([
      "负债端日均额（亿元）",
      "负债端利率（%）",
    ]);
    expect(liabilityOption.xAxis).toMatchObject({ data: ["2026年01月", "2026年02月"] });
    const liabilityMatrix = screen.getByTestId("product-category-liability-side-detail-matrix");
    expect(within(liabilityMatrix).getByText("2026年01月")).toBeInTheDocument();
    expect(within(liabilityMatrix).getByText("2026年02月")).toBeInTheDocument();
    expect(within(liabilityMatrix).getByText("环比月度变动情况")).toBeInTheDocument();
    expect(within(liabilityMatrix).getAllByText("日均额").length).toBeGreaterThanOrEqual(3);
    expect(within(liabilityMatrix).getAllByText("收益率").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByTestId("product-category-liability-side-detail-liability_total")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-liability-side-currency-matrix-cny")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-liability-side-currency-matrix-foreign")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("product-category-liability-side-currency-matrix-cny")).getAllByText("收益率").length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      within(screen.getByTestId("product-category-liability-side-currency-matrix-foreign")).getAllByText("收益率")
        .length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      screen.getByTestId("product-category-liability-side-currency-detail-cny-liability_total"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-liability-side-currency-detail-foreign-liability_total"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("product-category-liability-side-detail-credit_linked_notes")).toBeInTheDocument();
  });

  it("places a mobile liability-side detail matrix readout before the raw detail matrix", async () => {
    renderWorkbenchAppWithTwoMonthLiabilityTrend();

    await waitForTrendDiagnosticsAutoLoad();
    const rawMatrix = await screen.findByTestId("product-category-liability-side-detail-matrix");
    const readout = screen.getByTestId("product-category-liability-side-detail-matrix-mobile-readout");

    expect(readout.compareDocumentPosition(rawMatrix) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(readout).toHaveTextContent("1728.58");
    expect(readout).toHaveTextContent("1.63");
    expect(readout).toHaveTextContent("+5bp");
    expect(readout).toHaveTextContent("2");
  });

  it("places mobile liability-side currency readouts before each raw currency matrix", async () => {
    renderWorkbenchAppWithTwoMonthLiabilityTrend();

    await waitForTrendDiagnosticsAutoLoad();
    const cnyMatrix = await screen.findByTestId("product-category-liability-side-currency-matrix-cny");
    const foreignMatrix = screen.getByTestId("product-category-liability-side-currency-matrix-foreign");
    const cnyReadout = screen.getByTestId("product-category-liability-side-currency-matrix-cny-mobile-readout");
    const foreignReadout = screen.getByTestId(
      "product-category-liability-side-currency-matrix-foreign-mobile-readout",
    );

    expect(cnyReadout.compareDocumentPosition(cnyMatrix) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(foreignReadout.compareDocumentPosition(foreignMatrix) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(cnyReadout).toHaveTextContent("cny");
    expect(cnyReadout).toHaveTextContent("1729.55");
    expect(foreignReadout).toHaveTextContent("foreign");
    expect(foreignReadout).toHaveTextContent("0.97");
  });

  it("does not render all-currency spread comparison without backend spread fields", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const ratesByDate: Record<string, { asset: string; liability: string }> = {
      "2025-01-31": { asset: "2.20", liability: "1.60" },
      "2025-02-28": { asset: "2.28", liability: "1.63" },
      "2025-03-31": { asset: "2.35", liability: "1.65" },
      "2025-04-30": { asset: "2.28", liability: "1.60" },
      "2025-05-31": { asset: "2.29", liability: "1.60" },
      "2025-06-30": { asset: "2.32", liability: "1.60" },
      "2025-07-31": { asset: "2.31", liability: "1.60" },
      "2025-08-31": { asset: "2.33", liability: "1.60" },
      "2025-09-30": { asset: "2.34", liability: "1.60" },
      "2025-10-31": { asset: "2.36", liability: "1.60" },
      "2025-11-30": { asset: "2.38", liability: "1.60" },
      "2025-12-31": { asset: "2.40", liability: "1.60" },
      "2026-01-31": { asset: "2.40", liability: "1.65" },
      "2026-02-28": { asset: "2.48", liability: "1.68" },
      "2026-03-31": { asset: "2.55", liability: "1.70" },
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
            "2026-03-31",
            "2026-02-28",
            "2026-01-31",
            "2025-12-31",
            "2025-11-30",
            "2025-10-31",
            "2025-09-30",
            "2025-08-31",
            "2025-07-31",
            "2025-06-30",
            "2025-05-31",
            "2025-04-30",
            "2025-03-31",
            "2025-02-28",
            "2025-01-31",
          ],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const rates = ratesByDate[options.reportDate] ?? { asset: "2.00", liability: "1.50" };
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? { ...row, weighted_yield: rates.asset }
                : row,
            ),
            liability_total: {
              ...env.result.liability_total,
              weighted_yield: rates.liability,
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    expect(screen.queryByTestId("product-category-derived-chart-interest-spread-yoy")).not.toBeInTheDocument();
  });

  it("does not render CNY spread comparison without backend RMB spread fields", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const dateInputs: Record<string, { days: number; assetCny: number; liabilityCny: number }> = {
      "2025-01-31": { days: 31, assetCny: 2.2, liabilityCny: 1.5 },
      "2025-02-28": { days: 28, assetCny: 2.3, liabilityCny: 1.6 },
      "2025-03-31": { days: 31, assetCny: 2.35, liabilityCny: 1.65 },
      "2025-04-30": { days: 30, assetCny: 2.28, liabilityCny: 1.6 },
      "2025-05-31": { days: 31, assetCny: 2.29, liabilityCny: 1.6 },
      "2025-06-30": { days: 30, assetCny: 2.32, liabilityCny: 1.6 },
      "2025-07-31": { days: 31, assetCny: 2.31, liabilityCny: 1.6 },
      "2025-08-31": { days: 31, assetCny: 2.33, liabilityCny: 1.6 },
      "2025-09-30": { days: 30, assetCny: 2.34, liabilityCny: 1.6 },
      "2025-10-31": { days: 31, assetCny: 2.36, liabilityCny: 1.6 },
      "2025-11-30": { days: 30, assetCny: 2.38, liabilityCny: 1.6 },
      "2025-12-31": { days: 31, assetCny: 2.4, liabilityCny: 1.6 },
      "2026-01-31": { days: 31, assetCny: 2.4, liabilityCny: 1.55 },
      "2026-02-28": { days: 28, assetCny: 2.5, liabilityCny: 1.65 },
      "2026-03-31": { days: 31, assetCny: 2.55, liabilityCny: 1.7 },
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
            "2026-03-31",
            "2026-02-28",
            "2026-01-31",
            "2025-12-31",
            "2025-11-30",
            "2025-10-31",
            "2025-09-30",
            "2025-08-31",
            "2025-07-31",
            "2025-06-30",
            "2025-05-31",
            "2025-04-30",
            "2025-03-31",
            "2025-02-28",
            "2025-01-31",
          ],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const rates = dateInputs[options.reportDate] ?? { days: 31, assetCny: 2, liabilityCny: 1.5 };
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? {
                    ...row,
                    cny_scale: yuan(100),
                    cny_cash: fixtureCashAmount(100, rates.assetCny, rates.days),
                    weighted_yield: "9.99",
                  }
                : row,
            ),
            liability_total: {
              ...env.result.liability_total,
              cny_scale: yuan(80),
              cny_cash: fixtureCashAmount(80, rates.liabilityCny, rates.days),
              weighted_yield: "1.00",
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    expect(screen.queryByTestId("product-category-derived-chart-interest-spread-yoy-cny")).not.toBeInTheDocument();
  });

  it("renders a two-year comparison chart for intermediate business income from the governed row only", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const incomeByDate: Record<string, number | null> = {
      "2025-01-31": 1,
      "2025-02-28": 2,
      "2025-03-31": 3,
      "2025-04-30": 4,
      "2025-05-31": 5,
      "2025-06-30": 6,
      "2025-07-31": 7,
      "2025-08-31": 8,
      "2025-09-30": 9,
      "2025-10-31": 10,
      "2025-11-30": 11,
      "2025-12-31": 12,
      "2026-01-31": 21,
      "2026-02-28": 22,
      "2026-03-31": 23,
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
            "2026-03-31",
            "2026-02-28",
            "2026-01-31",
            "2025-12-31",
            "2025-11-30",
            "2025-10-31",
            "2025-09-30",
            "2025-08-31",
            "2025-07-31",
            "2025-06-30",
            "2025-05-31",
            "2025-04-30",
            "2025-03-31",
            "2025-02-28",
            "2025-01-31",
          ],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const income = incomeByDate[options.reportDate];
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "intermediate_business_income"
                ? {
                    ...row,
                    business_net_income: income === null ? row.business_net_income : yuan(income ?? 0),
                    cny_net: income === null ? row.cny_net : yuan(income ?? 0),
                  }
                : row,
            ),
            asset_total: {
              ...env.result.asset_total,
              business_net_income: yuan(999),
            },
            grand_total: {
              ...env.result.grand_total,
              business_net_income: yuan(-999),
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    await screen.findByTestId("product-category-derived-chart-intermediate-business-income-yoy");
    const incomeOption = readChartOption("product-category-derived-chart-intermediate-business-income-yoy");

    expect(incomeOption.legend?.data).toEqual(["\u0032\u0030\u0032\u0035\u5e74", "\u0032\u0030\u0032\u0036\u5e74"]);
    expect(incomeOption.xAxis).toMatchObject({
      data: [
        "\u0031\u6708",
        "\u0032\u6708",
        "\u0033\u6708",
        "\u0034\u6708",
        "\u0035\u6708",
        "\u0036\u6708",
        "\u0037\u6708",
        "\u0038\u6708",
        "\u0039\u6708",
        "\u0031\u0030\u6708",
        "\u0031\u0031\u6708",
        "\u0031\u0032\u6708",
      ],
    });
    expect(incomeOption.series?.map((series) => series.data)).toEqual([
      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
      [21, 22, 23, null, null, null, null, null, null, null, null, null],
    ]);
  });

  it("keeps interest-spread attribution incomplete when backend spread fields are absent", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const dateInputs: Record<
      string,
      {
        days: number;
        asset: string;
        liability: string;
        assetCny: number;
        liabilityCny: number;
      }
    > = {
      "2025-01-31": { days: 31, asset: "2.20", liability: "1.60", assetCny: 2.2, liabilityCny: 1.5 },
      "2025-02-28": { days: 28, asset: "2.28", liability: "1.63", assetCny: 2.3, liabilityCny: 1.6 },
      "2025-03-31": { days: 31, asset: "2.35", liability: "1.65", assetCny: 2.3, liabilityCny: 1.6 },
      "2025-12-31": { days: 31, asset: "2.40", liability: "1.60", assetCny: 2.4, liabilityCny: 1.6 },
      "2026-01-31": { days: 31, asset: "2.40", liability: "1.65", assetCny: 2.4, liabilityCny: 1.55 },
      "2026-02-28": { days: 28, asset: "2.48", liability: "1.68", assetCny: 2.5, liabilityCny: 1.65 },
      "2026-03-31": { days: 31, asset: "2.55", liability: "1.70", assetCny: 2.55, liabilityCny: 1.7 },
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
            "2026-03-31",
            "2026-02-28",
            "2026-01-31",
            "2025-12-31",
            "2025-03-31",
            "2025-02-28",
            "2025-01-31",
          ],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const rates = dateInputs[options.reportDate] ?? dateInputs["2026-03-31"]!;
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? {
                    ...row,
                    cny_scale: yuan(100),
                    cny_cash: fixtureCashAmount(100, rates.assetCny, rates.days),
                    weighted_yield: rates.asset,
                  }
                : row,
            ),
            liability_total: {
              ...env.result.liability_total,
              cny_scale: yuan(80),
              cny_cash: fixtureCashAmount(80, rates.liabilityCny, rates.days),
              weighted_yield: rates.liability,
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    const attribution = await screen.findByTestId("product-category-interest-spread-attribution");
    await waitFor(() => {
      expect(attribution).toHaveTextContent("\u5168\u53e3\u5f84");
      expect(attribution).toHaveTextContent("\u0033\u6708");
      expect(attribution).toHaveTextContent("\u90e8\u5206\u6570\u636e\u4f7f\u7528\u56de\u9000\u503c");
    });
    expect(screen.queryByTestId("product-category-derived-chart-interest-spread-yoy")).not.toBeInTheDocument();
    expect(screen.queryByTestId("product-category-derived-chart-interest-spread-yoy-cny")).not.toBeInTheDocument();
  });

  it("does not offer CNY linked attribution when backend RMB spread fields are absent", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const dateInputs: Record<
      string,
      { days: number; asset: string; liability: string; assetCny: number; liabilityCny: number }
    > = {
      "2025-02-28": { days: 28, asset: "2.28", liability: "1.63", assetCny: 2.3, liabilityCny: 1.6 },
      "2025-03-31": { days: 31, asset: "2.35", liability: "1.65", assetCny: 2.3, liabilityCny: 1.6 },
      "2026-02-28": { days: 28, asset: "2.48", liability: "1.68", assetCny: 2.5, liabilityCny: 1.65 },
      "2026-03-31": { days: 31, asset: "2.55", liability: "1.70", assetCny: 2.55, liabilityCny: 1.7 },
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-03-31", "2026-02-28", "2025-03-31", "2025-02-28"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        const rates = dateInputs[options.reportDate] ?? dateInputs["2026-03-31"]!;
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? {
                    ...row,
                    cny_scale: yuan(100),
                    cny_cash: fixtureCashAmount(100, rates.assetCny, rates.days),
                    weighted_yield: rates.asset,
                  }
                : row,
            ),
            liability_total: {
              ...env.result.liability_total,
              cny_scale: yuan(80),
              cny_cash: fixtureCashAmount(80, rates.liabilityCny, rates.days),
              weighted_yield: rates.liability,
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    await screen.findByTestId("product-category-interest-spread-attribution");
    expect(screen.queryByTestId("product-category-derived-chart-interest-spread-yoy-cny")).not.toBeInTheDocument();

    const monthSelect = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    await user.selectOptions(monthSelect, "2026-02-28");
    await waitForTrendDiagnosticsAutoLoad();

    await waitFor(() => {
      expect(screen.getByTestId("product-category-interest-spread-attribution")).toHaveTextContent(
        "\u5168\u53e3\u5f84",
      );
      expect(screen.getByTestId("product-category-interest-spread-attribution")).toHaveTextContent(
        "\u0032\u6708",
      );
      expect(screen.getByTestId("product-category-interest-spread-attribution")).toHaveTextContent(
        "\u90e8\u5206\u6570\u636e\u4f7f\u7528\u56de\u9000\u503c",
      );
    });
  });

  it("keeps the interest-spread attribution panel visible when comparable prior data is missing", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-03-31"],
        }),
      ),
    });

    await waitForTrendDiagnosticsAutoLoad();
    const panel = await screen.findByTestId("product-category-interest-spread-attribution");
    expect(panel).toHaveTextContent("\u5f85\u8865\u6570");
    expect(panel).toHaveTextContent("\u7f3a\u5c11\u4e0a\u5e74\u540c\u6708\u6570\u636e");
  });

  it("does not render an interest spread trend chart from asset and liability yields alone", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(buildMockProductCategoryPnlEnvelope(options));
        if (options.reportDate !== "2026-01-31") {
          return {
            ...env,
            result: {
              ...env.result,
              rows: env.result.rows.map((row) =>
                row.category_id === "interest_earning_assets"
                  ? { ...row, weighted_yield: "4.20" }
                  : row,
              ),
              asset_total: { ...env.result.asset_total, weighted_yield: "4.20" },
              liability_total: { ...env.result.liability_total, weighted_yield: "4.80" },
            },
          };
        }
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? { ...row, weighted_yield: "4.00" }
                : row,
            ),
            asset_total: { ...env.result.asset_total, weighted_yield: "4.00" },
            liability_total: { ...env.result.liability_total, weighted_yield: "4.50" },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    await waitFor(() => {
      expect(screen.queryByTestId("product-category-derived-chart-interest-spread")).not.toBeInTheDocument();
    });
  });

  it("builds derived charts on 2025 quarter-end points, 2025 Nov-Dec, and 2026 Jan-Mar with one view basis", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn(async (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
      buildMockProductCategoryPnlEnvelope(options),
    );
    const getProductCategoryAttribution = vi.fn(baseClient.getProductCategoryAttribution);
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
            "2026-03-31",
            "2026-02-28",
            "2026-01-31",
            "2025-12-31",
            "2025-11-30",
            "2025-10-31",
            "2025-09-30",
            "2025-06-30",
            "2025-03-31",
          ],
        }),
      ),
      getProductCategoryPnl,
      getProductCategoryAttribution,
    });

    await screen.findByTestId("product-category-table");
    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        view: "monthly",
      });
    });
    await screen.findByTestId("product-category-derived-chart-tpl-scale-yield");
    await waitFor(() => {
      const tplOption = readChartOption("product-category-derived-chart-tpl-scale-yield");
      expect(tplOption.xAxis).toMatchObject({
        data: [
          "\u0032\u0030\u0032\u0035\u5e74Q\u0031",
          "\u0032\u0030\u0032\u0035\u5e74Q\u0032",
          "\u0032\u0030\u0032\u0035\u5e74Q\u0033",
          "\u0032\u0030\u0032\u0035\u5e74\u0031\u0031\u6708",
          "\u0032\u0030\u0032\u0035\u5e74\u0031\u0032\u6708",
          "\u0032\u0030\u0032\u0036\u5e74\u0030\u0031\u6708",
          "\u0032\u0030\u0032\u0036\u5e74\u0030\u0032\u6708",
          "\u0032\u0030\u0032\u0036\u5e74\u0030\u0033\u6708",
        ],
      });
    });
    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledTimes(9);
    });
    const trendHistoryCalls = getProductCategoryPnl.mock.calls
      .map((call) => call[0])
      .filter((options) => options.reportDate !== "2026-03-31")
      .map((options) => `${options.reportDate}:${options.view}`)
      .sort();
    const currentCall = getProductCategoryPnl.mock.calls
      .map((call) => call[0])
      .filter((options) => options.reportDate === "2026-03-31")
      .map((options) => `${options.reportDate}:${options.view}`);

    expect(currentCall).toEqual(["2026-03-31:monthly"]);
    expect(trendHistoryCalls).toEqual([
      "2025-03-31:monthly",
      "2025-06-30:monthly",
      "2025-09-30:monthly",
      "2025-10-31:monthly",
      "2025-11-30:monthly",
      "2025-12-31:monthly",
      "2026-01-31:monthly",
      "2026-02-28:monthly",
    ]);
    await waitFor(() => {
      expect(
        getProductCategoryAttribution.mock.calls.filter((call) => call[0].reportDate !== "2026-03-31"),
      ).toHaveLength(7);
    });
    const historyAttributionCalls = getProductCategoryAttribution.mock.calls
      .map((call) => call[0])
      .filter((options) => options.reportDate !== "2026-03-31")
      .map((options) => `${options.reportDate}:${options.compare ?? "mom"}`)
      .sort();
    expect(historyAttributionCalls).toEqual([
      "2025-03-31:mom",
      "2025-06-30:mom",
      "2025-09-30:mom",
      "2025-11-30:mom",
      "2025-12-31:mom",
      "2026-01-31:mom",
      "2026-02-28:mom",
    ]);

    getProductCategoryPnl.mockClear();
    getProductCategoryAttribution.mockClear();
    const viewButtons = within(screen.getByRole("group", { name: "视图模式" })).getAllByRole("button");
    await user.click(viewButtons[1]!);
    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledWith({
        reportDate: "2026-03-31",
        view: "ytd",
      });
    });

    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledTimes(9);
    });
    const ytdCalls = getProductCategoryPnl.mock.calls
      .map((call) => call[0])
      .map((options) => `${options.reportDate}:${options.view}`)
      .sort();
    expect(ytdCalls).toEqual([
      "2025-03-31:ytd",
      "2025-06-30:ytd",
      "2025-09-30:ytd",
      "2025-10-31:ytd",
      "2025-11-30:ytd",
      "2025-12-31:ytd",
      "2026-01-31:ytd",
      "2026-02-28:ytd",
      "2026-03-31:ytd",
    ]);
  });
  it("Unit 2: formal detail table renders frozen backend fields in column order without metric_id invention", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...env,
          result: {
            ...env.result,
            available_views: ["monthly", "qtd", "ytd", "year_to_report_month_end"],
            rows: env.result.rows.map((r) => {
              if (r.category_id === "repo_assets") {
                return {
                  ...r,
                  cnx_scale: "101000000",
                  cny_scale: "102000000",
                  foreign_scale: "103000000",
                  cnx_cash: "104000000",
                  cny_cash: "105000000",
                  cny_ftp: "106000000",
                  cny_net: "-107000000",
                  foreign_cash: "108000000",
                  foreign_ftp: "109000000",
                  foreign_net: "-110000000",
                  business_net_income: "111000000",
                  weighted_yield: "2.345",
                };
              }
              if (r.category_id === "interbank_deposits") {
                return {
                  ...r,
                  category_name: "liability delta fixture",
                  cnx_scale: "-57850000000",
                  cny_scale: "-57906000000",
                  foreign_scale: "56000000",
                  cnx_cash: "-104000000",
                  cny_cash: "-105000000",
                  cny_ftp: "-106000000",
                  cny_net: "-107000000",
                  foreign_cash: "108000000",
                  foreign_ftp: "109000000",
                  foreign_net: "110000000",
                  business_net_income: "-111000000",
                  weighted_yield: "1.234",
                };
              }
              return r;
            }),
          },
        };
      }),
    });

    const table = await screen.findByTestId("product-category-table");
    const assetRow = within(table).getByText("买入返售").closest("tr");
    expect(assetRow).toBeTruthy();
    expect(within(assetRow as HTMLElement).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "买入返售",
      "1.01",
      "1.02",
      "1.03",
      "1.04",
      "1.05",
      "1.06",
      "-1.07",
      "1.08",
      "1.09",
      "-1.10",
      "1.11",
      "2.35",
    ]);
    const liabilityDeltaRow = within(table).getByText("liability delta fixture").closest("tr");
    expect(liabilityDeltaRow).toBeTruthy();
    expect(within(liabilityDeltaRow as HTMLElement).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "liability delta fixture",
      "578.50",
      "579.06",
      "-0.56",
      "1.04",
      "1.05",
      "1.06",
      "1.07",
      "-1.08",
      "-1.09",
      "-1.10",
      "1.11",
      "1.23",
    ]);

    const viewGroup = screen.getByRole("group", { name: "视图模式" });
    expect(within(viewGroup).getAllByRole("button")).toHaveLength(2);
    expect(within(viewGroup).queryByText("qtd")).not.toBeInTheDocument();
    expect(within(viewGroup).queryByText("year_to_report_month_end")).not.toBeInTheDocument();
  });

  it("Unit 9: table 营业减收入 uses liability absolute and asset signed display, and grand_total is only in footer (not in tbody)", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const negYuan = "-123456789";
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((r) => {
              if (r.category_id === "repo_liabilities") {
                return { ...r, business_net_income: negYuan };
              }
              if (r.category_id === "repo_assets") {
                return { ...r, business_net_income: negYuan };
              }
              return r;
            }),
          },
        };
      }),
    });
    const table = await screen.findByTestId("product-category-table");
    const liabilityRow = within(table).getByText("卖出回购").closest("tr");
    const assetRow = within(table).getByText("买入返售").closest("tr");
    expect(liabilityRow).toBeTruthy();
    expect(assetRow).toBeTruthy();
    const liabilityCells = within(liabilityRow as HTMLElement).getAllByRole("cell");
    const assetCells = within(assetRow as HTMLElement).getAllByRole("cell");
    // 营业减收入 = 倒数第二列；加权收益率 = 最后一列（与表头一致，避免列序魔法数漂移）
    expect(liabilityCells.at(-2)).toHaveTextContent("1.23");
    expect(assetCells.at(-2)).toHaveTextContent("-1.23");
    expect(liabilityCells.at(-1)).toHaveTextContent("1.41");
    expect(assetCells.at(-1)).toHaveTextContent("1.47");
    expect(within(table).queryByText("grand_total")).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-footer-total")).toHaveTextContent("2.85");
  });

  it("Unit 9: formal baseline refetch failure shows AsyncSection error; no stale table, summary, or footer", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const uniqueMarker = "unit9-formal-asyncsection-stale-marker";
    let denyBaselinePnl = false;
    const pnlSpy = vi.fn(async (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) => {
      if (denyBaselinePnl) {
        throw new Error("unit9-baseline-refetch-failed");
      }
      const env = buildMockProductCategoryPnlEnvelope(options);
      return {
        ...env,
        result: {
          ...env.result,
          rows: env.result.rows.map((r) =>
            r.category_id === "repo_assets" ? { ...r, category_name: uniqueMarker } : r,
          ),
        },
      };
    });
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:unit9-formal-error",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: pnlSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    const table = await screen.findByTestId("product-category-table");
    expect(within(table).getByText(uniqueMarker)).toBeInTheDocument();
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent("合计：");
    expect(screen.getByTestId("product-category-footer-total")).toHaveTextContent(
      "全部市场科目 + 投资收益合计：",
    );

    denyBaselinePnl = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    const formalLead = await screen.findByTestId("product-category-formal-table-lead");
    const formalSection = formalLead.nextElementSibling as HTMLElement | null;
    expect(formalSection).toBeTruthy();

    await waitFor(() => {
      expect(within(formalSection!).getByText("数据载入失败。")).toBeInTheDocument();
      expect(
        within(formalSection!).getByText("当前页面保留重试入口，不在浏览器端自行拼接正式口径。"),
      ).toBeInTheDocument();
    });
    expect(within(formalSection!).getByRole("button", { name: "重试" })).toBeInTheDocument();

    expect(screen.queryByTestId("product-category-table")).not.toBeInTheDocument();
    expect(screen.queryByText(uniqueMarker)).not.toBeInTheDocument();
    expect(screen.queryByTestId("product-category-summary")).not.toBeInTheDocument();
    expect(screen.queryByTestId("product-category-footer-total")).not.toBeInTheDocument();

    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(pnlSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
  it("pins the requested FTP scenarios and defaults 2026 reports to 1.6 before explicit apply", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const ftpSelect = screen.getByRole("combobox", { name: "FTP 场景" }) as HTMLSelectElement;
    expect(Array.from(ftpSelect.options).map((option) => [option.value, option.textContent])).toEqual([
      ["2.00", "2.0%"],
      ["1.75", "1.75%"],
      ["1.60", "1.6%"],
      ["1.50", "1.5%"],
    ]);
    await waitFor(() => {
      expect(ftpSelect.value).toBe("1.60");
    });
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent("当前场景：1.75%");

    await user.click(screen.getByTestId("product-category-apply-scenario-button"));
    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent("当前场景：1.60%");
      expect(screen.getByTestId("product-category-result-meta-scenario")).toHaveTextContent(
        "场景覆盖",
      );
    });
  });

  it("resets the FTP scenario to the selected report year default when switching months", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pnlSpy = vi.fn((options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
      baseClient.getProductCategoryPnl(options),
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2025-12-31"],
        }),
      ),
      getProductCategoryPnl: pnlSpy,
    });

    await screen.findByTestId("product-category-table");
    const [monthSelect, ftpSelect] = screen.getAllByRole("combobox") as HTMLSelectElement[];
    await waitFor(() => {
      expect(ftpSelect.value).toBe("1.60");
    });

    await user.selectOptions(ftpSelect, "2.00");
    await user.click(screen.getByTestId("product-category-apply-scenario-button"));
    await waitFor(() => {
      expect(pnlSpy).toHaveBeenCalledWith(expect.objectContaining({ scenarioRatePct: "2.00" }));
    });
    const callsBeforeSwitch = pnlSpy.mock.calls.length;

    await user.selectOptions(monthSelect, "2025-12-31");
    await waitFor(() => {
      expect(ftpSelect.value).toBe("1.75");
      expect(pnlSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reportDate: "2025-12-31",
          scenarioRatePct: "1.75",
        }),
      );
    });
    expect(
      pnlSpy.mock.calls
        .slice(callsBeforeSwitch)
        .some(
          ([options]) =>
            options?.reportDate === "2025-12-31" && options.scenarioRatePct === "2.00",
        ),
    ).toBe(false);
  });

  it("applies a scenario rate only after the apply action", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    await user.selectOptions(screen.getByRole("combobox", { name: "FTP 场景" }), "2.00");
    await user.click(screen.getByTestId("product-category-apply-scenario-button"));

    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent("2.00");
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent("0.52");
      expect(screen.getByTestId("product-category-result-meta-scenario")).toHaveTextContent(
        "场景覆盖",
      );
      expect(screen.getByTestId("product-category-result-meta-scenario")).toHaveTextContent(
        "是",
      );
      const distinct = screen.getByTestId("product-category-formal-scenario-meta-distinct");
      expect(distinct).toHaveTextContent("正式口径=正式口径");
      expect(distinct).toHaveTextContent("情景口径=情景口径");
      expect(distinct).toHaveTextContent("追踪编号=mock_product_category_pnl.detail");
    });
  });

  it("surfaces degraded result_meta (fallback, vendor, quality) in the governance strip, not only inside the meta panel", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...env,
          result_meta: {
            ...env.result_meta,
            fallback_mode: "latest_snapshot" as const,
            vendor_status: "vendor_stale" as const,
            quality_flag: "warning" as const,
          },
        };
      }),
    });

    await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "quality=warning",
    );
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "vendor=vendor_stale",
    );
    expect(screen.getByTestId("product-category-formal-readiness-status")).toHaveTextContent(
      "fallback=latest_snapshot",
    );
    expect(screen.getByTestId("product-category-formal-readiness-band")).toHaveTextContent(
      "data-state-review-required",
    );
    expect(screen.getByTestId("product-category-governance-notice-fallback_mode")).toHaveTextContent(
      "最新快照降级",
    );
    expect(screen.getByTestId("product-category-governance-notice-vendor_status")).toHaveTextContent(
      "供应商数据陈旧",
    );
    expect(screen.getByTestId("product-category-governance-notice-quality_flag")).toHaveTextContent(
      "预警",
    );
  });

  it("Unit 3: refresh shows in-flight status (queued→running), disables refresh, then records last run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "product_category_pnl:test-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
    }));
    const statusSpy = vi.fn();
    statusSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                status: "running",
                run_id: "product_category_pnl:test-run",
                job_name: "product_category_pnl",
                trigger_mode: "async",
                cache_key: "product_category_pnl.formal",
              }),
            100,
          ),
        ),
    );
    statusSpy.mockResolvedValueOnce({
      status: "completed",
      run_id: "product_category_pnl:test-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
      getProductCategoryRefreshStatus: statusSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-refresh-button"));

    expect(screen.getByTestId("product-category-refresh-button")).toBeDisabled();

    await waitFor(() => {
      const statusLine = screen.getByTestId("product-category-refresh-status");
      expect(statusLine).toHaveTextContent("queued");
      expect(statusLine).toHaveTextContent("product_category_pnl:test-run");
    });

    await waitFor(() => {
      const statusLine = screen.getByTestId("product-category-refresh-status");
      expect(statusLine).toHaveTextContent("running");
    });

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(statusSpy).toHaveBeenCalledTimes(2);
      expect(statusSpy).toHaveBeenCalledWith("product_category_pnl:test-run");
      expect(screen.getByTestId("product-category-refresh-button")).not.toBeDisabled();
    });

    expect(screen.queryByTestId("product-category-refresh-status")).not.toBeInTheDocument();
    expect(screen.getByText(/^最近刷新任务：/)).toHaveTextContent("product_category_pnl:test-run");
  });

  it("surfaces refresh conflict (409) with explicit copy and does not record a successful run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => {
      throw new ActionRequestError("Product-category refresh already in progress.", {
        status: 409,
      });
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();

    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText("Product-category refresh already in progress."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("product-category-refresh-status")).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-refresh-button")).toHaveTextContent("刷新损益数据");
  });

  it("surfaces sync-fallback service failure (503) with explicit copy and does not record a successful run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => {
      throw new ActionRequestError("Product-category refresh failed during sync fallback.", {
        status: 503,
      });
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText("Product-category refresh failed during sync fallback."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("product-category-refresh-status")).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-refresh-button")).toHaveTextContent("刷新损益数据");
  });

  it("surfaces terminal failed refresh status as an error (not silent success)", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "product_category_pnl:failed-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
    }));
    const statusSpy = vi.fn(async () => ({
      status: "failed",
      run_id: "product_category_pnl:failed-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
      detail: "Product-category refresh run failed (test).",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
      getProductCategoryRefreshStatus: statusSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(screen.getByText("Product-category refresh run failed (test).")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("product-category-refresh-status")).not.toBeInTheDocument();
    expect(screen.getByText(/product_category_pnl:failed-run/)).toBeInTheDocument();
    expect(screen.getByTestId("product-category-refresh-button")).toHaveTextContent("刷新损益数据");
  });

  it("Unit 4: rejects a manual create when report_date is missing (no API call)", async () => {
    const user = userEvent.setup();
    const createAdjustmentSpy = vi.fn();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope(
          "product_category_pnl.dates",
          { report_dates: [] },
          { generated_at: "2026-05-01T12:00:00Z" },
        ),
      ),
      createProductCategoryManualAdjustment: createAdjustmentSpy,
    });

    await screen.findByTestId("product-category-governance-strip");
    await user.click(screen.getByTestId("product-category-manual-button"));
    const form = screen.getByTestId("product-category-manual-form");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      const err = within(form).getByTestId("product-category-manual-error");
      expect(err).toHaveTextContent("请选择报表月份。");
    });
    expect(createAdjustmentSpy).not.toHaveBeenCalled();
  });
  it("Unit 4: rejects a manual create when account code is empty (no API call)", async () => {
    const user = userEvent.setup();
    const createAdjustmentSpy = vi.fn();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      createProductCategoryManualAdjustment: createAdjustmentSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-manual-button"));
    const form = screen.getByTestId("product-category-manual-form");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      const err = within(form).getByTestId("product-category-manual-error");
      expect(err).toHaveTextContent("请输入科目代码。");
    });
    expect(createAdjustmentSpy).not.toHaveBeenCalled();
  });
  it("Unit 4: rejects a manual create when all amount fields are empty (no API call)", async () => {
    const user = userEvent.setup();
    const createAdjustmentSpy = vi.fn();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      createProductCategoryManualAdjustment: createAdjustmentSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-manual-button"));
    const form = screen.getByTestId("product-category-manual-form");
    await user.type(
      within(form).getByRole("textbox", { name: "手工录入-科目代码" }),
      "13304010001",
    );
    await user.type(
      within(form).getByRole("textbox", { name: "手工录入-科目名称" }),
      "test-account",
    );
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      const err = within(form).getByTestId("product-category-manual-error");
      expect(err).toHaveTextContent("至少填写一个调整数值。");
    });
    expect(createAdjustmentSpy).not.toHaveBeenCalled();
  });
  it("Unit 4: accepts a manual create when only beginning_balance is filled among amount fields", async () => {
    const user = userEvent.setup();
    const createAdjustmentSpy = vi.fn(
      async (
        _payload: Parameters<
          ReturnType<typeof createApiClient>["createProductCategoryManualAdjustment"]
        >[0],
      ) => ({
        adjustment_id: "pca-unit4-beginning-only",
        event_type: "created",
        created_at: "2026-04-10T09:40:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: "2026-02-28",
        operator: "DELTA",
        approval_status: "approved",
        account_code: "13304010001",
        currency: "CNX",
        account_name: "test-account",
        monthly_pnl: null,
        beginning_balance: "7",
        ending_balance: null,
        daily_avg_balance: null,
        annual_avg_balance: null,
      }),
    );
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:unit4-beginning-only",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      createProductCategoryManualAdjustment: createAdjustmentSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-manual-button"));
    const form = screen.getByTestId("product-category-manual-form");
    await user.type(
      within(form).getByRole("textbox", { name: "手工录入-科目代码" }),
      "13304010001",
    );
    await user.type(
      within(form).getByRole("textbox", { name: "手工录入-期初余额" }),
      "7",
    );
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      expect(createAdjustmentSpy).toHaveBeenCalledTimes(1);
    });
    expect(createAdjustmentSpy.mock.calls[0]![0]).toMatchObject({
      report_date: "2026-02-28",
      account_code: "13304010001",
      beginning_balance: "7",
      monthly_pnl: null,
      ending_balance: null,
      daily_avg_balance: null,
      annual_avg_balance: null,
    });
    expect(refreshSpy).toHaveBeenCalled();
  });

  it("Unit 4: submits a manual adjustment and refreshes afterwards", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const datesSpy = vi.fn(baseClient.getProductCategoryDates);
    const createAdjustmentSpy = vi.fn(async () => ({
      adjustment_id: "pca-test-1",
      event_type: "created",
      created_at: "2026-04-10T09:40:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "13304010001",
      currency: "CNX",
      account_name: "test-account",
      monthly_pnl: "5",
      beginning_balance: null,
      ending_balance: null,
      daily_avg_balance: null,
      annual_avg_balance: null,
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:refresh-after-adjustment",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: datesSpy,
      createProductCategoryManualAdjustment: createAdjustmentSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-manual-button"));

    const form = screen.getByTestId("product-category-manual-form");
    const textboxes = within(form).getAllByRole("textbox");
    await user.type(textboxes[1]!, "13304010001");
    await user.type(textboxes[2]!, "test-account");
    await user.type(textboxes[5]!, "5");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      expect(createAdjustmentSpy).toHaveBeenCalledTimes(1);
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/pca-test-1/)).toBeInTheDocument();
    });
    // dates 查询的 queryKey 不依赖 selectedDate，refetch 在异步提交闭包中仍能命中同一查询；
    // baseline / adjustments 在 dates refetch 后若触发重渲染与日期对齐，其 refetch 可能落在新的 query 实例上，
    // 故用 getProductCategoryDates 的第二次调用来钉住「任务完成后再次拉取」。
    expect(datesSpy).toHaveBeenCalledTimes(2);
  });

  it("shows adjustment summary on the main page and keeps full timeline in audit view", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const confirmSpy = vi.spyOn(window, "confirm");
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 2,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-existing-1",
          created_at: "2026-04-10T09:30:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account",
          event_type: "edited",
          monthly_pnl: "6",
        },
      ],
      events: [
        {
          adjustment_id: "pca-existing-1",
          created_at: "2026-04-10T09:35:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account",
          event_type: "edited",
          monthly_pnl: "6",
        },
        {
          adjustment_id: "pca-existing-1",
          created_at: "2026-04-10T09:30:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account",
          event_type: "created",
          monthly_pnl: "5",
        },
      ],
    }));
    const revokeSpy = vi.fn(async () => ({
      adjustment_id: "pca-existing-1",
      event_type: "revoked",
      created_at: "2026-04-10T09:35:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "rejected",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "test-account",
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:revoke-refresh",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    try {
      renderWorkbenchAppWithClient({
        ...baseClient,
        getProductCategoryManualAdjustments: listSpy,
        revokeProductCategoryManualAdjustment: revokeSpy,
        refreshProductCategoryPnl: refreshSpy,
      });

      await screen.findByTestId("product-category-adjustment-history");
      expect(screen.queryByTestId("product-category-event-pca-existing-1-edited")).not.toBeInTheDocument();
      expect(screen.getByTestId("product-category-adjustment-history")).toHaveTextContent("2");
      expect(screen.getByTestId("product-category-audit-link")).toHaveAttribute(
        "href",
        "/product-category-pnl/audit",
      );

      const revokeButton = screen.getByTestId("product-category-revoke-pca-existing-1");
      confirmSpy.mockReturnValueOnce(false);
      await user.click(revokeButton);
      expect(confirmSpy).toHaveBeenCalledTimes(1);
      expect(revokeSpy).not.toHaveBeenCalled();
      expect(refreshSpy).not.toHaveBeenCalled();

      confirmSpy.mockReturnValueOnce(true);
      await user.click(revokeButton);

      await waitFor(() => {
        expect(revokeSpy).toHaveBeenCalledWith("pca-existing-1");
        expect(refreshSpy).toHaveBeenCalledTimes(1);
      });
      expect(confirmSpy).toHaveBeenCalledTimes(2);
    } finally {
      confirmSpy.mockRestore();
    }
  });

  it("Unit 5: main adjustment summary refetch failure hides stale rows and keeps retry available", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const staleMarker = "unit5-main-stale-adjustment";
    let denyAdjustments = false;
    const listSpy = vi.fn(async () => {
      if (denyAdjustments) {
        throw new Error("unit5-main-adjustment-refetch-failed");
      }
      return {
        report_date: "2026-02-28",
        adjustment_count: 1,
        adjustment_limit: 20,
        adjustment_offset: 0,
        event_total: 1,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          {
            adjustment_id: "pca-main-stale-1",
            created_at: "2026-04-10T09:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: staleMarker,
            event_type: "edited",
            monthly_pnl: "6",
          },
        ],
        events: [
          {
            adjustment_id: "pca-main-stale-1",
            created_at: "2026-04-10T09:35:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: staleMarker,
            event_type: "edited",
            monthly_pnl: "6",
          },
        ],
      };
    });
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:unit5-main-adjustment-error",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    const history = await screen.findByTestId("product-category-adjustment-history");
    expect(within(history).getByText(staleMarker)).toBeInTheDocument();

    denyAdjustments = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    const adjustmentLead = await screen.findByTestId("product-category-adjustment-lead");
    const adjustmentSection = adjustmentLead.nextElementSibling as HTMLElement | null;
    expect(adjustmentSection).toBeTruthy();

    await waitFor(() => {
      expect(within(adjustmentSection!).getByText("数据载入失败。")).toBeInTheDocument();
    });
    expect(within(adjustmentSection!).getByRole("button", { name: "重试" })).toBeInTheDocument();
    expect(within(adjustmentSection!).queryByTestId("product-category-adjustment-history")).not.toBeInTheDocument();
    expect(screen.queryByText(staleMarker)).not.toBeInTheDocument();
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(listSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("edits and restores a rejected adjustment", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 0,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-existing-2",
          created_at: "2026-04-10T09:40:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "rejected",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account-2",
          event_type: "rejected",
          monthly_pnl: "8",
        },
      ],
      events: [],
    }));
    const editSpy = vi.fn(async () => ({
      adjustment_id: "pca-existing-2",
      created_at: "2026-04-10T09:45:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "rejected",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "test-account-2",
      event_type: "edited",
      monthly_pnl: "9",
    }));
    const restoreSpy = vi.fn(async () => ({
      adjustment_id: "pca-existing-2",
      created_at: "2026-04-10T09:50:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "test-account-2",
      event_type: "restored",
      monthly_pnl: "9",
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:edit-restore-refresh",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
      updateProductCategoryManualAdjustment: editSpy,
      restoreProductCategoryManualAdjustment: restoreSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-adjustment-history");
    await user.click(screen.getByTestId("product-category-edit-pca-existing-2"));

    const form = screen.getByTestId("product-category-manual-form");
    const textboxes = within(form).getAllByRole("textbox");
    await user.clear(textboxes[5]!);
    await user.type(textboxes[5]!, "9");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      expect(editSpy).toHaveBeenCalledTimes(1);
      expect(refreshSpy).toHaveBeenCalledTimes(1);
    });

    const restoreButton = await screen.findByTestId("product-category-restore-pca-existing-2");
    await waitFor(() => {
      expect(restoreButton).not.toBeDisabled();
    });
    await user.click(restoreButton);

    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith("pca-existing-2");
      expect(refreshSpy).toHaveBeenCalledTimes(2);
    });
  });

  it("disables revoke/restore by approval_status and states lifecycle refresh in the adjustment lead", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const rowBase = {
      created_at: "2026-04-10T09:00:00Z",
      stream: "product_category_pnl_adjustments" as const,
      report_date: "2026-02-28",
      operator: "DELTA" as const,
      account_code: "51402010001",
      currency: "CNX" as const,
      account_name: "x",
      event_type: "created" as const,
      monthly_pnl: "1",
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: async () => ({
        report_date: "2026-02-28",
        adjustment_count: 3,
        adjustment_limit: 20,
        adjustment_offset: 0,
        event_total: 0,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          { ...rowBase, adjustment_id: "pca-st-approved", approval_status: "approved" as const },
          { ...rowBase, adjustment_id: "pca-st-pending", approval_status: "pending" as const },
          { ...rowBase, adjustment_id: "pca-st-rejected", approval_status: "rejected" as const },
        ],
        events: [],
      }),
    });

    const lead = await screen.findByTestId("product-category-adjustment-lead");
    expect(lead).toHaveTextContent("仅当审批通过可撤销");
    expect(lead).toHaveTextContent("仅当已拒绝可恢复");
    expect(lead).toHaveTextContent("刷新工作流");

    await screen.findByTestId("product-category-revoke-pca-st-approved");
    expect(screen.getByTestId("product-category-revoke-pca-st-approved")).not.toBeDisabled();
    expect(screen.getByTestId("product-category-restore-pca-st-approved")).toBeDisabled();
    expect(screen.getByTestId("product-category-revoke-pca-st-pending")).toBeDisabled();
    expect(screen.getByTestId("product-category-restore-pca-st-pending")).toBeDisabled();
    expect(screen.getByTestId("product-category-revoke-pca-st-rejected")).toBeDisabled();
    expect(screen.getByTestId("product-category-restore-pca-st-rejected")).not.toBeDisabled();

    expect(screen.getByTestId("product-category-edit-pca-st-approved")).not.toBeDisabled();
    expect(screen.getByTestId("product-category-edit-pca-st-pending")).not.toBeDisabled();
    expect(screen.getByTestId("product-category-edit-pca-st-rejected")).not.toBeDisabled();
  });
});
