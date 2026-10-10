import { describe, expect, it } from "vitest";

import {
  formatCrossAssetLinkageWarnings,
  localizeCrossAssetLinkageWarning,
  summarizeCrossAssetLinkageWarnings,
} from "./crossAssetLinkageWarnings";

describe("crossAssetLinkageWarnings", () => {
  it("localizes indicator history warnings into Chinese", () => {
    expect(localizeCrossAssetLinkageWarning("Indicator history too short: SHIBOR:隔夜")).toBe(
      "指标历史偏短：Shibor 隔夜。",
    );
    expect(localizeCrossAssetLinkageWarning("Indicator history too short: SHIBOR:1周")).toBe(
      "指标历史偏短：Shibor 1周。",
    );
  });

  it("normalizes risk tensor date lag copy for status detail", () => {
    expect(
      localizeCrossAssetLinkageWarning("风险张量使用最近日期 2026-05-31，目标日期为 2026-06-09。"),
    ).toBe("风险张量沿用 2026-05-31，报告日 2026-06-09 无更新。");
  });

  it("deduplicates formatted warnings and summarizes multiple alerts", () => {
    const formatted = formatCrossAssetLinkageWarnings([
      "Indicator history too short: SHIBOR:隔夜",
      "Indicator history too short: SHIBOR:隔夜",
      "Indicator history too short: SHIBOR:1周",
    ]);
    expect(formatted).toEqual(["指标历史偏短：Shibor 隔夜。", "指标历史偏短：Shibor 1周。"]);
    expect(summarizeCrossAssetLinkageWarnings(formatted)).toBe(
      "指标历史偏短：Shibor 隔夜。；另有 1 项告警。",
    );
  });
});
