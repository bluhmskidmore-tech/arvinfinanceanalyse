import type { Numeric } from "../../../api/contracts";

function coerceRaw(value: Numeric | string | number): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : Number.NaN;
  }
  if (typeof value === "string") {
    return Number.parseFloat(value);
  }
  if (value.raw === null || !Number.isFinite(value.raw)) {
    return Number.NaN;
  }
  return value.raw;
}

/** Format yuan amount to 亿 with 2 decimal places */
export const formatYi = (value: Numeric | string | number): string => {
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return "-";
  return `${(num / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
};

/** Format yuan amount to 万 with no decimal places */
export const formatWan = (value: Numeric | string | number): string => {
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return "-";
  return `${(num / 1e4).toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 万`;
};

/** Format percentage: `pct` unit uses server display; `ratio` uses raw×100 (e.g. 0.25 → 25%). */
export const formatPct = (value: Numeric | string): string => {
  if (typeof value !== "string") {
    if (value.unit === "pct" && value.display) {
      return value.display;
    }
    if (value.unit === "ratio" && value.raw !== null && Number.isFinite(value.raw)) {
      return `${(value.raw * 100).toFixed(2)}%`;
    }
  }
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return "-";
  return `${(num * 100).toFixed(2)}%`;
};

/** Format bp value */
export const formatBp = (value: Numeric | string): string => {
  if (typeof value !== "string" && value.unit === "bp" && value.display) {
    return value.display;
  }
  const num = coerceRaw(value);
  if (Number.isNaN(num)) return "-";
  return `${num.toFixed(1)} bp`;
};

/** Color for positive/negative values (China standard: red=up, green=down) */
export const toneColor = (value: number): string =>
  value >= 0 ? "#cf1322" : "#3f8600";
