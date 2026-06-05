import { describe, it, expect } from "vitest";
import {
  buildCorrelationMatrix,
  correlationColor,
  formatCorrelation,
  identifyMarketRegime,
  computeSparklinePercentile,
  percentileZoneColor,
  buildMomentumScoreboard,
  detectVolatilityClustering,
  computeEquityBondERP,
  buildDriverWaterfall,
  TREND_GROUPS,
  trendGroupLabels,
} from "../lib/crossAssetAnalytics";
import type { ResolvedCrossAssetKpi } from "../lib/crossAssetKpiModel";

function makeKpi(
  key: string,
  label: string,
  sparkline: number[],
  overrides: Partial<ResolvedCrossAssetKpi> = {},
): ResolvedCrossAssetKpi {
  return {
    key,
    label,
    format: "percent",
    tag: "test",
    resolvedSeriesId: key,
    sourceKind: "public",
    tradeDate: "2026-04-30",
    unit: "%",
    valueLabel: "1.00%",
    changeLabel: "+0.1bp",
    changeTone: "positive",
    sparkline,
    ...overrides,
  };
}

describe("buildCorrelationMatrix", () => {
  it("returns empty matrix if fewer than 2 eligible kpis", () => {
    const result = buildCorrelationMatrix([makeKpi("a", "A", [1, 2])]);
    expect(result.keys.length).toBe(0); // < 5 points → not eligible
  });

  it("computes NxN matrix for eligible kpis", () => {
    const kpis = [
      makeKpi("a", "A", [1, 2, 3, 4, 5]),
      makeKpi("b", "B", [2, 4, 6, 8, 10]),
      makeKpi("c", "C", [5, 4, 3, 2, 1]),
    ];
    const m = buildCorrelationMatrix(kpis);
    expect(m.keys).toEqual(["a", "b", "c"]);
    expect(m.cells.length).toBe(3);
    expect(m.cells[0].length).toBe(3);
    // Diagonal should be 1
    expect(m.cells[0][0].value).toBe(1);
    // A and B are perfectly correlated
    expect(m.cells[0][1].value).toBeCloseTo(1, 4);
    // A and C are perfectly anti-correlated
    expect(m.cells[0][2].value).toBeCloseTo(-1, 4);
  });
});

describe("correlationColor", () => {
  it("returns neutral for null", () => {
    expect(correlationColor(null)).toContain("rgba");
  });
  it("returns green-ish for positive", () => {
    expect(correlationColor(0.8)).toContain("34, 139, 34");
  });
  it("returns red-ish for negative", () => {
    expect(correlationColor(-0.7)).toContain("220, 53, 69");
  });
});

describe("formatCorrelation", () => {
  it("formats null as dash", () => {
    expect(formatCorrelation(null)).toBe("—");
  });
  it("formats number to 2 decimals", () => {
    expect(formatCorrelation(0.456)).toBe("0.46");
  });
});

describe("identifyMarketRegime", () => {
  it("identifies risk-on when equity rising and bond yield not falling", () => {
    const kpis = [
      makeKpi("cn_gov_10y", "10Y国债", [1.9, 1.91, 1.92, 1.93, 1.95, 1.96, 1.97, 1.98, 1.99, 2.0]),
      makeKpi("financial_conditions", "沪深300", [3800, 3820, 3850, 3870, 3900, 3920, 3950, 3980, 4000, 4050]),
      makeKpi("money_market_7d", "DR007", [1.8, 1.8, 1.81, 1.81, 1.82, 1.82, 1.82, 1.83, 1.83, 1.83]),
      makeKpi("brent", "布油", [65, 65, 66, 66, 66, 66, 66, 66, 66, 66], { format: "plain" }),
      makeKpi("steel", "钢", [3600, 3600, 3600, 3600, 3600, 3600, 3600, 3600, 3600, 3600], { format: "plain" }),
    ];
    const regime = identifyMarketRegime(kpis);
    expect(regime.regime).toBe("risk_on");
  });

  it("identifies risk-off when equity falling and bond yield falling", () => {
    const kpis = [
      makeKpi("cn_gov_10y", "10Y国债", [2.0, 1.98, 1.96, 1.93, 1.90]),
      makeKpi("financial_conditions", "沪深300", [4000, 3950, 3900, 3850, 3800]),
      makeKpi("money_market_7d", "DR007", [1.8, 1.8, 1.8, 1.8, 1.8]),
      makeKpi("brent", "布油", [65, 65, 65, 65, 65], { format: "plain" }),
      makeKpi("steel", "钢", [3600, 3600, 3600, 3600, 3600], { format: "plain" }),
    ];
    const regime = identifyMarketRegime(kpis);
    expect(regime.regime).toBe("risk_off");
  });

  it("returns mixed for unclear signals", () => {
    const kpis = [
      makeKpi("cn_gov_10y", "10Y国债", [2.0, 2.0, 2.0, 2.0, 2.0]),
      makeKpi("financial_conditions", "沪深300", [4000, 4000, 4000, 4000, 4000]),
      makeKpi("money_market_7d", "DR007", [1.8, 1.8, 1.8, 1.8, 1.8]),
      makeKpi("brent", "布油", [65, 65, 65, 65, 65], { format: "plain" }),
      makeKpi("steel", "钢", [3600, 3600, 3600, 3600, 3600], { format: "plain" }),
    ];
    const regime = identifyMarketRegime(kpis);
    expect(regime.regime).toBe("mixed");
  });
});

describe("computeSparklinePercentile", () => {
  it("returns null for insufficient data", () => {
    expect(computeSparklinePercentile([1])).toBeNull();
  });

  it("computes percentile for normal distribution", () => {
    const data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const result = computeSparklinePercentile(data);
    expect(result).not.toBeNull();
    expect(result!.percentile).toBe(100);
    expect(result!.zone).toBe("extreme_high");
  });

  it("computes low percentile when current is near minimum", () => {
    const data = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10];
    const result = computeSparklinePercentile(data);
    expect(result).not.toBeNull();
    expect(result!.percentile).toBe(0);
    expect(result!.zone).toBe("extreme_low");
  });

  it("computes mid percentile", () => {
    const data = [10, 30, 50, 70, 90, 50]; // 50 is the current
    const result = computeSparklinePercentile(data);
    expect(result).not.toBeNull();
    expect(result!.percentile).toBeGreaterThanOrEqual(30);
    expect(result!.percentile).toBeLessThanOrEqual(70);
    expect(result!.zone).toBe("mid");
  });
});

describe("percentileZoneColor", () => {
  it("returns different colors for different zones", () => {
    const colors = new Set([
      percentileZoneColor("extreme_low"),
      percentileZoneColor("low"),
      percentileZoneColor("mid"),
      percentileZoneColor("high"),
      percentileZoneColor("extreme_high"),
    ]);
    expect(colors.size).toBe(5);
  });
});

describe("buildMomentumScoreboard", () => {
  it("builds rows from kpis with sparklines", () => {
    const kpis = [
      makeKpi("a", "Asset A", [100, 101, 102, 103, 105]),
      makeKpi("b", "Asset B", [200, 198, 196, 194, 192]),
    ];
    const rows = buildMomentumScoreboard(kpis);
    expect(rows).toHaveLength(2);
    expect(rows[0].label).toBe("Asset A");
    expect(rows[0].direction).toBe("up");
    expect(rows[0].chg1d).not.toBeNull();
    expect(rows[1].direction).toBe("down");
  });
});

describe("TREND_GROUPS", () => {
  it("has expected groups", () => {
    expect(TREND_GROUPS.map((g) => g.key)).toEqual(["all", "rates", "equity", "commodity_fx"]);
  });
});

describe("trendGroupLabels", () => {
  it("returns null for 'all' group", () => {
    expect(trendGroupLabels("all", [])).toBeNull();
  });

  it("returns label set for specific group", () => {
    const kpis = [
      makeKpi("cn_gov_10y", "10Y国债", [1, 2, 3, 4, 5]),
      makeKpi("us_gov_10y", "10Y美债", [1, 2, 3, 4, 5]),
      makeKpi("brent", "布油", [60, 61, 62, 63, 64], { format: "plain" }),
    ];
    const labels = trendGroupLabels("rates", kpis);
    expect(labels).not.toBeNull();
    expect(labels!.has("10Y国债")).toBe(true);
    expect(labels!.has("10Y美债")).toBe(true);
    expect(labels!.has("布油")).toBe(false);
  });
});

describe("detectVolatilityClustering", () => {
  it("returns normal when no elevated assets", () => {
    const kpis = [
      makeKpi("a", "A", [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
      makeKpi("b", "B", [2, 2, 2, 2, 2, 2, 2, 2, 2, 2]),
    ];
    const alert = detectVolatilityClustering(kpis);
    expect(alert.severity).toBe("normal");
    expect(alert.triggered).toBe(false);
  });

  it("detects elevated vol when recent window has more variance", () => {
    // Stable for first 10 days, then spike in last 5
    const kpis = [
      makeKpi("a", "A", [100, 100, 100, 100, 100, 100, 100, 100, 110, 90, 115, 85, 120]),
      makeKpi("b", "B", [50, 50, 50, 50, 50, 50, 50, 50, 55, 45, 60, 40, 65]),
    ];
    const alert = detectVolatilityClustering(kpis);
    expect(alert.clusterCount).toBeGreaterThan(0);
  });
});

describe("computeEquityBondERP", () => {
  it("returns unavailable when PE or bond data missing", () => {
    const kpis = [makeKpi("other", "Other", [1, 2, 3])];
    const erp = computeEquityBondERP(kpis);
    expect(erp.available).toBe(false);
    expect(erp.verdict).toBe("unavailable");
  });

  it("computes equity_cheap when PE is low", () => {
    const kpis = [
      makeKpi("csi300_pe", "沪深300PE", [10, 10, 10, 10, 10], { format: "index" }), // 1/10 = 10%
      makeKpi("cn_gov_10y", "10Y国债", [2.5, 2.5, 2.5, 2.5, 2.5]),                // 2.5%
    ];
    const erp = computeEquityBondERP(kpis);
    expect(erp.available).toBe(true);
    expect(erp.erpPct).toBeCloseTo(7.5, 1); // 10% - 2.5% = 7.5%
    expect(erp.verdict).toBe("equity_cheap");
  });

  it("computes equity_expensive when PE is high", () => {
    const kpis = [
      makeKpi("csi300_pe", "沪深300PE", [50, 50, 50, 50, 50], { format: "index" }), // 1/50 = 2%
      makeKpi("cn_gov_10y", "10Y国债", [2.5, 2.5, 2.5, 2.5, 2.5]),                // 2.5%
    ];
    const erp = computeEquityBondERP(kpis);
    expect(erp.available).toBe(true);
    expect(erp.erpPct).toBeCloseTo(-0.5, 1); // 2% - 2.5% = -0.5%
    expect(erp.verdict).toBe("equity_expensive");
  });
});

describe("buildDriverWaterfall", () => {
  it("builds factor + total bars from env scores", () => {
    const bars = buildDriverWaterfall({
      liquidity_score: 0.15,
      rate_direction_score: -0.1,
      growth_score: 0.05,
      inflation_score: -0.02,
      composite_score: 0.08,
    });
    expect(bars).toHaveLength(5); // 4 factors + 1 total
    expect(bars[0].key).toBe("liquidity");
    expect(bars[0].kind).toBe("factor");
    expect(bars[4].key).toBe("composite");
    expect(bars[4].kind).toBe("total");
    expect(bars[4].value).toBe(0.08);
  });

  it("assigns correct colors based on value", () => {
    const bars = buildDriverWaterfall({
      liquidity_score: 0.2,
      rate_direction_score: -0.2,
      growth_score: 0,
      inflation_score: 0,
    });
    expect(bars[0].color).toBe("#16a34a"); // positive
    expect(bars[1].color).toBe("#dc2626"); // negative
    expect(bars[2].color).toBe("#94a3b8"); // neutral
  });
});
