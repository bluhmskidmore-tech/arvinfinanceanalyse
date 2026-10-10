/**
 * Demo/mock ProductCategory client.
 * Loaded only by mock composition paths and tests.
 */
import type {
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
} from "../api/contracts";
import type { ProductCategoryClientMethods } from "../api/productCategoryClient";
type Delay = () => Promise<void>;

type ProductCategoryMockBundle = Pick<
  typeof import("./mockApiEnvelope"),
  "buildMockApiEnvelope"
> &
  Pick<
    typeof import("./productCategoryPnl"),
    "buildMockProductCategoryPnlEnvelope" | "buildMockProductCategoryAttributionEnvelope"
  >;

let productCategoryMockBundleCache: ProductCategoryMockBundle | null = null;

async function ensureProductCategoryMockBundle(): Promise<ProductCategoryMockBundle> {
  productCategoryMockBundleCache ??= await loadProductCategoryMockBundle();
  return productCategoryMockBundleCache;
}

async function loadProductCategoryMockBundle(): Promise<ProductCategoryMockBundle> {
  const [apiEnvelopeModule, productCategory] = await Promise.all([
    import("./mockApiEnvelope"),
    import("./productCategoryPnl"),
  ]);

  return {
    buildMockApiEnvelope: apiEnvelopeModule.buildMockApiEnvelope,
    buildMockProductCategoryPnlEnvelope: productCategory.buildMockProductCategoryPnlEnvelope,
    buildMockProductCategoryAttributionEnvelope:
      productCategory.buildMockProductCategoryAttributionEnvelope,
  };
}

function reduceLatestManualAdjustments<
  T extends { adjustment_id: string; created_at: string },
>(records: T[]): T[] {
  const latestById = new Map<string, T>();
  for (const record of records) {
    const existing = latestById.get(record.adjustment_id);
    if (!existing || record.created_at >= existing.created_at) {
      latestById.set(record.adjustment_id, record);
    }
  }
  return Array.from(latestById.values());
}

function filterManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  },
>(
  records: T[],
  options: ProductCategoryManualAdjustmentQuery = {},
  applyEventType = true,
): T[] {
  const adjustmentId = options.adjustmentId?.trim() ?? "";
  const adjustmentIdExact = options.adjustmentIdExact ?? false;
  const accountCode = options.accountCode?.trim() ?? "";
  const approvalStatus = options.approvalStatus?.trim() ?? "";
  const eventType = options.eventType?.trim() ?? "";
  const createdAtFrom = options.createdAtFrom?.trim() ?? "";
  const createdAtTo = options.createdAtTo?.trim() ?? "";

  return records.filter((record) => {
    if (adjustmentId) {
      if (adjustmentIdExact) {
        if (record.adjustment_id !== adjustmentId) {
          return false;
        }
      } else if (!record.adjustment_id.includes(adjustmentId)) {
        return false;
      }
    }
    if (accountCode && !record.account_code.includes(accountCode)) {
      return false;
    }
    if (approvalStatus && record.approval_status !== approvalStatus) {
      return false;
    }
    if (applyEventType && eventType && record.event_type !== eventType) {
      return false;
    }
    if (createdAtFrom && record.created_at < createdAtFrom) {
      return false;
    }
    if (createdAtTo && record.created_at > createdAtTo) {
      return false;
    }
    return true;
  });
}

function sortManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  },
>(
  records: T[],
  field:
    | "created_at"
    | "adjustment_id"
    | "event_type"
    | "approval_status"
    | "account_code",
  direction: "asc" | "desc",
) {
  const sorted = [...records].sort((left, right) => {
    const leftValue = String(left[field] ?? "").toLowerCase();
    const rightValue = String(right[field] ?? "").toLowerCase();
    return leftValue.localeCompare(rightValue);
  });
  return direction === "desc" ? sorted.reverse() : sorted;
}

export function createDemoProductCategoryClient(delay: Delay): ProductCategoryClientMethods {
  const mockManualAdjustments: ProductCategoryManualAdjustmentPayload[] = [];
  let mockManualAdjustmentSeq = 0;

  return {
    async getProductCategoryDates() {
      await delay();
      return (await ensureProductCategoryMockBundle()).buildMockApiEnvelope(
        "product_category_pnl.dates",
        {
          report_dates: ["2026-02-28", "2026-01-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshProductCategoryPnl() {
      await delay();
      return {
        status: "queued",
        run_id: "product_category_pnl:mock-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
      };
    },
    async getProductCategoryRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
        month_count: 2,
        report_dates: ["2026-01-31", "2026-02-28"],
        rule_version: "rv_product_category_pnl_v2",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async createProductCategoryManualAdjustment(payload) {
      await delay();
      mockManualAdjustmentSeq += 1;
      const record = {
        adjustment_id: `pca-mock-${mockManualAdjustmentSeq}`,
        event_type: "created",
        created_at: "2026-04-10T09:30:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: payload.report_date,
        operator: payload.operator,
        approval_status: payload.approval_status,
        account_code: payload.account_code,
        currency: payload.currency,
        account_name: payload.account_name ?? "",
        beginning_balance: payload.beginning_balance ?? null,
        ending_balance: payload.ending_balance ?? null,
        monthly_pnl: payload.monthly_pnl ?? null,
        daily_avg_balance: payload.daily_avg_balance ?? null,
        annual_avg_balance: payload.annual_avg_balance ?? null,
      };
      mockManualAdjustments.unshift(record);
      return record;
    },
    async getProductCategoryManualAdjustments(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const events = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const limit = options.limit ?? 20;
      const offset = options.offset ?? 0;
      const adjustmentLimit = options.adjustmentLimit ?? 20;
      const adjustmentOffset = options.adjustmentOffset ?? 0;
      const pagedEvents = events.slice(offset, offset + limit);
      const adjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      return {
        report_date: reportDate,
        adjustment_count: adjustments.length,
        adjustment_limit: adjustmentLimit,
        adjustment_offset: adjustmentOffset,
        event_total: events.length,
        event_limit: limit,
        event_offset: offset,
        adjustments: adjustments.slice(
          adjustmentOffset,
          adjustmentOffset + adjustmentLimit,
        ),
        events: pagedEvents,
      };
    },
    async exportProductCategoryManualAdjustmentsCsv(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const filteredEvents = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const filteredAdjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      const headers = [
        "adjustment_id",
        "event_type",
        "created_at",
        "report_date",
        "operator",
        "approval_status",
        "account_code",
        "currency",
        "account_name",
      ];
      const toCsv = (rows: ProductCategoryManualAdjustmentPayload[]) =>
        rows
          .map((row) =>
            headers
              .map((header) => {
                const value = String(
                  (row as Record<string, string | number | null | undefined>)[header] ?? "",
                ).replace(/"/g, '""');
                return `"${value}"`;
              })
              .join(","),
          )
          .join("\n");
      return {
        filename: `product-category-audit-${reportDate}.csv`,
        content: [
          "Current State",
          headers.join(","),
          toCsv(filteredAdjustments),
          "",
          "Event Timeline",
          headers.join(","),
          toCsv(filteredEvents),
        ].join("\n"),
      };
    },
    async updateProductCategoryManualAdjustment(adjustmentId, payload) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const updated = {
        ...mockManualAdjustments[index],
        ...payload,
        event_type: "edited",
        created_at: "2026-04-10T09:40:00Z",
      };
      mockManualAdjustments.unshift(updated);
      return updated;
    },
    async revokeProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const revoked = {
        ...mockManualAdjustments[index],
        event_type: "revoked",
        approval_status: "rejected",
        created_at: "2026-04-10T09:45:00Z",
      };
      mockManualAdjustments.unshift(revoked);
      return revoked;
    },
    async restoreProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const restored = {
        ...mockManualAdjustments[index],
        event_type: "restored",
        approval_status: "approved",
        created_at: "2026-04-10T09:50:00Z",
      };
      mockManualAdjustments.unshift(restored);
      return restored;
    },
    async getProductCategoryPnl(options) {
      await delay();
      return (await ensureProductCategoryMockBundle()).buildMockProductCategoryPnlEnvelope(
        options,
      );
    },
    async getProductCategoryAttribution(options) {
      await delay();
      return (await ensureProductCategoryMockBundle()).buildMockProductCategoryAttributionEnvelope(
        options,
      );
    },
    /**
     * Delegates per period to `getProductCategoryPnl` so the batch stays exactly N single
     * reads — the same relationship the backend batch route has — and so a caller that
     * overrides the single-period method (tests, fixtures) also drives the batch.
     */
    async getProductCategoryHistory(
      this: ProductCategoryClientMethods,
      { reportDates, view, scenarioRatePct },
    ) {
      const bundle = await ensureProductCategoryMockBundle();
      const items = await Promise.all(
        reportDates.map(async (reportDate) => {
          const envelope = await this.getProductCategoryPnl({
            reportDate,
            view,
            ...(scenarioRatePct ? { scenarioRatePct } : {}),
          });
          return {
            report_date: reportDate,
            status: "ok" as const,
            detail: null,
            result: envelope.result,
            result_meta: envelope.result_meta,
          };
        }),
      );
      return bundle.buildMockApiEnvelope("product_category_pnl.history", {
        view,
        scenario_rate_pct: scenarioRatePct ?? null,
        items,
      });
    },
    async getProductCategoryAttributionHistory(
      this: ProductCategoryClientMethods,
      { reportDates, compare = "mom" },
    ) {
      const bundle = await ensureProductCategoryMockBundle();
      const items = await Promise.all(
        reportDates.map(async (reportDate) => {
          const envelope = await this.getProductCategoryAttribution({
            reportDate,
            compare,
          });
          return {
            report_date: reportDate,
            status: "ok" as const,
            detail: null,
            result: envelope.result,
            result_meta: envelope.result_meta,
          };
        }),
      );
      return bundle.buildMockApiEnvelope(
        "product_category_pnl.attribution_history",
        { compare, items },
      );
    },
  };
}
