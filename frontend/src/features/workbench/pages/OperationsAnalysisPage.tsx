import { Collapse } from "antd";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { AlertList } from "../../../components/AlertList";
import { CalendarList } from "../../../components/CalendarList";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { BusinessConclusion } from "../business-analysis/BusinessConclusion";
import { BusinessContributionTable } from "../business-analysis/BusinessContributionTable";
import {
  OPERATIONS_CALENDAR_MOCK,
  OPERATIONS_WATCH_ITEMS,
} from "../business-analysis/businessAnalysisWorkbenchMocks";
import { ManagementOutput } from "../business-analysis/ManagementOutput";
import { QualityObservation } from "../business-analysis/QualityObservation";
import { RevenueCostBridge } from "../business-analysis/RevenueCostBridge";
import { TenorConcentrationPanel } from "../business-analysis/TenorConcentrationPanel";
import { KpiCard } from "../components/KpiCard";

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

const tripleGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const pairGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const cardStyle = {
  padding: 24,
  borderRadius: 20,
  background: "#fbfcfe",
  border: "1px solid #e4ebf5",
  boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
  display: "grid",
  gap: 12,
} as const;

const linkStyle = {
  color: "#1f5eff",
  fontWeight: 600,
  textDecoration: "none",
} as const;

const balanceOverviewGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 16,
  marginTop: 16,
} as const;

function formatOverviewNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(n)) {
    return String(raw);
  }
  return n.toLocaleString("zh-CN");
}

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
  job_name?: string;
  trigger_mode?: string;
  cache_key?: string;
  report_date?: string;
  source_version?: string;
}) {
  return [
    `最近结果：${payload.status}`,
    payload.job_name ? `任务 ${payload.job_name}` : null,
    payload.trigger_mode ? `触发 ${payload.trigger_mode}` : null,
    payload.cache_key ? `cache ${payload.cache_key}` : null,
    payload.report_date ? `报告日 ${payload.report_date}` : null,
    payload.source_version ? `source ${payload.source_version}` : null,
  ]
    .filter(Boolean)
    .join(" 路 ");
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
  const fxFormalStatusQuery = useQuery({
    queryKey: ["operations-entry", "fx-formal-status", client.mode],
    queryFn: () => client.getFxFormalStatus(),
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
  const balanceDatesQuery = useQuery({
    queryKey: ["operations-entry", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });
  const balanceReportDates = balanceDatesQuery.data?.result.report_dates ?? [];
  const latestBalanceReportDate = balanceReportDates[0] ?? null;
  const balanceOverviewQuery = useQuery({
    queryKey: [
      "operations-entry",
      "balance-analysis-overview",
      client.mode,
      latestBalanceReportDate,
    ],
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: latestBalanceReportDate as string,
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    enabled: Boolean(latestBalanceReportDate),
    retry: false,
  });
  const balanceSummaryQuery = useQuery({
    queryKey: [
      "operations-entry",
      "balance-analysis-summary",
      client.mode,
      latestBalanceReportDate,
    ],
    queryFn: () =>
      client.getBalanceAnalysisSummary({
        reportDate: latestBalanceReportDate as string,
        positionScope: "all",
        currencyBasis: "CNY",
        limit: 48,
        offset: 0,
      }),
    enabled: Boolean(latestBalanceReportDate),
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
  const fxFormalStatus = fxFormalStatusQuery.data?.result;
  const fxFormalRows = useMemo(() => fxFormalStatus?.rows ?? [], [fxFormalStatus?.rows]);
  const missingFxRows = useMemo(
    () => fxFormalRows.filter((row) => row.status === "missing"),
    [fxFormalRows],
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

  const balanceSummaryRows = useMemo(
    () => balanceSummaryQuery.data?.result.rows ?? [],
    [balanceSummaryQuery.data?.result.rows],
  );

  async function handlePnlRefresh() {
    setIsPnlRefreshing(true);
    setPnlRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshFormalPnl(),
        getStatus: (runId) => client.getFormalPnlImportStatus(runId),
        onUpdate: (nextPayload) => {
          setLastPnlRefreshRunId(nextPayload.run_id ?? null);
          setLastPnlRefreshStatus(buildPnlRefreshStatusText(nextPayload));
        },
      });
      if (payload.status !== "completed") {
        const hint =
          payload.error_message ?? payload.detail ?? `PnL 刷新未完成：${payload.status}`;
        const rid = payload.run_id ? ` run_id: ${payload.run_id}` : "";
        throw new Error(`${hint}${rid}`);
      }
    } catch (error) {
      setPnlRefreshError(error instanceof Error ? error.message : "刷新 PnL 失败");
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
            经营分析
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
            上方为经营管理读面（示意 KPI、结论与贡献摘要）；下方折叠区保留数据源预览、宏观与新闻观测、formal FX 状态及
            PnL 刷新入口。所有正式数值均以后端契约为准。
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

      <div data-testid="operations-business-kpis" style={summaryGridStyle}>
        <KpiCard
          label="市场资产"
          value="3,525.0"
          unit="亿"
          detail="债券+买入"
          valueVariant="metric"
        />
        <KpiCard
          label="市场负债"
          value="1,817.9"
          unit="亿"
          detail="发行+买入"
          valueVariant="metric"
        />
        <KpiCard label="静态资产收益率" value="2.07%" detail="加权到期" valueVariant="metric" />
        <KpiCard label="静态负债成本" value="1.77%" detail="当期加权" valueVariant="metric" />
        <KpiCard
          label="静态利差"
          value="29.5"
          unit="bp"
          detail="资产收益-负债成本"
          valueVariant="metric"
        />
        <KpiCard
          label="净经营贡献"
          value="40.65"
          unit="亿"
          detail="静态年化口径"
          valueVariant="metric"
        />
        <KpiCard
          label="发行负债占比"
          value="66.3%"
          detail="CD占发行 81.8%"
          valueVariant="metric"
        />
        <KpiCard
          label="重大关注"
          value="4"
          unit="项"
          detail="缺口/滚续/集中度"
          valueVariant="metric"
          status="warning"
        />
      </div>

      <div
        data-testid="operations-entry-balance-section"
        style={{
          marginTop: 28,
          marginBottom: 28,
          paddingLeft: 20,
          borderLeft: "4px solid #1f5eff",
        }}
      >
        <AsyncSection
          title=""
          isLoading={balanceDatesQuery.isLoading || balanceOverviewQuery.isLoading}
          isError={balanceDatesQuery.isError || balanceOverviewQuery.isError}
          isEmpty={
            !balanceDatesQuery.isLoading &&
            !balanceOverviewQuery.isLoading &&
            !balanceDatesQuery.isError &&
            !balanceOverviewQuery.isError &&
            balanceReportDates.length === 0
          }
          onRetry={() => {
            void balanceDatesQuery.refetch();
            void balanceOverviewQuery.refetch();
          }}
          extra={
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                width: "100%",
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: 18,
                  fontWeight: 600,
                  lineHeight: 1.35,
                  color: "#162033",
                }}
              >
                资产负债分析（正式读面速览）
              </h2>
              <Link to="/balance-analysis" style={linkStyle} aria-label="进入资产负债分析">
                进入资产负债分析
              </Link>
            </div>
          }
        >
          {balanceOverviewQuery.data?.result ? (
            <div>
              <p
                style={{
                  margin: 0,
                  color: "#5c6b82",
                  fontSize: 14,
                  lineHeight: 1.7,
                }}
              >
                报告日{" "}
                <span data-testid="operations-entry-balance-report-date">
                  {balanceOverviewQuery.data.result.report_date}
                </span>
                ，口径 position_scope={balanceOverviewQuery.data.result.position_scope}，
                currency_basis={balanceOverviewQuery.data.result.currency_basis}。下列数值由{" "}
                <code style={{ fontSize: 13 }}>/ui/balance-analysis/overview</code>{" "}
                直接返回，单位与正式工作簿一致（亿元字段以后端约定为准）。
              </p>
              <div style={balanceOverviewGridStyle}>
                <div data-testid="operations-entry-balance-detail-rows">
                  <KpiCard
                    title="明细行数"
                    value={String(balanceOverviewQuery.data.result.detail_row_count)}
                    detail="overview.detail_row_count"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-summary-rows">
                  <KpiCard
                    title="汇总行数"
                    value={String(balanceOverviewQuery.data.result.summary_row_count)}
                    detail="overview.summary_row_count"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-market-value">
                  <KpiCard
                    title="总市值合计"
                    value={formatOverviewNumber(balanceOverviewQuery.data.result.total_market_value_amount)}
                    detail="overview.total_market_value_amount"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-amortized">
                  <KpiCard
                    title="摊余成本合计"
                    value={formatOverviewNumber(
                      balanceOverviewQuery.data.result.total_amortized_cost_amount,
                    )}
                    detail="overview.total_amortized_cost_amount"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-accrued">
                  <KpiCard
                    title="应计利息合计"
                    value={formatOverviewNumber(
                      balanceOverviewQuery.data.result.total_accrued_interest_amount,
                    )}
                    detail="overview.total_accrued_interest_amount"
                    valueVariant="text"
                  />
                </div>
              </div>
            </div>
          ) : null}
        </AsyncSection>
      </div>

      <div style={tripleGridStyle}>
        <BusinessConclusion />
        <RevenueCostBridge />
        <QualityObservation />
      </div>

      <div style={tripleGridStyle}>
        <BusinessContributionTable
          reportDate={latestBalanceReportDate}
          rows={balanceSummaryRows}
          loading={balanceSummaryQuery.isLoading}
          error={balanceSummaryQuery.isError}
          onRetry={() => void balanceSummaryQuery.refetch()}
        />
        <SectionCard title="关注事项">
          <AlertList items={OPERATIONS_WATCH_ITEMS} />
        </SectionCard>
        <SectionCard title="经营日历">
          <CalendarList items={OPERATIONS_CALENDAR_MOCK} />
        </SectionCard>
      </div>

      <div style={pairGridStyle}>
        <TenorConcentrationPanel />
        <ManagementOutput />
      </div>

      <Collapse
        style={{ marginTop: 28 }}
        bordered={false}
        defaultActiveKey={[]}
        items={[
          {
            key: "ops-sources",
            label: "数据源与运维状态",
            children: (
              <div>
                <div style={summaryGridStyle}>
                  <div data-testid="operations-entry-source-count">
                    <KpiCard
                      title="数据源批次"
                      value={String(sourceSummaries.length)}
                      detail="来自 source preview 总览的 source_family 摘要数量。"
                      valueVariant="text"
                    />
                  </div>
                  <div data-testid="operations-entry-macro-count">
                    <KpiCard
                      title="宏观最新点位"
                      value={String(macroLatest.length)}
                      detail={`宏观目录 ${macroCatalog.length} 条，最新交易日 ${latestTradeDate}`}
                      valueVariant="text"
                    />
                  </div>
                  <div data-testid="operations-entry-news-count">
                    <KpiCard
                      title="新闻事件"
                      value={String(newsTotal)}
                      detail="来自 Choice news 事件流的当前查询总行数。"
                      valueVariant="text"
                    />
                  </div>
                  <div data-testid="operations-entry-formal-fx-count">
                    <KpiCard
                      title="Formal FX status"
                      value={`${fxFormalStatus?.materialized_count ?? 0} / ${fxFormalStatus?.candidate_count ?? 0}`}
                      detail={`latest_trade_date ${fxFormalStatus?.latest_trade_date ?? "pending"} 路 carry_forward_count ${fxFormalStatus?.carry_forward_count ?? 0}`}
                      valueVariant="text"
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
                            报告日期 {summary.report_date ?? "—"} 路 行数 {summary.total_rows} 路 人工复核{" "}
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
                            {point.trade_date} 路 {point.value_numeric.toFixed(2)} {point.unit}
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
                            {event.group_id} 路 {event.received_at}
                          </div>
                          <div style={{ color: "#162033", fontSize: 14, lineHeight: 1.6 }}>
                            {summarizeNewsPayload(event)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </AsyncSection>

                  <AsyncSection
                    title="Formal FX middle-rate status"
                    isLoading={fxFormalStatusQuery.isLoading}
                    isError={fxFormalStatusQuery.isError}
                    isEmpty={
                      !fxFormalStatusQuery.isLoading && !fxFormalStatusQuery.isError && fxFormalRows.length === 0
                    }
                    onRetry={() => void fxFormalStatusQuery.refetch()}
                  >
                    <div data-testid="operations-entry-formal-fx-status" style={cardStyle}>
                      <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
                        Formal FX middle-rate status comes directly from the backend formal read model and is
                        displayed separately from analytical market observations.
                      </div>
                      <div style={{ display: "grid", gap: 8, color: "#5c6b82", fontSize: 14 }}>
                        <div>latest_trade_date {fxFormalStatus?.latest_trade_date ?? "pending"}</div>
                        <div>carry_forward_count {fxFormalStatus?.carry_forward_count ?? 0}</div>
                        <div>vendor_priority {(fxFormalStatus?.vendor_priority ?? []).join(" > ") || "pending"}</div>
                        <div>trace_id {fxFormalStatusQuery.data?.result_meta.trace_id ?? "pending"}</div>
                      </div>
                      <div style={{ display: "grid", gap: 10 }}>
                        {fxFormalRows.map((row) => (
                          <div
                            key={`${row.base_currency}:${row.quote_currency}`}
                            style={{
                              display: "grid",
                              gap: 6,
                              padding: 14,
                              borderRadius: 16,
                              border: "1px solid #e4ebf5",
                              background: "#ffffff",
                            }}
                          >
                            <strong>{row.pair_label}</strong>
                            <div style={{ color: "#5c6b82", fontSize: 13 }}>
                              status {row.status} 路 trade_date {row.trade_date ?? "pending"} 路 observed{" "}
                              {row.observed_trade_date ?? "pending"}
                            </div>
                            <div style={{ color: "#8090a8", fontSize: 12 }}>
                              {row.status === "missing"
                                ? `missing ${row.pair_label}`
                                : `mid_rate ${row.mid_rate ?? "n/a"} 路 vendor ${row.vendor_name ?? "n/a"} 路 carry_forward ${row.is_carry_forward ?? false}`}
                            </div>
                          </div>
                        ))}
                      </div>
                      {missingFxRows.length > 0 ? (
                        <div style={{ color: "#b42318", fontSize: 13 }}>
                          Missing formal FX pairs: {missingFxRows.map((row) => row.pair_label).join(", ")}
                        </div>
                      ) : null}
                    </div>
                  </AsyncSection>

                  <section style={cardStyle}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        justifyContent: "space-between",
                        gap: 12,
                      }}
                    >
                      <div>
                        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>PnL 表刷新</h2>
                        <p
                          style={{
                            marginTop: 8,
                            marginBottom: 0,
                            color: "#5c6b82",
                            fontSize: 13,
                            lineHeight: 1.7,
                          }}
                        >
                          手动触发正式损益（PnL）物化任务，与 formal FX 状态读面相互独立。该入口只负责发起刷新与展示任务状态，
                          不在当前页面演绎正式损益大表。
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
                        {isPnlRefreshing ? "刷新中..." : "刷新 PnL 表"}
                      </button>
                    </div>
                  </section>
                </div>
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}
