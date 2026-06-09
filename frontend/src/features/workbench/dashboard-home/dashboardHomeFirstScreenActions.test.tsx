import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { Numeric, VerdictPayload } from "../../../api/contracts";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen";
import { mapToHomeFirstScreenView } from "./dashboardHomeFirstScreenView";
import type { DashboardHomeFirstScreenView } from "./dashboardHomeFirstScreenTypes";

type DecisionActionForTest = {
  id: string;
  title: string;
  to?: string;
  sourceLabel: string;
  reason: string;
  statusKind: string;
};

const verdict: VerdictPayload = {
  conclusion: "review portfolio duration",
  tone: "warning",
  reasons: [{ label: "duration", value: "4.20", detail: "duration moved higher", tone: "warning" }],
  suggestions: [{ text: "review duration", link: "/risk-tensor" }],
};

function numeric(raw: number, display: string, unit: Numeric["unit"] = "ratio"): Numeric {
  return {
    raw,
    display,
    unit,
    precision: 2,
    sign_aware: false,
  };
}

function decisionActions(view: DashboardHomeFirstScreenView): readonly DecisionActionForTest[] {
  return ((view.decisionRail as { actions?: readonly DecisionActionForTest[] }).actions ?? []);
}

function firstScreenView(
  overrides: Partial<DashboardHomeFirstScreenView> = {},
): DashboardHomeFirstScreenView {
  return {
    reportDate: "2026-04-30",
    useMockFallback: false,
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
      keyRisk: "duration",
      suggestions: ["review duration"],
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
    ],
    keyRiskStrip: [
      {
        id: "duration",
        label: "Duration",
        value: "4.20",
        delta: "0.10",
        deltaTone: "warn",
      },
    ],
    ...overrides,
  };
}

describe("dashboard home first-screen actions", () => {
  it("preserves backend suggestion links and adds the risk review queue action", () => {
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
          title: "review duration",
          to: "/risk-tensor?report_date=2026-04-30",
          sourceLabel: "风险张量",
          statusKind: "ready",
        }),
        expect.objectContaining({
          id: "risk-review-queue",
          to: "/decision-items?source=dashboard-home&report_date=2026-04-30&action_id=risk-review-queue",
          sourceLabel: "待办",
        }),
      ]),
    );
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
          sourceLabel: "待办",
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
          sourceLabel: "待办",
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

    expect(decisionActions(view)).toEqual([
      expect.objectContaining({
        title: "review linked duration date",
        to: "/risk-tensor?report_date=2026-04-30&tab=dv01#bucket",
        sourceLabel: "风险张量",
      }),
    ]);
  });

  it("does not surface generic directionality copy as a business conclusion", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: {
        ...verdict,
        conclusion: "首屏整体偏多，可基于规模与收益做方向性判断",
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

    expect(view.decisionRail.conclusion).toBe(
      "债券资产规模 3,666.40亿，年度损益（不扣FTP） +36.39亿；趋势判断待复核。",
    );
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
        expect.objectContaining({ id: "risk-dv01", value: "9,812,345.00" }),
        expect.objectContaining({ id: "risk-duration", value: "4.18" }),
        expect.objectContaining({ id: "risk-credit", value: "62.10%" }),
        expect.objectContaining({ id: "risk-top5", value: "41.20%" }),
      ]),
    );
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
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
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
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
        />
      </MemoryRouter>,
    );

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(rail).toHaveTextContent("进入对应页面核对明细");
    expect(rail).not.toHaveTextContent("主快照回传入口");
  });

  it("anchors the first screen on business judgment instead of snapshot containers", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
        />
      </MemoryRouter>,
    );

    const hero = screen.getByTestId("dashboard-home-hero");
    expect(hero).toHaveTextContent("今日经营判断");
    expect(hero).toHaveTextContent("关键指标");
    expect(hero).toHaveTextContent("review portfolio duration");
    expect(hero).not.toHaveTextContent("主快照");

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(rail).toHaveTextContent("判断依据");
    expect(rail).toHaveTextContent("下一步");
    expect(rail).toHaveTextContent("数据口径");
    expect(rail).not.toHaveTextContent("复核记录");
    expect(rail).not.toHaveTextContent("来源台账");
    expect(rail).not.toHaveTextContent("主快照回传入口");
  });

  it("routes the first-screen risk strip to the real risk overview page", () => {
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={firstScreenView()} />
      </MemoryRouter>,
    );

    const marketPanel = screen.getByTestId("dashboard-home-market");
    expect(within(marketPanel).getByRole("link")).toHaveAttribute("href", "/risk-overview");
  });
});
