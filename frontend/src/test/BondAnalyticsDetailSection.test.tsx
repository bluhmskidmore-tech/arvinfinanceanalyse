import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { BondAnalyticsModuleKey } from "../features/bond-analytics/lib/bondAnalyticsModuleRegistry";
import { getBondAnalyticsModuleDefinition } from "../features/bond-analytics/lib/bondAnalyticsModuleRegistry";

vi.mock("../features/bond-analytics/components/ReturnDecompositionView", () => ({
  ReturnDecompositionView: () => <div data-testid="mock-detail-return-decomposition" />,
}));
vi.mock("../features/bond-analytics/components/BenchmarkExcessView", () => ({
  BenchmarkExcessView: () => <div data-testid="mock-detail-benchmark-excess" />,
}));
vi.mock("../features/bond-analytics/components/KRDCurveRiskView", () => ({
  KRDCurveRiskView: () => <div data-testid="mock-detail-krd-curve-risk" />,
}));
vi.mock("../features/bond-analytics/components/CreditSpreadView", () => ({
  CreditSpreadView: () => <div data-testid="mock-detail-credit-spread" />,
}));
vi.mock("../features/bond-analytics/components/ActionAttributionView", () => ({
  ActionAttributionView: () => <div data-testid="mock-detail-action-attribution" />,
}));
vi.mock("../features/bond-analytics/components/AccountingClassAuditView", () => ({
  AccountingClassAuditView: () => <div data-testid="mock-detail-accounting-audit" />,
}));
vi.mock("../features/bond-analytics/components/PortfolioHeadlinesView", () => ({
  PortfolioHeadlinesView: () => <div data-testid="mock-detail-portfolio-headlines" />,
}));
vi.mock("../features/bond-analytics/components/TopHoldingsView", () => ({
  TopHoldingsView: () => <div data-testid="mock-detail-top-holdings" />,
}));

import { BondAnalyticsDetailSection } from "../features/bond-analytics/components/BondAnalyticsDetailSection";

const defaultFilterProps = {
  assetClass: "all" as const,
  accountingClass: "all" as const,
  scenarioSet: "standard" as const,
  spreadScenarios: "10,25,50",
};

const TAB_MODULE_CASES: Array<{
  activeTab: BondAnalyticsModuleKey;
  mockTestId: string;
}> = [
  { activeTab: "return-decomposition", mockTestId: "mock-detail-return-decomposition" },
  { activeTab: "benchmark-excess", mockTestId: "mock-detail-benchmark-excess" },
  { activeTab: "krd-curve-risk", mockTestId: "mock-detail-krd-curve-risk" },
  { activeTab: "credit-spread", mockTestId: "mock-detail-credit-spread" },
  { activeTab: "portfolio-headlines", mockTestId: "mock-detail-portfolio-headlines" },
  { activeTab: "top-holdings", mockTestId: "mock-detail-top-holdings" },
  { activeTab: "action-attribution", mockTestId: "mock-detail-action-attribution" },
  { activeTab: "accounting-audit", mockTestId: "mock-detail-accounting-audit" },
];

describe("BondAnalyticsDetailSection", () => {
  it.each(TAB_MODULE_CASES)(
    "renders heading, registry copy, and the module panel for $activeTab",
    async ({ activeTab, mockTestId }) => {
      const onActiveTabChange = vi.fn();
      const def = getBondAnalyticsModuleDefinition(activeTab);

      render(
        <BondAnalyticsDetailSection
          activeTab={activeTab}
          onActiveTabChange={onActiveTabChange}
          reportDate="2026-03-31"
          periodType="MoM"
          {...defaultFilterProps}
        />,
      );

      expect(screen.getByRole("heading", { name: "分析明细" })).toBeInTheDocument();
      expect(screen.getByText(`当前查看：${def.label}`, { exact: true })).toBeInTheDocument();
      expect(screen.getByText(def.description, { exact: true })).toBeInTheDocument();

      expect(await screen.findByTestId(mockTestId)).toBeInTheDocument();
    },
  );

  it("calls onActiveTabChange when selecting a different tab", async () => {
    const user = userEvent.setup();
    const onActiveTabChange = vi.fn();

    render(
      <BondAnalyticsDetailSection
        activeTab="action-attribution"
        onActiveTabChange={onActiveTabChange}
        reportDate="2026-03-31"
        periodType="MoM"
        {...defaultFilterProps}
      />,
    );

    await user.click(screen.getByRole("tab", { name: "信用利差" }));

    expect(onActiveTabChange).toHaveBeenCalledTimes(1);
    expect(onActiveTabChange).toHaveBeenCalledWith("credit-spread");
  });
});
