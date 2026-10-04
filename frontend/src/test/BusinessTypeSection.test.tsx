import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BondBusinessTypeMetricItem } from "../api/contracts";
import BusinessTypeSection from "../features/bond-dashboard/sections/BusinessTypeSection";
import { BOND_SECTION_READY } from "../features/bond-dashboard/sectionStatus";
import { formatRawAsNumeric } from "../utils/format";

const pct = (raw: number | null) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
const ratio = (raw: number | null) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });

function item(overrides: Partial<BondBusinessTypeMetricItem> = {}): BondBusinessTypeMetricItem {
  return {
    name: "Core book",
    market_value: "1000000000.00",
    weighted_avg_ytm: pct(0.0255),
    weighted_avg_duration: "3.50000000",
    duration_source: "formal",
    weighted_avg_ytm_coverage_ratio: ratio(0.98),
    weighted_avg_duration_coverage_ratio: ratio(0.97),
    ...overrides,
  };
}

describe("BusinessTypeSection", () => {
  it("renders weighted_avg_ytm as governed Numeric percent, not a raw *100 string", () => {
    render(<BusinessTypeSection items={[item()]} state={BOND_SECTION_READY} />);

    // raw=0.0255 (ratio) -> 2.55%；不再是后端直发的百分点字符串 "2.55000000"。
    expect(screen.getByTestId("bond-dashboard-business-type-metrics")).toHaveTextContent("2.55%");
  });

  it("renders EM_DASH instead of a fabricated zero when weighted_avg_ytm coverage is missing", () => {
    render(
      <BusinessTypeSection
        items={[item({ weighted_avg_ytm: pct(null), weighted_avg_duration: "" })]}
        state={BOND_SECTION_READY}
      />,
    );

    const panel = screen.getByTestId("bond-dashboard-business-type-metrics");
    expect(panel).toHaveTextContent("—");
    expect(panel).not.toHaveTextContent("0.00%");
  });
});
