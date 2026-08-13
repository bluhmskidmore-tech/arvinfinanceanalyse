import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  MacroToolkitAShareRiskPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitSignalCard,
} from "../api/macroToolkitClient";
import {
  buildAShareRiskView,
  buildSignalCardViews,
  type MacroObservationConclusionView,
  type MacroObservationKpiItem,
} from "../features/macro-observation/model/macroObservationPageModel";
import MacroObservationConclusionSection from "../features/macro-observation/sections/MacroObservationConclusionSection";
import MacroObservationSignalRiskSection from "../features/macro-observation/sections/MacroObservationSignalRiskSection";
import { EM_DASH } from "../pageModel";

const kpiItems: MacroObservationKpiItem[] = [
  { key: "stance", label: "投研观点", value: EM_DASH, status: "ready" },
  { key: "decision-modules", label: "决策摘要可用模块", value: EM_DASH, status: "ready" },
];

const conclusion: MacroObservationConclusionView = {
  stance: "谨慎观察",
  tone: "negative",
  summary: "宏观信号偏谨慎，货币边际收敛叠加信用利差走阔，组合优先控制久期与信用敞口。",
  recommendedAction: "先补齐关键输入，再复核观察结论",
  warningNote: "2 条分析警示待复核",
};

const decisionResult: MacroToolkitCapabilityResult = {
  key: "decision_summary",
  legacy_module: "M16",
  label: "宏观决策摘要",
  group: "决策摘要",
  status: "degraded",
  tone: "negative",
  score: 42,
  headline: "宏观信号偏谨慎，优先控制久期和信用敞口。",
  primary_metric: { label: "可用模块", value: 13, unit: "/16" },
  evidence: [],
  warnings: ["部分模块数据降级或不可用"],
  result: { data_status: "degraded", usable_count: 13 },
};

function renderConclusionSection(
  overrides: Partial<Parameters<typeof MacroObservationConclusionSection>[0]> = {},
) {
  return render(
    <MacroObservationConclusionSection
      kpiItems={kpiItems}
      conclusion={conclusion}
      decisionResult={decisionResult}
      isCoreAnalysis={false}
      analysisBasis="analytical"
      {...overrides}
    />,
  );
}

const rawSignalCards: MacroToolkitSignalCard[] = [
  {
    key: "crisis_score_cn",
    title: "中国危机分",
    stance: "压力可控",
    tone: "positive",
    score: 32.5,
    evidence: ["近 20 日危机分位于低位区间"],
  },
  {
    key: "a_share_stampede_risk",
    title: "A股踩踏",
    stance: "数据不足",
    tone: "missing",
    score: null,
    evidence: [],
  },
  {
    key: "liquidity",
    title: "流动性",
    stance: "中性",
    tone: "neutral",
    score: 55,
    evidence: ["资金利率围绕政策利率波动"],
  },
  {
    key: "risk_appetite",
    title: "风险偏好",
    stance: "偏弱",
    tone: "negative",
    score: 40.2,
    evidence: ["股权风险溢价抬升"],
  },
  {
    key: "credit",
    title: "信用",
    stance: "偏支持",
    tone: "positive",
    score: 61.8,
    evidence: ["高等级利差走阔放缓"],
  },
];

const rawRiskPayload: MacroToolkitAShareRiskPayload = {
  trade_date: "2026-08-12",
  status: "complete",
  risk_score: 62,
  risk_level: "orange",
  risk_name: "情绪过热",
  summary: "两融余额与换手率同步抬升，短线拥挤度接近历史高位。",
  position_rule: "仓位不高于五成，禁止追高开新仓。",
  metrics: {},
  triggered_rules: ["turnover_spike", "margin_balance_high"],
  watch_next: ["观察两融余额变化", "观察北向资金方向", "观察成交额缩量节奏", "观察行业轮动速度"],
  warnings: [],
  tables_used: [],
};

describe("MacroObservationConclusionSection", () => {
  it("renders stance, summary and recommended action with the model tone", () => {
    renderConclusionSection();

    const main = screen.getByLabelText("观察结论正文");
    const stance = within(main).getByText("谨慎观察");
    expect(stance).toHaveAttribute("data-tone", "negative");
    expect(within(main).getByText(conclusion.summary)).toHaveAttribute(
      "title",
      conclusion.summary,
    );
    expect(within(main).getByText("建议动作")).toBeInTheDocument();
    expect(within(main).getByText(conclusion.recommendedAction)).toBeInTheDocument();
  });

  it("renders the decision summary with headline, module count and data-status badge", () => {
    renderConclusionSection();

    const decision = screen.getByTestId("macro-observation-decision-summary");
    expect(decision).toHaveTextContent("宏观决策摘要");
    expect(decision).toHaveTextContent("可用模块 13/16");
    expect(decision).toHaveTextContent("宏观信号偏谨慎，优先控制久期和信用敞口。");
    const badge = within(decision).getByText("部分降级");
    expect(badge).toHaveAttribute("data-status", "degraded");
    expect(
      within(decision).queryByTestId("macro-observation-decision-mock-flag"),
    ).not.toBeInTheDocument();
  });

  it("shows the mock-basis flag only when the envelope basis is mock", () => {
    renderConclusionSection({ analysisBasis: "mock" });

    const mockFlag = screen.getByTestId("macro-observation-decision-mock-flag");
    expect(mockFlag).toHaveTextContent("模拟口径");
  });

  it("renders the warnings note only when the model provides one", () => {
    const { unmount } = renderConclusionSection();
    expect(
      screen.getByTestId("macro-observation-conclusion-warning-note"),
    ).toHaveTextContent("2 条分析警示待复核，全文见证据与口径分区。");
    unmount();

    renderConclusionSection({ conclusion: { ...conclusion, warningNote: null } });
    expect(
      screen.queryByTestId("macro-observation-conclusion-warning-note"),
    ).not.toBeInTheDocument();
  });

  it("keeps the deferred decision copy when the capability row is missing on core scope", () => {
    renderConclusionSection({ decisionResult: null, isCoreAnalysis: true });

    expect(screen.getByTestId("macro-observation-decision-summary")).toHaveTextContent(
      "核心分析已先返回；决策摘要需打开完整分析后确认。",
    );
  });
});

describe("MacroObservationSignalRiskSection", () => {
  it("renders all five signal cards with EM_DASH for a null score and the first evidence line", () => {
    render(
      <MacroObservationSignalRiskSection
        signalCards={buildSignalCardViews(rawSignalCards)}
        risk={buildAShareRiskView(rawRiskPayload)}
      />,
    );

    const band = screen.getByRole("list", { name: "信号卡列表" });
    expect(within(band).getAllByRole("listitem")).toHaveLength(5);
    expect(within(band).getByText("近 20 日危机分位于低位区间")).toBeInTheDocument();

    const stampedeCell = within(band).getByText("A股踩踏").closest("li");
    expect(stampedeCell).not.toBeNull();
    expect(within(stampedeCell as HTMLElement).getByText(EM_DASH)).toBeInTheDocument();
    expect(within(stampedeCell as HTMLElement).getByText("观察证据待补齐")).toBeInTheDocument();
    expect(within(band).getByText("偏弱").closest("li")).toHaveAttribute(
      "data-tone",
      "negative",
    );
  });

  it("renders the ready A-share risk block with position rule, watch list and rule count", () => {
    render(
      <MacroObservationSignalRiskSection
        signalCards={buildSignalCardViews(rawSignalCards)}
        risk={buildAShareRiskView(rawRiskPayload)}
      />,
    );

    const riskBlock = screen.getByTestId("macro-observation-signalrisk-risk");
    expect(riskBlock).toHaveAttribute("data-state", "ready");
    expect(riskBlock).toHaveTextContent("2026-08-12");
    expect(riskBlock).toHaveTextContent("情绪过热");
    expect(riskBlock).toHaveTextContent("62");
    expect(within(riskBlock).getByText("仓位规则")).toBeInTheDocument();
    expect(within(riskBlock).getByText("仓位不高于五成，禁止追高开新仓。")).toBeInTheDocument();
    // 模型层截断为前 3 条 + 「另 N 项」。
    expect(within(riskBlock).getByText("观察两融余额变化")).toBeInTheDocument();
    expect(within(riskBlock).getByText("观察成交额缩量节奏")).toBeInTheDocument();
    expect(within(riskBlock).queryByText("观察行业轮动速度")).not.toBeInTheDocument();
    expect(within(riskBlock).getByText("另 1 项")).toBeInTheDocument();
    expect(riskBlock).toHaveTextContent("触发规则 2 条");
    const readout = riskBlock.querySelector(".macro-observation-signalrisk-risk-readout");
    expect(readout).toHaveAttribute("data-tone", "negative");
  });

  it("renders the deferred placeholder without ready-only fields when core has no risk payload", () => {
    render(
      <MacroObservationSignalRiskSection
        signalCards={buildSignalCardViews(rawSignalCards)}
        risk={buildAShareRiskView(null)}
      />,
    );

    const riskBlock = screen.getByTestId("macro-observation-signalrisk-risk");
    expect(riskBlock).toHaveAttribute("data-state", "deferred");
    expect(riskBlock).toHaveTextContent("A股风险完整分析后确认。");
    expect(within(riskBlock).queryByText("仓位规则")).not.toBeInTheDocument();
    expect(within(riskBlock).queryByText("触发规则", { exact: false })).not.toBeInTheDocument();
  });

  it("renders an explicit empty note when no signal cards are available", () => {
    render(
      <MacroObservationSignalRiskSection
        signalCards={[]}
        risk={buildAShareRiskView(null)}
      />,
    );

    expect(screen.getByText("暂无信号卡证据；宏观分析返回后自动补上。")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "信号卡列表" })).not.toBeInTheDocument();
  });
});
