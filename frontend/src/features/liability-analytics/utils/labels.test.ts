import { describe, expect, it } from "vitest";

import { EM_DASH, formatRawAsNumeric } from "../../../utils/format";
import { counterpartyTypeLabel, termBucketLabel, unsignedNumericDisplay } from "./labels";

describe("counterpartyTypeLabel", () => {
  it("maps backend counterparty type enums to Chinese labels", () => {
    expect(counterpartyTypeLabel("Bank")).toBe("银行");
    expect(counterpartyTypeLabel("Non-Bank FI")).toBe("非银金融");
    expect(counterpartyTypeLabel("NonBank")).toBe("非银金融");
    expect(counterpartyTypeLabel("Corporate")).toBe("企业");
    expect(counterpartyTypeLabel("Corporate/Other")).toBe("企业/其他");
    expect(counterpartyTypeLabel("Other")).toBe("其他");
  });

  it("passes unregistered or empty values through unchanged", () => {
    expect(counterpartyTypeLabel("Sovereign")).toBe("Sovereign");
    expect(counterpartyTypeLabel("")).toBe("");
    expect(counterpartyTypeLabel(null)).toBe("");
    expect(counterpartyTypeLabel(undefined)).toBe("");
  });
});

describe("termBucketLabel", () => {
  it("maps V1 monthly bucket enums to Chinese labels", () => {
    expect(termBucketLabel("0-3M")).toBe("0-3月");
    expect(termBucketLabel("3-6M")).toBe("3-6月");
    expect(termBucketLabel("6-12M")).toBe("6-12月");
    expect(termBucketLabel("1-3Y")).toBe("1-3年");
    expect(termBucketLabel("3-5Y")).toBe("3-5年");
    expect(termBucketLabel("5-10Y")).toBe("5-10年");
    expect(termBucketLabel("10Y+")).toBe("10年以上");
    expect(termBucketLabel("Matured")).toBe("已到期");
  });

  it("passes unregistered bucket names through unchanged", () => {
    expect(termBucketLabel("已到期/逾期")).toBe("已到期/逾期");
    expect(termBucketLabel("")).toBe("");
  });
});

describe("unsignedNumericDisplay", () => {
  it("strips the sign-aware leading plus but keeps negatives and precision", () => {
    const positive = formatRawAsNumeric({ raw: 0.014, unit: "pct", sign_aware: true });
    const negative = formatRawAsNumeric({ raw: -0.005, unit: "pct", sign_aware: true });
    expect(positive.display.startsWith("+")).toBe(true);
    expect(unsignedNumericDisplay(positive)).toBe(positive.display.slice(1));
    expect(unsignedNumericDisplay(negative)).toBe(negative.display);
  });

  it("falls back to EM_DASH for missing values", () => {
    expect(unsignedNumericDisplay(null)).toBe(EM_DASH);
    expect(unsignedNumericDisplay(undefined)).toBe(EM_DASH);
  });
});
