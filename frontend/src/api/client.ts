import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type {
  AlertsPayload,
  ApiEnvelope,
  ContributionPayload,
  HealthResponse,
  OverviewPayload,
  PlaceholderSnapshot,
  PnlAttributionPayload,
  RiskOverviewPayload,
  SummaryPayload,
} from "./contracts";
import {
  alertsPayload,
  contributionPayload,
  overviewPayload,
  placeholderSnapshots,
  pnlAttributionPayload,
  riskOverviewPayload,
  summaryPayload,
} from "../mocks/workbench";

export type DataSourceMode = "mock" | "real";

export type ApiClient = {
  mode: DataSourceMode;
  getHealth: () => Promise<HealthResponse>;
  getOverview: () => Promise<ApiEnvelope<OverviewPayload>>;
  getSummary: () => Promise<ApiEnvelope<SummaryPayload>>;
  getPnlAttribution: () => Promise<ApiEnvelope<PnlAttributionPayload>>;
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
};

type ApiClientOptions = {
  mode?: DataSourceMode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

const buildMockMeta = (resultKind: string) => ({
  trace_id: `mock_${resultKind}`,
  basis: "mock" as const,
  result_kind: resultKind,
  formal_use_allowed: false,
  source_version: "sv_mock_dashboard_v2",
  vendor_version: "vv_none",
  rule_version: "rv_dashboard_mock_v2",
  cache_version: "cv_dashboard_mock_v2",
  quality_flag: "ok" as const,
  scenario_flag: false,
  generated_at: "2026-04-09T10:30:00Z",
});

const normalizeBaseUrl = (value?: string) =>
  value ? value.replace(/\/$/, "") : "";

const parseEnvMode = (): DataSourceMode => {
  const envValue = import.meta.env.VITE_DATA_SOURCE;
  return envValue === "real" ? "real" : "mock";
};

const parseBaseUrl = () => normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

const requestJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<T>> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as ApiEnvelope<T>;
};

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseEnvMode();
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;

  const mockClient: ApiClient = {
    mode: "mock",
    async getHealth() {
      await delay();
      return { status: "ok" };
    },
    async getOverview() {
      await delay();
      return {
        result_meta: buildMockMeta("executive.overview"),
        result: overviewPayload,
      };
    },
    async getSummary() {
      await delay();
      return {
        result_meta: buildMockMeta("executive.summary"),
        result: summaryPayload,
      };
    },
    async getPnlAttribution() {
      await delay();
      return {
        result_meta: buildMockMeta("executive.pnl-attribution"),
        result: pnlAttributionPayload,
      };
    },
    async getRiskOverview() {
      await delay();
      return {
        result_meta: buildMockMeta("executive.risk-overview"),
        result: riskOverviewPayload,
      };
    },
    async getContribution() {
      await delay();
      return {
        result_meta: buildMockMeta("executive.contribution"),
        result: contributionPayload,
      };
    },
    async getAlerts() {
      await delay();
      return {
        result_meta: buildMockMeta("executive.alerts"),
        result: alertsPayload,
      };
    },
    async getPlaceholderSnapshot(key: string) {
      await delay();
      return {
        result_meta: buildMockMeta(`workbench.${key}`),
        result: placeholderSnapshots[key] ?? placeholderSnapshots.dashboard,
      };
    },
  };

  if (mode === "mock") {
    return mockClient;
  }

  return {
    mode,
    async getHealth() {
      const response = await fetchImpl(`${baseUrl}/health/ready`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Request failed: /health/ready (${response.status})`);
      }

      return (await response.json()) as HealthResponse;
    },
    getOverview: () =>
      requestJson<OverviewPayload>(fetchImpl, baseUrl, "/ui/home/overview"),
    getSummary: () =>
      requestJson<SummaryPayload>(fetchImpl, baseUrl, "/ui/home/summary"),
    getPnlAttribution: () =>
      requestJson<PnlAttributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/attribution",
      ),
    getRiskOverview: () =>
      requestJson<RiskOverviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/risk/overview",
      ),
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    getPlaceholderSnapshot: mockClient.getPlaceholderSnapshot,
  };
}

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({
  children,
  client,
}: ApiClientProviderProps) {
  const resolvedClient = useMemo(
    () => client ?? createApiClient(),
    [client],
  );

  return createElement(
    ApiClientContext.Provider,
    { value: resolvedClient },
    children,
  );
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);

  if (!client) {
    throw new Error("ApiClientProvider is missing");
  }

  return client;
}
