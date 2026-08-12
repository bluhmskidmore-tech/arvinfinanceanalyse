import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { MacroToolkitModelChainResults } from "../api/macroToolkitClient";
import { createMockMacroToolkitClient } from "../api/macroToolkitMockClient";
import { MacroToolkitModelChainPanel } from "../features/macro-toolkit/panels/MacroToolkitModelChainPanel";

const STEP_LABELS = [
  "市场状态识别",
  "策略选择",
  "资产配置",
  "风险管理",
  "再平衡",
  "绩效评估",
  "决策链输出",
] as const;

const MODEL_HEADLINES = [
  "象限 过热 · 债券方向 空",
  "高波动 1/5 · 原油 63.49%",
  "平均相关 0.2764 · 正常",
  "高波动 3/5",
  "强多头 铜、原油 · 强空头 沪深300、中证500",
  "风险平价最大权重 铜期货 24.6362%",
  "-0.068 · 宽松",
  "无冷却 · 正常运行",
  "告警 1 条 · VOL_ALERT 1",
  "最优 季度再平衡 · 夏普 1.21",
  "最佳 风险平价组合 · 夏普 1.179",
  "最优 全模型综合 · 夏普 1.767",
  "空仓 4/4",
] as const;

async function loadMockModelChainResults(): Promise<MacroToolkitModelChainResults> {
  const envelope = await createMockMacroToolkitClient().fetchMacroToolkitModelChainResults();
  return envelope.result;
}

const MISSING_ARTIFACT_RESULTS: MacroToolkitModelChainResults = {
  as_of_date: "2026-08-11",
  observation_only: true,
  formal_use_allowed: false,
  steps: [
    {
      key: "market_state",
      step_no: 1,
      label: "市场状态识别",
      models: [
        {
          id: "merrill_clock",
          label: "美林时钟（中国版）",
          script_name: "merrill_clock_cn",
          artifact: "merrill_clock_latest.csv",
          artifact_status: "missing",
          as_of: null,
          headline: "",
          columns: [],
          rows: [],
        },
      ],
    },
  ],
};

describe("MacroToolkitModelChainPanel", () => {
  it("renders the seven decision-chain steps and all thirteen model headlines", async () => {
    const results = await loadMockModelChainResults();

    render(<MacroToolkitModelChainPanel results={results} />);

    const panel = screen.getByTestId("macro-toolkit-model-chain");
    expect(panel).toHaveTextContent("模型链结果 · 决策链视图");
    expect(panel).toHaveTextContent("数据日 2026-08-11");
    expect(within(panel).getByText("仅观察 · 不入正式口径")).toBeInTheDocument();

    for (const label of STEP_LABELS) {
      expect(within(panel).getByText(label)).toBeInTheDocument();
    }
    for (const headline of MODEL_HEADLINES) {
      expect(within(panel).getByText(headline)).toBeInTheDocument();
    }
    expect(screen.getAllByTestId(/^macro-toolkit-model-chain-model-/)).toHaveLength(13);
  });

  it("keeps model tables collapsed by default and expands details on demand", async () => {
    const results = await loadMockModelChainResults();
    const user = userEvent.setup();

    render(<MacroToolkitModelChainPanel results={results} />);

    expect(screen.queryAllByRole("table")).toHaveLength(0);
    const toggles = screen.getAllByRole("button", { name: /^展开 .+ 明细$/ });
    expect(toggles).toHaveLength(13);

    const merrillCard = screen.getByTestId("macro-toolkit-model-chain-model-merrill_clock");
    const merrillToggle = within(merrillCard).getByRole("button", {
      name: "展开 美林时钟（中国版） 明细",
    });
    expect(merrillToggle).toHaveAttribute("aria-expanded", "false");

    await user.click(merrillToggle);

    expect(merrillToggle).toHaveAttribute("aria-expanded", "true");
    const table = within(merrillCard).getByRole("table");
    expect(within(table).getByText("增长动量")).toBeInTheDocument();
    expect(within(table).getByText("0.228")).toBeInTheDocument();
    expect(within(table).getByText("过热")).toBeInTheDocument();
    expect(within(table).getByText("0.228")).toHaveClass("macro-toolkit-model-chain__cell--numeric");

    await user.click(merrillToggle);
    expect(within(merrillCard).queryByRole("table")).not.toBeInTheDocument();
    expect(merrillToggle).toHaveAttribute("aria-expanded", "false");
  });

  it("shows a missing-artifact placeholder instead of a table", () => {
    render(<MacroToolkitModelChainPanel results={MISSING_ARTIFACT_RESULTS} />);

    const card = screen.getByTestId("macro-toolkit-model-chain-model-merrill_clock");
    expect(within(card).getByText("产物缺失")).toBeInTheDocument();
    expect(within(card).queryByRole("table")).not.toBeInTheDocument();
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders nothing when the decision chain has no steps", () => {
    const { container } = render(
      <MacroToolkitModelChainPanel
        results={{
          as_of_date: null,
          observation_only: true,
          formal_use_allowed: false,
          steps: [],
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
