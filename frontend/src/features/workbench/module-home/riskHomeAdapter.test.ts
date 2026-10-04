import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import type {
  ApiEnvelope,
  CashflowProjectionPayload,
  DV01RiskPayload,
  Numeric,
  ResultMeta,
  RiskTensorHistoryPayload,
  RiskTensorPayload,
  YieldCurveTermStructurePayload,
} from "../../../api/contracts";
import {
  buildRiskBondComparisonPlan,
  buildRiskBondDv01Summary,
  buildRiskSourceUseStatus,
  buildRiskV6Briefs,
  buildRiskV6CashflowTrack,
  buildRiskV6KpiCards,
  buildRiskV6DeltaChip,
  buildRiskV6DetailTables,
  buildRiskV6Hero,
  buildRiskV6KrdBars,
  buildRiskV6LineageRows,
  buildRiskV6Sparkline,
  buildRiskV6YieldCurveChart,
} from "./riskHomeAdapter";
import type { ModuleHomeStatus } from "./moduleHomeModel";

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

function numExact(raw: number, rawText: string, overrides?: Partial<Numeric>): Numeric {
  return {
    ...num(raw, overrides),
    raw_text: rawText,
  };
}

/** Artificial tensor: KRD sums to DV01; cashflow legs close to their gaps. No live readings. */
function tensorFixture(): RiskTensorPayload {
  return {
    report_date: "2026-06-30",
    portfolio_dv01: num(125678900.125, { unit: "dv01" }),
    regulatory_dv01: num(125678900.125, { unit: "dv01" }),
    krd_1y: num(8000000),
    krd_3y: num(24000000),
    krd_5y: num(19000000),
    krd_7y: num(10000000),
    krd_10y: num(34000000),
    krd_30y: num(30678900.125),
    cs01: num(45678900.25, { unit: "dv01" }),
    portfolio_convexity: num(28.34567891, { unit: "ratio", display: "28.35" }),
    portfolio_modified_duration: num(4.12345678, { unit: "ratio", display: "4.12" }),
    issuer_concentration_hhi: num(0.03765432, { unit: "ratio" }),
    issuer_top5_weight: num(0.35678912, { unit: "ratio" }),
    asset_cashflow_30d: num(5200000000),
    asset_cashflow_90d: num(11700000000),
    liability_cashflow_30d: num(9400000000),
    liability_cashflow_90d: num(13200000000),
    liquidity_gap_30d: num(-4200000000, { sign_aware: true }),
    liquidity_gap_90d: num(-1500000000, { sign_aware: true }),
    liquidity_gap_30d_ratio: num(-0.015, { unit: "ratio", sign_aware: true }),
    total_market_value: num(280000000000),
    rate_risk_market_value: num(240000000000),
    rate_risk_dv01: num(125000000, { unit: "dv01" }),
    rate_risk_modified_duration: num(4.12345678, { unit: "ratio" }),
    duration_excluded_market_value: num(40000000000),
    duration_excluded_count: 125,
    missing_maturity_market_value: num(0),
    missing_maturity_count: 0,
    floating_rate_proxy_market_value: num(0),
    floating_rate_proxy_count: 0,
    payment_frequency_fallback_market_value: num(0),
    payment_frequency_fallback_count: 0,
    bullet_value_date_fallback_market_value: num(0),
    bullet_value_date_fallback_count: 0,
    projection_quality_status: "available",
    bond_count: 1250,
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

  it("fails closed instead of drawing across a non-finite history gap", () => {
    const spark = buildRiskV6Sparkline([1, Number.NaN, 3]);
    expect(spark).toBeNull();
  });

  it("fails closed instead of drawing across a null history gap", () => {
    expect(buildRiskV6Sparkline([1, null, 3])).toBeNull();
  });
});

describe("buildRiskV6DeltaChip", () => {
  it("formats percent deltas with direction arrows", () => {
    expect(buildRiskV6DeltaChip(101, 100, "percent")).toEqual({ text: "▲ 1.0%", direction: "up" });
    expect(buildRiskV6DeltaChip(99, 100, "percent")).toEqual({ text: "▼ 1.0%", direction: "down" });
  });

  it("formats absolute deltas for duration/convexity", () => {
    expect(buildRiskV6DeltaChip(4.10, 4.12, "absolute", 2)).toEqual({ text: "▼ 0.02", direction: "down" });
  });

  it("formats ratio deltas in pp", () => {
    expect(buildRiskV6DeltaChip(0.4, 0.415, "pp", 1)).toEqual({ text: "▼ 1.5pp", direction: "down" });
    expect(buildRiskV6DeltaChip(0.0484, 0.0516, "pp", 2)).toEqual({ text: "▼ 0.32pp", direction: "down" });
  });

  it("formats yuan deltas in 亿元", () => {
    expect(buildRiskV6DeltaChip(-4200000000, -3000000000, "yi")).toEqual({
      text: "▼ 12.00 亿元",
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
    expect(regulatory.amount).toBe("12,567.89");
    expect(regulatory.unit).toBe("万元/bp");
    expect(regulatory.caption).toBe("面值基数线性读数");
    expect(regulatory.alert).toBe(false);
    expect(regulatory.sparkline).not.toBeNull();
    expect(regulatory.delta?.direction).toBe("up");

    const portfolio = cards[1];
    expect(portfolio.label).toBe("组合 DV01");
    expect(portfolio.amount).toBe("12,567.89");
    expect(portfolio.caption).toBe("全量面值基数 · 同值属范围预期");

    const duration = cards[2];
    expect(duration.amount).toBe("4.12");
    expect(duration.delta?.text).toBe("▼ 0.01");

    const convexity = cards[3];
    expect(convexity.amount).toBe("28.35");

    const cs01 = cards[4];
    expect(cs01.amount).toBe("4,567.89");
    expect(cs01.unit).toBe("万元/bp");
    expect(cs01.caption).toBe("信用债 DV01 代理 · 每 bp");

    const hhi = cards[5];
    expect(hhi.amount).toBe("0.03765432");
    expect(hhi.unit).toBeNull();
    expect(hhi.delta?.text.endsWith("pp")).toBe(false);

    const top5 = cards[6];
    expect(top5.amount).toBe("35.7");

    const gap = cards[7];
    expect(gap.label).toBe("30D 流动性缺口");
    expect(gap.amount).toBe("-42.00");
    expect(gap.unit).toBe("亿元");
    expect(gap.alert).toBe(true);
    expect(gap.caption).toBe("90D 缺口 -15.00 亿");
  });

  it("keeps cards readable when history is missing", () => {
    const cards = buildRiskV6KpiCards(tensorFixture(), undefined);
    expect(cards).toHaveLength(8);
    expect(cards[0].sparkline).toBeNull();
    expect(cards[0].delta).toBeNull();
    expect(cards[0].amount).toBe("12,567.89");
  });

  it("surfaces missing values explicitly instead of backfilling", () => {
    const tensor = { ...tensorFixture(), regulatory_dv01: null };
    const cards = buildRiskV6KpiCards(tensor, historyFixture());
    expect(cards[0].amount).toBe(EM_DASH);
    expect(cards[0].valuePresent).toBe(false);
    expect(cards[0].caption).toBe("待接入");
  });

  it("does not bridge a null observation in either the sparkline or period delta", () => {
    const history = historyFixture(3);
    history.points[1].portfolio_dv01 = null;
    const cards = buildRiskV6KpiCards(tensorFixture(), history);
    expect(cards[1].sparkline).toBeNull();
    expect(cards[1].delta).toBeNull();
  });

  it("returns no cards without a tensor payload", () => {
    expect(buildRiskV6KpiCards(undefined, historyFixture())).toEqual([]);
  });
});

describe("buildRiskV6Hero", () => {
  it("picks the peak KRD bucket and converts DV01 to 万元/亿元", () => {
    const hero = buildRiskV6Hero(tensorFixture());
    expect(hero.dv01Wan).toBe("12,567.89");
    expect(hero.dv01Yi).toBe("1.26");
    expect(hero.peakKrdBucket).toBe("10Y");
    expect(hero.peakKrdWan).toBe("3,400.00");
    expect(hero.duration).toBe("4.12");
    expect(hero.convexity).toBe("28.35");
    expect(hero.totalMarketValueYi).toBe("2,800.00");
    expect(hero.bondCount).toBe(1250);
  });

  it("returns nulls without a tensor", () => {
    expect(buildRiskV6Hero(undefined).dv01Wan).toBeNull();
  });

  it("prefers raw_text for the peak bucket while leaving chart-only KRD bars on raw values", () => {
    const tensor = {
      ...tensorFixture(),
      krd_7y: numExact(10_000_000_000_000_000, "10000000000000000.4"),
      krd_10y: numExact(10_000_000_000_000_000, "10000000000000000.5"),
    };

    const hero = buildRiskV6Hero(tensor);
    const bars = buildRiskV6KrdBars(tensor);

    expect(hero.peakKrdBucket).toBe("10Y");
    expect(bars.find((bar) => bar.hot)?.bucket).toBe("7Y");
  });
});

describe("buildRiskV6Briefs", () => {
  it("composes the three cross-section briefs from tensor fields", () => {
    const briefs = buildRiskV6Briefs(tensorFixture());
    expect(briefs).toHaveLength(3);
    expect(briefs[0].body).toBe("DV01 12,567.89 万元/bp，修正久期 4.12，凸度 28.35。");
    expect(briefs[1].body).toBe("CS01 4,567.89 万元/bp，前五大权重 35.7%，HHI 0.03765432。");
    expect(briefs[2].body).toBe("30D 缺口 -42.00 亿元，90D 缺口 -15.00 亿元。");
    expect(briefs[0].note).toContain("不表示按市价完整重估的损益");
    expect(briefs[1].note).toContain("信用债 DV01 代理");
    expect(briefs[2].note).toContain("30D / 90D 缺口直读风险张量");
  });

  it("uses raw_text on formal summary and table percent fields", () => {
    const tensorLow = {
      ...tensorFixture(),
      issuer_top5_weight: numExact(0.4, "0.4044", { unit: "ratio" }),
    };
    const tensorHigh = {
      ...tensorFixture(),
      issuer_top5_weight: numExact(0.4, "0.4046", { unit: "ratio" }),
    };

    const briefsLow = buildRiskV6Briefs(tensorLow);
    const briefsHigh = buildRiskV6Briefs(tensorHigh);
    const [, creditLow] = buildRiskV6DetailTables(tensorLow, undefined);
    const [, creditHigh] = buildRiskV6DetailTables(tensorHigh, undefined);
    const creditLowByKey = new Map(creditLow.rows.map((row) => [row.key, row.value]));
    const creditHighByKey = new Map(creditHigh.rows.map((row) => [row.key, row.value]));

    expect(briefsLow[1].body).toContain("40.4%");
    expect(briefsHigh[1].body).toContain("40.5%");
    expect(creditLowByKey.get("issuer-top5")).toBe("40.4%");
    expect(creditHighByKey.get("issuer-top5")).toBe("40.5%");
  });
});

describe("buildRiskV6KrdBars", () => {
  it("marks the peak bucket hot and scales widths to the max", () => {
    const bars = buildRiskV6KrdBars(tensorFixture());
    expect(bars).toHaveLength(6);
    const hot = bars.find((bar) => bar.hot);
    expect(hot?.bucket).toBe("10Y");
    expect(hot?.widthPct).toBe(100);
    expect(hot?.wanText).toBe("3,400.00");
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
  it("does not choose the first curve date when dates are mixed or missing", () => {
    const payload = curvePayload();
    payload.curves[0]!.trade_date_resolved = "2026-06-30";
    payload.curves[1]!.trade_date_resolved = "2026-06-29";
    payload.curves[2]!.trade_date_resolved = null;

    const chart = buildRiskV6YieldCurveChart(payload);

    expect(chart?.resolvedDate).toBeNull();
    expect(chart?.dateLabel).toContain("2026-06-30");
    expect(chart?.dateLabel).toContain("2026-06-29");
    expect(chart?.dateLabel).toContain("\u672a\u89e3\u6790");
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
    expect(track?.rows[0]).toMatchObject({ window: "30D", label: "资产流入", yiText: "52.00" });
    expect(track?.rows[3].widthPct).toBe(100);
    expect(track?.rows[1].widthPct).toBeCloseTo(71.21, 1);
    expect(track?.chips).toEqual([
      { key: "gap-30d", label: "30D 净缺口", text: "-42.00 亿", tone: "alert" },
      { key: "gap-90d", label: "90D 净缺口", text: "-15.00 亿", tone: "alert" },
      { key: "gap-ratio", label: "30D 缺口率", text: "-1.50%", tone: "dim" },
    ]);
  });

  it("honors raw_text at the alert boundary instead of raw-only sign flips", () => {
    const tensorNegative = {
      ...tensorFixture(),
      liquidity_gap_30d: numExact(0, "-0.0000000001", { sign_aware: true }),
    };
    const tensorPositive = {
      ...tensorFixture(),
      liquidity_gap_30d: numExact(0, "0.0000000001", { sign_aware: true }),
    };

    const cardsNegative = buildRiskV6KpiCards(tensorNegative, historyFixture());
    const cardsPositive = buildRiskV6KpiCards(tensorPositive, historyFixture());
    const trackNegative = buildRiskV6CashflowTrack(tensorNegative);
    const trackPositive = buildRiskV6CashflowTrack(tensorPositive);

    expect(cardsNegative[7].alert).toBe(true);
    expect(cardsPositive[7].alert).toBe(false);
    expect(trackNegative?.chips.find((chip) => chip.key === "gap-30d")?.tone).toBe("alert");
    expect(trackPositive?.chips.find((chip) => chip.key === "gap-30d")?.tone).toBe("dim");
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
      rate_sensitivity_1bp: num(125678900.13, { unit: "dv01" }),
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
    expect(portfolioByKey.get("total-market-value")).toBe("2,800.00 亿元");
    expect(portfolioByKey.get("bond-count")).toBe("1,250");
    expect(portfolioByKey.get("regulatory-dv01")).toBe("12,567.89 万元/bp");
    expect(portfolioByKey.get("rate-risk-dv01")).toBe("12,500.00 万元/bp");
    expect(portfolioByKey.get("rate-risk-mv")).toBe("2,400.00 亿元");
    expect(portfolioByKey.get("duration-excluded")).toBe("125 条 · 400.00 亿元");

    const creditByKey = new Map(credit.rows.map((row) => [row.key, row.value]));
    const creditLabelByKey = new Map(credit.rows.map((row) => [row.key, row.label]));
    expect(creditByKey.get("cs01")).toBe("4,567.89 万元/bp");
    expect(creditByKey.get("issuer-top5")).toBe("35.7%");
    expect(creditByKey.get("issuer-hhi")).toBe("0.03765432");
    expect(creditByKey.get("duration-gap")).toBe("+3.12");
    expect(creditByKey.get("reinvestment-risk-12m")).toBe("22.82%");
    expect(creditLabelByKey.get("cs01")).toBe("CS01（信用债 DV01 代理）");
    expect(creditLabelByKey.get("duration-gap")).toBe("久期缺口（分析口径）");
    expect(creditLabelByKey.get("reinvestment-risk-12m")).toBe("12M 再投资风险（分析口径）");
  });

  it("lists classified duration exclusions only when materialized disclosure is available", () => {
    const tensor = {
      ...tensorFixture(),
      maturity_breakdown_status: "available" as const,
      fund_no_maturity_count: 123,
      fund_no_maturity_market_value: num(38_000_000_000),
      unknown_maturity_count: 0,
      unknown_maturity_market_value: num(0),
      matured_outstanding_count: 2,
      matured_outstanding_market_value: num(2_000_000_000),
      nonpositive_duration_count: 0,
      nonpositive_duration_market_value: num(0),
    };
    const [classified] = buildRiskV6DetailTables(tensor, undefined);
    const byKey = new Map(classified.rows.map((row) => [row.key, row.value]));
    expect(byKey.get("fund-no-maturity")).toBe("123 条 · 380.00 亿元");
    expect(byKey.get("unknown-maturity")).toBe("0 条 · 0.00 亿元");
    expect(byKey.get("matured-outstanding")).toBe("2 条 · 20.00 亿元");

    const [legacy] = buildRiskV6DetailTables({ ...tensor, maturity_breakdown_status: "unavailable_legacy" }, undefined);
    expect(legacy.rows.some((row) => row.key === "fund-no-maturity")).toBe(false);
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
    rule_version: "rv_risk_tensor_formal_materialize_v7",
    cache_version: "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v7",
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
    expect(byKey.get("rule")).toBe("rv_risk_tensor_formal_materialize_v7");
    expect(byKey.get("cache")).toBe("cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v7");
    expect(byKey.get("trace")).toBe("tr_9f65d8ba5e40");
    expect(byKey.get("basis")).toBe("formal");
    expect(byKey.get("formal-use")).toBe("true");
    expect(byKey.has("fallback")).toBe(false);
  });

  it("prefixes auxiliary lineage and exposes a non-formal cashflow gate", () => {
    const rows = buildRiskV6LineageRows(
      { ...meta, basis: "analytical", formal_use_allowed: false },
      "CASHFLOW",
    );
    const byKey = new Map(rows.map((row) => [row.key, row.value]));
    expect(byKey.get("cashflow-basis")).toBe("analytical");
    expect(byKey.get("cashflow-formal-use")).toBe("false");
  });

  it("surfaces fallback lineage explicitly", () => {
    const rows = buildRiskV6LineageRows({ ...meta, fallback_mode: "latest_snapshot", fallback_date: "2026-06-27" });
    expect(rows.find((row) => row.key === "fallback")?.value).toBe("latest_snapshot · 2026-06-27");
  });

  it("returns nothing without meta", () => {
    expect(buildRiskV6LineageRows(undefined)).toEqual([]);
  });
});

describe("buildRiskSourceUseStatus", () => {
  const status: ModuleHomeStatus = {
    key: "tensor",
    label: "风险张量",
    value: "已返回",
    detail: "风险张量已返回。",
    tone: "ok",
  };
  const formalMeta: ResultMeta = {
    trace_id: "tr_risk_status",
    basis: "formal",
    result_kind: "risk.tensor",
    formal_use_allowed: true,
    source_version: "sv_risk",
    vendor_version: "vv_none",
    rule_version: "rv_risk",
    cache_version: "cv_risk",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-30T00:00:00Z",
  };

  it("keeps a formal source formal when quality warning blocks formal decision use", () => {
    const result = buildRiskSourceUseStatus(status, { ...formalMeta, quality_flag: "warning" });

    expect(result.value).toBe("正式来源 · 质量待复核");
    expect(result.tone).toBe("watch");
    expect(result.detail).toContain("来源口径：正式来源（basis=formal）");
    expect(result.detail).toContain("质量：warning");
    expect(result.detail).toContain("正式决策门禁未通过（quality_flag=warning）");
  });

  it("labels cashflow-style analytical results as review-only without upgrading their eligibility", () => {
    const result = buildRiskSourceUseStatus(status, {
      ...formalMeta,
      basis: "analytical",
      formal_use_allowed: false,
    });

    expect(result.value).toBe("分析口径 · 仅供复核");
    expect(result.tone).toBe("watch");
    expect(result.detail).toContain("basis=analytical");
    expect(result.detail).toContain("formal_use_allowed=false");
  });
});

describe("buildRiskBondComparisonPlan", () => {
  it("plans exact month-end comparisons and six ascending trend slots", () => {
    const available = [
      "2026-06-30",
      "2026-05-31",
      "2026-04-30",
      "2026-03-31",
      "2026-02-28",
      "2026-01-31",
      "2025-06-30",
    ];
    const plan = buildRiskBondComparisonPlan("2026-06-30", available);

    expect(plan.enabled).toBe(true);
    expect(plan.momDate).toBe("2026-05-31");
    expect(plan.yoyDate).toBe("2025-06-30");
    expect(plan.trendDates.map((slot) => slot.reportDate)).toEqual([
      "2026-01-31",
      "2026-02-28",
      "2026-03-31",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ]);
    expect(plan.requestDates).toEqual([
      "2025-06-30",
      "2026-01-31",
      "2026-02-28",
      "2026-03-31",
      "2026-04-30",
      "2026-05-31",
    ]);
    expect(plan.requestDates).not.toContain("2026-06-30");
  });

  it("disables comparison unless current is an available exact month-end", () => {
    expect(
      buildRiskBondComparisonPlan("2026-06-29", ["2026-06-29"]).enabled,
    ).toBe(false);
    expect(
      buildRiskBondComparisonPlan("2026-06-30", ["2026-06-29"]).enabled,
    ).toBe(false);
  });

  it("retains exact missing dates without substituting nearby snapshots", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
      "2026-05-30",
      "2025-06-29",
    ]);

    expect(plan.momDate).toBe("2026-05-31");
    expect(plan.yoyDate).toBe("2025-06-30");
    expect(plan.momAvailable).toBe(false);
    expect(plan.yoyAvailable).toBe(false);
    expect(plan.requestDates).not.toContain("2026-05-30");
    expect(plan.requestDates).not.toContain("2025-06-29");
    expect(plan.missingDates).toEqual(
      expect.arrayContaining(["2026-05-31", "2025-06-30"]),
    );
    expect(plan.trendDates.find((slot) => slot.reportDate === "2026-05-31"))
      .toMatchObject({ available: false });
  });

  it("uses the exact leap-year February month-end", () => {
    const plan = buildRiskBondComparisonPlan("2024-03-31", [
      "2024-03-31",
      "2024-02-29",
      "2023-03-31",
    ]);

    expect(plan.enabled).toBe(true);
    expect(plan.momDate).toBe("2024-02-29");
    expect(plan.yoyDate).toBe("2023-03-31");
    expect(plan.requestDates).toContain("2024-02-29");

    const leapDayPlan = buildRiskBondComparisonPlan("2024-02-29", [
      "2024-02-29",
      "2024-01-31",
      "2023-02-28",
    ]);
    expect(leapDayPlan.momDate).toBe("2024-01-31");
    expect(leapDayPlan.yoyDate).toBe("2023-02-28");
  });
});

describe("buildRiskBondDv01Summary", () => {
  function bondEnvelope(
    accountingClass: "OCI" | "TPL",
    overrides: {
      payload?: Partial<DV01RiskPayload>;
      meta?: Partial<ResultMeta>;
    } = {},
  ): ApiEnvelope<DV01RiskPayload> {
    const payload: DV01RiskPayload = {
      report_date: "2026-06-30",
      accounting_class: accountingClass,
      dv01_basis: "face_value_modified_duration",
      scenario_pnl_basis: "face_value_dv01_linear",
      total_face_value: num(1_250_000_000, { unit: "yuan" }),
      total_market_value: num(1_200_000_000, { unit: "yuan" }),
      face_weighted_modified_duration: num(3.45, {
        unit: "ratio",
        display: "3.45",
      }),
      total_dv01: num(125_000, { unit: "dv01" }),
      position_count: 12,
      shock_scenarios: [],
      tenor_buckets: [],
      top_bonds: [],
      top_issuers: [],
      warnings: [],
      computed_at: "2026-07-19T00:00:00Z",
      ...overrides.payload,
    };
    return {
      result_meta: {
        trace_id: "tr_bond_risk_home",
        basis: "formal",
        result_kind: "bond_analytics.dv01_risk",
        formal_use_allowed: true,
        source_version: "sv_bond_analytics",
        vendor_version: "vv_none",
        rule_version: "rv_bond_analytics",
        cache_version: "cv_bond_analytics",
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        generated_at: "2026-07-19T00:00:00Z",
        ...overrides.meta,
      },
      result: payload,
    };
  }

  function historyObservation(
    reportDate: string,
    accountingClass: "OCI" | "TPL",
    overrides: {
      payload?: Partial<DV01RiskPayload>;
      meta?: Partial<ResultMeta>;
      error?: unknown;
    } = {},
  ) {
    return {
      reportDate,
      envelope: bondEnvelope(accountingClass, {
        payload: { report_date: reportDate, ...overrides.payload },
        meta: {
          resolved_report_date: reportDate,
          ...overrides.meta,
        },
      }),
      error: overrides.error,
    };
  }

  it("formats governed payload fields without recalculating DV01 or duration", () => {
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
    });

    expect(summary).toMatchObject({
      key: "bond-oci",
      title: "OCI 债券（系统正式口径）",
      state: "review",
      statusLabel: "待复核",
      reportDate: "2026-06-30",
    });
    expect(summary.metrics).toEqual([
      {
        key: "total-face-value",
        label: "总面值（DV01 基数）",
        value: "12.50",
        unit: "亿元",
      },
      {
        key: "total-market-value",
        label: "公允价值（不含应计）",
        value: "12.00",
        unit: "亿元",
      },
      {
        key: "modified-duration",
        label: "面值加权修正久期",
        value: "3.45",
        unit: "年",
      },
      {
        key: "total-dv01",
        label: "正式 DV01（面值基数）",
        value: "12.50",
        unit: "万元/bp",
      },
      { key: "position-count", label: "持仓数", value: "12", unit: "只" },
    ]);
    expect(summary.notices.join(" ")).toContain("不按手工同名列直接比较");
  });

  it("builds signed MoM changes for all five metric display rules", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
      "2026-05-31",
      "2025-06-30",
    ]);
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history: [
        historyObservation("2026-05-31", "OCI", {
          payload: {
            total_face_value: num(1_000_000_000, { unit: "yuan" }),
            total_market_value: num(1_300_000_000, { unit: "yuan" }),
            face_weighted_modified_duration: num(3.25, { unit: "ratio" }),
            total_dv01: num(100_000, { unit: "dv01" }),
            position_count: 10,
          },
        }),
        historyObservation("2025-06-30", "OCI"),
      ],
    });

    expect(summary.comparisons["total-face-value"].mom).toMatchObject({
      state: "review",
      absoluteText: "+2.50 亿元",
      percentText: "+25.00%",
      basisDate: "2026-05-31",
    });
    expect(summary.comparisons["total-market-value"].mom).toMatchObject({
      absoluteText: "-1.00 亿元",
      percentText: "-7.69%",
    });
    expect(summary.comparisons["modified-duration"].mom).toMatchObject({
      absoluteText: "+0.20 年",
      percentText: "—",
    });
    expect(summary.comparisons["total-dv01"].mom).toMatchObject({
      absoluteText: "+2.50 万元/bp",
      percentText: "+25.00%",
    });
    expect(summary.comparisons["position-count"].mom).toMatchObject({
      absoluteText: "+2 只",
      percentText: "+20.00%",
    });
  });

  it("shows only absolute changes when the comparison denominator is zero", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
      "2026-05-31",
    ]);
    const zeroBaseline = historyObservation("2026-05-31", "OCI", {
      payload: {
        total_face_value: num(0, { unit: "yuan" }),
        total_market_value: num(0, { unit: "yuan" }),
        face_weighted_modified_duration: num(0, { unit: "ratio" }),
        total_dv01: num(0, { unit: "dv01" }),
        position_count: 0,
      },
    });
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history: [zeroBaseline],
    });

    expect(summary.comparisons["total-face-value"].mom).toMatchObject({
      absoluteText: "+12.50 亿元",
      percentText: "—",
    });
    expect(summary.comparisons["total-market-value"].mom.percentText).toBe("—");
    expect(summary.comparisons["total-dv01"].mom.percentText).toBe("—");
    expect(summary.comparisons["position-count"].mom).toMatchObject({
      absoluteText: "+12 只",
      percentText: "—",
    });
  });

  it("treats zero positions as explicit empty data and hides zero metrics", () => {
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI", {
        payload: {
          total_face_value: num(0, { unit: "yuan" }),
          total_market_value: num(0, { unit: "yuan" }),
          face_weighted_modified_duration: num(0, { unit: "ratio" }),
          total_dv01: num(0, { unit: "dv01" }),
          position_count: 0,
        },
      }),
    });

    expect(summary.state).toBe("empty");
    expect(summary.statusLabel).toBe("暂无数据");
    expect(summary.metrics).toEqual([]);
    expect(summary.notices.join(" ")).toContain("不将空载荷中的零值");
  });

  it("blocks non-formal envelopes and error-quality payloads", () => {
    const nonFormal = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI", {
        meta: { basis: "analytical", formal_use_allowed: false },
      }),
    });
    const badQuality = buildRiskBondDv01Summary({
      accountingClass: "TPL",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("TPL", { meta: { quality_flag: "error" } }),
    });

    expect(nonFormal.state).toBe("blocked");
    expect(nonFormal.metrics).toEqual([]);
    expect(nonFormal.notices.join(" ")).toContain("formal_use_allowed");
    expect(badQuality.state).toBe("blocked");
    expect(badQuality.notices.join(" ")).toContain("质量标记为 error");
  });

  it("blocks undeclared report-date and accounting-class mismatches", () => {
    const wrongDate = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI", {
        payload: { report_date: "2026-06-29" },
      }),
    });
    const wrongClass = buildRiskBondDv01Summary({
      accountingClass: "TPL",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
    });

    expect(wrongDate.state).toBe("blocked");
    expect(wrongDate.notices.join(" ")).toContain("报告日");
    expect(wrongClass.state).toBe("blocked");
    expect(wrongClass.notices.join(" ")).toContain("请求分类 TPL 不一致");
  });

  it("keeps declared fallback, stale quality, and warnings visible as review state", () => {
    const summary = buildRiskBondDv01Summary({
      accountingClass: "TPL",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("TPL", {
        payload: {
          report_date: "2026-06-29",
          warnings: ["久期覆盖存在缺口"],
        },
        meta: {
          quality_flag: "stale",
          fallback_mode: "latest_snapshot",
          fallback_date: "2026-06-29",
        },
      }),
    });

    expect(summary.state).toBe("review");
    expect(summary.reportDate).toBe("2026-06-29");
    expect(summary.metrics).toHaveLength(5);
    expect(summary.notices.join(" ")).toContain("stale");
    expect(summary.notices.join(" ")).toContain("回退快照（2026-06-29）");
    expect(summary.notices.join(" ")).toContain("警告：久期覆盖存在缺口");
  });

  it("keeps current fallback values but disables exact-month derived evidence", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
      "2026-05-31",
      "2025-06-30",
    ]);
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI", {
        payload: {
          report_date: "2026-06-29",
          warnings: ["当前回退快照警告"],
        },
        meta: {
          quality_flag: "stale",
          fallback_mode: "latest_snapshot",
          fallback_date: "2026-06-29",
          resolved_report_date: "2026-06-29",
        },
      }),
      comparisonPlan: plan,
      history: [
        historyObservation("2026-05-31", "OCI"),
        historyObservation("2025-06-30", "OCI"),
      ],
    });

    expect(summary.state).toBe("review");
    expect(summary.metrics).toHaveLength(5);
    expect(summary.reportDate).toBe("2026-06-29");
    expect(summary.notices.join(" ")).toContain("当前回退快照警告");
    Object.values(summary.comparisons).forEach((comparison) => {
      expect(comparison.mom.state).toBe("unavailable");
      expect(comparison.yoy.state).toBe("unavailable");
    });
    expect(summary.trend).toBeNull();
    expect(summary.comparisonBasisText).toContain(
      "当前快照为回退或日期与请求月末不一致",
    );
  });

  it("excludes even exact-date fallback history from strict comparisons", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
      "2026-05-31",
    ]);
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history: [
        historyObservation("2026-05-31", "OCI", {
          meta: {
            fallback_mode: "latest_snapshot",
            fallback_date: "2026-05-31",
          },
        }),
      ],
    });

    expect(summary.comparisons["total-dv01"].mom.state).toBe("unavailable");
    expect(summary.notices.join(" ")).toContain(
      "使用回退快照（2026-05-31）",
    );
    expect(summary.notices.join(" ")).toContain("该点已排除");
  });

  it("keeps one accounting-class failure independent from the other summary", () => {
    const oci = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      error: new Error("OCI unavailable"),
    });
    const tpl = buildRiskBondDv01Summary({
      accountingClass: "TPL",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("TPL"),
    });

    expect(oci.state).toBe("error");
    expect(oci.notices.join(" ")).toContain("OCI unavailable");
    expect(tpl.state).toBe("review");
    expect(tpl.metrics).toHaveLength(5);
    expect(tpl.notices.join(" ")).toContain("不可用本卡替代 630 小计");
  });

  it("sorts six complete DV01 month-end points before building the trend", () => {
    const dates = [
      "2026-01-31",
      "2026-02-28",
      "2026-03-31",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ];
    const plan = buildRiskBondComparisonPlan("2026-06-30", dates);
    const history = [
      ["2026-04-30", 40_000],
      ["2026-01-31", 10_000],
      ["2026-05-31", 50_000],
      ["2026-02-28", 20_000],
      ["2026-03-31", 30_000],
    ].map(([date, dv01]) =>
      historyObservation(String(date), "OCI", {
        payload: { total_dv01: num(Number(dv01), { unit: "dv01" }) },
      }),
    );
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history,
    });

    expect(summary.trend).toMatchObject({
      state: "review",
      dates,
      values: [1, 2, 3, 4, 5, 12.5],
      unit: "万元/bp",
    });
    expect(summary.trend?.linePaths).toHaveLength(1);
    expect(summary.trend?.points).toHaveLength(6);
    expect(summary.trend?.sparkline).not.toBeNull();
  });

  it("keeps valid points and splits line segments around a middle gap", () => {
    const dates = [
      "2026-01-31",
      "2026-02-28",
      "2026-03-31",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ];
    const plan = buildRiskBondComparisonPlan("2026-06-30", dates);
    const history = [
      ["2026-01-31", 10_000],
      ["2026-02-28", 20_000],
      ["2026-04-30", 40_000],
      ["2026-05-31", 50_000],
    ].map(([date, dv01]) =>
      historyObservation(String(date), "OCI", {
        payload: { total_dv01: num(Number(dv01), { unit: "dv01" }) },
      }),
    );
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history,
    });

    expect(summary.trend?.state).toBe("review");
    expect(summary.trend?.values).toEqual([1, 2, null, 4, 5, 12.5]);
    expect(summary.trend?.sparkline).toBeNull();
    expect(summary.trend?.linePaths).toHaveLength(2);
    expect(summary.trend?.points.map((point) => point.reportDate)).toEqual([
      "2026-01-31",
      "2026-02-28",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ]);
    expect(summary.trend?.points.map((point) => point.x)).toEqual([
      3,
      21,
      57,
      75,
      93,
    ]);
  });

  it("does not draw a trend with fewer than six points or across a gap", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
    ]);
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history: [],
    });

    expect(summary.trend?.values).toEqual([
      null,
      null,
      null,
      null,
      null,
      12.5,
    ]);
    expect(summary.trend?.state).toBe("unavailable");
    expect(summary.trend?.sparkline).toBeNull();
    expect(summary.trend?.points).toHaveLength(1);
    expect(summary.trend?.linePaths).toEqual([]);
    expect(summary.trend?.notices.join(" ")).toContain("不跨缺口连线");
  });

  it("excludes blocked, wrong-date, wrong-class, invalid-count, and null history points", () => {
    const dates = [
      "2026-01-31",
      "2026-02-28",
      "2026-03-31",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ];
    const plan = buildRiskBondComparisonPlan("2026-06-30", dates);
    const nullDv01: Numeric = {
      raw: null,
      unit: "dv01",
      display: "—",
      precision: 2,
      sign_aware: false,
    };
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history: [
        historyObservation("2026-01-31", "OCI", {
          meta: { basis: "analytical", formal_use_allowed: false },
        }),
        historyObservation("2026-02-28", "OCI", {
          payload: { report_date: "2026-02-27" },
          meta: {
            fallback_mode: "latest_snapshot",
            fallback_date: "2026-02-27",
            resolved_report_date: "2026-02-27",
          },
        }),
        historyObservation("2026-03-31", "TPL"),
        historyObservation("2026-04-30", "OCI", {
          payload: { position_count: -1 },
        }),
        historyObservation("2026-05-31", "OCI", {
          payload: { total_dv01: nullDv01 },
        }),
      ],
    });

    expect(summary.trend?.values).toEqual([
      null,
      null,
      null,
      null,
      null,
      12.5,
    ]);
    expect(summary.trend?.sparkline).toBeNull();
    expect(summary.comparisons["total-dv01"].mom.state).toBe("unavailable");
    expect(summary.notices.join(" ")).toContain("该点已排除");
  });

  it("marks warning history as review and aggregates repeated notices", () => {
    const dates = [
      "2026-01-31",
      "2026-02-28",
      "2026-03-31",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ];
    const plan = buildRiskBondComparisonPlan("2026-06-30", dates);
    const history = dates.slice(0, 5).map((date, index) =>
      historyObservation(date, "OCI", {
        payload: {
          total_dv01: num((index + 1) * 10_000, { unit: "dv01" }),
          warnings: ["USD 口径待复核"],
        },
        meta: index === 4 ? { quality_flag: "stale" } : {},
      }),
    );
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI", {
        payload: { warnings: ["当前报告警告"] },
      }),
      comparisonPlan: plan,
      history,
    });

    expect(summary.comparisons["total-dv01"].mom.state).toBe("review");
    expect(summary.trend?.state).toBe("review");
    expect(summary.trend?.sparkline).not.toBeNull();
    expect(summary.notices).toContain("警告：当前报告警告");
    expect(
      summary.notices.filter((notice) => notice.includes("USD 口径待复核")),
    ).toEqual([
      "5 个历史月末均有同类提示：警告：USD 口径待复核，比较待复核。",
    ]);
  });

  it("keeps OCI and TPL comparison histories independent", () => {
    const plan = buildRiskBondComparisonPlan("2026-06-30", [
      "2026-06-30",
      "2026-05-31",
    ]);
    const ociHistory = [historyObservation("2026-05-31", "OCI")];
    const oci = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      comparisonPlan: plan,
      history: ociHistory,
    });
    const tpl = buildRiskBondDv01Summary({
      accountingClass: "TPL",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("TPL"),
      comparisonPlan: plan,
      history: ociHistory,
    });

    expect(oci.comparisons["total-dv01"].mom.state).toBe("review");
    expect(tpl.comparisons["total-dv01"].mom.state).toBe("unavailable");
    expect(tpl.state).toBe("review");
    expect(tpl.metrics).toHaveLength(5);
  });

  it("keeps cached governed values visible when the latest refresh fails", () => {
    const summary = buildRiskBondDv01Summary({
      accountingClass: "OCI",
      reportDate: "2026-06-30",
      envelope: bondEnvelope("OCI"),
      error: new Error("temporary refresh failure"),
    });

    expect(summary.state).toBe("review");
    expect(summary.statusLabel).toBe("待复核");
    expect(summary.metrics).toHaveLength(5);
    expect(summary.notices.join(" ")).toContain("最新刷新失败");
    expect(summary.notices.join(" ")).toContain("当前展示上次成功结果");
  });
});
