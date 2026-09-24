import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  StockDeepAnalysisGateSummary,
  StockDeepZoneAuditRow,
} from "../lib/stockAnalysisPageModel";
import { StockAnalysisDeepZoneHeader } from "./StockAnalysisDeepZoneHeader";

const gateSummary: StockDeepAnalysisGateSummary = {
  line: "截至 10:30，证据链待补齐",
  tone: "warning",
};

const auditRows: StockDeepZoneAuditRow[] = [
  { key: "supply", label: "供数", value: "已返回", tone: "positive" },
  { key: "replay", label: "回放", value: "待复核", tone: "warning" },
  { key: "review", label: "候选", value: "3 只", tone: "neutral" },
  { key: "events", label: "事件", value: "1 项缺口", tone: "negative" },
];

describe("StockAnalysisDeepZoneHeader", () => {
  it("uses the dedicated evidence-header class contract without mixed theme utilities", () => {
    const { container } = render(
      <StockAnalysisDeepZoneHeader gateSummary={gateSummary} auditRows={auditRows} />,
    );

    expect(container.firstElementChild).toHaveAttribute(
      "class",
      "stock-analysis-page__deep-zone-header stock-analysis-page__deep-zone-header--compact",
    );

    const renderedClasses = Array.from(container.querySelectorAll("[class]"))
      .map((element) => element.getAttribute("class") ?? "")
      .join(" ");

    expect(renderedClasses).not.toMatch(
      /\b(?:bg-white|dark:|(?:bg|border|text)-(?:green|red|amber|zinc)-|rounded-(?:xl|lg|full)|shadow-sm|uppercase|tracking-)\S*/,
    );
    expect(screen.getByTestId("stock-analysis-deep-zone-gate-summary")).toHaveAttribute(
      "data-tone",
      "warning",
    );
    expect(screen.getByText("1 项缺口").closest("[data-tone]")).toHaveAttribute(
      "data-tone",
      "negative",
    );
  });

  it("preserves the evidence disclosure, status semantics, and business copy", () => {
    render(<StockAnalysisDeepZoneHeader gateSummary={gateSummary} auditRows={auditRows} />);

    const detailShell = screen.getByTestId("stock-analysis-deep-zone-detail-shell");
    const statusFlow = screen.getByTestId("stock-analysis-deep-zone-status-flow");

    expect(screen.getByRole("heading", { name: "供数闭环" })).toBeInTheDocument();
    expect(detailShell).not.toHaveAttribute("open");
    expect(statusFlow).toHaveAttribute("aria-label", "状态口径");
    expect(statusFlow).toHaveTextContent("阻断不可出正式信号");
    expect(statusFlow).toHaveTextContent("已就绪可进入回测");

    fireEvent.click(screen.getByText("供数 / 回放 / 候选 / 事件明细"));
    expect(detailShell).toHaveAttribute("open");
  });
});
