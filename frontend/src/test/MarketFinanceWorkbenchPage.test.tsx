import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientProvider,
  createApiClient,
  type ApiClient,
  type DataSourceMode,
} from "../api/client";
import type {
  ChoiceMacroLatestPoint,
  ResultMeta,
} from "../api/contracts";
import MarketFinanceWorkbenchPage from "../features/market-finance/pages/MarketFinanceWorkbenchPage";

function renderPage(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: {
              retry: false,
              staleTime: 0,
              refetchOnWindowFocus: false,
            },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <MemoryRouter>
        <MarketFinanceWorkbenchPage />
      </MemoryRouter>
    </Wrapper>,
  );
}

function resultMeta(
  resultKind: string,
  partial: Partial<ResultMeta> = {},
): ResultMeta {
  return {
    trace_id: `trace_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: `source_${resultKind}`,
    vendor_version: `vendor_${resultKind}`,
    rule_version: `rule_${resultKind}`,
    cache_version: `cache_${resultKind}`,
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-07-20T08:00:00Z",
    ...partial,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

type QueryState = "success" | "empty" | "error";

type ControlledClientOptions = {
  mode?: DataSourceMode;
  marketState?: QueryState;
  productDatesState?: QueryState;
  productPnlState?: Exclude<QueryState, "empty">;
  balanceDatesState?: QueryState;
  balanceOverviewState?: Exclude<QueryState, "empty">;
  decisionItemsState?: QueryState;
  marketMeta?: Partial<ResultMeta> | null;
  productDatesMeta?: Partial<ResultMeta> | null;
  productPnlMeta?: Partial<ResultMeta> | null;
  balanceDatesMeta?: Partial<ResultMeta> | null;
  balanceOverviewMeta?: Partial<ResultMeta> | null;
  decisionItemsMeta?: Partial<ResultMeta> | null;
  marketSeries?: ChoiceMacroLatestPoint[];
};

function point(
  partial: Partial<ChoiceMacroLatestPoint> = {},
): ChoiceMacroLatestPoint {
  return {
    series_id: "UNCONFIRMED.001",
    series_name: "未确认测试序列",
    trade_date: "2026-06-29",
    value_numeric: 9.99,
    unit: "%",
    source_version: "sv_unconfirmed",
    vendor_version: "vv_unconfirmed",
    quality_flag: "ok",
    ...partial,
  };
}

function resolvedMeta(
  resultKind: string,
  partial: Partial<ResultMeta> | null | undefined,
  defaults: Partial<ResultMeta> = {},
): ResultMeta {
  if (partial === null) {
    return undefined as unknown as ResultMeta;
  }
  return resultMeta(resultKind, {
    ...defaults,
    ...partial,
  });
}

function createControlledClient(
  options: ControlledClientOptions = {},
): ApiClient {
  const base = createApiClient({ mode: "mock" });
  const marketState = options.marketState ?? "success";
  const productDatesState = options.productDatesState ?? "success";
  const productPnlState = options.productPnlState ?? "success";
  const balanceDatesState = options.balanceDatesState ?? "success";
  const balanceOverviewState = options.balanceOverviewState ?? "success";
  const decisionItemsState = options.decisionItemsState ?? "success";

  return {
    ...base,
    mode: options.mode ?? "real",
    getMarketDataRates: vi.fn(async () => {
      if (marketState === "error") {
        throw new Error("market rates unavailable");
      }
      return {
        result_meta: resolvedMeta(
          "market_data.rates",
          options.marketMeta,
          { as_of_date: "2026-06-30" },
        ),
        result: {
          read_target: "duckdb" as const,
          series:
            marketState === "empty"
              ? []
              : (options.marketSeries ?? [point()]),
        },
      };
    }),
    getProductCategoryDates: vi.fn(async () => {
      if (productDatesState === "error") {
        throw new Error("product dates unavailable");
      }
      return {
        result_meta: resolvedMeta(
          "product_category_pnl.dates",
          options.productDatesMeta,
        ),
        result: {
          report_dates:
            productDatesState === "empty" ? [] : ["2026-02-28"],
        },
      };
    }),
    getProductCategoryPnl: vi.fn(async (request) => {
      if (productPnlState === "error") {
        throw new Error("product pnl unavailable");
      }
      const envelope = await base.getProductCategoryPnl(request);
      return {
        ...envelope,
        result_meta: resolvedMeta(
          "product_category_pnl.read",
          options.productPnlMeta,
        ),
        result: {
          ...envelope.result,
          report_date: request.reportDate,
          asset_total: {
            ...envelope.result.asset_total,
            baseline_ftp_rate_pct: "1.91",
          },
          grand_total: {
            ...envelope.result.grand_total,
            business_net_income: "250000000",
          },
        },
      };
    }),
    getBalanceAnalysisDates: vi.fn(async () => {
      if (balanceDatesState === "error") {
        throw new Error("balance dates unavailable");
      }
      return {
        result_meta: resolvedMeta(
          "balance_analysis.dates",
          options.balanceDatesMeta,
        ),
        result: {
          report_dates:
            balanceDatesState === "empty" ? [] : ["2025-12-31"],
        },
      };
    }),
    getBalanceAnalysisOverview: vi.fn(async (request) => {
      if (balanceOverviewState === "error") {
        throw new Error("balance overview unavailable");
      }
      const envelope = await base.getBalanceAnalysisOverview(request);
      return {
        ...envelope,
        result_meta: resolvedMeta(
          "balance_analysis.overview",
          options.balanceOverviewMeta,
        ),
        result: {
          ...envelope.result,
          report_date: request.reportDate,
          asset_total_market_value_amount: "12300000000",
          liability_total_market_value_amount: "9800000000",
        },
      };
    }),
    getBalanceAnalysisDecisionItems: vi.fn(async (request) => {
      if (decisionItemsState === "error") {
        throw new Error("decision items unavailable");
      }
      const envelope = await base.getBalanceAnalysisDecisionItems(request);
      return {
        ...envelope,
        result_meta: resolvedMeta(
          "balance_analysis.decision_items",
          options.decisionItemsMeta,
        ),
        result: {
          ...envelope.result,
          report_date: request.reportDate,
          rows:
            decisionItemsState === "empty" ? [] : envelope.result.rows,
        },
      };
    }),
  };
}

function metricValue(testId: string): HTMLElement {
  const value = screen
    .getByTestId(testId)
    .querySelector<HTMLElement>(".moss-page-v2-kpi-metric__value");
  if (!value) {
    throw new Error(`missing metric value for ${testId}`);
  }
  return value;
}

function expectMissingMetric(testId: string) {
  const value = metricValue(testId);
  expect(value.textContent?.trim()).toBe("—");
  expect(
    value.querySelector(".market-finance-workbench__metric-unit"),
  ).toBeNull();
}

function expectMetric(testId: string, expectedValue: string, unit: string) {
  const value = metricValue(testId);
  expect(value).toHaveTextContent(expectedValue);
  expect(
    value.querySelector(".market-finance-workbench__metric-unit"),
  ).toHaveTextContent(unit);
}

describe("MarketFinanceWorkbenchPage", () => {
  it("shows only approved formal market representatives as business evidence", async () => {
    renderPage(
      createControlledClient({
        marketSeries: [
          point({
            series_id: "CA.CN_GOV_10Y",
            series_name: "中国国债10年",
            value_numeric: 1.75,
            latest_change: 0.01,
          }),
          point({
            series_id: "CA.DR007",
            series_name: "DR007",
            value_numeric: 1.8,
            latest_change: -0.001,
          }),
          point({
            series_id: "CA.USDCNY",
            series_name: "美元兑人民币",
            value_numeric: 7.14,
            unit: "index",
            latest_change: 0.01,
          }),
          point({
            series_id: "CN_CREDIT_AAA_1Y",
            series_name: "中短票AAA信用利差",
            value_numeric: 25,
            unit: "bp",
            latest_change: -1,
          }),
          point(),
        ],
      }),
    );

    const marketKpi = await screen.findByTestId(
      "market-finance-kpi-market",
    );
    await waitFor(() => {
      expect(marketKpi).toHaveTextContent("10年国债");
      expect(metricValue("market-finance-kpi-market")).toHaveTextContent(
        "1.75%",
      );
    });
    expect(marketKpi).toHaveTextContent("+1bp");
    expect(marketKpi).toHaveTextContent("2026-06-29");
    expect(marketKpi).not.toHaveTextContent("9.99");

    const marketNode = screen.getByTestId("market-finance-spine-market");
    expect(marketNode).toHaveTextContent("DR007 1.8%");
    expect(marketNode).toHaveTextContent("人民币汇率 7.14");
    expect(marketNode).toHaveTextContent("信用利差 中短票AAA 25bp");

    const ratesRow = within(
      screen.getByTestId("market-finance-evidence-matrix"),
    ).getByRole("row", { name: /利率 \/ 资金/ });
    expect(ratesRow).toHaveTextContent("10年国债 1.75%");
    expect(ratesRow).toHaveTextContent("DR007 1.8%");
    expect(ratesRow).not.toHaveTextContent("9.99");
  });

  it("keeps an unconfirmed first market series out of business KPIs", async () => {
    renderPage(createControlledClient());

    expect(
      await screen.findByRole("heading", { name: "金市与计财协同台" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("当前市场变化如何影响资金成本、资产负债与经营结果？"),
    ).toBeInTheDocument();

    const root = screen.getByTestId("market-finance-workbench");
    expect(root.querySelector(".market-finance-workbench.theme-dh-api")).not.toBeNull();
    expect(root.querySelector("main")).toBeNull();
    expect(
      screen.getByRole("group", { name: "当前观察范围" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", {
        name: "市场信号与财务约束对照表",
      }),
    ).toHaveAttribute("tabindex", "0");
    const statusStrip = screen.getByTestId("market-finance-data-status");
    await waitFor(() => {
      expect(statusStrip).toHaveTextContent("市场数据日");
      expect(statusStrip).toHaveTextContent("2026-06-30");
      expect(statusStrip).toHaveTextContent("经营 2026-02-28");
      expect(statusStrip).toHaveTextContent("资产负债 2025-12-31");
      expect(statusStrip).toHaveTextContent("真实模式");
    });

    const spine = screen.getByTestId("market-finance-transmission-spine");
    for (const node of [
      "市场变化",
      "资金 / FTP",
      "ALM 约束",
      "损益 / 资本",
      "管理动作",
    ]) {
      expect(within(spine).getByText(node)).toBeInTheDocument();
    }

    expect(
      within(screen.getByTestId("market-finance-kpi-market")).getByText(
        "10年国债",
      ),
    ).toBeInTheDocument();
    await waitFor(() => {
      expectMissingMetric("market-finance-kpi-market");
      expectMetric("market-finance-kpi-ftp", "1.91", "%");
      expectMetric("market-finance-kpi-net-income", "2.50", "亿元");
      expectMetric("market-finance-kpi-asset-market-value", "123.00", "亿元");
    });
    expect(
      metricValue("market-finance-kpi-market").querySelector(
        ".market-finance-workbench__metric-unit",
      ),
    ).toBeNull();
    expect(root).not.toHaveTextContent("9.99");
    expect(root).not.toHaveTextContent("未确认测试序列");

    const evidence = screen.getByTestId("market-finance-evidence");
    expect(evidence).toHaveTextContent("页面配置白名单");
    expect(evidence).toHaveTextContent("PAGE contract");
    expect(evidence).toHaveTextContent("owner signoff");
    for (const query of [
      "market-rates",
      "product-dates",
      "product-pnl",
      "balance-dates",
      "balance-overview",
    ]) {
      expect(
        screen.getByTestId(`market-finance-query-status-${query}`),
      ).toHaveTextContent("已有证据");
    }
    const healthyFlags = screen.getByTestId(
      "market-finance-degradation-flags",
    );
    expect(healthyFlags).toHaveTextContent("未检测到降级");
    expect(healthyFlags).not.toHaveTextContent("部分证据");

    const matrix = screen.getByTestId("market-finance-evidence-matrix");
    for (const row of ["利率 / 资金", "FTP", "ALM", "OCI / 损益", "资本 / RWA"]) {
      expect(within(matrix).getByText(row)).toBeInTheDocument();
    }
    const capitalRow = within(matrix).getByRole("row", {
      name: /资本 \/ RWA/,
    });
    expect(within(capitalRow).queryByRole("link")).not.toBeInTheDocument();
    expect(capitalRow).toHaveTextContent("暂无证据入口");
    expect(
      root.querySelector('[title="capital-rwa-evidence-pending"]'),
    ).toBeNull();

    for (const endpoint of [
      "/ui/market-data/rates",
      "/ui/pnl/product-category",
      "/ui/balance-analysis/overview",
    ]) {
      const endpointCode = within(evidence).getByText(endpoint, {
        selector: "code",
      });
      expect(endpointCode).toBeInTheDocument();
      for (const titledElement of root.querySelectorAll(
        `[title="${endpoint}"]`,
      )) {
        expect(evidence).toContainElement(titledElement as HTMLElement);
      }
    }
  });

  it("shows a missing marker for every unfilled market representative slot", async () => {
    renderPage(
      createControlledClient({
        marketSeries: [
          point({
            series_id: "CA.CN_GOV_10Y",
            value_numeric: 1.75,
          }),
          point({
            series_id: "CA.USDCNY",
            value_numeric: 7.14,
            unit: "index",
          }),
          point(),
        ],
      }),
    );

    const root = await screen.findByTestId("market-finance-workbench");
    const marketNode = screen.getByTestId("market-finance-spine-market");
    await waitFor(() => {
      expect(marketNode).toHaveTextContent("10年国债 1.75%");
      expect(marketNode).toHaveTextContent("DR007 —");
      expect(marketNode).toHaveTextContent("人民币汇率 7.14");
      expect(marketNode).toHaveTextContent("信用利差 中短票AAA —");
      expect(marketNode).toHaveTextContent("待复核");
    });
    expect(root).not.toHaveTextContent("9.99");
    expect(root).not.toHaveTextContent("未确认测试序列");

    const ratesRow = within(
      screen.getByTestId("market-finance-evidence-matrix"),
    ).getByRole("row", { name: /利率 \/ 资金/ });
    expect(ratesRow).toHaveTextContent("DR007 —");
    expect(ratesRow).toHaveTextContent("信用利差 中短票AAA —");
  });

  it("renders pending decision items from the governed read endpoint", async () => {
    renderPage(createControlledClient());

    const panel = await screen.findByTestId(
      "market-finance-decision-items",
    );
    await waitFor(() => {
      expect(panel).toHaveTextContent("报告日 2025-12-31");
      expect(panel).toHaveTextContent("复核 1-2 年期限缺口配置");
      expect(panel).toHaveTextContent("复核缺口");
    });
    expect(panel).not.toHaveTextContent("对齐观察日期");
    expect(
      within(panel).getByRole("link", { name: "复核缺口" }),
    ).toHaveAttribute("href", "/decision-items");
  });

  it("shows a local empty state when no pending decision item exists", async () => {
    renderPage(
      createControlledClient({
        decisionItemsState: "empty",
      }),
    );

    const state = await screen.findByTestId(
      "market-finance-decision-items-state",
    );
    await waitFor(() => {
      expect(state).toHaveTextContent("暂无待协调事项");
    });
    expect(state).not.toHaveTextContent("查询失败");
    await waitFor(() => {
      expectMetric("market-finance-kpi-ftp", "1.91", "%");
    });
  });

  it("keeps financial KPIs visible when decision items fail locally", async () => {
    renderPage(
      createControlledClient({
        decisionItemsState: "error",
      }),
    );

    const state = await screen.findByTestId(
      "market-finance-decision-items-state",
    );
    await waitFor(() => {
      expect(state).toHaveTextContent("待协调事项读取失败");
    });
    expect(
      screen.getByRole("button", { name: "重新读取待办" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expectMetric("market-finance-kpi-net-income", "2.50", "亿元");
      expectMetric("market-finance-kpi-asset-market-value", "123.00", "亿元");
    });
  });

  it("surfaces stale, vendor-stale and fallback flags together with raw meta dates", async () => {
    renderPage(
      createControlledClient({
        marketMeta: {
          quality_flag: "stale",
          fallback_mode: "latest_snapshot",
          as_of_date: "2026-06-28",
          requested_report_date: "2026-06-30",
          resolved_report_date: "2026-06-28",
          fallback_date: "2026-06-28",
        },
        productPnlMeta: {
          vendor_status: "vendor_stale",
        },
      }),
    );

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("数据陈旧");
      expect(flags).toHaveTextContent("供应商陈旧");
      expect(flags).toHaveTextContent("使用回退");
      expect(flags).toHaveTextContent("部分证据");
    });
    expect(
      screen.getByTestId("market-finance-state-surface"),
    ).toHaveAttribute("data-state-variant", "stale");

    const marketStatus = screen.getByTestId(
      "market-finance-query-status-market-rates",
    );
    expect(marketStatus).toHaveTextContent("数据陈旧");
    expect(marketStatus).toHaveTextContent("使用回退");
    expect(marketStatus).not.toHaveTextContent("已有证据");

    const evidence = screen.getByTestId("market-finance-evidence");
    expect(evidence).toHaveTextContent("请求日 2026-06-30");
    expect(evidence).toHaveTextContent("解析日 2026-06-28");
    expect(evidence).toHaveTextContent("回退日 2026-06-28");
    expect(evidence).toHaveTextContent("数据日 2026-06-28");
  });

  it("uses the fallback-date state for a pure fallback response", async () => {
    renderPage(
      createControlledClient({
        marketMeta: {
          fallback_mode: "latest_snapshot",
          as_of_date: "2026-06-29",
          requested_report_date: "2026-06-30",
          resolved_report_date: "2026-06-29",
          fallback_date: "2026-06-29",
        },
      }),
    );

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("使用回退");
      expect(flags).toHaveTextContent("部分证据");
    });
    const stateSurface = screen.getByTestId(
      "market-finance-state-surface",
    );
    expect(stateSurface).toHaveAttribute(
      "data-state-variant",
      "fallback-date",
    );
    expect(stateSurface).toHaveTextContent("使用回退快照");
    expect(stateSurface).not.toHaveTextContent("查询失败");
  });

  it("derives warning, error, missing, vendor-unavailable and formal-use states per query", async () => {
    renderPage(
      createControlledClient({
        marketMeta: {
          quality_flag: "error",
          formal_use_allowed: false,
        },
        productDatesMeta: {
          quality_flag: "warning",
        },
        productPnlMeta: {
          quality_flag: "missing",
        },
        balanceOverviewMeta: {
          vendor_status: "vendor_unavailable",
        },
      }),
    );

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("质量错误");
      expect(flags).toHaveTextContent("不可用于正式口径");
      expect(flags).toHaveTextContent("质量预警");
      expect(flags).toHaveTextContent("数据缺失");
      expect(flags).toHaveTextContent("供应商不可用");
      expect(flags).toHaveTextContent("数据质量阻断");
      expect(flags).not.toHaveTextContent("查询失败");
      expect(flags).not.toHaveTextContent("部分证据");
    });

    const stateSurface = screen.getByTestId(
      "market-finance-state-surface",
    );
    expect(stateSurface).toHaveTextContent("数据质量阻断");
    expect(stateSurface).toHaveTextContent(
      "响应已返回但不可用于判断",
    );
    expect(stateSurface).not.toHaveTextContent("查询失败");
    expect(stateSurface).not.toHaveTextContent("失败链路");
    expect(
      screen.queryByRole("button", { name: "重新读取" }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByTestId("market-finance-query-status-market-rates"),
    ).toHaveTextContent("质量错误");
    expect(
      screen.getByTestId("market-finance-query-status-product-dates"),
    ).toHaveTextContent("质量预警");
    expect(
      screen.getByTestId("market-finance-query-status-product-pnl"),
    ).toHaveTextContent("数据缺失");
    expect(
      screen.getByTestId("market-finance-query-status-balance-overview"),
    ).toHaveTextContent("供应商不可用");

    await waitFor(() => {
      expectMissingMetric("market-finance-kpi-market");
      expectMissingMetric("market-finance-kpi-ftp");
      expectMissingMetric("market-finance-kpi-net-income");
      expectMissingMetric("market-finance-kpi-asset-market-value");
    });
  });

  it("treats empty responses with blocking metadata as quality blocks", async () => {
    const client = createControlledClient({
      marketState: "empty",
      marketMeta: {
        quality_flag: "error",
      },
      productDatesState: "empty",
      productDatesMeta: {
        vendor_status: "vendor_unavailable",
      },
    });
    renderPage(client);

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("质量错误");
      expect(flags).toHaveTextContent("供应商不可用");
      expect(flags).toHaveTextContent("数据质量阻断");
      expect(flags).toHaveTextContent("部分证据");
    });

    const marketStatus = screen.getByTestId(
      "market-finance-query-status-market-rates",
    );
    expect(marketStatus).toHaveTextContent("质量错误");
    expect(marketStatus).not.toHaveTextContent("无数据");
    const productDatesStatus = screen.getByTestId(
      "market-finance-query-status-product-dates",
    );
    expect(productDatesStatus).toHaveTextContent("供应商不可用");
    expect(productDatesStatus).not.toHaveTextContent("无数据");
    expect(
      screen.getByTestId("market-finance-query-status-product-pnl"),
    ).toHaveTextContent("未执行：日期目录受质量阻断");
    expect(
      screen.getByTestId("market-finance-state-surface"),
    ).toHaveTextContent("数据质量阻断");
    expect(client.getProductCategoryPnl).not.toHaveBeenCalled();
  });

  it("keeps dependent detail queries idle while the date catalog is loading", async () => {
    const seed = createControlledClient();
    const dateEnvelope = await seed.getProductCategoryDates();
    const pendingDates = deferred<typeof dateEnvelope>();
    const getProductCategoryPnl = vi.fn(
      seed.getProductCategoryPnl,
    );
    const client: ApiClient = {
      ...seed,
      getProductCategoryDates: vi.fn(() => pendingDates.promise),
      getProductCategoryPnl,
    };

    renderPage(client);

    expect(
      await screen.findByTestId(
        "market-finance-query-status-product-dates",
      ),
    ).toHaveTextContent("加载中");
    const detailStatus = screen.getByTestId(
      "market-finance-query-status-product-pnl",
    );
    expect(detailStatus).toHaveTextContent("等待日期目录");
    expect(detailStatus).not.toHaveTextContent("无数据");
    expect(getProductCategoryPnl).not.toHaveBeenCalled();

    await act(async () => {
      pendingDates.resolve(dateEnvelope);
    });
    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledTimes(1);
    });
  });

  it("blocks an otherwise populated query when result metadata is missing", async () => {
    renderPage(
      createControlledClient({
        balanceOverviewMeta: null,
      }),
    );

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("元信息缺失");
      expect(
        screen.getByTestId(
          "market-finance-query-status-balance-overview",
        ),
      ).toHaveTextContent("元信息缺失");
      expectMissingMetric("market-finance-kpi-asset-market-value");
    });
  });

  it("marks mock responses as review evidence instead of healthy evidence", async () => {
    renderPage(createControlledClient({ mode: "mock" }));

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("演示模式");
    });
    await waitFor(() => {
      for (const query of [
        "market-rates",
        "product-dates",
        "product-pnl",
        "balance-dates",
        "balance-overview",
      ]) {
        const queryStatus = screen.getByTestId(
          `market-finance-query-status-${query}`,
        );
        expect(queryStatus).toHaveTextContent("演示模式");
        expect(queryStatus).not.toHaveTextContent("已有证据");
      }
    });
  });

  it("keeps successful financial KPIs visible when the market query fails", async () => {
    renderPage(
      createControlledClient({
        marketState: "error",
      }),
    );

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("查询失败");
      expect(flags).toHaveTextContent("部分证据");
      expectMissingMetric("market-finance-kpi-market");
      expectMetric("market-finance-kpi-ftp", "1.91", "%");
      expectMetric("market-finance-kpi-net-income", "2.50", "亿元");
      expectMetric("market-finance-kpi-asset-market-value", "123.00", "亿元");
    });
    const stateSurface = screen.getByTestId(
      "market-finance-state-surface",
    );
    expect(stateSurface).toHaveTextContent("部分查询异常");
    expect(stateSurface).not.toHaveTextContent("数据质量阻断");
    expect(stateSurface).not.toHaveTextContent("失败链路");
  });

  it("shows query and metadata blocks as separate concurrent states", async () => {
    renderPage(
      createControlledClient({
        marketState: "error",
        balanceOverviewMeta: {
          vendor_status: "vendor_unavailable",
        },
      }),
    );

    const flags = await screen.findByTestId(
      "market-finance-degradation-flags",
    );
    await waitFor(() => {
      expect(flags).toHaveTextContent("查询失败");
      expect(flags).toHaveTextContent("数据质量阻断");
      expect(flags).toHaveTextContent("供应商不可用");
      expect(flags).toHaveTextContent("部分证据");
    });
    const stateSurface = screen.getByTestId(
      "market-finance-state-surface",
    );
    expect(stateSurface).toHaveTextContent(
      "查询异常与数据质量阻断",
    );
    expect(stateSurface).toHaveTextContent("部分请求未完成");
    expect(stateSurface).toHaveTextContent(
      "响应已返回但不可用于判断",
    );
    expect(stateSurface).not.toHaveTextContent("失败链路");
  });

  it("retries only failed child or independent query paths", async () => {
    const user = userEvent.setup();
    const client = createControlledClient({
      marketState: "error",
      productPnlState: "error",
    });
    renderPage(client);

    const retryButton = await screen.findByRole("button", {
      name: "重新读取",
    });
    await waitFor(() => {
      expect(client.getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(client.getProductCategoryDates).toHaveBeenCalledTimes(1);
      expect(client.getProductCategoryPnl).toHaveBeenCalledTimes(1);
      expect(client.getBalanceAnalysisDates).toHaveBeenCalledTimes(1);
      expect(client.getBalanceAnalysisOverview).toHaveBeenCalledTimes(
        1,
      );
    });

    await user.click(retryButton);
    await waitFor(() => {
      expect(client.getMarketDataRates).toHaveBeenCalledTimes(2);
      expect(client.getProductCategoryPnl).toHaveBeenCalledTimes(2);
    });
    expect(client.getProductCategoryDates).toHaveBeenCalledTimes(1);
    expect(client.getBalanceAnalysisDates).toHaveBeenCalledTimes(1);
    expect(client.getBalanceAnalysisOverview).toHaveBeenCalledTimes(1);
  });

  it("retries a failed parent date catalog before any dependent detail query", async () => {
    const user = userEvent.setup();
    const client = createControlledClient({
      productDatesState: "error",
    });
    renderPage(client);

    const retryButton = await screen.findByRole("button", {
      name: "重新读取",
    });
    await waitFor(() => {
      expect(client.getProductCategoryDates).toHaveBeenCalledTimes(1);
      expect(client.getProductCategoryPnl).not.toHaveBeenCalled();
    });

    await user.click(retryButton);
    await waitFor(() => {
      expect(client.getProductCategoryDates).toHaveBeenCalledTimes(2);
    });
    expect(client.getProductCategoryPnl).not.toHaveBeenCalled();
    expect(client.getMarketDataRates).toHaveBeenCalledTimes(1);
    expect(client.getBalanceAnalysisDates).toHaveBeenCalledTimes(1);
    expect(client.getBalanceAnalysisOverview).toHaveBeenCalledTimes(1);
  });

  it("disables retry while a selected path is fetching", async () => {
    const user = userEvent.setup();
    const seed = createControlledClient();
    const healthyMarket = await seed.getMarketDataRates();
    const retryResult = deferred<typeof healthyMarket>();
    let marketCallCount = 0;
    const getMarketDataRates = vi.fn(async () => {
      marketCallCount += 1;
      if (marketCallCount === 1) {
        throw new Error("market rates unavailable");
      }
      return retryResult.promise;
    });
    const client: ApiClient = {
      ...seed,
      getMarketDataRates,
    };
    renderPage(client);

    const retryButton = await screen.findByRole("button", {
      name: "重新读取",
    });
    expect(retryButton).toBeEnabled();
    await user.click(retryButton);
    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(2);
      expect(retryButton).toBeDisabled();
      expect(retryButton).toHaveTextContent("读取中");
    });

    await act(async () => {
      retryResult.resolve(healthyMarket);
    });
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "重新读取" }),
      ).not.toBeInTheDocument();
    });
  });

  it("renders every KPI as a unitless dash without a partial marker when all queries fail", async () => {
    const client = createControlledClient({
      marketState: "error",
      productDatesState: "error",
      balanceDatesState: "error",
    });
    renderPage(client);

    expect(
      (await screen.findAllByText("数据查询失败")).length,
    ).toBeGreaterThanOrEqual(1);
    await waitFor(() => {
      expectMissingMetric("market-finance-kpi-market");
      expectMissingMetric("market-finance-kpi-ftp");
      expectMissingMetric("market-finance-kpi-net-income");
      expectMissingMetric("market-finance-kpi-asset-market-value");
    });
    const flags = screen.getByTestId(
      "market-finance-degradation-flags",
    );
    expect(flags).toHaveTextContent("查询失败");
    expect(flags).not.toHaveTextContent("部分证据");
    const marketNode = screen.getByTestId("market-finance-spine-market");
    expect(marketNode).toHaveTextContent("查询失败");
    expect(marketNode).toHaveTextContent("暂无可核验代表序列");
    expect(marketNode).not.toHaveTextContent(
      "页面配置白名单暂无命中代表序列",
    );
    expect(
      screen.getByTestId("market-finance-query-status-product-pnl"),
    ).toHaveTextContent("未执行：日期目录查询异常");
    expect(
      screen.getByTestId(
        "market-finance-query-status-balance-overview",
      ),
    ).toHaveTextContent("未执行：日期目录查询异常");
    expect(client.getProductCategoryPnl).not.toHaveBeenCalled();
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
  });

  it("shows a non-contradictory empty state when every source is empty", async () => {
    const client = createControlledClient({
      marketState: "empty",
      productDatesState: "empty",
      balanceDatesState: "empty",
    });
    renderPage(client);

    const stateSurface = await screen.findByTestId(
      "market-finance-state-surface",
    );
    await waitFor(() => {
      expect(stateSurface).toHaveTextContent("暂无可核验数据");
      expectMissingMetric("market-finance-kpi-market");
      expectMissingMetric("market-finance-kpi-ftp");
      expectMissingMetric("market-finance-kpi-net-income");
      expectMissingMetric("market-finance-kpi-asset-market-value");
    });
    const flags = screen.getByTestId(
      "market-finance-degradation-flags",
    );
    expect(flags).toHaveTextContent("无数据");
    expect(flags).not.toHaveTextContent("查询失败");
    expect(flags).not.toHaveTextContent("部分证据");
    const marketNode = screen.getByTestId("market-finance-spine-market");
    expect(marketNode).toHaveTextContent("无数据");
    expect(marketNode).toHaveTextContent("暂无可核验代表序列");
    expect(marketNode).not.toHaveTextContent(
      "页面配置白名单暂无命中代表序列",
    );
    expect(
      screen.getByTestId("market-finance-query-status-product-pnl"),
    ).toHaveTextContent("未执行：日期目录为空");
    expect(
      screen.getByTestId(
        "market-finance-query-status-balance-overview",
      ),
    ).toHaveTextContent("未执行：日期目录为空");
    expect(client.getProductCategoryPnl).not.toHaveBeenCalled();
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
  });
});
