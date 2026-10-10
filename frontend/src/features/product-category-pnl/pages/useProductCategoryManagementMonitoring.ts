import { useMemo } from "react";
import { useQueries, type UseQueryResult } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import {
  buildProductCategoryTrendSnapshot,
  selectProductCategoryManagementMonitoringSurface,
  selectProductCategoryTrendReportPoints,
} from "./productCategoryPnlPageModel";
import { parseProductCategoryReportDateInternal } from "./model/productCategoryPnlModelInternals";

type HistoryQuery = UseQueryResult<
  Awaited<ReturnType<ApiClient["getProductCategoryHistory"]>>,
  Error
>;
type AttributionQuery = UseQueryResult<
  Awaited<ReturnType<ApiClient["getProductCategoryAttribution"]>>,
  Error
>;

export function useProductCategoryManagementMonitoring(input: {
  client: ApiClient;
  reportDate: string;
  reportDates: string[] | undefined;
  baseline: Awaited<ReturnType<ApiClient["getProductCategoryPnl"]>> | undefined;
  trendHistoryReportDates: string[];
  trendHistoryQueries: HistoryQuery[];
  attributionQuery: AttributionQuery;
  enabled: boolean;
  scenarioDistinct: boolean;
}) {
  const selected = parseProductCategoryReportDateInternal(input.reportDate);
  const historyPoints = useMemo(
    () =>
      selectProductCategoryTrendReportPoints(
        input.reportDate, input.reportDates, "monthly", 12,
      ).filter((point) =>
        point.reportDate !== input.reportDate &&
        parseProductCategoryReportDateInternal(point.reportDate)?.year === selected?.year,
      ),
    [input.reportDate, input.reportDates, selected?.year],
  );
  // 仅补取趋势最近八期之外的月份；最多四期，沿用现有批量历史接口。
  const supplementalDates = historyPoints
    .map((point) => point.reportDate)
    .filter((date) => !input.trendHistoryReportDates.includes(date));
  const supplementalQueries = useQueries({
    queries: (supplementalDates.length > 0 ? [supplementalDates] : []).map(
      (reportDates) => ({
        queryKey: [
          "product-category-pnl", "management-history-batch",
          input.client.mode, reportDates.join(","),
        ],
        queryFn: () => input.client.getProductCategoryHistory({
          reportDates, view: "monthly",
        }),
        enabled: input.enabled,
        retry: false,
      }),
    ),
  });
  const historyQueries = [...input.trendHistoryQueries, ...supplementalQueries];
  const snapshots = [
    ...(input.baseline
      ? [buildProductCategoryTrendSnapshot(
          input.baseline.result, undefined, input.baseline.result_meta,
        )]
      : []),
    ...historyQueries.flatMap((query) =>
      query.data?.result.items.flatMap((item) =>
        item.status === "ok" && item.result
          ? [buildProductCategoryTrendSnapshot(
              item.result, undefined, item.result_meta ?? undefined,
            )]
          : [],
      ) ?? [],
    ),
  ];
  return {
    surface: selectProductCategoryManagementMonitoringSurface({
      reportDate: input.reportDate,
      snapshots,
      currentAttribution: input.attributionQuery.data?.result,
      scenarioDistinct: input.scenarioDistinct,
    }),
    isLoading: !input.scenarioDistinct &&
      (input.attributionQuery.isLoading || historyQueries.some((query) => query.isLoading)),
    isError: !input.scenarioDistinct &&
      (input.attributionQuery.isError || historyQueries.some((query) => query.isError)),
    onRetry: () => {
      void Promise.all([
        input.attributionQuery.refetch(),
        ...historyQueries.map((query) => query.refetch()),
      ]);
    },
  };
}
