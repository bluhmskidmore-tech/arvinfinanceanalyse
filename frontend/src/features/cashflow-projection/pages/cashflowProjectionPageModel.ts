import type { Numeric } from "../../../api/contracts";
import { numericRaw, numericRawOrZero, type MetricTone } from "../../../pageModel";
import type { CashflowProjectionVM } from "../adapters/cashflowProjectionAdapter";

export type CashflowMonthlyProjectionSeries = {
  categories: string[];
  assetInflow: number[];
  liabilityOutflow: number[];
  cumulativeNet: number[];
};

export type CashflowProjectionRiskReadout = {
  tone: Extract<MetricTone, "positive" | "warning" | "neutral">;
  summary: string;
  negativeCumulativeMonths: number;
  worstCumulativeMonth: string;
  worstCumulativeDisplay: string;
  largestOutflowMonth: string;
  largestOutflowDisplay: string;
  finalCumulativeDisplay: string;
};

export type CashflowRateSensitivitySemantic = {
  tone: "default" | "positive" | "negative" | "warning";
  detail: string;
};

/** Display tone for duration gap — positive gap must never map to up/green. */
export type CashflowDurationGapTone = "default" | "gapPositive" | "negative" | "warning";

/**
 * Duration-gap color policy (DESIGN Decisions Log 2026-07-19):
 * - positive gap → neutral secondary (`gapPositive`) or warn when material; never `--ib-up`
 * - negative gap → `--ib-down` for direction only
 * - missing → warn
 */
export function selectCashflowDurationGapTone(
  value: Numeric | undefined,
): CashflowDurationGapTone {
  const raw = numericRaw(value);
  if (raw === null) return "warning";
  if (raw < 0) return "negative";
  if (raw > 0.05) return "warning";
  if (raw > 0) return "gapPositive";
  return "default";
}

export function selectCashflowRateSensitivitySemantic(
  value: Numeric | undefined,
): CashflowRateSensitivitySemantic {
  const raw = numericRaw(value);
  if (raw === null) {
    return {
      tone: "warning",
      detail: "利率上行 1bp 的权益变动待确认（原始单位：元）",
    };
  }
  if (raw < 0) {
    return {
      tone: "negative",
      detail: "利率上行 1bp → 权益减少（原始单位：元）",
    };
  }
  if (raw > 0) {
    return {
      tone: "positive",
      detail: "利率上行 1bp → 权益增加（原始单位：元）",
    };
  }
  return {
    tone: "default",
    detail: "利率上行 1bp → 权益基本不变（原始单位：元）",
  };
}

export function selectCashflowMonthlyProjectionSeries(
  vm: CashflowProjectionVM | null,
): CashflowMonthlyProjectionSeries | null {
  const buckets = vm?.monthlyBuckets ?? [];
  if (buckets.length === 0) return null;

  return {
    categories: buckets.map((bucket) => bucket.yearMonth),
    assetInflow: buckets.map((bucket) => numericRawOrZero(bucket.assetInflow)),
    liabilityOutflow: buckets.map((bucket) => numericRawOrZero(bucket.liabilityOutflow)),
    cumulativeNet: buckets.map((bucket) => numericRawOrZero(bucket.cumulativeNet)),
  };
}

export function selectCashflowProjectionRiskReadout(
  vm: CashflowProjectionVM | null,
): CashflowProjectionRiskReadout | null {
  const buckets = vm?.monthlyBuckets ?? [];
  if (buckets.length === 0) return null;

  const negativeCumulativeMonths = buckets.filter(
    (bucket) => numericRawOrZero(bucket.cumulativeNet) < 0,
  ).length;
  const worstCumulative = buckets.reduce((worst, bucket) =>
    numericRawOrZero(bucket.cumulativeNet) < numericRawOrZero(worst.cumulativeNet) ? bucket : worst,
  );
  const largestOutflow = buckets.reduce((largest, bucket) =>
    numericRawOrZero(bucket.liabilityOutflow) > numericRawOrZero(largest.liabilityOutflow) ? bucket : largest,
  );
  const finalBucket = buckets[buckets.length - 1];

  return {
    tone: negativeCumulativeMonths > 0 ? "warning" : "positive",
    summary:
      negativeCumulativeMonths > 0
        ? `${negativeCumulativeMonths} 个月累计净现金流为负`
        : "未见累计净现金流为负月份",
    negativeCumulativeMonths,
    worstCumulativeMonth: worstCumulative.yearMonth,
    worstCumulativeDisplay: worstCumulative.cumulativeNet.display,
    largestOutflowMonth: largestOutflow.yearMonth,
    largestOutflowDisplay: largestOutflow.liabilityOutflow.display,
    finalCumulativeDisplay: finalBucket.cumulativeNet.display,
  };
}
