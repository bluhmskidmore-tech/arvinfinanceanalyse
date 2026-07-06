import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/echarts", () => ({
  default: () => null,
}));

import type { Numeric, VerdictPayload } from "../../../api/contracts";
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
      {
        id: "pnl",
        label: "PnL",
        value: "+20.00",
        delta: "+1.20",
        deltaTone: "up",
        sparkline: [18, 19, 20],
        state: "ready",
      },
      {
        id: "spread",
        label: "Spread",
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
          statusKind: "ready",
        }),
        expect.objectContaining({
          id: "risk-review-queue",
          to: "/decision-items?source=dashboard-home&report_date=2026-04-30&action_id=risk-review-queue",
          statusKind: "ready",
        }),
      ]),
    );
  });

  it("hydrates the first-screen duration KPI from home snapshot metrics", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [
        {
          id: "duration",
          label: "加权久期",
          caliberLabel: "利率风险资产口径",
          value: numeric(4.37, "4.37", "ratio"),
          delta: { ...numeric(-0.05, "-0.05", "ratio"), sign_aware: true },
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
          id: "duration",
          value: "4.37",
        }),
      ]),
    );
    expect(view.terminalKpis.find((kpi) => kpi.id === "duration")?.delta).toContain("-0.05");

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-kpi-duration")).toHaveTextContent("4.37");
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

    expect(decisionActions(view)).toEqual([
      expect.objectContaining({
        title: "review linked duration date",
        to: "/risk-tensor?report_date=2026-04-30&tab=dv01#bucket",
      }),
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
    expect(rail).toHaveTextContent("review duration");
    expect(rail).not.toHaveTextContent("回传入口");
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
        />
      </MemoryRouter>,
    );

    const hero = screen.getByTestId("dashboard-home-morning-hero");
    expect(hero).toHaveTextContent("早间决策一览");
    expect(hero).toHaveTextContent("review portfolio duration");
    expect(screen.getByTestId("dashboard-home-report-identity")).toHaveTextContent("2026-04-30");
    expect(screen.getByTestId("dashboard-home-ambient-canvas")).toHaveAttribute("aria-hidden", "true");

    const heroKpiStrip = screen.getByTestId("dashboard-home-hero-kpi-strip");
    expect(within(heroKpiStrip).getAllByTestId(/dashboard-home-hero-kpi-/)).toHaveLength(4);

    const workspace = screen.getByTestId("dashboard-home-signal-workspace");
    expect(workspace).toHaveTextContent("risk workspace");
    expect(workspace).toHaveTextContent("attribution pulse");
    expect(workspace).toHaveTextContent("source linked");
    expect(workspace).toHaveTextContent("market & macro");
    expect(workspace).toHaveTextContent("asset allocation");
    expect(workspace).toHaveTextContent("rates -1.00");
    expect(workspace).toHaveTextContent("carry +0.20");
    expect(workspace).toHaveTextContent("待接入");

    const rail = screen.getByTestId("dashboard-home-decision-rail");
    expect(within(rail).getByTestId("dashboard-home-review-entry-card")).toHaveTextContent("待复核");
    expect(within(rail).getByTestId("dashboard-home-action-queue-card")).toHaveTextContent(
      "待办事项",
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
          toolbarSearch=""
          onSearchChange={() => {}}
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
