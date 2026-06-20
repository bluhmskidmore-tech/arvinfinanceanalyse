import type { LivermoreSectorRankSeriesPoint } from "../../../api/contracts";

export type SectorSeriesTrendLine = {
  sectorCode: string;
  sectorName: string;
  dates: string[];
  scores: Array<number | null>;
};

export function sectorRankUnavailable(
  strategyPayload: { sector_rank?: { formula_version?: string; items?: unknown[] } } | null,
) {
  const sectorRank = strategyPayload?.sector_rank;
  return (
    sectorRank == null ||
    !sectorRank.formula_version?.trim() ||
    !Array.isArray(sectorRank.items) ||
    sectorRank.items.length === 0
  );
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

export function buildSectorSeriesTrendLines(
  series: LivermoreSectorRankSeriesPoint[],
  topK = 5,
): SectorSeriesTrendLine[] {
  const latestRows = latestSectorSeriesTableRows(series);
  const topCodes = latestRows.slice(0, topK).map((row) => row.sector_code);
  const byCode = new Map<string, LivermoreSectorRankSeriesPoint[]>();

  for (const row of series) {
    if (!topCodes.includes(row.sector_code)) {
      continue;
    }
    const bucket = byCode.get(row.sector_code) ?? [];
    bucket.push(row);
    byCode.set(row.sector_code, bucket);
  }

  return topCodes.map((code) => {
    const rows = (byCode.get(code) ?? []).sort((left, right) =>
      left.trade_date.localeCompare(right.trade_date),
    );
    const latest = latestRows.find((row) => row.sector_code === code);
    return {
      sectorCode: code,
      sectorName: latest?.sector_name ?? code,
      dates: rows.map((row) => row.trade_date),
      scores: rows.map((row) => row.score),
    };
  });
}

export function localizeSectorSeriesUnsupportedNote(note: string): string {
  const lower = note.trim().toLowerCase();
  if (lower.includes("momentum_persistence")) {
    return "动量持续度：口径待评审（P1）";
  }
  if (lower.includes("sector_money_flow")) {
    return "板块资金流向：待 vendor 审批与新 schema（P1）";
  }
  return note.replace(/_/g, " ");
}

export function localizeSectorSeriesUnsupportedNotes(notes: string[] | null | undefined): string[] {
  return (notes ?? []).map(localizeSectorSeriesUnsupportedNote).filter((note) => note.trim().length > 0);
}

export function formatSectorSeriesScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(4);
}

export function formatSectorSeriesPctChange(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatSectorSeriesCumPctChange(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}
