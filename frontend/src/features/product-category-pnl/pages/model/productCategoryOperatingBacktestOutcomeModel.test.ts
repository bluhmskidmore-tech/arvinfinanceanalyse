import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../../utils/format";
import {
  buildProductCategoryOperatingBacktestExample,
  summarizeProductCategoryOperatingBacktestOutcomes,
  type ProductCategoryOperatingActionKind,
  type ProductCategoryOperatingBacktestOutcomeInput,
} from "./productCategoryOperatingBacktestOutcomeModel";

const formatYiDelta = (value: number | null) =>
  value === null ? EM_DASH : `amount:${value}`;

function example(
  actionKind: ProductCategoryOperatingActionKind,
  overrides: Partial<ProductCategoryOperatingBacktestOutcomeInput> = {},
) {
  return buildProductCategoryOperatingBacktestExample(
    {
      reportDate: "2026-01-31",
      nextReportDate: "2026-02-28",
      categoryId: "synthetic_product",
      categoryLabel: "Synthetic product",
      priorityLabel: "P1",
      actionLabel: "Synthetic action",
      actionKind,
      netIncomeDelta: 0,
      nextNetIncome: 0,
      yieldDeltaBp: 0,
      scaleDelta: 0,
      currentUnexplainedAbs: 0,
      nextUnexplainedAbs: 0,
      ...overrides,
    },
    formatYiDelta,
  );
}

describe("operating backtest outcome model", () => {
  it.each([
    ["shrink_or_limit", { netIncomeDelta: 0.00001 }],
    ["reprice_or_improve", { yieldDeltaBp: 0.00001 }],
    ["selective_growth", { scaleDelta: 0.00001, nextNetIncome: 0.00001 }],
    ["review_attribution", { currentUnexplainedAbs: 0.00002, nextUnexplainedAbs: 0.00001 }],
  ] satisfies Array<[
    ProductCategoryOperatingActionKind,
    Partial<ProductCategoryOperatingBacktestOutcomeInput>,
  ]>)("evaluates small raw improvements for %s before formatting", (kind, values) => {
    expect(example(kind, values)).toMatchObject({
      outcomeLabel: "命中",
      missReasonKeys: [],
      tone: "positive",
    });
  });

  it.each([
    ["shrink_or_limit", ["net_income_not_improved"]],
    ["reprice_or_improve", ["yield_not_improved"]],
    ["selective_growth", ["scale_not_expanded", "positive_contribution_missing", "yield_not_improved"]],
    ["review_attribution", ["attribution_not_reduced"]],
  ] satisfies Array<[ProductCategoryOperatingActionKind, string[]]>)(
    "retains the strict zero boundary and reason order for %s",
    (kind, missReasonKeys) => {
      expect(example(kind)).toMatchObject({
        outcomeLabel: "未命中",
        missReasonKeys,
        tone: "negative",
      });
    },
  );

  it.each([
    ["shrink_or_limit", { netIncomeDelta: null }],
    ["reprice_or_improve", { yieldDeltaBp: null }],
    ["selective_growth", { scaleDelta: null }],
    ["selective_growth", { nextNetIncome: null }],
    ["review_attribution", { currentUnexplainedAbs: null }],
    ["review_attribution", { nextUnexplainedAbs: null }],
  ] satisfies Array<[
    ProductCategoryOperatingActionKind,
    Partial<ProductCategoryOperatingBacktestOutcomeInput>,
  ]>)("keeps missing required evidence pending for %s", (kind, values) => {
    expect(example(kind, values)).toMatchObject({
      outcomeLabel: "待判定",
      missReasonKeys: [],
      tone: "neutral",
    });
  });

  it("shares the same sample evidence between hit judgment and miss reasons", () => {
    expect(example("reprice_or_improve", {
      yieldDeltaBp: -0.00001,
      scaleDelta: 0.00001,
      netIncomeDelta: -0.00001,
    })).toMatchObject({
      outcomeLabel: "未命中",
      yieldDeltaBp: -0.00001,
      yieldDeltaBpLabel: "-0.0 bp",
      missReasonKeys: ["yield_not_improved", "scale_mismatch", "net_income_drag"],
    });
  });

  it("retains action order, excludes pending samples from rates, and keeps reason ties stable", () => {
    const pending = example("review_attribution", { nextUnexplainedAbs: null });
    const { actionRows, missReasonRows, calibrationRows } =
      summarizeProductCategoryOperatingBacktestOutcomes({
        samples: [
          example("selective_growth"),
          pending,
          example("reprice_or_improve", { scaleDelta: 1, netIncomeDelta: -1 }),
          example("shrink_or_limit", { netIncomeDelta: 1 }),
          example("reprice_or_improve", { yieldDeltaBp: 0.00001 }),
        ],
        formatYiDelta,
      });

    expect(actionRows.map((row) => row.actionKind)).toEqual([
      "shrink_or_limit", "review_attribution", "reprice_or_improve", "selective_growth",
    ]);
    expect(actionRows[1]).toMatchObject({
      signalCount: 1, comparableCount: 0, hitCount: 0, hitRate: null,
      hitRateLabel: EM_DASH, tone: "neutral",
    });
    expect(actionRows[2]).toMatchObject({
      signalCount: 2, comparableCount: 2, hitCount: 1, hitRate: 0.5,
      averageYieldDeltaBp: 0, averageYieldDeltaBpLabel: "0.0 bp", tone: "positive",
    });
    expect(missReasonRows.map((row) => row.actionKind)).toEqual([
      "selective_growth", "reprice_or_improve",
    ]);
    expect(missReasonRows[1].reasonRows.map((row) => row.reasonKey)).toEqual([
      "yield_not_improved", "scale_mismatch", "net_income_drag",
    ]);
    expect(missReasonRows[1]).toMatchObject({
      missCount: 1, comparableCount: 2, missRate: 0.5,
      missRateLabel: "50.0%", primaryReasonLabel: "收益率未改善",
    });
    expect(calibrationRows.map((row) => row.actionKind)).toEqual([
      "selective_growth", "review_attribution", "shrink_or_limit", "reprice_or_improve",
    ]);
    expect(calibrationRows[1]).toMatchObject({
      recommendationLabel: "继续观察", confidenceLabel: "低置信",
      confidenceDetailLabel: "0 条可评价样本",
    });
  });

  it.each([
    [1, 4, "收紧触发条件", "中置信"],
    [3, 10, "继续观察", "高置信"],
    [1, 2, "保留规则", "低置信"],
    [2, 3, "保留规则", "中置信"],
  ])("preserves calibration thresholds at %s/%s hits", (hits, count, recommendationLabel, confidenceLabel) => {
    const summary = summarizeProductCategoryOperatingBacktestOutcomes({
      samples: Array.from({ length: count }, (_, index) =>
        example("shrink_or_limit", { netIncomeDelta: index < hits ? 1 : 0 }),
      ),
      formatYiDelta,
    });
    expect(summary.calibrationRows[0]).toMatchObject({ recommendationLabel, confidenceLabel });
  });

  it("keeps empty summaries empty", () => {
    expect(summarizeProductCategoryOperatingBacktestOutcomes({
      samples: [], formatYiDelta,
    })).toEqual({ actionRows: [], missReasonRows: [], calibrationRows: [] });
  });
});
