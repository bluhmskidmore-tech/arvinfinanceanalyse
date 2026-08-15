import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="bond-analytics-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { BondAnalyticsView } from "../features/bond-analytics/components/BondAnalyticsView";

function renderBondAnalyticsView(client?: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <MemoryRouter initialEntries={["/bond-analysis"]}>
      <ApiClientProvider client={client ?? createApiClient({ mode: "mock" })}>
        <QueryClientProvider client={queryClient}>
          <BondAnalyticsView />
        </QueryClientProvider>
      </ApiClientProvider>
    </MemoryRouter>,
  );
}

const BOND_ANALYTICS_FIND_TIMEOUT = 20000;

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.action_attribution",
    formal_use_allowed: true,
    source_version: "sv_demo",
    vendor_version: "vv_demo",
    rule_version: "rv_demo",
    cache_version: "cv_demo",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

function createReturnDecompositionResult() {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    carry: "0",
    roll_down: "0",
    rate_effect: "0",
    spread_effect: "0",
    trading: "0",
    fx_effect: "0",
    convexity_effect: "0",
    explained_pnl: "0",
    explained_pnl_accounting: "0",
    explained_pnl_economic: "0",
    oci_reserve_impact: "0",
    actual_pnl: "0",
    recon_error: "0",
    recon_error_pct: "0",
    by_asset_class: [],
    by_accounting_class: [],
    bond_details: [],
    bond_count: 0,
    total_market_value: "0",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
  };
}

function createActionAttributionResult(overrides: Record<string, unknown> = {}) {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    total_actions: 0,
    total_pnl_from_actions: "0",
    by_action_type: [],
    action_details: [],
    period_start_duration: "3.10",
    period_end_duration: "3.05",
    duration_change_from_actions: "-0.05",
    period_start_dv01: "120000",
    period_end_dv01: "115000",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("BondAnalyticsView", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

      if (url.includes("/api/bond-analytics/return-decomposition")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta({
              result_kind: "bond_analytics.return_decomposition",
            }),
            result: createReturnDecompositionResult(),
          }),
        };
      }

      if (url.includes("/api/bond-analytics/action-attribution")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta({
              quality_flag: "warning",
              fallback_mode: "latest_snapshot",
            }),
            result: createActionAttributionResult({
              warnings: ["DuckDB fact tables not yet populated - returning empty attribution"],
            }),
          }),
        };
      }

      throw new Error(`Unhandled fetch request: ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it(
    "renders a governed cockpit with top-right deferred visibility and non-promoted modules",
    async () => {
    renderBondAnalyticsView();

    expect(
      await screen.findByTestId("bond-analysis-toolbar", {}, { timeout: BOND_ANALYTICS_FIND_TIMEOUT }),
    ).toHaveClass("dashboard-home-toolbar");
    expect(screen.getByRole("heading", { name: "债券分析", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新" })).toHaveTextContent("刷新");
    expect(screen.getByTestId("bond-analysis-detail-drilldown")).not.toHaveAttribute("open");

    expect(
      await screen.findByTestId("bond-analysis-top-cockpit", {}, { timeout: BOND_ANALYTICS_FIND_TIMEOUT }),
    ).toBeInTheDocument();

    const topCockpit = await screen.findByTestId(
      "bond-analysis-top-cockpit",
      {},
      { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
    );
    expect(within(topCockpit).getByTestId("bond-analysis-market-ticker")).toHaveTextContent("10年国债");
    expect(within(topCockpit).getByTestId("bond-analysis-daily-judgment")).toHaveTextContent("核心读面");
    expect(within(topCockpit).getByTestId("bond-analysis-yield-curve-panel")).toHaveTextContent(
      "收益率曲线 / KRD",
    );
    expect(within(topCockpit).getByTestId("bond-analysis-evidence-boundary-panel")).toHaveTextContent("证据边界");
    expect(within(topCockpit).getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("利率证据");
    expect(within(topCockpit).getByTestId("bond-analysis-return-attribution-panel")).toHaveTextContent("收益归因 / DV01 变动证据");
    expect(within(topCockpit).getByTestId("bond-analysis-filter-action-strip")).toBeInTheDocument();
    expect(within(topCockpit).getAllByTestId("bond-analysis-kpi-ribbon")).toHaveLength(1);
    expect(within(topCockpit).getByTestId("bond-analysis-kpi-ribbon")).toHaveTextContent("久期");
    expect(within(topCockpit).getByTestId("bond-analysis-kpi-ribbon")).toHaveTextContent("组合到期收益率");
    expect(within(topCockpit).getByTestId("bond-analysis-kpi-ribbon")).toHaveTextContent("信用债收益率中位数");
    expect(within(topCockpit).getByTestId("bond-analysis-today-focus")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-summary-card")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-asset-structure")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-risk-monitor")).toBeInTheDocument();
    expect(within(topCockpit).getByText("尚未捕获刷新运行。")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-home-open-action-attribution")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-home-open-return-decomposition")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-home-open-credit-spread")).toBeInTheDocument();
    expect(screen.queryByTestId("bond-analysis-detail-section")).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0] instanceof Request ? call[0].url : call[0]).includes(
          "/api/bond-analytics/return-decomposition",
        ),
      ),
    ).toBe(false);
    },
    20_000,
  );

  it(
    "renders the bond analysis workstation sections from the reference",
    async () => {
      renderBondAnalyticsView();

      const topCockpit = await screen.findByTestId(
        "bond-analysis-top-cockpit",
        {},
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      );

      expect(within(topCockpit).getAllByTestId("bond-analysis-kpi-ribbon")).toHaveLength(1);
      expect(within(topCockpit).getByTestId("bond-analysis-summary-card")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-asset-structure")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-market-ticker")).toHaveTextContent("DR007");
      expect(within(topCockpit).getByTestId("bond-analysis-daily-judgment")).toHaveTextContent("核心读面");
      expect(within(topCockpit).getByTestId("bond-analysis-yield-curve-panel")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-judgment-matrix")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-return-attribution-panel")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-risk-monitor")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-today-focus")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-currency-basis-banner")).toHaveTextContent(
        "人民币/CNY口径",
      );
    },
    20_000,
  );

  it(
    "places mobile table readouts before the raw bond grids",
    async () => {
      renderBondAnalyticsView();

      const topCockpit = await screen.findByTestId(
        "bond-analysis-top-cockpit",
        {},
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      );

      const accountingSummary = within(topCockpit).getByTestId("bond-analysis-accounting-dv01-summary");
      const accountingReadout = within(accountingSummary).getByTestId(
        "bond-analysis-accounting-dv01-mobile-readout",
      );
      const accountingRawGrid = within(accountingSummary).getByTestId(
        "bond-analysis-accounting-dv01-raw-grid",
      );
      expect(accountingReadout.compareDocumentPosition(accountingRawGrid) & Node.DOCUMENT_POSITION_FOLLOWING)
        .toBeTruthy();
      expect(accountingReadout).toHaveTextContent("会计分类 DV01");
      expect(accountingReadout).toHaveTextContent("最高 DV01 分类");
      expect(accountingReadout).toHaveTextContent("面值加权久期");
      expect(accountingReadout).toHaveTextContent("面值");
      expect(accountingReadout).toHaveTextContent("持仓数");

      const holdingsTable = within(topCockpit).getByTestId("bond-analysis-holdings-table");
      const holdingsReadout = within(holdingsTable).getByTestId("bond-analysis-holdings-mobile-readout");
      const holdingsRawGrid = within(holdingsTable).getByTestId("bond-analysis-holdings-raw-grid");
      expect(holdingsReadout.compareDocumentPosition(holdingsRawGrid) & Node.DOCUMENT_POSITION_FOLLOWING)
        .toBeTruthy();
      expect(holdingsReadout).toHaveTextContent("前十大持仓");
      expect(holdingsReadout).toHaveTextContent("最大持仓");
      expect(holdingsReadout).toHaveTextContent("评级");
      expect(holdingsReadout).toHaveTextContent("市值");
      expect(holdingsReadout).toHaveTextContent("收益率");
      expect(holdingsReadout).toHaveTextContent("久期");
      expect(holdingsReadout).toHaveTextContent("权重");
    },
    20_000,
  );

  it(
    "shows portfolio headlines and top holdings tabs in the analysis detail strip",
    async () => {
      const user = userEvent.setup();
      renderBondAnalyticsView();
      await user.click(
        await screen.findByTestId("bond-analysis-home-open-portfolio-headlines", {}, {
          timeout: BOND_ANALYTICS_FIND_TIMEOUT,
        }),
      );
      const detail = await screen.findByTestId(
        "bond-analysis-detail-section",
        {},
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      );
      expect(detail).toHaveAttribute("data-module-key", "portfolio-headlines");
      expect(within(detail).getByRole("tab", { name: "组合头条" })).toBeInTheDocument();
      expect(within(detail).getByRole("tab", { name: "重仓券" })).toBeInTheDocument();
    },
    20_000,
  );

  it(
    "keeps the homepage stable with controlled fallback copy when action attribution fails",
    async () => {
      const client = createApiClient({ mode: "mock" });
      vi.spyOn(client, "getBondAnalyticsActionAttribution").mockRejectedValue(
        new Error("backend 503 for action attribution"),
      );

      renderBondAnalyticsView(client);

      const topCockpit = await screen.findByTestId(
        "bond-analysis-top-cockpit",
        {},
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      );

      expect(topCockpit).toBeInTheDocument();

      const focus = await within(topCockpit).findByTestId(
        "bond-analysis-today-focus",
        {},
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      );

      await waitFor(
        () => {
          expect(client.getBondAnalyticsActionAttribution).toHaveBeenCalled();
          expect(focus).toHaveTextContent("动作归因不可用");
          expect(within(topCockpit).getByTestId("bond-analysis-decision-rail")).toBeInTheDocument();
        },
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      );
    },
    BOND_ANALYTICS_FIND_TIMEOUT * 2,
  );

  it("keeps the homepage stable when portfolio headlines and top holdings both fail", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async () => {
        throw new Error("backend 503 for portfolio headlines");
      }),
      getBondAnalyticsTopHoldings: vi.fn(async () => {
        throw new Error("backend 503 for top holdings");
      }),
    };

    renderBondAnalyticsView(client);

    const topCockpit = await screen.findByTestId(
      "bond-analysis-top-cockpit",
      {},
      { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
    );

    expect(topCockpit).toBeInTheDocument();

    await waitFor(() => {
      expect(within(topCockpit).queryByText("backend 503 for portfolio headlines")).not.toBeInTheDocument();
      expect(within(topCockpit).queryByText("backend 503 for top holdings")).not.toBeInTheDocument();
      expect(within(topCockpit).queryByText("请求失败")).not.toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-summary-card")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-asset-structure")).toBeInTheDocument();
      expect(within(topCockpit).getByTestId("bond-analysis-today-focus")).toBeInTheDocument();
      expect(within(topCockpit).getByText("持仓明细暂未返回，评级分布稍后补齐。")).toBeInTheDocument();
    });
  });

  it("uses homepage action buttons to drive drill switching", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      if (url.includes("/api/bond-analytics/dates")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta({
              result_kind: "bond_analytics.dates",
            }),
            result: {
              report_dates: ["2026-03-31"],
            },
          }),
        };
      }

      if (url.includes("/api/bond-analytics/return-decomposition")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta({
              result_kind: "bond_analytics.return_decomposition",
            }),
            result: createReturnDecompositionResult(),
          }),
        };
      }

      if (url.includes("/api/bond-analytics/action-attribution")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta(),
            result: createActionAttributionResult({
              total_actions: 4,
              total_pnl_from_actions: "1500000",
              by_action_type: [
                {
                  action_type: "ADD_DURATION",
                  action_type_name: "Add duration",
                  action_count: 4,
                  total_pnl_economic: "1500000",
                  total_pnl_accounting: "1500000",
                  avg_pnl_per_action: "375000",
                },
              ],
            }),
          }),
        };
      }

      throw new Error(`Unhandled fetch request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBondAnalyticsView(
      createApiClient({
        mode: "real",
        baseUrl: "http://localhost:8000",
        fetchImpl: fetchMock as unknown as typeof fetch,
      }),
    );

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-action-attribution", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "action-attribution",
      );
    });

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-credit-spread", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "credit-spread",
      );
    });
  });

  it("uses homepage structure and holdings actions to drive drill switching", async () => {
    const user = userEvent.setup();

    renderBondAnalyticsView();

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-portfolio-headlines", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "portfolio-headlines",
      );
    });

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-top-holdings", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "top-holdings",
      );
    });
  });

  it("opens the detail drilldown when the homepage DV01 risk action is clicked", async () => {
    const user = userEvent.setup();

    renderBondAnalyticsView();

    expect(
      await screen.findByTestId("bond-analysis-detail-drilldown", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    ).not.toHaveAttribute("open");

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-dv01-risk", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-drilldown")).toHaveAttribute("open");
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "dv01-risk",
      );
    });
    expect(await screen.findByTestId("dv01-risk-view")).toBeInTheDocument();
  });

  it(
    "loads the default bond-analysis landing date from backend dates instead of client-generated month ends",
    async () => {
    const fetchSequence: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        fetchSequence.push(url);

        if (url.includes("/api/bond-analytics/dates")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                result_kind: "bond_analytics.dates",
              }),
              result: {
                report_dates: ["2026-02-28", "2025-12-31"],
              },
            }),
          };
        }

        if (url.includes("/api/bond-analytics/action-attribution")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                quality_flag: "warning",
                fallback_mode: "latest_snapshot",
              }),
              result: createActionAttributionResult({
                report_date: "2026-02-28",
                warnings: ["DuckDB fact tables not yet populated - returning empty attribution"],
              }),
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    renderBondAnalyticsView(
      createApiClient({ mode: "real" }),
    );

    await waitFor(
      () => {
        expect(
          screen.getByRole("combobox", { name: "报告日" }).closest("label"),
        ).toHaveTextContent("2026-02-28");
        expect(fetchSequence.some((url) => url.includes("/api/bond-analytics/dates"))).toBe(true);
        expect(
          fetchSequence.some((url) =>
            url.includes("/api/bond-analytics/action-attribution?report_date=2026-02-28"),
          ),
        ).toBe(true);
      },
      { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
    );
  });

  it("keeps a workstation frame when bond-analysis dates fail to load and no report_date is provided", async () => {
    const fetchSequence: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        fetchSequence.push(url);

        if (url.includes("/api/bond-analytics/dates")) {
          return {
            ok: false,
            status: 503,
            json: async () => ({ detail: "dates backend unavailable" }),
          };
        }

        if (url.includes("/ui/macro/choice-series/latest")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                result_kind: "macro.choice.latest",
              }),
              result: {
                read_target: "duckdb",
                series: [],
              },
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    renderBondAnalyticsView(createApiClient({ mode: "real" }));
    expect(await screen.findByTestId("bond-analysis-toolbar")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "债券分析", level: 1 })).toBeInTheDocument();
    // datesQuery retry: 2 — 兜底工作台要等 3 次尝试全部失败后才出现。
    const fallback = await screen.findByTestId("bond-analysis-date-fallback-workbench", {}, {
      timeout: BOND_ANALYTICS_FIND_TIMEOUT,
    });
    expect(fallback).toHaveTextContent("债券分析日期载入失败");
    expect(fallback).toHaveTextContent("核心读面");
    expect(fallback).toHaveTextContent("收益率曲线与日变动");
    expect(fallback).toHaveTextContent("风险监控");
    await waitFor(() => {
      expect(fetchSequence.some((url) => url.includes("/api/bond-analytics/dates"))).toBe(true);
      expect(
        fetchSequence.some((url) => url.includes("/api/bond-analytics/action-attribution")),
      ).toBe(false);
    });
  });

  it("retries bond-analysis dates loading from the explicit error state", async () => {
    const user = userEvent.setup();
    let datesAttempts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;

        if (url.includes("/api/bond-analytics/dates")) {
          datesAttempts += 1;
          // datesQuery retry: 2 — 初始加载共 3 次尝试全部失败才进入错误兜底，
          // 第 4 次（点击“重试日期载入”）成功。
          if (datesAttempts <= 3) {
            return {
              ok: false,
              status: 503,
              json: async () => ({ detail: "dates backend unavailable" }),
            };
          }
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                result_kind: "bond_analytics.dates",
              }),
              result: {
                report_dates: ["2026-02-28"],
              },
            }),
          };
        }

        if (url.includes("/api/bond-analytics/action-attribution")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta(),
              result: createActionAttributionResult({
                report_date: "2026-02-28",
                total_actions: 1,
              }),
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    renderBondAnalyticsView(createApiClient({ mode: "real" }));
    expect(
      await screen.findByRole(
        "button",
        { name: "重试日期载入" },
        { timeout: BOND_ANALYTICS_FIND_TIMEOUT },
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-date-fallback-workbench")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试日期载入" }));
    expect(
      await screen.findByTestId("bond-analysis-top-cockpit", {}, {
        timeout: BOND_ANALYTICS_FIND_TIMEOUT,
      }),
    ).toBeInTheDocument();
    expect(datesAttempts).toBe(4);
  });

  it("shows an explicit empty state when bond-analysis dates return no available report dates", async () => {
    const fetchSequence: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        fetchSequence.push(url);

        if (url.includes("/api/bond-analytics/dates")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                result_kind: "bond_analytics.dates",
              }),
              result: {
                report_dates: [],
              },
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    renderBondAnalyticsView(createApiClient({ mode: "real" }));
    expect(await screen.findByRole("button", { name: "重试日期载入" })).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-date-fallback-workbench")).toHaveTextContent("暂无可用报告日");
    expect(screen.queryByTestId("bond-analysis-top-cockpit")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(fetchSequence.some((url) => url.includes("/api/bond-analytics/dates"))).toBe(true);
      expect(
        fetchSequence.some((url) => url.includes("/api/bond-analytics/action-attribution")),
      ).toBe(false);
    });
  });

  it("retries bond-analysis dates loading from the explicit empty state", async () => {
    const user = userEvent.setup();
    let datesAttempts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;

        if (url.includes("/api/bond-analytics/dates")) {
          datesAttempts += 1;
          if (datesAttempts === 1) {
            return {
              ok: true,
              json: async () => ({
                result_meta: createResultMeta({
                  result_kind: "bond_analytics.dates",
                }),
                result: {
                  report_dates: [],
                },
              }),
            };
          }
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                result_kind: "bond_analytics.dates",
              }),
              result: {
                report_dates: ["2026-02-28"],
              },
            }),
          };
        }

        if (url.includes("/api/bond-analytics/action-attribution")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta(),
              result: createActionAttributionResult({
                report_date: "2026-02-28",
                total_actions: 1,
              }),
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    renderBondAnalyticsView(createApiClient({ mode: "real" }));
    expect(await screen.findByRole("button", { name: "重试日期载入" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试日期载入" }));
    expect(await screen.findByTestId("bond-analysis-top-cockpit")).toBeInTheDocument();
    expect(datesAttempts).toBe(2);
  });

  it("keeps rendering explicit bond-analysis report_date even if dates lookup fails", async () => {
    const fetchSequence: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        fetchSequence.push(url);

        if (url.includes("/api/bond-analytics/dates")) {
          return {
            ok: false,
            status: 503,
            json: async () => ({ detail: "dates backend unavailable" }),
          };
        }

        if (url.includes("/api/bond-analytics/action-attribution")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta(),
              result: createActionAttributionResult({
                report_date: "2026-02-28",
                total_actions: 4,
                total_pnl_from_actions: "1500000",
                by_action_type: [],
              }),
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    render(
      <MemoryRouter initialEntries={["/bond-analysis?report_date=2026-02-28"]}>
        <ApiClientProvider client={createApiClient({ mode: "real" })}>
          <QueryClientProvider
            client={
              new QueryClient({
                defaultOptions: {
                  queries: { retry: false, refetchOnWindowFocus: false },
                },
              })
            }
          >
            <BondAnalyticsView />
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: "重试日期载入" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        fetchSequence.some((url) =>
          url.includes("/api/bond-analytics/action-attribution?report_date=2026-02-28"),
        ),
      ).toBe(true);
    });
  });
});
