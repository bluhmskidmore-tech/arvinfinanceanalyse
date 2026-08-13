export function computeComparisonDeviationPct(
  spotBalance: number | null,
  avgBalance: number | null,
): number | null {
  if (spotBalance === null || Number.isNaN(spotBalance)) return null;
  if (avgBalance === null || Number.isNaN(avgBalance)) return null;
  return avgBalance > 0 ? ((spotBalance - avgBalance) / avgBalance) * 100 : 0;
}
