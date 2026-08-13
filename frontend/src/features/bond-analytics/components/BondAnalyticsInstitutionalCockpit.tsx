import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card } from "antd";

import { useApiClient } from "../../../api/client";
import type {
  AssetStructureItem,
  BondDashboardBundleSectionId,
} from "../../../api/contracts";
import { bondNumericRaw, bondNumericRawOrNull } from "../adapters/bondAnalyticsAdapter";
import {
  buildKpiValuePair,
  computeRelativeChangePct,
} from "../lib/bondAnalyticsHomeCalculations";
import type {
  BondAnalyticsActiveModuleContext,
  BondAnalyticsReadinessItem,
} from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { BondAnalyticsDecisionRail } from "./BondAnalyticsDecisionRail";
import type { ActionAttributionResponse } from "../types";
import { EM_DASH } from "../../../utils/format";
import { formatPct, formatWan, formatYi } from "../utils/formatters";
import { BOND_HOLDINGS_COCKPIT_SCOPE_NOTE } from "../lib/bondHoldingsEvidenceCopy";
import {
  bundleSectionQuery,
  useBondAnalyticsCockpitBundleQuery,
} from "../lib/bondAnalyticsCockpitBundleQuery";
import {
  InstitutionalKpiRail,
  InstitutionalKpiTile,
} from "../../workbench/shared/InstitutionalKpiTile";
import {
  buildCockpitConclusion,
  buildDeskVerdictFields,
  formatDurationDisplay,
  formatNumericDisplay,
  formatSignedPct,
  formatSpreadBpDisplay,
  normalizeSpreadBp,
  numOr,
  numOrNullAware,
} from "./bondAnalyticsCockpitFormat";
import {
  DistributionDonut,
  PendingReadModelPanel,
  ProgressStack,
  RegionDistributionPanel,
  SectionCardTitle,
} from "./BondAnalyticsCockpitPrimitives";
import { DISTRIBUTION_CHART_COLORS, cardBodyStyle } from "./bondAnalyticsCockpitTokens";
import { ReferenceYieldCurvePanel } from "./BondAnalyticsCockpitCurveZone";
import { curveHasReadout } from "./bondAnalyticsCockpitCurveZoneSupport";
import {
  AccountingDv01SummaryPanel,
  HoldingRows,
  HoldingsMobileReadout,
  ReferenceJudgmentMatrix,
  ReferenceMarketTicker,
  ReferenceReturnAttributionPanel,
} from "./BondAnalyticsCockpitSupportPanels";
import styles from "./BondAnalyticsInstitutionalCockpit.module.css";

const PORTFOLIO_HEADLINES_STRUCTURE_NOTE = "组合信用摘要暂未返回，资产结构稍后补齐。";
const PORTFOLIO_HEADLINES_CREDIT_NOTE = "组合信用摘要暂未返回，债券只数、集中度和 DV01 稍后补齐。";
const TOP_HOLDINGS_CARD_TITLE = "前十大返回持仓";
const TOP_HOLDINGS_COUNT_LABEL = "返回持仓";
const TOP_HOLDINGS_RATING_NOTE = "持仓明细暂未返回，评级分布稍后补齐。";
const BOND_ANALYTICS_CURRENCY_BASIS_TEXT =
  "金额指标按人民币/CNY口径展示，外币债券市值、摊余成本、应计利息等已折算为人民币。";
const DV01_ACCOUNTING_CLASSES = [
  { label: "AC", value: "AC" },
  { label: "OCI", value: "OCI" },
  { label: "TPL", value: "TPL" },
  { label: "全部", value: "all" },
] as const;

type Dv01AccountingClassValue = (typeof DV01_ACCOUNTING_CLASSES)[number]["value"];
const DV01_BUNDLE_SECTION_BY_ACCOUNTING_CLASS = {
  AC: "dv01-risk-ac",
  OCI: "dv01-risk-oci",
  TPL: "dv01-risk-tpl",
  all: "dv01-risk-all",
} as const satisfies Record<Dv01AccountingClassValue, BondDashboardBundleSectionId>;

export interface BondAnalyticsInstitutionalCockpitDecisionRailProps {
  activeModuleContext: BondAnalyticsActiveModuleContext;
  activeReadinessItem: BondAnalyticsReadinessItem;
  watchlistItems: BondAnalyticsReadinessItem[];
}

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
  topAnomalies?: string[];
  actionAttribution?: ActionAttributionResponse | null;
  decisionRail?: BondAnalyticsInstitutionalCockpitDecisionRailProps;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
  actionAttribution = null,
  decisionRail,
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
  const macroLatestQ = useQuery({
    queryKey: ["bond-analytics-institutional", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
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
  // Business queries below key off `queryReportDate` rather than waiting for
  // `dashboardReportDate` to resolve first: they fire immediately, optimistically assuming
  // `reportDate` is also a valid bond-dashboard snapshot (the common case). If the dashboard
  // dates lookup later reveals a fallback is needed, `dashboardReportDate` changes and every
  // query below picks up a new queryKey/param and re-fetches for the corrected date. This
  // removes the two-level "dates -> dates -> 12+ business calls" waterfall in the common case
  // without changing the final displayed data for the (rare) fallback case.
  const queryReportDate = dashboardReportDate || reportDate;

  const cockpitBundleQ = useBondAnalyticsCockpitBundleQuery(queryReportDate);
  const headlineQ = bundleSectionQuery(cockpitBundleQ, "headline-kpis");
  const maturityQ = bundleSectionQuery(cockpitBundleQ, "maturity-structure");
  const holdingsQ = bundleSectionQuery(cockpitBundleQ, "top-holdings");
  const portfolioHlQ = bundleSectionQuery(cockpitBundleQ, "portfolio-headlines");
  const assetStructureQ = bundleSectionQuery(cockpitBundleQ, "asset-structure");
  const riskQ = bundleSectionQuery(cockpitBundleQ, "risk-indicators");
  const industryQ = bundleSectionQuery(cockpitBundleQ, "industry-distribution");
  const yieldCurveQ = bundleSectionQuery(cockpitBundleQ, "yield-curve-term-structure");
  const dv01AccountingQueries = DV01_ACCOUNTING_CLASSES.map((item) =>
    bundleSectionQuery(cockpitBundleQ, DV01_BUNDLE_SECTION_BY_ACCOUNTING_CLASS[item.value]),
  );

  const headline = headlineQ.data?.result;
  const portfolioHl = portfolioHlQ.data?.result;
  const err = headlineQ.isError ? ((headlineQ.error as Error)?.message ?? "驾驶舱数据加载失败") : null;
  const portfolioHeadlinesUnavailable = portfolioHlQ.isError;
  const topHoldingsUnavailable = holdingsQ.isError;
  const dv01AccountingRows = DV01_ACCOUNTING_CLASSES.map((item, index) => ({
    ...item,
    payload: dv01AccountingQueries[index]?.data?.result ?? null,
  }));
  const dv01AccountingLoading = dv01AccountingQueries.some((query) => query.isLoading);
  const dv01AccountingUnavailable = dv01AccountingQueries.some((query) => query.isError);

  const dur = headline ? numOrNullAware(headline.kpis.weighted_duration) : Number.NaN;
  const riskCreditRatio = riskQ.data?.result ? numOrNullAware(riskQ.data.result.credit_ratio) : Number.NaN;
  const portfolioCreditWeight = portfolioHl ? numOrNullAware(portfolioHl.credit_weight) : Number.NaN;
  const creditWeight = Number.isFinite(riskCreditRatio) ? riskCreditRatio : portfolioCreditWeight;
  const spreadMedian = headline?.kpis.credit_spread_median ?? null;
  const spreadMedianBp = normalizeSpreadBp(spreadMedian);
  const conclusion = isDashboardDateFallback
    ? {
        title: "快照待复核",
        body: "当前请求报告日暂无债券驾驶舱快照。",
        detail: `请求 ${reportDate}，当前展示 ${dashboardReportDate} 快照；主结论需等目标报告日读面补齐后再确认。`,
      }
    : buildCockpitConclusion({
        duration: dur,
        creditWeight,
        spreadMedianBp,
      });

  const k = headline?.kpis;
  const previousK = headline?.prev_kpis;
  const marketValuePair = buildKpiValuePair(headline ?? null, "total_market_value");
  const unrealizedPnlPair = buildKpiValuePair(headline ?? null, "unrealized_pnl");
  const marketValueMomPct = computeRelativeChangePct(marketValuePair.current, marketValuePair.previous);
  const unrealizedPnlMomPct = computeRelativeChangePct(unrealizedPnlPair.current, unrealizedPnlPair.previous);
  const currentDv01Raw = k ? bondNumericRawOrNull(k.total_dv01) : null;
  const previousDv01Raw = previousK ? bondNumericRawOrNull(previousK.total_dv01) : null;
  const dv01Mom = currentDv01Raw !== null && previousDv01Raw !== null ? currentDv01Raw - previousDv01Raw : Number.NaN;

  const maturityItems = useMemo(() => {
    return [...(maturityQ.data?.result.items ?? [])]
      .flatMap((item) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 7)
      .map(({ item, rawMarketValue }, index) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        color: DISTRIBUTION_CHART_COLORS[index % DISTRIBUTION_CHART_COLORS.length],
      }));
  }, [maturityQ.data]);

  const leadMaturity = maturityItems[0];
  const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
  const dashboardAssetItems = useMemo(() => {
    const palette = DISTRIBUTION_CHART_COLORS;
    const dashboardItems = [...(assetStructureQ.data?.result.items ?? [])]
      .flatMap((item: AssetStructureItem, index) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, index, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 5)
      .map(({ item, index, rawMarketValue }) => ({
        key: item.category,
        label: item.category || "未分类",
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        detail: `${item.bond_count} 只`,
        color: palette[index % palette.length],
      }));

    if (dashboardItems.length > 0) {
      return dashboardItems;
    }

    return assetClassItems.flatMap((item, index) => {
      const rawMarketValue = bondNumericRawOrNull(item.market_value);
      return rawMarketValue === null
        ? []
        : [
            {
              key: item.asset_class,
              label: item.asset_class,
              value: rawMarketValue,
              caption: formatYi(item.market_value),
              detail: `久期 ${formatNumericDisplay(item.duration)} · 权重 ${formatNumericDisplay(item.weight)}`,
              color: palette[index % palette.length],
            },
          ];
    });
  }, [assetClassItems, assetStructureQ.data]);
  const industryItems = useMemo(() => {
    const palette = DISTRIBUTION_CHART_COLORS;
    return [...(industryQ.data?.result.items ?? [])]
      .flatMap((item, index) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, index, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 8)
      .map(({ item, index, rawMarketValue }) => ({
        key: item.industry_name,
        label: item.industry_name || "未分类",
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
        color: palette[index % palette.length],
      }));
  }, [industryQ.data]);
  const topHoldings = (holdingsQ.data?.result.items ?? []).slice(0, 10);
  const ratingDistribution = useMemo(() => {
    const buckets = new Map<string, { count: number; faceValue: number }>();
    for (const item of holdingsQ.data?.result.items ?? []) {
      const rawFaceValue = bondNumericRawOrNull(item.face_value);
      if (rawFaceValue === null) {
        continue;
      }
      const key = item.rating?.trim() || "Unrated";
      const next = buckets.get(key) ?? { count: 0, faceValue: 0 };
      next.count += 1;
      next.faceValue += rawFaceValue;
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
  const durationDisplay = Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : EM_DASH;
  const creditWeightDisplay = Number.isFinite(creditWeight) ? `${(creditWeight * 100).toFixed(2)}%` : EM_DASH;
  const marketValueDisplay = k ? formatYi(k.total_market_value) : EM_DASH;
  const unrealizedPnlDisplay = k ? formatYi(k.unrealized_pnl) : EM_DASH;
  const dv01Source = riskQ.data?.result?.total_dv01 ?? portfolioHl?.total_dv01 ?? k?.total_dv01 ?? null;
  const hasDv01Readout = bondNumericRawOrNull(dv01Source) !== null;
  const dv01Display = hasDv01Readout ? formatWan(dv01Source) : EM_DASH;
  const unrealizedPnlTone =
    k && numOr(k.unrealized_pnl) !== 0 ? (numOr(k.unrealized_pnl) > 0 ? "positive" : "negative") : "default";
  const actionPnlDisplay = actionAttribution ? formatWan(actionAttribution.total_pnl_from_actions) : EM_DASH;
  const actionPnlTone =
    totalActionPnl !== null && Number.isFinite(totalActionPnl) && totalActionPnl !== 0
      ? totalActionPnl > 0
        ? "positive"
        : "negative"
      : "default";
  const macroSeries = macroLatestQ.data?.result.series ?? [];
  const macroUnavailable = macroLatestQ.isError || macroSeries.length === 0;
  const yieldCurveCurves = yieldCurveQ.data?.result.curves ?? [];
  const hasYieldCurveReadout = yieldCurveCurves.some(curveHasReadout);
  const holdingRatingGapCount = topHoldings.filter((item) => !item.rating?.trim()).length;
  const holdingMetricGapCount = topHoldings.reduce((count, item) => {
    return (
      count +
      (bondNumericRawOrNull(item.market_value) === null ? 1 : 0) +
      (bondNumericRawOrNull(item.ytm) === null ? 1 : 0) +
      (bondNumericRawOrNull(item.modified_duration) === null ? 1 : 0) +
      (bondNumericRawOrNull(item.weight) === null ? 1 : 0)
    );
  }, 0);
  const deskVerdictFields = buildDeskVerdictFields({
    duration: dur,
    creditWeight,
    spreadMedianBp,
    dv01Display,
    reportDate,
    dashboardReportDate,
    isDashboardDateFallback,
    headlinePending: headlineQ.isPending,
    hasHeadline: Boolean(headline),
    hasCurveReadout: hasYieldCurveReadout,
    curvePending: yieldCurveQ.isLoading,
  });
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
    color: DISTRIBUTION_CHART_COLORS[index % DISTRIBUTION_CHART_COLORS.length],
  }));
  const durationRows = maturityItems.slice(0, 3).map((item) => ({
    ...item,
    detail: `市值 ${item.caption}`,
  }));
  const durationRiskRow = {
    label: "组合久期",
    value: riskQ.data?.result ? formatDurationDisplay(riskQ.data.result.weighted_duration) : durationDisplay,
    detail: "来自风险指标读面",
  };
  const dv01RiskRow = {
    label: "组合 DV01",
    value: dv01Display,
    detail: "利率敏感度",
  };
  const creditRatioRiskRow = {
    label: "信用占比",
    value: riskQ.data?.result ? formatPct(riskQ.data.result.credit_ratio) : creditWeightDisplay,
    detail: "信用债市值占比",
  };
  const spreadDv01RiskRow = {
    label: "利差 DV01",
    value: riskQ.data?.result ? formatWan(riskQ.data.result.total_spread_dv01) : EM_DASH,
    detail: "信用利差敏感度",
  };
  const riskRows = [durationRiskRow, dv01RiskRow, creditRatioRiskRow, spreadDv01RiskRow];
  const footerRiskRows = [durationRiskRow, dv01RiskRow, creditRatioRiskRow];
  const topbarReportDate = dashboardReportDate || reportDate || EM_DASH;
  const topbarReportStatus = isDashboardDateFallback
    ? `快照回退 ${dashboardReportDate || EM_DASH}`
    : dashboardReportDate
      ? "报告日匹配"
      : "报告日待确认";
  const topbarReadoutStatus = headlineQ.isPending ? "加载中" : headline ? "已返回" : "待返回";
  const topbarReadoutDetail = headlineQ.isPending
    ? "等待后端返回"
    : headline
      ? "核心读面可用"
      : "核心读面未返回";

  return (
    <section data-testid="bond-analysis-phase3-cockpit" className={styles.phaseSection}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <section data-testid="bond-analysis-reference-dashboard" className={styles.referenceDashboard}>
        <section data-testid="bond-analysis-reference-topbar" className={styles.heroSection}>
          <div className={styles.heroIdentity}>
            <h2 className={styles.heroTitle}>固定收益交易台</h2>
            <span className={styles.heroReportDate}>报告日 {topbarReportDate}</span>
          </div>

          <div data-testid="bond-analysis-cockpit-conclusion" className={styles.heroMain}>
            <div className={styles.heroConclusion}>
              <strong className={styles.heroHeadline}>{conclusion.body}</strong>
              <p className={styles.heroDetail}>{conclusion.detail}</p>
            </div>
            <div className={styles.heroMetrics}>
              <div className={styles.heroMetric}>
                <span>久期</span>
                <strong>{durationDisplay}</strong>
              </div>
              <div className={styles.heroMetric}>
                <span>信用利差</span>
                <strong>{formatSpreadBpDisplay(spreadMedian)}</strong>
              </div>
              <div className={styles.heroMetric}>
                <span>信用占比</span>
                <strong>{creditWeightDisplay}</strong>
              </div>
              <div className={styles.heroMetric}>
                <span>总收益</span>
                <strong className={styles.heroMetricValue} data-tone={unrealizedPnlTone}>
                  {unrealizedPnlDisplay}
                </strong>
                <small className={styles.heroMetricDelta} data-tone={unrealizedPnlTone}>
                  {formatSignedPct(unrealizedPnlMomPct)}
                </small>
              </div>
            </div>
          </div>
          <div className={styles.heroAside} data-testid="bond-analysis-hero-aside">
            <div data-testid="bond-analysis-daily-judgment" className={styles.heroGovernance}>
              <div className={styles.heroGovernanceLead}>
                <span className={styles.conclusionKicker}>证据展开 · 固定收益读面</span>
                <span className={styles.heroGovernanceHeading}>首屏读面拆解</span>
                <span className={styles.heroGovernanceDetail}>只展示后端返回事实，不补造读面。</span>
              </div>
              <div className={styles.heroGovernanceMetrics}>
                <span>久期 {durationDisplay}</span>
                <span>信用利差 {formatSpreadBpDisplay(spreadMedian)}</span>
                <span>信用占比 {creditWeightDisplay}</span>
              </div>
              <div className={styles.heroGovernanceStatus} data-testid="bond-analysis-daily-judgment-status">
                <span>
                  报告日 {topbarReportStatus} · {topbarReportDate}
                </span>
                <span>
                  首屏 KPI {topbarReadoutStatus} · {topbarReadoutDetail}
                </span>
              </div>
              <div className={styles.heroVerdictRow}>
                {deskVerdictFields.map((field) => (
                  <div key={field.label} className={styles.heroVerdictField}>
                    <span>{field.label}</span>
                    <strong>{field.value}</strong>
                    <small>{field.detail}</small>
                  </div>
                ))}
              </div>
            </div>
            {decisionRail && onOpenModuleDetail ? (
              <aside>
                <BondAnalyticsDecisionRail
                  activeModuleContext={decisionRail.activeModuleContext}
                  activeReadinessItem={decisionRail.activeReadinessItem}
                  watchlistItems={decisionRail.watchlistItems}
                  onOpenModuleDetail={onOpenModuleDetail}
                />
              </aside>
            ) : null}
          </div>
        </section>

        <ReferenceMarketTicker series={macroSeries} unavailable={macroUnavailable} />

        <div className={styles.holdingsKpiRail}>
          {/* 常态零徽标（首页 2026-08-13 降噪制度）：就绪读数不再挂「已读」，仅缺口/待读面发声。 */}
          <InstitutionalKpiRail testId="bond-analysis-kpi-ribbon" columns={7} flush>
            <InstitutionalKpiTile label="久期" value={durationDisplay} detail={leadMaturity ? `最重期限桶 ${leadMaturity.label}` : "期限结构待读面"} status={Number.isFinite(dur) ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="组合到期收益率" value={k ? formatPct(k.weighted_ytm) : EM_DASH} detail={previousK ? `上期 ${formatPct(previousK.weighted_ytm)}` : "收益率待读面"} status={k ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="信用利差" value={formatSpreadBpDisplay(spreadMedian)} detail="信用利差中位数" status={Number.isFinite(spreadMedianBp) ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="DV01" value={dv01Display} detail="风险指标读面" status={hasDv01Readout ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="Carry+Roll" value={EM_DASH} detail="接口未返回 / 待读面" status="缺口" priority="gap" />
            <InstitutionalKpiTile label="月度收益" value={actionPnlDisplay} detail={actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待读面"} status={actionAttribution ? undefined : "待读面"} tone={actionPnlTone} />
            <InstitutionalKpiTile label="总收益" value={unrealizedPnlDisplay} detail={`较上期 ${formatSignedPct(unrealizedPnlMomPct)}`} status={k ? undefined : "待读面"} tone={unrealizedPnlTone} />
          </InstitutionalKpiRail>
          <div
            data-testid="bond-analysis-currency-basis-banner"
            className={styles.currencyBasisBanner}
          >
            {BOND_ANALYTICS_CURRENCY_BASIS_TEXT}
          </div>
        </div>

        <section data-testid="bond-analysis-analysis-grid" className={styles.referenceAnalysisGrid}>
          <ReferenceYieldCurvePanel
            reportDate={dashboardReportDate || reportDate}
            maturityRows={maturityRows}
            curves={yieldCurveCurves}
            isLoading={yieldCurveQ.isLoading}
            hasError={yieldCurveQ.isError}
          />
          <div className={styles.referenceAnalysisSideStack}>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="证据边界" title="利率 / 曲线 / 信用 / 资金" />}
              data-testid="bond-analysis-evidence-boundary-panel"
              className={`${styles.dashboardCard} ${styles.referencePanelCard} ${styles.referenceEvidenceBoundaryCard}`}
              styles={{ body: cardBodyStyle }}
            >
              <ReferenceJudgmentMatrix
                duration={dur}
                creditWeight={creditWeight}
                spreadMedianBp={spreadMedianBp}
                dv01Display={dv01Display}
                hasDv01Readout={hasDv01Readout}
                hasCurveReadout={hasYieldCurveReadout}
                marketValueMomPct={marketValueMomPct}
              />
            </Card>
          </div>
          <ReferenceReturnAttributionPanel
            actionPnlDisplay={actionPnlDisplay}
            actionPnlTone={actionPnlTone}
            actionCount={actionAttribution?.total_actions ?? null}
            marketValueMomPct={marketValueMomPct}
            dv01Mom={dv01Mom}
            unrealizedPnlDisplay={unrealizedPnlDisplay}
            unrealizedPnlMomPct={unrealizedPnlMomPct}
            onOpenModuleDetail={onOpenModuleDetail}
          />
        </section>

        <AccountingDv01SummaryPanel
          rows={dv01AccountingRows}
          isLoading={dv01AccountingLoading}
          hasError={dv01AccountingUnavailable}
          onOpenModuleDetail={onOpenModuleDetail}
        />

        <section data-testid="bond-analysis-distribution-grid" className={styles.referenceDistributionGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="结构证据" title="券种分布" />}
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
            className={`${styles.dashboardCard} ${styles.referenceStructureLeadCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <DistributionDonut items={dashboardAssetItems} center={marketValueDisplay} emptyText="暂无资产结构" />
            {portfolioHeadlinesUnavailable ? <div className={styles.moduleNote}>{PORTFOLIO_HEADLINES_STRUCTURE_NOTE}</div> : null}
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="风险切片" title="久期 / DV01 / 信用" />}
            data-testid="bond-analysis-risk-monitor"
            className={`${styles.dashboardCard} ${styles.referenceMaturityCard} ${styles.referenceDistributionSupportCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.riskEvidenceList}>
              {riskRows.map((row) => (
                <div key={row.label} className={styles.riskEvidenceRow}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                  <small>{row.detail}</small>
                </div>
              ))}
              <div className={styles.riskEvidenceBoundary}>
                只列后端返回风险字段；缺失保持占位，不生成阈值判断。
              </div>
              <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                打开信用利差
              </Button>
            </div>
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="集中度证据" title="发行人/行业分布" />}
            className={`${styles.dashboardCard} ${styles.referenceDistributionSupportCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <RegionDistributionPanel items={industryItems} emptyText="暂无发行人/行业读面" />
          </Card>
        </section>

        <div className={styles.referenceBottomGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="持仓证据明细" title={TOP_HOLDINGS_CARD_TITLE} />}
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
            className={`${styles.dashboardCard} ${styles.referenceHoldingsCard}`}
            styles={{ body: { padding: 0 } }}
          >
            <HoldingsMobileReadout
              holdings={topHoldings}
              unavailable={topHoldingsUnavailable}
              reportDate={dashboardReportDate}
            />
            <div data-testid="bond-analysis-holdings-evidence-strip" className={styles.holdingsEvidenceStrip}>
              <div>
                <span>{TOP_HOLDINGS_COUNT_LABEL}</span>
                <strong>{topHoldingsUnavailable ? "待返回" : `${topHoldings.length} 条`}</strong>
                <small>{BOND_HOLDINGS_COCKPIT_SCOPE_NOTE}</small>
              </div>
              <div>
                <span>评级缺口</span>
                <strong>{topHoldingsUnavailable ? EM_DASH : `${holdingRatingGapCount} 条`}</strong>
                <small>缺失评级保持 —，不补造评级。</small>
              </div>
              <div>
                <span>数值缺口</span>
                <strong>{topHoldingsUnavailable ? EM_DASH : `${holdingMetricGapCount} 项`}</strong>
                <small>市值 / YTM / 久期 / 权重。</small>
              </div>
            </div>
            <div
              data-testid="bond-analysis-holdings-raw-grid"
              className={styles.holdingsTable}
            >
              <div
                data-testid="bond-analysis-holdings-scroll-cue"
                className={styles.holdingsScrollCue}
                aria-hidden="true"
              >
                <span />
              </div>
              <div className={styles.holdingsTableHeader}>
                <span>债券</span>
                <span>券种</span>
                <span>评级</span>
                <span>市值</span>
                <span>YTM</span>
                <span>久期</span>
                <span>权重</span>
              </div>
              <HoldingRows
                holdings={topHoldings}
                unavailable={topHoldingsUnavailable}
                reportDate={dashboardReportDate}
              />
            </div>
          </Card>


        </div>

        <aside className={styles.referenceSideStack}>
            <div data-testid="bond-analysis-risk-slice-stack" className={styles.sideStackHeader}>
              <span>风险切片</span>
              <strong>评级 / 期限 / 流动性</strong>
              <small>侧栏只汇总返回切片；接口缺口直接显示。</small>
            </div>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="评级证据" title="按市值" />}
              className={styles.dashboardCard}
              styles={{ body: cardBodyStyle }}
            >
              <ProgressStack items={ratingRows} emptyText={topHoldingsUnavailable ? TOP_HOLDINGS_RATING_NOTE : "暂无评级分布"} />
              {portfolioHeadlinesUnavailable ? <div className={styles.moduleNote}>{PORTFOLIO_HEADLINES_CREDIT_NOTE}</div> : null}
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="期限证据" title="按市值" />}
              className={styles.dashboardCard}
              styles={{ body: cardBodyStyle }}
            >
              <ProgressStack items={durationRows} emptyText="暂无久期分布" />
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="流动性缺口" title="按读面状态" />}
              className={styles.dashboardCard}
              styles={{ body: cardBodyStyle }}
            >
              <PendingReadModelPanel
                title="流动性读面待返回"
                detail="当前接口未提供流动性分布，不在前端补造。"
              />
            </Card>
        </aside>

        <div data-testid="bond-analysis-footer-evidence-grid" className={styles.referenceFooterGrid}>
          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="收益证据" title="本期估值收益" />}
            data-testid="bond-analysis-summary-card"
            className={`${styles.dashboardCard} ${styles.referenceFooterPrimaryCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.footerMetricPanel}>
              <strong>{unrealizedPnlDisplay}</strong>
              <span>{Number.isFinite(unrealizedPnlMomPct) ? `较上期 ${formatSignedPct(unrealizedPnlMomPct)}` : "收益时序证据待返回"}</span>
              <div className={styles.footerReturnLedger}>
                <div>
                  <span>估值收益</span>
                  <strong>{unrealizedPnlDisplay}</strong>
                </div>
                <div>
                  <span>较上期</span>
                  <strong>{Number.isFinite(unrealizedPnlMomPct) ? formatSignedPct(unrealizedPnlMomPct) : EM_DASH}</strong>
                </div>
                <div>
                  <span>收益时序</span>
                  <strong>待返回</strong>
                </div>
                <div>
                  <span>处理边界</span>
                  <strong>不补造趋势</strong>
                </div>
              </div>
              <div data-testid="bond-analysis-footer-primary-evidence" className={styles.footerEvidenceBlock}>
                <div data-testid="bond-analysis-return-trend-boundary" className={styles.footerEvidenceNote}>
                  收益时序未返回：不绘制趋势占位。
                </div>
                <div className={styles.footerActionBar}>
                  <span>收益证据缺口保留在当前读面上下文中。</span>
                  <Button size="small" type="text" data-testid="bond-analysis-home-open-return-decomposition" onClick={() => onOpenModuleDetail?.("return-decomposition")}>
                    打开收益拆解
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <div data-testid="bond-analysis-footer-support-stack" className={styles.footerSupportStack}>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="动作证据" title="动作归因" />}
              data-testid="bond-analysis-today-focus"
              className={styles.dashboardCard}
              styles={{ body: cardBodyStyle }}
            >
              <div className={styles.footerMetricPanel}>
                <strong>{actionPnlDisplay}</strong>
                <span>{actionAttribution ? `${actionAttribution.total_actions} 笔动作` : "动作归因待返回"}</span>
                <div className={styles.footerEvidenceBlock}>
                  <div className={styles.footerChangeSplit}>
                    <span>市值 {formatSignedPct(marketValueMomPct)}</span>
                    <span>DV01 {Number.isFinite(dv01Mom) ? `${dv01Mom >= 0 ? "+" : ""}${(dv01Mom / 10000).toFixed(2)} 万` : EM_DASH}</span>
                  </div>
                  <div className={styles.footerActionBar}>
                    <span>市值变动与 DV01 变动用于核对动作归因字段返回范围。</span>
                    <Button
                      size="small"
                      type="text"
                      data-testid="bond-analysis-footer-open-action-attribution"
                      onClick={() => onOpenModuleDetail?.("action-attribution")}
                    >
                      打开动作归因
                    </Button>
                  </div>
                </div>
              </div>
            </Card>

            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="风险读面" title="返回字段" />}
              data-testid="bond-analysis-risk-guardrails"
              className={styles.dashboardCard}
              styles={{ body: cardBodyStyle }}
            >
              <div className={styles.footerRiskList}>
                {footerRiskRows.map((row) => (
                  <div key={row.label} className={styles.footerRiskRow}>
                    <span>{row.label}</span>
                    <strong>{row.value}</strong>
                  </div>
                ))}
                <div className={styles.footerEvidenceNote}>
                  只列已返回风险字段；缺失保持证据缺口，不延伸为审批或阈值结论。
                </div>
                <div className={styles.footerActionBar}>
                  <span>信用利差字段以下钻返回为准；缺失继续保留证据缺口。</span>
                  <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread-footer" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                    打开信用利差
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </section>
    </section>
  );
}
