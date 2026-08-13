import type {
  FactorScreenCandidatesPayload,
  LivermoreSectorRankPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export type LivermoreSectorRankRow = {
  rank: number;
  sectorName: string;
  score: number | null;
  avgPctChange: number | null;
  constituentCount: number | null;
  leaderNames: string[];
};

export type LivermoreSectorRankRowsMeta = {
  asOfDate: string;
  sectorCount: number;
  isProvisional: boolean;
  formulaVersion: string;
};

export type LivermoreSectorRankRowsResult = {
  rows: LivermoreSectorRankRow[];
  meta: LivermoreSectorRankRowsMeta;
};

export type LivermoreFactorCandidateRow = {
  rank: number;
  stockCode: string;
  stockName: string;
  sectorName: string;
  score: number | null;
  pe: number | null;
  threeMonthReturnPct: number | null;
};

export type LivermoreFactorCandidateRowsMeta = {
  asOfDate: string;
  candidateCount: number;
  inputStockCount: number;
  observationOnly: boolean;
};

export type LivermoreFactorCandidateRowsResult = {
  rows: LivermoreFactorCandidateRow[];
  meta: LivermoreFactorCandidateRowsMeta;
};

function numericOrNull(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function textOrPlaceholder(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : EM_DASH;
}

export function buildLivermoreSectorRankRows(
  result: LivermoreSectorRankPayload | null | undefined,
  limit = 12,
): LivermoreSectorRankRowsResult {
  const meta: LivermoreSectorRankRowsMeta = {
    asOfDate: textOrPlaceholder(result?.as_of_date),
    sectorCount: numericOrNull(result?.sector_count) ?? 0,
    isProvisional: Boolean(result?.is_provisional),
    formulaVersion: textOrPlaceholder(result?.formula_version),
  };
  const items = Array.isArray(result?.items) ? result.items : [];
  const rows: LivermoreSectorRankRow[] = items.slice(0, Math.max(0, limit)).map((item, index) => {
    const leaders = Array.isArray(item?.leader_constituents) ? item.leader_constituents : [];
    const leaderNames = leaders
      .slice(0, 2)
      .map((leader) => (typeof leader?.stock_name === "string" ? leader.stock_name.trim() : ""))
      .filter((name) => name.length > 0);
    return {
      rank: numericOrNull(item?.rank) ?? index + 1,
      sectorName: textOrPlaceholder(item?.sector_name),
      score: numericOrNull(item?.score),
      avgPctChange: numericOrNull(item?.avg_pctchange),
      constituentCount: numericOrNull(item?.constituent_count),
      leaderNames,
    };
  });
  return { rows, meta };
}

export function buildLivermoreFactorCandidateRows(
  result: FactorScreenCandidatesPayload | null | undefined,
  limit = 10,
): LivermoreFactorCandidateRowsResult {
  const meta: LivermoreFactorCandidateRowsMeta = {
    asOfDate: textOrPlaceholder(result?.as_of_date),
    candidateCount: numericOrNull(result?.candidate_count) ?? 0,
    inputStockCount: numericOrNull(result?.input_stock_count) ?? 0,
    observationOnly: Boolean(result?.observation_only),
  };
  const items = Array.isArray(result?.items) ? result.items : [];
  const rows: LivermoreFactorCandidateRow[] = items.slice(0, Math.max(0, limit)).map((item, index) => {
    const threeMonthReturn = numericOrNull(item?.three_month_return);
    return {
      rank: numericOrNull(item?.rank) ?? index + 1,
      stockCode: textOrPlaceholder(item?.stock_code),
      stockName: textOrPlaceholder(item?.stock_name),
      sectorName: textOrPlaceholder(item?.sector_name),
      score: numericOrNull(item?.score),
      pe: numericOrNull(item?.pe),
      threeMonthReturnPct: threeMonthReturn == null ? null : threeMonthReturn * 100,
    };
  });
  return { rows, meta };
}
