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
          value: numeric(4.37, "4.37", "dv01"),
          delta: { ...numeric(-0.05, "-0.05", "dv01"), sign_aware: true },
          tone: "warning",
          detail: "portfolio_modified_duration",
          history: [4.42, 4.37],
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
          value: "4.37",
        }),
      ]),
    );
    expect(view.terminalKpis.find((kpi) => kpi.id === "dv01")?.delta).toContain("-0.05");

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-kpi-dv01")).toHaveTextContent("4.37");
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
        expect.objectContaining({ id: "risk-dv01", value: "9,812,345.00" }),
        expect.objectContaining({ id: "risk-duration", value: "4.18" }),
        expect.objectContaining({ id: "risk-credit", value: "62.10%" }),
        expect.objectContaining({ id: "risk-top5", value: "41.20%" }),
      ]),
    );
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
    ).not.toHaveTextContent("review duration");
    expect(
      within(rail).getByTestId("dashboard-home-action-queue-card"),
    ).toHaveTextContent("review duration");
    expect(textOccurrences(rail.textContent ?? "", "review duration")).toBe(1);
  });

  it("anchors the first screen on a morning-judgment hero and operational right rail", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
        <DecisionRailSection
          decisionRail={view.decisionRail}
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
    expect(screen.getByTestId("dashboard-home-ambient-canvas")).toHaveAttribute("aria-hidden", "true");

    const heroKpiStrip = screen.getByTestId("dashboard-home-hero-kpi-strip");
    expect(within(heroKpiStrip).getAllByRole("article")).toHaveLength(4);

    expect(screen.queryByTestId("dashboard-home-signal-workspace")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-market")).not.toBeInTheDocument();

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(within(rail).getByTestId("dashboard-home-review-entry-card")).toHaveTextContent("待复核");
    expect(within(rail).getByTestId("dashboard-home-action-queue-card")).toHaveTextContent(
      "决策建议",
    );
    expect(within(rail).getByTestId("dashboard-home-data-quality-card")).toHaveTextContent(
      "数据质量",
    );
    expect(rail).not.toHaveTextContent("复核记录");
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
    expect(reviewEntryCard).toHaveTextContent("暂无复核日志接口");
    expect(textOccurrences(reviewEntryCard.textContent ?? "", "2 risk items require review")).toBe(1);
    expect(textOccurrences(reviewEntryCard.textContent ?? "", "暂无复核日志接口")).toBe(1);
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
    expect(reviewEntryCard).toHaveTextContent("暂无");
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

  it("renders only the four governed PAGE-DASH KPI contracts", () => {
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
      "dashboard-home-kpi-dv01",
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
    const dataQuality = screen.getByTestId("dashboard-home-data-quality-card");
    expect(dataQuality).toHaveTextContent("balance_sheet");
    expect(dataQuality).toHaveTextContent("pnl");
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

    expect(screen.getByTestId("dashboard-home-rail-updated-at")).toHaveTextContent(
      "2026-05-01 08:42",
    );
    expect(screen.getByTestId("dashboard-home-rail-updated-at")).not.toHaveTextContent(
      "沿用报告日",
    );
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
          />
        </MemoryRouter>,
      );

      const dataQuality = screen.getByTestId("dashboard-home-data-quality-card");
      expect(dataQuality).toHaveTextContent("复核参考");
      expect(dataQuality).not.toHaveTextContent("正式经营决策");
    },
  );
});
