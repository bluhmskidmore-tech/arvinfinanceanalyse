import type {
  ApiEnvelope,
  StockAnalysisWorkbenchPayload,
  StockPortfolioConstructionPayload,
} from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";

type FetchLike = typeof fetch;

export type StockAnalysisWorkbenchOptions = {
  asOfDate?: string;
  include?: string[];
  sectorWindowDays?: number;
  topK?: number;
};

export type StockPortfolioConstructionOptions = {
  portfolioId: string;
  asOfDate?: string;
};

export type StockAnalysisWorkbenchClientMethods = {
  getStockAnalysisWorkbench: (
    options?: StockAnalysisWorkbenchOptions,
  ) => Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>>;
  getStockAnalysisPortfolioConstruction: (
    options: StockPortfolioConstructionOptions,
  ) => Promise<ApiEnvelope<StockPortfolioConstructionPayload>>;
};

type StockAnalysisWorkbenchClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

function buildStockAnalysisWorkbenchQuery(options?: StockAnalysisWorkbenchOptions) {
  const params = new URLSearchParams();
  const asOfDate = options?.asOfDate?.trim();
  if (asOfDate) params.set("as_of_date", asOfDate);
  const include = options?.include?.map((item) => item.trim()).filter(Boolean);
  if (include?.length) params.set("include", include.join(","));
  if (options?.sectorWindowDays != null) {
    params.set("sector_window_days", String(options.sectorWindowDays));
  }
  if (options?.topK != null) params.set("top_k", String(options.topK));
  const query = params.toString();
  return query ? `?${query}` : "";
}

function buildStockPortfolioConstructionQuery(options: StockPortfolioConstructionOptions) {
  const params = new URLSearchParams();
  params.set("portfolio_id", options.portfolioId.trim());
  const asOfDate = options.asOfDate?.trim();
  if (asOfDate) params.set("as_of_date", asOfDate);
  return `?${params.toString()}`;
}

async function requestJson<TPayload>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TPayload>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TPayload>;
}

export function createRealStockAnalysisWorkbenchClient({
  fetchImpl,
  baseUrl,
}: StockAnalysisWorkbenchClientFactoryOptions): StockAnalysisWorkbenchClientMethods {
  return {
    getStockAnalysisWorkbench: (options) =>
      requestJson<StockAnalysisWorkbenchPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/stock-analysis/workbench${buildStockAnalysisWorkbenchQuery(options)}`,
      ),
    getStockAnalysisPortfolioConstruction: (options) =>
      requestJson<StockPortfolioConstructionPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/stock-analysis/portfolio-construction${buildStockPortfolioConstructionQuery(options)}`,
      ),
  };
}
