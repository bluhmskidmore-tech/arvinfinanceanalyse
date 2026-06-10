import { describe, expect, it } from "vitest";

import type { ModuleHomeDetailRow } from "./moduleHomeModel";
import { rowChangeText, rowDisplayValue } from "./marketHomeRowDisplay";

function row(partial: Partial<ModuleHomeDetailRow>): ModuleHomeDetailRow {
  return {
    key: "test",
    label: "Test",
    value: "1.71%",
    detail: undefined,
    tradeDate: "2026-05-29",
    source: "CA.CN_GOV_10Y",
    tone: "ok",
    ...partial,
  };
}

describe("marketHomeRowDisplay", () => {
  it("keeps value intact when detail is present", () => {
    const sample = row({ value: "1.71%", detail: "-1bp" });
    expect(rowDisplayValue(sample)).toBe("1.71%");
    expect(rowChangeText(sample)).toBe("-1bp");
  });

  it("splits embedded change from combined value text", () => {
    const sample = row({ value: "4892.12 · 日变动 -0.45%" });
    expect(rowDisplayValue(sample)).toBe("4892.12");
    expect(rowChangeText(sample)).toBe("日变动 -0.45%");
  });
});
