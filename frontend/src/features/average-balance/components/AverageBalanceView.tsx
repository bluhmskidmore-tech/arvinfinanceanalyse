import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Input, Select, Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link, useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { CalibrationBadge } from "../../../components/CalibrationBadge";
import { FilterBar } from "../../../components/FilterBar";
import type {
  AdbCategoryItem,
  AdbComparisonResponse,
  AdbMonthlyBreakdownItem,
  AdbMonthlyDataItem,
  ResultMeta,
} from "../../../api/contracts";
import AdbComparisonChart, { type AdbComparisonChartRow } from "./AdbComparisonChart";
import { computeComparisonDeviationPct } from "./adbComparisonMetrics";
import AdbDailyTrendChart from "./AdbDailyTrendChart";
import AdbDenominatorSummary from "./AdbDenominatorSummary";
import AdbAccountingBasisSection from "./AdbAccountingBasisSection";
import AdbCoverageDiagnostics from "./AdbCoverageDiagnostics";
import AdbKpiStrip, { type AdbKpiStripItem } from "./AdbKpiStrip";
import AdbMonthlyHorizontalChart, {
  type AdbMonthlyHorizontalChartRow,
} from "./AdbMonthlyHorizontalChart";
import AdbMonthlyBreakdownTable from "./AdbMonthlyBreakdownTable";
import AdbNimTrendChart from "./AdbNimTrendChart";
import AdbSectionHead from "./AdbSectionHead";
import { shiftIsoDateByYears } from "./averageBalanceDateUtils";
import { EM_DASH } from "../../../utils/format";

import "./AverageBalanceView.css";

const YI = 100_000_000;

type RangeKey = "7d" | "30d" | "ytd" | "custom";
type PageTab = "daily" | "monthly";
type BreakdownKind = "asset" | "liability";
type MonthlyBarRow = AdbMonthlyHorizontalChartRow;
type MonthlyMatrixValueKind = "amount" | "pct";
type MonthlyMatrixRow = {
  rowKey: string;
  label: string;
  valueKind: MonthlyMatrixValueKind;
  values: Record<string, number | null | undefined>;
};

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${(value / YI).toFixed(2)} 亿元`;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toFixed(2)}%`;
}

function formatRatioPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${(value * 100).toFixed(1)}%`;
}

function isIncompleteRateCoverage(value: number | null | undefined): boolean {
  return value !== null && value !== undefined && Number.isFinite(value) && value < 0.9999;
}

function buildRateCoverageWarning(data: AdbComparisonResponse | null | undefined): string | null {
  if (!data) return null;
  const warnings = [
    isIncompleteRateCoverage(data.asset_rate_coverage_ratio)
      ? `资产利率覆盖 ${formatRatioPercent(data.asset_rate_coverage_ratio)}`
      : null,
    isIncompleteRateCoverage(data.liability_rate_coverage_ratio)
      ? `负债利率覆盖 ${formatRatioPercent(data.liability_rate_coverage_ratio)}`
      : null,
  ].filter(Boolean);
  if (warnings.length === 0) return null;
  return `加权利率覆盖不足：${warnings.join("，")}。收益率/付息率仅按有利率余额加权，缺失余额已从分母剔除。`;
}

const ADB_SNAPSHOT_FALLBACK_WARNING =
  "部分日期由快照补数（原币、未经 FX 中间价转换），非正式口径。";

function shouldShowSnapshotFallbackWarning(
  adbDenominatorBasis: string | null | undefined,
  meta: ResultMeta | undefined,
): boolean {
  if (adbDenominatorBasis?.includes("snapshot")) return true;
  return meta?.fallback_mode === "latest_snapshot";
}

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function toDateInput(date: Date): string {
  return [
    date.getFullYear(),
    `${date.getMonth() + 1}`.padStart(2, "0"),
    `${date.getDate()}`.padStart(2, "0"),
  ].join("-");
}

function buildPresetRange(reportDate: string, rangeKey: Exclude<RangeKey, "custom">) {
  if (!reportDate) return null;
  const end = new Date(`${reportDate}T12:00:00`);
  if (Number.isNaN(end.getTime())) return null;
  const start = new Date(end);
  if (rangeKey === "7d") start.setDate(start.getDate() - 6);
  if (rangeKey === "30d") start.setDate(start.getDate() - 29);
  if (rangeKey === "ytd") start.setMonth(0, 1);
  return { startDate: toDateInput(start), endDate: toDateInput(end) };
}

type AdbYoYAmountRow = {
  key: string;
  label: string;
  current: number | null;
  prior: number | null;
};

function computeYoyPct(current: number | null, prior: number | null): number | null {
  if (
    current === null ||
    prior === null ||
    !Number.isFinite(current) ||
    !Number.isFinite(prior) ||
    prior === 0
  ) return null;
  return ((current - prior) / prior) * 100;
}

function buildCategoryYoyRows(
  side: "asset" | "liability",
  current: AdbCategoryItem[],
  prior: AdbCategoryItem[] | undefined,
): AdbYoYAmountRow[] {
  const priorMap = new Map((prior ?? []).map((r) => [r.category, r]));
  return current.map((item) => ({
    key: `${side}-${item.category}`,
    label: `${side === "asset" ? "资产" : "负债"} · ${item.category}`,
    current: item.avg_balance,
    prior: priorMap.get(item.category)?.avg_balance ?? null,
  }));
}

function buildAdbYoYAdbScaleRows(
  dailyData: AdbComparisonResponse,
  priorData: AdbComparisonResponse,
): AdbYoYAmountRow[] {
  return [
    {
      key: "avg-assets",
      label: "区间日均总资产",
      current: dailyData.total_avg_assets,
      prior: priorData.total_avg_assets,
    },
    {
      key: "avg-liabilities",
      label: "区间日均总负债",
      current: dailyData.total_avg_liabilities,
      prior: priorData.total_avg_liabilities,
    },
  ];
}

function formatSignedYiBillions(deltaYuan: number): string {
  if (!Number.isFinite(deltaYuan)) return EM_DASH;
  const yi = deltaYuan / YI;
  const sign = yi > 0 ? "+" : "";
  return `${sign}${yi.toFixed(2)}`;
}

function formatYoyPriorYi(value: number | null): string {
  return value === null ? "缺去年同期" : (value / YI).toFixed(2);
}

function formatYoyDeltaYi(current: number | null, prior: number | null): string {
  return current === null || prior === null ? EM_DASH : formatSignedYiBillions(current - prior);
}

function buildYoYAmountColumns(): ColumnsType<AdbYoYAmountRow> {
  return [
    { title: "项目", dataIndex: "label", key: "label", ellipsis: true },
    {
      title: "本期（亿元）",
      key: "cur",
      align: "right",
      render: (_: unknown, row: AdbYoYAmountRow) =>
        row.current === null ? EM_DASH : (row.current / YI).toFixed(2),
    },
    {
      title: "去年同期（亿元）",
      key: "pri",
      align: "right",
      render: (_: unknown, row: AdbYoYAmountRow) => formatYoyPriorYi(row.prior),
    },
    {
      title: "增减（亿元）",
      key: "delta",
      align: "right",
      render: (_: unknown, row: AdbYoYAmountRow) => formatYoyDeltaYi(row.current, row.prior),
    },
    {
      title: "同比（%）",
      key: "yoy",
      align: "right",
      render: (_: unknown, row: AdbYoYAmountRow) => formatSignedPct(computeYoyPct(row.current, row.prior)),
    },
  ];
}

function buildDetailColumns(kind: BreakdownKind): ColumnsType<AdbCategoryItem> {
  return [
    { title: "分类", dataIndex: "category", key: "category" },
    { title: "期末时点（亿元）", dataIndex: "spot_balance", key: "spot_balance", align: "right", render: (value: number | null) => (value === null ? EM_DASH : (value / YI).toFixed(2)) },
    { title: "日均(亿元)", dataIndex: "avg_balance", key: "avg_balance", align: "right", render: (value: number | null) => (value === null ? EM_DASH : (value / YI).toFixed(2)) },
    { title: "占比(%)", dataIndex: "proportion", key: "proportion", align: "right", render: (value: number | null) => (value === null ? EM_DASH : value.toFixed(2)) },
    { title: kind === "asset" ? "收益率(%)" : "付息率(%)", dataIndex: "weighted_rate", key: "weighted_rate", align: "right", render: (value: number | null | undefined) => formatPct(value) },
    { title: "利率覆盖(%)", dataIndex: "rate_coverage_ratio", key: "rate_coverage_ratio", align: "right", render: (value: number | null | undefined) => formatRatioPercent(value) },
  ];
}

function buildMonthlyBreakdownColumns(kind: BreakdownKind): ColumnsType<AdbMonthlyBreakdownItem> {
  return [
    { title: "分类", dataIndex: "category", key: "category" },
    { title: "日均(亿元)", dataIndex: "avg_balance", key: "avg_balance", align: "right", render: (value: number | null) => formatMatrixValue(value, "amount") },
    { title: "占比(%)", dataIndex: "proportion", key: "proportion", align: "right", render: (value: number | null | undefined) => (value === null || value === undefined ? EM_DASH : value.toFixed(2)) },
    { title: kind === "asset" ? "收益率(%)" : "付息率(%)", dataIndex: "weighted_rate", key: "weighted_rate", align: "right", render: (value: number | null | undefined) => formatPct(value) },
    { title: "利率覆盖(%)", dataIndex: "rate_coverage_ratio", key: "rate_coverage_ratio", align: "right", render: (value: number | null | undefined) => formatRatioPercent(value) },
  ];
}

function hasFiniteAvgBalance(row: AdbMonthlyBreakdownItem): row is AdbMonthlyBreakdownItem & { avg_balance: number } {
  return row.avg_balance !== null && row.avg_balance !== undefined && Number.isFinite(row.avg_balance);
}

function buildMonthlyRows(breakdown: AdbMonthlyBreakdownItem[]): MonthlyBarRow[] {
  return breakdown
    .slice()
    .filter(hasFiniteAvgBalance)
    .sort((left, right) => right.avg_balance - left.avg_balance)
    .slice(0, 10)
    .map((row) => ({ category: row.category, avgYi: row.avg_balance / YI, weightedRate: row.weighted_rate ?? null }));
}

function sortMonthsAscending(months: AdbMonthlyDataItem[]): AdbMonthlyDataItem[] {
  return months.slice().sort((left, right) => left.month.localeCompare(right.month));
}

function formatMatrixValue(
  value: number | null | undefined,
  valueKind: MonthlyMatrixValueKind,
  signed = false,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const sign = signed && value > 0 ? "+" : "";
  if (valueKind === "pct") {
    return `${sign}${value.toFixed(2)}${signed ? "pp" : "%"}`;
  }
  return `${sign}${(value / YI).toFixed(2)}`;
}

function getMatrixDelta(row: MonthlyMatrixRow, months: AdbMonthlyDataItem[], baseIndex: number) {
  const latest = months[months.length - 1];
  const base = months[baseIndex];
  if (!latest || !base) return null;
  const latestValue = row.values[latest.month];
  const baseValue = row.values[base.month];
  if (
    latestValue === null ||
    latestValue === undefined ||
    baseValue === null ||
    baseValue === undefined
  ) {
    return null;
  }
  return latestValue - baseValue;
}

function buildMonthlyMatrixColumns(
  months: AdbMonthlyDataItem[],
  firstColumnTitle: "分类" | "项目",
): ColumnsType<MonthlyMatrixRow> {
  return [
    {
      title: firstColumnTitle,
      dataIndex: "label",
      key: "label",
      fixed: "left",
      width: 180,
    },
    ...months.map((month) => ({
      title: month.month_label,
      key: month.month,
      align: "right" as const,
      width: 120,
      render: (_: unknown, row: MonthlyMatrixRow) =>
        formatMatrixValue(row.values[month.month], row.valueKind),
    })),
    {
      title: "比上月",
      key: "compare-previous",
      align: "right" as const,
      width: 110,
      render: (_: unknown, row: MonthlyMatrixRow) =>
        formatMatrixValue(getMatrixDelta(row, months, months.length - 2), row.valueKind, true),
    },
    {
      title: "比年初",
      key: "compare-year-start",
      align: "right" as const,
      width: 110,
      render: (_: unknown, row: MonthlyMatrixRow) =>
        formatMatrixValue(getMatrixDelta(row, months, 0), row.valueKind, true),
    },
  ];
}

function buildMonthlyCategoryMatrixRows(months: AdbMonthlyDataItem[]): MonthlyMatrixRow[] {
  const rows = new Map<string, MonthlyMatrixRow>();
  const ensureRow = (rowKey: string, label: string) => {
    const existing = rows.get(rowKey);
    if (existing) return existing;
    const row: MonthlyMatrixRow = { rowKey, label, valueKind: "amount", values: {} };
    rows.set(rowKey, row);
    return row;
  };

  for (const month of months) {
    for (const item of month.breakdown_assets) {
      ensureRow(`asset-${item.category}`, `资产：${item.category}`).values[month.month] =
        item.avg_balance;
    }
    for (const item of month.breakdown_liabilities) {
      ensureRow(`liability-${item.category}`, `负债：${item.category}`).values[month.month] =
        item.avg_balance;
    }
  }

  const latest = months[months.length - 1];
  return Array.from(rows.values()).sort((left, right) => {
    const leftValue = latest ? (left.values[latest.month] ?? Number.NEGATIVE_INFINITY) : Number.NEGATIVE_INFINITY;
    const rightValue = latest ? (right.values[latest.month] ?? Number.NEGATIVE_INFINITY) : Number.NEGATIVE_INFINITY;
    return rightValue - leftValue;
  });
}

function buildMonthlyProjectMatrixRows(months: AdbMonthlyDataItem[]): MonthlyMatrixRow[] {
  const rows: MonthlyMatrixRow[] = [
    { rowKey: "avg-assets", label: "日均资产", valueKind: "amount", values: {} },
    { rowKey: "avg-liabilities", label: "日均负债", valueKind: "amount", values: {} },
    { rowKey: "asset-yield", label: "加权YTM", valueKind: "pct", values: {} },
    { rowKey: "liability-cost", label: "加权票息", valueKind: "pct", values: {} },
    { rowKey: "nim", label: "利差", valueKind: "pct", values: {} },
  ];
  for (const month of months) {
    rows[0].values[month.month] = month.avg_assets;
    rows[1].values[month.month] = month.avg_liabilities;
    rows[2].values[month.month] = month.asset_yield;
    rows[3].values[month.month] = month.liability_cost;
    rows[4].values[month.month] = month.net_interest_margin;
  }
  return rows;
}

function resolvePopupContainer(trigger: HTMLElement): HTMLElement {
  return trigger.parentElement ?? document.body;
}

/**
 * 结果元信息（证据卡语言：muted 标签列 + ink 值列，视觉降权、字段逐字保留）。
 * 标签内嵌分隔符（=／：／不换行空格），保证 textContent 与既有断言逐字一致。
 */
function ResultMetaNotice(props: {
  meta?: ResultMeta;
  testId: string;
}) {
  if (!props.meta) return null;
  const hasQualityIssue =
    props.meta.quality_flag !== "ok" || props.meta.fallback_mode !== "none";
  const qualityLabel =
    props.meta.quality_flag === "ok"
      ? "正常"
      : props.meta.quality_flag === "warning"
        ? "预警"
        : props.meta.quality_flag === "error"
          ? "错误"
          : props.meta.quality_flag === "stale"
            ? "陈旧"
            : props.meta.quality_flag;
  const fallbackLabel =
    props.meta.fallback_mode === "none"
      ? "未降级"
      : props.meta.fallback_mode === "latest_snapshot"
        ? "最新快照降级"
        : props.meta.fallback_mode;
  return (
    <div
      className="adb-evidence"
      data-testid={props.testId}
      data-tone={hasQualityIssue ? "warn" : "info"}
    >
      <span className="adb-evidence-title">
        候选指标 · 正式可用: {props.meta.formal_use_allowed ? "是" : "否"}
      </span>
      <div className="adb-evidence-grid">
        <span className="adb-evidence-line">PAGE-CONTRACT-PENDING:/average-balance</span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">日均余额后端链路：</span>
          <span className="adb-evidence-v">{props.meta.result_kind}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">{"口径\u00A0"}</span>
          <span className="adb-evidence-v">{props.meta.basis}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">来源=</span>
          <span className="adb-evidence-v">{props.meta.source_version}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">规则=</span>
          <span className="adb-evidence-v">{props.meta.rule_version}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">质量=</span>
          <span className="adb-evidence-v">{qualityLabel}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">降级=</span>
          <span className="adb-evidence-v">{fallbackLabel}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">{"日期基准\u00A0"}</span>
          <span className="adb-evidence-v">{props.meta.date_basis ?? EM_DASH}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">{"使用表\u00A0"}</span>
          <span className="adb-evidence-v">{props.meta.tables_used?.join(", ") || EM_DASH}</span>
        </span>
        <span className="adb-evidence-row">
          <span className="adb-evidence-k">{"证据行\u00A0"}</span>
          <span className="adb-evidence-v">{props.meta.evidence_rows ?? EM_DASH}</span>
        </span>
      </div>
    </div>
  );
}

export default function AverageBalanceView() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [activeTab, setActiveTab] = useState<PageTab>("daily");
  const [rangeKey, setRangeKey] = useState<RangeKey>("ytd");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState("");
  const [adbTopN, setAdbTopN] = useState(20);

  const datesQuery = useQuery({
    queryKey: ["average-balance", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const dateOptions = useMemo(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (explicitReportDate && !dates.includes(explicitReportDate)) return [explicitReportDate, ...dates];
    return dates;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const reportDate = useMemo(() => {
    if (explicitReportDate) return explicitReportDate;
    return selectedReportDate || datesQuery.data?.result.report_dates[0] || "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate, selectedReportDate]);

  const formalAnalysisHref = useMemo(() => {
    const params = new URLSearchParams();
    if (reportDate) params.set("report_date", reportDate);
    params.set("position_scope", "all");
    params.set("currency_basis", "CNY");
    return `/balance-analysis?${params.toString()}`;
  }, [reportDate]);

  useEffect(() => {
    if (rangeKey === "custom") return;
    const range = buildPresetRange(reportDate, rangeKey);
    if (!range) return;
    setStartDate(range.startDate);
    setEndDate(range.endDate);
  }, [rangeKey, reportDate]);

  useEffect(() => {
    const year = Number(reportDate.slice(0, 4));
    if (Number.isFinite(year) && year > 0) setSelectedYear(year);
  }, [reportDate]);

  const comparisonQuery = useQuery({
    queryKey: ["average-balance", "comparison", client.mode, startDate, endDate, adbTopN],
    queryFn: () => client.getAdbComparison(startDate, endDate, { topN: adbTopN }),
    enabled: activeTab === "daily" && Boolean(startDate && endDate),
    retry: false,
  });

  const trendQuery = useQuery({
    queryKey: ["average-balance", "trend", client.mode, startDate, endDate],
    queryFn: () => client.getAdb({ startDate, endDate }),
    enabled: activeTab === "daily" && Boolean(startDate && endDate && comparisonQuery.data),
    retry: false,
  });

  const priorYearRange = useMemo(() => {
    if (!startDate || !endDate) return null;
    return {
      startDate: shiftIsoDateByYears(startDate, -1),
      endDate: shiftIsoDateByYears(endDate, -1),
    };
  }, [startDate, endDate]);

  const priorYearComparisonQuery = useQuery({
    queryKey: [
      "average-balance",
      "comparison-prior-year",
      client.mode,
      priorYearRange?.startDate ?? "",
      priorYearRange?.endDate ?? "",
      adbTopN,
    ],
    queryFn: () =>
      client.getAdbComparison(priorYearRange!.startDate, priorYearRange!.endDate, {
        topN: adbTopN,
      }),
    enabled:
      activeTab === "daily" &&
      Boolean(comparisonQuery.data && priorYearRange?.startDate && priorYearRange?.endDate),
    retry: false,
  });

  const lowCoverageWarning = useMemo(() => {
    const d = comparisonQuery.data;
    if (!d) return false;
    if (d.num_days <= 1) return false;
    const cov = d.coverage_days;
    if (cov === undefined || cov === null) return false;
    return cov < d.num_days * 0.5;
  }, [comparisonQuery.data]);
  const rateCoverageWarning = useMemo(
    () => buildRateCoverageWarning(comparisonQuery.data),
    [comparisonQuery.data],
  );

  const coverageQuery = useQuery({
    queryKey: ["average-balance", "adb-coverage", client.mode, startDate, endDate],
    queryFn: () => client.getAdbCoverage(startDate, endDate),
    enabled: activeTab === "daily" && Boolean(startDate && endDate) && lowCoverageWarning,
    retry: false,
  });

  const monthlyQuery = useQuery({
    queryKey: ["average-balance", "monthly", client.mode, selectedYear],
    queryFn: () => client.getAdbMonthly(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  useEffect(() => {
    const months = monthlyQuery.data?.months ?? [];
    if (!months.length) {
      setSelectedMonth("");
      return;
    }
    if (!selectedMonth || !months.some((item) => item.month === selectedMonth)) {
      setSelectedMonth(months[0].month);
    }
  }, [monthlyQuery.data?.months, selectedMonth]);

  const dailyData = comparisonQuery.data;
  const dailyBootstrapBlocked = !explicitReportDate && datesQuery.isError;
  const canRunDailyQuery = Boolean(startDate && endDate) && !dailyBootstrapBlocked;
  const assetDeviationPct =
    dailyData && dailyData.total_avg_assets > 0
      ? ((dailyData.total_spot_assets - dailyData.total_avg_assets) / dailyData.total_avg_assets) * 100
      : 0;
  const liabilityDeviationPct =
    dailyData && dailyData.total_avg_liabilities > 0
      ? ((dailyData.total_spot_liabilities - dailyData.total_avg_liabilities) / dailyData.total_avg_liabilities) * 100
      : 0;

  const { comparisonAssetRows, comparisonLiabilityRows } = useMemo(() => {
    if (!dailyData) {
      return { comparisonAssetRows: [] as AdbComparisonChartRow[], comparisonLiabilityRows: [] as AdbComparisonChartRow[] };
    }
    const mapRows = (items: AdbCategoryItem[], prefix: string): AdbComparisonChartRow[] =>
      items.map((item) => ({
        label: `${prefix} · ${item.category}`,
        spot: item.spot_balance,
        avg: item.avg_balance,
        deviationPct: computeComparisonDeviationPct(item.spot_balance, item.avg_balance),
      }));
    return {
      comparisonAssetRows: mapRows(dailyData.assets_breakdown, "资产"),
      comparisonLiabilityRows: mapRows(dailyData.liabilities_breakdown, "负债"),
    };
  }, [dailyData]);

  const monthlyData = monthlyQuery.data;
  const selectedMonthData = monthlyData?.months.find((item) => item.month === selectedMonth) ?? null;
  const monthlyAssetRows = useMemo(() => buildMonthlyRows(selectedMonthData?.breakdown_assets ?? []), [selectedMonthData?.breakdown_assets]);
  const monthlyLiabilityRows = useMemo(() => buildMonthlyRows(selectedMonthData?.breakdown_liabilities ?? []), [selectedMonthData?.breakdown_liabilities]);
  const monthlyMatrixMonths = useMemo(
    () => sortMonthsAscending(monthlyData?.months ?? []),
    [monthlyData?.months],
  );
  const monthlyCategoryMatrixRows = useMemo(
    () => buildMonthlyCategoryMatrixRows(monthlyMatrixMonths),
    [monthlyMatrixMonths],
  );
  const monthlyProjectMatrixRows = useMemo(
    () => buildMonthlyProjectMatrixRows(monthlyMatrixMonths),
    [monthlyMatrixMonths],
  );
  const monthlyCategoryMatrixColumns = useMemo(
    () => buildMonthlyMatrixColumns(monthlyMatrixMonths, "分类"),
    [monthlyMatrixMonths],
  );
  const monthlyProjectMatrixColumns = useMemo(
    () => buildMonthlyMatrixColumns(monthlyMatrixMonths, "项目"),
    [monthlyMatrixMonths],
  );
  const yoyAdbRows = useMemo(() => {
    const prior = priorYearComparisonQuery.data;
    if (!dailyData || !prior) return [];
    return buildAdbYoYAdbScaleRows(dailyData, prior);
  }, [dailyData, priorYearComparisonQuery.data]);
  const yoyAssetCategoryRows = useMemo(
    () =>
      buildCategoryYoyRows(
        "asset",
        dailyData?.assets_breakdown ?? [],
        priorYearComparisonQuery.data?.assets_breakdown,
      ),
    [dailyData?.assets_breakdown, priorYearComparisonQuery.data?.assets_breakdown],
  );
  const yoyLiabilityCategoryRows = useMemo(
    () =>
      buildCategoryYoyRows(
        "liability",
        dailyData?.liabilities_breakdown ?? [],
        priorYearComparisonQuery.data?.liabilities_breakdown,
      ),
    [dailyData?.liabilities_breakdown, priorYearComparisonQuery.data?.liabilities_breakdown],
  );
  const yoyAmountColumns = useMemo(() => buildYoYAmountColumns(), []);

  const dailyAssetColumns = useMemo(() => buildDetailColumns("asset"), []);
  const dailyLiabilityColumns = useMemo(() => buildDetailColumns("liability"), []);
  const monthlyAssetColumns = useMemo(() => buildMonthlyBreakdownColumns("asset"), []);
  const monthlyLiabilityColumns = useMemo(() => buildMonthlyBreakdownColumns("liability"), []);

  const monthlyTableColumns: ColumnsType<AdbMonthlyDataItem> = useMemo(
    () => [
      { title: "月份", dataIndex: "month_label", key: "month_label", render: (value: string) => <span className="adb-cell-strong">{value}</span> },
      { title: "天数", dataIndex: "num_days", key: "num_days", align: "right" },
      { title: "日均资产(亿元)", dataIndex: "avg_assets", key: "avg_assets", align: "right", render: (value: number | null) => formatMatrixValue(value, "amount") },
      { title: "日均负债(亿元)", dataIndex: "avg_liabilities", key: "avg_liabilities", align: "right", render: (value: number | null) => formatMatrixValue(value, "amount") },
      { title: "加权YTM", dataIndex: "asset_yield", key: "asset_yield", align: "right", render: (value: number | null) => formatPct(value) },
      { title: "加权票息", dataIndex: "liability_cost", key: "liability_cost", align: "right", render: (value: number | null) => formatPct(value) },
      {
        title: "利差",
        dataIndex: "net_interest_margin",
        key: "net_interest_margin",
        align: "right",
        render: (value: number | null) => (
          <span className={value !== null && value < 0 ? "adb-tone--down" : undefined}>{formatPct(value)}</span>
        ),
      },
      {
        title: "资产环比",
        dataIndex: "mom_change_pct_assets",
        key: "mom_change_pct_assets",
        align: "right",
        render: (_value: number | null, row: AdbMonthlyDataItem) => (
          <span className="adb-cell-stack">
            <span>{formatSignedPct(row.mom_change_pct_assets ?? row.mom_change_assets)}</span>
            {row.mom_change_assets != null ? (
              <span className="adb-data-subline">
                额 {formatSignedYiBillions(row.mom_change_assets)} 亿元
              </span>
            ) : null}
          </span>
        ),
      },
      {
        title: "负债环比",
        dataIndex: "mom_change_pct_liabilities",
        key: "mom_change_pct_liabilities",
        align: "right",
        render: (_value: number | null, row: AdbMonthlyDataItem) => (
          <span className="adb-cell-stack">
            <span>{formatSignedPct(row.mom_change_pct_liabilities ?? row.mom_change_liabilities)}</span>
            {row.mom_change_liabilities != null ? (
              <span className="adb-data-subline">
                额 {formatSignedYiBillions(row.mom_change_liabilities)} 亿元
              </span>
            ) : null}
          </span>
        ),
      },
    ],
    [],
  );

  const yearOptions = useMemo(() => {
    const reportYear = Number(reportDate.slice(0, 4));
    const currentYear = new Date().getFullYear();
    return Array.from(new Set([currentYear - 2, currentYear - 1, currentYear, reportYear].filter((item) => Number.isFinite(item) && item > 0)))
      .sort((left, right) => right - left)
      .map((item) => ({ label: `${item}`, value: item }));
  }, [reportDate]);

  const applyPreset = (nextKey: Exclude<RangeKey, "custom">) => {
    setRangeKey(nextKey);
    const range = buildPresetRange(reportDate, nextKey);
    if (!range) return;
    setStartDate(range.startDate);
    setEndDate(range.endDate);
  };

  const onCustomRangeChange = (field: "start" | "end", value: string) => {
    setRangeKey("custom");
    if (field === "start") {
      setStartDate(value);
      return;
    }
    setEndDate(value);
  };

  const deviationWarning =
    assetDeviationPct > 5 || liabilityDeviationPct > 5
      ? "偏离度 > 5%，存在“窗口粉饰”风险，请结合实际头寸变化核查。"
      : null;
  const dailyErrorMessage = dailyBootstrapBlocked
    ? "可用报告日加载失败，请先恢复报告日列表后再查看日均分析。"
    : datesQuery.isError
      ? "可用报告日加载失败"
      : comparisonQuery.isError
        ? "日均分析加载失败"
        : null;

  /* 以下均为展示层派生（不改数值来源）：KPI 横带条目与 01 区警示可见性。 */
  const dailyScaleKpis: AdbKpiStripItem[] = dailyData
    ? [
        { key: "spot-assets", label: "期末时点总资产", value: formatYi(dailyData.total_spot_assets) },
        { key: "avg-assets", label: "日均总资产", value: formatYi(dailyData.total_avg_assets) },
        {
          key: "deviation-assets",
          label: "偏离度（资产）",
          value: formatSignedPct(assetDeviationPct),
          tone: assetDeviationPct > 5 ? "down" : undefined,
          warn: assetDeviationPct > 5,
        },
        { key: "spot-liabilities", label: "期末时点总负债", value: formatYi(dailyData.total_spot_liabilities) },
        { key: "avg-liabilities", label: "日均总负债", value: formatYi(dailyData.total_avg_liabilities) },
        {
          key: "deviation-liabilities",
          label: "偏离度（负债）",
          value: formatSignedPct(liabilityDeviationPct),
          tone: liabilityDeviationPct > 5 ? "down" : undefined,
          warn: liabilityDeviationPct > 5,
        },
      ]
    : [];
  const dailyRateKpis: AdbKpiStripItem[] = dailyData
    ? [
        { key: "asset-yield", label: "资产加权平均YTM", value: formatPct(dailyData.asset_yield) },
        { key: "liability-cost", label: "负债加权平均票息", value: formatPct(dailyData.liability_cost) },
        {
          key: "nim",
          label: "利差（YTM−票息）",
          value: formatPct(dailyData.net_interest_margin),
          tone:
            dailyData.net_interest_margin !== null && dailyData.net_interest_margin < 0
              ? "down"
              : undefined,
        },
        {
          key: "interbank-assets",
          label: "同业日均资产",
          value: formatYi(dailyData.total_avg_interbank_assets),
          detail: "TYW 正式余额（区间日均）",
        },
        {
          key: "interbank-liabilities",
          label: "同业日均负债",
          value: formatYi(dailyData.total_avg_interbank_liabilities),
          detail: "TYW 正式余额（区间日均）",
        },
      ]
    : [];
  const monthlyKpis: AdbKpiStripItem[] = monthlyData
    ? [
        { key: "ytd-avg-assets", label: "年初至今日均资产", value: formatYi(monthlyData.ytd_avg_assets) },
        { key: "ytd-avg-liabilities", label: "年初至今日均负债", value: formatYi(monthlyData.ytd_avg_liabilities) },
        { key: "ytd-asset-yield", label: "年初至今加权YTM", value: formatPct(monthlyData.ytd_asset_yield) },
        { key: "ytd-liability-cost", label: "年初至今加权票息", value: formatPct(monthlyData.ytd_liability_cost) },
        { key: "ytd-nim", label: "年初至今利差", value: formatPct(monthlyData.ytd_nim) },
      ]
    : [];

  const dailyLowCoverageVisible =
    dailyData != null &&
    dailyData.coverage_days != null &&
    dailyData.num_days > 1 &&
    dailyData.coverage_days < dailyData.num_days * 0.5;
  const dailySnapshotFallbackVisible =
    dailyData != null &&
    shouldShowSnapshotFallbackWarning(dailyData.adb_denominator_basis, dailyData.result_meta);
  const hasDailyNotices = Boolean(
    dailyData?.simulated ||
      dailyLowCoverageVisible ||
      dailySnapshotFallbackVisible ||
      deviationWarning ||
      rateCoverageWarning,
  );
  const dailyHasAccountingBasis = Boolean(
    dailyData &&
      (dailyData.accounting_basis_daily_avg ||
        (dailyData.accounting_basis_daily_avg_trend &&
          dailyData.accounting_basis_daily_avg_trend.length > 0)),
  );
  const monthlySnapshotFallbackVisible =
    monthlyData != null && shouldShowSnapshotFallbackWarning(undefined, monthlyData.result_meta);
  const monthlyHasAccountingBasis = Boolean(
    monthlyData?.accounting_basis_daily_avg_trend &&
      monthlyData.accounting_basis_daily_avg_trend.length > 0,
  );

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 独占；
   * 页根只声明换肤 scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <section
      data-testid="average-balance-page"
      data-moss-theme-scope="average-balance"
      className="average-balance-page theme-dh-api"
    >
      {/* 工具条（首页 dhTopbar 语言：无卡 + 发丝底边；左标题与口径 meta，右模式胶囊） */}
      <header className="adb-topbar">
        <div className="adb-topbar-left">
          <div className="adb-title-row">
            <h2 data-testid="average-balance-page-title" className="adb-page-title">
              日均分析
            </h2>
            <CalibrationBadge calibration={comparisonQuery.data?.calibration} />
          </div>
          <div className="adb-topbar-meta">
            <span data-testid="average-balance-page-subtitle" className="adb-page-subtitle">
              期末是否偏离日均、偏离由资产/负债哪类驱动，以及月度日均结构和 NIM
              是否变化。页面只消费后端返回结果，不在前端补算正式金融口径。
            </span>
            <span className="adb-scope-note">当前页面为资产负债分析的分析口径子视图。</span>
            <Link className="adb-formal-link" to={formalAnalysisHref}>
              打开正式资产负债分析
            </Link>
          </div>
        </div>
        <span className="adb-pill" data-tone={client.mode === "real" ? "ok" : "accent"}>
          <i aria-hidden="true" />
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </header>

      <p className="adb-analysis-brief" data-testid="average-balance-analysis-brief">
        <span className="adb-brief-label">日均分析回答什么</span>
        <span className="adb-brief-text">
          期末是否偏离日均，偏离由资产/负债哪类驱动，以及月度日均结构和 NIM 是否变化。
        </span>
      </p>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as PageTab)}
        destroyOnHidden
        items={[
          {
            key: "daily",
            label: "日均分析",
            children: (
              <div className="adb-stack">
                <div className="adb-tab-lead">
                  <h3>区间日均分析</h3>
                  <p>
                    先选择报告日和观察区间，再阅读期末时点与日均偏离、收益成本和分类明细；这里保持分析口径视图，不提升为正式口径。
                  </p>
                </div>

                <div className="adb-controls">
                  <FilterBar>
                    <span className="adb-control-label">报告日</span>
                    <Select
                      aria-label="adb-report-date"
                      className="adb-filter-date"
                      value={reportDate || undefined}
                      options={dateOptions.map((item) => ({ label: item, value: item }))}
                      onChange={setSelectedReportDate}
                      disabled={Boolean(explicitReportDate)}
                      placeholder="选择日期"
                      getPopupContainer={resolvePopupContainer}
                    />
                    <Button type={rangeKey === "7d" ? "primary" : "default"} onClick={() => applyPreset("7d")}>7日</Button>
                    <Button type={rangeKey === "30d" ? "primary" : "default"} onClick={() => applyPreset("30d")}>30日</Button>
                    <Button type={rangeKey === "ytd" ? "primary" : "default"} onClick={() => applyPreset("ytd")}>年初至今</Button>
                    <Input aria-label="adb-start-date" type="date" value={startDate} onChange={(event) => onCustomRangeChange("start", event.target.value)} className="adb-filter-input" />
                    <Input aria-label="adb-end-date" type="date" value={endDate} onChange={(event) => onCustomRangeChange("end", event.target.value)} className="adb-filter-input" />
                    <span className="adb-control-label">明细条数</span>
                    <Select
                      aria-label="adb-top-n"
                      data-testid="adb-top-n-select"
                      className="adb-filter-top-n"
                      value={adbTopN}
                      options={[20, 50, 100, 200].map((n) => ({ label: String(n), value: n }))}
                      onChange={(v) => setAdbTopN(v)}
                      getPopupContainer={resolvePopupContainer}
                    />
                  </FilterBar>
                  <div className="adb-days-box">
                    <span className="adb-days">区间天数：{dailyData?.num_days ?? EM_DASH} 天</span>
                    {dailyData?.coverage_days != null && dailyData.coverage_days !== dailyData.num_days ? (
                      <span className="adb-days-note">（实际有数据 {dailyData.coverage_days} 天）</span>
                    ) : null}
                  </div>
                </div>

                {datesQuery.isLoading || comparisonQuery.isLoading ? (
                  <div className="adb-skeleton" aria-busy="true">
                    <span>数据读取中…</span>
                  </div>
                ) : null}
                {dailyErrorMessage ? <Alert type="error" showIcon message={dailyErrorMessage} /> : null}
                {!datesQuery.isLoading &&
                !datesQuery.isError &&
                !explicitReportDate &&
                dateOptions.length === 0 ? (
                  <Alert type="warning" showIcon message="暂无可用报告日，暂无法展示日均分析。" />
                ) : null}

                {canRunDailyQuery && dailyData ? (
                  <>
                    <AdbKpiStrip columns={6} items={dailyScaleKpis} />
                    <AdbKpiStrip columns={5} items={dailyRateKpis} />

                    <section className="adb-sec">
                      <AdbSectionHead title="区间结论与警示" />
                      {hasDailyNotices ? (
                        <div className="adb-alert-stack">
                          {dailyData.simulated ? (
                            <Alert type="info" showIcon message="当前区间仅 1 天时，日均为稳态模拟，便于演示图表逻辑" />
                          ) : null}
                          {dailyLowCoverageVisible ? (
                            <Alert
                              type="warning"
                              showIcon
                              message={`数据覆盖不足：区间 ${dailyData.num_days} 天中仅 ${dailyData.coverage_days} 天有正式表数据`}
                              description="覆盖不足时日均余额会退化为有数据日的均值（极端情况等于期末时点），请确认 fact_formal 表已对区间内每个日期执行物化。"
                            />
                          ) : null}
                          {dailySnapshotFallbackVisible ? (
                            <Alert
                              data-testid="adb-snapshot-fallback-warning"
                              type="warning"
                              showIcon
                              message="快照补数降级"
                              description={ADB_SNAPSHOT_FALLBACK_WARNING}
                            />
                          ) : null}
                          {deviationWarning ? <Alert type="warning" showIcon message={deviationWarning} /> : null}
                          {rateCoverageWarning ? (
                            <Alert
                              data-testid="adb-rate-coverage-warning"
                              type="warning"
                              showIcon
                              message={rateCoverageWarning}
                            />
                          ) : null}
                        </div>
                      ) : (
                        <p className="adb-note">区间内未触发覆盖/降级/偏离警示。</p>
                      )}
                    </section>

                    <section className="adb-sec">
                      <AdbSectionHead title="口径与证据" />
                      <div className="adb-panel">
                        <p className="adb-note">
                          口径说明：期末时点=期末（{dailyData.end_date}）时点规模；区间日均=区间日均规模
                        </p>
                        <AdbDenominatorSummary data={dailyData} />
                        <ResultMetaNotice
                          meta={dailyData.result_meta}
                          testId="adb-daily-result-meta"
                        />
                        {(lowCoverageWarning || rateCoverageWarning) && startDate && endDate ? (
                          <AdbCoverageDiagnostics
                            loading={coverageQuery.isLoading}
                            isError={coverageQuery.isError}
                            data={coverageQuery.data}
                            rateCoverage={
                              rateCoverageWarning
                                ? {
                                    assetRateCoverageRatio: dailyData?.asset_rate_coverage_ratio,
                                    liabilityRateCoverageRatio: dailyData?.liability_rate_coverage_ratio,
                                  }
                                : undefined
                            }
                          />
                        ) : null}
                      </div>
                    </section>

                    {dailyHasAccountingBasis ? (
                      <section className="adb-sec">
                        <AdbSectionHead title="会计计量分桶" />
                        <AdbAccountingBasisSection
                          snapshot={dailyData.accounting_basis_daily_avg}
                          trend={dailyData.accounting_basis_daily_avg_trend}
                          titleSuffix="日度区间"
                        />
                      </section>
                    ) : null}

                    <section className="adb-sec">
                      <AdbSectionHead title="期末时点与日均偏离对比" />
                      <div className="adb-two-col">
                        <div className="adb-panel adb-chart-panel">
                          <div className="adb-subhead">期末时点与日均偏离对比 · 资产</div>
                          <AdbComparisonChart rows={comparisonAssetRows} />
                        </div>
                        <div className="adb-panel adb-chart-panel">
                          <div className="adb-subhead">期末时点与日均偏离对比 · 负债</div>
                          <AdbComparisonChart rows={comparisonLiabilityRows} />
                        </div>
                      </div>
                    </section>

                    {trendQuery.data?.trend && trendQuery.data.trend.length > 0 ? (
                      <section className="adb-sec" data-testid="adb-daily-trend-chart">
                        <AdbSectionHead
                          title="区间日均余额走势"
                          meta="细线为日余额，粗线为 30 日移动均线，用于识别区间内规模异常波动"
                        />
                        <div className="adb-panel adb-chart-panel">
                          <AdbDailyTrendChart trend={trendQuery.data.trend} />
                        </div>
                      </section>
                    ) : null}

                    {priorYearRange ? (
                      <section className="adb-sec" data-testid="adb-daily-yoy-summary">
                        <AdbSectionHead title="区间同比（去年同期对齐）" />
                        <div className="adb-panel">
                          <p className="adb-note">
                            本期 {startDate}～{endDate} 与去年同期 {priorYearRange.startDate}～{priorYearRange.endDate}{" "}
                            日历对齐。同比% =（本期−去年）/ 去年（分母为 0 时显示为「{EM_DASH}」）。
                          </p>
                          <Alert
                            type="info"
                            showIcon
                            message="两段表格不可加总、也不与彼此对账"
                            description="「区间日均总资/负债」与下方分类明细均来自债券投资（ZQTZ）与同业（TYW）读模型；明细占比为占上方日均总规模之比。"
                          />
                          {priorYearComparisonQuery.isError ? (
                            <Alert
                              type="warning"
                              showIcon
                              message="去年同期区间加载失败，同比表不可用。"
                            />
                          ) : null}
                          {yoyAdbRows.length > 0 ? (
                            <div className="adb-table-group">
                              <div className="adb-subhead">债券与同业 · 区间日均总规模</div>
                              <Table<AdbYoYAmountRow>
                                size="small"
                                pagination={false}
                                rowKey={(row) => row.key}
                                columns={yoyAmountColumns}
                                dataSource={yoyAdbRows}
                              />
                            </div>
                          ) : null}
                          {!priorYearComparisonQuery.isError &&
                          (yoyAssetCategoryRows.length > 0 || yoyLiabilityCategoryRows.length > 0) ? (
                            <div className="adb-table-group-stack" data-testid="adb-daily-yoy-category">
                              {yoyAssetCategoryRows.length > 0 ? (
                                <div className="adb-table-group">
                                  <div className="adb-subhead">资产端分类 · 区间日均同比</div>
                                  <Table<AdbYoYAmountRow>
                                    size="small"
                                    pagination={false}
                                    rowKey={(row) => row.key}
                                    columns={yoyAmountColumns}
                                    dataSource={yoyAssetCategoryRows}
                                  />
                                </div>
                              ) : null}
                              {yoyLiabilityCategoryRows.length > 0 ? (
                                <div className="adb-table-group">
                                  <div className="adb-subhead">负债端分类 · 区间日均同比</div>
                                  <Table<AdbYoYAmountRow>
                                    size="small"
                                    pagination={false}
                                    rowKey={(row) => row.key}
                                    columns={yoyAmountColumns}
                                    dataSource={yoyLiabilityCategoryRows}
                                  />
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </section>
                    ) : null}

                    <section className="adb-sec">
                      <AdbSectionHead title="分类明细" />
                      <div className="adb-two-col">
                        <div className="adb-panel">
                          <div className="adb-subhead">资产端分类明细</div>
                          <p className="adb-note">
                            债券投资（ZQTZ）与同业资产（TYW）；按日均规模降序；占比为占上方「日均总资产」比例；默认至多 20 类
                          </p>
                          <Table size="small" pagination={false} rowKey={(row) => `asset-${row.category}`} columns={dailyAssetColumns} dataSource={dailyData.assets_breakdown} locale={{ emptyText: "暂无数据" }} />
                        </div>
                        <div className="adb-panel">
                          <div className="adb-subhead">负债端分类明细</div>
                          <p className="adb-note">
                            发行类债券与同业负债（ZQTZ/TYW）；按日均规模降序；占比为占上方「日均总负债」比例；默认至多 20 类
                          </p>
                          <Table size="small" pagination={false} rowKey={(row) => `liability-${row.category}`} columns={dailyLiabilityColumns} dataSource={dailyData.liabilities_breakdown} locale={{ emptyText: "暂无数据" }} />
                        </div>
                      </div>
                    </section>
                  </>
                ) : null}
              </div>
            ),
          },
          {
            key: "monthly",
            label: "月度统计",
            children: (
              <div className="adb-stack">
                <div className="adb-tab-lead">
                  <h3>月度日均统计</h3>
                  <p>
                    按年份查看年初至今日均摘要、月度汇总表和单月深度分布，继续复用后端日均余额月度读模型。
                  </p>
                </div>

                <div className="adb-controls">
                  <FilterBar>
                    <span className="adb-control-label">年份</span>
                    <Select
                      aria-label="adb-year"
                      className="adb-filter-year"
                      value={selectedYear}
                      options={yearOptions}
                      onChange={setSelectedYear}
                      getPopupContainer={resolvePopupContainer}
                    />
                  </FilterBar>
                </div>

                {monthlyQuery.isLoading ? (
                  <div className="adb-skeleton" aria-busy="true">
                    <span>数据读取中…</span>
                  </div>
                ) : null}
                {monthlyQuery.isError ? <Alert type="error" showIcon message="月度统计加载失败" /> : null}

                {monthlyData ? (
                  <>
                    <AdbKpiStrip columns={5} items={monthlyKpis} />

                    {monthlyMatrixMonths.length > 1 ? (
                      <section className="adb-sec" data-testid="adb-monthly-nim-trend">
                        <AdbSectionHead
                          title="月度利差走势"
                          meta="加权YTM vs 加权票息 vs NIM利差"
                        />
                        <div className="adb-panel adb-chart-panel">
                          <AdbNimTrendChart months={monthlyMatrixMonths} />
                        </div>
                      </section>
                    ) : null}

                    <section className="adb-sec">
                      <AdbSectionHead title="口径与证据" />
                      {monthlyData.result_meta || monthlySnapshotFallbackVisible ? (
                        <div className="adb-panel">
                          <ResultMetaNotice
                            meta={monthlyData.result_meta}
                            testId="adb-monthly-result-meta"
                          />
                          {monthlySnapshotFallbackVisible ? (
                            <Alert
                              data-testid="adb-monthly-snapshot-fallback-warning"
                              type="warning"
                              showIcon
                              message="快照补数降级"
                              description={ADB_SNAPSHOT_FALLBACK_WARNING}
                            />
                          ) : null}
                        </div>
                      ) : (
                        <p className="adb-note">本次月度读取未返回结果元信息。</p>
                      )}
                    </section>

                    {monthlyHasAccountingBasis ? (
                      <section className="adb-sec">
                        <AdbSectionHead title="会计计量分桶" />
                        <AdbAccountingBasisSection
                          trend={monthlyData.accounting_basis_daily_avg_trend}
                          titleSuffix={`${monthlyData.year} 月度`}
                        />
                      </section>
                    ) : null}

                    <section className="adb-sec" data-testid="adb-monthly-analysis-matrix">
                      <AdbSectionHead title="月度日均分析矩阵" />
                      <div className="adb-panel">
                        <p className="adb-note">
                          单位：金额为亿元，收益率、付息率、NIM 为%；比上月、比年初均取最新月份相对变化。
                        </p>
                        <Table<MonthlyMatrixRow>
                          size="small"
                          pagination={false}
                          rowKey={(row) => row.rowKey}
                          columns={monthlyCategoryMatrixColumns}
                          dataSource={monthlyCategoryMatrixRows}
                          scroll={{ x: "max-content" }}
                        />
                        <Table<MonthlyMatrixRow>
                          size="small"
                          pagination={false}
                          rowKey={(row) => row.rowKey}
                          columns={monthlyProjectMatrixColumns}
                          dataSource={monthlyProjectMatrixRows}
                          scroll={{ x: "max-content" }}
                        />
                      </div>
                    </section>

                    <section className="adb-sec">
                      <AdbSectionHead title="月度汇总表" />
                      <div className="adb-panel">
                        <Table<AdbMonthlyDataItem>
                          size="small"
                          rowKey={(row) => row.month}
                          pagination={false}
                          columns={monthlyTableColumns}
                          dataSource={monthlyData.months}
                          expandable={{
                            expandedRowRender: (row) => (
                              <div className="adb-two-col">
                                <div className="adb-expanded-group">
                                  <div className="adb-subhead">资产端分类明细</div>
                                  <Table size="small" pagination={false} rowKey={(item) => `expanded-asset-${row.month}-${item.category}`} columns={monthlyAssetColumns} dataSource={row.breakdown_assets} />
                                </div>
                                <div className="adb-expanded-group">
                                  <div className="adb-subhead">负债端分类明细</div>
                                  <Table size="small" pagination={false} rowKey={(item) => `expanded-liability-${row.month}-${item.category}`} columns={monthlyLiabilityColumns} dataSource={row.breakdown_liabilities} />
                                </div>
                              </div>
                            ),
                          }}
                        />
                      </div>
                    </section>

                    {selectedMonthData ? (
                      <section className="adb-sec">
                        <AdbSectionHead
                          title="按月度日均分析 - 深度分析"
                          actions={
                            <Select
                              aria-label="adb-month"
                              className="adb-filter-month"
                              value={selectedMonth}
                              options={monthlyData.months.map((item) => ({ label: item.month_label, value: item.month }))}
                              onChange={setSelectedMonth}
                              getPopupContainer={resolvePopupContainer}
                            />
                          }
                        />
                        <div className="adb-two-col">
                          <div className="adb-panel">
                            <div className="adb-subhead">资产端分类明细</div>
                            <AdbMonthlyHorizontalChart
                              className="adb-chart-block"
                              rows={monthlyAssetRows}
                              title={`${selectedMonthData.month_label} 资产端`}
                              variant="asset"
                            />
                            <AdbMonthlyBreakdownTable rows={selectedMonthData.breakdown_assets} columns={monthlyAssetColumns} rowKeyPrefix="asset-deep" />
                          </div>
                          <div className="adb-panel">
                            <div className="adb-subhead">负债端分类明细</div>
                            <AdbMonthlyHorizontalChart
                              className="adb-chart-block"
                              rows={monthlyLiabilityRows}
                              title={`${selectedMonthData.month_label} 负债端`}
                              variant="liability"
                            />
                            <AdbMonthlyBreakdownTable rows={selectedMonthData.breakdown_liabilities} columns={monthlyLiabilityColumns} rowKeyPrefix="liability-deep" />
                          </div>
                        </div>
                      </section>
                    ) : null}
                  </>
                ) : null}
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}
