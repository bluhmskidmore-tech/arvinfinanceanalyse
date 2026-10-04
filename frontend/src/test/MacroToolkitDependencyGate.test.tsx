import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  MacroToolkitCapabilityResult,
  MacroToolkitSignalCard,
} from "../api/macroToolkitClient";
import { CapabilityResultCard } from "../features/macro-toolkit/sections/MacroToolkitCapabilityCards";
import { MacroToolkitSignalSection } from "../features/macro-toolkit/sections/MacroToolkitSignalSections";

function buildCapabilityResult(
  overrides: Partial<MacroToolkitCapabilityResult> = {},
): MacroToolkitCapabilityResult {
  return {
    key: "monetary_policy_stance",
    legacy_module: "M7",
    label: "货币政策姿态",
    group: "macro_signal",
    status: "complete",
    tone: "positive",
    score: 73,
    headline: "政策环境偏宽松",
    primary_metric: {
      label: "政策姿态",
      value: "宽松",
      unit: "",
    },
    evidence: ["DR007 最新值 1.62%"],
    warnings: [],
    result: {
      input_evidence: {
        sources: ["choice"],
        latest_dates: ["2026-08-24"],
      },
    },
    ...overrides,
  };
}

function buildCrisisResult(
  overrides: Partial<MacroToolkitCapabilityResult> = {},
): MacroToolkitCapabilityResult {
  return buildCapabilityResult({
    key: "crisis_score_cn",
    legacy_module: "Crisis",
    label: "Crisis Score",
    score: -0.57,
    headline: "风险压力偏低",
    primary_metric: {
      label: "Crisis Score",
      value: -0.57,
      unit: "",
    },
    result: {
      components: [
        {
          key: "liquidity",
          label: "流动性",
          raw_value: 1.62,
          z_score: -1.25,
          weight: 0.25,
        },
      ],
    },
    ...overrides,
  });
}

const CRISIS_SIGNAL_CARD: MacroToolkitSignalCard = {
  key: "crisis_score_cn",
  title: "Crisis Score",
  stance: "宽松",
  tone: "positive",
  score: -0.57,
  evidence: ["score=-0.57"],
};

describe("Macro Toolkit dependency gate", () => {
  it("renders a blocked M7 capability as unavailable for directional judgment while retaining evidence", () => {
    render(
      <CapabilityResultCard
        result={buildCapabilityResult({
          dependency_gate: {
            status: "blocked",
            blocked_by: ["choice_policy_rate_7d"],
            reason_code: "required_refresh_step_not_ready",
          },
        })}
      />,
    );

    expect(screen.getByText("依赖阻断")).toBeInTheDocument();
    expect(screen.getByText("不可用于方向判断")).toBeInTheDocument();
    expect(screen.getByText("依赖未通过")).toBeInTheDocument();
    expect(screen.queryByText("政策姿态 宽松")).not.toBeInTheDocument();
    expect(screen.queryByText("政策环境偏宽松")).not.toBeInTheDocument();
    expect(screen.getByText("DR007 最新值 1.62%")).toBeInTheDocument();
    expect(screen.getByText("数据源：choice")).toBeInTheDocument();
  });

  it("fails closed for a blocked Crisis signal even when the signal card still contains a score and stance", () => {
    render(
      <MacroToolkitSignalSection
        showOperations
        visibleSignalCards={[CRISIS_SIGNAL_CARD]}
        crisisScoreResult={buildCrisisResult({
          dependency_gate: {
            status: "blocked",
            blocked_by: ["choice_policy_rate_7d"],
            reason_code: "required_refresh_step_not_ready",
          },
        })}
      />,
    );

    const card = screen.getByText("Crisis Score").closest<HTMLElement>(".macro-toolkit-signal-card");
    if (!card) {
      throw new Error("Missing Crisis signal card");
    }
    expect(within(card).getByText("依赖阻断")).toBeInTheDocument();
    expect(within(card).getByText("不可用于方向判断")).toBeInTheDocument();
    expect(card).not.toHaveTextContent("宽松");
    expect(card).not.toHaveTextContent("-0.57");
    expect(
      within(card).queryByTestId("macro-toolkit-crisis-signal-component-summary"),
    ).not.toBeInTheDocument();
  });

  it("keeps the existing Crisis signal display when its dependency is not blocked", () => {
    render(
      <MacroToolkitSignalSection
        showOperations
        visibleSignalCards={[CRISIS_SIGNAL_CARD]}
        crisisScoreResult={buildCrisisResult({
          dependency_gate: {
            status: "ready",
            blocked_by: [],
            reason_code: "required_dependencies_ready",
          },
        })}
      />,
    );

    const card = screen.getByText("Crisis Score").closest<HTMLElement>(".macro-toolkit-signal-card");
    if (!card) {
      throw new Error("Missing Crisis signal card");
    }
    expect(within(card).getByText("宽松")).toBeInTheDocument();
    expect(within(card).getByText("-0.57")).toBeInTheDocument();
    expect(
      within(card).getByTestId("macro-toolkit-crisis-signal-component-summary"),
    ).toHaveTextContent("流动性");
    expect(within(card).queryByText("依赖阻断")).not.toBeInTheDocument();
  });
});
