import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BondDashboardHeadlinePayload, Numeric } from "../api/contracts";
import { BondKpiRow } from "../features/bond-analytics/components/BondKpiRow";
import { formatRawAsNumeric } from "../utils/format";

function numeric(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function headline(overrides: Partial<BondDashboardHeadlinePayload["kpis"]> = {}): BondDashboardHeadlinePayload {
  const kpis = {
    total_market_value: numeric(100_000_000, "yuan"),
    unrealized_pnl: numeric(1_000_000, "yuan", true),
    weighted_ytm: numeric(0.025, "pct"),
    weighted_duration: numeric(3.2, "ratio"),
    weighted_coupon: numeric(0.02, "pct"),
    credit_spread_median: numeric(80, "bp"),
    total_dv01: numeric(1000, "dv01"),
    bond_count: 12,
    ...overrides,
  };
  const completeKpis: BondDashboardHeadlinePayload["kpis"] = {
    ...kpis,
    bond_count: kpis.bond_count ?? 12,
  };
  return {
    report_date: "2026-03-31",
    prev_report_date: null,
    kpis: completeKpis,
    prev_kpis: {
      ...completeKpis,
      credit_spread_median: numeric(0.0038, "ratio"),
    },
  };
}

describe("BondKpiRow unit rendering", () => {
  it("renders credit spread from Numeric.unit instead of raw-value thresholds", () => {
    render(
      <BondKpiRow
        headline={headline({ credit_spread_median: numeric(0.42, "bp") })}
        portfolioHeadlines={undefined}
        loading={false}
      />,
    );

    expect(screen.getAllByText("0.4 bp")).toHaveLength(1);
    expect(screen.queryByText("4,200.0 bp")).not.toBeInTheDocument();
  });
});
