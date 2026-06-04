import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryManualAdjustmentRequest,
  ResultMeta,
} from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { DataStatusStrip, PageDecisionHero } from "../../../components/page/PagePrimitives";
import { DataQualityBanner } from "../../../components/page/DataQualityBanner";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import MonthlyOperatingAnalysisBranch from "./MonthlyOperatingAnalysisBranch";
import "./ProductCategoryPnlPage.css";
import { ProductCategoryGovernanceStrip } from "./ProductCategoryGovernanceStrip";
import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS,
  type ProductCategoryInterestSpreadAttributionSelection,
  type ProductCategoryInterestSpreadAttributionSurface,
  type ProductCategoryInterestSpreadBasis,
  buildProductCategoryDiagnosticsSurface,
  buildProductCategoryLiabilitySideTrendSurface,
  buildProductCategoryTrendSnapshot,
  buildLedgerPnlHrefForReportDate,
  collectProductCategoryGovernanceNotices,
  defaultProductCategoryScenarioRateForReportDate,
  formatProductCategoryAttributionEffect,
  formatProductCategoryDualMetaDistinctLine,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
  nextDefaultReportDateIfUnset,
  type ProductCategoryAttributionWaterfallSurface,
  selectProductCategoryAttributionWaterfallSurface,
  selectProductCategoryCurrencyNetIncomeChart,
  type ProductCategoryDecisionFocusSurface,
  selectProductCategoryDecisionFocusSurface,
  type ProductCategoryRootCauseSurface,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChart,
  selectProductCategoryInterestEarningIncomeScaleChart,
  selectProductCategoryOperatingAnalysisSurface,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryInterestSpreadAttributionSurface,
  selectProductCategoryInterestSpreadChart,
  selectProductCategoryInterestSpreadYearComparisonChart,
  selectProductCategoryRootCauseSurface,
  type ProductCategoryScenarioSensitivitySurface,
  type ProductCategoryScenarioExplanation,
  selectProductCategoryScenarioExplanation,
  selectProductCategoryScenarioSensitivitySurface,
  selectProductCategoryTplScaleYieldChart,
  selectProductCategoryTwoYearInterestSpreadReportPoints,
  selectProductCategoryTrendReportPoints,
  toneForProductCategoryValue,
} from "./productCategoryPnlPageModel";
import { designTokens } from "../../../theme/designSystem";

type ScenarioReviewActionStatus = "pending" | "confirmed" | "issue";
type ScenarioReviewIssueReason = "basis" | "ftp" | "attribution" | "data";
type ScenarioComparisonFilter = "all" | "pressure" | "improvement";
type ScenarioActionClosureStatus = "todo" | "reviewing" | "closed" | "issue";

const SCENARIO_REVIEW_ACTION_STATUS_OPTIONS: ReadonlyArray<
  readonly [ScenarioReviewActionStatus, string]
> = [
  ["pending", "待核对"],
  ["confirmed", "已确认"],
  ["issue", "有差异"],
];

const SCENARIO_REVIEW_ISSUE_REASON_OPTIONS: ReadonlyArray<
  readonly [ScenarioReviewIssueReason, string]
> = [
  ["basis", "口径不一致"],
  ["ftp", "FTP 驱动异常"],
  ["attribution", "正式归因未覆盖"],
  ["data", "数据待复核"],
];

const SCENARIO_COMPARISON_FILTER_OPTIONS: ReadonlyArray<
  readonly [ScenarioComparisonFilter, string]
> = [
  ["all", "全部"],
  ["pressure", "仅承压"],
  ["improvement", "仅改善"],
];

const SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS: ReadonlyArray<
  readonly [ScenarioActionClosureStatus, string]
> = [
  ["todo", "待处理"],
  ["reviewing", "复核中"],
  ["closed", "已关闭"],
  ["issue", "有差异"],
];

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
    <div data-testid={props.testId} className="product-category-section-lead">
      <span className="product-category-section-lead__eyebrow">{props.eyebrow}</span>
      <h2 className="product-category-section-lead__title">{props.title}</h2>
      <p className="product-category-section-lead__description">{props.description}</p>
    </div>
  );
}

function reportDateYearMonth(reportDate: string): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return null;
  }
  return { year, month };
}

function monthAnchoredInterestSpreadSelection(
  current: ProductCategoryInterestSpreadAttributionSelection,
  reportDate: string,
): ProductCategoryInterestSpreadAttributionSelection {
  const parsed = reportDateYearMonth(reportDate);
  if (!parsed || current.month === parsed.month) {
    return current;
  }
  return { ...current, month: parsed.month };
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
  wide?: boolean;
  onEvents?: EChartsReactProps["onEvents"];
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
    data: Array<number | null>;
    color: string;
  }>;
}): EChartsOption | null {
  const values = input.series
    .flatMap((series) => series.data)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!input.labels.length || values.length === 0) {
    return null;
  }
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

function buildInterestSpreadYearComparisonChartOption(input: {
  labels: string[];
  series: Array<{
    name: string;
    data: Array<number | null>;
    color: string;
  }>;
}): EChartsOption | null {
  const values = input.series
    .flatMap((series) => series.data)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!input.labels.length || values.length === 0) {
    return null;
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const padding = Math.max(range * 0.18, 0.05);
  const yAxisMin = Number((minValue - padding).toFixed(2));
  const yAxisMax = Number((maxValue + padding).toFixed(2));
  return {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: input.series.map((series) => series.name) },
    grid: { left: 56, right: 28, top: 20, bottom: 58 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: { interval: 0 },
      axisLine: { lineStyle: { color: designTokens.color.neutral[300] } },
    },
    yAxis: {
      type: "value",
      name: "%",
      min: yAxisMin,
      max: yAxisMax,
      scale: true,
      axisLabel: { formatter: "{value}%" },
      splitLine: { lineStyle: { type: "solid", color: designTokens.color.neutral[300] } },
    },
    series: input.series.map((series, index) => ({
      name: series.name,
      type: "line",
      data: series.data,
      smooth: false,
      showSymbol: true,
      symbol: index === 0 ? "diamond" : "rect",
      symbolSize: 7,
      itemStyle: { color: series.color },
      lineStyle: { color: series.color, width: 2.6 },
      label: {
        show: true,
        formatter: "{c}%",
        color: designTokens.color.neutral[900],
        position: index === 0 ? "top" : "bottom",
        distance: 4,
      },
      endLabel: { show: false },
      emphasis: { focus: "series" },
    })),
  };
}

function buildIncomeYearComparisonChartOption(input: {
  labels: string[];
  series: Array<{
    name: string;
    data: Array<number | null>;
    color: string;
  }>;
}): EChartsOption | null {
  const values = input.series
    .flatMap((series) => series.data)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!input.labels.length || values.length === 0) {
    return null;
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const padding = Math.max(range * 0.18, 0.5);
  return {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: input.series.map((series) => series.name) },
    grid: { left: 56, right: 28, top: 20, bottom: 58 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: { interval: 0 },
      axisLine: { lineStyle: { color: designTokens.color.neutral[300] } },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      min: Number((minValue - padding).toFixed(2)),
      max: Number((maxValue + padding).toFixed(2)),
      scale: true,
      axisLabel: { formatter: "{value}" },
      splitLine: { lineStyle: { type: "solid", color: designTokens.color.neutral[300] } },
    },
    series: input.series.map((series, index) => ({
      name: series.name,
      type: "line",
      data: series.data,
      smooth: false,
      showSymbol: true,
      symbol: index === 0 ? "diamond" : "rect",
      symbolSize: 7,
      itemStyle: { color: series.color },
      lineStyle: { color: series.color, width: 2.6 },
      label: {
        show: true,
        formatter: "{c}",
        color: designTokens.color.neutral[900],
        position: index === 0 ? "top" : "bottom",
        distance: 4,
      },
      endLabel: { show: false },
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
  const className = props.wide
    ? "product-category-derived-chart product-category-derived-chart--wide"
    : "product-category-derived-chart";
  return (
    <article className={className} data-testid={props.testId}>
      <div className="product-category-derived-chart__header">
        <h3 className="product-category-derived-chart__title">{props.title}</h3>
        <p className="product-category-derived-chart__description">{props.description}</p>
      </div>
      <ReactECharts
        option={props.option}
        className="product-category-derived-chart__canvas"
        notMerge
        lazyUpdate
        onEvents={props.onEvents}
      />
    </article>
  );
}

const ATTRIBUTION_EFFECT_COLUMNS = [
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["day_effect", "天数因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
] as const;

const ATTRIBUTION_POINT_COLUMNS = [
  ["scale", "日均"],
  ["cash", "收支"],
  ["yield_pct", "利率"],
  ["ftp", "FTP"],
  ["business_net_income", "净营收"],
] as const;

type ProductCategoryAttributionCompare = ProductCategoryAttributionPayload["compare"];

const ATTRIBUTION_COMPARE_OPTIONS: Array<{
  value: ProductCategoryAttributionCompare;
  label: string;
}> = [
  { value: "mom", label: "月环比" },
  { value: "yoy", label: "同比" },
];

function productCategoryAttributionPriorLabel(compare: ProductCategoryAttributionCompare): string {
  return compare === "yoy" ? "去年同期" : "上期";
}

function productCategoryAttributionLoadingCopy(compare: ProductCategoryAttributionCompare): string {
  return compare === "yoy" ? "正在加载同比经营差异归因。" : "正在加载月环比经营差异归因。";
}

function productCategoryAttributionIncompleteCopy(compare: ProductCategoryAttributionCompare): string {
  return compare === "yoy"
    ? "缺少去年同期正式月度数据，暂不能做同比归因。"
    : "缺少上月正式月度数据，暂不能做月环比归因。";
}

function ProductCategoryInterestSpreadAttributionPanel(props: {
  surface: ProductCategoryInterestSpreadAttributionSurface | null;
  resultMeta?: ResultMeta | null;
}) {
  if (!props.surface) {
    return null;
  }
  const basisLabel = props.surface.selected.basis === "cny" ? "人民币口径" : "全口径";
  return (
    <article
      className="product-category-interest-spread-attribution"
      data-testid="product-category-interest-spread-attribution"
    >
      <div className="product-category-interest-spread-attribution__header">
        <div>
          <h3 className="product-category-interest-spread-attribution__title">利差同比归因</h3>
          <p className="product-category-interest-spread-attribution__description">
            {basisLabel} · {props.surface.selected.month}月 · 生息资产收益率 - 负债端成本率
          </p>
        </div>
        <span className="product-category-interest-spread-attribution__badge">
          {props.surface.complete ? "闭合" : "待补数"}
        </span>
      </div>
      <div className="product-category-interest-spread-attribution__summary">
        {props.surface.rows.map((row) => (
          <div className="product-category-interest-spread-attribution__metric" key={row.key}>
            <span className="product-category-interest-spread-attribution__metric-label">{row.label}</span>
            <strong>{row.contributionLabel}</strong>
            <span>
              {row.priorLabel} → {row.currentLabel}
            </span>
          </div>
        ))}
      </div>
      <DataQualityBanner
        resultMeta={props.resultMeta}
        degradedReasons={props.surface.incompleteReasons}
      />
      <div className="product-category-interest-spread-attribution__table-wrap">
        <table className="product-category-interest-spread-attribution__table">
          <thead>
            <tr>
              <th>{"\u6307\u6807"}</th>
              <th>{"\u4e0a\u5e74\u540c\u6708"}</th>
              <th>{"\u5f53\u524d\u6708"}</th>
              <th>{"\u53d8\u5316(bp)"}</th>
              <th>{"\u5f52\u56e0\u8bf4\u660e"}</th>
            </tr>
          </thead>
          <tbody>
            {props.surface.rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.priorLabel}</td>
                <td>{row.currentLabel}</td>
                <td>{row.contributionLabel}</td>
                <td>{row.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="product-category-interest-spread-attribution__details">
        {props.surface.details.map((detail) => (
          <section className="product-category-interest-spread-attribution__detail" key={detail.key}>
            <h4>{detail.label}</h4>
            <div className="product-category-interest-spread-attribution__detail-grid">
              {[detail.prior, detail.current].map((point, index) => (
                <dl
                  className="product-category-interest-spread-attribution__detail-list"
                  key={`${detail.key}-${index}`}
                >
                  <dt>{point.reportLabel}</dt>
                  <dd>{"\u65e5\u5747\u989d"} {point.amountLabel}</dd>
                  <dd>{"\u5229\u606f\u6536\u652f"} {point.cashLabel}</dd>
                  <dd>{"\u6536\u76ca\u7387/\u6210\u672c"} {point.yieldLabel}</dd>
                </dl>
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}

function ProductCategoryAttributionPanel(props: {
  selectedView: string;
  compare: ProductCategoryAttributionCompare;
  payload?: ProductCategoryAttributionPayload;
  resultMeta?: ResultMeta | null;
  isLoading: boolean;
  isError: boolean;
  onCompareChange: (compare: ProductCategoryAttributionCompare) => void;
  onRetry: () => void;
}) {
  if (props.selectedView !== "monthly") {
    return (
      <article
        className="product-category-attribution product-category-attribution--ineligible"
        data-testid="product-category-attribution-ineligible"
      >
        <div className="product-category-attribution__header">
          <div>
            <h3 className="product-category-attribution__title">经营差异归因</h3>
            <p className="product-category-attribution__description">
              仅支持月度视图，汇总视图保持原正式明细口径。
            </p>
          </div>
          <span className="product-category-attribution__badge">正式基线</span>
        </div>
      </article>
    );
  }

  if (props.isLoading) {
    return (
      <article className="product-category-attribution" data-testid="product-category-attribution">
        <div className="product-category-attribution__empty">
          {productCategoryAttributionLoadingCopy(props.compare)}
        </div>
      </article>
    );
  }

  if (props.isError) {
    return (
      <article className="product-category-attribution" data-testid="product-category-attribution">
        <div className="product-category-attribution__error">
          <span>归因数据加载失败。</span>
          <button type="button" onClick={props.onRetry}>
            重试
          </button>
        </div>
      </article>
    );
  }

  if (!props.payload || props.payload.state === "incomplete") {
    return (
      <article className="product-category-attribution" data-testid="product-category-attribution">
        <div className="product-category-attribution__header">
          <div>
            <h3 className="product-category-attribution__title">经营差异归因</h3>
            <p className="product-category-attribution__description">
              正式基线归因，不解释 FTP 场景差异。
            </p>
          </div>
          <ProductCategoryAttributionCompareSwitch
            compare={props.compare}
            onCompareChange={props.onCompareChange}
          />
        </div>
        <DataQualityBanner
          resultMeta={props.resultMeta}
          degradedReasons={["归因数据准备中，请稍后刷新"]}
        />
        <div
          className="product-category-attribution__empty"
          data-testid="product-category-attribution-incomplete"
        >
          {productCategoryAttributionIncompleteCopy(props.compare)}
        </div>
      </article>
    );
  }

  const headlineRow = props.payload.totals?.grand_total;
  const headline = headlineRow?.effects;
  const grandTotalRow = props.payload.totals?.grand_total
    ? { ...props.payload.totals.grand_total, category_name: "全表合计" }
    : null;
  const rows = props.payload.totals
    ? [
        ...props.payload.rows,
        props.payload.totals.asset_total,
        props.payload.totals.liability_total,
        ...(grandTotalRow ? [grandTotalRow] : []),
      ]
    : props.payload.rows;
  return (
    <article className="product-category-attribution" data-testid="product-category-attribution">
      <div className="product-category-attribution__header">
        <div>
          <h3 className="product-category-attribution__title">经营差异归因</h3>
          <p className="product-category-attribution__description">
            {props.compare === "yoy" ? "同比正式基线归因，不解释 FTP 场景差异。" : "月环比正式基线归因，不解释 FTP 场景差异。"}
          </p>
        </div>
        <ProductCategoryAttributionCompareSwitch
          compare={props.compare}
          onCompareChange={props.onCompareChange}
        />
      </div>

      {headline ? (
        <div className="product-category-attribution__summary">
          <AttributionMetric label="变动合计" value={headline.delta_business_net_income} />
          <AttributionMetric label="本期净营收" value={headlineRow?.current?.business_net_income} />
          <AttributionMetric label="对比期净营收" value={headlineRow?.prior?.business_net_income} />
          <AttributionMetric label="已解释" value={headline.explained_effect} />
          <AttributionMetric label="未解释" value={headline.unexplained_effect} />
          <AttributionMetric label="闭合误差" value={headline.closure_error} />
        </div>
      ) : null}

      <AttributionComparisonTable
        compare={props.compare}
        currentReportDate={props.payload.current_report_date}
        priorReportDate={props.payload.prior_report_date}
        rows={rows}
      />
    </article>
  );
}

type ProductCategoryOperatingAnalysisSurface = ReturnType<
  typeof selectProductCategoryOperatingAnalysisSurface
>;

type ProductCategoryOperatingActionBacktestSurface = ReturnType<
  typeof selectProductCategoryOperatingActionBacktestSurface
>;

type ProductCategoryOperatingActionQueueRow =
  ProductCategoryOperatingAnalysisSurface["actionQueue"]["rows"][number];

function productCategoryOperatingActionRowKey(row: ProductCategoryOperatingActionQueueRow) {
  return `${row.priorityLabel}-${row.categoryId}`;
}

function ProductCategoryOperatingAnalysisPanel(props: {
  surface: ProductCategoryOperatingAnalysisSurface;
}) {
  const [selectedActionRowKey, setSelectedActionRowKey] = useState<string | null>(null);
  const selectedActionRow =
    props.surface.actionQueue.rows.find(
      (row) => productCategoryOperatingActionRowKey(row) === selectedActionRowKey,
    ) ?? null;
  const quadrantGroups = [
    "core_profit_pool",
    "selective_growth",
    "scale_efficiency_watch",
    "shrink_or_reprice",
  ] as const;
  useEffect(() => {
    if (selectedActionRowKey && !selectedActionRow) {
      setSelectedActionRowKey(null);
    }
  }, [selectedActionRow, selectedActionRowKey]);

  return (
    <section className="product-category-operating-analysis" data-testid="product-category-operating-analysis">
      <div className="product-category-operating-analysis__header">
        <div>
          <span className="product-category-operating-analysis__eyebrow">经营分析</span>
          <h2 className="product-category-operating-analysis__title">产品类别利润结构与经营动作</h2>
          <p className="product-category-operating-analysis__description">
            基于当前正式表和已有月环比归因，优先识别利润池、压力项、主要变动驱动和可优化产品。
          </p>
        </div>
        <span className="product-category-operating-analysis__badge">
          全表净营收 {props.surface.contribution.grandTotalLabel ?? "-"} 亿元
        </span>
      </div>
      <div className="product-category-operating-analysis__grid">
        <article
          className="product-category-operating-analysis__panel"
          data-testid="product-category-operating-profit-rank"
        >
          <h3 className="product-category-operating-analysis__panel-title">利润贡献排行</h3>
          <p className="product-category-operating-analysis__panel-note">按当前净营收排序，贡献率相对全表净营收计算。</p>
          {props.surface.contribution.emptyCopy ? (
            <div className="product-category-operating-analysis__empty">{props.surface.contribution.emptyCopy}</div>
          ) : (
            <div className="product-category-operating-analysis__rank-groups">
              <ProductCategoryOperatingContributionList
                label="利润池"
                rows={props.surface.contribution.profitRows}
              />
              <ProductCategoryOperatingContributionList
                label="压力项"
                rows={props.surface.contribution.pressureRows}
              />
            </div>
          )}
        </article>
        <article
          className="product-category-operating-analysis__panel"
          data-testid="product-category-operating-movement"
        >
          <h3 className="product-category-operating-analysis__panel-title">月环比变动驱动</h3>
          <p className="product-category-operating-analysis__panel-note">直接复用正式经营差异归因，按变动绝对值排序。</p>
          {props.surface.movement.emptyCopy ? (
            <div className="product-category-operating-analysis__empty">{props.surface.movement.emptyCopy}</div>
          ) : (
            <div className="product-category-operating-analysis__movement-list">
              {props.surface.movement.rows.map((row) => (
                <div className="product-category-operating-analysis__movement-row" key={row.categoryId}>
                  <div>
                    <strong>{row.categoryLabel}</strong>
                    <span>{row.leadingDriverLabel} {row.leadingDriverValueLabel}</span>
                  </div>
                  <b className={row.delta > 0 ? "is-positive" : "is-negative"}>{row.deltaLabel}</b>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>
      <article
        className="product-category-operating-analysis__panel product-category-operating-analysis__panel--wide"
        data-testid="product-category-operating-quadrant"
      >
        <div className="product-category-operating-analysis__quadrant-header">
          <div>
            <h3 className="product-category-operating-analysis__panel-title">规模-收益率象限</h3>
            <p className="product-category-operating-analysis__panel-note">
              以可用产品的中位数为基准：规模 {props.surface.quadrant.scaleBenchmarkLabel} 亿元，收益率{" "}
              {props.surface.quadrant.yieldBenchmarkLabel}%。
            </p>
          </div>
        </div>
        {props.surface.quadrant.emptyCopy ? (
          <div className="product-category-operating-analysis__empty">{props.surface.quadrant.emptyCopy}</div>
        ) : (
          <div className="product-category-operating-analysis__quadrant-grid">
            {quadrantGroups.map((quadrant) => {
              const rows = props.surface.quadrant.rows.filter((row) => row.quadrant === quadrant);
              if (rows.length === 0) {
                return null;
              }
              return (
                <section className={`product-category-operating-analysis__quadrant is-${quadrant}`} key={quadrant}>
                  <h4>{rows[0]?.quadrantLabel}</h4>
                  <div className="product-category-operating-analysis__quadrant-items">
                    {rows.map((row) => (
                      <div className="product-category-operating-analysis__quadrant-item" key={row.categoryId}>
                        <strong>{row.categoryLabel}</strong>
                        <span>{row.scaleLabel} 亿元 · {row.yieldLabel}% · 净营收 {row.netIncomeLabel}</span>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </article>
      <article
        className="product-category-operating-analysis__panel product-category-operating-analysis__panel--wide"
        data-testid="product-category-operating-action-queue"
      >
        <div className="product-category-operating-analysis__quadrant-header">
          <div>
            <h3 className="product-category-operating-analysis__panel-title">动作优先级队列</h3>
            <p className="product-category-operating-analysis__panel-note">
              从盈利、规模、收益率和正式归因中抽取需要进入经营闭环的产品类别。
            </p>
          </div>
        </div>
        {props.surface.actionQueue.emptyCopy ? (
          <div className="product-category-operating-analysis__empty">{props.surface.actionQueue.emptyCopy}</div>
        ) : (
          <div className="product-category-operating-analysis__action-list">
            {props.surface.actionQueue.rows.map((row) => {
              const rowKey = productCategoryOperatingActionRowKey(row);
              return (
                <div
                  className="product-category-operating-analysis__action-row"
                  key={rowKey}
                >
                  <div className="product-category-operating-analysis__action-main">
                    <span className="product-category-operating-analysis__action-priority">{row.priorityLabel}</span>
                    <div>
                      <strong>{row.categoryLabel}</strong>
                      <span>{row.actionLabel} · {row.triggerLabel}</span>
                    </div>
                  </div>
                  <b className={`is-${row.tone}`}>{row.primaryMetricLabel}</b>
                  <button
                    aria-expanded={selectedActionRowKey === rowKey}
                    type="button"
                    className="product-category-operating-analysis__action-detail-button"
                    onClick={() => setSelectedActionRowKey(rowKey)}
                  >
                    查看 {row.categoryLabel} 动作详情
                  </button>
                  <div className="product-category-operating-analysis__action-evidence">
                    {row.evidenceItems.map((item) => (
                      <small key={item}>{item}</small>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {selectedActionRow ? (
          <aside
            className="product-category-operating-analysis__action-drawer"
            data-testid="product-category-operating-action-drawer"
          >
            <div className="product-category-operating-analysis__action-drawer-head">
              <div>
                <span>动作闭环详情</span>
                <h4>{selectedActionRow.categoryLabel}</h4>
              </div>
              <button type="button" onClick={() => setSelectedActionRowKey(null)}>
                关闭动作详情
              </button>
            </div>
            <div className="product-category-operating-analysis__action-drawer-body">
              <p>
                {selectedActionRow.actionLabel} · {selectedActionRow.triggerLabel}
              </p>
              <p>核对正式表净营收、规模、收益率与归因变动。</p>
              <div className="product-category-operating-analysis__action-drawer-evidence">
                {selectedActionRow.evidenceItems.map((item) => (
                  <small key={item}>{item}</small>
                ))}
              </div>
            </div>
          </aside>
        ) : null}
      </article>
    </section>
  );
}

function ProductCategoryOperatingActionBacktestPanel(props: {
  surface: ProductCategoryOperatingActionBacktestSurface;
  isHistoryLoaded: boolean;
  historyLoading: boolean;
}) {
  return (
    <section className="product-category-action-backtest" data-testid="product-category-operating-action-backtest">
      <div className="product-category-action-backtest__header">
        <div>
          <span className="product-category-operating-analysis__eyebrow">信号回测</span>
          <h2 className="product-category-action-backtest__title">动作队列次月命中率</h2>
          <p className="product-category-action-backtest__description">
            用历史月度正式 payload 复放动作队列，观察下一期净营收、收益率和规模是否沿建议方向改善。
          </p>
        </div>
        <span className="product-category-action-backtest__badge">
          待观察 {props.surface.summary.latestPendingCount} 条
        </span>
      </div>
      {!props.isHistoryLoaded ? (
        <div className="product-category-action-backtest__empty">
          加载趋势诊断后，可用历史月度快照回测动作信号。
        </div>
      ) : props.historyLoading ? (
        <div className="product-category-action-backtest__empty">正在加载历史月度快照。</div>
      ) : props.surface.emptyCopy ? (
        <div className="product-category-action-backtest__empty">{props.surface.emptyCopy}</div>
      ) : (
        <>
          <div className="product-category-action-backtest__summary">
            <div className="product-category-action-backtest__metric">
              <span>覆盖月份</span>
              <strong>{props.surface.summary.evaluatedMonthCount}</strong>
              <small>{props.surface.summary.coverageLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>可评价信号</span>
              <strong>{props.surface.summary.signalCount}</strong>
              <small>{props.surface.summary.evidenceLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>归因覆盖</span>
              <strong>{props.surface.summary.attributionCoverageLabel}</strong>
              <small>{props.surface.summary.attributionCoverageDetailLabel}</small>
            </div>
            <div className={`product-category-action-backtest__metric is-${props.surface.summary.backtestGateTone}`}>
              <span>回测闸口</span>
              <strong>{props.surface.summary.backtestGateLabel}</strong>
              <small>{props.surface.summary.backtestGateDetailLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>复核工作量</span>
              <strong>{props.surface.summary.reviewWorkloadLabel}</strong>
              <small>{props.surface.summary.reviewWorkloadDetailLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>规则处置</span>
              <strong>{props.surface.summary.dispositionLabel}</strong>
              <small>{props.surface.summary.dispositionDetailLabel}</small>
            </div>
            {props.surface.actionRows.map((row) => (
              <div className={`product-category-action-backtest__metric is-${row.tone}`} key={row.actionKind}>
                <span>{row.actionLabel}</span>
                <strong>{row.hitRateLabel}</strong>
                <small>{row.signalCount} 条 · {row.evidenceLabel}</small>
              </div>
            ))}
          </div>
          <article className="product-category-action-backtest__coverage">
            <h3>样本覆盖</h3>
            <div className="product-category-action-backtest__coverage-list">
              {props.surface.coverageRows.slice(-6).map((row) => (
                <div
                  className={`product-category-action-backtest__coverage-row is-${row.tone}`}
                  key={`${row.reportDate}-${row.nextReportDate ?? "pending"}`}
                >
                  <span>{row.reportDate}{row.nextReportDate ? ` → ${row.nextReportDate}` : ""}</span>
                  <strong>{row.statusLabel}</strong>
                  <small>{row.signalCount} 条信号 · {row.detailLabel}</small>
                </div>
              ))}
            </div>
          </article>
          {props.surface.missReasonRows.length > 0 ? (
            <article className="product-category-action-backtest__panel product-category-action-backtest__miss-panel">
              <h3>未命中诊断</h3>
              <div className="product-category-action-backtest__miss-list">
                {props.surface.missReasonRows.map((row) => (
                  <div className={`product-category-action-backtest__miss-row is-${row.tone}`} key={row.actionKind}>
                    <div>
                      <strong>{row.actionLabel}</strong>
                      <span>
                        未命中 {row.missCount}/{row.comparableCount} · 主因 {row.primaryReasonLabel}
                      </span>
                    </div>
                    <b>{row.missRateLabel}</b>
                    <small>
                      {row.reasonRows.map((reason) => `${reason.reasonLabel} ${reason.sampleShareLabel}`).join(" · ")}
                    </small>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
          {props.surface.calibrationRows.length > 0 ? (
            <article className="product-category-action-backtest__panel product-category-action-backtest__miss-panel">
              <h3>回测校准建议</h3>
              <div className="product-category-action-backtest__miss-list">
                {props.surface.calibrationRows.map((row) => (
                  <div className={`product-category-action-backtest__miss-row is-${row.tone}`} key={row.actionKind}>
                    <div>
                      <strong>{row.actionLabel}</strong>
                      <span>{row.reasonLabel}</span>
                    </div>
                    <b>{row.recommendationLabel}</b>
                    <small>{row.confidenceLabel} · {row.confidenceDetailLabel} · {row.evidenceLabel}</small>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
          {props.surface.latestReviewRows.length > 0 ? (
            <article className="product-category-action-backtest__panel product-category-action-backtest__miss-panel">
              <h3>最新信号校准复核</h3>
              <div className="product-category-action-backtest__miss-list">
                {props.surface.latestReviewRows.map((row) => (
                  <div
                    className={`product-category-action-backtest__miss-row is-${row.tone}`}
                    key={`${row.priorityLabel}-${row.categoryId}-${row.actionKind}`}
                  >
                    <div>
                      <strong>{row.categoryLabel}</strong>
                      <span>{row.actionLabel} · {row.reasonLabel}</span>
                    </div>
                    <b>{row.reviewLabel} · {row.riskRankLabel}</b>
                    <small>{row.riskReasonLabel} · {row.impactLabel} · {row.evidenceLabel}</small>
                    <small>当前证据：{row.currentEvidenceItems.join(" · ")}</small>
                    <small>{row.watchReportDateLabel}</small>
                    <small>{row.observationLabel}</small>
                    <small>{row.gapLabel}</small>
                    <small>{row.releaseConditionLabel}</small>
                    <small>{row.checkItems.join(" · ")}</small>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
          <div className="product-category-action-backtest__grid">
            <article className="product-category-action-backtest__panel">
              <h3>动作类型表现</h3>
              <div className="product-category-action-backtest__table-wrap">
                <table className="product-category-action-backtest__table">
                  <thead>
                    <tr>
                      <th>动作</th>
                      <th>信号</th>
                      <th>命中率</th>
                      <th>净营收变化</th>
                      <th>收益率变化</th>
                      <th>规模变化</th>
                    </tr>
                  </thead>
                  <tbody>
                    {props.surface.actionRows.map((row) => (
                      <tr key={row.actionKind}>
                        <td>{row.actionLabel}</td>
                        <td>{row.signalCount}</td>
                        <td>{row.hitRateLabel}</td>
                        <td>{row.averageNetIncomeDeltaLabel}</td>
                        <td>{row.averageYieldDeltaBpLabel}</td>
                        <td>{row.averageScaleDeltaLabel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
            <article className="product-category-action-backtest__panel">
              <h3>典型样本</h3>
              <div className="product-category-action-backtest__examples">
                {props.surface.examples.map((example) => (
                  <div
                    className={`product-category-action-backtest__example is-${example.tone}`}
                    key={`${example.reportDate}-${example.categoryId}-${example.actionKind}`}
                  >
                    <div>
                      <strong>{example.categoryLabel}</strong>
                      <span>
                        {example.reportDate} → {example.nextReportDate} · {example.actionLabel}
                      </span>
                    </div>
                    <b>{example.outcomeLabel}</b>
                    <small>
                      净营收 {example.netIncomeDeltaLabel} 亿元 · 收益率 {example.yieldDeltaBpLabel} · 规模{" "}
                      {example.scaleDeltaLabel} 亿元
                    </small>
                  </div>
                ))}
              </div>
            </article>
          </div>
        </>
      )}
    </section>
  );
}

function ProductCategoryOperatingContributionList(props: {
  label: string;
  rows: ProductCategoryOperatingAnalysisSurface["contribution"]["profitRows"];
}) {
  if (props.rows.length === 0) {
    return null;
  }
  return (
    <div className="product-category-operating-analysis__rank-group">
      <span className="product-category-operating-analysis__rank-label">{props.label}</span>
      {props.rows.map((row) => (
        <div className="product-category-operating-analysis__rank-row" key={row.categoryId}>
          <div>
            <strong>{row.categoryLabel}</strong>
            <span>{row.sideLabel} · {row.contributionLabel}</span>
          </div>
          <b className={row.tone === "positive" ? "is-positive" : "is-negative"}>{row.netIncomeLabel}</b>
        </div>
      ))}
    </div>
  );
}

function ProductCategoryScenarioExplanationCard(props: {
  explanation: ProductCategoryScenarioExplanation;
  actionStatuses: Record<string, ScenarioReviewActionStatus>;
  issueReasons: Record<string, ScenarioReviewIssueReason>;
  onSetActionStatus: (
    categoryId: string,
    actionIndex: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onSetIssueReason: (
    categoryId: string,
    actionIndex: number,
    reason: ScenarioReviewIssueReason,
  ) => void;
  onBulkActionStatus: (categoryId: string, actionCount: number, status: ScenarioReviewActionStatus) => void;
  onResetActions: (categoryId: string, actionCount: number) => void;
}) {
  const explanation = props.explanation;
  const actionStatusEntries = explanation.reviewActionItems.map((_, index) => {
    const key = `${explanation.categoryId}:${index}`;
    return props.actionStatuses[key] ?? "pending";
  });
  const pendingCount = actionStatusEntries.filter((status) => status === "pending").length;
  const confirmedCount = actionStatusEntries.filter((status) => status === "confirmed").length;
  const issueCount = actionStatusEntries.filter((status) => status === "issue").length;
  const selectedIssueReasonEntries = explanation.reviewActionItems
    .map((_, index) => props.issueReasons[`${explanation.categoryId}:${index}`])
    .filter((reason): reason is ScenarioReviewIssueReason => Boolean(reason));
  const selectedIssueReasonLabels = SCENARIO_REVIEW_ISSUE_REASON_OPTIONS
    .filter(([reason]) => selectedIssueReasonEntries.includes(reason))
    .map(([, label]) => label);
  const conclusionLabel =
    issueCount > 0
      ? `复核结论：${explanation.categoryLabel}仍有 ${issueCount} 项差异，需补充原因和证据后归档。`
      : pendingCount > 0
        ? `复核结论：${explanation.categoryLabel}还有 ${pendingCount} 项待核对，暂不建议归档。`
        : `复核结论：${explanation.categoryLabel}动作已全部确认，可进入留痕归档。`;

  return (
    <div
      className="product-category-financial-analysis__explanation"
      data-testid="product-category-scenario-explanation"
    >
      <div className="product-category-financial-analysis__scenario-kicker">复核解释包</div>
      <strong>{explanation.categoryLabel}</strong>
      <p>{explanation.summaryLabel}</p>
      <div className="product-category-financial-analysis__bridge">
        <span className="product-category-financial-analysis__scenario-kicker">口径桥</span>
        <b className={`is-${explanation.bridgeTone}`}>{explanation.bridgeLabel}</b>
        <small>{explanation.bridgeConclusionLabel}</small>
      </div>
      <div className="product-category-financial-analysis__review-actions">
        <span className="product-category-financial-analysis__scenario-kicker">复核动作</span>
        {explanation.reviewActionItems.map((item, index) => {
          const categoryId = explanation.categoryId;
          const actionStatusKey = `${categoryId}:${index}`;
          const currentStatus = props.actionStatuses[actionStatusKey] ?? "pending";
          const currentReason = props.issueReasons[actionStatusKey];
          return (
            <div
              className="product-category-financial-analysis__review-action-item"
              key={actionStatusKey}
            >
              <small>{item}</small>
              <div className="product-category-financial-analysis__review-status-group">
                {SCENARIO_REVIEW_ACTION_STATUS_OPTIONS.map(([status, label]) => (
                  <button
                    aria-pressed={currentStatus === status}
                    className={`product-category-financial-analysis__review-status-button is-${status}`}
                    key={status}
                    onClick={() => props.onSetActionStatus(categoryId, index, status)}
                    type="button"
                  >
                    {label}
                  </button>
                ))}
              </div>
              {currentStatus === "issue" ? (
                <div className="product-category-financial-analysis__reason-group">
                  {SCENARIO_REVIEW_ISSUE_REASON_OPTIONS.map(([reason, label]) => (
                    <button
                      aria-pressed={currentReason === reason}
                      className="product-category-financial-analysis__reason-button"
                      key={reason}
                      onClick={() => props.onSetIssueReason(categoryId, index, reason)}
                      type="button"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      <div className="product-category-financial-analysis__review-console">
        <div className="product-category-financial-analysis__review-console-head">
          <span className="product-category-financial-analysis__scenario-kicker">复核结论台</span>
          <div className="product-category-financial-analysis__review-console-actions">
            <button
              onClick={() =>
                props.onBulkActionStatus(
                  explanation.categoryId,
                  explanation.reviewActionItems.length,
                  "confirmed",
                )
              }
              type="button"
            >
              全部确认
            </button>
            <button
              onClick={() => props.onResetActions(explanation.categoryId, explanation.reviewActionItems.length)}
              type="button"
            >
              重置复核
            </button>
          </div>
        </div>
        <div className="product-category-financial-analysis__review-totals">
          <b>待核对 {pendingCount}</b>
          <b>已确认 {confirmedCount}</b>
          <b>有差异 {issueCount}</b>
        </div>
        <strong>{conclusionLabel}</strong>
        <small>
          差异原因：
          {selectedIssueReasonLabels.length > 0 ? selectedIssueReasonLabels.join("、") : "未选择"}
        </small>
        <div className="product-category-financial-analysis__review-memo">
          <span>复核备忘</span>
          <p>
            当前产品：{explanation.categoryLabel}；情景：{explanation.triggerRateLabel}；差额：
            {explanation.scenarioDeltaLabel}；状态：待核对 {pendingCount}、已确认 {confirmedCount}、有差异{" "}
            {issueCount}。
          </p>
        </div>
      </div>
      <div className="product-category-financial-analysis__explanation-grid">
        <span>{explanation.sideLabel}</span>
        <span>基线 {explanation.baselineNetIncomeLabel}</span>
        <span>{explanation.triggerRateLabel} {explanation.scenarioNetIncomeLabel}</span>
        <span>{explanation.scenarioDeltaLabel}</span>
      </div>
      {explanation.driverRows.length === 0 ? (
        <small>{explanation.emptyCopy ?? "当前正式归因未返回可排序的驱动项。"}</small>
      ) : (
        <div className="product-category-financial-analysis__driver-list">
          <span>正式归因</span>
          {explanation.driverRows.map((row) => (
            <b className={`is-${row.tone}`} key={row.key}>
              {row.label} {row.valueLabel}
            </b>
          ))}
        </div>
      )}
    </div>
  );
}

function ProductCategoryScenarioComparisonPanel(props: {
  rows: ProductCategoryScenarioSensitivitySurface["comparisonRows"];
  filter: ScenarioComparisonFilter;
  selectedCategoryId: string | null;
  onFilterChange: (filter: ScenarioComparisonFilter) => void;
  onSelectCategory: (categoryId: string) => void;
}) {
  const visibleRows = props.rows.filter((row) => {
    if (props.filter === "pressure") {
      return row.worstDelta !== null && row.worstDelta < 0;
    }
    if (props.filter === "improvement") {
      return row.bestDelta !== null && row.bestDelta > 0;
    }
    return true;
  });
  const rateColumns = props.rows[0]?.cells ?? [];

  return (
    <div className="product-category-financial-analysis__comparison" data-testid="product-category-scenario-comparison">
      <div className="product-category-financial-analysis__comparison-head">
        <div>
          <div className="product-category-financial-analysis__scenario-kicker">多情景对比</div>
          <p>横向比较各产品行在不同 FTP 情景下的净营收和较基线差额。</p>
        </div>
        <div className="product-category-financial-analysis__comparison-filters">
          {SCENARIO_COMPARISON_FILTER_OPTIONS.map(([filter, label]) => (
            <button
              aria-pressed={props.filter === filter}
              key={filter}
              onClick={() => props.onFilterChange(filter)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {visibleRows.length === 0 ? (
        <div className="product-category-financial-analysis__empty">当前筛选下暂无可比较产品行。</div>
      ) : (
        <div className="product-category-financial-analysis__comparison-table-wrap">
          <table className="product-category-financial-analysis__comparison-table">
            <thead>
              <tr>
                <th>产品</th>
                <th>侧别</th>
                <th>基线</th>
                {rateColumns.map((cell) => (
                  <th key={cell.rate}>{cell.rateLabel}</th>
                ))}
                <th>最差情景</th>
                <th>区间</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr
                  className={props.selectedCategoryId === row.categoryId ? "is-selected" : undefined}
                  key={row.categoryId}
                >
                  <td>
                    <button
                      className="product-category-financial-analysis__comparison-row-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        props.onSelectCategory(row.categoryId);
                      }}
                      type="button"
                    >
                      {row.categoryLabel} 多情景对比
                    </button>
                  </td>
                  <td>{row.sideLabel}</td>
                  <td>{row.baselineNetIncomeLabel}</td>
                  {row.cells.map((cell) => (
                    <td className={`is-${cell.tone}`} key={cell.rate}>
                      {cell.netIncomeLabel} / {cell.deltaLabel}
                    </td>
                  ))}
                  <td className={`is-${row.tone}`}>
                    {row.worstRateLabel} / {row.worstDeltaLabel}
                  </td>
                  <td>{row.rangeLabel}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ProductCategoryScenarioActionClosurePanel(props: {
  rows: ProductCategoryScenarioSensitivitySurface["actionClosureRows"];
  statuses: Record<string, ScenarioActionClosureStatus>;
  memoCategoryId: string | null;
  onSetStatus: (categoryId: string, status: ScenarioActionClosureStatus) => void;
  onSelectMemo: (categoryId: string) => void;
}) {
  const statusCounts = SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS.map(([status, label]) => ({
    status,
    label,
    count: props.rows.filter((row) => (props.statuses[row.categoryId] ?? "todo") === status).length,
  }));
  const memoRow = props.memoCategoryId
    ? (props.rows.find((row) => row.categoryId === props.memoCategoryId) ?? null)
    : null;
  const memoStatusLabel = memoRow
    ? (SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS.find(
        ([status]) => status === (props.statuses[memoRow.categoryId] ?? "todo"),
      )?.[1] ?? "待处理")
    : "待处理";

  return (
    <div
      className="product-category-financial-analysis__closure"
      data-testid="product-category-scenario-action-closure"
    >
      <div className="product-category-financial-analysis__closure-head">
        <div>
          <div className="product-category-financial-analysis__scenario-kicker">情景动作闭环</div>
          <h4>本期经营动作清单</h4>
          <p>自动挑出承压产品，给出建议动作、复核证据和当前处理状态。</p>
        </div>
        <div className="product-category-financial-analysis__closure-totals">
          {statusCounts.map((item) => (
            <b key={item.status}>
              {item.label} {item.count}
            </b>
          ))}
        </div>
      </div>
      {props.rows.length === 0 ? (
        <div className="product-category-financial-analysis__empty">当前情景暂无需要闭环的承压动作。</div>
      ) : (
        <>
          <div className="product-category-financial-analysis__closure-list">
            {props.rows.map((row) => {
              const currentStatus = props.statuses[row.categoryId] ?? "todo";
              return (
                <article className="product-category-financial-analysis__closure-card" key={row.categoryId}>
                  <div className="product-category-financial-analysis__closure-card-head">
                    <span>{row.priorityLabel}</span>
                    <strong>{row.categoryLabel}</strong>
                    <b className={`is-${row.tone}`}>{row.exposureLabel}</b>
                  </div>
                  <p>
                    {row.sideLabel} · {row.triggerRateLabel} 情景净营收 {row.scenarioNetIncomeLabel} 亿元
                  </p>
                  <div className="product-category-financial-analysis__closure-action">
                    <span>建议动作</span>
                    <b>{row.recommendationLabel}</b>
                  </div>
                  <div className="product-category-financial-analysis__closure-evidence">
                    {row.evidenceItems.map((item) => (
                      <small key={item}>{item}</small>
                    ))}
                  </div>
                  <div className="product-category-financial-analysis__closure-status">
                    {SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS.map(([status, label]) => (
                      <button
                        aria-pressed={currentStatus === status}
                        key={status}
                        onClick={() => props.onSetStatus(row.categoryId, status)}
                        type="button"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <button
                    className="product-category-financial-analysis__closure-memo-button"
                    onClick={() => props.onSelectMemo(row.categoryId)}
                    type="button"
                  >
                    生成复核备忘
                  </button>
                </article>
              );
            })}
          </div>
          {memoRow ? (
            <div
              className="product-category-financial-analysis__closure-memo"
              data-testid="product-category-scenario-action-memo"
            >
              <span>复核备忘</span>
              <p>
                {memoRow.memoLabel} 状态：{memoStatusLabel}。
              </p>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function ProductCategoryFinancialAnalysisPanel(props: {
  scenarioSensitivity: ProductCategoryScenarioSensitivitySurface;
  scenarioExplanation: ProductCategoryScenarioExplanation | null;
  selectedScenarioReviewCategoryId: string | null;
  scenarioReviewActionStatuses: Record<string, ScenarioReviewActionStatus>;
  scenarioReviewIssueReasons: Record<string, ScenarioReviewIssueReason>;
  scenarioActionClosureStatuses: Record<string, ScenarioActionClosureStatus>;
  scenarioActionClosureMemoCategoryId: string | null;
  scenarioSensitivityRequested: boolean;
  scenarioSensitivityLoading: boolean;
  scenarioSensitivityError: boolean;
  onLoadScenarioSensitivity: () => void;
  onSelectScenarioReview: (categoryId: string) => void;
  onSetScenarioReviewActionStatus: (
    categoryId: string,
    actionIndex: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onSetScenarioReviewIssueReason: (
    categoryId: string,
    actionIndex: number,
    reason: ScenarioReviewIssueReason,
  ) => void;
  onBulkScenarioReviewActionStatus: (
    categoryId: string,
    actionCount: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onResetScenarioReviewActions: (categoryId: string, actionCount: number) => void;
  onSetScenarioActionClosureStatus: (categoryId: string, status: ScenarioActionClosureStatus) => void;
  onSelectScenarioActionClosureMemo: (categoryId: string) => void;
  waterfall: ProductCategoryAttributionWaterfallSurface;
  rootCause: ProductCategoryRootCauseSurface;
  decisionFocus: ProductCategoryDecisionFocusSurface;
}) {
  const scenarioExplanation = props.scenarioExplanation;
  const [scenarioComparisonFilter, setScenarioComparisonFilter] =
    useState<ScenarioComparisonFilter>("all");

  return (
    <section className="product-category-financial-analysis" data-testid="product-category-financial-analysis">
      <div className="product-category-financial-analysis__header">
        <div>
          <span className="product-category-operating-analysis__eyebrow">财务分析增强</span>
          <h2 className="product-category-operating-analysis__title">情景弹性、差异桥与决策焦点</h2>
          <p className="product-category-operating-analysis__description">
            保留正式表为主口径；这里只把后端情景结果和正式归因整理成可执行的财务观察。
          </p>
        </div>
        <span className="product-category-operating-analysis__badge">
          基线总净营收 {props.scenarioSensitivity.baselineGrandTotalLabel ?? "-"} 亿元
        </span>
      </div>
      <div className="product-category-financial-analysis__grid">
        <article
          className="product-category-financial-analysis__panel product-category-financial-analysis__panel--scenario"
          data-testid="product-category-scenario-sensitivity"
        >
          <div className="product-category-financial-analysis__panel-head">
            <div>
              <h3 className="product-category-financial-analysis__title">FTP 情景敏感度</h3>
              <p className="product-category-financial-analysis__note">
                四档情景均来自后端 scenario payload，本地仅展示与正式基线的差额。
              </p>
            </div>
            <button
              type="button"
              className="product-category-financial-analysis__load-button"
              onClick={props.onLoadScenarioSensitivity}
              disabled={props.scenarioSensitivityLoading}
            >
              {props.scenarioSensitivityRequested ? "刷新矩阵" : "加载矩阵"}
            </button>
          </div>
          {props.scenarioSensitivityError ? (
            <div className="product-category-financial-analysis__empty">情景敏感度加载失败。</div>
          ) : props.scenarioSensitivityLoading ? (
            <div className="product-category-financial-analysis__empty">正在加载四档 FTP 情景。</div>
          ) : props.scenarioSensitivity.emptyCopy ? (
            <div className="product-category-financial-analysis__empty">{props.scenarioSensitivity.emptyCopy}</div>
          ) : (
            <>
              <div className="product-category-financial-analysis__pressure-pack">
                <div className="product-category-financial-analysis__pressure-head">
                  <div>
                    <div className="product-category-financial-analysis__scenario-kicker">压力复核包</div>
                    <p>先看临界点、资产/负债冲抵，再决定复核顺序；以下均为情景辅助分析。</p>
                  </div>
                  <div className="product-category-financial-analysis__pressure-chip">
                    {props.scenarioSensitivity.pressureSummary.sideOffset.rateLabel}
                  </div>
                </div>
                <div className="product-category-financial-analysis__pressure-grid">
                  <div className="product-category-financial-analysis__pressure-metric">
                    <span>{props.scenarioSensitivity.pressureSummary.breakeven.label}</span>
                    <b className={`is-${props.scenarioSensitivity.pressureSummary.breakeven.tone}`}>
                      {props.scenarioSensitivity.pressureSummary.breakeven.valueLabel}
                    </b>
                    <small>{props.scenarioSensitivity.pressureSummary.breakeven.detailLabel}</small>
                  </div>
                  <div className="product-category-financial-analysis__pressure-offset">
                    <div className="product-category-financial-analysis__pressure-offset-head">
                      <span>资产/负债冲抵</span>
                      <b className={`is-${props.scenarioSensitivity.pressureSummary.sideOffset.tone}`}>
                        {props.scenarioSensitivity.pressureSummary.sideOffset.totalDeltaLabel}
                      </b>
                    </div>
                    <div className="product-category-financial-analysis__offset-bars">
                      <div className="product-category-financial-analysis__offset-bar-row">
                        <span>资产端 {props.scenarioSensitivity.pressureSummary.sideOffset.assetDeltaLabel}</span>
                        <div className="product-category-financial-analysis__offset-track">
                          <i
                            className={`product-category-financial-analysis__offset-bar is-asset ${props.scenarioSensitivity.pressureSummary.sideOffset.assetWidthClassName}`}
                          />
                        </div>
                      </div>
                      <div className="product-category-financial-analysis__offset-bar-row">
                        <span>负债端 {props.scenarioSensitivity.pressureSummary.sideOffset.liabilityDeltaLabel}</span>
                        <div className="product-category-financial-analysis__offset-track">
                          <i
                            className={`product-category-financial-analysis__offset-bar is-liability ${props.scenarioSensitivity.pressureSummary.sideOffset.liabilityWidthClassName}`}
                          />
                        </div>
                      </div>
                    </div>
                    <small>
                      冲抵 {props.scenarioSensitivity.pressureSummary.sideOffset.offsetLabel} 亿元 ·{" "}
                      {props.scenarioSensitivity.pressureSummary.sideOffset.conclusionLabel}
                    </small>
                  </div>
                </div>
                <div className="product-category-financial-analysis__review-board">
                  <div className="product-category-financial-analysis__scenario-kicker">复核顺序</div>
                  {props.scenarioSensitivity.pressureSummary.reviewRows.length === 0 ? (
                    <div className="product-category-financial-analysis__empty">暂无可排序的复核产品行。</div>
                  ) : (
                    <div className="product-category-financial-analysis__review-list">
                      {props.scenarioSensitivity.pressureSummary.reviewRows.map((row) => (
                        <button
                          aria-pressed={props.selectedScenarioReviewCategoryId === row.categoryId}
                          className="product-category-financial-analysis__review-row"
                          key={row.categoryId}
                          onClick={() => props.onSelectScenarioReview(row.categoryId)}
                          type="button"
                        >
                          <span>{row.priorityLabel}</span>
                          <strong>{row.categoryLabel}</strong>
                          <small>{row.sideLabel} · {row.triggerRateLabel} · {row.actionLabel}</small>
                          <b className={`is-${row.tone}`}>{row.deltaLabel}</b>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {scenarioExplanation ? (
                  <ProductCategoryScenarioExplanationCard
                    actionStatuses={props.scenarioReviewActionStatuses}
                    explanation={scenarioExplanation}
                    issueReasons={props.scenarioReviewIssueReasons}
                    onBulkActionStatus={props.onBulkScenarioReviewActionStatus}
                    onResetActions={props.onResetScenarioReviewActions}
                    onSetActionStatus={props.onSetScenarioReviewActionStatus}
                    onSetIssueReason={props.onSetScenarioReviewIssueReason}
                  />
                ) : null}
              </div>
              <ProductCategoryScenarioActionClosurePanel
                memoCategoryId={props.scenarioActionClosureMemoCategoryId}
                onSelectMemo={props.onSelectScenarioActionClosureMemo}
                onSetStatus={props.onSetScenarioActionClosureStatus}
                rows={props.scenarioSensitivity.actionClosureRows}
                statuses={props.scenarioActionClosureStatuses}
              />
              <ProductCategoryScenarioComparisonPanel
                filter={scenarioComparisonFilter}
                onFilterChange={setScenarioComparisonFilter}
                onSelectCategory={props.onSelectScenarioReview}
                rows={props.scenarioSensitivity.comparisonRows}
                selectedCategoryId={props.selectedScenarioReviewCategoryId}
              />
              <div className="product-category-financial-analysis__table-wrap">
                <table className="product-category-financial-analysis__table">
                  <thead>
                    <tr>
                      <th>FTP</th>
                      <th>资产端</th>
                      <th>负债端</th>
                      <th>总净营收</th>
                      <th>最大变动行</th>
                    </tr>
                  </thead>
                  <tbody>
                    {props.scenarioSensitivity.rows.map((row) => (
                      <tr key={row.rate}>
                        <td>{row.rateLabel}</td>
                        <td>{row.assetNetIncomeLabel} / {row.assetDeltaLabel}</td>
                        <td>{row.liabilityNetIncomeLabel} / {row.liabilityDeltaLabel}</td>
                        <td className={`is-${row.tone}`}>{row.grandNetIncomeLabel} / {row.grandDeltaLabel}</td>
                        <td>{row.topMoverCategoryLabel} {row.topMoverDeltaLabel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="product-category-financial-analysis__scenario-path">
                <div className="product-category-financial-analysis__scenario-kicker">FTP 压力路径</div>
                <div className="product-category-financial-analysis__path-rail">
                  {props.scenarioSensitivity.pathPoints.map((point) => (
                    <div
                      className={`product-category-financial-analysis__path-point is-${point.tone} ${point.positionClassName}`}
                      key={point.rateLabel}
                    >
                      <span>{point.rateLabel}</span>
                      <strong>{point.grandNetIncomeLabel}</strong>
                      <small>{point.grandDeltaLabel}</small>
                    </div>
                  ))}
                </div>
              </div>
              <div className="product-category-financial-analysis__scenario-brief">
                <div className="product-category-financial-analysis__scenario-summary">
                  <div className="product-category-financial-analysis__scenario-kicker">情景解读</div>
                  <p>{props.scenarioSensitivity.analysisCopy ?? "四档 FTP 情景已加载，可结合下方区间和变动行继续复核。"}</p>
                  <div className="product-category-financial-analysis__insight-grid">
                    {props.scenarioSensitivity.insightCards.map((card) => (
                      <div className="product-category-financial-analysis__insight-card" key={card.key}>
                        <span>{card.label}</span>
                        <b className={`is-${card.tone}`}>{card.valueLabel}</b>
                        <small>{card.detailLabel}</small>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="product-category-financial-analysis__scenario-actions">
                  <div className="product-category-financial-analysis__scenario-kicker">管理动作</div>
                  {props.scenarioSensitivity.actionItems.map((item) => (
                    <div className="product-category-financial-analysis__action-row" key={item.title}>
                      <div>
                        <strong>{item.title}</strong>
                        <span>{item.detailLabel}</span>
                      </div>
                      <b className={`is-${item.tone}`}>{item.valueLabel}</b>
                    </div>
                  ))}
                </div>
                <div className="product-category-financial-analysis__scenario-risks">
                  <div className="product-category-financial-analysis__scenario-kicker">关键变动行排行</div>
                  {props.scenarioSensitivity.riskRows.length === 0 ? (
                    <div className="product-category-financial-analysis__empty">暂无可排序的最大变动产品行。</div>
                  ) : (
                    <div className="product-category-financial-analysis__risk-list">
                      {props.scenarioSensitivity.riskRows.map((row) => (
                        <div className="product-category-financial-analysis__risk-row" key={row.categoryLabel}>
                          <div>
                            <strong>{row.categoryLabel}</strong>
                            <span>{row.occurrenceLabel} · 最弱 FTP {row.worstRateLabel}</span>
                          </div>
                          <b className={`is-${row.tone}`}>{row.worstDeltaLabel}</b>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="product-category-financial-analysis__scenario-heat">
                  <div className="product-category-financial-analysis__scenario-kicker">产品行热力条</div>
                  {props.scenarioSensitivity.heatRows.map((row) => (
                    <div className="product-category-financial-analysis__heat-row" key={row.categoryLabel}>
                      <div className="product-category-financial-analysis__heat-row-head">
                        <span>{row.categoryLabel}</span>
                        <b className={`is-${row.tone}`}>{row.exposureLabel}</b>
                      </div>
                      <div className="product-category-financial-analysis__heat-track">
                        <span
                          className={`product-category-financial-analysis__heat-bar is-${row.tone} ${row.widthClassName}`}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </article>
        <article
          className="product-category-financial-analysis__panel"
          data-testid="product-category-attribution-waterfall"
        >
          <div className="product-category-financial-analysis__panel-head">
            <div>
              <h3 className="product-category-financial-analysis__title">经营差异瀑布</h3>
              <p className="product-category-financial-analysis__note">
                {props.waterfall.title}，变动合计 {props.waterfall.deltaLabel} 亿元。
              </p>
            </div>
          </div>
          {props.waterfall.emptyCopy ? (
            <div className="product-category-financial-analysis__empty">{props.waterfall.emptyCopy}</div>
          ) : (
            <div className="product-category-financial-analysis__waterfall">
              {props.waterfall.rows.map((row) => (
                <div className="product-category-financial-analysis__waterfall-row" key={row.key}>
                  <span>{row.label}</span>
                  <b className={`is-${row.tone}`}>{row.valueLabel}</b>
                  <small>累计 {row.cumulativeLabel}</small>
                </div>
              ))}
            </div>
          )}
        </article>
        <article
          className="product-category-financial-analysis__panel"
          data-testid="product-category-root-cause"
        >
          <div className="product-category-financial-analysis__panel-head">
            <div>
              <h3 className="product-category-financial-analysis__title">产品差异根因拆解台</h3>
              <p className="product-category-financial-analysis__note">
                从正式归因中挑出变动最大的产品行，拆成规模、利率、FTP、直接和残差证据。
              </p>
            </div>
          </div>
          {props.rootCause.emptyCopy || !props.rootCause.headline ? (
            <div className="product-category-financial-analysis__empty">{props.rootCause.emptyCopy}</div>
          ) : (
            <div className="product-category-financial-analysis__root-cause">
              <div className="product-category-financial-analysis__root-cause-head">
                <div>
                  <span>主导原因</span>
                  <strong>{props.rootCause.headline.categoryLabel}</strong>
                  <small>{props.rootCause.headline.conclusionLabel}</small>
                </div>
                <b className={`is-${props.rootCause.headline.tone}`}>{props.rootCause.headline.deltaLabel}</b>
              </div>
              <div className="product-category-financial-analysis__root-cause-metrics">
                <span>本期 {props.rootCause.headline.currentNetIncomeLabel}</span>
                <span>对比期 {props.rootCause.headline.priorNetIncomeLabel}</span>
                <span>规模 {props.rootCause.headline.scaleLabel}</span>
                <span>收益率 {props.rootCause.headline.yieldLabel}</span>
              </div>
              <div className="product-category-financial-analysis__root-cause-drivers">
                {props.rootCause.driverRows.map((row) => (
                  <div className="product-category-financial-analysis__root-cause-driver" key={row.key}>
                    <span>{row.label}</span>
                    <b className={`is-${row.tone}`}>{row.valueLabel}</b>
                    <small>{row.shareLabel}</small>
                  </div>
                ))}
              </div>
              <div className="product-category-financial-analysis__root-cause-evidence">
                {props.rootCause.evidenceItems.map((item) => (
                  <small key={item}>{item}</small>
                ))}
              </div>
            </div>
          )}
        </article>
        <article
          className="product-category-financial-analysis__panel"
          data-testid="product-category-decision-focus"
        >
          <div className="product-category-financial-analysis__panel-head">
            <div>
              <h3 className="product-category-financial-analysis__title">本期决策焦点</h3>
              <p className="product-category-financial-analysis__note">
                只使用当前产品行和正式归因，按贡献、压力、恶化和未解释残差提取。
              </p>
            </div>
          </div>
          {props.decisionFocus.emptyCopy ? (
            <div className="product-category-financial-analysis__empty">{props.decisionFocus.emptyCopy}</div>
          ) : (
            <div className="product-category-financial-analysis__focus-list">
              {props.decisionFocus.items.map((item) => (
                <div className="product-category-financial-analysis__focus-item" key={item.key}>
                  <div>
                    <strong>{item.categoryLabel}</strong>
                    <span>{item.reasonLabel} · {item.secondaryLabel}</span>
                  </div>
                  <b className={`is-${item.tone}`}>{item.primaryLabel}</b>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}

function ProductCategoryAttributionCompareSwitch(props: {
  compare: ProductCategoryAttributionCompare;
  onCompareChange: (compare: ProductCategoryAttributionCompare) => void;
}) {
  return (
    <div className="product-category-attribution__actions">
      <span className="product-category-attribution__badge">正式基线</span>
      <div
        aria-label="归因对比方式"
        className="product-category-attribution__segmented"
        role="group"
      >
        {ATTRIBUTION_COMPARE_OPTIONS.map((option) => (
          <button
            aria-pressed={props.compare === option.value}
            className={[
              "product-category-attribution__segmented-button",
              props.compare === option.value ? "product-category-attribution__segmented-button--active" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={option.value}
            onClick={() => props.onCompareChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function AttributionMetric(props: {
  label: string;
  value: ProductCategoryAttributionRow["effects"]["scale_effect"] | null | undefined;
}) {
  return (
    <div className="product-category-attribution__metric">
      <span className="product-category-attribution__metric-label">{props.label}</span>
      <span className="product-category-attribution__metric-value">
        {formatProductCategoryAttributionEffect(props.value)}
      </span>
    </div>
  );
}

function AttributionComparisonTable(props: {
  compare: ProductCategoryAttributionCompare;
  currentReportDate: string;
  priorReportDate: string;
  rows: ProductCategoryAttributionRow[];
}) {
  const priorLabel = productCategoryAttributionPriorLabel(props.compare);
  return (
    <div className="product-category-attribution__compare-wrap">
      <div className="product-category-attribution__section-head">
        <div>
          <div className="product-category-attribution__section-title">归因拆分</div>
          <p className="product-category-attribution__section-note">
            先看变动闭合，再按需查看本期与{priorLabel}的日均、收支、利率和 FTP 明细。
          </p>
        </div>
      </div>
      <div className="product-category-attribution__table-wrap">
        <table
          className="product-category-attribution__table product-category-attribution__table--breakdown"
          data-testid="product-category-attribution-comparison-table"
        >
          <thead>
            <tr>
              <th>项目</th>
              <th>变动</th>
              {ATTRIBUTION_EFFECT_COLUMNS.map(([, label]) => (
                <th key={`effect-${label}`}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.rows.map((row) => (
              <tr
                className={attributionRowClassName(row)}
                data-testid={`product-category-attribution-comparison-row-${row.category_id}`}
                key={row.category_id}
              >
                <td className="product-category-attribution__item-cell">
                  <span className="product-category-attribution__row-name">{row.category_name}</span>
                  {row.state === "partial" ? (
                    <span className="product-category-attribution__row-state">部分</span>
                  ) : null}
                </td>
                <td className={attributionToneClass(row.effects.delta_business_net_income)}>
                  {formatProductCategoryAttributionEffect(row.effects.delta_business_net_income)}
                </td>
                {ATTRIBUTION_EFFECT_COLUMNS.map(([key]) => (
                  <td
                    className={["product-category-attribution__effect-cell", attributionToneClass(row.effects[key])]
                      .filter(Boolean)
                      .join(" ")}
                    key={`effect-${key}`}
                  >
                    {formatProductCategoryAttributionEffect(row.effects[key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="product-category-attribution__section-head product-category-attribution__section-head--detail">
        <div>
          <div className="product-category-attribution__section-title">
            本期 / {priorLabel}明细
          </div>
          <p className="product-category-attribution__section-note">
            本期 {formatProductCategoryReportMonthLabel(props.currentReportDate)} · {priorLabel}{" "}
            {formatProductCategoryReportMonthLabel(props.priorReportDate)}
          </p>
        </div>
      </div>
      <div className="product-category-attribution__table-wrap">
        <table
          className="product-category-attribution__table product-category-attribution__table--detail"
          data-testid="product-category-attribution-detail-table"
        >
          <thead>
            <tr>
              <th rowSpan={2}>项目</th>
              <th className="product-category-attribution__group-head--current" colSpan={5}>
                本期 {formatProductCategoryReportMonthLabel(props.currentReportDate)}
              </th>
              <th className="product-category-attribution__group-head--prior" colSpan={5}>
                {priorLabel} {formatProductCategoryReportMonthLabel(props.priorReportDate)}
              </th>
            </tr>
            <tr>
              {ATTRIBUTION_POINT_COLUMNS.map(([, label]) => (
                <th key={`detail-current-${label}`}>{label}</th>
              ))}
              {ATTRIBUTION_POINT_COLUMNS.map(([, label]) => (
                <th key={`detail-prior-${label}`}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.rows.map((row) => (
              <tr className={attributionRowClassName(row)} key={`detail-${row.category_id}`}>
                <td className="product-category-attribution__item-cell">
                  <span className="product-category-attribution__row-name">{row.category_name}</span>
                  {row.state === "partial" ? (
                    <span className="product-category-attribution__row-state">部分</span>
                  ) : null}
                </td>
                {ATTRIBUTION_POINT_COLUMNS.map(([key]) => (
                  <td key={`detail-current-${key}`}>
                    {formatAttributionPointValue(row, row.current, key)}
                  </td>
                ))}
                {ATTRIBUTION_POINT_COLUMNS.map(([key]) => (
                  <td className="product-category-attribution__prior-cell" key={`detail-prior-${key}`}>
                    {formatAttributionPointValue(row, row.prior, key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatAttributionPointValue(
  row: Pick<ProductCategoryAttributionRow, "side">,
  point: ProductCategoryAttributionRow["current"],
  key: (typeof ATTRIBUTION_POINT_COLUMNS)[number][0],
): string {
  if (!point) {
    return "-";
  }
  if (key === "yield_pct") {
    const value = formatProductCategoryYieldValue(point.yield_pct);
    return value === "-" ? "-" : `${value}%`;
  }
  if (key === "scale") {
    return formatProductCategoryRowDisplayValue({ side: row.side }, point.scale);
  }
  return formatProductCategoryAttributionEffect(point[key]);
}

function attributionToneClass(value: ProductCategoryAttributionRow["effects"]["scale_effect"]): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) {
    return "";
  }
  return numeric > 0
    ? "product-category-attribution__number--positive"
    : "product-category-attribution__number--negative";
}

function attributionRowClassName(row: ProductCategoryAttributionRow): string | undefined {
  return row.category_id.endsWith("_total") || row.category_id === "grand_total"
    ? "product-category-attribution__total-row"
    : undefined;
}

export default function ProductCategoryPnlPage() {
  const client = useApiClient();
  const [selectedBranch, setSelectedBranch] = useState<"product_category_pnl" | "monthly_operating_analysis">("product_category_pnl");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedView, setSelectedView] = useState("monthly");
  const [scenarioRate, setScenarioRate] = useState("1.75");
  const [appliedScenarioRate, setAppliedScenarioRate] = useState("");
  const [scenarioRateTouched, setScenarioRateTouched] = useState(false);
  const [attributionCompare, setAttributionCompare] =
    useState<ProductCategoryAttributionCompare>("mom");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshPollSnapshot, setRefreshPollSnapshot] = useState<{ status: string; run_id?: string } | null>(
    null,
  );
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [scenarioSensitivityRequested, setScenarioSensitivityRequested] = useState(false);
  const [selectedScenarioReviewCategoryId, setSelectedScenarioReviewCategoryId] = useState<string | null>(null);
  const [scenarioReviewActionStatuses, setScenarioReviewActionStatuses] = useState<
    Record<string, ScenarioReviewActionStatus>
  >({});
  const [scenarioReviewIssueReasons, setScenarioReviewIssueReasons] = useState<
    Record<string, ScenarioReviewIssueReason>
  >({});
  const [scenarioActionClosureStatuses, setScenarioActionClosureStatuses] = useState<
    Record<string, ScenarioActionClosureStatus>
  >({});
  const [scenarioActionClosureMemoCategoryId, setScenarioActionClosureMemoCategoryId] = useState<string | null>(null);
  const [loadedTrendDiagnosticsKey, setLoadedTrendDiagnosticsKey] = useState("");
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [isSubmittingAdjustment, setIsSubmittingAdjustment] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [lastAdjustmentId, setLastAdjustmentId] = useState<string | null>(null);
  const [interestSpreadAttributionSelection, setInterestSpreadAttributionSelection] =
    useState<ProductCategoryInterestSpreadAttributionSelection>({ basis: "weighted", month: 1 });
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
      setInterestSpreadAttributionSelection((current) =>
        monthAnchoredInterestSpreadSelection(current, next),
      );
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
    setInterestSpreadAttributionSelection((current) =>
      monthAnchoredInterestSpreadSelection(current, nextDate),
    );
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

  const scenarioSensitivityQueries = useQueries({
    queries: PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => ({
      queryKey: [
        "product-category-pnl",
        "scenario-sensitivity",
        client.mode,
        selectedDate,
        selectedView,
        option.value,
      ],
      queryFn: () =>
        client.getProductCategoryPnl({
          reportDate: selectedDate,
          view: selectedView,
          scenarioRatePct: option.value,
        }),
      enabled: Boolean(selectedDate && baselineQuery.data?.result && scenarioSensitivityRequested),
      retry: false,
    })),
  });

  const adjustmentsQuery = useQuery({
    queryKey: ["product-category-pnl", "adjustments", client.mode, selectedDate],
    queryFn: () => client.getProductCategoryManualAdjustments(selectedDate),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const attributionQuery = useQuery({
    queryKey: ["product-category-pnl", "attribution", client.mode, selectedDate, attributionCompare],
    queryFn: () =>
      client.getProductCategoryAttribution({
        reportDate: selectedDate,
        compare: attributionCompare,
      }),
    enabled: Boolean(selectedDate && selectedView === "monthly"),
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
  const trendDiagnosticsKey = `${selectedDate}|${selectedView}|${appliedScenarioRate}`;
  const trendDiagnosticsLoaded =
    Boolean(selectedDate) && loadedTrendDiagnosticsKey === trendDiagnosticsKey;
  const selectedYearMonth = useMemo(() => reportDateYearMonth(selectedDate), [selectedDate]);

  const rowsToRender = useMemo(
    () => selectProductCategoryDetailRows(baseline?.rows, scenario?.rows),
    [baseline?.rows, scenario?.rows],
  );
  const operatingAnalysisSurface = useMemo(
    () =>
      selectProductCategoryOperatingAnalysisSurface({
        rows: rowsToRender,
        grandTotal: displayedGrandTotal,
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, displayedGrandTotal, rowsToRender],
  );
  const scenarioSensitivityPayloads = useMemo(
    () => scenarioSensitivityQueries.flatMap((query) => (query.data?.result ? [query.data.result] : [])),
    [scenarioSensitivityQueries],
  );
  const scenarioSensitivitySurface = useMemo(
    () =>
      selectProductCategoryScenarioSensitivitySurface({
        baseline,
        scenarios: scenarioSensitivityPayloads,
      }),
    [baseline, scenarioSensitivityPayloads],
  );
  const scenarioReviewRows = scenarioSensitivitySurface.pressureSummary.reviewRows;
  const selectedScenarioExplanationCategoryId =
    scenarioReviewRows.find((row) => row.categoryId === selectedScenarioReviewCategoryId)?.categoryId ??
    scenarioReviewRows[0]?.categoryId ??
    null;
  const scenarioExplanation = useMemo(
    () =>
      selectProductCategoryScenarioExplanation({
        categoryId: selectedScenarioExplanationCategoryId,
        baseline,
        scenarios: scenarioSensitivityPayloads,
        attribution: attributionQuery.data?.result,
      }),
    [
      attributionQuery.data?.result,
      baseline,
      scenarioSensitivityPayloads,
      selectedScenarioExplanationCategoryId,
    ],
  );
  const handleScenarioReviewActionStatus = useCallback(
    (categoryId: string, actionIndex: number, status: ScenarioReviewActionStatus) => {
      const actionStatusKey = `${categoryId}:${actionIndex}`;
      setScenarioReviewActionStatuses((current) => ({
        ...current,
        [actionStatusKey]: status,
      }));
      if (status !== "issue") {
        setScenarioReviewIssueReasons((current) => {
          if (!(actionStatusKey in current)) {
            return current;
          }
          const next = { ...current };
          delete next[actionStatusKey];
          return next;
        });
      }
    },
    [],
  );
  const handleScenarioReviewIssueReason = useCallback(
    (categoryId: string, actionIndex: number, reason: ScenarioReviewIssueReason) => {
      setScenarioReviewIssueReasons((current) => ({
        ...current,
        [`${categoryId}:${actionIndex}`]: reason,
      }));
      setScenarioReviewActionStatuses((current) => ({
        ...current,
        [`${categoryId}:${actionIndex}`]: "issue",
      }));
    },
    [],
  );
  const handleBulkScenarioReviewActionStatus = useCallback(
    (categoryId: string, actionCount: number, status: ScenarioReviewActionStatus) => {
      setScenarioReviewActionStatuses((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          next[`${categoryId}:${index}`] = status;
        }
        return next;
      });
      if (status !== "issue") {
        setScenarioReviewIssueReasons((current) => {
          const next = { ...current };
          for (let index = 0; index < actionCount; index += 1) {
            delete next[`${categoryId}:${index}`];
          }
          return next;
        });
      }
    },
    [],
  );
  const handleResetScenarioReviewActions = useCallback((categoryId: string, actionCount: number) => {
    setScenarioReviewActionStatuses((current) => {
      const next = { ...current };
      for (let index = 0; index < actionCount; index += 1) {
        delete next[`${categoryId}:${index}`];
      }
      return next;
    });
    setScenarioReviewIssueReasons((current) => {
      const next = { ...current };
      for (let index = 0; index < actionCount; index += 1) {
        delete next[`${categoryId}:${index}`];
      }
      return next;
    });
  }, []);
  const handleScenarioActionClosureStatus = useCallback(
    (categoryId: string, status: ScenarioActionClosureStatus) => {
      setScenarioActionClosureStatuses((current) => ({
        ...current,
        [categoryId]: status,
      }));
    },
    [],
  );
  const attributionWaterfallSurface = useMemo(
    () => selectProductCategoryAttributionWaterfallSurface(attributionQuery.data?.result),
    [attributionQuery.data?.result],
  );
  const rootCauseSurface = useMemo(
    () =>
      selectProductCategoryRootCauseSurface({
        rows: rowsToRender,
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, rowsToRender],
  );
  const decisionFocusSurface = useMemo(
    () =>
      selectProductCategoryDecisionFocusSurface({
        rows: rowsToRender,
        grandTotal: displayedGrandTotal,
        attribution: attributionQuery.data?.result,
      }),
    [attributionQuery.data?.result, displayedGrandTotal, rowsToRender],
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
      enabled: Boolean(trendDiagnosticsLoaded && point.reportDate && point.view),
      retry: false,
    })),
  });
  const trendHistoryAttributionQueries = useQueries({
    queries: trendHistoryPoints.map((point) => ({
      queryKey: [
        "product-category-pnl",
        "trend-history-attribution",
        client.mode,
        point.reportDate,
        "mom",
      ],
      queryFn: () =>
        client.getProductCategoryAttribution({
          reportDate: point.reportDate,
          compare: "mom",
        }),
      enabled: Boolean(trendDiagnosticsLoaded && selectedView === "monthly" && point.reportDate),
      retry: false,
    })),
  });
  const interestSpreadComparisonReportPoints = useMemo(
    () =>
      selectProductCategoryTwoYearInterestSpreadReportPoints(
        selectedDate,
        datesQuery.data?.result.report_dates,
        selectedView,
      ),
    [datesQuery.data?.result.report_dates, selectedDate, selectedView],
  );
  const interestSpreadComparisonCurrentPoint = useMemo(
    () => interestSpreadComparisonReportPoints.find((point) => point.reportDate === selectedDate),
    [interestSpreadComparisonReportPoints, selectedDate],
  );
  const interestSpreadComparisonHistoryPoints = useMemo(
    () => interestSpreadComparisonReportPoints.filter((point) => point.reportDate !== selectedDate),
    [interestSpreadComparisonReportPoints, selectedDate],
  );
  const interestSpreadComparisonQueries = useQueries({
    queries: interestSpreadComparisonHistoryPoints.map((point) => ({
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
      enabled: Boolean(trendDiagnosticsLoaded && point.reportDate && point.view),
      retry: false,
    })),
  });
  const trendSnapshots = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(currentSelectedPayload
              ? [buildProductCategoryTrendSnapshot(currentSelectedPayload, currentTrendPoint?.label)]
              : []),
            ...trendHistoryQueries.flatMap((query, index) =>
              query.data
                ? [buildProductCategoryTrendSnapshot(query.data.result, trendHistoryPoints[index]?.label)]
                : [],
            ),
          ]
        : [],
    [currentSelectedPayload, currentTrendPoint?.label, trendDiagnosticsLoaded, trendHistoryPoints, trendHistoryQueries],
  );
  const operatingActionBacktestPayloads = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(baseline ? [baseline] : []),
            ...trendHistoryQueries.flatMap((query) => (query.data?.result ? [query.data.result] : [])),
          ]
        : baseline
          ? [baseline]
          : [],
    [baseline, trendDiagnosticsLoaded, trendHistoryQueries],
  );
  const operatingActionBacktestAttributions = useMemo(() => {
    const byReportDate = new Map<string, ProductCategoryAttributionPayload | null>();
    if (attributionQuery.data?.result && attributionCompare === "mom") {
      byReportDate.set(attributionQuery.data.result.report_date, attributionQuery.data.result);
    }
    trendHistoryAttributionQueries.forEach((query) => {
      if (query.data?.result) {
        byReportDate.set(query.data.result.report_date, query.data.result);
      }
    });
    return byReportDate;
  }, [attributionCompare, attributionQuery.data?.result, trendHistoryAttributionQueries]);
  const operatingActionBacktestSurface = useMemo(
    () =>
      selectProductCategoryOperatingActionBacktestSurface({
        payloads: operatingActionBacktestPayloads,
        attributionsByReportDate: operatingActionBacktestAttributions,
      }),
    [operatingActionBacktestAttributions, operatingActionBacktestPayloads],
  );
  const interestSpreadComparisonSnapshots = useMemo(
    () =>
      trendDiagnosticsLoaded
        ? [
            ...(currentSelectedPayload && interestSpreadComparisonCurrentPoint
              ? [
                  buildProductCategoryTrendSnapshot(
                    currentSelectedPayload,
                    interestSpreadComparisonCurrentPoint.label,
                  ),
                ]
              : []),
            ...interestSpreadComparisonQueries.flatMap((query, index) =>
              query.data
                ? [
                    buildProductCategoryTrendSnapshot(
                      query.data.result,
                      interestSpreadComparisonHistoryPoints[index]?.label,
                    ),
                  ]
                : [],
            ),
          ]
        : [],
    [
      currentSelectedPayload,
      interestSpreadComparisonCurrentPoint,
      interestSpreadComparisonHistoryPoints,
      interestSpreadComparisonQueries,
      trendDiagnosticsLoaded,
    ],
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
  const interestSpreadYearComparisonChart = useMemo(
    () => selectProductCategoryInterestSpreadYearComparisonChart(interestSpreadComparisonSnapshots),
    [interestSpreadComparisonSnapshots],
  );
  const cnyInterestSpreadYearComparisonChart = useMemo(
    () => selectProductCategoryInterestSpreadYearComparisonChart(interestSpreadComparisonSnapshots, "cny"),
    [interestSpreadComparisonSnapshots],
  );
  const intermediateBusinessIncomeYearComparisonChart = useMemo(
    () => selectProductCategoryIntermediateBusinessIncomeYearComparisonChart(interestSpreadComparisonSnapshots),
    [interestSpreadComparisonSnapshots],
  );
  const interestSpreadAttributionSurface = useMemo(
    () =>
      selectedYearMonth
        ? selectProductCategoryInterestSpreadAttributionSurface(
            interestSpreadComparisonSnapshots,
            interestSpreadAttributionSelection,
            selectedYearMonth.year,
          )
        : null,
    [interestSpreadAttributionSelection, interestSpreadComparisonSnapshots, selectedYearMonth],
  );
  const handleInterestSpreadAttributionPointClick = useCallback(
    (
      basis: ProductCategoryInterestSpreadBasis,
      monthKeys: number[] | undefined,
      params: { dataIndex?: number },
    ) => {
      if (typeof params.dataIndex !== "number") {
        return;
      }
      const month = monthKeys?.[params.dataIndex];
      if (!month) {
        return;
      }
      setInterestSpreadAttributionSelection({ basis, month });
    },
    [],
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
  const interestSpreadYearComparisonOption = useMemo(
    () =>
      interestSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: interestSpreadYearComparisonChart.labels,
            series: interestSpreadYearComparisonChart.series.map((series, index) => ({
              name: series.year,
              data: series.spread,
              color:
                index === interestSpreadYearComparisonChart.series.length - 1
                  ? designTokens.color.danger[500]
                  : designTokens.color.neutral[500],
            })),
          })
        : null,
    [interestSpreadYearComparisonChart],
  );
  const cnyInterestSpreadYearComparisonOption = useMemo(
    () =>
      cnyInterestSpreadYearComparisonChart
        ? buildInterestSpreadYearComparisonChartOption({
            labels: cnyInterestSpreadYearComparisonChart.labels,
            series: cnyInterestSpreadYearComparisonChart.series.map((series, index) => ({
              name: series.year,
              data: series.spread,
              color:
                index === cnyInterestSpreadYearComparisonChart.series.length - 1
                  ? designTokens.color.primary[600]
                  : designTokens.color.neutral[500],
            })),
          })
        : null,
    [cnyInterestSpreadYearComparisonChart],
  );
  const intermediateBusinessIncomeYearComparisonOption = useMemo(
    () =>
      intermediateBusinessIncomeYearComparisonChart
        ? buildIncomeYearComparisonChartOption({
            labels: intermediateBusinessIncomeYearComparisonChart.labels,
            series: intermediateBusinessIncomeYearComparisonChart.series.map((series, index) => ({
              name: series.year,
              data: series.income,
              color:
                index === intermediateBusinessIncomeYearComparisonChart.series.length - 1
                  ? designTokens.color.success[600]
                  : designTokens.color.neutral[500],
            })),
          })
        : null,
    [intermediateBusinessIncomeYearComparisonChart],
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
        className="product-category-summary"
      >
        <span>当前场景：{currentSceneRate}%</span>
        <span>基准场景：{baselineRate}%</span>
        <span className="product-category-summary__total">
          合计：{formatProductCategoryValue(displayedGrandTotal?.business_net_income)}
        </span>
      </div>
    ) : null;
  const ledgerPnlHref = buildLedgerPnlHrefForReportDate(selectedDate);

  if (selectedBranch === "monthly_operating_analysis") {
    return (
      <section data-testid="product-category-page">
        <FilterBar className="product-category-branch-switcher">
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
    <section data-testid="product-category-page" className="product-category-page-shell">
      <FilterBar className="product-category-branch-switcher">
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
      <PageDecisionHero
        testId="product-category-contract-hero"
        className="product-category-contract-hero"
        titleTestId="product-category-page-title"
        questionTestId="product-category-page-subtitle"
        eyebrow="工作台"
        title="产品分类损益"
        businessQuestion="按业务分类查看损益、FTP 和净收入。用于经营分析，不等同于逐笔损益明细。"
        reportDateSlot={<span data-testid="product-category-report-date-slot">报表日期：{selectedDate || "待选"}</span>}
        conclusion={
          <p
            data-testid="product-category-boundary-copy"
            className="product-category-contract-hero__boundary-copy"
          >
            系统层经营口径：正式基线来自正式读模型；情景预览仅在显式应用后生效。
          </p>
        }
        actions={
          <div className="product-category-contract-hero__actions">
            <span
              data-testid="product-category-role-badge"
              className="product-category-contract-hero__chip product-category-contract-hero__chip--role"
            >
              系统层
            </span>
            <span
              className={`product-category-contract-hero__chip product-category-contract-hero__chip--${
                client.mode === "real" ? "real" : "mock"
              }`}
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
              className="product-category-contract-hero__button"
            >
              + 手工录入
            </button>
            <button
              type="button"
              data-testid="product-category-refresh-button"
              onClick={() => void handleRefresh()}
              disabled={isRefreshing}
              className="product-category-contract-hero__button"
            >
              {isRefreshing ? "刷新中..." : "刷新损益数据"}
            </button>
          </div>
        }
      >
        <div className="product-category-contract-hero__status-stack">
          {isRefreshing ? (
            <p data-testid="product-category-refresh-status" className="product-category-contract-hero__status-line">
              {formatProductCategoryRefreshStatusLine(refreshPollSnapshot)}
            </p>
          ) : null}
          {lastRefreshRunId ? (
            <p className="product-category-contract-hero__status-note">
              最近刷新任务：{lastRefreshRunId}
            </p>
          ) : null}
          {lastAdjustmentId ? (
            <p className="product-category-contract-hero__status-note">
              最近录入调整：{lastAdjustmentId}
            </p>
          ) : null}
          {refreshError ? (
            <p className="product-category-contract-hero__status-error">{refreshError}</p>
          ) : null}
        </div>
      </PageDecisionHero>

      <DataStatusStrip testId="product-category-data-status-strip">
        <ProductCategoryGovernanceStrip
          asOfDateGapText={PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY}
          notices={governanceNotices}
          formalScenarioDistinct={formalScenarioDistinct}
        />
      </DataStatusStrip>

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
          className="product-category-manual-form"
        >
          <div className="product-category-manual-form__title">
            {editingAdjustmentId ? "编辑手工录入" : "手工录入"}
          </div>
          <div className="product-category-manual-form__grid">
            <label className="product-category-manual-form__field">
              报表日期
              <input
                aria-label="手工录入-报表日期"
                value={adjustmentDraft.report_date}
                readOnly
              />
            </label>
            <label className="product-category-manual-form__field">
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
            <label className="product-category-manual-form__field">
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
            <label className="product-category-manual-form__field">
              科目代码
              <input
                aria-label="手工录入-科目代码"
                value={adjustmentDraft.account_code}
                onChange={(event) => updateAdjustmentField("account_code", event.target.value)}
              />
            </label>
            <label className="product-category-manual-form__field">
              科目名称
              <input
                aria-label="手工录入-科目名称"
                value={adjustmentDraft.account_name ?? ""}
                onChange={(event) => updateAdjustmentField("account_name", event.target.value)}
              />
            </label>
            <label className="product-category-manual-form__field">
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
              <label key={field} className="product-category-manual-form__field">
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
              className="product-category-manual-form__error"
            >
              {adjustmentError}
            </div>
          ) : null}
          <div className="product-category-manual-form__actions">
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
          className="product-category-adjustment-history"
        >
          <div className="product-category-adjustment-history__title">当前状态</div>
          {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
            <div
              key={`current-${item.adjustment_id}`}
              className="product-category-adjustment-history__row"
            >
              <div>
                <div className="product-category-adjustment-history__account-code">{item.account_code}</div>
                <div className="product-category-adjustment-history__account-name">
                  {item.account_name || "未填写科目名称"}
                </div>
                <div className="product-category-adjustment-history__event">
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
          <div className="product-category-adjustment-history__audit-summary">
            <div className="product-category-adjustment-history__audit-copy">
              <div className="product-category-adjustment-history__audit-title">完整事件时间线已迁移到独立审计视图</div>
              <div className="product-category-adjustment-history__audit-note">
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
      <div className="product-category-scenario-controls">
        <label className="product-category-scenario-controls__field">
          选择报表月份
          <select
            aria-label="选择报表月份"
            value={selectedDate}
            onChange={(event) => handleReportDateChange(event.target.value)}
            className="product-category-scenario-controls__select"
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {formatProductCategoryReportMonthLabel(reportDate)}
              </option>
            ))}
          </select>
        </label>

        <label className="product-category-scenario-controls__field">
          视图模式
          <div
            role="group"
            aria-label="视图模式"
            className="product-category-scenario-controls__view-group"
          >
            <button
              type="button"
              onClick={() => setSelectedView("monthly")}
              className={
                selectedView === "monthly"
                  ? "product-category-scenario-controls__view-button product-category-scenario-controls__view-button--active"
                  : "product-category-scenario-controls__view-button"
              }
            >
              月度视图
            </button>
            <button
              type="button"
              onClick={() => setSelectedView("ytd")}
              className={
                selectedView === "ytd"
                  ? "product-category-scenario-controls__view-button product-category-scenario-controls__view-button--active"
                  : "product-category-scenario-controls__view-button"
              }
            >
              汇总视图
            </button>
          </div>
        </label>

        <label className="product-category-scenario-controls__field">
          FTP 场景
          <select
            aria-label="FTP 场景"
            value={scenarioRate}
            onChange={(event) => {
              setScenarioRateTouched(true);
              setScenarioRate(event.target.value);
            }}
            className="product-category-scenario-controls__select"
          >
            {PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="product-category-scenario-controls__actions">
        <button
          type="button"
          data-testid="product-category-apply-scenario-button"
          onClick={() => setAppliedScenarioRate(scenarioRate.trim())}
          className="product-category-scenario-controls__apply"
        >
          应用场景
        </button>
      </div>

      <ProductCategoryAttributionPanel
        selectedView={selectedView}
        compare={attributionCompare}
        payload={attributionQuery.data?.result}
        resultMeta={attributionQuery.data?.result_meta}
        isLoading={attributionQuery.isLoading}
        isError={attributionQuery.isError}
        onCompareChange={setAttributionCompare}
        onRetry={() => void attributionQuery.refetch()}
      />

      {!baselineQuery.isError ? (
        <ProductCategoryFinancialAnalysisPanel
          scenarioSensitivity={scenarioSensitivitySurface}
          scenarioExplanation={scenarioExplanation}
          selectedScenarioReviewCategoryId={selectedScenarioExplanationCategoryId}
          scenarioReviewActionStatuses={scenarioReviewActionStatuses}
          scenarioReviewIssueReasons={scenarioReviewIssueReasons}
          scenarioActionClosureStatuses={scenarioActionClosureStatuses}
          scenarioActionClosureMemoCategoryId={scenarioActionClosureMemoCategoryId}
          scenarioSensitivityRequested={scenarioSensitivityRequested}
          scenarioSensitivityLoading={scenarioSensitivityQueries.some((query) => query.isLoading)}
          scenarioSensitivityError={scenarioSensitivityQueries.some((query) => query.isError)}
          onLoadScenarioSensitivity={() => {
            setScenarioSensitivityRequested(true);
            if (scenarioSensitivityRequested) {
              scenarioSensitivityQueries.forEach((query) => void query.refetch());
            }
          }}
          onSelectScenarioReview={setSelectedScenarioReviewCategoryId}
          onBulkScenarioReviewActionStatus={handleBulkScenarioReviewActionStatus}
          onResetScenarioReviewActions={handleResetScenarioReviewActions}
          onSetScenarioReviewActionStatus={handleScenarioReviewActionStatus}
          onSetScenarioReviewIssueReason={handleScenarioReviewIssueReason}
          onSetScenarioActionClosureStatus={handleScenarioActionClosureStatus}
          onSelectScenarioActionClosureMemo={setScenarioActionClosureMemoCategoryId}
          waterfall={attributionWaterfallSurface}
          rootCause={rootCauseSurface}
          decisionFocus={decisionFocusSurface}
        />
      ) : null}

      {!baselineQuery.isError ? (
        <ProductCategoryOperatingAnalysisPanel
          surface={operatingAnalysisSurface}
        />
      ) : null}
      {!baselineQuery.isError ? (
        <ProductCategoryOperatingActionBacktestPanel
          surface={operatingActionBacktestSurface}
          isHistoryLoaded={trendDiagnosticsLoaded}
          historyLoading={
            trendHistoryQueries.some((query) => query.isLoading) ||
            trendHistoryAttributionQueries.some((query) => query.isLoading)
          }
        />
      ) : null}

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
        <div className="product-category-formal-table-wrap">
          <table data-testid="product-category-table" className="product-category-formal-table">
            <colgroup>
              <col className="product-category-formal-table__col--category" />
              <col className="product-category-formal-table__col--scale" />
              <col className="product-category-formal-table__col--scale" />
              <col className="product-category-formal-table__col--scale-foreign" />
              <col className="product-category-formal-table__col--pnl" />
              <col className="product-category-formal-table__col--pnl" />
              <col className="product-category-formal-table__col--pnl-ftp" />
              <col className="product-category-formal-table__col--pnl-net" />
              <col className="product-category-formal-table__col--pnl-foreign" />
              <col className="product-category-formal-table__col--pnl-ftp" />
              <col className="product-category-formal-table__col--pnl-net" />
              <col className="product-category-formal-table__col--business-net" />
              <col className="product-category-formal-table__col--yield" />
            </colgroup>
            <thead>
              <tr className="product-category-formal-table__header-row">
                <th
                  rowSpan={2}
                  className="product-category-formal-table__head product-category-formal-table__head--category"
                >
                  产品类别
                </th>
                <th colSpan={3} className="product-category-formal-table__head product-category-formal-table__head--group">
                  规模日均
                </th>
                <th colSpan={8} className="product-category-formal-table__head product-category-formal-table__head--group">
                  损益
                </th>
                <th
                  rowSpan={2}
                  className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--yield"
                >
                  加权收益率
                </th>
              </tr>
              <tr className="product-category-formal-table__header-row product-category-formal-table__header-row--metrics">
                <th className="product-category-formal-table__head product-category-formal-table__head--number">综本</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">人民币</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">外币</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--group-start">
                  综本
                </th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">人民币</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">人民币FTP</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">人民币减收入</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">外币</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">外币FTP</th>
                <th className="product-category-formal-table__head product-category-formal-table__head--number">外币减收入</th>
                <th
                  className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--highlight"
                >
                  营业减收入
                </th>
              </tr>
            </thead>
            <tbody>
              {rowsToRender.map((row) => (
                <tr
                  key={row.category_id}
                  className={`product-category-formal-table__row ${
                    row.is_total ? "product-category-formal-table__row--total" : ""
                  }`}
                >
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--category">
                    <div style={{ paddingLeft: row.level * 18 }}>
                      <div>{row.category_name}</div>
                    </div>
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                    {formatProductCategoryRowDisplayValue(row, row.cnx_scale)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                    {formatProductCategoryRowDisplayValue(row, row.cny_scale)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                    {formatProductCategoryRowDisplayValue(row, row.foreign_scale)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--group-start">
                    {formatProductCategoryRowDisplayValue(row, row.cnx_cash)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                    {formatProductCategoryRowDisplayValue(row, row.cny_cash)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--ftp">
                    {formatProductCategoryRowDisplayValue(row, row.cny_ftp)}
                  </td>
                  <td
                    className="product-category-formal-table__cell product-category-formal-table__cell--number"
                    style={{ color: toneForProductCategoryValue(row.cny_net) }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.cny_net)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                    {formatProductCategoryRowDisplayValue(row, row.foreign_cash)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--ftp">
                    {formatProductCategoryRowDisplayValue(row, row.foreign_ftp)}
                  </td>
                  <td
                    className="product-category-formal-table__cell product-category-formal-table__cell--number"
                    style={{ color: toneForProductCategoryValue(row.foreign_net) }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.foreign_net)}
                  </td>
                  <td
                    className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--highlight"
                    style={{ color: toneForProductCategoryValue(row.business_net_income) }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.business_net_income)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--yield">
                    {formatProductCategoryYieldValue(row.weighted_yield)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncSection>

      {displayedGrandTotal && !baselineQuery.isError ? (
        <div
          data-testid="product-category-footer-total"
          className="product-category-footer-total"
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
            {!trendDiagnosticsLoaded ? (
              <article
                className="product-category-diagnostics__card product-category-trend-diagnostics-gate"
                data-testid="product-category-trend-diagnostics-gate"
              >
                <div className="product-category-diagnostics__intro">
                  <h3 className="product-category-diagnostics__title">趋势诊断</h3>
                  <p className="product-category-diagnostics__description">
                    首屏先展示当前报表月正式口径；趋势图和两年利差对比需要额外加载历史快照。
                  </p>
                </div>
                <button
                  type="button"
                  className="product-category-trend-diagnostics-gate__button"
                  data-testid="product-category-load-trend-diagnostics"
                  onClick={() => setLoadedTrendDiagnosticsKey(trendDiagnosticsKey)}
                >
                  加载趋势诊断
                </button>
              </article>
            ) : null}
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
            {liabilitySideTrendSurface.detailMatrix.rows.length > 0 ? (
              <>
                <div className="product-category-diagnostics__table-wrap product-category-liability-matrix__wrap">
                  <table
                    className="product-category-diagnostics__table product-category-liability-matrix"
                    data-testid="product-category-liability-side-detail-matrix"
                    aria-label="负债端明细趋势矩阵"
                  >
                    <thead>
                      <tr>
                        <th
                          className="product-category-diagnostics__table-head product-category-liability-matrix__item-head"
                          rowSpan={2}
                          scope="col"
                        >
                          负债明细
                        </th>
                        {liabilitySideTrendSurface.detailMatrix.periods.map((period) => (
                          <th
                            key={period.key}
                            className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                            colSpan={2}
                            scope="colgroup"
                            data-testid={`product-category-liability-side-period-${period.key}`}
                          >
                            {period.label}
                          </th>
                        ))}
                        <th
                          className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                          colSpan={2}
                          scope="colgroup"
                        >
                          {liabilitySideTrendSurface.detailMatrix.movementGroupLabel}
                        </th>
                      </tr>
                      <tr>
                        {liabilitySideTrendSurface.detailMatrix.periods.map((period) => (
                          <Fragment key={period.key}>
                            <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                              日均额
                            </th>
                            <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                              收益率
                            </th>
                          </Fragment>
                        ))}
                        <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                          日均额
                        </th>
                        <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                          收益率
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {liabilitySideTrendSurface.detailMatrix.rows.map((item) => (
                        <tr
                          key={item.categoryId}
                          className={item.isSummary ? "product-category-liability-matrix__summary-row" : undefined}
                          data-testid={`product-category-liability-side-detail-${item.categoryId}`}
                        >
                          <td className="product-category-diagnostics__table-cell product-category-liability-matrix__item-cell">
                            {item.categoryLabel}
                          </td>
                          {item.cells.map((cell) => (
                            <Fragment key={cell.periodKey}>
                              <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                {cell.amountLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                {cell.rateLabel}
                              </td>
                            </Fragment>
                          ))}
                          <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                            {item.movement.amountLabel}
                          </td>
                          <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                            {item.movement.rateLabel}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="product-category-liability-matrix__currency-grid">
                  {liabilitySideTrendSurface.detailMatrix.currencyMatrices.map((currencyMatrix) => (
                    <section
                      key={currencyMatrix.currencyKey}
                      className="product-category-liability-matrix__currency-section"
                    >
                      <h3 className="product-category-liability-matrix__currency-title">
                        {currencyMatrix.currencyLabel}
                      </h3>
                      <div className="product-category-diagnostics__table-wrap product-category-liability-matrix__wrap">
                        <table
                          className="product-category-diagnostics__table product-category-liability-matrix product-category-liability-matrix--currency"
                          data-testid={`product-category-liability-side-currency-matrix-${currencyMatrix.currencyKey}`}
                          aria-label={`${currencyMatrix.currencyLabel}负债结构`}
                        >
                          <thead>
                            <tr>
                              <th
                                className="product-category-diagnostics__table-head product-category-liability-matrix__item-head"
                                rowSpan={2}
                                scope="col"
                              >
                                负债明细
                              </th>
                              {liabilitySideTrendSurface.detailMatrix.periods.map((period) => (
                                <th
                                  key={period.key}
                                  className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                  colSpan={2}
                                  scope="colgroup"
                                >
                                  {period.label}
                                </th>
                              ))}
                              <th
                                className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                colSpan={2}
                                scope="colgroup"
                              >
                                {currencyMatrix.movementGroupLabel}
                              </th>
                            </tr>
                            <tr>
                              {liabilitySideTrendSurface.detailMatrix.periods.map((period) => (
                                <Fragment key={period.key}>
                                  <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                    日均额
                                  </th>
                                  <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                    收益率
                                  </th>
                                </Fragment>
                              ))}
                              <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                日均额
                              </th>
                              <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                收益率
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {currencyMatrix.rows.map((item) => (
                              <tr
                                key={item.categoryId}
                                className={item.isSummary ? "product-category-liability-matrix__summary-row" : undefined}
                                data-testid={`product-category-liability-side-currency-detail-${currencyMatrix.currencyKey}-${item.categoryId}`}
                              >
                                <td className="product-category-diagnostics__table-cell product-category-liability-matrix__item-cell">
                                  {item.categoryLabel}
                                </td>
                                {item.cells.map((cell) => (
                                  <Fragment key={cell.periodKey}>
                                    <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                      {cell.amountLabel}
                                    </td>
                                    <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                      {cell.rateLabel}
                                    </td>
                                  </Fragment>
                                ))}
                                <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                  {item.movement.amountLabel}
                                </td>
                                <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                  {item.movement.rateLabel}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  ))}
                </div>
              </>
            ) : liabilitySideTrendSurface.detailRows.length > 0 ? (
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
            <DerivedChartPanel
              testId="product-category-derived-chart-interest-spread-yoy"
              title="2年生息资产利差变化对比图"
              description="按同月口径对比上年与当年生息资产利差，当前年仅展示已发生月份。"
              option={interestSpreadYearComparisonOption}
              onEvents={{
                click: (params: unknown) =>
                  handleInterestSpreadAttributionPointClick(
                    "weighted",
                    interestSpreadYearComparisonChart?.monthKeys,
                    params as { dataIndex?: number },
                  ),
              }}
            />
            <DerivedChartPanel
              testId="product-category-derived-chart-interest-spread-yoy-cny"
              title="人民币口径2年生息资产利差变化对比图"
              description="按人民币生息资产收益率减人民币负债端成本，对比上年全年与当年已发生月份。"
              option={cnyInterestSpreadYearComparisonOption}
              onEvents={{
                click: (params: unknown) =>
                  handleInterestSpreadAttributionPointClick(
                    "cny",
                    cnyInterestSpreadYearComparisonChart?.monthKeys,
                    params as { dataIndex?: number },
                  ),
              }}
            />
            <DerivedChartPanel
              testId="product-category-derived-chart-intermediate-business-income-yoy"
              title="中间业务收入两年变动对比图"
              description="按同月口径对比上一年全年与当前年已发生月份的中间业务收入，金额单位为亿元。"
              option={intermediateBusinessIncomeYearComparisonOption}
            />
          </div>
          <ProductCategoryInterestSpreadAttributionPanel
            surface={interestSpreadAttributionSurface}
            resultMeta={baselineQuery.data?.result_meta}
          />
        </>
      ) : null}
    </section>
  );
}
