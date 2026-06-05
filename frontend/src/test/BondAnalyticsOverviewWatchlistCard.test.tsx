import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondAnalyticsOverviewWatchlistCard } from "../features/bond-analytics/components/BondAnalyticsOverviewWatchlistCard";

describe("BondAnalyticsOverviewWatchlistCard", () => {
  it("lists flagged anomalies when the overview payload reports them", () => {
    const topAnomalies = ["First anomaly body", "Second anomaly body"];

    render(<BondAnalyticsOverviewWatchlistCard topAnomalies={topAnomalies} />);

    expect(screen.getByText("2 个标记信号")).toBeInTheDocument();
    expect(screen.getByText("First anomaly body")).toBeInTheDocument();
    expect(screen.getByText("Second anomaly body")).toBeInTheDocument();
  });

  it("renders calm helper copy when no anomalies are present", () => {
    render(<BondAnalyticsOverviewWatchlistCard topAnomalies={[]} />);

    expect(screen.getByText("当前总览载荷未触发异常。")).toBeInTheDocument();
    expect(
      screen.getByText(
        "当前总览载荷平稳。可使用右侧决策队列选择下一步下钻页面，不强行生成合成首屏指标。",
      ),
    ).toBeInTheDocument();
  });
});
