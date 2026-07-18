import { describe, expect, it } from "vitest";

import type {
  CashflowProjectionPayload,
  Numeric,
  ResultMeta,
  RiskTensorHistoryPayload,
  RiskTensorPayload,
  YieldCurveTermStructurePayload,
} from "../../../api/contracts";
import {
  buildRiskV6Briefs,
  buildRiskV6CashflowTrack,
  buildRiskV6DeltaChip,
  buildRiskV6DetailTables,
  buildRiskV6Hero,
  buildRiskV6KpiCards,
  buildRiskV6KrdBars,
  buildRiskV6LineageRows,
  buildRiskV6Sparkline,
  buildRiskV6YieldCurveChart,
} from "./riskHomeAdapter";

function num(raw: number, overrides?: Partial<Numeric>): Numeric {
  return {
    raw,
    unit: "yuan",
    display: String(raw),
    precision: 2,
    sign_aware: false,
    ...overrides,
  };
}

/** 与 2026-06-30 正式张量同形的载荷（数值即线上治理读数）。 */
function tensorFixture(): RiskTensorPayload {
  return {
    report_date: "2026-06-30",
    portfolio_dv01: num(106949424.12992053, { unit: "dv01" }),
    regulatory_dv01: num(106949424.12992053, { unit: "dv01" }),
    krd_1y: num(6204347.64058226),
    krd_3y: num(22789266.50395854),
    krd_5y: num(18158026.62229127),
    krd_7y: num(8575885.26732997),
    krd_10y: num(27539150.86824232),
    krd_30y: num(23682747.22751617),
    cs01: num(27308897.86532232, { unit: "dv01" }),
    portfolio_convexity: num(30.89728073, { unit: "ratio", display: "30.90" }),
    portfolio_modified_duration: num(3.77704871, { unit: "ratio", display: "3.78" }),
    issuer_concentration_hhi: num(0.04842124, { unit: "ratio" }),
    issuer_top5_weight: num(0.40305884, { unit: "ratio" }),
    asset_cashflow_30d: num(6201412918.165448),
    asset_cashflow_90d: num(14705758881.951147),
    liability_cashflow_30d: num(12515125677.89139),
    liability_cashflow_90d: num(15794163600.631117),
    liquidity_gap_30d: num(-6313712759.725942, { sign_aware: true }),
    liquidity_gap_90d: num(-1088404718.6799679, { sign_aware: true }),
    liquidity_gap_30d_ratio: num(-0.0181514, { unit: "ratio", sign_aware: true }),
    total_market_value: num(347836150851.31525),
    rate_risk_market_value: num(301718445315.9752),
    rate_risk_dv01: num(106868724.92027242, { unit: "dv01" }),
    rate_risk_modified_duration: num(3.77704871, { unit: "ratio" }),
    duration_excluded_market_value: num(46117705535.340004),
    duration_excluded_count: 131,
    bond_count: 1767,
    quality_flag: "warning",
    warnings: ["w1"],
  };
}

function historyFixture(periods = 24): RiskTensorHistoryPayload {
  const points = Array.from({ length: periods }, (_, index) => ({
    report_date: `2026-06-${String(index + 1).padStart(2, "0")}`,
    portfolio_dv01: String(100000000 + index * 100000),
    regulatory_dv01: String(100000000 + index * 100000),
    portfolio_modified_duration: String(3.8 - index * 0.01),
    portfolio_convexity: String(31 - index * 0.02),
    cs01: String(26000000 + index * 50000),
    issuer_concentration_hhi: String(0.05 - index * 0.0001),
    issuer_top5_weight: String(0.41 - index * 0.001),
    liquidity_gap_30d: String(-7000000000 + index * 10000000),
  }));
  return {
    report_date: "2026-06-30",
    periods,
    window: { from: points[0].report_date, to: points[periods - 1].report_date },
    points,
  };
}

describe("buildRiskV6Sparkline", () => {
  it("returns null for fewer than two usable points", () => {
    expect(buildRiskV6Sparkline([])).toBeNull();
    expect(buildRiskV6Sparkline([1])).toBeNull();
  });

  it("maps a rising series into the 96x30 viewBox with glow endpoint", () => {
    const spark = buildRiskV6Sparkline([1, 2, 3, 4]);
    expect(spark).not.toBeNull();
    expect(spark?.linePath.startsWith("M 3,25")).toBe(true);
    expect(spark?.linePath).toContain("C");
    expect(spark?.endX).toBe(93);
    expect(spark?.endY).toBe(5);
    expect(spark?.areaPath.endsWith("Z")).toBe(true);
    expect(spark?.areaPath).toContain("L 93,30 L 3,30 Z");
  });

  it("draws a midline for a flat series", () => {
    const spark = buildRiskV6Sparkline([2, 2, 2]);
    expect(spark?.endY).toBe(15);
  });

  it("drops non-finite values before laying out points", () => {
    const spark = buildRiskV6Sparkline([1, Number.NaN, 3]);
    expect(spark).not.toBeNull();
    expect(spark?.endX).toBe(93);
  });
});

describe("buildRiskV6DeltaChip", () => {
  it("formats percent deltas with direction arrows", () => {
    expect(buildRiskV6DeltaChip(101, 100, "percent")).toEqual({ text: "▲ 1.0%", direction: "up" });
    expect(buildRiskV6DeltaChip(99, 100, "percent")).toEqual({ text: "▼ 1.0%", direction: "down" });
  });

  it("formats absolute deltas for duration/convexity", () => {
    expect(buildRiskV6DeltaChip(3.76, 3.78, "absolute", 2)).toEqual({ text: "▼ 0.02", direction: "down" });
  });

  it("formats ratio deltas in pp", () => {
    expect(buildRiskV6DeltaChip(0.4, 0.415, "pp", 1)).toEqual({ text: "▼ 1.5pp", direction: "down" });
    expect(buildRiskV6DeltaChip(0.0484, 0.0516, "pp", 2)).toEqual({ text: "▼ 0.32pp", direction: "down" });
  });

  it("formats yuan deltas in 亿元", () => {
    expect(buildRiskV6DeltaChip(-6313712759.725942, -4492547186.2, "yi")).toEqual({
      text: "▼ 18.21 亿元",
      direction: "down",
    });
  });

  it("returns null when either period is missing or prev is zero for percent", () => {
    expect(buildRiskV6DeltaChip(null, 100, "percent")).toBeNull();
    expect(buildRiskV6DeltaChip(100, null, "percent")).toBeNull();
    expect(buildRiskV6DeltaChip(100, 0, "percent")).toBeNull();
  });

  it("marks exact zero deltas as flat", () => {
    expect(buildRiskV6DeltaChip(5, 5, "absolute", 2)).toEqual({ text: "· 0.00", direction: "flat" });
  });
});

describe("buildRiskV6KpiCards", () => {
  it("builds the eight obsidian cards with governed values and 24-period series", () => {
    const cards = buildRiskV6KpiCards(tensorFixture(), historyFixture());
    expect(cards).toHaveLength(8);

    const regulatory = cards[0];
    expect(regulatory.label).toBe("监管 DV01");
    expect(regulatory.amount).toBe("10,694.94");
    expect(regulatory.unit).toBe("万元");
    expect(regulatory.alert).toBe(false);
    expect(regulatory.sparkline).not.toBeNull();
    expect(regulatory.delta?.direction).toBe("up");

    const portfolio = cards[1];
    expect(portfolio.amount).toBe("10,694.94");
    expect(portfolio.caption).toBe("同值属口径预期");

    const duration = cards[2];
    expect(duration.amount).toBe("3.78");
    expect(duration.delta?.text).toBe("▼ 0.01");

    const convexity = cards[3];
    expect(convexity.amount).toBe("30.90");

    const cs01 = cards[4];
    expect(cs01.amount).toBe("2,730.89");
    expect(cs01.unit).toBe("万元");

    const hhi = cards[5];
    expect(hhi.amount).toBe("4.84");
    expect(hhi.unit).toBe("%");
    expect(hhi.delta?.text.endsWith("pp")).toBe(true);

    const top5 = cards[6];
    expect(top5.amount).toBe("40.3");

    const gap = cards[7];
    expect(gap.label).toBe("30D 流动性缺口");
    expect(gap.amount).toBe("-63.14");
    expect(gap.unit).toBe("亿元");
    expect(gap.alert).toBe(true);
    expect(gap.caption).toBe("90D 缺口 -10.88 亿");
  });

  it("keeps cards readable when history is missing", () => {
    const cards = buildRiskV6KpiCards(tensorFixture(), undefined);
    expect(cards).toHaveLength(8);
    expect(cards[0].sparkline).toBeNull();
    expect(cards[0].delta).toBeNull();
    expect(cards[0].amount).toBe("10,694.94");
  });

  it("surfaces missing values explicitly instead of backfilling", () => {
    const tensor = { ...tensorFixture(), regulatory_dv01: null };
    const cards = buildRiskV6KpiCards(tensor, historyFixture());
    expect(cards[0].amount).toBe("-");
    expect(cards[0].valuePresent).toBe(false);
    expect(cards[0].caption).toBe("待接入");
  });

  it("returns no cards without a tensor payload", () => {
    expect(buildRiskV6KpiCards(undefined, historyFixture())).toEqual([]);
  });
});

describe("buildRiskV6Hero", () => {
  it("picks the peak KRD bucket and converts DV01 to 万元/亿元", () => {
    const hero = buildRiskV6Hero(tensorFixture());
    expect(hero.dv01Wan).toBe("10,694.94");
    expect(hero.dv01Yi).toBe("1.07");
    expect(hero.peakKrdBucket).toBe("10Y");
    expect(hero.peakKrdWan).toBe("2,753.92");
    expect(hero.duration).toBe("3.78");
    expect(hero.convexity).toBe("30.90");
    expect(hero.totalMarketValueYi).toBe("3,478.36");
    expect(hero.bondCount).toBe(1767);
  });

  it("returns nulls without a tensor", () => {
    expect(buildRiskV6Hero(undefined).dv01Wan).toBeNull();
  });
});

describe("buildRiskV6Briefs", () => {
  it("composes the three cross-section briefs from tensor fields", () => {
    const briefs = buildRiskV6Briefs(tensorFixture());
    expect(briefs).toHaveLength(3);
    expect(briefs[0].body).toBe("DV01 10,694.94 万元，修正久期 3.78，凸度 30.90。");
    expect(briefs[1].body).toBe("CS01 2,730.89 万元，前五大权重 40.3%，HHI 4.84%。");
    expect(briefs[2].body).toBe("30D 缺口 -63.14 亿元，90D 缺口 -10.88 亿元。");
  });
});

describe("buildRiskV6KrdBars", () => {
  it("marks the peak bucket hot and scales widths to the max", () => {
    const bars = buildRiskV6KrdBars(tensorFixture());
    expect(bars).toHaveLength(6);
    const hot = bars.find((bar) => bar.hot);
    expect(hot?.bucket).toBe("10Y");
    expect(hot?.widthPct).toBe(100);
    expect(hot?.wanText).toBe("2,753.92");
    expect(bars[0].bucket).toBe("1Y");
  });
});

describe("buildRiskV6YieldCurveChart", () => {
  function curvePayload(): YieldCurveTermStructurePayload {
    const point = (tenor: string, pct: number | null) => ({
      tenor,
      yield_pct: pct === null ? null : num(pct / 100, { unit: "pct", sign_aware: true }),
      delta_bp_prev: null,
    });
    const tenors = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"];
    const treasury = [1.12, 1.28, 1.45, 1.68, 1.85, 2.05, 2.2, 2.24];
    const cdb = [1.35, 1.5, 1.66, 1.9, 2.1, 2.35, 2.6, 2.79];
    const aaa = [1.5, 1.62, 1.75, 1.95, 2.05, 2.08, null, null];
    const curve = (curve_type: string, values: Array<number | null>) => ({
      curve_type,
      trade_date_requested: "2026-06-30",
      trade_date_resolved: "2026-06-30",
      points: tenors.map((tenor, index) => point(tenor, values[index] ?? null)),
      source_version: "sv_curve",
      rule_version: "rv_yield_curve_formal_materialize_v1",
      vendor_name: "vendor",
      vendor_version: "vv",
    });
    return {
      report_date: "2026-06-30",
      curves: [curve("treasury", treasury), curve("cdb", cdb), curve("aaa_credit", aaa)],
      warnings: [],
      computed_at: "2026-07-18T00:00:00Z",
    };
  }

  it("builds three smoothed series with ticks and endpoint labels", () => {
    const chart = buildRiskV6YieldCurveChart(curvePayload());
    expect(chart).not.toBeNull();
    expect(chart?.series.map((item) => item.label)).toEqual(["国债", "国开", "AAA 信用"]);
    expect(chart?.resolvedDate).toBe("2026-06-30");
    expect(chart?.ruleVersion).toBe("rv_yield_curve_formal_materialize_v1");

    const treasury = chart?.series[0];
    expect(treasury?.points).toHaveLength(8);
    expect(treasury?.linePath?.startsWith("M 36,")).toBe(true);
    expect(treasury?.areaPath).not.toBeNull();
    expect(treasury?.endLabel?.text).toBe("2.24");

    const cdb = chart?.series[1];
    expect(cdb?.areaPath).toBeNull();
    expect(cdb?.endLabel?.text).toBe("2.79");

    // AAA 30Y/20Y 为 null：不插值，端点标签落在 10Y。
    const aaa = chart?.series[2];
    expect(aaa?.points).toHaveLength(6);
    expect(aaa?.endLabel?.text).toBe("2.08");

    expect(chart?.yTicks[0].text).toBe("1.0");
    expect(chart?.yTicks[chart.yTicks.length - 1].text).toBe("3.0");
    expect(chart?.xLabels).toHaveLength(8);
  });

  it("returns null when no governed curve is available", () => {
    expect(buildRiskV6YieldCurveChart(undefined)).toBeNull();
    expect(
      buildRiskV6YieldCurveChart({ report_date: "2026-06-30", curves: [], warnings: [], computed_at: "" }),
    ).toBeNull();
  });
});

describe("buildRiskV6CashflowTrack", () => {
  it("scales bars to the largest leg and signs the gap chips", () => {
    const track = buildRiskV6CashflowTrack(tensorFixture());
    expect(track?.rows).toHaveLength(4);
    expect(track?.rows[0]).toMatchObject({ window: "30D", label: "资产流入", yiText: "62.01" });
    expect(track?.rows[3].widthPct).toBe(100);
    expect(track?.rows[1].widthPct).toBeCloseTo(79.24, 1);
    expect(track?.chips).toEqual([
      { key: "gap-30d", label: "30D 净缺口", text: "-63.14 亿", tone: "alert" },
      { key: "gap-90d", label: "90D 净缺口", text: "-10.88 亿", tone: "alert" },
      { key: "gap-ratio", label: "30D 缺口率", text: "-1.82%", tone: "dim" },
    ]);
  });

  it("returns null when every cashflow leg is missing", () => {
    const tensor = {
      ...tensorFixture(),
      asset_cashflow_30d: null,
      asset_cashflow_90d: null,
      liability_cashflow_30d: null,
      liability_cashflow_90d: null,
    } as unknown as RiskTensorPayload;
    expect(buildRiskV6CashflowTrack(tensor)).toBeNull();
  });
});

describe("buildRiskV6DetailTables", () => {
  function cashflowFixture(): CashflowProjectionPayload {
    return {
      report_date: "2026-06-30",
      duration_gap: num(3.12, { unit: "ratio", display: "+3.12" }),
      asset_duration: num(3.8, { unit: "ratio" }),
      liability_duration: num(0.68, { unit: "ratio" }),
      equity_duration: num(3.1, { unit: "ratio" }),
      rate_sensitivity_1bp: num(106949424.13, { unit: "dv01" }),
      reinvestment_risk_12m: num(0.2282, { unit: "pct", display: "22.82%" }),
      monthly_buckets: [],
      top_maturing_assets_12m: [],
      warnings: [],
      computed_at: "2026-07-18T00:00:00Z",
    };
  }

  it("lists field-level rows for both tables", () => {
    const [portfolio, credit] = buildRiskV6DetailTables(tensorFixture(), cashflowFixture());
    const portfolioByKey = new Map(portfolio.rows.map((row) => [row.key, row.value]));
    expect(portfolioByKey.get("total-market-value")).toBe("3,478.36 亿元");
    expect(portfolioByKey.get("bond-count")).toBe("1,767");
    expect(portfolioByKey.get("regulatory-dv01")).toBe("10,694.94 万元");
    expect(portfolioByKey.get("rate-risk-dv01")).toBe("10,686.87 万元");
    expect(portfolioByKey.get("rate-risk-mv")).toBe("3,017.18 亿元");
    expect(portfolioByKey.get("duration-excluded")).toBe("131 只 · 461.18 亿元");

    const creditByKey = new Map(credit.rows.map((row) => [row.key, row.value]));
    expect(creditByKey.get("cs01")).toBe("2,730.89 万元");
    expect(creditByKey.get("issuer-top5")).toBe("40.3%");
    expect(creditByKey.get("issuer-hhi")).toBe("4.84%");
    expect(creditByKey.get("duration-gap")).toBe("+3.12");
    expect(creditByKey.get("reinvestment-risk-12m")).toBe("22.82%");
  });

  it("marks cashflow-sourced rows as 待接入 when the cashflow leg failed", () => {
    const [, credit] = buildRiskV6DetailTables(tensorFixture(), undefined);
    const gapRow = credit.rows.find((row) => row.key === "duration-gap");
    expect(gapRow?.value).toBe("待接入");
    expect(gapRow?.tone).toBe("watch");
  });
});

describe("buildRiskV6LineageRows", () => {
  const meta: ResultMeta = {
    trace_id: "tr_9f65d8ba5e40",
    basis: "formal",
    result_kind: "risk.tensor",
    formal_use_allowed: true,
    source_version: "sv_risk_tensor__sv_a583ab603b92__sv_fa8f64e200b6",
    vendor_version: "vv_none",
    rule_version: "rv_risk_tensor_formal_materialize_v3",
    cache_version: "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v3",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    requested_report_date: "2026-06-30",
    resolved_report_date: "2026-06-30",
    as_of_date: "2026-06-30",
    date_basis: "formal_snapshot",
    fallback_date: null,
    generated_at: "2026-07-18T10:05:41Z",
  };

  it("emits the version chain from result_meta", () => {
    const rows = buildRiskV6LineageRows(meta);
    const byKey = new Map(rows.map((row) => [row.key, row.value]));
    expect(byKey.get("source")).toBe("sv_risk_tensor__sv_a583ab603b92__sv_fa8f64e200b6");
    expect(byKey.get("rule")).toBe("rv_risk_tensor_formal_materialize_v3");
    expect(byKey.get("cache")).toBe("cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v3");
    expect(byKey.get("trace")).toBe("tr_9f65d8ba5e40");
    expect(byKey.has("fallback")).toBe(false);
  });

  it("surfaces fallback lineage explicitly", () => {
    const rows = buildRiskV6LineageRows({ ...meta, fallback_mode: "latest_snapshot", fallback_date: "2026-06-27" });
    expect(rows.find((row) => row.key === "fallback")?.value).toBe("latest_snapshot · 2026-06-27");
  });

  it("returns nothing without meta", () => {
    expect(buildRiskV6LineageRows(undefined)).toEqual([]);
  });
});
