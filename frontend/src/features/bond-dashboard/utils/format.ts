import Decimal from "decimal.js";

import type { Numeric } from "../../../api/contracts";
import { numericDecimalOrNull } from "../../../api/numeric";
import { EM_DASH, numericRaw } from "../../../pageModel";

type NumericLike = Numeric | number | null | undefined;

/** Read Numeric.raw without converting missing governed data into zero. */
export function nativeToNumber(value: NumericLike): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  return numericRaw(value);
}

/** Prefer governed lossless decimal text, with raw-only legacy responses kept compatible. */
export function nativeToDecimal(value: NumericLike): Decimal | null {
  const exact = numericDecimalOrNull(value);
  if (exact !== null) return exact;
  const raw = nativeToNumber(value);
  return raw === null ? null : new Decimal(raw);
}

/** Only treat governed raw_text as exact; raw-only numerics must stay on the legacy JS path. */
export function exactDecimalOrNull(value: NumericLike): Decimal | null {
  return numericDecimalOrNull(value);
}

function formatGroupedDecimal(
  value: Decimal,
  digits: number,
  rounding: Decimal.Rounding = Decimal.ROUND_HALF_UP,
): string {
  const fixed = value.toFixed(digits, rounding);
  const sign = fixed.startsWith("-") ? "-" : "";
  const unsigned = sign ? fixed.slice(1) : fixed;
  const [integerPart, fractionPart] = unsigned.split(".");
  const groupedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fractionPart === undefined ? `${sign}${groupedInteger}` : `${sign}${groupedInteger}.${fractionPart}`;
}

/** Governed yuan field -> yi display for cards/tables. */
export function formatYi(value: NumericLike, digits = 2): string {
  const exact = numericDecimalOrNull(value);
  if (exact !== null) return formatGroupedDecimal(exact.dividedBy("1e8"), digits);
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return (raw / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Governed ratio field -> percent display text for tooltips/readouts. */
export function formatRatioPercent(value: NumericLike, digits = 2): string {
  const exact = numericDecimalOrNull(value);
  if (exact !== null) return formatGroupedDecimal(exact.times(100), digits);
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return (raw * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Governed ratio/pct field -> percent display. */
export function formatRatePercent(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return (raw * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Governed bp field -> plain bp number display for callers that add the unit. */
export function formatBp(value: NumericLike, digits = 1): string {
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return raw.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Governed DV01 yuan field -> wan-yuan display. */
export function formatDv01Wan(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return (raw / 1e4).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/**
 * result_meta 时间戳（微秒 ISO，如 2026-08-13T19:24:06.752770Z）→ 本地
 * YYYY-MM-DD HH:mm:ss；不可解析时原样返回，不伪造时间。
 */
export function formatEvidenceTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`;
  const time = `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`;
  return `${date} ${time}`;
}

export function formatYears(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return raw.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatMomRatio(cur: Numeric | null | undefined, prev: Numeric | null | undefined): string | null {
  const exactCurrent = numericDecimalOrNull(cur);
  const exactPrevious = numericDecimalOrNull(prev);
  if (exactCurrent === null && exactPrevious === null) {
    const current = nativeToNumber(cur);
    const previous = nativeToNumber(prev);
    if (current === null || previous === null || previous === 0) return null;
    const pct = ((current - previous) / Math.abs(previous)) * 100;
    return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
  }

  const current = exactCurrent ?? nativeToDecimal(cur);
  const previous = exactPrevious ?? nativeToDecimal(prev);
  if (current === null || previous === null || previous.isZero()) return null;
  const pct = current.minus(previous).dividedBy(previous.abs()).times(100);
  return `${pct.greaterThanOrEqualTo(0) ? "+" : ""}${pct.toFixed(2, Decimal.ROUND_HALF_UP)}%`;
}

/**
 * How a KPI's month-over-month change must be expressed.
 * - `percent`: level amounts, where a relative change is meaningful
 * - `rateBp`: yields/coupons/spreads, where the market convention is a bp difference
 *   (2.50% -> 2.60% is +10.0bp, not +4.00%)
 * - `amountYi`: sign-variable P&L, where a ratio over a possibly negative base misleads
 */
export type BondKpiMomKind = "percent" | "rateBp" | "amountYi";

function momSignPrefix(delta: Decimal): string {
  return delta.greaterThan(0) ? "+" : "";
}

export function formatMomChange(
  kind: BondKpiMomKind,
  cur: Numeric | null | undefined,
  prev: Numeric | null | undefined,
): string | null {
  if (kind === "percent") return formatMomRatio(cur, prev);
  if (!cur || !prev) return null;
  const exactCurrent = numericDecimalOrNull(cur);
  const exactPrevious = numericDecimalOrNull(prev);
  if (exactCurrent === null && exactPrevious === null) {
    const current = nativeToNumber(cur);
    const previous = nativeToNumber(prev);
    if (current === null || previous === null) return null;
    if (kind === "rateBp") {
      if (cur.unit !== prev.unit) return null;
      const deltaBp = (current - previous) * (cur.unit === "bp" ? 1 : 10_000);
      const roundedBp = Math.round(deltaBp * 10) / 10;
      const displayBp = roundedBp === 0 ? 0 : roundedBp;
      return `${displayBp > 0 ? "+" : ""}${displayBp.toFixed(1)}bp`;
    }
    const deltaYi = (current - previous) / 1e8;
    return `${deltaYi > 0 ? "+" : ""}${deltaYi.toFixed(2)} 亿`;
  }

  const current = exactCurrent ?? nativeToDecimal(cur);
  const previous = exactPrevious ?? nativeToDecimal(prev);
  if (current === null || previous === null) return null;
  if (kind === "rateBp") {
    // Spread KPIs arrive either as a decimal ratio or already in bp; comparing across
    // the two bases would silently scale the delta by 10,000.
    if (cur.unit !== prev.unit) return null;
    const deltaBp = current.minus(previous).times(cur.unit === "bp" ? 1 : 10_000);
    // ROUND_HALF_CEIL preserves the legacy Math.round(x * 10) / 10 tie direction;
    // replacing Decimal zero with a fresh positive zero keeps rounded noise from
    // rendering as "-0.0bp".
    const roundedBp = deltaBp.toDecimalPlaces(1, Decimal.ROUND_HALF_CEIL);
    const displayBp = roundedBp.isZero() ? new Decimal(0) : roundedBp;
    return `${momSignPrefix(displayBp)}${displayBp.toFixed(1)}bp`;
  }
  const deltaYi = current.minus(previous).dividedBy("1e8");
  return `${momSignPrefix(deltaYi)}${deltaYi.toFixed(2, Decimal.ROUND_HALF_UP)} 亿`;
}

/**
 * Structure-pie categories whose backend `percentage` is missing fall back to a
 * client-computed value/total share. Rounding each category's share to 2 decimals
 * independently lets the displayed set drift off 100.00% (e.g. 99.99%/100.01%).
 *
 * This computes a corrected share (in percent units, e.g. 23.45) for every item that
 * lacks a backend percentage, so that the fallback subset always foots to
 * `100 - (sum of any items that do have a backend percentage)`. The residual from
 * independent rounding is absorbed by the largest holding in the fallback subset
 * (the one with the biggest market value / share), since a one-hundredth-of-a-percent
 * nudge is least noticeable on the biggest slice. Items that do have a backend
 * percentage are left untouched (`null` in the result) — this only feeds the
 * degraded/fallback tooltip path.
 */
export function computeFallbackPercentages(
  items: { total_market_value: NumericLike; percentage: NumericLike }[],
): (number | null)[] {
  const hasExactInput = items.some(
    (item) =>
      numericDecimalOrNull(item.total_market_value) !== null ||
      numericDecimalOrNull(item.percentage) !== null,
  );
  if (!hasExactInput) return computeFallbackPercentagesFromRaw(items);

  const values = items.map((it) => nativeToDecimal(it.total_market_value) ?? new Decimal(0));
  const backendPercents = items.map((it) => nativeToDecimal(it.percentage));
  const fallbackIndices = backendPercents
    .map((bp, index) => (bp === null ? index : -1))
    .filter((index) => index >= 0);

  const result: (number | null)[] = items.map(() => null);
  if (fallbackIndices.length === 0) return result;

  const backendPercentSum = backendPercents.reduce<Decimal>(
    (sum, bp) => (bp === null ? sum : sum.plus(bp.times(100))),
    new Decimal(0),
  );
  const target = new Decimal(100).minus(backendPercentSum);

  const fallbackTotal = fallbackIndices.reduce(
    (sum, index) => sum.plus(values[index]),
    new Decimal(0),
  );
  const rawPercents = fallbackIndices.map((index) =>
    fallbackTotal.greaterThan(0)
      ? values[index].dividedBy(fallbackTotal).times(target)
      : new Decimal(0),
  );
  const rounded = rawPercents.map((percent) =>
    percent.toDecimalPlaces(2, Decimal.ROUND_HALF_CEIL),
  );

  let maxPos = 0;
  for (let i = 1; i < rawPercents.length; i += 1) {
    if (rawPercents[i].greaterThan(rawPercents[maxPos])) maxPos = i;
  }
  const sumOfOthers = rounded.reduce(
    (sum, value, index) => (index === maxPos ? sum : sum.plus(value)),
    new Decimal(0),
  );
  rounded[maxPos] = target
    .minus(sumOfOthers)
    .toDecimalPlaces(2, Decimal.ROUND_HALF_CEIL);

  fallbackIndices.forEach((index, i) => {
    result[index] = rounded[i].toNumber();
  });
  return result;
}

/** Preserve the pre-raw_text Number behavior for legacy-only responses. */
function computeFallbackPercentagesFromRaw(
  items: { total_market_value: NumericLike; percentage: NumericLike }[],
): (number | null)[] {
  const values = items.map((item) => nativeToNumber(item.total_market_value) ?? 0);
  const backendPercents = items.map((item) => nativeToNumber(item.percentage));
  const fallbackIndices = backendPercents
    .map((percentage, index) => (percentage === null ? index : -1))
    .filter((index) => index >= 0);

  const result: (number | null)[] = items.map(() => null);
  if (fallbackIndices.length === 0) return result;

  const backendPercentSum = backendPercents.reduce<number>(
    (sum, percentage) => (percentage === null ? sum : sum + percentage * 100),
    0,
  );
  const target = 100 - backendPercentSum;
  const fallbackTotal = fallbackIndices.reduce((sum, index) => sum + values[index], 0);
  const rawPercents = fallbackIndices.map((index) =>
    fallbackTotal > 0 ? (values[index] / fallbackTotal) * target : 0,
  );
  const rounded = rawPercents.map((percentage) => Math.round(percentage * 100) / 100);

  let maxPos = 0;
  for (let i = 1; i < rawPercents.length; i += 1) {
    if (rawPercents[i] > rawPercents[maxPos]) maxPos = i;
  }
  const sumOfOthers = rounded.reduce(
    (sum, value, index) => (index === maxPos ? sum : sum + value),
    0,
  );
  rounded[maxPos] = Math.round((target - sumOfOthers) * 100) / 100;

  fallbackIndices.forEach((index, position) => {
    result[index] = rounded[position];
  });
  return result;
}
