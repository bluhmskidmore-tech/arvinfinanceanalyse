import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  BondDashboardBundlePayload,
  BondDashboardBundleSectionEnvelopeMap,
  BondDashboardBundleSectionId,
  ResultMeta,
} from "../api/contracts";
import { BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS } from "../features/bond-dashboard/bondDashboardBundleModel";
import { AssetStructurePie } from "../features/bond-dashboard/components/AssetStructurePie";
import { CreditRatingBlocks } from "../features/bond-dashboard/components/CreditRatingBlocks";
import { IndustryTable } from "../features/bond-dashboard/components/IndustryTable";
import { MaturityStructureChart } from "../features/bond-dashboard/components/MaturityStructureChart";
import { RiskIndicatorsPanel } from "../features/bond-dashboard/components/RiskIndicatorsPanel";
import BondDashboardPage from "../features/bond-dashboard/pages/BondDashboardPage";
import { BOND_SECTION_READY } from "../features/bond-dashboard/sectionStatus";
import { EM_DASH, formatRawAsNumeric } from "../utils/format";
import {
  PORTFOLIO_CROSS_PAGE_EXPECTED,
  PORTFOLIO_CROSS_PAGE_REPORT_DATE,
  portfolioCrossPageBondHomeSummary,
  portfolioCrossPageEnvelope,
} from "./portfolioCrossPageGoldenSample";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <div data-testid="bond-dashboard-echarts-stub" data-option={JSON.stringify(option)} />
  ),
}));

function resultMeta(resultKind: string, overrides: Partial<ResultMeta> = {}): ResultMeta {
  const isBondHeadline = resultKind === "bond_dashboard.headline_kpis";
  return {
    trace_id: `tr_${resultKind}`,
    basis: isBondHeadline ? "analytical" : "formal",
    result_kind: resultKind,
    formal_use_allowed: !isBondHeadline,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: isBondHeadline ? "warning" : "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
    ...overrides,
  };
}

const yuan = (raw: number | null) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number | null) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const ratio = (raw: number | null) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
const dv01 = (raw: number | null) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

type BondDashboardBundleSectionEnvelope =
  BondDashboardBundleSectionEnvelopeMap[BondDashboardBundleSectionId];

async function fetchMockedBundleSection(
  client: ApiClient,
  section: BondDashboardBundleSectionId,
  reportDate: string,
): Promise<[BondDashboardBundleSectionId, BondDashboardBundleSectionEnvelope]> {
  if (section === "dates") return [section, await client.getBondDashboardDates()];
  if (section === "headline-kpis") return [section, await client.getBondDashboardHeadlineKpis(reportDate)];
  if (section === "home-summary") return [section, await client.getBondDashboardHomeSummary(reportDate)];
  if (section === "asset-structure") return [section, await client.getBondDashboardAssetStructure(reportDate, "bond_type")];
  if (section === "asset-structure-rating") return [section, await client.getBondDashboardAssetStructure(reportDate, "rating")];
  if (section === "asset-structure-portfolio-name") {
    return [section, await client.getBondDashboardAssetStructure(reportDate, "portfolio_name")];
  }
  if (section === "asset-structure-tenor-bucket") {
    return [section, await client.getBondDashboardAssetStructure(reportDate, "tenor_bucket")];
  }
  if (section === "yield-distribution") return [section, await client.getBondDashboardYieldDistribution(reportDate)];
  if (section === "portfolio-comparison") return [section, await client.getBondDashboardPortfolioComparison(reportDate)];
  if (section === "spread-analysis") return [section, await client.getBondDashboardSpreadAnalysis(reportDate)];
  if (section === "maturity-structure") return [section, await client.getBondDashboardMaturityStructure(reportDate)];
  if (section === "industry-distribution") return [section, await client.getBondDashboardIndustryDistribution(reportDate)];
  if (section === "risk-indicators") return [section, await client.getBondDashboardRiskIndicators(reportDate)];
  return [section, await client.getBondBusinessTypeMetrics({ reportDate })];
}

/**
 * `transform` 让单条用例改写 bundle 的 result（去掉某个分区、写 section_statuses
 * 等），用于覆盖「请求已结束但该分区没回数」这类分区级状态；不传时行为与之前一致。
 */
function mockBondDashboardBundleFromClient(
  client: ApiClient,
  transform?: (result: BondDashboardBundlePayload) => BondDashboardBundlePayload,
) {
  return vi.spyOn(client, "fetchBondDashboardBundle").mockImplementation(async (reportDate, sections) => {
    const normalizedReportDate = reportDate?.trim() ?? "";
    const entries = await Promise.all(
      sections.map((section) => fetchMockedBundleSection(client, section, normalizedReportDate)),
    );
    const sectionEnvelopes: Partial<BondDashboardBundleSectionEnvelopeMap> = {};
    for (const [section, envelope] of entries) {
      (sectionEnvelopes as Record<BondDashboardBundleSectionId, BondDashboardBundleSectionEnvelope>)[section] =
        envelope;
    }
    const result: BondDashboardBundlePayload = {
      report_date: normalizedReportDate || null,
      requested_sections: [...sections],
      sections: sectionEnvelopes,
    };
    return {
      data_source: "bond_analytics_facts",
      result_meta: resultMeta("bond_dashboard.bundle"),
      result: transform ? transform(result) : result,
    };
  });
}

function withoutSection(
  sections: Partial<BondDashboardBundleSectionEnvelopeMap>,
  omitted: BondDashboardBundleSectionId,
): Partial<BondDashboardBundleSectionEnvelopeMap> {
  const next = { ...sections };
  delete next[omitted];
  return next;
}

function renderBondDashboard(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter>
          <BondDashboardPage />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("BondDashboardPage", () => {
  it("shows title and KPI cards when mock data loads", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "债券总览" })).toBeInTheDocument();
    await waitFor(() => {
      const conclusion = screen.getByTestId("bond-dashboard-conclusion");
      expect(conclusion).toHaveTextContent("当前结论");
      expect(conclusion).toHaveTextContent("当前信用占比");
      expect(conclusion).toHaveTextContent("总市值");
    });
    // 「债券持仓规模」同时出现在结论 hero 标签与 KPI 格标签（FR-6 双呈现）。
    expect((await screen.findAllByText("债券持仓规模")).length).toBeGreaterThanOrEqual(1);
    const headline = screen.getByTestId("bond-dashboard-headline-kpis");
    const scaleCard = within(headline).getByTestId("bond-dashboard-kpi-total_market_value");
    expect(scaleCard.textContent?.replace(/,/g, "")).toContain("3287.09");
  });

  /*
   * 以下两条锁的是 2026-08-27 组装式重写的成果：首屏 KPI 横带与四张只读表分别
   * 由 KpiStrip / DataTable 原语渲染，页面不再持有私有横带与 antd 表格覆盖。
   * 断言的是原语暴露在 DOM 上的契约（列数属性、语义 table 元素），不是内部结构。
   */
  it("renders the first-screen KPI band through the KpiStrip primitive", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const band = await screen.findByTestId("bond-dashboard-headline-kpis");
    expect(within(band).getAllByTestId(/^bond-dashboard-kpi-/)).toHaveLength(8);
    // 4×2 单框横带、720 以下折 2 列：重构前是页面 CSS 媒体查询，现在是原语入参。
    const strip = band.firstElementChild;
    expect(strip).toHaveAttribute("data-cols-xl", "4");
    expect(strip).toHaveAttribute("data-cols-base", "2");
  });

  it("renders the read-only dashboard tables through the DataTable primitive instead of antd Table", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    // 行业分布 / 组合表现 / 利差分析 / 业务类型加权指标。
    await waitFor(() => {
      expect(screen.getAllByRole("table")).toHaveLength(4);
    });
    expect(container.querySelector(".ant-table")).toBeNull();
    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).toHaveAttribute("scope", "col");
    }
  });

  /*
   * 分区级五态。重构前（以及 2026-08-27 组装式重写的第一轮）这三种情形都落进
   * 「rows 未到达 → 骨架」：请求已结束、分区失败，用户看到的却是「还在加载」。
   * bundle 一直返回 section_statuses / failed_sections（06 区证据披露在用），
   * 这三条锁的是「这份状态确实接到了数据块上」。
   */
  it("surfaces a failed bundle section as an error instead of a ghost skeleton", async () => {
    const client = createApiClient({ mode: "mock" });
    mockBondDashboardBundleFromClient(client, (result) => ({
      ...result,
      sections: withoutSection(result.sections, "industry-distribution"),
      section_statuses: {
        "industry-distribution": { status: "error", message: "行业分布查询超时", duration_ms: 12 },
      },
      failed_sections: ["industry-distribution"],
    }));

    renderBondDashboard(client);

    const table = await screen.findByTestId("bond-dashboard-industry-table");
    await waitFor(() => {
      expect(within(table).getByRole("alert")).toHaveTextContent("行业分布查询超时");
    });
    // 骨架视图的屏幕阅读器文案；出现即说明又退回了「假装在加载」。
    expect(within(table).queryByText("数据载入中")).toBeNull();
  });

  it("treats a silently missing bundle section as an error rather than a pending read", async () => {
    const client = createApiClient({ mode: "mock" });
    // 后端既没给 section_statuses 也没给 failed_sections，分区数据就是没回来。
    mockBondDashboardBundleFromClient(client, (result) => ({
      ...result,
      sections: withoutSection(result.sections, "industry-distribution"),
    }));

    renderBondDashboard(client);

    const table = await screen.findByTestId("bond-dashboard-industry-table");
    await waitFor(() => {
      expect(within(table).getByRole("alert")).toHaveTextContent("该分区未返回数据");
    });
    expect(within(table).queryByText("数据载入中")).toBeNull();
  });

  it("collapses an empty-but-successful bundle section to the empty message", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardIndustryDistribution = async () => ({
      result_meta: resultMeta("bond_dashboard.industry_distribution"),
      result: { report_date: "2026-04-30", total_market_value: yuan(0), items: [] },
    });
    mockBondDashboardBundleFromClient(client, (result) => ({
      ...result,
      section_statuses: {
        "industry-distribution": { status: "ok", message: null, duration_ms: 5 },
      },
    }));

    renderBondDashboard(client);

    const table = await screen.findByTestId("bond-dashboard-industry-table");
    await waitFor(() => {
      expect(within(table).getByText("暂无数据")).toBeInTheDocument();
    });
    expect(within(table).queryByRole("alert")).toBeNull();
    expect(within(table).queryByText("数据载入中")).toBeNull();
  });

  it("refetches blocks when report date changes", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const spy = vi.spyOn(client, "fetchBondDashboardBundle");
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const reportDateInput = await screen.findByRole("combobox", { name: "bond-dashboard-report-date" });
    await waitFor(() => {
      expect(reportDateInput).not.toBeDisabled();
    });
    const initial = spy.mock.calls.length;
    const reportDateSelect = reportDateInput.closest(".ant-select");
    expect(reportDateSelect).not.toBeNull();
    fireEvent.mouseDown(reportDateSelect!.querySelector(".ant-select-selector")!);
    // 弹层改挂 parentElement（getPopupContainer）后，a11y listbox 里的隐藏
    // option 不再可点；按仓库既有写法点带 title 的真实选项节点。
    await user.click(await screen.findByTitle("2026-02-28"));

    await waitFor(() => {
      expect(spy.mock.calls.length).toBeGreaterThan(initial);
    });
  });

  it("surfaces an explicit empty-state note when no report dates are available", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: {
        trace_id: "tr_bond_dashboard_dates_empty",
        basis: "formal",
        result_kind: "bond_dashboard.dates",
        formal_use_allowed: true,
        source_version: "sv_empty",
        vendor_version: "vv_none",
        rule_version: "rv_empty",
        cache_version: "cv_empty",
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        generated_at: "2026-04-19T00:00:00Z",
      },
      result: { report_dates: [] },
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-page-state")).toHaveTextContent("暂无可用报告日");
    });
    expect(screen.getByRole("combobox", { name: "bond-dashboard-report-date" })).toBeDisabled();
  });

  /*
   * 后端不可达（dates 502）时 bundle 查询 enabled=false：禁用态 query 的 isPending
   * 永远为真，2026-09 审计发现 02-05 区因此永远停在「读取中 / 正在载入 / 数据载入中」
   * 骨架。这条锁的是：报告日终态不可用后，各分区露出明确的阻断原因而不是假装在加载。
   */
  it("blocks every data section with an explicit reason instead of an endless skeleton when report dates fail", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => {
      throw new Error("bad gateway");
    };
    const bundleSpy = vi.spyOn(client, "fetchBondDashboardBundle");

    renderBondDashboard(client);

    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-page-state")).toHaveTextContent("报告日加载失败");
    });
    expect(bundleSpy).not.toHaveBeenCalled();

    for (const sectionId of [
      "bond-dashboard-section-structure",
      "bond-dashboard-section-maturity-industry",
      "bond-dashboard-section-portfolio-risk",
      "bond-dashboard-section-business-type",
    ]) {
      const section = document.getElementById(sectionId);
      expect(section).not.toBeNull();
      expect(within(section!).getAllByText("报告日不可用，未发起查询").length).toBeGreaterThan(0);
      expect(within(section!).queryByText("读取中")).toBeNull();
      expect(within(section!).queryByText("正在载入")).toBeNull();
      expect(within(section!).queryByText("数据载入中")).toBeNull();
    }
    // 首屏 KPI 横带同步落到终态占位（EM_DASH），不再是骨架。
    const headline = screen.getByTestId("bond-dashboard-headline-kpis");
    expect(within(headline).getByTestId("bond-dashboard-kpi-total_market_value")).toHaveTextContent(EM_DASH);
    expect(screen.queryByText("正在载入")).toBeNull();
  });

  it("uses backend headline numerics for weighted yield and duration in the portfolio table footer", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(100_000_000_000),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.025656206199),
          weighted_duration: ratio(4.1367831054),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(1000),
          bond_count: 3,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardPortfolioComparison = async () => ({
      result_meta: resultMeta("bond_dashboard.portfolio_comparison"),
      result: {
        report_date: "2026-04-30",
        items: [
          {
            portfolio_name: "Rate + credit",
            total_market_value: yuan(40_000_000_000),
            weighted_ytm: pct(0.035),
            weighted_duration: ratio(5),
            total_dv01: dv01(500),
            bond_count: 2,
          },
          {
            portfolio_name: "Other heavy",
            total_market_value: yuan(60_000_000_000),
            weighted_ytm: pct(0),
            weighted_duration: ratio(0),
            total_dv01: dv01(0),
            bond_count: 1,
          },
        ],
      },
    });
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByRole("heading", { name: "债券总览" });
    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-ytm")).toHaveTextContent("2.57");
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-duration")).toHaveTextContent("4.14");
    });
  });

  it("renders non-zero dashboard values from Numeric API payloads", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(343_822_795_478.69),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.02565621),
          weighted_duration: ratio(4.13678311),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(106_155_944.31),
          bond_count: 251,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators"),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(343_822_795_478.69),
        total_dv01: dv01(106_155_944.31),
        weighted_duration: ratio(4.13678311),
        credit_ratio: ratio(0.29250449),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(31_000_000),
        reinvestment_ratio_1y: ratio(0.12),
      },
    });
    client.getBondDashboardPortfolioComparison = async () => ({
      result_meta: resultMeta("bond_dashboard.portfolio_comparison"),
      result: {
        report_date: "2026-04-30",
        items: [
          {
            portfolio_name: "Core book",
            total_market_value: yuan(343_822_795_478.69),
            weighted_ytm: pct(0.02565621),
            weighted_duration: ratio(4.13678311),
            total_dv01: dv01(106_155_944.31),
            bond_count: 251,
          },
        ],
      },
    });
    client.getBondBusinessTypeMetrics = async () => ({
      result_meta: resultMeta("bond_dashboard.business_type_metrics"),
      result: {
        report_date: "2026-04-30",
        items: [
          {
            name: "Core book",
            market_value: "343822795478.69",
            weighted_avg_ytm: pct(0.02565621),
            weighted_avg_duration: "4.13678311",
            duration_source: "position_duration",
          },
        ],
      },
    });
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const scaleCard = await screen.findByTestId("bond-dashboard-kpi-total_market_value");
    expect(scaleCard.textContent?.replace(/,/g, "")).toContain("3438.23");

    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-conclusion")).toHaveTextContent("29.3%");
      expect(screen.getByTestId("bond-dashboard-risk-row-credit_ratio")).toHaveTextContent("29.25%");
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-ytm")).toHaveTextContent("2.57");
      expect(screen.getByTestId("bond-dashboard-business-type-metrics")).toHaveTextContent("2.57%");
    });
  });

  it("does not turn missing governed numerics into a zero-exposure business conclusion", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(null),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.025),
          weighted_duration: ratio(4.1),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(100),
          bond_count: 1,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators"),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(null),
        total_dv01: dv01(100),
        weighted_duration: ratio(4.1),
        credit_ratio: ratio(null),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(40),
        reinvestment_ratio_1y: ratio(0.12),
      },
    });
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const conclusion = await screen.findByTestId("bond-dashboard-conclusion");
    expect(conclusion).toHaveTextContent("—");
    expect(conclusion).toHaveTextContent("不形成投放状态结论");
    expect(conclusion).not.toHaveTextContent("尚未形成有效持仓");
    expect(conclusion).not.toHaveTextContent("信用占比 0.0%");
  });

  it("surfaces first-screen result_meta degradation for headline and risk envelopes", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis", {
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
        resolved_report_date: "2026-04-29",
        as_of_date: "2026-04-29",
      }),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(100_000_000),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.025),
          weighted_duration: ratio(4.1),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(100),
          bond_count: 1,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators", {
        quality_flag: "warning",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
        resolved_report_date: "2026-04-29",
        as_of_date: "2026-04-29",
      }),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(100_000_000),
        total_dv01: dv01(100),
        weighted_duration: ratio(4.1),
        credit_ratio: ratio(0.4),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(40),
        reinvestment_ratio_1y: ratio(0.12),
      },
    });
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    // 证据面板随分区信封渐进渲染（dates 先到，headline/risk 随 bundle 后到），
    // 降级字段要等 bundle 信封落地后再断言。
    const metaPanel = await screen.findByTestId("bond-dashboard-first-screen-result-meta");
    await waitFor(() => {
      expect(metaPanel).toHaveTextContent("供应商陈旧");
    });
    expect(metaPanel).toHaveTextContent("最新快照降级");
    expect(metaPanel).toHaveTextContent("2026-04-29");
  });

  it("shows a first-screen stale banner when result_meta reports fallback data", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis", {
        quality_flag: "stale",
        fallback_mode: "latest_snapshot",
        requested_report_date: "2026-04-30",
        resolved_report_date: "2026-04-29",
        fallback_date: "2026-04-29",
        as_of_date: "2026-04-29",
      }),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(100_000_000),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.025),
          weighted_duration: ratio(4.1),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(100),
          bond_count: 1,
        },
        prev_kpis: null,
      },
    });
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const banner = await screen.findByTestId("bond-dashboard-stale-banner");
    expect(banner).toHaveTextContent("回退/降级口径");
    expect(banner).toHaveTextContent("请求日 2026-04-30 回退至 2026-04-29");
    expect(banner).toHaveTextContent("回退日期 2026-04-29");
  });

  it("does not show the first-screen stale banner when result_meta is healthy", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis", {
        quality_flag: "ok",
        requested_report_date: "2026-04-30",
        resolved_report_date: "2026-04-30",
        as_of_date: "2026-04-30",
        fallback_date: null,
      }),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(100_000_000),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.025),
          weighted_duration: ratio(4.1),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(100),
          bond_count: 1,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators", {
        quality_flag: "ok",
        requested_report_date: "2026-04-30",
        resolved_report_date: "2026-04-30",
        as_of_date: "2026-04-30",
        fallback_date: null,
      }),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(100_000_000),
        total_dv01: dv01(100),
        weighted_duration: ratio(4.1),
        credit_ratio: ratio(0.4),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(40),
        reinvestment_ratio_1y: ratio(0.12),
      },
    });
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByTestId("bond-dashboard-conclusion");
    expect(screen.queryByTestId("bond-dashboard-stale-banner")).toBeNull();
  });

  it("renders the shared portfolio golden sample on the bond dashboard source page", async () => {
    const client = createApiClient({ mode: "mock" });
    const sample = portfolioCrossPageBondHomeSummary();
    client.getBondDashboardDates = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.dates", {
        report_dates: [PORTFOLIO_CROSS_PAGE_REPORT_DATE],
      });
    client.getBondDashboardHeadlineKpis = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.headline_kpis", sample.headline);
    client.getBondDashboardRiskIndicators = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.risk_indicators", sample.risk);
    client.getBondDashboardPortfolioComparison = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.portfolio_comparison", sample.portfolio_comparison);
    mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const headline = await screen.findByTestId("bond-dashboard-headline-kpis");
    expect(within(headline).getByTestId("bond-dashboard-kpi-total_market_value")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondMarketValueYi,
    );
    expect(within(headline).getByTestId("bond-dashboard-kpi-weighted_duration")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondDuration,
    );
    expect(within(headline).getByTestId("bond-dashboard-kpi-total_dv01")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondDv01Wan,
    );
  });

  it("surfaces candidate metric and risk-source boundaries on the governed dashboard", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const headlineBoundary = await screen.findByTestId("bond-dashboard-headline-candidate-boundary");
    expect(headlineBoundary).toHaveTextContent("MTR-BOND-001");
    expect(headlineBoundary).toHaveTextContent("pending_confirmation=true");
    expect(headlineBoundary).toHaveTextContent("GS-BOND-HEADLINE-A");
    expect(headlineBoundary).toHaveTextContent("非字典级批准");

    const riskBoundary = await screen.findByTestId("bond-dashboard-risk-source-boundary");
    expect(riskBoundary).toHaveTextContent("GAP-BOND-DASH-RISK");
    expect(riskBoundary).toHaveTextContent("不自动继承 GS-RISK-A");
  });

  it("renders credit-rating percentages from ratio Numeric values", () => {
    render(
      <CreditRatingBlocks
        state={BOND_SECTION_READY}
        data={{
          report_date: "2026-04-30",
          group_by: "rating",
          total_market_value: yuan(200),
          items: [
            { category: "AAA", total_market_value: yuan(199), bond_count: 1, percentage: pct(0.995) },
            { category: "AA", total_market_value: yuan(1), bond_count: 1, percentage: pct(0.005) },
          ],
        }}
      />,
    );

    expect(screen.getByText("99.50%")).toBeInTheDocument();
    expect(screen.getByText("0.50%")).toBeInTheDocument();
  });

  it("keeps the risk panel free of KPI-band duplicates and shows 2dp convexity with a full-precision title", () => {
    render(
      <RiskIndicatorsPanel
        state={BOND_SECTION_READY}
        data={{
          report_date: "2026-04-30",
          total_market_value: yuan(343_822_795_478.69),
          total_dv01: dv01(106_155_944.31),
          weighted_duration: ratio(4.13678311),
          credit_ratio: ratio(0.29250449),
          weighted_convexity: ratio(28.80084028),
          total_spread_dv01: dv01(31_000_000),
          reinvestment_ratio_1y: ratio(0.12),
        }}
      />,
    );

    // 组合市值 / DV01 / 加权久期与 01 区 KPI 带逐字同值，面板已去重。
    expect(screen.queryByTestId("bond-dashboard-risk-row-total_market_value")).toBeNull();
    expect(screen.queryByTestId("bond-dashboard-risk-row-total_dv01")).toBeNull();
    expect(screen.queryByTestId("bond-dashboard-risk-row-weighted_duration")).toBeNull();
    expect(screen.getByTestId("bond-dashboard-risk-row-credit_ratio")).toHaveTextContent("29.25%");
    const spreadDv01Row = screen.getByTestId("bond-dashboard-risk-row-total_spread_dv01");
    expect(spreadDv01Row).toHaveTextContent("利差 DV01（万元/bp）");
    expect(spreadDv01Row).toHaveTextContent("3,100.00");

    const convexityRow = screen.getByTestId("bond-dashboard-risk-row-weighted_convexity");
    expect(convexityRow).toHaveTextContent("28.80");
    expect(convexityRow).not.toHaveTextContent("28.8008");
    expect(within(convexityRow).getByTitle("原值 28.80084028")).toBeInTheDocument();
  });

  it("renders industry percentages from ratio Numeric values", () => {
    render(
      <IndustryTable
        state={BOND_SECTION_READY}
        data={{
          report_date: "2026-04-30",
          total_market_value: yuan(1),
          items: [
            {
              industry_name: "金融业",
              total_market_value: yuan(1),
              bond_count: 1,
              percentage: pct(0.005),
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("0.50")).toBeInTheDocument();
  });

  it("uses a segmented asset-structure group control without Ant Tabs overflow controls", () => {
    const onGroupByChange = vi.fn();
    const { container } = render(
      <AssetStructurePie
        state={BOND_SECTION_READY}
        groupBy="bond_type"
        onGroupByChange={onGroupByChange}
        data={{
          report_date: "2026-04-30",
          group_by: "bond_type",
          total_market_value: yuan(200),
          items: [{ category: "Rate", total_market_value: yuan(200), bond_count: 1, percentage: pct(1) }],
        }}
      />,
    );

    expect(container.querySelector(".ant-tabs-nav")).toBeNull();
    expect(container.querySelector(".ant-tabs-nav-more")).toBeNull();

    const groupOptions = container.querySelectorAll(".ant-segmented-item");
    expect(groupOptions).toHaveLength(4);
    fireEvent.click(groupOptions[1]);

    expect(onGroupByChange).toHaveBeenCalledWith("rating");
  });

  it("passes percent-point data to the maturity structure line chart", () => {
    render(
      <MaturityStructureChart
        state={BOND_SECTION_READY}
        data={{
          report_date: "2026-04-30",
          total_market_value: yuan(200),
          items: [
            { maturity_bucket: "7天内", total_market_value: yuan(1), bond_count: 1, percentage: pct(0.005) },
          ],
        }}
      />,
    );

    const option = JSON.parse(screen.getByTestId("bond-dashboard-echarts-stub").dataset.option ?? "{}");
    expect(option.series[1].data).toEqual([0.5]);
  });

  it("loads report dates before the single dashboard bundle", async () => {
    const client = createApiClient({ mode: "mock" });
    const calls: string[] = [];
    client.getBondDashboardDates = async () => {
      calls.push("dates");
      return {
        result_meta: resultMeta("bond_dashboard.dates"),
        result: { report_dates: ["2026-04-30"] },
      };
    };
    const bundleSpy = vi.spyOn(client, "fetchBondDashboardBundle").mockImplementation(async (reportDate, sections, opts) => {
      calls.push("bundle");
      expect(reportDate).toBe("2026-04-30");
      expect(sections).toEqual(BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS);
      expect(opts).toEqual({ industryTopN: 10 });
      return {
        data_source: "bond_analytics_facts",
        result_meta: resultMeta("bond_dashboard.bundle"),
        result: {
          report_date: "2026-04-30",
          requested_sections: [...sections],
          sections: {
            "headline-kpis": {
              result_meta: resultMeta("bond_dashboard.headline_kpis"),
              result: {
                report_date: "2026-04-30",
                prev_report_date: null,
                kpis: {
                  total_market_value: yuan(100_000_000),
                  unrealized_pnl: yuan(0),
                  weighted_ytm: pct(0.025),
                  weighted_duration: ratio(4.1),
                  weighted_coupon: pct(0.02),
                  credit_spread_median: pct(0.01),
                  total_dv01: dv01(100),
                  bond_count: 1,
                },
                prev_kpis: null,
              },
            },
            "risk-indicators": {
              result_meta: resultMeta("bond_dashboard.risk_indicators"),
              result: {
                report_date: "2026-04-30",
                total_market_value: yuan(100_000_000),
                credit_ratio: pct(0.4),
                weighted_duration: ratio(4.1),
                weighted_convexity: ratio(0.03),
                total_dv01: dv01(100),
                total_spread_dv01: dv01(40),
                reinvestment_ratio_1y: pct(0.12),
              },
            },
          },
        },
      };
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(calls).toEqual(["dates", "bundle"]);
    });
    expect(bundleSpy).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId("bond-dashboard-conclusion")).toHaveTextContent("当前结论");
  });

  it("adopts a valid report_date deep-link param instead of the latest date", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-05-31", "2026-04-30"] },
    });
    const bundleSpy = mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={["/bond-dashboard?report_date=2026-04-30"]}>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(bundleSpy).toHaveBeenCalledWith(
        "2026-04-30",
        BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
        { industryTopN: 10 },
      );
    });
    expect(bundleSpy).not.toHaveBeenCalledWith(
      "2026-05-31",
      expect.anything(),
      expect.anything(),
    );
  });

  it("falls back to the latest report date when the report_date param is not an available date", async () => {
    // 覆盖旧版深链的 report_date=- 伪参数：不采用、不发伪日期请求，回退最新报告日。
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-05-31", "2026-04-30"] },
    });
    const bundleSpy = mockBondDashboardBundleFromClient(client);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={["/bond-dashboard?report_date=-"]}>
            <BondDashboardPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(bundleSpy).toHaveBeenCalledWith(
        "2026-05-31",
        BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS,
        { industryTopN: 10 },
      );
    });
    expect(bundleSpy).not.toHaveBeenCalledWith("-", expect.anything(), expect.anything());
  });

  it("scrolls to the deep-linked dashboard section anchor after mount", async () => {
    const originalScrollIntoView = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollIntoView",
    );
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    try {
      const client = createApiClient({ mode: "mock" });
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
      });

      render(
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>
            <MemoryRouter
              initialEntries={["/bond-dashboard#bond-dashboard-section-portfolio-risk"]}
            >
              <BondDashboardPage />
            </MemoryRouter>
          </ApiClientProvider>
        </QueryClientProvider>,
      );

      await waitFor(() => {
        expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" });
      });
      expect(scrollIntoView.mock.instances.at(-1)).toBe(
        document.getElementById("bond-dashboard-section-portfolio-risk"),
      );
    } finally {
      if (originalScrollIntoView) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScrollIntoView);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
      }
    }
  });
});
