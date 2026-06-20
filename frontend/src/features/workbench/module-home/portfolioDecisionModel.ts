import type {
  BondDashboardHeadlinePayload,
  PnlAttributionAnalysisSummary,
  RiskIndicatorsPayload,
} from "../../../api/contracts";
import {
  formatDv01Wan,
  formatRatePercent,
  nativeToNumber,
} from "../../bond-dashboard/utils/format";
import type {
  ModuleHomeDecision,
  ModuleHomeDetailPanel,
  ModuleHomeDetailRow,
  ModuleHomeTone,
  ModuleHomeViewBody,
} from "./moduleHomeModel";
import type { PortfolioReadinessGate } from "./portfolioReadinessGate";

export type PortfolioReadPathState = {
  label: string;
  tone: ModuleHomeTone;
};

export type PortfolioPnlState = {
  label: string;
  tone: ModuleHomeTone;
};

export type PortfolioEvidenceState = {
  factValue: string;
  detail: string;
  tone: ModuleHomeTone;
};

export function pnlDriverLabel(driver: PnlAttributionAnalysisSummary["primary_driver"]) {
  if (driver === "volume") {
    return "规模";
  }
  if (driver === "rate") {
    return "利率";
  }
  if (driver === "market") {
    return "市场";
  }
  return "待确认";
}

function buildPortfolioActionQueue(args: {
  creditRatio: number | null;
  duration: number | null;
  pnlSummary: PnlAttributionAnalysisSummary | undefined;
  hasCoreReads: boolean;
  readPath: PortfolioReadPathState;
  readiness: PortfolioReadinessGate;
}) {
  if (args.readPath.tone === "error") {
    return "先复核失败读链路，再进入下钻页，不使用前端补数。";
  }
  if (!args.readiness.coreRender) {
    return "等待核心读数返回，不形成组合动作。";
  }
  if (!args.readiness.decisionReady) {
    return "先复核来源证据、日期和回退状态，不形成调仓建议。";
  }
  if (!args.readiness.riskClosureReady) {
    return "先复核风险张量日期闭合状态，不形成风险闭合判断。";
  }
  if (!args.hasCoreReads) {
    return "等待债券总览和风险指标返回后再形成组合动作。";
  }
  if (args.creditRatio !== null && args.creditRatio >= 0.3) {
    return "先看评级/行业集中度，再决定是否降信用或换券。";
  }
  if (args.duration !== null && args.duration >= 4.5) {
    return "优先复核久期和 DV01，再决定是否缩短利率暴露。";
  }
  if (!args.pnlSummary) {
    return "补看损益归因摘要，确认收益驱动后再下钻。";
  }
  return "维持观察，按子组合、收益率和利差面板继续核验。";
}

function buildPortfolioDecisionActions(args: {
  creditRatio: number | null;
  duration: number | null;
  pnlSummary: PnlAttributionAnalysisSummary | undefined;
  portfolioRows: ModuleHomeDetailRow[];
  readPath: PortfolioReadPathState;
  readiness: PortfolioReadinessGate;
}): ModuleHomeDecision["actions"] {
  if (args.readPath.tone === "error") {
    return [
      {
        title: "读链路复核",
        evidence: "资产负债、债券总览、持仓或归因读链路失败；先查正式页面状态。",
        path: "/portfolio",
        tone: "error",
        label: "回到首页",
      },
    ];
  }

  if (!args.readiness.decisionReady) {
    return [
      {
        title: "来源证据复核",
        evidence: args.readiness.blockingReasons.join("；") || "来源证据未达到决策级口径。",
        path: "/portfolio",
        tone: "error",
        label: "证据",
      },
      {
        title: "债券总览核对",
        evidence: "核对 bond-dashboard 的 result_meta、正式使用许可、质量标记和报告日。",
        path: "/bond-dashboard",
        tone: "watch",
        label: "债券总览",
      },
      {
        title: "收益归因复核",
        evidence: "核对 pnl-attribution 的正式口径、质量标记和报告日。",
        path: "/pnl-attribution",
        tone: "watch",
        label: "收益归因",
      },
    ];
  }

  if (!args.readiness.riskClosureReady) {
    return [
      {
        title: "风险张量日期复核",
        evidence: args.readiness.riskClosureFact,
        path: "/risk-tensor",
        tone: "watch",
        label: "风险张量",
      },
      {
        title: "债券总览核对",
        evidence: "组合值继续显示；先确认同日风险张量闭合后再提升结论口径。",
        path: "/bond-dashboard",
        tone: "watch",
        label: "债券总览",
      },
      {
        title: "收益归因复核",
        evidence: "确认本期收益驱动与风险闭合日期一致。",
        path: "/pnl-attribution",
        tone: "watch",
        label: "收益归因",
      },
    ];
  }

  const actions: NonNullable<ModuleHomeDecision["actions"]> = [];

  if (args.creditRatio !== null && args.creditRatio >= 0.3) {
    actions.push({
      title: "信用结构复核",
      evidence: `信用占比 ${formatRatePercent(args.creditRatio)}%，先看评级、行业与集中度。`,
      path: "/bond-dashboard",
      tone: "watch",
      label: "债券总览",
    });
  }

  if (args.duration !== null && args.duration >= 4.5) {
    actions.push({
      title: "久期 DV01 复核",
      evidence: `加权久期 ${args.duration.toFixed(2)} 年，复核利率风险和 DV01。`,
      path: "/bond-dashboard",
      tone: "watch",
      label: "债券总览",
    });
  }

  if (!args.pnlSummary) {
    actions.push({
      title: "收益归因补读",
      evidence: "归因摘要待读，进入归因页确认本期收益驱动。",
      path: "/pnl-attribution",
      tone: "watch",
      label: "收益归因",
    });
  }

  actions.push({
    title: "子组合分层核验",
    evidence:
      args.portfolioRows.length > 0
        ? `已返回 ${args.portfolioRows.length} 个子组合，按组合层级复核规模、YTM 与 DV01。`
        : "子组合对比未返回，先确认组合分层读链路。",
    path: "/bond-dashboard",
    tone: args.portfolioRows.length > 0 ? "ok" : "muted",
    label: "债券总览",
  });

  return actions.slice(0, 3);
}

export function buildPortfolioDecision(args: {
  bondKpis: BondDashboardHeadlinePayload["kpis"] | undefined;
  risk: RiskIndicatorsPayload | undefined;
  pnlSummary: PnlAttributionAnalysisSummary | undefined;
  bondDate: string;
  portfolioRows: ModuleHomeDetailRow[];
  readPath: PortfolioReadPathState;
  pnlState: PortfolioPnlState;
  evidenceState: PortfolioEvidenceState;
  readiness: PortfolioReadinessGate;
}): ModuleHomeDecision {
  const creditRatio = args.risk ? nativeToNumber(args.risk.credit_ratio) : null;
  const duration =
    args.bondKpis?.weighted_duration !== undefined
      ? nativeToNumber(args.bondKpis.weighted_duration)
      : args.risk
        ? nativeToNumber(args.risk.weighted_duration)
        : null;
  const hasCoreReads = Boolean(args.bondKpis || args.risk);
  const actionQueue = buildPortfolioActionQueue({
    creditRatio,
    duration,
    pnlSummary: args.pnlSummary,
    hasCoreReads,
    readPath: args.readPath,
    readiness: args.readiness,
  });
  const actions = buildPortfolioDecisionActions({
    creditRatio,
    duration,
    pnlSummary: args.pnlSummary,
    portfolioRows: args.portfolioRows,
    readPath: args.readPath,
    readiness: args.readiness,
  });

  let conclusion = "核心读数待返回，暂不形成调仓建议";
  let tone: ModuleHomeTone = args.readiness.tone;

  if (args.readPath.tone === "error") {
    conclusion = "读链路异常，先复核数据再决策";
    tone = "error";
  } else if (!args.readiness.coreRender) {
    conclusion = "核心读数待返回，暂不形成调仓建议";
    tone = "watch";
  } else if (!args.readiness.decisionReady) {
    conclusion = "仅供分析：来源证据未达到决策级口径";
    tone = "watch";
  } else if (!args.readiness.riskClosureReady) {
    conclusion = "仅供监控：风险张量未同日闭合";
    tone = "watch";
  } else if (creditRatio !== null && creditRatio >= 0.5) {
    conclusion = "信用仓位偏高，优先复核信用与集中度";
    tone = "watch";
  } else if (creditRatio !== null && creditRatio >= 0.3) {
    conclusion = "信用暴露需复核，维持久期前先看信用结构";
    tone = "watch";
  } else if (duration !== null && duration >= 4.5) {
    conclusion = "久期接近首屏监控阈值，先复核利率风险";
    tone = "watch";
  } else if (hasCoreReads) {
    conclusion = "组合风险收益读数可读，维持观察并下钻核验";
  }

  const dv01Value =
    args.bondKpis?.total_dv01 !== undefined
      ? `${formatDv01Wan(args.bondKpis.total_dv01)} 万元`
      : args.risk
        ? `${formatDv01Wan(args.risk.total_dv01)} 万元`
        : "-";
  const creditValue = args.risk ? `${formatRatePercent(args.risk.credit_ratio)}%` : "-";
  const attributionValue = args.pnlSummary
    ? pnlDriverLabel(args.pnlSummary.primary_driver)
    : args.pnlState.label;
  const readinessBlockers = [...args.readiness.blockingReasons, ...args.readiness.warningReasons];
  const readinessDetail = [
    readinessBlockers.length > 0 ? readinessBlockers.join("；") : "无阻断",
    args.readiness.sourceFacts.length > 0 ? `来源事实：${args.readiness.sourceFacts.join("；")}` : "",
  ]
    .filter(Boolean)
    .join("；");

  return {
    title: "今日组合判断",
    conclusion,
    detail: `风险约束使用现有字段与首屏监控阈值；行动队列：${actionQueue} 数据可信度：${args.readPath.label}；源日期：${args.readiness.sourceDates}；风险闭合：${args.readiness.riskClosureFact}；readiness：${readinessDetail}；证据：${args.evidenceState.detail}；不使用前端补数。`,
    tone,
    facts: [
      {
        label: "信用占比",
        value: creditValue,
        tone: creditRatio === null ? "muted" : creditRatio >= 0.3 ? "watch" : "ok",
      },
      {
        label: "DV01",
        value: dv01Value,
        tone: dv01Value === "-" ? "muted" : "ok",
      },
      {
        label: "归因摘要",
        value: attributionValue,
        tone: args.pnlState.tone,
      },
      {
        label: "数据链路",
        value: `${args.readPath.label} / ${args.bondDate}`,
        tone: args.readPath.tone,
      },
      {
        label: "源日期",
        value: args.readiness.sourceDates,
        tone: args.readiness.blockingReasons.some((reason) => reason.includes("日期不一致"))
          ? "error"
          : "ok",
      },
      {
        label: "风险闭合",
        value: args.readiness.riskClosureFact,
        tone: args.readiness.riskClosureReady ? "ok" : "watch",
      },
      {
        label: "证据样本",
        value: args.evidenceState.factValue,
        tone: args.evidenceState.tone,
      },
      {
        label: "子组合",
        value: `${args.portfolioRows.length} 个`,
        tone: args.portfolioRows.length > 0 ? "ok" : "muted",
      },
    ],
    actions,
  };
}

const MOCK_PORTFOLIO_GUARD_DETAIL =
  "当前为 MOCK 模式，样例市值、信用占比、DV01、持仓只数和归因结论仅用于页面结构验证，不可用于业务决策。";

export function guardMockPortfolioHomeView(view: ModuleHomeViewBody): ModuleHomeViewBody {
  const guardedDetailPanel: ModuleHomeDetailPanel = {
    key: "mock-portfolio-guard",
    title: "模拟数据防误用",
    meta: "MOCK 模式",
    stateLabel: "不可用于业务决策",
    stateDetail: MOCK_PORTFOLIO_GUARD_DETAIL,
    rows: [
      {
        key: "mock-portfolio-guard-row",
        label: "正式数据源",
        value: "待切换",
        tradeDate: "-",
        source: "mock-mode-guard",
        tone: "error",
        detail: "切换真实数据源后再查看组合规模、信用占比、DV01、持仓只数和归因摘要。",
      },
    ],
    tone: "error",
  };

  return {
    ...view,
    stateLabel: "模拟数据",
    stateDetail: MOCK_PORTFOLIO_GUARD_DETAIL,
    kpis: view.kpis.map((item) => ({
      ...item,
      value: "模拟数据",
      detail: "MOCK 模式下不展示样例数值；请切换正式数据源后查看。",
      tone: "muted",
    })),
    statuses: view.statuses.map((item) => ({
      ...item,
      value: "模拟数据",
      detail: "该读链路当前返回前端样例 envelope，不作为正式证据。",
      tone: "watch",
    })),
    decision: {
      title: "模拟数据防误用",
      conclusion: "当前为模拟数据，不能形成组合判断",
      detail: MOCK_PORTFOLIO_GUARD_DETAIL,
      tone: "error",
      facts: [
        { label: "数据模式", value: "模拟数据", tone: "error" },
        { label: "决策状态", value: "不可用于业务决策", tone: "error" },
        { label: "正式链路", value: "待切换真实数据源", tone: "watch" },
        { label: "动作建议", value: "不生成调仓动作", tone: "muted" },
      ],
      actions: [],
    },
    briefings: [
      {
        title: "数据模式",
        conclusion: "当前仅验证页面结构",
        evidence: "样例数值已从首屏判断中移除，避免误当正式组合读数。",
        tone: "error",
      },
      {
        title: "正式链路",
        conclusion: "切换真实数据源后再查看组合读数",
        evidence: "正式展示以 API result_meta 的报告日、证据行数和来源表为准。",
        tone: "watch",
      },
      {
        title: "决策状态",
        conclusion: "不生成调仓或风险动作",
        evidence: "MOCK 模式不触发信用、久期、DV01 或归因驱动的行动建议。",
        tone: "muted",
      },
    ],
    distributionPanels: [],
    detailPanels: [guardedDetailPanel],
    dataNote: {
      title: "模拟数据说明",
      lines: [
        MOCK_PORTFOLIO_GUARD_DETAIL,
        "请切换正式数据源后再查看组合规模、信用占比、DV01、持仓只数和归因摘要。",
      ],
      tone: "error",
    },
  };
}
