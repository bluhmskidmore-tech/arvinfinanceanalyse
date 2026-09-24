import { describe, expect, it } from "vitest";

import type {
  AssetStructurePayload,
  YieldDistributionPayload,
} from "../../../../api/contracts";
import { mapHomeSummaryDistributions } from "./mapHomeSummaryDistributions";

function numeric(
  raw: number,
  display: string,
  unit: "yuan" | "pct" | "bp" | "ratio" | "dv01" | "yi" = "yuan",
) {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
  };
}

describe("mapHomeSummaryDistributions", () => {
  it("maps home summary distributions without inventing missing percentages", () => {
    const assetPayload: AssetStructurePayload = {
      report_date: "2026-04-30",
      group_by: "bond_type",
      total_market_value: numeric(20_000_000_000, "200.00 yi"),
      items: [
        {
          category: "credit",
          total_market_value: numeric(12_000_000_000, "120.00 yi"),
          bond_count: 4,
          percentage: numeric(0.6, "60%", "pct"),
        },
        {
          category: "",
          total_market_value: numeric(0, ""),
          bond_count: 0,
          percentage: numeric(0, "", "pct"),
        },
      ],
    };
    const yieldPayload: YieldDistributionPayload = {
      report_date: "2026-04-30",
      weighted_ytm: numeric(0.028, "2.80%", "pct"),
      items: [
        {
          yield_bucket: "2.5%-3.0%",
          total_market_value: numeric(12_000_000_000, "120.00 yi"),
          bond_count: 4,
        },
      ],
    };

    const sections = mapHomeSummaryDistributions({
      report_date: "2026-04-30",
      asset_type: assetPayload,
      yield_distribution: yieldPayload,
    });

    const assetSection = sections.find((section) => section.key === "asset_type");
    const yieldSection = sections.find((section) => section.key === "yield_distribution");

    expect(assetSection?.rows[0]).toMatchObject({
      label: "credit",
      valueRaw: 12_000_000_000,
      valueDisplay: "120.00 yi",
      percentageRaw: 0.6,
      percentageDisplay: "60%",
      count: 4,
    });
    expect(assetSection?.rows[1]).toMatchObject({
      label: "—",
      valueRaw: 0,
      valueDisplay: "—",
      percentageRaw: 0,
      count: 0,
    });
    expect(yieldSection?.rows[0]).toMatchObject({
      label: "2.5%-3.0%",
      valueDisplay: "120.00 yi",
      percentageRaw: null,
      count: 4,
    });
  });
});
