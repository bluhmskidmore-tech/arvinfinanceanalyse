import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { CampisiFourEffectsPayload, ResultMeta } from "../../../api/contracts";
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

function campisiPayload(
  status: "ok" | "partial" | "unavailable",
  overrides: Partial<CampisiFourEffectsPayload> = {},
): CampisiFourEffectsPayload {
  const excluded = status === "partial" ? 259 : status === "unavailable" ? 2 : 0;
  const total = status === "unavailable" ? 2 : 1854;
  return {
    report_date: "2026-08-31",
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    num_days: 30,
    totals: {
      market_value_start: 0,
      income_return: status === "unavailable" ? 0 : 20_000_000,
      treasury_effect: 0,
      spread_effect: 0,
      selection_effect: 0,
      total_return: status === "unavailable" ? 0 : 20_000_000,
    },
    by_asset_class: [],
    by_bond: [],
    warnings: [],
    effect_availability: {
      bonds: total,
      position_change: {
        status,
        reason: status === "ok" ? null : "principal_change_without_cashflows",
        unavailable_bonds: excluded,
        covered_bonds: total - excluded,
        unavailable_market_value_start: status === "ok" ? 0 : 50_000_000,
        unavailable_market_value_end: status === "ok" ? 0 : 30_000_000,
      },
      treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
    },
    ...overrides,
  };
}

function viewWithCampisi(
  payload: CampisiFourEffectsPayload | null,
  reportDate = "2026-08-31",
  state: Partial<MapToHomeBodyViewInput> = {},
): DashboardHomeBodyView {
  return mapToHomeBodyView({
    ...buildInput(reportDate),
    campisiFourEffects: payload,
    ...state,
  });
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

  it("keeps DV01 exposure in its own panel instead of the treasury yield card", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      krdState: { kind: "ready", label: "已就绪" },
      krdBuckets: [
        {
          id: "6M-0",
          tenor: "6M",
          dv01Display: "117.01",
          dv01Raw: 1_170_100,
          barWidthPct: 5,
        },
        {
          id: "20Y-1",
          tenor: "20Y",
          dv01Display: "2,319.97",
          dv01Raw: 23_199_700,
          barWidthPct: 100,
        },
      ],
    };

    renderBand(view);

    const krdPanel = screen.getByTestId("dashboard-home-krd-panel");
    expect(krdPanel).toHaveAttribute("data-state", "ready");
    expect(
      within(krdPanel).getByRole("heading", { name: "各期限 DV01 敞口" }),
    ).toBeInTheDocument();
    expect(krdPanel).toHaveTextContent("万元/bp");
    expect(
      within(krdPanel).getByTestId("dashboard-home-krd-strip").children,
    ).toHaveLength(2);
    expect(krdPanel).toHaveTextContent("2,319.97");

    // 收益率卡回归单一业务对象：不再承载组合敞口。
    const context = screen.getByTestId("dashboard-home-market-context");
    expect(
      within(context).queryByTestId("dashboard-home-krd-strip"),
    ).not.toBeInTheDocument();
    expect(context).not.toHaveTextContent("2,319.97");
  });

  it("surfaces spread DV01 in the exposure panel", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      riskExposureMetrics: [
        { id: "duration", label: "加权久期", value: "4.29" },
        { id: "spread-dv01", label: "利差 DV01", value: "2,736.63 万" },
      ],
    };

    renderBand(view);

    // 组合层利差 DV01 此前只存在于一个 display:none 的指标条，全页读不到。
    const footer = within(screen.getByTestId("dashboard-home-krd-panel")).getByTestId(
      "dashboard-home-spread-dv01",
    );
    expect(footer).toHaveTextContent("利差 DV01");
    expect(footer).toHaveTextContent("2,736.63 万");
  });

  it("omits the spread DV01 footer when the metric is absent", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      riskExposureMetrics: [{ id: "duration", label: "加权久期", value: "4.29" }],
    };

    renderBand(view);

    expect(
      screen.queryByTestId("dashboard-home-spread-dv01"),
    ).not.toBeInTheDocument();
  });

  it("keeps the DV01 panel speaking when no exposure bucket landed", () => {
    const base = buildView();
    const view: DashboardHomeBodyView = {
      ...base,
      krdState: { kind: "empty", label: "暂无期限敞口" },
      krdBuckets: [],
    };

    renderBand(view);

    const krdPanel = screen.getByTestId("dashboard-home-krd-panel");
    expect(krdPanel).toHaveAttribute("data-state", "empty");
    expect(within(krdPanel).getByRole("status")).toHaveTextContent(
      "暂无期限敞口",
    );
    expect(
      within(krdPanel).queryByTestId("dashboard-home-krd-strip"),
    ).not.toBeInTheDocument();
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

  it("renders the covered subset, excluded holdings, actual period, and same-window detail link", () => {
    renderBand(viewWithCampisi(campisiPayload("partial")));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "partial");
    expect(coverage).toHaveTextContent("持仓收益归因覆盖");
    expect(coverage).toHaveTextContent("2026-08-01 至 2026-08-31");
    expect(coverage).toHaveTextContent("覆盖 1595/1854 项持仓");
    expect(coverage).toHaveTextContent("排除 259/1854 项持仓");
    expect(coverage).toHaveTextContent("期初 0.50 亿");
    expect(coverage).toHaveTextContent("期末 0.30 亿");
    expect(coverage).toHaveTextContent("不可正式使用");
    expect(within(coverage).getByRole("link", { name: "查看同区间四效应明细" })).toHaveAttribute(
      "href",
      "/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31",
    );
  });

  it.each(["ok", "error"] as const)("discloses formal accounting row inclusion with %s source quality", (quality) => {
    const payload = campisiPayload("ok", {
      basis: "formal_report_pnl_bridge",
      period_start: "2026-07-31",
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl", report_date: "2026-08-31", status: "closed",
        campisi_total_return: 20_000_000, formal_actual_pnl: 20_000_000,
        residual_to_formal_pnl: 0, residual_ratio: 0, message: "合计闭合",
        bridge_quality_flag: "ok", bridge_vendor_status: "ok", bridge_fallback_mode: "none",
      },
      input_quality: {
        formal_bridge_coverage: {
          source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "ok", bridge_rows: 4, attributed_rows: 4,
        },
      },
    });
    payload.effect_availability = {
      ...payload.effect_availability!, bonds: 4, position_change: undefined,
      roll_down_availability: { status: "ok", unavailable_rows: 0, applicable_rows: 2, reasons: [] },
      treasury_curve_availability: { status: "ok", unavailable_rows: 0, applicable_rows: 2, reasons: [] },
      credit_spread_availability: { status: "not_applicable", unavailable_rows: 0, applicable_rows: 0, reasons: ["not_credit_book"] },
    };
    const meta: ResultMeta = {
      trace_id: "synthetic-coverage", basis: "formal", result_kind: "campisi",
      formal_use_allowed: true, source_version: "synthetic", vendor_version: "synthetic",
      rule_version: "synthetic", cache_version: "synthetic", quality_flag: quality,
      vendor_status: "ok", fallback_mode: "none", scenario_flag: false, generated_at: "2026-08-31T00:00:00Z",
    };
    renderBand(viewWithCampisi(payload, "2026-08-31", { campisiResultMeta: meta }));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", quality === "error" ? "error" : "complete");
    expect(coverage).toHaveTextContent("正式桥归因覆盖");
    expect(coverage).toHaveTextContent("会计记录行纳入 4/4 行");
    expect(coverage).toHaveTextContent("信用利差效应不适用");
    expect(coverage).not.toHaveTextContent("本金变化");
    expect(coverage).not.toHaveTextContent("排除绝对市值");
    if (quality === "error") {
      expect(coverage).toHaveTextContent("数据质量错误");
      expect(coverage).toHaveTextContent("金额闭合不代表数据质量通过");
      expect(coverage).toHaveTextContent("不可正式使用");
    }
    expect(within(coverage).getByRole("link", { name: "查看同区间四效应明细" })).toHaveAttribute(
      "href",
      "/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-07-31&campisi_end_date=2026-08-31",
    );
  });

  it("keeps all-excluded placeholder zero out of the visible coverage summary", () => {
    renderBand(viewWithCampisi(campisiPayload("unavailable")));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "unavailable");
    expect(coverage).toHaveTextContent("排除 2/2 项持仓");
    expect(coverage).toHaveTextContent("无可归因持仓");
    expect(coverage).not.toHaveTextContent("总收益 0");
    expect(coverage).not.toHaveTextContent("0.00 亿");
  });

  it("keeps confirmed zero exclusions as zero even when unrelated warnings exist", () => {
    renderBand(viewWithCampisi(campisiPayload("ok", { warnings: ["curve warning"] })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "complete");
    expect(coverage).toHaveTextContent("覆盖 1854/1854 项持仓");
    expect(coverage).toHaveTextContent("排除 0/1854 项持仓");
    expect(coverage).not.toHaveTextContent("部分覆盖");
    expect(coverage).not.toHaveTextContent("到期日不可用");
  });

  it("shows the backend maturity gap even when curve and other coverage inputs are ok", () => {
    renderBand(viewWithCampisi(campisiPayload("ok", {
      input_quality: {
        included_maturity_unavailable: {
          positions: 17,
          market_value_start_abs: 50_000_000,
          model_residual: -2_000_000,
        },
      },
    })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "partial");
    expect(coverage).toHaveTextContent("到期日不可用 17 项持仓");
    expect(coverage).toHaveTextContent("期初绝对市值 0.50 亿");
    expect(coverage).toHaveTextContent("模型剩余项 -0.02 亿");
    expect(coverage).toHaveTextContent("国债曲线可用不代表逐项久期可用");
    expect(coverage).toHaveTextContent("不代表主动选券");
    expect(coverage).not.toHaveTextContent("逐效应输入均有覆盖诊断");
  });

  it("does not invent a maturity gap from a present zero summary", () => {
    renderBand(viewWithCampisi(campisiPayload("ok", {
      input_quality: {
        included_maturity_unavailable: {
          positions: 0,
          market_value_start_abs: 0,
          model_residual: 0,
        },
      },
    })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "complete");
    expect(coverage).not.toHaveTextContent("到期日不可用");
    expect(coverage).not.toHaveTextContent("模型剩余项");
  });

  it("shows a small nonzero maturity exposure and residual in yuan", () => {
    renderBand(viewWithCampisi(campisiPayload("ok", {
      input_quality: {
        included_maturity_unavailable: {
          positions: 1,
          market_value_start_abs: 120_000,
          model_residual: 25_000,
        },
      },
    })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "partial");
    expect(coverage).toHaveTextContent("期初绝对市值 120,000 元");
    expect(coverage).toHaveTextContent("模型剩余项 +25,000 元");
    expect(coverage).not.toHaveTextContent("0.00 亿");
  });

  it.each([
    { market_value_start_abs: Number.NaN, model_residual: -2_000_000 },
    { market_value_start_abs: 50_000_000, model_residual: Number.POSITIVE_INFINITY },
    { market_value_start_abs: -1, model_residual: -2_000_000 },
  ])("ignores an incomplete maturity quality summary: %j", (quality) => {
    renderBand(viewWithCampisi(campisiPayload("ok", {
      input_quality: {
        included_maturity_unavailable: { positions: 17, ...quality },
      },
    })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "complete");
    expect(coverage).not.toHaveTextContent("到期日不可用");
    expect(coverage).not.toHaveTextContent("NaN");
    expect(coverage).not.toHaveTextContent("Infinity");
  });

  it("does not publish model maturity quality on a formal bridge path", () => {
    renderBand(viewWithCampisi(campisiPayload("ok", {
      basis: "formal_report_pnl_bridge",
      input_quality: {
        included_maturity_unavailable: {
          positions: 17,
          market_value_start_abs: 50_000_000,
          model_residual: -2_000_000,
        },
      },
    })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "unknown");
    expect(coverage).toHaveTextContent("正式损益桥归因");
    expect(coverage).not.toHaveTextContent("到期日不可用");
  });

  it("keeps an observed zero return distinct from unavailable input and does not claim closure", () => {
    const payload = campisiPayload("ok");
    payload.totals = { ...payload.totals, income_return: 0, total_return: 0 };
    // The backend can return null even though the current frontend contract marks closure optional.
    (payload as unknown as { formal_closure: null }).formal_closure = null;
    renderBand(viewWithCampisi(payload));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "complete");
    expect(coverage).toHaveTextContent("本金变化维度覆盖 1854/1854 项持仓");
    expect(coverage).not.toHaveTextContent("无可归因持仓");
    expect(coverage).not.toHaveTextContent("占位零");
    expect(coverage).not.toHaveTextContent("闭合");
    expect(within(coverage).getByRole("link", { name: "查看同区间四效应明细" })).toBeInTheDocument();
  });

  it("shows other missing effects separately from the position-change subset", () => {
    const payload = campisiPayload("partial");
    // The other effects cover only the 1,854 - 259 attributable holdings;
    // excluded principal-change positions stay in the separate coverage line.
    const attributableHoldings = 1854 - 259;
    payload.effect_availability!.treasury_effect = {
      status: "unavailable", reason: "insufficient_shared_positive_tenors", unavailable_bonds: attributableHoldings,
      unavailable_market_value_start: 0,
    };
    payload.effect_availability!.accrued_interest = {
      status: "partial", reason: "accrued_interest_missing", unavailable_bonds: 163,
      unavailable_market_value_start: 0,
    };
    renderBand(viewWithCampisi(payload));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveTextContent("本金变化维度覆盖 1595/1854 项持仓");
    expect(coverage).toHaveTextContent("国债曲线效应不可用");
    expect(coverage).toHaveTextContent("两端共同的有效正收益率期限不足");
    expect(coverage).toHaveTextContent("影响 1595/1595 项持仓");
    expect(coverage).toHaveTextContent("应计利息口径部分不可用");
    expect(coverage).toHaveTextContent("影响 163/1595 项持仓");
    expect(coverage).not.toHaveTextContent("国债曲线 0.00 亿");
  });

  it("does not call all effects complete when position coverage is complete but rate inputs are absent", () => {
    const payload = campisiPayload("ok");
    payload.effect_availability!.treasury_effect = {
      status: "unavailable", reason: "curve_absent", unavailable_bonds: 1854,
      unavailable_market_value_start: 0,
    };
    renderBand(viewWithCampisi(payload));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "partial");
    expect(coverage).toHaveTextContent("本金变化维度覆盖 1854/1854 项持仓");
    expect(coverage).toHaveTextContent("国债曲线效应不可用");
    expect(coverage).not.toHaveTextContent("全部效应完整");
  });

  it("does not infer complete coverage or a same-window link from an old payload", () => {
    renderBand(viewWithCampisi(campisiPayload("ok", { effect_availability: undefined })));

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "unknown");
    expect(coverage).toHaveTextContent("覆盖信息未提供");
    expect(coverage).not.toHaveTextContent("全部覆盖");
    expect(within(coverage).queryByRole("link", { name: "查看同区间四效应明细" })).not.toBeInTheDocument();
  });

  it("rejects a Campisi date mismatch even when another source has the home date", () => {
    const view = viewWithCampisi(
      campisiPayload("partial", {
        report_date: "2026-08-30",
        period_end: "2026-08-30",
        input_quality: {
          included_maturity_unavailable: {
            positions: 17,
            market_value_start_abs: 50_000_000,
            model_residual: -2_000_000,
          },
        },
      }),
      "2026-08-31",
      {
        yieldCurveTermStructure: {
          report_date: "2026-08-31",
          curves: [{
            curve_type: "CGB", trade_date_requested: "2026-08-31", trade_date_resolved: "2026-08-31",
            points: [], source_version: "", rule_version: "", vendor_name: "", vendor_version: "",
          }],
          warnings: [],
          computed_at: "2026-08-31T00:00:00Z",
        },
      },
    );
    expect(view.marketContext.asOfLabel).toBe("数据截至 2026-08-31");
    renderBand(view);

    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "date-mismatch");
    expect(coverage).toHaveTextContent("来源报告日与首页不一致");
    expect(coverage).not.toHaveTextContent("到期日不可用");
    expect(within(coverage).queryByRole("link", { name: "查看同区间四效应明细" })).not.toBeInTheDocument();
  });

  it("distinguishes loading and error from missing coverage", () => {
    const first = renderBand(viewWithCampisi(null, "2026-08-31", { campisiRequested: true, campisiLoading: true }));
    expect(screen.getByTestId("dashboard-home-attribution-coverage")).toHaveAttribute("data-state", "loading");
    first.unmount();

    renderBand(viewWithCampisi(null, "2026-08-31", { campisiRequested: true, campisiError: true }));
    const coverage = screen.getByTestId("dashboard-home-attribution-coverage");
    expect(coverage).toHaveAttribute("data-state", "error");
    expect(coverage).toHaveTextContent("读取失败");
  });
});
