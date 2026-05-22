import { describe, expect, it } from "vitest";

import { formatAvgBalanceYi } from "./pnlByBusinessPageModel";

describe("PnlByBusinessPage avg balance display", () => {
  it("treats numeric zero as present rather than missing", () => {
    expect(formatAvgBalanceYi(0)).toBe("0.00");
    expect(formatAvgBalanceYi("0")).toBe("0.00");
  });

  it("treats nullish and invalid values as missing", () => {
    expect(formatAvgBalanceYi(null)).toBe("日均缺失");
    expect(formatAvgBalanceYi(undefined)).toBe("日均缺失");
    expect(formatAvgBalanceYi("")).toBe("日均缺失");
    expect(formatAvgBalanceYi("abc")).toBe("日均缺失");
    expect(formatAvgBalanceYi(Number.NaN)).toBe("日均缺失");
  });
});
