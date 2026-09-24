import type { ApiEnvelope, StockAnalysisWorkbenchPayload } from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";

type FetchLike = typeof fetch;

export type StockAnalysisWorkbenchOptions = {
  asOfDate?: string;
  include?: string[];
  sectorWindowDays?: number;
  topK?: number;
};

export type StockAnalysisWorkbenchClientMethods = {
  getStockAnalysisWorkbench: (
    options?: StockAnalysisWorkbenchOptions,
  ) => Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>>;
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

async function requestJson(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<StockAnalysisWorkbenchPayload>;
}

export function createRealStockAnalysisWorkbenchClient({
  fetchImpl,
  baseUrl,
}: StockAnalysisWorkbenchClientFactoryOptions): StockAnalysisWorkbenchClientMethods {
  return {
    getStockAnalysisWorkbench: (options) =>
      requestJson(
        fetchImpl,
        baseUrl,
        `/ui/market-data/stock-analysis/workbench${buildStockAnalysisWorkbenchQuery(options)}`,
      ),
  };
}
