import { useMemo } from "react";
import { useQueries, type UseQueryResult } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";

type ProductCategoryHistoryQuery = UseQueryResult<
  Awaited<ReturnType<ApiClient["getProductCategoryHistory"]>>,
  Error
>;

type ProductCategoryBacktestHistoryOptions = {
  client: ApiClient;
  baseline: Awaited<ReturnType<ApiClient["getProductCategoryPnl"]>> | undefined;
  reportDateBatches: string[][];
  trendHistoryQueries: ProductCategoryHistoryQuery[];
  backtestWorkspaceOpen: boolean;
  historyReady: boolean;
  selectedView: string;
  appliedScenarioRate: string;
};

export function useProductCategoryBacktestHistory({
  client,
  baseline,
  reportDateBatches,
  trendHistoryQueries,
  backtestWorkspaceOpen,
  historyReady,
  selectedView,
  appliedScenarioRate,
}: ProductCategoryBacktestHistoryOptions) {
  const formalHistoryQueries = useQueries({
    queries: reportDateBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-batch",
        client.mode,
        batchReportDates.join(","),
        "monthly",
        "",
      ],
      queryFn: () =>
        client.getProductCategoryHistory({
          reportDates: batchReportDates,
          view: "monthly",
        }),
      enabled: Boolean(
        backtestWorkspaceOpen &&
          historyReady &&
          selectedView === "monthly" &&
          appliedScenarioRate,
      ),
      retry: false,
    })),
  });
  const historyQueries = appliedScenarioRate
    ? formalHistoryQueries
    : trendHistoryQueries;
  const payloads = useMemo(
    () =>
      [
        ...(baseline ? [baseline] : []),
        ...(historyReady && selectedView === "monthly"
          ? historyQueries.flatMap(
              (query) =>
                query.data?.result.items.filter((item) => item.status === "ok") ??
                [],
            )
          : []),
      ].flatMap(({ result, result_meta }) =>
        result &&
        result_meta?.basis === "formal" &&
        result_meta.formal_use_allowed === true &&
        result_meta.scenario_flag === false
          ? [result]
          : [],
      ),
    [baseline, historyQueries, historyReady, selectedView],
  );

  return {
    historyQueries,
    payloads,
    isError:
      selectedView === "monthly" &&
      historyQueries.some((query) => query.isError),
  };
}
