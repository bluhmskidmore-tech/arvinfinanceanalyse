import { Collapse } from "antd";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { AlertList } from "../../../components/AlertList";
import { CalendarList } from "../../../components/CalendarList";
import { FilterBar } from "../../../components/FilterBar";
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

const controlStyle = {
  minWidth: 172,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
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

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 28,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 860,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
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

function buildStatusCardContent(input: {
  isError: boolean;
  value: string;
  detail: string;
}) {
  if (input.isError) {
    return {
      value: "不可用",
      detail: "当前查询失败，请在下方面板重试。",
    };
  }
  return input;
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
    return event.error_msg || "供应商回调返回了空错误信息。";
  }
  return "回调内容为空。";
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
    payload.cache_key ? `缓存 ${payload.cache_key}` : null,
    payload.report_date ? `报告日 ${payload.report_date}` : null,
    payload.source_version ? `源版本 ${payload.source_version}` : null,
  ]
    .filter(Boolean)
    .join(" / ");
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
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
  const sourceStatusCard = buildStatusCardContent({
    isError: sourceQuery.isError,
    value: String(sourceSummaries.length),
    detail: "来自数据源预览总览的来源摘要数量。",
  });
  const macroStatusCard = buildStatusCardContent({
    isError: macroCatalogQuery.isError || macroLatestQuery.isError,
    value: String(macroLatest.length),
    detail: `宏观目录 ${macroCatalog.length} 条，最新交易日 ${latestTradeDate}`,
  });
  const newsStatusCard = buildStatusCardContent({
    isError: newsQuery.isError,
    value: String(newsTotal),
    detail: "来自 Choice 新闻事件流的当前查询总行数。",
  });
  const formalFxStatusCard = buildStatusCardContent({
    isError: fxFormalStatusQuery.isError,
    value: `${fxFormalStatus?.materialized_count ?? 0} / ${fxFormalStatus?.candidate_count ?? 0}`,
    detail: `最新交易日 ${fxFormalStatus?.latest_trade_date ?? "待定"} / 沿用前值数量 ${fxFormalStatus?.carry_forward_count ?? 0}`,
  });

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
            当前页上半区聚焦经营结论、收益成本桥和质量观察；下半区保留数据源预览、宏观观察、新闻事件、正式 FX 状态和
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

      <FilterBar style={{ marginBottom: 20 }}>
        <label>
          <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
            范围
          </span>
          <select style={controlStyle} disabled>
            <option>金融市场条线</option>
          </select>
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
            口径
          </span>
          <select style={controlStyle} disabled>
            <option>静态经营</option>
          </select>
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
            币种
          </span>
          <select style={controlStyle} disabled>
            <option>全部</option>
          </select>
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
            周期
          </span>
          <select style={controlStyle} disabled>
            <option>单日截面</option>
          </select>
        </label>
      </FilterBar>

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

      <SectionLead
        eyebrow="核心视图"
        title="结论、桥接与质量观察"
        description="先看管理层结论，再看收益成本桥和质量观察，确认当前经营判断、利差来源和压力点是否一致。"
      />
      <div style={tripleGridStyle}>
        <BusinessConclusion />
        <RevenueCostBridge />
        <QualityObservation />
      </div>

      <SectionLead
        eyebrow="经营贡献"
        title="经营贡献与重点事项"
        description="这一组把余额贡献、重点事项和经营日历放在同一层，方便从结论直接过渡到行动与跟踪。"
      />
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

      <SectionLead
        eyebrow="结构解读"
        title="期限结构与管理输出"
        description="将期限缺口、集中度和管理输出并排，形成经营判断之后的结构解释层。"
      />
      <div style={pairGridStyle}>
        <TenorConcentrationPanel />
        <ManagementOutput />
      </div>

      <SectionLead
        eyebrow="专题入口"
        title="专题入口"
        description="经营分析页只保留专题速览和跳转，正式工作簿与细项下钻仍在对应主题页中查看。"
      />
      <div
        data-testid="operations-entry-balance-section"
        style={{
          marginTop: 12,
          marginBottom: 4,
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
                专题入口：资产负债正式读面
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
                currency_basis={balanceOverviewQuery.data.result.currency_basis}。这里仅保留正式工作簿速览，
                作为经营分析后的专题入口，不在本页展开完整工作簿。
              </p>
              <div style={balanceOverviewGridStyle}>
                <div data-testid="operations-entry-balance-detail-rows">
                  <KpiCard
                    title="明细行数"
                    value={String(balanceOverviewQuery.data.result.detail_row_count)}
                    detail="正式读面明细行数"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-summary-rows">
                  <KpiCard
                    title="汇总行数"
                    value={String(balanceOverviewQuery.data.result.summary_row_count)}
                    detail="正式读面汇总行数"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-market-value">
                  <KpiCard
                    title="总市值合计"
                    value={formatOverviewNumber(balanceOverviewQuery.data.result.total_market_value_amount)}
                    detail="正式读面总市值"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-amortized">
                  <KpiCard
                    title="摊余成本合计"
                    value={formatOverviewNumber(
                      balanceOverviewQuery.data.result.total_amortized_cost_amount,
                    )}
                    detail="正式读面摊余成本"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-accrued">
                  <KpiCard
                    title="应计利息合计"
                    value={formatOverviewNumber(
                      balanceOverviewQuery.data.result.total_accrued_interest_amount,
                    )}
                    detail="正式读面应计利息"
                    valueVariant="text"
                  />
                </div>
              </div>
            </div>
          ) : null}
        </AsyncSection>
      </div>

      <Collapse
        style={{ marginTop: 28 }}
        bordered={false}
        defaultActiveKey={["ops-sources"]}
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
                      value={sourceStatusCard.value}
                      detail={sourceStatusCard.detail}
                      valueVariant="text"
                      status={sourceQuery.isError ? "warning" : "normal"}
                    />
                  </div>
                  <div data-testid="operations-entry-macro-count">
                    <KpiCard
                      title="宏观最新点位"
                      value={macroStatusCard.value}
                      detail={macroStatusCard.detail}
                      valueVariant="text"
                      status={macroCatalogQuery.isError || macroLatestQuery.isError ? "warning" : "normal"}
                    />
                  </div>
                  <div data-testid="operations-entry-news-count">
                    <KpiCard
                      title="新闻事件"
                      value={newsStatusCard.value}
                      detail={newsStatusCard.detail}
                      valueVariant="text"
                      status={newsQuery.isError ? "warning" : "normal"}
                    />
                  </div>
                  <div data-testid="operations-entry-formal-fx-count">
                    <KpiCard
                      title="正式 FX 状态"
                      value={formalFxStatusCard.value}
                      detail={formalFxStatusCard.detail}
                      valueVariant="text"
                      status={fxFormalStatusQuery.isError ? "warning" : "normal"}
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
                            报告日 {summary.report_date ?? "—"} / 行数 {summary.total_rows} / 人工复核{" "}
                            {summary.manual_review_count}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }}>
                            导入批次 {summary.ingest_batch_id ?? "latest"}
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
                            {point.trade_date} / {point.value_numeric.toFixed(2)} {point.unit}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }}>
                            源版本 {point.source_version}
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
                            分组 {event.group_id} / {event.received_at}
                          </div>
                          <div style={{ color: "#162033", fontSize: 14, lineHeight: 1.6 }}>
                            {summarizeNewsPayload(event)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </AsyncSection>

                  <AsyncSection
                    title="正式 FX 中间价状态"
                    isLoading={fxFormalStatusQuery.isLoading}
                    isError={fxFormalStatusQuery.isError}
                    isEmpty={
                      !fxFormalStatusQuery.isLoading && !fxFormalStatusQuery.isError && fxFormalRows.length === 0
                    }
                    onRetry={() => void fxFormalStatusQuery.refetch()}
                  >
                    <div data-testid="operations-entry-formal-fx-status" style={cardStyle}>
                      <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
                        正式 FX 中间价状态直接来自后端正式读模型，并与分析口径的市场观察分开展示。
                      </div>
                      <div style={{ display: "grid", gap: 8, color: "#5c6b82", fontSize: 14 }}>
                        <div>最新交易日 {fxFormalStatus?.latest_trade_date ?? "待定"}</div>
                        <div>沿用前值数量 {fxFormalStatus?.carry_forward_count ?? 0}</div>
                        <div>
                          供应商优先级 {(fxFormalStatus?.vendor_priority ?? []).join(" > ") || "待定"}
                        </div>
                        <div>trace_id {fxFormalStatusQuery.data?.result_meta.trace_id ?? "待定"}</div>
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
                              状态 {row.status} / 交易日 {row.trade_date ?? "待定"} / 观测日{" "}
                              {row.observed_trade_date ?? "待定"}
                            </div>
                            <div style={{ color: "#8090a8", fontSize: 12 }}>
                              {row.status === "missing"
                                ? `缺失 ${row.pair_label}`
                                : `中间价 ${row.mid_rate ?? "n/a"} / 供应商 ${row.vendor_name ?? "n/a"} / 沿用前值 ${row.is_carry_forward ?? false}`}
                            </div>
                          </div>
                        ))}
                      </div>
                      {missingFxRows.length > 0 ? (
                        <div style={{ color: "#b42318", fontSize: 13 }}>
                          缺失的正式 FX 货币对：{missingFxRows.map((row) => row.pair_label).join(", ")}
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
                          手动触发正式损益（PnL）物化任务，与正式 FX 状态读面相互独立。该入口只负责发起刷新与展示任务状态，
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
