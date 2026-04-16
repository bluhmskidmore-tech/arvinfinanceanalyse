import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../api/client";
import {
  buildSourcePreviewHistoryQuery,
  buildSourcePreviewRowsQuery,
  buildSourcePreviewTracesQuery,
  SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
  SOURCE_PREVIEW_HISTORY_PAGE_SIZE,
} from "../features/source-preview/sourcePreviewApi";

function createMockClient(): ApiClient {
  return {
    mode: "real",
    getHealth: vi.fn(),
    getOverview: vi.fn(),
    getSummary: vi.fn(),
    getFormalPnlDates: vi.fn(),
    getFormalPnlData: vi.fn(),
    getFormalPnlOverview: vi.fn(),
    getPnlBridge: vi.fn(),
    refreshFormalPnl: vi.fn(),
    getFormalPnlImportStatus: vi.fn(),
    getPnlAttribution: vi.fn(),
    getRiskOverview: vi.fn(),
    getContribution: vi.fn(),
    getAlerts: vi.fn(),
    getPlaceholderSnapshot: vi.fn(),
    getSourceFoundation: vi.fn(),
    refreshSourcePreview: vi.fn(),
    getSourcePreviewRefreshStatus: vi.fn(),
    getSourceFoundationHistory: vi.fn(async () => ({ result_meta: {} as never, result: {} as never })),
    getSourceFoundationRows: vi.fn(async () => ({ result_meta: {} as never, result: {} as never })),
    getSourceFoundationTraces: vi.fn(async () => ({ result_meta: {} as never, result: {} as never })),
    getProductCategoryDates: vi.fn(),
    refreshProductCategoryPnl: vi.fn(),
    getProductCategoryRefreshStatus: vi.fn(),
    createProductCategoryManualAdjustment: vi.fn(),
    getProductCategoryManualAdjustments: vi.fn(),
    updateProductCategoryManualAdjustment: vi.fn(),
    revokeProductCategoryManualAdjustment: vi.fn(),
    restoreProductCategoryManualAdjustment: vi.fn(),
    getProductCategoryPnl: vi.fn(),
  } as unknown as ApiClient;
}

describe("sourcePreviewApi", () => {
  it("builds a family-scoped history query with the feature page size", async () => {
    const client = createMockClient();

    const query = buildSourcePreviewHistoryQuery(client, "zqtz", 4);
    await query.queryFn();

    expect(query.queryKey).toEqual(["source-preview-history", "real", "zqtz", 4]);
    expect(client.getSourceFoundationHistory).toHaveBeenCalledWith({
      sourceFamily: "zqtz",
      limit: SOURCE_PREVIEW_HISTORY_PAGE_SIZE,
      offset: 4,
    });
  });

  it("builds rows and traces queries with the feature detail page size", async () => {
    const client = createMockClient();

    const rowsQuery = buildSourcePreviewRowsQuery(client, "tyw", "batch-1", 20);
    const tracesQuery = buildSourcePreviewTracesQuery(client, "tyw", "batch-1", 40);

    await rowsQuery.queryFn();
    await tracesQuery.queryFn();

    expect(client.getSourceFoundationRows).toHaveBeenCalledWith({
      sourceFamily: "tyw",
      ingestBatchId: "batch-1",
      limit: SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
      offset: 20,
    });
    expect(client.getSourceFoundationTraces).toHaveBeenCalledWith({
      sourceFamily: "tyw",
      ingestBatchId: "batch-1",
      limit: SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
      offset: 40,
    });
  });

  it("uses separate TanStack Query key namespaces for history, rows, and traces", () => {
    const client = createMockClient();
    const history = buildSourcePreviewHistoryQuery(client, "zqtz", 8);
    const rows = buildSourcePreviewRowsQuery(client, "zqtz", "ib-1", 8);
    const traces = buildSourcePreviewTracesQuery(client, "zqtz", "ib-1", 8);
    expect(history.queryKey[0]).toBe("source-preview-history");
    expect(rows.queryKey[0]).toBe("source-preview-rows");
    expect(traces.queryKey[0]).toBe("source-preview-traces");
  });
});
