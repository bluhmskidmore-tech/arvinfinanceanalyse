import { describe, expect, it } from "vitest";

import { AVG_BALANCE_MISSING_DISPLAY, formatAvgBalanceYi } from "./pnlByBusinessPageModel";

describe("PnlByBusinessPage avg balance display", () => {
  it("treats numeric zero as present rather than missing", () => {
    expect(formatAvgBalanceYi(0)).toBe("0.00");
    expect(formatAvgBalanceYi("0")).toBe("0.00");
  });

  it("treats nullish and invalid values as missing with the EM_DASH label", () => {
    expect(AVG_BALANCE_MISSING_DISPLAY).toBe("—（日均缺失）");
    expect(formatAvgBalanceYi(null)).toBe(AVG_BALANCE_MISSING_DISPLAY);
    expect(formatAvgBalanceYi(undefined)).toBe(AVG_BALANCE_MISSING_DISPLAY);
    expect(formatAvgBalanceYi("")).toBe(AVG_BALANCE_MISSING_DISPLAY);
    expect(formatAvgBalanceYi("abc")).toBe(AVG_BALANCE_MISSING_DISPLAY);
    expect(formatAvgBalanceYi(Number.NaN)).toBe(AVG_BALANCE_MISSING_DISPLAY);
  });
});
