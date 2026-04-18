import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="advanced-attribution-echarts-stub" />,
}));

import type {
  AdvancedAttributionSummary,
  CarryRollDownPayload,
  KRDAttributionPayload,
  Numeric,
  SpreadAttributionPayload,
} from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import { AdvancedAttributionChart } from "../features/pnl-attribution/components/AdvancedAttributionChart";

function n(raw: number | null, unit: Numeric["unit"] = "yuan"): Numeric {
  return {
    raw,
    unit,
    display: "",
    precision: 2,
    sign_aware: false,
  };
}

describe("AdvancedAttributionChart", () => {
  it("renders annualized static return without multiplying it twice", () => {
    const carryData: CarryRollDownPayload = {
      report_date: "2026-03-31",
      total_market_value: n(12_000_000_000),
      portfolio_carry: n(1.85, "pct"),
      portfolio_rolldown: n(0.42, "pct"),
      portfolio_static_return: n(2.27, "pct"),
      total_carry_pnl: n(18_000_000),
      total_rolldown_pnl: n(4_000_000),
      total_static_pnl: n(22_000_000),
      ftp_rate: n(2.15, "pct"),
      items: [],
    };
    const spreadData: SpreadAttributionPayload = {
      report_date: "2026-03-31",
      start_date: "2026-03-01",
      end_date: "2026-03-31",
      treasury_10y_start: n(2.35, "pct"),
      treasury_10y_end: n(2.2, "pct"),
      treasury_10y_change: n(-15, "bp"),
      total_market_value: n(12_000_000_000),
      portfolio_duration: n(3.8),
      total_treasury_effect: n(22_000_000),
      total_spread_effect: n(-4_000_000),
      total_price_change: n(18_000_000),
      primary_driver: "treasury",
      interpretation: "test",
      items: [],
    };
    const krdData: KRDAttributionPayload = {
      report_date: "2026-03-31",
      start_date: "2026-03-01",
      end_date: "2026-03-31",
      total_market_value: n(12_000_000_000),
      portfolio_duration: n(3.8),
      portfolio_dv01: n(4_200_000),
      total_duration_effect: n(18_000_000),
      curve_shift_type: "bull_steepener",
      curve_interpretation: "test",
      max_contribution_tenor: "5Y",
      max_contribution_value: n(8_500_000),
      buckets: [],
    };
    const summary: AdvancedAttributionSummary = {
      report_date: "2026-03-31",
      portfolio_carry: n(1.85, "pct"),
      portfolio_rolldown: n(0.42, "pct"),
      static_return_annualized: n(9.99, "pct"),
      treasury_effect_total: n(22_000_000),
      spread_effect_total: n(-4_000_000),
      spread_driver: "treasury",
      max_krd_tenor: "5Y",
      curve_shape_change: "bull_steepener",
      key_insights: [],
    };

    const okState: DataSectionState = { kind: "ok" };

    render(
      <AdvancedAttributionChart
        carryData={carryData}
        spreadData={spreadData}
        krdData={krdData}
        summaryData={summary}
        state={okState}
        onRetry={() => {}}
      />,
    );

    expect(screen.getByText("9.99%")).toBeInTheDocument();
    expect(screen.queryByText("326.88%")).not.toBeInTheDocument();
  });
});
