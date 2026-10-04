import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CorrelationHeatmapPanel } from "./CorrelationAndRegimePanels";
import type { CorrelationMatrix } from "../lib/crossAssetAnalytics";

vi.mock("./CrossAssetECharts", () => ({
  LazyCrossAssetECharts: ({ option }: { option: unknown }) => <div data-testid="correlation-option">{JSON.stringify(option)}</div>,
}));

function matrixFor(values: (number | null)[][]): CorrelationMatrix {
  const keys = values.map((_, index) => `asset-${index}`);
  return {
    keys,
    labels: keys.map((_, index) => `资产${index + 1}`),
    cells: values.map((row, ri) => row.map((value, ci) => ({ rowKey: keys[ri], colKey: keys[ci], value }))),
  };
}

describe("CorrelationHeatmapPanel", () => {
  it("shows a heatmap immediately and preserves zero and missing values in chart and folded table", () => {
    render(<CorrelationHeatmapPanel matrix={matrixFor([[1, 0, null], [0, 1, -0.82], [null, -0.82, 1]])} theme="terminal" />);
    const option = JSON.parse(screen.getByTestId("correlation-option").textContent!);
    expect(option.series[0].type).toBe("heatmap");
    expect(option.series[0].data).toContainEqual([1, 0, 0]);
    expect(option.series[0].data).toContainEqual([2, 0, "-"]);
    expect(option.series[0].data).toContainEqual([2, 1, -0.82]);
    expect(option.visualMap).toMatchObject({ min: -1, max: 1 });
    const details = screen.getByTestId("cross-asset-correlation-details");
    expect(details).not.toHaveAttribute("open");
    expect(within(details).getByRole("table", { hidden: true })).toHaveTextContent("—");
    expect(within(details).getByRole("table", { hidden: true })).toHaveTextContent("0.00");
    expect(screen.queryByText("关注组合")).not.toBeInTheDocument();
  });

  it("does not describe an all-positive matrix as negative correlation", () => {
    render(<CorrelationHeatmapPanel matrix={matrixFor([[1, 0.4], [0.4, 1]])} />);
    expect(screen.getByText("最低相关")).toBeInTheDocument();
    expect(screen.queryByText("最强背离")).not.toBeInTheDocument();
  });

  it("does not describe an all-negative matrix as positive correlation", () => {
    render(<CorrelationHeatmapPanel matrix={matrixFor([[1, -0.4], [-0.4, 1]])} />);
    expect(screen.getByText("最高相关")).toBeInTheDocument();
    expect(screen.queryByText("最强共振")).not.toBeInTheDocument();
  });
});
