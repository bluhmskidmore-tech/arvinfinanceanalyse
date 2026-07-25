import { describe, expect, it } from "vitest";

import { buildEnvFactorDetailRows } from "./envScoreFactorDetail";

const baseFactor = {
  category: "rate",
  series_id: "s-rate-10y",
  series_name: "中债国债到期收益率:10年",
  window_start: "2026-04-24",
  window_end: "2026-07-22",
  start_value: 1.7601,
  latest_value: 1.7297,
  delta: -0.0304,
  score: -0.295,
  weight: 1.0,
  scoring_method: "robust_environment_score_v1",
  observation_count: 61,
  winsorized: true,
  normalized_signal: -0.61,
};

describe("buildEnvFactorDetailRows", () => {
  it("maps factor categories to Chinese labels", () => {
    const rows = buildEnvFactorDetailRows({
      contributing_factors: [
        { ...baseFactor, category: "rate" },
        { ...baseFactor, category: "liquidity" },
        { ...baseFactor, category: "growth" },
        { ...baseFactor, category: "inflation" },
      ],
    });
    expect(rows.map((row) => row.categoryLabel)).toEqual(["利率", "流动性", "增长", "通胀"]);
  });

  it("formats window as MM-DD~MM-DD and falls back to ~ when start/end is null", () => {
    const rows = buildEnvFactorDetailRows({
      contributing_factors: [
        baseFactor,
        { ...baseFactor, series_id: "s2", window_start: null, window_end: null },
        { ...baseFactor, series_id: "s3", window_start: null, window_end: "2026-07-22" },
      ],
    });
    expect(rows[0].windowLabel).toBe("04-24~07-22");
    expect(rows[1].windowLabel).toBe("~");
    expect(rows[2].windowLabel).toBe("~");
  });

  it("formats delta with sign and 4 decimals, compacting huge values like GDP", () => {
    const rows = buildEnvFactorDetailRows({
      contributing_factors: [
        baseFactor,
        { ...baseFactor, series_id: "s2", delta: 0.8 },
        { ...baseFactor, series_id: "s3", delta: 21344.11 },
      ],
    });
    expect(rows[0].deltaLabel).toBe("-0.0304");
    expect(rows[1].deltaLabel).toBe("+0.8000");
    expect(rows[2].deltaLabel).toBe("+2.1万");
  });

  it("formats score with sign and 3 decimals and derives tone", () => {
    const rows = buildEnvFactorDetailRows({
      contributing_factors: [
        baseFactor,
        { ...baseFactor, series_id: "s2", score: 0.54 },
        { ...baseFactor, series_id: "s3", score: 0 },
      ],
    });
    expect(rows[0].scoreLabel).toBe("-0.295");
    expect(rows[0].tone).toBe("neg");
    expect(rows[1].scoreLabel).toBe("+0.540");
    expect(rows[1].tone).toBe("pos");
    expect(rows[2].scoreLabel).toBe("0.000");
    expect(rows[2].tone).toBe("neu");
  });

  it("returns an empty array for null/undefined/empty inputs", () => {
    expect(buildEnvFactorDetailRows(null)).toEqual([]);
    expect(buildEnvFactorDetailRows(undefined)).toEqual([]);
    expect(buildEnvFactorDetailRows({})).toEqual([]);
    expect(buildEnvFactorDetailRows({ contributing_factors: [] })).toEqual([]);
  });

  it("keeps raw numeric fields and observation count", () => {
    const rows = buildEnvFactorDetailRows({ contributing_factors: [baseFactor] });
    expect(rows[0].delta).toBe(-0.0304);
    expect(rows[0].score).toBe(-0.295);
    expect(rows[0].weight).toBe(1.0);
    expect(rows[0].observationCount).toBe(61);
    expect(rows[0].seriesName).toBe("中债国债到期收益率:10年");
  });
});
