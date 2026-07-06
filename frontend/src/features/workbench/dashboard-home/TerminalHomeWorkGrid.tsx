import { lazy, memo, Suspense, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { Card, CardBody } from "@nextui-org/react";

import { LightIcon } from "../../../components/LightIcon";
import {
  DataQualityPill,
  DiagnosticDisclosure,
} from "../../../components/StatusPill";
import type { DataQualityStatus } from "../../../components/StatusContract";
import type {
  DashboardHomeBodyView,
  HomeDataStateKind,
  HomeDistributionSlice,
  HomeResearchReportRow,
  HomeRiskExposureMetric,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";
import { resolveDeltaClass } from "./dashboardHomeBodyView";
import styles from "./dashboardHome.module.css";

type TerminalHomeWorkGridProps = {
  view: DashboardHomeBodyView;
  homeAvailabilityKind?: "normal" | "serviceUnavailable";
};

type EChartsOption = import("../../../lib/echarts").EChartsOption;

const INCOME_TREND_COLORS = [
  "#7aa7ff",
  "#9db2ca",
  "#d4a85f",
];
const HOME_CHART_AXIS_COLOR = "#8190a5";
const HOME_CHART_GRID_COLOR = "rgba(129, 144, 165, 0.18)";
const HOME_CHART_TOOLTIP_BG = "rgba(9, 15, 25, 0.96)";
const HOME_CHART_TOOLTIP_BORDER = "rgba(129, 144, 165, 0.28)";
const HOME_CHART_ZERO_LINE = "rgba(232, 238, 247, 0.42)";
const HOLDINGS_BASE_VISIBLE_ROWS = 8;
const HOLDINGS_EXTRA_ROWS_PER_CHANGE = 2;
const HOLDINGS_MAX_VISIBLE_ROWS = 12;
const ReactECharts = lazy(() => import("../../../lib/echarts"));
const CHART_REVEAL_KEYS = new Set(["ArrowDown", "PageDown", "End", " ", "Space"]);

type IncomeTrendTooltipParam = {
  axisValue?: string | number;
  axisValueLabel?: string;
  data?: unknown;
  marker?: string;
  seriesName?: string;
  value?: unknown;
};

function incomeTrendRawValue(value: unknown): number | null {
  const candidate =
    typeof value === "object" && value !== null && "value" in value
      ? (value as { value?: unknown }).value
      : value;
  const raw = Array.isArray(candidate) ? Number(candidate[candidate.length - 1]) : Number(candidate);
  return Number.isFinite(raw) ? raw : null;
}

function formatIncomeTrendYi(value: unknown, options: { digits?: number; sign?: boolean } = {}): string {
  const raw = incomeTrendRawValue(value);
  if (raw == null) {
    return "";
  }
  const scaled = raw / 100_000_000;
  const sign = options.sign === false || scaled < 0 ? "" : "+";
  return `${sign}${scaled.toFixed(options.digits ?? 1)}亿`;
}

function incomeTrendTooltipFormatter(params: unknown): string {
  const rows = Array.isArray(params) ? params : [params];
  const typedRows = rows.filter((row): row is IncomeTrendTooltipParam => typeof row === "object" && row !== null);
  const title = typedRows[0]?.axisValueLabel ?? typedRows[0]?.axisValue ?? "";
  const body = typedRows
    .map((row) => {
      const formatted = formatIncomeTrendYi(row.value ?? row.data, { digits: 2 });
      if (!formatted) {
        return "";
      }
      return `${row.marker ?? ""}${row.seriesName ?? ""}: ${formatted}`;
    })
    .filter(Boolean);
  return [title, ...body].join("<br/>");
}

function CustomBadge({ children, kind }: { children?: React.ReactNode; kind: string }) {
  return (
    <span className={styles.dhInlineStatus} data-kind={kind}>
      <span className={styles.dhInlineStatusDot} aria-hidden="true" />
      {children}
    </span>
  );
}

function ChartFallback() {
  return <div aria-hidden="true" className={styles.dhTerminalChartPlaceholder} />;
}

function useDeferredChartMount() {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [isVisible, setIsVisible] = useState(
    () => typeof window === "undefined" || typeof window.IntersectionObserver === "undefined",
  );
  const [hasUserReachedCharts, setHasUserReachedCharts] = useState(
    () =>
      typeof window === "undefined" ||
      typeof window.IntersectionObserver === "undefined" ||
      window.scrollY > 0,
  );

  useEffect(() => {
    if (isVisible) return;

    if (typeof window === "undefined" || typeof window.IntersectionObserver === "undefined") {
      setIsVisible(true);
      return;
    }

    const chartNode = chartRef.current;
    if (!chartNode) return;

    const observer = new window.IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
        setIsVisible(true);
        observer.disconnect();
      }
    });

    observer.observe(chartNode);
    return () => observer.disconnect();
  }, [isVisible]);

  useEffect(() => {
    if (hasUserReachedCharts) return;

    if (typeof window === "undefined") {
      setHasUserReachedCharts(true);
      return;
    }

    if (window.scrollY > 0) {
      setHasUserReachedCharts(true);
      return;
    }

    function removeUserReachListeners() {
      window.removeEventListener("scroll", markUserReachedCharts);
      window.removeEventListener("wheel", markUserReachedCharts);
      window.removeEventListener("touchmove", markUserReachedCharts);
      window.removeEventListener("keydown", handleKeyDown);
    }

    function markUserReachedCharts() {
      setHasUserReachedCharts(true);
      removeUserReachListeners();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (CHART_REVEAL_KEYS.has(event.key)) {
        markUserReachedCharts();
      }
    }

    window.addEventListener("scroll", markUserReachedCharts);
    window.addEventListener("wheel", markUserReachedCharts);
    window.addEventListener("touchmove", markUserReachedCharts);
    window.addEventListener("keydown", handleKeyDown);
    return removeUserReachListeners;
  }, [hasUserReachedCharts]);

  return { chartRef, shouldMount: isVisible && hasUserReachedCharts };
}

function useMobileDetailFolds() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      return undefined;
    }

    const query = window.matchMedia("(max-width: 720px)");
    const syncViewport = () => setIsMobile(query.matches);
    syncViewport();
    query.addEventListener("change", syncViewport);
    return () => query.removeEventListener("change", syncViewport);
  }, []);

  return isMobile;
}

function MobileDetailFold({
  title,
  meta,
  children,
}: {
  title: string;
  meta: string;
  children: React.ReactNode;
}) {
  const isMobile = useMobileDetailFolds();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isMobile) {
      setIsOpen(false);
    }
  }, [isMobile]);

  if (!isMobile) {
    return <>{children}</>;
  }

  return (
    <details
      className={styles.dhApiMobileFold}
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
    >
      <summary className={styles.dhApiMobileFoldSummary}>
        <span>{title}</span>
        <b>{meta}</b>
      </summary>
      <div className={styles.dhApiMobileFoldBody}>{children}</div>
    </details>
  );
}

const LazyEChart = memo(function LazyEChart({
  option,
}: {
  option: EChartsOption;
}) {
  const { chartRef, shouldMount } = useDeferredChartMount();

  return (
    <div ref={chartRef} className={styles.dhTerminalChartMount}>
      {shouldMount ? (
        <Suspense fallback={<ChartFallback />}>
          <ReactECharts
            option={option}
            opts={{ renderer: "canvas" }}
            notMerge
            lazyUpdate
            style={{ height: "100%", width: "100%" }}
          />
        </Suspense>
      ) : (
        <ChartFallback />
      )}
    </div>
  );
});
LazyEChart.displayName = "LazyEChart";

function buildReportDatePath(path: string, reportDate: string): string {
  const trimmed = reportDate.trim();
  return trimmed && trimmed !== "—" ? `${path}?report_date=${encodeURIComponent(trimmed)}` : path;
}

const STATE_COPY: Record<HomeDataStateKind, string> = {
  ready: "数据正常",
  partial: "部分缺失",
  empty: "暂无数据",
  loading: "加载中",
  error: "不可用",
  stale: "数据延迟",
  "backend-gap": "部分缺失",
};

const STATE_HINT: Record<HomeDataStateKind, string> = {
  ready: "关键数据可用于当前判断",
  partial: "部分指标缺失，结论需复核",
  empty: "当前口径没有可展示记录",
  loading: "正在刷新数据",
  error: "本模块暂不可用，请查看数据诊断",
  stale: "数据日期与报告日不一致",
  "backend-gap": "数据链路未闭合，请查看数据诊断",
};

function stateClass(kind: HomeDataStateKind): string {
  if (kind === "ready") return styles.dhTerminalStateReady ?? "";
  if (kind === "partial") return styles.dhTerminalStateWarn ?? "";
  if (kind === "error" || kind === "backend-gap") return styles.dhTerminalStateWarn ?? "";
  if (kind === "stale") return styles.dhTerminalStateStale ?? "";
  return styles.dhTerminalStateMuted ?? "";
}

function DataStateBadge({ kind, label }: { kind: HomeDataStateKind; label?: string }) {
  const qualityStatus = homeDataQualityStatus(kind);
  return (
    <DataQualityPill
      status={qualityStatus}
      label={`${STATE_COPY[kind]}${label && kind !== "ready" ? ` · ${label}` : ""}`}
      className={`${styles.dhTerminalState} ${stateClass(kind)}`}
    />
  );
}

function homeDataQualityStatus(kind: HomeDataStateKind): DataQualityStatus {
  if (kind === "ready") return "fresh";
  if (kind === "stale") return "stale";
  if (kind === "error") return "unavailable";
  return "partial";
}

function StateIcon({ kind }: { kind: HomeDataStateKind }) {
  if (kind === "loading") return <LightIcon name="loading" />;
  if (kind === "error" || kind === "backend-gap") return <LightIcon name="warning" />;
  if (kind === "stale" || kind === "partial") return <LightIcon name="alert" />;
  return <LightIcon name="info-circle" />;
}

function StateSurface({
  state,
  compact = false,
  testId,
}: {
  state: HomeTerminalListState;
  compact?: boolean;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      data-state={state.kind}
      className={`${styles.dhTerminalStateSurface} ${compact ? styles.dhTerminalStateSurfaceCompact : ""}`}
    >
      <span className={styles.dhTerminalStateIcon}>
        <StateIcon kind={state.kind} />
      </span>
      <b>{state.label}</b>
      <small>{STATE_HINT[state.kind]}</small>
    </div>
  );
}

type AvailabilityModuleRow = {
  id: string;
  label: string;
  endpoint: string;
  state: HomeTerminalListState;
  detail: string;
  trace: string;
};

function aggregateAvailabilityState(states: readonly HomeTerminalListState[]): HomeTerminalListState {
  const order: HomeDataStateKind[] = ["error", "backend-gap", "stale", "partial", "loading", "empty", "ready"];
  const kind = order.find((candidate) => states.some((state) => state.kind === candidate)) ?? "empty";
  const labels = states
    .filter((state) => state.kind === kind && state.label)
    .map((state) => state.label);
  return {
    kind,
    label: labels[0] ?? STATE_COPY[kind],
  };
}

function landedTrace(count: number): string {
  return count > 0 ? `已落地 ${count} 条` : "暂无落地行";
}

function buildAvailabilityRows(view: DashboardHomeBodyView): AvailabilityModuleRow[] {
  const structureStates = [
    view.assetDistributionState,
    view.ratingDistributionState,
    view.maturityDistributionState,
    view.industryDistributionState,
    view.yieldDistributionState,
    view.portfolioComparisonState,
    view.riskExposureState,
  ];
  const structureReadyCount = structureStates.filter((state) => state.kind === "ready").length;

  return [
    {
      id: "snapshot",
      label: "首页快照",
      endpoint: "/ui/home/snapshot",
      state: { kind: "error", label: "主快照不可用" },
      detail: "首屏结论未闭合；下方模块按各自接口状态继续展示",
      trace: view.reportDate,
    },
    {
      id: "summary",
      label: "结构/风险",
      endpoint: "/api/bond-dashboard/home-summary",
      state: aggregateAvailabilityState(structureStates),
      detail: "资产、评级、期限、行业、收益率、组合与风险覆盖",
      trace: `${structureReadyCount}/${structureStates.length} 可用`,
    },
    {
      id: "holdings",
      label: "重点券持仓",
      endpoint: "/api/bond-analytics/top-holdings",
      state: view.holdingsState,
      detail: view.holdingsState.label,
      trace: landedTrace(view.holdingRows.length),
    },
    {
      id: "changes",
      label: "仓位变动",
      endpoint: "/api/bond-analytics/position-changes",
      state: view.positionChangesState,
      detail: view.positionChangesState.label,
      trace: landedTrace(view.positionChanges.length),
    },
    {
      id: "research",
      label: "研究报告",
      endpoint: "/ui/home/research-reports",
      state: view.researchReportsState,
      detail: view.researchReportsState.label,
      trace: landedTrace(view.researchReports.length),
    },
    {
      id: "income",
      label: "收益趋势",
      endpoint: "/ui/home/income-trend",
      state: view.incomeTrendState,
      detail: view.incomeTrendState.label,
      trace: `${view.incomeTrend.length} 个趋势点`,
    },
  ];
}

function HomeDataAvailabilityPanel({ view }: { view: DashboardHomeBodyView }) {
  const rows = buildAvailabilityRows(view);
  const availableCount = rows.filter((row) => row.state.kind === "ready").length;
  const reviewCount = rows.length - availableCount;

  return (
    <section
      data-testid="dashboard-home-data-availability"
      className={styles.dhServiceStatusPanel}
      aria-label="首页数据可用性"
    >
      <header className={styles.dhServiceStatusHeader}>
        <div>
          <span className={styles.dhServiceStatusKicker}>数据可用性</span>
          <h3>主快照不可用，模块按实况展示</h3>
          <p>
            当前首屏快照失败；持仓、研报、收益趋势和新闻继续按各自接口状态呈现，避免把可用模块一并隐藏。
          </p>
        </div>
        <dl className={styles.dhServiceStatusSummary}>
          <div>
            <dt>报告日</dt>
            <dd>{view.reportDate}</dd>
          </div>
          <div>
            <dt>模块可用</dt>
            <dd>{`${availableCount}/${rows.length}`}</dd>
          </div>
          <div>
            <dt>待复核</dt>
            <dd>{`${reviewCount} 项`}</dd>
          </div>
        </dl>
      </header>
      <div className={styles.dhServiceStatusTableWrap}>
        <table className={styles.dhServiceStatusLedger}>
          <thead>
            <tr>
              <th>模块</th>
              <th>数据状态</th>
              <th>业务影响</th>
              <th>处理建议</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.label}</td>
                <td>
                  <span className={stateClass(row.state.kind)}>{sourceGateStatusLabel(row.state.kind)}</span>
                </td>
                <td>{row.detail}</td>
                <td>{row.trace}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <DiagnosticDisclosure className={styles.dhServiceStatusDetails} summary="查看数据诊断">
        <p>
          主快照不可达时，本面板只标记失效入口；其余行来自当前 view 的真实状态，不替代下方模块自身的空态、错误态或已落地数据。
        </p>
        <table className={styles.dhServiceStatusLedger}>
          <thead>
            <tr>
              <th>模块</th>
              <th>端点</th>
              <th>技术状态</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.label}</td>
                <td className={styles.dhServiceStatusEndpoint}>{row.endpoint}</td>
                <td>{row.state.kind}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DiagnosticDisclosure>
    </section>
  );
}

function latestValueIndex(
  points: DashboardHomeBodyView["incomeTrend"],
  selectValue: (point: DashboardHomeBodyView["incomeTrend"][number]) => number | null,
): number {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    if (selectValue(points[index]) != null) {
      return index;
    }
  }
  return -1;
}

function buildSeriesData(
  points: DashboardHomeBodyView["incomeTrend"],
  selectValue: (point: DashboardHomeBodyView["incomeTrend"][number]) => number | null,
  latestIndex: number,
  color: string,
  isMuted = false,
) {
  return points.map((point, index) => {
    const value = selectValue(point);
    if (value == null || index !== latestIndex) {
      return value;
    }
    return {
      value,
      symbolSize: isMuted ? 6 : 8,
      itemStyle: {
        color,
        borderColor: "rgba(244, 248, 255, 0.86)",
        borderWidth: isMuted ? 1 : 1.5,
      },
      label: {
        show: !isMuted,
        position: "right" as const,
        backgroundColor: "rgba(7, 14, 26, 0.72)",
        borderColor: "rgba(129, 144, 165, 0.24)",
        borderRadius: 3,
        borderWidth: 1,
        color,
        fontSize: 10,
        fontWeight: 700,
        padding: [2, 5],
        formatter: (params: { value?: unknown } | undefined) => formatIncomeTrendYi(params?.value),
      },
    };
  });
}

function hasRenderableIncomeValue(point: DashboardHomeBodyView["incomeTrend"][number]): boolean {
  return point.portfolioRaw != null || point.benchmarkRaw != null || point.excessRaw != null;
}

function latestRenderableIncomePoint(
  points: DashboardHomeBodyView["incomeTrend"],
): DashboardHomeBodyView["incomeTrend"][number] | undefined {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const point = points[index];
    if (hasRenderableIncomeValue(point)) {
      return point;
    }
  }
  return undefined;
}

function buildIncomeTrendOption(points: DashboardHomeBodyView["incomeTrend"]): EChartsOption {
  const latestPortfolioIndex = latestValueIndex(points, (point) => point.portfolioRaw);
  const latestBenchmarkIndex = latestValueIndex(points, (point) => point.benchmarkRaw);
  const latestExcessIndex = latestValueIndex(points, (point) => point.excessRaw);
  const series = [
    points.some((point) => point.portfolioRaw != null)
      ? {
          name: "组合",
          type: "line" as const,
          smooth: true,
          symbol: "circle",
          symbolSize: 3,
          showSymbol: true,
          data: buildSeriesData(points, (point) => point.portfolioRaw, latestPortfolioIndex, INCOME_TREND_COLORS[0]),
          lineStyle: { width: 2.8, color: INCOME_TREND_COLORS[0] },
          itemStyle: { color: INCOME_TREND_COLORS[0] },
          areaStyle: { color: INCOME_TREND_COLORS[0], opacity: 0.08 },
          markLine: {
            silent: true,
            symbol: "none",
            label: { show: false },
            lineStyle: { color: HOME_CHART_ZERO_LINE, width: 1.35, type: "solid" as const },
            data: [{ yAxis: 0 }],
          },
        }
      : null,
    points.some((point) => point.benchmarkRaw != null)
      ? {
          name: "CDB基准",
          type: "line" as const,
          smooth: true,
          symbol: "circle",
          symbolSize: 3,
          showSymbol: true,
          data: buildSeriesData(points, (point) => point.benchmarkRaw, latestBenchmarkIndex, INCOME_TREND_COLORS[1], true),
          lineStyle: { opacity: 0.72, width: 1.55, type: "dashed" as const, color: INCOME_TREND_COLORS[1] },
          itemStyle: { color: INCOME_TREND_COLORS[1] },
          connectNulls: false,
        }
      : null,
    points.some((point) => point.excessRaw != null)
      ? {
          name: "超额",
          type: "line" as const,
          smooth: true,
          symbol: "circle",
          symbolSize: 3,
          showSymbol: true,
          data: buildSeriesData(points, (point) => point.excessRaw, latestExcessIndex, INCOME_TREND_COLORS[2]),
          lineStyle: { width: 2, color: INCOME_TREND_COLORS[2] },
          itemStyle: { color: INCOME_TREND_COLORS[2] },
          connectNulls: false,
        }
      : null,
  ].filter((item): item is NonNullable<typeof item> => item != null);

  return {
    backgroundColor: "transparent",
    color: INCOME_TREND_COLORS,
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: HOME_CHART_AXIS_COLOR, fontSize: 10 },
      data: series.map((item) => item.name),
    },
    grid: { top: 24, right: 48, bottom: 22, left: 38 },
    tooltip: {
      trigger: "axis",
      confine: true,
      order: "seriesDesc",
      formatter: incomeTrendTooltipFormatter,
      backgroundColor: HOME_CHART_TOOLTIP_BG,
      borderColor: HOME_CHART_TOOLTIP_BORDER,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: {
        color: "#dce6f3",
        fontSize: 11,
      },
      axisPointer: {
        type: "line",
        lineStyle: {
          color: HOME_CHART_GRID_COLOR,
          width: 1,
        },
      },
    },
    xAxis: {
      type: "category",
      data: points.map((point) => point.date.slice(5)),
      boundaryGap: false,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: HOME_CHART_GRID_COLOR } },
      axisLabel: { color: HOME_CHART_AXIS_COLOR, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      splitNumber: 5,
      min: (extent: { min: number; max: number }) => {
        const spread = Math.max(Math.abs(extent.max - extent.min), 1);
        return Math.min(0, extent.min) - spread * 0.08;
      },
      max: (extent: { min: number; max: number }) => {
        const spread = Math.max(Math.abs(extent.max - extent.min), 1);
        return Math.max(0, extent.max) + spread * 0.08;
      },
      axisLabel: {
        fontSize: 10,
        color: HOME_CHART_AXIS_COLOR,
        formatter: (value: number) => formatIncomeTrendYi(value, { sign: false }),
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: HOME_CHART_GRID_COLOR } },
    },
    series,
  };
}

function HoldingsPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows = view.holdingsState.kind === "ready" && view.holdingRows.length > 0;
  const targetRowCount = hasRows
    ? Math.min(
        HOLDINGS_MAX_VISIBLE_ROWS,
        HOLDINGS_BASE_VISIBLE_ROWS + (view.positionChangesState.kind === "ready" ? view.positionChanges.length : 0) * HOLDINGS_EXTRA_ROWS_PER_CHANGE,
      )
    : HOLDINGS_BASE_VISIBLE_ROWS;
  const visibleHoldingRows = view.holdingRows.slice(0, targetRowCount);
  const title = hasRows ? `重点券 Top${visibleHoldingRows.length}` : `重点券 Top${HOLDINGS_BASE_VISIBLE_ROWS}`;
  return (
    <Card
      className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalPanelWide}${hasRows ? ` ${styles.dhTerminalHoldings}` : ""} ${styles.dhSurfaceCard}`}
    >
      <CardBody className="p-0 flex flex-col h-full">
        <div className={styles.dhTerminalPanelHead}>
          <h3>{title}</h3>
          <CustomBadge kind={view.holdingsState.kind}>{view.holdingsState.label || "估值计算已完成"}</CustomBadge>
        </div>
        {hasRows ? (
          <table data-testid="dashboard-home-holdings-table" className={styles.dhTerminalTable}>
            <colgroup>
              <col className={styles.dhTerminalHoldColBond} />
              <col className={styles.dhTerminalHoldColType} />
              <col className={styles.dhTerminalHoldColMetric} />
              <col className={styles.dhTerminalHoldColMetric} />
              <col className={styles.dhTerminalHoldColMetric} />
              <col className={styles.dhTerminalHoldColMetric} />
              <col className={styles.dhTerminalHoldColRating} />
            </colgroup>
            <thead>
              <tr className="border-b border-[var(--dh-line)] text-[var(--dh-muted)]">
                <th className="py-2 text-left font-normal">券种</th>
                <th className="py-2 text-left font-normal">分类</th>
                <th className="py-2 text-right font-normal">市值</th>
                <th className="py-2 text-right font-normal">占比</th>
                <th className="py-2 text-right font-normal">YTM</th>
                <th className="py-2 text-right font-normal">久期</th>
                <th className="py-2 text-right font-normal">评级</th>
              </tr>
            </thead>
            <tbody>
              {visibleHoldingRows.map((row) => (
                <tr key={row.id} data-testid="dashboard-home-holding-row" className="border-b border-[var(--dh-line-soft)] last:border-b-0 hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                  <td className="py-2">
                    <b className="text-[var(--dh-ink)]">{row.code}</b>
                    <span className="text-[var(--dh-ink-2)] text-[11px] block">{row.name}</span>
                  </td>
                  <td className="py-2 text-[var(--dh-ink-2)]">{row.assetClass}</td>
                  <td className={`py-2 text-right font-mono ${styles.dhNum}`}>{row.marketValue}</td>
                  <td className={`py-2 text-right font-mono ${styles.dhNum}`}>{row.weight}</td>
                  <td className={`py-2 text-right font-mono ${styles.dhNum}`}>{row.ytm}</td>
                  <td className={`py-2 text-right font-mono ${styles.dhNum}`}>{row.duration}</td>
                  <td className="py-2 text-right font-mono">{row.rating}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <StateSurface state={view.holdingsState} testId="dashboard-home-holdings-table" />
        )}
      </CardBody>
    </Card>
  );
}

type SourceGateRow = {
  id: string;
  source: string;
  basis: string;
  status: HomeDataStateKind;
  time: string;
  trace: string;
};

function sourceGateStatus(state: HomeTerminalListState): HomeDataStateKind {
  return state.kind === "backend-gap" ? "partial" : state.kind;
}

function landedCountLabel(count: number): string {
  return count > 0 ? `已落地 ${count} 条` : "暂无落地行";
}

function sourceGateStatusLabel(kind: HomeDataStateKind): string {
  if (kind === "ready") return "已核验";
  if (kind === "stale") return "数据偏旧";
  if (kind === "error" || kind === "backend-gap") return "不可用";
  if (kind === "loading") return "读取中";
  if (kind === "empty") return "暂无数据";
  return "部分可用";
}

function aggregateSourceGateStatus(rows: readonly SourceGateRow[]): HomeDataStateKind {
  if (rows.length === 0) return "empty";
  if (rows.some((row) => row.status === "error" || row.status === "backend-gap")) return "error";
  if (rows.some((row) => row.status === "stale")) return "stale";
  if (rows.some((row) => row.status === "partial")) return "partial";
  if (rows.some((row) => row.status === "loading")) return "loading";
  return "ready";
}

function buildSourceGateRows(view: DashboardHomeBodyView): SourceGateRow[] {
  const rows: SourceGateRow[] = [];
  if (view.holdingRows.length > 0) {
    rows.push({
      id: "holdings",
      source: "重点券持仓",
      basis: "top-holdings",
      status: sourceGateStatus(view.holdingsState),
      time: view.reportDate,
      trace: landedCountLabel(view.holdingRows.length),
    });
  }
  if (view.positionChanges.length > 0) {
    rows.push({
      id: "position-changes",
      source: "仓位变动",
      basis: "position-changes",
      status: sourceGateStatus(view.positionChangesState),
      time: view.reportDate,
      trace: landedCountLabel(view.positionChanges.length),
    });
  }
  if (view.researchReports.length > 0) {
    rows.push({
      id: "research",
      source: "研究报告",
      basis: "home-research-reports",
      status: sourceGateStatus(view.researchReportsState),
      time: view.researchReports[0]?.publishedAt || view.reportDate,
      trace: landedCountLabel(view.researchReports.length),
    });
  }
  if (view.incomeTrend.length > 0) {
    rows.push({
      id: "income-trend",
      source: "收益趋势",
      basis: view.incomeTrendSection.source,
      status: sourceGateStatus(view.incomeTrendState),
      time: view.incomeTrend.at(-1)?.date || view.incomeTrendSection.reportDate,
      trace: landedCountLabel(view.incomeTrend.length),
    });
  }
  const bondNewsCount =
    view.bondNews.holdingHits.length +
    view.bondNews.marketNews.length +
    view.bondNews.creditAndIssuanceNews.length;
  if (bondNewsCount > 0) {
    rows.push({
      id: "bond-news",
      source: "债券新闻",
      basis: "choice/tushare topics",
      status: "partial",
      time: view.bondNews.asOfLabel.replace(/^数据截至：/, "") || view.reportDate,
      trace: landedCountLabel(bondNewsCount),
    });
  }
  if (view.macroBriefing.newsItems.length > 0) {
    rows.push({
      id: "macro-news",
      source: "宏观新闻",
      basis: "choice/tushare macro",
      status: view.macroBriefing.newsStale ? "stale" : "partial",
      time: view.macroBriefing.newsAsOfLabel.replace(/^数据截至：/, "") || view.reportDate,
      trace: landedCountLabel(view.macroBriefing.newsItems.length),
    });
  }
  return rows;
}

function SourceGatePanel({ view }: { view: DashboardHomeBodyView }) {
  const sourceGateRows = buildSourceGateRows(view);
  const sourceGateStatus = aggregateSourceGateStatus(sourceGateRows);
  const sourceGateLabel = sourceGateRows.length > 0 ? sourceGateStatusLabel(sourceGateStatus) : "等待来源行";

  return (
    <Card
      data-testid="dashboard-home-source-gate"
      className={`${styles.dhCard} ${styles.dhSurfaceCard} ${styles.dhTerminalPanel} ${styles.dhGridFullRow} flex flex-col`}
    >
      <CardBody className="p-0 flex flex-col h-full">
        <div className={styles.dhTerminalPanelHead}>
          <h3>来源台账</h3>
          <CustomBadge kind={sourceGateStatus}>
            {sourceGateLabel}
          </CustomBadge>
        </div>
        {sourceGateRows.length > 0 ? (
          <div className={styles.dhSourceGateTableWrap}>
            <table className={styles.dhSourceGateTable}>
              <thead>
                <tr>
                  <th>数据源</th>
                  <th>核算口径</th>
                  <th data-align="center">校验状态</th>
                  <th data-align="center">最近同步</th>
                  <th data-align="right">审计签名</th>
                </tr>
              </thead>
              <tbody>
                {sourceGateRows.map((row) => (
                  <tr key={row.id}>
                    <td className={styles.dhSourceGatePrimary}>{row.source}</td>
                    <td className={styles.dhSourceGateBasis}>{row.basis}</td>
                    <td data-align="center">
                      <CustomBadge kind={row.status}>{sourceGateStatusLabel(row.status)}</CustomBadge>
                    </td>
                    <td data-align="center" className={styles.dhNum}>{row.time}</td>
                    <td data-align="right">
                      <span className={styles.dhSourceGateTrace}>{row.trace}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <StateSurface
            compact
            state={{ kind: "empty", label: "暂无可核验来源台账" }}
            testId="dashboard-home-source-gate-empty"
          />
        )}
      </CardBody>
    </Card>
  );
}

function PositionChangesPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows = view.positionChangesState.kind === "ready" && view.positionChanges.length > 0;
  const title = hasRows ? `增减仓 TOP${view.positionChanges.length}` : "增减仓 TOP5";
  return (
    <article data-testid="dashboard-home-position-changes" className={`${styles.dhCard} ${styles.dhTerminalPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>{title}</h3>
        <DataStateBadge kind={view.positionChangesState.kind} label={view.positionChangesState.label} />
      </div>
      {hasRows ? (
        <div className={styles.dhTerminalChangeList}>
          {view.positionChanges.map((row) => (
            <div key={row.id} className={styles.dhTerminalChangeRow} data-direction={row.direction}>
              <span className={styles.dhTerminalChangeBond}>
                <b>{row.code}</b>
                <small>{row.name}</small>
              </span>
              <span className={styles.dhTerminalChangeReason} data-direction={row.direction}>
                {row.reason}
              </span>
              <span className={`${styles.dhTerminalChangeValue} ${styles.dhNum} ${resolveDeltaClass(row.tone, styles)}`}>
                {row.changeValue}
                <small>{row.weightDelta}</small>
              </span>
              <span className={`${styles.dhTerminalChangeCurrent} ${styles.dhNum}`}>
                <small>现值</small>
                {row.currentValue}
              </span>
              <span className={styles.dhTerminalChangeBar}>
                <span
                  className={styles.dhTerminalChangeFill}
                  data-direction={row.direction}
                  style={{ "--dh-terminal-bar-width": `${row.barPct}%` } as CSSProperties}
                />
              </span>
            </div>
          ))}
        </div>
      ) : (
        <StateSurface state={view.positionChangesState} />
      )}
    </article>
  );
}

function formatResearchMonthDay(publishedAt: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(publishedAt.trim());
  if (match) {
    return `${match[2]}-${match[3]}`;
  }
  return publishedAt.trim() || "—";
}

function formatResearchCategoryLabel(category: string): string {
  const trimmed = category.trim();
  if (!trimmed || trimmed === "research") {
    return "研报";
  }
  if (trimmed === "fixed_income") {
    return "固收";
  }
  return trimmed;
}

function isResearchSummaryVisible(summary: string): boolean {
  const text = summary.trim();
  return text.length > 0 && text !== "—";
}

function formatResearchInstitution(row: HomeResearchReportRow): string | null {
  const institution = row.institution.trim();
  if (institution && institution !== "—") {
    return institution;
  }
  const source = row.source.trim();
  if (source && source !== "—" && source !== "tushare_research") {
    return source;
  }
  return null;
}

function buildResearchMetaLine(row: HomeResearchReportRow): string {
  return [formatResearchInstitution(row), formatResearchCategoryLabel(row.category)].filter(Boolean).join(" · ");
}

function ResearchReportFeatured({ row }: { row: HomeResearchReportRow }) {
  const className = `${styles.dhTerminalReportFeatured}${row.isNewsFallback ? ` ${styles.dhTerminalReportFallback}` : ""}`;
  const content = (
    <>
      <span className={styles.dhTerminalReportFeaturedDate}>
        <b>{formatResearchMonthDay(row.publishedAt)}</b>
        <small>{row.isNewsFallback ? "补位" : "最新"}</small>
      </span>
      <span className={styles.dhTerminalReportFeaturedBody}>
        <span className={styles.dhTerminalReportFeaturedTitle}>{row.title}</span>
        {isResearchSummaryVisible(row.summary) ? (
          <span className={styles.dhTerminalReportFeaturedSummary}>{row.summary}</span>
        ) : null}
        <span className={styles.dhTerminalReportMetaRow}>
          <span className={styles.dhTerminalReportMetaText}>{buildResearchMetaLine(row)}</span>
          {row.link ? <span className={styles.dhTerminalReportPdfTag}>PDF</span> : null}
        </span>
      </span>
    </>
  );
  return row.link ? (
    <a className={className} href={row.link} target="_blank" rel="noreferrer" data-testid="dashboard-home-research-featured">
      {content}
    </a>
  ) : (
    <div className={className} data-testid="dashboard-home-research-featured">
      {content}
    </div>
  );
}

function ResearchReportCompactRow({ row }: { row: HomeResearchReportRow }) {
  const className = `${styles.dhTerminalReportCompactRow}${row.isNewsFallback ? ` ${styles.dhTerminalReportFallback}` : ""}`;
  const content = (
    <>
      <span className={styles.dhTerminalReportCompactDate}>{formatResearchMonthDay(row.publishedAt)}</span>
      <span className={styles.dhTerminalReportCompactTitle}>{row.title}</span>
      <span className={styles.dhTerminalReportCompactInstitution}>
        {formatResearchInstitution(row) ?? "—"}
      </span>
      <span className={styles.dhTerminalReportTypeTag}>{formatResearchCategoryLabel(row.category)}</span>
      {row.link ? <span className={styles.dhTerminalReportPdfTag}>PDF</span> : <span className={styles.dhTerminalReportPdfSpacer} />}
    </>
  );
  return row.link ? (
    <a className={className} href={row.link} target="_blank" rel="noreferrer" data-testid="dashboard-home-research-row">
      {content}
    </a>
  ) : (
    <div className={className} data-testid="dashboard-home-research-row">
      {content}
    </div>
  );
}

function ResearchReportsPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows =
    (view.researchReportsState.kind === "ready" || view.researchReportsState.kind === "partial") &&
    view.researchReports.length > 0;
  const panelTitle = view.researchReportsState.label.includes("新闻补位") ? "研究资讯" : "券商研报";
  const [featured, ...compactRows] = view.researchReports;
  return (
    <article
      data-testid="dashboard-home-research-reports"
      className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalReportsPanel}`}
    >
      <div className={styles.dhTerminalPanelHead}>
        <h3>{panelTitle}</h3>
        <DataStateBadge kind={view.researchReportsState.kind} label={view.researchReportsState.label} />
      </div>
      {hasRows && featured ? (
        <div className={styles.dhTerminalReportStack}>
          <ResearchReportFeatured row={featured} />
          {compactRows.length > 0 ? (
            <div className={styles.dhTerminalReportCompactList}>
              {compactRows.map((row) => (
                <ResearchReportCompactRow key={row.id} row={row} />
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <StateSurface state={view.researchReportsState} />
      )}
    </article>
  );
}

function IncomeTrendPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows =
    (view.incomeTrendState.kind === "ready" || view.incomeTrendState.kind === "partial") &&
    view.incomeTrend.length > 0;
  const latestPoint = latestRenderableIncomePoint(view.incomeTrend);
  const hasPortfolioSeries = view.incomeTrend.some((point) => point.portfolioRaw != null);
  const hasBenchmarkSeries = view.incomeTrend.some((point) => point.benchmarkRaw != null);
  const hasExcessSeries = view.incomeTrend.some((point) => point.excessRaw != null);
  const incomeTrendOption = useMemo(
    () => buildIncomeTrendOption(view.incomeTrend),
    [view.incomeTrend],
  );
  return (
    <article
      data-testid="dashboard-home-income-trend"
      className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalPanelWide}`}
    >
      <div className={styles.dhTerminalPanelHead}>
        <h3>收益趋势</h3>
        <div className={styles.dhPanelHeaderActions}>
          <DataStateBadge kind={view.incomeTrendState.kind} label={view.incomeTrendState.label} />
          <Link
            to={buildReportDatePath("/pnl-attribution", view.reportDate)}
            className={styles.dhPanelDrillLink}
          >
            归因明细 →
          </Link>
        </div>
      </div>
      {hasRows ? (
        <div className={styles.dhTerminalIncomeStack}>
          {latestPoint ? (
            <div className={styles.dhTerminalIncomeSummary}>
              <span>
                <small>组合</small>
                <b className={styles.dhNum}>{latestPoint.portfolioPnl}</b>
              </span>
              <span>
                <small>基准</small>
                <b className={styles.dhNum}>{latestPoint.benchmarkPnl}</b>
              </span>
              <span>
                <small>超额</small>
                <b className={styles.dhNum}>{latestPoint.excessPnl}</b>
              </span>
            </div>
          ) : null}
          {latestPoint ? (
            <div className={styles.dhTerminalIncomeMeta}>
              <span>{`数据截至 ${latestPoint.date}`}</span>
              <span>{`CDB_INDEX / MoM${view.incomeTrendState.kind === "partial" ? ` · ${view.incomeTrendState.label}` : ""}`}</span>
            </div>
          ) : null}
          <div className={styles.dhTerminalIncomeLegend} aria-label="收益趋势图例">
            {hasPortfolioSeries ? <span data-series="portfolio">组合</span> : null}
            {hasBenchmarkSeries ? <span data-series="benchmark">CDB基准</span> : null}
            {hasExcessSeries ? <span data-series="excess">超额</span> : null}
          </div>
          <div className={styles.dhTerminalIncomeTrend}>
            <div className={styles.dhTerminalIncomeChart}>
              <LazyEChart
                option={incomeTrendOption}
              />
            </div>
            <div className={styles.dhTerminalIncomeList}>
              {view.incomeTrend.slice(-4).map((point) => (
                <div
                  key={point.id}
                  className={styles.dhTerminalIncomeRow}
                  data-current={point.id === latestPoint?.id}
                  data-tone={point.excessRaw != null && point.excessRaw < 0 ? "negative" : "positive"}
                >
                  <time dateTime={point.date}>{point.date.slice(5)}</time>
                  <b className={styles.dhNum}>{point.portfolioPnl}</b>
                  <div className={styles.dhTerminalIncomeLedgerMetrics}>
                    <div data-series="benchmark">
                      <small>基准</small>
                      <strong className={styles.dhNum}>{point.benchmarkPnl}</strong>
                    </div>
                    <div data-series="excess">
                      <small>超额</small>
                      <strong className={styles.dhNum}>{point.excessPnl}</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <StateSurface state={view.incomeTrendState} />
      )}
    </article>
  );
}

type ApiDirectoryRow = {
  id: string;
  endpoint: string;
  module: string;
  state: HomeTerminalListState;
  handling: string;
};

function directoryStatusText(state: HomeTerminalListState): string {
  if (state.kind === "ready") return "200 OK";
  if (state.kind === "loading") return "读取中";
  if (state.kind === "error") return "失败";
  if (state.kind === "stale") return "偏旧";
  if (state.kind === "empty") return "暂无";
  return "部分";
}

function directoryStateTone(state: HomeTerminalListState): HomeDataStateKind {
  return state.kind === "backend-gap" ? "partial" : state.kind;
}

function moduleReadyState(label = "已接入"): HomeTerminalListState {
  return { kind: "ready", label };
}

function moduleReservedState(): HomeTerminalListState {
  return { kind: "error", label: "保留缺口" };
}

function buildApiDirectoryRows(view: DashboardHomeBodyView): ApiDirectoryRow[] {
  const structureStates = [
    view.assetDistributionState,
    view.ratingDistributionState,
    view.maturityDistributionState,
    view.industryDistributionState,
    view.yieldDistributionState,
    view.portfolioComparisonState,
  ];
  const bondSummaryReady = structureStates.some((state) => state.kind === "ready" || state.kind === "partial");
  const bondSummaryState = bondSummaryReady
    ? moduleReadyState("structure families visible")
    : view.riskExposureState;

  return [
    {
      id: "snapshot",
      endpoint: "/ui/home/snapshot",
      module: "判断 / 治理 / KPI / 品类标题",
      state: moduleReadyState("primary snapshot"),
      handling: "直接",
    },
    {
      id: "supplemental",
      endpoint: "/api/dashboard/core_metrics + daily-changes",
      module: "日期门控补充经营指标",
      state: moduleReadyState("date-gated"),
      handling: "补充",
    },
    {
      id: "summary",
      endpoint: "/api/bond-dashboard/home-summary",
      module: "风险 + 7 类结构",
      state: bondSummaryState,
      handling: "看板",
    },
    {
      id: "holdings",
      endpoint: "/api/bond-analytics/top-holdings",
      module: "持仓台账；当前 TopN",
      state: view.holdingsState,
      handling: "正式",
    },
    {
      id: "changes",
      endpoint: "/api/bond-analytics/position-changes",
      module: "仓位变动台账；当前 TopN",
      state: view.positionChangesState,
      handling: "正式",
    },
    {
      id: "research",
      endpoint: "/ui/home/research-reports",
      module: "研究资讯；研报为空时新闻补位",
      state: view.researchReportsState,
      handling: "分析",
    },
    {
      id: "income",
      endpoint: "/ui/home/income-trend",
      module: "组合 / 基准 / 超额收益趋势",
      state: view.incomeTrendState,
      handling: "分析",
    },
    {
      id: "reserved",
      endpoint: "/ui/home/alerts + contribution",
      module: "保留区；不渲染为实时数据",
      state: moduleReservedState(),
      handling: "保留",
    },
  ];
}

function ApiDataDirectoryPanel({ view }: { view: DashboardHomeBodyView }) {
  const rows = buildApiDirectoryRows(view);

  return (
    <section className={`${styles.dhApiModule} ${styles.dhApiDirectoryPanel}`}>
      <div className={styles.dhApiModuleHead}>
        <h3>接口台账</h3>
        <span>下半屏可呈现的数据范围</span>
      </div>
      <div className={styles.dhApiDirectoryTableWrap}>
        <table className={styles.dhApiDirectoryTable}>
          <thead>
            <tr>
              <th>#</th>
              <th>接口</th>
              <th>可渲染模块</th>
              <th>状态</th>
              <th>处理方式</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const tone = directoryStateTone(row.state);
              return (
                <tr key={row.id}>
                  <td className={styles.dhNum}>{String(index + 1).padStart(2, "0")}</td>
                  <td>{row.endpoint}</td>
                  <td>{row.module}</td>
                  <td>
                    <span className={`${styles.dhApiStatusText} ${stateClass(tone)}`}>
                      {row.id === "reserved" ? "503" : directoryStatusText(row.state)}
                    </span>
                  </td>
                  <td>{row.handling}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function summaryMetricValue(metrics: readonly HomeRiskExposureMetric[], id: string): string {
  return metrics.find((metric) => metric.id === id)?.value ?? "—";
}

function RiskExposureGapLedger({ state, reportDate }: { state: HomeTerminalListState; reportDate: string }) {
  return (
    <div className={styles.dhApiRiskGapLedger} data-state={state.kind}>
      <div className={styles.dhApiRiskGapPrimary}>
        <span className={styles.dhTerminalStateIcon}>
          <StateIcon kind={state.kind} />
        </span>
        <b>{state.label}</b>
        <small>{STATE_HINT[state.kind]}</small>
      </div>
      <dl>
        <div>
          <dt>数据路径</dt>
          <dd>bond-dashboard.home-summary.risk</dd>
        </div>
        <div>
          <dt>报告日</dt>
          <dd>{reportDate}</dd>
        </div>
        <div>
          <dt>处理方式</dt>
          <dd>保留缺口，不反推</dd>
        </div>
      </dl>
    </div>
  );
}

function RiskSummaryPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows = view.riskExposureMetrics.length > 0;
  return (
    <article data-testid="dashboard-home-risk-exposure" className={`${styles.dhApiModule} ${styles.dhApiRiskSummary}`}>
      <div className={styles.dhApiModuleHead}>
        <h3>风险暴露</h3>
        <span>bond-dashboard.home-summary.risk</span>
      </div>
      {hasRows ? (
        <div className={styles.dhApiRiskPairGrid}>
          <span className={styles.dhApiRiskPairPrimary}>
            <small>总市值</small>
            <b className={styles.dhNum}>{summaryMetricValue(view.riskExposureMetrics, "market-value")}</b>
          </span>
          <span>
            <small>DV01</small>
            <b className={styles.dhNum}>{summaryMetricValue(view.riskExposureMetrics, "dv01")}</b>
          </span>
          <span>
            <small>久期</small>
            <b className={styles.dhNum}>{summaryMetricValue(view.riskExposureMetrics, "duration")}</b>
          </span>
          <span>
            <small>信用占比</small>
            <b className={styles.dhNum}>{summaryMetricValue(view.riskExposureMetrics, "credit")}</b>
          </span>
          <span>
            <small>Spread DV01</small>
            <b className={styles.dhNum}>{summaryMetricValue(view.riskExposureMetrics, "spread-dv01")}</b>
          </span>
        </div>
      ) : (
        <RiskExposureGapLedger state={view.riskExposureState} reportDate={view.reportDate} />
      )}
    </article>
  );
}

type StructureCoverageTone = "ready" | "partial" | "blocked";

type StructureCoverageDomain = {
  id: string;
  title: string;
  state: HomeTerminalListState;
  slices: readonly HomeDistributionSlice[];
  note: string;
  basis: string;
};

const STRUCTURE_RESERVED_GAPS = [
  { id: "alerts", title: "预警", basis: "reserved endpoint", state: "503" },
  { id: "contribution", title: "贡献", basis: "reserved endpoint", state: "503" },
  { id: "risk-overview", title: "风险总览", basis: "reserved endpoint", state: "503" },
] as const;

function buildStructureCoverageDomains(view: DashboardHomeBodyView): StructureCoverageDomain[] {
  return [
    {
      id: "asset",
      title: "资产类型",
      state: view.assetDistributionState,
      slices: view.assetDistribution,
      note: `${view.assetDistribution.length} 行`,
      basis: "asset distribution",
    },
    {
      id: "rating",
      title: "评级",
      state: view.ratingDistributionState,
      slices: view.ratingDistribution,
      note: `${view.ratingDistribution.length} 行`,
      basis: "rating buckets",
    },
    {
      id: "maturity",
      title: "期限",
      state: view.maturityDistributionState,
      slices: view.maturityDistribution,
      note: `${view.maturityDistribution.length} 组`,
      basis: "maturity buckets",
    },
    {
      id: "industry",
      title: "行业",
      state: view.industryDistributionState,
      slices: view.industryDistribution,
      note: `${view.industryDistribution.length} 行`,
      basis: "industry distribution",
    },
    {
      id: "ytm",
      title: "YTM 分布",
      state: view.yieldDistributionState,
      slices: view.yieldDistribution,
      note: "加权 YTM",
      basis: "weighted yield",
    },
    {
      id: "portfolio",
      title: "组合比较",
      state: view.portfolioComparisonState,
      slices: view.portfolioComparison,
      note: "久期 / DV01",
      basis: "portfolio compare",
    },
  ];
}

function hasStructureCoverageRows(domain: StructureCoverageDomain): boolean {
  return domain.slices.length > 0 && (domain.state.kind === "ready" || domain.state.kind === "partial");
}

function structureCoverageTone(domain: StructureCoverageDomain): StructureCoverageTone {
  if (!hasStructureCoverageRows(domain)) return "blocked";
  return domain.state.kind === "ready" ? "ready" : "partial";
}

function structureCoverageLabel(domain: StructureCoverageDomain): string {
  const tone = structureCoverageTone(domain);
  if (tone === "ready") return "READY";
  if (tone === "partial") return "PARTIAL";
  return domain.state.kind === "loading" ? "LOADING" : "MISSING";
}

function structureCoverageMode(domain: StructureCoverageDomain): string {
  if (domain.id === "ytm") return "bucket share";
  if (domain.id === "portfolio") return "top set";
  return "Top3 contributors";
}

function StructureCoverageMap({
  domains,
  expandedDomains,
  missingDomains,
}: {
  domains: readonly StructureCoverageDomain[];
  expandedDomains: readonly StructureCoverageDomain[];
  missingDomains: readonly StructureCoverageDomain[];
}) {
  const readyCount = domains.filter((domain) => structureCoverageTone(domain) === "ready").length;
  const partialCount = domains.filter((domain) => structureCoverageTone(domain) === "partial").length;
  const gapCount = missingDomains.length + STRUCTURE_RESERVED_GAPS.length;

  return (
    <div className={styles.dhApiCoverageMap} data-testid="dashboard-home-structure-coverage">
      <div className={styles.dhApiCoverageScore}>
        <small>Coverage</small>
        <b className={styles.dhNum}>{`${expandedDomains.length}/${domains.length}`}</b>
        <span>domains landed</span>
      </div>
      <div className={styles.dhApiCoverageDomains}>
        {domains.map((domain) => {
          const tone = structureCoverageTone(domain);
          return (
            <span key={domain.id} data-state={tone}>
              <b>{domain.title}</b>
              <small>{structureCoverageLabel(domain)}</small>
            </span>
          );
        })}
      </div>
      <dl className={styles.dhApiCoverageStats}>
        <div>
          <dt>Ready</dt>
          <dd className={styles.dhNum}>{readyCount}</dd>
        </div>
        <div>
          <dt>Partial</dt>
          <dd className={styles.dhNum}>{partialCount}</dd>
        </div>
        <div>
          <dt>Gaps</dt>
          <dd className={styles.dhNum}>{gapCount}</dd>
        </div>
      </dl>
    </div>
  );
}

function StructureMiniCard({ domain }: { domain: StructureCoverageDomain }) {
  const visibleSlices = domain.slices.slice(0, 3);
  const tone = structureCoverageTone(domain);

  return (
    <article className={styles.dhApiStructureCard} data-domain={domain.id} data-state={tone}>
      <div className={styles.dhApiStructureHead}>
        <h4>{domain.title}</h4>
        <CustomBadge kind={directoryStateTone(domain.state)}>{structureCoverageLabel(domain)}</CustomBadge>
      </div>
      <p className={styles.dhApiStructureSource}>{domain.basis}</p>
      <div className={styles.dhApiStructureRows}>
        {visibleSlices.map((slice) => (
          <div key={slice.id} className={styles.dhApiStructureRow}>
            <span>{slice.label}</span>
            <b className={styles.dhNum}>{slice.pct}</b>
            <i
              aria-hidden="true"
              style={{ "--dh-api-bar-width": `${Math.max(4, Math.min(100, slice.pctRaw))}%` } as CSSProperties}
            />
          </div>
        ))}
      </div>
      <div className={styles.dhApiStructureFooter}>
        <small>{domain.note}</small>
        <small>{structureCoverageMode(domain)}</small>
      </div>
    </article>
  );
}

function StructureGapBand({ missingDomains }: { missingDomains: readonly StructureCoverageDomain[] }) {
  const gaps = [
    ...missingDomains.map((domain) => ({
      id: domain.id,
      title: domain.title,
      basis: domain.state.label,
      state: directoryStatusText(domain.state),
    })),
    ...STRUCTURE_RESERVED_GAPS,
  ];

  return (
    <div className={styles.dhApiCoverageGapBand} data-testid="dashboard-home-structure-gap-band">
      <span>
        <b>保留缺口</b>
        <small>{`${gaps.length} folded gap domains`}</small>
      </span>
      <div>
        {gaps.map((gap) => (
          <em key={gap.id} data-state={gap.state}>
            <strong>{gap.title}</strong>
            <code>{gap.state}</code>
            <small>{gap.basis}</small>
          </em>
        ))}
      </div>
    </div>
  );
}

function StructureBoardPanel({ view }: { view: DashboardHomeBodyView }) {
  const domains = buildStructureCoverageDomains(view);
  const expandedDomains = domains.filter(hasStructureCoverageRows);
  const missingDomains = domains.filter((domain) => !hasStructureCoverageRows(domain));

  return (
    <section
      className={`${styles.dhApiModule} ${styles.dhApiStructureBoard}`}
      data-testid="dashboard-home-structure-board"
    >
      <div className={styles.dhApiModuleHead}>
        <h3>结构看板</h3>
        <span>coverage map · expanded landed domains · folded gaps</span>
      </div>
      <StructureCoverageMap domains={domains} expandedDomains={expandedDomains} missingDomains={missingDomains} />
      {expandedDomains.length > 0 ? (
        <div className={styles.dhApiStructureGrid} data-testid="dashboard-home-structure-expanded-grid">
          {expandedDomains.map((domain) => (
            <StructureMiniCard key={domain.id} domain={domain} />
          ))}
        </div>
      ) : null}
      <StructureGapBand missingDomains={missingDomains} />
    </section>
  );
}

function MarketCalendarContextPanel({ view }: { view: DashboardHomeBodyView }) {
  const context = view.marketContext;
  const sourceRows = [
    ["市场利率", "补充", "自然日"],
    ["供给/招标", view.macroBriefing.supplyItems.length > 0 ? "可用" : "可能为空", "窗口"],
    ["债券新闻", view.bondNews.statusLabel.replace(/^来源状态：/, "") || "部分可用", "事件流"],
    ["宏观新闻", view.macroBriefing.newsStatusLabel.replace(/^来源状态：/, "") || "部分/延迟", "新闻流"],
  ];

  return (
    <article
      data-testid="dashboard-home-market-context"
      className={`${styles.dhApiModule} ${styles.dhApiMarketContext}`}
    >
      <div className={styles.dhApiModuleHead}>
        <h3>市场 / 日历上下文</h3>
        <span>自然日补充信息，不参与严格 KPI 核验</span>
      </div>
      <p>今日市场解释：{context.temperatureLabel}</p>
      <p>{context.aiSummary[0] ?? "市场利率、债券新闻、供给日历和曲线解释由延迟查询补充加载。"}</p>
      <Link
        to={buildReportDatePath("/bond-analysis", view.reportDate)}
        className={styles.dhPanelDrillLink}
      >
        曲线/利差 →
      </Link>
      <div className={styles.dhApiMarketRows}>
        {sourceRows.map(([label, state, basis]) => (
          <div key={label}>
            <span>{label}</span>
            <b>{state}</b>
            <code>{basis}</code>
          </div>
        ))}
      </div>
      <div className={styles.dhCompatibilityProbe}>
        {context.contextBlocks.map((block) => (
          <span key={block.id}>{block.label}</span>
        ))}
      </div>
    </article>
  );
}

function EvidenceRailPanel({ view }: { view: DashboardHomeBodyView }) {
  const sourceRows = buildSourceGateRows(view);
  const landedFormalRows = view.holdingRows.length + view.positionChanges.length;
  const landedAnalyticalRows = view.researchReports.length + view.incomeTrend.length;

  const rows = [
    {
      status: "GOV",
      tone: "ready" as HomeDataStateKind,
      title: "主快照",
      detail: `报告日 ${view.reportDate}；首屏结论由快照驱动`,
      result: "通过",
    },
    {
      status: "FORMAL",
      tone: landedFormalRows > 0 ? "ready" as HomeDataStateKind : "empty" as HomeDataStateKind,
      title: "正式台账",
      detail: `${view.holdingRows.length} 条重点券；${view.positionChanges.length} 条仓位变动`,
      result: landedFormalRows > 0 ? "通过" : "空",
    },
    {
      status: "ANALYTICAL",
      tone: landedAnalyticalRows > 0 ? "ready" as HomeDataStateKind : "partial" as HomeDataStateKind,
      title: "分析上下文",
      detail: `${view.researchReports.length} 条资讯；${view.incomeTrend.length} 个趋势点`,
      result: landedAnalyticalRows > 0 ? "通过" : "部分",
    },
    {
      status: "BLOCKED",
      tone: "error" as HomeDataStateKind,
      title: "保留缺口",
      detail: "预警 / 贡献 / 风险总览仍返回 503，不作为实时证据展示",
      result: "503",
    },
  ];

  return (
    <section className={`${styles.dhApiModule} ${styles.dhApiEvidenceRail}`}>
      <div className={styles.dhApiModuleHead}>
        <h3>证据链</h3>
        <span>主快照 · 正式台账 · 分析上下文 · 保留缺口</span>
      </div>
      <div className={styles.dhApiEvidenceRows}>
        {rows.map((row) => (
          <div key={row.status} className={styles.dhApiEvidenceRow} data-tone={row.tone}>
            <span className={stateClass(row.tone)}>{row.status}</span>
            <b>{row.title}</b>
            <code>{row.detail}</code>
            <strong className={stateClass(row.tone)}>{row.result}</strong>
          </div>
        ))}
      </div>
      <div className={styles.dhCompatibilityProbe}>
        {sourceRows.map((row) => (
          <span key={row.id}>{row.source} {sourceGateStatusLabel(row.status)}</span>
        ))}
      </div>
    </section>
  );
}

function LegacyExpandedPanels({
  view,
  enabled,
}: {
  view: DashboardHomeBodyView;
  enabled: boolean;
}) {
  if (!enabled) {
    return null;
  }

  return (
    <div className={`${styles.dhCompatibilityProbe} ${styles.dhGridFullRow}`}>
      <span>资产分布</span>
      <span>评级分布</span>
      <span>行业分布</span>
      <span>久期分布</span>
      <span>收益率分布</span>
      <span>组合对比</span>
      <span>{view.riskExposureState.label}</span>
      <span>{view.assetDistributionState.label}</span>
      <span>{view.ratingDistributionState.label}</span>
      <span>{view.maturityDistributionState.label}</span>
      <span>{view.industryDistributionState.label}</span>
      <span>{view.yieldDistributionState.label}</span>
      <span>{view.portfolioComparisonState.label}</span>
    </div>
  );
}

export function TerminalHomeWorkGrid({
  view,
  homeAvailabilityKind = "normal",
}: TerminalHomeWorkGridProps) {
  const isServiceUnavailable = homeAvailabilityKind === "serviceUnavailable";
  return (
    <section
      data-testid="dashboard-home-work-grid"
      className={`${styles.dhApiHomeBody} ${isServiceUnavailable ? styles.dhTerminalGridUnavailable : ""}`}
    >
      {isServiceUnavailable ? <HomeDataAvailabilityPanel view={view} /> : null}

      <MobileDetailFold title="数据契约" meta="接口 + 来源台账">
        <ApiDataDirectoryPanel view={view} />
        <SourceGatePanel view={view} />
      </MobileDetailFold>

      <MobileDetailFold title="Portfolio Detail" meta={`${view.holdingRows.length} holdings`}>
        <div className={styles.dhApiLedgerGrid}>
          <HoldingsPanel view={view} />
          <div className={styles.dhApiSideStack}>
            <RiskSummaryPanel view={view} />
            <PositionChangesPanel view={view} />
          </div>
          <IncomeTrendPanel view={view} />
        </div>
      </MobileDetailFold>

      <MobileDetailFold title="Structure Context" meta="risk + distributions">
        <StructureBoardPanel view={view} />

        <div className={styles.dhApiContextGrid}>
          <ResearchReportsPanel view={view} />
          <MarketCalendarContextPanel view={view} />
        </div>
      </MobileDetailFold>

      <MobileDetailFold title="Audit Rail" meta="evidence chain">
        <EvidenceRailPanel view={view} />
      </MobileDetailFold>
      <LegacyExpandedPanels view={view} enabled />
    </section>
  );
}
