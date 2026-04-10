import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import type { SourcePreviewColumn } from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";
import {
  buildSourcePreviewHistoryQuery,
  buildSourcePreviewRowsQuery,
  buildSourcePreviewTracesQuery,
  SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
  SOURCE_PREVIEW_HISTORY_PAGE_SIZE,
} from "../sourcePreviewApi";

const sectionShell: CSSProperties = {
  height: "100%",
  padding: 24,
  borderRadius: 20,
  background: "#fbfcfe",
  border: "1px solid #e4ebf5",
  boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
};

const sectionHeaderRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  marginBottom: 16,
};

const pagerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginTop: 14,
};

function readString(row: Record<string, unknown>, key: string) {
  const value = row[key];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function readNumber(row: Record<string, unknown>, key: string) {
  const value = row[key];
  return typeof value === "number" ? value : undefined;
}

function formatCellValue(value: unknown, type: SourcePreviewColumn["type"]) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (type === "boolean") {
    return value === true ? "true" : value === false ? "false" : String(value);
  }
  if (type === "number") {
    return String(value);
  }
  if (typeof value === "number" || typeof value === "string") {
    return String(value);
  }
  return JSON.stringify(value);
}

function clampOffset(offset: number) {
  return Math.max(0, offset);
}

function pagerDisabled(offset: number, pageSize: number, totalRows: number) {
  return offset + pageSize >= totalRows;
}

function currentPage(offset: number, pageSize: number) {
  return Math.floor(offset / pageSize) + 1;
}

function totalPages(totalRows: number, pageSize: number) {
  return Math.max(1, Math.ceil(totalRows / pageSize));
}

function buildRefreshStatusText(payload: {
  status: string;
  job_name?: string;
  trigger_mode?: string;
  cache_key?: string;
  ingest_batch_id?: string | null;
  preview_sources?: string[];
  report_dates?: string[];
  source_version?: string;
}) {
  return [
    `最近结果：${payload.status}`,
    payload.job_name ? `任务 ${payload.job_name}` : null,
    payload.trigger_mode ? `触发 ${payload.trigger_mode}` : null,
    payload.cache_key ? `cache ${payload.cache_key}` : null,
    payload.ingest_batch_id ? `批次 ${payload.ingest_batch_id}` : null,
    payload.preview_sources?.length ? payload.preview_sources.join(" / ") : null,
    payload.report_dates?.length ? `报告日 ${payload.report_dates.join(", ")}` : null,
    payload.source_version ? `source ${payload.source_version}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function GenericPreviewTable({
  columns,
  rows,
  tableTestId,
}: {
  columns: SourcePreviewColumn[];
  rows: Array<Record<string, unknown>>;
  tableTestId: string;
}) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        data-testid={tableTestId}
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13,
        }}
      >
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #d7dfea" }}>
            {columns.map((column) => (
              <th
                key={column.key}
                style={{
                  padding: "10px 8px",
                  whiteSpace: "nowrap",
                  color: "#5c6b82",
                  fontWeight: 600,
                }}
                scope="col"
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={[
                readString(row, "ingest_batch_id") ?? "batch",
                readNumber(row, "row_locator") ?? index,
                readNumber(row, "trace_step") ?? "notrace",
              ].join("-")}
              style={{ borderBottom: "1px solid #e4ebf5" }}
            >
              {columns.map((column) => (
                <td
                  key={`${index}-${column.key}`}
                  style={{
                    padding: "10px 8px",
                    verticalAlign: "top",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatCellValue(row[column.key], column.type)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SourcePreviewPage() {
  const client = useApiClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const [lastRefreshStatus, setLastRefreshStatus] = useState<string | null>(null);
  const previewQuery = useQuery({
    queryKey: ["source-preview", client.mode],
    queryFn: () => client.getSourceFoundation(),
    retry: false,
  });

  const sources = useMemo(
    () => previewQuery.data?.result.sources ?? [],
    [previewQuery.data?.result.sources],
  );
  const sourceFamilies = useMemo(
    () => [...new Set(sources.map((row) => row.source_family))],
    [sources],
  );

  const [selectedSourceFamily, setSelectedSourceFamily] = useState("");
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [historyOffset, setHistoryOffset] = useState(0);
  const [rowsOffset, setRowsOffset] = useState(0);
  const [tracesOffset, setTracesOffset] = useState(0);

  useEffect(() => {
    if (!selectedSourceFamily && sourceFamilies.length > 0) {
      setSelectedSourceFamily(sourceFamilies[0]);
    }
  }, [selectedSourceFamily, sourceFamilies]);

  const historyQuery = useQuery({
    ...buildSourcePreviewHistoryQuery(client, selectedSourceFamily, historyOffset),
  });

  const historyRows = useMemo(
    () => historyQuery.data?.result.rows ?? [],
    [historyQuery.data?.result.rows],
  );
  const historyTotalRows = historyQuery.data?.result.total_rows ?? 0;

  const effectiveBatchId = useMemo(() => {
    if (!historyRows.length) {
      return "";
    }
    if (
      selectedBatchId &&
      historyRows.some((row) => row.ingest_batch_id === selectedBatchId)
    ) {
      return selectedBatchId;
    }
    return String(historyRows[0].ingest_batch_id ?? "");
  }, [historyRows, selectedBatchId]);

  useEffect(() => {
    if (!historyRows.length) {
      if (selectedBatchId) {
        setSelectedBatchId("");
        setRowsOffset(0);
        setTracesOffset(0);
      }
      return;
    }
    if (selectedBatchId !== effectiveBatchId) {
      setSelectedBatchId(effectiveBatchId);
      setRowsOffset(0);
      setTracesOffset(0);
    }
  }, [effectiveBatchId, historyRows, selectedBatchId]);

  const rowsQuery = useQuery({
    ...buildSourcePreviewRowsQuery(
      client,
      selectedSourceFamily,
      effectiveBatchId,
      rowsOffset,
    ),
  });

  const tracesQuery = useQuery({
    ...buildSourcePreviewTracesQuery(
      client,
      selectedSourceFamily,
      effectiveBatchId,
      tracesOffset,
    ),
  });

  const rowsTotal = rowsQuery.data?.result.total_rows ?? 0;
  const rowColumns = rowsQuery.data?.result.columns ?? [];
  const tracesTotal = tracesQuery.data?.result.total_rows ?? 0;
  const traceColumns = tracesQuery.data?.result.columns ?? [];
  const isEmpty =
    !previewQuery.isLoading && !previewQuery.isError && sources.length === 0;

  function handleSourceFamilyChange(nextFamily: string) {
    setSelectedSourceFamily(nextFamily);
    setSelectedBatchId("");
    setHistoryOffset(0);
    setRowsOffset(0);
    setTracesOffset(0);
  }

  function handleBatchChange(nextBatchId: string) {
    setSelectedBatchId(nextBatchId);
    setRowsOffset(0);
    setTracesOffset(0);
  }

  async function handleRefresh() {
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshSourcePreview(),
        getStatus: (runId) => client.getSourcePreviewRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          setLastRefreshRunId(nextPayload.run_id);
          setLastRefreshStatus(buildRefreshStatusText(nextPayload));
        },
      });
      if (payload.status !== "completed") {
        const hint =
          payload.error_message ??
          payload.detail ??
          `数据源预览刷新未完成：${payload.status}`;
        const rid = payload.run_id ? ` run_id: ${payload.run_id}` : "";
        throw new Error(`${hint}${rid}`);
      }
      setHistoryOffset(0);
      setRowsOffset(0);
      setTracesOffset(0);
      await Promise.all([
        previewQuery.refetch(),
        historyQuery.refetch(),
        rowsQuery.refetch(),
        tracesQuery.refetch(),
      ]);
    } catch (error) {
      setRefreshError(
        error instanceof Error ? error.message : "数据源预览刷新失败",
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              marginTop: 0,
              marginBottom: 10,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            数据源规则预览
          </h1>
          <p
            style={{
              marginTop: 0,
              marginBottom: 0,
              color: "#5c6b82",
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            汇总查看 ZQTZ、TYW 等数据源的规则命中与人工复核提示。下钻结果以真实 preview
            API 返回为准。
          </p>
          {lastRefreshRunId ? (
            <p
              data-testid="source-preview-refresh-run-id"
              style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}
            >
              最近刷新任务：{lastRefreshRunId}
            </p>
          ) : null}
          {lastRefreshStatus ? (
            <p
              data-testid="source-preview-refresh-status"
              style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}
            >
              {lastRefreshStatus}
            </p>
          ) : null}
          {refreshError ? (
            <p
              style={{ marginTop: 8, marginBottom: 0, color: "#b42318", fontSize: 12 }}
            >
              {refreshError}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          data-testid="source-preview-refresh-button"
          onClick={() => void handleRefresh()}
          disabled={isRefreshing}
          style={{
            padding: "10px 16px",
            borderRadius: 12,
            border: "1px solid #162033",
            background: "#fbfcfe",
            color: "#162033",
            fontWeight: 600,
            cursor: isRefreshing ? "progress" : "pointer",
            opacity: isRefreshing ? 0.7 : 1,
          }}
        >
          {isRefreshing ? "刷新中..." : "刷新数据源预览"}
        </button>
      </div>

      <section style={sectionShell}>
        <div style={sectionHeaderRow}>
          <span style={{ fontWeight: 600 }}>规则预览摘要</span>
        </div>
        <AsyncSection
          title="规则预览摘要"
          isLoading={previewQuery.isLoading}
          isError={previewQuery.isError}
          isEmpty={isEmpty}
          onRetry={() => void previewQuery.refetch()}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 16,
            }}
          >
            {sources.map((source) => {
              const groups = Object.entries(source.group_counts)
                .map(([label, count]) => `${label} ${count}`)
                .join(" / ");

              return (
                <PlaceholderCard
                  key={`${source.source_family}:${source.ingest_batch_id ?? source.report_date ?? source.source_version}`}
                  title={source.source_family.toUpperCase()}
                  value={`共 ${source.total_rows} 行`}
                  detail={`报告日期：${source.report_date ?? "—"} · ${groups || "暂无分组"} · 待人工复核 ${source.manual_review_count} 行`}
                  valueVariant="text"
                />
              );
            })}
          </div>
        </AsyncSection>
      </section>

      <section style={{ ...sectionShell, marginTop: 18 }}>
        <div style={sectionHeaderRow}>
          <span style={{ fontWeight: 600 }}>下钻明细</span>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
            marginBottom: 20,
          }}
        >
          <label style={{ display: "grid", gap: 8 }}>
            <span>Source family</span>
            <select
              aria-label="source-family"
              value={selectedSourceFamily}
              onChange={(event) => handleSourceFamilyChange(event.target.value)}
            >
              {sourceFamilies.map((family) => (
                <option key={family} value={family}>
                  {family}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "grid", gap: 8 }}>
            <span>Ingest batch</span>
            <select
              aria-label="ingest-batch"
              value={effectiveBatchId}
              onChange={(event) => handleBatchChange(event.target.value)}
            >
              {historyRows.map((batch) => (
                <option
                  key={batch.ingest_batch_id ?? batch.source_version}
                  value={batch.ingest_batch_id ?? ""}
                >
                  {batch.ingest_batch_id}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={pagerRow}>
          <button
            type="button"
            data-testid="source-preview-history-prev"
            disabled={historyOffset === 0}
            onClick={() =>
              setHistoryOffset((current) =>
                clampOffset(current - SOURCE_PREVIEW_HISTORY_PAGE_SIZE),
              )
            }
          >
            上一批
          </button>
          <button
            type="button"
            data-testid="source-preview-history-next"
            disabled={pagerDisabled(
              historyOffset,
              SOURCE_PREVIEW_HISTORY_PAGE_SIZE,
              historyTotalRows,
            )}
            onClick={() =>
              setHistoryOffset((current) => current + SOURCE_PREVIEW_HISTORY_PAGE_SIZE)
            }
          >
            下一批
          </button>
          <span data-testid="source-preview-history-page">
            {currentPage(historyOffset, SOURCE_PREVIEW_HISTORY_PAGE_SIZE)} /{" "}
            {totalPages(historyTotalRows, SOURCE_PREVIEW_HISTORY_PAGE_SIZE)}
          </span>
          <span data-testid="source-preview-history-total">批次总数 {historyTotalRows}</span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 18,
            marginTop: 18,
          }}
        >
          <AsyncSection
            title="行级预览"
            isLoading={rowsQuery.isLoading}
            isError={rowsQuery.isError}
            isEmpty={
              !rowsQuery.isLoading &&
              !rowsQuery.isError &&
              (rowsQuery.data?.result.rows.length ?? 0) === 0
            }
            onRetry={() => void rowsQuery.refetch()}
          >
            <GenericPreviewTable
              columns={rowColumns}
              rows={rowsQuery.data?.result.rows ?? []}
              tableTestId="source-preview-rows-table"
            />
            <div style={pagerRow}>
              <button
                type="button"
                data-testid="source-preview-rows-prev"
                disabled={rowsOffset === 0}
                onClick={() =>
                  setRowsOffset((current) =>
                    clampOffset(current - SOURCE_PREVIEW_DETAIL_PAGE_SIZE),
                  )
                }
              >
                上一页
              </button>
              <button
                type="button"
                data-testid="source-preview-rows-next"
                disabled={pagerDisabled(
                  rowsOffset,
                  SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
                  rowsTotal,
                )}
                onClick={() =>
                  setRowsOffset((current) => current + SOURCE_PREVIEW_DETAIL_PAGE_SIZE)
                }
              >
                下一页
              </button>
              <span data-testid="source-preview-rows-page">
                {currentPage(rowsOffset, SOURCE_PREVIEW_DETAIL_PAGE_SIZE)} /{" "}
                {totalPages(rowsTotal, SOURCE_PREVIEW_DETAIL_PAGE_SIZE)}
              </span>
              <span data-testid="source-preview-rows-total">行数 {rowsTotal}</span>
            </div>
          </AsyncSection>

          <AsyncSection
            title="规则轨迹"
            isLoading={tracesQuery.isLoading}
            isError={tracesQuery.isError}
            isEmpty={
              !tracesQuery.isLoading &&
              !tracesQuery.isError &&
              (tracesQuery.data?.result.rows.length ?? 0) === 0
            }
            onRetry={() => void tracesQuery.refetch()}
          >
            <GenericPreviewTable
              columns={traceColumns}
              rows={tracesQuery.data?.result.rows ?? []}
              tableTestId="source-preview-traces-table"
            />
            <div style={pagerRow}>
              <button
                type="button"
                data-testid="source-preview-traces-prev"
                disabled={tracesOffset === 0}
                onClick={() =>
                  setTracesOffset((current) =>
                    clampOffset(current - SOURCE_PREVIEW_DETAIL_PAGE_SIZE),
                  )
                }
              >
                上一页
              </button>
              <button
                type="button"
                data-testid="source-preview-traces-next"
                disabled={pagerDisabled(
                  tracesOffset,
                  SOURCE_PREVIEW_DETAIL_PAGE_SIZE,
                  tracesTotal,
                )}
                onClick={() =>
                  setTracesOffset((current) => current + SOURCE_PREVIEW_DETAIL_PAGE_SIZE)
                }
              >
                下一页
              </button>
              <span data-testid="source-preview-traces-page">
                {currentPage(tracesOffset, SOURCE_PREVIEW_DETAIL_PAGE_SIZE)} /{" "}
                {totalPages(tracesTotal, SOURCE_PREVIEW_DETAIL_PAGE_SIZE)}
              </span>
              <span data-testid="source-preview-traces-total">轨迹数 {tracesTotal}</span>
            </div>
          </AsyncSection>
        </div>
      </section>
    </section>
  );
}
