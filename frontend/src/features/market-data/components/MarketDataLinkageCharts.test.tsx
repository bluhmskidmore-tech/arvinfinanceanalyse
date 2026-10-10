import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarketDataLinkageEnvironmentChart } from "./MarketDataLinkageCharts";

describe("MarketDataLinkageEnvironmentChart", () => {
  it("discloses unavailable derived spreads instead of hiding the chart region", () => {
    render(<MarketDataLinkageEnvironmentChart environmentScore={{ composite_score: 0.2 }} />);

    expect(screen.getByTestId("market-data-linkage-derived-spreads-bar")).toHaveTextContent(
      "缺少同日、可用的期限利差数据。",
    );
  });
});
