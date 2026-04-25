import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { MacroBondLinkagePayload, MacroBondLinkageTopCorrelation } from "../../../api/contracts";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../../components/AsyncSection";
import { PageHeader, PageSectionLead } from "../../../components/page/PagePrimitives";
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
  buildCrossAssetClassAnalysisRows,
  buildCrossAssetEventItems,
  buildCrossAssetNcdProxyEvidence,
  buildCrossAssetStatusFlags,
  buildCrossAssetWatchList,
  buildResearchSummaryCards,
  buildTransmissionAxisRows,
  formatLinkageCorrelationDisplay,
  type CrossAssetClassAnalysisLine,
  type CrossAssetClassAnalysisRow,
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
import "./CrossAssetDriversPage.css";

const t = designTokens;

const crossAssetPanelClass = "cross-asset-drivers-page__panel";

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
        current: "不可用",
        mid: "不可用",
        eval: "Pending",
        evalTone: "warning" as const,
      },
    ];
  }

  return correlations.slice(0, 8).map((row) => {
    const indicator = `${row.series_name} -> ${row.target_family}${row.target_tenor ? ` (${row.target_tenor})` : ""}`;
    const current = formatLinkageCorrelationDisplay(row.correlation_3m);
    const mid = formatLinkageCorrelationDisplay(row.correlation_6m);
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
    <article className="cross-asset-drivers-page__mini-kpi" aria-label={kpi.label}>
      <div className="cross-asset-drivers-page__mini-kpi-main">
        <div className="cross-asset-drivers-page__mini-kpi-copy">
          <div className="cross-asset-drivers-page__mini-kpi-label">{kpi.label}</div>
          <div className="cross-asset-drivers-page__mini-kpi-value" style={tabularNumsStyle}>
            {kpi.valueLabel}
          </div>
          <div className="cross-asset-drivers-page__mini-kpi-delta" style={{ color: stroke }}>
            {kpi.changeLabel}
          </div>
          {kpi.tag ? <div className="cross-asset-drivers-page__mini-kpi-tag">{kpi.tag}</div> : null}
        </div>
        <div className="cross-asset-drivers-page__mini-kpi-chart">
          <CrossAssetSparkline values={kpi.sparkline} stroke={stroke} height={40} />
        </div>
      </div>
    </article>
  );
}

function ResearchViewsPanel({ rows }: { rows: CrossAssetResearchViewCard[] }) {
  return (
    <section data-testid="cross-asset-research-views" className={crossAssetPanelClass}>
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
      className={
        isProxyNotMatrix
          ? `${crossAssetPanelClass} cross-asset-drivers-page__panel--ncd-warn`
          : crossAssetPanelClass
      }
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
    <section data-testid="cross-asset-transmission-axes" className={crossAssetPanelClass}>
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

function AssetClassAnalysisPanel({ rows }: { rows: CrossAssetClassAnalysisRow[] }) {
  const stockRow = rows.find((row) => row.key === "stock");
  const commodityRow = rows.find((row) => row.key === "commodities");
  const optionsRow = rows.find((row) => row.key === "options");
  const readyRows = rows.filter((row) => row.status === "ready");
  const primaryRows = readyRows;
  const pendingGroups = rows
    .map((row) => ({
      row,
      lines: row.lines.filter((line) => line.status !== "ready"),
    }))
    .filter((group) => group.lines.length > 0);
  const pendingLineCount = pendingGroups.reduce((count, group) => count + group.lines.length, 0);
  const verdictParts = [
    stockRow ? `${UI.stock}${assetDirectionLabel(stockRow.direction)}` : "",
    commodityRow ? `${UI.commodity}${assetDirectionLabel(commodityRow.direction)}` : "",
    optionsRow ? `${UI.options}${optionsRow.status === "ready" ? assetDirectionLabel(optionsRow.direction) : UI.pending}` : "",
  ].filter(Boolean);

  return (
    <section data-testid="cross-asset-asset-class-analysis" className="cross-asset-class-analysis">
      <div className="cross-asset-class-analysis__header">
        <div className="cross-asset-class-analysis__eyebrow">{UI.verdictKicker}</div>
        <h2 className="cross-asset-class-analysis__title">{verdictParts.join(UI.joiner)}</h2>
        <p className="cross-asset-class-analysis__description">{UI.verdictDescription}</p>
      </div>
      <div className="cross-asset-class-analysis__body">
        <div className="cross-asset-class-analysis__primary">
          <div className="cross-asset-class-analysis__column-head">
            <span>{UI.readyJudgment}</span>
            <span>{readyRows.length}/{rows.length}</span>
          </div>
          <div className="cross-asset-class-analysis__cards">
            {primaryRows.map((row) => (
              <article
                key={row.key}
                data-testid={`cross-asset-asset-analysis-${row.key}`}
                className="cross-asset-class-analysis__card"
              >
                <div className="cross-asset-class-analysis__card-header">
                  <div>
                    <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                    <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                  </div>
                  <span
                    className={`cross-asset-class-analysis__direction cross-asset-class-analysis__direction--${directionClassName(row.direction)}`}
                  >
                    {assetDirectionLabel(row.direction)}
                  </span>
                </div>
                <p className="cross-asset-class-analysis__summary">{row.explanation}</p>
                <div className="cross-asset-class-analysis__lines">
                  {row.lines.map((line) => (
                    <div
                      key={line.key}
                      data-testid={`cross-asset-asset-analysis-${row.key}-${line.key}`}
                      className={`cross-asset-class-analysis__line${
                        line.status === "ready" ? "" : " cross-asset-class-analysis__line--pending"
                      }`}
                    >
                      <div className="cross-asset-class-analysis__line-header">
                        <span className="cross-asset-class-analysis__line-title">{line.label}</span>
                        <span className="cross-asset-class-analysis__line-status">{lineStatusLabel(line.stateLabel)}</span>
                      </div>
                      <div className="cross-asset-class-analysis__line-source" title={line.sourceLabel}>
                        <strong>{line.dataLabel}</strong>
                      </div>
                      <p className="cross-asset-class-analysis__line-explanation">{line.explanation}</p>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="cross-asset-class-analysis__pending">
          <div className="cross-asset-class-analysis__column-head">
            <span>{UI.pendingList}</span>
            <span>{pendingLineCount} {UI.items}</span>
          </div>
          {pendingGroups.map(({ row, lines }) => {
            const hasPrimaryCard = primaryRows.some((primaryRow) => primaryRow.key === row.key);
            const testIdSuffix = hasPrimaryCard ? "-pending" : "";
            return (
              <article
                key={row.key}
                data-testid={`cross-asset-asset-analysis-${row.key}${testIdSuffix}`}
                className="cross-asset-class-analysis__pending-card"
              >
                <div className="cross-asset-class-analysis__card-header">
                  <div>
                    <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                    <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                  </div>
                  <span className="cross-asset-class-analysis__direction cross-asset-class-analysis__direction--pending">
                    {UI.pending}
                  </span>
                </div>
                <p className="cross-asset-class-analysis__summary">{row.explanation}</p>
                <div className="cross-asset-class-analysis__pending-lines">
                  {lines.map((line) => (
                    <div
                      key={line.key}
                      data-testid={`cross-asset-asset-analysis-${row.key}-${line.key}${testIdSuffix}`}
                      className="cross-asset-class-analysis__pending-line"
                      title={line.sourceLabel}
                    >
                      <span>{line.label}</span>
                      <span>{assetDirectionLabel(line.direction)}</span>
                      <small>
                        {lineStatusLabel(line.stateLabel)} · {line.dataLabel}
                      </small>
                    </div>
                  ))}
                </div>
              </article>
            );
          })}
          <p className="cross-asset-class-analysis__pending-note">{UI.pendingNote}</p>
        </aside>
      </div>
    </section>
  );
}

const UI = {
  verdictKicker: "\u8de8\u8d44\u4ea7\u7ed3\u8bba",
  verdictDescription:
    "\u53cc\u6570\u636e\u6765\u6e90\u53e3\u5f84\uff1aChoice \u63a5\u5165\u7801\u4e0e Tushare/\u516c\u5171\u8865\u5145\u6e90\u5e76\u5217\u5c55\u793a\uff1b\u5df2\u63a5\u5165\u8bc1\u636e\u8fdb\u5165\u4e3b\u5224\u65ad\uff0c\u7f3a\u53e3\u6536\u655b\u5230\u5f85\u63a5\u5165\u6e05\u5355\u3002",
  readyJudgment: "\u5df2\u5f62\u6210\u5224\u65ad",
  pendingList: "\u5f85\u63a5\u5165\u6e05\u5355",
  pendingNote:
    "\u671f\u6743\u3001\u6ce2\u52a8\u7387\u548c\u90e8\u5206\u5546\u54c1\u94fe\u6761\u4ecd\u6309 pending-confirmation \u5904\u7406\uff1b\u7f3a\u53e3\u4f18\u5148\u8865 Choice \u63a5\u5165\u7801\uff0c\u4e5f\u53ef\u63a5 Tushare/\u516c\u5171\u8865\u5145\u6cbb\u7406\u6e90\uff0c\u4e0d\u7528\u76f8\u90bb\u8d44\u4ea7\u66ff\u4ee3\u3002",
  stock: "\u80a1\u7968",
  commodity: "\u5546\u54c1",
  options: "\u671f\u6743",
  pending: "\u5f85\u63a5\u5165",
  dataReady: "\u6570\u636e\u53ef\u7528",
  inputPending: "\u8f93\u5165\u5f85\u63a5\u5165",
  supportive: "\u652f\u6491",
  restrictive: "\u538b\u5236",
  neutral: "\u4e2d\u6027",
  conflicted: "\u5206\u6b67",
  joiner: "\uff0c",
  items: "\u9879",
} as const;

function analysisStatusLabel(status: CrossAssetClassAnalysisRow["status"]) {
  return status === "ready" ? UI.dataReady : UI.inputPending;
}

function lineStatusLabel(stateLabel: CrossAssetClassAnalysisLine["stateLabel"]) {
  return stateLabel;
}

function assetDirectionLabel(direction: string) {
  const normalized = direction.toLowerCase();
  if (normalized.includes("supportive")) {
    return UI.supportive;
  }
  if (normalized.includes("restrictive")) {
    return UI.restrictive;
  }
  if (normalized.includes("neutral")) {
    return UI.neutral;
  }
  if (normalized.includes("conflicted")) {
    return UI.conflicted;
  }
  if (normalized.includes("pending") || normalized.includes("definition")) {
    return UI.pending;
  }
  return direction;
}

function directionClassName(direction: string) {
  const normalized = direction.toLowerCase();
  if (normalized.includes("supportive")) {
    return "supportive";
  }
  if (normalized.includes("restrictive")) {
    return "restrictive";
  }
  if (normalized.includes("conflicted")) {
    return "conflicted";
  }
  if (normalized.includes("pending") || normalized.includes("definition")) {
    return "pending";
  }
  return "neutral";
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
  const remainder = kpis.length % 4;
  const kpiPlaceholderCount = remainder !== 0 ? 4 - remainder : 0;
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
  const assetClassAnalysisRows = useMemo(
    () =>
      buildCrossAssetClassAnalysisRows({
        kpis,
        transmissionAxes: transmissionAxisRows,
        latestMeta,
        linkageMeta,
      }),
    [kpis, latestMeta, linkageMeta, transmissionAxisRows],
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
      loadingFailures: [
        latestQuery.isError ? "choice_macro.latest" : "",
        macroBondLinkageQuery.isError ? "macro_bond_linkage.analysis" : "",
      ],
    });
  }, [
    crossAssetDataDate,
    latestMeta,
    latestQuery.isError,
    latestQuery.isLoading,
    latestSeries,
    linkageMeta,
    linkageReportDate,
    macroBondLinkageQuery.isError,
    macroBondLinkageQuery.isLoading,
  ]);

  const evalColor = {
    bull: t.color.semantic.profit,
    bear: t.color.semantic.loss,
    warning: t.color.warning[500],
  } as const;

  return (
    <section
      className="cross-asset-drivers-page"
      data-testid="cross-asset-drivers-page"
      style={{
        minHeight: "100%",
        borderRadius: t.radius.lg,
        padding: t.space[4],
      }}
    >
      <div data-testid="cross-asset-page">
        <PageHeader
          title="跨资产驱动"
          eyebrow="市场工作台"
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

        <div className="cross-asset-drivers-page__flow">
            <div className="cross-asset-drivers-page__lede">
              <PageSectionLead
                eyebrow="投资研究"
                title="研究结论先行"
                description="先看研究判断和传导主线，再决定如何解释后面的 KPI、事件和观察项。"
              />
            </div>
            <ResearchViewsPanel rows={researchViewCards} />
            <TransmissionAxesPanel rows={transmissionAxisRows} />
            <AssetClassAnalysisPanel rows={assetClassAnalysisRows} />

            <div className="cross-asset-drivers-page__lede">
              <PageSectionLead
                eyebrow="环境上下文"
                title="环境概览与 KPI"
                description="以下 KPI 为跨资产头线条目；数值与变化来自同一条宏观序列链路，与下方市场判断、传导拆解一致。"
              />
            </div>
            <div className="cross-asset-drivers-page__kpi-grid" data-testid="cross-asset-kpi-band">
              {kpis.map((kpi) => (
                <MiniKpiCard key={kpi.key} kpi={kpi} />
              ))}
              {remainder !== 0
                ? Array.from({ length: kpiPlaceholderCount }, (_, index) => (
                    <div
                      key={`kpi-placeholder-${index}`}
                      className="cross-asset-drivers-page__kpi-placeholder"
                      aria-hidden={true}
                    />
                  ))
                : null}
            </div>

            <div className="cross-asset-drivers-page__row-two">
              <section className={`${crossAssetPanelClass} cross-asset-drivers-page__panel--stack`}>
                <h2 className="cross-asset-drivers-page__panel-title">市场判断</h2>
                <div className="cross-asset-drivers-page__panel-stack">
                  <p className="cross-asset-drivers-page__panel-prose">
                    {macroBondLinkageQuery.isLoading || latestQuery.isLoading
                      ? "正在加载联动分析…"
                      : env.signal_description ?? "当前暂无可用摘要；请确认数据日期与联动分析是否已就绪。"}
                  </p>
                  <div className="cross-asset-drivers-page__chip-row">
                    <StatusPill status="normal" label={`主导因素 · ${envTags.primary}`} />
                    <StatusPill status="caution" label={`次要因素 · ${envTags.secondary}`} />
                    <StatusPill status="warning" label={`风格 · ${envTags.style}`} />
                  </div>
                </div>
              </section>

              <section className={`${crossAssetPanelClass} cross-asset-drivers-page__panel--stack`}>
                <h2 className="cross-asset-drivers-page__panel-title">宏观 — 债市相关性（Top）</h2>
                <p className="cross-asset-drivers-page__heatmap-intro">
                  使用联动分析中的滚动相关结果作参考，不替代个券估值分位或正式风险结论。
                </p>
                <table className="cross-asset-drivers-page__heatmap">
                  <thead>
                    <tr>
                      <th>指标</th>
                      <th>corr(3M)</th>
                      <th>corr(6M)</th>
                      <th>方向</th>
                    </tr>
                  </thead>
                  <tbody>
                    {heatmapRows.map((row) => (
                      <tr key={row.indicator} style={{ borderTop: `1px solid ${t.color.neutral[100]}` }}>
                        <td style={{ color: t.color.neutral[800] }}>{row.indicator}</td>
                        <td style={{ ...tabularNumsStyle, color: t.color.neutral[900], fontWeight: 600 }}>{row.current}</td>
                        <td style={{ ...tabularNumsStyle, color: t.color.neutral[600] }}>{row.mid}</td>
                        <td style={{ color: evalColor[row.evalTone], fontWeight: 600 }}>{row.eval}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </div>

            <section className={`${crossAssetPanelClass} cross-asset-drivers-page__drivers`}>
              <h2 className="cross-asset-drivers-page__panel-title">驱动拆解</h2>
              <div className="cross-asset-drivers-page__drivers-grid">
                {drivers.map((col) => {
                  const stanceStyle = driverStanceStyle(col.tone);
                  return (
                    <div key={col.title} className="cross-asset-drivers-page__driver-cell">
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
                      <ul
                        style={{
                          margin: 0,
                          paddingLeft: t.space[5],
                          color: t.color.neutral[700],
                          fontSize: t.fontSize[11],
                          lineHeight: t.lineHeight.normal,
                        }}
                      >
                        {col.bullets.map((bullet) => (
                          <li key={bullet}>{bullet}</li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </section>

            <MarketCandidateActions rows={candidateActions} />

            <NcdProxyEvidencePanel evidence={ncdProxyEvidence} isLoading={ncdFundingProxyQuery.isLoading} />

            <div className="cross-asset-drivers-page__lede">
              <PageSectionLead
                eyebrow="观察项"
                title="走势、事件与观察"
                description="完成研究判断后，再查看价格走势、事件流和观察名单，避免把短噪音误当成主结论。"
              />
            </div>
            <section className={crossAssetPanelClass}>
              <h2 className="cross-asset-drivers-page__panel-title" style={{ margin: `0 0 ${t.space[2]}px` }}>
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

            <div className="cross-asset-drivers-page__lede">
              <PageSectionLead
                eyebrow="分析结果"
                title="宏观联动与输出"
                description="以下为联动评分与组合影响的分析口径，仅供决策参考，不替代正式风控与会计口径。"
              />
            </div>
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

                  <section data-testid="cross-asset-linkage-portfolio-impact" className={crossAssetPanelClass}>
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
      </div>
    </section>
  );
}
