import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

const MARKET_HOME_QUERY_OPTIONS = {
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: 5 * 60_000,
  gcTime: 10 * 60_000,
} as const;

export function useMarketHomeQueries(): ModuleHomeSourceQueries {
  const client = useApiClient();

  const choiceLatestQuery = useQuery({
    queryKey: ["module-home", "choice-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const marketRatesQuery = useQuery({
    queryKey: ["module-home", "market-rates", client.mode],
    queryFn: () => client.getMarketDataRates(),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const marketCatalogQuery = useQuery({
    queryKey: ["module-home", "market-catalog", client.mode],
    queryFn: () => client.getMarketDataCatalog(),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const macroToolkitAnalysisQuery = useQuery({
    queryKey: ["module-home", "macro-toolkit-analysis", "full", client.mode],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "full" }),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const primaryQueriesReady = Boolean(
    choiceLatestQuery.data &&
      marketRatesQuery.data &&
      marketCatalogQuery.data &&
      macroToolkitAnalysisQuery.data,
  );

  const macroToolkitStrategySummariesQuery = useQuery({
    queryKey: ["module-home", "macro-toolkit-strategy-summaries", client.mode],
    queryFn: () => client.getMacroToolkitStrategySummaries(),
    enabled: primaryQueriesReady,
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  return {
    choiceLatest: choiceLatestQuery,
    marketRates: marketRatesQuery,
    marketCatalog: marketCatalogQuery,
    macroToolkitAnalysis: macroToolkitAnalysisQuery,
    macroToolkitStrategySummaries: macroToolkitStrategySummariesQuery,
  };
}
