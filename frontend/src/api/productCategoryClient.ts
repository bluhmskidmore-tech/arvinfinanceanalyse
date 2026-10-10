/**
 * Product Category client slice.
 * Imported by client.ts for ApiClient composition.
 */
import type {
  ApiEnvelope,
  ProductCategoryAttributionHistoryPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryDatesPayload,
  ProductCategoryHistoryPayload,
  ProductCategoryManualAdjustmentExportPayload,
  ProductCategoryManualAdjustmentListPayload,
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryPnlPayload,
  ProductCategoryRefreshPayload,
} from "./contracts";

export type ProductCategoryClientMethods = {
  getProductCategoryDates: () => Promise<ApiEnvelope<ProductCategoryDatesPayload>>;
  refreshProductCategoryPnl: () => Promise<ProductCategoryRefreshPayload>;
  getProductCategoryRefreshStatus: (runId: string) => Promise<ProductCategoryRefreshPayload>;
  createProductCategoryManualAdjustment: (
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryManualAdjustments: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentListPayload>;
  exportProductCategoryManualAdjustmentsCsv: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentExportPayload>;
  updateProductCategoryManualAdjustment: (
    adjustmentId: string,
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  revokeProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  restoreProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryPnl: (options: {
    reportDate: string;
    view: string;
    scenarioRatePct?: string;
  }) => Promise<ApiEnvelope<ProductCategoryPnlPayload>>;
  getProductCategoryAttribution: (options: {
    reportDate: string;
    compare?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<ProductCategoryAttributionPayload>>;
  /** Batch sibling of getProductCategoryPnl: one request for the whole trend window. */
  getProductCategoryHistory: (options: {
    reportDates: string[];
    view: string;
    scenarioRatePct?: string;
  }) => Promise<ApiEnvelope<ProductCategoryHistoryPayload>>;
  getProductCategoryAttributionHistory: (options: {
    reportDates: string[];
    compare?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<ProductCategoryAttributionHistoryPayload>>;
};

type FetchLike = typeof fetch;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

type RequestActionJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
) => Promise<T>;

type RequestText = (
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename?: string,
) => Promise<{ content: string; filename: string }>;

type RequestActionWithBody = <TResponse, TBody>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  body: TBody,
) => Promise<TResponse>;

export type ProductCategoryClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  requestActionJson: RequestActionJson;
  requestText: RequestText;
  requestActionWithBody: RequestActionWithBody;
};

function buildManualAdjustmentSearchParams(
  reportDate: string,
  options: ProductCategoryManualAdjustmentQuery = {},
) {
  const params = new URLSearchParams({
    report_date: reportDate,
  });
  if (options.adjustmentId?.trim()) {
    params.set("adjustment_id", options.adjustmentId.trim());
  }
  if (options.adjustmentIdExact) {
    params.set("adjustment_id_exact", "true");
  }
  if (options.accountCode?.trim()) {
    params.set("account_code", options.accountCode.trim());
  }
  if (options.approvalStatus?.trim()) {
    params.set("approval_status", options.approvalStatus.trim());
  }
  if (options.eventType?.trim()) {
    params.set("event_type", options.eventType.trim());
  }
  if (options.currentSortField) {
    params.set("current_sort_field", options.currentSortField);
  }
  if (options.currentSortDir) {
    params.set("current_sort_dir", options.currentSortDir);
  }
  if (options.eventSortField) {
    params.set("event_sort_field", options.eventSortField);
  }
  if (options.eventSortDir) {
    params.set("event_sort_dir", options.eventSortDir);
  }
  if (options.createdAtFrom?.trim()) {
    params.set("created_at_from", options.createdAtFrom.trim());
  }
  if (options.createdAtTo?.trim()) {
    params.set("created_at_to", options.createdAtTo.trim());
  }
  if (options.adjustmentLimit !== undefined) {
    params.set("adjustment_limit", String(options.adjustmentLimit));
  }
  if (options.adjustmentOffset !== undefined) {
    params.set("adjustment_offset", String(options.adjustmentOffset));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  return params;
}

export function createRealProductCategoryClient(
  options: ProductCategoryClientFactoryOptions,
): ProductCategoryClientMethods {
  const {
    fetchImpl,
    baseUrl,
    requestJson,
    requestActionJson,
    requestText,
    requestActionWithBody,
  } = options;

  return {
    getProductCategoryDates: () =>
      requestJson<ProductCategoryDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/dates",
      ),
    refreshProductCategoryPnl: () =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/refresh",
        {
          method: "POST",
        },
      ),
    getProductCategoryRefreshStatus: (runId: string) =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    createProductCategoryManualAdjustment: (payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/manual-adjustments",
        payload,
      ),
    getProductCategoryManualAdjustments: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestActionJson<ProductCategoryManualAdjustmentListPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments?${params.toString()}`,
      );
    },
    exportProductCategoryManualAdjustmentsCsv: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/export?${params.toString()}`,
        "product-category-audit.csv",
      );
    },
    updateProductCategoryManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        {
          method: "POST",
        },
      ),
    restoreProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        {
          method: "POST",
        },
      ),
    getProductCategoryPnl: ({ reportDate, view, scenarioRatePct }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        view,
      });
      if (scenarioRatePct?.trim()) {
        params.set("scenario_rate_pct", scenarioRatePct);
      }
      return requestJson<ProductCategoryPnlPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category?${params.toString()}`,
      );
    },
    getProductCategoryAttribution: ({ reportDate, compare = "mom" }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        compare,
      });
      return requestJson<ProductCategoryAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/attribution?${params.toString()}`,
      );
    },
    getProductCategoryHistory: ({ reportDates, view, scenarioRatePct }) => {
      const params = new URLSearchParams({
        report_dates: reportDates.join(","),
        view,
      });
      if (scenarioRatePct?.trim()) {
        params.set("scenario_rate_pct", scenarioRatePct);
      }
      return requestJson<ProductCategoryHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/history?${params.toString()}`,
      );
    },
    getProductCategoryAttributionHistory: ({ reportDates, compare = "mom" }) => {
      const params = new URLSearchParams({
        report_dates: reportDates.join(","),
        compare,
      });
      return requestJson<ProductCategoryAttributionHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/attribution/history?${params.toString()}`,
      );
    },
  };
}
