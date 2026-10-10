import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MomentumScoreboardPanel, VolatilityClusteringPanel } from "./MomentumAndVolatilityPanels";

vi.mock("./CrossAssetECharts", () => ({ LazyCrossAssetECharts: () => <div /> }));

describe("cross-asset analytical presentation", () => {
  it("keeps window change and latest direction independent", () => {
    render(<MomentumScoreboardPanel rows={[{
      key: "cn_gov_10y", label: "10Y国债", tag: "利率", current: 1.68,
      chg1d: 0.1, chg5d: -0.11, chg20d: null, direction: "up", acceleration: "steady",
    }]} />);
    const table = screen.getByTestId("cross-asset-momentum-table-wrap");
    expect(table).toHaveTextContent("-0.11%");
    expect(table).toHaveTextContent("上行");
    expect(screen.getByText(/方向取最近 1 个间隔/)).toBeInTheDocument();
  });

  it("folds all normal assets and retains numeric detail when opened", () => {
    render(<VolatilityClusteringPanel alert={{ triggered: false, clusterCount: 0,
      totalAssets: 1, severity: "normal", headline: "暂无聚类信号。",
      assets: [{ key: "usdcny", label: "USD/CNY", rollingStdDev: 0.01, volRatio: 0.83, isElevated: false }],
    }} />);
    const summary = screen.getByTestId("cross-asset-vol-folded-assets");
    const details = summary.closest("details")!;
    expect(details.open).toBe(false);
    fireEvent.click(summary);
    expect(details.open).toBe(true);
    expect(within(details).getByRole("cell", { name: "0.83x" })).toBeVisible();
  });
});
