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
  /** 后端原始精度串（收进 title）；无可缩写值时为 null。 */
  worstCumulativeTitle: string | null;
  largestOutflowMonth: string;
  largestOutflowDisplay: string;
  largestOutflowTitle: string | null;
  finalCumulativeDisplay: string;
  finalCumulativeTitle: string | null;
};

export function toYi(raw: number): number {
  return raw / 100_000_000;
}

/** 元 → “X.XX 亿” 展示串；null/undefined/"" 与非有限值一律回 EM_DASH，缺失桶不得画成 0.00 亿。 */
export function tooltipYi(value: unknown): string {
  if (value === null || value === undefined || value === "") return EM_DASH;
  const raw = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(raw)) return EM_DASH;
  return `${toYi(raw).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
}

/** 亿元缩写主值 + 原始精度 title；非 yuan 或缺 raw 时回退后端 display、title 置空。 */
function yuanReadout(value: Numeric | null | undefined): { display: string; title: string | null } {
  if (!value) return { display: EM_DASH, title: null };
  const raw = numericRaw(value);
  if (raw === null || value.unit !== "yuan") {
    return { display: value.display || EM_DASH, title: null };
  }
  return { display: tooltipYi(raw), title: value.display || null };
}

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

  const worstCumulativeReadout = yuanReadout(worstCumulative?.cumulativeNet);
  const largestOutflowReadout = yuanReadout(largestOutflow?.liabilityOutflow);
  const finalCumulativeReadout = yuanReadout(finalBucket.cumulativeNet);

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
    worstCumulativeDisplay: worstCumulativeReadout.display,
    worstCumulativeTitle: worstCumulativeReadout.title,
    largestOutflowMonth: largestOutflow?.yearMonth ?? EM_DASH,
    largestOutflowDisplay: largestOutflowReadout.display,
    largestOutflowTitle: largestOutflowReadout.title,
    finalCumulativeDisplay: finalCumulativeReadout.display,
    finalCumulativeTitle: finalCumulativeReadout.title,
  };
}

export type CashflowWarningDisplay = {
  /** 面向阅读的中文摘要行；未登记句原样透出（此时 summary 即原文）。 */
  summary: string;
  /** 已登记句的英文原文（收进默认折叠区）；未登记时为 null，避免折叠区重复原样句。 */
  original: string | null;
};

/** 后端 Decimal 串（含可选负号/科学计数）。 */
const DECIMAL_TOKEN = String.raw`(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)`;

function warningAmountYi(text: string): string | null {
  const value = Number(text);
  if (!Number.isFinite(value)) return null;
  return tooltipYi(value);
}

type CashflowWarningRule = {
  pattern: RegExp;
  /** 返回 null 表示金额解析失败，按未登记处理（fail-closed，原样透出）。 */
  build: (match: RegExpExecArray) => string | null;
};

/**
 * 现金流预测 warnings 的显示层映射（DESIGN §7：一页一语域）。
 * 只翻译登记过的后端句式；登记句的英文原文收进默认折叠区作证据，
 * 未登记句不猜测业务含义、原样透出。金额（元、8 位小数）缩写为亿元。
 */
const CASHFLOW_WARNING_RULES: CashflowWarningRule[] = [
  {
    pattern:
      /^Liability duration uses a remaining-term proxy \(years to maturity\), not a cashflow-weighted duration\.$/,
    build: () => "负债久期为剩余期限（到期年限）代理，非现金流加权久期。",
  },
  {
    pattern: /^No liability rows were available; liability duration defaults to zero\.$/,
    build: () => "无可用负债行，负债久期按 0 计。",
  },
  {
    pattern: new RegExp(
      `^(\\d+) floating-rate rows with market_value=${DECIMAL_TOKEN} use the current coupon rate as a frozen proxy for the full projection horizon; reset rates are not modeled\\.$`,
    ),
    build: (match) => {
      const yi = warningAmountYi(match[2]);
      return yi === null
        ? null
        : `${match[1]} 个浮息行按当前票息冻结推演全期，不建模利率重定价（市值 ${yi}）。`;
    },
  },
  {
    pattern: new RegExp(
      `^(\\d+) rows with market_value=${DECIMAL_TOKEN} lack an explicit payment frequency; annual coupon frequency is used as a proxy\\.$`,
    ),
    build: (match) => {
      const yi = warningAmountYi(match[2]);
      return yi === null ? null : `${match[1]} 行缺付息频率，按年付代理（市值 ${yi}）。`;
    },
  },
  {
    pattern: new RegExp(
      `^(\\d+) explicit bullet rows with market_value=${DECIMAL_TOKEN} lack a valid value_date; a one-year interest proxy is used\\.$`,
    ),
    build: (match) => {
      const yi = warningAmountYi(match[2]);
      return yi === null
        ? null
        : `${match[1]} 个一次性还本付息行缺有效起息日，按一年期利息代理（市值 ${yi}）。`;
    },
  },
  {
    pattern: new RegExp(
      `^${DECIMAL_TOKEN} of ${DECIMAL_TOKEN} (asset market value|liability value) lacks duration information; the duration gap uses only the duration-covered balance and does not extrapolate the covered average duration onto the excluded balance\\.$`,
    ),
    build: (match) => {
      const excludedYi = warningAmountYi(match[1]);
      const totalYi = warningAmountYi(match[2]);
      if (excludedYi === null || totalYi === null) return null;
      const side = match[3] === "asset market value" ? "资产市值" : "负债价值";
      return `${side} ${excludedYi}（合计 ${totalYi}）缺久期信息；久期缺口仅按久期覆盖余额计算，不向缺失部分外推。`;
    },
  },
];

/** 单条 warning 的显示层映射；登记句翻中文摘要并保留英文原文，未登记句原样透出。 */
export function describeCashflowWarning(warning: string): CashflowWarningDisplay {
  for (const rule of CASHFLOW_WARNING_RULES) {
    const match = rule.pattern.exec(warning);
    if (!match) continue;
    const summary = rule.build(match);
    if (summary === null) break;
    return { summary, original: warning };
  }
  return { summary: warning, original: null };
}
