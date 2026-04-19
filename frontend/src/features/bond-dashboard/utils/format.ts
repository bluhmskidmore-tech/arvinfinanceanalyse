import type { Numeric } from "../../../api/contracts";

type NumericLike = Numeric | string | number | null | undefined;

/** Read governed Numeric.raw for dashboard render math. */
export function nativeToNumber(value: NumericLike): number {
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }
  if (value?.raw === null || value?.raw === undefined || !Number.isFinite(value.raw)) {
    return 0;
  }
  return value.raw;
}

/** 鍘熷竵 鈫?浜垮厓 */
export function formatYi(value: NumericLike, digits = 2): string {
  return (nativeToNumber(value) / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** 灏忔暟鍒╃巼 鈫?鐧惧垎姣旀樉绀?*/
export function formatRatePercent(value: NumericLike, digits = 2): string {
  return (nativeToNumber(value) * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** DV01 鍘熷竵锛堝厓锛夆啋 涓囧厓 */
export function formatDv01Wan(value: NumericLike, digits = 2): string {
  return (nativeToNumber(value) / 1e4).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatYears(value: NumericLike, digits = 2): string {
  return nativeToNumber(value).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatMomRatio(cur: NumericLike, prev: NumericLike): string | null {
  if (prev === undefined || prev === null) return null;
  const a = nativeToNumber(cur);
  const b = nativeToNumber(prev);
  if (b === 0) return null;
  const pct = ((a - b) / b) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}
