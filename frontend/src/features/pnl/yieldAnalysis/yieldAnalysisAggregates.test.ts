import { describe, expect, it } from "vitest";

import type { PnlV1DetailRow } from "../../../api/contracts";
import { buildYieldAnalysisAggregates } from "./yieldAnalysisAggregates";

function makeRow(overrides: Partial<PnlV1DetailRow> = {}): PnlV1DetailRow {
  return {
    report_date: "2026-05-21",
    source: "FI",
    asset_code: "BOND-001",
    bond_name: "Bond A",
    portfolio: "Portfolio A",
    asset_type: "Type A",
    asset_class: "Class A",
    market_value: "100",
    interest_income: "10",
    fair_value_change: "20",
    capital_gain: "30",
    total_pnl: "60",
    source_version: "v1",
    trace_id: "trace-1",
    ...overrides,
  };
}

describe("buildYieldAnalysisAggregates", () => {
  it("keeps valid numeric strings aggregating as numeric totals and proportions", () => {
    const aggregates = buildYieldAnalysisAggregates([
      makeRow({ portfolio: "P1", total_pnl: "100.5", interest_income: "40.25" }),
      makeRow({
        asset_code: "BOND-002",
        bond_name: "Bond B",
        portfolio: "P1",
        total_pnl: "99.5",
        interest_income: "9.75",
        fair_value_change: "-10",
        capital_gain: "100",
      }),
    ]);

    expect(aggregates.by_portfolio).toEqual([
      expect.objectContaining({
        key: "P1",
        total_pnl: 200,
        interest_income: 50,
        fair_value_change: 10,
        capital_gain: 130,
        proportion: 1,
      }),
    ]);
  });

  it("does not coerce invalid money inputs into zero totals or proportions", () => {
    const aggregates = buildYieldAnalysisAggregates([
      makeRow({
        portfolio: "P-invalid",
        interest_income: null as unknown as string,
        fair_value_change: "" as unknown as string,
        capital_gain: "Infinity",
        total_pnl: undefined as unknown as string,
      }),
    ]);

    const [portfolioRow] = aggregates.by_portfolio;
    const [sourceRow] = aggregates.by_source;
    const [bondRow] = aggregates.by_bond_name;
    const [assetTypeRow] = aggregates.by_asset_type;

    for (const row of [portfolioRow, sourceRow, bondRow, assetTypeRow]) {
      expect(row).toBeDefined();
      expect(row.total_pnl).toBeNaN();
      expect(row.proportion).toBeNull();
    }

    expect(portfolioRow.interest_income).toBeNaN();
    expect(portfolioRow.fair_value_change).toBeNaN();
    expect(portfolioRow.capital_gain).toBeNaN();
  });
});
