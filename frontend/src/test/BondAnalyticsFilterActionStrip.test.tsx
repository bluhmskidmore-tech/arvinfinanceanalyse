import { ConfigProvider } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";

import { BondAnalyticsFilterActionStrip } from "../features/bond-analytics/components/BondAnalyticsFilterActionStrip";

function renderStrip(ui: ReactElement) {
  return render(
    <ConfigProvider getPopupContainer={(triggerNode) => triggerNode?.parentElement ?? document.body}>
      {ui}
    </ConfigProvider>,
  );
}

const dateOptions = [
  { value: "2026-03-31", label: "2026-03-31" },
  { value: "2026-02-28", label: "2026-02-28" },
];

function mockAnalyticsFilterProps() {
  return {
    assetClass: "all" as const,
    onAssetClassChange: vi.fn(),
    accountingClass: "all" as const,
    onAccountingClassChange: vi.fn(),
    scenarioSet: "standard" as const,
    onScenarioSetChange: vi.fn(),
    spreadScenarios: "10,25,50",
    onSpreadScenariosChange: vi.fn(),
  };
}

describe("BondAnalyticsFilterActionStrip", () => {
  it("renders filters, refresh control, refresh state, and cockpit rule; wires callbacks", async () => {
    const user = userEvent.setup();
    const onReportDateChange = vi.fn();
    const onPeriodTypeChange = vi.fn();
    const onRefreshAnalytics = vi.fn();

    renderStrip(
      <BondAnalyticsFilterActionStrip
        dateOptions={dateOptions}
        reportDate="2026-03-31"
        onReportDateChange={onReportDateChange}
        periodType="MoM"
        onPeriodTypeChange={onPeriodTypeChange}
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={onRefreshAnalytics}
        isAnalyticsRefreshing={false}
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByTestId("bond-analysis-filter-action-strip")).toBeInTheDocument();
    expect(screen.getByText("Report date")).toBeInTheDocument();
    expect(screen.getByText("Period")).toBeInTheDocument();
    expect(screen.getByText("Overview refresh")).toBeInTheDocument();
    expect(screen.getByText("Refresh state")).toBeInTheDocument();
    expect(screen.getByText("Cockpit rule")).toBeInTheDocument();
    expect(screen.getByText("No refresh run has been captured yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Only action attribution may promote into headline or main-rail analytics in this phase."),
    ).toBeInTheDocument();

    expect(screen.getByTitle("2026-03-31")).toBeInTheDocument();
    expect(screen.getByTitle("Month")).toBeInTheDocument();

    const comboboxes = screen.getAllByRole("combobox");
    expect(comboboxes).toHaveLength(6);

    fireEvent.mouseDown(comboboxes[0]!);
    const dateOption = await screen.findByTitle("2026-02-28");
    await user.click(dateOption);

    await waitFor(() => {
      expect(onReportDateChange).toHaveBeenCalled();
      expect(onReportDateChange.mock.calls[0]?.[0]).toBe("2026-02-28");
    });

    fireEvent.mouseDown(screen.getAllByRole("combobox")[1]!);
    const periodOption = await screen.findByTitle("YTD");
    await user.click(periodOption);

    await waitFor(() => {
      expect(onPeriodTypeChange).toHaveBeenCalledWith("YTD");
    });

    await user.click(screen.getByTestId("bond-analytics-refresh-button"));
    expect(onRefreshAnalytics).toHaveBeenCalledTimes(1);
  });

  it("shows refreshing copy when analytics refresh is in flight", () => {
    render(
      <BondAnalyticsFilterActionStrip
        dateOptions={dateOptions}
        reportDate="2026-03-31"
        onReportDateChange={vi.fn()}
        periodType="MoM"
        onPeriodTypeChange={vi.fn()}
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={vi.fn()}
        isAnalyticsRefreshing
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByText("Refreshing governed overview state...")).toBeInTheDocument();
  });

  it("shows latest run id when provided", () => {
    render(
      <BondAnalyticsFilterActionStrip
        dateOptions={dateOptions}
        reportDate="2026-03-31"
        onReportDateChange={vi.fn()}
        periodType="MoM"
        onPeriodTypeChange={vi.fn()}
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={vi.fn()}
        isAnalyticsRefreshing={false}
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId="run-xyz"
      />,
    );

    expect(screen.getByText("Latest run run-xyz")).toBeInTheDocument();
  });

  it("surfaces analytics refresh errors in the refresh state panel", () => {
    render(
      <BondAnalyticsFilterActionStrip
        dateOptions={dateOptions}
        reportDate="2026-03-31"
        onReportDateChange={vi.fn()}
        periodType="MoM"
        onPeriodTypeChange={vi.fn()}
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={vi.fn()}
        isAnalyticsRefreshing={false}
        analyticsRefreshError="Refresh pipeline failed"
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByText("Refresh pipeline failed")).toBeInTheDocument();
  });
});
