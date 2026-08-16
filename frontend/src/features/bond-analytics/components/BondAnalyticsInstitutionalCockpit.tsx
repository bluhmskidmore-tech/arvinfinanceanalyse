import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card } from "antd";

import { useApiClient } from "../../../api/client";
import type { CalendarItem } from "../../../components/CalendarList";
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
import type { ActionAttributionResponse } from "../types";
import { EM_DASH } from "../../../utils/format";
import { formatDv01Wan, formatPct, formatWan, formatYi } from "../utils/formatters";
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
  formatDurationDisplay,
  formatNumericDisplay,
  formatSignedPct,
  formatSpreadYtmPctDisplay,
  normalizeSpreadBp,
  numOr,
  numOrNullAware,
  stripLeadingPlus,
} from "./bondAnalyticsCockpitFormat";
import {
  DistributionDonut,
  DistributionRows,
  SectionCardTitle,
} from "./BondAnalyticsCockpitPrimitives";
import { DISTRIBUTION_CHART_COLORS, PERIOD_OPTIONS, cardBodyStyle } from "./bondAnalyticsCockpitTokens";
import { ReferenceYieldCurvePanel } from "./BondAnalyticsCockpitCurveZone";
import { curveHasReadout } from "./bondAnalyticsCockpitCurveZoneSupport";
import BondEventCalendar from "./BondEventCalendar";
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
  periodType?: string;
  topAnomalies?: string[];
  calendarItems?: CalendarItem[];
  calendarLoading?: boolean;
  calendarError?: boolean;
  actionAttribution?: ActionAttributionResponse | null;
  actionAttributionPending?: boolean;
  decisionRail?: BondAnalyticsInstitutionalCockpitDecisionRailProps;
  onOpenModuleDetail?: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsInstitutionalCockpit({
  reportDate,
  periodType = "MoM",
  topAnomalies = [],
  calendarItems = [],
  calendarLoading = false,
  calendarError = false,
  actionAttribution = null,
  actionAttributionPending = false,
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
  /* Carry+Roll KPI 读收益分解（formal）：carry + roll_down 现成返回，不再标"接口未返回"。 */
  const returnDecompQ = useQuery({
    queryKey: [
      "bond-analytics-institutional",
      "return-decomposition-summary",
      client.mode,
      queryReportDate,
      periodType,
    ],
    queryFn: () =>
      client.getBondAnalyticsReturnDecomposition(queryReportDate, periodType, {
        detail: "summary",
      }),
    enabled: Boolean(queryReportDate),
    retry: false,
    staleTime: 60_000,
  });
  /* 正式 KRD 读面：接口数据齐备（桶 DV01 与组合 DV01 勾稽），驾驶舱只点亮状态，明细看下钻 KRD 标签页。 */
  const krdQ = useQuery({
    queryKey: ["bond-analytics-institutional", "krd-curve-risk", client.mode, queryReportDate],
    queryFn: () => client.getBondAnalyticsKrdCurveRisk(queryReportDate),
    enabled: Boolean(queryReportDate),
    retry: false,
    staleTime: 60_000,
  });
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
    // 单序列（市值）条形不再按桶轮播分类色（§4 无语义彩色装饰）：统一走强调单色。
    return [...(maturityQ.data?.result.items ?? [])]
      .flatMap((item) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 7)
      .map(({ item, rawMarketValue }) => ({
        key: item.maturity_bucket,
        label: item.maturity_bucket,
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
      }));
  }, [maturityQ.data]);

  const leadMaturity = maturityItems[0];
  const dashboardAssetItems = useMemo(() => {
    const palette = DISTRIBUTION_CHART_COLORS;
    const assetClassItems = (portfolioHl?.by_asset_class ?? []).slice(0, 4);
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
  }, [portfolioHl?.by_asset_class, assetStructureQ.data]);
  const industryItems = useMemo(() => {
    // 单序列（市值）行条不按行业轮播分类色：统一强调单色（首页分布行制度）。
    return [...(industryQ.data?.result.items ?? [])]
      .flatMap((item) => {
        const rawMarketValue = bondNumericRawOrNull(item.total_market_value);
        return rawMarketValue === null ? [] : [{ item, rawMarketValue }];
      })
      .sort((left, right) => right.rawMarketValue - left.rawMarketValue)
      .slice(0, 8)
      .map(({ item, rawMarketValue }) => ({
        key: item.industry_name,
        label: item.industry_name || "未分类",
        value: rawMarketValue,
        caption: formatYi(item.total_market_value),
      }));
  }, [industryQ.data]);
  const topHoldings = (holdingsQ.data?.result.items ?? []).slice(0, 10);
  const totalActionPnl = bondNumericRaw(actionAttribution?.total_pnl_from_actions ?? null);
  const durationDisplay = Number.isFinite(dur) ? `${dur.toFixed(2)} 年` : EM_DASH;
  const creditWeightDisplay = Number.isFinite(creditWeight) ? `${(creditWeight * 100).toFixed(2)}%` : EM_DASH;
  const marketValueDisplay = k ? formatYi(k.total_market_value) : EM_DASH;
  const unrealizedPnlDisplay = k ? formatYi(k.unrealized_pnl) : EM_DASH;
  const dv01Source = riskQ.data?.result?.total_dv01 ?? portfolioHl?.total_dv01 ?? k?.total_dv01 ?? null;
  const hasDv01Readout = bondNumericRawOrNull(dv01Source) !== null;
  /* KPI 瓦片单行放不下带单位的读数，值只出数字，单位交给 detail；证据位仍用带单位形态。 */
  const dv01Value = hasDv01Readout ? formatDv01Wan(dv01Source) : EM_DASH;
  const dv01Display = hasDv01Readout ? `${dv01Value} 万元/bp` : EM_DASH;
  /* 三源兜底时如实标注实际命中源，避免回退值仍宣称来自风险指标读面。 */
  const dv01SourceLabel = riskQ.data?.result?.total_dv01
    ? "风险指标读面"
    : portfolioHl?.total_dv01
      ? "风险指标未返回，取组合摘要读数"
      : k?.total_dv01
        ? "风险指标未返回，取 headline 读数"
        : "风险指标读面未返回";
  const unrealizedPnlTone =
    k && numOr(k.unrealized_pnl) !== 0 ? (numOr(k.unrealized_pnl) > 0 ? "positive" : "negative") : "default";
  const actionPnlDisplay = actionAttribution ? formatWan(actionAttribution.total_pnl_from_actions) : EM_DASH;
  const actionPnlTone =
    totalActionPnl !== null && Number.isFinite(totalActionPnl) && totalActionPnl !== 0
      ? totalActionPnl > 0
        ? "positive"
        : "negative"
      : "default";
  const periodLabel = PERIOD_OPTIONS.find((option) => option.value === periodType)?.label ?? periodType;
  /* Carry+Roll = 收益分解（formal）的票息 carry + 骑乘 roll_down，单位元，合计后按万展示。 */
  const returnDecomp = returnDecompQ.data?.result ?? null;
  const carryRaw = returnDecomp ? bondNumericRawOrNull(returnDecomp.carry) : null;
  const rollDownRaw = returnDecomp ? bondNumericRawOrNull(returnDecomp.roll_down) : null;
  const carryRollRaw = carryRaw !== null && rollDownRaw !== null ? carryRaw + rollDownRaw : null;
  const carryRollDisplay = carryRollRaw !== null ? formatWan(carryRollRaw) : EM_DASH;
  const carryRollTone =
    carryRollRaw !== null && carryRollRaw !== 0
      ? carryRollRaw > 0
        ? "positive"
        : "negative"
      : "default";
  const carryRollDetail =
    carryRollRaw !== null
      ? `${periodLabel} · 票息+骑乘（收益分解读面）`
      : returnDecompQ.isPending
        ? "收益分解读面加载中"
        : "收益分解读面未返回";
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
  /* caption 已经是「x.xx 亿」市值读数，行条不再挂重复的「规模/市值 …」尾巴。 */
  const maturityRows = maturityItems;
  /* 来源状态上收卡头一处（DESIGN §6 状态去重）：主源可用时行内只留口径词；
     回退/缺失时该行保留如实的回退标注（dv01 三源兜底语义不丢）。 */
  const riskSourceReady = Boolean(riskQ.data?.result);
  const riskSourceNote = riskSourceReady
    ? "来源：风险指标读面"
    : "风险指标读面未返回，以下行按实际命中源标注";
  const durationRiskRow = {
    label: "组合久期",
    value: riskQ.data?.result ? formatDurationDisplay(riskQ.data.result.weighted_duration) : durationDisplay,
    detail: riskSourceReady ? "市值加权" : "风险指标未返回，取 headline 读数",
  };
  const dv01RiskRow = {
    label: "组合 DV01（万元/bp）",
    value: dv01Display,
    detail: riskQ.data?.result?.total_dv01 ? "利率敏感度" : dv01SourceLabel,
  };
  const creditRatioRiskRow = {
    label: "信用占比",
    value: riskQ.data?.result ? formatPct(riskQ.data.result.credit_ratio) : creditWeightDisplay,
    detail: "信用债市值占比",
  };
  const spreadDv01RiskRow = {
    label: "利差 DV01（万元/bp）",
    value: riskQ.data?.result ? `${formatDv01Wan(riskQ.data.result.total_spread_dv01)} 万元/bp` : EM_DASH,
    detail: "信用利差敏感度",
  };
  const riskRows = [durationRiskRow, dv01RiskRow, creditRatioRiskRow, spreadDv01RiskRow];
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
  /* 技术告警码（全 ASCII）不直接示人，但必须计数披露，不能静默丢弃。 */
  const readableAnomalies = topAnomalies.filter((item) => /[\u3400-\u9fff]/u.test(item));
  const shownAnomalies = readableAnomalies.slice(0, 2);
  const hiddenAnomalyCount = topAnomalies.length - shownAnomalies.length;
  const todayFocusItems = actionAttributionPending
    ? ["异常信号读取中，暂不下无异常结论。"]
    : shownAnomalies.length > 0
      ? hiddenAnomalyCount > 0
        ? [...shownAnomalies, `另有 ${hiddenAnomalyCount} 条信号未在此列示，见证据下钻。`]
        : shownAnomalies
      : topAnomalies.length > 0
        ? [`${topAnomalies.length} 条技术告警未在此列示，见证据下钻。`]
        : ["暂无新增异常"];

  return (
    <section data-testid="bond-analysis-phase3-cockpit" className={styles.phaseSection}>
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <section data-testid="bond-analysis-reference-dashboard" className={styles.referenceDashboard}>
        <ReferenceMarketTicker series={macroSeries} unavailable={macroUnavailable} />

        <section data-testid="bond-analysis-reference-topbar" className={styles.heroSection}>
          <div className={styles.heroIdentity}>
            <h2 className={styles.heroTitle}>01 本日判断</h2>
            <span className={styles.heroReportDate}>报告日 {topbarReportDate}</span>
          </div>

          <div data-testid="bond-analysis-cockpit-conclusion" className={styles.heroMain}>
            <div className={styles.heroConclusion}>
              <strong className={styles.heroHeadline}>{conclusion.body}</strong>
              <p className={styles.heroDetail}>{conclusion.detail}</p>
            </div>
            <div
              data-testid="bond-analysis-daily-judgment"
              className={styles.heroConclusionMeta}
            >
              <span>
                报告日 {topbarReportStatus} · {topbarReportDate}
              </span>
              <span>
                核心读面 {topbarReadoutStatus} · {topbarReadoutDetail}
              </span>
            </div>
          </div>
        </section>

        <div className={styles.holdingsKpiRail}>
          {/* 常态零徽标（首页 2026-08-13 降噪制度）：就绪读数不再挂「已读」，仅缺口/待读面发声。 */}
          <InstitutionalKpiRail testId="bond-analysis-kpi-ribbon" columns={7} flush>
            <InstitutionalKpiTile label="久期" value={durationDisplay} detail={leadMaturity ? `最重期限桶 ${leadMaturity.label}` : "期限结构待读面"} status={Number.isFinite(dur) ? undefined : "待读面"} priority="primary" />
            {/* 收益率是水平值非变动量：去前导 +（变动量读数仍走 formatSignedPct 保符号）。 */}
            <InstitutionalKpiTile label="组合到期收益率" value={k ? stripLeadingPlus(formatPct(k.weighted_ytm)) : EM_DASH} detail={previousK ? `上期 ${stripLeadingPlus(formatPct(previousK.weighted_ytm))}` : "收益率待读面"} status={k ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="信用债收益率中位数" value={formatSpreadYtmPctDisplay(spreadMedian)} detail="信用债 YTM 中位数，非对基准利差" status={Number.isFinite(spreadMedianBp) ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="DV01（万元/bp）" value={dv01Value} detail={dv01SourceLabel} status={hasDv01Readout ? undefined : "待读面"} priority="primary" />
            <InstitutionalKpiTile label="Carry+Roll" value={carryRollDisplay} detail={carryRollDetail} status={carryRollRaw !== null ? undefined : "待读面"} tone={carryRollTone} />
            <InstitutionalKpiTile label="动作归因损益" value={actionPnlDisplay} detail={actionAttribution ? `${periodLabel} · ${actionAttribution.total_actions} 笔动作` : "动作归因待读面"} status={actionAttribution ? undefined : "待读面"} tone={actionPnlTone} />
            <InstitutionalKpiTile label="未实现损益" value={unrealizedPnlDisplay} detail={`存量浮盈（非本期损益）· 较上期 ${formatSignedPct(unrealizedPnlMomPct)}`} status={k ? undefined : "待读面"} tone={unrealizedPnlTone} />
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
            krdBucketCount={krdQ.data?.result?.krd_buckets?.length ?? null}
            krdPending={krdQ.isPending}
          />
          <div className={styles.referenceAnalysisSideStack}>
            <Card
              variant="borderless"
              size="small"
              title={<SectionCardTitle eyebrow="证据边界" title="利率 / 曲线 / 信用 / 资金" />}
              data-testid="bond-analysis-evidence-boundary-panel"
              className={`${styles.dashboardCard} ${styles.referencePanelCard}`}
              styles={{ body: cardBodyStyle }}
            >
              <ReferenceJudgmentMatrix
                duration={dur}
                creditWeight={creditWeight}
                spreadMedianBp={spreadMedianBp}
                hasDv01Readout={hasDv01Readout}
                hasCurveReadout={hasYieldCurveReadout}
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
            <div className={styles.structureConcentration}>
              <span>行业集中度</span>
              <DistributionRows items={industryItems.slice(0, 4)} emptyText="暂无发行人/行业读面" />
            </div>
            {portfolioHeadlinesUnavailable ? <div className={styles.moduleNote}>{PORTFOLIO_HEADLINES_STRUCTURE_NOTE}</div> : null}
            {portfolioHeadlinesUnavailable ? <div className={styles.moduleNote}>{PORTFOLIO_HEADLINES_CREDIT_NOTE}</div> : null}
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="风险切片" title="久期 / DV01 / 信用" />}
            data-testid="bond-analysis-risk-monitor"
            className={`${styles.dashboardCard} ${styles.referenceDistributionSupportCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <div data-testid="bond-analysis-risk-slice-stack" className={styles.riskEvidenceList}>
              <div data-testid="bond-analysis-risk-source-note" className={styles.riskEvidenceSource}>
                {riskSourceNote}
              </div>
              {riskRows.map((row) => (
                <div key={row.label} className={styles.riskEvidenceRow}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                  <small>{row.detail}</small>
                </div>
              ))}
              <div data-testid="bond-analysis-risk-guardrails" className={styles.riskEvidenceGuardrail}>
                <div className={styles.riskEvidenceBoundary}>
                  只列后端返回风险字段；缺失保持证据缺口，不延伸为审批或阈值结论。
                </div>
                <Button size="small" type="text" data-testid="bond-analysis-home-open-credit-spread" onClick={() => onOpenModuleDetail?.("credit-spread")}>
                  打开信用利差
                </Button>
              </div>
            </div>
          </Card>

          <Card
            variant="borderless"
            size="small"
            title={<SectionCardTitle eyebrow="今日焦点" title="动作与异常" />}
            data-testid="bond-analysis-today-focus"
            className={`${styles.dashboardCard} ${styles.referenceDistributionSupportCard}`}
            styles={{ body: cardBodyStyle }}
          >
            <div className={styles.todayFocusPanel}>
              {/* 读数去重（DESIGN §6 ≤2 处）：估值收益/动作归因金额已在 KPI 带与归因面板可见，
                  本卡改增量信息（环比 / 笔数），完整金额收进 title 供复核。 */}
              <div
                data-testid="bond-analysis-summary-card"
                className={styles.todayFocusMetric}
                title={`本期估值收益 ${unrealizedPnlDisplay}`}
              >
                <span>本期估值收益</span>
                <strong>{Number.isFinite(unrealizedPnlMomPct) ? `较上期 ${formatSignedPct(unrealizedPnlMomPct)}` : EM_DASH}</strong>
                <small>{Number.isFinite(unrealizedPnlMomPct) ? "存量浮盈环比" : "收益时序证据待返回"}</small>
              </div>
              <div
                className={styles.todayFocusAction}
                title={actionAttribution ? `动作归因损益 ${actionPnlDisplay}` : undefined}
              >
                <span>动作归因</span>
                <strong>{actionAttribution ? `${actionAttribution.total_actions} 笔动作` : EM_DASH}</strong>
                <small>{actionAttribution ? "本期动作数" : "动作归因待返回"}</small>
              </div>
              {decisionRail && onOpenModuleDetail ? (
                <div data-testid="bond-analysis-decision-rail" className={styles.todayFocusDecision}>
                  <div data-testid="bond-analysis-decision-trust">
                    <span>当前下钻</span>
                    <strong>{decisionRail.activeModuleContext.label}</strong>
                    <small>{decisionRail.activeModuleContext.description}</small>
                  </div>
                  <Button
                    size="small"
                    type="text"
                    data-testid="bond-analysis-decision-next-action"
                    onClick={() => onOpenModuleDetail(decisionRail.activeModuleContext.key)}
                  >
                    打开
                  </Button>
                </div>
              ) : null}
              <div className={styles.todayFocusList}>
                {todayFocusItems.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
              <div data-testid="bond-analysis-return-trend-boundary" className={styles.footerEvidenceNote}>
                收益时序未返回：不绘制趋势占位。
              </div>
              <div className={styles.footerActionBar}>
                <span>保留返回事实与缺口，不补造趋势。</span>
                <Button size="small" type="text" data-testid="bond-analysis-home-open-return-decomposition" onClick={() => onOpenModuleDetail?.("return-decomposition")}>
                  打开收益拆解
                </Button>
              </div>
            </div>
          </Card>
        </section>

        <div className={styles.referenceBottomGrid}>
          <div data-testid="bond-analysis-event-calendar" className={styles.referenceCalendarPanel}>
            <BondEventCalendar
              items={calendarItems}
              isLoading={calendarLoading}
              hasError={calendarError}
            />
          </div>
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
            {topHoldingsUnavailable ? <div className={styles.moduleNote}>{TOP_HOLDINGS_RATING_NOTE}</div> : null}
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
      </section>
    </section>
  );
}
