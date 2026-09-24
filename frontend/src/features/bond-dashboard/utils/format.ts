import type { Numeric } from "../../../api/contracts";
import { EM_DASH, numericRaw } from "../../../pageModel";

type NumericLike = Numeric | number | null | undefined;

/** Read Numeric.raw without converting missing governed data into zero. */
export function nativeToNumber(value: NumericLike): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  return numericRaw(value);
}

/** Governed yuan field -> yi display for cards/tables. */
export function formatYi(value: NumericLike, digits = 2): string {
  const raw = nativeToNumber(value);
  if (raw === null) return EM_DASH;
  return (raw / 1e8).toLocaleString("zh-CN", {
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
  if (!prev) return null;
  const current = nativeToNumber(cur);
  const previous = nativeToNumber(prev);
  if (current === null || previous === null || previous === 0) return null;
  const pct = ((current - previous) / Math.abs(previous)) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

/**
 * How a KPI's month-over-month change must be expressed.
 * - `percent`: level amounts, where a relative change is meaningful
 * - `rateBp`: yields/coupons/spreads, where the market convention is a bp difference
 *   (2.50% -> 2.60% is +10.0bp, not +4.00%)
 * - `amountYi`: sign-variable P&L, where a ratio over a possibly negative base misleads
 */
export type BondKpiMomKind = "percent" | "rateBp" | "amountYi";

function momSignPrefix(delta: number): string {
  return delta > 0 ? "+" : "";
}

export function formatMomChange(
  kind: BondKpiMomKind,
  cur: Numeric | null | undefined,
  prev: Numeric | null | undefined,
): string | null {
  if (kind === "percent") return formatMomRatio(cur, prev);
  if (!cur || !prev) return null;
  const current = nativeToNumber(cur);
  const previous = nativeToNumber(prev);
  if (current === null || previous === null) return null;
  if (kind === "rateBp") {
    // Spread KPIs arrive either as a decimal ratio or already in bp; comparing across
    // the two bases would silently scale the delta by 10,000.
    if (cur.unit !== prev.unit) return null;
    const deltaBp = (current - previous) * (cur.unit === "bp" ? 1 : 10_000);
    return `${momSignPrefix(deltaBp)}${deltaBp.toFixed(1)}bp`;
  }
  const deltaYi = (current - previous) / 1e8;
  return `${momSignPrefix(deltaYi)}${deltaYi.toFixed(2)} 亿`;
}
