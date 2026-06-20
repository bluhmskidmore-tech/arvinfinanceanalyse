/** 以余额占比（0–1）计算 Top10 合计与 HHI（0–10000 常用口径）。 */
export function concentrationMetrics(weights: number[]): {
  top10Share: number;
  hhiTimes10000: number;
} {
  const w = weights.filter((x) => Number.isFinite(x) && x >= 0);
  const sum = w.reduce((a, b) => a + b, 0);
  if (sum <= 0) {
    return { top10Share: 0, hhiTimes10000: 0 };
  }
  const shares = w.map((x) => x / sum);
  const sorted = [...shares].sort((a, b) => b - a);
  const top10Share = sorted.slice(0, 10).reduce((a, b) => a + b, 0);
  const hhi = shares.reduce((s, x) => s + x * x, 0);
  return { top10Share, hhiTimes10000: hhi * 10000 };
}
