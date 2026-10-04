import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";
import type { MarketFinancialChartSection } from "./marketFinancialChartsModel";

const MARKET_HOME_QUERY_OPTIONS = {
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: 5 * 60_000,
  gcTime: 10 * 60_000,
} as const;

export const MARKET_OVERVIEW_SNAPSHOT_QUERY_VERSION = "v8";

export type MarketHomeDeferredReads = {
  chartsVisible: boolean;
  backendActiveKey: string;
  chartSectionKeys?: readonly MarketFinancialChartSection["key"][];
};

export function useMarketHomeQueries({
  chartsVisible,
  backendActiveKey,
  chartSectionKeys = [],
}: MarketHomeDeferredReads): ModuleHomeSourceQueries {
  const client = useApiClient();
  const readsChartSection = (key: MarketFinancialChartSection["key"]) =>
    chartsVisible && chartSectionKeys.includes(key);

  const marketSnapshotQuery = useQuery({
    queryKey: [
      "module-home",
      "market-snapshot",
      MARKET_OVERVIEW_SNAPSHOT_QUERY_VERSION,
      client.mode,
    ],
    queryFn: () => client.getMarketOverviewSnapshot(),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const choiceLatestQuery = useQuery({
    queryKey: ["workbench-shell", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    enabled: readsChartSection("rates") || readsChartSection("cross") || backendActiveKey === "choice",
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const marketRatesQuery = useQuery({
    queryKey: ["module-home", "market-rates", client.mode],
    queryFn: () => client.getMarketDataRates(),
    enabled: readsChartSection("rates") || backendActiveKey === "rates",
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const marketCatalogQuery = useQuery({
    queryKey: ["module-home", "market-catalog", client.mode],
    queryFn: () => client.getMarketDataCatalog(),
    enabled: readsChartSection("coverage") || backendActiveKey === "catalog",
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  // 首屏结论、Crisis 与图表源统一来自 market snapshot。完整宏观分析仅供第 03/04 章，
  // 不传 historyLimit 时继续复用 market_home_warmup_service 的 full 缓存键。
  const macroToolkitAnalysisQuery = useQuery({
    queryKey: ["module-home", "macro-toolkit-analysis", "full", client.mode],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "full" }),
    enabled: readsChartSection("macro") || backendActiveKey === "macro",
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
    enabled: readsChartSection("news"),
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  const macroToolkitStrategySummariesQuery = useQuery({
    queryKey: ["module-home", "macro-toolkit-strategy-summaries", client.mode],
    queryFn: () => client.getMacroToolkitStrategySummaries(),
    enabled: readsChartSection("strategy") || backendActiveKey === "strategies",
    ...MARKET_HOME_QUERY_OPTIONS,
  });

  // 返回对象随任一 query 结果变化才更新引用，供页面 useMemo 直接依赖 queries 本身。
  return useMemo(
    () => ({
      choiceLatest: choiceLatestQuery,
      marketSnapshot: marketSnapshotQuery,
      marketRates: marketRatesQuery,
      marketCatalog: marketCatalogQuery,
      macroToolkitAnalysis: macroToolkitAnalysisQuery,
      macroToolkitStrategySummaries: macroToolkitStrategySummariesQuery,
      newsEvents: newsEventsQuery,
    }),
    [
      choiceLatestQuery,
      marketSnapshotQuery,
      marketRatesQuery,
      marketCatalogQuery,
      macroToolkitAnalysisQuery,
      macroToolkitStrategySummariesQuery,
      newsEventsQuery,
    ],
  );
}
