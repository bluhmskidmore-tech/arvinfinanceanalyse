import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type { ApiClient, ApiClientOptions, DataSourceMode } from "./client";
import type { HomeExecutiveClientMethods } from "./homeExecutiveClient";
import type { HomeMarketTickerClientMethods } from "./homeMarketTickerClient";
import type { HomeSupplementalClientMethods } from "./homeSupplementalClient";
import type { MacroToolkitClientMethods } from "./macroToolkitClient";

export type { ApiClient, DataSourceMode } from "./client";

export type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
};

const parseDeferredEnvMode = (): DataSourceMode => {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  const isProd = import.meta.env.PROD === true;

  if (envValue === "real") return "real";
  if (envValue === "mock") {
    if (isProd) throw new Error("VITE_DATA_SOURCE='mock' is not allowed in production.");
    return "mock";
  }

  if (isProd) {
    throw new Error(
      "VITE_DATA_SOURCE must be explicitly set to 'real' or 'mock' in production build. " +
        "Refusing to silently fall back to mock. " +
        "See docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md section 9.1.",
    );
  }

  console.warn("[client] VITE_DATA_SOURCE not set or invalid (raw=%o). Defaulting to real.", raw);
  return "real";
};

const normalizeBaseUrl = (value?: string) => (value ? value.replace(/\/$/, "") : "");

const parseDeferredBaseUrl = () => {
  const raw = import.meta.env.VITE_API_BASE_URL;
  return normalizeBaseUrl(typeof raw === "string" ? raw.trim() : undefined);
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const MACRO_TOOLKIT_METHODS = new Set<keyof MacroToolkitClientMethods>([
  "getMacroToolkitAnalysis",
  "getMacroToolkitStrategySummaries",
  "getMacroToolkitScripts",
  "runMacroToolkitScript",
  "refreshCffexMemberRank",
  "refreshMacroSourceBackfill",
  "refreshChoiceStock",
  "getChoiceStockRefreshStatus",
]);

const HOME_EXECUTIVE_METHODS = new Set<keyof HomeExecutiveClientMethods>([
  "getHomeSnapshot",
  "getHomeMacroReleaseContext",
  "getHomeResearchReports",
  "getHomeIncomeTrend",
]);

const HOME_SUPPLEMENTAL_METHODS = new Set<keyof HomeSupplementalClientMethods>([
  "getCoreMetrics",
  "getDailyChanges",
  "getBondDashboardHeadlineKpis",
  "getBondDashboardHomeSummary",
  "getBondAnalyticsPortfolioHeadlines",
  "getBondDashboardPortfolioComparison",
  "getBondAnalyticsCreditSpreadMigration",
  "getBondAnalyticsReturnDecomposition",
  "getPnlCampisiFourEffects",
  "getBondAnalyticsYieldCurveTermStructure",
  "getBalanceAnalysisDecisionItems",
  "getBondDashboardAssetStructure",
  "getBondDashboardMaturityStructure",
  "getBondDashboardIndustryDistribution",
  "getBondDashboardRiskIndicators",
  "getBondAnalyticsTopHoldings",
  "getBondAnalyticsPositionChanges",
  "getCockpitWarnings",
]);

const HOME_MARKET_TICKER_METHODS = new Set<keyof HomeMarketTickerClientMethods>([
  "getChoiceMacroLatest",
  "getMarketDataRates",
  "getChoiceNewsEvents",
  "getResearchCalendarEvents",
]);

export function createDeferredApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseDeferredEnvMode();
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseDeferredBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  let clientPromise: Promise<ApiClient> | null = null;
  let homeExecutiveClientPromise: Promise<HomeExecutiveClientMethods> | null = null;
  let homeMarketTickerClientPromise: Promise<HomeMarketTickerClientMethods> | null = null;
  let homeSupplementalClientPromise: Promise<HomeSupplementalClientMethods> | null = null;
  let macroToolkitClientPromise: Promise<MacroToolkitClientMethods> | null = null;

  const loadClient = () => {
    if (!clientPromise) {
      clientPromise = import("./client").then(({ createApiClient }) =>
        createApiClient({ ...options, mode }),
      );
    }
    return clientPromise;
  };

  const loadMacroToolkitClient = () => {
    if (!macroToolkitClientPromise) {
      macroToolkitClientPromise = import("./macroToolkitClient").then(
        ({ createMockMacroToolkitClient, createRealMacroToolkitClient }) =>
          mode === "mock"
            ? createMockMacroToolkitClient()
            : createRealMacroToolkitClient({ fetchImpl, baseUrl }),
      );
    }
    return macroToolkitClientPromise;
  };

  const loadHomeExecutiveClient = () => {
    if (!homeExecutiveClientPromise) {
      homeExecutiveClientPromise = import("./homeExecutiveClient").then(
        ({ createMockHomeExecutiveClient, createRealHomeExecutiveClient }) =>
          mode === "mock"
            ? createMockHomeExecutiveClient()
            : createRealHomeExecutiveClient({ fetchImpl, baseUrl }),
      );
    }
    return homeExecutiveClientPromise;
  };

  const loadHomeSupplementalClient = () => {
    if (!homeSupplementalClientPromise) {
      homeSupplementalClientPromise = import("./homeSupplementalClient").then(
        ({ createMockHomeSupplementalClient, createRealHomeSupplementalClient }) =>
          mode === "mock"
            ? createMockHomeSupplementalClient()
            : createRealHomeSupplementalClient({ fetchImpl, baseUrl }),
      );
    }
    return homeSupplementalClientPromise;
  };

  const loadHomeMarketTickerClient = () => {
    if (!homeMarketTickerClientPromise) {
      homeMarketTickerClientPromise = import("./homeMarketTickerClient").then(
        ({ createMockHomeMarketTickerClient, createRealHomeMarketTickerClient }) =>
          mode === "mock"
            ? createMockHomeMarketTickerClient()
            : createRealHomeMarketTickerClient({ fetchImpl, baseUrl }),
      );
    }
    return homeMarketTickerClientPromise;
  };

  return new Proxy(
    { mode } as ApiClient,
    {
      get(target, property, receiver) {
        if (property === "mode") {
          return mode;
        }
        if (property === "then") {
          return undefined;
        }
        if (typeof property === "symbol") {
          return Reflect.get(target, property, receiver);
        }

        return async (...args: unknown[]) => {
          if (HOME_EXECUTIVE_METHODS.has(property as keyof HomeExecutiveClientMethods)) {
            const client = await loadHomeExecutiveClient();
            const method = client[property as keyof HomeExecutiveClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          if (HOME_SUPPLEMENTAL_METHODS.has(property as keyof HomeSupplementalClientMethods)) {
            const client = await loadHomeSupplementalClient();
            const method = client[property as keyof HomeSupplementalClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          if (MACRO_TOOLKIT_METHODS.has(property as keyof MacroToolkitClientMethods)) {
            const client = await loadMacroToolkitClient();
            const method = client[property as keyof MacroToolkitClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          if (HOME_MARKET_TICKER_METHODS.has(property as keyof HomeMarketTickerClientMethods)) {
            const client = await loadHomeMarketTickerClient();
            const method = client[property as keyof HomeMarketTickerClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          const client = await loadClient();
          const value = client[property as keyof ApiClient];
          if (typeof value !== "function") {
            return value;
          }
          const method = value as (...methodArgs: unknown[]) => unknown;
          return method(...args);
        };
      },
    },
  );
}

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({
  children,
  client,
}: ApiClientProviderProps) {
  const resolvedClient = useMemo(
    () => client ?? createDeferredApiClient(),
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
