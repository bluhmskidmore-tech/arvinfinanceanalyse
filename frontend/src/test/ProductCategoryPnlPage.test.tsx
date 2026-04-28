import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ActionRequestError, createApiClient } from "../api/client";
import { PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY } from "../features/product-category-pnl/pages/productCategoryPnlPageModel";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="product-category-echarts-stub">{JSON.stringify(option ?? null)}</div>
  ),
}));

function renderWorkbenchAppWithClient(client: ReturnType<typeof createApiClient>) {
  return renderWorkbenchApp(["/product-category-pnl"], { client });
}

function yuan(yi: number): string {
  return String(yi * 100_000_000);
}

function readChartOption(panelTestId: string) {
  const panel = screen.getByTestId(panelTestId);
  return JSON.parse(
    within(panel).getByTestId("product-category-echarts-stub").textContent ?? "null",
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
      endLabel?: { show?: boolean };
    }>;
  };
}

describe("ProductCategoryPnlPage", () => {
  it("renders the page shell, summary, and table structure", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const table = await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-page-title")).toHaveTextContent("产品分类损益");
    expect(screen.getByTestId("product-category-page-subtitle")).toHaveTextContent(
      "按业务分类查看损益、FTP 和净收入",
    );
    expect(screen.getByTestId("product-category-role-badge")).toHaveTextContent("系统层");
    expect(screen.getByTestId("product-category-boundary-copy")).toHaveTextContent("系统层经营口径");
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
    expect(screen.getByTestId("product-category-as-of-date-gap")).toHaveTextContent(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY);
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
    expect(pnlSpy.mock.calls.some((call) => call[0]!.reportDate === firstDate)).toBe(true);
    expect(pnlSpy.mock.calls.map((call) => call[0]!.reportDate)).toEqual(
      expect.arrayContaining([firstDate, "2026-02-28", "2026-01-31"]),
    );
    expect(pnlSpy.mock.calls[0]![0]).toMatchObject({ view: "monthly" });
    expect(adjSpy.mock.calls.every((call) => call[0] === firstDate)).toBe(true);
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      "/ledger-pnl?report_date=2026-03-31",
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

  it("renders spread movement attribution from current and prior trend snapshots", async () => {
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

    const spread = await screen.findByTestId("product-category-diagnostics-spread");
    await waitFor(() => {
      expect(spread).toHaveTextContent("105bp");
    });
    expect(spread).toHaveTextContent("2026年02月");
    expect(spread).toHaveTextContent("2026年01月");
    expect(spread).toHaveTextContent("+13bp");
    expect(spread).toHaveTextContent("+3bp");
    expect(spread).toHaveTextContent("+10bp");
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
        const envelope = buildMockProductCategoryPnlEnvelope(options);
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
      "当前资产端或负债端收益率缺失，无法计算当期利差。",
    );
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

  it("renders the four requested derived chart panels with chart stubs", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-derived-chart-tpl-scale-yield")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-currency-net-income")).toBeInTheDocument();
    expect(
      screen.getByTestId("product-category-derived-chart-interest-earning-income-scale"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("product-category-derived-chart-interest-spread")).toBeInTheDocument();
    expect(screen.getAllByTestId("product-category-echarts-stub")).toHaveLength(5);
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
        const env = buildMockProductCategoryPnlEnvelope(options);
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

    const spreadOption = readChartOption("product-category-derived-chart-interest-spread");
    expect(spreadOption.legend?.data).toEqual([
      "生息资产收益率（%）",
      "负债端加权收益率（%）",
      "生息资产利差（%）",
    ]);
    expect(spreadOption.series?.map((series) => series.name)).toEqual([
      "生息资产收益率（%）",
      "负债端加权收益率（%）",
      "生息资产利差（%）",
    ]);
    expect(spreadOption.series?.[0]?.data).toEqual([2.35, 2.4]);
    expect(spreadOption.series?.[1]?.data).toEqual([1.58, 1.63]);
    expect(spreadOption.series?.[2]?.data).toEqual([0.77, 0.77]);

    const liabilityOption = readChartOption("product-category-liability-side-trend");
    expect(liabilityOption.legend?.data).toEqual([
      "负债端日均额（亿元）",
      "负债端利率（%）",
    ]);
    expect(liabilityOption.xAxis).toMatchObject({ data: ["2026年01月", "2026年02月"] });
    expect(screen.getByTestId("product-category-liability-side-detail-credit_linked_notes")).toBeInTheDocument();
  });

  it("makes the interest spread trend visually prominent without clipping out-of-band values", async () => {
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

    await screen.findByTestId("product-category-derived-chart-interest-spread");

    const spreadOption = readChartOption("product-category-derived-chart-interest-spread");
    expect(spreadOption.yAxis).toMatchObject({ scale: true });
    const yAxis = Array.isArray(spreadOption.yAxis) ? spreadOption.yAxis[0] : spreadOption.yAxis;
    const plottedValues = (spreadOption.series ?? []).flatMap((series) =>
      Array.isArray(series.data) ? series.data.filter((value): value is number => typeof value === "number") : [],
    );
    expect(yAxis?.min).toBeLessThanOrEqual(Math.min(...plottedValues));
    expect(yAxis?.max).toBeGreaterThanOrEqual(Math.max(...plottedValues));
    expect(spreadOption.series?.map((series) => series.lineStyle?.width)).toEqual([4, 3.4, 4]);
    expect(spreadOption.series?.map((series) => series.symbolSize)).toEqual([8, 7, 8]);
    expect(spreadOption.series?.every((series) => series.endLabel?.show)).toBe(true);
  });

  it("builds derived charts on 2025 quarter-end points, 2025 Nov-Dec, and 2026 Jan-Mar with one view basis", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getProductCategoryPnl = vi.fn(async (options: Parameters<typeof baseClient.getProductCategoryPnl>[0]) =>
      buildMockProductCategoryPnlEnvelope(options),
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
      expect(getProductCategoryPnl).toHaveBeenCalledTimes(8);
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
      "2025-11-30:monthly",
      "2025-12-31:monthly",
      "2026-01-31:monthly",
      "2026-02-28:monthly",
    ]);

    getProductCategoryPnl.mockClear();
    const viewButtons = within(screen.getByRole("group", { name: "视图模式" })).getAllByRole("button");
    await user.click(viewButtons[1]!);
    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledTimes(8);
    });
    const ytdCalls = getProductCategoryPnl.mock.calls
      .map((call) => call[0])
      .map((options) => `${options.reportDate}:${options.view}`)
      .sort();
    expect(ytdCalls).toEqual([
      "2025-03-31:ytd",
      "2025-06-30:ytd",
      "2025-09-30:ytd",
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
            rows: env.result.rows.map((r) =>
              r.category_id === "repo_assets"
                ? {
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
                  }
                : r,
            ),
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

    const formalTableTitle = await screen.findByText("产品类别损益分析表（单位：亿元）");
    const formalSection = formalTableTitle.closest("section");
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
        "scenario",
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
        "scenario",
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

    await user.click(screen.getByTestId("product-category-revoke-pca-existing-1"));

    await waitFor(() => {
      expect(revokeSpy).toHaveBeenCalledWith("pca-existing-1");
      expect(refreshSpy).toHaveBeenCalledTimes(1);
    });
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
