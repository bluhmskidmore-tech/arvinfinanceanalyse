import { render, screen } from "@testing-library/react";

import { AgentAnswerPanel } from "../features/agent/components/AgentAnswerPanel";

describe("AgentAnswerPanel", () => {
  it("renders a completed answer as staggered readable segments", () => {
    render(
      <AgentAnswerPanel
        answer={"先给出结论：久期风险集中在 3Y-5Y。\n\n下一步：复核信用利差和成交明细。"}
        testId="agent-answer"
      />,
    );

    expect(screen.getByTestId("agent-answer")).toBeInTheDocument();
    expect(screen.getAllByTestId("agent-answer-segment")).toHaveLength(2);
    expect(screen.getByText("先给出结论：久期风险集中在 3Y-5Y。")).toHaveStyle({
      "--agent-answer-segment-delay": "0ms",
    });
    expect(screen.getByText("下一步：复核信用利差和成交明细。")).toHaveStyle({
      "--agent-answer-segment-delay": "70ms",
    });
  });

  it("keeps a short answer as one segment", () => {
    render(<AgentAnswerPanel answer="当前没有明显异常。" />);

    expect(screen.getAllByTestId("agent-answer-segment")).toHaveLength(1);
    expect(screen.getByText("当前没有明显异常。")).toBeInTheDocument();
  });

  it("preserves single-line breaks inside one answer segment", () => {
    render(<AgentAnswerPanel answer={"结论：风险集中在 3Y-5Y。\n依据：成交明细显示换仓集中。"} />);

    const segment = screen.getByTestId("agent-answer-segment");
    expect(screen.getAllByTestId("agent-answer-segment")).toHaveLength(1);
    expect(segment).toHaveTextContent("结论：风险集中在 3Y-5Y。");
    expect(segment).toHaveTextContent("依据：成交明细显示换仓集中。");
  });
});
