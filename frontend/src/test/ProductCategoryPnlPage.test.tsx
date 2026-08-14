import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, vi } from "vitest";

import { ActionRequestError, createApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryInterestSpreadPayload,
} from "../api/contracts";
import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  buildProductCategoryDataHealth,
  formatProductCategoryChartNumberTwoDecimals,
} from "../features/product-category-pnl/pages/productCategoryPnlPageModel";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";
import { nocturneTokens } from "../theme/designSystem";
import { EM_DASH } from "../utils/format";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: ({
    option,
    onEvents,
  }: {
    option?: unknown;
    onEvents?: {
      click?: (params: { dataIndex: number; seriesIndex?: number }) => void;
    };
  }) => {
    const series =
      (option as { series?: Array<{ silent?: boolean }> } | null | undefined)
        ?.series ?? [];

    return (
      <div data-testid="product-category-echarts-stub">
        <span data-testid="product-category-echarts-option">
          {JSON.stringify(option ?? null)}
        </span>
        {onEvents?.click
          ? series.flatMap((item, seriesIndex) =>
              Array.from({ length: 12 }, (_, dataIndex) => (
                <button
                  key={`${seriesIndex}-${dataIndex}`}
                  data-testid={`product-category-echarts-click-series-${seriesIndex}-index-${dataIndex}`}
                  type="button"
                  disabled={item.silent === true}
                  onClick={() => {
                    if (!item.silent) {
                      onEvents.click?.({ dataIndex, seriesIndex });
                    }
                  }}
                >
                  click series {seriesIndex} index {dataIndex}
                </button>
              )),
            )
          : null}
      </div>
    );
  },
}));

// 该路由的模块链（页面组件 + 图表/归因/情景面板 + 页面模型）实测预加载约 17–24s，
// 贴着 20s 上限，在有负载的机器上会稳定超时假失败。与 dashboard-home 同样按重路由放宽。
beforeAll(async () => {
  await preloadWorkbenchRouteModules("product-category-pnl");
}, 60_000);

const TREND_WORKSPACE_STORAGE_KEY =
  "moss.product-category-pnl.trend-workspace-open";

// 趋势折叠区的展开状态会持久化，用例之间必须复位，否则先跑的用例会决定后跑用例的初始状态。
beforeEach(() => {
  window.localStorage.removeItem(TREND_WORKSPACE_STORAGE_KEY);
});

/** 显式选择折叠，用于继续覆盖"消费方关闭时不加载历史"的懒加载契约。 */
function preferCollapsedTrendWorkspace() {
  window.localStorage.setItem(TREND_WORKSPACE_STORAGE_KEY, "0");
}

function renderWorkbenchAppWithClient(
  client: ReturnType<typeof createApiClient>,
) {
  return renderWorkbenchApp(["/product-category-pnl"], { client });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

function apiLedgerRow(
  surfaceTestId:
    | "product-category-api-read-surfaces"
    | "product-category-api-write-surfaces",
  path: string,
) {
  const pathCell = within(screen.getByTestId(surfaceTestId)).getByText(path, {
    exact: true,
  });
  const row = pathCell.closest<HTMLElement>(
    ".product-category-api-ledger__row",
  );
  expect(row).not.toBeNull();
  return row!;
}

function yuan(yi: number): string {
  return String(yi * 100_000_000);
}

function fixtureCashAmount(
  scaleYi: number,
  ratePct: number,
  days: number,
): string {
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

function withEmptyInterestEarningSpread<T extends { result: object }>(
  envelope: T,
): T {
  const result = { ...envelope.result } as Record<string, unknown>;
  result.interest_earning_spread = {
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
    within(panel).getByTestId("product-category-echarts-option").textContent ??
      "null",
  ) as {
    backgroundColor?: string;
    grid?:
      | { top?: number; bottom?: number; containLabel?: boolean }
      | Array<{
          top?: number;
          bottom?: number;
          height?: number;
          containLabel?: boolean;
        }>;
    legend?: { data?: string[]; top?: number; right?: number; bottom?: number };
    tooltip?: { backgroundColor?: string; borderColor?: string };
    xAxis?: { data?: string[] } | Array<{ data?: string[] }>;
    yAxis?:
      | { min?: number; max?: number; name?: string; scale?: boolean }
      | Array<{ min?: number; max?: number; name?: string; scale?: boolean }>;
    series?: Array<{
      name?: string;
      type?: string;
      data?: unknown[];
      xAxisIndex?: number;
      yAxisIndex?: number;
      silent?: boolean;
      barMinHeight?: number;
      barGap?: string;
      barMaxWidth?: number;
      itemStyle?: {
        color?: string;
        borderColor?: string;
        borderWidth?: number;
        borderRadius?: number[];
        opacity?: number;
      };
      symbolSize?: number;
      lineStyle?: { width?: number; type?: string };
      label?: { show?: boolean };
      endLabel?: { show?: boolean };
      markLine?: {
        data?: Array<{ xAxis?: string; yAxis?: number }>;
      };
      markArea?: {
        data?: Array<
          Array<{
            xAxis?: string;
          }>
        >;
      };
    }>;
  };
}

async function waitForTrendDiagnosticsAutoLoad() {
  const user = userEvent.setup();
  const diagnosticsWorkspace = await screen.findByTestId(
    "product-category-diagnostics-workspace",
  );
  if (!diagnosticsWorkspace.hasAttribute("open")) {
    const diagnosticsSummary = within(diagnosticsWorkspace)
      .getByText("诊断与负债趋势候选分析", { exact: true })
      .closest("summary");
    expect(diagnosticsSummary).not.toBeNull();
    await user.click(diagnosticsSummary!);
  }
  await screen.findByTestId("product-category-diagnostics-surface");
  const trendWorkspace = await screen.findByTestId(
    "product-category-trend-workspace",
  );
  if (!trendWorkspace.hasAttribute("open")) {
    const trendSummary = within(trendWorkspace)
      .getByText("趋势与利差候选图表", { exact: true })
      .closest("summary");
    expect(trendSummary).not.toBeNull();
    await user.click(trendSummary!);
  }
  await screen.findByTestId("product-category-derived-chart-grid");
  await screen.findByTestId("product-category-trend-comparison-charts");
  await waitFor(() => {
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).not.toHaveTextContent("选择报表日期后");
  });
}

async function openProductCategoryTrendWorkspace() {
  const user = userEvent.setup();
  const trendWorkspace = await screen.findByTestId(
    "product-category-trend-workspace",
  );
  if (!trendWorkspace.hasAttribute("open")) {
    const trendSummary = within(trendWorkspace)
      .getByText("趋势与利差候选图表", { exact: true })
      .closest("summary");
    expect(trendSummary).not.toBeNull();
    await user.click(trendSummary!);
  }
  await screen.findByTestId("product-category-derived-chart-grid");
}

function buildMockAttributionEnvelope(
  reportDate: string,
  compare: "mom" | "yoy" = "mom",
  options: { closureErrorYi?: number } = {},
): ApiEnvelope<ProductCategoryAttributionPayload> {
  const priorReportDate = compare === "yoy" ? "2025-02-28" : "2026-01-31";
  const closureErrorYi = options.closureErrorYi ?? 0;
  const effect = {
    day_effect: yuan(-0.04),
    scale_effect: yuan(0.3),
    rate_effect: yuan(0.18),
    ftp_effect: yuan(0.02),
    direct_effect: yuan(0),
    unexplained_effect: yuan(0),
    explained_effect: yuan(0.46),
    delta_business_net_income: yuan(0.46),
    closure_error: yuan(closureErrorYi),
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
  const total: ProductCategoryAttributionRow = {
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
      liability_total: {
        ...total,
        category_id: "liability_total",
        category_name: "负债端合计",
        side: "liability",
      },
      grand_total: {
        ...total,
        category_id: "grand_total",
        category_name: "grand_total",
        side: "all",
      },
    },
  });
}

function buildTieOutAttributionEnvelope(
  reportDate: string,
  compare: "mom" | "yoy" = "mom",
) {
  const envelope = buildMockAttributionEnvelope(reportDate, compare);
  const totals = envelope.result.totals;
  if (!totals) {
    return envelope;
  }
  const withTiedCurrent = (
    row: ProductCategoryAttributionRow,
  ): ProductCategoryAttributionRow => ({
    ...row,
    current: row.current
      ? { ...row.current, business_net_income: yuan(0.72) }
      : row.current,
  });

  return {
    ...envelope,
    result: {
      ...envelope.result,
      rows: envelope.result.rows.map(withTiedCurrent),
      totals: {
        asset_total: withTiedCurrent(totals.asset_total),
        liability_total: withTiedCurrent(totals.liability_total),
        grand_total: withTiedCurrent(totals.grand_total),
      },
    },
  };
}

function buildDrilldownAttributionEnvelope(
  reportDate: string,
  compare: "mom" | "yoy" = "mom",
) {
  const envelope = buildTieOutAttributionEnvelope(reportDate, compare);
  const primary = envelope.result.rows[0];
  if (!primary) {
    return envelope;
  }
  const secondary: ProductCategoryAttributionRow = {
    ...primary,
    category_id: "repo_assets",
    category_name: "买入返售",
    current: primary.current
      ? {
          ...primary.current,
          scale: yuan(80),
          yield_pct: "1.70",
          cash: yuan(0.22),
          ftp: yuan(0.08),
          business_net_income: yuan(0.1),
        }
      : primary.current,
    prior: primary.prior
      ? {
          ...primary.prior,
          scale: yuan(90),
          yield_pct: "1.60",
          cash: yuan(0.26),
          ftp: yuan(0.1),
          business_net_income: yuan(0.2),
        }
      : primary.prior,
    effects: {
      ...primary.effects,
      day_effect: yuan(-0.01),
      scale_effect: yuan(-0.04),
      rate_effect: yuan(-0.03),
      ftp_effect: yuan(-0.01),
      direct_effect: yuan(-0.01),
      unexplained_effect: yuan(0),
      explained_effect: yuan(-0.1),
      delta_business_net_income: yuan(-0.1),
      closure_error: yuan(0),
    },
  };
  return {
    ...envelope,
    result: {
      ...envelope.result,
      rows: [primary, secondary],
    },
  };
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
      if (options.view === "ytd") {
        return {
          ...env,
          result: {
            ...env.result,
            liability_total: {
              ...env.result.liability_total,
              cnx_scale: "-200000000000.00",
              weighted_yield: "1.80",
            },
          },
        };
      }
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

const H1_MANAGEMENT_REPORT_DATES = [
  "2026-06-30",
  "2026-05-31",
  "2026-04-30",
  "2026-03-31",
  "2026-02-28",
  "2026-01-31",
];

function buildManagementMonitorAttributionEnvelope(
  reportDate: string,
  compare: "mom" | "yoy" = "mom",
) {
  const envelope = buildMockAttributionEnvelope(reportDate, compare);
  const sourceRow = envelope.result.rows[0]!;
  return {
    ...envelope,
    result: {
      ...envelope.result,
      rows: [
        ...envelope.result.rows,
        {
          ...sourceRow,
          category_id: "bond_tpl",
          category_name: "TPL",
        },
      ],
    },
  };
}

describe("ProductCategoryPnlPage", () => {
  it("renders the H1 management monitor as a compact candidate analysis section", async () => {
    const monthEndDates = [
      "2026-06-30",
      "2026-05-31",
      "2026-04-30",
      "2026-03-31",
      "2026-02-28",
      "2026-01-31",
    ];
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: monthEndDates,
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) =>
        buildMockProductCategoryPnlEnvelope(options),
      ),
      getProductCategoryAttribution: vi.fn(
        async ({ reportDate, compare = "mom" }) => {
          const envelope = buildMockAttributionEnvelope(reportDate, compare);
          const sourceRow = envelope.result.rows[0]!;
          return {
            ...envelope,
            result: {
              ...envelope.result,
              rows: [
                ...envelope.result.rows,
                {
                  ...sourceRow,
                  category_id: "bond_tpl",
                  category_name: "TPL",
                },
              ],
            },
          };
        },
      ),
    });

    await openProductCategoryTrendWorkspace();
    const monitor = await screen.findByTestId(
      "product-category-management-monitor",
    );
    await waitFor(() => {
      expect(within(monitor).getByText("TPL 恢复阈值")).toBeInTheDocument();
    });
    expect(monitor).toHaveTextContent("候选指标 · 非正式结论");
    expect(monitor).toHaveTextContent("6/6 月正式数据");
    expect(monitor).toHaveTextContent("负债改善质量");
    expect(monitor).toHaveTextContent("衍生品稳定性代理");
    expect(monitor).toHaveTextContent("经营节奏");
    expect(
      within(monitor).getByRole("heading", { name: "风险与节奏信号" }),
    ).toBeInTheDocument();
    expect(
      within(monitor).getByText("达到 5 月净营收水平"),
    ).toBeInTheDocument();
    expect(
      within(monitor).getByText("达到 H1 月均净营收水平"),
    ).toBeInTheDocument();
    expect(
      within(monitor).getByText("达到 Q1 月均净营收水平"),
    ).toBeInTheDocument();
    expect(
      within(monitor).getByText("方法与证据边界").closest("details"),
    ).not.toHaveAttribute("open");
  });

  it("blocks the formal H1 monitor when the current scenario fails but scenario history succeeds", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (options.reportDate === "2026-06-30" && options.scenarioRatePct) {
          throw new Error("current-scenario-failed");
        }
        return buildMockProductCategoryPnlEnvelope(options);
      },
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: H1_MANAGEMENT_REPORT_DATES,
        }),
      ),
      getProductCategoryPnl: pnlSpy,
      getProductCategoryAttribution: vi.fn(
        async ({ reportDate, compare = "mom" }) =>
          buildManagementMonitorAttributionEnvelope(reportDate, compare),
      ),
    });

    await openProductCategoryTrendWorkspace();
    const monitor = await screen.findByTestId(
      "product-category-management-monitor",
    );
    await waitFor(() => expect(monitor).toHaveTextContent("6/6 月正式数据"));
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );

    await waitFor(() => expect(monitor).toHaveTextContent("正式基线停算"));
    expect(monitor).not.toHaveTextContent("6/6 月正式数据");
    expect(
      pnlSpy.mock.calls.some(
        ([options]) =>
          options.reportDate === "2026-05-31" &&
          Boolean(options.scenarioRatePct),
      ),
    ).toBe(true);
  });

  it("blocks the formal H1 monitor when an applied scenario rate equals the baseline rate", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: H1_MANAGEMENT_REPORT_DATES,
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) =>
        buildMockProductCategoryPnlEnvelope(options),
      ),
      getProductCategoryAttribution: vi.fn(
        async ({ reportDate, compare = "mom" }) =>
          buildManagementMonitorAttributionEnvelope(reportDate, compare),
      ),
    });

    await openProductCategoryTrendWorkspace();
    const monitor = await screen.findByTestId(
      "product-category-management-monitor",
    );
    await waitFor(() => expect(monitor).toHaveTextContent("6/6 月正式数据"));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "FTP 场景" }),
      "1.75",
    );
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );

    await waitFor(() => expect(monitor).toHaveTextContent("正式基线停算"));
    expect(monitor).not.toHaveTextContent("6/6 月正式数据");
  });

  it("shows an explicit retryable error when an H1 history request fails", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let denyMayHistory = true;
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (
          denyMayHistory &&
          options.reportDate === "2026-05-31" &&
          !options.scenarioRatePct
        ) {
          throw new Error("history-month-failed");
        }
        return buildMockProductCategoryPnlEnvelope(options);
      },
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: H1_MANAGEMENT_REPORT_DATES,
        }),
      ),
      getProductCategoryPnl: pnlSpy,
      getProductCategoryAttribution: vi.fn(
        async ({ reportDate, compare = "mom" }) =>
          buildManagementMonitorAttributionEnvelope(reportDate, compare),
      ),
    });

    await openProductCategoryTrendWorkspace();
    const monitor = await screen.findByTestId(
      "product-category-management-monitor",
    );
    const retry = await within(monitor).findByRole("button", {
      name: "重试经营监控",
    });
    expect(monitor).toHaveTextContent("经营修复监控加载失败");
    expect(monitor).not.toHaveTextContent("当前缺少 5 月");

    denyMayHistory = false;
    await user.click(retry);
    await waitFor(() => expect(monitor).toHaveTextContent("6/6 月正式数据"));
    expect(
      within(monitor).queryByRole("button", { name: "重试经营监控" }),
    ).not.toBeInTheDocument();
  });

  it("formats chart display numbers with two decimals", () => {
    expect(formatProductCategoryChartNumberTwoDecimals(0.7)).toBe("0.70");
    expect(formatProductCategoryChartNumberTwoDecimals("1728.585")).toBe(
      "1728.59",
    );
    expect(formatProductCategoryChartNumberTwoDecimals(null)).toBe(EM_DASH);
    expect(formatProductCategoryChartNumberTwoDecimals(undefined)).toBe(EM_DASH);
  });

  it("models the report-date and baseline data-health states without silent fallback", () => {
    const envelope = buildMockProductCategoryPnlEnvelope({
      reportDate: "2026-02-28",
      view: "monthly",
    });
    const baseInput = {
      datesLoading: false,
      datesError: false,
      reportDates: ["2026-02-28"],
      selectedDate: "2026-02-28",
      baselineLoading: false,
      baselineError: false,
      baseline: envelope.result,
      meta: envelope.result_meta,
    };

    expect(
      buildProductCategoryDataHealth({ ...baseInput, datesLoading: true }),
    ).toMatchObject({
      state: "loading",
      judgementState: "pending",
      judgementLabel: "等待数据完成",
      retryTarget: null,
    });
    expect(
      buildProductCategoryDataHealth({ ...baseInput, datesError: true }),
    ).toMatchObject({
      state: "error",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
      retryTarget: "dates",
    });
    expect(
      buildProductCategoryDataHealth({ ...baseInput, reportDates: [] }),
    ).toMatchObject({
      state: "empty",
      judgementState: "blocked",
      retryTarget: null,
    });
    expect(
      buildProductCategoryDataHealth({ ...baseInput, baselineError: true }),
    ).toMatchObject({
      state: "error",
      judgementState: "blocked",
      retryTarget: "baseline",
      facts: [{ label: "报告日期", value: "2026-02-28" }],
    });
    expect(
      buildProductCategoryDataHealth({
        ...baseInput,
        baseline: { ...envelope.result, rows: [] },
      }),
    ).toMatchObject({
      state: "empty",
      judgementState: "blocked",
      retryTarget: null,
    });
    expect(
      buildProductCategoryDataHealth({
        ...baseInput,
        meta: {
          ...envelope.result_meta,
          quality_flag: "warning" as const,
          vendor_status: "vendor_stale" as const,
          fallback_mode: "latest_snapshot" as const,
        },
      }),
    ).toMatchObject({
      state: "degraded",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
      retryTarget: null,
    });
  });

  it("orders ready health evidence as report date, source, rows, and generation time", () => {
    const envelope = buildMockProductCategoryPnlEnvelope({
      reportDate: "2026-02-28",
      view: "monthly",
    });

    const health = buildProductCategoryDataHealth({
      datesLoading: false,
      datesError: false,
      reportDates: ["2026-02-28"],
      selectedDate: "2026-02-28",
      baselineLoading: false,
      baselineError: false,
      baseline: envelope.result,
      meta: envelope.result_meta,
    });

    expect(health.state).toBe("ready");
    expect(health).toMatchObject({
      judgementState: "allowed",
      judgementLabel: "可用于经营判断",
    });
    expect(health.facts.map((fact) => fact.label)).toEqual([
      "报告日期",
      "来源版本",
      "明细",
      "生成时间",
    ]);
  });

  it("offers anchored navigation for the six business views", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const navigation = await screen.findByRole("navigation", {
      name: "产品分类损益页面分区",
    });
    expect(within(navigation).getByText("分析路径")).toBeInTheDocument();
    const expectedLinks = [
      ["经营总览", "#product-category-overview"],
      ["差异归因", "#product-category-attribution"],
      ["产品结构", "#product-category-products"],
      ["负债结构", "#product-category-liabilities"],
      ["完整报表", "#product-category-report"],
      ["治理审计", "#product-category-governance"],
    ] as const;

    expectedLinks.forEach(([name, href]) => {
      expect(within(navigation).getByRole("link", { name })).toHaveAttribute(
        "href",
        href,
      );
      expect(document.querySelector(href)).toBeInTheDocument();
    });
  });

  it("leads the second screen with a compact bridge and three primary drivers", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const attribution = await screen.findByTestId(
      "product-category-attribution",
    );
    const summary = await within(attribution).findByTestId(
      "product-category-attribution-summary",
    );
    expect(
      within(summary).getAllByTestId(
        "product-category-attribution-summary-metric",
      ),
    ).toHaveLength(4);
    expect(summary).toHaveTextContent("变动合计");
    expect(summary).toHaveTextContent("已解释");
    expect(summary).toHaveTextContent("未解释");
    expect(summary).toHaveTextContent("闭合误差");
    expect(summary).not.toHaveTextContent("本期净营收");
    expect(summary).not.toHaveTextContent("对比期净营收");

    const bridge = await screen.findByTestId(
      "product-category-attribution-bridge",
    );
    const rootCause = within(bridge).getByTestId("product-category-root-cause");
    const fullPath = within(bridge).getByTestId(
      "product-category-attribution-full-path",
    );
    expect(
      within(rootCause).getAllByTestId("product-category-root-cause-driver"),
    ).toHaveLength(3);
    expect(
      within(rootCause).getByRole("button", { name: "查看正式明细" }),
    ).toBeEnabled();
    expect(fullPath).not.toHaveAttribute("open");
    expect(fullPath).toHaveTextContent("候选归因路径");
    expect(
      rootCause.compareDocumentPosition(fullPath) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("places five headline metrics and top drivers before expandable governance detail", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const band = await screen.findByTestId(
      "product-category-formal-readiness-band",
    );
    const totals = within(band).getByTestId(
      "product-category-formal-headline-totals",
    );
    const drivers = within(band).getByTestId(
      "product-category-formal-driver-readout",
    );
    const governance = await screen.findByTestId(
      "product-category-governance-evidence",
    );

    expect(
      within(totals).getAllByTestId("product-category-core-metric"),
    ).toHaveLength(5);
    expect(
      totals.compareDocumentPosition(drivers) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      drivers.compareDocumentPosition(governance) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      within(band).queryByTestId("product-category-first-screen-category-rows"),
    ).toBeNull();
    expect(governance).not.toHaveAttribute("open");
    expect(governance).toHaveTextContent("治理与证据");
    expect(governance).toHaveTextContent("3 项认证待完成");
  });

  it("groups the desktop decision flow into one editorial operating surface", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const page = await screen.findByTestId("product-category-page");
    const masthead = within(page).getByTestId(
      "product-category-report-masthead",
    );
    const decisionCanvas = await within(page).findByTestId(
      "product-category-decision-canvas",
    );
    const commandRail = within(page).getByTestId(
      "product-category-operating-command-rail",
    );

    expect(masthead).toContainElement(
      within(page).getByTestId(
        "product-category-branch-monthly-operating-analysis",
      ),
    );
    expect(masthead).toContainElement(
      within(page).getByTestId("product-category-contract-hero"),
    );
    expect(decisionCanvas).toContainElement(
      within(page).getByTestId("product-category-formal-headline-totals"),
    );
    expect(decisionCanvas).toContainElement(
      within(page).getByTestId("product-category-formal-driver-readout"),
    );
    expect(commandRail).toContainElement(
      within(page).getByTestId("product-category-unified-controls"),
    );
    expect(commandRail).toContainElement(
      within(page).getByTestId("product-category-data-status-strip"),
    );
  });

  it("surfaces the monthly delta and closure gap from the attribution API in the headline band", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const band = await screen.findByTestId(
      "product-category-formal-readiness-band",
    );

    await waitFor(() => {
      expect(band).toHaveTextContent("环比变动");
      expect(band).toHaveTextContent("闭合误差");
      expect(band).toHaveTextContent("对比期");
    });
  });

  it("presents attribution drivers as first-screen visual evidence", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const driverReadout = await screen.findByTestId(
      "product-category-formal-driver-readout",
    );

    await waitFor(() => {
      expect(
        within(driverReadout).getAllByTestId("product-category-driver-item"),
      ).toHaveLength(3);
    });
    const driverItems = within(driverReadout).getAllByTestId(
      "product-category-driver-item",
    );
    expect(driverReadout).toHaveTextContent("关键驱动与风险");
    expect(driverItems.map((item) => item.textContent)).toEqual([
      expect.stringContaining("规模因素"),
      expect.stringContaining("利率因素"),
      expect.stringContaining("天数因素"),
    ]);
    expect(within(driverReadout).queryByRole("progressbar")).toBeNull();
  });

  it("keeps full attribution and candidate analysis in closed secondary workspaces", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const secondaryWorkspaces = [
      "product-category-attribution-details",
      "product-category-financial-workspace",
      "product-category-operating-workspace",
      "product-category-backtest-workspace",
      "product-category-diagnostics-workspace",
    ].map((testId) => screen.getByTestId(testId));

    secondaryWorkspaces.forEach((workspace) => {
      expect(workspace.tagName).toBe("DETAILS");
      expect(workspace).not.toHaveAttribute("open");
    });
  });

  it("mounts all eight reference blocks and five comparison charts from one trend disclosure", async () => {
    const user = userEvent.setup();
    preferCollapsedTrendWorkspace();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const diagnosticsWorkspace = await screen.findByTestId(
      "product-category-diagnostics-workspace",
    );
    const diagnosticsSummary = within(diagnosticsWorkspace)
      .getByText("诊断与负债趋势候选分析", { exact: true })
      .closest("summary");
    expect(diagnosticsSummary).not.toBeNull();
    expect(
      screen.queryByTestId("product-category-diagnostics-surface"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-derived-chart-grid"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryAllByTestId("product-category-echarts-stub"),
    ).toHaveLength(0);

    await user.click(diagnosticsSummary!);

    await screen.findByTestId("product-category-diagnostics-surface");
    expect(
      screen.queryByTestId("product-category-derived-chart-tpl-scale-yield"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-scope-chart-workspace"),
    ).not.toBeInTheDocument();

    const trendWorkspace = screen.getByTestId(
      "product-category-trend-workspace",
    );
    expect(diagnosticsWorkspace).not.toContainElement(trendWorkspace);
    expect(trendWorkspace).not.toHaveAttribute("open");
    const trendSummary = within(trendWorkspace)
      .getByText("趋势与利差候选图表", { exact: true })
      .closest("summary");
    expect(trendSummary).not.toBeNull();

    await user.click(trendSummary!);

    const coreCharts = await screen.findByTestId(
      "product-category-trend-core-charts",
    );
    const coreGrid = within(coreCharts).getByTestId(
      "product-category-derived-chart-grid",
    );
    [
      "product-category-derived-chart-tpl-scale-yield",
      "product-category-derived-chart-currency-net-income",
      "product-category-derived-chart-interest-earning-income-scale",
      "product-category-derived-chart-interest-spread",
      "product-category-derived-chart-interest-earning-spread",
      "product-category-derived-chart-interest-earning-asset-liability-scale",
    ].forEach((testId) => {
      expect(within(coreGrid).getByTestId(testId)).toBeInTheDocument();
    });

    const analysis = screen.getByTestId("product-category-trend-analysis");
    [
      "product-category-trend-spread-attribution",
      "product-category-trend-liability-card",
    ].forEach((testId) => {
      expect(within(analysis).getByTestId(testId)).toBeInTheDocument();
    });

    const supportingWorkspace = screen.getByTestId(
      "product-category-trend-supporting",
    );
    expect(supportingWorkspace.tagName).toBe("SECTION");
    expect(supportingWorkspace).toHaveTextContent("同比趋势与后端字段归因");
    expect(supportingWorkspace).toHaveTextContent("日期覆盖");
    expect(supportingWorkspace).toHaveTextContent("对比期载入");
    const comparisonCharts = within(supportingWorkspace).getByTestId(
      "product-category-trend-comparison-charts",
    );
    [
      "product-category-derived-chart-interest-earning-spread-yoy",
      "product-category-derived-chart-interest-earning-spread-yoy-cny",
      "product-category-derived-chart-interest-spread-yoy",
      "product-category-derived-chart-interest-spread-yoy-cny",
      "product-category-derived-chart-intermediate-business-income-yoy",
    ].forEach((testId) => {
      expect(within(comparisonCharts).getByTestId(testId)).toBeInTheDocument();
    });
    expect(
      within(supportingWorkspace).getByTestId(
        "product-category-interest-spread-attribution",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        readChartOption(
          "product-category-derived-chart-interest-earning-spread",
        ).series?.map((series) => series.data),
      ).toEqual([
        [2.4, 2.4],
        [1.63, 1.63],
        [0.77, 0.77],
      ]);
    });
    const earningSpreadOption = readChartOption(
      "product-category-derived-chart-interest-earning-spread",
    );
    expect(earningSpreadOption.series?.map((series) => series.name)).toEqual([
      "生息资产收益率（%）",
      "负债端成本率（%）",
      "生息资产负债利差（%）",
    ]);
    expect(earningSpreadOption.series?.map((series) => series.type)).toEqual([
      "line",
      "line",
      "line",
    ]);
    const spreadAttribution = screen.getByTestId(
      "product-category-trend-spread-attribution",
    );
    expect(
      spreadAttribution.querySelectorAll(
        ".product-category-diagnostics__spread-card",
      ),
    ).toHaveLength(3);
    expect(spreadAttribution).toHaveTextContent("2026年02月");
    expect(spreadAttribution).toHaveTextContent("2026年01月");
    expect(spreadAttribution).toHaveTextContent("归因结论");
    expect(spreadAttribution).toHaveTextContent("资产 2.68% / 负债 1.63%");
    expect(spreadAttribution).toHaveTextContent(
      "资产与负债收益率变动基本对冲，利差持平",
    );

    const liabilityCard = screen.getByTestId(
      "product-category-trend-liability-card",
    );
    const liabilityOption = readChartOption(
      "product-category-trend-liability-card",
    );
    expect(liabilityCard).toHaveTextContent("负债端趋势分析");
    expect(liabilityOption.legend?.data).toEqual([
      "负债端日均额（亿元）",
      "负债端利率（%）",
    ]);
    expect(liabilityOption.series?.map((series) => series.name)).toEqual([
      "负债端日均额（亿元）",
      "负债端利率（%）",
    ]);
    expect(liabilityOption.series?.map((series) => series.type)).toEqual([
      "bar",
      "line",
    ]);
    expect(liabilityOption.xAxis).toMatchObject({
      data: ["2026年01月", "2026年02月"],
    });
    expect(liabilityCard).toHaveTextContent("1728.58");
    expect(liabilityCard).toHaveTextContent("1.63");
    expect(liabilityCard).toHaveTextContent("0 bp");

    await user.click(trendSummary!);
    await waitFor(() => {
      expect(
        screen.queryByTestId("product-category-derived-chart-grid"),
      ).not.toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("product-category-trend-supporting"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-derived-chart-tpl-scale-yield"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-liability-side-trend"),
    ).toBeInTheDocument();

    await user.click(diagnosticsSummary!);
    await waitFor(() =>
      expect(
        screen.queryAllByTestId("product-category-echarts-stub"),
      ).toHaveLength(0),
    );
  });

  it("exposes all 11 backend connections in the API contract ledger", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const ledger = await screen.findByTestId(
      "product-category-api-contract-ledger",
    );
    expect(ledger).toHaveAccessibleName("产品分类损益后端端点衔接状态");
    expect(ledger).toHaveTextContent("11 个前端衔接动作");
    expect(
      ledger.querySelectorAll(".product-category-api-ledger__row"),
    ).toHaveLength(11);

    [
      "/dates",
      "/?report_date&view",
      "/attribution?compare=mom|yoy",
      "/manual-adjustments/export",
      "/refresh-status?run_id",
      "/refresh",
      "/{id}/edit",
      "/{id}/revoke",
      "/{id}/restore",
    ].forEach((path) => {
      expect(
        within(ledger).getByText(path, { exact: true }),
      ).toBeInTheDocument();
    });
    expect(
      within(ledger).getAllByText("/manual-adjustments", { exact: true }),
    ).toHaveLength(2);
    expect(
      screen.getByTestId("product-category-api-read-surfaces"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-api-write-surfaces"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-api-contract-runtime"),
    ).toHaveTextContent("读接口已联调 6/6 · 写接口已联调 5/5");
    expect(ledger).toHaveTextContent("不是服务健康检查");
    await screen.findByTestId("product-category-table");
    expect(
      screen.getByTestId("product-category-export-adjustments"),
    ).toBeEnabled();
    expect(
      within(ledger).getByRole("link", { name: "打开审计账本" }),
    ).toHaveAttribute("href", "/product-category-pnl/audit");
  });

  it("does not report disabled date-dependent reads as live", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const datesRequest =
      deferred<
        Awaited<ReturnType<typeof baseClient.getProductCategoryDates>>
      >();

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: () => datesRequest.promise,
    });

    await screen.findByTestId("product-category-api-contract-ledger");
    expect(
      apiLedgerRow("product-category-api-read-surfaces", "/dates"),
    ).toHaveTextContent("LOADING");
    [
      "/?report_date&view",
      "/attribution?compare=mom|yoy",
      "/manual-adjustments",
      "/manual-adjustments/export",
    ].forEach((path) => {
      const row = apiLedgerRow("product-category-api-read-surfaces", path);
      expect(row).toHaveTextContent("WAITING · REPORT DATE");
      expect(row).toHaveAttribute("data-endpoint-state", "contracted");
    });
    expect(
      screen.getByTestId("product-category-export-adjustments"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("product-category-api-contract-runtime"),
    ).not.toHaveTextContent("READ LIVE");
  });

  it("exports adjustment CSV from the main-page ledger and reports the call state", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportPayload = {
      filename: "product-category-main-ledger.csv",
      content: "adjustment_id,monthly_pnl\npca-ledger,1\n",
    };
    const exportRequest = deferred<typeof exportPayload>();
    const exportSpy = vi.fn(() => exportRequest.promise);
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    const createObjectUrl = vi.fn(() => "blob:product-category-main-ledger");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const createElementSpy = vi.spyOn(document, "createElement");
    createElementSpy.mockImplementation(((tagName: string) => {
      const element = document.createElementNS(
        "http://www.w3.org/1999/xhtml",
        tagName,
      );
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          value: clickSpy,
          configurable: true,
        });
      }
      return element as HTMLElement;
    }) as typeof document.createElement);
    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;

    try {
      renderWorkbenchAppWithClient({
        ...baseClient,
        exportProductCategoryManualAdjustmentsCsv: exportSpy,
      });

      await screen.findByTestId("product-category-table");
      await user.click(
        screen.getByTestId("product-category-export-adjustments"),
      );
      expect(
        apiLedgerRow(
          "product-category-api-read-surfaces",
          "/manual-adjustments/export",
        ),
      ).toHaveTextContent("EXPORTING");

      exportRequest.resolve(exportPayload);
      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith("2026-02-28");
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(
          apiLedgerRow(
            "product-category-api-read-surfaces",
            "/manual-adjustments/export",
          ),
        ).toHaveTextContent("CSV EXPORTED");
      });
      expect(
        screen.getByTestId("product-category-api-contract-ledger"),
      ).toHaveTextContent(exportPayload.filename);
      expect(createObjectUrl).toHaveBeenCalledTimes(1);
      expect(revokeObjectUrl).toHaveBeenCalledTimes(1);
    } finally {
      createElementSpy.mockRestore();
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it("keeps CSV export failure local to the endpoint ledger", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportSpy = vi.fn(async () => {
      throw new Error("main-ledger-export-failure");
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      exportProductCategoryManualAdjustmentsCsv: exportSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-export-adjustments"));

    expect(
      await screen.findByText("main-ledger-export-failure"),
    ).toHaveAttribute("role", "alert");
    const exportRow = apiLedgerRow(
      "product-category-api-read-surfaces",
      "/manual-adjustments/export",
    );
    expect(exportRow).toHaveTextContent("ERROR");
    expect(exportRow).toHaveAttribute("data-endpoint-state", "error");
    expect(screen.getByTestId("product-category-table")).toBeInTheDocument();
  });

  it("collapses technical signing fields behind a Chinese summary", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const governance = await screen.findByTestId(
      "product-category-governance-evidence",
    );
    const signingStatus = await screen.findByTestId(
      "product-category-owner-signable-status",
    );
    expect(governance.tagName).toBe("DETAILS");
    expect(governance).not.toHaveAttribute("open");
    expect(signingStatus.tagName).toBe("SECTION");
    expect(governance).toContainElement(signingStatus);
    expect(signingStatus).toHaveTextContent("签署状态");
    expect(signingStatus).toHaveTextContent("待认证");
    expect(signingStatus).toHaveTextContent("可签署：否");
  });

  it("keeps result metadata collapsed as an evidence layer", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const metadataWorkspace = await screen.findByTestId(
      "product-category-result-meta-workspace",
    );

    expect(metadataWorkspace.tagName).toBe("DETAILS");
    expect(metadataWorkspace).not.toHaveAttribute("open");
    expect(metadataWorkspace).toHaveTextContent("结果元信息与证据");
    expect(
      within(metadataWorkspace).getByTestId("product-category-result-meta"),
    ).toBeInTheDocument();
  });

  it("renders the page shell, summary, and table structure", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const table = await screen.findByTestId("product-category-table");
    expect(table).toHaveTextContent("人民币净收入");
    expect(table).toHaveTextContent("外币净收入");
    expect(table).toHaveTextContent("营业净收入");
    expect(table).not.toHaveTextContent("人民币减收入");
    expect(table).not.toHaveTextContent("外币减收入");
    expect(table).not.toHaveTextContent("营业减收入");
    expect(screen.getByTestId("product-category-page")).toHaveClass(
      "product-category-page-shell",
      "theme-dh-api",
    );
    expect(screen.getByTestId("product-category-contract-hero")).toHaveClass(
      "product-category-contract-hero",
    );
    expect(screen.getByTestId("product-category-page-title")).toHaveTextContent(
      "产品分类损益",
    );
    expect(
      screen.getByTestId("product-category-page-subtitle"),
    ).toHaveTextContent("报告月 2026年02月");
    expect(
      screen.getByTestId("product-category-report-date-slot"),
    ).toHaveTextContent("2026-02-28 · 正式口径 | 月度视图");
    expect(screen.getByTestId("product-category-role-badge")).toHaveTextContent(
      "本地离线契约回放",
    );
    expect(
      screen.queryByTestId("product-category-boundary-copy"),
    ).not.toBeInTheDocument();
    const ownerStatus = screen.getByTestId(
      "product-category-owner-signable-status",
    );
    const productCategoryBranch = screen.getByTestId(
      "product-category-branch-product-category-pnl",
    );
    expect(
      productCategoryBranch.compareDocumentPosition(ownerStatus) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(ownerStatus).toHaveTextContent("可签署：否");
    expect(ownerStatus).toHaveTextContent("已认证：否");
    expect(ownerStatus).toHaveTextContent("待业主审批");
    expect(ownerStatus).toHaveTextContent("黄金样本待审批");
    expect(ownerStatus).toHaveTextContent("人工抽核未完成：已核 10 个单元");
    expect(
      screen.getByTestId("product-category-formal-readiness-band"),
    ).toHaveTextContent("本期经营结果");
    expect(
      screen.getByTestId("product-category-formal-headline-copy"),
    ).toHaveTextContent("本期合计经营净收入");
    expect(
      screen.getAllByTestId("product-category-core-metric")[0],
    ).toHaveTextContent("FTP后经营净收入（亿元）");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("report_date=2026-02-28");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("view=monthly");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("quality=ok");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("fallback=none");
    const certificationBlockers = screen.getByTestId(
      "product-category-certification-blockers",
    );
    expect(certificationBlockers).toHaveTextContent("待业主审批");
    expect(certificationBlockers).toHaveTextContent("黄金样本待审批");
    expect(certificationBlockers).toHaveTextContent(
      "人工抽核未完成：已核 10 个单元",
    );
    expect(certificationBlockers).toHaveTextContent("签署前需重新运行核算");
    expect(certificationBlockers).toHaveTextContent("单位：亿元");
    expect(certificationBlockers).toHaveTextContent("日期基准：report_date");
    expect(certificationBlockers).toHaveTextContent("数据来源：正式只读模型");
    expect(
      screen.getByTestId("product-category-formal-headline-totals"),
    ).toHaveTextContent("MTR-PCP-001");
    expect(
      screen.getByTestId("product-category-formal-headline-totals"),
    ).toHaveTextContent("MTR-PCP-002");
    expect(
      screen.getByTestId("product-category-formal-headline-totals"),
    ).toHaveTextContent("MTR-PCP-003");
    expect(
      screen.queryByTestId("product-category-first-screen-category-rows"),
    ).not.toBeInTheDocument();
    expect(screen.getAllByTestId("product-category-core-metric")).toHaveLength(
      5,
    );
    expect(
      screen.getByTestId("product-category-adjustment-lead"),
    ).toHaveTextContent("手工调整与审计");
    expect(
      screen.getByTestId("product-category-unified-controls"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-formal-table-lead"),
    ).toHaveTextContent("正式产品类别损益表");
    await waitForTrendDiagnosticsAutoLoad();
    expect(
      screen.getByTestId("product-category-diagnostics-lead"),
    ).toHaveTextContent("受治理诊断面板");
    expect(
      screen.getByTestId("product-category-diagnostics-surface"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-diagnostics-matrix"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-diagnostics-watchlist"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-diagnostics-spread"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-operating-analysis"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-operating-profit-rank"),
    ).toHaveTextContent("1.45");
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-movement"),
      ).toHaveTextContent("0.02");
    });
    expect(
      screen.getByTestId("product-category-operating-quadrant"),
    ).toHaveTextContent("2.57");
    expect(
      screen.getByTestId("product-category-operating-action-queue"),
    ).toHaveTextContent("动作优先级队列");
    expect(
      screen.getByTestId("product-category-operating-action-queue"),
    ).toHaveTextContent("选择性扩张");
    expect(
      screen.getByTestId("product-category-operating-action-queue"),
    ).toHaveTextContent("重定价/提效");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("动作队列次月命中率");
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("动作类型表现");
    });
    expect(
      screen.getByTestId("product-category-financial-analysis"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("FTP 情景敏感度");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("加载矩阵");
    expect(
      screen.getByTestId("product-category-attribution-waterfall"),
    ).toHaveTextContent("经营差异瀑布");
    expect(
      screen.getByTestId("product-category-attribution-bridge"),
    ).toHaveTextContent("主导产品与前三驱动");
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent(
      "主导产品",
    );
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent(
      "FTP因素",
    );
    expect(screen.getByTestId("product-category-root-cause")).toHaveTextContent(
      "未解释",
    );
    expect(
      screen.getByTestId("product-category-decision-focus"),
    ).toHaveTextContent("本期决策焦点");
    expect(
      screen.getByTestId("product-category-liability-side-trend"),
    ).toHaveTextContent("负债端趋势分析");
    expect(
      screen.getByTestId("product-category-liability-side-trend"),
    ).toHaveTextContent("负债侧产品类别口径");
    expect(screen.queryByText("同业负债")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-diagnostics-summary"),
    ).toHaveTextContent("2.85");
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
      "1.75",
    );
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
      "FTP后经营净收入：",
    );
    expect(
      screen.getByTestId("product-category-footer-total"),
    ).toHaveTextContent("全部市场科目FTP后经营净收入：");
    const metaPanel = screen.getByTestId(
      "product-category-result-meta-baseline",
    );
    expect(metaPanel).toHaveTextContent("product_category_pnl.detail");
    expect(metaPanel).toHaveTextContent("mock_product_category_pnl.detail");
    expect(
      screen.getByTestId("product-category-governance-strip"),
    ).toBeInTheDocument();
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
      "product-category-formal-readiness-band",
      "product-category-formal-headline-totals",
      "product-category-formal-driver-readout",
      "product-category-unified-controls",
      "product-category-data-status-strip",
      "product-category-governance-evidence",
      "product-category-owner-signable-status",
      "product-category-section-nav",
      "product-category-next-analysis-preview",
      "product-category-attribution-workbench",
      "product-category-attribution",
      "product-category-attribution-bridge",
      "product-category-adjustment-workspace",
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

  it("continues from the next-analysis cue into a tied-out attribution bridge before adjustments", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryAttribution: vi.fn(async (options) =>
        buildTieOutAttributionEnvelope(options.reportDate, options.compare),
      ),
    });

    const preview = await screen.findByTestId(
      "product-category-next-analysis-preview",
    );
    const workbench = await screen.findByTestId(
      "product-category-attribution-workbench",
    );
    const attribution = await screen.findByTestId(
      "product-category-attribution",
    );
    const summary = within(attribution).getByTestId(
      "product-category-attribution-summary",
    );
    const bridge = await screen.findByTestId(
      "product-category-attribution-bridge",
    );
    const formalDetails = within(attribution).getByTestId(
      "product-category-attribution-details",
    );
    const adjustment = screen.getByTestId(
      "product-category-adjustment-workspace",
    );

    expect(
      preview.compareDocumentPosition(workbench) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      workbench.compareDocumentPosition(adjustment) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(workbench).toContainElement(attribution);
    expect(workbench).toContainElement(bridge);
    expect(attribution).toContainElement(bridge);
    expect(
      summary.compareDocumentPosition(bridge) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      bridge.compareDocumentPosition(formalDetails) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(formalDetails).not.toHaveAttribute("open");
    expect(
      within(bridge).getByTestId("product-category-attribution-full-path"),
    ).not.toHaveAttribute("open");
    expect(
      within(summary).queryByText(/候选指标|不可用于正式签署/),
    ).not.toBeInTheDocument();
    expect(bridge).toHaveTextContent("候选指标 · 非正式结论");
    expect(bridge).toHaveTextContent("经营差异瀑布");
    expect(bridge).toHaveTextContent("主导产品与前三驱动");

    await waitFor(() => {
      expect(
        screen.getAllByTestId("product-category-driver-item"),
      ).toHaveLength(3);
    });
    expect(
      screen.getByTestId(
        "product-category-attribution-bridge-driver-scale_effect",
      ),
    ).toHaveTextContent("+0.30");
    expect(
      screen.getByTestId(
        "product-category-attribution-bridge-driver-rate_effect",
      ),
    ).toHaveTextContent("+0.18");
    expect(
      screen.getByTestId(
        "product-category-attribution-bridge-driver-day_effect",
      ),
    ).toHaveTextContent("-0.04");
  });

  it("keeps the attribution readout on formal rows after an FTP scenario is applied", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryAttribution: vi.fn(
        async ({ reportDate, compare = "mom" }) => {
          const envelope = buildMockAttributionEnvelope(reportDate, compare);
          return {
            ...envelope,
            result: {
              ...envelope.result,
              rows: envelope.result.rows.map((row) => ({
                ...row,
                current: null,
              })),
            },
          };
        },
      ),
    });

    const rootCause = await screen.findByTestId("product-category-root-cause");
    expect(rootCause).toHaveTextContent("本期 0.10");

    await user.selectOptions(
      screen.getByRole("combobox", { name: "FTP 场景" }),
      "2.00",
    );
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );
    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "当前场景：2.00%",
      );
    });

    expect(rootCause).toHaveTextContent("本期 0.10");
    expect(rootCause).not.toHaveTextContent("本期 0.03");
    expect(
      screen.getByTestId("product-category-attribution-candidate-status"),
    ).toHaveTextContent("候选指标 · 非正式结论");

    await user.click(
      within(rootCause).getByRole("button", { name: "查看正式明细" }),
    );
    const selectionContext = await screen.findByTestId(
      "product-category-formal-selection-context",
    );
    expect(selectionContext).toHaveTextContent("FTP 2.00% 场景");
    expect(selectionContext).toHaveTextContent("正式基线归因定位");
  });

  it("surfaces ready baseline evidence in the first-screen data health strip", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const health = await screen.findByTestId("product-category-data-health");
    await waitFor(() => {
      expect(health).toHaveAttribute("data-health-state", "ready");
    });
    expect(health).toHaveTextContent("正式基线已就绪");
    expect(health).toHaveTextContent("报告日期 2026-02-28");
    expect(health).toHaveTextContent("生成时间 2026-04-09T10:30:00Z");
    expect(health).toHaveTextContent("来源版本 sv_mock_dashboard_v2");
    expect(health).toHaveTextContent("明细 18 行");
    const judgement = within(health).getByTestId(
      "product-category-formal-judgement-status",
    );
    expect(judgement).toHaveAttribute("data-judgement-state", "allowed");
    expect(judgement).toHaveTextContent("可用于经营判断");
  });

  it("separates signing blockers, source version, and audit evidence without repeating data health", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const governance = screen.getByTestId(
      "product-category-governance-evidence",
    );
    expect(governance).toHaveTextContent("3 项认证待完成");
    expect(governance).not.toHaveTextContent("可用于经营判断");

    const signing = within(governance).getByTestId(
      "product-category-governance-signing-blockers",
    );
    expect(
      within(signing).getByRole("heading", { level: 3, name: "签署阻断" }),
    ).toBeInTheDocument();
    expect(signing).toHaveTextContent("签署阻断");
    expect(signing).toHaveTextContent("待业主审批");

    const source = within(governance).getByTestId(
      "product-category-governance-source-version",
    );
    expect(
      within(source).getByRole("heading", { level: 3, name: "来源与版本" }),
    ).toBeInTheDocument();
    expect(source).toHaveTextContent("来源与版本");
    expect(source).toHaveTextContent("basis=formal");
    expect(source).toHaveTextContent("generated_at=2026-04-09T10:30:00Z");

    const audit = within(governance).getByTestId(
      "product-category-governance-audit-evidence",
    );
    expect(
      within(audit).getByRole("heading", { level: 3, name: "审计证据" }),
    ).toBeInTheDocument();
    expect(audit).toHaveTextContent("审计证据");
    expect(audit).toHaveTextContent("单位：亿元");
    expect(audit).toHaveTextContent("日期基准：report_date");
  });

  it("surfaces an explicit no-data state when the selected baseline has no detail rows", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: vi.fn(async (options) => {
        const envelope = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: [],
          },
        };
      }),
    });

    const health = await screen.findByTestId("product-category-data-health");
    await waitFor(() => {
      expect(health).toHaveAttribute("data-health-state", "empty");
    });
    expect(health).toHaveTextContent("所选月份暂无产品明细");
    expect(health).toHaveTextContent("报告日期 2026-02-28");
    expect(
      within(health).getByTestId("product-category-formal-judgement-status"),
    ).toHaveTextContent("正式判断阻断");
    expect(
      screen.queryByTestId("product-category-formal-readiness-band"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-summary"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-attribution"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-financial-workspace"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-operating-workspace"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-backtest-workspace"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-footer-total"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-diagnostics-workspace"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-table"),
    ).not.toBeInTheDocument();
  });

  it("surfaces a first-screen baseline failure and recovers through its retry action", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let denyBaseline = true;
    const getProductCategoryPnl = vi.fn(async (options) => {
      if (denyBaseline) {
        throw new Error("baseline-unavailable");
      }
      return buildMockProductCategoryPnlEnvelope(options);
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl,
    });

    const failedHealth = await screen.findByTestId(
      "product-category-data-health",
    );
    await waitFor(() => {
      expect(failedHealth).toHaveAttribute("data-health-state", "error");
    });
    expect(failedHealth).toHaveTextContent("正式基线加载失败");
    expect(failedHealth).toHaveAttribute("role", "alert");
    expect(
      within(failedHealth).getByTestId(
        "product-category-formal-judgement-status",
      ),
    ).toHaveTextContent("正式判断阻断");
    expect(
      screen.queryByTestId("product-category-table"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-attribution-bridge"),
    ).not.toBeInTheDocument();

    denyBaseline = false;
    await user.click(
      within(failedHealth).getByRole("button", { name: "重试正式基线" }),
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-data-health"),
      ).toHaveAttribute("data-health-state", "ready");
    });
    expect(
      await screen.findByTestId("product-category-table"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("product-category-attribution-bridge"),
    ).toBeInTheDocument();
  });

  it("hides the prior formal conclusion while a newly selected report month is loading", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pendingBaseline =
      deferred<Awaited<ReturnType<typeof baseClient.getProductCategoryPnl>>>();
    let holdNextBaseline = false;
    const getProductCategoryPnl = vi.fn((options) => {
      if (holdNextBaseline && !options.scenarioRatePct) {
        holdNextBaseline = false;
        return pendingBaseline.promise;
      }
      return baseClient.getProductCategoryPnl(options);
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2026-01-31"],
        }),
      ),
      getProductCategoryPnl,
    });

    await screen.findByTestId("product-category-table");
    holdNextBaseline = true;
    await user.selectOptions(
      screen.getByRole("combobox", { name: "选择报告月份" }),
      "2026-01-31",
    );

    const health = screen.getByTestId("product-category-data-health");
    await waitFor(() => {
      expect(health).toHaveAttribute("data-health-state", "loading");
    });
    expect(
      within(health).getByTestId("product-category-formal-judgement-status"),
    ).toHaveTextContent("等待数据完成");
    expect(
      screen.queryByTestId("product-category-formal-readiness-band"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-table"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-report-date-slot"),
    ).toHaveTextContent("2026-01-31 · 口径待确认");

    pendingBaseline.resolve(
      buildMockProductCategoryPnlEnvelope({
        reportDate: "2026-01-31",
        view: "monthly",
      }),
    );
    await waitFor(() => {
      expect(health).toHaveAttribute("data-health-state", "ready");
    });
    expect(
      await screen.findByTestId("product-category-table"),
    ).toBeInTheDocument();
  });

  it("hides the monthly conclusion while the summary view baseline is loading", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pendingBaseline =
      deferred<Awaited<ReturnType<typeof baseClient.getProductCategoryPnl>>>();
    let holdNextBaseline = false;
    const getProductCategoryPnl = vi.fn((options) => {
      if (
        holdNextBaseline &&
        options.view === "ytd" &&
        !options.scenarioRatePct
      ) {
        holdNextBaseline = false;
        return pendingBaseline.promise;
      }
      return baseClient.getProductCategoryPnl(options);
    });

    renderWorkbenchAppWithClient({ ...baseClient, getProductCategoryPnl });
    await screen.findByTestId("product-category-table");
    holdNextBaseline = true;
    await user.click(screen.getByRole("button", { name: "汇总视图" }));

    const health = screen.getByTestId("product-category-data-health");
    await waitFor(() => {
      expect(health).toHaveAttribute("data-health-state", "loading");
    });
    expect(
      screen.queryByTestId("product-category-formal-readiness-band"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-table"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-report-date-slot"),
    ).toHaveTextContent("口径待确认 | 汇总视图");

    pendingBaseline.resolve(
      buildMockProductCategoryPnlEnvelope({
        reportDate: "2026-02-28",
        view: "ytd",
      }),
    );
    await waitFor(() => {
      expect(health).toHaveAttribute("data-health-state", "ready");
    });
    expect(
      await screen.findByTestId("product-category-table"),
    ).toBeInTheDocument();
  });

  it("announces FTP recalculation and shows the baseline instead of the prior scenario", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pendingScenario =
      deferred<Awaited<ReturnType<typeof baseClient.getProductCategoryPnl>>>();
    let heldScenarioRate: string | null = null;
    const getProductCategoryPnl = vi.fn((options) => {
      if (options.scenarioRatePct === heldScenarioRate) {
        heldScenarioRate = null;
        return pendingScenario.promise;
      }
      return baseClient.getProductCategoryPnl(options);
    });

    renderWorkbenchAppWithClient({ ...baseClient, getProductCategoryPnl });
    await screen.findByTestId("product-category-table");

    await user.selectOptions(
      screen.getByRole("combobox", { name: "FTP 场景" }),
      "2.00",
    );
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );
    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "当前场景：2.00%",
      );
    });

    heldScenarioRate = "1.50";
    await user.selectOptions(
      screen.getByRole("combobox", { name: "FTP 场景" }),
      "1.50",
    );
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );

    const loading = await screen.findByTestId(
      "product-category-scenario-loading",
    );
    expect(loading).toHaveTextContent("情景计算中，当前展示正式基线");
    expect(
      screen.getByTestId("product-category-formal-readiness-band"),
    ).toHaveTextContent("正式基线");
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
      "当前场景：1.75%",
    );
    expect(
      screen.getByTestId("product-category-summary"),
    ).not.toHaveTextContent("当前场景：2.00%");

    pendingScenario.resolve(
      buildMockProductCategoryPnlEnvelope({
        reportDate: "2026-02-28",
        view: "monthly",
        scenarioRatePct: "1.50",
      }),
    );
    await waitFor(() => {
      expect(
        screen.queryByTestId("product-category-scenario-loading"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "当前场景：1.50%",
      );
    });
  });

  it("places a mobile formal table readout before the raw formal grid", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const readout = screen.getByTestId(
      "product-category-formal-table-mobile-readout",
    );
    const rawGrid = screen.getByTestId(
      "product-category-formal-table-raw-grid",
    );

    expect(
      readout.compareDocumentPosition(rawGrid) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(readout).toHaveTextContent("当前核查");
    expect(readout).toHaveTextContent("2026年02月");
    expect(readout).toHaveTextContent("视图");
    expect(readout).toHaveTextContent("人民币净收入");
    expect(readout).toHaveTextContent("外币净收入");
    expect(readout).toHaveTextContent("营业净收入");
    expect(readout).toHaveTextContent("合计经营净收入");
    expect(readout).toHaveTextContent("当前产品");
    expect(readout).toHaveTextContent("规模日均");
    expect(readout).toHaveTextContent("加权收益率");
    expect(readout).toHaveTextContent("总表参照");
    expect(
      within(rawGrid).getByTestId("product-category-table"),
    ).toBeInTheDocument();
  });

  it("defaults the formal table to key columns and can reveal the complete audit view", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const table = await screen.findByTestId("product-category-table");
    const displayMode = screen.getByRole("group", { name: "报表列展示" });
    const keyButton = within(displayMode).getByRole("button", {
      name: "关键读数",
    });
    const fullButton = within(displayMode).getByRole("button", {
      name: "完整口径",
    });
    const keyRow = within(table).getByText("买入返售").closest("tr");

    expect(keyButton).toHaveAttribute("aria-pressed", "true");
    expect(fullButton).toHaveAttribute("aria-pressed", "false");
    expect(table).toHaveClass("product-category-formal-table--key");
    expect(within(table).queryByText("人民币FTP")).not.toBeInTheDocument();
    expect(within(keyRow as HTMLElement).getAllByRole("cell")).toHaveLength(6);

    await user.click(fullButton);

    const fullRow = within(table).getByText("买入返售").closest("tr");
    expect(keyButton).toHaveAttribute("aria-pressed", "false");
    expect(fullButton).toHaveAttribute("aria-pressed", "true");
    expect(table).toHaveClass("product-category-formal-table--full");
    expect(within(table).getByText("人民币FTP")).toBeInTheDocument();
    expect(within(fullRow as HTMLElement).getAllByRole("cell")).toHaveLength(
      13,
    );
  });

  it("keeps the selected product review context through column mode changes", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
        buildDrilldownAttributionEnvelope(options.reportDate, options.compare),
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryAttribution: attributionSpy,
    });

    const rootCause = await screen.findByTestId("product-category-root-cause");
    await user.click(
      within(rootCause).getByRole("button", { name: "查看正式明细" }),
    );

    const context = await screen.findByTestId(
      "product-category-formal-selection-context",
    );
    expect(context).toHaveTextContent("当前核查");
    expect(context).toHaveTextContent("拆放同业");
    expect(context).toHaveTextContent("2026年02月");
    expect(context).toHaveTextContent("月度");
    expect(context).toHaveTextContent("正式基线归因定位");
    expect(context).toHaveTextContent("规模日均");
    expect(context).toHaveTextContent("人民币净收入");
    expect(context).toHaveTextContent("外币净收入");
    expect(context).toHaveTextContent("营业净收入");
    expect(context).toHaveTextContent("加权收益率");

    const readout = screen.getByTestId(
      "product-category-formal-table-mobile-readout",
    );
    expect(
      within(readout).getByRole("heading", { name: "拆放同业" }),
    ).toBeInTheDocument();
    expect(
      within(readout).getByText("人民币净收入", { selector: "span" }),
    ).toBeInTheDocument();
    expect(
      within(readout).getByText("外币净收入", { selector: "span" }),
    ).toBeInTheDocument();
    expect(
      within(readout).getByText("营业净收入", { selector: "span" }),
    ).toBeInTheDocument();

    const displayMode = screen.getByRole("group", { name: "报表列展示" });
    await user.click(
      within(displayMode).getByRole("button", { name: "完整口径" }),
    );

    expect(context).toHaveTextContent("拆放同业");
    expect(
      await screen.findByTestId(
        "product-category-formal-row-interbank_lending_assets",
      ),
    ).toHaveAttribute("data-selected", "true");
  });

  it("marks parent and child rows for structural scanning", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const table = await screen.findByTestId("product-category-table");
    const parentRow = within(table).getByText("债券投资").closest("tr");
    const childRow = within(table).getByText("TPL").closest("tr");

    expect(parentRow).toHaveAttribute("data-row-level", "0");
    expect(parentRow).toHaveClass("product-category-formal-table__row--parent");
    expect(childRow).toHaveAttribute("data-row-level", "1");
    expect(childRow).toHaveClass("product-category-formal-table__row--child");
  });

  it("drops a prior row selection when an FTP scenario becomes active", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
        buildDrilldownAttributionEnvelope(options.reportDate, options.compare),
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryAttribution: attributionSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(
      screen.getByRole("button", { name: "查看 买入返售 归因证据" }),
    );
    const repoRow = screen.getByTestId(
      "product-category-formal-row-repo_assets",
    );
    expect(repoRow).toHaveAttribute("data-selected", "true");

    await user.selectOptions(
      screen.getByRole("combobox", { name: "FTP 场景" }),
      "2.00",
    );
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );
    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "当前场景：2.00%",
      );
    });

    expect(repoRow).not.toHaveAttribute("data-selected");
    expect(
      screen.getByTestId("product-category-formal-selection-context"),
    ).not.toHaveTextContent("买入返售");
  });

  it("opens an action queue closure drawer from an operating action row", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const queue = await screen.findByTestId(
      "product-category-operating-action-queue",
    );
    await user.click(
      await within(queue).findByRole("button", {
        name: /查看 买入返售 动作详情/,
      }),
    );

    const drawer = screen.getByTestId(
      "product-category-operating-action-drawer",
    );
    expect(drawer).toHaveTextContent("动作闭环详情");
    expect(drawer).toHaveTextContent("买入返售");
    expect(drawer).toHaveTextContent("压降或限额复核");
    expect(drawer).toHaveTextContent(
      "核对正式表净营收、规模、收益率与归因变动",
    );
    expect(drawer).toHaveTextContent("净营收 -0.05 亿元");

    await user.click(
      within(drawer).getByRole("button", { name: "关闭动作详情" }),
    );
    expect(
      screen.queryByTestId("product-category-operating-action-drawer"),
    ).not.toBeInTheDocument();
  });

  it("renders monthly MoM operating attribution from the formal baseline", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
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
    const attribution = await screen.findByTestId(
      "product-category-attribution",
    );
    await waitFor(() => {
      expect(attribution).toHaveTextContent("拆放同业");
    });
    expect(attribution).toHaveTextContent("经营差异归因");
    expect(attribution).toHaveTextContent("正式基线");
    expect(attribution).toHaveTextContent("拆放同业");
    expect(attribution).toHaveTextContent("规模因素");
    expect(attribution).toHaveTextContent("本期经营净收入");
    expect(attribution).toHaveTextContent("对比期经营净收入");
    expect(attribution).toHaveTextContent("0.30");
    expect(attribution).toHaveTextContent("0.18");
    const comparison = screen.getByTestId(
      "product-category-attribution-comparison-table",
    );
    expect(comparison).toHaveTextContent("规模因素");
    expect(comparison).toHaveTextContent("利率因素");
    const grandTotalRow = screen.getByTestId(
      "product-category-attribution-comparison-row-grand_total",
    );
    expect(grandTotalRow).toHaveTextContent("全表合计");
    const pointDetails = screen.getByTestId(
      "product-category-attribution-detail-table",
    );
    expect(
      within(pointDetails).queryByText("grand_total"),
    ).not.toBeInTheDocument();
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

  it("keeps attribution evidence and the formal product row in one bidirectional selection", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
        buildDrilldownAttributionEnvelope(options.reportDate, options.compare),
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

    const rootCause = await screen.findByTestId("product-category-root-cause");
    await user.click(
      within(rootCause).getByRole("button", { name: "查看正式明细" }),
    );

    const details = screen.getByTestId("product-category-attribution-details");
    expect(details).not.toHaveAttribute("open");
    expect(
      await screen.findByTestId(
        "product-category-formal-row-interbank_lending_assets",
      ),
    ).toHaveAttribute("data-selected", "true");

    await user.click(
      screen.getByRole("button", { name: "查看 拆放同业 归因证据" }),
    );
    const evidence = screen.getByTestId(
      "product-category-attribution-selected-detail",
    );
    expect(details).toHaveAttribute("open");
    expect(evidence).toHaveTextContent("拆放同业");
    expect(
      screen.getByTestId(
        "product-category-attribution-comparison-row-interbank_lending_assets",
      ),
    ).toHaveAttribute("data-selected", "true");
    expect(
      screen.getByTestId(
        "product-category-attribution-detail-row-interbank_lending_assets",
      ),
    ).toHaveAttribute("data-selected", "true");

    await user.click(
      within(evidence).getByRole("button", { name: "定位正式报表" }),
    );
    expect(
      screen.getByTestId(
        "product-category-formal-row-interbank_lending_assets",
      ),
    ).toHaveAttribute("data-selected", "true");

    await user.click(
      screen.getByRole("button", { name: "查看 买入返售 归因证据" }),
    );
    expect(evidence).toHaveTextContent("买入返售");
    expect(
      screen.getByTestId(
        "product-category-attribution-comparison-row-repo_assets",
      ),
    ).toHaveAttribute("data-selected", "true");
    expect(
      screen.getByTestId("product-category-formal-row-repo_assets"),
    ).toHaveAttribute("data-selected", "true");
    expect(
      screen.getByTestId("product-category-formal-table-mobile-readout"),
    ).toHaveTextContent("买入返售");

    await user.selectOptions(
      screen.getByLabelText("查看产品"),
      "interbank_lending_assets",
    );
    expect(evidence).toHaveTextContent("拆放同业");

    await user.click(screen.getByRole("button", { name: "同比" }));
    await waitFor(() => {
      expect(attributionSpy).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        compare: "yoy",
      });
    });
    expect(evidence).toHaveTextContent("拆放同业");
    expect(
      screen.getByTestId(
        "product-category-formal-row-interbank_lending_assets",
      ),
    ).toHaveAttribute("data-selected", "true");
    expect(
      screen.getByTestId("product-category-formal-row-repo_assets"),
    ).not.toHaveAttribute("data-selected");

    await user.click(screen.getByRole("button", { name: "汇总视图" }));
    await screen.findByTestId("product-category-attribution-ineligible");
    expect(
      screen.queryByRole("button", { name: "查看 买入返售 归因证据" }),
    ).not.toBeInTheDocument();
    expect(
      screen
        .queryByTestId("product-category-formal-row-repo_assets")
        ?.getAttribute("data-selected") ?? null,
    ).toBeNull();
  });

  it("prioritizes the selected product decision and keeps full attribution evidence collapsed", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryAttribution: async (options) =>
        buildDrilldownAttributionEnvelope(options.reportDate, options.compare),
    });

    await user.click(
      await screen.findByRole("button", { name: "查看 拆放同业 归因证据" }),
    );

    const evidence = screen.getByTestId(
      "product-category-attribution-selected-detail",
    );
    const decision = within(evidence).getByTestId(
      "product-category-attribution-selected-decision",
    );
    expect(decision).toHaveTextContent("拆放同业");
    expect(decision).toHaveTextContent("变动合计");
    expect(decision).toHaveTextContent("本期经营净收入");
    expect(decision).toHaveTextContent("对比期经营净收入");
    expect(decision).toHaveTextContent("闭合误差");

    const drivers = within(evidence).getAllByTestId(
      "product-category-attribution-selected-driver",
    );
    expect(drivers).toHaveLength(3);
    expect(drivers[0]).toHaveTextContent("规模因素");
    expect(drivers[1]).toHaveTextContent("利率因素");
    expect(drivers[2]).toHaveTextContent("天数因素");

    const fullEvidence = within(evidence).getByTestId(
      "product-category-attribution-selected-full-evidence",
    );
    expect(fullEvidence).not.toHaveAttribute("open");
    expect(fullEvidence).toHaveTextContent("完整口径与证据");
    expect(fullEvidence).toHaveTextContent("本期规模");
    expect(fullEvidence).toHaveTextContent("FTP因素");

    await user.click(within(fullEvidence).getByText("完整口径与证据"));
    expect(fullEvidence).toHaveAttribute("open");
  });

  it("shows a closure-error warning when attribution residual is non-zero", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
        buildMockAttributionEnvelope(options.reportDate, options.compare, {
          closureErrorYi: 0.02,
        }),
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

    await screen.findByTestId("product-category-attribution");
    const warning = await screen.findByTestId(
      "product-category-closure-error-warning",
    );
    expect(warning).toHaveTextContent(
      "对账残差非零，父级自报变动与子项之和存在缺口",
    );
  });

  it("places a mobile attribution comparison readout before the raw comparison table", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
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

    const rawTable = await screen.findByTestId(
      "product-category-attribution-comparison-table",
    );
    const readout = screen.getByTestId(
      "product-category-attribution-comparison-mobile-readout",
    );

    expect(
      readout.compareDocumentPosition(rawTable) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(readout).toHaveTextContent("0.46");
    expect(readout).toHaveTextContent("0.30");
    expect(readout).toHaveTextContent("0.00");
    expect(readout).toHaveTextContent("complete");
  });

  it("places a mobile attribution detail readout before the raw detail table", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
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

    const rawTable = await screen.findByTestId(
      "product-category-attribution-detail-table",
    );
    const readout = screen.getByTestId(
      "product-category-attribution-detail-mobile-readout",
    );

    expect(
      readout.compareDocumentPosition(rawTable) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
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

    const attribution = await screen.findByTestId(
      "product-category-attribution",
    );
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
    expect(
      screen.getByTestId("product-category-attribution-detail-table"),
    ).toHaveTextContent("2025年02月");
  });

  it("does not request product-category attribution outside the monthly view", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const attributionSpy = vi.fn(
      async (options: { reportDate: string; compare?: "mom" | "yoy" }) =>
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

    const attribution = await screen.findByTestId(
      "product-category-attribution",
    );
    await waitFor(() => {
      expect(attribution).toHaveTextContent("拆放同业");
    });
    attributionSpy.mockClear();
    const viewButtons = within(
      screen.getByRole("group", { name: "视图模式" }),
    ).getAllByRole("button");
    await user.click(viewButtons[1]!);

    const ineligible = await screen.findByTestId(
      "product-category-attribution-ineligible",
    );
    expect(ineligible).toHaveTextContent("仅支持月度视图");
    const driverReadout = await screen.findByTestId(
      "product-category-formal-driver-readout",
    );
    expect(driverReadout).toHaveTextContent("关键驱动仅支持月度视图");
    expect(driverReadout).not.toHaveTextContent("归因数据加载中");
    expect(
      screen.queryByTestId("product-category-attribution-bridge"),
    ).not.toBeInTheDocument();
    expect(attributionSpy).not.toHaveBeenCalled();
  });

  it("keeps attribution failure explicit and restores the bridge after retry", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let denyAttribution = true;
    const attributionSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryAttribution>[0],
      ) => {
        if (denyAttribution) {
          throw new Error("attribution unavailable");
        }
        return buildTieOutAttributionEnvelope(
          options.reportDate,
          options.compare,
        );
      },
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryAttribution: attributionSpy,
    });

    const workbench = await screen.findByTestId(
      "product-category-attribution-workbench",
    );
    await waitFor(() => {
      expect(
        within(workbench).getByText("归因数据加载失败。"),
      ).toBeInTheDocument();
    });
    expect(
      within(workbench).queryByTestId("product-category-attribution-bridge"),
    ).not.toBeInTheDocument();

    denyAttribution = false;
    await user.click(within(workbench).getByRole("button", { name: "重试" }));

    await waitFor(() => {
      expect(
        within(workbench).getByTestId("product-category-attribution-bridge"),
      ).toBeInTheDocument();
    });
    expect(attributionSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("Unit 1: first report_dates entry drives baseline PnL, manual adjustments list, and ledger link", async () => {
    preferCollapsedTrendWorkspace();
    const baseClient = createApiClient({ mode: "mock" });
    const firstDate = "2026-03-31";
    const pnlSpy = vi.fn(
      (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
        baseClient.getProductCategoryPnl(options),
    );
    const adjSpy = vi.fn(
      (
        reportDate: string,
        opts?: Parameters<
          typeof baseClient.getProductCategoryManualAdjustments
        >[1],
      ) => baseClient.getProductCategoryManualAdjustments(reportDate, opts),
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
    expect(pnlSpy.mock.calls.map((call) => call[0]!.reportDate)).toEqual([
      firstDate,
    ]);
    expect(pnlSpy.mock.calls[0]![0]).toMatchObject({
      reportDate: firstDate,
      view: "monthly",
    });
    expect(adjSpy.mock.calls.every((call) => call[0] === firstDate)).toBe(true);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      "/ledger-pnl?report_date=2026-03-31",
    );
  });

  it("loads product-category scenario sensitivity only when requested", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn(
      (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
        baseClient.getProductCategoryPnl(options),
    );

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl,
    });

    await screen.findByTestId("product-category-table");
    expect(
      getProductCategoryPnl.mock.calls.every(
        (call) => call[0]?.scenarioRatePct === undefined,
      ),
    ).toBe(true);

    await user.click(
      within(
        screen.getByTestId("product-category-scenario-sensitivity"),
      ).getByRole("button"),
    );

    await waitFor(() => {
      const scenarioRates = getProductCategoryPnl.mock.calls
        .map((call) => call[0]?.scenarioRatePct)
        .filter(Boolean)
        .sort();
      expect(scenarioRates).toEqual(["1.50", "1.60", "1.75", "2.00"]);
    });
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-scenario-sensitivity"),
      ).toHaveTextContent("总净营收");
    });
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("情景解读");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("关键变动行排行");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("每 1 bp");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("FTP 压力路径");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("压力复核包");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("临界 FTP");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("资产/负债冲抵");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("复核顺序");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("管理动作");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("产品行热力条");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("多情景对比");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("仅承压");
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("仅改善");
    const closure = screen.getByTestId(
      "product-category-scenario-action-closure",
    );
    expect(closure).toHaveTextContent("情景动作闭环");
    expect(closure).toHaveTextContent("本期经营动作清单");
    expect(closure).toHaveTextContent("待处理");
    expect(closure).toHaveTextContent("建议动作");
    expect(
      within(closure).queryByTestId("product-category-scenario-action-memo"),
    ).not.toBeInTheDocument();
    await user.click(
      within(closure).getAllByRole("button", { name: "复核中" })[0]!,
    );
    expect(closure).toHaveTextContent("复核中 1");
    expect(
      within(closure).queryByTestId("product-category-scenario-action-memo"),
    ).not.toBeInTheDocument();
    await user.click(
      within(closure).getAllByRole("button", { name: "生成复核备忘" })[0]!,
    );
    const memo = within(closure).getByTestId(
      "product-category-scenario-action-memo",
    );
    expect(memo).toHaveTextContent("复核备忘");
    expect(memo).toHaveTextContent("状态：复核中");

    await user.click(screen.getByRole("button", { name: "仅改善" }));
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("当前筛选下暂无可比较产品行。");
    await user.click(screen.getByRole("button", { name: "仅承压" }));
    expect(
      screen.getByTestId("product-category-scenario-sensitivity"),
    ).toHaveTextContent("生息资产");
    await user.click(
      screen.getByRole("button", { name: /生息资产 多情景对比/ }),
    );
    expect(
      screen.getByTestId("product-category-scenario-explanation"),
    ).toHaveTextContent("生息资产");

    await user.click(screen.getByRole("button", { name: /复核 1/ }));
    const explanation = screen.getByTestId(
      "product-category-scenario-explanation",
    );
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
    expect(
      within(explanation).getAllByRole("button", { name: "待核对" }),
    ).toHaveLength(3);

    await user.click(
      within(explanation).getAllByRole("button", { name: "已确认" })[0]!,
    );
    expect(
      within(explanation).getAllByRole("button", { name: "已确认" })[0],
    ).toHaveAttribute("aria-pressed", "true");

    await user.click(
      within(explanation).getAllByRole("button", { name: "有差异" })[0]!,
    );
    expect(
      within(explanation).getAllByRole("button", { name: "有差异" })[0],
    ).toHaveAttribute("aria-pressed", "true");

    expect(explanation).toHaveTextContent("复核结论台");
    expect(explanation).toHaveTextContent("待核对 2");
    expect(explanation).toHaveTextContent("已确认 0");
    expect(explanation).toHaveTextContent("有差异 1");

    await user.click(
      within(explanation).getByRole("button", { name: "全部确认" }),
    );
    expect(
      within(explanation).getAllByRole("button", { name: "已确认" }),
    ).toHaveLength(3);
    expect(explanation).toHaveTextContent("已确认 3");
    expect(explanation).toHaveTextContent(
      "复核结论：生息资产动作已全部确认，可进入留痕归档。",
    );

    await user.click(
      within(explanation).getAllByRole("button", { name: "有差异" })[1]!,
    );
    await user.click(
      within(explanation).getByRole("button", { name: "FTP 驱动异常" }),
    );
    expect(
      within(explanation).getByRole("button", { name: "FTP 驱动异常" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(explanation).toHaveTextContent("差异原因：FTP 驱动异常");
    expect(explanation).toHaveTextContent("复核备忘");
    expect(explanation).toHaveTextContent("当前产品：生息资产");

    await user.click(
      within(explanation).getAllByRole("button", { name: "已确认" })[1]!,
    );
    expect(explanation).toHaveTextContent("差异原因：未选择");

    await user.click(
      within(explanation).getByRole("button", { name: "重置复核" }),
    );
    expect(explanation).toHaveTextContent("待核对 3");
    expect(
      within(explanation).getAllByRole("button", { name: "待核对" })[0],
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("Unit 1: empty report_dates skips PnL and adjustments fetches; ledger stays bare; as_of gap does not inject meta dates", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const guard = () =>
      Promise.reject(new Error("unexpected product-category dependent fetch"));
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
    expect(screen.getByTestId("product-category-data-health")).toHaveAttribute(
      "data-health-state",
      "empty",
    );
    expect(
      screen.getByTestId("product-category-data-health"),
    ).toHaveTextContent("暂无可选报告月份");
    expect(
      screen.queryByTestId("product-category-formal-readiness-band"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      "/ledger-pnl",
    );
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
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (
          staleSelectedDateShouldFail &&
          options.reportDate === selectedDate
        ) {
          throw new Error("unit1-selected-date-disappeared");
        }
        return baseClient.getProductCategoryPnl(options);
      },
    );
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
    expect(
      screen.getByTestId("product-category-report-date-slot"),
    ).toHaveTextContent(selectedDate);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      `/ledger-pnl?report_date=${selectedDate}`,
    );

    staleSelectedDateShouldFail = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => expect(datesSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      expect(
        pnlSpy.mock.calls.some(
          (call) =>
            call[0]?.reportDate === selectedDate && call[0]?.view === "monthly",
        ),
      ).toBe(true);
    });
    expect(
      pnlSpy.mock.calls.some((call) => call[0]?.reportDate === replacementDate),
    ).toBe(false);
    expect(
      screen.getByTestId("product-category-report-date-slot"),
    ).toHaveTextContent(selectedDate);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      `/ledger-pnl?report_date=${selectedDate}`,
    );

    await waitFor(() => {
      expect(
        screen.queryByTestId("product-category-table"),
      ).not.toBeInTheDocument();
    });
    expect(
      screen
        .getAllByRole("button")
        .some(
          (button) =>
            button.textContent === "\u91cd\u8bd5" ||
            button.textContent === "閲嶈瘯",
        ),
    ).toBe(true);
  });

  it("shows report date choices as months while keeping month-end values for the API", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const monthSelect = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    expect(monthSelect.value).toBe("2026-02-28");
    expect(
      Array.from(monthSelect.options)
        .slice(0, 2)
        .map((option) => [option.value, option.textContent]),
    ).toEqual([
      ["2026-02-28", "2026年02月"],
      ["2026-01-31", "2026年01月"],
    ]);
  });

  it("renders the governed diagnostics matrix and negative watchlist from existing payload rows", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await waitForTrendDiagnosticsAutoLoad();
    await screen.findByTestId("product-category-diagnostics-matrix");
    expect(
      screen.getByTestId("product-category-diagnostics-watchlist"),
    ).toBeInTheDocument();
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
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
    const spread = await screen.findByTestId(
      "product-category-diagnostics-spread",
    );
    await waitFor(() => {
      expect(spread).toHaveTextContent("缺少完整收益率对比");
    });
    expect(spread).toHaveTextContent("2026年02月");
    expect(spread).toHaveTextContent("2026年01月");
    expect(spread).toHaveTextContent(
      "后端未返回资产端或负债端收益率字段，无法展示利差归因。",
    );
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
        const envelope = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const assetTotal = {
          ...envelope.result.asset_total,
          weighted_yield: null,
        };
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

    await waitForTrendDiagnosticsAutoLoad();
    expect(
      screen.getByTestId("product-category-diagnostics-matrix-empty"),
    ).toHaveTextContent("当前 payload 未返回可诊断的产品行。");
    expect(
      screen.getByTestId("product-category-diagnostics-watchlist-empty"),
    ).toHaveTextContent("当前 payload 未返回可诊断的产品行。");
    expect(
      screen.getByTestId("product-category-diagnostics-spread-incomplete"),
    ).toHaveTextContent(
      "后端未返回资产端或负债端收益率字段，无法展示利差归因。",
    );
    const liabilityOption = readChartOption(
      "product-category-liability-side-trend",
    );
    expect(liabilityOption.xAxis).toMatchObject({ data: ["2026年02月"] });
    expect(liabilityOption.series?.[0]?.data).toEqual([null]);
    expect(liabilityOption.series?.[1]?.data).toEqual([null]);
    expect(
      screen.getByTestId("product-category-liability-side-trend-incomplete"),
    ).toHaveTextContent("2026年02月负债端日均额缺失");
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
    await screen.findByTestId(
      "product-category-liability-side-detail-credit_linked_notes",
    );
    const liabilityOption = readChartOption(
      "product-category-liability-side-trend",
    );
    expect(liabilityOption.xAxis).toMatchObject({ data: ["2026年02月"] });
    expect(liabilityOption.series?.[0]?.data).toEqual([null]);
    expect(liabilityOption.series?.[1]?.data).toEqual([null]);
    expect(
      screen.queryByTestId("product-category-liability-side-trend-empty"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-liability-side-trend-incomplete"),
    ).toHaveTextContent("2026年02月负债端日均额缺失");
    expect(
      screen.getByTestId(
        "product-category-liability-side-detail-credit_linked_notes",
      ),
    ).toBeInTheDocument();
  });

  it("renders the requested derived chart panels with chart stubs", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await waitForTrendDiagnosticsAutoLoad();
    expect(
      await screen.findByTestId(
        "product-category-derived-chart-tpl-scale-yield",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-derived-chart-currency-net-income"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(
        "product-category-derived-chart-interest-earning-income-scale",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-derived-chart-interest-spread"),
    ).toHaveTextContent("资产负债利差趋势图");
    const existingInterestSpreadOption = readChartOption(
      "product-category-derived-chart-interest-spread",
    );
    // 含TPL 口径面板的系列名必须与紧邻的真·生息资产面板区分开（78BP vs 93BP）。
    expect(existingInterestSpreadOption.legend?.data).toEqual([
      "资产端收益率（含TPL）（%）",
      "负债端成本率（%）",
      "资产负债利差（含TPL）（%）",
    ]);
    expect(
      existingInterestSpreadOption.series?.map((series) => series.name),
    ).toEqual([
      "资产端收益率（含TPL）（%）",
      "负债端成本率（%）",
      "资产负债利差（含TPL）（%）",
    ]);
    const earningSpreadOption = readChartOption(
      "product-category-derived-chart-interest-earning-spread",
    );
    expect(earningSpreadOption.legend?.data).toEqual([
      "生息资产收益率（%）",
      "负债端成本率（%）",
      "生息资产负债利差（%）",
    ]);
    expect(existingInterestSpreadOption.legend?.data).not.toContain(
      "生息资产收益率（%）",
    );
    expect(
      screen.getByTestId(
        "product-category-derived-chart-interest-earning-spread",
      ),
    ).toHaveTextContent("生息资产负债利差趋势图");
    expect(
      screen.getByTestId(
        "product-category-derived-chart-interest-earning-asset-liability-scale",
      ),
    ).toHaveTextContent("生息资产和附息负债走势图");
    expect(
      screen.getByTestId(
        "product-category-derived-chart-interest-earning-spread-yoy",
      ),
    ).toHaveTextContent("生息资产利差：今年与上年同月");
    expect(
      screen.getByTestId(
        "product-category-derived-chart-interest-earning-spread-yoy-cny",
      ),
    ).toHaveTextContent("人民币生息资产利差：今年与上年同月");
    expect(
      screen.getByTestId("product-category-derived-chart-interest-spread-yoy"),
    ).toHaveTextContent("资产负债利差：今年与上年同月");
    expect(
      screen.getByTestId(
        "product-category-derived-chart-interest-spread-yoy-cny",
      ),
    ).toHaveTextContent("人民币资产负债利差：今年与上年同月");
    expect(
      screen.getByTestId(
        "product-category-derived-chart-intermediate-business-income-yoy",
      ),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("动作类型表现");
    });
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("样本覆盖");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("等待下一期 2026-03-31 payload 验证");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("已回测");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("最新月待观察");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("归因覆盖");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("回测闸口");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("样本不足");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("补样本任务");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("补 2 个月");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("需补月份：2026-03-31、2026-04-30");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("最早复核：2026-04-30 后");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("复核工作量");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("规则处置");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("收紧 3");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("回测校准建议");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("收紧触发条件");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("低置信");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("最新信号校准复核");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("补样本后复核");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("P3 低样本复核");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("历史均值");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("当前证据");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("规模 1013.32 亿元");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("观察月份");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("观察口径");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("判定缺口");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("确认最新收益率改善证据");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("放行条件");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("未命中诊断");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("收益率未改善");
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).toHaveTextContent("典型样本");
    expect(screen.getAllByTestId("product-category-echarts-stub")).toHaveLength(
      13,
    );
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const withGrandTotal = {
          ...env,
          result: {
            ...env.result,
            grand_total: {
              ...env.result.grand_total,
              cny_net: yuan(options.reportDate === "2026-01-31" ? 2.12 : 2.71),
              foreign_net: yuan(
                options.reportDate === "2026-01-31" ? 0.18 : 0.14,
              ),
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

    const tplOption = readChartOption(
      "product-category-derived-chart-tpl-scale-yield",
    );
    expect(tplOption.legend?.data).toEqual([
      "人民币规模（亿元）",
      "外币规模（亿元）",
      "收益率（%）",
    ]);
    expect(tplOption.xAxis).toMatchObject({
      data: ["2026年01月", "2026年02月"],
    });
    expect(tplOption.series?.map((series) => series.name)).toEqual([
      "人民币规模（亿元）",
      "外币规模（亿元）",
      "收益率（%）",
    ]);
    expect(tplOption.series?.map((series) => series.type)).toEqual([
      "bar",
      "bar",
      "line",
    ]);
    expect(tplOption.series?.[0]?.data).toEqual([810, 865.79]);
    expect(tplOption.series?.[1]?.data).toEqual([12, -0.8]);
    expect(tplOption.series?.[2]?.data).toEqual([2.18, 2.31]);

    const netIncomeOption = readChartOption(
      "product-category-derived-chart-currency-net-income",
    );
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

    const interestEarningAssetLiabilityScaleOption = readChartOption(
      "product-category-derived-chart-interest-earning-asset-liability-scale",
    );
    expect(interestEarningAssetLiabilityScaleOption.legend?.data).toEqual([
      "生息资产日均额（亿元）",
      "附息负债日均额（亿元）",
    ]);
    expect(
      interestEarningAssetLiabilityScaleOption.series?.map(
        (series) => series.name,
      ),
    ).toEqual(["生息资产日均额（亿元）", "附息负债日均额（亿元）"]);
    expect(
      interestEarningAssetLiabilityScaleOption.series?.map(
        (series) => series.type,
      ),
    ).toEqual(["bar", "bar"]);
    expect(interestEarningAssetLiabilityScaleOption.series?.[0]?.data).toEqual([
      2800, 2898.5,
    ]);
    expect(interestEarningAssetLiabilityScaleOption.series?.[1]?.data).toEqual([
      1728.58, 1728.58,
    ]);
    expect(interestEarningAssetLiabilityScaleOption.backgroundColor).toBe(
      "transparent",
    );
    expect(interestEarningAssetLiabilityScaleOption.tooltip).toMatchObject({
      backgroundColor: nocturneTokens.color.panel2,
      borderColor: nocturneTokens.color.line,
    });
    expect(interestEarningAssetLiabilityScaleOption.legend).toMatchObject({
      top: 4,
      right: 8,
      data: ["生息资产日均额（亿元）", "附息负债日均额（亿元）"],
    });
    expect(interestEarningAssetLiabilityScaleOption.grid).toMatchObject({
      top: 46,
      bottom: 18,
      containLabel: true,
    });
    expect(interestEarningAssetLiabilityScaleOption.yAxis).toMatchObject({
      name: "亿元",
      scale: true,
    });
    expect(interestEarningAssetLiabilityScaleOption.series?.[0]).toMatchObject({
      barMaxWidth: 12,
      barMinHeight: 2,
      barGap: "36%",
      itemStyle: {
        color: "rgba(145,132,217,0.72)",
        borderColor: "rgba(145,132,217,0.4)",
        borderRadius: [2, 2, 0, 0],
      },
    });
    expect(interestEarningAssetLiabilityScaleOption.series?.[1]).toMatchObject({
      barMaxWidth: 12,
      barMinHeight: 2,
      itemStyle: {
        color: "rgba(213,178,110,0.72)",
        borderColor: "rgba(213,178,110,0.4)",
        borderRadius: [2, 2, 0, 0],
      },
    });

    const interestEarningSpreadYoyOption = readChartOption(
      "product-category-derived-chart-interest-earning-spread-yoy",
    );
    expect(
      interestEarningSpreadYoyOption.series?.map((series) => series.name),
    ).toEqual(["2026年"]);
    expect(interestEarningSpreadYoyOption.series?.[0]?.data).toEqual([
      0.77,
      0.77,
      ...Array(10).fill(null),
    ]);
    expect(interestEarningSpreadYoyOption.series?.[0]?.label?.show).toBe(false);
    expect(interestEarningSpreadYoyOption.series?.[0]?.lineStyle).toMatchObject(
      {
        type: "solid",
        width: 3,
      },
    );

    expect(
      screen.queryByTestId("product-category-derived-chart-interest-spread"),
    ).not.toBeInTheDocument();

    const liabilityOption = readChartOption(
      "product-category-liability-side-trend",
    );
    expect(liabilityOption.legend?.data).toEqual([
      "负债端日均额（亿元）",
      "负债端利率（%）",
    ]);
    expect(liabilityOption.xAxis).toMatchObject({
      data: ["2026年01月", "2026年02月"],
    });
    const liabilityMatrix = screen.getByTestId(
      "product-category-liability-side-detail-matrix",
    );
    expect(within(liabilityMatrix).getByText("2026年01月")).toBeInTheDocument();
    expect(within(liabilityMatrix).getByText("2026年02月")).toBeInTheDocument();
    expect(
      within(liabilityMatrix).getByText("环比月度变动情况"),
    ).toBeInTheDocument();
    expect(
      within(liabilityMatrix).getAllByText("日均额").length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      within(liabilityMatrix).getAllByText("收益率").length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      screen.getByTestId(
        "product-category-liability-side-detail-liability_total",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-liability-side-currency-matrix-cny"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(
        "product-category-liability-side-currency-matrix-foreign",
      ),
    ).toBeInTheDocument();
    expect(
      within(
        screen.getByTestId(
          "product-category-liability-side-currency-matrix-cny",
        ),
      ).getAllByText("收益率").length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      within(
        screen.getByTestId(
          "product-category-liability-side-currency-matrix-foreign",
        ),
      ).getAllByText("收益率").length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      screen.getByTestId(
        "product-category-liability-side-currency-detail-cny-liability_total",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(
        "product-category-liability-side-currency-detail-foreign-liability_total",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(
        "product-category-liability-side-detail-credit_linked_notes",
      ),
    ).toBeInTheDocument();
  });

  it("places a mobile liability-side detail matrix readout before the raw detail matrix", async () => {
    renderWorkbenchAppWithTwoMonthLiabilityTrend();

    await waitForTrendDiagnosticsAutoLoad();
    const rawMatrix = await screen.findByTestId(
      "product-category-liability-side-detail-matrix",
    );
    const readout = screen.getByTestId(
      "product-category-liability-side-detail-matrix-mobile-readout",
    );

    expect(
      readout.compareDocumentPosition(rawMatrix) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(readout).toHaveAccessibleName("负债结构核查");
    expect(readout).toHaveTextContent("全币种");
    expect(readout).toHaveTextContent("1728.58");
    expect(readout).toHaveTextContent("1.63");
    expect(readout).toHaveTextContent("+5 bp");
    expect(readout).toHaveTextContent("2");
  });

  it("switches liability detail matrices between backend YTD and monthly values", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithTwoMonthLiabilityTrend();

    await waitForTrendDiagnosticsAutoLoad();
    const controls = await screen.findByTestId(
      "product-category-liability-matrix-display-mode",
    );
    const ytdButton = within(controls).getByRole("button", {
      name: "累进值",
    });
    const monthlyButton = within(controls).getByRole("button", {
      name: "单月值",
    });

    expect(ytdButton).toHaveAttribute("aria-pressed", "false");
    expect(monthlyButton).toHaveAttribute("aria-pressed", "true");

    await user.click(ytdButton);

    expect(ytdButton).toHaveAttribute("aria-pressed", "true");
    expect(monthlyButton).toHaveAttribute("aria-pressed", "false");
    await waitFor(() => {
      expect(
        within(
          screen.getByTestId(
            "product-category-liability-side-detail-liability_total",
          ),
        ).getAllByText("2000.00"),
      ).toHaveLength(2);
    });
    expect(
      screen.getByTestId("product-category-liability-matrix-caliber-note"),
    ).toHaveTextContent("后端原始年初至今累计口径");
    expect(
      screen.getByTestId("product-category-trend-liability-card"),
    ).toHaveTextContent("2000.00");
    expect(
      screen.getByTestId("product-category-trend-liability-card"),
    ).toHaveTextContent("1.80");

    await user.click(monthlyButton);

    const liabilityTotalRow = screen.getByTestId(
      "product-category-liability-side-detail-liability_total",
    );
    expect(
      within(liabilityTotalRow).getAllByText("1728.58"),
    ).toHaveLength(2);
    expect(
      screen.getByTestId("product-category-liability-matrix-caliber-note"),
    ).toHaveTextContent("后端原始单月口径");
    expect(
      screen.getByTestId("product-category-trend-liability-card"),
    ).toHaveTextContent("1728.58");
    expect(
      screen.getByTestId("product-category-trend-liability-card"),
    ).toHaveTextContent("1.63");
  });

  it("places mobile liability-side currency readouts before each raw currency matrix", async () => {
    renderWorkbenchAppWithTwoMonthLiabilityTrend();

    await waitForTrendDiagnosticsAutoLoad();
    const cnyMatrix = await screen.findByTestId(
      "product-category-liability-side-currency-matrix-cny",
    );
    const foreignMatrix = screen.getByTestId(
      "product-category-liability-side-currency-matrix-foreign",
    );
    const cnyReadout = screen.getByTestId(
      "product-category-liability-side-currency-matrix-cny-mobile-readout",
    );
    const foreignReadout = screen.getByTestId(
      "product-category-liability-side-currency-matrix-foreign-mobile-readout",
    );

    expect(
      cnyReadout.compareDocumentPosition(cnyMatrix) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      foreignReadout.compareDocumentPosition(foreignMatrix) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(cnyReadout).toHaveAccessibleName("人民币结构核查");
    expect(foreignReadout).toHaveAccessibleName("外币结构核查");
    expect(cnyReadout).toHaveTextContent("cny");
    expect(cnyReadout).toHaveTextContent("1729.55");
    expect(foreignReadout).toHaveTextContent("foreign");
    expect(foreignReadout).toHaveTextContent("0.97");
  });

  it("keeps raw liability matrices in closed disclosures until requested", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithTwoMonthLiabilityTrend();

    await waitForTrendDiagnosticsAutoLoad();
    const totalDisclosure = await screen.findByTestId(
      "product-category-liability-side-detail-disclosure",
    );
    const cnyDisclosure = screen.getByTestId(
      "product-category-liability-side-currency-disclosure-cny",
    );
    const foreignDisclosure = screen.getByTestId(
      "product-category-liability-side-currency-disclosure-foreign",
    );

    [totalDisclosure, cnyDisclosure, foreignDisclosure].forEach(
      (disclosure) => {
        expect(disclosure.tagName).toBe("DETAILS");
        expect(disclosure).not.toHaveAttribute("open");
      },
    );
    expect(
      within(totalDisclosure).getByTestId(
        "product-category-liability-side-detail-matrix",
      ),
    ).toBeInTheDocument();
    expect(totalDisclosure).toHaveTextContent("全币种明细矩阵");

    const summary = totalDisclosure.querySelector("summary");
    expect(summary).toBeTruthy();
    await user.click(summary as HTMLElement);
    expect(totalDisclosure).toHaveAttribute("open");
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const rates = ratesByDate[options.reportDate] ?? {
          asset: "2.00",
          liability: "1.50",
        };
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
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-spread-yoy",
      ),
    ).not.toBeInTheDocument();
  });

  it("does not render CNY spread comparison without backend RMB spread fields", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const dateInputs: Record<
      string,
      { days: number; assetCny: number; liabilityCny: number }
    > = {
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const rates = dateInputs[options.reportDate] ?? {
          days: 31,
          assetCny: 2,
          liabilityCny: 1.5,
        };
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? {
                    ...row,
                    cny_scale: yuan(100),
                    cny_cash: fixtureCashAmount(
                      100,
                      rates.assetCny,
                      rates.days,
                    ),
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
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-spread-yoy-cny",
      ),
    ).not.toBeInTheDocument();
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const income = incomeByDate[options.reportDate];
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "intermediate_business_income"
                ? {
                    ...row,
                    business_net_income:
                      income === null
                        ? row.business_net_income
                        : yuan(income ?? 0),
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
    await screen.findByTestId(
      "product-category-derived-chart-intermediate-business-income-yoy",
    );
    const incomeOption = readChartOption(
      "product-category-derived-chart-intermediate-business-income-yoy",
    );

    expect(incomeOption.legend?.data).toEqual([
      "\u0032\u0030\u0032\u0035\u5e74",
      "\u0032\u0030\u0032\u0036\u5e74",
    ]);
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
    expect(incomeOption.series?.map((series) => series.type)).toEqual([
      "bar",
      "bar",
    ]);
    expect(incomeOption.yAxis).toMatchObject({
      name: "亿元",
      min: 0,
    });
    expect(incomeOption.series?.[1]?.markLine?.data).toMatchObject([
      { yAxis: 0 },
      { xAxis: "3月" },
    ]);
    expect(incomeOption.series?.[0]?.markArea?.data).toEqual([
      [{ xAxis: "4月" }, { xAxis: "12月" }],
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
      "2025-01-31": {
        days: 31,
        asset: "2.20",
        liability: "1.60",
        assetCny: 2.2,
        liabilityCny: 1.5,
      },
      "2025-02-28": {
        days: 28,
        asset: "2.28",
        liability: "1.63",
        assetCny: 2.3,
        liabilityCny: 1.6,
      },
      "2025-03-31": {
        days: 31,
        asset: "2.35",
        liability: "1.65",
        assetCny: 2.3,
        liabilityCny: 1.6,
      },
      "2025-12-31": {
        days: 31,
        asset: "2.40",
        liability: "1.60",
        assetCny: 2.4,
        liabilityCny: 1.6,
      },
      "2026-01-31": {
        days: 31,
        asset: "2.40",
        liability: "1.65",
        assetCny: 2.4,
        liabilityCny: 1.55,
      },
      "2026-02-28": {
        days: 28,
        asset: "2.48",
        liability: "1.68",
        assetCny: 2.5,
        liabilityCny: 1.65,
      },
      "2026-03-31": {
        days: 31,
        asset: "2.55",
        liability: "1.70",
        assetCny: 2.55,
        liabilityCny: 1.7,
      },
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const rates =
          dateInputs[options.reportDate] ?? dateInputs["2026-03-31"]!;
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? {
                    ...row,
                    cny_scale: yuan(100),
                    cny_cash: fixtureCashAmount(
                      100,
                      rates.assetCny,
                      rates.days,
                    ),
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
    const attribution = await screen.findByTestId(
      "product-category-interest-spread-attribution",
    );
    await waitFor(() => {
      expect(attribution).toHaveTextContent("\u5168\u53e3\u5f84");
      expect(attribution).toHaveTextContent("\u0033\u6708");
      expect(attribution).toHaveTextContent(
        "\u90e8\u5206\u6570\u636e\u4f7f\u7528\u56de\u9000\u503c",
      );
    });
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-spread-yoy",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-spread-yoy-cny",
      ),
    ).not.toBeInTheDocument();
  });

  it("does not offer CNY linked attribution when backend RMB spread fields are absent", async () => {
    const user = userEvent.setup();
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
      "2025-02-28": {
        days: 28,
        asset: "2.28",
        liability: "1.63",
        assetCny: 2.3,
        liabilityCny: 1.6,
      },
      "2025-03-31": {
        days: 31,
        asset: "2.35",
        liability: "1.65",
        assetCny: 2.3,
        liabilityCny: 1.6,
      },
      "2026-02-28": {
        days: 28,
        asset: "2.48",
        liability: "1.68",
        assetCny: 2.5,
        liabilityCny: 1.65,
      },
      "2026-03-31": {
        days: 31,
        asset: "2.55",
        liability: "1.70",
        assetCny: 2.55,
        liabilityCny: 1.7,
      },
    };
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
            "2026-03-31",
            "2026-02-28",
            "2025-03-31",
            "2025-02-28",
          ],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const rates =
          dateInputs[options.reportDate] ?? dateInputs["2026-03-31"]!;
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? {
                    ...row,
                    cny_scale: yuan(100),
                    cny_cash: fixtureCashAmount(
                      100,
                      rates.assetCny,
                      rates.days,
                    ),
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
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-spread-yoy-cny",
      ),
    ).not.toBeInTheDocument();

    const monthSelect = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    await user.selectOptions(monthSelect, "2026-02-28");
    await waitForTrendDiagnosticsAutoLoad();

    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-interest-spread-attribution"),
      ).toHaveTextContent("\u5168\u53e3\u5f84");
      expect(
        screen.getByTestId("product-category-interest-spread-attribution"),
      ).toHaveTextContent("\u0032\u6708");
      expect(
        screen.getByTestId("product-category-interest-spread-attribution"),
      ).toHaveTextContent(
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
    const panel = await screen.findByTestId(
      "product-category-interest-spread-attribution",
    );
    expect(panel).toHaveTextContent("\u5f85\u8865\u6570");
    expect(panel).toHaveTextContent(
      "\u7f3a\u5c11\u4e0a\u5e74\u540c\u6708\u6570\u636e",
    );
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
        const env = withEmptyInterestSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
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
              asset_total: {
                ...env.result.asset_total,
                weighted_yield: "4.20",
              },
              liability_total: {
                ...env.result.liability_total,
                weighted_yield: "4.80",
              },
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
            liability_total: {
              ...env.result.liability_total,
              weighted_yield: "4.50",
            },
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    await waitFor(() => {
      expect(
        screen.queryByTestId("product-category-derived-chart-interest-spread"),
      ).not.toBeInTheDocument();
    });
  });

  it("does not render interest-earning spread comparison charts without backend interest-earning spread fields", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: [
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
        const env = withEmptyInterestEarningSpread(
          buildMockProductCategoryPnlEnvelope(options),
        );
        const allCurrencySpreadPct =
          options.reportDate === "2026-01-31"
            ? "1.12"
            : options.reportDate === "2026-02-28"
              ? "0.97"
              : "1.05";
        const allCurrencyAssetYieldPct = (
          1.63 + Number(allCurrencySpreadPct)
        ).toFixed(2);
        const interestSpread: ProductCategoryInterestSpreadPayload = {
          all_currency_asset_yield_pct: {
            raw: allCurrencyAssetYieldPct,
            display: `${allCurrencyAssetYieldPct}%`,
            unit: "percent",
          },
          all_currency_liability_yield_pct: {
            raw: "1.63",
            display: "1.63%",
            unit: "percent",
          },
          all_currency_spread_pct: {
            raw: allCurrencySpreadPct,
            display: `${allCurrencySpreadPct}%`,
            unit: "percent",
          },
          cny_asset_yield_pct: {
            raw: "2.64",
            display: "2.64%",
            unit: "percent",
          },
          cny_liability_yield_pct: {
            raw: "1.62",
            display: "1.62%",
            unit: "percent",
          },
          cny_spread_pct: { raw: "1.02", display: "1.02%", unit: "percent" },
        };
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((row) =>
              row.category_id === "interest_earning_assets"
                ? { ...row, weighted_yield: "9.99" }
                : row,
            ),
            interest_spread: interestSpread,
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    expect(
      await screen.findByTestId(
        "product-category-derived-chart-interest-spread-yoy",
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId(
        "product-category-derived-chart-interest-spread-yoy-cny",
      ),
    ).toBeInTheDocument();
    const spreadComparisonOption = readChartOption(
      "product-category-derived-chart-interest-spread-yoy",
    );
    expect(spreadComparisonOption.series?.map((series) => series.name)).toEqual(
      ["2025年", "2025年 · 上年参考", "2026年", "同比差（bp）"],
    );
    expect(spreadComparisonOption.series?.map((series) => series.type)).toEqual(
      ["line", "line", "line", "bar"],
    );
    expect(
      spreadComparisonOption.series?.map((series) => series.lineStyle?.type),
    ).toEqual(["dashed", "dotted", "solid", undefined]);
    expect(
      spreadComparisonOption.series?.map(
        (series) => series.itemStyle?.borderWidth,
      ),
    ).toEqual([2, undefined, 1, undefined]);
    expect(spreadComparisonOption.series?.[1]).toMatchObject({
      silent: true,
      markArea: {
        data: [[{ xAxis: "3月" }, { xAxis: "12月" }]],
      },
    });
    expect(spreadComparisonOption.series?.[0]?.data?.[1]).toBe(1.05);
    expect(spreadComparisonOption.series?.[1]?.data?.[1]).toBeNull();
    expect(spreadComparisonOption.series?.[1]?.data?.[2]).toBe(1.05);
    expect(spreadComparisonOption.grid).toMatchObject([
      { top: 18, height: 92 },
      { top: 132, height: 36 },
    ]);
    expect(spreadComparisonOption.yAxis).toMatchObject([
      { name: "利差（%）", scale: true },
      { name: "同比差（bp）", scale: true },
    ]);
    expect(spreadComparisonOption.series?.[3]).toMatchObject({
      xAxisIndex: 1,
      yAxisIndex: 1,
      barMaxWidth: 14,
      barMinHeight: 2,
      markLine: { data: [{ yAxis: 0 }] },
    });
    expect(
      spreadComparisonOption.series?.[3]?.data?.map((point) =>
        typeof point === "object" && point !== null && "value" in point
          ? (point as { value: unknown }).value
          : point,
      ),
    ).toEqual([7, -8, ...Array(10).fill(null)]);
    const weightedSpreadChart = within(
      screen.getByTestId("product-category-derived-chart-interest-spread-yoy"),
    );
    await user.click(
      weightedSpreadChart.getByTestId(
        "product-category-echarts-click-series-2-index-0",
      ),
    );
    await waitFor(() => {
      const attribution = screen.getByTestId(
        "product-category-interest-spread-attribution",
      );
      expect(attribution).toHaveTextContent("全口径");
      expect(attribution).toHaveTextContent("1月");
    });
    const weightedSilentReference = weightedSpreadChart.getByTestId(
      "product-category-echarts-click-series-1-index-1",
    );
    expect(weightedSilentReference).toBeDisabled();
    await user.click(weightedSilentReference);
    expect(
      screen.getByTestId("product-category-interest-spread-attribution"),
    ).toHaveTextContent("1月");
    await user.click(
      weightedSpreadChart.getByTestId(
        "product-category-echarts-click-series-3-index-1",
      ),
    );
    await waitFor(() => {
      const attribution = screen.getByTestId(
        "product-category-interest-spread-attribution",
      );
      expect(attribution).toHaveTextContent("全口径");
      expect(attribution).toHaveTextContent("2月");
    });
    const cnySpreadChart = within(
      screen.getByTestId(
        "product-category-derived-chart-interest-spread-yoy-cny",
      ),
    );
    await user.click(
      cnySpreadChart.getByTestId(
        "product-category-echarts-click-series-2-index-0",
      ),
    );
    await waitFor(() => {
      const attribution = screen.getByTestId(
        "product-category-interest-spread-attribution",
      );
      expect(attribution).toHaveTextContent("人民币");
      expect(attribution).toHaveTextContent("1月");
    });
    const cnySilentReference = cnySpreadChart.getByTestId(
      "product-category-echarts-click-series-1-index-1",
    );
    expect(cnySilentReference).toBeDisabled();
    await user.click(cnySilentReference);
    expect(
      screen.getByTestId("product-category-interest-spread-attribution"),
    ).toHaveTextContent("1月");
    await user.click(
      cnySpreadChart.getByTestId(
        "product-category-echarts-click-series-3-index-1",
      ),
    );
    await waitFor(() => {
      const attribution = screen.getByTestId(
        "product-category-interest-spread-attribution",
      );
      expect(attribution).toHaveTextContent("人民币");
      expect(attribution).toHaveTextContent("2月");
    });
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-earning-spread-yoy",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId(
        "product-category-derived-chart-interest-earning-spread-yoy-cny",
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps prior-year spread data muted when the current spread is missing", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2025-02-28"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const envelope = buildMockProductCategoryPnlEnvelope(options);
        return options.reportDate === "2026-02-28"
          ? withEmptyInterestSpread(envelope)
          : envelope;
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    const priorOnlyOption = readChartOption(
      "product-category-derived-chart-interest-spread-yoy",
    );
    expect(priorOnlyOption.series?.map((series) => series.name)).toEqual([
      "2025年",
      "2026年",
      "同比差（bp）",
    ]);
    expect(priorOnlyOption.series?.[0]?.lineStyle?.type).toBe("dashed");
    expect(priorOnlyOption.series?.[0]?.itemStyle?.borderWidth).toBe(2);
    expect(priorOnlyOption.series?.[1]?.lineStyle?.type).toBe("solid");
    expect(priorOnlyOption.series?.[1]?.data).toEqual(Array(12).fill(null));
    expect(priorOnlyOption.series?.[1]?.markLine).toBeUndefined();
    expect(priorOnlyOption.series?.[2]).toMatchObject({
      type: "bar",
      data: Array(12).fill(null),
      markLine: { data: [{ yAxis: 0 }] },
    });
    const spreadCard = screen.getByTestId(
      "product-category-derived-chart-interest-spread-yoy",
    );
    const spreadCardStatus = spreadCard.querySelector(
      ".product-category-derived-chart__status",
    );
    expect(spreadCardStatus).not.toBeNull();
    expect(spreadCardStatus).toHaveClass("is-unknown");
    expect(spreadCardStatus).toHaveAttribute(
      "data-comparison-state",
      "insufficient",
    );
    expect(spreadCardStatus).toHaveAttribute("data-quality-state", "ok");
    expect(spreadCardStatus).toHaveTextContent("可比 0/12");
    expect(spreadCardStatus).toHaveTextContent("缺少可比值");

    const comparisonStatus = screen.getByTestId(
      "product-category-trend-comparison-status",
    );
    expect(comparisonStatus).toHaveTextContent("日期覆盖 1/12");
    expect(comparisonStatus).toHaveTextContent("对比期载入 2/2");
    expect(comparisonStatus).not.toHaveTextContent("可比月份");
  });

  it("marks a spread card degraded when a comparable historical envelope uses warning fallback metadata", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: ["2026-02-28", "2025-02-28"],
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) => {
        const envelope = buildMockProductCategoryPnlEnvelope(options);
        if (options.reportDate !== "2025-02-28") {
          return envelope;
        }
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            quality_flag: "warning" as const,
            fallback_mode: "latest_snapshot" as const,
            requested_report_date: "2025-02-28",
            resolved_report_date: "2025-01-31",
            fallback_date: "2025-01-31",
          },
        };
      }),
    });

    await waitForTrendDiagnosticsAutoLoad();
    const spreadCard = await screen.findByTestId(
      "product-category-derived-chart-interest-spread-yoy",
    );
    const spreadCardStatus = spreadCard.querySelector(
      ".product-category-derived-chart__status",
    );
    expect(spreadCardStatus).not.toBeNull();
    expect(spreadCardStatus).toHaveAttribute("data-quality-state", "degraded");
    expect(spreadCardStatus).toHaveTextContent("可比 1/12");
    expect(spreadCardStatus).toHaveTextContent("降级1期");
  });

  it("builds derived charts on 2025 quarter-end points, 2025 Nov-Dec, and 2026 Jan-Mar with one view basis", async () => {
    const user = userEvent.setup();
    preferCollapsedTrendWorkspace();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn(
      async (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
        buildMockProductCategoryPnlEnvelope(options),
    );
    const getProductCategoryAttribution = vi.fn(
      baseClient.getProductCategoryAttribution,
    );
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
    const collapsedTrendWorkspace = await screen.findByTestId(
      "product-category-trend-workspace",
    );
    expect(collapsedTrendWorkspace).not.toHaveAttribute("open");
    expect(getProductCategoryPnl.mock.calls.map((call) => call[0])).toEqual([
      {
        reportDate: "2026-03-31",
        view: "monthly",
      },
    ]);
    expect(
      screen.queryByTestId("product-category-derived-chart-tpl-scale-yield"),
    ).not.toBeInTheDocument();

    await waitForTrendDiagnosticsAutoLoad();
    await screen.findByTestId("product-category-derived-chart-tpl-scale-yield");
    await waitFor(() => {
      const tplOption = readChartOption(
        "product-category-derived-chart-tpl-scale-yield",
      );
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
        getProductCategoryAttribution.mock.calls.filter(
          (call) => call[0].reportDate !== "2026-03-31",
        ),
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
    const viewButtons = within(
      screen.getByRole("group", { name: "视图模式" }),
    ).getAllByRole("button");
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

    // 汇总视图下趋势折叠区保持可见，走势图按 ytd 口径重建。
    expect(
      screen.getByTestId("product-category-trend-workspace"),
    ).toBeInTheDocument();
    await waitFor(() => {
      const ytdTplOption = readChartOption(
        "product-category-derived-chart-tpl-scale-yield",
      );
      expect(
        (ytdTplOption.xAxis as { data: string[] }).data,
      ).toHaveLength(8);
    });
  });

  it("opens the trend workspace by default and remembers the reader's choice", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    // 图表折叠区在页面下方、与多条同款折叠条并列，默认折叠会被读成“图表不见了”。
    const trendWorkspace = await screen.findByTestId(
      "product-category-trend-workspace",
    );
    expect(trendWorkspace).toHaveAttribute("open");
    await screen.findByTestId("product-category-derived-chart-grid");

    const trendSummary = within(trendWorkspace)
      .getByText("趋势与利差候选图表", { exact: true })
      .closest("summary");
    await user.click(trendSummary!);

    await waitFor(() => {
      expect(
        window.localStorage.getItem(TREND_WORKSPACE_STORAGE_KEY),
      ).toBe("0");
    });
    expect(trendWorkspace).not.toHaveAttribute("open");
    expect(
      screen.queryByTestId("product-category-derived-chart-grid"),
    ).not.toBeInTheDocument();

    await user.click(trendSummary!);
    await waitFor(() => {
      expect(
        window.localStorage.getItem(TREND_WORKSPACE_STORAGE_KEY),
      ).toBe("1");
    });
    await screen.findByTestId("product-category-derived-chart-grid");
  });

  it("honours a stored collapsed preference on the next visit", async () => {
    preferCollapsedTrendWorkspace();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const trendWorkspace = await screen.findByTestId(
      "product-category-trend-workspace",
    );
    expect(trendWorkspace).not.toHaveAttribute("open");
    expect(
      screen.queryByTestId("product-category-derived-chart-grid"),
    ).not.toBeInTheDocument();
  });

  it("requests trend history as batches instead of one request per report date", async () => {
    preferCollapsedTrendWorkspace();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryHistory = vi.fn(baseClient.getProductCategoryHistory);
    const getProductCategoryAttributionHistory = vi.fn(
      baseClient.getProductCategoryAttributionHistory,
    );
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
      getProductCategoryHistory,
      getProductCategoryAttributionHistory,
    });

    await screen.findByTestId("product-category-table");
    expect(getProductCategoryHistory).not.toHaveBeenCalled();

    await openProductCategoryTrendWorkspace();

    await waitFor(() => {
      expect(getProductCategoryHistory.mock.calls.length).toBeGreaterThanOrEqual(1);
    });
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-trend-comparison-status"),
      ).toHaveTextContent("对比期载入");
    });

    const historyCalls = getProductCategoryHistory.mock.calls;
    const batchedDates = historyCalls.flatMap(([options]) => options.reportDates);
    // Batched, not per period: each request must carry several report dates on average.
    expect(batchedDates.length / historyCalls.length).toBeGreaterThanOrEqual(2);
    // Batches stay disjoint so no report date is fetched twice.
    expect(new Set(batchedDates).size).toBe(batchedDates.length);
    expect(batchedDates).not.toContain("2026-03-31");

    await waitFor(() => {
      expect(getProductCategoryAttributionHistory).toHaveBeenCalled();
    });
    const attributionDates = getProductCategoryAttributionHistory.mock.calls.flatMap(
      ([options]) => options.reportDates,
    );
    expect(new Set(attributionDates).size).toBe(attributionDates.length);
    expect(attributionDates).not.toContain("2026-03-31");
  });

  it("loads trend history when only the diagnostics or backtest workspace opens", async () => {
    const user = userEvent.setup();
    preferCollapsedTrendWorkspace();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn(
      async (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
        buildMockProductCategoryPnlEnvelope(options),
    );
    const getProductCategoryAttribution = vi.fn(
      baseClient.getProductCategoryAttribution,
    );
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
    const trendWorkspace = await screen.findByTestId(
      "product-category-trend-workspace",
    );
    expect(trendWorkspace).not.toHaveAttribute("open");
    expect(getProductCategoryPnl.mock.calls.map((call) => call[0])).toEqual([
      { reportDate: "2026-03-31", view: "monthly" },
    ]);

    const diagnosticsWorkspace = await screen.findByTestId(
      "product-category-diagnostics-workspace",
    );
    const diagnosticsSummary = within(diagnosticsWorkspace)
      .getByText("诊断与负债趋势候选分析", { exact: true })
      .closest("summary");
    expect(diagnosticsSummary).not.toBeNull();
    await user.click(diagnosticsSummary!);
    await screen.findByTestId("product-category-diagnostics-surface");

    // 诊断折叠区（负债结构核查）消费同一份趋势历史快照：
    // 不展开趋势折叠区也必须补齐历史期间，矩阵才有“较上期变动”和完整走势。
    await waitFor(() => {
      const historyCalls = getProductCategoryPnl.mock.calls
        .map((call) => call[0])
        .filter((options) => options.reportDate !== "2026-03-31")
        .map((options) => `${options.reportDate}:${options.view}`)
        .sort();
      expect(historyCalls).toEqual([
        "2025-03-31:monthly",
        "2025-06-30:monthly",
        "2025-09-30:monthly",
        "2025-11-30:monthly",
        "2025-12-31:monthly",
        "2026-01-31:monthly",
        "2026-02-28:monthly",
      ]);
    });
    expect(trendWorkspace).not.toHaveAttribute("open");
    const liabilityDisclosure = await screen.findByTestId(
      "product-category-liability-side-detail-disclosure",
    );
    await waitFor(() => {
      expect(
        within(liabilityDisclosure).getByText(/8期/),
      ).toBeInTheDocument();
    });

    const backtestWorkspace = await screen.findByTestId(
      "product-category-backtest-workspace",
    );
    const backtestSummary = within(backtestWorkspace)
      .getByText("动作回测候选分析", { exact: true })
      .closest("summary");
    expect(backtestSummary).not.toBeNull();
    await user.click(backtestSummary!);

    // 动作回测折叠区展开后应触发历史归因加载（趋势折叠区仍保持折叠）。
    await waitFor(() => {
      expect(
        getProductCategoryAttribution.mock.calls.filter(
          (call) => call[0].reportDate !== "2026-03-31",
        ),
      ).toHaveLength(7);
    });
    expect(trendWorkspace).not.toHaveAttribute("open");
  });

  it("loads trend history for the management monitor even with every workspace collapsed", async () => {
    preferCollapsedTrendWorkspace();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryHistory = vi.fn(baseClient.getProductCategoryHistory);
    const getProductCategoryAttributionHistory = vi.fn(
      baseClient.getProductCategoryAttributionHistory,
    );
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: vi.fn(async () =>
        buildMockApiEnvelope("product_category_pnl.dates", {
          report_dates: H1_MANAGEMENT_REPORT_DATES,
        }),
      ),
      getProductCategoryPnl: vi.fn(async (options) =>
        buildMockProductCategoryPnlEnvelope(options),
      ),
      getProductCategoryAttribution: vi.fn(
        async ({ reportDate, compare = "mom" }) =>
          buildManagementMonitorAttributionEnvelope(reportDate, compare),
      ),
      getProductCategoryHistory,
      getProductCategoryAttributionHistory,
    });

    // 经营修复监控面板常显在所有折叠区之外：选中 6 月末报告期时，
    // 即便一个折叠区都不展开，它也必须能自己拉到 1—6 月历史，而不是停在“数据不足”提示上。
    const monitor = await screen.findByTestId(
      "product-category-management-monitor",
    );
    await waitFor(() => expect(monitor).toHaveTextContent("6/6 月正式数据"));
    expect(monitor).not.toHaveTextContent("需要 1—6 月连续");
    expect(monitor).not.toHaveTextContent("需选择 6 月末");

    const historyDates = getProductCategoryHistory.mock.calls.flatMap(
      ([options]) => options.reportDates,
    );
    expect(historyDates.sort()).toEqual(
      ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"].sort(),
    );

    // 该面板只消费当前归因（managementMomAttributionQuery），不消费归因历史批量，
    // 所以修复门控不应该顺带触发归因历史请求。
    expect(getProductCategoryAttributionHistory).not.toHaveBeenCalled();

    expect(
      screen.getByTestId("product-category-trend-workspace"),
    ).not.toHaveAttribute("open");
    expect(
      screen.getByTestId("product-category-diagnostics-workspace"),
    ).not.toHaveAttribute("open");
    expect(
      screen.getByTestId("product-category-backtest-workspace"),
    ).not.toHaveAttribute("open");
  });

  it("does not request trend history when the selected report date is not June and every workspace stays collapsed", async () => {
    preferCollapsedTrendWorkspace();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryHistory = vi.fn(baseClient.getProductCategoryHistory);
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
          ],
        }),
      ),
      getProductCategoryHistory,
    });

    await screen.findByTestId("product-category-table");
    const monitor = await screen.findByTestId(
      "product-category-management-monitor",
    );
    // 非 6 月末报告期不需要历史快照，懒加载收益必须保留：不应发出批量历史请求。
    expect(monitor).toHaveTextContent("需选择 6 月末");
    expect(getProductCategoryHistory).not.toHaveBeenCalled();

    expect(
      screen.getByTestId("product-category-trend-workspace"),
    ).not.toHaveAttribute("open");
    expect(
      screen.getByTestId("product-category-diagnostics-workspace"),
    ).not.toHaveAttribute("open");
    expect(
      screen.getByTestId("product-category-backtest-workspace"),
    ).not.toHaveAttribute("open");
  });

  it("Unit 2: formal detail table renders frozen backend fields in column order without metric_id invention", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...env,
          result: {
            ...env.result,
            available_views: [
              "monthly",
              "qtd",
              "ytd",
              "year_to_report_month_end",
            ],
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
    await user.click(screen.getByRole("button", { name: "完整口径" }));
    const assetRow = within(table).getByText("买入返售").closest("tr");
    expect(assetRow).toBeTruthy();
    expect(
      within(assetRow as HTMLElement)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual([
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

    const viewGroup = screen.getByRole("group", { name: "视图模式" });
    const liabilityRow = within(table)
      .getByText("liability delta fixture")
      .closest("tr");
    expect(liabilityRow).toBeTruthy();
    expect(
      within(liabilityRow as HTMLElement)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual([
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
    expect(within(viewGroup).getAllByRole("button")).toHaveLength(2);
    expect(within(viewGroup).queryByText("qtd")).not.toBeInTheDocument();
    expect(
      within(viewGroup).queryByText("year_to_report_month_end"),
    ).not.toBeInTheDocument();
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
    const liabilityCells = within(liabilityRow as HTMLElement).getAllByRole(
      "cell",
    );
    const assetCells = within(assetRow as HTMLElement).getAllByRole("cell");
    // 营业减收入 = 倒数第二列；加权收益率 = 最后一列（与表头一致，避免列序魔法数漂移）
    expect(liabilityCells.at(-2)).toHaveTextContent("1.23");
    expect(assetCells.at(-2)).toHaveTextContent("-1.23");
    expect(liabilityCells.at(-1)).toHaveTextContent("1.41");
    expect(assetCells.at(-1)).toHaveTextContent("1.47");
    expect(within(table).queryByText("grand_total")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-footer-total"),
    ).toHaveTextContent("2.85");
  });

  it("Unit 9: formal baseline refetch failure shows AsyncSection error; no stale table, summary, or footer", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const uniqueMarker = "unit9-formal-asyncsection-stale-marker";
    let denyBaselinePnl = false;
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (denyBaselinePnl) {
          throw new Error("unit9-baseline-refetch-failed");
        }
        const env = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...env,
          result: {
            ...env.result,
            rows: env.result.rows.map((r) =>
              r.category_id === "repo_assets"
                ? { ...r, category_name: uniqueMarker }
                : r,
            ),
          },
        };
      },
    );
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
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
      "FTP后经营净收入：",
    );
    expect(
      screen.getByTestId("product-category-footer-total"),
    ).toHaveTextContent("全部市场科目FTP后经营净收入：");

    denyBaselinePnl = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    const formalLead = await screen.findByTestId(
      "product-category-formal-table-lead",
    );
    const formalSection = formalLead.nextElementSibling as HTMLElement | null;
    expect(formalSection).toBeTruthy();

    await waitFor(() => {
      expect(
        within(formalSection!).getByText("数据载入失败。"),
      ).toBeInTheDocument();
      expect(
        within(formalSection!).getByText(
          "当前页面保留重试入口，不在浏览器端自行拼接正式口径。",
        ),
      ).toBeInTheDocument();
    });
    expect(
      within(formalSection!).getByRole("button", { name: "重试" }),
    ).toBeInTheDocument();

    expect(
      screen.queryByTestId("product-category-table"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(uniqueMarker)).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-summary"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-footer-total"),
    ).not.toBeInTheDocument();

    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(pnlSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
  it("pins the requested FTP scenarios and defaults 2026 reports to 1.6 before explicit apply", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const ftpSelect = screen.getByRole("combobox", {
      name: "FTP 场景",
    }) as HTMLSelectElement;
    expect(
      Array.from(ftpSelect.options).map((option) => [
        option.value,
        option.textContent,
      ]),
    ).toEqual([
      ["2.00", "2.0%"],
      ["1.75", "1.75%"],
      ["1.60", "1.6%"],
      ["1.50", "1.5%"],
    ]);
    await waitFor(() => {
      expect(ftpSelect.value).toBe("1.60");
    });
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
      "当前场景：1.75%",
    );

    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );
    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "当前场景：1.60%",
      );
      expect(
        screen.getByTestId("product-category-result-meta-scenario"),
      ).toHaveTextContent("场景覆盖");
    });
  });

  it("resets the FTP scenario to the selected report year default when switching months", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pnlSpy = vi.fn(
      (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
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
    const [monthSelect, ftpSelect] = screen.getAllByRole(
      "combobox",
    ) as HTMLSelectElement[];
    await waitFor(() => {
      expect(ftpSelect.value).toBe("1.60");
    });

    await user.selectOptions(ftpSelect, "2.00");
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );
    await waitFor(() => {
      expect(pnlSpy).toHaveBeenCalledWith(
        expect.objectContaining({ scenarioRatePct: "2.00" }),
      );
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
            options?.reportDate === "2025-12-31" &&
            options.scenarioRatePct === "2.00",
        ),
    ).toBe(false);
  });

  it("applies a scenario rate only after the apply action", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "FTP 场景" }),
      "2.00",
    );
    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );

    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "2.00",
      );
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent(
        "0.52",
      );
      expect(
        screen.getByTestId("product-category-result-meta-scenario"),
      ).toHaveTextContent("场景覆盖");
      expect(
        screen.getByTestId("product-category-result-meta-scenario"),
      ).toHaveTextContent("是");
      const distinct = screen.getByTestId(
        "product-category-formal-scenario-meta-distinct",
      );
      expect(distinct).toHaveTextContent("正式口径=正式口径");
      expect(distinct).toHaveTextContent("情景口径=情景口径");
      expect(distinct).toHaveTextContent(
        "追踪编号=mock_product_category_pnl.detail",
      );
      expect(
        screen.getByTestId("product-category-scenario-signing-warning"),
      ).toHaveAttribute("title", "formal_use_allowed=false");
      expect(
        screen.getByTestId("product-category-scenario-signing-warning"),
      ).toHaveTextContent("下方归因继续使用正式基线响应");
      expect(
        screen.getByTestId("product-category-result-meta-attribution"),
      ).toHaveTextContent("mock_product_category_pnl.attribution");
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
            fallback_date: "2026-01-31",
            vendor_status: "vendor_stale" as const,
            quality_flag: "warning" as const,
          },
        };
      }),
    });

    await screen.findByTestId("product-category-table");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("quality=warning");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("vendor=vendor_stale");
    expect(
      screen.getByTestId("product-category-formal-readiness-status"),
    ).toHaveTextContent("fallback=latest_snapshot");
    expect(
      screen.getByTestId("product-category-governance-evidence"),
    ).toHaveTextContent("数据状态待复核");
    expect(
      screen.getByTestId("product-category-governance-notice-fallback_mode"),
    ).toHaveTextContent("最新快照降级");
    expect(
      screen.getByTestId("product-category-governance-notice-vendor_status"),
    ).toHaveTextContent("供应商数据陈旧");
    expect(
      screen.getByTestId("product-category-governance-notice-quality_flag"),
    ).toHaveTextContent("预警");
    const health = screen.getByTestId("product-category-data-health");
    expect(health).toHaveAttribute("data-health-state", "degraded");
    expect(health).toHaveAttribute("role", "alert");
    expect(
      within(health).getByTestId("product-category-formal-judgement-status"),
    ).toHaveTextContent("正式判断阻断");
    expect(
      screen.getByTestId("product-category-formal-readiness-band"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-attribution"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-footer-total"),
    ).toBeInTheDocument();
    expect(health).not.toHaveTextContent("回退日期");
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

    expect(
      screen.getByTestId("product-category-refresh-button"),
    ).toBeDisabled();

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
      expect(
        screen.getByTestId("product-category-refresh-button"),
      ).not.toBeDisabled();
    });

    expect(
      screen.queryByTestId("product-category-refresh-status"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/^最近刷新任务：/)).toHaveTextContent(
      "product_category_pnl:test-run",
    );
  });

  it("marks a background baseline refetch as refreshing instead of live", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const baselineRefresh =
      deferred<Awaited<ReturnType<typeof baseClient.getProductCategoryPnl>>>();
    let holdSelectedBaseline = false;
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (
          holdSelectedBaseline &&
          options.reportDate === "2026-02-28" &&
          options.view === "monthly" &&
          !options.scenarioRatePct
        ) {
          return baselineRefresh.promise;
        }
        return buildMockProductCategoryPnlEnvelope(options);
      },
    );
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:ledger-refetch",
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

    await screen.findByTestId("product-category-table");
    holdSelectedBaseline = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      const row = apiLedgerRow(
        "product-category-api-read-surfaces",
        "/?report_date&view",
      );
      expect(row).toHaveTextContent("REFRESHING");
      expect(row).toHaveAttribute("data-endpoint-state", "loading");
    });

    holdSelectedBaseline = false;
    baselineRefresh.resolve(
      buildMockProductCategoryPnlEnvelope({
        reportDate: "2026-02-28",
        view: "monthly",
      }),
    );
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-refresh-button"),
      ).not.toBeDisabled();
      expect(
        apiLedgerRow(
          "product-category-api-read-surfaces",
          "/?report_date&view",
        ),
      ).toHaveTextContent("ROWS");
    });
  });

  it("surfaces refresh conflict (409) with explicit copy and does not record a successful run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => {
      throw new ActionRequestError(
        "Product-category refresh already in progress.",
        {
          status: 409,
        },
      );
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
    expect(
      screen.queryByTestId("product-category-refresh-status"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-refresh-button"),
    ).toHaveTextContent("刷新损益数据");
  });

  it("surfaces sync-fallback service failure (503) with explicit copy and does not record a successful run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => {
      throw new ActionRequestError(
        "Product-category refresh failed during sync fallback.",
        {
          status: 503,
        },
      );
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
        screen.getByText(
          "Product-category refresh failed during sync fallback.",
        ),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-refresh-status"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-refresh-button"),
    ).toHaveTextContent("刷新损益数据");
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
      expect(
        screen.getByText("Product-category refresh run failed (test)."),
      ).toBeInTheDocument();
    });

    expect(
      screen.queryByTestId("product-category-refresh-status"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/product_category_pnl:failed-run/),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-refresh-button"),
    ).toHaveTextContent("刷新损益数据");
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
          ReturnType<
            typeof createApiClient
          >["createProductCategoryManualAdjustment"]
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
    const revokePayload = {
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
    } as const;
    const revokeRequest = deferred<typeof revokePayload>();
    const revokeSpy = vi.fn(() => revokeRequest.promise);
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
      expect(
        screen.queryByTestId("product-category-event-pca-existing-1-edited"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId("product-category-adjustment-history"),
      ).toHaveTextContent("2");
      expect(screen.getByTestId("product-category-audit-link")).toHaveAttribute(
        "href",
        "/product-category-pnl/audit",
      );

      const revokeButton = screen.getByTestId(
        "product-category-revoke-pca-existing-1",
      );
      confirmSpy.mockReturnValueOnce(false);
      await user.click(revokeButton);
      expect(confirmSpy).toHaveBeenCalledTimes(1);
      expect(revokeSpy).not.toHaveBeenCalled();
      expect(refreshSpy).not.toHaveBeenCalled();

      confirmSpy.mockReturnValueOnce(true);
      await user.click(revokeButton);

      expect(
        apiLedgerRow("product-category-api-write-surfaces", "/{id}/revoke"),
      ).toHaveTextContent("REVOKING");
      expect(
        apiLedgerRow(
          "product-category-api-write-surfaces",
          "/manual-adjustments",
        ),
      ).toHaveTextContent("AUTH · CREATE");
      revokeRequest.resolve(revokePayload);

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

    const history = await screen.findByTestId(
      "product-category-adjustment-history",
    );
    expect(within(history).getByText(staleMarker)).toBeInTheDocument();

    denyAdjustments = true;
    await user.click(screen.getByTestId("product-category-refresh-button"));

    const adjustmentLead = await screen.findByTestId(
      "product-category-adjustment-lead",
    );
    const adjustmentSection =
      adjustmentLead.nextElementSibling as HTMLElement | null;
    expect(adjustmentSection).toBeTruthy();

    await waitFor(() => {
      expect(
        within(adjustmentSection!).getByText("数据载入失败。"),
      ).toBeInTheDocument();
    });
    expect(
      within(adjustmentSection!).getByRole("button", { name: "重试" }),
    ).toBeInTheDocument();
    expect(
      within(adjustmentSection!).queryByTestId(
        "product-category-adjustment-history",
      ),
    ).not.toBeInTheDocument();
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
    const editPayload = {
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
    } as const;
    const editRequest = deferred<typeof editPayload>();
    const editSpy = vi.fn(() => editRequest.promise);
    const restorePayload = {
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
    } as const;
    const restoreRequest = deferred<typeof restorePayload>();
    const restoreSpy = vi.fn(() => restoreRequest.promise);
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
    await user.click(
      screen.getByTestId("product-category-edit-pca-existing-2"),
    );

    const form = screen.getByTestId("product-category-manual-form");
    const textboxes = within(form).getAllByRole("textbox");
    await user.clear(textboxes[5]!);
    await user.type(textboxes[5]!, "9");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    expect(
      apiLedgerRow("product-category-api-write-surfaces", "/{id}/edit"),
    ).toHaveTextContent("EDITING");
    expect(
      apiLedgerRow(
        "product-category-api-write-surfaces",
        "/manual-adjustments",
      ),
    ).toHaveTextContent("AUTH · CREATE");
    editRequest.resolve(editPayload);

    await waitFor(() => {
      expect(editSpy).toHaveBeenCalledTimes(1);
      expect(refreshSpy).toHaveBeenCalledTimes(1);
    });

    const restoreButton = await screen.findByTestId(
      "product-category-restore-pca-existing-2",
    );
    await waitFor(() => {
      expect(restoreButton).not.toBeDisabled();
    });
    await user.click(restoreButton);

    expect(
      apiLedgerRow("product-category-api-write-surfaces", "/{id}/restore"),
    ).toHaveTextContent("RESTORING");
    expect(
      apiLedgerRow(
        "product-category-api-write-surfaces",
        "/manual-adjustments",
      ),
    ).toHaveTextContent("AUTH · CREATE");
    restoreRequest.resolve(restorePayload);

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
          {
            ...rowBase,
            adjustment_id: "pca-st-approved",
            approval_status: "approved" as const,
          },
          {
            ...rowBase,
            adjustment_id: "pca-st-pending",
            approval_status: "pending" as const,
          },
          {
            ...rowBase,
            adjustment_id: "pca-st-rejected",
            approval_status: "rejected" as const,
          },
        ],
        events: [],
      }),
    });

    const lead = await screen.findByTestId("product-category-adjustment-lead");
    expect(lead).toHaveTextContent("仅当审批通过可撤销");
    expect(lead).toHaveTextContent("仅当已拒绝可恢复");
    expect(lead).toHaveTextContent("刷新工作流");

    await screen.findByTestId("product-category-revoke-pca-st-approved");
    expect(
      screen.getByTestId("product-category-revoke-pca-st-approved"),
    ).not.toBeDisabled();
    expect(
      screen.getByTestId("product-category-restore-pca-st-approved"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("product-category-revoke-pca-st-pending"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("product-category-restore-pca-st-pending"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("product-category-revoke-pca-st-rejected"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("product-category-restore-pca-st-rejected"),
    ).not.toBeDisabled();

    expect(
      screen.getByTestId("product-category-edit-pca-st-approved"),
    ).not.toBeDisabled();
    expect(
      screen.getByTestId("product-category-edit-pca-st-pending"),
    ).not.toBeDisabled();
    expect(
      screen.getByTestId("product-category-edit-pca-st-rejected"),
    ).not.toBeDisabled();
  });

  it("PCP-01: shows an explicit error state with retry when the report-dates fetch fails", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let denyDates = true;
    const datesSpy = vi.fn(async () => {
      if (denyDates) {
        throw new Error("pcp01-dates-failed");
      }
      return baseClient.getProductCategoryDates();
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryDates: datesSpy,
    });

    const stateSurface = await screen.findByTestId(
      "product-category-data-health",
    );
    await waitFor(() => {
      expect(stateSurface).toHaveTextContent("报告月份加载失败");
      expect(stateSurface).toHaveAttribute("data-health-state", "error");
    });
    expect(
      screen.queryByTestId("product-category-dates-state"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-formal-readiness-band"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-table"),
    ).not.toBeInTheDocument();

    denyDates = false;
    await user.click(
      within(stateSurface).getByRole("button", { name: "重试报告月份" }),
    );

    await waitFor(() => {
      expect(stateSurface).toHaveAttribute("data-health-state", "ready");
    });
    await screen.findByTestId("product-category-table");
  });

  it("PCP-02: shows a scenario error banner while keeping the baseline table when the scenario fetch fails", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (options.scenarioRatePct) {
          throw new Error("pcp02-scenario-failed");
        }
        return baseClient.getProductCategoryPnl(options);
      },
    );

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: pnlSpy,
    });

    const table = await screen.findByTestId("product-category-table");
    expect(
      screen.queryByTestId("product-category-scenario-error"),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByTestId("product-category-apply-scenario-button"),
    );

    const scenarioError = await screen.findByTestId(
      "product-category-scenario-error",
    );
    expect(scenarioError).toHaveTextContent("情景计算失败，当前展示为基线口径");
    expect(
      within(scenarioError).getByRole("button", { name: "重试情景计算" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("product-category-table")).toBe(table);
  });

  it("PCP-03: shows an explicit error state with retry when scenario sensitivity fetch fails", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const sensitivityRates = new Set(["1.50", "1.60", "1.75", "2.00"]);
    let denySensitivity = true;
    const pnlSpy = vi.fn(
      async (
        options: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        if (
          denySensitivity &&
          options.scenarioRatePct &&
          sensitivityRates.has(options.scenarioRatePct)
        ) {
          throw new Error("pcp03-sensitivity-failed");
        }
        return baseClient.getProductCategoryPnl(options);
      },
    );

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: pnlSpy,
    });

    await screen.findByTestId("product-category-table");
    const sensitivityPanel = screen.getByTestId(
      "product-category-scenario-sensitivity",
    );
    const initialState = within(sensitivityPanel).getByTestId(
      "product-category-scenario-sensitivity-state",
    );
    expect(initialState).toHaveAttribute("data-state-variant", "empty");
    expect(initialState).toHaveTextContent("尚未加载情景敏感度矩阵");

    await user.click(
      within(sensitivityPanel).getByRole("button", { name: "加载矩阵" }),
    );

    const errorState = await within(sensitivityPanel).findByTestId(
      "product-category-scenario-sensitivity-state",
    );
    expect(errorState).toHaveAttribute("data-state-variant", "error");
    expect(errorState).toHaveTextContent("情景敏感度加载失败");
    expect(
      within(errorState).getByRole("button", { name: "重试加载矩阵" }),
    ).toBeInTheDocument();
    expect(sensitivityPanel).not.toHaveTextContent("总净营收");

    denySensitivity = false;
    await user.click(
      within(errorState).getByRole("button", { name: "重试加载矩阵" }),
    );

    await waitFor(() => {
      expect(
        within(sensitivityPanel).queryByTestId(
          "product-category-scenario-sensitivity-state",
        ),
      ).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(sensitivityPanel).toHaveTextContent("总净营收");
    });
  });

  function spreadSectionFixture(input: {
    asset: string;
    liability: string;
    spread: string;
  }): ProductCategoryInterestSpreadPayload {
    const percent = (raw: string) => ({
      raw,
      display: `${Number(raw).toFixed(2)}%`,
      unit: "percent" as const,
    });
    return {
      all_currency_asset_yield_pct: percent(input.asset),
      all_currency_liability_yield_pct: percent(input.liability),
      all_currency_spread_pct: percent(input.spread),
      cny_asset_yield_pct: null,
      cny_liability_yield_pct: null,
      cny_spread_pct: null,
    };
  }

  /**
   * 用已核定的 2026-07-31 口径覆盖 mock 的利差段，使两个视图返回不同读数。
   * `liability_cost_decomposition` 由 B1 并行落地，这里按 CONTRACT.md 形状注入以覆盖两条路径。
   */
  function createSpreadReadoutClient(options: { withDecomposition: boolean }) {
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn(
      async (
        request: Parameters<typeof baseClient.getProductCategoryPnl>[0],
      ) => {
        const envelope = await baseClient.getProductCategoryPnl(request);
        const isYtd = request.view === "ytd";
        return {
          ...envelope,
          result: {
            ...envelope.result,
            interest_earning_spread: spreadSectionFixture(
              isYtd
                ? { asset: "2.36", liability: "1.58", spread: "0.78" }
                : { asset: "2.29", liability: "1.53", spread: "0.76" },
            ),
            interest_spread: spreadSectionFixture(
              isYtd
                ? { asset: "2.51", liability: "1.58", spread: "0.93" }
                : { asset: "2.17", liability: "1.53", spread: "0.64" },
            ),
            ...(options.withDecomposition
              ? {
                  liability_cost_decomposition: {
                    liability_yield_pct: {
                      raw: "1.58",
                      display: "1.58%",
                      unit: "percent",
                    },
                    liability_yield_ex_cln_pct: {
                      raw: "1.57",
                      display: "1.57%",
                      unit: "percent",
                    },
                    cln_yield_pct: {
                      raw: "2.79",
                      display: "2.79%",
                      unit: "percent",
                    },
                    cln_drag_bp: { raw: "1.4", display: "1.4bp", unit: "bp" },
                    cln_scale: "-1947000000",
                  },
                }
              : {}),
          } as typeof envelope.result,
        };
      },
    );
    return { ...baseClient, getProductCategoryPnl };
  }

  it("answers the overall spread on the first screen and follows the monthly/summary toggle", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(
      createSpreadReadoutClient({ withDecomposition: false }),
    );

    await screen.findByTestId("product-category-table");
    const readout = await screen.findByTestId("product-category-spread-readout");
    expect(
      within(readout).getByTestId("product-category-spread-readout-view"),
    ).toHaveTextContent("单月口径");
    expect(
      within(readout).getByTestId(
        "product-category-spread-readout-metric-interest_earning_spread",
      ),
    ).toHaveTextContent("76.0 bp");
    expect(
      within(readout).getByTestId(
        "product-category-spread-readout-metric-interest_spread_with_tpl",
      ),
    ).toHaveTextContent("64.0 bp");
    expect(
      within(readout).getByTestId(
        "product-category-spread-readout-metric-interest_earning_asset_yield",
      ),
    ).toHaveTextContent("2.29%");

    await user.click(screen.getByRole("button", { name: "汇总视图" }));

    await waitFor(() => {
      expect(
        screen.getByTestId(
          "product-category-spread-readout-metric-interest_earning_spread",
        ),
      ).toHaveTextContent("78.0 bp");
    });
    expect(
      screen.getByTestId(
        "product-category-spread-readout-metric-interest_spread_with_tpl",
      ),
    ).toHaveTextContent("93.0 bp");
    expect(
      screen.getByTestId(
        "product-category-spread-readout-metric-asset_yield_with_tpl",
      ),
    ).toHaveTextContent("2.51%");
    expect(
      screen.getByTestId("product-category-spread-readout-view"),
    ).toHaveTextContent("累计口径");
    expect(
      screen.getByTestId("product-category-spread-readout-caliber"),
    ).toHaveTextContent("年初至今累计口径");
  });

  it("hides the CLN drag block behind a gap notice until the backend returns the decomposition", async () => {
    renderWorkbenchAppWithClient(
      createSpreadReadoutClient({ withDecomposition: false }),
    );

    await screen.findByTestId("product-category-table");
    const gap = await screen.findByTestId(
      "product-category-spread-readout-liability-gap",
    );
    expect(gap).toHaveTextContent("后端未返回负债成本拆解字段");
    expect(
      screen.queryByTestId("product-category-spread-readout-liability"),
    ).not.toBeInTheDocument();
    expect(gap).not.toHaveTextContent("NaN");
    expect(gap).not.toHaveTextContent("0.00");
  });

  it("renders the CLN drag block once liability_cost_decomposition is returned", async () => {
    renderWorkbenchAppWithClient(
      createSpreadReadoutClient({ withDecomposition: true }),
    );

    await screen.findByTestId("product-category-table");
    const liability = await screen.findByTestId(
      "product-category-spread-readout-liability",
    );
    expect(
      within(liability).getByTestId(
        "product-category-spread-readout-liability-metric-liability_yield_pct",
      ),
    ).toHaveTextContent("1.58%");
    expect(
      within(liability).getByTestId(
        "product-category-spread-readout-liability-metric-liability_yield_ex_cln_pct",
      ),
    ).toHaveTextContent("1.57%");
    expect(
      within(liability).getByTestId(
        "product-category-spread-readout-liability-metric-cln_drag_bp",
      ),
    ).toHaveTextContent("1.4 bp");
    expect(
      within(liability).getByTestId(
        "product-category-spread-readout-liability-metric-cln_yield_pct",
      ),
    ).toHaveTextContent("规模 19.47 亿元");
    expect(
      screen.queryByTestId("product-category-spread-readout-liability-gap"),
    ).not.toBeInTheDocument();
  });
});
