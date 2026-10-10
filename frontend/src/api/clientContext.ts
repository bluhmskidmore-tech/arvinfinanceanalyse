import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type { CandidateFinancialIndicatorsClientMethods } from "./candidateFinancialIndicatorsClient";
import type { ApiClient, ApiClientOptions } from "./client";
import type { ExecutiveClientMethods } from "./executiveClient";
import type { HomeExecutiveClientMethods } from "./homeExecutiveClient";
import type { HomeMarketTickerClientMethods } from "./homeMarketTickerClient";
import type { HomeSupplementalClientMethods } from "./homeSupplementalClient";
import type { MacroToolkitClientMethods } from "./macroToolkitClient";
import type { MarketDataClientMethods } from "./marketDataClient";
import type { PositionsClientMethods } from "./positionsClient";
import type { StockAnalysisWorkbenchClientMethods } from "./stockAnalysisWorkbenchClient";
import { registerApiClientFactory } from "./clientFactoryOptions";
import { resolveDataSourceMode } from "./dataSourceMode";

export type { ApiClient, DataSourceMode } from "./client";

export type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
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
  "fetchMacroToolkitModelChainResults",
  "getMacroToolkitScripts",
  "runMacroToolkitScript",
  "runMacroToolkitScriptChain",
  "refreshCffexMemberRank",
  "getCffexMemberRankRefreshStatus",
  "refreshMacroSourceBackfill",
  "getMacroSourceBackfillRefreshStatus",
  "refreshCommodityFutures",
  "getCommodityFuturesRefreshStatus",
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
  "getBondAnalyticsKrdCurveRisk",
  "getBalanceAnalysisDates",
  "getBalanceAnalysisPublicationStatus",
  "getBalanceAnalysisOverview",
  "getBalanceAnalysisSummary",
  "getBalanceAnalysisWorkbook",
  "getBalanceAnalysisCurrentUser",
  "getBalanceAnalysisSummaryByBasis",
  "getBalanceAnalysisDetail",
  "getBalanceAnalysisAdvancedAttribution",
  "getBalanceAnalysisDecisionItems",
  "getBalanceMovementDates",
  "getBalanceMovementAnalysis",
  "getAdbComparison",
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
  // Batch path used by dashboard-home to collapse 13 per-topic news reads.
  "getChoiceNewsEventsBatch",
  "getResearchCalendarEvents",
]);

const CANDIDATE_FINANCIAL_INDICATOR_METHODS = new Set<
  keyof CandidateFinancialIndicatorsClientMethods
>(["getLedgerPnlCandidateFinancialIndicators"]);

const STOCK_ANALYSIS_MARKET_DATA_METHODS = new Set<keyof MarketDataClientMethods>([
  "getLivermoreStrategy",
  "getLivermoreStockDetail",
  "getStockKlineAnalysis",
  "getStockHeavyweightTrends",
  "getLivermoreCandidateHistory",
  "getLivermoreStrategyScore",
  "getLivermoreStrategyOptimization",
  "getLivermoreCycleProxyBacktest",
  "getLivermoreCandidateHistoryPortfolioBacktest",
  "getLivermoreSectorRankSeries",
  "getLivermoreSignalConfluence",
  "materializeLivermorePositionSnapshot",
  "materializeLivermoreManualPositionSnapshot",
  "getLivermoreGateSupplementRefreshStatus",
  "refreshGateSupplement",
]);

const MARKET_OVERVIEW_METHODS = new Set<keyof MarketDataClientMethods>([
  "getMarketOverviewSnapshot",
]);

const POSITIONS_METHODS = new Set<keyof PositionsClientMethods>([
  "getPositionsBondSubTypes",
  "getPositionsBondsList",
  "getPositionsCounterpartyBonds",
  "getPositionsInterbankProductTypes",
  "getPositionsInterbankList",
  "getPositionsCounterpartyInterbankSplit",
  "getPositionsStatsRating",
  "getPositionsStatsIndustry",
  "getPositionsCustomerDetails",
  "getPositionsCustomerTrend",
]);

type RiskPageClientMethods = Pick<ExecutiveClientMethods,
  "getRiskTensorDates" | "getRiskTensor" | "getRiskScenarioStress"
>;

const RISK_PAGE_METHODS = new Set<keyof RiskPageClientMethods>([
  "getRiskTensorDates", "getRiskTensor", "getRiskScenarioStress",
]);

export function createDeferredApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = resolveDataSourceMode(options.mode);
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseDeferredBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  let clientPromise: Promise<ApiClient> | null = null;
  let candidateFinancialIndicatorsClientPromise: Promise<CandidateFinancialIndicatorsClientMethods> | null = null;
  let homeExecutiveClientPromise: Promise<HomeExecutiveClientMethods> | null = null;
  let homeMarketTickerClientPromise: Promise<HomeMarketTickerClientMethods> | null = null;
  let homeSupplementalClientPromise: Promise<HomeSupplementalClientMethods> | null = null;
  let macroToolkitClientPromise: Promise<MacroToolkitClientMethods> | null = null;
  let marketDataClientPromise: Promise<MarketDataClientMethods> | null = null;
  let stockAnalysisWorkbenchClientPromise: Promise<StockAnalysisWorkbenchClientMethods> | null = null;
  let positionsClientPromise: Promise<PositionsClientMethods> | null = null;
  let riskPageClientPromise: Promise<RiskPageClientMethods> | null = null;

  const loadPositionsClient = () => {
    if (!positionsClientPromise) {
      positionsClientPromise = !import.meta.env.PROD && mode === "mock"
        ? import("../mocks/positionsMockClient").then(({ createDemoPositionsClient }) =>
            createDemoPositionsClient(
              async () => new Promise<void>((resolve) => setTimeout(resolve, 40)),
              () => import("../mocks/mockApiEnvelope"),
            ),
          )
        : Promise.all([import("./positionsClient"), import("./transport")]).then(
            ([{ createRealPositionsClient }, { requestJson }]) =>
              createRealPositionsClient({ fetchImpl, baseUrl, requestJson }),
          );
    }
    return positionsClientPromise;
  };

  const loadRiskPageClient = () => {
    if (!riskPageClientPromise) {
      riskPageClientPromise = !import.meta.env.PROD && mode === "mock"
        ? import("../mocks/executiveMockClient").then(({ createDemoExecutiveClient }) =>
            createDemoExecutiveClient(
              async () => new Promise<void>((resolve) => setTimeout(resolve, 40)),
              async () => {
                const [envelope, workbench] = await Promise.all([
                  import("../mocks/mockApiEnvelope"), import("../mocks/workbench"),
                ]);
                return { ...envelope, ...workbench };
              },
            ),
          )
        : Promise.all([
            import("./executiveClient").then(({ createRealExecutiveClient }) => createRealExecutiveClient),
            import("./transport").then(({ requestJson }) => requestJson),
          ]).then(
            ([createRealExecutiveClient, requestJson]) =>
              createRealExecutiveClient({ fetchImpl, baseUrl, requestJson }),
          );
    }
    return riskPageClientPromise;
  };

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
      macroToolkitClientPromise =
        !import.meta.env.PROD && mode === "mock"
          ? import("../mocks/macroToolkitMockClient").then(
              ({ createMockMacroToolkitClient }) => createMockMacroToolkitClient(),
            )
          : import("./macroToolkitClient").then(
              ({ createRealMacroToolkitClient }) =>
                createRealMacroToolkitClient({ fetchImpl, baseUrl }),
            );
    }
    return macroToolkitClientPromise;
  };

  const loadMarketDataClient = () => {
    if (!marketDataClientPromise) {
      marketDataClientPromise =
        !import.meta.env.PROD && mode === "mock"
          ? import("../mocks/marketDataMockClient").then(
              ({ createMockMarketDataClient }) => createMockMarketDataClient(),
            )
          : import("./marketDataClient").then(
              ({ createRealMarketDataClient }) =>
                createRealMarketDataClient({ fetchImpl, baseUrl }),
            );
    }
    return marketDataClientPromise;
  };

  const loadStockAnalysisWorkbenchClient = () => {
    if (!stockAnalysisWorkbenchClientPromise) {
      stockAnalysisWorkbenchClientPromise =
        !import.meta.env.PROD && mode === "mock"
          ? loadMarketDataClient()
          : import("./stockAnalysisWorkbenchClient").then(
              ({ createRealStockAnalysisWorkbenchClient }) =>
                createRealStockAnalysisWorkbenchClient({ fetchImpl, baseUrl }),
            );
    }
    return stockAnalysisWorkbenchClientPromise;
  };

  const loadHomeExecutiveClient = () => {
    if (!homeExecutiveClientPromise) {
      homeExecutiveClientPromise = !import.meta.env.PROD && mode === "mock"
        ? import("../mocks/homeExecutiveMockClient").then(
            ({ createMockHomeExecutiveClient }) => createMockHomeExecutiveClient(),
          )
        : import("./homeExecutiveClient").then(
            ({ createRealHomeExecutiveClient }) => createRealHomeExecutiveClient({ fetchImpl, baseUrl }),
          );
    }
    return homeExecutiveClientPromise;
  };

  const loadCandidateFinancialIndicatorsClient = () => {
    if (!candidateFinancialIndicatorsClientPromise) {
      candidateFinancialIndicatorsClientPromise = !import.meta.env.PROD && mode === "mock"
        ? import("./candidateFinancialIndicatorsClient").then(
            ({ createMockCandidateFinancialIndicatorsClient }) => createMockCandidateFinancialIndicatorsClient(),
          )
        : import("./candidateFinancialIndicatorsClient").then(
            ({ createRealCandidateFinancialIndicatorsClient }) =>
              createRealCandidateFinancialIndicatorsClient({ fetchImpl, baseUrl }),
          );
    }
    return candidateFinancialIndicatorsClientPromise;
  };

  const loadHomeSupplementalClient = () => {
    if (!homeSupplementalClientPromise) {
      homeSupplementalClientPromise = !import.meta.env.PROD && mode === "mock"
        ? import("./homeSupplementalClient").then(
            ({ createMockHomeSupplementalClient }) => createMockHomeSupplementalClient(),
          )
        : import("./homeSupplementalClient").then(
            ({ createRealHomeSupplementalClient }) => createRealHomeSupplementalClient({ fetchImpl, baseUrl }),
          );
    }
    return homeSupplementalClientPromise;
  };

  const loadHomeMarketTickerClient = () => {
    if (!homeMarketTickerClientPromise) {
      homeMarketTickerClientPromise = !import.meta.env.PROD && mode === "mock"
        ? import("../mocks/homeMarketTickerMockClient").then(
            ({ createMockHomeMarketTickerClient }) => createMockHomeMarketTickerClient(),
          )
        : import("./homeMarketTickerClient").then(
            ({ createRealHomeMarketTickerClient }) => createRealHomeMarketTickerClient({ fetchImpl, baseUrl }),
          );
    }
    return homeMarketTickerClientPromise;
  };

  const client = new Proxy(
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
          if (POSITIONS_METHODS.has(property as keyof PositionsClientMethods)) {
            const client = await loadPositionsClient();
            const method = client[property as keyof PositionsClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          if (RISK_PAGE_METHODS.has(property as keyof RiskPageClientMethods)) {
            const client = await loadRiskPageClient();
            const method = client[property as keyof RiskPageClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          if (HOME_EXECUTIVE_METHODS.has(property as keyof HomeExecutiveClientMethods)) {
            const client = await loadHomeExecutiveClient();
            const method = client[property as keyof HomeExecutiveClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          if (
            CANDIDATE_FINANCIAL_INDICATOR_METHODS.has(
              property as keyof CandidateFinancialIndicatorsClientMethods,
            )
          ) {
            const client = await loadCandidateFinancialIndicatorsClient();
            const method = client[
              property as keyof CandidateFinancialIndicatorsClientMethods
            ] as (...methodArgs: unknown[]) => unknown;
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
          if (MARKET_OVERVIEW_METHODS.has(property as keyof MarketDataClientMethods)) {
            const client = await loadMarketDataClient();
            const method = client[property as keyof MarketDataClientMethods] as (
              ...methodArgs: unknown[]
            ) => unknown;
            return method(...args);
          }
          if (
            property === "getStockAnalysisWorkbench" ||
            property === "getStockAnalysisPortfolioConstruction"
          ) {
            const client = await loadStockAnalysisWorkbenchClient();
            if (property === "getStockAnalysisWorkbench") {
              return client.getStockAnalysisWorkbench(
                ...(args as Parameters<StockAnalysisWorkbenchClientMethods["getStockAnalysisWorkbench"]>),
              );
            }
            return client.getStockAnalysisPortfolioConstruction(
              ...(args as Parameters<
                StockAnalysisWorkbenchClientMethods["getStockAnalysisPortfolioConstruction"]
              >),
            );
          }
          if (STOCK_ANALYSIS_MARKET_DATA_METHODS.has(property as keyof MarketDataClientMethods)) {
            const client = await loadMarketDataClient();
            const method = client[property as keyof MarketDataClientMethods] as (...methodArgs: unknown[]) => unknown;
            return method(...args);
          }
          const client = await loadClient();
          const value = client[property as keyof ApiClient];
          if (typeof value !== "function") {
            return value;
          }
          const method = value as (...methodArgs: unknown[]) => unknown;
          return Reflect.apply(method, client, args);
        };
      },
    },
  );

  return registerApiClientFactory(
    client,
    { mode, baseUrl, fetchImpl },
    createDeferredApiClient,
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
