import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import { mapToHomeBodyView, type MapToHomeBodyViewInput } from "./dashboardHomeBodyView";
import { TerminalHomeContent } from "./TerminalHomeContent";

function numeric(raw: number | null, display: string, unit: "yuan" | "pct" | "ratio" | "dv01" = "yuan") {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: unit === "pct",
  };
}

function resultMeta(): ResultMeta {
  return {
    trace_id: "tr_home_summary_component",
    basis: "analytical",
    result_kind: "bond_dashboard.home_summary",
    formal_use_allowed: false,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-21T08:10:59Z",
  };
}

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

function buildView(reportDate = "2026-04-30") {
  return mapToHomeBodyView(buildInput(reportDate));
}

function topHolding(index: number) {
  return {
    instrument_code: `24000${index}.IB`,
    instrument_name: `测试债券${index}`,
    issuer_name: `发行人${index}`,
    rating: "AAA",
    asset_class: "credit",
    market_value: numeric(100_000_000 + index, "1.00 亿"),
    face_value: numeric(100_000_000 + index, "1.00 亿"),
    ytm: numeric(0.021, "2.10%", "pct"),
    modified_duration: numeric(5.2, "5.20", "ratio"),
    weight: numeric(0.1, "10.00%", "ratio"),
  };
}

function positionChange(index: number, direction: "increase" | "decrease") {
  return {
    instrument_code: `25000${index}.IB`,
    instrument_name: `变动债券${index}`,
    issuer_name: `变动发行人${index}`,
    rating: "AAA",
    asset_class: "credit",
    previous_market_value: numeric(100_000_000, "1.00 亿"),
    current_market_value: numeric(120_000_000, "1.20 亿"),
    change_market_value: numeric(20_000_000, "+0.20 亿"),
    previous_weight: numeric(0.1, "10.00%", "ratio"),
    current_weight: numeric(0.12, "12.00%", "ratio"),
    change_weight: numeric(0.02, "+2.00pp", "ratio"),
    direction,
    reason_label: direction === "increase" ? "增持" : "减持",
    source_status: "ready" as const,
  };
}

describe("TerminalHomeContent drilldowns", () => {
  it("exposes evidence links with the active report date", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView()} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("link", { name: /归因明细/ })).toHaveAttribute(
      "href",
      "/pnl-attribution?report_date=2026-04-30",
    );
    expect(screen.getByRole("link", { name: /曲线\/利差/ })).toHaveAttribute(
      "href",
      "/bond-analysis?report_date=2026-04-30",
    );
  });

  it("does not pass placeholder report dates into evidence links", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView("—")} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("link", { name: /归因明细/ })).toHaveAttribute("href", "/pnl-attribution");
    expect(screen.getByRole("link", { name: /曲线\/利差/ })).toHaveAttribute("href", "/bond-analysis");
  });

  it("keeps macro context before the below-fold API directory", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView()} />
      </MemoryRouter>,
    );

    const macroContext = await screen.findByTestId("dashboard-home-research-calendar");
    const apiDirectoryHeading = await screen.findByText("接口台账");
    expect(
      macroContext.compareDocumentPosition(apiDirectoryHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("keeps available modules visible when the home service is unavailable", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView()} homeAvailabilityKind="serviceUnavailable" />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("dashboard-home-research-calendar")).toBeInTheDocument();
    const availabilityPanel = await screen.findByTestId("dashboard-home-data-availability");
    expect(availabilityPanel).toHaveTextContent("主快照不可用，模块按实况展示");
    expect(availabilityPanel).toHaveTextContent("主快照不可用");
    expect(availabilityPanel).toHaveTextContent("模块可用");
    const diagnosticDetails = availabilityPanel.querySelector("details");
    expect(diagnosticDetails).not.toBeNull();
    expect(diagnosticDetails?.querySelector("summary")).toHaveTextContent("查看数据诊断");
    expect(diagnosticDetails).toHaveTextContent("/ui/home/snapshot");
    expect(diagnosticDetails).toHaveTextContent("/api/bond-analytics/top-holdings");
    expect(await screen.findByTestId("dashboard-home-position-changes")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-income-trend")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-bottom-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-bond-news")).toBeInTheDocument();
  });

  it("renders warning home-summary risk and landed distribution sections", async () => {
    const view = mapToHomeBodyView({
      ...buildInput("2026-05-31"),
      reportDate: "2026-05-31",
      homeSummaryMeta: resultMeta(),
      riskIndicators: {
        report_date: "2026-05-31",
        total_market_value: numeric(337_242_490_797.34, "337,242,490,797.34"),
        total_dv01: numeric(106_224_411.96, "106,224,411.96", "dv01"),
        weighted_duration: numeric(4.42, "4.42", "ratio"),
        credit_ratio: numeric(0.3024, "0.30", "ratio"),
        weighted_convexity: numeric(27.63, "27.63", "ratio"),
        total_spread_dv01: numeric(26_332_652.11, "26,332,652.11", "dv01"),
        reinvestment_ratio_1y: numeric(0.35, "0.35", "ratio"),
      },
      yieldDistribution: {
        report_date: "2026-05-31",
        weighted_ytm: numeric(0.0259, "+2.59%", "pct"),
        items: [
          {
            yield_bucket: "1.5%-2.0%",
            total_market_value: numeric(109_194_864_868.17, "109,194,864,868.17"),
            bond_count: 429,
          },
        ],
      },
      portfolioComparison: {
        report_date: "2026-05-31",
        items: [
          {
            portfolio_name: "FIOA",
            total_market_value: numeric(327_086_315_391.14, "327,086,315,391.14"),
            weighted_ytm: numeric(0.026, "+2.60%", "pct"),
            weighted_duration: numeric(4.31, "4.31", "ratio"),
            total_dv01: numeric(99_445_175, "99,445,175.00", "dv01"),
            bond_count: 1609,
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeContent view={view} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("收益率分布")).toBeInTheDocument();
    expect(screen.getByText("组合对比")).toBeInTheDocument();
    expect(screen.getByText("1.5%-2.0%")).toBeInTheDocument();
    expect(screen.getByText("FIOA")).toBeInTheDocument();
    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-risk-exposure")).toHaveTextContent("10,622.44 万");
    expect(screen.getByTestId("dashboard-home-risk-exposure")).toHaveTextContent("2,633.27 万");
    expect(screen.getAllByText(/quality warning/).length).toBeGreaterThan(0);
  });

  it("does not advertise missing benchmark or excess income trend series as chart legend items", async () => {
    const view = mapToHomeBodyView({
      ...buildInput("2026-05-31"),
      reportDate: "2026-05-31",
      incomeTrend: {
        report_date: "2026-05-31",
        window: 4,
        source_status: "partial",
        warnings: ["CDB_INDEX unavailable"],
        missing_components: ["benchmark_pnl", "excess_pnl"],
        points: [
          {
            date: "2026-05-31",
            portfolio_pnl: numeric(269_000_000, "+2.69 亿"),
            benchmark_pnl: numeric(null, "缺CDB_INDEX"),
            excess_pnl: numeric(null, "缺CDB_INDEX"),
            basis: "product_category_pnl_monthly",
            source_status: "partial",
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeContent view={view} />
      </MemoryRouter>,
    );

    const legend = await screen.findByLabelText("收益趋势图例");
    expect(legend).toHaveTextContent("组合");
    expect(legend).not.toHaveTextContent("CDB基准");
    expect(legend).not.toHaveTextContent("超额");

    const panel = screen.getByTestId("dashboard-home-income-trend");
    expect(panel).toHaveTextContent("缺 CDB_INDEX 曲线");
    expect(within(panel).queryAllByText("缺CDB_INDEX")).toHaveLength(0);
  });
});

describe("TerminalHomeContent data honesty", () => {
  it("shows an empty source gate instead of static ledger rows when no governed source rows landed", async () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={buildView("2026-05-31")} />
      </MemoryRouter>,
    );

    const sourceGate = await screen.findByTestId("dashboard-home-source-gate");
    expect(sourceGate).toHaveTextContent("暂无可核验来源台账");
    expect(sourceGate).not.toHaveTextContent("中债估值数据源");
    expect(sourceGate).not.toHaveTextContent("12:27:04");
  });

  it("keeps source-gate and TopN labels consistent with landed rows", async () => {
    const view = mapToHomeBodyView({
      ...buildInput("2026-05-31"),
      reportDate: "2026-05-31",
      topHoldings: {
        report_date: "2026-05-31",
        top_n: 8,
        items: Array.from({ length: 8 }, (_, index) => topHolding(index + 1)),
        total_market_value: numeric(800_000_000, "8.00 亿"),
        warnings: [],
        computed_at: "2026-05-31T10:00:00Z",
      },
      positionChanges: {
        report_date: "2026-05-31",
        prev_report_date: "2026-05-30",
        top_n: 5,
        source_status: "ready",
        items: [positionChange(1, "increase"), positionChange(2, "decrease")],
        total_market_value: numeric(800_000_000, "8.00 亿"),
        prev_total_market_value: numeric(780_000_000, "7.80 亿"),
        warnings: [],
        computed_at: "2026-05-31T10:00:00Z",
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeContent view={view} />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    const sourceGate = screen.getByTestId("dashboard-home-source-gate");
    expect(screen.getByText(/Top8/)).toBeInTheDocument();
    expect(screen.queryByText(/Top10/)).not.toBeInTheDocument();
    expect(screen.getByText(/TOP2/)).toBeInTheDocument();
    expect(screen.queryByText(/TOP5/)).not.toBeInTheDocument();
    expect(sourceGate).not.toHaveTextContent("中债估值数据源");
    expect(sourceGate).not.toHaveTextContent("12:27:04");
    expect(sourceGate).not.toHaveTextContent("analytical_mock");
    expect(sourceGate).not.toHaveTextContent("stale_fallback");
  });

  it("caps visible holdings at the dense risk-workbench height", async () => {
    const view = mapToHomeBodyView({
      ...buildInput("2026-05-31"),
      reportDate: "2026-05-31",
      topHoldings: {
        report_date: "2026-05-31",
        top_n: 14,
        items: Array.from({ length: 14 }, (_, index) => topHolding(index + 1)),
        total_market_value: numeric(1_400_000_000, "14.00 亿"),
        warnings: [],
        computed_at: "2026-05-31T10:00:00Z",
      },
      positionChanges: {
        report_date: "2026-05-31",
        prev_report_date: "2026-05-30",
        top_n: 5,
        source_status: "ready",
        items: [positionChange(1, "increase"), positionChange(2, "decrease")],
        total_market_value: numeric(1_400_000_000, "14.00 亿"),
        prev_total_market_value: numeric(1_380_000_000, "13.80 亿"),
        warnings: [],
        computed_at: "2026-05-31T10:00:00Z",
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeContent view={view} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/重点券 Top12/)).toBeInTheDocument();
    expect(screen.getAllByTestId("dashboard-home-holding-row")).toHaveLength(12);
    expect(screen.getByText(/增减仓 TOP2/)).toBeInTheDocument();
  });

  it("surfaces partial source-gate status as text instead of only a color dot", async () => {
    const view = mapToHomeBodyView({
      ...buildInput("2026-05-31"),
      reportDate: "2026-05-31",
      incomeTrend: {
        report_date: "2026-05-31",
        window: 2,
        source_status: "partial",
        warnings: ["Benchmark unavailable"],
        missing_components: ["benchmark_pnl"],
        points: [
          {
            date: "2026-05-31",
            portfolio_pnl: numeric(269_000_000, "+2.69 亿"),
            benchmark_pnl: numeric(null, "缺CDB_INDEX"),
            excess_pnl: numeric(null, "缺CDB_INDEX"),
            basis: "product_category_pnl_monthly",
            source_status: "partial",
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeContent view={view} />
      </MemoryRouter>,
    );

    const sourceGate = await screen.findByTestId("dashboard-home-source-gate");
    expect(sourceGate).toHaveTextContent("部分可用");
    expect(sourceGate).not.toHaveTextContent("随数据生成");
  });
});
