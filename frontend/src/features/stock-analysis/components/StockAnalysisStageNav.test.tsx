import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { StockAnalysisStageNav } from "./StockAnalysisStageNav";

function renderStageNav(pathname: string, variant: "bar" | "menu" = "bar") {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <StockAnalysisStageNav variant={variant} />
    </MemoryRouter>,
  );
}

describe("StockAnalysisStageNav", () => {
  it("marks only the current available stage", () => {
    renderStageNav("/stock-analysis/portfolio");

    expect(screen.getByRole("navigation", { name: "股票策略阶段" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /组合构建/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: /研究/ })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: /组合风险/ })).not.toHaveAttribute("aria-current");
  });

  it("keeps the first three stages navigable and later stages non-clickable", () => {
    renderStageNav("/stock-analysis");

    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /研究/ })).toHaveAttribute(
      "href",
      "/stock-analysis",
    );
    expect(screen.getByRole("link", { name: /组合构建/ })).toHaveAttribute(
      "href",
      "/stock-analysis/portfolio",
    );
    expect(screen.getByRole("link", { name: /组合风险/ })).toHaveAttribute(
      "href",
      "/stock-analysis/risk",
    );

    expect(screen.queryByRole("link", { name: /交易执行/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /绩效归因/ })).not.toBeInTheDocument();
    expect(screen.getByText("交易执行")).toBeInTheDocument();
    expect(screen.getByText("绩效归因")).toBeInTheDocument();
  });

  it("keeps the menu disclosure and stage navigation structurally connected", () => {
    renderStageNav("/stock-analysis", "menu");

    const details = screen.getByTestId("stock-analysis-stage-menu");
    const summary = screen.getByText("策略阶段");
    const navigation = screen.getByRole("navigation", { name: "股票策略阶段" });
    const popover = navigation.parentElement;

    expect(summary.tagName).toBe("SUMMARY");
    expect(popover).not.toBeNull();
    expect(summary).toHaveAttribute("aria-controls", popover?.id);
    expect(details).not.toHaveAttribute("open");

    fireEvent.click(summary);
    expect(details).toHaveAttribute("open");
  });
});
