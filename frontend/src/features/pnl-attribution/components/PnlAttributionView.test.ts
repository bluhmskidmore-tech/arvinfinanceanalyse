import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import type {
  AdvancedAttributionSummary,
  Numeric,
  PnlCompositionPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import {
  buildAttributionBridge,
  buildVolumeRateBridgeSummary,
  formatGeneratedAtDisplay,
  formatMetaDateLabel,
  formatYi,
  formatYiNumeric,
  numericRaw,
  resolveDualReportDates,
  summarizePnlAttributionError,
  VOLUME_RATE_CLOSURE_DISCLOSURE,
  VOLUME_RATE_CLOSURE_TOLERANCE_YUAN,
} from "./pnlAttributionViewModel";

const pnlAttributionViewSourcePath = resolve(
  process.cwd(),
  "src/features/pnl-attribution/components/PnlAttributionView.tsx",
);
const attributionWaterfallSourcePath = resolve(
  process.cwd(),
  "src/features/pnl-attribution/components/AttributionWaterfallChart.tsx",
);

function numeric(overrides: Partial<Numeric>): Numeric {
  return {
    raw: overrides.raw ?? null,
    unit: overrides.unit ?? "yuan",
    display: overrides.display ?? "—",
    precision: overrides.precision ?? 2,
    sign_aware: overrides.sign_aware ?? true,
  };
}

describe("PnlAttributionView helpers", () => {
  it("keeps the main view visual shell class-based and tokenized", () => {
    const source = readFileSync(pnlAttributionViewSourcePath, "utf8");
    const inlineStyleMarker = ["style", "="].join("");
    const privateShadowPattern = new RegExp(
      [
        ["box", "Shadow"].join(""),
        ["box", "-", "shadow"].join(""),
        ["rgba", "\\("].join(""),
      ].join("|"),
    );

    expect(source).not.toContain(inlineStyleMarker);
    expect(source).not.toMatch(/#[0-9a-fA-F]{3,8}/);
    expect(source).not.toMatch(privateShadowPattern);
  });

  it("reads raw numeric values without inventing zeros", () => {
    expect(numericRaw(undefined)).toBeUndefined();
    expect(numericRaw(null)).toBeUndefined();
    expect(numericRaw(numeric({ raw: 125000000 }))).toBe(125000000);
    expect(numericRaw(numeric({ raw: 0, display: "+0.00 亿" }))).toBe(0);
    expect(numericRaw(numeric({ raw: null, display: "—" }))).toBeUndefined();
    expect(numericRaw(numeric({ raw: undefined, display: "1.25 亿" }))).toBeUndefined();
  });

  it("formats yi values with explicit sign and missing fallback", () => {
    expect(formatYi(250000000)).toBe("+2.50 亿");
    expect(formatYi(-50000000)).toBe("-0.50 亿");
    expect(formatYi(null)).toBe("—");
  });

  it("prefers governed Numeric.display before recomputing from raw", () => {
    expect(
      formatYiNumeric(
        numeric({
          raw: 125000000,
          display: "+1.30 亿",
        }),
      ),
    ).toBe("+1.30 亿");

    expect(formatYiNumeric(numeric({ raw: 0, display: "+0.00 亿" }))).toBe("+0.00 亿");
    expect(formatYiNumeric(numeric({ raw: null, display: "—" }))).toBe("—");
    expect(formatYiNumeric(numeric({ raw: 125000000, display: "   " }))).toBe("+1.25 亿");
    expect(formatYiNumeric(numeric({ raw: 125000000, display: "  +1.30 亿  " }))).toBe("+1.30 亿");
  });

  it("builds a bridge summary that surfaces cross effect and unexplained residual", () => {
    const summary = buildVolumeRateBridgeSummary({
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric({ raw: 851_454_959.25 }),
      total_previous_pnl: numeric({ raw: 785_715_634.31 }),
      total_pnl_change: numeric({ raw: 65_739_324.94 }),
      total_volume_effect: numeric({ raw: 11_514_483.36 }),
      total_rate_effect: numeric({ raw: 28_641_449.42 }),
      total_interaction_effect: numeric({ raw: 22_637_086.67 }),
      total_recon_error: numeric({ raw: 2_946_305.49 }),
      has_previous_data: true,
      items: [],
    });

    expect(summary).toMatchObject({
      explainedEffect: 62_793_019.45,
      status: "residual",
      statusLabel: "存在未解释差额",
    });
    expect(summary?.unexplainedEffect).toBeCloseTo(2_946_305.49, 2);
    expect(summary?.coveragePct).toBeCloseTo(95.52, 2);
  });

  it("describes cross effect separately from the unexplained residual", () => {
    const source = readFileSync(attributionWaterfallSourcePath, "utf8");

    expect(source).toContain("交叉效应为规模与收益率同时变化的二阶联动项");
    expect(source).toContain("未解释差额为损益变动扣除三项效应后的归因残差");
    expect(source).not.toContain("交叉效应为残差项");
  });

  it("treats fully explained volume-rate attribution as closed", () => {
    const summary = buildVolumeRateBridgeSummary({
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric({ raw: 110_000 }),
      total_previous_pnl: numeric({ raw: 100_000 }),
      total_pnl_change: numeric({ raw: 10_000 }),
      total_volume_effect: numeric({ raw: 2_000 }),
      total_rate_effect: numeric({ raw: 3_000 }),
      total_interaction_effect: numeric({ raw: 5_000 }),
      total_recon_error: numeric({ raw: 0 }),
      has_previous_data: true,
      items: [],
    });

    expect(summary).toMatchObject({
      explainedEffect: 10_000,
      unexplainedEffect: 0,
      coveragePct: 100,
      status: "closed",
    });
  });

  it("locks the frontend closure tolerance as a display heuristic contract", () => {
    // 容差是前端展示口径，不是后端 workbench 契约；数值变动必须先过治理评审。
    expect(VOLUME_RATE_CLOSURE_TOLERANCE_YUAN).toBe(10_000);
    expect(VOLUME_RATE_CLOSURE_DISCLOSURE).toBe("闭合判定为前端口径（容差 1 万元，非后端契约）");

    const summary = buildVolumeRateBridgeSummary({
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric({ raw: 1_200_000 }),
      total_previous_pnl: numeric({ raw: 1_000_000 }),
      total_pnl_change: numeric({ raw: 200_000 }),
      total_volume_effect: numeric({ raw: 100_000 }),
      total_rate_effect: numeric({ raw: 60_000 }),
      total_interaction_effect: numeric({ raw: 30_000 }),
      total_recon_error: numeric({ raw: 10_000 }),
      has_previous_data: true,
      items: [],
    });

    expect(summary?.closureDisclosure).toBe(VOLUME_RATE_CLOSURE_DISCLOSURE);
  });

  it("treats residuals at the tolerance boundary as closed and just above it as residual", () => {
    const buildWithResidual = (interactionRaw: number, reconRaw: number) =>
      buildVolumeRateBridgeSummary({
        current_period: "2026-04",
        previous_period: "2026-03",
        compare_type: "mom",
        total_current_pnl: numeric({ raw: 1_200_000 }),
        total_previous_pnl: numeric({ raw: 1_000_000 }),
        total_pnl_change: numeric({ raw: 200_000 }),
        total_volume_effect: numeric({ raw: 100_000 }),
        total_rate_effect: numeric({ raw: 60_000 }),
        total_interaction_effect: numeric({ raw: interactionRaw }),
        total_recon_error: numeric({ raw: reconRaw }),
        has_previous_data: true,
        items: [],
      });

    // |残差| = 容差（恰好 1 万元）→ 仍判闭合（严格大于才算未解释差额）。
    expect(buildWithResidual(30_000, 10_000)).toMatchObject({ status: "closed" });
    // |残差| = 容差 + 1 元 → 判存在未解释差额。
    expect(buildWithResidual(29_999, 10_001)).toMatchObject({
      status: "residual",
      statusLabel: "存在未解释差额",
    });
    // 负向残差同样按绝对值过容差判定。
    expect(buildWithResidual(50_001, -10_001)).toMatchObject({ status: "residual" });
  });

  it("suppresses coverage instead of fabricating it when the pnl change is inside the tolerance", () => {
    const summary = buildVolumeRateBridgeSummary({
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric({ raw: 1_010_000 }),
      total_previous_pnl: numeric({ raw: 1_000_000 }),
      total_pnl_change: numeric({ raw: 10_000 }),
      total_volume_effect: numeric({ raw: 8_000 }),
      total_rate_effect: numeric({ raw: 3_000 }),
      total_interaction_effect: numeric({ raw: 1_000 }),
      total_recon_error: numeric({ raw: -2_000 }),
      has_previous_data: true,
      items: [],
    });

    // 分母（损益变动）落在容差内且解释项超容差时，覆盖率不可计算 → undefined，不得渲染成读数。
    expect(summary?.explainedEffect).toBe(12_000);
    expect(summary?.coveragePct).toBeUndefined();
    expect(summary?.status).toBe("closed");
  });

  it("selects the current-view date label per tab", () => {
    expect(
      formatMetaDateLabel("volume-rate", {
        volumeRateData: { current_period: "2026-03" } as VolumeRateAttributionPayload,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "当前期间",
      value: "2026-03",
    });

    expect(
      formatMetaDateLabel("tpl-market", {
        volumeRateData: null,
        tplMarketData: {
          start_period: "2025-04",
          end_period: "2026-03",
        } as TPLMarketCorrelationPayload,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "观察区间",
      value: "2025-04 ~ 2026-03",
    });

    expect(
      formatMetaDateLabel("composition", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: { report_period: "2026-03" } as PnlCompositionPayload,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "报告日期",
      value: "2026-03",
    });

    expect(
      formatMetaDateLabel("advanced", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: { report_date: "2026-04-09" } as AdvancedAttributionSummary,
      }),
    ).toEqual({
      label: "报告日期",
      value: "2026-04-09",
    });
  });

  it("keeps missing date labels explicit instead of fabricating values", () => {
    expect(
      formatMetaDateLabel("tpl-market", {
        volumeRateData: null,
        tplMarketData: { start_period: "2025-04", end_period: null } as unknown as TPLMarketCorrelationPayload,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "观察区间",
      value: "—",
    });

    expect(
      formatMetaDateLabel("advanced", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "报告日期",
      value: "—",
    });
  });

  it("labels product category attribution by its own selected report date", () => {
    expect(
      formatMetaDateLabel("product-category", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: null,
        productCategoryAttributionData: {
          current_report_date: "2026-03-31",
        } as ProductCategoryAttributionPayload,
        productCategoryMonthlyData: { report_date: "2026-03-31" } as ProductCategoryPnlPayload,
        productCategoryYtdData: null,
      }),
    ).toMatchObject({
      value: "2026-03-31",
    });
  });

  it("defaults each lens to its own latest report date", () => {
    expect(
      resolveDualReportDates({
        businessDates: ["2026-04-30", "2026-03-31", "2026-02-28"],
        productCategoryDates: ["2026-03-31", "2026-02-28"],
      }),
    ).toMatchObject({
      formalReportDate: "2026-04-30",
      productCategoryReportDate: "2026-03-31",
      hasFormalDate: true,
      hasProductCategoryDate: true,
      datesAligned: false,
      missingSource: "none",
    });
  });

  it("keeps an explicitly selected report date per source independently", () => {
    expect(
      resolveDualReportDates({
        businessDates: ["2026-04-30", "2026-03-31", "2026-02-28"],
        productCategoryDates: ["2026-03-31", "2026-02-28"],
        preferredReportDate: "2026-02-28",
      }),
    ).toMatchObject({
      formalReportDate: "2026-02-28",
      productCategoryReportDate: "2026-02-28",
      datesAligned: true,
    });

    expect(
      resolveDualReportDates({
        businessDates: ["2026-04-30", "2026-03-31"],
        productCategoryDates: ["2026-02-28"],
        preferredReportDate: "2026-04-30",
      }),
    ).toMatchObject({
      formalReportDate: "2026-04-30",
      productCategoryReportDate: "2026-02-28",
      hasFormalDate: true,
      hasProductCategoryDate: true,
      datesAligned: false,
      missingSource: "none",
    });
  });

  it("summarizes client request failures into a Chinese conclusion with the raw detail kept aside", () => {
    const summary = summarizePnlAttributionError(
      "Request failed: /api/pnl-attribution/campisi?end_date=2026-03-31 (500)",
    );

    expect(summary?.message).toBe(
      "后端接口请求失败（HTTP 500），当前视图数据未能读取；请重试或先检查后端服务。",
    );
    // 接口路径属证据层：只进 detail（供 title），不进正文。
    expect(summary?.message).not.toContain("/api/pnl-attribution");
    expect(summary?.detail).toBe(
      "Request failed: /api/pnl-attribution/campisi?end_date=2026-03-31 (500)",
    );
  });

  it("passes through non-request-failure error text verbatim", () => {
    expect(summarizePnlAttributionError("Campisi 决策级解释加载失败")).toEqual({
      message: "Campisi 决策级解释加载失败",
      detail: "Campisi 决策级解释加载失败",
    });
    expect(summarizePnlAttributionError(null)).toBeNull();
    expect(summarizePnlAttributionError("   ")).toBeNull();
  });

  it("formats microsecond ISO generated_at down to minutes and keeps the raw value for title", () => {
    expect(formatGeneratedAtDisplay("2026-08-13T16:52:36.869107Z")).toEqual({
      text: "2026-08-13 16:52",
      title: "2026-08-13T16:52:36.869107Z",
    });
    // 非 ISO 形态原样透出；缺失显示 EM_DASH，不伪造时间。
    expect(formatGeneratedAtDisplay("mock-run")).toEqual({
      text: "mock-run",
      title: "mock-run",
    });
    expect(formatGeneratedAtDisplay(null)).toEqual({ text: "—", title: "" });
    expect(formatGeneratedAtDisplay("")).toEqual({ text: "—", title: "" });
  });

  it("builds a cumulative attribution bridge with pads, connectors, and signed values", () => {
    const bridge = buildAttributionBridge({
      previous: 7.86,
      volume: 0.12,
      rate: -0.29,
      interaction: 0.23,
      current: 8.51,
    });

    expect(bridge).not.toBeNull();
    const bars = bridge!.bars;
    expect(bars.map((bar) => bar.category)).toEqual([
      "上期损益",
      "规模效应",
      "利率效应",
      "交叉效应",
      "当期损益",
    ]);
    // 上期总值从 0 起画。
    expect(bars[0]).toMatchObject({ base: 0, size: 7.86, value: 7.86, tone: "total-prev" });
    // 正效应从上期累计位起画。
    expect(bars[1].base).toBeCloseTo(7.86, 10);
    expect(bars[1].size).toBeCloseTo(0.12, 10);
    expect(bars[1].tone).toBe("positive");
    // 负效应垫柱压到累计终点（低位），柱体跨度为绝对值。
    expect(bars[2].base).toBeCloseTo(7.86 + 0.12 - 0.29, 10);
    expect(bars[2].size).toBeCloseTo(0.29, 10);
    expect(bars[2].value).toBeCloseTo(-0.29, 10);
    expect(bars[2].tone).toBe("negative");
    // 交叉效应方向语义弱，恒中性。
    expect(bars[3].tone).toBe("neutral");
    expect(bars[4]).toMatchObject({ base: 0, tone: "total-current" });
    expect(bars[4].size).toBeCloseTo(8.51, 10);

    // 连线落在各段累计位：上期 → 各效应累计 → 效应合计（与当期柱顶的落差即残差）。
    expect(bridge!.connectors.map((connector) => [connector.from, connector.to])).toEqual([
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
    ]);
    expect(bridge!.connectors[0].level).toBeCloseTo(7.86, 10);
    expect(bridge!.connectors[3].level).toBeCloseTo(7.86 + 0.12 - 0.29 + 0.23, 10);
  });

  it("refuses to build a bridge when any input is missing instead of padding zeros", () => {
    expect(
      buildAttributionBridge({
        previous: 7.86,
        volume: null,
        rate: -0.29,
        interaction: 0.23,
        current: 8.51,
      }),
    ).toBeNull();
  });

  it("keeps negative totals anchored to zero in the bridge", () => {
    const bridge = buildAttributionBridge({
      previous: -1.2,
      volume: 0.5,
      rate: 0.1,
      interaction: 0,
      current: -0.6,
    });

    expect(bridge!.bars[0]).toMatchObject({ base: -1.2, size: 1.2, value: -1.2 });
    // 从负累计位向上画正效应：垫柱停在累计起点（更低的一端）。
    expect(bridge!.bars[1].base).toBeCloseTo(-1.2, 10);
    expect(bridge!.bars[1].size).toBeCloseTo(0.5, 10);
    expect(bridge!.bars[4]).toMatchObject({ base: -0.6, size: 0.6, value: -0.6 });
  });

  it("reports missing source sides instead of fabricating a date", () => {
    expect(
      resolveDualReportDates({
        businessDates: [],
        productCategoryDates: ["2026-03-31"],
      }),
    ).toMatchObject({
      formalReportDate: null,
      productCategoryReportDate: "2026-03-31",
      hasFormalDate: false,
      hasProductCategoryDate: true,
      missingSource: "formal-attribution",
    });

    expect(
      resolveDualReportDates({
        businessDates: [],
        productCategoryDates: [],
      }),
    ).toMatchObject({
      formalReportDate: null,
      productCategoryReportDate: null,
      hasFormalDate: false,
      hasProductCategoryDate: false,
      missingSource: "both",
    });
  });
});
