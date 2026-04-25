import { Collapse } from "antd";
import { useMemo, useState, type ReactNode } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import type { ApiEnvelope, BalanceAnalysisOverviewPayload } from "../../../api/contracts";
import { AlertList } from "../../../components/AlertList";
import { CalendarList } from "../../../components/CalendarList";
import { FilterBar } from "../../../components/FilterBar";
import {
  PageFilterTray,
  pageInsetCardStyle,
  PageHeader,
  PageSurfacePanel,
} from "../../../components/page/PagePrimitives";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { shellTokens } from "../../../theme/tokens";
import { BusinessConclusion } from "../business-analysis/BusinessConclusion";
import { BusinessContributionTable } from "../business-analysis/BusinessContributionTable";
import { ManagementOutput } from "../business-analysis/ManagementOutput";
import { QualityObservation } from "../business-analysis/QualityObservation";
import { RevenueCostBridge } from "../business-analysis/RevenueCostBridge";
import { TenorConcentrationPanel } from "../business-analysis/TenorConcentrationPanel";
import {
  OPERATIONS_CALENDAR_MOCK,
  OPERATIONS_WATCH_ITEMS,
} from "../business-analysis/businessAnalysisWorkbenchMocks";
import { KpiCard } from "../components/KpiCard";
import { formatYuanAmountAsYiPlain } from "../../../utils/format";

const DISPLAY_FONT =
  '"Alibaba PuHuiTi 3.0", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei UI", sans-serif';

const pageShellStyle = {
  display: "grid",
  gap: 24,
} as const;

const heroShellStyle = {
  display: "grid",
  gap: 18,
  padding: "26px 26px 22px",
  borderRadius: 28,
  background:
    "linear-gradient(180deg, rgba(252,251,248,0.98) 0%, rgba(247,247,242,0.94) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 22px 52px rgba(22, 35, 46, 0.07)",
} as const;

const heroHeaderStyle = {
  marginBottom: 0,
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const hubGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: 18,
  marginTop: 20,
} as const;

const controlStyle = {
  minWidth: 172,
  padding: "12px 14px",
  borderRadius: 14,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "rgba(255, 255, 255, 0.88)",
  color: shellTokens.colorTextPrimary,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.75)",
} as const;

const linkStyle = {
  color: shellTokens.colorAccent,
  fontWeight: 700,
  letterSpacing: "0.01em",
  textDecoration: "none",
} as const;

const filterTrayStyle = {
  background: "rgba(255,255,255,0.6)",
  borderColor: "rgba(214, 222, 220, 0.9)",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.7)",
} as const;

const filterLabelStyle = {
  display: "block",
  marginBottom: 6,
  color: shellTokens.colorTextMuted,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
} as const;

const balanceOverviewGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 16,
  marginTop: 16,
} as const;

const operationsHeroStripStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: 16,
  marginTop: 4,
} as const;

const headlineMetricShellStyle = {
  display: "grid",
  gap: 14,
  minHeight: 172,
  padding: "18px 18px 16px",
  borderRadius: 22,
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(250,249,245,0.96) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 16px 36px rgba(22, 35, 46, 0.05)",
} as const;

const compactMetricShellStyle = {
  ...headlineMetricShellStyle,
  minHeight: 138,
  gap: 10,
  padding: "16px 16px 14px",
  borderRadius: 18,
  boxShadow: "0 12px 28px rgba(22, 35, 46, 0.04)",
} as const;

const metricLabelRowStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 10,
} as const;

const metricLabelStyle = {
  margin: 0,
  color: shellTokens.colorTextMuted,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  lineHeight: 1.45,
  textTransform: "uppercase",
} as const;

const metricValueBlockStyle = {
  display: "grid",
  alignContent: "start",
  gap: 8,
  minHeight: 0,
} as const;

const metricUnitRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "baseline",
  gap: "4px 8px",
  minHeight: 0,
} as const;

const metricDetailStyle = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const tripleGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: 18,
  alignItems: "start",
  marginTop: 14,
} as const;

const contributionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: 18,
  alignItems: "start",
  marginTop: 14,
} as const;

const pairGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
  gap: 18,
  alignItems: "start",
  marginTop: 14,
} as const;

const sectionLeadShellStyle = {
  display: "grid",
  gap: 10,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: shellTokens.colorTextMuted,
} as const;

const sectionTitleStyle = {
  margin: 0,
  maxWidth: 820,
  color: shellTokens.colorTextPrimary,
  fontSize: 24,
  fontWeight: 800,
  letterSpacing: "-0.03em",
  lineHeight: 1.2,
  fontFamily: DISPLAY_FONT,
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 760,
  color: shellTokens.colorTextSecondary,
  fontSize: 14,
  lineHeight: 1.85,
} as const;

const sectionBlockStyle = {
  display: "grid",
  gap: 14,
} as const;

const focusEntryShellStyle = {
  marginTop: 8,
  marginBottom: 2,
  padding: "18px 22px 22px",
  borderRadius: 24,
  borderLeft: `4px solid ${shellTokens.colorAccent}`,
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.76) 0%, rgba(247,247,242,0.88) 100%)",
} as const;

const recommendationBodyStyle = {
  display: "grid",
  gap: 12,
} as const;

const recommendationTextStyle = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 14,
  lineHeight: 1.8,
  maxWidth: 760,
} as const;

const alignedPanelStyle = {
  display: "grid",
  gap: 16,
  height: "100%",
  padding: 22,
  borderRadius: 24,
  background:
    "linear-gradient(180deg, rgba(252,251,248,0.98) 0%, rgba(247,247,242,0.95) 100%)",
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "0 18px 44px rgba(22, 35, 46, 0.06)",
} as const;

const alignedPanelTitleStyle = {
  margin: 0,
  color: shellTokens.colorTextPrimary,
  fontSize: 18,
  fontWeight: 750,
  letterSpacing: "-0.02em",
  lineHeight: 1.3,
  fontFamily: DISPLAY_FONT,
} as const;

const alignedPanelContentStyle = {
  display: "grid",
  gap: 12,
  alignContent: "start",
  minHeight: 0,
} as const;

const disclosureLabelStyle = {
  color: shellTokens.colorTextPrimary,
  fontSize: 15,
  fontWeight: 700,
  letterSpacing: "-0.01em",
} as const;

const entryHeaderStyle = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: 12,
  width: "100%",
} as const;

const entryTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 750,
  lineHeight: 1.3,
  letterSpacing: "-0.02em",
  color: shellTokens.colorTextPrimary,
  fontFamily: DISPLAY_FONT,
} as const;

const entryIntroStyle = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 14,
  lineHeight: 1.8,
  maxWidth: 760,
} as const;

function OperationsSectionLead({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadShellStyle}>
      <span style={sectionEyebrowStyle}>{eyebrow}</span>
      <h2 style={sectionTitleStyle}>{title}</h2>
      <p style={sectionDescriptionStyle}>{description}</p>
    </div>
  );
}

function OperationsPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <PageSurfacePanel as="section" style={alignedPanelStyle}>
      <h3 style={alignedPanelTitleStyle}>{title}</h3>
      <div style={alignedPanelContentStyle}>{children}</div>
    </PageSurfacePanel>
  );
}

function OperationsMetricCard({
  label,
  value,
  detail,
  unit,
  compact = false,
  status = "normal",
}: {
  label: string;
  value: string;
  detail?: string;
  unit?: string;
  compact?: boolean;
  status?: "normal" | "warning" | "danger";
}) {
  const valueColor =
    status === "warning"
      ? shellTokens.colorWarning
      : status === "danger"
        ? shellTokens.colorDanger
        : shellTokens.colorTextPrimary;

  return (
    <div style={compact ? compactMetricShellStyle : headlineMetricShellStyle}>
      <div style={metricLabelRowStyle}>
        <p style={metricLabelStyle}>{label}</p>
      </div>
      <div style={metricValueBlockStyle}>
        <div style={metricUnitRowStyle}>
          <span
            style={{
              color: valueColor,
              fontSize: compact ? 22 : 30,
              fontWeight: 800,
              letterSpacing: "-0.03em",
              lineHeight: compact ? 1.15 : 1.08,
              fontFamily: DISPLAY_FONT,
            }}
          >
            {value}
          </span>
          {unit ? (
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: compact ? 12 : 13,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {unit}
            </span>
          ) : null}
        </div>
        {detail ? <p style={metricDetailStyle}>{detail}</p> : null}
      </div>
    </div>
  );
}

function formatOverviewNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return String(raw);
  }
  return parsed.toLocaleString("zh-CN");
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

function formatGroupCounts(groupCounts: Record<string, number> | undefined): string {
  if (!groupCounts || Object.keys(groupCounts).length === 0) {
    return "—";
  }
  return Object.entries(groupCounts)
    .map(([key, count]) => `${key} ${count}`)
    .join(" / ");
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
    return event.error_msg || "供应商回调返回空错误信息。";
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
  }) as Omit<UseQueryResult<ApiEnvelope<BalanceAnalysisOverviewPayload>, Error>, "data"> & {
    data: ApiEnvelope<BalanceAnalysisOverviewPayload>;
  };
  const balanceOverview = balanceOverviewQuery.data?.result;

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
        limit: 6,
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
  const balanceSummaryRows = useMemo(
    () => balanceSummaryQuery.data?.result.rows ?? [],
    [balanceSummaryQuery.data?.result.rows],
  );

  const latestTradeDate = useMemo(() => {
    if (macroLatest.length === 0) {
      return "暂无";
    }
    return macroLatest
      .map((point) => point.trade_date)
      .sort((left, right) => right.localeCompare(left))[0];
  }, [macroLatest]);

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

  const recommendation = useMemo(() => {
    const hasCriticalError =
      sourceQuery.isError ||
      macroCatalogQuery.isError ||
      macroLatestQuery.isError ||
      fxFormalStatusQuery.isError ||
      balanceDatesQuery.isError ||
      balanceOverviewQuery.isError;
    const hasCriticalEmpty =
      sourceSummaries.length === 0 ||
      macroLatest.length === 0 ||
      fxFormalRows.length === 0;

    if (hasCriticalError || hasCriticalEmpty) {
      return {
        title: "Evidence chain incomplete",
        detail:
          "One or more governed reads failed. Validate source preview, macro latest, formal FX status, and the balance overview before making today’s operating judgment.",
        actionLabel: "Review source preview",
        actionTo: "/source-preview",
      };
    }

    if (!latestBalanceReportDate || !balanceOverviewQuery.data?.result) {
      return {
        title: "Await governed balance evidence",
        detail:
          "Today’s operating judgment is not yet backed by a resolved balance-analysis report date. Start from the formal balance page when the report becomes available.",
        actionLabel: "Open balance analysis",
        actionTo: "/balance-analysis",
      };
    }

    if (missingFxRows.length > 0) {
      return {
        title: "Judgment is usable but degraded",
        detail: `Formal FX status is still missing ${missingFxRows.length} pair(s). Use the formal balance overview for the first decision, then verify market coverage before wider drilldown.`,
        actionLabel: "Open market data",
        actionTo: "/market-data",
      };
    }

    return {
      title: "Evidence is sufficient for today’s operating call",
      detail: `Current evidence resolves to balance report ${balanceOverviewQuery.data.result.report_date}. Start with the governed balance overview, then drill into source preview or market context only if the first conclusion needs explanation.`,
      actionLabel: "Open balance analysis",
      actionTo: "/balance-analysis",
    };
  }, [
    balanceDatesQuery.isError,
    balanceOverviewQuery.data?.result,
    balanceOverviewQuery.isError,
    fxFormalRows.length,
    fxFormalStatusQuery.isError,
    latestBalanceReportDate,
    macroCatalogQuery.isError,
    macroLatest.length,
    macroLatestQuery.isError,
    missingFxRows.length,
    sourceQuery.isError,
    sourceSummaries.length,
  ]);

  const operationsHeadlineCards = useMemo(
    () => [
      {
        title: "Market Value",
        value: formatYuanAmountAsYiPlain(balanceOverviewQuery.data?.result.total_market_value_amount),
        unit: "亿元",
        detail: "governed balance overview",
      },
      {
        title: "Amortized Cost",
        value: formatYuanAmountAsYiPlain(balanceOverviewQuery.data?.result.total_amortized_cost_amount),
        unit: "亿元",
        detail: "governed balance overview",
      },
      {
        title: "Accrued Interest",
        value: formatYuanAmountAsYiPlain(balanceOverviewQuery.data?.result.total_accrued_interest_amount),
        unit: "亿元",
        detail: "governed balance overview",
      },
      {
        title: "Source Batches",
        value: sourceStatusCard.value,
        detail: sourceStatusCard.detail,
      },
      {
        title: "Macro Latest",
        value: macroStatusCard.value,
        detail: macroStatusCard.detail,
      },
      {
        title: "Formal FX Coverage",
        value: formalFxStatusCard.value,
        detail: formalFxStatusCard.detail,
        status: fxFormalStatusQuery.isError ? "warning" as const : "normal" as const,
      },
      {
        title: "News Events",
        value: newsStatusCard.value,
        detail: newsStatusCard.detail,
      },
      {
        title: "Summary Rows",
        value: String(balanceOverviewQuery.data?.result.summary_row_count ?? 0),
        detail: `detail ${balanceOverviewQuery.data?.result.detail_row_count ?? 0} rows`,
      },
    ],
    [
      balanceOverviewQuery.data?.result?.detail_row_count,
      balanceOverviewQuery.data?.result?.summary_row_count,
      balanceOverviewQuery.data?.result?.total_accrued_interest_amount,
      balanceOverviewQuery.data?.result?.total_amortized_cost_amount,
      balanceOverviewQuery.data?.result?.total_market_value_amount,
      formalFxStatusCard.detail,
      formalFxStatusCard.value,
      fxFormalStatusQuery.isError,
      macroStatusCard.detail,
      macroStatusCard.value,
      newsStatusCard.detail,
      newsStatusCard.value,
      sourceStatusCard.detail,
      sourceStatusCard.value,
    ],
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
          payload.error_message ?? payload.detail ?? `PnL refresh not completed: ${payload.status}`;
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
    <section style={pageShellStyle}>
      <div style={heroShellStyle}>
      <PageHeader
        title="经营分析"
        eyebrow="Overview"
        description="本页先回答经营判断、贡献结构和管理动作，再把受治理专题入口与运维证据面板放到后面。首页不再把 staged 指标伪装成正式经营结论。"
        badgeLabel={client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        style={heroHeaderStyle}
      >
        <PageFilterTray style={filterTrayStyle}>
          <FilterBar>
            <label>
              <span style={filterLabelStyle}>
                范围
              </span>
              <select style={controlStyle} disabled>
                <option>金融市场条线</option>
              </select>
            </label>
            <label>
              <span style={filterLabelStyle}>
                口径
              </span>
              <select style={controlStyle} disabled>
                <option>静态经营</option>
              </select>
            </label>
            <label>
              <span style={filterLabelStyle}>
                币种
              </span>
              <select style={controlStyle} disabled>
                <option>全部</option>
              </select>
            </label>
            <label>
              <span style={filterLabelStyle}>
                周期
              </span>
              <select style={controlStyle} disabled>
                <option>单日截面</option>
              </select>
            </label>
          </FilterBar>
        </PageFilterTray>
      </PageHeader>

      <div data-testid="operations-business-kpis" style={operationsHeroStripStyle}>
        {operationsHeadlineCards.map((card) => (
          <OperationsMetricCard
            key={card.title}
            label={card.title}
            value={card.value}
            unit={card.unit}
            detail={card.detail}
            status={card.status}
          />
        ))}
      </div>
      </div>

      <div style={sectionBlockStyle}>
      <OperationsSectionLead
        eyebrow="Core View"
        title="结论、桥接与质量观察"
        description="首屏先给出当前已被正式读链路支撑的经营判断，再用质量观察告诉你哪些指标仍是待补口径。收益成本桥继续明确标为示意。"
      />
      <div data-testid="operations-conclusion-grid" style={tripleGridStyle}>
        <BusinessConclusion
          reportDate={balanceOverviewQuery.data?.result.report_date}
          detailRowCount={balanceOverviewQuery.data?.result.detail_row_count}
          summaryRowCount={balanceOverviewQuery.data?.result.summary_row_count}
          marketValueAmount={formatYuanAmountAsYiPlain(balanceOverviewQuery.data?.result.total_market_value_amount)}
          amortizedCostAmount={formatYuanAmountAsYiPlain(balanceOverviewQuery.data?.result.total_amortized_cost_amount)}
          accruedInterestAmount={formatYuanAmountAsYiPlain(balanceOverviewQuery.data?.result.total_accrued_interest_amount)}
          missingFxCount={missingFxRows.length}
        />
        <RevenueCostBridge />
        <QualityObservation
          sourceCount={sourceSummaries.length}
          macroCount={macroLatest.length}
          newsCount={newsTotal}
          fxMaterializedCount={fxFormalStatus?.materialized_count}
          fxCandidateCount={fxFormalStatus?.candidate_count}
          missingFxCount={missingFxRows.length}
        />
      </div>
      </div>

      <div style={sectionBlockStyle}>
      <OperationsSectionLead
        eyebrow="Contribution"
        title="经营贡献与行动项"
        description="把正式余额读面的汇总行、当前关注事项和近期经营日历放到同一层，方便从判断直接过渡到行动。"
      />
      <div data-testid="operations-contribution-grid" style={contributionGridStyle}>
        <BusinessContributionTable
          reportDate={latestBalanceReportDate}
          rows={balanceSummaryRows}
          loading={balanceSummaryQuery.isLoading}
          error={balanceSummaryQuery.isError}
          onRetry={() => void balanceSummaryQuery.refetch()}
        />
        <OperationsPanel title="本期关注事项">
          <AlertList items={OPERATIONS_WATCH_ITEMS} />
        </OperationsPanel>
        <OperationsPanel title="近期经营日历">
          <CalendarList items={OPERATIONS_CALENDAR_MOCK} />
        </OperationsPanel>
      </div>
      </div>

      <div style={sectionBlockStyle}>
      <OperationsSectionLead
        eyebrow="Structure"
        title="期限与集中度 / 管理输出"
        description="期限缺口和管理动作继续放在本页首屏，但只保留可读的结构解读，不再冒充正式阈值结论。"
      />
      <div data-testid="operations-structure-grid" style={pairGridStyle}>
        <TenorConcentrationPanel />
        <ManagementOutput
          recommendationTitle={recommendation.title}
          recommendationDetail={recommendation.detail}
          recommendationActionLabel={recommendation.actionLabel}
          missingFxCount={missingFxRows.length}
        />
      </div>
      </div>

      <div style={sectionBlockStyle}>
      <OperationsSectionLead
        eyebrow="专题入口"
        title="专题入口"
        description="经营分析页只保留专题速览和跳转，正式工作簿与细项下钻仍在对应主题页中查看。"
      />
      <div
        data-testid="operations-entry-balance-section"
        style={focusEntryShellStyle}
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
            <div style={entryHeaderStyle}>
              <h2 style={entryTitleStyle}>
                专题入口：资产负债正式读面
              </h2>
              <Link to="/balance-analysis" style={linkStyle} aria-label="进入资产负债分析">
                进入资产负债分析
              </Link>
            </div>
          }
        >
          {balanceOverview ? (
            <div>
              <p style={entryIntroStyle}>
                报告日{" "}
                <span data-testid="operations-entry-balance-report-date">
                  {balanceOverview.report_date}
                </span>
                ，口径 position_scope={balanceOverview.position_scope}，
                currency_basis={balanceOverview.currency_basis}。这里只保留正式工作簿速览，
                作为经营分析后的专题入口，不在本页展开完整工作簿。
              </p>
              <div style={balanceOverviewGridStyle}>
                {[
                  {
                    testId: "operations-entry-balance-detail-rows",
                    label: "明细行数",
                    value: String(balanceOverview!.detail_row_count),
                    detail: "正式读面明细行数",
                  },
                  {
                    testId: "operations-entry-balance-summary-rows",
                    label: "汇总行数",
                    value: String(balanceOverview!.summary_row_count),
                    detail: "正式读面汇总行数",
                  },
                  {
                    testId: "operations-entry-balance-market-value",
                    label: "总市值合计",
                    value: formatYuanAmountAsYiPlain(balanceOverview!.total_market_value_amount),
                    detail: "正式读面总市值",
                  },
                  {
                    testId: "operations-entry-balance-amortized",
                    label: "摊余成本合计",
                    value: formatYuanAmountAsYiPlain(balanceOverview!.total_amortized_cost_amount),
                    detail: "正式读面摊余成本",
                  },
                  {
                    testId: "operations-entry-balance-accrued",
                    label: "应计利息合计",
                    value: formatYuanAmountAsYiPlain(balanceOverview!.total_accrued_interest_amount),
                    detail: "正式读面应计利息",
                  },
                ].map((item) => (
                  <div key={item.testId} data-testid={item.testId}>
                    <OperationsMetricCard
                      label={item.label}
                      value={item.value}
                      detail={item.detail}
                      unit={
                        item.testId === "operations-entry-balance-market-value" ||
                        item.testId === "operations-entry-balance-amortized" ||
                        item.testId === "operations-entry-balance-accrued"
                          ? "亿元"
                          : undefined
                      }
                      compact
                    />
                  </div>
                ))}
                {/*
                <div data-testid="operations-entry-balance-detail-rows">
                  <KpiCard
                    title="明细行数"
                    value={String(balanceOverview!.detail_row_count)}
                    detail="正式读面明细行数"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-summary-rows">
                  <KpiCard
                    title="汇总行数"
                    value={String(balanceOverview!.summary_row_count)}
                    detail="正式读面汇总行数"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-market-value">
                  <KpiCard
                    title="总市值合计"
                    value={formatYuanAmountAsYiPlain(balanceOverview!.total_market_value_amount)}
                    detail="正式读面总市值"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-amortized">
                  <KpiCard
                    title="摊余成本合计"
                    value={formatYuanAmountAsYiPlain(balanceOverview!.total_amortized_cost_amount)}
                    detail="正式读面摊余成本"
                    valueVariant="text"
                  />
                </div>
                <div data-testid="operations-entry-balance-accrued">
                  <KpiCard
                    title="应计利息合计"
                    value={formatYuanAmountAsYiPlain(balanceOverview!.total_accrued_interest_amount)}
                    detail="正式读面应计利息"
                    valueVariant="text"
                  />
                </div>
                */}
              </div>
            </div>
          ) : null}
        </AsyncSection>
      </div>
      </div>

      <OperationsPanel title={recommendation.title}>
        <div data-testid="operations-entry-recommendation" style={recommendationBodyStyle}>
          <p style={recommendationTextStyle}>
            {recommendation.detail}
          </p>
          <div>
            <Link to={recommendation.actionTo} style={linkStyle}>
              {recommendation.actionLabel}
            </Link>
          </div>
        </div>
      </OperationsPanel>

      <Collapse
        style={{ marginTop: 28 }}
        bordered={false}
        defaultActiveKey={["ops-sources"]}
        items={[
          {
            key: "ops-sources",
            label: <span style={disclosureLabelStyle}>数据源与运维状态</span>,
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
                            ...pageInsetCardStyle,
                            padding: 14,
                          }}
                        >
                          <strong>{summary.source_family.toUpperCase()}</strong>
                          <div style={{ color: "#5c6b82", fontSize: 13 }}>
                            报告日 {summary.report_date ?? "—"} / 行数 {summary.total_rows} / 人工复核{" "}
                            {summary.manual_review_count}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-source-file">
                            源文件 {summary.source_file?.trim() ? summary.source_file : "—"}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-source-group-counts">
                            分组计数 {formatGroupCounts(summary.group_counts)}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-source-preview-mode">
                            预览模式 {summary.preview_mode ?? "—"}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }}>
                            区间 {summary.report_start_date ?? "—"} - {summary.report_end_date ?? "—"} / 粒度{" "}
                            {summary.report_granularity ?? "—"}
                            {summary.rule_version ? ` / 规则 ${summary.rule_version}` : ""}
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
                            ...pageInsetCardStyle,
                            padding: 14,
                          }}
                        >
                          <strong>{point.series_name}</strong>
                          <div style={{ color: "#5c6b82", fontSize: 13 }}>
                            {point.trade_date} / {point.value_numeric.toFixed(2)} {point.unit}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-macro-fetch-meta">
                            刷新层级 {point.refresh_tier ?? "—"} / 拉取 {point.fetch_mode ?? "—"} / 粒度{" "}
                            {point.fetch_granularity ?? "—"}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-macro-policy-note">
                            策略说明 {point.policy_note?.trim() ? point.policy_note : "—"}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-macro-latest-change">
                            最新变化{" "}
                            {point.latest_change === null || point.latest_change === undefined
                              ? "—"
                              : String(point.latest_change)}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-macro-recent-points">
                            近期点位{" "}
                            {Array.isArray(point.recent_points) && point.recent_points.length > 0
                              ? `有 ${point.recent_points.length} 条`
                              : "无"}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }}>
                            频率 {point.frequency ?? "—"} / 供应商版本 {point.vendor_version ?? "—"}
                            {point.quality_flag ? ` / 质量 ${point.quality_flag}` : ""}
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
                            ...pageInsetCardStyle,
                            padding: 14,
                          }}
                        >
                          <strong>{event.topic_code}</strong>
                          <div style={{ color: "#5c6b82", fontSize: 13 }}>
                            分组 {event.group_id} / {event.received_at}
                          </div>
                          <div style={{ color: "#8090a8", fontSize: 12 }} data-testid={`operations-news-meta-${event.event_key}`}>
                            类型 {event.content_type ?? "—"} / serial {event.serial_id ?? "—"} / req{" "}
                            {event.request_id ?? "—"} / idx {event.item_index ?? "—"} / err{" "}
                            {event.error_code}
                            {event.error_msg?.trim() ? ` / ${event.error_msg}` : ""}
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
                    isEmpty={!fxFormalStatusQuery.isLoading && !fxFormalStatusQuery.isError && fxFormalRows.length === 0}
                    onRetry={() => void fxFormalStatusQuery.refetch()}
                  >
                    <PageSurfacePanel
                      testId="operations-entry-formal-fx-status"
                      as="div"
                      style={{ display: "grid", gap: 12 }}
                    >
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
                              ...pageInsetCardStyle,
                              padding: 14,
                            }}
                          >
                            <strong>{row.pair_label}</strong>
                            <div style={{ color: "#8090a8", fontSize: 12 }}>
                              {row.series_name?.trim() || row.vendor_series_code || "—"}
                            </div>
                            <div style={{ color: "#5c6b82", fontSize: 13 }}>
                              状态 {row.status} / 交易日 {row.trade_date ?? "待定"} / 观测日{" "}
                              {row.observed_trade_date ?? "待定"} / 营业日{" "}
                              {row.is_business_day === null ? "—" : row.is_business_day ? "是" : "否"}
                            </div>
                            <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="operations-fx-row-versions">
                              来源 {row.source_name ?? "—"} / 源版本 {row.source_version ?? "—"} / 供应商版本{" "}
                              {row.vendor_version ?? "—"}
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
                    </PageSurfacePanel>
                  </AsyncSection>

                  <PageSurfacePanel as="section" style={{ display: "grid", gap: 12 }}>
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
                          手动触发正式损益（PnL）物化任务，与正式 FX 状态读面相互独立。
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
                  </PageSurfacePanel>
                </div>
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}
