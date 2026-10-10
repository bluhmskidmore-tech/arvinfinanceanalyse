import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type { ProductCategoryPnlPayload, ResultMeta } from "../../../api/contracts";
import {
  selectProductCategoryTrendReportPoints,
  selectProductCategoryTwoYearInterestSpreadReportPoints,
} from "./productCategoryPnlPageModel";

type ProductCategoryHistoryOptions = {
  client: ApiClient;
  selectedDate: string;
  reportDates: string[] | undefined;
  selectedView: string;
  appliedScenarioRate: string;
  trendWorkspaceOpen: boolean;
  trendHistoryConsumerOpen: boolean;
  attributionHistoryConsumerOpen: boolean;
};

export function uniqueProductCategoryReportDates(
  points: ReadonlyArray<{ reportDate: string }>,
): string[] {
  const seen = new Set<string>();
  const reportDates: string[] = [];
  points.forEach((point) => {
    if (!point.reportDate || seen.has(point.reportDate)) {
      return;
    }
    seen.add(point.reportDate);
    reportDates.push(point.reportDate);
  });
  return reportDates;
}

/**
 * Measured against the live read model: a few medium chunks beat both per-period requests
 * (queue behind the browser's per-host connection limit) and one giant chunk (queues
 * behind the backend's bounded worker pool).
 */
const PRODUCT_CATEGORY_HISTORY_BATCH_SIZE = 10;

function chunkProductCategoryReportDates(
  reportDates: string[],
  size = PRODUCT_CATEGORY_HISTORY_BATCH_SIZE,
): string[][] {
  const chunks: string[][] = [];
  for (let index = 0; index < reportDates.length; index += size) {
    chunks.push(reportDates.slice(index, index + size));
  }
  return chunks;
}

/** Owns the disjoint recent-history and two-year comparison request windows. */
export function useProductCategoryHistoryQueries({
  client,
  selectedDate,
  reportDates,
  selectedView,
  appliedScenarioRate,
  trendWorkspaceOpen,
  trendHistoryConsumerOpen,
  attributionHistoryConsumerOpen,
}: ProductCategoryHistoryOptions) {
  const trendDiagnosticsLoaded = Boolean(selectedDate);

  const trendReportPoints = useMemo(
    () =>
      selectProductCategoryTrendReportPoints(
        selectedDate,
        reportDates,
        selectedView,
      ),
    [reportDates, selectedDate, selectedView],
  );
  const currentTrendPoint = useMemo(
    () => trendReportPoints.find((point) => point.reportDate === selectedDate),
    [selectedDate, trendReportPoints],
  );
  const trendHistoryPoints = useMemo(
    () =>
      trendReportPoints.filter((point) => point.reportDate !== selectedDate),
    [selectedDate, trendReportPoints],
  );
  const trendHistoryReportDates = useMemo(
    () => uniqueProductCategoryReportDates(trendHistoryPoints),
    [trendHistoryPoints],
  );
  const trendHistoryView = trendHistoryPoints[0]?.view ?? selectedView;
  const trendHistoryBatches = useMemo(
    () => chunkProductCategoryReportDates(trendHistoryReportDates),
    [trendHistoryReportDates],
  );
  const trendHistoryQueries = useQueries({
    queries: trendHistoryBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-batch",
        client.mode,
        batchReportDates.join(","),
        trendHistoryView,
        appliedScenarioRate,
      ],
      queryFn: () =>
        client.getProductCategoryHistory({
          reportDates: batchReportDates,
          view: trendHistoryView,
          ...(appliedScenarioRate
            ? { scenarioRatePct: appliedScenarioRate }
            : {}),
        }),
      enabled: Boolean(trendHistoryConsumerOpen && trendDiagnosticsLoaded),
      retry: false,
    })),
  });
  const trendHistoryAttributionQueries = useQueries({
    queries: trendHistoryBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-attribution-batch",
        client.mode,
        batchReportDates.join(","),
        "mom",
      ],
      queryFn: () =>
        client.getProductCategoryAttributionHistory({
          reportDates: batchReportDates,
          compare: "mom",
        }),
      enabled: Boolean(
        attributionHistoryConsumerOpen &&
        trendDiagnosticsLoaded &&
        selectedView === "monthly",
      ),
      retry: false,
    })),
  });
  const interestSpreadComparisonReportPoints = useMemo(
    () =>
      selectProductCategoryTwoYearInterestSpreadReportPoints(
        selectedDate,
        reportDates,
        selectedView,
      ),
    [reportDates, selectedDate, selectedView],
  );
  const interestSpreadComparisonCurrentPoint = useMemo(
    () =>
      interestSpreadComparisonReportPoints.find(
        (point) => point.reportDate === selectedDate,
      ),
    [interestSpreadComparisonReportPoints, selectedDate],
  );
  const interestSpreadComparisonHistoryPoints = useMemo(
    () =>
      interestSpreadComparisonReportPoints.filter(
        (point) => point.reportDate !== selectedDate,
      ),
    [interestSpreadComparisonReportPoints, selectedDate],
  );
  // Only the months the trend batch does not already cover, so the two batches stay disjoint
  // and opening the diagnostics workspace alone never pulls the wider comparison window.
  const interestSpreadOnlyReportDates = useMemo(() => {
    const covered = new Set(trendHistoryReportDates);
    return uniqueProductCategoryReportDates(
      interestSpreadComparisonHistoryPoints,
    ).filter((reportDate) => !covered.has(reportDate));
  }, [interestSpreadComparisonHistoryPoints, trendHistoryReportDates]);
  const interestSpreadHistoryView =
    interestSpreadComparisonHistoryPoints[0]?.view ?? selectedView;
  const interestSpreadHistoryBatches = useMemo(
    () => chunkProductCategoryReportDates(interestSpreadOnlyReportDates),
    [interestSpreadOnlyReportDates],
  );
  const interestSpreadHistoryQueries = useQueries({
    queries: interestSpreadHistoryBatches.map((batchReportDates) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-batch",
        client.mode,
        batchReportDates.join(","),
        interestSpreadHistoryView,
        appliedScenarioRate,
      ],
      queryFn: () =>
        client.getProductCategoryHistory({
          reportDates: batchReportDates,
          view: interestSpreadHistoryView,
          ...(appliedScenarioRate
            ? { scenarioRatePct: appliedScenarioRate }
            : {}),
        }),
      enabled: Boolean(trendWorkspaceOpen && trendDiagnosticsLoaded),
      retry: false,
    })),
  });
  /** Merged period lookup so each consumer resolves its own points regardless of which batch carried them. */
  const historyPayloadByReportDate = useMemo(() => {
    const byReportDate = new Map<
      string,
      { payload: ProductCategoryPnlPayload; resultMeta: ResultMeta | undefined }
    >();
    [...trendHistoryQueries, ...interestSpreadHistoryQueries].forEach(
      (query) => {
        query.data?.result.items.forEach((item) => {
          if (item.status !== "ok" || !item.result) {
            return;
          }
          byReportDate.set(item.report_date, {
            payload: item.result,
            resultMeta: item.result_meta ?? undefined,
          });
        });
      },
    );
    return byReportDate;
  }, [interestSpreadHistoryQueries, trendHistoryQueries]);

  return {
    trendReportPoints,
    currentTrendPoint,
    trendHistoryPoints,
    trendHistoryReportDates,
    trendHistoryBatches,
    trendHistoryQueries,
    trendHistoryAttributionQueries,
    interestSpreadComparisonCurrentPoint,
    interestSpreadComparisonHistoryPoints,
    interestSpreadHistoryBatches,
    interestSpreadHistoryQueries,
    historyPayloadByReportDate,
  };
}
