import { describe, expect, it } from "vitest";

import type { BondDashboardHeadlinePayload, Numeric } from "../api/contracts";
import { BOND_ALIGNMENT_THRESHOLDS } from "../features/bond-analytics/lib/alignmentThresholds";
import {
  buildKpiValuePair,
  checkBondAlignment,
  computeBpDelta,
  computeRelativeChangePct,
} from "../features/bond-analytics/lib/bondAnalyticsHomeCalculations";

function numeric(raw: number | null, unit: Numeric["unit"] = "ratio"): Numeric {
  return {
    raw,
    unit,
    display: raw === null ? "—" : String(raw),
    precision: 4,
    sign_aware: true,
  };
}

function createHeadlinePayload(overrides: Partial<BondDashboardHeadlinePayload> = {}): BondDashboardHeadlinePayload {
  return {
    report_date: "2026-03-31",
    prev_report_date: "2026-02-28",
    kpis: {
      total_market_value: numeric(100_000_000, "yuan"),
      unrealized_pnl: numeric(2_000_000, "yuan"),
      weighted_ytm: numeric(0.0315, "ratio"),
      weighted_duration: numeric(3.2, "ratio"),
      weighted_coupon: numeric(0.028, "ratio"),
      credit_spread_median: numeric(0.0042, "ratio"),
      total_dv01: numeric(120_000, "dv01"),
      bond_count: 120,
    },
    prev_kpis: {
      total_market_value: numeric(99_500_000, "yuan"),
      unrealized_pnl: numeric(1_800_000, "yuan"),
      weighted_ytm: numeric(0.0312, "ratio"),
      weighted_duration: numeric(3.18, "ratio"),
      weighted_coupon: numeric(0.0275, "ratio"),
      credit_spread_median: numeric(0.0041, "ratio"),
      total_dv01: numeric(118_000, "dv01"),
      bond_count: 118,
    },
    ...overrides,
  };
}

describe("bondAnalyticsHomeCalculations", () => {
  it("正常值时按 raw 计算环比和 bp 变化", () => {
    const payload = createHeadlinePayload();
    const marketValuePair = buildKpiValuePair(payload, "total_market_value");
    const ytmDeltaBp = computeBpDelta(payload.kpis.weighted_ytm, payload.prev_kpis?.weighted_ytm ?? null);

    expect(computeRelativeChangePct(marketValuePair.current, marketValuePair.previous)).toBeCloseTo(
      0.502512,
      5,
    );
    expect(ytmDeltaBp).toBeCloseTo(3, 5);
  });

  it("previous 缺失时返回 null", () => {
    const payload = createHeadlinePayload({ prev_kpis: null });
    const ytmPair = buildKpiValuePair(payload, "weighted_ytm");
    expect(computeRelativeChangePct(ytmPair.current, ytmPair.previous)).toBeNull();
    expect(computeBpDelta(payload.kpis.weighted_ytm, null)).toBeNull();
  });

  it("previous=0 时环比返回 null", () => {
    expect(computeRelativeChangePct(100, 0)).toBeNull();
    expect(computeRelativeChangePct(-100, 0)).toBeNull();
  });

  it("负基数改善时保持正确业务语义", () => {
    expect(computeRelativeChangePct(-90, -100)).toBeCloseTo(10, 5);
    expect(computeRelativeChangePct(-110, -100)).toBeCloseTo(-10, 5);
  });

  it("null/undefined 输入时返回 null", () => {
    expect(computeRelativeChangePct(null, 100)).toBeNull();
    expect(computeRelativeChangePct(100, undefined)).toBeNull();
    expect(computeBpDelta(undefined, numeric(0.02, "ratio"))).toBeNull();
  });

  it("按阈值校验金额偏差（<=0.5%）", () => {
    const within = checkBondAlignment({
      kind: "amount",
      baseline: 100_000_000,
      candidate: 100_400_000,
    });
    const beyond = checkBondAlignment({
      kind: "amount",
      baseline: 100_000_000,
      candidate: 100_700_000,
    });

    expect(within.actualDeviation).toBeCloseTo(0.004, 6);
    expect(within.threshold).toBe(BOND_ALIGNMENT_THRESHOLDS.amountRelativeRatio);
    expect(within.withinThreshold).toBe(true);
    expect(beyond.withinThreshold).toBe(false);
  });

  it("按阈值校验收益率/利差偏差（<=1bp）", () => {
    const within = checkBondAlignment({
      kind: "yieldOrSpread",
      baseline: 10,
      candidate: 10.8,
    });
    const beyond = checkBondAlignment({
      kind: "yieldOrSpread",
      baseline: 10,
      candidate: 11.2,
    });

    expect(within.actualDeviation).toBeCloseTo(0.8, 6);
    expect(within.threshold).toBe(BOND_ALIGNMENT_THRESHOLDS.yieldOrSpreadBp);
    expect(within.withinThreshold).toBe(true);
    expect(beyond.withinThreshold).toBe(false);
  });

  it("按阈值校验比例偏差（<=0.1pct）", () => {
    const within = checkBondAlignment({
      kind: "ratio",
      baseline: 2.3,
      candidate: 2.37,
    });
    const beyond = checkBondAlignment({
      kind: "ratio",
      baseline: 2.3,
      candidate: 2.45,
    });

    expect(within.actualDeviation).toBeCloseTo(0.07, 6);
    expect(within.threshold).toBe(BOND_ALIGNMENT_THRESHOLDS.ratioPctPoint);
    expect(within.withinThreshold).toBe(true);
    expect(beyond.withinThreshold).toBe(false);
  });
});
