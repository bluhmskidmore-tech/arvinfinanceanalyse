import { describe, expect, it } from "vitest";

import type { BondDashboardHeadlinePayload, PnlAttributionAnalysisSummary } from "../api/contracts";
import {
  buildPortfolioDecision,
  guardMockPortfolioHomeView,
  type PortfolioEvidenceState,
  type PortfolioPnlState,
  type PortfolioReadPathState,
} from "../features/workbench/module-home/portfolioDecisionModel";
import type {
  ModuleHomeDetailRow,
  ModuleHomeViewBody,
} from "../features/workbench/module-home/moduleHomeModel";
import type { PortfolioReadinessGate } from "../features/workbench/module-home/portfolioReadinessGate";
import { formatRawAsNumeric } from "../utils/format";

const FALSE_CLOSURE_TERMS = [
  "closure_approved=true",
  "已审批",
  "decision-ready",
  "full closure",
] as const;

const STRICT_SCORECARD_BLOCKERS = [
  "risk_tensor_quality_warning",
  "krd_contract_decision_required",
  "bond_maturity_date_remediation_required",
  "tyw_liability_maturity_date_remediation_required",
  "business_owner_approval",
] as const;

function n(raw: number, unit: Parameters<typeof formatRawAsNumeric>[0]["unit"], signAware = false) {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function bondKpis(
  overrides: Partial<BondDashboardHeadlinePayload["kpis"]> = {},
): BondDashboardHeadlinePayload["kpis"] {
  return {
    total_market_value: n(332_281_921_064.45, "yuan"),
    unrealized_pnl: n(8_202_912_484.65, "yuan", true),
    weighted_ytm: n(0.02561294, "pct", true),
    weighted_duration: n(4.4484273, "ratio"),
    weighted_coupon: n(0.01871629, "pct", true),
    credit_spread_median: n(0.023682, "pct", true),
    total_dv01: n(105_628_442.39590558, "dv01"),
    bond_count: 1710,
    ...overrides,
  };
}

function risk(overrides: Partial<NonNullable<Parameters<typeof buildPortfolioDecision>[0]["risk"]>> = {}) {
  return {
    report_date: "2026-05-31",
    total_market_value: n(332_281_921_064.45, "yuan"),
    total_dv01: n(105_628_442.39590558, "dv01"),
    weighted_duration: n(4.4484273, "ratio"),
    credit_ratio: n(0.29955411, "ratio"),
    weighted_convexity: n(28.73609304, "ratio"),
    total_spread_dv01: n(25_862_175.57270329, "dv01"),
    reinvestment_ratio_1y: n(0.3448817, "ratio"),
    ...overrides,
  };
}

function pnlSummary(): PnlAttributionAnalysisSummary {
  return {
    report_date: "2026-05-31",
    primary_driver: "market",
    primary_driver_pct: n(0.58, "ratio"),
    key_findings: ["市值变动主要来自市场重估。"],
    tpl_market_aligned: true,
    tpl_market_note: "与 TPL 市场变动方向一致。",
  };
}

function readiness(overrides: Partial<PortfolioReadinessGate> = {}): PortfolioReadinessGate {
  return {
    coreRender: true,
    decisionReady: true,
    riskClosureReady: true,
    tone: "ok",
    blockingReasons: [],
    warningReasons: [],
    sourceFacts: ["债券总览: basis=formal, formal_use_allowed=true, quality=ok, fallback=none"],
    sourceDates: "债券总览=2026-05-31；风险指标=2026-05-31；资产负债=2026-05-31；损益归因=2026-05-31",
    riskClosureFact: "同日闭合 2026-05-31",
    ...overrides,
  };
}

function detailRow(label: string): ModuleHomeDetailRow {
  return {
    key: label,
    label,
    value: "1.00",
    tradeDate: "2026-05-31",
    source: "test",
    tone: "ok",
  };
}

function buildDecision(overrides: Partial<Parameters<typeof buildPortfolioDecision>[0]> = {}) {
  const readPath: PortfolioReadPathState = { label: "已接入", tone: "ok" };
  const pnlState: PortfolioPnlState = { label: "已返回", tone: "ok" };
  const evidenceState: PortfolioEvidenceState = {
    factValue: "1710 行",
    detail: "bond_dashboard.home_summary / 1710 行 / fact_formal_bond_analytics_daily / 无回退",
    tone: "ok",
  };
  return buildPortfolioDecision({
    bondKpis: bondKpis(),
    risk: risk(),
    pnlSummary: pnlSummary(),
    bondDate: "2026-05-31",
    portfolioRows: [detailRow("固收组合")],
    readPath,
    pnlState,
    evidenceState,
    readiness: readiness(),
    ...overrides,
  });
}

function decisionText(decision: ReturnType<typeof buildPortfolioDecision>) {
  return [
    decision.title,
    decision.conclusion,
    decision.detail,
    ...decision.facts.flatMap((fact) => [fact.label, fact.value]),
    ...(decision.actions ?? []).flatMap((action) => [
      action.title,
      action.evidence,
      action.label ?? "",
      action.path,
    ]),
  ].join(" ");
}

function mockView(): ModuleHomeViewBody {
  return {
    stateLabel: "已接入",
    stateDetail: "样例详情",
    kpis: [
      {
        key: "bond-market",
        label: "债券组合市值",
        value: "3,287.09 亿元",
        detail: "sample",
        tone: "ok",
      },
    ],
    statuses: [
      {
        key: "source",
        label: "来源",
        value: "已接入",
        detail: "sample",
        tone: "ok",
      },
    ],
    briefings: [],
    decision: {
      title: "今日组合判断",
      conclusion: "组合风险收益读数可读",
      detail: "信用占比 42.00%；DV01 -12.54",
      tone: "ok",
      facts: [],
    },
    distributionPanels: [],
    detailPanels: [],
    dataNote: {
      title: "数据说明",
      lines: ["sample"],
      tone: "ok",
    },
  };
}

describe("portfolio decision model", () => {
  it("returns normal drilldown actions only when decision and risk evidence are closed", () => {
    const decision = buildDecision();

    expect(decision.conclusion).toBe("组合风险收益读数可读，维持观察并下钻核验");
    expect(decision.detail).toContain("同日闭合 2026-05-31");
    expect(decision.actions?.map((action) => action.title)).toEqual([
      "子组合分层核验",
    ]);
    expect(decision.actions?.some((action) => action.title === "来源证据复核")).toBe(false);
  });

  it("downgrades and suppresses normal risk actions when decision evidence is not ready", () => {
    const decision = buildDecision({
      readiness: readiness({
        decisionReady: false,
        tone: "watch",
        blockingReasons: ["损益归因 basis=analytical"],
      }),
    });

    expect(decision.conclusion).toBe("仅供分析：来源证据未达到决策级口径");
    expect(decision.detail).toContain("损益归因 basis=analytical");
    expect(decision.actions?.map((action) => action.title)).toEqual([
      "来源证据复核",
      "债券总览核对",
      "收益归因复核",
    ]);
    expect(decision.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
    const text = decisionText(decision);
    for (const term of FALSE_CLOSURE_TERMS) {
      expect(text).not.toContain(term);
    }
    for (const blocker of STRICT_SCORECARD_BLOCKERS) {
      expect(text).not.toContain(blocker);
    }
  });

  it("routes to risk date review when decision evidence is ready but risk closure is not", () => {
    const decision = buildDecision({
      readiness: readiness({
        riskClosureReady: false,
        tone: "watch",
        warningReasons: ["风险张量未闭合至 2026-05-31，最新 2026-04-30"],
        riskClosureFact: "风险张量未闭合至 2026-05-31，最新 2026-04-30",
      }),
    });

    expect(decision.conclusion).toBe("仅供监控：风险张量未同日闭合");
    expect(decision.detail).not.toContain("同日闭合 2026-05-31");
    expect(decision.actions?.[0]).toMatchObject({
      title: "风险张量日期复核",
      path: "/risk-tensor",
    });
    const text = decisionText(decision);
    for (const term of FALSE_CLOSURE_TERMS) {
      expect(text).not.toContain(term);
    }
    for (const blocker of STRICT_SCORECARD_BLOCKERS) {
      expect(text).not.toContain(blocker);
    }
  });

  it("removes mock sample values and decision actions from mock portfolio views", () => {
    const guarded = guardMockPortfolioHomeView(mockView());

    expect(guarded.stateLabel).toBe("模拟数据");
    expect(guarded.kpis[0]?.value).toBe("模拟数据");
    expect(guarded.kpis[0]?.detail).toContain("不展示样例数值");
    expect(guarded.decision?.title).toBe("模拟数据防误用");
    expect(guarded.decision?.detail).toContain("不可用于业务决策");
    expect(guarded.decision?.detail).not.toContain("42.00%");
    expect(guarded.decision?.actions).toEqual([]);
    expect(guarded.detailPanels?.[0]?.key).toBe("mock-portfolio-guard");
    expect(guarded.dataNote.lines.join(" ")).toContain("不可用于业务决策");
    const text = [
      guarded.stateLabel,
      guarded.stateDetail,
      guarded.decision?.conclusion,
      guarded.decision?.detail,
      ...(guarded.dataNote.lines ?? []),
    ].join(" ");
    for (const term of FALSE_CLOSURE_TERMS) {
      expect(text).not.toContain(term);
    }
  });
});
