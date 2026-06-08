export function computeComparisonDeviationPct(
  spotBalance: number,
  avgBalance: number | null,
): number | null {
  if (avgBalance === null || Number.isNaN(avgBalance)) return null;
  return avgBalance > 0 ? ((spotBalance - avgBalance) / avgBalance) * 100 : 0;
}
