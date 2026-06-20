import type { DashboardHomeFirstScreenView } from "./dashboardHomeFirstScreenTypes";
import {
  HOME_FIRST_SCREEN_FALLBACK_HEADER_STATUS,
  HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE,
  HOME_FIRST_SCREEN_MARKET_PULSE_FALLBACK,
} from "./homeFirstScreenFallback";

function reportDatePath(path: string | null | undefined, reportDate: string): string | undefined {
  const trimmed = path?.trim();
  if (!trimmed || !trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return undefined;
  }

  try {
    const url = new URL(trimmed, "http://moss.local");
    if (reportDate) {
      url.searchParams.set("report_date", reportDate);
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return undefined;
  }
}

export function createMockHomeFirstScreenView(): DashboardHomeFirstScreenView {
  return {
    reportDate: HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE,
    useMockFallback: true,
    headerStatus: {
      dataStatusKind: "ok",
      dataUpdatedAt: HOME_FIRST_SCREEN_FALLBACK_HEADER_STATUS.dataUpdatedAt,
      marketStatus: HOME_FIRST_SCREEN_FALLBACK_HEADER_STATUS.marketStatus,
      valuationLabel: "估值已完成",
      valuationTone: "ok",
      riskReviewCount: 3,
      showRiskReview: true,
      dataSyncPrefix: "样例已加载",
    },
    decisionRail: {
      conclusion:
        "样例组合收益主要受利率上行拖累，信用利差收窄对冲了部分回撤。",
      maxDragLabel: "利率变动",
      maxDragValue: "-512.34",
      maxContributionLabel: "信用利差",
      maxContributionValue: "+286.21",
      keyRisk: "Top5 集中度 41.35%；久期较前期小幅抬升。",
      suggestions: [
        "复核长久期账户约束",
        "检查 Top5 主体集中暴露",
        "跟踪曲线陡峭化风险",
      ],
      actions: [
        {
          id: "risk-overview",
          title: "复核风险总览",
          priority: "high",
          sourceLabel: "risk",
          reason: "3 项风险事项需要复核",
          to: reportDatePath("/risk-overview", HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE),
          statusKind: "ready",
        },
        {
          id: "risk-tensor",
          title: "打开风险张量",
          priority: "medium",
          sourceLabel: "risk-tensor",
          reason: "定位久期与利率风险贡献",
          to: reportDatePath("/risk-tensor", HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE),
          statusKind: "ready",
        },
      ],
      pendingSummary: "4 项，1 项高优先级",
      reportDate: HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE,
      dataUpdatedAt: HOME_FIRST_SCREEN_FALLBACK_HEADER_STATUS.dataUpdatedAt,
      dataSyncPrefix: "样例已加载",
    },
    terminalKpis: [
      {
        id: "aum",
        label: "组合市值",
        value: "3,708.10",
        unit: "亿元",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [3650, 3668, 3680, 3695, 3700, 3705, 3706, 3708],
        state: "ready",
      },
      {
        id: "bond-market-value",
        label: "债券市值",
        value: "3,708.10",
        unit: "亿元",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [3600, 3620, 3655, 3660, 3678, 3688, 3708],
        state: "ready",
      },
      {
        id: "unrealized-pnl",
        label: "浮动盈亏",
        value: "+18.42",
        unit: "亿元",
        delta: "样例模式",
        deltaTone: "up",
        sparkline: [8, 11, 10, 13, 15, 18],
        state: "ready",
      },
      {
        id: "day-pnl",
        label: "月度盈亏",
        value: "+0.85",
        unit: "亿元",
        delta: "样例模式",
        deltaTone: "up",
        sparkline: [0.2, 0.3, 0.4, 0.5, 0.85],
        state: "ready",
      },
      {
        id: "duration",
        label: "加权久期",
        value: "4.23",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [4.1, 4.12, 4.18, 4.23],
        state: "ready",
      },
      {
        id: "ytm",
        label: "组合 YTM",
        value: "2.3684",
        unit: "%",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [2.3, 2.33, 2.35, 2.36],
        state: "ready",
      },
      {
        id: "credit-ratio",
        label: "信用债占比",
        value: "92.36",
        unit: "%",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [91, 92, 91.8, 92.36],
        state: "ready",
      },
    ],
    keyRiskStrip: HOME_FIRST_SCREEN_MARKET_PULSE_FALLBACK.slice(0, 8).map((item) => ({
      id: item.id,
      label: item.label,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone === "up" ? "up" : item.deltaTone === "down" ? "down" : "flat",
    })),
  };
}
