import { readHttpJsonDetail } from "./httpResponseError";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroRefreshPayload,
  ChoiceNewsEventsPayload,
  ExternalDataWatermarkLedger,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  MarketDataBondFuturesRankingsPayload,
  MarketDataCatalogPayload,
  MarketDataCoverageSummaryPayload,
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreManualPositionInput,
  LivermoreCandidateHistoryPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermorePositionSnapshotPayload,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  LivermoreStockDetailPayload,
  LivermoreStrategyPayload,
  MacroBondLinkagePayload,
  NcdFundingProxyPayload,
  TushareSupplementPayload,
  ResearchCalendarEvent,
  ResearchCalendarResultPayload,
  SourcePreviewHistoryPayload,
  SourcePreviewPayload,
  SourcePreviewRefreshPayload,
  SourcePreviewRowsPayload,
  SourcePreviewTracesPayload,
  StockAnalysisWorkbenchPayload,
  StockKlineAnalysisPayload,
} from "./contracts";
import { mapResearchCalendarApiEvent } from "../lib/researchCalendarApiEvent";

type FetchLike = typeof fetch;

type MarketDataClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

export type LivermoreGateSupplementRefreshAcceptance = {
  status:
    | "queued"
    | "running"
    | "retrying"
    | "completed"
    | "failed"
    | "partial"
    | "insufficient_data"
    | "no_computable_dates";
  run_id: string;
  trigger_mode: "async" | "terminal";
  as_of_date: string | null;
  lookback_days: number | null;
  queued_at: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  computed_rows?: number | null;
  first_date?: string | null;
  last_date?: string | null;
  basis?: string | null;
  message?: string | null;
  failure_category?: string | null;
  failure_reason?: string | null;
  error_message?: string | null;
  idempotency_key: string | null;
  idempotency_replay: boolean;
};

/**
 * Market Data domain methods and their mock/real factories.
 */
export type MarketDataClientMethods = {
  getSourceFoundation: () => Promise<ApiEnvelope<SourcePreviewPayload>>;
  refreshSourcePreview: () => Promise<SourcePreviewRefreshPayload>;
  getSourcePreviewRefreshStatus: (runId: string) => Promise<SourcePreviewRefreshPayload>;
  getSourceFoundationHistory: (options: {
    sourceFamily?: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewHistoryPayload>>;
  getSourceFoundationRows: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewRowsPayload>>;
  getSourceFoundationTraces: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewTracesPayload>>;
  getMacroFoundation: () => Promise<ApiEnvelope<MarketDataCatalogPayload>>;
  getChoiceMacroLatest: () => Promise<ApiEnvelope<ChoiceMacroLatestPayload>>;
  getExternalDataWatermarks: () => Promise<ExternalDataWatermarkLedger>;
  getMacroBondLinkageAnalysis: (options: {
    reportDate: string;
  }) => Promise<ApiEnvelope<MacroBondLinkagePayload>>;
  getBondFuturesRankings: (options?: {
    contract?: string;
    tradeDate?: string;
    limit?: number;
  }) => Promise<ApiEnvelope<MarketDataBondFuturesRankingsPayload>>;
  getMarketDataCoverageSummary: () => Promise<ApiEnvelope<MarketDataCoverageSummaryPayload>>;
  getNcdFundingProxy: () => Promise<ApiEnvelope<NcdFundingProxyPayload>>;
  getTushareSupplement: (options?: {
    moneySupplyLimit?: number;
    ecoCalLimit?: number;
  }) => Promise<ApiEnvelope<TushareSupplementPayload>>;
  getFxFormalStatus: () => Promise<ApiEnvelope<FxFormalStatusPayload>>;
  getFxAnalytical: () => Promise<ApiEnvelope<FxAnalyticalPayload>>;
  refreshChoiceMacro: (backfillDays?: number) => Promise<ChoiceMacroRefreshPayload>;
  getChoiceMacroRefreshStatus: (runId: string) => Promise<ChoiceMacroRefreshPayload>;
  getLivermoreStrategy: (options?: {
    asOfDate?: string;
  }) => Promise<ApiEnvelope<LivermoreStrategyPayload>>;
  getStockAnalysisWorkbench: (options?: {
    asOfDate?: string;
    include?: string[];
    sectorWindowDays?: number;
    topK?: number;
  }) => Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>>;
  getLivermoreStockDetail: (options: {
    stockCode: string;
    asOfDate?: string;
    lookback?: number;
  }) => Promise<ApiEnvelope<LivermoreStockDetailPayload>>;
  getStockKlineAnalysis: (options: {
    stockCode: string;
    asOfDate?: string;
    lookback?: number;
  }) => Promise<ApiEnvelope<StockKlineAnalysisPayload>>;
  getLivermoreCandidateHistory: (options?: {
    stockCode?: string;
    snapshotFrom?: string;
    snapshotTo?: string;
    evaluationAsOfDate?: string;
    limit?: number;
  }) => Promise<ApiEnvelope<LivermoreCandidateHistoryPayload>>;
  getLivermoreStrategyScore: (options?: {
    snapshotFrom?: string;
    snapshotTo?: string;
    currentMarketState?: string;
    minSample?: number;
    primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
  }) => Promise<ApiEnvelope<LivermoreStrategyScorePayload>>;
  getLivermoreStrategyOptimization: (options?: {
    snapshotFrom?: string;
    snapshotTo?: string;
    currentMarketState?: string;
    minSample?: number;
    primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
  }) => Promise<ApiEnvelope<LivermoreStrategyOptimizationPayload>>;
  getLivermoreCycleProxyBacktest: (options?: {
    snapshotFrom?: string;
    snapshotTo?: string;
  }) => Promise<ApiEnvelope<LivermoreCycleProxyBacktestPayload>>;
  getLivermoreCandidateHistoryPortfolioBacktest: (options?: {
    snapshotFrom?: string;
    snapshotTo?: string;
  }) => Promise<ApiEnvelope<LivermoreCandidateHistoryPortfolioBacktestPayload>>;
  getLivermoreSectorRankSeries: (options?: {
    asOfDate?: string;
    windowDays?: number;
    sectorCode?: string;
    topK?: number;
  }) => Promise<ApiEnvelope<LivermoreSectorRankSeriesPayload>>;
  getLivermoreSignalConfluence: (options?: {
    asOfDate?: string;
  }) => Promise<ApiEnvelope<LivermoreSignalConfluencePayload>>;
  materializeLivermorePositionSnapshot: (options: {
    asOfDate: string;
    csvPath: string;
  }) => Promise<LivermorePositionSnapshotPayload>;
  materializeLivermoreManualPositionSnapshot: (options: {
    asOfDate: string;
    positions: LivermoreManualPositionInput[];
  }) => Promise<LivermorePositionSnapshotPayload>;
  getLivermoreGateSupplementRefreshStatus: (
    runId: string,
  ) => Promise<LivermoreGateSupplementRefreshAcceptance>;
  refreshGateSupplement: (options?: {
    asOfDate?: string;
    lookbackDays?: number;
  }) => Promise<LivermoreGateSupplementRefreshAcceptance>;
  getChoiceNewsEvents: (options: {
    limit: number;
    offset: number;
    groupId?: string;
    topicCode?: string;
    stockCode?: string;
    errorOnly?: boolean;
    receivedFrom?: string;
    receivedTo?: string;
  }) => Promise<ApiEnvelope<ChoiceNewsEventsPayload>>;
  ingestTushareNprNews: (options?: { limit?: number }) => Promise<{
    status: string;
    inserted: number;
    skipped_duplicates: number;
    fetched: number;
    npr: { inserted: number; skipped_duplicates: number; fetched: number };
    news: { inserted: number; skipped_duplicates: number; fetched: number; src: string; error?: string };
  }>;
  getResearchCalendarEvents: (options?: {
    reportDate?: string;
    startDate?: string;
    endDate?: string;
  }) => Promise<ResearchCalendarEvent[]>;
  getMarketDataRates: () => Promise<ApiEnvelope<ChoiceMacroLatestPayload>>;
  getMarketDataCatalog: () => Promise<ApiEnvelope<MarketDataCatalogPayload>>;
};

export type MarketDataDomainClientMethods = MarketDataClientMethods;

function buildLivermoreQuery(options?: { asOfDate?: string }) {
  const asOfDate = options?.asOfDate?.trim();
  if (!asOfDate) {
    return "";
  }
  return `?as_of_date=${encodeURIComponent(asOfDate)}`;
}

function buildStockAnalysisWorkbenchQuery(options?: {
  asOfDate?: string;
  include?: string[];
  sectorWindowDays?: number;
  topK?: number;
}) {
  const params = new URLSearchParams();
  const asOfDate = options?.asOfDate?.trim();
  if (asOfDate) {
    params.set("as_of_date", asOfDate);
  }
  const include = options?.include?.map((item) => item.trim()).filter(Boolean);
  if (include?.length) {
    params.set("include", include.join(","));
  }
  if (options?.sectorWindowDays != null) {
    params.set("sector_window_days", String(options.sectorWindowDays));
  }
  if (options?.topK != null) {
    params.set("top_k", String(options.topK));
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

function buildBondFuturesRankingsQuery(options?: {
  contract?: string;
  tradeDate?: string;
  limit?: number;
}) {
  const params = new URLSearchParams();
  const contract = options?.contract?.trim();
  if (contract) {
    params.set("contract", contract);
  }
  const tradeDate = options?.tradeDate?.trim();
  if (tradeDate) {
    params.set("trade_date", tradeDate);
  }
  if (options?.limit != null) {
    params.set("limit", String(options.limit));
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

function buildStockDetailQuery(options: { stockCode: string; asOfDate?: string; lookback?: number }) {
  const params = new URLSearchParams();
  params.set("stock_code", options.stockCode.trim());
  const asOf = options.asOfDate?.trim();
  if (asOf) {
    params.set("as_of_date", asOf);
  }
  if (options.lookback != null) {
    params.set("lookback", String(options.lookback));
  }
  return `?${params.toString()}`;
}

function buildSectorRankSeriesQuery(options?: {
  asOfDate?: string;
  windowDays?: number;
  sectorCode?: string;
  topK?: number;
}) {
  const params = new URLSearchParams();
  const asOf = options?.asOfDate?.trim();
  if (asOf) {
    params.set("as_of_date", asOf);
  }
  if (options?.windowDays != null) {
    params.set("window_days", String(options.windowDays));
  }
  const code = options?.sectorCode?.trim();
  if (code) {
    params.set("sector_code", code);
  }
  if (options?.topK != null) {
    params.set("top_k", String(options.topK));
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

function buildCandidateHistoryQuery(options?: {
  stockCode?: string;
  snapshotFrom?: string;
  snapshotTo?: string;
  evaluationAsOfDate?: string;
  limit?: number;
}) {
  const params = new URLSearchParams();
  const code = options?.stockCode?.trim();
  if (code) {
    params.set("stock_code", code);
  }
  const sf = options?.snapshotFrom?.trim();
  if (sf) {
    params.set("snapshot_from", sf);
  }
  const st = options?.snapshotTo?.trim();
  if (st) {
    params.set("snapshot_to", st);
  }
  const evaluationAsOfDate = options?.evaluationAsOfDate?.trim();
  if (evaluationAsOfDate) {
    params.set("evaluation_as_of_date", evaluationAsOfDate);
  }
  if (options?.limit != null) {
    params.set("limit", String(options.limit));
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

function buildStrategyScoreQuery(options?: {
  snapshotFrom?: string;
  snapshotTo?: string;
  currentMarketState?: string;
  minSample?: number;
  primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
}) {
  const params = new URLSearchParams();
  const sf = options?.snapshotFrom?.trim();
  if (sf) {
    params.set("snapshot_from", sf);
  }
  const st = options?.snapshotTo?.trim();
  if (st) {
    params.set("snapshot_to", st);
  }
  const state = options?.currentMarketState?.trim();
  if (state) {
    params.set("current_market_state", state);
  }
  if (options?.minSample != null) {
    params.set("min_sample", String(options.minSample));
  }
  if (options?.primaryHorizon) {
    params.set("primary_horizon", options.primaryHorizon);
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

function buildSnapshotWindowQuery(options?: {
  snapshotFrom?: string;
  snapshotTo?: string;
}) {
  const params = new URLSearchParams();
  const sf = options?.snapshotFrom?.trim();
  if (sf) {
    params.set("snapshot_from", sf);
  }
  const st = options?.snapshotTo?.trim();
  if (st) {
    params.set("snapshot_to", st);
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  readonly errorMessage?: string;
  readonly detail?: unknown;

  constructor(
    message: string,
    opts: {
      status: number;
      runId?: string;
      errorMessage?: string;
      detail?: unknown;
    },
  ) {
    super(message);
    this.name = "ActionRequestError";
    this.status = opts.status;
    this.runId = opts.runId;
    this.errorMessage = opts.errorMessage;
    this.detail = opts.detail;
  }
}

function extractApiRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const top = body.run_id;
  if (typeof top === "string" && top.trim()) {
    return top;
  }
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = (detail as Record<string, unknown>).run_id;
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }
  return undefined;
}

function extractTopLevelErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const errMsg = (payload as Record<string, unknown>).error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  return undefined;
}

function extractApiErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const errMsg = body.error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = detail as Record<string, unknown>;
    const nestedMsg = nested.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = nested.detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    const joined = parts.filter((part) => part.trim()).join("; ");
    return joined || undefined;
  }
  return undefined;
}

function extractRawDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  if (!("detail" in (payload as Record<string, unknown>))) {
    return undefined;
  }
  return (payload as Record<string, unknown>).detail;
}

export function createRealMarketDataClient({
  fetchImpl,
  baseUrl,
}: MarketDataClientFactoryOptions): MarketDataDomainClientMethods {
  return {
    getSourceFoundation: () =>
      requestJson<SourcePreviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation",
      ),
    refreshSourcePreview: () =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation/refresh",
        {
          method: "POST",
        },
      ),
    getSourcePreviewRefreshStatus: (runId: string) =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getSourceFoundationHistory: ({ sourceFamily, limit, offset }) => {
      const params = new URLSearchParams();
      if (sourceFamily?.trim()) {
        params.set("source_family", sourceFamily);
      }
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      return requestJson<SourcePreviewHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/history?${params.toString()}`,
      );
    },
    getSourceFoundationRows: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewRowsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/rows?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getSourceFoundationTraces: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewTracesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/traces?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getMacroFoundation: () =>
      requestJson<MarketDataCatalogPayload>(fetchImpl, baseUrl, "/ui/market-data/catalog"),
    getChoiceMacroLatest: () =>
      requestJson<ChoiceMacroLatestPayload>(fetchImpl, baseUrl, "/ui/macro/choice-series/latest"),
    getExternalDataWatermarks: () =>
      requestPlainJson<ExternalDataWatermarkLedger>(
        fetchImpl,
        baseUrl,
        "/api/external-data/watermarks",
      ),
    getMacroBondLinkageAnalysis: ({ reportDate }) =>
      requestJson<MacroBondLinkagePayload>(
        fetchImpl,
        baseUrl,
        `/api/macro-bond-linkage/analysis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondFuturesRankings: (options) =>
      requestJson<MarketDataBondFuturesRankingsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/bond-futures/rankings${buildBondFuturesRankingsQuery(options)}`,
      ),
    getMarketDataCoverageSummary: () =>
      requestJson<MarketDataCoverageSummaryPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/coverage-summary",
      ),
    getNcdFundingProxy: () =>
      requestJson<NcdFundingProxyPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/ncd-funding-proxy",
      ),
    getTushareSupplement: (options) => {
      const params = new URLSearchParams();
      if (options?.moneySupplyLimit != null) {
        params.set("money_supply_limit", String(options.moneySupplyLimit));
      }
      if (options?.ecoCalLimit != null) {
        params.set("eco_cal_limit", String(options.ecoCalLimit));
      }
      const query = params.toString();
      return requestJson<TushareSupplementPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/tushare-supplement${query ? `?${query}` : ""}`,
      );
    },
    getFxFormalStatus: () =>
      requestJson<FxFormalStatusPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/fx/formal-status",
      ),
    getFxAnalytical: () =>
      requestJson<FxAnalyticalPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/fx/analytical",
      ),
    refreshChoiceMacro: (backfillDays?: number) => {
      const query = backfillDays ? `?backfill_days=${backfillDays}` : "";
      return requestActionJson<ChoiceMacroRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/choice-series/refresh${query}`,
        { method: "POST" },
      );
    },
    getChoiceMacroRefreshStatus: (runId: string) =>
      requestActionJson<ChoiceMacroRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/choice-series/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getLivermoreStrategy: (options?: { asOfDate?: string }) =>
      requestJson<LivermoreStrategyPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore${buildLivermoreQuery(options)}`,
      ),
    getStockAnalysisWorkbench: (options?: {
      asOfDate?: string;
      include?: string[];
      sectorWindowDays?: number;
      topK?: number;
    }) =>
      requestJson<StockAnalysisWorkbenchPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/stock-analysis/workbench${buildStockAnalysisWorkbenchQuery(options)}`,
      ),
    getLivermoreStockDetail: (options: { stockCode: string; asOfDate?: string; lookback?: number }) =>
      requestJson<LivermoreStockDetailPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/stock-detail${buildStockDetailQuery(options)}`,
      ),
    getStockKlineAnalysis: (options: { stockCode: string; asOfDate?: string; lookback?: number }) =>
      requestJson<StockKlineAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/stock-analysis/kline-analysis${buildStockDetailQuery(options)}`,
      ),
    getLivermoreCandidateHistory: (options?: {
      stockCode?: string;
      snapshotFrom?: string;
      snapshotTo?: string;
      evaluationAsOfDate?: string;
      limit?: number;
    }) =>
      requestJson<LivermoreCandidateHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/candidate-history${buildCandidateHistoryQuery(options)}`,
      ),
    getLivermoreStrategyScore: (options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
      currentMarketState?: string;
      minSample?: number;
      primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
    }) =>
      requestJson<LivermoreStrategyScorePayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/strategy-score${buildStrategyScoreQuery(options)}`,
      ),
    getLivermoreStrategyOptimization: (options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
      currentMarketState?: string;
      minSample?: number;
      primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
    }) =>
      requestJson<LivermoreStrategyOptimizationPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/strategy-optimization${buildStrategyScoreQuery(options)}`,
      ),
    getLivermoreCycleProxyBacktest: (options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
    }) =>
      requestJson<LivermoreCycleProxyBacktestPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/cycle-proxy-backtest${buildSnapshotWindowQuery(options)}`,
      ),
    getLivermoreCandidateHistoryPortfolioBacktest: (options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
    }) =>
      requestJson<LivermoreCandidateHistoryPortfolioBacktestPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/candidate-history-portfolio-backtest${buildSnapshotWindowQuery(options)}`,
      ),
    getLivermoreSectorRankSeries: (options?: {
      asOfDate?: string;
      windowDays?: number;
      sectorCode?: string;
      topK?: number;
    }) =>
      requestJson<LivermoreSectorRankSeriesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/sector-rank-series${buildSectorRankSeriesQuery(options)}`,
      ),
    getLivermoreSignalConfluence: (options?: { asOfDate?: string }) =>
      requestJson<LivermoreSignalConfluencePayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/signal-confluence${buildLivermoreQuery(options)}`,
      ),
    materializeLivermorePositionSnapshot: (options: { asOfDate: string; csvPath: string }) =>
      requestActionJson<LivermorePositionSnapshotPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/livermore/position-snapshot",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            as_of_date: options.asOfDate,
            csv_path: options.csvPath,
          }),
        },
      ),
    materializeLivermoreManualPositionSnapshot: (options: {
      asOfDate: string;
      positions: LivermoreManualPositionInput[];
    }) =>
      requestActionJson<LivermorePositionSnapshotPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/livermore/position-snapshot/manual",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            as_of_date: options.asOfDate,
            positions: options.positions.map((position) => ({
              stock_code: position.stockCode.trim(),
              stock_name: position.stockName?.trim() || undefined,
              entry_cost: position.entryCost,
              bars_since_entry: position.barsSinceEntry,
              entry_date: position.entryDate?.trim() || undefined,
              position_quantity: position.positionQuantity,
              position_status: position.positionStatus,
            })),
          }),
        },
      ),
    getLivermoreGateSupplementRefreshStatus: (runId: string) =>
      requestActionJson<LivermoreGateSupplementRefreshAcceptance>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/refresh-gate-supplement/status?run_id=${encodeURIComponent(runId)}`,
      ),
    getChoiceNewsEvents: ({
      limit,
      offset,
      groupId,
      topicCode,
      stockCode,
      errorOnly,
      receivedFrom,
      receivedTo,
    }) => {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (groupId?.trim()) {
        params.set("group_id", groupId.trim());
      }
      if (topicCode?.trim()) {
        params.set("topic_code", topicCode.trim());
      }
      if (stockCode?.trim()) {
        params.set("stock_code", stockCode.trim());
      }
      if (errorOnly) {
        params.set("error_only", "true");
      }
      if (receivedFrom?.trim()) {
        params.set("received_from", receivedFrom.trim());
      }
      if (receivedTo?.trim()) {
        params.set("received_to", receivedTo.trim());
      }
      return requestJson<ChoiceNewsEventsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest?${params.toString()}`,
      );
    },
    getResearchCalendarEvents: (options) => {
      const params = new URLSearchParams();
      if (options?.startDate?.trim()) {
        params.set("start_date", options.startDate.trim());
      }
      if (options?.endDate?.trim()) {
        params.set("end_date", options.endDate.trim());
      } else if (options?.reportDate?.trim()) {
        params.set("end_date", options.reportDate.trim());
      }
      const query = params.toString();
      return requestJson<ResearchCalendarResultPayload>(
        fetchImpl,
        baseUrl,
        `/ui/calendar/supply-auctions${query ? `?${query}` : ""}`,
      ).then((payload) => payload.result.events.map(mapResearchCalendarApiEvent));
    },
    ingestTushareNprNews: (options?: { limit?: number }) => {
      const params = new URLSearchParams();
      if (options?.limit != null) {
        params.set("limit", String(options.limit));
      }
      const query = params.toString();
      return requestActionJson<{
        status: string;
        inserted: number;
        skipped_duplicates: number;
        fetched: number;
        npr: { inserted: number; skipped_duplicates: number; fetched: number };
        news: { inserted: number; skipped_duplicates: number; fetched: number; src: string; error?: string };
      }>(
        fetchImpl,
        baseUrl,
        `/api/news/tushare-npr/ingest${query ? `?${query}` : ""}`,
        { method: "POST" },
      );
    },
    refreshGateSupplement: (options?: { asOfDate?: string; lookbackDays?: number }) => {
      const params = new URLSearchParams();
      if (options?.asOfDate?.trim()) {
        params.set("as_of_date", options.asOfDate.trim());
      }
      if (options?.lookbackDays != null) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const query = params.toString();
      return requestActionJson<LivermoreGateSupplementRefreshAcceptance>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore/refresh-gate-supplement${query ? `?${query}` : ""}`,
        { method: "POST" },
      );
    },
    getMarketDataRates: () =>
      requestJson<ChoiceMacroLatestPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/rates",
      ),
    getMarketDataCatalog: () =>
      requestJson<MarketDataCatalogPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/catalog",
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestPlainJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<TData> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as TData;
}

async function requestActionJson<TResponse>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const detailText =
      extractApiErrorDetail(body) ?? `Request failed: ${path} (${response.status})`;
    const runId = extractApiRunId(body);
    const rawDetail = extractRawDetail(body);
    const topErrorMessage = extractTopLevelErrorMessage(body);
    const nestedDetail =
      rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
        ? (rawDetail as Record<string, unknown>).error_message
        : undefined;
    const errorMessage =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage,
      detail: rawDetail,
    });
  }
  return (await response.json()) as TResponse;
}
