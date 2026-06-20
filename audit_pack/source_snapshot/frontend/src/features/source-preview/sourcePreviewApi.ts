import type { ApiClient } from "../../api/client";

export const SOURCE_PREVIEW_HISTORY_PAGE_SIZE = 2;
export const SOURCE_PREVIEW_DETAIL_PAGE_SIZE = 20;

export function buildSourcePreviewHistoryQuery(
  client: ApiClient,
  sourceFamily: string,
  offset: number,
) {
  return {
    queryKey: ["source-preview-history", client.mode, sourceFamily, offset],
    queryFn: () =>
      client.getSourceFoundationHistory({
        sourceFamily,
        limit: SOURCE_PREVIEW_HISTORY_PAGE_SIZE,
        offset,
      }),
    enabled: Boolean(sourceFamily),
    retry: false as const,
  };
}

export function buildSourcePreviewRowsQuery(
  client: ApiClient,
  sourceFamily: string,
  ingestBatchId: string,
  offset: number,
) {
  return {
    queryKey: ["source-preview-rows", client.mode, sourceFamily, ingestBatchId, offset],
    queryFn: () =>
      client.getSourceFoundationRows({
        sourceFamily,
        ingestBatchId,
        limit: SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
        offset,
      }),
    enabled: Boolean(sourceFamily && ingestBatchId),
    retry: false as const,
  };
}

export function buildSourcePreviewTracesQuery(
  client: ApiClient,
  sourceFamily: string,
  ingestBatchId: string,
  offset: number,
) {
  return {
    queryKey: ["source-preview-traces", client.mode, sourceFamily, ingestBatchId, offset],
    queryFn: () =>
      client.getSourceFoundationTraces({
        sourceFamily,
        ingestBatchId,
        limit: SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
        offset,
      }),
    enabled: Boolean(sourceFamily && ingestBatchId),
    retry: false as const,
  };
}
