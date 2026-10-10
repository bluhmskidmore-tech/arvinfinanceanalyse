import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentGenericCardsGrid } from "../features/agent/components/AgentGenericCardsGrid";

const formatValue = (value: unknown) => String(value ?? "—");

describe("AgentGenericCardsGrid", () => {
  it("renders a localized read-only workflow plan with honest pending intent states", () => {
    render(
      <AgentGenericCardsGrid
        cards={[
          {
            title: "Workflow Plan",
            type: "workflow_plan",
            data: {
              workflow_id: "pnl_review",
              title: "PnL Review",
              description:
                "Reference workflow plan for reviewing PnL summary, bridge, and product-level PnL.",
              category: "pnl",
              source: "anthropic_financial_services_reference",
              output_kind: "workflow_plan",
              phase: "plan_only",
            },
          },
          {
            title: "Mapped MOSS Intents",
            type: "workflow_intents",
            data: [
              { order: 1, intent: "pnl_summary" },
              { order: 2, intent: "pnl_bridge" },
              { order: 3, intent: "product_pnl" },
            ],
          },
          {
            title: "Governance Notes",
            type: "governance_notes",
            data: [
              {
                note: "Keeps formal PnL calculations inside existing MOSS intent handlers.",
              },
              {
                note: "Does not write adjustments or trigger downstream posting workflows.",
              },
            ],
          },
        ]}
        formatValue={formatValue}
      />,
    );

    const planCard = screen.getByTestId("agent-workflow-plan-card");
    expect(within(planCard).getByRole("heading", { name: "工作流计划" })).toBeInTheDocument();
    expect(within(planCard).getByText("损益复核")).toBeInTheDocument();
    expect(within(planCard).getByText("只读计划")).toBeInTheDocument();
    expect(within(planCard).getAllByText("工作流标识")).toHaveLength(1);
    expect(within(planCard).getByText("pnl_review")).toBeInTheDocument();
    expect(within(planCard).getByText("仅规划")).toBeInTheDocument();

    const intentsCard = screen.getByTestId("agent-workflow-intents-card");
    expect(within(intentsCard).getByRole("heading", { name: "子任务编排" })).toBeInTheDocument();
    expect(within(intentsCard).getByText("损益汇总复核")).toBeInTheDocument();
    expect(within(intentsCard).getByText("损益桥接复核")).toBeInTheDocument();
    expect(within(intentsCard).getByText("产品损益复核")).toBeInTheDocument();
    expect(within(intentsCard).getByText("pnl_summary")).toBeInTheDocument();
    expect(within(intentsCard).getByText("pnl_bridge")).toBeInTheDocument();
    expect(within(intentsCard).getByText("product_pnl")).toBeInTheDocument();
    expect(within(intentsCard).getAllByText("待人工执行")).toHaveLength(3);
    expect(within(intentsCard).getByText("只读计划，不会自动执行。")).toBeInTheDocument();
    expect(within(intentsCard).queryByText(/运行中|执行中|已完成/)).not.toBeInTheDocument();

    const governanceCard = screen.getByTestId("agent-governance-notes-card");
    expect(within(governanceCard).getByRole("heading", { name: "治理边界" })).toBeInTheDocument();
    expect(
      within(governanceCard).getByText("正式损益计算仍由 MOSS 现有意图处理器完成。"),
    ).toBeInTheDocument();
    expect(
      within(governanceCard).getByText("不写入调整项，也不触发下游入账流程。"),
    ).toBeInTheDocument();
  });

  it("keeps generic object fields singular and generic array fields row-based", () => {
    render(
      <AgentGenericCardsGrid
        cards={[
          {
            title: "Object Evidence",
            type: "resource",
            data: { evidence_id: "ev-1", state: "ready" },
          },
          {
            title: "Array Evidence",
            type: "table",
            data: [
              { order: 1, intent: "alpha" },
              { order: 2, intent: "beta" },
            ],
          },
        ]}
        formatValue={formatValue}
      />,
    );

    expect(screen.getAllByText("evidence_id:")).toHaveLength(1);
    expect(screen.getAllByText("state:")).toHaveLength(1);
    expect(screen.getAllByText("order:")).toHaveLength(2);
    expect(screen.getAllByText("intent:")).toHaveLength(2);
  });

  it("renders markdown memo cards with line structure preserved", () => {
    const memoValue = [
      "## Workflow Memo：风险纪要（risk_memo）",
      "报告日期：2026-03-31",
      "",
      "### 分步结论",
      "- duration_risk: 组合久期 4.2 年。",
      "",
      "非正式结果，仅供分析参考（formal_use_allowed=false）。",
    ].join("\n");

    render(
      <AgentGenericCardsGrid
        cards={[{ title: "Workflow Memo", type: "markdown", value: memoValue }]}
        formatValue={formatValue}
      />,
    );

    expect(screen.getByText("Workflow Memo")).toBeInTheDocument();
    const body = screen.getByTestId("agent-memo-card-body");
    // 换行结构必须保留，否则多行 memo 会被压成一行
    expect(body.textContent).toBe(memoValue);
    // markdown 卡不应走 scalar 分支（scalar 分支会附加类型角标）
    expect(body.closest(".agent-generic-cards__card--memo")).not.toBeNull();
  });

  it("keeps scalar rendering for non-markdown cards", () => {
    render(
      <AgentGenericCardsGrid
        cards={[{ title: "组合久期", type: "metric", value: "4.2" }]}
        formatValue={formatValue}
      />,
    );

    expect(screen.getByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("4.2")).toBeInTheDocument();
    expect(screen.getByText("指标")).toBeInTheDocument();
  });

  it("localizes formal PnL card titles without changing their values", () => {
    render(
      <AgentGenericCardsGrid
        cards={[
          { title: "Total PnL", type: "metric", value: "1109199251.63" },
          { title: "Interest 514", type: "metric", value: "541744932.29" },
          { title: "Fair Value 516", type: "metric", value: "541555331.07" },
          { title: "Capital Gain 517", type: "metric", value: "25898988.27" },
        ]}
        formatValue={formatValue}
      />,
    );

    expect(screen.getByText("总损益")).toBeInTheDocument();
    expect(screen.getByText("利息收入（514）")).toBeInTheDocument();
    expect(screen.getByText("公允价值变动（516）")).toBeInTheDocument();
    expect(screen.getByText("资本利得（517）")).toBeInTheDocument();
    expect(screen.getByText("1109199251.63")).toBeInTheDocument();
    expect(screen.queryByText("Total PnL")).not.toBeInTheDocument();
  });

  it("keeps a formatted zero distinct from a missing metric value", () => {
    render(
      <AgentGenericCardsGrid
        cards={[
          { title: "利息收入", type: "metric", value: "0.00 元" },
          { title: "正式总损益", type: "metric", value: null },
        ]}
        formatValue={formatValue}
      />,
    );

    const zeroCard = screen.getByText("利息收入").closest(".agent-generic-cards__card");
    const missingCard = screen.getByText("正式总损益").closest(".agent-generic-cards__card");

    expect(zeroCard).not.toBeNull();
    expect(missingCard).not.toBeNull();
    expect(within(zeroCard as HTMLElement).getByText("0.00 元")).toBeInTheDocument();
    expect(within(missingCard as HTMLElement).getByText("—")).toBeInTheDocument();
  });
});
