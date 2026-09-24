import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import {
  mapToHomeBodyView,
  type DashboardHomeBodyView,
  type MapToHomeBodyViewInput,
} from "./dashboardHomeBodyView";
import type { HomeGovernanceStatusKind } from "./dashboardHomeFirstScreenTypes";
import type { HomeMarketTicker } from "./dashboardHomeMarket";
import { DashboardHomeOptionTwoSupportBand } from "./DashboardHomeOptionTwoSupportBand";

function buildInput(reportDate = "2026-04-30"): MapToHomeBodyViewInput {
  return {
    reportDate,
    useMockFallback: false,
    attribution: null,
    creditSpreadMigration: null,
    returnDecomposition: null,
    campisiFourEffects: null,
    yieldCurveTermStructure: null,
    marketPoints: [],
    assetStructure: null,
    ratingStructure: null,
    maturityStructure: null,
    industryDistribution: null,
    homeSummaryMeta: null,
    yieldDistribution: null,
    portfolioComparison: null,
    spreadAnalysis: null,
    businessType: null,
    riskIndicators: null,
    topHoldings: null,
    topHoldingsLoading: false,
    topHoldingsError: false,
    positionChanges: null,
    positionChangesLoading: false,
    positionChangesError: false,
    researchReports: null,
    researchReportsLoading: false,
    researchReportsError: false,
    incomeTrend: null,
    incomeTrendLoading: false,
    incomeTrendError: false,
    calendarEvents: null,
    calendarLoading: false,
    calendarError: false,
    calendarStartDate: "2026-04-23",
    calendarEndDate: "2026-05-14",
    macroNewsEvents: null,
    macroNewsFallbackEvents: null,
    macroNewsLoading: false,
    macroNewsError: false,
  };
}

function buildView(): DashboardHomeBodyView {
  return mapToHomeBodyView(buildInput());
}

function fundingTicker(
  id: string,
  overrides: Partial<HomeMarketTicker> = {},
): HomeMarketTicker {
  return {
    id,
    label: id,
    value: "1.50%",
    delta: "+4bp",
    deltaTone: "up",
    sparkline: [],
    tradeDate: "2026-07-29",
    valueNumeric: 1.5,
    unit: "%",
    qualityFlag: "ok",
    vendorName: "Choice",
    policyNote: "governed funding source",
    sourceVersion: "sv_funding_test",
    ...overrides,
  };
}

function renderBand(
  view: DashboardHomeBodyView,
  dataStatusKind: HomeGovernanceStatusKind = "ok",
) {
  return render(
    <MemoryRouter>
      <DashboardHomeOptionTwoSupportBand
        view={view}
        dataStatusKind={dataStatusKind}
      />
    </MemoryRouter>,
  );
}

describe("DashboardHomeOptionTwoSupportBand", () => {
  it("shows the governed curve source, dates, four tenors, and honest row gaps", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      marketContext: {
        ...base.marketContext,
        sourceLabel: "来源：正式曲线服务",
        asOfLabel: "数据截至 2026-04-30",
        statusLabel: "来源状态：正式链路有提示",
        refreshLabel: "刷新：随报告日查询自动更新",
        curveTable: {
          title: "国债收益率",
          asOfLabel: "2026-04-30",
          emptyMessage: null,
          rows: [
            {
              tenor: "1Y",
              yieldLabel: "1.60%",
              deltaLabel: "-1.20",
              deltaTone: "down",
            },
            {
              tenor: "3Y",
              yieldLabel: "—",
              deltaLabel: "—",
              deltaTone: "muted",
            },
            {
              tenor: "5Y",
              yieldLabel: "1.80%",
              deltaLabel: "-0.40",
              deltaTone: "down",
            },
            {
              tenor: "10Y",
              yieldLabel: "1.90%",
              deltaLabel: "+0.20",
              deltaTone: "up",
            },
          ],
        },
      },
    };

    renderBand(view);

    const context = screen.getByTestId("dashboard-home-market-context");
    expect(context).toHaveTextContent("国债收益率");
    expect(context).toHaveTextContent("2026-04-30");
    expect(context).toHaveTextContent("来源：正式曲线服务");
    expect(context).toHaveTextContent("数据截至 2026-04-30");
    // 窄格可见处只留值（去"标签："前缀），全文保留在 title 全量披露。
    expect(context).toHaveTextContent("正式链路有提示");
    expect(context).toHaveTextContent("随报告日查询自动更新");
    expect(context).not.toHaveTextContent("来源状态：正式链路有提示");
    expect(
      within(context).getByTitle("来源状态：正式链路有提示"),
    ).toBeInTheDocument();
    expect(
      within(context).getByTitle("刷新：随报告日查询自动更新"),
    ).toBeInTheDocument();

    const table = screen.getByTestId("dashboard-home-market-curve-table");
    expect(table).toHaveAttribute("data-as-of", "2026-04-30");
    expect(table.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(
      Array.from(table.querySelectorAll("tbody th"), (cell) => cell.textContent),
    ).toEqual(["1Y", "3Y", "5Y", "10Y"]);
    const missingRow = within(table).getByRole("row", { name: /3Y/ });
    expect(missingRow).toHaveAttribute("data-state", "backend-gap");
    expect(missingRow).toHaveTextContent("—");

    // 卡内只保留一个可见日期（数据截至）；快照日与数据截至一致时无 stale 徽标，
    // 快照日收进标题 title 与表格 data-as-of。
    expect(
      screen.queryByTestId("dashboard-home-curve-stale-flag"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "国债收益率" }).getAttribute("title"),
    ).toContain("曲线快照日 2026-04-30");
    expect(
      screen.getByRole("heading", { name: "国债收益率" }).getAttribute("title"),
    ).toContain("报告日正式链路");
  });

  it("raises an amber stale flag when the curve snapshot lags the data as-of date", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      marketContext: {
        ...base.marketContext,
        asOfLabel: "数据截至 2026-07-31",
        curveTable: {
          title: "国债收益率",
          asOfLabel: "2026-06-30",
          emptyMessage: null,
          rows: [
            {
              tenor: "10Y",
              yieldLabel: "1.73%",
              deltaLabel: "+0.80",
              deltaTone: "up",
            },
          ],
        },
      },
    };

    renderBand(view);

    const staleFlag = screen.getByTestId("dashboard-home-curve-stale-flag");
    expect(staleFlag).toHaveTextContent("快照 2026-06-30");
    expect(staleFlag.getAttribute("title")).toContain("曲线快照日 2026-06-30");
    expect(staleFlag.getAttribute("title")).toContain("数据截至 2026-07-31");
  });

  it("keeps the DR007 alias order and accepts only landed proxy qualities", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      marketContext: {
        ...base.marketContext,
        rateSeries: [
          fundingTicker("CA.DR007", {
            tradeDate: "2026-07-28",
            vendorName: "public_repo_rate_query",
          }),
          fundingTicker("M002", {
            value: "1.42%",
            tradeDate: "2026-07-29",
            qualityFlag: "warning",
            vendorName: "Choice",
            policyNote: "primary governed DR007 alias",
          }),
          fundingTicker("NCD.SHIBOR.1M", {
            qualityFlag: "warning",
            vendorName: "Tushare",
          }),
          fundingTicker("NCD.SHIBOR.3M", {
            qualityFlag: "stale",
            vendorName: "Tushare",
          }),
          fundingTicker("NCD.SHIBOR.6M", {
            policyNote:
              "public fallback headline lane via repo_rate_query FDR007",
            vendorName: "public_repo_rate_query",
          }),
        ],
      },
    };

    renderBand(view);

    const panel = screen.getByTestId("dashboard-home-liquidity-panel");
    expect(panel).toHaveAttribute("data-state", "ready");
    expect(panel).toHaveTextContent("4 条代理已落地");
    expect(
      within(panel).getByRole("group", { name: "资金代理覆盖 4 条" }),
    ).toHaveTextContent("4");
    const dr007 = within(panel).getByText("DR007").closest("div");
    expect(dr007?.querySelector("dd")).toHaveAttribute("data-series-id", "M002");
    expect(dr007?.querySelector("dd")).toHaveAttribute(
      "data-trade-date",
      "2026-07-29",
    );
    expect(dr007).toHaveTextContent("Choice");
    // 非 FDR007 的长政策说明不再占可见行，但行级 title 保留全量披露。
    expect(dr007).not.toHaveTextContent("primary governed DR007 alias");
    expect(dr007?.getAttribute("title")).toContain("primary governed DR007 alias");
    expect(panel).toHaveTextContent("FDR007代理");
    expect(panel).toHaveTextContent(
      "未接入：R007 / R001 / GC001；不以 DR007 或 SHIBOR 替代",
    );
    expect(panel).not.toHaveTextContent("流动性评分");
    expect(panel).not.toHaveTextContent("偏松");
    expect(panel).not.toHaveTextContent("偏紧");
  });

  it("keeps raw source tokens out of the visible vendor slot but in the row title", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      marketContext: {
        ...base.marketContext,
        rateSeries: [
          fundingTicker("M002", {
            vendorName: null,
            sourceVersion: "public_repo_rate_query",
          }),
          fundingTicker("NCD.SHIBOR.1M", {
            vendorName: "public_repo_rate_query",
          }),
          fundingTicker("NCD.SHIBOR.3M", { vendorName: "tushare" }),
        ],
      },
    };

    renderBand(view);

    const panel = screen.getByTestId("dashboard-home-liquidity-panel");
    // vendorName 缺失时可见行不再回退 sourceVersion 原始 token。
    const dr007 = within(panel).getByText("DR007").closest("div");
    expect(dr007).not.toHaveTextContent("public_repo_rate_query");
    expect(dr007?.getAttribute("title")).toContain("public_repo_rate_query");
    // vendorName 本身是 snake_case 内部 token 时同样只留在 title。
    const shibor1m = within(panel).getByText("SHIBOR 1M").closest("div");
    expect(shibor1m).not.toHaveTextContent("public_repo_rate_query");
    expect(shibor1m?.getAttribute("title")).toContain("public_repo_rate_query");
    // 全小写数据管道 token（如 tushare）不占可见行，收进行级 title，正文留日期。
    const shibor3m = within(panel).getByText("SHIBOR 3M").closest("div");
    expect(shibor3m).not.toHaveTextContent("tushare");
    expect(shibor3m?.getAttribute("title")).toContain("tushare");
    expect(shibor3m).toHaveTextContent("2026-07-29");
  });

  it("uses the next DR007 alias when the preferred alias fails validation", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      marketContext: {
        ...base.marketContext,
        rateSeries: [
          fundingTicker("M002", { unit: "bp" }),
          fundingTicker("CA.DR007", {
            value: "1.46%",
            tradeDate: "2026-07-30",
            vendorName: "public_repo_rate_query",
          }),
        ],
      },
    };

    renderBand(view);

    const panel = screen.getByTestId("dashboard-home-liquidity-panel");
    const dr007 = within(panel).getByText("DR007").closest("div");
    expect(panel).toHaveAttribute("data-state", "ready");
    expect(dr007?.querySelector("dd")).toHaveAttribute(
      "data-series-id",
      "CA.DR007",
    );
    expect(dr007).toHaveTextContent("1.46%");
  });

  it("fails closed for wrong units, non-finite values, and rejected quality", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      marketContext: {
        ...base.marketContext,
        rateSeries: [
          fundingTicker("CA.DR007", { qualityFlag: "error" }),
          fundingTicker("NCD.SHIBOR.1M", { unit: "bp" }),
          fundingTicker("NCD.SHIBOR.3M", {
            valueNumeric: Number.POSITIVE_INFINITY,
          }),
          fundingTicker("NCD.SHIBOR.6M", { qualityFlag: "missing" }),
        ],
      },
    };

    renderBand(view);

    const panel = screen.getByTestId("dashboard-home-liquidity-panel");
    expect(panel).toHaveAttribute("data-state", "backend-gap");
    expect(panel).toHaveTextContent("资金代理未落地");
    expect(
      within(panel).getByRole("group", { name: "资金代理覆盖 0 条" }),
    ).toHaveTextContent("—");
    expect(panel.querySelectorAll("dd[data-series-id]")).toHaveLength(0);
    expect(
      Array.from(panel.querySelectorAll("dl > div"), (row) => ({
        label: row.querySelector("dt")?.textContent,
        value: row.querySelector("dd")?.textContent,
        state: row.getAttribute("data-state"),
      })),
    ).toEqual([
      { label: "DR007", value: "—", state: "backend-gap" },
      { label: "SHIBOR 1M", value: "—", state: "backend-gap" },
      { label: "SHIBOR 3M", value: "—", state: "backend-gap" },
      { label: "SHIBOR 6M", value: "—", state: "backend-gap" },
    ]);
  });

  it("renders all eight route-backed quick links with data-status labels only", () => {
    const view = buildView();
    renderBand(view, "partial");

    const quickLinks = screen.getByTestId("dashboard-home-bottom-grid");
    const links = within(quickLinks).getAllByRole("link");
    expect(links).toHaveLength(8);
    expect(links.map((link) => link.getAttribute("href"))).toEqual(
      view.quickDrilldowns.map((item) => item.path),
    );
    expect(links.map((link) => link.querySelector("strong")?.textContent)).toEqual(
      view.quickDrilldowns.map((item) => item.label),
    );
    expect(within(quickLinks).queryAllByRole("button")).toHaveLength(0);
    const statusLabels = quickLinks.querySelectorAll(
      "small[data-status-kind='partial']",
    );
    expect(statusLabels).toHaveLength(8);
    expect(Array.from(statusLabels, (label) => label.textContent)).toEqual(
      Array.from({ length: 8 }, () => "部分可用"),
    );
  });

  it("renders no per-link status word when the data status is ok", () => {
    const view = buildView();
    renderBand(view, "ok");

    const quickLinks = screen.getByTestId("dashboard-home-bottom-grid");
    expect(within(quickLinks).getAllByRole("link")).toHaveLength(8);
    expect(quickLinks.querySelectorAll("small")).toHaveLength(0);
    expect(quickLinks).not.toHaveTextContent("已同步");
  });
});
