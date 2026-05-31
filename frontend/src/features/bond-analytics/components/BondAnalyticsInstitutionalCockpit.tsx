import { useMemo, type CSSProperties } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import type { AssetStructureItem, BondTopHoldingItem, Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import {
  buildKpiValuePair,
  computeRelativeChangePct,
} from "../lib/bondAnalyticsHomeCalculations";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type { ActionAttributionResponse } from "../types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { formatPct, formatWan, formatYi } from "../utils/formatters";
import { FIELD, panelStyle } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const { Text } = Typography;

const dt = designTokens;
const inkStrong = dt.color.primary[900];
const muted = dt.color.neutral[700];
const sub = dt.color.neutral[600];
const infoAccent = dt.color.info[500];
const gradBar = `linear-gradient(90deg, ${dt.color.info[300]} 0%, ${infoAccent} 100%)`;
const restrainedShadow = "0 8px 18px rgba(22, 35, 46, 0.05)";
const dashboardCardStyle: CSSProperties = {
  ...panelStyle(displayTokens.surface.section),
  borderRadius: dt.radius.lg,
  boxShadow: restrainedShadow,
};
const cardBodyStyle = { padding: 14 } as const;
const sectionTitleWrapStyle = {
  display: "grid",
  gap: 2,
} as const;
const sectionTitleStyle = {
  color: inkStrong,
  fontSize: dt.fontSize[16],
  fontWeight: 700,
  lineHeight: dt.lineHeight.tight,
} as const;
const moduleNoteStyle = {
  color: sub,
  fontSize: dt.fontSize[12],
  lineHeight: dt.lineHeight.normal,
} as const;

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

function SectionCardTitle({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div style={sectionTitleWrapStyle}>
      <div style={{ ...FIELD, marginBottom: 0 }}>{eyebrow}</div>
      <div style={sectionTitleStyle}>{title}</div>
    </div>
  );
}

function ReferenceKpiTile({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <div className={styles.referenceKpiTile}>
      <div className={styles.referenceKpiLabel}>{label}</div>
      <div
        className={styles.referenceKpiValue}
        data-tone={tone}
        style={tabularNumsStyle}
      >
        {value}
      </div>
      <div className={styles.referenceKpiDetail}>{detail}</div>
    </div>
  );
}

function ReferenceKpiDonutTile({
  label,
  value,
  detail,
  ratio,
}: {
  label: string;
  value: string;
  detail: string;
  ratio: number | null;
}) {
  const pct = ratio !== null && Number.isFinite(ratio) ? Math.min(Math.max(ratio, 0), 1) * 100 : 0;
  const gradient =
    ratio !== null && Number.isFinite(ratio)
      ? `conic-gradient(${dt.color.primary[700]} 0 ${pct.toFixed(2)}%, ${dt.color.neutral[100]} ${pct.toFixed(2)}% 100%)`
      : `conic-gradient(${dt.color.neutral[200]} 0 100%)`;

  return (
    <div className={styles.referenceKpiDonutTile}>
      <div>
        <div className={styles.referenceKpiLabel}>{label}</div>
        <div className={styles.referenceKpiValue} style={tabularNumsStyle}>
          {value}
        </div>
        <div className={styles.referenceKpiDetail}>{detail}</div>
      </div>
      <div className={styles.kpiMiniDonut} style={{ "--donut": gradient } as CSSProperties}>
        <span>{value}</span>
      </div>
    </div>
  );
}

function ProgressStack({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <Text type="secondary">{emptyText}</Text>;
  }

  return (
    <div className={styles.progressList}>
      {items.map((item) => (
        <div key={item.key} className={styles.referenceProgressRow}>
          <div className={styles.progressHeader}>
            <span>{item.label}</span>
            <span style={tabularNumsStyle}>{item.caption}</span>
          </div>
          <div className={styles.referenceProgressTrack}>
            <div
              className={styles.referenceProgressBar}
              style={{
                width: `${Math.max(8, (Math.abs(item.value) / maxValue) * 100)}%`,
                background: item.color ?? gradBar,
              }}
            />
          </div>
          {item.detail ? <div className={styles.progressDetail}>{item.detail}</div> : null}
        </div>
      ))}
    </div>
  );
}

function PendingReadModelPanel({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className={styles.pendingReadModelPanel}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function MaturityColumnChart({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const maxValue = Math.max(...items.map((item) => Math.abs(item.value)), 1);

  if (items.length === 0) {
    return <Text type="secondary">{emptyText}</Text>;
  }

  return (
    <div className={styles.maturityChart}>
      {items.slice(0, 7).map((item) => (
        <div key={item.key} className={styles.maturityColumn}>
          <span>{item.caption}</span>
          <div
            style={{
              height: `${Math.max(10, (Math.abs(item.value) / maxValue) * 118)}px`,
              background: item.color ?? gradBar,
            }}
          />
          <small>{item.label}</small>
        </div>
      ))}
    </div>
  );
}

function buildDonutGradient(items: Array<{ value: number; color?: string }>) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  if (total <= 0) {
    return "conic-gradient(var(--moss-color-neutral-200) 0 100%)";
  }

  let cursor = 0;
  const stops = items.map((item, index) => {
    const start = cursor;
    cursor += (Math.max(item.value, 0) / total) * 100;
    const color = item.color ?? [dt.color.primary[600], dt.color.info[500], dt.color.success[500], dt.color.warning[500]][index % 4];
    return `${color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
  });

  return `conic-gradient(${stops.join(", ")})`;
}

function DistributionDonut({
  items,
  center,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    detail?: string;
    color?: string;
  }>;
  center: string;
  emptyText: string;
}) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  if (items.length === 0 || total <= 0) {
    return <Text type="secondary">{emptyText}</Text>;
  }

  return (
    <div className={styles.referenceDonutPanel}>
      <div className={styles.referenceDonutLegend}>
        {items.slice(0, 5).map((item) => (
          <div key={item.key} className={styles.referenceDonutLegendRow}>
            <span style={{ background: item.color ?? dt.color.primary[500] }} />
            <strong>{item.label}</strong>
            <em style={tabularNumsStyle}>{item.caption}</em>
          </div>
        ))}
      </div>
      <div
        className={styles.referenceDonut}
        style={{ "--donut": buildDonutGradient(items) } as CSSProperties}
      >
        <span>{center}</span>
      </div>
    </div>
  );
}

function HoldingRows({
  holdings,
  unavailable,
}: {
  holdings: BondTopHoldingItem[];
  unavailable: boolean;
}) {
  if (unavailable) {
    return <div className={styles.tableEmpty}>{TOP_HOLDINGS_HOME_NOTE}</div>;
  }

  if (holdings.length === 0) {
    return <div className={styles.tableEmpty}>暂无持仓明细</div>;
  }

  return (
    <div className={styles.holdingsTableRows}>
      {holdings.map((item) => (
        <div key={item.instrument_code} className={styles.holdingsTableRow}>
          <div className={styles.holdingNameCell}>
            <strong>{item.instrument_name ?? item.instrument_code}</strong>
            <span>{item.instrument_code}</span>
          </div>
          <span>{item.asset_class}</span>
          <span>{item.rating ?? "—"}</span>
          <span style={tabularNumsStyle}>{formatYi(item.market_value)}</span>
          <span style={tabularNumsStyle}>{formatPct(item.ytm)}</span>
          <span style={tabularNumsStyle}>{item.modified_duration.display}</span>
          <span style={tabularNumsStyle}>{formatPct(item.weight)}</span>
        </div>
      ))}
    </div>
  );
}

function RegionDistributionPanel({
  items,
  emptyText,
}: {
  items: Array<{
    key: string;
    label: string;
    value: number;
    caption: string;
    color?: string;
  }>;
  emptyText: string;
}) {
  const topItems = items.slice(0, 8);

  if (topItems.length === 0) {
    return (
      <div className={styles.regionPanel}>
        <div className={styles.mapPlaceholder}>
          <span>地区/行业分布暂无可用读面</span>
        </div>
        <Text type="secondary">{emptyText}</Text>
      </div>
    );
  }

  return (
    <div className={styles.regionPanel}>
      <div className={styles.mapPlaceholder}>
        {topItems.slice(0, 5).map((item, index) => (
          <span
            key={item.key}
            style={{
              left: `${18 + ((index * 17) % 58)}%`,
              top: `${22 + ((index * 23) % 48)}%`,
              width: `${22 + index * 4}px`,
              height: `${14 + index * 3}px`,
              background: item.color ?? dt.color.info[300],
              opacity: 0.38 + index * 0.08,
            }}
            title={item.label}
          />
        ))}
      </div>
      <div className={styles.regionList}>
        {topItems.map((item) => (
          <div key={item.key} className={styles.regionRow}>
            <strong>{item.label}</strong>
            <span style={tabularNumsStyle}>{item.caption}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
  topAnomalies?: string[];
  actionAttribution?: ActionAttributionResponse | null;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
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

  const [
    headlineQ,
    _spreadQ,
    maturityQ,
    holdingsQ,
    portfolioHlQ,
    assetStructureQ,
    riskQ,
    industryQ,
  ] = useQueries({
    queries: [
      {
        queryKey: apiQueryKeys.bondDashboardHeadline(client.mode, dashboardReportDate),
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
        queryKey: ["bond-analytics-institutional", "holdings", client.mode, dashboardReportDate],
        queryFn: () => client.getBondAnalyticsTopHoldings(dashboardReportDate, 10),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(client.mode, dashboardReportDate),
        queryFn: () => client.getBondAnalyticsPortfolioHeadlines(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "asset-structure", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardAssetStructure(dashboardReportDate, "bond_type"),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "risk-indicators", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardRiskIndicators(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "industry-distribution", client.mode, dashboardReportDate],
        queryFn: () => client.getBondDashboardIndustryDistribution(dashboardReportDate),
        enabled: Boolean(dashboardReportDate),
      },
    ],
  });

  const headline = headlineQ.data?.result;
  const portfolioHl = portfolioHlQ.data?.result;
  const err = headlineQ.isError ? ((headlineQ.error as Error)?.message ?? "驾驶舱数据加载失败") : null;
  const portfolioHeadlinesUnavailable = portfolioHlQ.isError;
  const topHoldingsUnavailable = holdingsQ.isError;

  const dur = headline ? numOr(headline.kpis.weighted_duration) : Number.NaN;
  const riskCreditRatio = riskQ.data?.result ? numOr(riskQ.data.result.credit_ratio) : Number.NaN;
  const portfolioCreditWeight = portfolioHl ? numOr(portfolioHl.credit_weight) : Number.NaN;
  const creditWeight = Number.isFinite(riskCreditRatio) ? riskCreditRatio : portfolioCreditWeight;
  const spreadMedian = headline ? numOr(headline.kpis.credit_spread_median) : Number.NaN;
  const conclusion = buildCockpitConclusion({
    duration: dur,
    creditWeight,
    spreadMedian,
  });

  const k = headline?.kpis;
  const previousK = headline?.prev_kpis;
  const marketValuePair = buildKpiValuePair(headline ?? null, "total_market_value");
  const unrealizedPnlPair = buildKpiValuePair(headline ?? null, "unrealized_pnl");
  const marketValueMomPct = computeRelativeChangePct(marketValuePair.current, marketValuePair.previous);
  const unrealizedPnlMomPct = computeRelativeChangePct(unrealizedPnlPair.current, unrealizedPnlPair.previous);
  const dv01Mom = k && previousK ? numOr(k.total_dv01) - numOr(previousK.total_dv01) : Number.NaN;

  const maturityItems = useMemo(() => {
    return [...(maturityQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 7)
      .map((item) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: numOr(item.total_market_value),
        caption: formatYi(item.total_market_value),
        color: dt.color.success[500],
      }));
  }, [maturityQ.data]);

  const leadMaturity = maturityItems[0];
  const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
  const dashboardAssetItems = useMemo(() => {
    const palette = [dt.color.primary[700], dt.color.info[500], dt.color.success[600], dt.color.warning[500], dt.color.neutral[400]];
    const dashboardItems = [...(assetStructureQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 5)
      .map((item: AssetStructureItem, index) => ({
        key: item.category,
        label: item.category || "未分类",
        value: numOr(item.total_market_value),
        caption: formatYi(item.total_market_value),
        detail: `${item.bond_count} 只`,
        color: palette[index % palette.length],
      }));

    if (dashboardItems.length > 0) {
      return dashboardItems;
    }

    return assetClassItems.map((item, index) => ({
      key: item.asset_class,
      label: item.asset_class,
      value: numOr(item.market_value),
      caption: formatYi(item.market_value),
      detail: `久期 ${item.duration.display} · 权重 ${item.weight.display}`,
      color: palette[index % palette.length],
    }));
  }, [assetClassItems, assetStructureQ.data]);
  const industryItems = useMemo(() => {
    const palette = [dt.color.primary[700], dt.color.info[500], dt.color.success[600], dt.color.warning[500], dt.color.neutral[500]];
    return [...(industryQ.data?.result.items ?? [])]
      .sort((left, right) => numOr(right.total_market_value) - numOr(left.total_market_value))
      .slice(0, 8)
      .map((item, index) => ({
        key: item.industry_name,
        label: item.industry_name || "未分类",
        value: numOr(item.total_market_value),
        caption: formatYi(item.total_market_value),
        color: palette[index % palette.length],
      }));
  }, [industryQ.data]);
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
  const totalActionPnl = bondNumericRaw(actionAttribution?.total_pnl_from_actions ?? null);
  const durationDisplay = Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : "—";
  const creditWeightDisplay = Number.isFinite(creditWeight) ? `${(creditWeight * 100).toFixed(2)}%` : "—";
  const marketValueDisplay = k ? formatYi(k.total_market_value) : "—";
  const unrealizedPnlDisplay = k ? formatYi(k.unrealized_pnl) : "—";
  const bondCountDisplay = k ? formatNumericString(k.bond_count) : portfolioHl ? formatNumericString(portfolioHl.bond_count) : "—";
  const dv01Display = riskQ.data?.result
    ? formatWan(riskQ.data.result.total_dv01)
    : portfolioHl
      ? formatWan(portfolioHl.total_dv01)
      : k
        ? formatWan(k.total_dv01)
        : "—";
  const unrealizedPnlTone =
    k && numOr(k.unrealized_pnl) !== 0 ? (numOr(k.unrealized_pnl) > 0 ? "positive" : "negative") : "default";
  const actionPnlDisplay = actionAttribution ? formatWan(actionAttribution.total_pnl_from_actions) : "—";
  const actionPnlTone =
    Number.isFinite(totalActionPnl) && totalActionPnl !== 0
      ? totalActionPnl > 0
        ? "positive"
        : "negative"
      : "default";
  const maturityRows = maturityItems.map((item) => ({
    ...item,
    detail: `规模 ${item.caption}`,
  }));
  const ratingRows = ratingDistribution.map((item, index) => ({
    key: item.rating,
    label: item.rating,
    value: item.faceValue,
    caption: `${item.count} 只`,
    detail: formatYi(item.faceValue),
    color: [dt.color.primary[600], dt.color.info[500], dt.color.success[500], dt.color.warning[500], dt.color.neutral[500], dt.color.primary[300]][index % 6],
  }));
  const durationRows = maturityItems.slice(0, 3).map((item) => ({
    ...item,
    detail: `市值 ${item.caption}`,
  }));
  const riskRows = [
    {
      label: "组合久期",
      value: riskQ.data?.result ? `${numOr(riskQ.data.result.weighted_duration).toFixed(2)} 年` : durationDisplay,
      detail: "来自风险指标读面",
    },
    {
      label: "组合 DV01",
      value: dv01Display,
      detail: "利率敏感度",
    },
    {
      label: "信用占比",
      value: riskQ.data?.result ? formatPct(riskQ.data.result.credit_ratio) : creditWeightDisplay,
      detail: "信用债市值占比",
    },
    {
      label: "利差 DV01",
      value: riskQ.data?.result ? formatWan(riskQ.data.result.total_spread_dv01) : "—",
      detail: "信用利差敏感度",
    },
  ];
  const investmentGradeRatio = Number.isFinite(creditWeight) ? creditWeight : null;

  return (
    <section data-testid="bond-analysis-phase3-cockpit" className={styles.phaseSection}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <section data-testid="bond-analysis-reference-dashboard" className={styles.referenceDashboard}>
        <div className={styles.holdingsKpiRail}>
          <div data-testid="bond-analysis-kpi-ribbon" className={styles.holdingsKpiGrid}>
            <ReferenceKpiTile label="组合总览" value={marketValueDisplay} detail={`较上期 ${formatSignedPct(marketValueMomPct)}`} />
            <ReferenceKpiTile label="债券总市值" value={marketValueDisplay} detail="正式读面市值" />
            <ReferenceKpiTile label="持仓收益（估值）" value={unrealizedPnlDisplay} detail={`较上期 ${formatSignedPct(unrealizedPnlMomPct)}`} tone={unrealizedPnlTone} />
            <ReferenceKpiTile label="今日收益（估值）" value={actionPnlDisplay} detail={actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待返回"} tone={actionPnlTone} />
            <ReferenceKpiTile label="加权久期" value={durationDisplay} detail={leadMaturity ? `最重期限桶 ${leadMaturity.label}` : "期限结构待返回"} />
            <ReferenceKpiTile label="组合 DV01" value={dv01Display} detail="风险指标读面" />
            <ReferenceKpiDonutTile label="信用债占比" value={creditWeightDisplay} detail={`债券只数 ${bondCountDisplay}`} ratio={investmentGradeRatio} />
          </div>
        </div>

        <div className={styles.referenceTopbar}>
          <div>
            <div style={{ ...FIELD, marginBottom: 4 }}>债券持仓</div>
            <h2 className={styles.referenceTitle}>组合总览</h2>
            <p className={styles.referenceSubtitle}>
              报告日 {dashboardReportDate || reportDate || "—"} · 首屏只展示后端读面与已确认下钻入口。
            </p>
          </div>
          <div className={styles.referenceStatusPills}>
            <span>数据更新时间 {headline?.report_date ?? dashboardReportDate ?? "—"}</span>
            <span>{isDashboardDateFallback ? `快照回退 ${dashboardReportDate}` : "报告日匹配"}</span>
            <span>估值状态 {headlineQ.isPending ? "加载中" : headline ? "已完成" : "待确认"}</span>
          </div>
        </div>

        <div
          data-testid="bond-analysis-cockpit-conclusion"
          className={styles.referenceSignalStrip}
        >
          <div>
            <div style={{ ...FIELD, marginBottom: 3 }}>{conclusion.title}</div>
            <strong>{conclusion.body}</strong>
            <span>{conclusion.detail}</span>
          </div>
          <div className={styles.referenceStatusPills}>
            <span>数据更新时间 {headline?.report_date ?? dashboardReportDate ?? "—"}</span>
            <span>{isDashboardDateFallback ? `快照回退 ${dashboardReportDate}` : "报告日匹配"}</span>
            <span>估值状态 {headlineQ.isPending ? "加载中" : headline ? "已完成" : "待确认"}</span>
          </div>
        </div>
        <section data-testid="bond-analysis-distribution-grid" className={styles.referenceDistributionGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="资产分布" title="按券种分布" />}
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
            styles={{ body: cardBodyStyle }}
          >
            <DistributionDonut items={dashboardAssetItems} center={marketValueDisplay} emptyText="暂无资产结构" />
            {portfolioHeadlinesUnavailable ? <div style={moduleNoteStyle}>{PORTFOLIO_HEADLINES_STRUCTURE_NOTE}</div> : null}
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="到期结构" title="期限桶分布" />}
            style={dashboardCardStyle}
            className={styles.referenceMaturityCard}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.statRow}>
              <span style={{ color: muted, fontSize: dt.fontSize[12] }}>加权收益率</span>
              <span style={{ color: inkStrong, fontWeight: 700, ...tabularNumsStyle }}>{k ? formatPct(k.weighted_ytm) : "—"}</span>
            </div>
            <ProgressStack items={maturityRows} emptyText="暂无期限结构" />
            <MaturityColumnChart items={maturityRows} emptyText="暂无期限结构" />
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="地区分布" title="发行人/行业分布" />}
            style={dashboardCardStyle}
            styles={{ body: cardBodyStyle }}
          >
            <RegionDistributionPanel items={industryItems} emptyText="暂无行业/地区读面" />
          </Card>
        </section>

        <div className={styles.referenceBottomGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="持仓明细" title="前十大持仓" />}
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
            data-testid="bond-analysis-holdings-table"
            style={dashboardCardStyle}
            className={styles.referenceHoldingsCard}
            styles={{ body: { padding: 0 } }}
          >
            <div className={styles.holdingsTable}>
              <div className={styles.holdingsTableHeader}>
                <span>债券</span>
                <span>券种</span>
                <span>评级</span>
                <span>市值</span>
                <span>收益率</span>
                <span>久期</span>
                <span>权重</span>
              </div>
              <HoldingRows holdings={topHoldings} unavailable={topHoldingsUnavailable} />
            </div>
          </Card>


        </div>

        <aside className={styles.referenceSideStack}>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="评级分布" title="按市值" />}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <ProgressStack items={ratingRows} emptyText={topHoldingsUnavailable ? TOP_HOLDINGS_RATING_NOTE : "暂无评级分布"} />
              {portfolioHeadlinesUnavailable ? <div style={moduleNoteStyle}>{PORTFOLIO_HEADLINES_CREDIT_NOTE}</div> : null}
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="久期分布" title="按市值" />}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <ProgressStack items={durationRows} emptyText="暂无久期分布" />
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="流动性分布" title="按读面状态" />}
              style={dashboardCardStyle}
              styles={{ body: cardBodyStyle }}
            >
              <PendingReadModelPanel
                title="流动性读面待返回"
                detail="当前接口未提供流动性分布，不在前端补造。"
              />
            </Card>
        </aside>

        <div className={styles.referenceFooterGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="持仓收益走势" title="本期估值收益" />}
            data-testid="bond-analysis-summary-card"
            style={dashboardCardStyle}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.footerMetricPanel}>
              <strong style={tabularNumsStyle}>{unrealizedPnlDisplay}</strong>
              <span>{Number.isFinite(unrealizedPnlMomPct) ? `较上期 ${formatSignedPct(unrealizedPnlMomPct)}` : "收益走势明细待读面返回"}</span>
              <div className={styles.footerSparkline} aria-hidden="true">
                {[18, 42, 28, 56, 44, 68, 50, 76, 62, 84].map((height, index) => (
                  <i key={index} style={{ height: `${height}%` }} />
                ))}
              </div>
              <Button size="small" type="text" data-testid="bond-analysis-home-open-return-decomposition" onClick={() => onOpenModuleDetail?.("return-decomposition")}>
                打开收益拆解
              </Button>
            </div>
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="持仓变动" title="动作归因" />}
            data-testid="bond-analysis-today-focus"
            style={dashboardCardStyle}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.footerMetricPanel}>
              <strong style={tabularNumsStyle}>{actionPnlDisplay}</strong>
              <span>{actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待返回"}</span>
              <div className={styles.footerChangeSplit}>
                <span>市值 {formatSignedPct(marketValueMomPct)}</span>
                <span>DV01 {Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : "—"}</span>
              </div>
              <Button size="small" type="text" data-testid="bond-analysis-home-open-action-attribution" onClick={() => onOpenModuleDetail?.("action-attribution")}>
                打开动作归因
              </Button>
            </div>
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="风险指标" title="实时护栏" />}
            data-testid="bond-analysis-risk-guardrails"
            style={dashboardCardStyle}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.footerRiskList}>
              {riskRows.slice(0, 3).map((row) => (
                <div key={row.label}>
                  <span>{row.label}</span>
                  <strong style={tabularNumsStyle}>{row.value}</strong>
                </div>
              ))}
              <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                打开信用利差
              </Button>
            </div>
          </Card>
        </div>
      </section>
    </section>
  );
}
