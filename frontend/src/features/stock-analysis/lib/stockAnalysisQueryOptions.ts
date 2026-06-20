import type { LivermoreStrategyScorePayload } from "../../../api/contracts";

const STOCK_ANALYSIS_STALE_TIME_MS = 5 * 60_000;
const STOCK_ANALYSIS_GC_TIME_MS = 15 * 60_000;

export const stockAnalysisReadQueryOptions = {
  staleTime: STOCK_ANALYSIS_STALE_TIME_MS,
  gcTime: STOCK_ANALYSIS_GC_TIME_MS,
  refetchOnWindowFocus: false,
} as const;

export const EMPTY_STRATEGY_PRIORITY_ROWS: LivermoreStrategyScorePayload["rows"] = [];
