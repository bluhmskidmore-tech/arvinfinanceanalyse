import { render, screen } from "@testing-library/react";

import { AgentAnswerPanel } from "../features/agent/components/AgentAnswerPanel";

describe("AgentAnswerPanel", () => {
  it("renders a completed answer as readable Markdown paragraphs in source order", () => {
    render(
      <AgentAnswerPanel
        answer={"先给出结论：久期风险集中在 3Y-5Y。\n\n下一步：复核信用利差和成交明细。"}
        testId="agent-answer"
      />,
    );

    expect(screen.getByTestId("agent-answer")).toBeInTheDocument();
    const paragraphs = screen.getAllByTestId("agent-answer-segment");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs.map((paragraph) => paragraph.tagName)).toEqual(["P", "P"]);
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "先给出结论：久期风险集中在 3Y-5Y。",
      "下一步：复核信用利差和成交明细。",
    ]);
  });

  it("keeps a short answer as one segment", () => {
    render(<AgentAnswerPanel answer="当前没有明显异常。" />);

    expect(screen.getAllByTestId("agent-answer-segment")).toHaveLength(1);
    expect(screen.getByText("当前没有明显异常。")).toBeInTheDocument();
  });

  it("shows governed query summaries while collapsing technical evidence", () => {
    render(
      <AgentAnswerPanel
        answer={[
          "结论：2026-08-31 的损益汇总已返回，正式 FI 1697 行，总损益 1109199251.63。",
          "关键数字：Total PnL=1109199251.63; Interest 514=541744932.29; Fair Value 516=541555331.07; Capital Gain 517=25898988.27",
          "证据：fact_formal_pnl_fi、fact_nonstd_pnl_bridge；证据行数=1856；质量标识=ok。",
          "口径边界：basis=formal；可正式使用；currency_basis=CNY；report_date=2026-08-31。",
          "下一步：按券查看；按组合查看",
        ].join("\n")}
        testId="agent-answer"
      />,
    );

    expect(screen.getByTestId("agent-structured-answer")).toBeInTheDocument();
    expect(screen.getByText("总损益")).toBeInTheDocument();
    expect(screen.getByText("利息收入（514）")).toBeInTheDocument();
    expect(screen.getByText("按券查看；按组合查看")).toBeInTheDocument();
    const details = screen.getByText("查看数据依据与口径").closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
  });

  it("preserves single-line breaks inside one answer segment", () => {
    render(<AgentAnswerPanel answer={"结论：风险集中在 3Y-5Y。\n依据：成交明细显示换仓集中。"} />);

    const segment = screen.getByTestId("agent-answer-segment");
    expect(screen.getAllByTestId("agent-answer-segment")).toHaveLength(1);
    expect(segment).toHaveTextContent("结论：风险集中在 3Y-5Y。");
    expect(segment).toHaveTextContent("依据：成交明细显示换仓集中。");
  });

  it("hides a character-fragmented Hermes toolset warning without dropping the answer", () => {
    const fragmentedBanner = [
      [..."Warning:"].join("\n"),
      [..."Unknown"].join("\n"),
      [..."toolsets:"].join("\n"),
      [..."evidence,"].join("\n"),
      [..."query,"].join("\n"),
      [..."research"].join("\n"),
    ].join("\n\n");

    render(<AgentAnswerPanel answer={`${fragmentedBanner}\n真正的回答。`} />);

    expect(screen.getByText("真正的回答。")).toBeInTheDocument();
    expect(screen.queryByText("W")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("agent-answer-segment")).toHaveLength(1);
  });

  it("preserves warning text when it continues as legitimate prose", () => {
    const exactProse =
      "Warning: Unknown toolsets: evidence, query, research means the runtime configuration is stale.";
    const fragmentedProse = `${[..."Warning: Unknown toolsets: evidence, query, research"].join("\n")} means the runtime configuration is stale.`;

    const { rerender } = render(<AgentAnswerPanel answer={exactProse} testId="agent-answer" />);
    expect(screen.getByText(exactProse)).toBeInTheDocument();

    rerender(<AgentAnswerPanel answer={fragmentedProse} testId="agent-answer" />);
    expect(screen.getByTestId("agent-answer").textContent?.replace(/\s/g, "")).toBe(
      exactProse.replace(/\s/g, ""),
    );
  });
});
