import { describe, expect, it } from "vitest";

import {
  buildLedgerPnlHrefForReportDate,
  nextDefaultReportDateIfUnset,
} from "./productCategoryPnlPageModel";

describe("productCategoryPnlPageModel date semantics", () => {
  describe("nextDefaultReportDateIfUnset", () => {
    it("does not override a non-empty selection", () => {
      expect(nextDefaultReportDateIfUnset("2026-01-31", ["2026-02-28"])).toBeNull();
    });

    it("returns null when the API list is missing", () => {
      expect(nextDefaultReportDateIfUnset("", undefined)).toBeNull();
    });

    it("returns null when the API list is empty", () => {
      expect(nextDefaultReportDateIfUnset("", [])).toBeNull();
    });

    it("defaults to the first report_dates entry in API order when none selected", () => {
      expect(nextDefaultReportDateIfUnset("", ["2026-03-31", "2026-02-28"])).toBe("2026-03-31");
    });

    it("preserves an explicit empty first slot", () => {
      expect(nextDefaultReportDateIfUnset("", [""])).toBe("");
    });
  });

  describe("buildLedgerPnlHrefForReportDate", () => {
    it("uses the bare ledger path when report_date is not chosen", () => {
      expect(buildLedgerPnlHrefForReportDate("")).toBe("/ledger-pnl");
    });

    it("appends encoded report_date for cross-page navigation", () => {
      expect(buildLedgerPnlHrefForReportDate("2026-01-31")).toBe(
        "/ledger-pnl?report_date=2026-01-31",
      );
      expect(buildLedgerPnlHrefForReportDate("2026/01")).toBe("/ledger-pnl?report_date=2026%2F01");
    });
  });
});
