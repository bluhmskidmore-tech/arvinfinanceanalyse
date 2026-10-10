import { EM_DASH } from "../../../../utils/format";

export type ProductCategoryOperatingActionKind =
  | "shrink_or_limit"
  | "review_attribution"
  | "reprice_or_improve"
  | "selective_growth";

export type ProductCategoryOperatingBacktestActionRow = {
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  signalCount: number;
  comparableCount: number;
  hitCount: number;
  hitRate: number | null;
  hitRateLabel: string;
  averageNetIncomeDelta: number | null;
  averageNetIncomeDeltaLabel: string;
  averageYieldDeltaBp: number | null;
  averageYieldDeltaBpLabel: string;
  averageScaleDelta: number | null;
  averageScaleDeltaLabel: string;
  evidenceLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestMissReasonKey =
  | "net_income_not_improved"
  | "yield_not_improved"
  | "scale_not_expanded"
  | "positive_contribution_missing"
  | "attribution_not_reduced"
  | "scale_mismatch"
  | "net_income_drag"
  | "outcome_not_improved";

export type ProductCategoryOperatingBacktestMissReasonRow = {
  reasonKey: ProductCategoryOperatingBacktestMissReasonKey;
  reasonLabel: string;
  sampleCount: number;
  sampleShareLabel: string;
};

export type ProductCategoryOperatingBacktestMissActionRow = {
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  missCount: number;
  comparableCount: number;
  missRate: number | null;
  missRateLabel: string;
  primaryReasonLabel: string;
  reasonRows: ProductCategoryOperatingBacktestMissReasonRow[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestCalibrationRow = {
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  recommendationLabel: string;
  reasonLabel: string;
  evidenceLabel: string;
  confidenceLabel: string;
  confidenceDetailLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestExample = {
  reportDate: string;
  nextReportDate: string;
  categoryId: string;
  categoryLabel: string;
  priorityLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  outcomeLabel: string;
  netIncomeDelta: number | null;
  netIncomeDeltaLabel: string;
  yieldDeltaBp: number | null;
  yieldDeltaBpLabel: string;
  scaleDelta: number | null;
  scaleDeltaLabel: string;
  missReasonKeys: ProductCategoryOperatingBacktestMissReasonKey[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestOutcomeInput = {
  actionKind: ProductCategoryOperatingActionKind;
  netIncomeDelta: number | null;
  nextNetIncome: number | null;
  yieldDeltaBp: number | null;
  scaleDelta: number | null;
  currentUnexplainedAbs: number | null;
  nextUnexplainedAbs: number | null;
};

function productCategoryActionLabel(
  kind: ProductCategoryOperatingActionKind,
): string {
  if (kind === "shrink_or_limit") {
    return "压降或限额复核";
  }
  if (kind === "review_attribution") {
    return "归因复核";
  }
  if (kind === "reprice_or_improve") {
    return "重定价/提效";
  }
  return "选择性扩张";
}

function averageProductCategoryNumber(
  values: Array<number | null>,
): number | null {
  const candidates = values.filter(
    (value): value is number => value !== null && Number.isFinite(value),
  );
  if (candidates.length === 0) {
    return null;
  }
  return Number(
    (
      candidates.reduce((total, value) => total + value, 0) / candidates.length
    ).toFixed(2),
  );
}

function productCategoryRateLabel(rate: number | null): string {
  if (rate === null || !Number.isFinite(rate)) {
    return EM_DASH;
  }
  return `${(rate * 100).toFixed(1)}%`;
}

function signedProductCategoryBpDeltaLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value === 0) {
    return "0.0 bp";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(1)} bp`;
}

function productCategoryOutcomeHit(input: ProductCategoryOperatingBacktestOutcomeInput,
): boolean | null {
  if (input.actionKind === "shrink_or_limit") {
    return input.netIncomeDelta === null ? null : input.netIncomeDelta > 0;
  }
  if (input.actionKind === "reprice_or_improve") {
    return input.yieldDeltaBp === null ? null : input.yieldDeltaBp > 0;
  }
  if (input.actionKind === "selective_growth") {
    if (input.scaleDelta === null || input.nextNetIncome === null) {
      return null;
    }
    return input.scaleDelta > 0 && input.nextNetIncome > 0;
  }
  if (
    input.currentUnexplainedAbs === null ||
    input.nextUnexplainedAbs === null
  ) {
    return null;
  }
  return input.nextUnexplainedAbs < input.currentUnexplainedAbs;
}

function productCategoryBacktestEvidenceLabel(
  kind: ProductCategoryOperatingActionKind,
): string {
  if (kind === "shrink_or_limit") {
    return "命中=次月净营收改善";
  }
  if (kind === "reprice_or_improve") {
    return "命中=次月收益率改善";
  }
  if (kind === "selective_growth") {
    return "命中=次月规模扩张且仍为正贡献";
  }
  return "命中=次月未解释差异下降";
}

function productCategoryBacktestTone(
  hitRate: number | null,
): "positive" | "negative" | "neutral" {
  if (hitRate === null) {
    return "neutral";
  }
  if (hitRate >= 0.5) {
    return "positive";
  }
  if (hitRate < 0.3) {
    return "negative";
  }
  return "neutral";
}

const PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER: ProductCategoryOperatingBacktestMissReasonKey[] =
  [
    "yield_not_improved",
    "net_income_not_improved",
    "scale_not_expanded",
    "positive_contribution_missing",
    "attribution_not_reduced",
    "scale_mismatch",
    "net_income_drag",
    "outcome_not_improved",
  ];

function productCategoryBacktestMissReasonLabel(
  reasonKey: ProductCategoryOperatingBacktestMissReasonKey,
): string {
  if (reasonKey === "yield_not_improved") {
    return "收益率未改善";
  }
  if (reasonKey === "net_income_not_improved") {
    return "净营收未改善";
  }
  if (reasonKey === "scale_not_expanded") {
    return "规模未扩张";
  }
  if (reasonKey === "positive_contribution_missing") {
    return "正贡献不足";
  }
  if (reasonKey === "attribution_not_reduced") {
    return "未解释差异未下降";
  }
  if (reasonKey === "scale_mismatch") {
    return "规模方向错配";
  }
  if (reasonKey === "net_income_drag") {
    return "净营收拖累";
  }
  return "结果未改善";
}

function productCategoryBacktestMissReasonKeys(
  input: ProductCategoryOperatingBacktestOutcomeInput & { hit: boolean | null },
): ProductCategoryOperatingBacktestMissReasonKey[] {
  if (input.hit !== false) {
    return [];
  }
  const reasons: ProductCategoryOperatingBacktestMissReasonKey[] = [];
  if (input.actionKind === "reprice_or_improve") {
    if (input.yieldDeltaBp !== null && input.yieldDeltaBp <= 0) {
      reasons.push("yield_not_improved");
    }
    if (
      input.scaleDelta !== null &&
      input.scaleDelta > 0 &&
      (input.yieldDeltaBp === null || input.yieldDeltaBp <= 0)
    ) {
      reasons.push("scale_mismatch");
    }
    if (input.netIncomeDelta !== null && input.netIncomeDelta < 0) {
      reasons.push("net_income_drag");
    }
  } else if (input.actionKind === "shrink_or_limit") {
    if (input.netIncomeDelta !== null && input.netIncomeDelta <= 0) {
      reasons.push("net_income_not_improved");
    }
    if (input.scaleDelta !== null && input.scaleDelta > 0) {
      reasons.push("scale_mismatch");
    }
  } else if (input.actionKind === "selective_growth") {
    if (input.scaleDelta !== null && input.scaleDelta <= 0) {
      reasons.push("scale_not_expanded");
    }
    if (input.nextNetIncome !== null && input.nextNetIncome <= 0) {
      reasons.push("positive_contribution_missing");
    }
    if (input.yieldDeltaBp !== null && input.yieldDeltaBp <= 0) {
      reasons.push("yield_not_improved");
    }
  } else if (
    input.currentUnexplainedAbs !== null &&
    input.nextUnexplainedAbs !== null &&
    input.nextUnexplainedAbs >= input.currentUnexplainedAbs
  ) {
    reasons.push("attribution_not_reduced");
  }
  if (reasons.length === 0) {
    reasons.push("outcome_not_improved");
  }
  return reasons;
}

function productCategoryBacktestCalibrationRows(input: {
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  missReasonRows: ProductCategoryOperatingBacktestMissActionRow[];
}): ProductCategoryOperatingBacktestCalibrationRow[] {
  const missRowsByAction = new Map(
    input.missReasonRows.map((row) => [row.actionKind, row]),
  );
  const confidenceForCount = (count: number) => ({
    confidenceLabel: count >= 6 ? "高置信" : count >= 3 ? "中置信" : "低置信",
    confidenceDetailLabel: `${count} 条可评价样本`,
  });
  return input.actionRows
    .map((row) => {
      const missRow = missRowsByAction.get(row.actionKind);
      const confidence = confidenceForCount(row.comparableCount);
      if (row.hitRate !== null && row.hitRate >= 0.5) {
        return {
          actionKind: row.actionKind,
          actionLabel: row.actionLabel,
          recommendationLabel: "保留规则",
          reasonLabel: `命中率 ${row.hitRateLabel}，样本方向可继续复用`,
          evidenceLabel: `${row.signalCount} 条信号 · ${row.evidenceLabel}`,
          ...confidence,
          tone: "positive" as const,
        };
      }
      if (row.hitRate !== null && row.hitRate < 0.3 && missRow) {
        return {
          actionKind: row.actionKind,
          actionLabel: row.actionLabel,
          recommendationLabel: "收紧触发条件",
          reasonLabel: `命中率 ${row.hitRateLabel}，主因${missRow.primaryReasonLabel}`,
          evidenceLabel: `${missRow.missCount}/${missRow.comparableCount} 未命中 · ${row.evidenceLabel}`,
          ...confidence,
          tone: "negative" as const,
        };
      }
      return {
        actionKind: row.actionKind,
        actionLabel: row.actionLabel,
        recommendationLabel: "继续观察",
        reasonLabel: `命中率 ${row.hitRateLabel}，样本仍需累积`,
        evidenceLabel: `${row.signalCount} 条信号 · ${row.evidenceLabel}`,
        ...confidence,
        tone: "neutral" as const,
      };
    })
    .sort((left, right) => {
      const rank = { negative: 0, neutral: 1, positive: 2 };
      return rank[left.tone] - rank[right.tone];
    });
}

/** Evaluate candidate operating signals from raw deltas; round only display labels. */
export function buildProductCategoryOperatingBacktestExample(
  input: ProductCategoryOperatingBacktestOutcomeInput &
    Pick<
      ProductCategoryOperatingBacktestExample,
      | "reportDate"
      | "nextReportDate"
      | "categoryId"
      | "categoryLabel"
      | "priorityLabel"
      | "actionLabel"
    >,
  formatYiDelta: (value: number | null) => string,
): ProductCategoryOperatingBacktestExample {
  const hit = productCategoryOutcomeHit(input);
  return {
    reportDate: input.reportDate,
    nextReportDate: input.nextReportDate,
    categoryId: input.categoryId,
    categoryLabel: input.categoryLabel,
    priorityLabel: input.priorityLabel,
    actionKind: input.actionKind,
    actionLabel: input.actionLabel,
    outcomeLabel: hit === null ? "待判定" : hit ? "命中" : "未命中",
    netIncomeDelta: input.netIncomeDelta,
    netIncomeDeltaLabel: formatYiDelta(input.netIncomeDelta),
    yieldDeltaBp: input.yieldDeltaBp,
    yieldDeltaBpLabel: signedProductCategoryBpDeltaLabel(input.yieldDeltaBp),
    scaleDelta: input.scaleDelta,
    scaleDeltaLabel: formatYiDelta(input.scaleDelta),
    missReasonKeys: productCategoryBacktestMissReasonKeys({ ...input, hit }),
    tone: hit === null ? "neutral" : hit ? "positive" : "negative",
  };
}

const PRODUCT_CATEGORY_BACKTEST_ACTION_ORDER: ProductCategoryOperatingActionKind[] = [
  "shrink_or_limit",
  "review_attribution",
  "reprice_or_improve",
  "selective_growth",
];

/** Group each sample once for action, miss-reason, and calibration readouts. */
export function summarizeProductCategoryOperatingBacktestOutcomes(input: {
  samples: ProductCategoryOperatingBacktestExample[];
  formatYiDelta: (value: number | null) => string;
}): {
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  missReasonRows: ProductCategoryOperatingBacktestMissActionRow[];
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[];
} {
  const samplesByAction = new Map<
    ProductCategoryOperatingActionKind,
    ProductCategoryOperatingBacktestExample[]
  >(PRODUCT_CATEGORY_BACKTEST_ACTION_ORDER.map((kind) => [kind, []]));
  for (const sample of input.samples) {
    samplesByAction.get(sample.actionKind)?.push(sample);
  }
  const groups = Array.from(samplesByAction.entries());
  const actionRows = groups.flatMap(([actionKind, rows]) => {
    if (rows.length === 0) {
      return [];
    }
    const hitCount = rows.filter((row) => row.outcomeLabel === "命中").length;
    const comparableCount = rows.filter(
      (row) => row.outcomeLabel !== "待判定",
    ).length;
    const hitRate = comparableCount === 0 ? null : hitCount / comparableCount;
    const averageNetIncomeDelta = averageProductCategoryNumber(
      rows.map((row) => row.netIncomeDelta),
    );
    const averageYieldDeltaBp = averageProductCategoryNumber(
      rows.map((row) => row.yieldDeltaBp),
    );
    const averageScaleDelta = averageProductCategoryNumber(
      rows.map((row) => row.scaleDelta),
    );
    return [
      {
        actionKind,
        actionLabel: productCategoryActionLabel(actionKind),
        signalCount: rows.length,
        comparableCount,
        hitCount,
        hitRate,
        hitRateLabel: productCategoryRateLabel(hitRate),
        averageNetIncomeDelta,
        averageNetIncomeDeltaLabel: input.formatYiDelta(averageNetIncomeDelta),
        averageYieldDeltaBp,
        averageYieldDeltaBpLabel:
          signedProductCategoryBpDeltaLabel(averageYieldDeltaBp),
        averageScaleDelta,
        averageScaleDeltaLabel: input.formatYiDelta(averageScaleDelta),
        evidenceLabel: productCategoryBacktestEvidenceLabel(actionKind),
        tone: productCategoryBacktestTone(hitRate),
      },
    ];
  });
  const missReasonRows = groups
    .flatMap(([actionKind, rows]) => {
      const comparableRows = rows.filter(
        (row) => row.outcomeLabel !== "待判定",
      );
      const missedRows = rows.filter((row) => row.outcomeLabel === "未命中");
      if (missedRows.length === 0) {
        return [];
      }
      const reasonCounts = missedRows.reduce((counts, row) => {
        row.missReasonKeys.forEach((reasonKey) => {
          counts.set(reasonKey, (counts.get(reasonKey) ?? 0) + 1);
        });
        return counts;
      }, new Map<ProductCategoryOperatingBacktestMissReasonKey, number>());
      const reasonRows = Array.from(reasonCounts.entries())
        .sort((left, right) => {
          if (right[1] !== left[1]) {
            return right[1] - left[1];
          }
          return (
            PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER.indexOf(left[0]) -
            PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER.indexOf(right[0])
          );
        })
        .map(([reasonKey, sampleCount]) => ({
          reasonKey,
          reasonLabel: productCategoryBacktestMissReasonLabel(reasonKey),
          sampleCount,
          sampleShareLabel: `${sampleCount}/${missedRows.length}`,
        }));
      const missRate =
        comparableRows.length === 0
          ? null
          : missedRows.length / comparableRows.length;
      return [
        {
          actionKind,
          actionLabel: productCategoryActionLabel(actionKind),
          missCount: missedRows.length,
          comparableCount: comparableRows.length,
          missRate,
          missRateLabel: productCategoryRateLabel(missRate),
          primaryReasonLabel: reasonRows[0]?.reasonLabel ?? EM_DASH,
          reasonRows,
          tone: productCategoryBacktestTone(
            missRate === null ? null : 1 - missRate,
          ),
        },
      ];
    })
    .sort((left, right) => {
      if ((right.missRate ?? -1) !== (left.missRate ?? -1)) {
        return (right.missRate ?? -1) - (left.missRate ?? -1);
      }
      return right.missCount - left.missCount;
    });
  const calibrationRows = productCategoryBacktestCalibrationRows({
    actionRows,
    missReasonRows,
  });
  return { actionRows, missReasonRows, calibrationRows };
}
