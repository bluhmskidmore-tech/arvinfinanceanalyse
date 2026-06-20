import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import {
  addDaysToIsoDate,
  buildReviewEvidenceLabel,
  isNetworkUnavailableError,
  reportDateMismatch,
} from "./dashboardPageHelpers";

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "trace-id",
    basis: "formal",
    result_kind: "k",
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("dashboardPageHelpers", () => {
  describe("buildReviewEvidenceLabel", () => {
    it("prioritizes domain effective dates over meta versions", () => {
      expect(
        buildReviewEvidenceLabel({
          domainsEffectiveDate: {
            overview: "2026-05-20",
            attribution: "2026-05-19",
          },
          overviewMeta: resultMeta(),
          attributionMeta: resultMeta(),
        }),
      ).toBe("overview=2026-05-20 / attribution=2026-05-19");
    });

    it("falls back to overview or attribution meta versions and filters unknown parts", () => {
      expect(
        buildReviewEvidenceLabel({
          domainsEffectiveDate: {},
          overviewMeta: null,
          attributionMeta: resultMeta({
            source_version: "source-v2",
            rule_version: "unknown",
            cache_version: "cache-v5",
          }),
        }),
      ).toBe("source-v2 / cache-v5");
    });

    it("returns the empty-state copy when dates and meta are unavailable", () => {
      expect(
        buildReviewEvidenceLabel({
          domainsEffectiveDate: {},
          overviewMeta: null,
          attributionMeta: null,
        }),
      ).toBe("首页快照返回后展示来源版本与有效日期");
    });
  });

  describe("addDaysToIsoDate", () => {
    it("adds calendar days to an ISO date", () => {
      expect(addDaysToIsoDate("2026-01-31", 1)).toBe("2026-02-01");
    });

    it("keeps invalid date input unchanged and preserves empty input", () => {
      expect(addDaysToIsoDate("not-a-date", 1)).toBe("not-a-date");
      expect(addDaysToIsoDate("   ", 1)).toBe("");
    });
  });

  describe("reportDateMismatch", () => {
    it("reports only when both dates are present and different", () => {
      expect(reportDateMismatch("2026-04-30", "2026-04-29")).toBe(true);
      expect(reportDateMismatch("2026-04-30", "2026-04-30")).toBe(false);
      expect(reportDateMismatch("2026-04-30", undefined)).toBe(false);
      expect(reportDateMismatch("", "2026-04-30")).toBe(false);
    });
  });

  describe("isNetworkUnavailableError", () => {
    it("matches common fetch and connection failures", () => {
      expect(isNetworkUnavailableError(new Error("Failed to fetch"))).toBe(true);
      expect(isNetworkUnavailableError("ERR_CONNECTION_REFUSED")).toBe(true);
    });

    it("ignores non-network errors", () => {
      expect(isNetworkUnavailableError(new Error("HTTP 500"))).toBe(false);
      expect(isNetworkUnavailableError(null)).toBe(false);
    });
  });
});
