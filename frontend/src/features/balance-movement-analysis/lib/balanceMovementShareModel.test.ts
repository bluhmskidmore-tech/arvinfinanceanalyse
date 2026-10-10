import { describe, expect, it } from "vitest";

import type { BalanceMovementRow, BalanceMovementTrendMonth } from "../../../api/contracts";
import { buildBalanceStructureEvolution, nullableNumber, resolveBucketSharePct } from "./balanceMovementShareModel";

describe("resolveBucketSharePct", () => {
  it("prefers backend current_balance_pct when present", () => {
    expect(resolveBucketSharePct("42.44")).toBe(42.44);
  });

  it("keeps missing backend share missing instead of recomputing it", () => {
    expect(resolveBucketSharePct(null)).toBeNull();
    expect(resolveBucketSharePct(undefined)).toBeNull();
    expect(resolveBucketSharePct("")).toBeNull();
    expect(resolveBucketSharePct("   ")).toBeNull();
  });

  it("returns null for an invalid backend share", () => {
    expect(resolveBucketSharePct("not-a-number")).toBeNull();
  });

  it("does not treat backend zero as missing", () => {
    expect(resolveBucketSharePct("0")).toBe(0);
  });
});

describe("nullableNumber", () => {
  it("returns null for empty or non-finite inputs", () => {
    expect(nullableNumber(null)).toBeNull();
    expect(nullableNumber(undefined)).toBeNull();
    expect(nullableNumber("")).toBeNull();
    expect(nullableNumber("   ")).toBeNull();
    expect(nullableNumber("NaN")).toBeNull();
  });
});

function structureMonth(
  reportMonth: string,
  shares: Array<BalanceMovementRow["current_balance_pct"]> = ["10", "20", "70"],
): BalanceMovementTrendMonth {
  const reportDate = reportMonth + "-28";
  return {
    report_date: reportDate,
    report_month: reportMonth,
    current_balance_total: "987654321",
    balance_change_total: "0",
    rows: (["AC", "OCI", "TPL"] as const).map((basisBucket, index) => ({
      report_date: reportDate,
      report_month: reportMonth,
      currency_basis: "CNX",
      basis_bucket: basisBucket,
      sort_order: index,
      current_balance: "123456789",
      previous_balance: "0",
      previous_balance_pct: null,
      current_balance_pct: shares[index],
      balance_change: "0",
      change_pct: null,
      contribution_pct: null,
      zqtz_amount: "0",
      gl_amount: "0",
      reconciliation_diff: "0",
      reconciliation_status: "matched",
      source_version: "fixture",
      rule_version: "fixture",
      chain_status: null,
      position_source_basis: "CNY",
    })),
  };
}

describe("buildBalanceStructureEvolution", () => {
  it("uses backend shares and amounts without losing real zero or display precision", () => {
    const month = structureMonth("2026-02", ["42.4444", "0", "57.5556"]);
    const model = buildBalanceStructureEvolution([month]);

    expect(model.chartRows).toEqual([{
      monthLabel: "26-02",
      AC: 42.4444,
      OCI: 0,
      TPL: 57.5556,
      acValueYi: 1.23456789,
      ociValueYi: 1.23456789,
      tplValueYi: 1.23456789,
      totalValueYi: 9.87654321,
    }]);
    expect(model.balanceStructureInsight).toBeNull();
    expect(model.structureShareTableRows[0].point.OCI).toBe(0);
    expect(month.rows[1].current_balance_pct).toBe("0");
  });

  it("keeps all detail months but suppresses the whole chart for an incomplete intermediate snapshot", () => {
    const months = [
      structureMonth("2026-01"),
      structureMonth("2026-02", ["12", null, "68"]),
      structureMonth("2026-03", ["15", "20", "65"]),
    ];
    const model = buildBalanceStructureEvolution(months);

    expect(model.structureShareTableRows.map((row) => row.reportMonth)).toEqual([
      "2026-01", "2026-02", "2026-03",
    ]);
    expect(model.structureShareTableRows[1].point.OCI).toBeNull();
    expect(model.chartRows).toEqual([]);
    expect(model.balanceStructureInsight).toBe("AC占比较首月 +5.00pp，OCI 0.00pp，TPL -5.00pp。");
    expect(model.shareRowByReportMonth.get("2026-02")).toBe(model.structureShareTableRows[1]);
  });

  it.each([0, 2])("does not substitute an inner snapshot for an incomplete endpoint %s", (index) => {
    const months = ["2026-01", "2026-02", "2026-03"].map((month) => structureMonth(month));
    months[index].rows[0].current_balance_pct = null;
    const model = buildBalanceStructureEvolution(months);

    expect(model.chartRows).toEqual([]);
    expect(model.balanceStructureInsight).toBeNull();
    expect(model.structureShareTableRows).toHaveLength(3);
  });

  it("preserves first bucket matches and the last report-month match without sorting or deduplicating snapshots", () => {
    const first = structureMonth("2025-02");
    first.rows.push({ ...first.rows[0], current_balance_pct: "99", current_balance: "999" });
    const last = structureMonth("2025-02", ["15", "20", "65"]);
    last.report_date = "2025-02-27";
    const model = buildBalanceStructureEvolution([first, structureMonth("2026-01"), last]);

    expect(model.structureShareTableRows.map((row) => row.reportMonth)).toEqual([
      "2025-02", "2026-01", "2025-02",
    ]);
    expect(model.structureShareTableRows[0].point.AC).toBe(10);
    expect(model.structureShareTableRows[0].point.acValueYi).toBe(1.23456789);
    expect(model.shareRowByReportMonth.get("2025-02")).toBe(model.structureShareTableRows[2]);
    expect(model.chartRows).toHaveLength(3);
    expect(model.balanceStructureInsight).toBeNull();
  });

  it("leaves an empty history empty", () => {
    const model = buildBalanceStructureEvolution([]);

    expect(model.structureShareTableRows).toEqual([]);
    expect(model.shareRowByReportMonth.size).toBe(0);
    expect(model.chartRows).toEqual([]);
    expect(model.balanceStructureInsight).toBeNull();
  });
});
