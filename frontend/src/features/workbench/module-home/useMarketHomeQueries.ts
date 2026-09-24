import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

export const MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT = 430;

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
    queryKey: [
      "module-home",
      "macro-toolkit-analysis",
      "full",
      MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT,
      client.mode,
    ],
    queryFn: () =>
      client.getMacroToolkitAnalysis({
        detail: "full",
        historyLimit: MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT,
      }),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const newsEventsQuery = useQuery({
    queryKey: [
      "module-home",
      "news-events",
      "compact",
      500,
      0,
      false,
      client.mode,
    ],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: 500,
        offset: 0,
        includePayloadJson: false,
      }),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const macroToolkitStrategySummariesQuery = useQuery({
    queryKey: ["module-home", "macro-toolkit-strategy-summaries", client.mode],
    queryFn: () => client.getMacroToolkitStrategySummaries(),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  // 返回对象随任一 query 结果变化才更新引用，供页面 useMemo 直接依赖 queries 本身。
  return useMemo(
    () => ({
      choiceLatest: choiceLatestQuery,
      marketRates: marketRatesQuery,
      marketCatalog: marketCatalogQuery,
      macroToolkitAnalysis: macroToolkitAnalysisQuery,
      macroToolkitStrategySummaries: macroToolkitStrategySummariesQuery,
      newsEvents: newsEventsQuery,
    }),
    [
      choiceLatestQuery,
      marketRatesQuery,
      marketCatalogQuery,
      macroToolkitAnalysisQuery,
      macroToolkitStrategySummariesQuery,
      newsEventsQuery,
    ],
  );
}
