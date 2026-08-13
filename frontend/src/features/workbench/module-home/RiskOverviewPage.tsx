import { Suspense, lazy, useCallback, useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { isAgentFrontendEnabled } from "../../../app/navigation";
import { EM_DASH } from "../../../utils/format";
import {
  formatYieldCurveDateSummary,
  summarizeYieldCurveDates,
} from "../../../lib/yieldCurveDateSummary";
import {
  buildModuleHomeView,
  type ModuleHomeTone,
} from "./moduleHomeModel";
import {
  moduleWorkbenchHomeConfigs,
  type ModuleWorkbenchHomeKind,
} from "./moduleHomeConfig";
import {
  buildRiskV6Briefs,
  buildRiskV6CashflowTrack,
  buildRiskV6DetailTables,
  buildRiskV6Hero,
  buildRiskV6KpiCards,
  buildRiskV6KrdBars,
  buildRiskV6LineageRows,
  buildRiskV6YieldCurveChart,
  buildRiskBondComparisonPlan,
  buildRiskBondDv01Summary,
  type RiskBondComparisonReadout,
  type RiskBondHistoryObservation,
  type RiskBondMetricKey,
  type RiskV6CurveTone,
  type RiskV6KpiCard,
} from "./riskHomeAdapter";
import dh from "../dashboard-home/dashboardHomeShell.module.css";
import styles from "./riskOverview.module.css";

const LazyRiskOverviewAgentDrawer = lazy(() =>
  import("./RiskOverviewAgentDrawer").then((module) => ({
    default: module.RiskOverviewAgentDrawer,
  })),
);

type RiskOverviewPageProps = {
  kind?: ModuleWorkbenchHomeKind;
};

const BOND_EVIDENCE_TOP_N = 1;
const BOND_EVIDENCE_SHOCK_BPS = "1";
const BOND_EVIDENCE_CLASSES = ["OCI", "TPL"] as const;

function dhStateClass(tone: ModuleHomeTone): string {
  if (tone === "ok") return dh.dhApiStateOk;
  if (tone === "error") return dh.dhApiStateBad;
  if (tone === "watch") return dh.dhApiStateWarn;
  return dh.dhApiStateMuted;
}

function roToneClass(tone: ModuleHomeTone): string {
  if (tone === "ok") return styles.roToneOk;
  if (tone === "watch") return styles.roToneWatch;
  if (tone === "error") return styles.roToneError;
  return styles.roToneMuted;
}

function v6PillClass(tone: ModuleHomeTone): string {
  if (tone === "ok") return styles.roV6Pill;
  if (tone === "watch") return `${styles.roV6Pill} ${styles.roV6PillWarn}`;
  if (tone === "error") return `${styles.roV6Pill} ${styles.roV6PillBad}`;
  return `${styles.roV6Pill} ${styles.roV6PillMut}`;
}

function curveToneClass(tone: RiskV6CurveTone): string {
  if (tone === "amber") return styles.roV6CurveAmber;
  if (tone === "acc") return styles.roV6CurveAcc;
  return styles.roV6CurveInk;
}

/* ── 债券分析辅助证据（OCI / TPL 独立状态） ───────────────────── */
type RiskBondDv01Summary = ReturnType<typeof buildRiskBondDv01Summary>;
type RiskBondComparisonPeriod = "mom" | "yoy";

function bondSummaryTone(summary: RiskBondDv01Summary): ModuleHomeTone {
  if (summary.state === "ready") return "ok";
  if (summary.state === "review") return "watch";
  if (summary.state === "error" || summary.state === "blocked") return "error";
  return "muted";
}

function BondMetricComparison({
  summaryKey,
  metricKey,
  period,
  readout,
  unavailableText,
}: {
  summaryKey: RiskBondDv01Summary["key"];
  metricKey: RiskBondMetricKey;
  period: RiskBondComparisonPeriod;
  readout: RiskBondComparisonReadout | undefined;
  unavailableText: string;
}) {
  const label = period === "mom" ? "系统环比" : "系统同比";
  const absoluteText =
    !readout || readout.state === "unavailable"
      ? unavailableText
      : readout.absoluteText;
  return (
    <div
      className={styles.roBondComparison}
      data-state={readout?.state ?? "unavailable"}
      data-testid={`risk-overview-${summaryKey}-${metricKey}-${period}`}
    >
      <span>{label}</span>
      <strong className={styles.roNum}>{absoluteText}</strong>
      <em className={styles.roNum}>{readout?.percentText ?? EM_DASH}</em>
    </div>
  );
}

function formatBondTrendValue(value: number): string {
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function BondDv01Trend({
  summary,
  comparisonLoading,
}: {
  summary: RiskBondDv01Summary;
  comparisonLoading: boolean;
}) {
  const trend = summary.trend;
  const availablePointCount = trend?.points.length ?? 0;
  const expectedPointCount = trend?.dates.length ?? 6;
  const segmentCount = trend?.linePaths.length ?? 0;
  const dateRange =
    trend && trend.dates.length > 0
      ? `${trend.dates[0]} → ${trend.dates[trend.dates.length - 1]}`
      : "基期日期待接入";
  const emptyText =
    (comparisonLoading ? "系统口径近 6 个报告月趋势读取中。" : trend?.notices[0]) ??
    (trend === null
      ? "系统口径近 6 个报告月趋势待接入。"
      : "系统口径近 6 个报告月数据不完整，暂不连线。");
  const firstPoint = trend?.points[0];
  const lastPoint = trend?.points[trend.points.length - 1];
  const valueRangeLabel = trend?.sparkline
    ? "期初 → 本期"
    : availablePointCount > 1
      ? "首个有效点 → 最近有效点"
      : "有效点";
  const valueRangeText =
    trend && firstPoint && lastPoint
      ? availablePointCount > 1
        ? `${formatBondTrendValue(firstPoint.value)} → ${formatBondTrendValue(lastPoint.value)} ${trend.unit}`
        : `${formatBondTrendValue(firstPoint.value)} ${trend.unit}`
      : "暂无有效月末点";
  const trendNoticeText =
    trend && trend.notices.length > 0
      ? availablePointCount === expectedPointCount
        ? `历史趋势含 ${trend.notices.length} 条待复核提示。`
        : `${trend.notices[0]}${
            trend.notices.length > 1
              ? ` 另有 ${trend.notices.length - 1} 条待复核提示。`
              : ""
          }`
      : null;

  return (
    <div
      className={styles.roBondTrend}
      data-expected-points={expectedPointCount}
      data-point-count={availablePointCount}
      data-segment-count={segmentCount}
      data-state={trend?.state ?? "unavailable"}
      data-testid={`risk-overview-${summary.key}-dv01-trend`}
    >
      <div className={styles.roBondTrendHead}>
        <b>系统口径 · 近 6 个报告月 DV01 趋势</b>
        <span>{trend?.unit ?? "万元/bp"}</span>
      </div>
      {trend && trend.points.length > 0 ? (
        <svg
          aria-label={`${summary.title}系统口径近 6 个报告月 DV01 趋势`}
          className={styles.roBondTrendSvg}
          preserveAspectRatio="none"
          role="img"
          data-testid={`risk-overview-${summary.key}-dv01-trend-plot`}
          viewBox="0 0 96 30"
        >
          {trend.sparkline ? (
            <path className={styles.roBondTrendArea} d={trend.sparkline.areaPath} />
          ) : null}
          {trend.linePaths.map((linePath, segmentIndex) => (
            <path
              className={styles.roBondTrendLine}
              d={linePath}
              data-segment-index={segmentIndex}
              data-testid={`risk-overview-${summary.key}-dv01-trend-segment-${segmentIndex}`}
              key={`${segmentIndex}-${linePath}`}
            />
          ))}
          {trend.points.map((point) => (
            <circle
              className={styles.roBondTrendDot}
              cx={point.x}
              cy={point.y}
              data-report-date={point.reportDate}
              data-slot-index={point.slotIndex}
              data-testid={`risk-overview-${summary.key}-dv01-trend-point-${point.slotIndex}`}
              data-value={point.value}
              key={point.reportDate}
              r="2.2"
            />
          ))}
        </svg>
      ) : (
        <p className={styles.roBondTrendEmpty}>{emptyText}</p>
      )}
      <div className={styles.roBondTrendDates}>
        <span>{dateRange}</span>
        <span>{availablePointCount}/{expectedPointCount} 点</span>
      </div>
      <div className={styles.roBondTrendValues}>
        <span>{valueRangeLabel}</span>
        <b className={styles.roNum}>{valueRangeText}</b>
      </div>
      {trendNoticeText && trend && trend.points.length > 0 ? (
        <p className={styles.roBondTrendNotice}>{trendNoticeText}</p>
      ) : null}
    </div>
  );
}

function BondEvidenceCard({
  summary,
  comparisonLoading,
}: {
  summary: RiskBondDv01Summary;
  comparisonLoading: boolean;
}) {
  const tone = bondSummaryTone(summary);
  const currentNotices = summary.notices.filter(
    (notice) => !/^\d{4}-\d{2}-\d{2}：/.test(notice),
  );
  const historyNotices = summary.notices.filter((notice) =>
    /^\d{4}-\d{2}-\d{2}：/.test(notice),
  );
  const visibleNotices = [...currentNotices, ...historyNotices.slice(0, 2)];
  const hiddenHistoryNoticeCount = Math.max(0, historyNotices.length - 2);
  const comparisonUnavailableText = comparisonLoading ? "读取中" : "基期不可用";

  return (
    <article
      className={`${styles.roBondCard} ${styles[`roBondCard${summary.state}`] ?? ""}`}
      data-testid={`risk-overview-${summary.key}`}
    >
      <div className={styles.roBondCardHead}>
        <div>
          <span>{summary.accountingClass}</span>
          <h3>{summary.title}</h3>
        </div>
        <span className={v6PillClass(tone)}>
          <i aria-hidden="true" />
          {summary.statusLabel}
        </span>
      </div>

      {summary.metrics.length > 0 ? (
        <div className={styles.roBondMetrics}>
          {summary.metrics.map((metric) => {
            const comparison = summary.comparisons[metric.key];
            return (
              <div className={styles.roBondMetric} key={metric.key}>
                <span>{metric.label}</span>
                <strong className={styles.roNum}>
                  {metric.value} <small>{metric.unit}</small>
                </strong>
                <div className={styles.roBondComparisonGrid}>
                  <BondMetricComparison
                    metricKey={metric.key}
                    period="mom"
                    readout={comparison?.mom}
                    summaryKey={summary.key}
                    unavailableText={comparisonUnavailableText}
                  />
                  <BondMetricComparison
                    metricKey={metric.key}
                    period="yoy"
                    readout={comparison?.yoy}
                    summaryKey={summary.key}
                    unavailableText={comparisonUnavailableText}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className={styles.roBondState}>{summary.statusLabel}</p>
      )}

      <div className={styles.roBondComparisonBasis}>
        <span>系统比较基期</span>
        <b>
          {comparisonLoading
            ? "精确月末基期读取中。"
            : summary.comparisonBasisText}
        </b>
      </div>
      <BondDv01Trend
        comparisonLoading={comparisonLoading}
        summary={summary}
      />
      <div className={styles.roBondMeta}>
        <span>报告日</span>
        <b className={styles.roNum}>{summary.reportDate ?? EM_DASH}</b>
      </div>
      {summary.notices.length > 0 ? (
        <div className={styles.roBondNotices}>
          {visibleNotices.map((notice) => (
            <p key={notice}>{notice}</p>
          ))}
          {hiddenHistoryNoticeCount > 0 ? (
            <p>另有 {hiddenHistoryNoticeCount} 条历史基期提示未逐条展开。</p>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

/* ── KPI 曜石卡（渐变描边 ::before mask + 渐变数字 + 辉光走势 + 涨跌胶囊） ── */
function V6KpiCardView({ card }: { card: RiskV6KpiCard }) {
  return (
    <article
      className={`${styles.roV6Kpi} ${card.alert ? styles.roV6KpiAlert : ""}`}
      data-testid={`risk-overview-kpi-${card.key}`}
    >
      <div className={styles.roV6KpiCap}>
        <span className={styles.roV6KpiCapText} title={card.label}>
          {card.label}
        </span>
        <i className={card.alert ? styles.roV6CapDotBad : styles.roV6CapDot} aria-hidden="true" />
      </div>
      <div
        className={`${styles.roV6KpiNum} ${card.valuePresent ? "" : styles.roV6KpiNumVoid}`}
        title={card.valuePresent ? `${card.amount}${card.unit ? ` ${card.unit}` : ""}` : "待接入"}
      >
        {card.amount}
        {card.unit ? <small> {card.unit}</small> : null}
      </div>
      {card.sparkline ? (
        <svg
          className={styles.roV6Spark}
          viewBox="0 0 96 30"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path className={styles.roV6SparkArea} d={card.sparkline.areaPath} />
          <path className={styles.roV6SparkLine} d={card.sparkline.linePath} />
          <circle
            className={styles.roV6SparkHalo}
            cx={card.sparkline.endX}
            cy={card.sparkline.endY}
            r="5.5"
          />
          <circle
            className={styles.roV6SparkDot}
            cx={card.sparkline.endX}
            cy={card.sparkline.endY}
            r="2.2"
          />
        </svg>
      ) : (
        <div className={styles.roV6SparkEmpty}>近 24 期序列待接入</div>
      )}
      <div className={styles.roV6KpiFoot}>
        {card.delta ? (
          <span className={styles.roV6KpiChip}>{card.delta.text}</span>
        ) : (
          <span className={styles.roV6KpiChipVoid}>—</span>
        )}
        <span className={styles.roV6KpiSub} title={card.caption}>
          {card.caption}
        </span>
      </div>
    </article>
  );
}

export default function RiskOverviewPage({ kind = "risk" }: RiskOverviewPageProps) {
  const client = useApiClient();
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [agentPanelMounted, setAgentPanelMounted] = useState(false);

  const openAgentPanel = useCallback(() => {
    setAgentPanelMounted(true);
    setAgentPanelOpen(true);
  }, []);

  const riskDatesQuery = useQuery({
    queryKey: ["risk-overview", "risk-dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    retry: false,
    staleTime: 60_000,
  });
  const riskReportDate = riskDatesQuery.data?.result.report_dates[0] ?? "";
  const blockedReportDates = riskDatesQuery.data?.result.blocked_report_dates ?? [];
  const bondDatesQuery = useQuery({
    queryKey: ["risk-overview", "bond-analytics-dates", client.mode],
    queryFn: () => client.getBondAnalyticsDates(),
    retry: false,
    staleTime: 60_000,
  });
  const bondComparisonPlan = useMemo(
    () =>
      buildRiskBondComparisonPlan(
        riskReportDate,
        bondDatesQuery.data?.result.report_dates ?? [],
      ),
    [riskReportDate, bondDatesQuery.data],
  );
  const latestBlocked =
    blockedReportDates.length > 0
      ? [...blockedReportDates].sort((a, b) =>
          b.report_date.localeCompare(a.report_date),
        )[0]
      : undefined;
  const riskTensorQuery = useQuery({
    queryKey: ["risk-overview", "risk-tensor", client.mode, riskReportDate],
    queryFn: () => client.getRiskTensor(riskReportDate),
    enabled: Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const cashflowQuery = useQuery({
    queryKey: ["risk-overview", "cashflow", client.mode, riskReportDate],
    queryFn: () => client.getCashflowProjection(riskReportDate),
    enabled: Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const riskHistoryQuery = useQuery({
    queryKey: ["risk-overview", "risk-tensor-history", client.mode, riskReportDate],
    queryFn: () => client.getRiskTensorHistory(riskReportDate, 24),
    enabled: Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const yieldCurveQuery = useQuery({
    queryKey: ["risk-overview", "yield-curve-term", client.mode, riskReportDate],
    queryFn: () =>
      client.getBondAnalyticsYieldCurveTermStructure(riskReportDate, {
        curveTypes: "treasury,cdb,aaa_credit",
      }),
    enabled: Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondOciQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Risk(
      client.mode,
      riskReportDate,
      "OCI",
      BOND_EVIDENCE_TOP_N,
      BOND_EVIDENCE_SHOCK_BPS,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01Risk(riskReportDate, {
        accountingClass: "OCI",
        topN: BOND_EVIDENCE_TOP_N,
        shockBps: BOND_EVIDENCE_SHOCK_BPS,
      }),
    enabled: Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const bondTplQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Risk(
      client.mode,
      riskReportDate,
      "TPL",
      BOND_EVIDENCE_TOP_N,
      BOND_EVIDENCE_SHOCK_BPS,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01Risk(riskReportDate, {
        accountingClass: "TPL",
        topN: BOND_EVIDENCE_TOP_N,
        shockBps: BOND_EVIDENCE_SHOCK_BPS,
      }),
    enabled: Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondHistoryRequests = useMemo(
    () =>
      bondComparisonPlan.requestDates
        .filter((reportDate) => reportDate !== riskReportDate)
        .flatMap((reportDate) =>
          BOND_EVIDENCE_CLASSES.map((accountingClass) => ({
            accountingClass,
            reportDate,
          })),
        ),
    [bondComparisonPlan.requestDates, riskReportDate],
  );
  const bondHistoryQueries = useQueries({
    queries: bondHistoryRequests.map(({ accountingClass, reportDate }) => ({
      queryKey: apiQueryKeys.bondAnalyticsDv01Risk(
        client.mode,
        reportDate,
        accountingClass,
        BOND_EVIDENCE_TOP_N,
        BOND_EVIDENCE_SHOCK_BPS,
      ),
      queryFn: () =>
        client.getBondAnalyticsDv01Risk(reportDate, {
          accountingClass,
          topN: BOND_EVIDENCE_TOP_N,
          shockBps: BOND_EVIDENCE_SHOCK_BPS,
        }),
      enabled: bondComparisonPlan.enabled,
      retry: false,
      staleTime: 60_000,
    })),
  });

  const config = moduleWorkbenchHomeConfigs[kind];
  const view = useMemo(
    () =>
      buildModuleHomeView(kind, client, {
        riskDates: riskDatesQuery,
        riskTensor: riskTensorQuery,
        cashflow: cashflowQuery,
      }),
    [kind, client, riskDatesQuery, riskTensorQuery, cashflowQuery],
  );

  const bondHistoryByClass = useMemo(() => {
    const observations: Record<
      (typeof BOND_EVIDENCE_CLASSES)[number],
      RiskBondHistoryObservation[]
    > = { OCI: [], TPL: [] };
    bondHistoryRequests.forEach((request, index) => {
      const query = bondHistoryQueries[index];
      observations[request.accountingClass].push({
        reportDate: request.reportDate,
        envelope: query?.data,
        error: query?.error,
        isLoading: query?.isLoading ?? false,
      });
    });
    return observations;
  }, [bondHistoryQueries, bondHistoryRequests]);

  const bondOciSummary = useMemo(
    () =>
      buildRiskBondDv01Summary({
        accountingClass: "OCI",
        reportDate: riskReportDate,
        envelope: bondOciQuery.data,
        isLoading: riskDatesQuery.isLoading || bondOciQuery.isLoading,
        error: bondOciQuery.error ?? riskDatesQuery.error,
        comparisonPlan: bondComparisonPlan,
        history: bondHistoryByClass.OCI,
      }),
    [
      riskReportDate,
      riskDatesQuery.isLoading,
      riskDatesQuery.error,
      bondOciQuery.data,
      bondOciQuery.isLoading,
      bondOciQuery.error,
      bondComparisonPlan,
      bondHistoryByClass.OCI,
    ],
  );
  const bondTplSummary = useMemo(
    () =>
      buildRiskBondDv01Summary({
        accountingClass: "TPL",
        reportDate: riskReportDate,
        envelope: bondTplQuery.data,
        isLoading: riskDatesQuery.isLoading || bondTplQuery.isLoading,
        error: bondTplQuery.error ?? riskDatesQuery.error,
        comparisonPlan: bondComparisonPlan,
        history: bondHistoryByClass.TPL,
      }),
    [
      riskReportDate,
      riskDatesQuery.isLoading,
      riskDatesQuery.error,
      bondTplQuery.data,
      bondTplQuery.isLoading,
      bondTplQuery.error,
      bondComparisonPlan,
      bondHistoryByClass.TPL,
    ],
  );
  const bondComparisonHistoryLoading = bondHistoryQueries.some(
    (query) => query.isLoading,
  );
  const bondComparisonHistoryError = bondHistoryQueries.some(
    (query) => query.isError && query.data === undefined,
  );
  const bondCurrentLoading =
    riskDatesQuery.isLoading ||
    bondOciQuery.isLoading ||
    bondTplQuery.isLoading;
  const currentSnapshotDisabledText =
    "系统口径快照比较未启用：当前快照为回退或日期与请求月末不一致。";
  const disabledComparisonClasses = [
    { label: "OCI", summary: bondOciSummary },
    { label: "TPL", summary: bondTplSummary },
  ].filter(
    ({ summary }) =>
      summary.metrics.length > 0 &&
      summary.comparisonBasisText.startsWith(currentSnapshotDisabledText),
  );
  const anyComparisonReview = [bondOciSummary, bondTplSummary].some(
    (summary) =>
      summary.trend?.state === "review" ||
      Object.values(summary.comparisons).some(
        (comparison) =>
          comparison.mom.state === "review" ||
          comparison.yoy.state === "review",
      ),
  );
  const comparisonLoading =
    bondDatesQuery.isLoading ||
    bondCurrentLoading ||
    bondComparisonHistoryLoading;
  const comparisonPlanDisabled = !bondComparisonPlan.enabled;
  const bothComparisonClassesDisabled = disabledComparisonClasses.length === 2;
  const oneComparisonClassDisabled = disabledComparisonClasses.length === 1;
  const disabledComparisonClassLabel = disabledComparisonClasses[0]?.label;
  const availableComparisonClassLabel =
    disabledComparisonClassLabel === "OCI" ? "TPL" : "OCI";
  const bondComparisonStatusState = comparisonLoading
    ? "loading"
    : bondDatesQuery.isError ||
        comparisonPlanDisabled ||
        bondComparisonHistoryError ||
        bothComparisonClassesDisabled
      ? "unavailable"
      : oneComparisonClassDisabled || anyComparisonReview
        ? "review"
        : "ready";
  const bondComparisonStatusText = comparisonLoading
    ? "系统环比、系统同比基期与近 6 个报告月趋势读取中。"
    : bondDatesQuery.isError
      ? "债券报告日读取失败；当前值仍可读取，系统比较与趋势暂不可用。"
      : comparisonPlanDisabled
        ? bondComparisonPlan.disabledReason ?? bondComparisonPlan.basisText
        : bondComparisonHistoryError
          ? "部分精确月末基期读取失败；当前值仍可读取，失败点不补数。"
          : bothComparisonClassesDisabled
            ? "OCI、TPL 当前快照为回退或日期与请求月末不一致；两类系统环比、系统同比和趋势均已禁用。"
            : oneComparisonClassDisabled
              ? `${disabledComparisonClassLabel} 当前快照为回退或日期与请求月末不一致；${disabledComparisonClassLabel} 系统环比、系统同比和趋势已禁用，${availableComparisonClassLabel} 仍可使用系统比较与趋势。`
              : bondComparisonPlan.basisText;
  const bondOciComparisonLoading =
    bondDatesQuery.isLoading ||
    bondHistoryByClass.OCI.some((observation) => observation.isLoading);
  const bondTplComparisonLoading =
    bondDatesQuery.isLoading ||
    bondHistoryByClass.TPL.some((observation) => observation.isLoading);

  const tensor = riskTensorQuery.data?.result;
  const history = riskHistoryQuery.data?.result;
  const cashflow = cashflowQuery.data?.result;

  const hero = useMemo(() => buildRiskV6Hero(tensor), [tensor]);
  const kpiCards = useMemo(() => buildRiskV6KpiCards(tensor, history), [tensor, history]);
  const briefs = useMemo(() => buildRiskV6Briefs(tensor), [tensor]);
  const krdBars = useMemo(() => buildRiskV6KrdBars(tensor), [tensor]);
  const curveChart = useMemo(
    () => buildRiskV6YieldCurveChart(yieldCurveQuery.data?.result),
    [yieldCurveQuery.data],
  );
  const cashTrack = useMemo(() => buildRiskV6CashflowTrack(tensor), [tensor]);
  const curveDateLabel = useMemo(
    () =>
      formatYieldCurveDateSummary(
        summarizeYieldCurveDates(yieldCurveQuery.data?.result.curves ?? []),
      ),
    [yieldCurveQuery.data?.result.curves],
  );
  const detailTables = useMemo(() => buildRiskV6DetailTables(tensor, cashflow), [tensor, cashflow]);
  const lineageRows = useMemo(
    () => buildRiskV6LineageRows(riskTensorQuery.data?.result_meta),
    [riskTensorQuery.data],
  );
  const tensorWarnings = tensor?.warnings ?? [];
  const visibleTensorWarnings = tensorWarnings.slice(0, 3);
  const remainingTensorWarnings = tensorWarnings.slice(3);
  const hotKrdBucket = krdBars.find((bar) => bar.hot)?.bucket;

  const isFetching =
    riskDatesQuery.isFetching ||
    riskTensorQuery.isFetching ||
    cashflowQuery.isFetching ||
    riskHistoryQuery.isFetching ||
    yieldCurveQuery.isFetching ||
    bondDatesQuery.isFetching ||
    bondOciQuery.isFetching ||
    bondTplQuery.isFetching ||
    bondHistoryQueries.some((query) => query.isFetching);

  const refreshAll = () => {
    void riskDatesQuery.refetch();
    void riskTensorQuery.refetch();
    void cashflowQuery.refetch();
    void riskHistoryQuery.refetch();
    void yieldCurveQuery.refetch();
    void bondDatesQuery.refetch();
    void bondOciQuery.refetch();
    void bondTplQuery.refetch();
    bondHistoryQueries.forEach((query) => {
      void query.refetch();
    });
  };

  const reportDate = view.decision?.facts.find((fact) => fact.label === "报告日")?.value ?? EM_DASH;
  const agentPanelFilters = useMemo(
    () => ({
      kind,
      shock_bps: BOND_EVIDENCE_SHOCK_BPS,
      top_n: BOND_EVIDENCE_TOP_N,
      accounting_classes: [...BOND_EVIDENCE_CLASSES],
    }),
    [kind],
  );

  const tones = [
    ...view.kpis.map((kpi) => kpi.tone),
    ...view.statuses.map((status) => status.tone),
  ];
  const grade =
    tones.includes("error")
      ? { label: "承压", tone: "error" as ModuleHomeTone }
      : tones.includes("watch")
        ? { label: "关注", tone: "watch" as ModuleHomeTone }
        : { label: "可控", tone: "ok" as ModuleHomeTone };

  const stateTone: ModuleHomeTone = view.stateLabel === "读取失败" ? "error" : "ok";

  const heroFacts = [
    ...(view.decision?.facts ?? []),
    ...(hero.totalMarketValueYi !== null
      ? [{ label: "总市值", value: `${hero.totalMarketValueYi} 亿元`, tone: "ok" as ModuleHomeTone }]
      : []),
    ...(hero.bondCount !== null
      ? [
          {
            label: "持仓",
            value: `${hero.bondCount.toLocaleString("zh-CN")} 只`,
            tone: "ok" as ModuleHomeTone,
          },
        ]
      : []),
  ];

  return (
    <section
      className={`theme-dh-api ${dh.dhPage} ${dh.dhApiBackedHome} ${styles.roV6Scope}`}
      data-moss-theme-scope="risk-overview"
      data-testid="risk-overview-page"
    >
      <div
        className={`${dh.dhLayout} ${styles.roLayout}`}
        data-testid="risk-overview-layout"
      >
        <div
          className={`${dh.dhMain} ${styles.roMain}`}
          data-testid="risk-overview-main"
        >
          {/* 工具栏 — 首页 dhTopbar 语言：左标题+报告日，右状态胶囊+刷新 */}
          <header className={styles.roTopbar} data-testid="risk-overview-toolbar">
            <div className={styles.roTopbarLeft}>
              <h1 className={styles.roPageTitle}>MOSS 利率风险总览</h1>
              <div className={styles.roTopbarMeta}>
                <span>
                  {reportDate !== EM_DASH ? (
                    <>
                      报告日 <strong className={styles.roNum}>{reportDate}</strong>
                    </>
                  ) : (
                    "暂无数据日"
                  )}
                </span>
                {view.question ? <span title={view.question}>{view.question}</span> : null}
              </div>
            </div>
            <div className={styles.roTopbarRight}>
              <span
                className={styles.roStatusPill}
                data-tone={stateTone}
                title={view.stateDetail}
              >
                <i className={dhStateClass(stateTone)} aria-hidden="true" />
                {view.stateLabel}
              </span>
              <button
                type="button"
                className={`${dh.dhRefreshBtn} ${styles.roShellBtn}`}
                onClick={refreshAll}
                disabled={isFetching}
              >
                {isFetching ? "刷新中…" : "刷新"}
              </button>
              {isAgentFrontendEnabled() ? (
                <button
                  type="button"
                  className={`${dh.dhRefreshBtn} ${styles.roShellBtn}`}
                  data-testid="risk-overview-agent-open"
                  onClick={openAgentPanel}
                  aria-label="打开复核助手"
                >
                  复核助手
                </button>
              ) : null}
            </div>
          </header>

          {/* 质量警示横幅 — 规则版本拦截的报告日 */}
          {blockedReportDates.length > 0 ? (
            <section
              className={styles.roBlockedBand}
              data-testid="risk-overview-blocked-band"
            >
              <span className={styles.roBlockedBadge}>数据陈旧</span>
              <div className={styles.roBlockedBody}>
                <strong>
                  {blockedReportDates.length} 个报告日被规则版本拦截
                  {latestBlocked ? `，最新 ${latestBlocked.report_date}` : ""}
                </strong>
                <span>{latestBlocked?.reason ?? "需重新物化后恢复风险张量读取。"}</span>
              </div>
              <Link className={styles.roBlockedLink} to="/risk-tensor">
                前往风险张量页 →
              </Link>
            </section>
          ) : null}

          {/* 01 风险处置判断（hero 大数字 + 上下文 chips） */}
          <section
            className={styles.roV6Hero}
            data-testid="risk-overview-hero"
            id="risk-overview-actions"
          >
            <div data-testid="risk-overview-decision">
              <div className={styles.roSecHead}>
                <i>01</i>
                <h2>风险处置判断</h2>
                <span>数据来源 风险张量 / 现金流</span>
              </div>
              <div className={styles.roV6HeroGrid}>
                <div>
                  <div className={styles.roV6HeroQ}>利率每变动 1 个基点，组合市值约变动</div>
                  <div
                    className={`${styles.roV6HeroNum} ${
                      hero.dv01Wan === null ? styles.roV6HeroNumVoid : ""
                    }`}
                  >
                    {hero.dv01Wan ?? EM_DASH}
                    {hero.dv01Wan !== null ? <small> 万元</small> : null}
                  </div>
                  {hero.dv01Wan !== null ? (
                    <div className={styles.roV6HeroSub}>
                      ≈ {hero.dv01Yi} 亿元 / bp
                      {hero.peakKrdBucket !== null && hero.peakKrdWan !== null ? (
                        <>
                          {" "}
                          · 峰值敞口位于{" "}
                          <b>
                            {hero.peakKrdBucket}（KRD {hero.peakKrdWan} 万元）
                          </b>
                        </>
                      ) : null}
                      {hero.duration !== null ? `，修正久期 ${hero.duration}` : null}
                      {hero.convexity !== null ? `，凸度 ${hero.convexity}` : null}
                    </div>
                  ) : tensor === undefined ? (
                    <div className={styles.roV6HeroSub}>主链数据读取中…</div>
                  ) : (
                    <div className={styles.roV6HeroSub}>监管 DV01 待接入，不用估值口径回填。</div>
                  )}
                  <p className={styles.roV6HeroLede}>
                    {view.decision?.conclusion ?? "等待数据"} {view.decision?.detail ?? ""}
                  </p>
                  {heroFacts.length > 0 ? (
                    <div className={styles.roV6Facts} data-testid="risk-overview-decision-facts">
                      {heroFacts.map((fact) => (
                        <span key={fact.label}>
                          <i
                            className={fact.tone === "watch" ? styles.roV6FactDotWarn : styles.roV6FactDot}
                            aria-hidden="true"
                          />
                          {fact.label}{" "}
                          <b className={fact.tone === "watch" ? styles.roV6FactWarnText : undefined}>
                            {fact.value}
                          </b>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className={styles.roV6HeroSide}>
                  <div className={styles.roV6Rate}>
                    <div className={styles.roV6RateCap}>组合风险评级</div>
                    <div className={`${styles.roV6RateVal} ${roToneClass(grade.tone)}`}>
                      {grade.label}
                    </div>
                    <div className={styles.roV6RateNote}>组合层面综合信号，由 KPI 与链路状态推导</div>
                  </div>
                  <div className={styles.roV6Gate} data-testid="risk-overview-status-strip">
                    <h3>
                      链路状态<span title={view.stateDetail}>{view.stateDetail}</span>
                    </h3>
                    {view.statuses.map((status) => (
                      <div className={styles.roV6GateRow} key={status.key}>
                        <span>{status.label}</span>
                        <span className={v6PillClass(status.tone)} title={status.detail}>
                          <i aria-hidden="true" />
                          {status.value}
                        </span>
                        {status.tone === "error" ? (
                          <em className={styles.roV6GateDetail}>{status.detail}</em>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section
            aria-labelledby="risk-overview-bond-evidence-title"
            className={styles.roBondEvidence}
            data-manual-comparison="blocked"
            data-testid="risk-overview-bond-evidence"
            id="risk-overview-bond-evidence"
          >
            <div className={styles.roBondEvidenceHead}>
              <div>
                <span>系统正式读面</span>
                <h2 id="risk-overview-bond-evidence-title">债券分析正式口径</h2>
                <p>与上方 Risk Tensor 正式风险结论分开展示；本区只反映系统债券分析口径。</p>
              </div>
              <Link className={styles.roBondEvidenceLink} to="/bond-analysis">
                查看债券分析明细 →
              </Link>
            </div>
            <div className={styles.roBondBoundary}>
              <span>630 对账状态</span>
              <b>不可直接比较：金额列定义不同，TPL 还缺分账簿与市值型基金正式源。</b>
              <em>以下数值、环比、同比和趋势仅代表系统正式债券分析口径，不替代 630 手工小计或监管 DV01。</em>
            </div>
            <div
              className={styles.roBondPlanState}
              data-state={bondComparisonStatusState}
              data-testid="risk-overview-bond-comparison-status"
            >
              <span>系统比较与趋势</span>
              <b>{bondComparisonStatusText}</b>
            </div>
            <div className={styles.roBondGrid}>
              <BondEvidenceCard
                comparisonLoading={bondOciComparisonLoading}
                summary={bondOciSummary}
              />
              <BondEvidenceCard
                comparisonLoading={bondTplComparisonLoading}
                summary={bondTplSummary}
              />
            </div>
          </section>

          {/* 曜石 KPI 卡 ×8 */}
          <section className={styles.roV6Kpis} data-testid="risk-overview-kpi-strip">
            {kpiCards.length > 0 ? (
              kpiCards.map((card) => <V6KpiCardView card={card} key={card.key} />)
            ) : (
              <div className={styles.roEmptyState}>
                <i className={styles.roEmptyGlyph} aria-hidden="true" />
                <p className={styles.roV6EmptyText}>风险张量未返回，KPI 待接入。</p>
              </div>
            )}
          </section>
          {kpiCards.length > 0 ? (
            history ? (
              <div className={styles.roV6SparkCap} data-testid="risk-overview-sparkcap">
                走势为近 {history.points.length} 期真实读数（{history.window.from} →{" "}
                {history.window.to}）· 血缘版本见 04
              </div>
            ) : (
              <div className={styles.roV6SparkCap} data-testid="risk-overview-sparkcap">
                近 24 期序列未返回，走势与涨跌胶囊暂不展示，不使用前端补数。
              </div>
            )
          ) : null}

          {/* 02 风险截面摘要（开放三栏） */}
          <section data-testid="risk-overview-briefings" id="risk-overview-briefings">
            <div className={styles.roSecHead}>
              <i>02</i>
              <h2>风险截面摘要</h2>
              <span>字段级读数，不在首页补算</span>
            </div>
            <div className={styles.roV6BriefGrid}>
              {briefs.map((brief) => (
                <article className={styles.roV6Brief} key={brief.key}>
                  <div className={styles.roV6BriefT}>{brief.title}</div>
                  <div className={styles.roV6BriefC}>{brief.body}</div>
                  <div className={styles.roV6BriefE}>{brief.note}</div>
                </article>
              ))}
            </div>
          </section>

          {/* 03 风险证据链 */}
          <section data-testid="risk-overview-evidence" id="risk-overview-evidence">
            <div className={styles.roSecHead}>
              <i>03</i>
              <h2>风险证据板</h2>
              <span>KRD / 收益率曲线 / 现金流窗口 / 字段级明细</span>
            </div>
            <div className={styles.roV6Duo}>
              <div className={styles.roV6Panel} data-testid="risk-overview-krd-panel">
                <div className={styles.roV6PanelHead}>
                  <b>KRD 分布</b>
                  <span>DV01 贡献 · 万元</span>
                </div>
                {krdBars.length > 0 ? (
                  <>
                    {krdBars.map((bar) => (
                      <div className={styles.roV6KrdRow} key={bar.bucket}>
                        <span
                          className={`${styles.roV6KrdBk} ${bar.hot ? styles.roV6KrdHot : ""}`}
                        >
                          {bar.bucket}
                        </span>
                        <span className={styles.roV6KrdTrack} aria-hidden="true">
                          <svg
                            className={styles.roV6KrdSvg}
                            preserveAspectRatio="none"
                            viewBox="0 0 100 11"
                          >
                            <rect
                              className={`${styles.roV6KrdBar} ${bar.hot ? styles.roV6KrdBarHot : ""}`}
                              height="11"
                              rx="4"
                              width={bar.widthPct}
                              x="0"
                              y="0"
                            />
                            <rect
                              className={`${styles.roV6KrdBarTip} ${bar.hot ? styles.roV6KrdBarTipHot : ""}`}
                              height="7"
                              rx="1.4"
                              width="2.8"
                              x={Math.max(0, bar.widthPct - 2.2)}
                              y="2"
                            />
                          </svg>
                        </span>
                        <span
                          className={`${styles.roV6KrdVal} ${bar.hot ? styles.roV6KrdHot : ""} ${styles.roNum}`}
                        >
                          {bar.wanText}
                        </span>
                      </div>
                    ))}
                    <div className={styles.roV6PanelFoot}>
                      条形长度为读数比例{hotKrdBucket ? ` · ${hotKrdBucket} 为峰值桶（琥珀）` : ""}
                    </div>
                  </>
                ) : (
                  <p className={styles.roV6EmptyText}>KRD 字段待接入。</p>
                )}
              </div>

              <div className={styles.roV6Panel} data-testid="risk-overview-curve-panel">
                <div className={styles.roV6PanelHead}>
                  <b>收益率曲线水平</b>
                  <span>
                    {curveChart?.dateLabel ?? curveDateLabel}
                    {curveChart?.ruleVersion ? ` · ${curveChart.ruleVersion}` : ""}
                  </span>
                </div>
                {curveChart ? (
                  <>
                    <div className={styles.roV6CurveLegend}>
                      {curveChart.series.map((series) => (
                        <span key={series.curveType}>
                          <i className={curveToneClass(series.tone)} aria-hidden="true" />
                          {series.label}
                        </span>
                      ))}
                    </div>
                    <svg
                      className={styles.roV6CurveSvg}
                      viewBox="0 0 420 190"
                      role="img"
                      aria-label="收益率曲线水平"
                    >
                      {curveChart.yTicks.map((tick) => (
                        <g key={tick.text}>
                          <line
                            className={styles.roV6CurveGrid}
                            x1="36"
                            y1={tick.y}
                            x2="352"
                            y2={tick.y}
                          />
                          <text className={styles.roV6CurveTick} x="358" y={tick.y + 3}>
                            {tick.text}
                          </text>
                        </g>
                      ))}
                      {curveChart.xLabels.map((label) => (
                        <text
                          className={styles.roV6CurveTick}
                          key={label.tenor}
                          x={label.x}
                          y="176"
                          textAnchor="middle"
                        >
                          {label.tenor}
                        </text>
                      ))}
                      {curveChart.series.map((series) => (
                        <g key={series.curveType}>
                          {series.areaPath ? (
                            <path
                              className={`${styles.roV6CurveArea} ${curveToneClass(series.tone)}`}
                              d={series.areaPath}
                            />
                          ) : null}
                          {series.linePath ? (
                            <path
                              className={`${styles.roV6CurveLine} ${curveToneClass(series.tone)}`}
                              d={series.linePath}
                            />
                          ) : null}
                          {series.endLabel ? (
                            <>
                              <circle
                                className={`${styles.roV6CurveEndHalo} ${curveToneClass(series.tone)}`}
                                cx={series.endLabel.x - 6}
                                cy={series.endLabel.y}
                                r="5"
                              />
                              <circle
                                className={`${styles.roV6CurveEndDot} ${curveToneClass(series.tone)}`}
                                cx={series.endLabel.x - 6}
                                cy={series.endLabel.y}
                                r="2.6"
                              />
                              <text
                                className={`${styles.roV6CurveEndText} ${curveToneClass(series.tone)}`}
                                x={series.endLabel.x + 17}
                                y={series.endLabel.y + 3.5}
                                textAnchor="middle"
                              >
                                {series.endLabel.text}
                              </text>
                            </>
                          ) : null}
                        </g>
                      ))}
                    </svg>
                    <div className={styles.roV6PanelFoot}>
                      治理规则读数直读{curveChart.ruleVersion ? ` · ${curveChart.ruleVersion}` : ""}
                    </div>
                  </>
                ) : (
                  <p className={styles.roV6EmptyText}>
                    收益率曲线待接入{yieldCurveQuery.isError ? "（读取失败，不使用前端补数）" : ""}。
                  </p>
                )}
              </div>
            </div>

            <div className={`${styles.roV6Panel} ${styles.roV6CashPanel}`} data-testid="risk-overview-cashflow-panel">
              <div className={styles.roV6PanelHead}>
                <b>现金流窗口 · 资产端 vs 负债端</b>
                <span>亿元 · 30D / 90D</span>
              </div>
              {cashTrack ? (
                <>
                  {cashTrack.rows.map((row) => (
                    <div className={styles.roV6CashRow} key={row.key}>
                      <span className={styles.roV6CashW}>{row.kind === "asset" ? row.window : ""}</span>
                      <span className={styles.roV6CashT}>{row.label}</span>
                      <span className={styles.roV6CashTrack} aria-hidden="true">
                        <svg
                          className={styles.roV6CashSvg}
                          preserveAspectRatio="none"
                          viewBox="0 0 100 9"
                        >
                          <rect
                            className={
                              row.kind === "asset" ? styles.roV6CashBarA : styles.roV6CashBarL
                            }
                            height="9"
                            rx="3"
                            width={row.widthPct}
                            x="0"
                            y="0"
                          />
                        </svg>
                      </span>
                      <span className={`${styles.roV6CashVal} ${styles.roNum}`}>{row.yiText}</span>
                    </div>
                  ))}
                  {cashTrack.chips.length > 0 ? (
                    <div className={styles.roV6GapChips}>
                      {cashTrack.chips.map((chip) => (
                        <span
                          className={`${styles.roV6GapChip} ${
                            chip.tone === "dim" ? styles.roV6GapChipDim : ""
                          }`}
                          key={chip.key}
                        >
                          <span>{chip.label}</span>
                          <b className={styles.roNum}>{chip.text}</b>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <p className={styles.roV6EmptyText}>现金流窗口字段待接入。</p>
              )}
            </div>

            <div className={styles.roV6Tables}>
              {detailTables.map((table) => (
                <div className={styles.roV6Tbl} data-testid={`risk-overview-table-${table.key}`} key={table.key}>
                  <div className={styles.roV6TblHead}>
                    {table.title}
                    <span>字段级证据</span>
                  </div>
                  {table.rows.length > 0 ? (
                    <table>
                      <thead>
                        <tr>
                          <th>字段</th>
                          <th>读数</th>
                          <th>报告日</th>
                        </tr>
                      </thead>
                      <tbody>
                        {table.rows.map((row) => (
                          <tr key={row.key}>
                            <td>{row.label}</td>
                            <td
                              className={`${styles.roV6TblNum} ${styles.roNum} ${
                                row.tone === "watch" ? styles.roToneWatch : ""
                              }`}
                            >
                              {row.value}
                            </td>
                            <td className={`${styles.roV6TblDt} ${styles.roNum}`}>{row.date}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className={styles.roV6EmptyText}>字段待接入。</p>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* 04 数据质量与血缘 */}
          <section data-testid="risk-overview-quality" id="risk-overview-quality">
            <div className={styles.roSecHead}>
              <i>04</i>
              <h2>数据质量与血缘</h2>
              <span>warnings_json 原文 · 版本与追溯</span>
            </div>
            <div className={styles.roV6Qual}>
              <div>
                <div className={styles.roV6TblHead}>
                  质量提示 · {tensorWarnings.length} 条
                  <span
                    className={
                      tensorWarnings.length > 0
                        ? `${styles.roV6Pill} ${styles.roV6PillWarn}`
                        : styles.roV6Pill
                    }
                  >
                    <i aria-hidden="true" />
                    {tensor?.quality_flag?.toUpperCase() ?? "待接入"}
                  </span>
                </div>
                {tensorWarnings.length > 0 ? (
                  <div
                    className={styles.roV6Warns}
                    data-testid="risk-overview-warning-list"
                  >
                    {visibleTensorWarnings.map((warning, index) => (
                      <p key={`${index}-${warning}`}>{warning}</p>
                    ))}
                    {remainingTensorWarnings.length > 0 ? (
                      <details
                        className={styles.roWarningDetails}
                        data-testid="risk-overview-warning-details"
                      >
                        <summary className={styles.roWarningSummary}>
                          展开其余 {remainingTensorWarnings.length} 条原始提示
                        </summary>
                        <div className={styles.roWarningRemainder}>
                          {remainingTensorWarnings.map((warning, index) => (
                            <p key={`${index + visibleTensorWarnings.length}-${warning}`}>{warning}</p>
                          ))}
                        </div>
                      </details>
                    ) : null}
                  </div>
                ) : (
                  <p className={styles.roV6EmptyText}>
                    {tensor ? "无质量提示。" : "风险张量未返回，质量标记待接入。"}
                  </p>
                )}
              </div>
              <div data-testid="risk-overview-lineage">
                <div className={styles.roV6TblHead}>
                  血缘追溯
                  <span>报告日 {tensor?.report_date ?? reportDate}</span>
                </div>
                {lineageRows.length > 0 ? (
                  <div className={styles.roV6Lineage}>
                    {lineageRows.map((row) => (
                      <div className={styles.roV6LineageRow} key={row.key}>
                        <span className={styles.roV6LineageKey}>{row.label}</span>
                        <span className={styles.roV6LineageVal}>{row.value}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className={styles.roV6EmptyText}>血缘元数据待接入。</p>
                )}
              </div>
            </div>
          </section>
        </div>

        <aside
          className={`${dh.dhRail} ${styles.roRail}`}
          data-testid="risk-overview-rail"
        >
          <section className={`${dh.dhRailCard} ${styles.roRailCard}`} data-testid="risk-overview-drilldowns">
            <div className={dh.dhRailCardHeader}>
              <span>下钻入口</span>
            </div>
            <div className={dh.dhRailCardBody}>
              <nav className={styles.roSectionNav} aria-label="风险总览页内章节">
                <span className={styles.roSectionNavLabel}>页内章节</span>
                <a className={styles.roSectionNavLink} href="#risk-overview-actions">
                  01 风险处置
                </a>
                <a className={styles.roSectionNavLink} href="#risk-overview-bond-evidence">
                  债券口径
                </a>
                <a className={styles.roSectionNavLink} href="#risk-overview-briefings">
                  02 风险摘要
                </a>
                <a className={styles.roSectionNavLink} href="#risk-overview-evidence">
                  03 风险证据
                </a>
                <a className={styles.roSectionNavLink} href="#risk-overview-quality">
                  04 数据质量
                </a>
              </nav>
              <div className={dh.dhRailActionList}>
                {config.drilldowns.map((item) => (
                  <div className={`${dh.dhRailActionRow} ${styles.roDrillRow}`} key={item.key}>
                    <Link to={item.path}>
                      <span>{item.label}</span>
                    </Link>
                    <span>{item.description}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className={`${dh.dhRailCard} ${styles.roRailCard}`} data-testid="risk-overview-data-note">
            <div className={dh.dhRailCardHeader}>
              <span>{view.dataNote.title}</span>
            </div>
            <div className={dh.dhRailCardBody}>
              <ul className={dh.dhRailSuggestionList}>
                {view.dataNote.lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          </section>
        </aside>
      </div>

      {agentPanelMounted ? (
        <Suspense fallback={null}>
          <LazyRiskOverviewAgentDrawer
            open={agentPanelOpen}
            reportDate={riskReportDate}
            currentFilters={agentPanelFilters}
            onClose={() => setAgentPanelOpen(false)}
          />
        </Suspense>
      ) : null}
    </section>
  );
}
