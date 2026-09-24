import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentGenericCardsGrid } from "../features/agent/components/AgentGenericCardsGrid";

const formatValue = (value: unknown) => String(value ?? "—");

describe("AgentGenericCardsGrid", () => {
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
});
