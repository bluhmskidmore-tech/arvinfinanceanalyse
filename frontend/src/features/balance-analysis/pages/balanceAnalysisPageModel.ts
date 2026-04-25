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
const STRICT_DISPLAY_FINITE_NUMBER = /^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

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

export type BalanceScopeAmountKey =
  | "marketValueAmount"
  | "amortizedCostAmount"
  | "accruedInterestAmount";

export type BalanceScopeAmountTotals = {
  rowCount: number;
  hasRows: boolean;
  marketValueAmount: number | null;
  amortizedCostAmount: number | null;
  accruedInterestAmount: number | null;
};

type BalanceScopeSummaryInput = {
  position_scope?: unknown;
  row_count?: unknown;
  market_value_amount?: unknown;
  amortized_cost_amount?: unknown;
  accrued_interest_amount?: unknown;
};

function createEmptyScopeTotals(): BalanceScopeAmountTotals {
  return {
    rowCount: 0,
    hasRows: false,
    marketValueAmount: 0,
    amortizedCostAmount: 0,
    accruedInterestAmount: 0,
  };
}

function finiteNumberFromUnknown(value: unknown): number | null {
  if (typeof value !== "string" && typeof value !== "number") {
    return null;
  }
  return finiteNumberFromOverviewInput(value);
}

function addFiniteAmount(current: number | null, value: unknown): number | null {
  if (current === null) {
    return null;
  }
  const n = finiteNumberFromUnknown(value);
  return n === null ? null : current + n;
}

export function summarizeBalanceAmountsByPositionScope(
  rows: readonly BalanceScopeSummaryInput[],
): Record<"asset" | "liability", BalanceScopeAmountTotals> {
  const totals = {
    asset: createEmptyScopeTotals(),
    liability: createEmptyScopeTotals(),
  };

  for (const row of rows) {
    if (row.position_scope !== "asset" && row.position_scope !== "liability") {
      continue;
    }
    const bucket = totals[row.position_scope];
    bucket.hasRows = true;
    const rowCount = finiteNumberFromUnknown(row.row_count);
    bucket.rowCount += rowCount === null ? 0 : rowCount;
    bucket.marketValueAmount = addFiniteAmount(bucket.marketValueAmount, row.market_value_amount);
    bucket.amortizedCostAmount = addFiniteAmount(bucket.amortizedCostAmount, row.amortized_cost_amount);
    bucket.accruedInterestAmount = addFiniteAmount(bucket.accruedInterestAmount, row.accrued_interest_amount);
  }

  return totals;
}

export function formatBalanceScopeTotalAmountToYi(
  totals: BalanceScopeAmountTotals,
  amountKey: BalanceScopeAmountKey,
): string {
  if (!totals.hasRows) {
    return "—";
  }
  const value = totals[amountKey];
  return value === null ? "—" : formatBalanceAmountToYiFromYuan(value);
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

/** Workbook wan-yuan amount cell display with unit, preserving invalid source text. */
export function formatBalanceWorkbookWanAmountDisplay(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  if (typeof raw !== "string" && typeof raw !== "number") {
    return String(raw);
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return `${formatBalanceAmountToYiFromWan(raw)} 亿元`;
}

const WORKBOOK_WAN_YUAN_TEXT_PATTERN = /(-?(?:\d[\d,]*(?:\.\d*)?|\.\d+))\s*(?:wan yuan|万元)/gi;

/** Workbook governed prose display: replace embedded wan-yuan amounts with yi-yuan amounts. */
export function formatBalanceWorkbookWanTextDisplay(value: unknown): string {
  const text = formatBalanceWorkbookCellDisplay(value);
  if (text === "—") {
    return text;
  }
  return text.replace(WORKBOOK_WAN_YUAN_TEXT_PATTERN, (_match, rawAmount: string) =>
    formatBalanceWorkbookWanAmountDisplay(rawAmount),
  );
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
