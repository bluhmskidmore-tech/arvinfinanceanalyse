import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../components/PlaceholderCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const hubGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const linkStyle = {
  color: "#1f5eff",
  fontWeight: 600,
  textDecoration: "none",
} as const;

function summarizeNewsPayload(event: {
  payload_text: string | null;
  payload_json: string | null;
  error_code: number;
  error_msg: string;
}) {
  if (event.payload_text?.trim()) {
    return event.payload_text;
  }
  if (event.payload_json?.trim()) {
    return event.payload_json;
  }
  if (event.error_code !== 0) {
    return event.error_msg || "Vendor callback returned an empty error envelope.";
  }
  return "Empty callback envelope.";
}

function buildPnlRefreshStatusText(payload: {
  status: string;
  report_date?: string;
  source_version?: string;
}) {
  return [
    `最近结果：${payload.status}`,
    payload.report_date ? `报告日 ${payload.report_date}` : null,
    payload.source_version ? `source ${payload.source_version}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default function OperationsAnalysisPage() {
  const client = useApiClient();
  const [isPnlRefreshing, setIsPnlRefreshing] = useState(false);
  const [pnlRefreshError, setPnlRefreshError] = useState<string | null>(null);
  const [lastPnlRefreshRunId, setLastPnlRefreshRunId] = useState<string | null>(null);
  const [lastPnlRefreshStatus, setLastPnlRefreshStatus] = useState<string | null>(null);
  const sourceQuery = useQuery({
    queryKey: ["operations-entry", "source-preview", client.mode],
    queryFn: () => client.getSourceFoundation(),
    retry: false,
  });
  const macroCatalogQuery = useQuery({
    queryKey: ["operations-entry", "macro-foundation", client.mode],
    queryFn: () => client.getMacroFoundation(),
    retry: false,
  });
  const macroLatestQuery = useQuery({
    queryKey: ["operations-entry", "macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const newsQuery = useQuery({
    queryKey: ["operations-entry", "choice-news", client.mode],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: 3,
        offset: 0,
      }),
    retry: false,
  });

  const sourceSummaries = useMemo(
    () => sourceQuery.data?.result.sources ?? [],
    [sourceQuery.data?.result.sources],
  );
  const macroCatalog = useMemo(
    () => macroCatalogQuery.data?.result.series ?? [],
    [macroCatalogQuery.data?.result.series],
  );
  const macroLatest = useMemo(
    () => macroLatestQuery.data?.result.series ?? [],
    [macroLatestQuery.data?.result.series],
  );
  const newsEvents = useMemo(
    () => newsQuery.data?.result.events ?? [],
    [newsQuery.data?.result.events],
  );
  const newsTotal = newsQuery.data?.result.total_rows ?? 0;
  const latestTradeDate = useMemo(() => {
    if (macroLatest.length === 0) {
      return "暂无";
    }
    return macroLatest
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [macroLatest]);

  async function handlePnlRefresh() {
    setIsPnlRefreshing(true);
    setPnlRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshFormalPnl(),
        getStatus: (runId) => client.getFormalPnlImportStatus(runId),
        onUpdate: (nextPayload) => {
          setLastPnlRefreshRunId(nextPayload.run_id);
          setLastPnlRefreshStatus(buildPnlRefreshStatusText(nextPayload));
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `PnL 刷新未完成：${payload.status}`);
      }
    } catch (error) {
      setPnlRefreshError(error instanceof Error ? error.message : "刷新 PnL 表失败");
    } finally {
      setIsPnlRefreshing(false);
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
              margin: 0,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            经营分析入口
          </h1>
          <p
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 860,
              color: "#5c6b82",
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            将 source preview、macro、news 三个只读分析面收口到同一入口。页面只消费现有后端只读契约，不在前端补算任何正式金融指标。
          </p>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background: client.mode === "real" ? "#e8f6ee" : "#edf3ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        </span>
      </div>

      <div style={summaryGridStyle}>
        <div data-testid="operations-entry-source-count">
          <PlaceholderCard
            title="数据源批次"
            value={String(sourceSummaries.length)}
            detail="来自 source preview 总览的 source_family 摘要数量。"
          />
        </div>
        <div data-testid="operations-entry-macro-count">
          <PlaceholderCard
            title="宏观最新点位"
            value={String(macroLatest.length)}
            detail={`宏观目录 ${macroCatalog.length} 条，最新交易日 ${latestTradeDate}`}
          />
        </div>
        <div data-testid="operations-entry-news-count">
          <PlaceholderCard
            title="新闻事件"
            value={String(newsTotal)}
            detail="来自 Choice news 事件流的当前查询总行数。"
          />
        </div>
      </div>

      <div style={hubGridStyle}>
        <AsyncSection
          title="数据源预览"
          isLoading={sourceQuery.isLoading}
          isError={sourceQuery.isError}
          isEmpty={!sourceQuery.isLoading && !sourceQuery.isError && sourceSummaries.length === 0}
          onRetry={() => void sourceQuery.refetch()}
          extra={
            <Link to="/source-preview" style={linkStyle} aria-label="进入数据源预览">
              进入数据源预览
            </Link>
          }
        >
          <div style={{ display: "grid", gap: 12 }}>
            {sourceSummaries.map((summary) => (
              <div
                key={`${summary.source_family}:${summary.ingest_batch_id ?? summary.report_date ?? summary.source_version}`}
                style={{
                  display: "grid",
                  gap: 6,
                  padding: 14,
                  borderRadius: 16,
                  border: "1px solid #e4ebf5",
                  background: "#ffffff",
                }}
              >
                <strong>{summary.source_family.toUpperCase()}</strong>
                <div style={{ color: "#5c6b82", fontSize: 13 }}>
                  报告日期 {summary.report_date ?? "—"} · 行数 {summary.total_rows} · 人工复核{" "}
                  {summary.manual_review_count}
                </div>
                <div style={{ color: "#8090a8", fontSize: 12 }}>
                  ingest_batch_id {summary.ingest_batch_id ?? "latest"}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>

        <AsyncSection
          title="宏观观察"
          isLoading={macroLatestQuery.isLoading || macroCatalogQuery.isLoading}
          isError={macroLatestQuery.isError || macroCatalogQuery.isError}
          isEmpty={
            !macroLatestQuery.isLoading &&
            !macroCatalogQuery.isLoading &&
            !macroLatestQuery.isError &&
            !macroCatalogQuery.isError &&
            macroLatest.length === 0
          }
          onRetry={() => {
            void macroCatalogQuery.refetch();
            void macroLatestQuery.refetch();
          }}
          extra={
            <Link to="/market-data" style={linkStyle} aria-label="进入市场数据页">
              进入市场数据页
            </Link>
          }
        >
          <div style={{ display: "grid", gap: 12 }}>
            {macroLatest.map((point) => (
              <div
                key={point.series_id}
                style={{
                  display: "grid",
                  gap: 6,
                  padding: 14,
                  borderRadius: 16,
                  border: "1px solid #e4ebf5",
                  background: "#ffffff",
                }}
              >
                <strong>{point.series_name}</strong>
                <div style={{ color: "#5c6b82", fontSize: 13 }}>
                  {point.trade_date} · {point.value_numeric.toFixed(2)} {point.unit}
                </div>
                <div style={{ color: "#8090a8", fontSize: 12 }}>
                  source_version {point.source_version}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>

        <AsyncSection
          title="新闻事件窗"
          isLoading={newsQuery.isLoading}
          isError={newsQuery.isError}
          isEmpty={!newsQuery.isLoading && !newsQuery.isError && newsEvents.length === 0}
          onRetry={() => void newsQuery.refetch()}
          extra={
            <Link to="/news-events" style={linkStyle} aria-label="进入新闻事件窗">
              进入新闻事件窗
            </Link>
          }
        >
          <div style={{ display: "grid", gap: 12 }}>
            {newsEvents.map((event) => (
              <div
                key={event.event_key}
                style={{
                  display: "grid",
                  gap: 6,
                  padding: 14,
                  borderRadius: 16,
                  border: "1px solid #e4ebf5",
                  background: "#ffffff",
                }}
              >
                <strong>{event.topic_code}</strong>
                <div style={{ color: "#5c6b82", fontSize: 13 }}>
                  {event.group_id} · {event.received_at}
                </div>
                <div style={{ color: "#162033", fontSize: 14, lineHeight: 1.6 }}>
                  {summarizeNewsPayload(event)}
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>

        <section
          style={{
            padding: 24,
            borderRadius: 20,
            background: "#fbfcfe",
            border: "1px solid #e4ebf5",
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
            display: "grid",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>正式损益刷新</h2>
              <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
            手动触发正式损益物化任务。该入口只负责发起刷新与显示任务状态，不在当前页面渲染正式损益结果表。
              </p>
              {lastPnlRefreshRunId ? (
                <p
                  data-testid="operations-entry-pnl-refresh-run-id"
                  style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}
                >
                  最近刷新任务：{lastPnlRefreshRunId}
                </p>
              ) : null}
              {lastPnlRefreshStatus ? (
                <p
                  data-testid="operations-entry-pnl-refresh-status"
                  style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}
                >
                  {lastPnlRefreshStatus}
                </p>
              ) : null}
              {pnlRefreshError ? (
                <p style={{ marginTop: 8, marginBottom: 0, color: "#b42318", fontSize: 12 }}>
                  {pnlRefreshError}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              data-testid="operations-entry-pnl-refresh-button"
              onClick={() => void handlePnlRefresh()}
              disabled={isPnlRefreshing}
              style={{
                padding: "10px 16px",
                borderRadius: 12,
                border: "1px solid #162033",
                background: "#fbfcfe",
                color: "#162033",
                fontWeight: 600,
                cursor: isPnlRefreshing ? "progress" : "pointer",
                opacity: isPnlRefreshing ? 0.7 : 1,
              }}
            >
            {isPnlRefreshing ? "刷新中..." : "刷新正式损益表"}
            </button>
          </div>
        </section>
      </div>
    </section>
  );
}
