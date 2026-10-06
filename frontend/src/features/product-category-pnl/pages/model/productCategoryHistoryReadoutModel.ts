import type {
  ProductCategoryAttributionHistoryPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryHistoryItem,
  ProductCategoryPnlPayload,
  ResultMeta,
} from "../../../../api/contracts";
import { countProductCategoryComparableReportMonths } from "../ProductCategoryComparisonCharts";
import {
  buildProductCategoryTrendSnapshot,
  formatProductCategoryReportMonthLabel,
  type ProductCategoryTrendReportPoint,
  type ProductCategoryTrendSnapshot,
} from "../productCategoryPnlPageModel";

type HistoryPayloadEntry = {
  payload: ProductCategoryPnlPayload;
  resultMeta: ResultMeta | undefined;
};

type HistoryQueryState = {
  isError: boolean;
  isFetching: boolean;
  data?: unknown;
};

/** Resolves each consumer's requested periods without filling missing dates. */
export function buildProductCategoryHistorySnapshots(input: {
  enabled: boolean;
  currentPayload?: ProductCategoryPnlPayload;
  currentLabel?: string;
  currentResultMeta?: ResultMeta;
  historyPoints: ReadonlyArray<Pick<ProductCategoryTrendReportPoint, "reportDate" | "label">>;
  historyPayloadByReportDate: ReadonlyMap<string, HistoryPayloadEntry>;
}): ProductCategoryTrendSnapshot[] {
  if (!input.enabled) {
    return [];
  }
  return [
    ...(input.currentPayload
      ? [
          buildProductCategoryTrendSnapshot(
            input.currentPayload,
            input.currentLabel,
            input.currentResultMeta,
          ),
        ]
      : []),
    ...input.historyPoints.flatMap((point) => {
      const entry = input.historyPayloadByReportDate.get(point.reportDate);
      return entry
        ? [buildProductCategoryTrendSnapshot(entry.payload, point.label, entry.resultMeta)]
        : [];
    }),
  ];
}

export function buildProductCategoryHistoryBatchSnapshots(
  items: readonly ProductCategoryHistoryItem[] | undefined,
): ProductCategoryTrendSnapshot[] {
  return items?.flatMap((item) =>
    item.status === "ok" && item.result
      ? [
          buildProductCategoryTrendSnapshot(
            item.result,
            formatProductCategoryReportMonthLabel(item.report_date),
            item.result_meta ?? undefined,
          ),
        ]
      : [],
  ) ?? [];
}

export function buildProductCategoryBacktestAttributions(input: {
  compare: "mom" | "yoy";
  currentAttribution?: ProductCategoryAttributionPayload;
  historyQueries: ReadonlyArray<{ data?: { result: ProductCategoryAttributionHistoryPayload } }>;
}): Map<string, ProductCategoryAttributionPayload | null> {
  const byReportDate = new Map<string, ProductCategoryAttributionPayload | null>();
  if (input.currentAttribution && input.compare === "mom") {
    byReportDate.set(input.currentAttribution.report_date, input.currentAttribution);
  }
  input.historyQueries.forEach((query) => {
    query.data?.result.items.forEach((item) => {
      if (item.status === "ok" && item.result) {
        byReportDate.set(item.result.report_date, item.result);
      }
    });
  });
  return byReportDate;
}

export function buildProductCategoryComparisonReadout(input: {
  selectedDate: string;
  selectedYearMonth: { year: number; month: number } | null;
  comparisonSnapshots: ProductCategoryTrendSnapshot[];
  historyPoints: ReadonlyArray<Pick<ProductCategoryTrendReportPoint, "reportDate">>;
  historyPayloadByReportDate: ReadonlyMap<string, unknown>;
  trendHistoryBatches: readonly (readonly string[])[];
  trendHistoryQueries: readonly HistoryQueryState[];
  interestSpreadHistoryBatches: readonly (readonly string[])[];
  interestSpreadHistoryQueries: readonly HistoryQueryState[];
  baseline: HistoryQueryState;
}) {
  const ownerByReportDate = new Map<
    string,
    { isError: boolean; isFetching: boolean; hasData: boolean }
  >();
  const indexOwners = (
    batches: readonly (readonly string[])[],
    queries: readonly HistoryQueryState[],
  ) => {
    batches.forEach((batchReportDates, index) => {
      const query = queries[index];
      if (!query) {
        return;
      }
      batchReportDates.forEach((reportDate) => {
        ownerByReportDate.set(reportDate, {
          isError: query.isError,
          isFetching: query.isFetching,
          hasData: Boolean(query.data),
        });
      });
    });
  };
  indexOwners(input.trendHistoryBatches, input.trendHistoryQueries);
  indexOwners(input.interestSpreadHistoryBatches, input.interestSpreadHistoryQueries);

  let loaded = 0;
  let failed = 0;
  let loading = 0;
  // Each period resolves against its batch. An unrequested batch is neither loaded nor failed.
  input.historyPoints.forEach((point) => {
    if (input.historyPayloadByReportDate.has(point.reportDate)) {
      loaded += 1;
      return;
    }
    const owner = ownerByReportDate.get(point.reportDate);
    if (!owner) {
      return;
    }
    if (owner.isError) {
      failed += 1;
    } else if (owner.isFetching) {
      loading += 1;
    } else if (owner.hasData) {
      failed += 1;
    }
  });

  const periodTotal = input.historyPoints.length + (input.selectedDate ? 1 : 0);
  const periodLoaded = loaded + (input.baseline.data ? 1 : 0);
  const periodFailed = failed + (input.baseline.isError ? 1 : 0);
  const periodLoading = loading + (input.baseline.isFetching ? 1 : 0);
  const loadState: "loading" | "partial" | "complete" | "error" =
    periodFailed > 0
      ? periodLoaded > 0
        ? "partial"
        : "error"
      : periodLoading > 0
        ? "loading"
        : periodLoaded < periodTotal
          ? "partial"
          : "complete";
  const loadLabel = [
    `对比期载入 ${periodLoaded}/${periodTotal}`,
    periodLoading > 0 ? `载入中 ${periodLoading}` : null,
    periodFailed > 0
      ? `失败 ${periodFailed}`
      : loadState === "partial"
        ? "载入不全"
        : null,
  ]
    .filter(Boolean)
    .join("；");

  return {
    loadState,
    loadLabel,
    comparableMonthCount: input.selectedYearMonth
      ? countProductCategoryComparableReportMonths(input.comparisonSnapshots, input.selectedYearMonth.year)
      : 0,
    priorPeriodLabel: input.selectedYearMonth
      ? `${input.selectedYearMonth.year - 1}年全年`
      : "上年全年待选",
    currentPeriodLabel: input.selectedYearMonth
      ? `${input.selectedYearMonth.year}年截至${input.selectedYearMonth.month}月`
      : "当前年截止月待选",
  };
}
