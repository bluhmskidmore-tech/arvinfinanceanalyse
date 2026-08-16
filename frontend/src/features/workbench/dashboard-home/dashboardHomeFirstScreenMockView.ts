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
    reportDateContext: {
      requestedDate: "",
      actualDataDate: HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE,
      divergenceReason: "样例数据日",
      dataAsOfDate: HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE,
      generatedAt: `${HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE} ${HOME_FIRST_SCREEN_FALLBACK_HEADER_STATUS.dataUpdatedAt}`,
      mode: "mock",
    },
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
      hasDrag: true,
      hasContribution: true,
      keyRisk: "Top5 集中度 41.35%；久期较前期小幅抬升。",
      suggestions: [
        {
          id: "mock-suggestion-duration",
          text: "复核长久期账户约束",
          to: reportDatePath("/risk-overview", HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE),
        },
        {
          id: "mock-suggestion-concentration",
          text: "检查 Top5 主体集中暴露",
          to: reportDatePath(
            "/concentration-monitor",
            HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE,
          ),
        },
        {
          id: "mock-suggestion-curve",
          text: "跟踪曲线陡峭化风险",
          to: reportDatePath("/risk-tensor", HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE),
        },
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
    productCategoryHeadline: {
      state: "ready",
      metrics: [
        {
          id: "summary_pnl",
          label: "年度损益",
          value: "+12.40 亿元",
          detail: "样例模式 · 不可用于正式经营决策",
        },
        {
          id: "operating_income",
          label: "经营净收入",
          value: "+8.90 亿元",
          detail: "样例模式 · 不可用于正式经营决策",
        },
        {
          id: "intermediate_business_income",
          label: "中间业务收入",
          value: "+3.50 亿元",
          detail: "样例模式 · 不可用于正式经营决策",
        },
        {
          id: "monthly_income",
          label: "月度损益",
          value: "+1.20 亿元",
          detail: "样例模式 · 不可用于正式经营决策",
        },
      ],
    },
    missingDomains: [],
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
        id: "yield",
        label: "年度损益",
        value: "+12.40",
        unit: "亿元",
        delta: "样例模式",
        deltaTone: "up",
        sparkline: [8.2, 9.1, 9.8, 10.6, 11.5, 12.4],
        state: "ready",
      },
      {
        id: "nim",
        label: "净息差",
        value: "1.82",
        unit: "%",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [1.78, 1.79, 1.8, 1.8, 1.81, 1.82],
        state: "ready",
      },
      {
        id: "dv01",
        label: "组合 DV01",
        value: "106,224",
        unit: "元/bp",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [101200, 102600, 103400, 104800, 105600, 106224],
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
