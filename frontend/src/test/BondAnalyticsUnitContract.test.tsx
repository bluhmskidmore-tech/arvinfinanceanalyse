import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BondDashboardHeadlinePayload, Numeric } from "../api/contracts";
import { BondKpiRow } from "../features/bond-analytics/components/BondKpiRow";
import { computeBpDelta } from "../features/bond-analytics/lib/bondAnalyticsHomeCalculations";
import { formatDv01Wan, formatPct } from "../features/bond-analytics/utils/formatters";

function numeric(raw: number | null, unit: Numeric["unit"], display?: string): Numeric {
  return {
    raw,
    unit,
    display: display ?? (raw === null ? "—" : String(raw)),
    precision: 4,
    sign_aware: true,
  };
}

function headline(
  overrides: Partial<BondDashboardHeadlinePayload["kpis"]> = {},
): BondDashboardHeadlinePayload {
  return {
    report_date: "2026-03-31",
    prev_report_date: null,
    kpis: {
      total_market_value: numeric(100_000_000, "yuan"),
      unrealized_pnl: numeric(2_000_000, "yuan"),
      weighted_ytm: numeric(0.0315, "ratio"),
      weighted_duration: numeric(3.204, "years"),
      weighted_coupon: numeric(0.028, "ratio"),
      credit_spread_median: numeric(42, "bp"),
      total_dv01: numeric(120_000, "dv01"),
      bond_count: 120,
      ...overrides,
    },
    prev_kpis: null,
  };
}

function tileValue(label: string): string | null | undefined {
  return screen.getByText(label).nextElementSibling?.textContent;
}

describe("bond-analysis unit contract (duration years / DV01 万元/bp / yield % vs bp)", () => {
  it("formatDv01Wan converts backend 元/bp DV01 to 万元/bp with 2 decimals", () => {
    // Backend serves DV01 in raw 元/bp (unit "dv01", pinned by
    // tests/test_bond_analytics_api.py); the page displays 万元/bp, so the
    // only correct axis is ÷1e4 — not ÷1e8 (亿 axis) and not raw passthrough.
    expect(formatDv01Wan(numeric(120_000, "dv01"))).toBe("12.00");
    expect(formatDv01Wan("120000")).toBe("12.00");
  });

  it("formatDv01Wan keeps null semantics as dash instead of 0", () => {
    expect(formatDv01Wan(null)).toBe("-");
    expect(formatDv01Wan(undefined)).toBe("-");
    expect(formatDv01Wan(numeric(null, "dv01"))).toBe("-");
  });

  it("renders weighted duration as raw years with 2 decimals, no unit rescaling", () => {
    render(<BondKpiRow headline={headline()} portfolioHeadlines={undefined} loading={false} />);
    expect(tileValue("加权久期")).toBe("3.20 年");
  });

  it("renders missing duration as em dash instead of 0.00 年", () => {
    render(
      <BondKpiRow
        headline={headline({ weighted_duration: numeric(null, "years") })}
        portfolioHeadlines={undefined}
        loading={false}
      />,
    );
    expect(tileValue("加权久期")).toBe("—");
  });

  it("keeps ratio yields on the % axis and yield deltas on the bp axis", () => {
    expect(formatPct(numeric(0.0315, "ratio"))).toBe("3.15%");
    expect(computeBpDelta(numeric(0.0315, "ratio"), numeric(0.0312, "ratio"))).toBeCloseTo(3, 5);
  });

  it("does not re-scale a server-formatted pct display (no double ×100)", () => {
    expect(formatPct(numeric(3.15, "pct", "3.15%"))).toBe("3.15%");
  });
});
