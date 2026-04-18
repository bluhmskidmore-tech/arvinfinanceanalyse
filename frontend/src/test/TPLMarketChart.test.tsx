import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="tpl-market-echarts-stub" />,
}));

import type { Numeric, TPLMarketCorrelationPayload } from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import { TPLMarketChart } from "../features/pnl-attribution/components/TPLMarketChart";

function num(raw: number | null, unit: Numeric["unit"] = "yuan"): Numeric {
  return {
    raw,
    unit,
    display: "",
    precision: 2,
    sign_aware: false,
  };
}

describe("TPLMarketChart", () => {
  it("renders cumulative treasury change in bp", () => {
    const data: TPLMarketCorrelationPayload = {
      start_period: "2026-02",
      end_period: "2026-03",
      num_periods: 2,
      correlation_coefficient: num(-0.62, "ratio"),
      correlation_interpretation: "test",
      total_tpl_fv_change: num(42_000_000),
      avg_treasury_10y_change: num(-7.5, "bp"),
      treasury_10y_total_change: num(-15.0, "bp"),
      analysis_summary: "summary",
      data_points: [
        {
          period: "2026-02",
          period_label: "2026年02月",
          tpl_fair_value_change: num(10_000_000),
          tpl_total_pnl: num(10_000_000),
          tpl_scale: num(1_000_000_000),
          treasury_10y: num(2.35, "pct"),
          treasury_10y_change: num(null, "bp"),
          dr007: num(null, "pct"),
        },
        {
          period: "2026-03",
          period_label: "2026年03月",
          tpl_fair_value_change: num(32_000_000),
          tpl_total_pnl: num(32_000_000),
          tpl_scale: num(1_100_000_000),
          treasury_10y: num(2.2, "pct"),
          treasury_10y_change: num(-15.0, "bp"),
          dr007: num(null, "pct"),
        },
      ],
    };

    const okState: DataSectionState = { kind: "ok" };

    render(<TPLMarketChart data={data} state={okState} onRetry={() => {}} />);

    expect(screen.getByText("-15.0 BP")).toBeInTheDocument();
    expect(screen.getByTestId("tpl-market-echarts-stub")).toBeInTheDocument();
  });
});
