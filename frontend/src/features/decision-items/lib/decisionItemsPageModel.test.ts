import { describe, expect, it } from "vitest";

import { formatDecisionReasonText } from "./decisionItemsPageModel";

describe("decisionItemsPageModel", () => {
  describe("formatDecisionReasonText", () => {
    it("formats small, large, and negative plain-decimal reason amounts without a number round-trip", () => {
      expect(formatDecisionReasonText("Gap 9999.999 万元")).toBe("Gap 10,000.00 万元");
      expect(formatDecisionReasonText("Gap 10000.00 万元")).toBe("Gap 1.00 亿元");
      expect(formatDecisionReasonText("Gap -12000.1 万元 and -10000.00 万元")).toBe(
        "Gap -1.20 亿元 and -1.00 亿元",
      );
      expect(formatDecisionReasonText("Gap 9007199254740993.00 万元")).toBe(
        "Gap 900,719,925,474.10 亿元",
      );
    });

    it("keeps non-numeric reason text unchanged", () => {
      expect(formatDecisionReasonText("No amounts present.")).toBe("No amounts present.");
      expect(formatDecisionReasonText("Bad 0E-8 万元 and n/a")).toBe("Bad 0E-8 万元 and n/a");
      expect(formatDecisionReasonText("Infinity 万元")).toBe("Infinity 万元");
    });

    it("preserves raw text for scientific or malformed amount fragments", () => {
      expect(formatDecisionReasonText("量化口径 1e5 万元。")).toBe("量化口径 1e5 万元。");
      expect(formatDecisionReasonText("金额 12abc 万元")).toBe("金额 12abc 万元");
    });
  });

});
