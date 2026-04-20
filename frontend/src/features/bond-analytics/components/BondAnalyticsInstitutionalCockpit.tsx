import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Row, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { HeadlineKpis } from "../../bond-dashboard/components/HeadlineKpis";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import {
  buildKpiValuePair,
  computeBpDelta,
  computeRelativeChangePct,
} from "../lib/bondAnalyticsHomeCalculations";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type { ActionAttributionResponse } from "../types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { formatBp, formatPct, formatWan, formatYi, toneColor } from "../utils/formatters";
import { FIELD, panelStyle } from "./bondAnalyticsCockpitTokens";

const { Text } = Typography;

const dt = designTokens;
const inkStrong = dt.color.primary[900];
const ink = dt.color.primary[800];
const muted = dt.color.neutral[700];
const sub = dt.color.neutral[600];
const borderHair = dt.color.neutral[200];
const trackBg = dt.color.primary[100];
const cnUp = dt.color.danger[500];
const cnDown = dt.color.success[600];
const infoAccent = dt.color.info[500];
const gradBar = `linear-gradient(90deg, ${dt.color.info[300]} 0%, ${infoAccent} 100%)`;
const cockpitHeroBg = `linear-gradient(135deg, ${dt.color.primary[50]} 0%, ${dt.color.info[50]} 55%, ${dt.color.primary[100]} 100%)`;

const statusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: dt.space[3],
} as const;

const compactListStyle = {
  display: "grid",
  gap: dt.space[3],
} as const;

const moduleNoteStyle = {
  color: sub,
  fontSize: dt.fontSize[12],
  lineHeight: dt.lineHeight.normal,
} as const;

const dashboardCardStyle = panelStyle(dt.color.primary[50]);

const PORTFOLIO_HEADLINES_HOME_NOTE = "组合信用摘要暂未返回，首页先依据仪表盘指标判断方向。";
const PORTFOLIO_HEADLINES_STRUCTURE_NOTE = "组合信用摘要暂未返回，资产结构稍后补齐。";
const PORTFOLIO_HEADLINES_CREDIT_NOTE = "组合信用摘要暂未返回，债券只数、集中度和 DV01 稍后补齐。";
const TOP_HOLDINGS_HOME_NOTE = "前十大持仓暂未返回，首页先保留组合规模与浮盈快照。";
const TOP_HOLDINGS_RATING_NOTE = "持仓明细暂未返回，评级分布稍后补齐。";

function isFiniteNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

function numOr(raw: Numeric | null | undefined): number {
  const n = bondNumericRaw(raw);
  return Number.isFinite(n) ? n : Number.NaN;
}

function relRatioLine(
  label: string,
  prevRaw: number | null | undefined,
  curRaw: number | null | undefined,
): string | null {
  const pct = computeRelativeChangePct(curRaw, prevRaw);
  if (!isFiniteNumber(pct)) return null;
  return `${label} ${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function formatCompactValue(raw: Numeric | null | undefined, kind: "pct" | "bp" | "yi" | "wan") {
  if (!raw) return "—";
  if (kind === "pct") return formatPct(raw);
  if (kind === "bp") return formatBp(raw);
  if (kind === "yi") return formatYi(raw);
  return formatWan(raw);
}

function formatNumericString(raw: string | number | null | undefined) {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return String(raw);
  }
  return parsed.toLocaleString("zh-CN");
}

function formatSignedPct(pct: number | null): string {
  if (!isFiniteNumber(pct)) {
    return "—";
  }
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function buildCockpitConclusion(args: {
  duration: number;
  creditWeight: number;
  spreadMedian: number;
}) {
  const { duration, creditWeight, spreadMedian } = args;

  if (Number.isFinite(duration) && duration >= 3.8) {
    return {
      title: "当前结论",
      body: "久期敞口仍是首页第一观察位。",
      detail: `加权久期 ${duration.toFixed(2)} 年，先看期限结构和动作归因，再决定是否切到 KRD 下钻。`,
    };
  }

  if (Number.isFinite(creditWeight) && creditWeight >= 0.35) {
    return {
      title: "当前结论",
      body: "信用敞口偏重，需优先盯利差与集中度。",
      detail: `信用权重 ${(creditWeight * 100).toFixed(1)}%，建议先复核信用利差和行业集中暴露。`,
    };
  }

  const spreadBp = Number.isFinite(spreadMedian)
    ? (spreadMedian < 0.5 ? spreadMedian * 10000 : spreadMedian)
    : Number.NaN;

  return {
    title: "当前结论",
    body: "收益率和信用利差都处在可读但不宽松的区间。",
    detail: `加权久期 ${Number.isFinite(duration) ? `${duration.toFixed(2)} 年` : "—"}，信用利差中位数 ${
      Number.isFinite(spreadBp) ? `${spreadBp.toFixed(1)} bp` : "—"
    }。`,
  };
}

function DashboardMetric({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <div
      style={{
        borderRadius: dt.radius.lg,
        border: `1px solid ${dt.color.neutral[200]}`,
        background: dt.color.primary[50],
        padding: `${dt.space[3]}px ${dt.space[3] + 2}px`,
        display: "grid",
        gap: dt.space[1] + 1,
      }}
    >
      <div style={{ ...FIELD, marginBottom: 0 }}>{label}</div>
      <div
        style={{
          fontSize: dt.fontSize[20],
          fontWeight: 700,
          letterSpacing: "-0.03em",
          color: tone === "positive" ? cnUp : tone === "negative" ? cnDown : inkStrong,
          ...tabularNumsStyle,
        }}
      >
        {value}
      </div>
      <div style={{ color: muted, fontSize: dt.fontSize[12], lineHeight: dt.lineHeight.snug }}>
        {detail}
      </div>
    </div>
  );
}

function SignalCell({
  label,
  summary,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  summary: string;
  value: string;
  detail: string;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <div
      style={{
        borderRadius: dt.radius.lg,
        border: `1px solid ${dt.color.neutral[200]}`,
        background: dt.color.primary[50],
        padding: `${dt.space[3] + 2}px ${dt.space[3] + 2}px ${dt.space[3]}px`,
        display: "grid",
        gap: dt.space[2],
      }}
    >
      <div style={{ ...FIELD, marginBottom: 0 }}>{label}</div>
      <div
        style={{
          color: tone === "positive" ? cnUp : tone === "negative" ? cnDown : ink,
          fontSize: dt.fontSize[18],
          fontWeight: 800,
          lineHeight: dt.lineHeight.tight,
          letterSpacing: "-0.03em",
          ...tabularNumsStyle,
        }}
      >
        {summary}
      </div>
      <div style={{ color: muted, fontSize: dt.fontSize[12], fontWeight: 700 }}>{value}</div>
      <div style={{ color: sub, fontSize: dt.fontSize[12], lineHeight: dt.lineHeight.snug }}>{detail}</div>
    </div>
  );
}

function scoreBarRows(
  items: Array<{ key: string; label: string; value: number; caption: string; color: string }>,
) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  return (
    <div style={compactListStyle}>
      {items.map((item) => (
        <div key={item.key} style={{ display: "grid", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: inkStrong, fontWeight: 700, fontSize: dt.fontSize[13] }}>{item.label}</span>
            <span style={{ color: item.color, fontWeight: 700, fontSize: dt.fontSize[12] }}>{item.caption}</span>
          </div>
          <div style={{ width: "100%", height: 7, borderRadius: 999, background: trackBg, overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.max(14, (Math.abs(item.value) / maxValue) * 100)}%`,
                height: "100%",
                borderRadius: 999,
                background: item.color,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function buildSummaryNarrative(args: {
  duration: number;
  creditWeight: number;
  spreadMedian: number;
  marketValueText: string;
}) {
  const parts: string[] = [];

  if (args.marketValueText !== "—") {
    parts.push(`当前组合规模约 ${args.marketValueText}`);
  }
  if (Number.isFinite(args.duration)) {
    parts.push(`久期 ${args.duration.toFixed(2)} 年`);
  }
  if (Number.isFinite(args.creditWeight)) {
    parts.push(`信用权重 ${(args.creditWeight * 100).toFixed(1)}%`);
  }
  if (Number.isFinite(args.spreadMedian)) {
    const spreadBp = args.spreadMedian < 0.5 ? args.spreadMedian * 10000 : args.spreadMedian;
    parts.push(`信用利差中位数 ${spreadBp.toFixed(1)} bp`);
  }

  return parts.length > 0 ? `${parts.join("，")}。当前首页先给判断，再进入细项下钻。` : "当前首页先给判断，再进入细项下钻。";
}

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
  topAnomalies?: string[];
  actionAttribution?: ActionAttributionResponse | null;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
  topAnomalies = [],
  actionAttribution = null,
  onOpenModuleDetail,
}: BondAnalyticsInstitutionalCockpitProps) {
  const client = useApiClient();
  const dashboardDatesQuery = useQuery({
    queryKey: ["bond-analytics-institutional", "dashboard-dates", client.mode],
    queryFn: () => client.getBondDashboardDates(),
    enabled: Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });
  const dashboardReportDate = useMemo(() => {
    if (!reportDate) {
      return "";
    }

    if (!dashboardDatesQuery.data && !dashboardDatesQuery.isError) {
      return "";
    }

    const availableDates = dashboardDatesQuery.data?.result.report_dates ?? [];
    if (availableDates.length > 0) {
      return availableDates.includes(reportDate) ? reportDate : availableDates[0];
    }

    return reportDate;
  }, [dashboardDatesQuery.data, dashboardDatesQuery.isError, reportDate]);
  const isDashboardDateFallback =
    Boolean(reportDate) &&
    Boolean(dashboardReportDate) &&
    dashboardReportDate !== reportDate;

  const [headlineQ, spreadQ, maturityQ, holdingsQ, portfolioHlQ] = useQueries({
    queries: [
      {
        queryKey: ["bond-analytics-institutional", "headline", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardHeadlineKpis(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "spread", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardSpreadAnalysis(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "maturity", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardMaturityStructure(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "holdings", client.mode, reportDate],
        queryFn: () => client.getBondAnalyticsTopHoldings(reportDate, 10),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "portfolio-hl", client.mode, reportDate],
        queryFn: () => client.getBondAnalyticsPortfolioHeadlines(reportDate),
        enabled: Boolean(reportDate),
      },
    ],
  });

  const headline = headlineQ.data?.result;
  const portfolioHl = portfolioHlQ.data?.result;
  const err = headlineQ.isError ? ((headlineQ.error as Error)?.message ?? "驾驶舱数据加载失败") : null;
  const portfolioHeadlinesUnavailable = portfolioHlQ.isError;
  const topHoldingsUnavailable = holdingsQ.isError;

  const dur = headline ? numOr(headline.kpis.weighted_duration) : Number.NaN;
  const creditWeight = portfolioHl ? numOr(portfolioHl.credit_weight) : Number.NaN;
  const spreadMedian = headline ? numOr(headline.kpis.credit_spread_median) : Number.NaN;
  const conclusion = buildCockpitConclusion({
    duration: dur,
    creditWeight,
    spreadMedian,
  });

  const k = headline?.kpis;
  const p = headline?.prev_kpis;
  const marketValuePair = buildKpiValuePair(headline ?? null, "total_market_value");
  const unrealizedPnlPair = buildKpiValuePair(headline ?? null, "unrealized_pnl");
  const ytmPair = buildKpiValuePair(headline ?? null, "weighted_ytm");
  const spreadPair = buildKpiValuePair(headline ?? null, "credit_spread_median");
  const marketValueMomPct = computeRelativeChangePct(marketValuePair.current, marketValuePair.previous);
  const unrealizedPnlMomPct = computeRelativeChangePct(unrealizedPnlPair.current, unrealizedPnlPair.previous);
  const spreadMomPct = computeRelativeChangePct(spreadPair.current, spreadPair.previous);

  const focusItems = useMemo(() => {
    const merged = [
      ...topAnomalies,
      ...(portfolioHl?.warnings ?? []),
      ...(actionAttribution?.warnings ?? []),
    ]
      .map((item) => item.trim())
      .filter(Boolean);

    const unique = Array.from(new Set(merged));
    if (unique.length > 0) {
      return unique.slice(0, 4);
    }

    const fallback = [
      k ? `组合规模 ${formatYi(k.total_market_value)}，浮盈 ${formatYi(k.unrealized_pnl)}。` : "",
      portfolioHl ? `信用权重 ${formatPct(portfolioHl.credit_weight)}，债券只数 ${portfolioHl.bond_count}。` : "",
      actionAttribution ? `本期动作 ${actionAttribution.total_actions} 笔，贡献 ${formatWan(actionAttribution.total_pnl_from_actions)}。` : "",
    ]
      .map((item) => item.trim())
      .filter(Boolean);

    return fallback.length > 0 ? fallback.slice(0, 3) : ["当前未返回额外异常或治理提示。"];
  }, [actionAttribution, k, portfolioHl, topAnomalies]);

  const maturityItems = useMemo(() => {
    return [...(maturityQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 4)
      .map((item) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: numOr(item.total_market_value),
        caption: formatYi(item.total_market_value),
        color: dt.color.success[500],
      }));
  }, [maturityQ.data]);

  const spreadItems = useMemo(() => {
    return [...(spreadQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 4);
  }, [spreadQ.data]);

  const leadMaturity = maturityItems[0];
  const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
  const topHoldings = (holdingsQ.data?.result.items ?? []).slice(0, 10);
  const ratingDistribution = useMemo(() => {
    const buckets = new Map<string, { count: number; faceValue: number }>();
    for (const item of holdingsQ.data?.result.items ?? []) {
      const key = item.rating?.trim() || "Unrated";
      const next = buckets.get(key) ?? { count: 0, faceValue: 0 };
      next.count += 1;
      next.faceValue += bondNumericRaw(item.face_value);
      buckets.set(key, next);
    }
    return Array.from(buckets.entries())
      .map(([rating, stats]) => ({
        rating,
        count: stats.count,
        faceValue: stats.faceValue,
      }))
      .sort((left, right) => right.faceValue - left.faceValue)
      .slice(0, 6);
  }, [holdingsQ.data?.result.items]);
  const actionTypeRows = (actionAttribution?.by_action_type ?? []).slice(0, 4);
  const totalActionPnl = bondNumericRaw(actionAttribution?.total_pnl_from_actions ?? null);
  const ytmDeltaBp = computeBpDelta(k?.weighted_ytm ?? null, p?.weighted_ytm ?? null);
  const spreadDeltaBp = computeBpDelta(k?.credit_spread_median ?? null, p?.credit_spread_median ?? null);

  return (
    <section data-testid="bond-analysis-phase3-cockpit" style={{ display: "grid", gap: dt.space[3] }}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <Card
        size="small"
        data-testid="bond-analysis-asset-momentum"
        title="资产变动与首屏 KPI"
        style={dashboardCardStyle}
        styles={{ header: { minHeight: 44 }, body: { paddingBlock: 12 } }}
      >
        <div data-testid="bond-analysis-kpi-ribbon">
          <HeadlineKpis data={headline} loading={headlineQ.isPending} />
        </div>
        {isDashboardDateFallback ? (
          <div style={{ marginTop: dt.space[2] + 2, fontSize: dt.fontSize[11], color: sub, lineHeight: dt.lineHeight.normal }}>
            仪表盘快照使用 {dashboardReportDate}
          </div>
        ) : null}
        <div style={{ marginTop: dt.space[2] + 2, fontSize: dt.fontSize[11], color: sub, lineHeight: dt.lineHeight.normal }}>
          指标与债券驾驶舱首屏一致；资产变动环比（规模 {formatSignedPct(marketValueMomPct)} / 浮盈{" "}
{formatSignedPct(unrealizedPnlMomPct)}）与利率/利差变化（{isFiniteNumber(ytmDeltaBp) ? `${ytmDeltaBp.toFixed(1)}bp` : "—"} /{" "}
{isFiniteNumber(spreadDeltaBp) ? `${spreadDeltaBp.toFixed(1)}bp` : "—"}）均按 raw 数值计算。切换上方「报表日期」可更新全页对比基准。
        </div>
      </Card>

      <Row gutter={[dt.space[3], dt.space[3]]}>
        <Col xs={24} xl={16}>
          <Card
            size="small"
            data-testid="bond-analysis-cockpit-conclusion"
            style={panelStyle(cockpitHeroBg)}
            styles={{ body: { padding: dt.space[4] } }}
          >
            <div style={{ display: "grid", gap: dt.space[3] + 2 }}>
              <div style={{ display: "grid", gap: dt.space[2] }}>
                <div style={FIELD}>市场状态（一句话）</div>
                <div
                  style={{
                    fontSize: dt.fontSize[30],
                    fontWeight: 800,
                    lineHeight: 1.18,
                    letterSpacing: "-0.04em",
                    color: inkStrong,
                  }}
                >
                  {conclusion.body}
                </div>
                <Text type="secondary">{conclusion.detail}</Text>
              </div>

              <div style={statusGridStyle}>
                <SignalCell
                  label="利率"
                  summary={isFiniteNumber(ytmDeltaBp) ? (ytmDeltaBp <= 0 ? "下行未尽" : "短端回弹") : "方向待确认"}
                  value={k ? `${formatPct(k.weighted_ytm)} · ${isFiniteNumber(ytmDeltaBp) ? `${ytmDeltaBp >= 0 ? "+" : ""}${ytmDeltaBp.toFixed(1)}bp` : "—"}` : "—"}
                  detail={relRatioLine("较上期", ytmPair.previous, ytmPair.current) ?? "关注收益率方向与波动。"}
                  tone={isFiniteNumber(ytmDeltaBp) ? (ytmDeltaBp <= 0 ? "negative" : "positive") : "default"}
                />
                <SignalCell
                  label="曲线"
                  summary={leadMaturity ? `${leadMaturity.label} 最集中` : "期限待确认"}
                  value={leadMaturity ? leadMaturity.caption : Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—"}
                  detail="先看最重期限桶，再决定是否切到 KRD 和收益率曲线下钻。"
                />
                <SignalCell
                  label="信用"
                  summary={Number.isFinite(creditWeight) && creditWeight >= 0.35 ? "压缩尾段" : "压缩可读"}
                  value={
                    Number.isFinite(spreadMedian)
                      ? `${(spreadMedian < 0.5 ? spreadMedian * 10000 : spreadMedian).toFixed(1)} bp · 权重 ${portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"}`
                      : "—"
                  }
                  detail={
                    portfolioHeadlinesUnavailable
                      ? PORTFOLIO_HEADLINES_HOME_NOTE
                      : Number.isFinite(spreadMomPct)
                      ? `信用权重 ${portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"} · 较上期 ${formatSignedPct(spreadMomPct)}`
                      : portfolioHl
                        ? `信用权重 ${formatPct(portfolioHl.credit_weight)}`
                        : "关注信用权重与利差位置。"
                  }
                />
                <SignalCell
                  label="资金"
                  summary={k && numOr(k.unrealized_pnl) >= 0 ? "收益垫仍在" : "收益垫转弱"}
                  value={k ? `${formatYi(k.total_market_value)} · 浮盈 ${formatYi(k.unrealized_pnl)}` : "—"}
                  detail={
                    Number.isFinite(unrealizedPnlMomPct)
                      ? `浮盈较上期 ${formatSignedPct(unrealizedPnlMomPct)}，结合规模变化 ${formatSignedPct(marketValueMomPct)} 判断仓位防守空间。`
                      : "用组合规模和浮盈变化判断当前仓位的防守空间。"
                  }
                  tone={k && numOr(k.unrealized_pnl) !== 0 ? (numOr(k.unrealized_pnl) > 0 ? "positive" : "negative") : "default"}
                />
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card
            size="small"
            title="今日关注"
            data-testid="bond-analysis-today-focus"
            style={dashboardCardStyle}
            styles={{ body: { padding: 14 } }}
          >
            <div style={compactListStyle}>
              {focusItems.map((item, index) => (
                <div
                  key={`${item}-${index}`}
                  style={{
                    display: "flex",
                    gap: dt.space[2] + 2,
                    alignItems: "flex-start",
                    paddingBottom: dt.space[2] + 2,
                    borderBottom: `1px solid ${borderHair}`,
                  }}
                >
                  <span style={{ color: infoAccent, fontSize: dt.fontSize[18], lineHeight: 1 }}>•</span>
                  <span style={{ color: ink, fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed }}>{item}</span>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[dt.space[3], dt.space[3]]}>
        <Col xs={24} lg={14}>
          <Card
            size="small"
            title="组合摘要"
            data-testid="bond-analysis-summary-card"
            style={dashboardCardStyle}
            styles={{ body: { padding: 14 } }}
          >
            <div style={{ display: "grid", gap: 10 }}>
              <div style={{ color: ink, fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed }}>
                {buildSummaryNarrative({
                  duration: dur,
                  creditWeight,
                  spreadMedian,
                  marketValueText: k ? formatYi(k.total_market_value) : "—",
                })}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: dt.space[2] }}>
                <span
                  style={{
                    padding: `${dt.space[1]}px ${dt.space[2] + 2}px`,
                    borderRadius: 999,
                    background: dt.color.info[50],
                    color: dt.color.info[700],
                    fontSize: dt.fontSize[12],
                    fontWeight: 700,
                  }}
                >
                  久期 {Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—"}
                </span>
                <span
                  style={{
                    padding: `${dt.space[1]}px ${dt.space[2] + 2}px`,
                    borderRadius: 999,
                    background: dt.color.success[50],
                    color: dt.color.success[700],
                    fontSize: dt.fontSize[12],
                    fontWeight: 700,
                  }}
                >
                  信用 {portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"}
                </span>
                <span
                  style={{
                    padding: `${dt.space[1]}px ${dt.space[2] + 2}px`,
                    borderRadius: 999,
                    background: dt.color.warning[50],
                    color: dt.color.warning[700],
                    fontSize: dt.fontSize[12],
                    fontWeight: 700,
                  }}
                >
                  利差 {k ? formatCompactValue(k.credit_spread_median, "bp") : "—"}
                </span>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            size="small"
            title="债券资产结构"
            extra={
              <Button
                size="small"
                type="text"
                data-testid="bond-analysis-home-open-portfolio-headlines"
                onClick={() => onOpenModuleDetail?.("portfolio-headlines")}
              >
                查看组合详情
              </Button>
            }
            data-testid="bond-analysis-asset-structure"
            style={dashboardCardStyle}
            styles={{ body: { padding: 14 } }}
          >
            {assetClassItems.length > 0 ? (
              <div style={compactListStyle}>
                {assetClassItems.map((item) => (
                  <div key={item.asset_class} style={{ display: "grid", gap: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <span style={{ color: inkStrong, fontWeight: 700, fontSize: dt.fontSize[13] }}>{item.asset_class}</span>
                      <span style={{ color: muted, fontSize: dt.fontSize[12] }}>{item.weight.display}</span>
                    </div>
                    <div style={{ width: "100%", height: 7, borderRadius: 999, background: trackBg, overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${Math.max(10, Math.min(100, bondNumericRaw(item.weight) * 100))}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: gradBar,
                        }}
                      />
                    </div>
                    <div style={{ color: sub, fontSize: dt.fontSize[12] }}>
                      市值 {formatYi(item.market_value)} · 久期 {item.duration.display}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Text type="secondary">
                {portfolioHeadlinesUnavailable ? PORTFOLIO_HEADLINES_STRUCTURE_NOTE : "暂无资产结构"}
              </Text>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[dt.space[3], dt.space[3]]}>
        <Col xs={24} lg={8}>
          <Card size="small" title="收益率与久期分布" style={dashboardCardStyle} styles={{ body: { padding: 14 } }}>
            <div style={compactListStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                <span style={{ color: muted, fontSize: dt.fontSize[12] }}>加权收益率</span>
                <span style={{ color: inkStrong, fontWeight: 700, ...tabularNumsStyle }}>{k ? formatPct(k.weighted_ytm) : "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                <span style={{ color: muted, fontSize: dt.fontSize[12] }}>加权久期</span>
                <span style={{ color: inkStrong, fontWeight: 700, ...tabularNumsStyle }}>
                  {Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—"}
                </span>
              </div>
              {maturityItems.length > 0 ? scoreBarRows(maturityItems) : <Text type="secondary">暂无期限结构</Text>}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="利差分析（中位数，bp）" style={dashboardCardStyle} styles={{ body: { padding: 14 } }}>
            <div style={compactListStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                <span style={{ color: muted, fontSize: dt.fontSize[12] }}>信用权重</span>
                <span style={{ color: inkStrong, fontWeight: 700, ...tabularNumsStyle }}>
                  {portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                <span style={{ color: muted, fontSize: dt.fontSize[12] }}>利差中位数</span>
                <span style={{ color: inkStrong, fontWeight: 700, ...tabularNumsStyle }}>
                  {k ? formatCompactValue(k.credit_spread_median, "bp") : "—"}
                </span>
              </div>
              {spreadItems.length > 0 ? (
                <div style={compactListStyle}>
                  {spreadItems.map((item) => (
                    <div
                      key={item.bond_type}
                      style={{ display: "grid", gap: dt.space[1], paddingBottom: dt.space[2] + 2, borderBottom: `1px solid ${borderHair}` }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                        <span style={{ color: inkStrong, fontWeight: 700, fontSize: dt.fontSize[13] }}>{item.bond_type}</span>
                        <span style={{ color: muted, fontSize: dt.fontSize[12], ...tabularNumsStyle }}>{formatYi(item.total_market_value)}</span>
                      </div>
                      <div style={{ color: sub, fontSize: dt.fontSize[12] }}>
                        中位收益率 {item.median_yield ? formatPct(item.median_yield) : "—"} · 只数 {item.bond_count}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Text type="secondary">暂无利差分布</Text>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            size="small"
            title="持仓明细（前10）"
            extra={
              <Button
                size="small"
                type="text"
                data-testid="bond-analysis-home-open-top-holdings"
                onClick={() => onOpenModuleDetail?.("top-holdings")}
              >
                查看完整持仓
              </Button>
            }
            style={dashboardCardStyle}
            styles={{ body: { padding: 14 } }}
          >
            <div style={compactListStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                <span style={{ color: muted, fontSize: dt.fontSize[12] }}>组合市值</span>
                <span style={{ color: inkStrong, fontWeight: 700, ...tabularNumsStyle }}>{k ? formatYi(k.total_market_value) : "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                <span style={{ color: muted, fontSize: dt.fontSize[12] }}>浮动盈亏</span>
                <span
                  style={{
                    color: k ? toneColor(numOr(k.unrealized_pnl)) : inkStrong,
                    fontWeight: 700,
                    ...tabularNumsStyle,
                  }}
                >
                  {k ? formatYi(k.unrealized_pnl) : "—"}
                </span>
              </div>
              {topHoldings.length > 0 ? (
                <div style={compactListStyle}>
                  {topHoldings.map((item) => (
                    <div
                      key={item.instrument_code}
                      style={{ display: "grid", gap: dt.space[1], paddingBottom: dt.space[2] + 2, borderBottom: `1px solid ${borderHair}` }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                        <span style={{ color: inkStrong, fontWeight: 700, fontSize: dt.fontSize[13] }}>{item.instrument_name}</span>
                        <span style={{ color: muted, fontSize: dt.fontSize[12], ...tabularNumsStyle }}>{formatWan(item.face_value)}</span>
                      </div>
                      <div style={{ color: sub, fontSize: dt.fontSize[12] }}>
                        收益率 {formatPct(item.ytm)} · 久期 {item.modified_duration.display} · {item.rating}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Text type="secondary">
                  {topHoldingsUnavailable ? TOP_HOLDINGS_HOME_NOTE : "暂无持仓明细"}
                </Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[dt.space[3], dt.space[3]]}>
        <Col xs={24} lg={8}>
          <Card size="small" title="信用等级分布" style={dashboardCardStyle} styles={{ body: { padding: 14 } }}>
            <div style={compactListStyle}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: dt.space[2] + 2 }}>
                <DashboardMetric
                  label="债券只数"
                  value={portfolioHl ? formatNumericString(portfolioHl.bond_count) : "—"}
                  detail="portfolio headlines"
                />
                <DashboardMetric
                  label="Top5 集中度"
                  value={portfolioHl ? formatPct(portfolioHl.issuer_top5_weight) : "—"}
                  detail="发行人权重"
                />
                <DashboardMetric
                  label="信用权重"
                  value={portfolioHl ? formatPct(portfolioHl.credit_weight) : "—"}
                  detail="信用债市值占比"
                />
                <DashboardMetric
                  label="DV01"
                  value={portfolioHl ? formatWan(portfolioHl.total_dv01) : "—"}
                  detail="组合利率敏感度"
                />
              </div>
              {portfolioHeadlinesUnavailable ? (
                <div style={moduleNoteStyle}>{PORTFOLIO_HEADLINES_CREDIT_NOTE}</div>
              ) : null}
              {topHoldingsUnavailable ? (
                <div style={moduleNoteStyle}>{TOP_HOLDINGS_RATING_NOTE}</div>
              ) : ratingDistribution.length > 0 ? (
                <div style={compactListStyle}>
                  {ratingDistribution.map((item) => (
                    <div key={item.rating} style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3] }}>
                      <span style={{ color: sub, fontSize: dt.fontSize[12] }}>{item.rating}</span>
                      <span style={{ color: inkStrong, fontWeight: 700, fontSize: dt.fontSize[12], ...tabularNumsStyle }}>
                        {item.count} bonds · {formatWan(item.faceValue)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="组合收益归因（本期）" style={dashboardCardStyle} styles={{ body: { padding: 14 } }}>
            <div style={compactListStyle}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: dt.space[2] + 2 }}>
                <DashboardMetric
                  label="动作数量"
                  value={actionAttribution ? formatNumericString(actionAttribution.total_actions) : "—"}
                  detail="action attribution"
                />
                <DashboardMetric
                  label="动作贡献"
                  value={actionAttribution ? formatWan(actionAttribution.total_pnl_from_actions) : "—"}
                  detail="经济口径损益"
                  tone={Number.isFinite(totalActionPnl) && totalActionPnl !== 0 ? (totalActionPnl > 0 ? "positive" : "negative") : "default"}
                />
              </div>
              {actionTypeRows.length > 0 ? (
                <div style={compactListStyle}>
                  {actionTypeRows.map((item) => {
                    const pnl = bondNumericRaw(item.total_pnl_economic);
                    return (
                      <div
                        key={item.action_type}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: dt.space[3],
                          paddingBottom: dt.space[2] + 2,
                          borderBottom: `1px solid ${borderHair}`,
                        }}
                      >
                        <span style={{ color: inkStrong, fontWeight: 700, fontSize: dt.fontSize[13] }}>{item.action_type_name}</span>
                        <span style={{ color: toneColor(pnl), fontWeight: 700, fontSize: dt.fontSize[12], ...tabularNumsStyle }}>
                          {formatWan(item.total_pnl_economic)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <Text type="secondary">当前没有可展示的动作类型汇总。</Text>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title="决策事项" style={dashboardCardStyle} styles={{ body: { padding: 14 } }}>
            <div style={compactListStyle}>
              <div style={{ color: muted, fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed }}>
                首页只给动作方向，不在这里塞完整模块。需要证据时，直接进入对应 drill。
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, color: ink, lineHeight: dt.lineHeight.relaxed }}>
                <li>{Number.isFinite(dur) && dur >= 3.8 ? "先看久期和期限结构，再决定是否做久期调整。" : "先看收益率分布和期限桶，确认久期是否仍在舒适区。"}</li>
                <li>{Number.isFinite(creditWeight) && creditWeight >= 0.35 ? "信用权重偏高，优先复核利差和行业集中度。" : "信用权重可控，但仍需关注利差收窄后的回撤风险。"}</li>
                <li>{actionAttribution ? `本期动作 ${actionAttribution.total_actions} 笔，可先看动作归因再下钻明细。` : "动作归因未返回时，不在首页补造操作建议。 "}</li>
              </ul>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                <Button
                  size="small"
                  type="text"
                  data-testid="bond-analysis-home-open-action-attribution"
                  onClick={() => onOpenModuleDetail?.("action-attribution")}
                >
                  打开动作归因
                </Button>
                <Button
                  size="small"
                  type="text"
                  data-testid="bond-analysis-home-open-return-decomposition"
                  onClick={() => onOpenModuleDetail?.("return-decomposition")}
                >
                  打开收益拆解
                </Button>
                <Button
                  size="small"
                  type="text"
                  data-testid="bond-analysis-home-open-credit-spread"
                  onClick={() => onOpenModuleDetail?.("credit-spread")}
                >
                  打开信用利差
                </Button>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
