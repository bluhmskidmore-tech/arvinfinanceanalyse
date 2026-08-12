import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/echarts", () => ({
  default: () => null,
}));

import type { Numeric, ResultMeta, VerdictPayload } from "../../../api/contracts";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { mapToHomeFirstScreenView } from "./dashboardHomeFirstScreenView";
import type { DashboardHomeFirstScreenView } from "./dashboardHomeFirstScreenTypes";
import type { HomeSnapshotPnlAttributionVM } from "./dashboardHomeSnapshotAdapter";

type DecisionActionForTest = {
  id: string;
  title: string;
  to?: string;
  reason: string;
  statusKind: string;
};

const verdict: VerdictPayload = {
  conclusion: "review portfolio duration",
  tone: "warning",
  reasons: [{ label: "duration", value: "4.20", detail: "duration moved higher", tone: "warning" }],
  suggestions: [{ text: "review duration", link: "/risk-tensor" }],
};

const currentReviewReasons: VerdictPayload["reasons"] = [
  {
    label: "债券资产规模（zqtz）",
    value: "3,734.29 亿",
    detail: "来自 fact_formal_zqtz_balance_daily，在 2026-06-30 的 CNY 资产口径市值合计。",
    tone: "positive",
  },
  {
    label: "年度损益（不扣FTP）",
    value: "+42.43 亿",
    detail: "来自 fact_formal_pnl_fi + fact_nonstd_pnl_bridge 截至 2026-06-30 的年度累计 total_pnl，不扣减 FTP。",
    tone: "positive",
  },
  {
    label: "净息差",
    value: "+0.93%",
    detail: "来自受治理负债分析收益指标，在 2026-06-30 的 NIM 读面。",
    tone: "positive",
  },
];

function reviewSnapshotMeta(): ResultMeta {
  return {
    trace_id: "trace-review-basis",
    basis: "analytical",
    result_kind: "home_snapshot",
    formal_use_allowed: false,
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    rule_version: "rule-v1",
    cache_version: "cache-v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-07-31T00:44:00Z",
  };
}

function numeric(raw: number, display: string, unit: Numeric["unit"] = "ratio"): Numeric {
  return {
    raw,
    display,
    unit,
    precision: 2,
    sign_aware: false,
  };
}

function contributionAttribution(
  overrides: Partial<HomeSnapshotPnlAttributionVM> = {},
): HomeSnapshotPnlAttributionVM {
  return {
    title: "经营贡献拆解",
    total: numeric(190_000_000, "+1.90 亿", "yuan"),
    segments: [
      {
        id: "carry",
        label: "Carry",
        amount: numeric(169_000_000, "+1.69 亿", "yuan"),
        tone: "positive",
      },
      {
        id: "roll",
        label: "Roll-down",
        amount: numeric(-1_000_000, "-0.01 亿", "yuan"),
        tone: "negative",
      },
      {
        id: "credit",
        label: "信用利差",
        amount: numeric(-3_000_000, "-0.03 亿", "yuan"),
        tone: "negative",
      },
      {
        id: "trading",
        label: "交易损益",
        amount: numeric(25_000_000, "+0.25 亿", "yuan"),
        tone: "positive",
      },
      {
        id: "other",
        label: "其他",
        amount: numeric(0, "+0.00 亿", "yuan"),
        tone: "neutral",
      },
    ],
    ...overrides,
  };
}

function decisionActions(view: DashboardHomeFirstScreenView): readonly DecisionActionForTest[] {
  return ((view.decisionRail as { actions?: readonly DecisionActionForTest[] }).actions ?? []);
}

function textOccurrences(text: string, needle: string): number {
  return text.split(needle).length - 1;
}

function firstScreenView(
  overrides: Partial<DashboardHomeFirstScreenView> = {},
): DashboardHomeFirstScreenView {
  return {
    reportDate: "2026-04-30",
    useMockFallback: false,
    reportDateContext: {
      requestedDate: "",
      actualDataDate: "2026-04-30",
      divergenceReason: null,
      dataAsOfDate: "2026-04-30 16:00",
      mode: "exact",
    },
    productCategoryHeadline: {
      state: "empty",
      metrics: [],
    },
    missingDomains: [],
    headerStatus: {
      dataStatusKind: "ok",
      dataUpdatedAt: "16:00",
      marketStatus: "closed",
      valuationLabel: "ok",
      valuationTone: "ok",
      riskReviewCount: 0,
      showRiskReview: false,
      dataSyncPrefix: "formal",
    },
    decisionRail: {
      conclusion: "review portfolio duration",
      maxDragLabel: "rates",
      maxDragValue: "-1.00",
      maxContributionLabel: "carry",
      maxContributionValue: "+0.20",
      hasDrag: true,
      hasContribution: true,
      keyRisk: "duration",
      suggestions: [
        {
          id: "suggestion-1-risk",
          text: "review duration",
          to: "/risk-tensor?report_date=2026-04-30",
        },
      ],
      pendingSummary: "1 item",
      reportDate: "2026-04-30",
      dataUpdatedAt: "16:00",
      dataSyncPrefix: "formal",
      actions: [
        {
          id: "risk-overview",
          title: "Review risk workbench",
          priority: "high",
          sourceLabel: "risk",
          reason: "2 risk items require review",
          to: "/risk-overview?report_date=2026-04-30",
          statusKind: "ready",
        },
      ],
    } as unknown as DashboardHomeFirstScreenView["decisionRail"],
    terminalKpis: [
      {
        id: "aum",
        label: "AUM",
        value: "100.00",
        delta: "flat",
        deltaTone: "flat",
        sparkline: [100, 100],
        state: "ready",
      },
      {
        id: "yield",
        label: "年度损益",
        value: "+20.00",
        delta: "+1.20",
        deltaTone: "up",
        sparkline: [18, 19, 20],
        state: "ready",
      },
      {
        id: "nim",
        label: "净息差",
        value: "1.05%",
        delta: "+0.10bp",
        deltaTone: "warn",
        sparkline: [1, 1.02, 1.05],
        state: "ready",
      },
      {
        id: "dv01",
        label: "DV01",
        value: "106,224",
        delta: "+1.85%",
        deltaTone: "up",
        sparkline: [101000, 103000, 106224],
        state: "ready",
      },
    ],
    keyRiskStrip: [
      {
        id: "duration",
        label: "Duration",
        value: "4.20",
        delta: "0.10",
        deltaTone: "warn",
      },
      {
        id: "credit-ratio",
        label: "信用占比",
        value: "62.10%",
        delta: "当前值",
        deltaTone: "flat",
      },
    ],
    ...overrides,
  };
}

describe("dashboard home first-screen actions", () => {
  it("keeps backend navigation suggestions separate from the risk review queue", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 2,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(decisionActions(view)).toEqual([
      expect.objectContaining({
        id: "risk-review-queue",
        to: "/decision-items?source=dashboard-home&report_date=2026-04-30&action_id=risk-review-queue",
        statusKind: "ready",
      }),
    ]);
    expect(view.decisionRail.suggestions).toEqual([
      expect.objectContaining({
        text: "review duration",
        to: "/risk-tensor?report_date=2026-04-30",
      }),
    ]);
    expect(view.decisionRail.pendingSummary).toBe("1 项");
  });

  it("hydrates the first-screen governed DV01 KPI from home snapshot metrics", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [
        {
          id: "dv01",
          label: "组合 DV01",
          caliberLabel: "利率风险资产口径",
          value: numeric(43_700, "43,700.00", "dv01"),
          delta: {
            ...numeric(-500, "-500.00", "dv01"),
            sign_aware: true,
          },
          tone: "warning",
          detail: "portfolio_modified_duration",
          history: [44_200, 43_700],
        },
      ],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.terminalKpis).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "dv01",
          value: "43,700.00",
        }),
      ]),
    );
    expect(view.terminalKpis.find((kpi) => kpi.id === "dv01")?.delta).toContain(
      "-500.00",
    );

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-kpi-dv01-wan")).toHaveTextContent("4.37");
  });

  it("routes risk review queue actions into decision items with dashboard context", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 2,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(decisionActions(view)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "risk-review-queue",
          to: "/decision-items?source=dashboard-home&report_date=2026-04-30&action_id=risk-review-queue",
          statusKind: "ready",
        }),
      ]),
    );
  });

  it("does not make risk review queue actions clickable without a concrete report date", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "—",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 2,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(decisionActions(view)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "risk-review-queue",
          to: undefined,
          statusKind: "stale",
        }),
      ]),
    );
  });

  it("overrides stale report dates from backend suggestion links", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: {
        ...verdict,
        suggestions: [
          {
            text: "review linked duration date",
            link: "/risk-tensor?report_date=2026-04-29&tab=dv01#bucket",
          },
        ],
      },
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.decisionRail.suggestions).toEqual([
      expect.objectContaining({
        text: "review linked duration date",
        to: "/risk-tensor?report_date=2026-04-30&tab=dv01#bucket",
      }),
    ]);
    expect(decisionActions(view)).toEqual([
      expect.objectContaining({ id: "no-action", statusKind: "empty" }),
    ]);
  });

  it("does not surface generic directionality copy as a business conclusion", () => {
    const genericConclusion = "首屏整体偏多，可基于规模与收益做方向性判断";
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: {
        ...verdict,
        conclusion: genericConclusion,
      },
      metrics: [
        {
          id: "aum",
          label: "债券资产规模",
          caliberLabel: null,
          value: numeric(366_640_000_000, "3,666.40 亿", "yuan"),
          delta: numeric(-0.0112, "-1.12%", "pct"),
          tone: "negative",
          detail: "",
          history: [1, 2],
        },
        {
          id: "yield",
          label: "年度损益（不扣FTP）",
          caliberLabel: null,
          value: numeric(3_639_000_000, "+36.39 亿", "yuan"),
          delta: numeric(0.2251, "+22.51%", "pct"),
          tone: "positive",
          detail: "",
          history: [1, 2],
        },
      ],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.decisionRail.conclusion).not.toBe(genericConclusion);
    expect(view.decisionRail.conclusion).toContain("3,666.40");
    expect(view.decisionRail.conclusion).toContain("+36.39");
  });

  it("does not fabricate clickable action links when the home snapshot is unavailable", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: true,
      snapshotStale: false,
      snapshotLoading: false,
    });

    const actions = decisionActions(view);
    expect(actions).toHaveLength(1);
    expect(actions[0]).toEqual(
      expect.objectContaining({
        id: "snapshot-unavailable",
        to: undefined,
        statusKind: "backend-gap",
      }),
    );
  });

  it("uses a non-clickable empty action when there is no backend drilldown work", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    const actions = decisionActions(view);
    expect(actions).toHaveLength(1);
    expect(actions[0]).toEqual(
      expect.objectContaining({
        id: "no-action",
        to: undefined,
        statusKind: "empty",
      }),
    );
  });

  it("does not fabricate first-screen risk strip items before supplemental data hydrates", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.keyRiskStrip).toEqual([]);
  });

  it("hydrates first-screen risk strip items from real bond supplemental data", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: {
        report_date: "2026-04-30",
        prev_report_date: "2026-04-29",
        kpis: {
          total_market_value: numeric(328_709_000_000, "3,287.09 亿", "yuan"),
          unrealized_pnl: numeric(12_300_000, "1,230.00 万", "yuan"),
          weighted_ytm: numeric(0.023, "2.30%", "pct"),
          weighted_duration: numeric(4.18, "4.18"),
          weighted_coupon: numeric(0.031, "3.10%", "pct"),
          credit_spread_median: numeric(0.0069, "69bp", "bp"),
          total_dv01: numeric(9_812_345, "9,812,345.00", "dv01"),
          bond_count: 128,
        },
        prev_kpis: null,
      },
      portfolio: {
        report_date: "2026-04-30",
        total_market_value: numeric(328_709_000_000, "3,287.09 亿", "yuan"),
        weighted_ytm: numeric(0.023, "2.30%", "pct"),
        weighted_duration: numeric(4.18, "4.18"),
        weighted_coupon: numeric(0.031, "3.10%", "pct"),
        total_dv01: numeric(9_812_345, "9,812,345.00", "dv01"),
        bond_count: 128,
        credit_weight: numeric(0.621, "62.10%", "pct"),
        issuer_hhi: numeric(0.08, "8.00%", "pct"),
        issuer_top5_weight: numeric(0.412, "41.20%", "pct"),
        by_asset_class: [],
        warnings: [],
        computed_at: "2026-04-30T16:00:00Z",
      },
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.keyRiskStrip).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "risk-dv01", value: "981.23 万" }),
        expect.objectContaining({ id: "risk-duration", value: "4.18" }),
        expect.objectContaining({ id: "risk-credit", value: "62.10%" }),
        expect.objectContaining({ id: "risk-top5", value: "41.20%" }),
      ]),
    );

    const dv01WanKpi = view.terminalKpis.find((kpi) => kpi.id === "dv01-wan");
    const riskDv01 = view.keyRiskStrip.find((item) => item.id === "risk-dv01");
    expect(riskDv01?.value).toBe(`${dv01WanKpi?.value} 万`);

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    const cards = within(
      screen.getByTestId("dashboard-home-hero-kpi-strip"),
    ).getAllByRole("article");
    expect(cards.map((card) => card.getAttribute("data-testid"))).toEqual([
      "dashboard-home-kpi-aum",
      "dashboard-home-kpi-yield",
      "dashboard-home-kpi-nim",
      "dashboard-home-kpi-dv01-wan",
    ]);
    expect(
      screen.queryByTestId("dashboard-home-kpi-risk-dv01"),
    ).not.toBeInTheDocument();
  });

  it("labels scale calibers and keeps level YTM unsigned while deltas stay signed", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [
        {
          id: "aum",
          label: "债券资产规模",
          caliberLabel: "债券资产口径",
          value: numeric(373_429_000_000, "3,734.29 亿", "yuan"),
          delta: numeric(-0.0112, "-1.12%", "pct"),
          tone: "negative",
          detail: "",
          history: [1, 2],
        },
      ],
      attribution: null,
      bondHeadline: {
        report_date: "2026-04-30",
        prev_report_date: "2026-04-29",
        kpis: {
          total_market_value: numeric(347_836_000_000, "3,478.36 亿", "yuan"),
          unrealized_pnl: { ...numeric(8_219_000_000, "+82.19 亿", "yuan"), sign_aware: true },
          weighted_ytm: { ...numeric(0.0259, "+2.59%", "pct"), sign_aware: true },
          weighted_duration: numeric(4.18, "4.18"),
          weighted_coupon: numeric(0.031, "3.10%", "pct"),
          credit_spread_median: numeric(0.0069, "69bp", "bp"),
          total_dv01: numeric(9_812_345, "9,812,345.00", "dv01"),
          bond_count: 128,
        },
        prev_kpis: {
          total_market_value: numeric(346_000_000_000, "3,460.00 亿", "yuan"),
          unrealized_pnl: { ...numeric(8_000_000_000, "+80.00 亿", "yuan"), sign_aware: true },
          weighted_ytm: { ...numeric(0.0255, "+2.55%", "pct"), sign_aware: true },
          weighted_duration: numeric(4.2, "4.20"),
          weighted_coupon: numeric(0.031, "3.10%", "pct"),
          credit_spread_median: numeric(0.0069, "69bp", "bp"),
          total_dv01: numeric(9_800_000, "9,800,000.00", "dv01"),
          bond_count: 128,
        },
      },
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    const kpiById = new Map(view.terminalKpis.map((kpi) => [kpi.id, kpi]));

    // 疑点1：两个规模数是不同口径，标签必须自带口径说明，数值不改。
    expect(kpiById.get("aum")).toEqual(
      expect.objectContaining({ label: "债券资产规模（债券资产口径）", value: "3,734.29" }),
    );
    expect(kpiById.get("bond-market-value")).toEqual(
      expect.objectContaining({ label: "债券市值（持仓口径）", value: "3,478.36" }),
    );

    // 疑点2：unrealized_pnl 是存量浮盈，不得标注为"当日"；盈亏值保留符号。
    expect(kpiById.get("unrealized-pnl")).toEqual(
      expect.objectContaining({ label: "未实现损益（存量）", value: "+82.19" }),
    );

    // 疑点3：组合YTM 是水平值，展示不带正号；较前日 delta 保留符号。
    expect(kpiById.get("ytm")).toEqual(
      expect.objectContaining({ value: "2.59", unit: "%" }),
    );
    expect(kpiById.get("ytm")?.delta).toContain("+0.04%");
  });

  it("ignores backend suggestion links outside the known workbench drilldowns", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: {
        ...verdict,
        suggestions: [{ text: "open unknown page", link: "/not-a-workbench-route" }],
      },
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(decisionActions(view)).toEqual([
      expect.objectContaining({
        id: "no-action",
        to: undefined,
        statusKind: "empty",
      }),
    ]);
  });

  it("renders decision actions as drilldown links", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          riskObservations={view.keyRiskStrip}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-decision-action-risk-overview")).toHaveAttribute(
      "href",
      "/risk-overview?report_date=2026-04-30",
    );
  });

  it("renders generated next steps without snapshot transport copy", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          riskObservations={view.keyRiskStrip}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(rail).toHaveTextContent("review duration");
    expect(rail).not.toHaveTextContent("回传入口");
    expect(
      within(rail).getByTestId("dashboard-home-review-entry-card"),
    ).toHaveTextContent("建议｜review duration");
    expect(
      within(rail).getByTestId("dashboard-home-action-queue-card"),
    ).not.toHaveTextContent("review duration");
    expect(textOccurrences(rail.textContent ?? "", "review duration")).toBe(1);
  });

  it("anchors the first screen on a morning-judgment hero and operational right rail", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
        <DecisionRailSection
          decisionRail={view.decisionRail}
          riskObservations={view.keyRiskStrip}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const hero = screen.getByTestId("dashboard-home-morning-hero");
    expect(hero).toHaveTextContent("早间决策一览");
    expect(hero).toHaveTextContent("review portfolio duration");
    expect(screen.getByTestId("dashboard-home-report-identity")).toHaveTextContent("2026-04-30");

    const heroKpiStrip = screen.getByTestId("dashboard-home-hero-kpi-strip");
    expect(
      within(heroKpiStrip)
        .getAllByRole("article")
        .map((card) => card.getAttribute("data-testid")),
    ).toEqual([
      "dashboard-home-kpi-aum",
      "dashboard-home-kpi-yield",
      "dashboard-home-kpi-nim",
      "dashboard-home-kpi-dv01-wan",
    ]);

    expect(screen.queryByTestId("dashboard-home-signal-workspace")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-market")).not.toBeInTheDocument();

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(within(rail).getByTestId("dashboard-home-review-entry-card")).toHaveTextContent("待复核");
    expect(within(rail).getByTestId("dashboard-home-action-queue-card")).toHaveTextContent(
      "复核依据",
    );
    expect(within(rail).getByTestId("dashboard-home-data-quality-card")).toHaveTextContent(
      "经营贡献观察",
    );
    expect(
      within(rail).getByTestId("dashboard-home-evidence-material-card"),
    ).toHaveTextContent("最新动态");
    const railHeadings = within(rail).getAllByRole("heading", { level: 2 });
    expect(railHeadings).toHaveLength(5);
    expect(railHeadings[0]).toHaveTextContent("风险观察");
    expect(railHeadings[1]).toHaveTextContent("待办事项");
    expect(railHeadings[2]).toHaveTextContent("复核依据");
    expect(railHeadings[3]).toHaveTextContent("经营贡献观察");
    expect(railHeadings[4]).toHaveTextContent("最新动态");
    const anomalyCard = within(rail).getByTestId("dashboard-home-anomaly-card");
    expect(anomalyCard).toHaveTextContent("预警未接入");
    expect(anomalyCard).toHaveTextContent("Duration");
    expect(anomalyCard).toHaveTextContent("4.20");
    expect(anomalyCard).toHaveTextContent("页面已加载观察项 · 非预警");
    expect(
      within(anomalyCard).getAllByTestId(
        "dashboard-home-risk-observation-row",
      ),
    ).toHaveLength(2);
    expect(rail).not.toHaveTextContent("决策建议");
    expect(rail).not.toHaveTextContent("数据与操作");
    expect(rail).not.toHaveTextContent("证券与资料");
    expect(rail).not.toHaveTextContent("复核记录");
  });

  it("renders keyRiskStrip as truthful 风险观察 without inventing alerts", () => {
    const view = firstScreenView();
    const riskObservations: DashboardHomeFirstScreenView["keyRiskStrip"] = [
      {
        id: "dv01",
        label: "组合 DV01",
        value: "43,700.00",
        delta: "当前值",
        deltaTone: "flat",
      },
      {
        id: "duration",
        label: "组合久期",
        value: "4.20 年",
        delta: "+0.10 年",
        deltaTone: "warn",
      },
      {
        id: "duration-duplicate",
        label: "组合久期",
        value: "4.20 年",
        delta: "+0.10 年",
        deltaTone: "up",
      },
      {
        id: "empty-observation",
        label: "空观察",
        value: "—",
        delta: "暂无",
        deltaTone: "flat",
      },
      {
        id: "credit-ratio",
        label: "信用占比",
        value: "62.10%",
        delta: "当前值",
        deltaTone: "flat",
      },
      {
        id: "top5",
        label: "Top5 集中度",
        value: "41.20%",
        delta: "-0.30pct",
        deltaTone: "down",
      },
      {
        id: "yield",
        label: "组合收益率",
        value: "2.345%",
        delta: "+1.2bp",
        deltaTone: "up",
      },
      {
        id: "overflow",
        label: "不应显示",
        value: "9.99",
        delta: "当前值",
        deltaTone: "flat",
      },
    ];

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          riskObservations={riskObservations}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const riskCard = screen.getByTestId("dashboard-home-anomaly-card");
    const rows = within(riskCard).getAllByTestId(
      "dashboard-home-risk-observation-row",
    );
    expect(rows).toHaveLength(5);
    expect(rows.map((row) => row.firstElementChild?.textContent)).toEqual([
      "组合 DV01",
      "组合久期",
      "信用占比",
      "Top5 集中度",
      "组合收益率",
    ]);
    expect(rows[0]).toHaveTextContent("43,700.00");
    expect(rows[1]).toHaveTextContent("+0.10 年");
    expect(rows[4]).toHaveTextContent("2.345%");
    expect(textOccurrences(riskCard.textContent ?? "", "组合久期")).toBe(1);
    expect(riskCard).not.toHaveTextContent("空观察");
    expect(riskCard).not.toHaveTextContent("不应显示");
    expect(riskCard).toHaveTextContent("预警未接入");
    expect(riskCard).toHaveTextContent("页面已加载观察项 · 非预警");
    expect(riskCard).not.toHaveTextContent("高风险");
    expect(riskCard).not.toHaveTextContent("负责人");
    expect(riskCard).not.toHaveTextContent("截止时间");
    expect(within(riskCard).queryByRole("link")).not.toBeInTheDocument();
    expect(within(riskCard).queryByRole("button")).not.toBeInTheDocument();
    expect(
      within(riskCard).getByRole("region", {
        name: "风险观察：来自页面已加载风险带，不是受管风险预警",
      }),
    ).toBeInTheDocument();

    expect(screen.getByTestId("dashboard-home-action-queue-card")).toHaveTextContent(
      "暂无可核验复核依据",
    );
    expect(screen.getByTestId("dashboard-home-data-quality-card")).not.toHaveTextContent(
      "组合 DV01",
    );
    expect(screen.getByTestId("dashboard-home-evidence-material-card")).toHaveTextContent(
      "最新动态",
    );
  });

  it("orders the reference rail and keeps risk and data-gap semantics separate", () => {
    const base = firstScreenView();
    const view: DashboardHomeFirstScreenView = {
      ...base,
      missingDomains: [{ id: "pnl", label: "pnl" }],
      decisionRail: {
        ...base.decisionRail,
        actions: [
          {
            id: "risk-review-queue",
            title: "处理风险复核队列",
            priority: "high",
            sourceLabel: "待办",
            reason: "2 项风险事项需要复核",
            to: "/decision-items?action_id=risk-review-queue",
            statusKind: "ready",
          },
        ],
      },
    };

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          riskObservations={view.keyRiskStrip}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
          missingDomains={view.missingDomains}
        />
      </MemoryRouter>,
    );

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(
      Array.from(rail.children).map((child) => child.getAttribute("data-testid")),
    ).toEqual([
      "dashboard-home-anomaly-card",
      "dashboard-home-review-entry-card",
      "dashboard-home-action-queue-card",
      "dashboard-home-data-quality-card",
      "dashboard-home-evidence-material-card",
    ]);

    const riskCard = within(rail).getByTestId("dashboard-home-anomaly-card");
    expect(riskCard).toHaveTextContent("风险观察");
    expect(riskCard).toHaveTextContent("Duration");
    expect(riskCard).toHaveTextContent("预警未接入");
    expect(riskCard).toHaveTextContent("非预警");
    expect(riskCard).not.toHaveTextContent("2 项风险事项需要复核");
    const riskReviewAction = within(rail).getByTestId(
      "dashboard-home-decision-action-risk-review-queue",
    );
    expect(riskReviewAction).toHaveAttribute(
      "href",
      "/decision-items?action_id=risk-review-queue",
    );
    expect(
      within(rail).getByTestId("dashboard-home-evidence-material-card"),
    ).toHaveTextContent("pnl");
  });

  it("renders the current snapshot verdict reasons as bounded review reference", () => {
    const base = firstScreenView();
    const view: DashboardHomeFirstScreenView = {
      ...base,
      reportDate: "2026-06-30",
      reportDateContext: {
        ...base.reportDateContext,
        actualDataDate: "2026-06-30",
        dataAsOfDate: "2026-06-30 16:00",
      },
      decisionRail: {
        ...base.decisionRail,
        reportDate: "2026-06-30",
      },
    };
    const fourthReason: VerdictPayload["reasons"][number] = {
      label: "不应显示的第四项",
      value: "+9.99 亿",
      detail: "只用于证明当前卡最多保留前三条来源记录。",
      tone: "warning",
    };

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          snapshotMeta={reviewSnapshotMeta()}
          reportDateContext={view.reportDateContext}
          reviewReasons={[...currentReviewReasons, fourthReason]}
        />
      </MemoryRouter>,
    );

    const reviewCard = screen.getByTestId("dashboard-home-action-queue-card");
    expect(
      within(reviewCard).getByRole("heading", {
        name: "复核依据",
        level: 2,
      }),
    ).toBeInTheDocument();
    expect(reviewCard).toHaveTextContent("复核参考");
    const reviewRegion = within(reviewCard).getByRole("region", {
      name: "复核依据",
    });
    expect(reviewRegion).toHaveAttribute("data-state", "ok");
    expect(reviewRegion).toHaveAttribute("tabindex", "0");
    expect(reviewRegion.getAttribute("aria-description")).toContain(
      "分析口径，仅供复核参考，报告日2026-06-30",
    );

    const rows = Array.from(
      reviewRegion.querySelectorAll<HTMLElement>("[data-review-basis-index]"),
    );
    expect(rows).toHaveLength(3);
    expect(
      rows.map((row) => ({
        index: row.dataset.reviewBasisIndex,
        tone: row.dataset.tone,
        label: row.querySelector("span")?.textContent,
        value: row.querySelector("strong")?.textContent,
        detail: row.querySelector("small")?.textContent,
      })),
    ).toEqual(
      currentReviewReasons.map((reason, index) => ({
        index: String(index + 1),
        tone: reason.tone,
        label: reason.label,
        value: reason.value,
        detail: reason.detail,
      })),
    );
    rows.forEach((row, index) => {
      const reason = currentReviewReasons[index];
      expect(row).toHaveAttribute(
        "aria-label",
        `${reason.label}：${reason.value}；${reason.detail}`,
      );
      expect(row).toHaveAttribute(
        "title",
        `${reason.label}：${reason.value}；${reason.detail}`,
      );
      const marker = row.querySelector("i");
      expect(marker).toHaveAttribute("aria-hidden", "true");
      expect(marker).not.toHaveAttribute("role");
    });

    expect(reviewCard).not.toHaveTextContent("不应显示的第四项");
    expect(reviewCard).not.toHaveTextContent("+9.99 亿");
    expect(reviewCard).not.toHaveTextContent(base.decisionRail.keyRisk);
    expect(reviewCard).not.toHaveTextContent(base.decisionRail.conclusion);
    expect(reviewCard).not.toHaveTextContent("协作消息");
    expect(reviewCard).not.toHaveTextContent("更多");
    expect(reviewCard).not.toHaveTextContent("负责人");
    expect(reviewCard).not.toHaveTextContent("提醒");
    expect(reviewCard).not.toHaveTextContent("预警");
    expect(reviewCard.querySelectorAll("a, button, img, time")).toHaveLength(0);
    const footer = within(reviewCard).getByTestId(
      "dashboard-home-review-basis-footer",
    );
    expect(footer).toHaveTextContent("首页快照 · 报告日 06-30");
    expect(footer).toHaveAttribute(
      "title",
      "来源：首页快照；报告日：2026-06-30",
    );
    currentReviewReasons.forEach((reason) => {
      expect(textOccurrences(reviewCard.textContent ?? "", reason.label)).toBe(1);
    });
  });

  it.each([
    ["loading", "复核依据加载中"],
    ["error", "复核依据暂不可用"],
  ] as const)(
    "suppresses review-basis rows for %s without inventing retained content",
    (dataStatusKind, expectedCopy) => {
      const base = firstScreenView();
      const view = firstScreenView({
        headerStatus: {
          ...base.headerStatus,
          dataStatusKind,
        },
      });

      render(
        <MemoryRouter>
          <DecisionRailSection
            decisionRail={view.decisionRail}
            reportDate={view.reportDate}
            dataSyncPrefix={view.headerStatus.dataSyncPrefix}
            dataStatusKind={dataStatusKind}
            snapshotMeta={reviewSnapshotMeta()}
            reportDateContext={view.reportDateContext}
            reviewReasons={currentReviewReasons}
          />
        </MemoryRouter>,
      );

      const reviewCard = screen.getByTestId("dashboard-home-action-queue-card");
      expect(reviewCard).toHaveTextContent(expectedCopy);
      expect(
        reviewCard.querySelectorAll("[data-review-basis-index]"),
      ).toHaveLength(0);
      expect(
        within(reviewCard).queryByRole("region", { name: "复核依据" }),
      ).not.toBeInTheDocument();
    },
  );

  it("fails closed for an empty verdict while retaining real snapshot provenance", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          snapshotMeta={reviewSnapshotMeta()}
          reportDateContext={view.reportDateContext}
          reviewReasons={[]}
        />
      </MemoryRouter>,
    );

    const reviewCard = screen.getByTestId("dashboard-home-action-queue-card");
    const reviewRegion = within(reviewCard).getByRole("region", {
      name: "复核依据",
    });
    expect(reviewRegion).toHaveAttribute("data-state", "empty");
    expect(reviewRegion).toHaveTextContent("暂无可核验复核依据");
    expect(reviewRegion).toHaveTextContent("首页快照 · 报告日 04-30");
    expect(reviewRegion.querySelectorAll("[data-review-basis-index]")).toHaveLength(0);
  });
  it("assigns each governed field to one rail card and deduplicates todo rows", () => {
    const base = firstScreenView();
    const view: DashboardHomeFirstScreenView = {
      ...base,
      decisionRail: {
        ...base.decisionRail,
        conclusion: "结论只属于最新动态",
        keyRisk: "信用利差走阔",
        maxContributionLabel: "Carry",
        maxContributionValue: "+0.20 亿",
        maxDragLabel: "利率变动",
        maxDragValue: "-0.10 亿",
        pendingSummary: "2 项待复核",
        actions: [
          {
            id: "review-credit",
            title: "复核信用风险",
            priority: "high",
            sourceLabel: "风险",
            reason: "信用利差需要复核",
            to: "/risk-overview?report_date=2026-04-30",
            statusKind: "ready",
          },
          {
            id: "review-credit-duplicate",
            title: "复核信用风险",
            priority: "high",
            sourceLabel: "风险",
            reason: "重复动作不应重复显示",
            to: "/risk-overview?report_date=2026-04-30",
            statusKind: "ready",
          },
        ],
        suggestions: [
          {
            id: "review-credit-unlinked",
            text: "复核信用风险",
          },
          {
            id: "offline-note",
            text: "记录线下复核结论",
          },
          {
            id: "open-duration",
            text: "打开久期分析",
            to: "/risk-tensor?report_date=2026-04-30",
          },
          {
            id: "document-source",
            text: "补充数据来源",
          },
          {
            id: "over-limit",
            text: "不应超过上限",
          },
        ],
      },
    };

    render(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={contributionAttribution()}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const riskCard = screen.getByTestId("dashboard-home-anomaly-card");
    const todoCard = screen.getByTestId("dashboard-home-review-entry-card");
    const reviewBasisCard = screen.getByTestId(
      "dashboard-home-action-queue-card",
    );
    const holdingCard = screen.getByTestId(
      "dashboard-home-data-quality-card",
    );
    const activityCard = screen.getByTestId(
      "dashboard-home-evidence-material-card",
    );

    expect(riskCard).toHaveTextContent("暂无可核验风险观察");
    expect(riskCard).not.toHaveTextContent("信用利差走阔");
    expect(holdingCard).not.toHaveTextContent("信用利差走阔");
    expect(holdingCard).toHaveTextContent("经营贡献观察");
    expect(holdingCard).toHaveTextContent("复核参考");
    expect(holdingCard).toHaveTextContent("Carry");
    expect(holdingCard).toHaveTextContent("+1.69 亿");
    expect(holdingCard).toHaveTextContent("Roll-down");
    expect(holdingCard).toHaveTextContent("-0.01 亿");
    expect(holdingCard).toHaveTextContent("信用利差");
    expect(holdingCard).toHaveTextContent("-0.03 亿");
    expect(holdingCard).toHaveTextContent("交易损益");
    expect(holdingCard).toHaveTextContent("+0.25 亿");
    expect(holdingCard).toHaveTextContent("其他");
    expect(holdingCard).toHaveTextContent("+0.00 亿");
    expect(holdingCard).not.toHaveTextContent("+1.90 亿");
    expect(holdingCard).not.toHaveTextContent("持仓提醒");
    expect(holdingCard).not.toHaveTextContent("预警");
    expect(holdingCard).not.toHaveTextContent("更多");
    expect(holdingCard.querySelectorAll("a, button, img, time")).toHaveLength(0);
    expect(
      Array.from(
        holdingCard.querySelectorAll<HTMLElement>("[data-contribution-kind]"),
      ).map((row) => row.dataset.contributionKind),
    ).toEqual(["carry", "roll", "credit", "trading", "other"]);
    expect(
      Array.from(
        holdingCard.querySelectorAll<HTMLElement>("[data-contribution-kind]"),
      ).map((row) => row.dataset.tone),
    ).toEqual(["positive", "negative", "negative", "positive", "neutral"]);
    const contributionRegion = within(holdingCard).getByRole("region", {
      name: "经营贡献观察",
    });
    expect(contributionRegion).toHaveAttribute("tabindex", "0");
    expect(contributionRegion.getAttribute("aria-description")).toContain(
      "产品类别级经营贡献拆解",
    );
    expect(riskCard).not.toHaveTextContent("+1.69 亿");
    expect(riskCard).not.toHaveTextContent("-0.03 亿");

    expect(todoCard).toHaveTextContent("2 项待复核");
    expect(textOccurrences(todoCard.textContent ?? "", "复核信用风险")).toBe(1);
    expect(
      within(todoCard).getByText("建议｜记录线下复核结论").closest("a"),
    ).toBeNull();
    expect(
      within(todoCard).getByRole("link", { name: "建议｜打开久期分析" }),
    ).toHaveAttribute("href", "/risk-tensor?report_date=2026-04-30");
    expect(todoCard).toHaveTextContent("建议｜补充数据来源");
    expect(todoCard).not.toHaveTextContent("不应超过上限");
    const todoRegion = within(todoCard).getByRole("region", {
      name: "待复核列表",
    });
    expect(
      todoRegion.querySelectorAll(
        ':scope > [title^="待复核："], :scope > [data-testid="dashboard-home-decision-action-row"], :scope > ul > li',
      ),
    ).toHaveLength(5);

    expect(reviewBasisCard).toHaveTextContent("复核依据");
    expect(reviewBasisCard).toHaveTextContent("暂无可核验复核依据");
    expect(reviewBasisCard).toHaveTextContent("暂无受管来源元数据");
    expect(reviewBasisCard).not.toHaveTextContent("结论只属于最新动态");
    expect(reviewBasisCard).not.toHaveTextContent("2 项待复核");

    const activityRows = within(activityCard).getByRole("region", {
      name: "最新动态明细",
    });
    expect(activityRows.children.length).toBeLessThanOrEqual(5);
    expect(activityRows).toHaveTextContent("结论只属于最新动态");
    expect(within(activityRows).queryByText("来源", { exact: true })).toBeNull();
    expect(activityCard).toHaveTextContent("来源");
    expect(textOccurrences(activityCard.textContent ?? "", "结论只属于最新动态")).toBe(1);
  });

  it("gates backend-gap zeros while preserving legitimate zero and partial null semantics", () => {
    const view = firstScreenView();
    const sourceAttribution = contributionAttribution();
    const backendGapAttribution = contributionAttribution({
      title: "无受控产品分类月度数据",
      segments: sourceAttribution.segments.map((segment) => ({
        ...segment,
        amount: numeric(0, "+0.00 亿", "yuan"),
      })),
    });

    const { rerender } = render(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={backendGapAttribution}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const holdingCard = screen.getByTestId(
      "dashboard-home-data-quality-card",
    );
    const contributionRegion = within(holdingCard).getByRole("region", {
      name: "经营贡献观察",
    });
    expect(holdingCard).toHaveTextContent("暂无数据");
    expect(contributionRegion).toHaveTextContent(
      "暂无可核验经营贡献拆解。",
    );
    expect(
      contributionRegion.querySelectorAll("[data-contribution-kind]"),
    ).toHaveLength(0);
    expect(holdingCard).not.toHaveTextContent("+0.00 亿");

    const legitimateZeroAttribution = contributionAttribution({
      segments: sourceAttribution.segments.map((segment) => ({
        ...segment,
        amount: numeric(0, "+0.00 亿", "yuan"),
      })),
    });
    rerender(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={legitimateZeroAttribution}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    expect(holdingCard).toHaveTextContent("复核参考");
    expect(
      contributionRegion.querySelectorAll("[data-contribution-kind]"),
    ).toHaveLength(5);
    expect(textOccurrences(contributionRegion.textContent ?? "", "+0.00 亿")).toBe(
      5,
    );
    expect(contributionRegion).not.toHaveTextContent(
      "暂无可核验经营贡献拆解。",
    );

    const partialAttribution = contributionAttribution({
      segments: sourceAttribution.segments.map((segment, index) =>
        index === 1
          ? {
              ...segment,
              amount: {
                ...segment.amount,
                raw: null,
                display: "+9.99 亿",
              },
            }
          : segment,
      ),
    });
    rerender(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={partialAttribution}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind="partial"
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    expect(holdingCard).toHaveTextContent("需复核");
    expect(
      contributionRegion.querySelectorAll("[data-contribution-kind]"),
    ).toHaveLength(5);
    const rollDownRow = contributionRegion.querySelector<HTMLElement>(
      '[data-contribution-kind="roll"]',
    );
    expect(rollDownRow).toHaveTextContent("Roll-down");
    expect(rollDownRow).toHaveTextContent("—");
    expect(rollDownRow).not.toHaveTextContent("+9.99 亿");

    rerender(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={sourceAttribution}
          contributionState={{ kind: "vendor_unavailable" }}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );
    expect(holdingCard).toHaveTextContent("不可用");
    expect(holdingCard).toHaveTextContent("经营贡献数据来源暂不可用");
    expect(
      within(holdingCard).queryByRole("region", {
        name: "经营贡献观察",
      }),
    ).toBeNull();
    expect(holdingCard).not.toHaveTextContent("Carry");

    rerender(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={sourceAttribution}
          contributionState={{
            kind: "explicit_miss",
            requested_date: "2026-04-30",
          }}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );
    expect(holdingCard).toHaveTextContent("指定日无数据");
    expect(holdingCard).toHaveTextContent("指定报告日暂无经营贡献数据");
    expect(holdingCard).not.toHaveTextContent("Carry");
  });

  it("keeps toolbar, hero, and rail in a loading state without inventing a failure outage", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: true,
    });
    expect(view.headerStatus.dataStatusKind).toBe("loading");

    render(
      <MemoryRouter>
        <DashboardHomeToolbar
          headerStatus={view.headerStatus}
          reportDateInput={view.reportDate}
          onReportDateChange={() => {}}
          reportDateContext={view.reportDateContext}
          toolbarSearch=""
          onSearchChange={() => {}}
          terminalKpis={view.terminalKpis}
          decisionActions={view.decisionRail.actions}
          allowPartial={false}
          onAllowPartialChange={() => {}}
          onRefresh={() => {}}
          refreshLabel="刷新"
        />
        <TerminalHomeFirstScreen view={view} />
        <DecisionRailSection
          contributionAttribution={contributionAttribution()}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-data-status")).toHaveTextContent("读取中");

    const reportIdentity = screen.getByTestId("dashboard-home-report-identity");
    expect(reportIdentity).toHaveTextContent("等待数据");
    expect(reportIdentity).toHaveTextContent("读取中");
    expect(reportIdentity).not.toHaveTextContent("未取得");

    const hero = screen.getByTestId("dashboard-home-morning-hero");
    expect(hero).toHaveTextContent("读取中");
    expect(hero).not.toHaveTextContent("未取得");

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(rail).toHaveTextContent("读取中");
    expect(rail).not.toHaveTextContent("未取得");
    expect(rail).not.toHaveTextContent("服务恢复后");
    expect(rail).not.toHaveTextContent("主动模已就绪");
    expect(rail).not.toHaveTextContent("2026-04-30 12:27");
    expect(
      screen.getByTestId("dashboard-home-data-quality-card"),
    ).toHaveTextContent("经营贡献数据加载中");
    expect(
      within(
        screen.getByTestId("dashboard-home-data-quality-card"),
      ).queryByRole("region", { name: "经营贡献观察" }),
    ).toBeNull();
    expect(
      screen
        .getByTestId("dashboard-home-data-quality-card")
        .querySelectorAll("[data-contribution-kind]"),
    ).toHaveLength(0);
    expect(
      screen.getByTestId("dashboard-home-data-quality-card"),
    ).not.toHaveTextContent("Carry");
  });

  it("surfaces the review entry as a true current-state card instead of a fake audit log", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const reviewEntryCard = screen.getByTestId("dashboard-home-review-entry-card");
    expect(reviewEntryCard).toHaveTextContent("待复核");
    expect(reviewEntryCard).toHaveTextContent("1 item");
    expect(reviewEntryCard).toHaveTextContent("Review risk workbench");
    expect(reviewEntryCard).toHaveTextContent("建议｜review duration");
    expect(textOccurrences(reviewEntryCard.textContent ?? "", "2 risk items require review")).toBe(1);
    expect(textOccurrences(reviewEntryCard.textContent ?? "", "暂无复核日志接口")).toBe(0);
    expect(reviewEntryCard).not.toHaveTextContent("复核记录");

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(rail).not.toHaveTextContent("复核人: 张三");
    expect(rail).not.toHaveTextContent("复核人: 李四");
    expect(rail).not.toHaveTextContent("复核人: 王五");
    expect(rail).not.toHaveTextContent("查看全部日志");
  });

  it("does not fabricate a pending review count when the snapshot has none", () => {
    const view = firstScreenView();
    const noPendingView: DashboardHomeFirstScreenView = {
      ...view,
      decisionRail: {
        ...view.decisionRail,
        pendingSummary: "",
      },
    };

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={noPendingView.decisionRail}
          reportDate={noPendingView.reportDate}
          dataSyncPrefix={noPendingView.headerStatus.dataSyncPrefix}
          dataStatusKind={noPendingView.headerStatus.dataStatusKind}
          reportDateContext={noPendingView.reportDateContext}
        />
      </MemoryRouter>,
    );

    const reviewEntryCard = screen.getByTestId("dashboard-home-review-entry-card");
    expect(reviewEntryCard).not.toHaveTextContent("1 item");
    expect(reviewEntryCard).not.toHaveTextContent("待复核");
    expect(reviewEntryCard).toHaveTextContent("Review risk workbench");
  });

  it("renders data status as a status label instead of the sync prefix", () => {
    const view = firstScreenView({
      headerStatus: {
        ...firstScreenView().headerStatus,
        dataStatusKind: "stale",
        dataSyncPrefix: "formal",
      },
    });

    render(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={contributionAttribution()}
          contributionState={{
            kind: "stale",
            effective_date: "2026-04-30",
          }}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const statusRow = screen.getByTestId("dashboard-home-rail-data-status");
    expect(statusRow).toHaveTextContent("偏旧");
    expect(statusRow).not.toHaveTextContent("formal");
    const holdingCard = screen.getByTestId(
      "dashboard-home-data-quality-card",
    );
    expect(holdingCard).toHaveTextContent("数据偏旧");
    expect(
      within(holdingCard).getByRole("region", {
        name: "经营贡献观察",
      }),
    ).toHaveAttribute("data-state", "stale");
    expect(
      holdingCard.querySelectorAll("[data-contribution-kind]"),
    ).toHaveLength(5);
  });

  it("uses the page-level failure copy for rail status when the snapshot is unavailable", () => {
    const view = firstScreenView({
      headerStatus: {
        ...firstScreenView().headerStatus,
        dataStatusKind: "error",
        dataSyncPrefix: "首页数据服务不可达",
      },
    });

    render(
      <MemoryRouter>
        <DecisionRailSection
          contributionAttribution={contributionAttribution()}
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-rail-data-status")).toHaveTextContent(
      "首页数据服务不可达",
    );
    expect(
      screen.getByTestId("dashboard-home-data-quality-card"),
    ).toHaveTextContent("经营贡献数据暂不可用");
    expect(
      screen
        .getByTestId("dashboard-home-data-quality-card")
        .querySelectorAll("[data-contribution-kind]"),
    ).toHaveLength(0);
    expect(
      screen.getByTestId("dashboard-home-data-quality-card"),
    ).not.toHaveTextContent("Carry");
  });

  it("surfaces the reserved source gap in business language instead of a raw 503", () => {
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={firstScreenView()} />
      </MemoryRouter>,
    );

    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    expect(sourceGate).toHaveTextContent("保留缺口");
    expect(sourceGate).toHaveTextContent("暂不可用");
    expect(sourceGate).not.toHaveTextContent("503");
    expect(within(sourceGate).getByTitle(/503/)).toHaveTextContent("暂不可用");
  });

  it("marks report-date-dependent source rows as unrequested after a hard snapshot error", () => {
    const view = firstScreenView({
      reportDate: "",
      reportDateContext: {
        requestedDate: "",
        actualDataDate: "",
        divergenceReason: null,
        dataAsOfDate: "",
        mode: "error",
      },
      headerStatus: {
        ...firstScreenView().headerStatus,
        dataStatusKind: "error",
        dataSyncPrefix: "首页快照权限不足",
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    expect(within(sourceGate).getByText("受管快照").parentElement).toHaveTextContent("失败");
    expect(within(sourceGate).getByText("正式台账").parentElement).toHaveTextContent("未请求");
    expect(within(sourceGate).getByText("分析上下文").parentElement).toHaveTextContent("未请求");
    expect(within(sourceGate).getAllByTitle("等待主快照报告日")).toHaveLength(2);
  });

  it("keeps report-date-dependent source rows unrequested for an empty snapshot", () => {
    const view = firstScreenView({
      reportDate: "",
      reportDateContext: {
        requestedDate: "",
        actualDataDate: "",
        divergenceReason: "暂无可用数据日",
        dataAsOfDate: "",
        mode: "empty",
      },
      headerStatus: {
        ...firstScreenView().headerStatus,
        dataStatusKind: "partial",
      },
    });

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    expect(within(sourceGate).getByText("正式台账").parentElement).toHaveTextContent("未请求");
    expect(within(sourceGate).getByText("分析上下文").parentElement).toHaveTextContent("未请求");
  });

  it("renders the four governed first-screen KPI contracts", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [
        { id: "aum", label: "资产规模", caliberLabel: null, value: numeric(1, "1.00", "yuan"), delta: numeric(0, "0.00", "yuan"), tone: "neutral", detail: "", history: null },
        { id: "yield", label: "年度损益", caliberLabel: null, value: numeric(2, "2.00", "yuan"), delta: numeric(0, "0.00", "yuan"), tone: "neutral", detail: "", history: null },
        { id: "nim", label: "净息差", caliberLabel: null, value: numeric(0.01, "1.00%", "pct"), delta: numeric(0, "0.00%", "pct"), tone: "neutral", detail: "", history: null },
        { id: "dv01", label: "组合 DV01", caliberLabel: null, value: numeric(3, "3.00", "dv01"), delta: numeric(0, "0.00", "dv01"), tone: "neutral", detail: "", history: null },
        { id: "duration", label: "加权久期", caliberLabel: null, value: numeric(4, "4.00"), delta: numeric(0, "0.00"), tone: "neutral", detail: "", history: null },
      ],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    const cards = within(screen.getByTestId("dashboard-home-hero-kpi-strip")).getAllByRole("article");
    expect(cards.map((card) => card.getAttribute("data-testid"))).toEqual([
      "dashboard-home-kpi-aum",
      "dashboard-home-kpi-yield",
      "dashboard-home-kpi-nim",
      "dashboard-home-kpi-dv01-wan",
    ]);
    expect(screen.queryByTestId("dashboard-home-kpi-duration")).not.toBeInTheDocument();
  });

  it("distinguishes a governed zero from a null KPI", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [
        { id: "aum", label: "资产规模", caliberLabel: null, value: numeric(0, "0.00", "yuan"), delta: numeric(0, "0.00", "yuan"), tone: "neutral", detail: "", history: null },
        { id: "yield", label: "年度损益", caliberLabel: null, value: { ...numeric(0, "0.00 亿", "yuan"), raw: null }, delta: numeric(0, "0.00", "yuan"), tone: "neutral", detail: "", history: null },
      ],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.terminalKpis.find((kpi) => kpi.id === "aum")?.state).toBe("ready");
    expect(view.terminalKpis.find((kpi) => kpi.id === "yield")?.state).toBe("empty");
    expect(view.terminalKpis.find((kpi) => kpi.id === "yield")?.delta).toBe("—");
    expect(view.terminalKpis.find((kpi) => kpi.id === "yield")?.deltaTone).toBe("muted");

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("0.00亿");
    expect(screen.getByTestId("dashboard-home-kpi-yield")).toHaveTextContent("—");
    expect(screen.getByTestId("dashboard-home-kpi-yield")).not.toHaveTextContent(
      "0.00亿",
    );
    expect(screen.getByTestId("dashboard-home-kpi-yield")).not.toHaveTextContent(
      "较前日 0.00",
    );
  });

  it("keeps a zero-action snapshot neutral without inventing a sync task", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: { conclusion: "stable", tone: "neutral", reasons: [], suggestions: [] },
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    expect(view.decisionRail.pendingSummary).toBe("暂无");
    expect(view.decisionRail.suggestions).toEqual([]);
  });

  it("renders the governed product-category headline and its explicit empty state", () => {
    const readyView = {
      ...firstScreenView(),
      productCategoryHeadline: {
        state: "ready",
        metrics: [
          { id: "ytd-summary-pnl", label: "年度汇总损益", value: "+12.30 亿元", detail: "后端口径" },
          { id: "monthly-income", label: "本月收入", value: "+1.20 亿元", detail: "后端口径" },
        ],
      },
    } as DashboardHomeFirstScreenView;

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={readyView} />
      </MemoryRouter>,
    );
    const headline = screen.getByTestId("dashboard-home-product-category-headline");
    expect(headline).toHaveTextContent("年度汇总损益");
    expect(headline).toHaveTextContent("+12.30 亿元");

    const emptyView = {
      ...firstScreenView(),
      productCategoryHeadline: { state: "empty", metrics: [] },
    } as DashboardHomeFirstScreenView;
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={emptyView} />
      </MemoryRouter>,
    );
    expect(screen.getByText("暂无产品分类经营摘要")).toBeInTheDocument();
  });
  it("surfaces the concrete missing domain ids in the source gate and data-quality rail", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      domainsMissing: ["balance_sheet", "pnl"],
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: false,
    });

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          reportDateContext={view.reportDateContext}
          missingDomains={view.missingDomains}
        />
      </MemoryRouter>,
    );

    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    expect(sourceGate).toHaveTextContent("balance_sheet");
    expect(sourceGate).toHaveTextContent("pnl");
    const latestActivity = screen.getByTestId(
      "dashboard-home-evidence-material-card",
    );
    expect(latestActivity).toHaveTextContent("balance_sheet");
    expect(latestActivity).toHaveTextContent("pnl");
  });

  it("keeps generated_at as the rail update time when a governed snapshot needs review", () => {
    const view = firstScreenView({
      headerStatus: {
        ...firstScreenView().headerStatus,
        dataStatusKind: "stale",
        dataSyncPrefix: "部分数据域缺失，需复核",
      },
    });
    const snapshotMeta: ResultMeta = {
      trace_id: "trace-home",
      basis: "formal",
      result_kind: "home_snapshot",
      formal_use_allowed: false,
      source_version: "source-v1",
      vendor_version: "vendor-v1",
      rule_version: "rule-v1",
      cache_version: "cache-v1",
      quality_flag: "warning",
      vendor_status: "vendor_stale",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-05-01T08:42:00+08:00",
    };

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          snapshotMeta={snapshotMeta}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const latestActivity = screen.getByTestId(
      "dashboard-home-evidence-material-card",
    );
    const activityRegion = within(latestActivity).getByRole("region", {
      name: "最新动态明细",
    });
    expect(
      Array.from(activityRegion.children).map((row) =>
        row.getAttribute("data-activity-kind"),
      ),
    ).toEqual([
      "report-date",
      "snapshot-generated",
      "conclusion",
      "formal-use",
      "missing-domains",
    ]);
    expect(activityRegion).toHaveAttribute("tabindex", "0");

    const reportDateTime = within(
      screen.getByTestId("dashboard-home-rail-report-date"),
    ).getByText("2026-04-30");
    expect(reportDateTime.tagName).toBe("TIME");
    expect(reportDateTime).toHaveAttribute("datetime", "2026-04-30");

    const generatedAt = screen.getByTestId(
      "dashboard-home-rail-updated-at",
    );
    expect(generatedAt.tagName).toBe("TIME");
    expect(generatedAt).toHaveAttribute(
      "datetime",
      "2026-05-01T08:42:00+08:00",
    );
    expect(generatedAt).toHaveTextContent(
      "2026-05-01 08:42 UTC+08:00",
    );
    expect(generatedAt).not.toHaveTextContent("沿用报告日");
    expect(latestActivity).toHaveTextContent("来源首页快照");
    expect(latestActivity).not.toHaveTextContent("更多动态");
    expect(within(latestActivity).queryByRole("link")).not.toBeInTheDocument();
    expect(within(latestActivity).queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("DecisionRailSection governed usage", () => {
  it.each(["partial", "fallback", "stale"] as const)(
    "forces %s snapshots to review-only even when metadata allows formal use",
    (dataStatusKind) => {
      const view = firstScreenView({
        headerStatus: {
          ...firstScreenView().headerStatus,
          dataStatusKind,
          dataSyncPrefix: "主链需复核",
        },
      });
      const snapshotMeta: ResultMeta = {
        trace_id: "trace-home-formal-use",
        basis: "formal",
        result_kind: "home_snapshot",
        formal_use_allowed: true,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        rule_version: "rule-v1",
        cache_version: "cache-v1",
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        generated_at: "2026-05-01T08:42:00+08:00",
      };

      render(
        <MemoryRouter>
          <DecisionRailSection
            decisionRail={view.decisionRail}
            reportDate={view.reportDate}
            dataSyncPrefix={view.headerStatus.dataSyncPrefix}
            dataStatusKind={dataStatusKind}
            snapshotMeta={snapshotMeta}
            reportDateContext={view.reportDateContext}
            reviewReasons={currentReviewReasons}
          />
        </MemoryRouter>,
      );

      const reviewBasis = screen.getByTestId(
        "dashboard-home-action-queue-card",
      );
      expect(reviewBasis).toHaveTextContent(
        dataStatusKind === "stale" ? "数据偏旧" : "需复核",
      );
      const reviewRegion = within(reviewBasis).getByRole("region", {
        name: "复核依据",
      });
      expect(reviewRegion).toHaveAttribute("data-state", dataStatusKind);
      expect(
        reviewRegion.querySelectorAll("[data-review-basis-index]"),
      ).toHaveLength(3);

      const latestActivity = screen.getByTestId(
        "dashboard-home-evidence-material-card",
      );
      expect(latestActivity).toHaveTextContent("复核参考");
      expect(latestActivity).not.toHaveTextContent("正式经营决策");
    },
  );
});
