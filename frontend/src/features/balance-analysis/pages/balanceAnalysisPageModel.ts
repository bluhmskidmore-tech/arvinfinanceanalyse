/** Minimum bar width (%) used by workbook distribution / gap panels (matches BalanceAnalysisPage). */
export const BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT = 14;

export type BalanceChartMagnitude =
  | { kind: "missing" }
  | { kind: "invalid"; raw: string }
  | { kind: "finite"; value: number };

function stripThousandsSeparators(raw: string): string {
  return raw.replace(/,/g, "").trim();
}

/** Full-string numeric match so `parseFloat("12abc") === 12` cannot slip through as valid. */
const STRICT_DISPLAY_FINITE_NUMBER = /^-?(?:\d+(?:\.\d*)?|\.\d+)$/;

function strictFiniteNumberFromDisplayText(text: string): number | null {
  if (text === "") {
    return null;
  }
  if (!STRICT_DISPLAY_FINITE_NUMBER.test(text)) {
    return null;
  }
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

function finiteNumberFromOverviewInput(raw: string | number): number | null {
  if (typeof raw === "number") {
    return Number.isFinite(raw) ? raw : null;
  }
  const text = stripThousandsSeparators(raw);
  return strictFiniteNumberFromDisplayText(text);
}

/**
 * Typed workbook/chart magnitude parse. Does not coerce invalid input to 0.
 * Missing: null, undefined, or whitespace-only string after comma strip.
 */
export function parseBalanceChartMagnitude(value: unknown): BalanceChartMagnitude {
  if (value === null || value === undefined) {
    return { kind: "missing" };
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? { kind: "finite", value } : { kind: "invalid", raw: String(value) };
  }
  const asString = String(value);
  const text = stripThousandsSeparators(asString);
  if (text === "") {
    return { kind: "missing" };
  }
  const parsed = strictFiniteNumberFromDisplayText(text);
  if (parsed === null) {
    return { kind: "invalid", raw: asString };
  }
  return { kind: "finite", value: parsed };
}

/**
 * Max scale for chart widths: largest absolute value among finite magnitudes, else 1.
 * Ignores missing/invalid so bad cells do not shrink the scale toward 0.
 */
export function maxAbsFiniteChartScale(values: readonly unknown[]): number {
  let maxAbs = 0;
  for (const v of values) {
    const m = parseBalanceChartMagnitude(v);
    if (m.kind === "finite") {
      const a = Math.abs(m.value);
      if (a > maxAbs) {
        maxAbs = a;
      }
    }
  }
  return maxAbs > 0 ? maxAbs : 1;
}

/**
 * Max positive scale for nonnegative workbook bars (distribution, rating blocks).
 */
export function maxFiniteChartScale(values: readonly unknown[]): number {
  let max = 0;
  for (const v of values) {
    const m = parseBalanceChartMagnitude(v);
    if (m.kind === "finite" && m.value > max) {
      max = m.value;
    }
  }
  return max > 0 ? max : 1;
}

/**
 * Bar width for distribution-style panels. Null when magnitude is missing/invalid (not a real zero bar).
 */
export function distributionChartBarWidthPercent(
  magnitude: BalanceChartMagnitude,
  maxAmongFinite: number,
): number | null {
  if (magnitude.kind !== "finite") {
    return null;
  }
  const denom = maxAmongFinite > 0 ? maxAmongFinite : 1;
  const pct = (magnitude.value / denom) * 100;
  return Math.max(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT, pct);
}

/**
 * Maturity-gap style: width from absolute magnitude; null if missing/invalid.
 */
export function gapChartBarWidthPercent(
  magnitude: BalanceChartMagnitude,
  maxAbsAmongFinite: number,
): number | null {
  if (magnitude.kind !== "finite") {
    return null;
  }
  const denom = maxAbsAmongFinite > 0 ? maxAbsAmongFinite : 1;
  const pct = (Math.abs(magnitude.value) / denom) * 100;
  return Math.max(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT, pct);
}

/** Workbook cell / label display: null, undefined, empty string → em dash. */
export function formatBalanceWorkbookCellDisplay(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

/** Overview-style integer grouping; missing → "—"; invalid → original string. */
export function formatBalanceOverviewNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return n.toLocaleString("zh-CN");
}

/** Yuan → 亿元 display (2 decimals, zh-CN). */
export function formatBalanceAmountToYiFromYuan(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return (n / 100_000_000).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** 万元 → 亿元 display (2 decimals, zh-CN). */
export function formatBalanceAmountToYiFromWan(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return (n / 10_000).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Core AG Grid value formatter: null/undefined/"" → "—"; invalid → original string; else zh-CN grouped.
 */
export function formatBalanceGridThousandsValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString("zh-CN") : String(value);
  }
  const text = stripThousandsSeparators(String(value));
  const n = strictFiniteNumberFromDisplayText(text);
  if (n === null) {
    return String(value);
  }
  return n.toLocaleString("zh-CN");
}
