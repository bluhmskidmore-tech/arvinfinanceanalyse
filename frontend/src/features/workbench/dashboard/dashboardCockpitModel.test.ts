import { describe, expect, it } from "vitest";

import type { BondPortfolioHeadlinesPayload, Numeric } from "../../../api/contracts";
import { buildRiskItems } from "./dashboardCockpitModel";

function numeric(display: string, raw = 1): Numeric {
  return {
    raw,
    unit: "ratio",
    display,
    precision: 2,
    sign_aware: false,
  };
}

function backendScalarPortfolio(reportDate = "2026-04-30"): BondPortfolioHeadlinesPayload {
  return {
    report_date: reportDate,
    total_market_value: "343822795478.69000000",
    weighted_ytm: "0.02565621",
    weighted_duration: "4.13678311",
    weighted_coupon: "0.02069003",
    total_dv01: "106155944.30769531",
    bond_count: 1740,
    credit_weight: "0.29250449",
    issuer_hhi: "0.05088252",
    issuer_top5_weight: "0.41354965",
    by_asset_class: [
      {
        asset_class: "credit",
        market_value: "100569711455.34000000",
        duration: "2.40294438",
        dv01: "23572092.66263087",
        weight: "0.29250449",
      },
      {
        asset_class: "rate",
        market_value: "134490494185.69000000",
        duration: "5.62782976",
        dv01: "73667216.08117440",
        weight: "0.39116224",
      },
    ],
    warnings: [],
    computed_at: "2026-05-10T00:00:00Z",
  } as unknown as BondPortfolioHeadlinesPayload;
}

describe("buildRiskItems", () => {
  it("formats backend scalar strings for risk rows", () => {
    const riskItems = buildRiskItems(backendScalarPortfolio(), "2026-04-30");

    expect(riskItems.map((item) => item.value)).toEqual([
      "10,615.59 万",
      "4.14",
      "41.35%",
      "29.25%",
    ]);
    expect(riskItems.map((item) => item.level)).toEqual([71, 59, 41, 29]);
  });

  it("trusts the ratio contract for risk levels instead of the |x|<=1 percent heuristic", () => {
    const base = backendScalarPortfolio();

    // 契约内：raw 为小数比率，固定 ×100。
    const decimalRatio = buildRiskItems(
      {
        ...base,
        issuer_top5_weight: "0.41354965",
        credit_weight: "0.0009",
      } as unknown as BondPortfolioHeadlinesPayload,
      "2026-04-30",
    );
    expect(decimalRatio.find((item) => item.id === "issuer-top5")?.level).toBe(41);
    expect(decimalRatio.find((item) => item.id === "credit-weight")?.level).toBe(0);

    // 越出契约（疑似百分点值）不再被启发式原样透传，×100 后按上限截断。
    const outOfContract = buildRiskItems(
      {
        ...base,
        issuer_top5_weight: "41.35",
      } as unknown as BondPortfolioHeadlinesPayload,
      "2026-04-30",
    );
    expect(outOfContract.find((item) => item.id === "issuer-top5")?.level).toBe(100);

    // raw 缺失 → level 0（该字段有其他风险值时仍渲染行）。
    const nullWeight = buildRiskItems(
      {
        ...base,
        issuer_top5_weight: null,
      } as unknown as BondPortfolioHeadlinesPayload,
      "2026-04-30",
    );
    expect(nullWeight.find((item) => item.id === "issuer-top5")?.level).toBe(0);
  });

  it("blocks mismatched report-date risk reads", () => {
    const riskItems = buildRiskItems(backendScalarPortfolio("2026-03-31"), "2026-04-30");

    expect(riskItems).toEqual([
      expect.objectContaining({
        id: "portfolio-risk-blocked",
        status: "blocked",
        value: "—",
      }),
    ]);
  });

  it("renders a blocked placeholder when same-day risk fields are unusable", () => {
    const emptyPortfolio = {
      ...backendScalarPortfolio(),
      by_asset_class: [],
      total_dv01: null,
      weighted_duration: null,
      issuer_top5_weight: null,
      credit_weight: null,
    } as unknown as BondPortfolioHeadlinesPayload;

    const riskItems = buildRiskItems(emptyPortfolio, "2026-04-30");

    expect(riskItems).toEqual([
      expect.objectContaining({
        id: "portfolio-risk-empty",
        status: "blocked",
        value: "—",
      }),
    ]);
  });

  it("accepts Numeric display objects for risk values", () => {
    const riskItems = buildRiskItems(
      {
        ...backendScalarPortfolio(),
        total_dv01: numeric("10,615.59 万", 106_155_876.54),
        weighted_duration: numeric("4.14", 4.14),
        issuer_top5_weight: numeric("41.35%", 0.4135),
        credit_weight: numeric("29.25%", 0.2925),
      } as unknown as BondPortfolioHeadlinesPayload,
      "2026-04-30",
    );

    expect(riskItems.map((item) => item.value)).toEqual([
      "10,615.59 万",
      "4.14",
      "41.35%",
      "29.25%",
    ]);
  });
});
