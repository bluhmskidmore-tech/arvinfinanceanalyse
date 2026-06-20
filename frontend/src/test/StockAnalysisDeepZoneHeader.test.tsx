import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StockAnalysisDeepZoneHeader } from "../features/stock-analysis/components/StockAnalysisDeepZoneHeader";
import type {
  StockDeepAnalysisGateSummary,
  StockDeepZoneAuditRow,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";

const gateSummary: StockDeepAnalysisGateSummary = {
  line: "Gate ready for replay evidence.",
  tone: "positive",
};

const auditRows: StockDeepZoneAuditRow[] = [
  { key: "supply", label: "Supply", value: "ready", tone: "positive" },
  { key: "replay", label: "Replay", value: "3 windows", tone: "warning" },
  { key: "review", label: "Review", value: "5 candidates", tone: "positive" },
  { key: "events", label: "Events", value: "1 alert", tone: "negative" },
];

describe("StockAnalysisDeepZoneHeader", () => {
  it("renders the deep-zone gate summary and audit strip with stable page classes", () => {
    render(<StockAnalysisDeepZoneHeader gateSummary={gateSummary} auditRows={auditRows} />);

    const gate = screen.getByTestId("stock-analysis-deep-zone-gate-summary");
    const strip = screen.getByTestId("stock-analysis-deep-zone-audit-strip");

    expect(gate).toHaveClass("stock-analysis-page__deep-zone-gate-summary");
    expect(gate).toHaveAttribute("data-tone", "positive");
    expect(gate).toHaveTextContent("Gate ready for replay evidence.");
    expect(strip).toHaveClass("stock-analysis-page__deep-zone-audit-strip");
    expect(strip.querySelectorAll(".stock-analysis-page__deep-zone-audit-item")).toHaveLength(4);

    for (const row of auditRows) {
      const item = within(strip)
        .getByText(row.label)
        .closest(".stock-analysis-page__deep-zone-audit-item");

      expect(item).toHaveAttribute("data-tone", row.tone);
      expect(item).toHaveTextContent(row.value);
    }
  });

  it.each([
    ["supply", "database"] as const,
    ["replay", "bar-chart"] as const,
    ["review", "stock"] as const,
    ["events", "fire"] as const,
  ])("maps %s audit rows to the expected decorative icon", (key, iconLabel) => {
    render(
      <StockAnalysisDeepZoneHeader
        gateSummary={gateSummary}
        auditRows={auditRows.filter((row) => row.key === key)}
      />,
    );

    expect(
      screen.getByTestId("stock-analysis-deep-zone-audit-strip").querySelector(`[aria-label="${iconLabel}"]`),
    ).toBeInTheDocument();
  });
});
