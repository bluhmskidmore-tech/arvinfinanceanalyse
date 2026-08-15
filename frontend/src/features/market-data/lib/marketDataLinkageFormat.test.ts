import { describe, expect, it } from "vitest";

import {
  displayLinkageWarning,
  formatImpactRatioPercent,
  formatRateDirectionLabel,
  isLinkageSelfCorrelation,
  linkageScoreTone,
} from "./marketDataLinkageFormat";

describe("formatImpactRatioPercent", () => {
  it("formats fractional ratios as two-decimal percentages", () => {
    expect(formatImpactRatioPercent("0.003819989568694886028786885406")).toBe("0.38%");
    expect(formatImpactRatioPercent(0.0041)).toBe("0.41%");
    expect(formatImpactRatioPercent(-0.012)).toBe("-1.20%");
  });

  it("keeps empty and non-numeric semantics", () => {
    expect(formatImpactRatioPercent(null)).toBe("不可用");
    expect(formatImpactRatioPercent("")).toBe("不可用");
    expect(formatImpactRatioPercent("n/a")).toBe("n/a");
  });
});

describe("formatRateDirectionLabel", () => {
  it("maps backend enums to Chinese labels", () => {
    expect(formatRateDirectionLabel("falling")).toBe("下行");
    expect(formatRateDirectionLabel("rising")).toBe("上行");
    expect(formatRateDirectionLabel("neutral")).toBe("震荡");
    expect(formatRateDirectionLabel("sideways")).toBe("震荡");
  });

  it("passes through unregistered enums and handles missing values", () => {
    expect(formatRateDirectionLabel("mixed_regime")).toBe("mixed_regime");
    expect(formatRateDirectionLabel(null)).toBe("不可用");
    expect(formatRateDirectionLabel(undefined)).toBe("不可用");
  });
});

describe("linkageScoreTone", () => {
  it("treats |score| < 0.2 as neutral band", () => {
    expect(linkageScoreTone(-0.1)).toBe("default");
    expect(linkageScoreTone(0.19)).toBe("default");
    expect(linkageScoreTone(0)).toBe("default");
  });

  it("colors by sign outside the band and defaults on missing", () => {
    expect(linkageScoreTone(-0.35)).toBe("negative");
    expect(linkageScoreTone(0.51)).toBe("positive");
    expect(linkageScoreTone(null)).toBe("default");
    expect(linkageScoreTone(Number.NaN)).toBe("default");
  });
});

describe("displayLinkageWarning", () => {
  it("translates indicator-score-unavailable warnings and keeps the payload", () => {
    expect(displayLinkageWarning("Indicator score unavailable: 中国:GDP:不变价:当季同比")).toBe(
      "指标评分不可用：中国:GDP:不变价:当季同比",
    );
  });

  it("passes through unrecognized warnings verbatim", () => {
    expect(displayLinkageWarning("仅为分析信号，不要把估算影响当作正式归因。")).toBe(
      "仅为分析信号，不要把估算影响当作正式归因。",
    );
  });
});

describe("isLinkageSelfCorrelation", () => {
  it("flags the target family's own yield-curve tenor series", () => {
    expect(
      isLinkageSelfCorrelation({ series_name: "中债国债到期收益率:10年", target_family: "treasury" }),
    ).toBe(true);
    expect(
      isLinkageSelfCorrelation({ series_name: "中债国开债到期收益率:5年", target_family: "cdb" }),
    ).toBe(true);
    expect(
      isLinkageSelfCorrelation({
        series_name: "中债中短期票据到期收益率(AAA):3年",
        target_family: "aaa_credit",
      }),
    ).toBe(true);
  });

  it("keeps genuine cross-dimension series", () => {
    expect(
      isLinkageSelfCorrelation({ series_name: "沪深300前五大权重占比", target_family: "treasury" }),
    ).toBe(false);
    expect(isLinkageSelfCorrelation({ series_name: "DR007", target_family: "treasury" })).toBe(false);
    // 国开收益率对国债目标是跨品种信息，不按自相关剔除。
    expect(
      isLinkageSelfCorrelation({ series_name: "中债国开债到期收益率:10年", target_family: "treasury" }),
    ).toBe(false);
    expect(isLinkageSelfCorrelation({ series_name: "CPI YoY", target_family: "aaa_credit" })).toBe(false);
  });
});
