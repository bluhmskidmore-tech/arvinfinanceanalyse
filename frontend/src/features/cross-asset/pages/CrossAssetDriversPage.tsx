import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { MacroBondLinkagePayload, MacroBondLinkageTopCorrelation } from "../../../api/contracts";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../../components/AsyncSection";
import { PageHeader, PageSectionLead, pageSurfacePanelStyle } from "../../../components/page/PagePrimitives";
import { StatusPill } from "../../../components/StatusPill";
import ReactECharts from "../../../lib/echarts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { KpiCard } from "../../workbench/components/KpiCard";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { CrossAssetEventCalendar } from "../components/CrossAssetEventCalendar";
import { CrossAssetSparkline } from "../components/CrossAssetSparkline";
import { MarketCandidateActions } from "../components/MarketCandidateActions";
import { PageOutput } from "../components/PageOutput";
import { WatchList } from "../components/WatchList";
import {
  buildCrossAssetCandidateActions,
  buildCrossAssetEventItems,
  buildCrossAssetNcdProxyEvidence,
  buildCrossAssetStatusFlags,
  buildCrossAssetWatchList,
  buildResearchSummaryCards,
  buildTransmissionAxisRows,
  type CrossAssetNcdProxyEvidence,
  type CrossAssetResearchViewCard,
  type CrossAssetTransmissionAxisRow,
} from "../lib/crossAssetDriversPageModel";
import { buildDriverColumns, buildEnvironmentTags, driverStanceStyle } from "../lib/crossAssetDriversModel";
import { buildCrossAssetTrendOption } from "../lib/crossAssetTrendChart";
import {
  maxCrossAssetHeadlineTradeDate,
  resolveCrossAssetKpis,
  type ResolvedCrossAssetKpi,
} from "../lib/crossAssetKpiModel";

const t = designTokens;

const pageBg = t.color.neutral[50];

const detailPanelStyle = {
  ...pageSurfacePanelStyle,
  padding: t.space[5],
  boxShadow: t.shadow.card,
} as const;

const sparkStroke: Record<ResolvedCrossAssetKpi["changeTone"], string> = {
  positive: t.color.semantic.profit,
  negative: t.color.semantic.loss,
  warning: t.color.warning[500],
  default: t.color.primary[600],
};

function linkageHeatmapRows(correlations: MacroBondLinkageTopCorrelation[]) {
  if (correlations.length === 0) {
    return [
      {
        indicator: "No governed linkage ranking yet",
        current: "-",
        mid: "-",
        eval: "Pending",
        evalTone: "warning" as const,
      },
    ];
  }

  return correlations.slice(0, 8).map((row) => {
    const indicator = `${row.series_name} -> ${row.target_family}${row.target_tenor ? ` (${row.target_tenor})` : ""}`;
    const current = row.correlation_3m != null ? row.correlation_3m.toFixed(2) : "-";
    const mid = row.correlation_6m != null ? row.correlation_6m.toFixed(2) : "-";
    let evalLabel = "Mixed";
    let evalTone: "bull" | "bear" | "warning" = "warning";
    if (row.direction === "positive") {
      evalLabel = "Positive";
      evalTone = "bull";
    } else if (row.direction === "negative") {
      evalLabel = "Negative";
      evalTone = "bear";
    }
    return { indicator, current, mid, eval: evalLabel, evalTone };
  });
}

function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
}

function MiniKpiCard({ kpi }: { kpi: ResolvedCrossAssetKpi }) {
  const stroke = sparkStroke[kpi.changeTone];
  return (
    <div
      style={{
        padding: `${t.space[4]}px ${t.space[4]}px ${t.space[3]}px`,
        borderRadius: t.radius.md,
        background: t.color.primary[50],
        border: `1px solid ${t.color.neutral[200]}`,
        boxShadow: t.shadow.card,
        minHeight: 132,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: t.fontSize[11],
          color: t.color.neutral[600],
          fontWeight: 600,
          lineHeight: t.lineHeight.snug,
        }}
      >
        {kpi.label}
      </div>
      <div
        style={{
          ...tabularNumsStyle,
          fontSize: t.fontSize[20],
          fontWeight: 700,
          color: t.color.neutral[800],
          marginTop: t.space[2],
          letterSpacing: "-0.02em",
        }}
      >
        {kpi.valueLabel}
      </div>
      <div
        style={{
          fontSize: t.fontSize[12],
          fontWeight: 600,
          color: stroke,
          marginTop: t.space[1],
        }}
      >
        {kpi.changeLabel}
      </div>
      <div style={{ marginTop: "auto", paddingTop: t.space[2] }}>
        <CrossAssetSparkline values={kpi.sparkline} stroke={stroke} height={26} />
      </div>
      <div style={{ fontSize: t.fontSize[11], color: t.color.neutral[500], marginTop: t.space[2] }}>{kpi.tag}</div>
    </div>
  );
}

function ResearchViewsPanel({ rows }: { rows: CrossAssetResearchViewCard[] }) {
  return (
    <section data-testid="cross-asset-research-views" style={detailPanelStyle}>
      <div style={{ display: "grid", gap: t.space[2], marginBottom: t.space[4] }}>
        <h2 style={{ margin: 0, fontSize: t.fontSize[16], fontWeight: 700, color: t.color.neutral[900] }}>
          投资研究判断
        </h2>
        <p style={{ margin: 0, color: t.color.neutral[600], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
          第一屏先给出 duration / curve / credit / instrument 结论，再往下看证据和执行观察。
        </p>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: t.space[3],
        }}
      >
        {rows.map((row) => (
          <article
            key={row.key}
            data-testid={`cross-asset-research-card-${row.key}`}
            style={{
              borderRadius: t.radius.md,
              border: `1px solid ${t.color.neutral[100]}`,
              background: t.color.neutral[50],
              padding: t.space[4],
              display: "grid",
              gap: t.space[2],
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: t.space[2], alignItems: "center" }}>
              <div style={{ fontSize: t.fontSize[14], fontWeight: 700, color: t.color.neutral[900] }}>{row.label}</div>
              <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap", justifyContent: "flex-end" }}>
                <StatusPill status={row.status === "ready" ? "normal" : "caution"} label={row.status === "ready" ? "ready" : "pending"} />
                <StatusPill status={row.source === "backend" ? "normal" : "warning"} label={row.source} />
              </div>
            </div>
            <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap" }}>
              <StatusPill status="normal" label={row.stance} />
              <StatusPill status="caution" label={row.confidence} />
            </div>
            <p style={{ margin: 0, color: t.color.neutral[700], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
              {row.summary}
            </p>
            <div style={{ fontSize: t.fontSize[12], color: t.color.neutral[500], lineHeight: t.lineHeight.relaxed }}>
              Targets: {row.affectedTargets.length > 0 ? row.affectedTargets.join(", ") : "pending mapping"}
            </div>
            {row.evidence.length > 0 ? (
              <div style={{ fontSize: t.fontSize[12], color: t.color.neutral[600], lineHeight: t.lineHeight.relaxed }}>
                Evidence: {row.evidence[0]}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function NcdProxyEvidencePanel({
  evidence,
  isLoading,
}: {
  evidence: CrossAssetNcdProxyEvidence;
  isLoading?: boolean;
}) {
  const isProxyNotMatrix = !evidence.isActualNcdMatrix;
  return (
    <section
      data-testid="cross-asset-ncd-proxy"
      style={{
        ...detailPanelStyle,
        border: `1px solid ${isProxyNotMatrix ? t.color.warning[200] : t.color.neutral[200]}`,
        background: isProxyNotMatrix ? t.color.warning[50] : t.color.neutral[50],
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: t.space[3], flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: t.fontSize[16], fontWeight: 700, color: t.color.neutral[900] }}>NCD / 资金代理</h2>
        {isLoading ? (
          <StatusPill status="caution" label="loading" />
        ) : (
          <StatusPill
            status={isProxyNotMatrix ? "warning" : "normal"}
            label={isProxyNotMatrix ? "proxy · not NCD matrix" : "actual matrix (verify)"}
          />
        )}
      </div>
      <p style={{ margin: `${t.space[2]}px 0 0`, color: t.color.neutral[600], fontSize: t.fontSize[12] }}>{evidence.proxyLabel}</p>
      {evidence.asOfDate ? (
        <p data-testid="cross-asset-ncd-asof" style={{ margin: `${t.space[1]}px 0 0`, color: t.color.neutral[500], fontSize: t.fontSize[12] }}>
          as of {evidence.asOfDate}
        </p>
      ) : null}
      <p
        data-testid="cross-asset-ncd-proxy-warning"
        style={{
          margin: `${t.space[3]}px 0 0`,
          color: isLoading ? t.color.neutral[500] : t.color.warning[800],
          fontSize: t.fontSize[13],
          lineHeight: t.lineHeight.relaxed,
        }}
      >
        {isLoading ? "正在加载资金代理…" : evidence.proxyWarning}
      </p>
      {evidence.rowCaptions.length > 0 ? (
        <ul
          data-testid="cross-asset-ncd-proxy-rows"
          style={{ margin: `${t.space[2]}px 0 0`, paddingLeft: t.space[5], color: t.color.neutral[700], fontSize: t.fontSize[12] }}
        >
          {evidence.rowCaptions.map((line) => (
            <li key={line} style={{ marginBottom: t.space[1] }}>
              {line}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function TransmissionAxesPanel({ rows }: { rows: CrossAssetTransmissionAxisRow[] }) {
  return (
    <section data-testid="cross-asset-transmission-axes" style={detailPanelStyle}>
      <div style={{ display: "grid", gap: t.space[2], marginBottom: t.space[4] }}>
        <h2 style={{ margin: 0, fontSize: t.fontSize[16], fontWeight: 700, color: t.color.neutral[900] }}>
          传导主线
        </h2>
        <p style={{ margin: 0, color: t.color.neutral[600], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
          Unsupported axes stay visible as pending signals instead of being inferred from unrelated data.
        </p>
      </div>
      <div style={{ display: "grid", gap: t.space[3] }}>
        {rows.map((row) => (
          <article
            key={row.axisKey}
            data-testid={`cross-asset-transmission-axis-${row.axisKey}`}
            style={{
              borderRadius: t.radius.md,
              border: `1px solid ${t.color.neutral[100]}`,
              background: row.status === "pending_signal" ? t.color.warning[50] : t.color.neutral[50],
              padding: t.space[4],
              display: "grid",
              gap: t.space[2],
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: t.space[2], alignItems: "center" }}>
              <div style={{ fontSize: t.fontSize[14], fontWeight: 700, color: t.color.neutral[900] }}>{row.label}</div>
              <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap", justifyContent: "flex-end" }}>
                <StatusPill status={row.status === "ready" ? "normal" : "caution"} label={row.status === "ready" ? "ready" : "pending_signal"} />
                <StatusPill status={row.source === "backend" ? "normal" : "warning"} label={row.source} />
              </div>
            </div>
            <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap" }}>
              <StatusPill status={row.status === "ready" ? "normal" : "warning"} label={row.stance} />
              {row.impactedViews.length > 0 ? (
                <StatusPill status="caution" label={`views ${row.impactedViews.join(", ")}`} />
              ) : null}
            </div>
            <p style={{ margin: 0, color: t.color.neutral[700], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
              {row.summary}
            </p>
            {row.requiredSeriesIds.length > 0 ? (
              <div style={{ fontSize: t.fontSize[12], color: t.color.neutral[500] }}>
                Required series: {row.requiredSeriesIds.join(", ")}
              </div>
            ) : null}
            {row.warnings.length > 0 ? (
              <div style={{ fontSize: t.fontSize[12], color: t.color.warning[600] }}>
                {row.warnings[0]}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

export default function CrossAssetDriversPage() {
  const client = useApiClient();
  const latestQuery = useQuery({
    queryKey: ["cross-asset", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const latestSeries = useMemo(() => latestQuery.data?.result.series ?? [], [latestQuery.data?.result.series]);
  const latestMeta = latestQuery.data?.result_meta;

  const crossAssetDataDate = useMemo(() => maxCrossAssetHeadlineTradeDate(latestSeries), [latestSeries]);
  const linkageReportDate = useMemo(() => {
    if (latestSeries.length === 0) {
      return "";
    }
    return latestSeries.map((point) => point.trade_date).sort((left, right) => right.localeCompare(left))[0];
  }, [latestSeries]);

  const researchCalendarQuery = useQuery({
    queryKey: ["cross-asset", "research-calendar", client.mode, linkageReportDate],
    queryFn: () => client.getResearchCalendarEvents({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });

  const macroBondLinkageQuery = useQuery({
    queryKey: ["cross-asset", "macro-bond-linkage", client.mode, linkageReportDate],
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });

  const ncdFundingProxyQuery = useQuery({
    queryKey: ["cross-asset", "ncd-funding-proxy", client.mode],
    queryFn: () => client.getNcdFundingProxy(),
    retry: false,
  });

  const macroBondLinkage = useMemo(
    () => macroBondLinkageQuery.data?.result ?? ({} as Partial<MacroBondLinkagePayload>),
    [macroBondLinkageQuery.data?.result],
  );
  const linkageMeta = macroBondLinkageQuery.data?.result_meta;
  const macroBondLinkageWarnings = useMemo(() => macroBondLinkage.warnings ?? [], [macroBondLinkage.warnings]);
  const hasPortfolioImpact = Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0;
  const linkageBodyEmpty =
    macroBondLinkageQuery.isSuccess &&
    Boolean(linkageReportDate) &&
    macroBondLinkage.environment_score?.composite_score == null &&
    !hasPortfolioImpact &&
    macroBondLinkageWarnings.length === 0 &&
    (macroBondLinkage.top_correlations ?? []).length === 0;

  const env = useMemo(() => macroBondLinkage.environment_score ?? {}, [macroBondLinkage.environment_score]);
  const kpis = useMemo(() => resolveCrossAssetKpis(latestSeries), [latestSeries]);
  const trendOption = useMemo(() => buildCrossAssetTrendOption(latestSeries), [latestSeries]);
  const drivers = useMemo(() => buildDriverColumns(env), [env]);
  const envTags = useMemo(() => buildEnvironmentTags(env), [env]);
  const heatmapRows = useMemo(() => linkageHeatmapRows(macroBondLinkage.top_correlations ?? []), [macroBondLinkage.top_correlations]);
  const researchViewCards = useMemo(
    () =>
      buildResearchSummaryCards({
        researchViews: macroBondLinkage.research_views,
        env,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
      }),
    [env, macroBondLinkage.research_views, macroBondLinkage.top_correlations, macroBondLinkageWarnings],
  );
  const transmissionAxisRows = useMemo(
    () =>
      buildTransmissionAxisRows({
        transmissionAxes: macroBondLinkage.transmission_axes,
        env,
      }),
    [env, macroBondLinkage.transmission_axes],
  );
  const ncdProxyPayload = ncdFundingProxyQuery.data?.result ?? null;
  const ncdProxyEvidence = useMemo(
    () =>
      buildCrossAssetNcdProxyEvidence({
        result: ncdProxyPayload,
        available: ncdFundingProxyQuery.isSuccess && !ncdFundingProxyQuery.isError && Boolean(ncdFundingProxyQuery.data),
      }),
    [ncdFundingProxyQuery.data, ncdFundingProxyQuery.isError, ncdFundingProxyQuery.isSuccess, ncdProxyPayload],
  );
  const candidateActions = useMemo(
    () =>
      buildCrossAssetCandidateActions({
        researchViews: macroBondLinkage.research_views,
        transmissionAxes: macroBondLinkage.transmission_axes,
        env,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        ncdProxy: ncdProxyPayload,
      }),
    [
      env,
      macroBondLinkage.research_views,
      macroBondLinkage.top_correlations,
      macroBondLinkage.transmission_axes,
      macroBondLinkageWarnings,
      ncdProxyPayload,
    ],
  );
  const eventItems = useMemo(
    () =>
      buildCrossAssetEventItems({
        events: researchCalendarQuery.data ?? [],
      }),
    [researchCalendarQuery.data],
  );
  const watchRows = useMemo(
    () =>
      buildCrossAssetWatchList({
        kpis,
        researchViews: macroBondLinkage.research_views,
        transmissionAxes: macroBondLinkage.transmission_axes,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
      }),
    [
      kpis,
      macroBondLinkage.research_views,
      macroBondLinkage.top_correlations,
      macroBondLinkage.transmission_axes,
      macroBondLinkageWarnings,
    ],
  );
  const statusFlags = useMemo(() => {
    if (latestQuery.isLoading || (Boolean(linkageReportDate) && macroBondLinkageQuery.isLoading)) {
      return [];
    }
    return buildCrossAssetStatusFlags({
      latestMeta,
      linkageMeta,
      latestSeries,
      crossAssetDataDate,
      linkageReportDate,
    });
  }, [
    crossAssetDataDate,
    latestMeta,
    latestQuery.isLoading,
    latestSeries,
    linkageMeta,
    linkageReportDate,
    macroBondLinkageQuery.isLoading,
  ]);

  const evalColor = {
    bull: t.color.semantic.profit,
    bear: t.color.semantic.loss,
    warning: t.color.warning[500],
  } as const;

  return (
    <section
      data-testid="cross-asset-drivers-page"
      style={{
        background: pageBg,
        minHeight: "100%",
        borderRadius: t.radius.lg,
        padding: t.space[4],
      }}
    >
      <div data-testid="cross-asset-page">
        <PageHeader
          title="跨资产驱动"
          eyebrow="Overview"
          badgeLabel={client.mode === "real" ? "真实 analytical 读链路" : "本地 mock contract replay"}
          badgeTone={client.mode === "real" ? "positive" : "accent"}
          description="这页只回答一个问题：外部变量正在怎样传导到债券，不直接替代正式执行与风控口径。完整宏观序列仍在市场数据页，跨资产页只保留判断、告警和候选动作。"
        >
          <div style={{ display: "grid", gap: t.space[3] }}>
            <p style={{ margin: 0, color: t.color.neutral[600], fontSize: t.fontSize[13] }}>
              数据日期 <strong style={{ ...tabularNumsStyle, color: t.color.neutral[800] }}>{crossAssetDataDate || linkageReportDate || "—"}</strong>
              {" · "}
              完整序列请转到 <Link to="/market-data" style={{ color: t.color.primary[600], fontWeight: 600 }}>市场数据</Link>
            </p>
            <div data-testid="cross-asset-status-flags" style={{ display: "flex", flexWrap: "wrap", gap: t.space[2] }}>
              {statusFlags.map((flag) => (
                <StatusPill key={flag.id} status={flag.tone} label={flag.label} />
              ))}
            </div>
          </div>
        </PageHeader>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) minmax(300px, 360px)",
            gap: t.space[4],
            alignItems: "start",
          }}
        >
          <div style={{ display: "grid", gap: t.space[4], minWidth: 0 }}>
            <PageSectionLead
              eyebrow="Investment Research"
              title="研究结论先行"
              description="先看研究判断和传导主线，再决定如何解释后面的 KPI、事件和 analytical 证据。"
            />
            <ResearchViewsPanel rows={researchViewCards} />
            <TransmissionAxesPanel rows={transmissionAxisRows} />

            <PageSectionLead
              eyebrow="Context"
              title="环境概览"
              description="在研究判断之后，用顶部环境 KPI 和驱动拆解补充证据。"
            />
            <div
              data-testid="cross-asset-kpi-band"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: t.space[3],
              }}
            >
              {kpis.map((kpi) => (
                <MiniKpiCard key={kpi.key} kpi={kpi} />
              ))}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
                gap: t.space[3],
              }}
            >
              <section style={detailPanelStyle}>
                <h2 style={{ margin: `0 0 ${t.space[3]}px`, fontSize: t.fontSize[16], fontWeight: 600, color: t.color.neutral[900] }}>
                  市场判断
                </h2>
                <p style={{ margin: 0, color: t.color.neutral[700], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
                  {macroBondLinkageQuery.isLoading || latestQuery.isLoading
                    ? "正在加载联动分析…"
                    : env.signal_description ?? "当前暂无可用摘要；请先确认 provenance 与日期状态。"}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: t.space[2], marginTop: t.space[4] }}>
                  <StatusPill status="normal" label={`主导因素 ${envTags.primary}`} />
                  <StatusPill status="caution" label={`次要扰动 ${envTags.secondary}`} />
                  <StatusPill status="warning" label={`风格判断 ${envTags.style}`} />
                </div>
              </section>

              <section style={detailPanelStyle}>
                <h2 style={{ margin: `0 0 ${t.space[3]}px`, fontSize: t.fontSize[16], fontWeight: 600, color: t.color.neutral[900] }}>
                  驱动拆解
                </h2>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                    gap: t.space[3],
                  }}
                >
                  {drivers.map((col) => {
                    const stanceStyle = driverStanceStyle(col.tone);
                    return (
                      <div
                        key={col.title}
                        style={{
                          borderRadius: t.radius.md,
                          border: `1px solid ${t.color.neutral[100]}`,
                          padding: t.space[3],
                          background: t.color.neutral[50],
                          minHeight: 160,
                        }}
                      >
                        <div style={{ fontSize: t.fontSize[12], fontWeight: 600, color: t.color.neutral[600], marginBottom: t.space[2] }}>
                          {col.title}
                        </div>
                        <div
                          style={{
                            display: "inline-block",
                            padding: `2px ${t.space[2]}px`,
                            borderRadius: t.radius.sm,
                            fontSize: t.fontSize[12],
                            fontWeight: 700,
                            background: stanceStyle.bg,
                            color: stanceStyle.color,
                            marginBottom: t.space[2],
                          }}
                        >
                          {col.stance}
                        </div>
                        <ul style={{ margin: 0, paddingLeft: t.space[5], color: t.color.neutral[700], fontSize: t.fontSize[11], lineHeight: t.lineHeight.normal }}>
                          {col.bullets.map((bullet) => (
                            <li key={bullet}>{bullet}</li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>

            <MarketCandidateActions rows={candidateActions} />

            <NcdProxyEvidencePanel evidence={ncdProxyEvidence} isLoading={ncdFundingProxyQuery.isLoading} />

            <PageSectionLead
              eyebrow="Observation"
              title="走势、事件与观察"
              description="完成研究判断后，再看走势、事件流和观察名单，避免把噪音放到结论前面。"
            />
            <section style={detailPanelStyle}>
              <h2 style={{ margin: `0 0 ${t.space[2]}px`, fontSize: t.fontSize[16], fontWeight: 600, color: t.color.neutral[900] }}>
                跨资产走势（近 20 日，统一基准 = 100）
              </h2>
              <p style={{ margin: `0 0 ${t.space[2]}px`, color: t.color.neutral[500], fontSize: t.fontSize[12] }}>
                所有序列使用首日 = 100 的归一化结果，便于直接比较方向与节奏。
              </p>
              {latestQuery.isLoading ? (
                <div style={{ height: 320, display: "flex", alignItems: "center", justifyContent: "center", color: t.color.neutral[500] }}>
                  正在加载宏观序列…
                </div>
              ) : trendOption ? (
                <ReactECharts option={trendOption} style={{ height: 320, width: "100%" }} notMerge lazyUpdate />
              ) : (
                <div style={{ height: 200, color: t.color.neutral[500], fontSize: t.fontSize[13] }}>
                  当前没有足够历史点，无法绘制跨资产走势。
                </div>
              )}
            </section>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
                gap: t.space[3],
                alignItems: "start",
              }}
            >
              <CrossAssetEventCalendar items={eventItems} />
              <WatchList rows={watchRows} />
            </div>

            <PageSectionLead
              eyebrow="Analytical"
              title="分析结果与输出"
              description="联动评分与组合影响继续保持 analytical 口径，只提供证据与风险提示。"
            />
            <AsyncSection
              title="宏观 - 债券联动（评分与组合影响）"
              isLoading={macroBondLinkageQuery.isLoading || latestQuery.isLoading}
              isError={macroBondLinkageQuery.isError || latestQuery.isError}
              isEmpty={linkageBodyEmpty}
              onRetry={() => {
                void latestQuery.refetch();
                void macroBondLinkageQuery.refetch();
                void researchCalendarQuery.refetch();
              }}
            >
              {!linkageReportDate ? (
                <p style={{ color: t.color.neutral[600], fontSize: t.fontSize[14] }}>
                  缺少可用交易日，当前无法计算宏观-债券联动分析。
                </p>
              ) : (
                <div style={{ display: "grid", gap: t.space[4] }}>
                  {macroBondLinkageWarnings.length > 0 ? (
                    <ul
                      data-testid="cross-asset-linkage-warning-list"
                      style={{
                        margin: 0,
                        paddingLeft: t.space[5],
                        color: t.color.neutral[600],
                        fontSize: t.fontSize[13],
                        lineHeight: t.lineHeight.relaxed,
                      }}
                    >
                      {macroBondLinkageWarnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  ) : null}

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                      gap: t.space[3],
                    }}
                  >
                    <div data-testid="cross-asset-linkage-composite-score">
                      <KpiCard
                        title="综合评分"
                        value={env.composite_score != null ? String(env.composite_score.toFixed(2)) : "不可用"}
                        detail={env.signal_description ?? "缺少环境评分数据。"}
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.composite_score != null ? env.composite_score : null)}
                      />
                    </div>
                    <div data-testid="cross-asset-linkage-rate-direction">
                      <KpiCard
                        title="利率方向"
                        value={env.rate_direction ?? "不可用"}
                        detail={env.rate_direction_score != null ? `direction score ${env.rate_direction_score.toFixed(2)}` : "缺少方向评分。"}
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.rate_direction_score != null ? env.rate_direction_score : null)}
                      />
                    </div>
                    <div data-testid="cross-asset-linkage-liquidity-score">
                      <KpiCard
                        title="流动性评分"
                        value={env.liquidity_score != null ? env.liquidity_score.toFixed(2) : "不可用"}
                        detail="正值偏松，负值偏紧。"
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.liquidity_score != null ? env.liquidity_score : null)}
                      />
                    </div>
                    <div data-testid="cross-asset-linkage-growth-score">
                      <KpiCard
                        title="增长评分"
                        value={env.growth_score != null ? env.growth_score.toFixed(2) : "不可用"}
                        detail="宏观增长方向的简化分值。"
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.growth_score != null ? env.growth_score : null)}
                      />
                    </div>
                  </div>

                  <section data-testid="cross-asset-linkage-portfolio-impact" style={detailPanelStyle}>
                    <h2 style={{ marginTop: 0, marginBottom: t.space[2], fontSize: t.fontSize[16], fontWeight: 600, color: t.color.neutral[900] }}>
                      组合影响估算
                    </h2>
                    <p style={{ marginTop: 0, color: t.color.neutral[600], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
                      以下数值属于 analytical estimate，只作为环境敏感度提示，不代表正式损益。
                    </p>
                    {hasPortfolioImpact ? (
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                          gap: t.space[3],
                        }}
                      >
                        <div>
                          <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>rate change</div>
                          <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}</div>
                        </div>
                        <div>
                          <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>spread widening</div>
                          <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}</div>
                        </div>
                        <div>
                          <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>total estimate</div>
                          <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[14] }}>当前没有可用组合影响估算。</div>
                    )}
                  </section>
                </div>
              )}
            </AsyncSection>

            <div data-testid="cross-asset-page-output">
              <PageOutput
                envTags={envTags}
                signalPreview={env.signal_description ?? null}
                linkageWarnings={macroBondLinkageWarnings}
                topCorrelationSummary={
                  macroBondLinkage.top_correlations?.[0]
                    ? `${macroBondLinkage.top_correlations[0].series_name} -> ${macroBondLinkage.top_correlations[0].target_family}${macroBondLinkage.top_correlations[0].target_tenor ? ` ${macroBondLinkage.top_correlations[0].target_tenor}` : ""}`
                    : null
                }
              />
            </div>
          </div>

          <aside
            style={{
              display: "flex",
              flexDirection: "column",
              gap: t.space[3],
              position: "sticky",
              top: t.space[4],
            }}
          >
            <SectionCard title="数据状态">
              <div style={{ display: "grid", gap: t.space[3] }}>
                {statusFlags.length === 0 ? (
                  <p style={{ margin: 0, color: t.color.neutral[600], fontSize: t.fontSize[13] }}>当前没有额外状态告警。</p>
                ) : (
                  statusFlags.map((flag) => (
                    <div key={flag.id} style={{ display: "grid", gap: t.space[1] }}>
                      <StatusPill status={flag.tone} label={flag.label} />
                      <span style={{ color: t.color.neutral[600], fontSize: t.fontSize[12], lineHeight: t.lineHeight.relaxed }}>
                        {flag.detail}
                      </span>
                    </div>
                  ))
                )}
                <div style={{ color: t.color.neutral[600], fontSize: t.fontSize[12], lineHeight: t.lineHeight.relaxed }}>
                  latest quality {latestMeta?.quality_flag ?? "pending"} · linkage quality {linkageMeta?.quality_flag ?? "pending"}
                </div>
                <div style={{ color: t.color.neutral[600], fontSize: t.fontSize[12], lineHeight: t.lineHeight.relaxed }}>
                  latest generated {latestMeta?.generated_at ?? "pending"}
                </div>
                <div style={{ color: t.color.neutral[600], fontSize: t.fontSize[12], lineHeight: t.lineHeight.relaxed }}>
                  linkage generated {linkageMeta?.generated_at ?? "pending"}
                </div>
              </div>
            </SectionCard>

            <SectionCard title="宏观-债市相关性（Top）">
              <p style={{ margin: `0 0 ${t.space[3]}px`, fontSize: t.fontSize[11], color: t.color.neutral[500], lineHeight: t.lineHeight.snug }}>
                来源为联动分析返回的滚动相关性结果；这里只展示 analytical 证据，不替代估值分位。
              </p>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: t.fontSize[12] }}>
                <thead>
                  <tr style={{ color: t.color.neutral[500], textAlign: "left" }}>
                    <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>指标</th>
                    <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>corr(3M)</th>
                    <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>corr(6M)</th>
                    <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>方向</th>
                  </tr>
                </thead>
                <tbody>
                  {heatmapRows.map((row) => (
                    <tr key={row.indicator} style={{ borderTop: `1px solid ${t.color.neutral[100]}` }}>
                      <td style={{ padding: `${t.space[2]}px ${t.space[1]}px`, color: t.color.neutral[800] }}>{row.indicator}</td>
                      <td style={{ ...tabularNumsStyle, padding: `${t.space[2]}px ${t.space[1]}px`, color: t.color.neutral[900], fontWeight: 600 }}>
                        {row.current}
                      </td>
                      <td style={{ ...tabularNumsStyle, padding: `${t.space[2]}px ${t.space[1]}px`, color: t.color.neutral[600] }}>{row.mid}</td>
                      <td style={{ padding: `${t.space[2]}px ${t.space[1]}px`, color: evalColor[row.evalTone], fontWeight: 600 }}>{row.eval}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </SectionCard>
          </aside>
        </div>
      </div>
    </section>
  );
}
