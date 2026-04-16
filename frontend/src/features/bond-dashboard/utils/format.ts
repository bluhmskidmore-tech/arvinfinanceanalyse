/** Format backend decimal strings (native CNY amounts) for display. */

export function nativeToNumber(s: string): number {
  const n = Number.parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}

/** 原币 → 亿元 */
export function formatYi(s: string, digits = 2): string {
  return (nativeToNumber(s) / 1e8).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** 小数利率 → 百分比显示 */
export function formatRatePercent(s: string, digits = 2): string {
  return (nativeToNumber(s) * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** DV01 原币（元）→ 万元 */
export function formatDv01Wan(s: string, digits = 2): string {
  return (nativeToNumber(s) / 1e4).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatYears(s: string, digits = 2): string {
  return nativeToNumber(s).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatMomRatio(cur: string, prev: string | undefined): string | null {
  if (prev === undefined) return null;
  const a = nativeToNumber(cur);
  const b = nativeToNumber(prev);
  if (b === 0) return null;
  const pct = ((a - b) / b) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}
