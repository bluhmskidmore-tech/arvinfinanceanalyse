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
  it("renders primary controls, exposes advanced filters progressively, and wires callbacks", async () => {
    const user = userEvent.setup();
    const onReportDateChange = vi.fn();
    const onPeriodTypeChange = vi.fn();
    const onRefreshAnalytics = vi.fn();
    const analyticsProps = mockAnalyticsFilterProps();

    renderStrip(
      <BondAnalyticsFilterActionStrip
        dateOptions={dateOptions}
        reportDate="2026-03-31"
        onReportDateChange={onReportDateChange}
        periodType="MoM"
        onPeriodTypeChange={onPeriodTypeChange}
        {...analyticsProps}
        onRefreshAnalytics={onRefreshAnalytics}
        isAnalyticsRefreshing={false}
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByTestId("bond-analysis-filter-action-strip")).toBeInTheDocument();
    expect(screen.getByText("报表日期")).toBeInTheDocument();
    expect(screen.getByText("统计区间")).toBeInTheDocument();
    expect(screen.getByText("刷新分析")).toBeInTheDocument();
    expect(screen.getByText("尚未捕获刷新运行。")).toBeInTheDocument();
    expect(screen.getByText("高级筛选")).toBeInTheDocument();

    expect(screen.getByTitle("2026-03-31")).toBeInTheDocument();
    expect(screen.getByTitle("月度环比")).toBeInTheDocument();

    const comboboxes = screen.getAllByRole("combobox");
    expect(comboboxes.length).toBeGreaterThanOrEqual(2);

    fireEvent.mouseDown(comboboxes[0]!);
    const dateOption = await screen.findByTitle("2026-02-28");
    await user.click(dateOption);

    await waitFor(() => {
      expect(onReportDateChange).toHaveBeenCalled();
      expect(onReportDateChange.mock.calls[0]?.[0]).toBe("2026-02-28");
    });

    fireEvent.mouseDown(screen.getAllByRole("combobox")[1]!);
    const periodOption = await screen.findByTitle("年初至今");
    await user.click(periodOption);

    await waitFor(() => {
      expect(onPeriodTypeChange).toHaveBeenCalledWith("YTD");
    });

    await user.click(screen.getByText("高级筛选"));
    const advancedComboboxes = screen.getAllByRole("combobox");
    expect(advancedComboboxes).toHaveLength(6);

    fireEvent.mouseDown(advancedComboboxes[2]!);
    const assetOption = await screen.findByTitle("利率债");
    await user.click(assetOption);
    await waitFor(() => {
      expect(analyticsProps.onAssetClassChange).toHaveBeenCalledWith("rate");
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

    expect(screen.getByText("正在刷新受治理总览状态...")).toBeInTheDocument();
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

    expect(screen.getByText("最近运行 run-xyz")).toBeInTheDocument();
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
