import type { Numeric } from "../../../api/contracts";
import { numericRaw, type MetricTone } from "../../../pageModel";
import { EM_DASH } from "../../../utils/format";
import type { CashflowBucketVM, CashflowProjectionVM } from "../adapters/cashflowProjectionAdapter";

export type CashflowMonthlyProjectionSeries = {
  categories: string[];
  /** `null` marks a missing bucket value; ECharts must render it as a gap, not as 0. */
  assetInflow: (number | null)[];
  liabilityOutflow: (number | null)[];
  cumulativeNet: (number | null)[];
};

export type CashflowProjectionRiskReadout = {
  tone: Extract<MetricTone, "positive" | "warning" | "neutral">;
  summary: string;
  negativeCumulativeMonths: number;
  missingCumulativeMonths: number;
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
    assetInflow: buckets.map((bucket) => numericRaw(bucket.assetInflow)),
    liabilityOutflow: buckets.map((bucket) => numericRaw(bucket.liabilityOutflow)),
    cumulativeNet: buckets.map((bucket) => numericRaw(bucket.cumulativeNet)),
  };
}

/** Pick the extreme bucket across readable values only; a missing bucket never wins. */
function pickExtremeBucket(
  buckets: CashflowBucketVM[],
  read: (bucket: CashflowBucketVM) => number | null,
  isBetter: (candidate: number, incumbent: number) => boolean,
): CashflowBucketVM | null {
  let best: { bucket: CashflowBucketVM; value: number } | null = null;
  for (const bucket of buckets) {
    const value = read(bucket);
    if (value === null) continue;
    if (best === null || isBetter(value, best.value)) {
      best = { bucket, value };
    }
  }
  return best?.bucket ?? null;
}

export function selectCashflowProjectionRiskReadout(
  vm: CashflowProjectionVM | null,
): CashflowProjectionRiskReadout | null {
  const buckets = vm?.monthlyBuckets ?? [];
  if (buckets.length === 0) return null;

  const cumulativeRaws = buckets.map((bucket) => numericRaw(bucket.cumulativeNet));
  const negativeCumulativeMonths = cumulativeRaws.filter((raw) => raw !== null && raw < 0).length;
  const missingCumulativeMonths = cumulativeRaws.filter((raw) => raw === null).length;

  const worstCumulative = pickExtremeBucket(
    buckets,
    (bucket) => numericRaw(bucket.cumulativeNet),
    (candidate, incumbent) => candidate < incumbent,
  );
  const largestOutflow = pickExtremeBucket(
    buckets,
    (bucket) => numericRaw(bucket.liabilityOutflow),
    (candidate, incumbent) => candidate > incumbent,
  );
  const finalBucket = buckets[buckets.length - 1];

  const summaryParts: string[] = [];
  if (negativeCumulativeMonths > 0) {
    summaryParts.push(`${negativeCumulativeMonths} 个月累计净现金流为负`);
  }
  if (missingCumulativeMonths > 0) {
    summaryParts.push(`${missingCumulativeMonths} 个月累计净现金流缺数`);
  }

  return {
    // A missing month can hide a negative month, so the readout must never claim "positive".
    tone:
      negativeCumulativeMonths > 0
        ? "warning"
        : missingCumulativeMonths > 0
          ? "neutral"
          : "positive",
    summary: summaryParts.length > 0 ? summaryParts.join(" · ") : "未见累计净现金流为负月份",
    negativeCumulativeMonths,
    missingCumulativeMonths,
    worstCumulativeMonth: worstCumulative?.yearMonth ?? EM_DASH,
    worstCumulativeDisplay: worstCumulative?.cumulativeNet.display ?? EM_DASH,
    largestOutflowMonth: largestOutflow?.yearMonth ?? EM_DASH,
    largestOutflowDisplay: largestOutflow?.liabilityOutflow.display ?? EM_DASH,
    finalCumulativeDisplay: finalBucket.cumulativeNet.display,
  };
}
