import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="market-data-echarts-stub" />,
}));

vi.mock("../app/jobs/polling", () => ({
  runPollingTask: vi.fn(),
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { runPollingTask } from "../app/jobs/polling";
import type { ChoiceMacroLatestPoint, ResultMeta } from "../api/contracts";
import { LiveResultMetaStrip } from "../features/market-data/components/LiveResultMetaStrip";
import MarketDataPage from "../features/market-data/pages/MarketDataPage";
import { EM_DASH } from "../utils/format";

const FORMAL_NCD_MATRIX_BLOCKED_STATUS = {
  status: "blocked",
  required_shape: "tenor_rating_matrix",
  current_proxy_basis: "shibor_funding_proxy",
  choice_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
  tushare_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
  missing_requirements: [
    "governed NCD tenor-rating source contract",
    "issuer/rating tenor matrix rows",
    "unit/date semantics and golden sample approval",
  ],
};

/** 完整策略/联动读面的承接锚点（MarketDataLinkageSummaryCard 与页内策略证据卡共用）。 */
const CROSS_ASSET_LINKAGE_HREF = "/cross-asset#cross-asset-zone-linkage";

function renderPage(client: ApiClient, options?: { initialEntries?: string[] }) {
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
      <MemoryRouter initialEntries={options?.initialEntries}>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <MarketDataPage />
    </Wrapper>,
  );
}

function renderPageWithQueryClient(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  const result = render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MarketDataPage />
        </ApiClientProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );

  return { ...result, queryClient };
}

function stubIntersectionObserver() {
  const callbacks: IntersectionObserverCallback[] = [];
  const observe = vi.fn();
  const disconnect = vi.fn();
  const MockObserver = vi.fn(function MockIntersectionObserver(callback: IntersectionObserverCallback) {
    callbacks.push(callback);
    return { observe, disconnect };
  });
  vi.stubGlobal("IntersectionObserver", MockObserver);

  return {
    observe,
    disconnect,
    triggerAll(isIntersecting: boolean) {
      for (const callback of callbacks) {
        callback(
          [{ isIntersecting } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    },
  };
}

/** 旧锚点跳转断言用：MemoryRouter 内没有真实路由表，用探针读取跳转后的 location。 */
function LocationProbe() {
  const location = useLocation();
  return (
    <span data-testid="market-data-test-location">
      {`${location.pathname}${location.search}${location.hash}`}
    </span>
  );
}

function renderPageWithLocationProbe(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  return render(
    <MemoryRouter initialEntries={["/market-data"]}>
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MarketDataPage />
          <LocationProbe />
        </ApiClientProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

/** antd DatePicker：向内部 input 输入并以 Enter 提交（format=YYYY-MM-DD）。 */
function changeMarketDataWatchDate(value: string) {
  const picker = screen.getByTestId("market-data-date-picker");
  const input = picker instanceof HTMLInputElement ? picker : picker.querySelector("input");
  if (!(input instanceof HTMLInputElement)) {
    throw new Error("date picker input missing");
  }
  fireEvent.mouseDown(input);
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
  fireEvent.blur(input);
}

function buildResultMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_market_data_test",
    basis: "formal",
    result_kind: "market_data.rates",
    formal_use_allowed: true,
    source_version: "sv_market_data_test",
    vendor_version: "vv_market_data_test",
    rule_version: "rv_market_data_test",
    cache_version: "cv_market_data_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T09:00:00Z",
    ...partial,
  };
}

function buildMacroPoint(
  partial: Partial<ChoiceMacroLatestPoint> & Pick<ChoiceMacroLatestPoint, "series_id">,
): ChoiceMacroLatestPoint {
  return {
    series_name: partial.series_id,
    trade_date: "2026-04-30",
    value_numeric: 1.94,
    unit: "%",
    source_version: "sv_market_data_test",
    vendor_version: "vv_market_data_test",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    quality_flag: "ok",
    latest_change: 0.012,
    recent_points: [],
    ...partial,
  };
}

describe("MarketDataPage", () => {
  afterEach(() => {
    vi.mocked(runPollingTask).mockReset();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", window.location.pathname);
  });

  it("keeps the page stylesheet on tokens instead of raw color or shadow debt", () => {
    const css = readFileSync(join(process.cwd(), "src/features/market-data/pages/MarketDataPage.css"), "utf8");
    // 2026-06-23 visual upgrade introduces a paper/ink palette via CSS custom
    // properties and subtle rgba shadows. Only flag non-standard shadow patterns.
    const privateShadowLines = css
      .split(/\r?\n/)
      .filter((line) => /box-shadow\s*:/.test(line))
      .filter((line) => !/rgba\(/.test(line))
      .filter((line) => !/box-shadow\s*:\s*(?:none|var\()/.test(line));

    expect(privateShadowLines).toEqual([]);
  });

  it("uses one hero status surface and shared section-head regions", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    await screen.findByTestId("market-data-kpi-band");

    const hero = screen.getByTestId("market-data-hero");
    const statusStrip = screen.getByTestId("market-data-status-strip");
    expect(statusStrip.parentElement).toBe(hero);
    expect(hero.querySelector(".moss-page-v2-decision-hero__conclusion")).toBeNull();

    const formalRatesBoard = screen.getByTestId("market-data-formal-rates-board");
    expect(formalRatesBoard).toHaveAttribute("aria-labelledby", "market-data-formal-rates-title");

    const formalRatesHead = screen.getByTestId("market-data-formal-rates-head");
    expect(formalRatesHead).toHaveAttribute("data-numbered", "false");
    expect(within(formalRatesHead).getByText("利率行情")).toBeInTheDocument();
    expect(within(formalRatesHead).getByText("利率曲线与宏观深度")).toBeInTheDocument();
    expect(within(formalRatesHead).getByRole("heading", { level: 2, name: "01 正式利率" })).toHaveAttribute(
      "id",
      "market-data-formal-rates-title",
    );
    expect(within(formalRatesHead).getByRole("link")).toHaveAttribute(
      "href",
      "#market-data-evidence-gate",
    );

    const liquidityRegion = screen.getByRole("region", { name: "03 资金市场与存单" });
    expect(liquidityRegion).toHaveAttribute("aria-labelledby", "market-data-liquidity-title");

    const liquidityHead = within(liquidityRegion).getByTestId("market-data-liquidity-head");
    expect(liquidityHead).toHaveAttribute("data-numbered", "false");
    expect(within(liquidityHead).getByText("资金读数")).toBeInTheDocument();
    expect(
      within(liquidityHead).getByText("DR007、回购与 Shibor 代理矩阵；正式口径摘要见右侧源门禁。"),
    ).toBeInTheDocument();
    expect(within(liquidityHead).getByRole("heading", { level: 2, name: "03 资金市场与存单" })).toHaveAttribute(
      "id",
      "market-data-liquidity-title",
    );
  });

  it("renders the market data page as an institutional terminal cockpit", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const kpiBand = await screen.findByTestId("market-data-kpi-band");

    const formalRatesBoard = screen.getByTestId("market-data-formal-rates-board");

    expect(screen.getByTestId("market-data-page")).toHaveAttribute("data-layout-rev", "2026-07-01-redesign");
    expect(screen.getByTestId("market-data-supply-evidence-rail")).toBeInTheDocument();
    expect(formalRatesBoard).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-coverage-command")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-analyst-split")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-contract-hero")).not.toBeInTheDocument();
    // 右栏治理元数据默认收起为"数据状态"入口条；details 收起时契约 testid 仍须在 DOM 中可及。
    expect(screen.getByTestId("market-data-layout")).toHaveAttribute("data-rail-expanded", "false");
    expect(screen.getByTestId("market-data-rail-disclosure")).not.toHaveAttribute("open");
    expect(screen.getByTestId("market-data-rail-summary")).toHaveTextContent(/^数据状态：正式 \d+ · 代理 \d+ · 未接入 \d+/);
    // 面板内分三组：线路状态 / 口径证据 / 数据运维（方案 §5）。
    const supplyEvidence = screen.getByTestId("market-data-supply-evidence-rail");
    expect(within(supplyEvidence).getByText("线路状态")).toBeInTheDocument();
    expect(within(supplyEvidence).getByText("口径证据")).toBeInTheDocument();
    expect(within(supplyEvidence).getByText("数据运维")).toBeInTheDocument();
    // 正常态（无 stale/error）静默：不出现"下一步动作"置顶块（L2 专用）。
    expect(within(supplyEvidence).queryByText("下一步动作")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-rail-next-actions")).not.toBeInTheDocument();
    // 线路状态组九条链路逐行可及；结构性行（代理/未接入）标为 L1 灰列。
    expect(screen.getByTestId("market-data-rail-line-formal_rates")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rail-line-money_market")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rail-line-fx_formal")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rail-line-ncd_proxy")).toHaveAttribute("data-layer", "l1");
    expect(screen.getByTestId("market-data-rail-line-bond_futures")).toHaveAttribute("data-layer", "l1");
    // 3 个 source-pending 面板的摘要并入"未接入"清单（复用 sourcePendingLabels）。
    expect(screen.getByTestId("market-data-rail-source-pending-summary")).toHaveTextContent(
      "国债期货 / 现券成交 / 信用成交",
    );
    // 口径证据组承载 basis / formal_use_allowed 与时间语义三行。
    const evidenceGroup = screen.getByTestId("market-data-rail-group-evidence");
    expect(within(evidenceGroup).getByText("允许正式使用")).toBeInTheDocument();
    expect(within(evidenceGroup).getByText("报告日期")).toBeInTheDocument();
    expect(within(evidenceGroup).getByText("生成时间")).toBeInTheDocument();
    // 数据运维组披露 Choice 刷新链路与最近刷新状态。
    const opsGroup = screen.getByTestId("market-data-rail-group-ops");
    expect(within(opsGroup).getByText("Choice 宏观 · 回填 30 天")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-refresh-btn")).toHaveTextContent("刷新 Choice 宏观（回填 30 天）");
    expect(within(formalRatesBoard).getByText("01 正式利率")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-formal-rates-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-formal-rates-curve")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-key-rate-list")).toBeInTheDocument();
    expect(kpiBand).toBeInTheDocument();
    expect(screen.getByTestId("market-data-coverage-bucket-analytical-usable")).toHaveTextContent("分析口径");
    expect(screen.getByTestId("market-data-coverage-bucket-proxy-only")).toHaveTextContent("代理数据");
    expect(screen.getByTestId("market-data-coverage-bucket-source-pending")).toHaveTextContent("未接入");
    expect(screen.queryByTestId("market-data-terminal-decision-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-workbench-nav")).toHaveAttribute("data-density", "compact");
  });

  it("expands the data-status rail entry into the full evidence rail and back", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    await screen.findByTestId("market-data-kpi-band");
    const layout = screen.getByTestId("market-data-layout");
    const disclosure = screen.getByTestId("market-data-rail-disclosure");
    expect(layout).toHaveAttribute("data-rail-expanded", "false");
    // 收起态下右栏契约锚点仍在 DOM（显式披露折叠可及，不是隐藏删除）。
    expect(screen.getByTestId("market-data-supply-evidence-rail")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("market-data-rail-summary"));
    await waitFor(() => {
      expect(layout).toHaveAttribute("data-rail-expanded", "true");
    });
    expect(disclosure).toHaveAttribute("open");
    expect(screen.getByTestId("market-data-rail-summary")).toHaveTextContent("收起明细");

    fireEvent.click(screen.getByTestId("market-data-rail-summary"));
    await waitFor(() => {
      expect(layout).toHaveAttribute("data-rail-expanded", "false");
    });
    expect(screen.getByTestId("market-data-rail-summary")).toHaveTextContent("展开明细");
  });

  it("tops runtime anomalies as next actions and marks the affected line as L2", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMarketDataCoverageSummary = vi.fn(async () => {
      const envelope = await base.getMarketDataCoverageSummary();
      return {
        ...envelope,
        result: {
          ...envelope.result,
          sections: envelope.result.sections.map((section) =>
            section.key === "macro_latest" ? { ...section, status: "stale" as const } : section,
          ),
        },
      };
    });

    renderPage({ ...base, getMarketDataCoverageSummary });

    await screen.findByTestId("market-data-kpi-band");
    // L2 运行时异常：入口条亮灯计数与面板置顶"下一步动作"一致。
    await waitFor(() => {
      expect(screen.getByTestId("market-data-rail-summary")).toHaveTextContent("延迟 1");
    });
    const supplyEvidence = screen.getByTestId("market-data-supply-evidence-rail");
    const nextActions = screen.getByTestId("market-data-rail-next-actions");
    expect(supplyEvidence.firstElementChild).toBe(nextActions);
    expect(within(nextActions).getByText("下一步动作")).toBeInTheDocument();
    expect(nextActions).toHaveTextContent("复核数据延迟");
    expect(nextActions).toHaveTextContent("Macro latest observations");
    expect(within(nextActions).getByText("数据延迟")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rail-line-macro_latest")).toHaveAttribute("data-layer", "l2");
    // 结构性未接入行仍是 L1 灰列，不因异常升级而混入下一步动作。
    expect(screen.getByTestId("market-data-rail-line-cash_bond_trades")).toHaveAttribute("data-layer", "l1");
    expect(nextActions).not.toHaveTextContent("Cash bond trades");
  });

  it("renders external comparison stale and fallback lineage in map rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        quality_flag: "stale",
        vendor_status: "vendor_stale",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "CA.CSI300",
            series_name: "CSI300",
            trade_date: "2026-04-10",
            value_numeric: 4102.25,
            unit: "index",
            quality_flag: "stale",
          }),
          buildMacroPoint({
            series_id: "CA.COPPER",
            series_name: "Copper",
            trade_date: "2026-04-10",
            value_numeric: 81234.5,
            unit: "CNY/t",
          }),
        ],
      },
    }));
    const getTushareSupplement = vi.fn(async () => {
      const envelope = await base.getTushareSupplement();
      return {
        ...envelope,
        result_meta: buildResultMeta({
          basis: "analytical",
          result_kind: "market_data.tushare_supplement",
          formal_use_allowed: false,
          quality_flag: "stale",
          vendor_status: "vendor_stale",
          fallback_mode: "latest_snapshot",
        }),
      };
    });

    renderPage({
      ...base,
      getChoiceMacroLatest,
      getTushareSupplement,
    });

    await waitFor(() => {
      const evidenceRail = screen.getByTestId("market-data-macro-evidence-rail");
      expect(evidenceRail).toHaveTextContent("数据延迟");
      expect(evidenceRail).toHaveTextContent("来源需复核");
    });
  });

  it("renders macro catalog plus trend and lineage evidence from the API client contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const foundationMeta: ResultMeta = {
      trace_id: "tr_macro_foundation_test",
      basis: "analytical",
      result_kind: "preview.macro-foundation",
      formal_use_allowed: false,
      source_version: "sv_macro_vendor_test",
      vendor_version: "vv_choice_catalog_v1",
      rule_version: "rv_phase1_macro_vendor_v1",
      cache_version: "cv_phase1_macro_vendor_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:00:00Z",
    };
    const latestMeta: ResultMeta = {
      trace_id: "tr_choice_macro_latest_test",
      basis: "analytical",
      result_kind: "macro.choice.latest",
      formal_use_allowed: false,
      source_version: "sv_choice_macro_latest_test",
      vendor_version: "vv_choice_macro_20260410",
      rule_version: "rv_choice_macro_thin_slice_v1",
      cache_version: "cv_choice_macro_thin_slice_v1",
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:05:00Z",
    };
    const getMacroFoundation = vi.fn(async () => ({
      result_meta: foundationMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
          },
          {
            series_id: "M002",
            series_name: "DR007",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "fallback" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "single" as const,
            policy_note: "low-frequency latest-only lane",
          },
          {
            series_id: "M003",
            series_name: "RMB Index",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
          },
        ],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: latestMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            trade_date: "2026-04-10",
            value_numeric: 1.75,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
            frequency: "daily",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
            quality_flag: "ok" as const,
            latest_change: 0.2,
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 1.75,
                source_version: "sv_choice_macro_latest_test",
                vendor_version: "vv_choice_macro_20260410",
                quality_flag: "ok" as const,
              },
              {
                trade_date: "2026-04-09",
                value_numeric: 1.55,
                source_version: "sv_choice_macro_prev_test",
                vendor_version: "vv_choice_macro_20260409",
                quality_flag: "ok" as const,
              },
            ],
          },
          {
            series_id: "M002",
            series_name: "DR007",
            trade_date: "2026-04-10",
            value_numeric: 1.83,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
            frequency: "daily",
            refresh_tier: "fallback" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "single" as const,
            policy_note: "low-frequency latest-only lane",
            quality_flag: "warning" as const,
            latest_change: null,
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 1.83,
                source_version: "sv_choice_macro_latest_test",
                vendor_version: "vv_choice_macro_20260410",
                quality_flag: "warning" as const,
              },
            ],
          },
        ],
      },
    }));
    // 策略读面已迁 /cross-asset：这里只留探针，断言本页不再触发该端点。
    const getLivermoreStrategy = vi.fn((options?: { asOfDate?: string }) =>
      base.getLivermoreStrategy(options),
    );
    const getMarketDataCoverageSummary = vi.fn(() => base.getMarketDataCoverageSummary());

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getLivermoreStrategy,
      getMarketDataCoverageSummary,
    });

    expect(await screen.findByTestId("market-data-hero")).toHaveTextContent("市场数据");
    expect(screen.getByTestId("market-data-page")).toHaveAttribute("data-layout-rev", "2026-07-01-redesign");
    expect(screen.getByTestId("market-data-page")).toHaveAttribute("data-view-mode", "default");
    await waitFor(() => {
      expect(getMarketDataCoverageSummary).toHaveBeenCalledTimes(1);
    });
    const statusStrip = screen.getByTestId("market-data-status-strip");
    expect(statusStrip).toBeInTheDocument();
    expect(screen.getByText(/数据日期/)).toBeInTheDocument();
    expect(statusStrip).not.toHaveTextContent("目录 3");
    expect(statusStrip).not.toHaveTextContent("稳定回收 1 / 2");
    expect(statusStrip).not.toHaveTextContent("口径 正式");
    expect(statusStrip).not.toHaveTextContent("口径 分析");
    expect(screen.getByText("利率曲线与宏观深度")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-card")).toBeInTheDocument();
    // 02 区卡壳退役后，走势读面并入 01 区次行（方案裁决 #4）。
    expect(screen.getByTestId("market-data-rate-trend-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-view-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("正式利率");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("查看数据诊断");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("外汇分析");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("利弗莫尔");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("宏观债券联动");
    expect(screen.getByTestId("market-data-source-pending-deck")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-extended-terminal-collapse")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-source-pending-contract-note")).toHaveTextContent(
      "国债期货",
    );
    // 外汇正式区上提：简表常显，完整明细收在原生 details（默认收起、首开挂载）。
    expect(screen.getByTestId("market-data-fx-formal-summary-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-formal-collapse")).not.toHaveAttribute("open");
    expect(screen.queryByTestId("market-data-fx-formal-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-livermore-collapse")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-livermore-panel")).not.toBeInTheDocument();
    expect(screen.queryByText("宏观序列与分析观察")).not.toBeInTheDocument();
    // 04 区已迁入序列浏览器：主列只保留单行入口卡，不再平铺宏观/外汇序列。
    expect(screen.queryByTestId("market-data-supplementary-series-section")).not.toBeInTheDocument();
    const seriesLibraryEntry = screen.getByTestId("market-data-series-library-entry");
    expect(seriesLibraryEntry).toHaveTextContent("宏观与外汇序列");
    await waitFor(() => {
      expect(seriesLibraryEntry).toHaveTextContent("稳定 1 · 降级 1 · 按需查看");
    });
    expect(screen.queryByText("目录与结果元数据")).not.toBeInTheDocument();
    // Livermore 读面已迁 /cross-asset（方案裁决 #9）：本页只留导航证据卡，门控/板块/候选断言归该页。
    expect(screen.getByTestId("market-data-strategy-evidence-card")).toBeInTheDocument();
    expect(screen.queryByTestId("livermore-market-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("livermore-rule-readiness")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-missing-stable-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-result-meta")).not.toBeInTheDocument();
    const macroReadiness = await screen.findByTestId("market-data-macro-readiness");
    await waitFor(() => {
      expect(macroReadiness).toHaveTextContent("DR007");
      expect(macroReadiness).toHaveTextContent("T+48");
      expect(macroReadiness).toHaveTextContent("stale");
      expect(macroReadiness).toHaveTextContent("2026-04-10T09:05:00Z");
    });
    expect(macroReadiness).not.toHaveTextContent("Brent crude oil futures close");
    expect(macroReadiness).not.toHaveTextContent("USD/CNY spot 数据 T+");
    expect(screen.queryByTestId("market-data-overview-live-meta")).not.toBeInTheDocument();
    expect(statusStrip).toHaveTextContent("数据正常");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent(
      "宏观最新：仅分析使用 / 部分缺失 / 暂不可用于正式决策",
    );
    expect(screen.queryByTestId("market-data-curve-live-meta")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-section-meta")).not.toBeInTheDocument();
    expect(screen.queryByText("仅取最新降级")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-section-meta")).not.toBeInTheDocument();
    // 外汇分析组读面归属序列浏览器（domain=fx），驾驶舱主列不再出现分组标题。
    expect(screen.queryByText("外汇分析：中间价")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "结果元数据" })).not.toBeInTheDocument();

    // 原 02 区“收益率曲线”Tab 标题退役，走势读面标题落在 01 区次行。
    expect(screen.queryByText("收益率曲线")).not.toBeInTheDocument();
    expect(screen.getByRole("figure", { name: "收益率走势" })).toHaveTextContent("收益率走势");
    expect(screen.getByRole("figure", { name: "收益率走势" })).toHaveTextContent(
      "近 30 日 · 分析口径",
    );
    expect(screen.getByTestId("market-data-rate-quote-table")).toBeInTheDocument();
    const liquidityDeck = screen.getByTestId("market-data-liquidity-deck");
    expect(liquidityDeck).toContainElement(screen.getByTestId("market-data-money-market-card"));
    expect(liquidityDeck).toContainElement(screen.getByTestId("market-data-ncd-card"));
    expect(screen.getByTestId("market-data-money-market-table")).toBeInTheDocument();
    // mock NCD 为单行矩阵：无对比维度，热力视图与切换按约定隐藏，仅保留表格。
    expect(screen.queryByTestId("market-data-ncd-view-toggle")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-trend-chart")).toHaveTextContent("无法绘制走势图");

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
    // 策略端点由 /cross-asset 负责，本页任何加载阶段都不得调用。
    expect(getLivermoreStrategy).not.toHaveBeenCalled();
  });

  it("keeps KPI band available in the hero section", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const kpiBand = await screen.findByTestId("market-data-kpi-band");
    expect(kpiBand).toBeInTheDocument();
    const hero = screen.getByTestId("market-data-hero");
    expect(hero).toContainElement(kpiBand);
  });

  it("keeps below-fold workspaces unmounted until their observer activates", async () => {
    const observer = stubIntersectionObserver();

    const base = createApiClient({ mode: "mock" });
    const getMacroBondLinkageAnalysis = vi.fn((options: { reportDate: string }) =>
      base.getMacroBondLinkageAnalysis(options),
    );

    renderPage({ ...base, getMacroBondLinkageAnalysis });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    // extended terminal / linkage summary / news-calendar summary 各一个观察者；
    // 04 序列区已迁入 ?view=explorer，Livermore 读面已迁 /cross-asset，均不再懒挂载。
    await waitFor(() => expect(observer.observe).toHaveBeenCalledTimes(3));
    expect(screen.queryByTestId("market-data-source-pending-deck")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-supplementary-series-section")).not.toBeInTheDocument();
    // 入口卡与摘要卡壳随驾驶舱主列同步渲染，不依赖观察者；只有明细请求被推迟。
    expect(screen.getByTestId("market-data-series-library-entry")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-summary-card")).toBeInTheDocument();
    expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalled();

    act(() => {
      observer.triggerAll(true);
    });

    expect(await screen.findByTestId("market-data-source-pending-deck")).toBeInTheDocument();
    await waitFor(() => expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(1));
  });

  it.each([
    {
      label: "printing",
      reveal: () => window.dispatchEvent(new Event("beforeprint")),
    },
    {
      label: "native page search",
      reveal: () =>
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "f", ctrlKey: true })),
    },
  ])("materializes below-fold workspaces for $label", async ({ reveal }) => {
    stubIntersectionObserver();
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-source-pending-deck")).not.toBeInTheDocument();

    act(() => {
      reveal();
    });

    expect(await screen.findByTestId("market-data-source-pending-deck")).toBeInTheDocument();
  });

  it("materializes the supplementary section for a direct macro-series deep link", async () => {
    // 旧锚点 #market-data-macro-series 的兼容语义改为：直接打开序列浏览器（?view=explorer），不再滚动主列平铺区。
    stubIntersectionObserver();
    window.location.hash = "#market-data-macro-series";

    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-explorer-view")).toBeInTheDocument();
    // 契约锚点迁入浏览器视图后仍可达（宏观域读面容器）。
    expect(await screen.findByTestId("market-data-macro-series-deck")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-supplementary-series-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-formal-rates-board")).not.toBeInTheDocument();
  });

  it("materializes the supplementary section after a post-mount macro-series hashchange", async () => {
    // 同上：post-mount hashchange 也应打开序列浏览器，而不是物化旧平铺区。
    stubIntersectionObserver();
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-explorer-view")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-supplementary-series-section")).not.toBeInTheDocument();

    act(() => {
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}#market-data-macro-series`,
      );
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(await screen.findByTestId("market-data-explorer-view")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-macro-series-deck")).toBeInTheDocument();
  });

  function buildExplorerFixtureClient() {
    const base = createApiClient({ mode: "mock" });
    const recentPoints = (values: Array<[string, number]>) =>
      values.map(([tradeDate, value]) => ({
        trade_date: tradeDate,
        value_numeric: value,
        source_version: "sv_explorer_test",
        vendor_version: "vv_explorer_test",
        quality_flag: "ok" as const,
      }));
    const getMacroFoundation = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "preview.macro-foundation",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M101",
            series_name: "中债国债到期收益率:10年",
            vendor_name: "choice",
            vendor_version: "vv_explorer_test",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
          },
          {
            series_id: "M102",
            series_name: "存款类机构质押式回购加权利率:DR007",
            vendor_name: "choice",
            vendor_version: "vv_explorer_test",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
          },
          {
            series_id: "M201",
            series_name: "沪深300指数",
            vendor_name: "choice",
            vendor_version: "vv_explorer_test",
            frequency: "daily",
            unit: "点",
            refresh_tier: "fallback" as const,
          },
          {
            series_id: "M301",
            series_name: "稳定缺失测试序列",
            vendor_name: "choice",
            vendor_version: "vv_explorer_test",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
          },
        ],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "M101",
            series_name: "中债国债到期收益率:10年",
            value_numeric: 1.94,
            recent_points: recentPoints([
              ["2026-04-29", 1.92],
              ["2026-04-30", 1.94],
            ]),
          }),
          buildMacroPoint({
            series_id: "M102",
            series_name: "存款类机构质押式回购加权利率:DR007",
            value_numeric: 1.82,
            recent_points: recentPoints([
              ["2026-04-29", 1.8],
              ["2026-04-30", 1.82],
            ]),
          }),
          buildMacroPoint({
            series_id: "M201",
            series_name: "沪深300指数",
            value_numeric: 4102.25,
            unit: "点",
            refresh_tier: "fallback",
            fetch_mode: "latest",
          }),
        ],
      },
    }));
    return { ...base, getMacroFoundation, getChoiceMacroLatest } as ApiClient;
  }

  it("browses macro themes, tiers, search, and missing-stable list inside the series explorer", async () => {
    renderPage(buildExplorerFixtureClient());

    // 入口卡计数来自 stableSeries/fallbackSeries。
    const entry = await screen.findByTestId("market-data-series-library-entry");
    await waitFor(() => {
      expect(entry).toHaveTextContent("稳定 2 · 降级 1 · 按需查看");
    });

    fireEvent.click(entry);
    expect(await screen.findByTestId("market-data-explorer-view")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-macro-series-deck")).toBeInTheDocument();

    // 目录按链路分节：稳定 2 条 1 组（利率与流动性），降级 1 条 1 组（权益市场）。
    expect(screen.getByTestId("market-data-macro-stable-tier-rail")).toHaveTextContent(
      "稳定链路 2 条 · 1 组",
    );
    expect(screen.getByTestId("market-data-macro-fallback-tier-rail")).toHaveTextContent(
      "降级链路 1 条 · 1 组",
    );
    const stableThemeEntry = screen.getByTestId("market-data-macro-stable-theme-rates");
    expect(stableThemeEntry).toHaveAttribute("data-active", "true");
    // 右侧单表只渲染选中主题的序列。
    expect(await screen.findByTestId("market-data-explorer-series-M101")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-explorer-series-M102")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-explorer-series-M201")).not.toBeInTheDocument();

    // 切换到降级主题：表格只剩该主题序列。
    fireEvent.click(screen.getByTestId("market-data-macro-fallback-group-equity"));
    expect(await screen.findByTestId("market-data-explorer-series-M201")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-explorer-series-M101")).not.toBeInTheDocument();

    // 名称搜索同时作用于目录与表格；无命中的降级组收敛为空态，主题回落到首个可见组。
    fireEvent.change(screen.getByTestId("market-data-explorer-search"), {
      target: { value: "国债" },
    });
    expect(await screen.findByTestId("market-data-explorer-series-M101")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-stable-tier-rail")).toHaveTextContent(
      "稳定链路 1 条 · 1 组",
    );
    expect(screen.getByTestId("market-data-macro-fallback-tier-rail")).toHaveTextContent(
      "降级链路 0 条 · 0 组",
    );
    fireEvent.change(screen.getByTestId("market-data-explorer-search"), {
      target: { value: "" },
    });

    // 链路等级筛选：稳定档隐藏降级目录节。
    fireEvent.click(screen.getByTestId("market-data-explorer-tier-stable"));
    await waitFor(() => {
      expect(screen.queryByTestId("market-data-macro-fallback-directory")).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("market-data-explorer-tier-all"));
    expect(await screen.findByTestId("market-data-macro-fallback-directory")).toBeInTheDocument();

    // 单序列钻取：走势 + 元数据行；受控模式下表内不再重复内联图。
    fireEvent.click(screen.getByTestId("market-data-macro-stable-theme-rates"));
    await screen.findByTestId("market-data-explorer-series-M101");
    fireEvent.click(screen.getByTestId("market-data-explorer-series-chart-toggle-M101"));
    const detail = await screen.findByTestId("market-data-explorer-series-detail");
    expect(detail).toHaveTextContent("中债国债到期收益率:10年");
    expect(detail).toHaveTextContent("M101");
    expect(detail).toHaveTextContent("时效档");
    expect(screen.getByTestId("market-data-explorer-series-detail-meta")).toHaveTextContent(
      "2026-04-30",
    );
    expect(
      screen.queryByTestId("market-data-explorer-series-inline-chart-M101"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("market-data-explorer-series-detail-close"));
    await waitFor(() => {
      expect(screen.queryByTestId("market-data-explorer-series-detail")).not.toBeInTheDocument();
    });

    // 待补齐稳定链路并入目录：选中后右侧展示 catalog 缺口清单。
    fireEvent.click(screen.getByTestId("market-data-macro-missing-stable-entry"));
    const missingSection = await screen.findByTestId("market-data-missing-stable-section");
    expect(missingSection).toHaveTextContent("稳定缺失测试序列");
    expect(missingSection).toHaveTextContent("M301");

    // 返回驾驶舱：主列恢复正式利率区。
    fireEvent.click(screen.getByTestId("market-data-explorer-close"));
    expect(await screen.findByTestId("market-data-formal-rates-board")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-explorer-view")).not.toBeInTheDocument();
  });

  it("restores explorer drill-down state from a series deep link", async () => {
    renderPage(buildExplorerFixtureClient(), {
      initialEntries: ["/market-data?view=explorer&series=M102"],
    });

    expect(await screen.findByTestId("market-data-explorer-view")).toBeInTheDocument();
    const detail = await screen.findByTestId("market-data-explorer-series-detail");
    expect(detail).toHaveTextContent("存款类机构质押式回购加权利率:DR007");
    expect(detail).toHaveTextContent("M102");
    // theme 缺省时按选中序列回落到其所属主题，同组序列同表可见。
    expect(await screen.findByTestId("market-data-explorer-series-M101")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-explorer-series-chart-toggle-M102")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("shows the FX formal summary table by default and defers full detail behind a native details", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    // 简表常显：无需任何展开动作即可读到正式中间价（货币对/中间价/交易日/状态）。
    const summaryTable = await screen.findByTestId("market-data-fx-formal-summary-table");
    await waitFor(() => {
      expect(summaryTable).toHaveTextContent("USD/CNY");
    });
    expect(summaryTable).toHaveTextContent("7.2000");
    expect(summaryTable).toHaveTextContent("2026-04-10");
    // missing 行显式呈现"缺失"，不静默补数。
    expect(summaryTable).toHaveTextContent("JPY/CNY");
    expect(summaryTable).toHaveTextContent("缺失");

    // 行序按后端返回顺序取前 N（N=5）：mock 3 行候选全部进入简表，且不超上界。
    const summaryRows = summaryTable.querySelectorAll("tbody tr");
    expect(summaryRows.length).toBe(3);
    expect(summaryRows.length).toBeLessThanOrEqual(5);

    // 正式简表不得混入 FX analytical 序列（mock analytical 专有名不出现）。
    expect(summaryTable).not.toHaveTextContent("中间价观察");
    expect(summaryTable).not.toHaveTextContent("CFETS");

    // 完整明细默认收起，且首开才挂载（panel 初始不在 DOM）。
    expect(screen.getByTestId("market-data-fx-formal-collapse")).not.toHaveAttribute("open");
    expect(screen.queryByTestId("market-data-fx-formal-panel")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("market-data-fx-formal-details-summary"));

    expect(await screen.findByTestId("market-data-fx-formal-panel")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("market-data-fx-formal-table")).toHaveTextContent("USD/CNY");
    });
    // 明细才有的列（供应商/观测日）在展开后可见。
    expect(screen.getByTestId("market-data-fx-formal-table")).toHaveTextContent("choice");
    expect(screen.queryByTestId("market-data-fx-formal-meta")).not.toBeInTheDocument();
  });

  it("surfaces an explicit blocked warning when FX formal use is not allowed", async () => {
    const base = createApiClient({ mode: "mock" });
    const getFxFormalStatus = vi.fn(async () => {
      const envelope = await base.getFxFormalStatus();
      return {
        ...envelope,
        result_meta: { ...envelope.result_meta, formal_use_allowed: false },
      };
    });

    renderPage({ ...base, getFxFormalStatus });

    const blocked = await screen.findByTestId("market-data-fx-formal-blocked");
    expect(blocked).toHaveTextContent("暂不可正式使用");
  });

  it("defers macro-bond linkage until the summary card approaches the viewport", async () => {
    const observer = stubIntersectionObserver();
    const base = createApiClient({ mode: "mock" });
    const getMacroBondLinkageAnalysis = vi.fn((options: { reportDate: string }) =>
      base.getMacroBondLinkageAnalysis(options),
    );

    renderPage({
      ...base,
      getMacroBondLinkageAnalysis,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    // 摘要卡壳常驻主列（PAGE-MKT-001 §B 的 report_date 回答处），明细请求近视口才发。
    expect(screen.getByTestId("market-data-linkage-summary-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-caveat")).toBeInTheDocument();
    expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalled();

    act(() => {
      observer.triggerAll(true);
    });

    await waitFor(() => expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("market-data-linkage-summary-report-date")).toHaveTextContent(
      "报告日期",
    );
    // 明细读面已由 /cross-asset 承接：本页只留摘要 + 跳转，不再展开相关性矩阵。
    expect(screen.getByTestId("market-data-linkage-summary-link")).toHaveAttribute(
      "href",
      CROSS_ASSET_LINKAGE_HREF,
    );
    expect(screen.queryByTestId("market-data-linkage-collapse")).not.toBeInTheDocument();
  });

  it("keeps Livermore off the cockpit and routes to cross-asset through the evidence card", async () => {
    // 方案裁决 #9：Livermore 读面已迁 /cross-asset（该页测试覆盖门控/板块/候选/退出明细），本页只留导航证据卡。
    const base = createApiClient({ mode: "mock" });
    const getLivermoreStrategy = vi.fn(() => base.getLivermoreStrategy());

    renderPage({
      ...base,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    const evidenceCard = screen.getByTestId("market-data-strategy-evidence-card");
    expect(evidenceCard).toHaveTextContent("Livermore");
    // 口径标注不可省：策略读面是分析口径，跳转前后语义一致。
    expect(evidenceCard).toHaveTextContent("分析口径");
    expect(screen.getByTestId("market-data-strategy-evidence-link")).toHaveAttribute(
      "href",
      CROSS_ASSET_LINKAGE_HREF,
    );
    expect(screen.queryByTestId("market-data-livermore-collapse")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-livermore-panel")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("market-data-refresh-btn"));
    await waitFor(() => expect(screen.getByTestId("market-data-refresh-btn")).toBeEnabled());
    // 初始与显式刷新均不得拉取策略数据。
    expect(getLivermoreStrategy).not.toHaveBeenCalled();
  });

  it("keeps the rate trend read surface inside the formal rates board", async () => {
    // 方案裁决 #4：02 区三 Tab 容器退役，曲线走势并入 01 区次行；利差/联动明细归 /cross-asset。
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    const board = await screen.findByTestId("market-data-formal-rates-board");
    const trendPanel = within(board).getByTestId("market-data-rate-trend-panel");
    expect(trendPanel).toHaveTextContent("收益率走势");
    expect(within(trendPanel).getByTestId("market-data-macro-readiness")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-depth-card")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-tab-curve")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-tab-spreads")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-tab-linkage")).not.toBeInTheDocument();
  });

  it("drives terminal market panels from formal/latest data and source-pending states", async () => {
    const base = createApiClient({ mode: "mock" });
    const rateSeries = [
      buildMacroPoint({
        series_id: "EMM00166466",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.94,
        latest_change: -0.012,
      }),
      buildMacroPoint({
        series_id: "EMM00166502",
        series_name: "中债政策性金融债到期收益率(国开行)10年",
        value_numeric: 2.05,
        latest_change: 0.004,
      }),
      buildMacroPoint({
        series_id: "M001",
        series_name: "公开市场7天逆回购利率",
        value_numeric: 1.75,
        latest_change: 0.001,
      }),
      buildMacroPoint({
        series_id: "CA.DR007",
        series_name: "存款类机构质押式回购加权利率:DR007",
        value_numeric: 1.82,
        latest_change: -0.006,
        fetch_mode: "latest",
      }),
    ];
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_formal_rates_terminal_test",
        source_version: "sv_formal_rates_terminal_test",
        resolved_report_date: "2026-04-30",
        as_of_date: "2026-04-30",
        fallback_date: null,
      }),
      result: {
        read_target: "duckdb" as const,
        series: rateSeries,
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        series: rateSeries,
      },
    }));
    const getBondFuturesRankings = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical" as const,
        result_kind: "market_data.bond_futures_rankings",
        formal_use_allowed: false,
        source_version: "sv_test_cffex_rank",
        vendor_version: "vv_test_tushare",
        rule_version: "rv_cffex_member_rank_choice_tushare_v1",
        cache_version: "cv_market_data_bond_futures_rankings_v1",
        source_surface: "market_data",
        tables_used: ["fact_cffex_member_rank_daily", "vw_cffex_member_rank_daily"],
        evidence_rows: 1,
      }),
      result: {
        read_target: "duckdb" as const,
        as_of_date: "2026-06-11",
        requested_trade_date: null,
        contract: "T.CFE",
        rows: [
          {
            trade_date: "2026-06-11",
            contract: "T.CFE",
            product_code: "T",
            exchange: "CFFEX",
            member_name: "中信期货",
            source_vendor: "tushare",
            source_row_no: 1,
            volume: 12345,
            volume_change: 101,
            long_holding: 23456,
            long_change: 202,
            short_holding: 21000,
            short_change: -50,
            source_version: "sv_test_cffex_rank",
            vendor_version: "vv_test_tushare",
            rule_version: "rv_cffex_member_rank_choice_tushare_v1",
          },
        ],
        warnings: [],
      },
    }));
    const getMarketDataCoverageSummary = vi.fn(async () => {
      const envelope = await base.getMarketDataCoverageSummary();
      return {
        ...envelope,
        result: {
          ...envelope.result,
          headline: {
            ...envelope.result.headline,
            source_pending_count: 2,
          },
          sections: envelope.result.sections.map((section) =>
            section.key === "bond_futures"
              ? {
                  ...section,
                  status: "ready" as const,
                  row_count: 1,
                  source_pending: false,
                  vendor_status: "ok" as const,
                }
              : section,
          ),
        },
      };
    });

    renderPage({
      ...base,
      getMarketDataRates,
      getChoiceMacroLatest,
      getBondFuturesRankings,
      getMarketDataCoverageSummary,
    } as ApiClient);

    // 快捷行情 chips 与 KPI 带同源同值，已按 §6 去重删除；行情读数由 KPI 带承载。
    const kpiCgb10y = await screen.findByTestId("market-data-terminal-kpi-cgb10y");
    expect(kpiCgb10y).toHaveTextContent("10年国债");
    expect(kpiCgb10y).toHaveTextContent("1.94%");
    expect(kpiCgb10y).toHaveTextContent("-1bp");
    expect(screen.queryByTestId("market-data-terminal-ticker")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-kpi-band")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-terminal-kpi-strip")).not.toBeInTheDocument();

    const rateTable = await screen.findByTestId("market-data-rate-quote-table");
    expect(within(rateTable).getAllByText("10Y").length).toBeGreaterThan(0);
    expect(rateTable).toHaveTextContent("1.94%");
    expect(rateTable).toHaveTextContent("-1bp");
    expect(rateTable).not.toHaveTextContent("4,856");
    const sharedMeta = screen.getByTestId("market-data-workbench-shared-meta");
    expect(sharedMeta).toHaveTextContent("口径摘要 正式");
    expect(sharedMeta).not.toHaveTextContent("供应商");
    expect(screen.queryByTestId("market-data-overview-live-meta")).not.toBeInTheDocument();

    const evidenceRail = screen.getByTestId("market-data-macro-evidence-rail");
    expect(evidenceRail).toHaveTextContent("正式利率");
    expect(evidenceRail).toHaveTextContent("正式利率：正式可用 / 数据正常 / 可正式使用");
    expect(evidenceRail).not.toHaveTextContent("formal_use_allowed");
    expect(evidenceRail).not.toHaveTextContent("sv_formal_rates_terminal_test");
    expect(evidenceRail).toHaveTextContent("外汇分析");
    expect(evidenceRail).toHaveTextContent("利弗莫尔");
    expect(evidenceRail).toHaveTextContent("宏观债券联动");
    expect(screen.getByTestId("market-data-source-pending-summary")).toHaveTextContent(
      "未接入",
    );

    const moneyTable = screen.getByTestId("market-data-money-market-table");
    expect(moneyTable).toHaveTextContent("公开市场7天逆回购利率");
    expect(moneyTable).toHaveTextContent("CA.DR007");
    expect(moneyTable).toHaveTextContent("-0.6bp");
    expect(moneyTable).not.toHaveTextContent("24,331");

    const bondFuturesTable = screen.getByTestId("market-data-bond-futures-table");
    expect(bondFuturesTable).toHaveTextContent("中信期货");
    expect(bondFuturesTable).toHaveTextContent("T.CFE");
    expect(bondFuturesTable).toHaveTextContent("23,456");
    expect(screen.getByTestId("market-data-source-pending-summary")).toHaveTextContent("未接入 2");
    expect(screen.queryByTestId("market-data-bond-futures-source-pending")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-bond-trades-source-pending")).toHaveTextContent("未接入");
    expect(screen.getByTestId("market-data-credit-trades-source-pending")).toHaveTextContent("未接入");

    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getBondFuturesRankings).toHaveBeenCalledTimes(1);
      expect(getMarketDataCoverageSummary).toHaveBeenCalledTimes(1);
    });
  });

  it("surfaces a visible warning when formal-labeled rates are not allowed for formal use", async () => {
    const base = createApiClient({ mode: "mock" });
    const rateSeries = [
      buildMacroPoint({
        series_id: "EMM00166466",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.94,
        latest_change: -0.012,
      }),
    ];
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_formal_blocked_rates_test",
        basis: "formal",
        formal_use_allowed: false,
        source_version: "sv_candidate_rates_test",
      }),
      result: {
        read_target: "duckdb" as const,
        series: rateSeries,
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        series: rateSeries,
      },
    }));

    renderPage({
      ...base,
      getMarketDataRates,
      getChoiceMacroLatest,
    });

    const rateTable = await screen.findByTestId("market-data-rate-quote-table");
    await waitFor(() => {
      expect(within(rateTable).getByText("1.94%")).toBeInTheDocument();
    });

    const sharedMeta = await screen.findByTestId("market-data-workbench-shared-meta");
    expect(sharedMeta).toHaveTextContent("口径摘要 暂不可正式使用");
    expect(sharedMeta).toHaveTextContent("禁止作为正式口径");
    expect(screen.queryByTestId("market-data-overview-live-meta")).not.toBeInTheDocument();
    const statusStrip = screen.getByTestId("market-data-status-strip");
    expect(statusStrip).toHaveTextContent("仅分析使用");
    expect(statusStrip).toHaveTextContent("暂不可正式使用");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("暂不可用于正式决策");
  });

  it("labels mock basis and falls back from blank resolved report date", () => {
    render(
      <LiveResultMetaStrip
        lead="测试读面"
        testId="market-data-live-meta-unit"
        meta={buildResultMeta({
          basis: "mock",
          formal_use_allowed: false,
          resolved_report_date: "",
          requested_report_date: "2026-04-30",
        })}
      />,
    );

    const meta = screen.getByTestId("market-data-live-meta-unit");
    expect(meta).toHaveTextContent("口径=模拟口径");
    expect(meta).toHaveTextContent("正式可用=否");
    expect(meta).toHaveTextContent("报告日=2026-04-30");
  });

  it("renders explicit empty states for missing rate and money sources instead of demo rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_empty_terminal_test",
        source_version: "sv_empty_terminal_test",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        series: [],
      },
    }));

    renderPage({
      ...base,
      getMarketDataRates,
      getChoiceMacroLatest,
    });

    expect(await screen.findByTestId("market-data-rate-quotes-empty")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quotes-empty")).toHaveTextContent(/\S/);
    expect(screen.getByTestId("market-data-money-market-empty")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-money-market-empty")).toHaveTextContent(/\S/);
    expect(screen.queryByText("EMM00166466")).not.toBeInTheDocument();
    expect(screen.queryByText("公开市场7天逆回购利率")).not.toBeInTheDocument();
    expect(screen.queryByText("4,856")).not.toBeInTheDocument();
    expect(screen.queryByText("24,331")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("renders rate trend ECharts when Choice macro includes configured yield series", async () => {
    const base = createApiClient({ mode: "mock" });
    const pointMeta = {
      source_version: "sv_rate_test",
      vendor_version: "vv_rate_test",
      frequency: "daily" as const,
      refresh_tier: "stable" as const,
      fetch_mode: "date_slice" as const,
      fetch_granularity: "batch" as const,
      policy_note: "rate lane",
      quality_flag: "ok" as const,
    };
    const recent = [
      {
        trade_date: "2026-04-10",
        value_numeric: 2.85,
        source_version: "sv_rate_test",
        vendor_version: "vv_rate_test",
        quality_flag: "ok" as const,
      },
      {
        trade_date: "2026-04-09",
        value_numeric: 2.83,
        source_version: "sv_rate_test",
        vendor_version: "vv_rate_test",
        quality_flag: "ok" as const,
      },
    ];
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_rate_trend",
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        source_version: "sv_rate_test",
        vendor_version: "vv_rate_test",
        rule_version: "rv_test",
        cache_version: "cv_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:00:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "EMM00166466",
            series_name: "国债 10Y 测试",
            trade_date: "2026-04-10",
            value_numeric: 2.85,
            unit: "%",
            latest_change: 0.02,
            recent_points: recent,
            ...pointMeta,
          },
          {
            series_id: "EMM00166462",
            series_name: "国开 5Y 测试",
            trade_date: "2026-04-10",
            value_numeric: 2.92,
            unit: "%",
            latest_change: 0.01,
            recent_points: recent.map((p, i) =>
              i === 0 ? { ...p, value_numeric: 2.92 } : { ...p, value_numeric: 2.9 },
            ),
            ...pointMeta,
          },
          {
            series_id: "EMM00166252",
            series_name: "SHIBOR O/N 测试",
            trade_date: "2026-04-10",
            value_numeric: 1.42,
            unit: "%",
            latest_change: null,
            recent_points: recent.map((p, i) =>
              i === 0 ? { ...p, value_numeric: 1.42 } : { ...p, value_numeric: 1.4 },
            ),
            ...pointMeta,
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_foundation_min",
          basis: "analytical" as const,
          result_kind: "preview.macro-foundation",
          formal_use_allowed: false,
          source_version: "sv_f",
          vendor_version: "vv_f",
          rule_version: "rv_f",
          cache_version: "cv_f",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: { read_target: "duckdb" as const, series: [] },
      })),
      getChoiceMacroLatest,
    });

    expect(await screen.findByTestId("market-data-rate-trend-chart")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByTestId("market-data-echarts-stub").length).toBeGreaterThan(0);
    });

    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("distinguishes Choice macro latest failures from an empty rate trend", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceMacroLatest = vi.fn(async () => {
      throw new Error("choice latest unavailable");
    });

    renderPage({
      ...base,
      getChoiceMacroLatest,
    });

    const curveError = await screen.findByTestId("market-data-rate-trend-chart");
    await waitFor(() => {
      expect(curveError).toHaveTextContent("图表数据载入失败");
    });
    expect(screen.queryByTestId("market-data-rate-trend-empty")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("hides fx analysis subsection while still fetching FX payloads for KPIs", async () => {
    const base = createApiClient({ mode: "mock" });
    const getFxAnalytical = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_fx_analytical_test",
        basis: "analytical" as const,
        result_kind: "fx.analytical.groups",
        formal_use_allowed: false,
        source_version: "sv_fx_analytical_test",
        vendor_version: "vv_fx_analytical_test",
        rule_version: "rv_fx_analytical_v1",
        cache_version: "cv_fx_analytical_v1",
        quality_flag: "warning" as const,
        vendor_status: "ok" as const,
        fallback_mode: "latest_snapshot" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T09:10:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        groups: [
          {
            group_key: "middle_rate" as const,
            title: "Analytical FX: middle-rates",
            description:
              "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam.",
            series: [
              {
                group_key: "middle_rate" as const,
                series_id: "FX.USD.CNY",
                series_name: "USD/CNY middle-rate observation",
                trade_date: "2026-04-11",
                value_numeric: 7.21,
                frequency: "daily",
                unit: "CNY",
                source_version: "sv_fx_analytical_test",
                vendor_version: "vv_fx_analytical_test",
                refresh_tier: "stable" as const,
                fetch_mode: "date_slice" as const,
                fetch_granularity: "batch" as const,
                policy_note: "analytical middle-rate observation only",
                quality_flag: "ok" as const,
                latest_change: 0.01,
                recent_points: [
                  {
                    trade_date: "2026-04-11",
                    value_numeric: 7.21,
                    source_version: "sv_fx_analytical_test",
                    vendor_version: "vv_fx_analytical_test",
                    quality_flag: "ok" as const,
                  },
                  {
                    trade_date: "2026-04-10",
                    value_numeric: 7.2,
                    source_version: "sv_fx_analytical_prev",
                    vendor_version: "vv_fx_analytical_prev",
                    quality_flag: "ok" as const,
                  },
                ],
              },
            ],
          },
          {
            group_key: "fx_index" as const,
            title: "Analytical FX: indices",
            description:
              "RMB index / estimate index series stay analytical-only and never flow into formal FX.",
            series: [
              {
                group_key: "fx_index" as const,
                series_id: "FX.RMB.INDEX",
                series_name: "RMB basket index",
                trade_date: "2026-04-11",
                value_numeric: 101.32,
                frequency: "daily",
                unit: "index",
                source_version: "sv_fx_analytical_test",
                vendor_version: "vv_fx_analytical_test",
                refresh_tier: "fallback" as const,
                fetch_mode: "latest" as const,
                fetch_granularity: "single" as const,
                policy_note: "analytical index observation only",
                quality_flag: "warning" as const,
                latest_change: null,
                recent_points: [],
              },
            ],
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getFxAnalytical,
    });

    // 外汇分析 payload 仍在首屏拉取（KPI 与覆盖摘要共用），懒加载策略不回退。
    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
    });
    // 驾驶舱主列不再平铺外汇分析组。
    expect(screen.queryByTestId("market-data-fx-series-deck")).not.toBeInTheDocument();
    expect(screen.queryByText("外汇分析：中间价")).not.toBeInTheDocument();

    // 从入口卡进入序列浏览器并切到外汇域。
    fireEvent.click(screen.getByTestId("market-data-series-library-entry"));
    expect(await screen.findByTestId("market-data-explorer-view")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("market-data-explorer-domain-fx"));

    expect(await screen.findByTestId("market-data-fx-tier-rail")).toHaveTextContent("2 组");
    expect(screen.getByTestId("market-data-fx-explorer-group-middle_rate")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-fx-group-card-middle_rate")).toBeInTheDocument();
    expect(screen.getAllByText("外汇分析：中间价").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("market-data-fx-section-meta")).not.toBeInTheDocument();
    // 浏览器视图复用同一查询缓存：切换 domain 不重复发起外汇请求。
    expect(getFxAnalytical).toHaveBeenCalledTimes(1);
  });

  it("renders macro-bond linkage as an analytical summary with an explicit report date", async () => {
    // 方案裁决 #10：明细读面（相关性矩阵、利差槽位、传导链路）归 /cross-asset；
    // 本页保留 PAGE-MKT-001 §B 要求的环境/组合摘要与 analytical 警示。
    const observer = stubIntersectionObserver();
    const client = createApiClient({ mode: "mock" });

    renderPage(client);

    const card = await screen.findByTestId("market-data-linkage-summary-card");
    const caveat = screen.getByTestId("market-data-linkage-caveat");
    expect(caveat).toHaveTextContent("分析口径");
    expect(caveat).toHaveTextContent("非正式口径");
    expect(caveat).toHaveTextContent("分析估算");

    act(() => {
      observer.triggerAll(true);
    });

    await waitFor(() =>
      expect(screen.getByTestId("market-data-linkage-summary-composite")).toHaveTextContent("-0.11"),
    );
    // rate_direction 后端枚举中文化：falling → 下行。
    const direction = screen.getByTestId("market-data-linkage-summary-direction");
    expect(direction).toHaveTextContent("下行");
    expect(direction).not.toHaveTextContent("falling");
    expect(screen.getByTestId("market-data-linkage-summary-impact")).toHaveTextContent("有估算");
    expect(screen.getByTestId("market-data-linkage-summary-report-date")).toHaveTextContent(
      "报告日期",
    );
    expect(screen.getByTestId("market-data-linkage-summary-warnings")).toBeInTheDocument();
    expect(within(card).getByTestId("market-data-linkage-summary-link")).toHaveAttribute(
      "href",
      CROSS_ASSET_LINKAGE_HREF,
    );
    // 明细锚点不得在本页复活。
    expect(screen.queryByTestId("market-data-macro-spread-slot-5Y")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-linkage-spreads-audit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-linkage-top-correlations")).not.toBeInTheDocument();
  });

  it("labels the linkage summary with the payload report date and falls back to the requested date", async () => {
    // 跨页 report_date 口径风险（方案 §8-2）：摘要卡必须显式标注日期，载荷日期优先于请求侧日期。
    const observer = stubIntersectionObserver();
    const base = createApiClient({ mode: "mock" });
    const getMacroBondLinkageAnalysis = vi.fn(async (options: { reportDate: string }) => {
      const envelope = await base.getMacroBondLinkageAnalysis(options);
      return {
        ...envelope,
        result: { ...envelope.result, report_date: "2026-01-05" },
      };
    });

    renderPage({ ...base, getMacroBondLinkageAnalysis });

    const reportDate = await screen.findByTestId("market-data-linkage-summary-report-date");
    // 载荷未回时回退请求侧报告日，不留空、不提前展示载荷日期。
    await waitFor(() => {
      expect(reportDate).toHaveTextContent(/报告日期 \d{4}-\d{2}-\d{2}/);
    });
    expect(reportDate).not.toHaveTextContent("2026-01-05");

    act(() => {
      observer.triggerAll(true);
    });

    await waitFor(() => {
      expect(reportDate).toHaveTextContent("报告日期 2026-01-05");
    });
  });

  it("discloses linkage summary loading and failure states without dropping the analytical caveat", async () => {
    const observer = stubIntersectionObserver();
    const base = createApiClient({ mode: "mock" });
    let failLinkage: ((reason: Error) => void) | null = null;
    const getMacroBondLinkageAnalysis = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<ApiClient["getMacroBondLinkageAnalysis"]>>>((_resolve, reject) => {
          failLinkage = reject;
        }),
    );

    renderPage({ ...base, getMacroBondLinkageAnalysis });

    expect(await screen.findByTestId("market-data-linkage-summary-card")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-linkage-summary-loading")).not.toBeInTheDocument();

    act(() => {
      observer.triggerAll(true);
    });

    expect(await screen.findByTestId("market-data-linkage-summary-loading")).toHaveTextContent(
      "加载中",
    );

    const rejectLinkage = failLinkage as ((reason: Error) => void) | null;
    expect(rejectLinkage).not.toBeNull();
    if (!rejectLinkage) {
      throw new Error("Expected linkage rejecter to be registered");
    }
    await act(async () => {
      rejectLinkage(new Error("macro-bond linkage upstream unavailable"));
    });

    expect(await screen.findByTestId("market-data-linkage-summary-error")).toHaveTextContent(
      "加载失败",
    );
    // 失败态仍显式缺失为 EM_DASH，且 analytical 警示不可随失败消失。
    expect(screen.getByTestId("market-data-linkage-summary-composite")).toHaveTextContent(EM_DASH);
    expect(screen.getByTestId("market-data-linkage-summary-direction")).toHaveTextContent(EM_DASH);
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("非正式口径");
  });

  it("redirects the retired linkage-correlation hash to the cross-asset linkage anchor", async () => {
    // 旧锚点兼容（方案 §2）：#market-data-linkage-correlation 不再滚动本页，改为跨页跳转。
    stubIntersectionObserver();
    window.location.hash = "#market-data-linkage-correlation";

    renderPageWithLocationProbe(createApiClient({ mode: "mock" }));

    await waitFor(() => {
      expect(screen.getByTestId("market-data-test-location")).toHaveTextContent(
        CROSS_ASSET_LINKAGE_HREF,
      );
    });
  });

  it("treats degraded refresh as terminal, discloses it, and refetches market-data queries", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(() => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(() => base.getChoiceMacroLatest());
    const getFxAnalytical = vi.fn(() => base.getFxAnalytical());
    const getNcdFundingProxy = vi.fn(() => base.getNcdFundingProxy());
    const getMacroBondLinkageAnalysis = vi.fn((options: { reportDate: string }) =>
      base.getMacroBondLinkageAnalysis(options),
    );
    const refreshChoiceMacro = vi.fn(async () => ({
      status: "queued",
      run_id: "run-market-data-1",
      detail: null,
      error_message: null,
    }));
    const getChoiceMacroRefreshStatus = vi.fn(async () => ({
      status: "degraded",
      run_id: "run-market-data-1",
      detail: null,
      error_message: null,
    }));

    let completeRefresh: (() => void) | null = null;
    vi.mocked(runPollingTask).mockImplementation(async ({ start, getStatus, onUpdate }) => {
      const started = await start();
      onUpdate?.(started);
      await new Promise<void>((resolve) => {
        completeRefresh = resolve;
      });
      const completed = await getStatus(started.run_id ?? "");
      onUpdate?.(completed);
      return completed;
    });

    const { queryClient } = renderPageWithQueryClient({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getFxAnalytical,
      getNcdFundingProxy,
      getMacroBondLinkageAnalysis,
      refreshChoiceMacro,
      getChoiceMacroRefreshStatus,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    // 全量套件并行负载下 refetch 调度可超过 RTL 默认 1s 超时，显式放宽消除时序抖动。
    const REFRESH_WAIT = { timeout: 5000 } as const;
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
      expect(getNcdFundingProxy).toHaveBeenCalledTimes(1);
      expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalled();
    }, REFRESH_WAIT);

    await waitFor(() => {
      for (const queryKey of [
        ["market-data", "macro-foundation", "mock"],
        ["workbench-shell", "choice-macro-latest", "mock"],
        ["market-data", "fx-analytical", "mock"],
        ["market-data", "ncd-funding-proxy", "mock"],
      ] as const) {
        const queryState = queryClient.getQueryState(queryKey);
        expect(queryState?.status).toBe("success");
        expect(queryState?.fetchStatus).toBe("idle");
      }
    }, REFRESH_WAIT);

    fireEvent.click(screen.getByTestId("market-data-refresh-btn"));

    await waitFor(() => {
      expect(refreshChoiceMacro).toHaveBeenCalledWith(30);
      expect(screen.getByTestId("market-data-refresh-btn")).toBeDisabled();
      // 刷新状态最多两处：hero 状态条一处 + 数据状态面板"数据运维"组一处。
      expect(screen.getAllByText("queued · run-market-data-1").length).toBeLessThanOrEqual(2);
    }, REFRESH_WAIT);
    const pollingOptions = vi.mocked(runPollingTask).mock.calls[0]?.[0];
    expect(pollingOptions?.isTerminal?.("partial")).toBe(true);
    expect(pollingOptions?.isTerminal?.("degraded")).toBe(true);
    expect(pollingOptions?.isTerminal?.("failed")).toBe(true);

    const finishRefresh = completeRefresh as (() => void) | null;
    expect(finishRefresh).not.toBeNull();
    if (!finishRefresh) {
      throw new Error("Expected refresh completer to be registered");
    }
    finishRefresh();

    await waitFor(() => {
      expect(getChoiceMacroRefreshStatus).toHaveBeenCalledWith("run-market-data-1");
      expect(screen.getByTestId("market-data-refresh-btn")).not.toBeDisabled();
      // 刷新状态最多两处：hero 状态条一处 + 数据状态面板"数据运维"组一处。
      expect(screen.getAllByText("刷新完成，但数据质量需复核").length).toBeLessThanOrEqual(2);
    }, REFRESH_WAIT);

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(2);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(2);
      expect(getFxAnalytical).toHaveBeenCalledTimes(2);
      expect(getNcdFundingProxy).toHaveBeenCalledTimes(2);
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(1);
    }, REFRESH_WAIT);
  });

  it("surfaces the governed refresh deadline error returned by polling", async () => {
    const base = createApiClient({ mode: "mock" });
    const refreshChoiceMacro = vi.fn(async () => ({
      status: "queued",
      run_id: "run-market-data-deadline",
      detail: null,
      error_message: null,
    }));
    const deadlineMessage =
      "Choice macro refresh terminal status is unavailable after its governed deadline.";
    vi.mocked(runPollingTask).mockImplementationOnce(async ({ start }) => {
      await start();
      throw new Error(deadlineMessage);
    });

    renderPage({
      ...base,
      refreshChoiceMacro,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("market-data-refresh-btn"));

    await waitFor(() => {
      expect(refreshChoiceMacro).toHaveBeenCalledWith(30);
      // 刷新错误最多两处：hero 状态条一处 + 数据状态面板"数据运维"组一处。
      expect(screen.getAllByText(deadlineMessage).length).toBeLessThanOrEqual(2);
      expect(screen.getByTestId("market-data-refresh-btn")).not.toBeDisabled();
    });
  });

  it("registers section-level refresh policy without pulling stable/date-slice sections into fallback polling", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(() => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        quality_flag: "warning",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "M002",
            series_name: "DR007",
            refresh_tier: "fallback",
            fetch_mode: "latest",
            quality_flag: "warning",
          }),
        ],
      },
    }));
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        result_kind: "market_data.rates",
        vendor_status: "ok",
        fallback_mode: "none",
        quality_flag: "ok",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            refresh_tier: "stable",
            fetch_mode: "date_slice",
            quality_flag: "ok",
          }),
        ],
      },
    }));
    const getFxAnalytical = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "fx.analytical.groups",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        groups: [],
      },
    }));
    const getNcdFundingProxy = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "market_data.ncd_proxy",
        formal_use_allowed: false,
      }),
      result: {
        as_of_date: "2026-05-21",
        proxy_label: "test ncd proxy",
        is_actual_ncd_matrix: false,
        formal_ncd_matrix_status: FORMAL_NCD_MATRIX_BLOCKED_STATUS,
        rows: [],
        warnings: [],
      },
    }));
    const getMacroBondLinkageAnalysis = vi.fn(async (options: { reportDate: string }) => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro_bond_linkage.analysis",
        formal_use_allowed: false,
        quality_flag: "warning",
      }),
      result: {
        report_date: options.reportDate,
        environment_score: {},
        top_correlations: [],
        portfolio_impact: {},
        warnings: [],
        computed_at: "2026-05-21T09:00:00Z",
      },
    }));
    const { queryClient } = renderPageWithQueryClient({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getMarketDataRates,
      getFxAnalytical,
      getNcdFundingProxy,
      getMacroBondLinkageAnalysis,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
    });

    const macroLatest = queryClient.getQueryCache().find({
      queryKey: ["workbench-shell", "choice-macro-latest", "mock"],
      exact: true,
    });
    const formalRates = queryClient.getQueryCache().find({
      queryKey: ["market-data", "formal-rates", "mock"],
      exact: false,
    });
    const catalog = queryClient.getQueryCache().find({
      queryKey: ["market-data", "macro-foundation", "mock"],
      exact: true,
    });

    expect(
      typeof macroLatest?.observers[0]?.options.refetchInterval === "function"
        ? macroLatest.observers[0].options.refetchInterval(macroLatest)
        : macroLatest?.observers[0]?.options.refetchInterval,
    ).toBe(3 * 60 * 1000);
    expect(
      typeof formalRates?.observers[0]?.options.refetchInterval === "function"
        ? formalRates.observers[0].options.refetchInterval(formalRates)
        : formalRates?.observers[0]?.options.refetchInterval,
    ).toBe(false);
    expect(
      typeof catalog?.observers[0]?.options.refetchInterval === "function"
        ? catalog.observers[0].options.refetchInterval(catalog)
        : catalog?.observers[0]?.options.refetchInterval,
    ).toBe(false);
  });

  it("updates shell filter state locally without changing the current query contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(() => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(() => base.getChoiceMacroLatest());
    const getLivermoreStrategy = vi.fn((options?: { asOfDate?: string }) =>
      base.getLivermoreStrategy(options),
    );

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });

    changeMarketDataWatchDate("2026-03-01");

    const curveFilter = screen.getByTestId("market-data-curve-filter");
    const curveSelector = curveFilter.querySelector(".ant-select-selector");
    if (!curveSelector) {
      throw new Error("curve select shell not found");
    }
    fireEvent.mouseDown(curveSelector);
    // rc-select also exposes a hidden a11y option; click the titled visual option.
    const curveOption = await screen.findByTitle("国债");
    fireEvent.click(curveOption);
    await waitFor(() => {
      expect(screen.getByTestId("market-data-rate-curve-lock")).toHaveTextContent("国债曲线");
    });

    const sourceFilter = screen.getByTestId("market-data-source-filter");
    const sourceSelector = sourceFilter.querySelector(".ant-select-selector");
    if (!sourceSelector) {
      throw new Error("source select shell not found");
    }
    fireEvent.mouseDown(sourceSelector);
    const sourceOption = await screen.findByTitle("Choice");
    fireEvent.click(sourceOption);
    await waitFor(() => {
      expect(sourceFilter).toHaveTextContent("Choice");
    });

    // 02 区 Tab 与信用利差读面已退役（方案裁决 #4）：筛选只影响前端选择，
    // 不改变 API 查询参数，也不再触发额外拉取；Livermore 端点本页不再调用。
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
    expect(getLivermoreStrategy).not.toHaveBeenCalled();
  });

  it("keeps the hero data date tied to the formal rates result date instead of the selected watch date", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_formal_rates_status_date_test",
        resolved_report_date: "2026-04-30",
        as_of_date: "2026-04-30",
        fallback_date: null,
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "EMM00166466",
            series_name: "中债国债到期收益率:10年",
            trade_date: "2026-04-30",
            value_numeric: 1.94,
          }),
          buildMacroPoint({
            series_id: "EMM00166502",
            series_name: "中债政策性金融债到期收益率(国开行)10年",
            trade_date: "2026-04-30",
            value_numeric: 2.05,
          }),
        ],
      },
    }));

    renderPage({
      ...base,
      getMarketDataRates,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
    });
    // 先等正式利率结果日同步落定，再改观察日，避免受控输入在提交间隙被回写。
    await waitFor(() => {
      expect(screen.getByTestId("market-data-hero-date-note")).toHaveTextContent("2026-04-30");
    });

    changeMarketDataWatchDate("2026-03-01");

    await waitFor(() => {
      expect(screen.getByTestId("market-data-hero-date-note")).toHaveTextContent("2026-04-30");
      expect(screen.getByTestId("market-data-hero-date-note")).not.toHaveTextContent("2026-03-01");
    });
  });

  // Livermore 的门控/板块/候选/stale 诊断/保留面文案断言随读面迁往 /cross-asset，
  // 由 CrossAssetPage.test.tsx 覆盖；本页只保留导航证据卡与"零策略请求"断言。

  it("renders the market-data cockpit sections after the IA split", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-hero")).toHaveTextContent("市场数据");
    expect(screen.getByText("利率行情")).toBeInTheDocument();
    // 曲线走势并入 01 区次行；02 区三 Tab 与利差明细已退役。
    expect(screen.getByTestId("market-data-rate-trend-panel")).toHaveTextContent("收益率走势");
    expect(screen.queryByTestId("market-data-linkage-spread-table")).not.toBeInTheDocument();
    // "资金市场"同时出现在 03 区卡标题与数据状态面板线路状态行，允许多处命中。
    expect(screen.getAllByText("资金市场").length).toBeGreaterThan(0);
    expect(screen.getAllByText("国债期货").length).toBeGreaterThan(0);
    expect(screen.getByText("同业存单")).toBeInTheDocument();
    // 扩展终端三表在懒挂载点物化后才进 DOM（02 区退役后本用例不再有先行的 await）。
    expect(await screen.findByText("债券成交明细（现券）")).toBeInTheDocument();
    expect(screen.getByText("信用债成交明细")).toBeInTheDocument();
    // 序列库入口卡与两张摘要/证据卡构成主列尾部。
    expect(screen.getByTestId("market-data-series-library-entry")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-summary-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-strategy-evidence-card")).toBeInTheDocument();
  });

  it("loads supply-auction calendar events into the first-screen event tape", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(base.getResearchCalendarEvents);

    renderPage({
      ...base,
      getResearchCalendarEvents,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "事件日历", hidden: true })).not.toBeInTheDocument();
  });

  it("mounts the analytical news-and-calendar summary card on the cockpit", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(base.getResearchCalendarEvents);

    renderPage({ ...base, getResearchCalendarEvents });

    const summary = await screen.findByTestId("market-data-news-calendar-summary");
    expect(summary).toHaveTextContent("资讯与日历");
    expect(summary).toHaveTextContent("分析口径");
    expect(summary).toHaveTextContent("完整日历见新闻事件页");
    // mock 日历返回 supply/auction/macro 三条，均属利率/供给口径，全部渲染为单行事件。
    expect(await within(summary).findAllByTestId("market-data-news-calendar-item")).toHaveLength(3);
    expect(getResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: expect.any(String) });
  });

  it("renders an explicit Shibor proxy in the NCD panel instead of pretending it is a live NCD matrix", async () => {
    const base = createApiClient({ mode: "mock" });
    const getNcdFundingProxy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_ncd_proxy_test",
        basis: "analytical" as const,
        result_kind: "market_data.ncd_proxy",
        formal_use_allowed: false,
        source_version: "sv_ncd_proxy_test",
        vendor_version: "vv_tushare_shibor",
        rule_version: "rv_ncd_proxy_v1",
        cache_version: "cv_ncd_proxy_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-23T10:00:00Z",
      },
      result: {
        as_of_date: "2026-06-09",
        proxy_label: "Choice/Tushare Shibor funding proxy",
        is_actual_ncd_matrix: false,
        formal_ncd_matrix_status: FORMAL_NCD_MATRIX_BLOCKED_STATUS,
        rows: [
          {
            row_key: "shibor_fixing",
            label: "Shibor fixing",
            "1M": 1.427,
            "3M": 1.4144,
            "6M": 1.4299,
            "9M": 1.45,
            "1Y": 1.43,
            quote_count: null,
          },
        ],
        warnings: [
          "Using landed Choice Shibor with Tushare fallback for 9M; fallback date 2026-05-28; quote medians unavailable.",
          "Proxy only; not actual NCD issuance matrix.",
        ],
      },
    }));

    const { queryClient } = renderPageWithQueryClient({
      ...base,
      getNcdFundingProxy,
    });

    const ncdPanel = await screen.findByTestId("market-data-ncd-matrix");
    await waitFor(() => {
      expect(getNcdFundingProxy).toHaveBeenCalled();
      expect(
        queryClient.getQueryState(["market-data", "ncd-funding-proxy", "mock"])?.status,
      ).toBe("success");
    });
    await waitFor(() => {
      expect(within(ncdPanel).getByText(/Choice\/Tushare Shibor funding proxy/)).toBeInTheDocument();
    });
    expect(within(ncdPanel).getByText("Shibor fixing")).toBeInTheDocument();
    expect(screen.queryByText("Quote median")).not.toBeInTheDocument();
    // 两条警示各自成行（中文化 + 原文 title），逐条可见。
    expect(
      (await screen.findAllByText(/报价中位数不可用|不是真实存单发行矩阵/)).length,
    ).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("1.427")).toBeInTheDocument();
    expect(await screen.findByText(/回退日期 2026-05-28/)).toBeInTheDocument();
    const evidenceRail = screen.getByTestId("market-data-macro-evidence-rail");
    expect(evidenceRail).toHaveTextContent("存单代理");
    expect(evidenceRail).toHaveTextContent("仅分析使用");
    expect(evidenceRail).not.toHaveTextContent("sv_ncd_proxy_test");
    expect(screen.queryByTestId("market-data-ncd-live-meta")).not.toBeInTheDocument();
  });

  it("exposes chart view toggles for rate quotes and hides the ncd heatmap for single-row proxies", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-rate-quote-view-toggle")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-term-structure-chart")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-rate-trend-chart")).toBeInTheDocument();
    // mock NCD 为单行矩阵：热力无对比维度，视图切换与热力图收敛，仅保留表格。
    await screen.findByTestId("market-data-ncd-matrix");
    expect(screen.queryByTestId("market-data-ncd-view-toggle")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-ncd-heatmap")).not.toBeInTheDocument();
  });
});
