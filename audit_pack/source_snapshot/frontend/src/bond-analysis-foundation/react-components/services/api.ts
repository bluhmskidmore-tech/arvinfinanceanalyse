import type {
  Bond,
  BondListQuery,
  BondSearchRequest,
  DateString,
  PaginatedResponse,
  TimeSeriesPoint,
} from "../../data-structures/BondModel";
import type {
  HistoricalSeriesQuery,
  MarketIndexSnapshot,
  MarketIndicesQuery,
  YieldCurve,
  YieldCurveQuery,
} from "../../data-structures/MarketModel";
import type { Order, OrderCreateRequest, OrderQuery } from "../../data-structures/OrderModel";
import type {
  Portfolio,
  PortfolioAnalytics,
  PortfolioCreateRequest,
  PortfolioUpdateRequest,
} from "../../data-structures/PortfolioModel";

type RequestQueryValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | string[]
  | number[];

export type RealtimeChannel = "bond-prices" | "yield-curve";

export interface BondApiServiceOptions {
  baseUrl?: string;
  realtimeBaseUrl?: string;
  fetcher?: typeof fetch;
  headers?: HeadersInit;
}

export interface BondApiService {
  getBonds(query?: BondListQuery): Promise<PaginatedResponse<Bond>>;
  getBond(bondId: string): Promise<Bond>;
  searchBonds(payload: BondSearchRequest): Promise<PaginatedResponse<Bond>>;
  getPortfolios(): Promise<PaginatedResponse<Portfolio>>;
  getPortfolio(portfolioId: string): Promise<Portfolio>;
  createPortfolio(payload: PortfolioCreateRequest): Promise<Portfolio>;
  updatePortfolio(portfolioId: string, payload: PortfolioUpdateRequest): Promise<Portfolio>;
  getPortfolioAnalytics(
    portfolioId: string,
    params?: { asOfDate?: DateString },
  ): Promise<PortfolioAnalytics>;
  getYieldCurve(params?: YieldCurveQuery): Promise<YieldCurve>;
  getMarketIndices(params?: MarketIndicesQuery): Promise<MarketIndexSnapshot>;
  getBondPriceHistory(
    bondId: string,
    params?: HistoricalSeriesQuery,
  ): Promise<TimeSeriesPoint[]>;
  getBondYieldHistory(
    bondId: string,
    params?: HistoricalSeriesQuery,
  ): Promise<TimeSeriesPoint[]>;
  createOrder(payload: OrderCreateRequest): Promise<Order>;
  getOrders(query?: OrderQuery): Promise<PaginatedResponse<Order>>;
  getOrder(orderId: string): Promise<Order>;
  cancelOrder(orderId: string): Promise<Order>;
}

export class ApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function resolveRestBaseUrl(baseUrl: string): string {
  if (/^https?:\/\//.test(baseUrl)) {
    return baseUrl.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    return new URL(baseUrl || "/", window.location.origin).toString().replace(/\/+$/, "");
  }

  return `http://localhost${baseUrl.startsWith("/") ? baseUrl : `/${baseUrl}`}`.replace(
    /\/+$/,
    "",
  );
}

function appendQuery(searchParams: URLSearchParams, key: string, value: RequestQueryValue) {
  if (value === undefined || value === null || value === "") {
    return;
  }

  if (Array.isArray(value)) {
    value.forEach((item) => searchParams.append(key, String(item)));
    return;
  }

  searchParams.append(key, String(value));
}

async function requestJson<T>(
  fetcher: typeof fetch,
  baseUrl: string,
  path: string,
  init: RequestInit & { query?: object } = {},
): Promise<T> {
  const url = new URL(path.replace(/^\//, ""), `${resolveRestBaseUrl(baseUrl)}/`);
  const searchParams = new URLSearchParams(url.search);

  Object.entries(init.query ?? {}).forEach(([key, value]) => {
    if (
      value === undefined ||
      value === null ||
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean" ||
      (Array.isArray(value) &&
        value.every((entry) => typeof entry === "string" || typeof entry === "number"))
    ) {
      appendQuery(searchParams, key, value as RequestQueryValue);
    }
  });
  url.search = searchParams.toString();

  const response = await fetcher(url.toString(), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  });
  const payload =
    typeof response.json === "function" ? await response.json().catch(() => undefined) : undefined;

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "message" in payload
        ? String(payload.message)
        : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export function buildRealtimeStreamUrl(
  baseUrl: string,
  channel: RealtimeChannel,
  params: Record<string, string | number | undefined> = {},
): string {
  const normalizedBase = resolveRestBaseUrl(baseUrl).replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  const url = new URL(`live/${channel}`, `${normalizedBase}/`);

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value));
    }
  });

  return url.toString();
}

export function createBondApiService(options: BondApiServiceOptions = {}): BondApiService {
  const baseUrl = options.baseUrl ?? "";
  const fetcher = options.fetcher ?? fetch;
  const headers = options.headers;

  return {
    getBonds(query = {}) {
      return requestJson<PaginatedResponse<Bond>>(fetcher, baseUrl, "/api/bonds", {
        method: "GET",
        headers,
        query,
      });
    },
    getBond(bondId) {
      return requestJson<Bond>(fetcher, baseUrl, `/api/bonds/${bondId}`, {
        method: "GET",
        headers,
      });
    },
    searchBonds(payload) {
      return requestJson<PaginatedResponse<Bond>>(fetcher, baseUrl, "/api/bonds/search", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
    },
    getPortfolios() {
      return requestJson<PaginatedResponse<Portfolio>>(fetcher, baseUrl, "/api/portfolio", {
        method: "GET",
        headers,
      });
    },
    getPortfolio(portfolioId) {
      return requestJson<Portfolio>(fetcher, baseUrl, `/api/portfolio/${portfolioId}`, {
        method: "GET",
        headers,
      });
    },
    createPortfolio(payload) {
      return requestJson<Portfolio>(fetcher, baseUrl, "/api/portfolio/create", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
    },
    updatePortfolio(portfolioId, payload) {
      return requestJson<Portfolio>(fetcher, baseUrl, `/api/portfolio/${portfolioId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify(payload),
      });
    },
    getPortfolioAnalytics(portfolioId, params = {}) {
      return requestJson<PortfolioAnalytics>(
        fetcher,
        baseUrl,
        `/api/portfolio/${portfolioId}/analytics`,
        {
          method: "GET",
          headers,
          query: params,
        },
      );
    },
    getYieldCurve(params = {}) {
      return requestJson<YieldCurve>(fetcher, baseUrl, "/api/market/yield-curve", {
        method: "GET",
        headers,
        query: params,
      });
    },
    getMarketIndices(params = {}) {
      return requestJson<MarketIndexSnapshot>(fetcher, baseUrl, "/api/market/indices", {
        method: "GET",
        headers,
        query: params,
      });
    },
    getBondPriceHistory(bondId, params = {}) {
      return requestJson<TimeSeriesPoint[]>(
        fetcher,
        baseUrl,
        `/api/bonds/${bondId}/price-history`,
        {
          method: "GET",
          headers,
          query: params,
        },
      );
    },
    getBondYieldHistory(bondId, params = {}) {
      return requestJson<TimeSeriesPoint[]>(
        fetcher,
        baseUrl,
        `/api/bonds/${bondId}/yield-history`,
        {
          method: "GET",
          headers,
          query: params,
        },
      );
    },
    createOrder(payload) {
      return requestJson<Order>(fetcher, baseUrl, "/api/orders", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
    },
    getOrders(query = {}) {
      return requestJson<PaginatedResponse<Order>>(fetcher, baseUrl, "/api/orders", {
        method: "GET",
        headers,
        query,
      });
    },
    getOrder(orderId) {
      return requestJson<Order>(fetcher, baseUrl, `/api/orders/${orderId}`, {
        method: "GET",
        headers,
      });
    },
    cancelOrder(orderId) {
      return requestJson<Order>(fetcher, baseUrl, `/api/orders/${orderId}`, {
        method: "DELETE",
        headers,
      });
    },
  };
}
