import { describe, expect, it } from "vitest";

import type {
  CampisiFourEffectsPayload,
  ChoiceMacroLatestPoint,
  ResultMeta,
  YieldCurveTermPointPayload,
  YieldCurveTermStructureCurvePayload,
  YieldCurveTermStructurePayload,
} from "../../../../api/contracts";
import { buildHomeMarketContextModel } from "./buildHomeMarketContextModel";

const campisiMeta: ResultMeta = {
  trace_id: "synthetic-home-coverage", basis: "formal", result_kind: "campisi",
  formal_use_allowed: true, source_version: "synthetic", vendor_version: "synthetic",
  rule_version: "synthetic", cache_version: "synthetic", quality_flag: "ok",
  vendor_status: "ok", fallback_mode: "none", scenario_flag: false,
  generated_at: "2026-08-31T00:00:00Z",
};

function formalBridgePayload(): CampisiFourEffectsPayload {
  return {
    report_date: "2026-08-31", period_start: "2026-07-31", period_end: "2026-08-31", num_days: 31,
    basis: "formal_report_pnl_bridge",
    totals: { income_return: 10, treasury_effect: 0, spread_effect: 0, selection_effect: 0, total_return: 10, market_value_start: 100 },
    by_asset_class: [], by_bond: [],
    formal_closure: {
      basis: "pnl.bridge.total_actual_pnl", report_date: "2026-08-31", status: "closed",
      campisi_total_return: 10, formal_actual_pnl: 10, residual_to_formal_pnl: 0, residual_ratio: 0,
      bridge_quality_flag: "ok", bridge_vendor_status: "ok", bridge_fallback_mode: "none", message: "合计闭合",
    },
    input_quality: {
      formal_bridge_coverage: { source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "ok", bridge_rows: 4, attributed_rows: 4 },
    },
    effect_availability: {
      bonds: 4,
      treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      roll_down_availability: { status: "ok", unavailable_rows: 0, applicable_rows: 2, reasons: [] },
      treasury_curve_availability: { status: "ok", unavailable_rows: 0, applicable_rows: 2, reasons: [] },
      credit_spread_availability: { status: "not_applicable", unavailable_rows: 0, applicable_rows: 0, reasons: ["not_credit_book"] },
    },
  };
}

function coverageModel(
  payload = formalBridgePayload(),
  meta = campisiMeta,
) {
  return buildHomeMarketContextModel({
    marketTape: [], marketPoints: null, macroNewsEvents: null, todayIsoDate: "2026-08-31",
    expectedReportDate: "2026-08-31", campisiFourEffects: payload, campisiResultMeta: meta,
    returnDecomposition: null, yieldCurveTermStructure: null, creditSpreadMigration: null,
    attribution: { maxDragLabel: "", maxContributionLabel: "" },
  }).attributionCoverage;
}

describe("formal bridge coverage disclosure", () => {
  it("uses backend accounting row counts even when the summary omits bond details", () => {
    const coverage = coverageModel();
    expect(coverage.state).toBe("complete");
    expect(coverage.label).toBe("正式桥归因覆盖");
    expect(coverage.positionLabel).toBe("会计记录行纳入 4/4 行");
    expect(coverage.summary).toContain("适用市场效应");
    expect(coverage.effectNotices.join(" ")).toContain("信用利差效应不适用");
    expect(coverage.effectNotices.join(" ")).not.toContain("本金变化");
    expect(coverage.detailPath).toContain("campisi_start_date=2026-07-31");
  });

  it("keeps upstream quality errors despite closed totals and allowed formal use", () => {
    const coverage = coverageModel(formalBridgePayload(), { ...campisiMeta, quality_flag: "error" });
    expect(coverage.state).toBe("error");
    expect(coverage.effectNotices.join(" ")).toContain("数据质量错误");
    expect(coverage.effectNotices.join(" ")).toContain("金额闭合不代表数据质量通过");
    expect(coverage.basisLabel).toContain("不可正式使用");
    expect(coverage.positionLabel).toBe("会计记录行纳入 4/4 行");
  });

  it("uses effect applicable rows independently from accounting inclusion counts", () => {
    const payload = formalBridgePayload();
    payload.effect_availability!.treasury_curve_availability = {
      status: "partial", unavailable_rows: 1, applicable_rows: 2, reasons: ["curve_unavailable"],
    };
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("partial");
    expect(coverage.positionLabel).toBe("会计记录行纳入 4/4 行");
    expect(coverage.effectNotices.join(" ")).toContain("1/2 个适用行");
    expect(coverage.effectNotices.join(" ")).toContain("国债曲线效应部分不可用");
    expect(coverage.effectNotices.join(" ")).not.toContain("1/4");
  });

  it("distinguishes partial accounting inclusion from market effect coverage", () => {
    const payload = formalBridgePayload();
    payload.input_quality!.formal_bridge_coverage = {
      source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "partial", bridge_rows: 4, attributed_rows: 2,
    };
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("partial");
    expect(coverage.positionLabel).toBe("会计记录行纳入 2/4 行");
    expect(coverage.summary).toContain("仅部分会计记录行");
    expect(coverage.excludedValueLabel).toBeNull();
  });

  it("keeps an empty bridge distinct from confirmed zero returns", () => {
    const payload = formalBridgePayload();
    payload.input_quality!.formal_bridge_coverage = {
      source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "unavailable", bridge_rows: 0, attributed_rows: 0,
      reason: "bridge_rows_empty",
    };
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("unavailable");
    expect(coverage.summary).toContain("无会计记录行");
    expect(coverage.summary).not.toContain("市场效应输入可用");
  });

  it.each([
    { bridge_rows: null, attributed_rows: 4, status: "unavailable" as const, expected: "unavailable" },
    { bridge_rows: 4, attributed_rows: 5, status: "ok" as const, expected: "unknown" },
    { bridge_rows: 4, attributed_rows: 5, status: "unavailable" as const, expected: "unavailable" },
    { bridge_rows: 4, attributed_rows: 0, status: "partial" as const, expected: "unknown" },
  ])("does not infer full accounting inclusion from inconsistent counts: %j", ({ expected, ...values }) => {
    const payload = formalBridgePayload();
    payload.input_quality!.formal_bridge_coverage = {
      source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", ...values,
    };
    expect(coverageModel(payload).state).toBe(expected);
  });

  it("keeps legacy formal coverage unknown and ignores model-only diagnostics", () => {
    const payload = formalBridgePayload();
    payload.input_quality = { included_maturity_unavailable: { positions: 1, market_value_start_abs: 100, model_residual: 5 } };
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("unknown");
    expect(coverage.positionLabel).toBeNull();
    expect(coverage.detailPath).toBeNull();
    expect(coverage.effectNotices.join(" ")).not.toContain("到期日");
  });

  it("requires preserved market diagnostics before calling formal coverage complete", () => {
    const payload = formalBridgePayload();
    delete payload.effect_availability!.roll_down_availability;
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("unknown");
    expect(coverage.positionLabel).toBe("会计记录行纳入 4/4 行");
    expect(coverage.effectNotices.join(" ")).toContain("市场效应覆盖诊断未提供");
  });

  it.each([
    { quality_flag: "warning" as const },
    { quality_flag: "stale" as const },
    { vendor_status: "vendor_unavailable" as const },
    { fallback_mode: "latest_snapshot" as const, fallback_date: "2026-08-30" },
    { formal_use_allowed: false },
  ])("does not let row inclusion override the source status: %j", (source) => {
    const coverage = coverageModel(formalBridgePayload(), { ...campisiMeta, ...source });
    expect(coverage.state).toBe("partial");
    expect(coverage.basisLabel).toContain("不可正式使用");
  });

  it("retains bridge quality errors even when outer metadata is clean", () => {
    const payload = formalBridgePayload();
    payload.formal_closure!.bridge_quality_flag = "error";
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("error");
    expect(coverage.effectNotices.join(" ")).toContain("数据质量错误");
  });

  it("requires closure and source metadata to confirm formal coverage", () => {
    const payload = formalBridgePayload();
    delete payload.formal_closure;
    expect(coverageModel(payload).state).toBe("unknown");
    const noMetadata = buildHomeMarketContextModel({
      marketTape: [], marketPoints: null, macroNewsEvents: null, todayIsoDate: "2026-08-31",
      expectedReportDate: "2026-08-31", campisiFourEffects: formalBridgePayload(), campisiFormalUseAllowed: true,
      returnDecomposition: null, yieldCurveTermStructure: null, creditSpreadMigration: null,
      attribution: { maxDragLabel: "", maxContributionLabel: "" },
    });
    expect(noMetadata.attributionCoverage.state).toBe("unknown");
  });

  it("does not publish counts or a detail link for a different report date", () => {
    const payload = formalBridgePayload();
    payload.report_date = "2026-08-30";
    payload.period_end = "2026-08-30";
    const coverage = coverageModel(payload);
    expect(coverage.state).toBe("date-mismatch");
    expect(coverage.positionLabel).toBeNull();
    expect(coverage.detailPath).toBeNull();
  });
});

function curve(
  curveType: string,
  resolvedDate: string | null,
  points: YieldCurveTermPointPayload[] = [],
): YieldCurveTermStructureCurvePayload {
  return {
    curve_type: curveType,
    trade_date_requested: "2026-04-10",
    trade_date_resolved: resolvedDate,
    points,
    source_version: "test",
    rule_version: "test",
    vendor_name: "test",
    vendor_version: "test",
  };
}

function mixedCurvePayload(): YieldCurveTermStructurePayload {
  return {
    report_date: "2026-04-10",
    curves: [
      curve("treasury", "2026-04-10"),
      curve("cdb", "2026-04-09"),
      curve("aaa_credit", null),
    ],
    warnings: [],
    computed_at: "2026-04-10T16:00:00Z",
  };
}

describe("buildHomeMarketContextModel yield curve dates", () => {
  it("keeps mixed dates in the curve block and excludes them from the global as-of date", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: mixedCurvePayload(),
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    const curveBlock = model.contextBlocks.find(
      (block) => block.id === "curve",
    );
    expect(curveBlock?.foot).toContain("2026-04-10");
    expect(curveBlock?.foot).toContain("2026-04-09");
    expect(model.curveTable.title).toBe("国债收益率");
    expect(model.asOfLabel).not.toContain("2026-04-10");
  });

  it("keeps the panel title stable when no curve is available", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    // 失败态与成功态同名，避免标题跳变；vendor 源名不进标题。
    expect(model.curveTable.title).toBe("国债收益率");
  });

  it("exposes governed key-tenor rows for the compact market table", () => {
    const payload: YieldCurveTermStructurePayload = {
      report_date: "2026-04-10",
      curves: [
        curve("cdb", "2026-04-10", [
          {
            tenor: "1Y",
            yield_pct: {
              raw: 0.016,
              unit: "pct",
              display: "1.60%",
              precision: 2,
              sign_aware: false,
            },
            delta_bp_prev: {
              raw: -1.2,
              unit: "bp",
              display: "-1.20",
              precision: 2,
              sign_aware: true,
            },
          },
          {
            tenor: "3Y",
            yield_pct: {
              raw: 0.0178,
              unit: "pct",
              display: "1.78%",
              precision: 2,
              sign_aware: false,
            },
            delta_bp_prev: {
              raw: 0,
              unit: "bp",
              display: "0.00",
              precision: 2,
              sign_aware: true,
            },
          },
          {
            tenor: "5Y",
            yield_pct: {
              raw: 0.0192,
              unit: "pct",
              display: "undefined",
              precision: 2,
              sign_aware: false,
            },
            delta_bp_prev: {
              raw: -1.5,
              unit: "bp",
              display: "",
              precision: 2,
              sign_aware: true,
            },
          },
        ]),
      ],
      warnings: [],
      computed_at: "2026-04-10T16:00:00Z",
    };
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: payload,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    expect(model.curveTable.title).toBe("国开债收益率");
    expect(model.curveTable.asOfLabel).toBe("2026-04-10");
    expect(model.curveTable.rows).toEqual([
      {
        tenor: "1Y",
        // 收益率水平列剥离后端 display 的「+」符号（水平值非变动），变动列保留符号。
        yieldLabel: "1.60%",
        deltaLabel: "-1.20",
        deltaTone: "down",
      },
      {
        tenor: "3Y",
        yieldLabel: "1.78%",
        deltaLabel: "0.00",
        deltaTone: "flat",
      },
      {
        tenor: "5Y",
        yieldLabel: "—",
        deltaLabel: "—",
        deltaTone: "muted",
      },
      {
        tenor: "10Y",
        yieldLabel: "—",
        deltaLabel: "—",
        deltaTone: "muted",
      },
    ]);
    expect(model.curveTable.emptyMessage).toBeNull();
  });

  it("strips the plus sign from yield levels but keeps it on deltas", () => {
    const payload: YieldCurveTermStructurePayload = {
      report_date: "2026-07-31",
      curves: [
        curve("treasury", "2026-06-30", [
          {
            tenor: "10Y",
            yield_pct: {
              raw: 0.0173,
              unit: "pct",
              display: "+1.73%",
              precision: 2,
              sign_aware: true,
            },
            delta_bp_prev: {
              raw: 0.8,
              unit: "bp",
              display: "+0.80",
              precision: 2,
              sign_aware: true,
            },
          },
        ]),
      ],
      warnings: [],
      computed_at: "2026-07-31T16:00:00Z",
    };
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-07-31",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: payload,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    const tenYear = model.curveTable.rows.find((row) => row.tenor === "10Y");
    expect(tenYear?.yieldLabel).toBe("1.73%");
    expect(tenYear?.deltaLabel).toBe("+0.80");
    expect(tenYear?.deltaTone).toBe("up");
  });

  it("preserves the full formal rate series independently from the market-temperature tape", () => {
    const marketPoint: ChoiceMacroLatestPoint = {
      series_id: "EMM00166502",
      series_name: "10年国开债",
      trade_date: "2026-07-17",
      value_numeric: 1.7875,
      unit: "%",
      latest_change: -0.0035,
      source_version: "sv_choice",
      vendor_version: "vv_choice",
      vendor_name: "Choice",
      refresh_tier: "stable",
      quality_flag: "ok",
      recent_points: [],
    };
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: [
        marketPoint,
        {
          ...marketPoint,
          series_id: "TEST.ISOLATED",
          refresh_tier: "isolated",
        },
      ],
      macroNewsEvents: null,
      todayIsoDate: "2026-07-31",
      campisiFourEffects: null,
      returnDecomposition: null,
      yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    expect(model.rateSeries).toHaveLength(1);
    expect(model.rateSeries[0]).toMatchObject({
      id: "EMM00166502",
      tradeDate: "2026-07-17",
      vendorName: "Choice",
    });
  });
});

describe("buildHomeMarketContextModel campisi bridge components", () => {
  it("limits partial model attribution to the source-covered holdings", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [], marketPoints: null, macroNewsEvents: null,
      todayIsoDate: "2026-08-31",
      campisiFourEffects: {
        report_date: "2026-08-31", period_start: "2026-08-01",
        period_end: "2026-08-31", num_days: 30,
        totals: {
          income_return: 20_000_000, treasury_effect: -3_000_000,
          spread_effect: 4_000_000, selection_effect: 9_000_000,
          total_return: 30_000_000, market_value_start: 100_000_000,
        },
        by_asset_class: [], by_bond: [],
        effect_availability: {
          bonds: 1854,
          position_change: {
            status: "partial", reason: "principal_change_without_cashflows",
            unavailable_bonds: 259, covered_bonds: 1595,
            unavailable_market_value_start: 50_000_000,
          },
          treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
          spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
          accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        },
      },
      returnDecomposition: null, yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: { maxDragLabel: "", maxContributionLabel: "" },
    });

    const pnl = model.contextBlocks.find((block) => block.id === "pnl");
    expect(pnl?.title).toContain("可归因持仓");
    expect(pnl?.detail).toContain("排除 259/1854 项持仓");
    expect(pnl?.detail).toContain("覆盖 1595 项持仓");
    expect(pnl?.foot).toContain("可归因持仓");
    expect(model.aiSummary[0]).toContain("排除 259/1854 项持仓");
  });

  it("does not publish all-excluded placeholder totals or a leading contribution", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [], marketPoints: null, macroNewsEvents: null,
      todayIsoDate: "2026-08-31",
      campisiFourEffects: {
        report_date: "2026-08-31", period_start: "2026-08-01",
        period_end: "2026-08-31", num_days: 30,
        totals: {
          income_return: 0, treasury_effect: 0, spread_effect: 0,
          selection_effect: 0, total_return: 0, market_value_start: 0,
        },
        by_asset_class: [], by_bond: [],
        effect_availability: {
          bonds: 2,
          position_change: {
            status: "unavailable", reason: "principal_change_without_cashflows",
            unavailable_bonds: 2, covered_bonds: 0,
            unavailable_market_value_start: 10_000_000,
          },
          treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
          spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
          accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        },
      },
      returnDecomposition: null, yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: { maxDragLabel: "", maxContributionLabel: "" },
    });

    const pnl = model.contextBlocks.find((block) => block.id === "pnl");
    expect(pnl?.title).toContain("无法归因");
    expect(pnl?.detail).toContain("排除 2/2 项持仓");
    expect(pnl?.foot).not.toContain("0.00");
    expect(model.aiSummary[0]).not.toContain("0.00");
  });

  it("includes realized trading and fx in contribution/drag candidates", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: {
        report_date: "2026-04-10",
        period_start: "2026-03-11",
        period_end: "2026-04-10",
        num_days: 30,
        totals: {
          income_return: 50_000_000,
          treasury_effect: 30_000_000,
          spread_effect: 30_000_000,
          realized_trading: 120_000_000,
          manual_adjustment: -80_000_000,
          fx_translation: 60_000_000,
          selection_effect: 40_000_000,
          total_return: 250_000_000,
          market_value_start: 10_000_000_000,
        },
        by_asset_class: [],
        by_bond: [],
      },
      returnDecomposition: null,
      yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    const pnl = model.contextBlocks.find((block) => block.id === "pnl");
    expect(pnl?.title).toContain("已实现交易");
    expect(pnl?.detail).toContain("手工调整");
    expect(pnl?.detail).toContain("汇兑");
    expect(pnl?.detail).toContain("分量");
  });

  it("keeps model-path four components when bridge detail fields are absent", () => {
    const model = buildHomeMarketContextModel({
      marketTape: [],
      marketPoints: null,
      macroNewsEvents: null,
      todayIsoDate: "2026-04-10",
      campisiFourEffects: {
        report_date: "2026-04-10",
        period_start: "2026-03-11",
        period_end: "2026-04-10",
        num_days: 30,
        totals: {
          income_return: 20,
          treasury_effect: -3,
          spread_effect: 4,
          selection_effect: 9,
          total_return: 30,
          market_value_start: 100,
        },
        by_asset_class: [],
        by_bond: [],
      },
      returnDecomposition: null,
      yieldCurveTermStructure: null,
      creditSpreadMigration: null,
      attribution: {
        maxDragLabel: "",
        maxContributionLabel: "",
      },
    });

    const pnl = model.contextBlocks.find((block) => block.id === "pnl");
    expect(pnl?.title).toContain("Carry/Income");
    expect(pnl?.detail).not.toContain("已实现交易");
    expect(pnl?.detail).not.toContain("汇兑");
  });
});
