import { describe, expect, it } from "vitest";

import {
  buildLedgerKpiCards,
  formatLedgerYiAmount,
  formatLedgerYuanAmount,
  ledgerDataState,
} from "../features/ledger-dashboard/pages/ledgerDashboardPageModel";

describe("ledgerDashboardPageModel", () => {
  it("keeps dashboard KPI values in yi yuan", () => {
    expect(formatLedgerYiAmount(3289.07)).toBe("3289.07 亿元");
    expect(formatLedgerYiAmount(null)).toBe("--");

    const cards = buildLedgerKpiCards({
      as_of_date: "2026-03-17",
      asset_face_amount: 3289.07,
      liability_face_amount: 1231.77,
      net_face_exposure: 2057.31,
      alert_count: 0,
    });

    expect(cards.map((item) => item.value)).toEqual([
      "3289.07 亿元",
      "1231.77 亿元",
      "2057.31 亿元",
      "0",
    ]);
  });

  it("keeps position amounts as raw yuan for detail rows", () => {
    expect(formatLedgerYuanAmount(100000000)).toBe("100,000,000.00");
    expect(formatLedgerYuanAmount(null)).toBe("--");
  });

  it("prioritizes explicit loading, no-data, and fallback states", () => {
    expect(ledgerDataState(undefined, new Error("boom"))).toBe("loading_failure");
    expect(
      ledgerDataState(
        {
          source_version: null,
          rule_version: null,
          batch_id: null,
          stale: false,
          fallback: false,
          no_data: true,
        },
        null,
      ),
    ).toBe("no_data");
    expect(
      ledgerDataState(
        {
          source_version: "sv",
          rule_version: "rv",
          batch_id: 1,
          stale: true,
          fallback: true,
          no_data: false,
        },
        null,
      ),
    ).toBe("fallback");
  });
});
