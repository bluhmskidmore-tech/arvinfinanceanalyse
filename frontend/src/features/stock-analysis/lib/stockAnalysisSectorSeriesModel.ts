import type { LivermoreSectorRankSeriesPoint } from "../../../api/contracts";

export function sectorRankUnavailable(
  strategyPayload: { sector_rank?: { formula_version?: string; items?: unknown[] } } | null,
) {
  const items = strategyPayload?.sector_rank?.items ?? [];
  const formulaVersion = strategyPayload?.sector_rank?.formula_version;
  return items.length === 0 || formulaVersion == null || String(formulaVersion).trim() === "";
}

export function latestSectorSeriesTableRows(
  series: LivermoreSectorRankSeriesPoint[],
): LivermoreSectorRankSeriesPoint[] {
  const byCode = new Map<string, LivermoreSectorRankSeriesPoint>();
  for (const row of series) {
    const current = byCode.get(row.sector_code);
    if (!current || row.trade_date > current.trade_date) {
      byCode.set(row.sector_code, row);
    }
  }
  return Array.from(byCode.values()).sort((left, right) => {
    const leftRank = left.rank ?? 9999;
    const rightRank = right.rank ?? 9999;
    return leftRank - rightRank;
  });
}
