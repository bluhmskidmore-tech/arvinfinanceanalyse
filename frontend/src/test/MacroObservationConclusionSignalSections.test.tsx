import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitAShareRiskPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitSignalCard,
} from "../api/macroToolkitClient";
import MacroObservationKpiBand from "../features/macro-observation/components/MacroObservationKpiBand";
import {
  buildAShareRiskView,
  buildObservationKpiBand,
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

  it("routes the yellow risk level through the model to an amber warning readout", () => {
    // 当日真实数据 green、mock orange 都造不出 yellow 档；这里从模型层打通
    // risk_level:"yellow" → tone:"warning" → DOM data-tone 的全链。
    render(
      <MacroObservationSignalRiskSection
        signalCards={buildSignalCardViews(rawSignalCards)}
        risk={buildAShareRiskView({ ...rawRiskPayload, risk_level: "yellow" })}
      />,
    );

    const riskBlock = screen.getByTestId("macro-observation-signalrisk-risk");
    expect(riskBlock).toHaveAttribute("data-state", "ready");
    const readout = riskBlock.querySelector(".macro-observation-signalrisk-risk-readout");
    expect(readout).toHaveAttribute("data-tone", "warning");
  });
});

// ---------------------------------------------------------------------------
// KPI 横带 tone 链路（模型 tone → data-tone 挂点 → CSS 消费规则）
// ---------------------------------------------------------------------------

/** buildObservationKpiBand 所需的最小 full 分析载荷（可选段一律省略）。 */
function analysisWithRisk(risk: MacroToolkitAShareRiskPayload): MacroToolkitAnalysisPayload {
  return {
    default_data_sources: [],
    as_of_date: "2026-08-12",
    conclusion: {
      stance: "偏防御",
      tone: "negative",
      summary: "宏观信号偏谨慎。",
      recommended_action: "维持防御仓位",
    },
    coverage: { indicator_count: 20, hit_count: 18, hit_rate: 0.9, script_count: 0, output_file_count: 0 },
    indicators: [],
    signal_cards: rawSignalCards,
    capability_results: [],
    strategy_summaries: [],
    a_share_risk: risk,
    output_files: [],
    source_checks: [],
    capabilities: [],
    runtime_status: { analysis_scope: "full", deferred_sections: [] },
    warnings: [],
  };
}

describe("MacroObservationKpiBand tone wiring", () => {
  const cellOf = (band: HTMLElement, label: string) =>
    within(band).getByText(label).closest(".macro-observation-view__kpi-cell");

  it("writes item.tone onto the KPI cell as data-tone with the value element inside", () => {
    const items: MacroObservationKpiItem[] = [
      { key: "stance", label: "投研观点", value: "偏防御", tone: "negative", status: "ready" },
      { key: "a-share-risk", label: "A股风险", value: "35", tone: "warning", status: "ready" },
      { key: "primary-signal", label: "主信号", value: "信用", tone: "positive", status: "ready" },
      { key: "decision-modules", label: "决策摘要可用模块", value: "12/16", status: "ready" },
    ];
    render(<MacroObservationKpiBand items={items} testId="kpi-band-tone" />);

    const band = screen.getByTestId("kpi-band-tone");
    expect(cellOf(band, "投研观点")).toHaveAttribute("data-tone", "negative");
    expect(cellOf(band, "A股风险")).toHaveAttribute("data-tone", "warning");
    expect(cellOf(band, "主信号")).toHaveAttribute("data-tone", "positive");
    // 无 tone 缺省 neutral：CSS 不着色，主值保持 ink。
    expect(cellOf(band, "决策摘要可用模块")).toHaveAttribute("data-tone", "neutral");
    // CSS 以 [data-tone] 后代 __kpi-value 消费，锁定主值元素确实在格内。
    expect(
      cellOf(band, "A股风险")?.querySelector(".macro-observation-view__kpi-value"),
    ).toHaveTextContent("35");
  });

  it("carries a yellow a_share_risk payload to a warning KPI cell end to end", () => {
    const band = buildObservationKpiBand({
      analysis: analysisWithRisk({ ...rawRiskPayload, risk_level: "yellow" }),
      strategyPayload: undefined,
      analysisLoading: false,
      strategySupply: "loaded",
    });
    const riskItem = band.find((item) => item.key === "a-share-risk");
    expect(riskItem?.tone).toBe("warning");
    expect(riskItem?.status).toBe("ready");

    render(<MacroObservationKpiBand items={band} testId="kpi-band-yellow" />);
    const cell = cellOf(screen.getByTestId("kpi-band-yellow"), "A股风险");
    expect(cell).toHaveAttribute("data-tone", "warning");
    expect(cell).toHaveAttribute("data-status", "ready");
  });
});

describe("MacroObservationPage.css KPI tone rules", () => {
  it("keeps the ready-scoped tone color rules for the KPI value", () => {
    const css = readFileSync(
      resolve(process.cwd(), "src/features/macro-observation/pages/MacroObservationPage.css"),
      "utf8",
    );
    // 锁定三档着色规则存在且限定 data-status="ready"（loading/deferred 的
    // muted 降权、failed 的红色不被 tone 覆盖）；yellow 档琥珀链路防误删。
    const toneRules = [
      ["positive", "--dh-api-green"],
      ["warning", "--dh-api-amber"],
      ["negative", "--dh-api-red"],
    ] as const;
    for (const [tone, cssVar] of toneRules) {
      const rule = new RegExp(
        `\\.macro-observation-view__kpi-cell\\[data-status="ready"\\]\\[data-tone="${tone}"\\]\\s*` +
          `\\.macro-observation-view__kpi-value\\s*\\{\\s*color:\\s*var\\(${cssVar}\\);`,
      );
      expect(css).toMatch(rule);
    }
    // neutral 保持缺省 ink，不应出现 neutral 着色规则。
    expect(css).not.toMatch(/__kpi-cell\[data-status="ready"\]\[data-tone="neutral"\]/);
  });
});
