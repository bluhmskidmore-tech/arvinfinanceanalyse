import { describe, expect, it } from "vitest";

import { formatDetailComputedAt } from "./BondAnalyticsDetailPrimitives";

describe("formatDetailComputedAt", () => {
  it("annotates parsed timestamps with the registered UTC basis", () => {
    // UTC 口径是登记过的决策（不转本地时区），必须显式标注，
    // 否则 UTC+8 用户会把展示值误读成本地时间（慢 8 小时）。
    expect(formatDetailComputedAt("2026-08-13T15:38:32.639045+00:00")).toBe("2026-08-13 15:38 UTC");
    expect(formatDetailComputedAt("2026-04-10T00:00:00Z")).toBe("2026-04-10 00:00 UTC");
    expect(formatDetailComputedAt("2026-04-10T08:00:00+08:00")).toBe("2026-04-10 00:00 UTC");
  });

  it("passes through unparseable input without inventing a timezone label", () => {
    expect(formatDetailComputedAt("not-a-timestamp")).toBe("not-a-timestamp");
  });
});
