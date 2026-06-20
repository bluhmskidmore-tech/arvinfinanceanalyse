import type { Numeric } from "../../../api/contracts";

type NumericLike = Numeric | number | null | undefined;

/** Read Numeric.raw without converting missing governed data into zero. */
export function nativeToNumber(value: NumericLike): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (value?.raw === null || value?.raw === undefined || !Number.isFinite(value.raw)) {
    return null;
  }
  return value.raw;
}

/** Governed yuan field -> yi display for cards/tables. */
export function formatYi(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return "—";
  return (raw / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Governed ratio/pct field -> percent display. */
export function formatRatePercent(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return "—";
  return (raw * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Governed DV01 yuan field -> wan-yuan display. */
export function formatDv01Wan(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return "—";
  return (raw / 1e4).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatYears(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return "—";
  return raw.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatMomRatio(cur: Numeric | null | undefined, prev: Numeric | null | undefined): string | null {
  if (!prev) return null;
  const current = nativeToNumber(cur);
  const previous = nativeToNumber(prev);
  if (current === null || previous === null || previous === 0) return null;
  const pct = ((current - previous) / previous) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}
