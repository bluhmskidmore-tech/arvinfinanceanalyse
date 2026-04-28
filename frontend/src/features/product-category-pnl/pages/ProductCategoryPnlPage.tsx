import { useEffect, useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type { ProductCategoryManualAdjustmentRequest } from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import MonthlyOperatingAnalysisBranch from "./MonthlyOperatingAnalysisBranch";
import "./ProductCategoryPnlPage.css";
import { ProductCategoryGovernanceStrip } from "./ProductCategoryGovernanceStrip";
import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS,
  buildProductCategoryDiagnosticsSurface,
  buildProductCategoryLiabilitySideTrendSurface,
  buildProductCategoryTrendSnapshot,
  buildLedgerPnlHrefForReportDate,
  collectProductCategoryGovernanceNotices,
  defaultProductCategoryScenarioRateForReportDate,
  formatProductCategoryDualMetaDistinctLine,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
  nextDefaultReportDateIfUnset,
  selectProductCategoryCurrencyNetIncomeChart,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
  selectProductCategoryInterestEarningIncomeScaleChart,
  selectProductCategoryInterestSpreadChart,
  selectProductCategoryTplScaleYieldChart,
  selectProductCategoryTrendReportPoints,
  toneForProductCategoryValue,
} from "./productCategoryPnlPageModel";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  marginBottom: 18,
} as const;

const chipTypography = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase" as const,
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginBottom: 14,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: designTokens.color.neutral[500],
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: designTokens.color.neutral[600],
  fontSize: 13,
  lineHeight: 1.7,
} as const;

function formatProductCategoryRefreshStatusLine(
  snapshot: { status: string; run_id?: string } | null,
): string {
  const statusPart = snapshot ? `状态：${snapshot.status}` : "状态：启动中…";
  const runPart = snapshot?.run_id ? `；run_id：${snapshot.run_id}` : "";
  return `正在刷新产品分类损益数据。${statusPart}${runPart}。刷新期间「刷新损益数据」等部分控件将暂时不可用。`;
}

function buildAdjustmentDraft(reportDate: string): ProductCategoryManualAdjustmentRequest {
  return {
    report_date: reportDate,
    operator: "DELTA",
    approval_status: "approved",
    account_code: "",
    currency: "CNX",
    account_name: "",
    beginning_balance: null,
    ending_balance: null,
    monthly_pnl: null,
    daily_avg_balance: null,
    annual_avg_balance: null,
  };
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function diagnosticsToneClassName(tone: "neutral" | "positive" | "negative"): string {
  if (tone === "positive") {
    return "product-category-diagnostics__value--positive";
  }
  if (tone === "negative") {
    return "product-category-diagnostics__value--negative";
  }
  return "";
}

type DerivedChartPanelProps = {
  testId: string;
  title: string;
  description: string;
  option: EChartsOption | null;
};

function buildDualAxisChartOption(input: {
  labels: string[];
  leftAxisName: string;
  rightAxisName: string;
  series: Array<{
    name: string;
    type: "bar" | "line";
    data: number[];
    yAxisIndex: 0 | 1;
    color: string;
  }>;
}): EChartsOption | null {
  if (!input.labels.length || input.series.every((series) => series.data.length === 0)) {
    return null;
  }
  return {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: input.series.map((series) => series.name) },
    grid: { left: 56, right: 56, top: 20, bottom: input.labels.length > 6 ? 64 : 52 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: { interval: 0, rotate: input.labels.length > 6 ? 24 : 0 },
      axisLine: { lineStyle: { color: designTokens.color.neutral[300] } },
    },
    yAxis: [
      {
        type: "value",
        name: input.leftAxisName,
        splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[200] } },
      },
      {
        type: "value",
        name: input.rightAxisName,
        splitLine: { show: false },
      },
    ],
    series: input.series.map((series) => ({
      name: series.name,
      type: series.type,
      yAxisIndex: series.yAxisIndex,
      data: series.data,
      smooth: series.type === "line",
      itemStyle: { color: series.color },
      lineStyle: { color: series.color, width: series.type === "line" ? 3 : undefined },
      barMaxWidth: series.type === "bar" ? 26 : undefined,
    })),
  };
}

function buildSingleAxisChartOption(input: {
  labels: string[];
  axisName: string;
  series: Array<{
    name: string;
    type: "bar" | "line";
    data: number[];
    color: string;
  }>;
}): EChartsOption | null {
  if (!input.labels.length || input.series.every((series) => series.data.length === 0)) {
    return null;
  }
  return {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: input.series.map((series) => series.name) },
    grid: { left: 56, right: 24, top: 20, bottom: input.labels.length > 6 ? 64 : 52 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: { interval: 0, rotate: input.labels.length > 6 ? 24 : 0 },
      axisLine: { lineStyle: { color: designTokens.color.neutral[300] } },
    },
    yAxis: {
      type: "value",
      name: input.axisName,
      splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[200] } },
    },
    series: input.series.map((series) => ({
      name: series.name,
      type: series.type,
      data: series.data,
      smooth: series.type === "line",
      itemStyle: { color: series.color },
      lineStyle: { color: series.color, width: series.type === "line" ? 3 : undefined },
      barMaxWidth: series.type === "bar" ? 26 : undefined,
    })),
  };
}

function buildInterestSpreadChartOption(input: {
  labels: string[];
  series: Array<{
    name: string;
    data: number[];
    color: string;
  }>;
}): EChartsOption | null {
  if (!input.labels.length || input.series.every((series) => series.data.length === 0)) {
    return null;
  }
  const values = input.series.flatMap((series) => series.data).filter(Number.isFinite);
  const minValue = values.length ? Math.min(...values) : 0;
  const maxValue = values.length ? Math.max(...values) : 0;
  const range = maxValue - minValue;
  const padding = Math.max(range * 0.12, Math.abs(maxValue || minValue) * 0.08, 0.1);
  const yAxisMin = Number((minValue - padding).toFixed(2));
  const yAxisMax = Number((maxValue + padding).toFixed(2));
  const lineWidths = [4, 3.4, 4];
  const symbolSizes = [8, 7, 8];
  return {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: input.series.map((series) => series.name) },
    grid: { left: 56, right: 72, top: 20, bottom: input.labels.length > 6 ? 64 : 52 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: { interval: 0, rotate: input.labels.length > 6 ? 24 : 0 },
      axisLine: { lineStyle: { color: designTokens.color.neutral[300] } },
    },
    yAxis: {
      type: "value",
      name: "%",
      min: yAxisMin,
      max: yAxisMax,
      scale: true,
      axisLabel: { formatter: "{value}%" },
      splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[200] } },
    },
    series: input.series.map((series, index) => ({
      name: series.name,
      type: "line",
      data: series.data,
      smooth: true,
      showSymbol: true,
      symbol: "circle",
      symbolSize: symbolSizes[index] ?? 7,
      itemStyle: { color: series.color, borderColor: "#fff", borderWidth: 2 },
      lineStyle: { color: series.color, width: lineWidths[index] ?? 3.4 },
      endLabel: {
        show: true,
        color: series.color,
        formatter: "{c}%",
        fontWeight: 700,
      },
      labelLayout: { moveOverlap: "shiftY" },
      emphasis: { focus: "series" },
    })),
  };
}

function buildLiabilitySideTrendChartOption(input: {
  labels: string[];
  averageDaily: Array<number | null>;
  rate: Array<number | null>;
}): EChartsOption | null {
  if (!input.labels.length) {
    return null;
  }
  return {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["负债端日均额（亿元）", "负债端利率（%）"] },
    grid: { left: 56, right: 64, top: 20, bottom: input.labels.length > 6 ? 64 : 52 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: { interval: 0, rotate: input.labels.length > 6 ? 24 : 0 },
      axisLine: { lineStyle: { color: designTokens.color.neutral[300] } },
    },
    yAxis: [
      {
        type: "value",
        name: "亿元",
        splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[200] } },
      },
      {
        type: "value",
        name: "%",
        scale: true,
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "负债端日均额（亿元）",
        type: "bar",
        yAxisIndex: 0,
        data: input.averageDaily,
        itemStyle: { color: designTokens.color.primary[600] },
        barMaxWidth: 28,
      },
      {
        name: "负债端利率（%）",
        type: "line",
        yAxisIndex: 1,
        data: input.rate,
        smooth: true,
        showSymbol: true,
        symbol: "circle",
        symbolSize: 7,
        itemStyle: { color: designTokens.color.warning[600], borderColor: "#fff", borderWidth: 2 },
        lineStyle: { color: designTokens.color.warning[600], width: 3.4 },
        emphasis: { focus: "series" },
      },
    ],
  };
}

function DerivedChartPanel(props: DerivedChartPanelProps) {
  if (!props.option) {
    return null;
  }
  return (
    <article className="product-category-derived-chart" data-testid={props.testId}>
      <div className="product-category-derived-chart__header">
        <h3 className="product-category-derived-chart__title">{props.title}</h3>
        <p className="product-category-derived-chart__description">{props.description}</p>
      </div>
      <ReactECharts
        option={props.option}
        className="product-category-derived-chart__canvas"
        notMerge
        lazyUpdate
      />
    </article>
  );
}

export default function ProductCategoryPnlPage() {
  const client = useApiClient();
  const [selectedBranch, setSelectedBranch] = useState<"product_category_pnl" | "monthly_operating_analysis">("product_category_pnl");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedView, setSelectedView] = useState("monthly");
  const [scenarioRate, setScenarioRate] = useState("1.75");
  const [appliedScenarioRate, setAppliedScenarioRate] = useState("");
  const [scenarioRateTouched, setScenarioRateTouched] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshPollSnapshot, setRefreshPollSnapshot] = useState<{ status: string; run_id?: string } | null>(
    null,
  );
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [isSubmittingAdjustment, setIsSubmittingAdjustment] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [lastAdjustmentId, setLastAdjustmentId] = useState<string | null>(null);
  const [adjustmentDraft, setAdjustmentDraft] = useState<ProductCategoryManualAdjustmentRequest>(
    buildAdjustmentDraft(""),
  );

  const datesQuery = useQuery({
    queryKey: ["product-category-pnl", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  useEffect(() => {
    const next = nextDefaultReportDateIfUnset(selectedDate, datesQuery.data?.result.report_dates);
    if (next !== null) {
      setSelectedDate(next);
    }
  }, [datesQuery.data, selectedDate]);

  useEffect(() => {
    setAdjustmentDraft((current) => ({
      ...current,
      report_date: selectedDate,
    }));
  }, [selectedDate]);

  useEffect(() => {
    if (!selectedDate || scenarioRateTouched) {
      return;
    }
    const defaultRate = defaultProductCategoryScenarioRateForReportDate(selectedDate);
    setScenarioRate(defaultRate);
    setAppliedScenarioRate((current) => (current ? defaultRate : current));
  }, [scenarioRateTouched, selectedDate]);

  const handleReportDateChange = (nextDate: string) => {
    const defaultRate = defaultProductCategoryScenarioRateForReportDate(nextDate);
    setSelectedDate(nextDate);
    setScenarioRate(defaultRate);
    setScenarioRateTouched(false);
    setAppliedScenarioRate((current) => (current ? defaultRate : current));
  };

  const baselineQuery = useQuery({
    queryKey: ["product-category-pnl", "baseline", client.mode, selectedDate, selectedView],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const scenarioQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "scenario",
      client.mode,
      selectedDate,
      selectedView,
      appliedScenarioRate,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
        scenarioRatePct: appliedScenarioRate,
      }),
    enabled: Boolean(selectedDate && appliedScenarioRate),
    retry: false,
  });

  const adjustmentsQuery = useQuery({
    queryKey: ["product-category-pnl", "adjustments", client.mode, selectedDate],
    queryFn: () => client.getProductCategoryManualAdjustments(selectedDate),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const baseline = baselineQuery.data?.result;
  const scenario = scenarioQuery.data?.result;
  const displayedGrandTotal = selectDisplayedProductCategoryGrandTotal(
    scenario?.grand_total,
    baseline?.grand_total,
  );
  const baselineRate = baseline?.asset_total.baseline_ftp_rate_pct ?? "1.75";
  const currentSceneRate = scenario?.scenario_rate_pct ?? baselineRate;
  const displayedAssetTotal = scenario?.asset_total ?? baseline?.asset_total;
  const displayedLiabilityTotal = scenario?.liability_total ?? baseline?.liability_total;
  const currentSelectedPayload = scenario ?? baseline;

  const rowsToRender = useMemo(
    () => selectProductCategoryDetailRows(baseline?.rows, scenario?.rows),
    [baseline?.rows, scenario?.rows],
  );
  const trendReportPoints = useMemo(
    () => selectProductCategoryTrendReportPoints(selectedDate, datesQuery.data?.result.report_dates, selectedView),
    [datesQuery.data?.result.report_dates, selectedDate, selectedView],
  );
  const currentTrendPoint = useMemo(
    () => trendReportPoints.find((point) => point.reportDate === selectedDate),
    [selectedDate, trendReportPoints],
  );
  const trendHistoryPoints = useMemo(
    () => trendReportPoints.filter((point) => point.reportDate !== selectedDate),
    [selectedDate, trendReportPoints],
  );
  const trendHistoryQueries = useQueries({
    queries: trendHistoryPoints.map((point) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history",
        client.mode,
        point.reportDate,
        point.view,
        appliedScenarioRate,
      ],
      queryFn: () =>
        client.getProductCategoryPnl({
          reportDate: point.reportDate,
          view: point.view,
          ...(appliedScenarioRate ? { scenarioRatePct: appliedScenarioRate } : {}),
        }),
      enabled: Boolean(point.reportDate && point.view),
      retry: false,
    })),
  });
  const trendSnapshots = useMemo(
    () => [
      ...(currentSelectedPayload
        ? [buildProductCategoryTrendSnapshot(currentSelectedPayload, currentTrendPoint?.label)]
        : []),
      ...trendHistoryQueries.flatMap((query, index) =>
        query.data ? [buildProductCategoryTrendSnapshot(query.data.result, trendHistoryPoints[index]?.label)] : [],
      ),
    ],
    [currentSelectedPayload, currentTrendPoint?.label, trendHistoryPoints, trendHistoryQueries],
  );
  const diagnosticsSurface = useMemo(
    () =>
      buildProductCategoryDiagnosticsSurface({
        rows: rowsToRender,
        assetTotal: displayedAssetTotal,
        liabilityTotal: displayedLiabilityTotal,
        grandTotal: displayedGrandTotal,
        trendSnapshots,
      }),
    [displayedAssetTotal, displayedGrandTotal, displayedLiabilityTotal, rowsToRender, trendSnapshots],
  );
  const hasDiagnosticsSurface =
    diagnosticsSurface.matrixRows.length > 0 ||
    diagnosticsSurface.matrixEmptyCopy !== null ||
    diagnosticsSurface.negativeWatchlistRows.length > 0 ||
    diagnosticsSurface.negativeWatchlistEmptyCopy !== null ||
    diagnosticsSurface.spreadAttribution.state === "ready" ||
    (diagnosticsSurface.spreadAttribution.state === "incomplete" &&
      diagnosticsSurface.spreadAttribution.reason.length > 0);
  const liabilitySideTrendSurface = useMemo(
    () => buildProductCategoryLiabilitySideTrendSurface(trendSnapshots),
    [trendSnapshots],
  );
  const tplScaleYieldChart = useMemo(
    () => selectProductCategoryTplScaleYieldChart(trendSnapshots),
    [trendSnapshots],
  );
  const currencyNetIncomeChart = useMemo(
    () => selectProductCategoryCurrencyNetIncomeChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestEarningIncomeScaleChart = useMemo(
    () => selectProductCategoryInterestEarningIncomeScaleChart(trendSnapshots),
    [trendSnapshots],
  );
  const interestSpreadChart = useMemo(
    () => selectProductCategoryInterestSpreadChart(trendSnapshots),
    [trendSnapshots],
  );
  const tplScaleYieldOption = useMemo(
    () =>
      tplScaleYieldChart
        ? buildDualAxisChartOption({
            labels: tplScaleYieldChart.labels,
            leftAxisName: "亿元",
            rightAxisName: "%",
            series: [
              {
                name: "人民币规模（亿元）",
                type: "bar",
                data: tplScaleYieldChart.cnyScale,
                yAxisIndex: 0,
                color: designTokens.color.primary[500],
              },
              {
                name: "外币规模（亿元）",
                type: "bar",
                data: tplScaleYieldChart.foreignScale,
                yAxisIndex: 0,
                color: designTokens.color.warning[500],
              },
              {
                name: "收益率（%）",
                type: "line",
                data: tplScaleYieldChart.weightedYield,
                yAxisIndex: 1,
                color: designTokens.color.success[600],
              },
            ],
          })
        : null,
    [tplScaleYieldChart],
  );
  const currencyNetIncomeOption = useMemo(
    () =>
      currencyNetIncomeChart
        ? buildSingleAxisChartOption({
            labels: currencyNetIncomeChart.labels,
            axisName: "亿元",
            series: [
              {
                name: "人民币净收入（亿元）",
                type: "bar",
                data: currencyNetIncomeChart.cnyNet,
                color: designTokens.color.primary[500],
              },
              {
                name: "外币净收入（亿元）",
                type: "bar",
                data: currencyNetIncomeChart.foreignNet,
                color: designTokens.color.warning[500],
              },
            ],
          })
        : null,
    [currencyNetIncomeChart],
  );
  const interestEarningIncomeScaleOption = useMemo(
    () =>
      interestEarningIncomeScaleChart
        ? buildDualAxisChartOption({
            labels: interestEarningIncomeScaleChart.labels,
            leftAxisName: "亿元",
            rightAxisName: "亿元",
            series: [
              {
                name: "生息资产规模（亿元）",
                type: "bar",
                data: interestEarningIncomeScaleChart.scale,
                yAxisIndex: 0,
                color: designTokens.color.info[500],
              },
              {
                name: "生息资产收入（亿元）",
                type: "line",
                data: interestEarningIncomeScaleChart.income,
                yAxisIndex: 1,
                color: designTokens.color.success[600],
              },
            ],
          })
        : null,
    [interestEarningIncomeScaleChart],
  );
  const interestSpreadOption = useMemo(
    () =>
      interestSpreadChart
        ? buildInterestSpreadChartOption({
            labels: interestSpreadChart.labels,
            series: [
              {
                name: "生息资产收益率（%）",
                data: interestSpreadChart.assetYield,
                color: designTokens.color.success[600],
              },
              {
                name: "负债端加权收益率（%）",
                data: interestSpreadChart.liabilityYield,
                color: designTokens.color.neutral[500],
              },
              {
                name: "生息资产利差（%）",
                data: interestSpreadChart.spread,
                color: designTokens.color.danger[500],
              },
            ],
          })
        : null,
    [interestSpreadChart],
  );
  const liabilitySideTrendOption = useMemo(
    () =>
      liabilitySideTrendSurface.chart
        ? buildLiabilitySideTrendChartOption({
            labels: liabilitySideTrendSurface.chart.labels,
            averageDaily: liabilitySideTrendSurface.chart.totalAverageDaily,
            rate: liabilitySideTrendSurface.chart.totalRate,
          })
        : null,
    [liabilitySideTrendSurface.chart],
  );

  async function runRefreshWorkflow() {
    const payload = await runPollingTask({
      start: () => client.refreshProductCategoryPnl(),
      getStatus: (runId) => client.getProductCategoryRefreshStatus(runId),
      onUpdate: (pollPayload) => {
        setRefreshPollSnapshot({ status: pollPayload.status, run_id: pollPayload.run_id });
      },
    });
    setLastRefreshRunId(payload.run_id);
    if (payload.status !== "completed") {
      throw new Error(payload.detail ?? `刷新任务未完成：${payload.status}`);
    }
    await datesQuery.refetch();
    await baselineQuery.refetch();
    await adjustmentsQuery.refetch();
    if (appliedScenarioRate) {
      await scenarioQuery.refetch();
    }
  }

  async function handleRefresh() {
    setIsRefreshing(true);
    setRefreshError(null);
    setRefreshPollSnapshot(null);
    try {
      await runRefreshWorkflow();
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新损益数据失败");
    } finally {
      setIsRefreshing(false);
      setRefreshPollSnapshot(null);
    }
  }

  function updateAdjustmentField<K extends keyof ProductCategoryManualAdjustmentRequest>(
    key: K,
    value: ProductCategoryManualAdjustmentRequest[K],
  ) {
    setAdjustmentDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleManualAdjustmentSubmit() {
    setAdjustmentError(null);
    if (!adjustmentDraft.report_date) {
      setAdjustmentError("请选择报表月份。");
      return;
    }
    if (!adjustmentDraft.account_code.trim()) {
      setAdjustmentError("请输入科目代码。");
      return;
    }
    if (
      !adjustmentDraft.beginning_balance &&
      !adjustmentDraft.ending_balance &&
      !adjustmentDraft.monthly_pnl &&
      !adjustmentDraft.daily_avg_balance &&
      !adjustmentDraft.annual_avg_balance
    ) {
      setAdjustmentError("至少填写一个调整数值。");
      return;
    }

    setIsSubmittingAdjustment(true);
    try {
      const payload = editingAdjustmentId
        ? await client.updateProductCategoryManualAdjustment(editingAdjustmentId, adjustmentDraft)
        : await client.createProductCategoryManualAdjustment(adjustmentDraft);
      setLastAdjustmentId(payload.adjustment_id);
      await runRefreshWorkflow();
      setShowManualForm(false);
      setEditingAdjustmentId(null);
      setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "手工录入失败");
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  async function handleManualAdjustmentRevoke(adjustmentId: string) {
    setAdjustmentError(null);
    setIsSubmittingAdjustment(true);
    try {
      await client.revokeProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "撤销手工录入失败");
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  async function handleManualAdjustmentRestore(adjustmentId: string) {
    setAdjustmentError(null);
    setIsSubmittingAdjustment(true);
    try {
      await client.restoreProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "恢复手工录入失败");
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  function handleManualAdjustmentEdit(adjustment: {
    adjustment_id: string;
    report_date: string;
    operator: "ADD" | "DELTA" | "OVERRIDE";
    approval_status: "approved" | "pending" | "rejected";
    account_code: string;
    currency: "CNX" | "CNY";
    account_name?: string;
    beginning_balance?: string | null;
    ending_balance?: string | null;
    monthly_pnl?: string | null;
    daily_avg_balance?: string | null;
    annual_avg_balance?: string | null;
  }) {
    setEditingAdjustmentId(adjustment.adjustment_id);
    setAdjustmentDraft({
      report_date: adjustment.report_date,
      operator: adjustment.operator,
      approval_status: adjustment.approval_status,
      account_code: adjustment.account_code,
      currency: adjustment.currency,
      account_name: adjustment.account_name ?? "",
      beginning_balance: adjustment.beginning_balance ?? null,
      ending_balance: adjustment.ending_balance ?? null,
      monthly_pnl: adjustment.monthly_pnl ?? null,
      daily_avg_balance: adjustment.daily_avg_balance ?? null,
      annual_avg_balance: adjustment.annual_avg_balance ?? null,
    });
    setAdjustmentError(null);
    setShowManualForm(true);
  }

  const governanceNotices = collectProductCategoryGovernanceNotices(baselineQuery.data?.result_meta);
  const formalScenarioDistinct =
    baselineQuery.data?.result_meta && scenarioQuery.data?.result_meta
      ? formatProductCategoryDualMetaDistinctLine(
          baselineQuery.data.result_meta,
          scenarioQuery.data.result_meta,
        )
      : null;

  const reportExtra =
    baseline && !baselineQuery.isError ? (
      <div
        data-testid="product-category-summary"
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          justifyContent: "flex-end",
          color: designTokens.color.neutral[600],
          fontSize: 13,
        }}
      >
        <span>当前场景：{currentSceneRate}%</span>
        <span>基准场景：{baselineRate}%</span>
        <span style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>
          合计：{formatProductCategoryValue(displayedGrandTotal?.business_net_income)}
        </span>
      </div>
    ) : null;
  const ledgerPnlHref = buildLedgerPnlHrefForReportDate(selectedDate);

  if (selectedBranch === "monthly_operating_analysis") {
    return (
      <section data-testid="product-category-page">
        <FilterBar style={{ marginBottom: 16 }}>
          <button
            type="button"
            data-testid="product-category-branch-product-category-pnl"
            aria-pressed="false"
            onClick={() => setSelectedBranch("product_category_pnl")}
          >
            产品分类损益
          </button>
          <button
            type="button"
            data-testid="product-category-branch-monthly-operating-analysis"
            aria-pressed="true"
            onClick={() => setSelectedBranch("monthly_operating_analysis")}
          >
            月度经营分析
          </button>
        </FilterBar>
        <MonthlyOperatingAnalysisBranch />
      </section>
    );
  }

  return (
    <section data-testid="product-category-page">
      <FilterBar style={{ marginBottom: 16 }}>
        <button
          type="button"
          data-testid="product-category-branch-product-category-pnl"
          aria-pressed="true"
          onClick={() => setSelectedBranch("product_category_pnl")}
        >
          产品分类损益
        </button>
        <button
          type="button"
          data-testid="product-category-branch-monthly-operating-analysis"
          aria-pressed="false"
          onClick={() => setSelectedBranch("monthly_operating_analysis")}
        >
          月度经营分析
        </button>
      </FilterBar>
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="product-category-page-title"
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 700,
              letterSpacing: "-0.03em",
            }}
          >
            产品分类损益
          </h1>
          <p
            data-testid="product-category-page-subtitle"
            style={{
              marginTop: 8,
              marginBottom: 0,
              color: designTokens.color.neutral[600],
              fontSize: 14,
              lineHeight: 1.7,
            }}
          >
            按业务分类查看损益、FTP 和净收入。用于经营分析，不等同于逐笔损益明细。
          </p>
          <p data-testid="product-category-boundary-copy" style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 12 }}>
            系统层经营口径：正式基线来自正式读模型；情景预览仅在显式应用后生效。
          </p>
          {isRefreshing ? (
            <p data-testid="product-category-refresh-status">
              {formatProductCategoryRefreshStatusLine(refreshPollSnapshot)}
            </p>
          ) : null}
          {lastRefreshRunId ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 12 }}>
              最近刷新任务：{lastRefreshRunId}
            </p>
          ) : null}
          {lastAdjustmentId ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 12 }}>
              最近录入调整：{lastAdjustmentId}
            </p>
          ) : null}
          {refreshError ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.danger[700], fontSize: 12 }}>
              {refreshError}
            </p>
          ) : null}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <span
            data-testid="product-category-role-badge"
            style={{
              ...chipTypography,
              background: designTokens.color.primary[50],
              color: designTokens.color.primary[600],
            }}
          >
            系统层
          </span>
          <span
            style={{
              ...chipTypography,
              background:
                client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
              color:
                client.mode === "real"
                  ? displayTokens.apiMode.realForeground
                  : displayTokens.apiMode.mockForeground,
            }}
          >
            {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
          </span>
          <a data-testid="product-category-audit-link" href="/product-category-pnl/audit">
            查看调整审计
          </a>
          <a data-testid="product-category-ledger-link" href={ledgerPnlHref}>
            总账损益
          </a>
          <button
            type="button"
            data-testid="product-category-manual-button"
            onClick={() => {
              setShowManualForm((current) => !current);
              setEditingAdjustmentId(null);
              setAdjustmentError(null);
              if (showManualForm) {
                setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
              }
            }}
            style={{
              padding: "10px 16px",
              borderRadius: 12,
              border: `1px solid ${designTokens.color.neutral[900]}`,
              background: designTokens.color.neutral[50],
              color: designTokens.color.neutral[900],
              fontWeight: 600,
            }}
          >
            + 手工录入
          </button>
          <button
            type="button"
            data-testid="product-category-refresh-button"
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
            style={{
              padding: "10px 16px",
              borderRadius: 12,
              border: `1px solid ${designTokens.color.neutral[900]}`,
              background: designTokens.color.neutral[50],
              color: designTokens.color.neutral[900],
              fontWeight: 600,
              cursor: isRefreshing ? "progress" : "pointer",
              opacity: isRefreshing ? 0.7 : 1,
            }}
          >
            {isRefreshing ? "刷新中..." : "刷新损益数据"}
          </button>
        </div>
      </div>

      <ProductCategoryGovernanceStrip
        asOfDateGapText={PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY}
        notices={governanceNotices}
        formalScenarioDistinct={formalScenarioDistinct}
      />

      <FormalResultMetaPanel
        testId="product-category-result-meta"
        title="产品分类结果元信息"
        sections={[
          {
            key: "baseline",
            title: "基线读模型",
            meta: baselineQuery.data?.result_meta,
          },
          {
            key: "scenario",
            title: "场景覆盖",
            meta: scenarioQuery.data?.result_meta,
          },
        ]}
      />

      {showManualForm ? (
        <div
          data-testid="product-category-manual-form"
          style={{
            display: "grid",
            gap: 12,
            marginBottom: 18,
            padding: 18,
            borderRadius: 18,
            border: `1px solid ${designTokens.color.neutral[200]}`,
            background: designTokens.color.neutral[50],
          }}
        >
          <div style={{ fontWeight: 600 }}>
            {editingAdjustmentId ? "编辑手工录入" : "手工录入"}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <label style={{ display: "grid", gap: 6 }}>
              报表日期
              <input
                aria-label="手工录入-报表日期"
                value={adjustmentDraft.report_date}
                readOnly
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              操作方式
              <select
                aria-label="手工录入-操作方式"
                value={adjustmentDraft.operator}
                onChange={(event) =>
                  updateAdjustmentField(
                    "operator",
                    event.target.value as "ADD" | "DELTA" | "OVERRIDE",
                  )
                }
              >
                <option value="ADD">新增</option>
                <option value="DELTA">差额调整</option>
                <option value="OVERRIDE">覆盖</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              币种
              <select
                aria-label="手工录入-币种"
                value={adjustmentDraft.currency}
                onChange={(event) =>
                  updateAdjustmentField("currency", event.target.value as "CNX" | "CNY")
                }
              >
                <option value="CNX">CNX</option>
                <option value="CNY">CNY</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              科目代码
              <input
                aria-label="手工录入-科目代码"
                value={adjustmentDraft.account_code}
                onChange={(event) => updateAdjustmentField("account_code", event.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              科目名称
              <input
                aria-label="手工录入-科目名称"
                value={adjustmentDraft.account_name ?? ""}
                onChange={(event) => updateAdjustmentField("account_name", event.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              审批状态
              <select
                aria-label="手工录入-审批状态"
                value={adjustmentDraft.approval_status}
                onChange={(event) =>
                  updateAdjustmentField(
                    "approval_status",
                    event.target.value as "approved" | "pending" | "rejected",
                  )
                }
              >
                <option value="approved">已通过</option>
                <option value="pending">待审批</option>
                <option value="rejected">已拒绝</option>
              </select>
            </label>
            {[
              ["beginning_balance", "期初余额"],
              ["ending_balance", "期末余额"],
              ["monthly_pnl", "月度损益"],
              ["daily_avg_balance", "月日均"],
              ["annual_avg_balance", "年日均"],
            ].map(([field, label]) => (
              <label key={field} style={{ display: "grid", gap: 6 }}>
                {label}
                <input
                  aria-label={`手工录入-${label}`}
                  value={(adjustmentDraft as Record<string, string | null | undefined>)[field] ?? ""}
                  onChange={(event) =>
                    updateAdjustmentField(
                      field as keyof ProductCategoryManualAdjustmentRequest,
                      event.target.value || null,
                    )
                  }
                />
              </label>
            ))}
          </div>
          {adjustmentError ? (
            <div
              data-testid="product-category-manual-error"
              style={{ color: designTokens.color.danger[700], fontSize: 12 }}
            >
              {adjustmentError}
            </div>
          ) : null}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              data-testid="product-category-manual-submit"
              onClick={() => void handleManualAdjustmentSubmit()}
              disabled={isSubmittingAdjustment}
            >
              {isSubmittingAdjustment
                ? "提交中..."
                : editingAdjustmentId
                  ? "保存并刷新"
                  : "提交并刷新"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowManualForm(false);
                setEditingAdjustmentId(null);
                setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
              }}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}

      <SectionLead
        eyebrow="治理"
        title="手工调整与审计"
        description="手工调整仍走既有新增、更新、撤销、恢复接口，完整事件时间线保留在独立审计视图。仅当审批通过可撤销、仅当已拒绝可恢复；其余审批状态下对应按钮为禁用。撤销、恢复、保存后均触发与全页「刷新损益数据」一致的损益刷新工作流以更新本列表。"
        testId="product-category-adjustment-lead"
      />
      <AsyncSection
        title="手工调整历史"
        isLoading={adjustmentsQuery.isLoading}
        isError={adjustmentsQuery.isError}
        isEmpty={
          !adjustmentsQuery.isLoading &&
          !adjustmentsQuery.isError &&
          (adjustmentsQuery.data?.adjustments.length ?? 0) === 0
        }
        fillHeight={false}
        onRetry={() => void adjustmentsQuery.refetch()}
      >
        <div
          data-testid="product-category-adjustment-history"
          style={{ display: "grid", gap: 10 }}
        >
          <div style={{ fontWeight: 600 }}>当前状态</div>
          {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
            <div
              key={`current-${item.adjustment_id}`}
              style={{
                display: "grid",
                gridTemplateColumns: "1.2fr 0.8fr 0.8fr 0.8fr auto auto auto",
                gap: 12,
                alignItems: "center",
                padding: 12,
                borderRadius: 12,
                border: `1px solid ${designTokens.color.neutral[200]}`,
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{item.account_code}</div>
                <div style={{ color: designTokens.color.neutral[600], fontSize: 12 }}>
                  {item.account_name || "未填写科目名称"}
                </div>
                <div style={{ color: designTokens.color.neutral[500], fontSize: 12 }}>
                  最近事件：{item.event_type}
                </div>
              </div>
              <div>{item.currency}</div>
              <div>{item.operator}</div>
              <div>{item.approval_status}</div>
              <button
                type="button"
                data-testid={`product-category-edit-${item.adjustment_id}`}
                disabled={isSubmittingAdjustment}
                onClick={() =>
                  handleManualAdjustmentEdit({
                    adjustment_id: item.adjustment_id,
                    report_date: item.report_date,
                    operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
                    approval_status: item.approval_status as "approved" | "pending" | "rejected",
                    account_code: item.account_code,
                    currency: item.currency as "CNX" | "CNY",
                    account_name: item.account_name,
                    beginning_balance: item.beginning_balance ?? null,
                    ending_balance: item.ending_balance ?? null,
                    monthly_pnl: item.monthly_pnl ?? null,
                    daily_avg_balance: item.daily_avg_balance ?? null,
                    annual_avg_balance: item.annual_avg_balance ?? null,
                  })
                }
              >
                编辑
              </button>
              <button
                type="button"
                data-testid={`product-category-revoke-${item.adjustment_id}`}
                disabled={item.approval_status !== "approved" || isSubmittingAdjustment}
                onClick={() => void handleManualAdjustmentRevoke(item.adjustment_id)}
              >
                撤销
              </button>
              <button
                type="button"
                data-testid={`product-category-restore-${item.adjustment_id}`}
                disabled={item.approval_status !== "rejected" || isSubmittingAdjustment}
                onClick={() => void handleManualAdjustmentRestore(item.adjustment_id)}
              >
                恢复
              </button>
            </div>
          ))}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              padding: 12,
              borderRadius: 12,
              border: `1px dashed ${designTokens.color.neutral[200]}`,
              background: designTokens.color.neutral[50],
            }}
          >
            <div style={{ display: "grid", gap: 4 }}>
              <div style={{ fontWeight: 600 }}>完整事件时间线已迁移到独立审计视图</div>
              <div style={{ color: designTokens.color.neutral[600], fontSize: 12 }}>
                当前报表月份共有 {(adjustmentsQuery.data?.events ?? []).length} 条调整事件。
              </div>
            </div>
            <a
              href="/product-category-pnl/audit"
              data-testid="product-category-audit-summary-link"
            >
              查看调整审计
            </a>
          </div>
        </div>
      </AsyncSection>

      <SectionLead
        eyebrow="场景"
        title="报告口径与场景预览"
        description="报告月份和视图模式驱动正式基线；FTP 场景只有点击应用后才触发情景查询，不覆盖正式结果。"
        testId="product-category-scenario-lead"
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.3fr 1.3fr 1.3fr",
          gap: 14,
          marginBottom: 18,
          padding: 18,
          borderRadius: 18,
          border: `1px solid ${designTokens.color.neutral[200]}`,
          background: designTokens.color.neutral[50],
        }}
      >
        <label style={{ display: "grid", gap: 8, fontSize: 13, color: designTokens.color.neutral[600] }}>
          选择报表月份
          <select
            aria-label="选择报表月份"
            value={selectedDate}
            onChange={(event) => handleReportDateChange(event.target.value)}
            style={{ padding: "10px 12px", borderRadius: 12, border: `1px solid ${designTokens.color.neutral[200]}` }}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {formatProductCategoryReportMonthLabel(reportDate)}
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: "grid", gap: 8, fontSize: 13, color: designTokens.color.neutral[600] }}>
          视图模式
          <div
            role="group"
            aria-label="视图模式"
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 6,
            }}
          >
            <button
              type="button"
              onClick={() => setSelectedView("monthly")}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: `1px solid ${designTokens.color.neutral[200]}`,
                background:
                  selectedView === "monthly"
                    ? designTokens.color.neutral[900]
                    : designTokens.color.neutral[50],
                color:
                  selectedView === "monthly"
                    ? designTokens.color.neutral[50]
                    : designTokens.color.neutral[900],
                fontWeight: 600,
              }}
            >
              月度视图
            </button>
            <button
              type="button"
              onClick={() => setSelectedView("ytd")}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: `1px solid ${designTokens.color.neutral[200]}`,
                background:
                  selectedView === "ytd"
                    ? designTokens.color.neutral[900]
                    : designTokens.color.neutral[50],
                color:
                  selectedView === "ytd"
                    ? designTokens.color.neutral[50]
                    : designTokens.color.neutral[900],
                fontWeight: 600,
              }}
            >
              汇总视图
            </button>
          </div>
        </label>

        <label style={{ display: "grid", gap: 8, fontSize: 13, color: designTokens.color.neutral[600] }}>
          FTP 场景
          <select
            aria-label="FTP 场景"
            value={scenarioRate}
            onChange={(event) => {
              setScenarioRateTouched(true);
              setScenarioRate(event.target.value);
            }}
            style={{ padding: "10px 12px", borderRadius: 12, border: `1px solid ${designTokens.color.neutral[200]}` }}
          >
            {PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ marginBottom: 18 }}>
        <button
          type="button"
          data-testid="product-category-apply-scenario-button"
          onClick={() => setAppliedScenarioRate(scenarioRate.trim())}
          style={{
            padding: "11px 14px",
            borderRadius: 12,
            border: `1px solid ${designTokens.color.primary[200]}`,
            background: designTokens.color.primary[100],
            color: designTokens.color.primary[600],
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          应用场景
        </button>
      </div>

      <SectionLead
        eyebrow="正式口径"
        title="正式产品类别损益表"
        description="表格继续展示后端返回的产品类别读模型，资产/负债符号展示、情景行为和合计行保持原有逻辑。"
        testId="product-category-formal-table-lead"
      />
      <AsyncSection
        title="产品类别损益分析表（单位：亿元）"
        isLoading={baselineQuery.isLoading}
        isError={baselineQuery.isError}
        isEmpty={!baselineQuery.isLoading && !baselineQuery.isError && rowsToRender.length === 0}
        fillHeight={false}
        onRetry={() => void baselineQuery.refetch()}
        extra={reportExtra}
      >
        <div style={{ overflowX: "auto" }}>
          <table
            data-testid="product-category-table"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 13,
            }}
          >
            <thead>
              <tr
                style={{
                  textAlign: "left",
                  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                  background: designTokens.color.primary[50],
                }}
              >
                <th rowSpan={2} style={{ padding: "12px 8px" }}>产品类别</th>
                <th colSpan={3} style={{ padding: "12px 8px", textAlign: "center" }}>规模日均</th>
                <th colSpan={8} style={{ padding: "12px 8px", textAlign: "center" }}>损益</th>
                <th rowSpan={2} style={{ padding: "12px 8px", textAlign: "right" }}>加权收益率</th>
              </tr>
              <tr
                style={{
                  textAlign: "left",
                  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                  background: designTokens.color.primary[50],
                }}
              >
                <th style={{ padding: "12px 8px", textAlign: "right" }}>综本</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>综本</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币FTP</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币减收入</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币FTP</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币减收入</th>
                <th
                  style={{
                    padding: "12px 8px",
                    textAlign: "right",
                    background: designTokens.color.warning[50],
                  }}
                >
                  营业减收入
                </th>
              </tr>
            </thead>
            <tbody>
              {rowsToRender.map((row) => (
                <tr
                  key={row.category_id}
                  style={{
                    borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
                    background: row.is_total ? designTokens.color.primary[100] : displayTokens.surface.section,
                    fontWeight: row.is_total ? 700 : 400,
                  }}
                >
                  <td style={{ padding: "12px 8px" }}>
                    <div style={{ paddingLeft: row.level * 18 }}>
                      <div>{row.category_name}</div>
                    </div>
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryRowDisplayValue(row, row.cnx_scale)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryRowDisplayValue(row, row.cny_scale)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryRowDisplayValue(row, row.foreign_scale)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryRowDisplayValue(row, row.cnx_cash)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryRowDisplayValue(row, row.cny_cash)}</td>
                  <td
                    style={{
                      padding: "12px 8px",
                      textAlign: "right",
                      color: designTokens.color.primary[600],
                    }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.cny_ftp)}
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right", color: toneForProductCategoryValue(row.cny_net) }}>
                    {formatProductCategoryRowDisplayValue(row, row.cny_net)}
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryRowDisplayValue(row, row.foreign_cash)}</td>
                  <td
                    style={{
                      padding: "12px 8px",
                      textAlign: "right",
                      color: designTokens.color.primary[600],
                    }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.foreign_ftp)}
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right", color: toneForProductCategoryValue(row.foreign_net) }}>
                    {formatProductCategoryRowDisplayValue(row, row.foreign_net)}
                  </td>
                  <td
                    style={{
                      padding: "12px 8px",
                      textAlign: "right",
                      color: toneForProductCategoryValue(row.business_net_income),
                      background: designTokens.color.warning[50],
                    }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.business_net_income)}
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatProductCategoryYieldValue(row.weighted_yield)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncSection>

      {displayedGrandTotal && !baselineQuery.isError ? (
        <div
          data-testid="product-category-footer-total"
          style={{
            marginTop: 16,
            padding: "14px 18px",
            borderRadius: 16,
            background: designTokens.color.neutral[900],
            color: designTokens.color.neutral[50],
            fontWeight: 700,
            textAlign: "center",
          }}
        >
          全部市场科目 + 投资收益合计：{formatProductCategoryValue(displayedGrandTotal.business_net_income)}
        </div>
      ) : null}

      {!baselineQuery.isError && hasDiagnosticsSurface ? (
        <>
          <SectionLead
            eyebrow="诊断"
            title="受治理诊断面板"
            description="仅使用当前 payload 行与趋势快照，补充产品经营诊断矩阵、负贡献观察名单和利差变动归因，不改写后端总计。"
            testId="product-category-diagnostics-lead"
          />
          <div className="product-category-diagnostics" data-testid="product-category-diagnostics-surface">
            <article className="product-category-diagnostics__card" data-testid="product-category-diagnostics-matrix">
              <div className="product-category-diagnostics__header">
                <div className="product-category-diagnostics__intro">
                  <h3 className="product-category-diagnostics__title">产品经营诊断矩阵</h3>
                  <p className="product-category-diagnostics__description">
                    逐行回看规模、营业净收入、收益率和双币净收入拆分，行身份仅取自
                    `category_id/category_name/side`。
                  </p>
                </div>
                {diagnosticsSurface.headlineTotalLabel ? (
                  <span
                    className="product-category-diagnostics__summary"
                    data-testid="product-category-diagnostics-summary"
                  >
                    当前总损益 {diagnosticsSurface.headlineTotalLabel}
                  </span>
                ) : null}
              </div>
              {diagnosticsSurface.matrixEmptyCopy ? (
                <div
                  data-testid="product-category-diagnostics-matrix-empty"
                  className="product-category-diagnostics__empty"
                >
                  {diagnosticsSurface.matrixEmptyCopy}
                </div>
              ) : (
                <div className="product-category-diagnostics__table-wrap">
                  <table className="product-category-diagnostics__table">
                    <thead>
                      <tr>
                        <th className="product-category-diagnostics__table-head">产品行</th>
                        <th className="product-category-diagnostics__table-head">端别</th>
                        <th className="product-category-diagnostics__table-head">规模</th>
                        <th className="product-category-diagnostics__table-head">营业净收入</th>
                        <th className="product-category-diagnostics__table-head">收益率</th>
                        <th className="product-category-diagnostics__table-head">人民币净收入</th>
                        <th className="product-category-diagnostics__table-head">外币净收入</th>
                        <th className="product-category-diagnostics__table-head">驱动提示</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagnosticsSurface.matrixRows.map((item) => (
                        <tr key={item.categoryId}>
                          <td className="product-category-diagnostics__table-cell">{item.categoryLabel}</td>
                          <td className="product-category-diagnostics__table-cell">{item.sideLabel}</td>
                          <td className="product-category-diagnostics__table-cell">{item.scaleLabel}</td>
                          <td
                            className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.businessNetIncomeTone)}`}
                          >
                            {item.businessNetIncomeLabel}
                          </td>
                          <td className="product-category-diagnostics__table-cell">{item.yieldLabel}</td>
                          <td
                            className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.cnyNetTone)}`}
                          >
                            {item.cnyNetLabel}
                          </td>
                          <td
                            className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.foreignNetTone)}`}
                          >
                            {item.foreignNetLabel}
                          </td>
                          <td className="product-category-diagnostics__table-cell">{item.driverHint}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>

            <article className="product-category-diagnostics__card" data-testid="product-category-diagnostics-watchlist">
              <div className="product-category-diagnostics__intro">
                <h3 className="product-category-diagnostics__title">负贡献观察名单</h3>
                <p className="product-category-diagnostics__description">
                  仅列出 `business_net_income &lt; 0` 的行，并按亏损幅度排序；缺失规模或收益率会显式标注。
                </p>
              </div>
              {diagnosticsSurface.negativeWatchlistEmptyCopy ? (
                <div
                  data-testid="product-category-diagnostics-watchlist-empty"
                  className="product-category-diagnostics__empty"
                >
                  {diagnosticsSurface.negativeWatchlistEmptyCopy}
                </div>
              ) : (
                <div className="product-category-diagnostics__watchlist">
                  {diagnosticsSurface.negativeWatchlistRows.map((item) => (
                    <div
                      key={item.categoryId}
                      className="product-category-diagnostics__watchlist-row"
                      data-testid={`product-category-diagnostics-watchlist-row-${item.categoryId}`}
                    >
                      <div className="product-category-diagnostics__watchlist-primary">
                        <div className="product-category-diagnostics__metric-value product-category-diagnostics__metric-value--primary">
                          {item.categoryLabel}
                        </div>
                        <div className="product-category-diagnostics__metric-detail">{item.sideLabel}</div>
                      </div>
                      <div className="product-category-diagnostics__metric">
                        <span className="product-category-diagnostics__metric-label">亏损</span>
                        <span className="product-category-diagnostics__metric-value product-category-diagnostics__value--negative">
                          {item.lossLabel}
                        </span>
                      </div>
                      <div className="product-category-diagnostics__metric">
                        <span className="product-category-diagnostics__metric-label">规模</span>
                        <span className="product-category-diagnostics__metric-value">{item.scaleLabel}</span>
                      </div>
                      <div className="product-category-diagnostics__metric">
                        <span className="product-category-diagnostics__metric-label">收益率</span>
                        <span className="product-category-diagnostics__metric-value">{item.yieldLabel}</span>
                      </div>
                      <div className="product-category-diagnostics__metric">
                        <span className="product-category-diagnostics__metric-label">缺口提示</span>
                        <span className="product-category-diagnostics__metric-value">
                          {[item.scaleMissing ? "规模缺失" : null, item.yieldMissing ? "收益率缺失" : null]
                            .filter(Boolean)
                            .join(" / ") || "字段齐全"}
                        </span>
                      </div>
                      <div className="product-category-diagnostics__metric">
                        <span className="product-category-diagnostics__metric-label">驱动提示</span>
                        <span className="product-category-diagnostics__metric-detail">{item.driverHint}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="product-category-diagnostics__card" data-testid="product-category-diagnostics-spread">
              <div className="product-category-diagnostics__intro">
                <h3 className="product-category-diagnostics__title">利差变动归因</h3>
                <p className="product-category-diagnostics__description">
                  使用当前期与可比上期趋势快照，展示资产收益率、负债收益率、利差和变动方向。
                </p>
              </div>
              <div className="product-category-diagnostics__spread-grid">
                <div className="product-category-diagnostics__spread-card">
                  <span className="product-category-diagnostics__spread-caption">
                    {diagnosticsSurface.spreadAttribution.currentLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-value">
                    {diagnosticsSurface.spreadAttribution.currentSpreadLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-detail">
                    资产 {diagnosticsSurface.spreadAttribution.currentAssetYieldLabel} / 负债{" "}
                    {diagnosticsSurface.spreadAttribution.currentLiabilityYieldLabel}
                  </span>
                </div>
                <div className="product-category-diagnostics__spread-card">
                  <span className="product-category-diagnostics__spread-caption">
                    {diagnosticsSurface.spreadAttribution.priorLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-value">
                    {diagnosticsSurface.spreadAttribution.priorSpreadLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-detail">
                    资产变动 {diagnosticsSurface.spreadAttribution.assetYieldDeltaLabel} / 负债变动{" "}
                    {diagnosticsSurface.spreadAttribution.liabilityYieldDeltaLabel}
                  </span>
                </div>
                <div className="product-category-diagnostics__spread-card">
                  <span className="product-category-diagnostics__spread-caption">归因结论</span>
                  <span className="product-category-diagnostics__spread-value">
                    {diagnosticsSurface.spreadAttribution.spreadDeltaLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-detail">
                    {diagnosticsSurface.spreadAttribution.driverHint}
                  </span>
                </div>
              </div>
              {diagnosticsSurface.spreadAttribution.state === "incomplete" ? (
                <div
                  data-testid="product-category-diagnostics-spread-incomplete"
                  className="product-category-diagnostics__empty"
                >
                  {diagnosticsSurface.spreadAttribution.reason}
                </div>
              ) : null}
            </article>
          </div>
          <article
            className="product-category-diagnostics__card product-category-liability-side-trend"
            data-testid="product-category-liability-side-trend"
          >
            <div className="product-category-diagnostics__header">
              <div className="product-category-diagnostics__intro">
                <h3 className="product-category-diagnostics__title">负债端趋势分析</h3>
                <p className="product-category-diagnostics__description">
                  负债侧产品类别口径：使用当前产品分类 payload 的负债明细行和后端
                  liability_total，展示日均额与利率走势。
                </p>
              </div>
              <span className="product-category-diagnostics__summary">负债侧产品类别口径</span>
            </div>
            {liabilitySideTrendOption ? (
              <ReactECharts
                option={liabilitySideTrendOption}
                className="product-category-derived-chart__canvas"
                data-testid="product-category-liability-side-trend-chart"
                notMerge
                lazyUpdate
              />
            ) : (
              <div
                className="product-category-diagnostics__empty"
                data-testid="product-category-liability-side-trend-empty"
              >
                {liabilitySideTrendSurface.emptyCopy ?? "负债端趋势数据不完整，无法绘制完整走势。"}
              </div>
            )}
            {liabilitySideTrendSurface.incompleteReasons.length > 0 ? (
              <div
                className="product-category-diagnostics__empty"
                data-testid="product-category-liability-side-trend-incomplete"
              >
                {liabilitySideTrendSurface.incompleteReasons.join("；")}
              </div>
            ) : null}
            {liabilitySideTrendSurface.detailRows.length > 0 ? (
              <div className="product-category-diagnostics__table-wrap">
                <table
                  className="product-category-diagnostics__table"
                  data-testid="product-category-liability-side-detail-table"
                >
                  <thead>
                    <tr>
                      <th className="product-category-diagnostics__table-head">负债明细</th>
                      <th className="product-category-diagnostics__table-head">最新日均额</th>
                      <th className="product-category-diagnostics__table-head">日均额变动</th>
                      <th className="product-category-diagnostics__table-head">最新利率</th>
                      <th className="product-category-diagnostics__table-head">利率变动</th>
                      <th className="product-category-diagnostics__table-head">对比期</th>
                    </tr>
                  </thead>
                  <tbody>
                    {liabilitySideTrendSurface.detailRows.map((item) => (
                      <tr
                        key={item.categoryId}
                        data-testid={`product-category-liability-side-detail-${item.categoryId}`}
                      >
                        <td className="product-category-diagnostics__table-cell">{item.categoryLabel}</td>
                        <td className="product-category-diagnostics__table-cell">{item.latestAmountLabel}</td>
                        <td className="product-category-diagnostics__table-cell">{item.amountDeltaLabel}</td>
                        <td className="product-category-diagnostics__table-cell">{item.latestRateLabel}</td>
                        <td className="product-category-diagnostics__table-cell">{item.rateDeltaLabel}</td>
                        <td className="product-category-diagnostics__table-cell">{item.comparisonLabel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </article>
          <div
            className="product-category-derived-charts"
            data-testid="product-category-derived-chart-grid"
          >
            <DerivedChartPanel
              testId="product-category-derived-chart-tpl-scale-yield"
              title="TPL资产规模收益率走势图"
              description="跟踪TPL资产人民币规模、外币规模与综合收益率变化。"
              option={tplScaleYieldOption}
            />
            <DerivedChartPanel
              testId="product-category-derived-chart-currency-net-income"
              title="人民币/外币净收入走势分析图"
              description="按全市场净收入拆分人民币与外币贡献，观察币种结构变化。"
              option={currencyNetIncomeOption}
            />
            <DerivedChartPanel
              testId="product-category-derived-chart-interest-earning-income-scale"
              title="生息资产收入规模趋势图"
              description="联动展示生息资产规模与营业净收入趋势。"
              option={interestEarningIncomeScaleOption}
            />
            <DerivedChartPanel
              testId="product-category-derived-chart-interest-spread"
              title="生息资产利差分析图"
              description="按生息资产收益率减负债端付息率展示利差变化。"
              option={interestSpreadOption}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}
