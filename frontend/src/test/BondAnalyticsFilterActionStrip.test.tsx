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
  it("keeps only advanced filters below the homepage toolbar and wires callbacks", async () => {
    const user = userEvent.setup();
    const onRefreshAnalytics = vi.fn();
    const analyticsProps = mockAnalyticsFilterProps();

    renderStrip(
      <BondAnalyticsFilterActionStrip
        {...analyticsProps}
        onRefreshAnalytics={onRefreshAnalytics}
        isAnalyticsRefreshing={false}
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByTestId("bond-analysis-filter-action-strip")).toBeInTheDocument();
    expect(screen.getByText("复核入口")).toBeInTheDocument();
    expect(screen.getByText("参数与下钻边界")).toBeInTheDocument();
    expect(screen.getByText("高级筛选 / 参数调整")).toBeInTheDocument();
    expect(screen.getByText("尚未捕获刷新运行。")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-refresh-state")).toHaveAttribute("data-state", "idle");
    expect(screen.queryByText("报告日期")).not.toBeInTheDocument();
    expect(screen.queryByText("统计区间")).not.toBeInTheDocument();

    await user.click(screen.getByText("高级筛选 / 参数调整"));
    const advancedComboboxes = screen.getAllByRole("combobox");
    expect(advancedComboboxes).toHaveLength(4);

    fireEvent.mouseDown(advancedComboboxes[0]!);
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
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={vi.fn()}
        isAnalyticsRefreshing
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByText("刷新中")).toBeInTheDocument();
    expect(screen.getByText("正在刷新受治理总览状态...")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-refresh-state")).toHaveAttribute("data-state", "running");
  });

  it("shows latest run id when provided", () => {
    render(
      <BondAnalyticsFilterActionStrip
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={vi.fn()}
        isAnalyticsRefreshing={false}
        analyticsRefreshError={null}
        lastAnalyticsRefreshRunId="run-xyz"
      />,
    );

    expect(screen.getByText("最近运行")).toBeInTheDocument();
    expect(screen.getByText("最近运行 run-xyz")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-refresh-state")).toHaveAttribute("data-state", "complete");
  });

  it("surfaces analytics refresh errors in the refresh state panel", () => {
    render(
      <BondAnalyticsFilterActionStrip
        {...mockAnalyticsFilterProps()}
        onRefreshAnalytics={vi.fn()}
        isAnalyticsRefreshing={false}
        analyticsRefreshError="Refresh pipeline failed"
        lastAnalyticsRefreshRunId={null}
      />,
    );

    expect(screen.getByText("刷新异常")).toBeInTheDocument();
    expect(screen.getByText("Refresh pipeline failed")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-refresh-state")).toHaveAttribute("data-state", "error");
  });
});
