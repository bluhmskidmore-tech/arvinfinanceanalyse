import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import ReactECharts, { type EChartsOption } from "../../lib/echarts";
import { useApiClient } from "../../api/client";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { designTokens } from "../../theme/designSystem";
import { shellTokens as t } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../components/KpiCard";
import type { Numeric, ResultMeta, RiskTensorChangeMetric, RiskTensorPayload } from "../../api/contracts";
import {
  toneFromSignedDisplayString,
} from "../workbench/components/kpiFormat";
import {
  bondNumericDisplay,
  bondNumericRawOrNull,
} from "../bond-analytics/adapters/bondAnalyticsAdapter";
import "./RiskTensorPage.css";

/** 雷达轴顺序与后端字段一一对应；max 仅用于可视化比例，不做前端金融重算。 */
const RADAR_META = [
  { key: "duration" as const, name: "久期", max: 10 },
  { key: "dv01" as const, name: "估值DV01", max: "dynamic_dv01" as const },
  { key: "convexity" as const, name: "凸性", max: 200 },
  { key: "cs01" as const, name: "CS01", max: "dynamic_cs01" as const },
  { key: "hhi" as const, name: "集中度", max: 1 },
  { key: "liq_ratio" as const, name: "流动性缺口", max: 1 },
] as const;

type RadarKey = (typeof RADAR_META)[number]["key"];

const RADAR_NAVIGATION_TARGETS: Record<RadarKey, string> = {
  duration: "risk-tensor-duration-scope",
  dv01: "risk-tensor-dv01-controls",
  convexity: "risk-tensor-kpi-grid",
  cs01: "risk-tensor-kpi-grid",
  hhi: "risk-tensor-issuer-concentration-detail",
  liq_ratio: "risk-tensor-liquidity-gap-detail",
};

const PRIOR_CHANGE_NAVIGATION_TARGETS: Record<string, string> = {
  dominant_krd_bucket: "risk-tensor-tenor-drill",
  liquidity_gap_30d_ratio: "risk-tensor-liquidity-gap-detail",
};

const PRIOR_CHANGE_DV01_KEYS = new Set(["regulatory_dv01", "portfolio_dv01"]);

const chartRowStyle = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: 16,
  marginTop: 24,
  alignItems: "stretch" as const,
} as const;

const chartColumnStyle = {
  flex: "1 1 calc(50% - 8px)",
  minWidth: 280,
  maxWidth: "100%",
} as const;

const radarCardStyle = {
  height: "100%",
  minHeight: 400,
  padding: 20,
  borderRadius: 18,
  background: t.colorBgCanvas,
  border: `1px solid ${t.colorBorderSoft}`,
  boxShadow: t.shadowPanel,
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

const drillPanelStyle = {
  marginTop: 24,
  padding: 16,
  borderRadius: 16,
  border: `1px solid ${t.colorBorderSoft}`,
  background: t.colorBgCanvas,
} as const;

const chipRowStyle = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: 8,
  marginTop: 12,
} as const;

function chipButtonStyle(active: boolean) {
  return {
    padding: "8px 12px",
    borderRadius: 999,
    border: active ? `1px solid ${designTokens.color.primary[600]}` : `1px solid ${t.colorBorderSoft}`,
    background: active ? designTokens.color.primary[50] : "#ffffff",
    color: active ? designTokens.color.primary[600] : t.colorTextPrimary,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  } as const;
}

function displayStr(value: Parameters<typeof bondNumericDisplay>[0]) {
  return bondNumericDisplay(value);
}

type RiskTensorDisplayValue = Parameters<typeof bondNumericDisplay>[0];
type PriorMetricValueKey = "current" | "previous" | "delta";
type KrdChartClickParams = { name?: unknown };

const YUAN_PER_WAN = 10_000;
const YUAN_PER_YI = 100_000_000;
const WAN_YUAN_UNIT = "\u4e07\u5143";
const YI_YUAN_UNIT = "\u4ebf\u5143";
const RADAR_SPLIT_NUMBER = 5;
const MAIN_PAYLOAD_NUMERIC_FIELDS = [
  { key: "portfolio_dv01", label: "portfolio_dv01" },
  { key: "krd_1y", label: "krd_1y" },
  { key: "krd_3y", label: "krd_3y" },
  { key: "krd_5y", label: "krd_5y" },
  { key: "krd_7y", label: "krd_7y" },
  { key: "krd_10y", label: "krd_10y" },
  { key: "krd_30y", label: "krd_30y" },
  { key: "cs01", label: "cs01" },
  { key: "portfolio_convexity", label: "portfolio_convexity" },
  { key: "portfolio_modified_duration", label: "portfolio_modified_duration" },
  { key: "issuer_concentration_hhi", label: "issuer_concentration_hhi" },
  { key: "issuer_top5_weight", label: "issuer_top5_weight" },
  { key: "asset_cashflow_30d", label: "asset_cashflow_30d" },
  { key: "asset_cashflow_90d", label: "asset_cashflow_90d" },
  { key: "liability_cashflow_30d", label: "liability_cashflow_30d" },
  { key: "liability_cashflow_90d", label: "liability_cashflow_90d" },
  { key: "liquidity_gap_30d", label: "liquidity_gap_30d" },
  { key: "liquidity_gap_90d", label: "liquidity_gap_90d" },
  { key: "liquidity_gap_30d_ratio", label: "liquidity_gap_30d_ratio" },
  { key: "total_market_value", label: "total_market_value" },
] as const;
const KRD_FIELDS = [
  { key: "krd_1y", tenor: "1Y" },
  { key: "krd_3y", tenor: "3Y" },
  { key: "krd_5y", tenor: "5Y" },
  { key: "krd_7y", tenor: "7Y" },
  { key: "krd_10y", tenor: "10Y" },
  { key: "krd_30y", tenor: "30Y" },
] as const;

function riskTensorRawOrNull(value: RiskTensorDisplayValue): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    const normalized = value.trim().replace(/,/g, "");
    if (!normalized) {
      return null;
    }
    const raw = Number(normalized);
    return Number.isFinite(raw) ? raw : null;
  }
  return value.raw !== null && Number.isFinite(value.raw) ? value.raw : null;
}

function riskTensorScalarIssue(value: RiskTensorDisplayValue | null | undefined) {
  if (value === null || value === undefined) {
    return "缺失";
  }
  if (typeof value === "string") {
    const normalized = value.trim();
    if (!normalized || normalized === "undefined") {
      return "缺失";
    }
    return riskTensorRawOrNull(value) === null ? "不可解析" : null;
  }
  if (value.raw === null) {
    return "缺失";
  }
  return Number.isFinite(value.raw) ? null : "不可解析";
}

function riskTensorPayloadQualityIssues(result: RiskTensorPayload) {
  return MAIN_PAYLOAD_NUMERIC_FIELDS.flatMap((field) => {
    const issue = riskTensorScalarIssue(result[field.key]);
    return issue ? [{ ...field, issue }] : [];
  });
}

function amountUnit(value: RiskTensorDisplayValue, unit: string) {
  return riskTensorRawOrNull(value) === null ? undefined : unit;
}

function shouldPrefixPositiveAmount(value: RiskTensorDisplayValue) {
  if (typeof value === "string") {
    return value.trim().startsWith("+");
  }
  return Boolean(value?.sign_aware);
}

function formatYuanAmount(value: RiskTensorDisplayValue, divisor: number) {
  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return displayStr(value);
  }
  const scaled = raw / divisor;
  const formatted = Math.abs(scaled).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (scaled < 0) {
    return `-${formatted}`;
  }
  return `${shouldPrefixPositiveAmount(value) && scaled > 0 ? "+" : ""}${formatted}`;
}

function yuanAsWanDisplay(value: RiskTensorDisplayValue) {
  return formatYuanAmount(value, YUAN_PER_WAN);
}

function yuanAsYiDisplay(value: RiskTensorDisplayValue) {
  return formatYuanAmount(value, YUAN_PER_YI);
}

function yuanAsWanWithUnit(value: RiskTensorDisplayValue) {
  const display = yuanAsWanDisplay(value);
  return riskTensorRawOrNull(value) === null ? display : `${display} ${WAN_YUAN_UNIT}`;
}

function yuanAsYiWithUnit(value: RiskTensorDisplayValue) {
  const display = yuanAsYiDisplay(value);
  return riskTensorRawOrNull(value) === null ? display : `${display} ${YI_YUAN_UNIT}`;
}

function yuanAsWanMagnitudeOrNull(value: RiskTensorDisplayValue) {
  const raw = riskTensorRawOrNull(value);
  return raw === null ? null : raw / YUAN_PER_WAN;
}

function isWanAmountMetric(key: string) {
  return key === "portfolio_dv01" || key === "regulatory_dv01" || key === "cs01" || key.startsWith("krd_");
}

function priorMetricDisplay(metric: RiskTensorChangeMetric, key: PriorMetricValueKey) {
  if (!isWanAmountMetric(metric.key)) {
    const displayKey = `${key}_display` as const;
    return metric[displayKey];
  }
  return yuanAsWanWithUnit(metric[key] as Numeric);
}

function chartMagnitudeOrNull(value: RiskTensorDisplayValue) {
  const raw = riskTensorRawOrNull(value);
  return raw === null ? null : raw;
}

function ratioPercentDisplay(value: Parameters<typeof bondNumericRawOrNull>[0]) {
  const display = displayStr(value);
  if (display.includes("%")) {
    return display;
  }
  const raw = bondNumericRawOrNull(value);
  if (raw === null) {
    return display;
  }
  const abs = Math.abs(raw);
  if (abs <= 1) {
    return `${(raw * 100).toFixed(1)}%`;
  }
  if (abs <= 100) {
    return `${raw.toFixed(1)}%`;
  }
  return display;
}

function ratioTone(value: Parameters<typeof bondNumericRawOrNull>[0]) {
  return toneFromSignedDisplayString(ratioPercentDisplay(value));
}

function hasRiskTensorValue(value: RiskTensorDisplayValue | null | undefined) {
  return value !== null && value !== undefined;
}

function countDisplay(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return value.toLocaleString("zh-CN");
}

function hasDurationScopeDisclosure(result: RiskTensorPayload) {
  return (
    hasRiskTensorValue(result.rate_risk_market_value) ||
    hasRiskTensorValue(result.rate_risk_dv01) ||
    hasRiskTensorValue(result.rate_risk_modified_duration) ||
    hasRiskTensorValue(result.duration_excluded_market_value) ||
    (result.duration_excluded_count !== null && result.duration_excluded_count !== undefined)
  );
}

function durationExclusionTone(result: RiskTensorPayload) {
  const excludedMarketValue = riskTensorRawOrNull(result.duration_excluded_market_value);
  if ((result.duration_excluded_count ?? 0) > 0 || (excludedMarketValue ?? 0) > 0) {
    return "warning";
  }
  return "default";
}

function priorMetricTone(tone: string) {
  if (tone === "good" || tone === "warning") {
    return tone;
  }
  return "neutral";
}

function qualityFlagLabel(flag: string | undefined) {
  if (flag === "ok") {
    return "正常";
  }
  if (flag === "warning") {
    return "预警";
  }
  if (flag === "error") {
    return "错误";
  }
  if (flag === "stale") {
    return "陈旧";
  }
  if (flag === "missing") {
    return "缺失";
  }
  return flag || "未提供";
}

function qualityTone(flag: string | undefined) {
  if (flag === "error" || flag === "stale") {
    return "danger";
  }
  if (flag === "warning") {
    return "warning";
  }
  if (flag === "ok") {
    return "ok";
  }
  return "neutral";
}

function fallbackModeLabel(mode: ResultMeta["fallback_mode"] | string | undefined) {
  if (mode === "none") {
    return "未降级";
  }
  if (mode === "latest" || mode === "latest_snapshot") {
    return "latest snapshot fallback";
  }
  if (mode === "mock") {
    return "mock fallback";
  }
  if (mode === "degraded") {
    return "降级";
  }
  return mode || "未提供";
}

function compactVersion(value: string | undefined) {
  if (!value) {
    return "未提供";
  }
  if (value.length <= 42) {
    return value;
  }
  return `${value.slice(0, 22)}...${value.slice(-12)}`;
}

function metaValueLabel(value: unknown) {
  if (value === null) {
    return "null";
  }
  if (value === undefined) {
    return "未提供";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function filtersAppliedLabel(filters: ResultMeta["filters_applied"] | undefined) {
  const entries = Object.entries(filters ?? {});
  return entries.map(([key, value]) => `${key}=${metaValueLabel(value)}`).join("；");
}

function liquidityGapLabel(raw: number | null) {
  if (raw === null) {
    return "30 日缺口待确认";
  }
  if (raw < 0) {
    return "30 日缺口为负";
  }
  if (raw > 0) {
    return "30 日缺口为正";
  }
  return "30 日缺口持平";
}

function liquidityGapTone(raw: number | null) {
  if (raw === null) {
    return "neutral";
  }
  return raw < 0 ? "danger" : "ok";
}

function errorStatusCode(error: unknown) {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const match = message.match(/\((\d{3})\)/);
  return match ? match[1] : "";
}

function riskTensorErrorMessage(statusCode: string) {
  if (statusCode === "404") {
    return "当前报告日无风险张量数据";
  }
  if (statusCode === "503") {
    return "风险张量治理前置缺失";
  }
  return "风险张量主读面加载失败";
}

function requiredActionSummary(actions: NonNullable<RiskTensorPayload["dv01_controls"]>["control_actions"] | undefined) {
  if (!actions) {
    return "控制项未接入";
  }
  const required = actions.filter((item) => item.status === "required");
  if (required.length === 0) {
    return "暂无必做项";
  }
  return `${required.length} 项必做`;
}

function dynamicAxisMax(raw: number, fallback: number) {
  const base = Math.abs(raw) * 1.5;
  if (!Number.isFinite(base) || base === 0) {
    return fallback;
  }
  return readableRadarAxisMax(base);
}

function readableRadarAxisMax(max: number) {
  const intervalBase = max / RADAR_SPLIT_NUMBER;
  if (!Number.isFinite(intervalBase) || intervalBase <= 0) {
    return max;
  }
  const magnitude = 10 ** Math.floor(Math.log10(intervalBase));
  const normalized = intervalBase / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 3 ? 3 : normalized <= 5 ? 5 : 10;
  return niceNormalized * magnitude * RADAR_SPLIT_NUMBER;
}

function radarIndicator(name: string, max: number) {
  const readableMax = readableRadarAxisMax(max);
  return { name, min: 0, max: readableMax, interval: readableMax / RADAR_SPLIT_NUMBER };
}

function regulatoryDv01Display(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return "待接入";
  }
  return yuanAsWanDisplay(value);
}

function regulatoryDv01DisplayWithUnit(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return regulatoryDv01Display(value);
  }
  return `${regulatoryDv01Display(value)} ${WAN_YUAN_UNIT}`;
}

function regulatoryDv01Tone(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return "warning";
  }
  return toneFromSignedDisplayString(regulatoryDv01Display(value));
}

function dv01ControlStatusLabel(status: string) {
  if (status === "pending_configuration") {
    return "限额待配置";
  }
  if (status === "ok") {
    return "限额内";
  }
  if (status === "near") {
    return "接近限额";
  }
  if (status === "breach") {
    return "已超限";
  }
  return status;
}

function dv01ControlStatusDescription(status: string) {
  if (status === "pending_configuration") {
    return "暂不判定超限";
  }
  if (status === "ok") {
    return "可承受";
  }
  if (status === "near") {
    return "接近预警";
  }
  if (status === "breach") {
    return "需要处置";
  }
  return "状态待核对";
}

function dv01VolatilityLabel(status: string) {
  if (status === "pending_market_volatility") {
    return "波动源待接入";
  }
  return status;
}

function dv01VolatilityDescription(status: string) {
  if (status === "pending_market_volatility") {
    return "未接入利率波动率源，先看标准冲击。";
  }
  return "波动输入已接入。";
}

function dv01ControlActionStatusLabel(status: string) {
  if (status === "required") {
    return "必做项";
  }
  if (status === "done") {
    return "已完成";
  }
  if (status === "watch") {
    return "观察项";
  }
  return "待核对";
}

export default function RiskTensorPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const [selectedTenor, setSelectedTenor] = useState<string>("");
  const [qualityEvidenceCopyStatus, setQualityEvidenceCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const [qualityEvidenceReviewConfirmed, setQualityEvidenceReviewConfirmed] = useState(false);
  const [qualityEvidenceReviewRecordCopyStatus, setQualityEvidenceReviewRecordCopyStatus] = useState<
    "idle" | "copied" | "failed"
  >("idle");
  const [qualityEvidenceRequestCopyStatus, setQualityEvidenceRequestCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );
  const [payloadQualityRequestCopyStatus, setPayloadQualityRequestCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );
  const [combinedQualityRequestCopyStatus, setCombinedQualityRequestCopyStatus] = useState<
    "idle" | "copied" | "failed"
  >("idle");
  const [tensorErrorCopyStatus, setTensorErrorCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const [blockedDateCopyStatus, setBlockedDateCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const [datesErrorCopyStatus, setDatesErrorCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const [datesEmptyCopyStatus, setDatesEmptyCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const [emptyPositionCopyStatus, setEmptyPositionCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const datesQuery = useQuery({
    queryKey: ["risk-tensor", "dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    retry: false,
  });

  const blockedReportDates = datesQuery.data?.result.blocked_report_dates ?? [];
  const selectedBlockedReportDate = explicitReportDate
    ? blockedReportDates.find((entry) => entry.report_date === explicitReportDate)
    : undefined;
  const latestBlockedReportDate = [...blockedReportDates].sort((a, b) => b.report_date.localeCompare(a.report_date))[0];
  const highlightedBlockedReportDate = selectedBlockedReportDate ?? latestBlockedReportDate;

  const reportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return datesQuery.data?.result.report_dates[0] ?? "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);
  const reportDateOptions = useMemo(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (!reportDate || dates.includes(reportDate)) {
      return dates;
    }
    return [reportDate, ...dates];
  }, [datesQuery.data?.result.report_dates, reportDate]);

  const datesBlockingError = datesQuery.isError;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;
  const tensorBlockedByReportDate = Boolean(selectedBlockedReportDate);
  const tensorQueryEnabled = Boolean(reportDate) && datesQuery.isSuccess && !tensorBlockedByReportDate;

  const tensorQuery = useQuery({
    queryKey: ["risk-tensor", reportDate],
    queryFn: () => client.getRiskTensor(reportDate),
    enabled: tensorQueryEnabled,
    retry: false,
  });

  const envelope = datesBlockingError || tensorBlockedByReportDate ? undefined : tensorQuery.data;
  const result = envelope?.result;
  const isEmpty =
    !tensorQuery.isLoading &&
    !tensorQuery.isError &&
    result !== undefined &&
    result.bond_count === 0;
  const tensorErrorStatusCode = errorStatusCode(tensorQuery.error);
  const datesErrorStatusCode = errorStatusCode(datesQuery.error);
  const tensorErrorReportDate = reportDate || explicitReportDate || "未选择";
  const datesErrorReportDate = explicitReportDate || "未选择";
  const datesGovernanceMeta = datesQuery.data?.result_meta;
  const datesEmptyTraceId = datesGovernanceMeta?.trace_id ?? "未提供";

  const krdChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const labels = KRD_FIELDS.map((item) => item.tenor);
    const data = KRD_FIELDS.map((item) => yuanAsWanMagnitudeOrNull(result[item.key]));
    return {
      grid: { left: 52, right: 16, top: 36, bottom: 28 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#5c6b82" },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#5c6b82" },
        splitLine: { lineStyle: { color: "#eef2f7" } },
      },
      series: [
        {
          type: "bar",
          data,
          itemStyle: { color: designTokens.color.primary[600], borderRadius: [6, 6, 0, 0] },
        },
      ],
    };
  }, [result]);

  const tenorRows = useMemo(() => {
    if (!result) {
      return [];
    }
    return KRD_FIELDS.map((item) => ({
      key: item.key,
      tenor: item.tenor,
      value: result[item.key],
      magnitude: yuanAsWanMagnitudeOrNull(result[item.key]),
    }));
  }, [result]);

  const invalidKrdRows = useMemo(() => tenorRows.filter((row) => row.magnitude === null), [tenorRows]);
  const invalidRadarRows = useMemo(() => {
    if (!result) {
      return [];
    }
    return [
      { key: "portfolio_modified_duration", issue: riskTensorScalarIssue(result.portfolio_modified_duration) },
      { key: "portfolio_dv01", issue: riskTensorScalarIssue(result.portfolio_dv01) },
      { key: "portfolio_convexity", issue: riskTensorScalarIssue(result.portfolio_convexity) },
      { key: "cs01", issue: riskTensorScalarIssue(result.cs01) },
      { key: "issuer_concentration_hhi", issue: riskTensorScalarIssue(result.issuer_concentration_hhi) },
      { key: "liquidity_gap_30d_ratio", issue: riskTensorScalarIssue(result.liquidity_gap_30d_ratio) },
    ].filter((item): item is { key: string; issue: string } => Boolean(item.issue));
  }, [result]);

  const dominantTenorRow = useMemo(() => {
    if (tenorRows.length === 0) {
      return undefined;
    }
    const backendBucket = result?.dv01_controls?.dominant_krd_bucket;
    const backendRow = backendBucket ? tenorRows.find((row) => row.tenor === backendBucket) : undefined;
    if (backendRow && backendRow.magnitude !== null) {
      return backendRow;
    }
    return [...tenorRows]
      .filter((row) => row.magnitude !== null)
      .sort((left, right) => Math.abs(right.magnitude ?? 0) - Math.abs(left.magnitude ?? 0))[0];
  }, [result?.dv01_controls?.dominant_krd_bucket, tenorRows]);

  useEffect(() => {
    if (tenorRows.length === 0) {
      setSelectedTenor("");
      return;
    }
    const defaultTenor = dominantTenorRow?.tenor ?? tenorRows.find((row) => row.magnitude !== null)?.tenor ?? "";
    if (!selectedTenor || !tenorRows.some((row) => row.tenor === selectedTenor)) {
      setSelectedTenor(defaultTenor);
    }
  }, [dominantTenorRow?.tenor, selectedTenor, tenorRows]);

  const selectedTenorRow =
    tenorRows.find((row) => row.tenor === selectedTenor) ??
    dominantTenorRow ??
    tenorRows.find((row) => row.magnitude !== null);
  const tensorMeta = envelope?.result_meta;

  const fallbackStatus = fallbackModeLabel(tensorMeta?.fallback_mode);
  const blockedReportDateSummary = `${blockedReportDates.length} 个陈旧日期已拦截`;
  const metadataTablesUsed = tensorMeta?.tables_used?.filter(Boolean).join(" / ") ?? "";
  const metadataFiltersApplied = filtersAppliedLabel(tensorMeta?.filters_applied);
  const primaryTenor = dominantTenorRow?.tenor ?? result?.dv01_controls?.dominant_krd_bucket ?? "--";
  const primaryTenorValue = dominantTenorRow
    ? yuanAsWanWithUnit(dominantTenorRow.value)
    : result?.dv01_controls
      ? yuanAsWanWithUnit(result.dv01_controls.dominant_krd)
      : "--";
  const liquidity30dRaw = result ? bondNumericRawOrNull(result.liquidity_gap_30d) : null;
  const requiredActions = result?.dv01_controls?.control_actions.filter((item) => item.status === "required") ?? [];
  const firstRequiredAction = requiredActions[0];
  const actionTileDetail =
    firstRequiredAction?.title ??
    result?.warnings[0] ??
    "后端未返回必做控制动作，继续按质量标记和明细核对。";
  const actionTileCanJump = Boolean(result && (requiredActions.length > 0 || result.warnings.length > 0));
  const actionTileTone = !result?.dv01_controls || requiredActions.length > 0 || (result?.warnings.length ?? 0) > 0 ? "warning" : "ok";
  const showDurationScope = result ? hasDurationScopeDisclosure(result) : false;
  const radarNavigationItems = result
    ? RADAR_META.map((item) => {
        const targetTestId =
          (item.key === "duration" && !showDurationScope) || (item.key === "dv01" && !result.dv01_controls)
            ? "risk-tensor-kpi-grid"
            : RADAR_NAVIGATION_TARGETS[item.key];
        return {
          key: item.key,
          name: item.name,
          targetTestId,
        };
      })
    : [];
  const priorChangeTargetFor = (metricKey: string) => {
    if (PRIOR_CHANGE_DV01_KEYS.has(metricKey)) {
      return result?.dv01_controls ? "risk-tensor-dv01-controls" : "risk-tensor-kpi-grid";
    }
    return PRIOR_CHANGE_NAVIGATION_TARGETS[metricKey];
  };
  const topLineSummary = result
    ? [
        `主风险桶 ${primaryTenor}`,
        liquidityGapLabel(liquidity30dRaw),
        `质量标记：${qualityFlagLabel(result.quality_flag)}`,
      ].join(" / ")
    : "";
  const conclusionNeedsQualityReview = result?.quality_flag === "stale" || result?.quality_flag === "error";
  const qualityReviewReasons = [
    tensorMeta?.fallback_date ? `fallback_date ${tensorMeta.fallback_date}` : null,
    blockedReportDates.length > 0 ? blockedReportDateSummary : null,
    result?.warnings[0] ?? null,
  ].filter((item): item is string => Boolean(item));
  const qualityReviewReasonSummary =
    qualityReviewReasons.length > 0 ? qualityReviewReasons.join("；") : "查看质量证据";
  const qualityTraceFallbackDetail = tensorMeta?.fallback_date
    ? `${fallbackStatus}；fallback_date ${tensorMeta.fallback_date}`
    : fallbackStatus;
  const qualityTraceBlockedDetail = highlightedBlockedReportDate
    ? `${blockedReportDateSummary}；${highlightedBlockedReportDate.report_date}${
        highlightedBlockedReportDate.reason ? ` ${highlightedBlockedReportDate.reason}` : ""
      }`
    : blockedReportDateSummary;
  const qualityTraceWarningDetail = result?.warnings.filter(Boolean).join(" / ") || "无预警";
  const qualityTraceMetadataDetail = `trace_id ${tensorMeta?.trace_id ?? "未提供"}；evidence_rows ${
    typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "未提供"
  }；tables_used ${metadataTablesUsed || "未提供"}；filters_applied ${metadataFiltersApplied || "未提供"}`;
  const payloadQualityIssues = result ? riskTensorPayloadQualityIssues(result) : [];
  const payloadQualityIssueLabels = payloadQualityIssues.map((item) => `${item.label} ${item.issue}`);
  const payloadQualityIssueSummary = payloadQualityIssueLabels.join(" / ");
  const qualityEvidenceStateKey = [
    `evidence_rows:${typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "missing"}`,
    `tables_used:${metadataTablesUsed || "missing"}`,
    `filters_applied:${metadataFiltersApplied || "missing"}`,
  ].join("|");
  const qualityLineageStateKey = [
    `source_version:${tensorMeta?.source_version ?? "missing"}`,
    `rule_version:${tensorMeta?.rule_version ?? "missing"}`,
  ].join("|");
  const qualityFallbackStateKey = [
    `fallback_mode:${tensorMeta?.fallback_mode ?? "missing"}`,
    `fallback_date:${tensorMeta?.fallback_date ?? "missing"}`,
  ].join("|");
  const qualityIssuanceStateKey = [
    `basis:${tensorMeta?.basis ?? "missing"}`,
    `cache_version:${tensorMeta?.cache_version ?? "missing"}`,
    `generated_at:${tensorMeta?.generated_at ?? "missing"}`,
  ].join("|");
  const qualityWarningStateKey = `warning:${qualityTraceWarningDetail}`;
  const qualityBlockedDateStateKey = `blocked:${qualityTraceBlockedDetail}`;
  const qualityFlagStateKey = `quality_flag:${result?.quality_flag ?? tensorMeta?.quality_flag ?? "missing"}`;
  const qualityResultKindStateKey = `result_kind:${tensorMeta?.result_kind ?? "missing"}`;
  const qualityStateKey = `${tensorMeta?.trace_id ?? ""}|${result?.report_date ?? reportDate ?? ""}|${payloadQualityIssueSummary}|${qualityEvidenceStateKey}|${qualityLineageStateKey}|${qualityFallbackStateKey}|${qualityIssuanceStateKey}|${qualityWarningStateKey}|${qualityBlockedDateStateKey}|${qualityFlagStateKey}|${qualityResultKindStateKey}`;

  useEffect(() => {
    setQualityEvidenceCopyStatus("idle");
  }, [qualityStateKey]);

  useEffect(() => {
    setQualityEvidenceReviewConfirmed(false);
    setQualityEvidenceReviewRecordCopyStatus("idle");
    setQualityEvidenceRequestCopyStatus("idle");
    setPayloadQualityRequestCopyStatus("idle");
    setCombinedQualityRequestCopyStatus("idle");
  }, [qualityStateKey]);
  const qualityEvidenceReviewItems = [
    {
      key: "evidence_rows",
      label: "evidence_rows",
      status: typeof tensorMeta?.evidence_rows === "number" ? "已提供" : "未提供",
    },
    {
      key: "tables_used",
      label: "tables_used",
      status: metadataTablesUsed ? "已提供" : "未提供",
    },
    {
      key: "filters_applied",
      label: "filters_applied",
      status: metadataFiltersApplied ? "已提供" : "未提供",
    },
  ];
  const hasMissingQualityEvidence = qualityEvidenceReviewItems.some((item) => item.status === "未提供");
  const missingQualityEvidenceLabels = qualityEvidenceReviewItems
    .filter((item) => item.status === "未提供")
    .map((item) => item.label);
  const canConfirmQualityEvidenceReview =
    !hasMissingQualityEvidence && qualityEvidenceCopyStatus === "copied" && !qualityEvidenceReviewConfirmed;
  const qualityReviewStateLabel =
    hasMissingQualityEvidence
      ? "证据不完整，待补证"
      : qualityEvidenceReviewConfirmed
        ? "业务已确认"
      : qualityEvidenceCopyStatus === "copied"
        ? "证据已复制，待业务确认"
        : qualityEvidenceCopyStatus === "failed"
          ? "复制失败，需手动选择证据"
          : "待复核";
  const qualityIssuanceCopyLines = [
    `basis ${tensorMeta?.basis ?? "未提供"}`,
    `cache_version ${tensorMeta?.cache_version ?? "未提供"}`,
    `generated_at ${tensorMeta?.generated_at ?? "未提供"}`,
  ];
  const qualityTraceCopyText = [
    "风险张量质量证据",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `复核状态 ${qualityReviewStateLabel}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `fallback ${qualityTraceFallbackDetail}`,
    `陈旧日期 ${qualityTraceBlockedDetail}`,
    `warning ${qualityTraceWarningDetail}`,
    `主读 payload 字段 ${payloadQualityIssueSummary || "全部可解析"}`,
    `证据范围 ${qualityTraceMetadataDetail}`,
    "证据字段复核",
    ...qualityEvidenceReviewItems.map((item) => `${item.label} ${item.status}`),
  ].join("\n");
  const qualityEvidenceRequestCopyText = [
    "风险张量质量证据补证请求",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `缺失字段 ${missingQualityEvidenceLabels.join(" / ") || "无"}`,
    "请在 result_meta 补充 evidence_rows、tables_used、filters_applied 后重新出具",
  ].join("\n");
  const payloadQualityRequestCopyText = [
    "风险张量主读 payload 补证请求",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `异常字段 ${payloadQualityIssueSummary || "无"}`,
    "后端主读字段缺失或不可解析时，页面只保留后端原始展示/占位，不会在前端补算正式指标",
    "请核对风险张量物化任务、字段序列化、result_meta 证据和来源 lineage 后重新出具",
  ].join("\n");
  const combinedQualityRequestCopyText = [
    "风险张量首屏补证包",
    payloadQualityRequestCopyText,
    "",
    qualityEvidenceRequestCopyText,
  ].join("\n");
  const qualityEvidenceReviewRecordCopyText = [
    "风险张量质量证据确认记录",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    "确认状态 业务已确认",
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `quality_flag ${result?.quality_flag ?? tensorMeta?.quality_flag ?? "未提供"}`,
    `fallback ${qualityTraceFallbackDetail}`,
    `陈旧日期 ${qualityTraceBlockedDetail}`,
    `warning ${qualityTraceWarningDetail}`,
    `证据范围 ${qualityTraceMetadataDetail}`,
    `主读 payload 字段 ${payloadQualityIssueSummary || "全部可解析"}`,
    "证据字段复核",
    ...qualityEvidenceReviewItems.map((item) => `${item.label} ${item.status}`),
  ].join("\n");
  const qualityEvidenceCopyMessage =
    qualityEvidenceCopyStatus === "copied"
      ? "已复制证据摘要"
      : qualityEvidenceCopyStatus === "failed"
        ? "复制失败，请手动选择证据"
        : "";
  const qualityEvidenceRequestCopyMessage =
    qualityEvidenceRequestCopyStatus === "copied"
      ? "已复制补证请求"
      : qualityEvidenceRequestCopyStatus === "failed"
        ? "复制失败，请手动选择补证请求"
        : "";
  const qualityEvidenceReviewRecordCopyMessage =
    qualityEvidenceReviewRecordCopyStatus === "copied"
      ? "已复制确认记录"
      : qualityEvidenceReviewRecordCopyStatus === "failed"
        ? "复制失败，请手动选择确认记录"
        : "";
  const payloadQualityRequestCopyMessage =
    payloadQualityRequestCopyStatus === "copied"
      ? "已复制字段补证请求"
      : payloadQualityRequestCopyStatus === "failed"
        ? "复制失败，请手动选择字段补证请求"
        : "";
  const combinedQualityRequestCopyMessage =
    combinedQualityRequestCopyStatus === "copied"
      ? "已复制完整补证包"
      : combinedQualityRequestCopyStatus === "failed"
        ? "复制失败，请手动选择完整补证包"
        : "";
  const tensorErrorCopyText = [
    "风险张量主读面加载失败排查信息",
    `报告日 ${tensorErrorReportDate}`,
    `HTTP 状态 ${tensorErrorStatusCode || "未知"}`,
    `日期治理 trace_id ${datesGovernanceMeta?.trace_id ?? "未提供"}`,
    `basis ${datesGovernanceMeta?.basis ?? "未提供"}`,
    `cache_version ${datesGovernanceMeta?.cache_version ?? "未提供"}`,
    `generated_at ${datesGovernanceMeta?.generated_at ?? "未提供"}`,
    `source_version ${datesGovernanceMeta?.source_version ?? "未提供"}`,
    `rule_version ${datesGovernanceMeta?.rule_version ?? "未提供"}`,
    "主读面 trace_id 未提供",
    "请先核对正式风险张量物化和 lineage 新鲜度",
    "页面不会使用缓存或前端补算替代正式主读结果",
  ].join("\n");
  const tensorErrorCopyMessage =
    tensorErrorCopyStatus === "copied"
      ? "已复制排查信息"
      : tensorErrorCopyStatus === "failed"
        ? "复制失败，请手动选择排查信息"
        : "";
  const blockedDateCopyText = [
    "风险张量报告日拦截排查信息",
    `报告日 ${selectedBlockedReportDate?.report_date ?? (explicitReportDate || "未选择")}`,
    `reason ${selectedBlockedReportDate?.reason || "后端未返回原因"}`,
    `日期治理 trace_id ${datesGovernanceMeta?.trace_id ?? "未提供"}`,
    "主读面未读取",
    "请切换到可用报告日",
  ].join("\n");
  const blockedDateCopyMessage =
    blockedDateCopyStatus === "copied"
      ? "已复制拦截信息"
      : blockedDateCopyStatus === "failed"
        ? "复制失败，请手动选择拦截信息"
        : "";
  const datesErrorCopyText = [
    "风险张量报告日列表加载失败排查信息",
    `HTTP 状态 ${datesErrorStatusCode || "未知"}`,
    "请求 /api/risk/tensor/dates",
    `报告日参数 ${datesErrorReportDate}`,
    "页面不会回退到硬编码报告日",
    "主读面未读取",
    "请核对风险张量报告日物化任务和日期治理接口",
  ].join("\n");
  const datesErrorCopyMessage =
    datesErrorCopyStatus === "copied"
      ? "已复制日期排查信息"
      : datesErrorCopyStatus === "failed"
        ? "复制失败，请手动选择日期排查信息"
        : "";
  const datesEmptyCopyText = [
    "风险张量报告日列表为空排查信息",
    `trace_id ${datesEmptyTraceId}`,
    "可用报告日 0 个",
    `报告日参数 ${datesErrorReportDate}`,
    "页面不会回退到硬编码报告日",
    "主读面未读取",
    "请核对风险张量报告日物化任务和日期治理结果",
  ].join("\n");
  const datesEmptyCopyMessage =
    datesEmptyCopyStatus === "copied"
      ? "已复制空日期排查信息"
      : datesEmptyCopyStatus === "failed"
        ? "复制失败，请手动选择空日期排查信息"
        : "";
  const emptyPositionCopyText = [
    "风险张量空持仓排查信息",
    `报告日 ${result?.report_date ?? (reportDate || "未选择")}`,
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `bond_count ${result?.bond_count ?? "未提供"}`,
    `quality_flag ${result?.quality_flag ?? tensorMeta?.quality_flag ?? "未提供"}`,
    `evidence_rows ${typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "未提供"}`,
    `tables_used ${metadataTablesUsed || "未提供"}`,
    `filters_applied ${metadataFiltersApplied || "未提供"}`,
    "页面不会在前端补算正式指标",
    "请核对持仓快照、风险张量物化任务和元数据证据",
  ].join("\n");
  const emptyPositionCopyMessage =
    emptyPositionCopyStatus === "copied"
      ? "已复制空持仓排查信息"
      : emptyPositionCopyStatus === "failed"
        ? "复制失败，请手动选择空持仓排查信息"
        : "";

  useEffect(() => {
    setTensorErrorCopyStatus("idle");
  }, [
    tensorErrorReportDate,
    tensorErrorStatusCode,
    datesGovernanceMeta?.trace_id,
    datesGovernanceMeta?.basis,
    datesGovernanceMeta?.cache_version,
    datesGovernanceMeta?.generated_at,
    datesGovernanceMeta?.source_version,
    datesGovernanceMeta?.rule_version,
  ]);

  useEffect(() => {
    setBlockedDateCopyStatus("idle");
  }, [
    selectedBlockedReportDate?.report_date,
    selectedBlockedReportDate?.reason,
    explicitReportDate,
    datesGovernanceMeta?.trace_id,
  ]);

  useEffect(() => {
    setDatesErrorCopyStatus("idle");
  }, [datesErrorReportDate, datesErrorStatusCode]);

  useEffect(() => {
    setDatesEmptyCopyStatus("idle");
  }, [datesEmptyTraceId, datesErrorReportDate]);

  useEffect(() => {
    setEmptyPositionCopyStatus("idle");
  }, [
    result?.report_date,
    result?.bond_count,
    result?.quality_flag,
    tensorMeta?.trace_id,
    tensorMeta?.quality_flag,
    tensorMeta?.evidence_rows,
    metadataTablesUsed,
    metadataFiltersApplied,
  ]);

  const handlePrimaryTenorDrill = () => {
    if (!dominantTenorRow) {
      return;
    }
    setSelectedTenor(dominantTenorRow.tenor);
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-tenor-drill"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleQualityDetailJump = () => {
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-quality-detail"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleDv01ControlsJump = () => {
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-dv01-controls"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleLiquidityDetailJump = () => {
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-liquidity-gap-detail"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleIssuerConcentrationJump = () => {
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-issuer-concentration-detail"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handlePayloadChecklistJump = () => {
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-quality-payload-checklist"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleSectionJump = (targetTestId: string) => {
    document.querySelector<HTMLElement>(`[data-testid="${targetTestId}"]`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  const handleCopyQualityEvidence = () => {
    if (!navigator.clipboard?.writeText) {
      setQualityEvidenceCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityTraceCopyText)
      .then(() => setQualityEvidenceCopyStatus("copied"))
      .catch(() => setQualityEvidenceCopyStatus("failed"));
  };

  const handleCopyQualityEvidenceRequest = () => {
    if (!navigator.clipboard?.writeText) {
      setQualityEvidenceRequestCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityEvidenceRequestCopyText)
      .then(() => setQualityEvidenceRequestCopyStatus("copied"))
      .catch(() => setQualityEvidenceRequestCopyStatus("failed"));
  };

  const handleCopyPayloadQualityRequest = () => {
    if (!navigator.clipboard?.writeText) {
      setPayloadQualityRequestCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(payloadQualityRequestCopyText)
      .then(() => setPayloadQualityRequestCopyStatus("copied"))
      .catch(() => setPayloadQualityRequestCopyStatus("failed"));
  };

  const handleCopyCombinedQualityRequest = () => {
    if (!navigator.clipboard?.writeText) {
      setCombinedQualityRequestCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(combinedQualityRequestCopyText)
      .then(() => setCombinedQualityRequestCopyStatus("copied"))
      .catch(() => setCombinedQualityRequestCopyStatus("failed"));
  };

  const handleConfirmQualityEvidenceReview = () => {
    setQualityEvidenceReviewConfirmed(true);
  };

  const handleCopyQualityEvidenceReviewRecord = () => {
    if (!navigator.clipboard?.writeText) {
      setQualityEvidenceReviewRecordCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityEvidenceReviewRecordCopyText)
      .then(() => setQualityEvidenceReviewRecordCopyStatus("copied"))
      .catch(() => setQualityEvidenceReviewRecordCopyStatus("failed"));
  };

  const handleCopyTensorError = () => {
    if (!navigator.clipboard?.writeText) {
      setTensorErrorCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(tensorErrorCopyText)
      .then(() => setTensorErrorCopyStatus("copied"))
      .catch(() => setTensorErrorCopyStatus("failed"));
  };

  const handleCopyBlockedDate = () => {
    if (!navigator.clipboard?.writeText) {
      setBlockedDateCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(blockedDateCopyText)
      .then(() => setBlockedDateCopyStatus("copied"))
      .catch(() => setBlockedDateCopyStatus("failed"));
  };

  const handleCopyDatesError = () => {
    if (!navigator.clipboard?.writeText) {
      setDatesErrorCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(datesErrorCopyText)
      .then(() => setDatesErrorCopyStatus("copied"))
      .catch(() => setDatesErrorCopyStatus("failed"));
  };

  const handleCopyDatesEmpty = () => {
    if (!navigator.clipboard?.writeText) {
      setDatesEmptyCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(datesEmptyCopyText)
      .then(() => setDatesEmptyCopyStatus("copied"))
      .catch(() => setDatesEmptyCopyStatus("failed"));
  };

  const handleCopyEmptyPosition = () => {
    if (!navigator.clipboard?.writeText) {
      setEmptyPositionCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(emptyPositionCopyText)
      .then(() => setEmptyPositionCopyStatus("copied"))
      .catch(() => setEmptyPositionCopyStatus("failed"));
  };

  const handleKrdChartClick = (params: KrdChartClickParams) => {
    const tenor = typeof params.name === "string" ? params.name : "";
    const row = tenorRows.find((item) => item.tenor === tenor);
    if (!row) {
      return;
    }
    setSelectedTenor(row.tenor);
    document
      .querySelector<HTMLElement>('[data-testid="risk-tensor-tenor-drill"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleRequiredInformationJump = () => {
    const targetTestId =
      requiredActions.length > 0 ? "risk-tensor-dv01-actions" : result?.warnings.length ? "risk-tensor-quality-detail" : null;
    if (!targetTestId) {
      return;
    }
    document.querySelector<HTMLElement>(`[data-testid="${targetTestId}"]`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  const radarChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const duration = chartMagnitudeOrNull(result.portfolio_modified_duration);
    const dv01 = yuanAsWanMagnitudeOrNull(result.portfolio_dv01);
    const convexity = chartMagnitudeOrNull(result.portfolio_convexity);
    const cs01 = yuanAsWanMagnitudeOrNull(result.cs01);
    const hhi = chartMagnitudeOrNull(result.issuer_concentration_hhi);
    const liqRatio = chartMagnitudeOrNull(result.liquidity_gap_30d_ratio);

    const dv01Max = dynamicAxisMax(dv01 ?? 0, 1);
    const cs01Max = dynamicAxisMax(cs01 ?? 0, 1);

    const indicator = RADAR_META.map((m) => {
      if (m.max === "dynamic_dv01") {
        return radarIndicator(m.name, dv01Max);
      }
      if (m.max === "dynamic_cs01") {
        return radarIndicator(m.name, cs01Max);
      }
      return radarIndicator(m.name, m.max);
    });

    const radarValues = [duration, dv01, convexity, cs01, hhi, liqRatio];

    return {
      color: [designTokens.color.primary[600]],
      tooltip: {
        trigger: "item",
        borderColor: t.colorBorderSoft,
        textStyle: { color: t.colorTextPrimary, fontSize: 13 },
      },
      radar: {
        indicator,
        radius: "66%",
        center: ["50%", "54%"],
        axisName: {
          color: t.colorTextSecondary,
          fontSize: 12,
        },
        splitLine: {
          lineStyle: { color: t.colorBorderSoft },
        },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: t.colorBorderSoft } },
      },
      series: [
        {
          type: "radar",
          symbolSize: 5,
          lineStyle: { width: 1.5, color: designTokens.color.primary[600] },
          areaStyle: {
            color: "rgba(31, 94, 255, 0.15)",
          },
          itemStyle: {
            color: designTokens.color.primary[600],
            borderColor: designTokens.color.primary[600],
          },
          data: [
            {
              value: radarValues,
              name: "组合",
            },
          ],
        },
      ],
    };
  }, [result]);

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          风险张量
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          第一屏先回答风险集中在哪个期限桶、30 日流动性是否有缺口、DV01 控制是否可判定，以及当前数据是否可用。
        </p>
      </div>

      <div style={controlBarStyle}>
        {reportDateOptions.length > 0 ? (
          <label className="risk-tensor-report-date-select">
            <span>风险报告日</span>
            <select
              value={reportDate}
              onChange={(event) => {
                const nextReportDate = event.target.value;
                setSearchParams((previous) => {
                  const next = new URLSearchParams(previous);
                  next.set("report_date", nextReportDate);
                  return next;
                });
              }}
            >
              {reportDateOptions.map((dateValue) => (
                <option key={dateValue} value={dateValue}>
                  {dateValue}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid #d7dfea",
            background: "#ffffff",
            color: "#162033",
            fontSize: 14,
          }}
        >
          {datesEmpty ? (
            <span>后端未返回可用风险报告日。</span>
          ) : datesBlockingError ? (
            <span>风险报告日载入失败。</span>
          ) : (
            <>
              报告日：<strong>{reportDate}</strong>
              <span style={{ marginLeft: 8, color: "#8090a8", fontSize: 13 }}>
                （可通过地址栏报告日参数覆盖）
              </span>
            </>
          )}
          {highlightedBlockedReportDate ? (
            <>
              <br />
              <span data-testid="risk-tensor-blocked-dates">
                后端拦截陈旧日期：{blockedReportDates.length} 个。当前提示日期：{" "}
                <strong>{highlightedBlockedReportDate.report_date}</strong>
                {highlightedBlockedReportDate.reason
                  ? ` (${highlightedBlockedReportDate.reason})`
                  : null}
                {selectedBlockedReportDate
                  ? " 当前选择的报告日已被新鲜度校验拦截。"
                  : null}
              </span>
            </>
          ) : null}
        </div>
      </div>

      {selectedBlockedReportDate ? (
        <div className="risk-tensor-error-context" data-testid="risk-tensor-error-context">
          <strong>风险报告日已被新鲜度校验拦截</strong>
          <span>
            报告日 {selectedBlockedReportDate.report_date}；原因{" "}
            {selectedBlockedReportDate.reason || "后端未返回原因"}。trace_id{" "}
            {datesQuery.data?.result_meta.trace_id ?? "未提供"}。主读面未读取；请切换到可用报告日。
          </span>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
            >
              定位元数据
            </button>
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyBlockedDate}>
              复制拦截信息
            </button>
          </div>
          {blockedDateCopyMessage ? (
            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
              {blockedDateCopyMessage}
            </small>
          ) : null}
          {blockedDateCopyStatus === "failed" ? (
            <pre
              className="risk-tensor-quality-detail__manual-copy"
              data-testid="risk-tensor-blocked-date-manual-copy"
              tabIndex={0}
            >
              {blockedDateCopyText}
            </pre>
          ) : null}
        </div>
      ) : tensorQuery.isError ? (
        <div className="risk-tensor-error-context" data-testid="risk-tensor-error-context">
          <strong>{riskTensorErrorMessage(tensorErrorStatusCode)}</strong>
          <span>
            报告日 {tensorErrorReportDate}；HTTP 状态{" "}
            {tensorErrorStatusCode || "未知"}。日期治理 trace_id{" "}
            {datesGovernanceMeta?.trace_id ?? "未提供"}；主读面 trace_id 未提供。请先核对正式风险张量物化和
            lineage 新鲜度；页面不会使用缓存或前端补算替代正式主读结果。
          </span>
          <span>
            日期治理元数据：basis {datesGovernanceMeta?.basis ?? "未提供"}；cache_version{" "}
            {datesGovernanceMeta?.cache_version ?? "未提供"}；generated_at{" "}
            {datesGovernanceMeta?.generated_at ?? "未提供"}；source_version{" "}
            {datesGovernanceMeta?.source_version ?? "未提供"}；rule_version {datesGovernanceMeta?.rule_version ?? "未提供"}。
          </span>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
            >
              定位元数据
            </button>
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyTensorError}>
              复制排查信息
            </button>
          </div>
          {tensorErrorCopyMessage ? (
            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
              {tensorErrorCopyMessage}
            </small>
          ) : null}
          {tensorErrorCopyStatus === "failed" ? (
            <pre
              className="risk-tensor-quality-detail__manual-copy"
              data-testid="risk-tensor-error-manual-copy"
              tabIndex={0}
            >
              {tensorErrorCopyText}
            </pre>
          ) : null}
        </div>
      ) : datesBlockingError ? (
        <div className="risk-tensor-error-context" data-testid="risk-tensor-error-context">
          <strong>风险报告日列表加载失败</strong>
          <span>
            HTTP 状态 {datesErrorStatusCode || "未知"}。页面不会回退到硬编码报告日。
          </span>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyDatesError}>
              复制日期排查信息
            </button>
          </div>
          {datesErrorCopyMessage ? (
            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
              {datesErrorCopyMessage}
            </small>
          ) : null}
          {datesErrorCopyStatus === "failed" ? (
            <pre
              className="risk-tensor-quality-detail__manual-copy"
              data-testid="risk-tensor-dates-error-manual-copy"
              tabIndex={0}
            >
              {datesErrorCopyText}
            </pre>
          ) : null}
        </div>
      ) : null}

      <AsyncSection
        title="组合风险张量"
        isLoading={datesQuery.isLoading || tensorQuery.isLoading}
        isError={datesBlockingError || tensorBlockedByReportDate || tensorQuery.isError}
        isEmpty={isEmpty && !result}
        onRetry={() => {
          void datesQuery.refetch();
          if (tensorQueryEnabled) {
            void tensorQuery.refetch();
          }
        }}
      >
        {datesEmpty ? (
          <div className="risk-tensor-empty-state" data-testid="risk-tensor-dates-empty-state">
            <strong>后端未返回可用风险报告日</strong>
            <span>trace_id {datesEmptyTraceId}</span>
            <span>可用报告日 0 个</span>
            <p>页面不会回退到硬编码报告日；请核对风险张量报告日物化任务和日期治理结果。</p>
            <div className="risk-tensor-quality-detail__trace-actions">
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
              >
                定位元数据
              </button>
              <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyDatesEmpty}>
                复制空日期排查信息
              </button>
            </div>
            {datesEmptyCopyMessage ? (
              <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                {datesEmptyCopyMessage}
              </small>
            ) : null}
            {datesEmptyCopyStatus === "failed" ? (
              <pre
                className="risk-tensor-quality-detail__manual-copy"
                data-testid="risk-tensor-dates-empty-manual-copy"
                tabIndex={0}
              >
                {datesEmptyCopyText}
              </pre>
            ) : null}
          </div>
        ) : isEmpty && result ? (
          <div className="risk-tensor-empty-state" data-testid="risk-tensor-empty-state">
            <strong>当前报告日无风险张量持仓</strong>
            <span>报告日 {result.report_date}</span>
            <span>trace_id {tensorMeta?.trace_id ?? "未提供"}</span>
            <span>质量标记：{qualityFlagLabel(result.quality_flag)}</span>
            <span>{qualityTraceMetadataDetail}</span>
            <p>后端返回 bond_count 为 0，页面不会在前端补算正式指标；请核对持仓快照、风险张量物化任务和元数据证据。</p>
            <div className="risk-tensor-quality-detail__trace-actions">
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
              >
                定位元数据
              </button>
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={handleCopyEmptyPosition}
              >
                复制空持仓排查信息
              </button>
            </div>
            {emptyPositionCopyMessage ? (
              <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                {emptyPositionCopyMessage}
              </small>
            ) : null}
            {emptyPositionCopyStatus === "failed" ? (
              <pre
                className="risk-tensor-quality-detail__manual-copy"
                data-testid="risk-tensor-empty-position-manual-copy"
                tabIndex={0}
              >
                {emptyPositionCopyText}
              </pre>
            ) : null}
          </div>
        ) : result ? (
          <>
            <section className="risk-tensor-brief" data-testid="risk-tensor-brief">
              <div className="risk-tensor-brief__lead" data-tone={qualityTone(result.quality_flag)}>
                <span>风险判读</span>
                <h2>{topLineSummary}</h2>
                <p>
                  {result.prior_period_change?.summary ??
                    result.dv01_controls?.operating_judgement ??
                    "暂无可比上期，当前仅展示截面风险读数。"}
                </p>
                {conclusionNeedsQualityReview ? (
                  <button
                    type="button"
                    className="risk-tensor-brief__review-button"
                    data-testid="risk-tensor-quality-review-action"
                    onClick={handleQualityDetailJump}
                  >
                    结论需复核：数据状态为{qualityFlagLabel(result.quality_flag)}；原因：{qualityReviewReasonSummary}
                  </button>
                ) : null}
                {result.warnings.length > 0 ? (
                  <ul aria-label="risk tensor warnings">
                    {result.warnings.slice(0, 2).map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                    {result.warnings.length > 2 ? (
                      <li>
                        <button
                          type="button"
                          className="risk-tensor-brief__link-button"
                          data-testid="risk-tensor-quality-detail-action"
                          onClick={handleQualityDetailJump}
                        >
                          另有 {result.warnings.length - 2} 条预警见下方质量明细。
                        </button>
                      </li>
                    ) : null}
                  </ul>
                ) : null}
                <div className="risk-tensor-brief__badges" aria-label="risk tensor data status">
                  <span>报告日 {result.report_date}</span>
                  <span>{tensorMeta?.basis ?? "formal"} 口径</span>
                  <span>{fallbackStatus}</span>
                  <span>{blockedReportDateSummary}</span>
                </div>
              </div>

              <div className="risk-tensor-brief__tiles">
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-primary-tenor-action"
                  data-tone="neutral"
                  onClick={handlePrimaryTenorDrill}
                >
                  <span>主风险桶</span>
                  <strong>{primaryTenor}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    KRD {primaryTenorValue}，按后端 KRD 桶绝对值定位。
                  </span>
                </button>
                {result.dv01_controls ? (
                  <button
                    type="button"
                    className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                    data-testid="risk-tensor-dv01-controls-action"
                    data-tone="warning"
                    onClick={handleDv01ControlsJump}
                  >
                    <span>DV01 控制</span>
                    <strong>{dv01ControlStatusLabel(result.dv01_controls.limit_status)}</strong>
                    <span className="risk-tensor-brief__tile-detail">
                      监管口径 {regulatoryDv01DisplayWithUnit(result.regulatory_dv01)}；{result.dv01_controls.control_message}
                    </span>
                  </button>
                ) : (
                  <article className="risk-tensor-brief__tile" data-tone="warning">
                    <span>DV01 控制</span>
                    <strong>控制未接入</strong>
                    <p>监管口径 {regulatoryDv01DisplayWithUnit(result.regulatory_dv01)}；后端未返回限额控制载荷。</p>
                  </article>
                )}
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-liquidity-action"
                  data-tone={liquidityGapTone(liquidity30dRaw)}
                  onClick={handleLiquidityDetailJump}
                >
                  <span>流动性</span>
                  <strong>{ratioPercentDisplay(result.liquidity_gap_30d_ratio)}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    {yuanAsYiWithUnit(result.liquidity_gap_30d)} = 30 日资产现金流 - 负债现金流。
                  </span>
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-issuer-concentration-action"
                  data-tone="neutral"
                  onClick={handleIssuerConcentrationJump}
                >
                  <span>发行人集中度</span>
                  <strong>{ratioPercentDisplay(result.issuer_top5_weight)}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    前五大权重；HHI {displayStr(result.issuer_concentration_hhi)}。
                  </span>
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-data-status-action"
                  data-tone={qualityTone(result.quality_flag)}
                  onClick={handleQualityDetailJump}
                >
                  <span>数据状态</span>
                  <strong>{qualityFlagLabel(result.quality_flag)}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    来源 {compactVersion(tensorMeta?.source_version)}；规则 {compactVersion(tensorMeta?.rule_version)}；
                    {fallbackStatus}；{blockedReportDateSummary}。
                  </span>
                </button>
                {actionTileCanJump ? (
                  <button
                    type="button"
                    className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                    data-testid="risk-tensor-required-action"
                    data-tone={actionTileTone}
                    onClick={handleRequiredInformationJump}
                  >
                    <span>待补信息</span>
                    <strong>{requiredActionSummary(result.dv01_controls?.control_actions)}</strong>
                    <span className="risk-tensor-brief__tile-detail">{actionTileDetail}</span>
                  </button>
                ) : (
                  <article className="risk-tensor-brief__tile" data-tone={actionTileTone}>
                    <span>待补信息</span>
                    <strong>{requiredActionSummary(result.dv01_controls?.control_actions)}</strong>
                    <p>{actionTileDetail}</p>
                  </article>
                )}
              </div>
            </section>

            {payloadQualityIssues.length > 0 ? (
              <div className="risk-tensor-payload-quality" data-testid="risk-tensor-payload-quality-warning">
                <strong>主读 payload 字段待核对</strong>
                <span>报告日 {result.report_date}</span>
                <span>trace_id {tensorMeta?.trace_id ?? "未提供"}</span>
                <span>字段 {payloadQualityIssueSummary}</span>
                <span>{qualityTraceMetadataDetail}</span>
                <p>
                  后端主读返回了缺失或不可解析字段；页面只保留后端原始展示/占位，不会在前端补算正式指标，请结合下方
                  result_meta 与质量证据复核。
                </p>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  data-testid="risk-tensor-payload-quality-review-action"
                  onClick={handlePayloadChecklistJump}
                >
                  查看字段复核与补证请求
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  data-testid="risk-tensor-payload-quality-meta-action"
                  onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
                >
                  查看 result_meta
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  onClick={handleCopyPayloadQualityRequest}
                >
                  复制字段补证请求
                </button>
                {missingQualityEvidenceLabels.length > 0 ? (
                  <>
                    <button
                      type="button"
                      className="risk-tensor-brief__link-button"
                      onClick={handleCopyQualityEvidenceRequest}
                    >
                      复制证据补证请求
                    </button>
                    <button
                      type="button"
                      className="risk-tensor-brief__link-button"
                      onClick={handleCopyCombinedQualityRequest}
                    >
                      复制完整补证包
                    </button>
                  </>
                ) : null}
                {payloadQualityRequestCopyMessage ? (
                  <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                    {payloadQualityRequestCopyMessage}
                  </small>
                ) : null}
                {qualityEvidenceRequestCopyMessage ? (
                  <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                    {qualityEvidenceRequestCopyMessage}
                  </small>
                ) : null}
                {combinedQualityRequestCopyMessage ? (
                  <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                    {combinedQualityRequestCopyMessage}
                  </small>
                ) : null}
                {qualityEvidenceRequestCopyStatus === "failed" ? (
                  <pre
                    className="risk-tensor-quality-detail__manual-copy"
                    data-testid="risk-tensor-quality-evidence-warning-request-manual-copy"
                    tabIndex={0}
                  >
                    {qualityEvidenceRequestCopyText}
                  </pre>
                ) : null}
                {combinedQualityRequestCopyStatus === "failed" ? (
                  <pre
                    className="risk-tensor-quality-detail__manual-copy"
                    data-testid="risk-tensor-combined-quality-warning-request-manual-copy"
                    tabIndex={0}
                  >
                    {combinedQualityRequestCopyText}
                  </pre>
                ) : null}
                {payloadQualityRequestCopyStatus === "failed" ? (
                  <pre
                    className="risk-tensor-quality-detail__manual-copy"
                    data-testid="risk-tensor-payload-quality-warning-manual-copy"
                    tabIndex={0}
                  >
                    {payloadQualityRequestCopyText}
                  </pre>
                ) : null}
              </div>
            ) : null}

            <div data-testid="risk-tensor-kpi-grid" style={summaryGridStyle}>
              <KpiCard
                title="估值口径 DV01"
                value={yuanAsWanDisplay(result.portfolio_dv01)}
                detail="portfolio_dv01，持仓估值敏感性口径，非监管限额口径。"
                unit={WAN_YUAN_UNIT}
                tone={toneFromSignedDisplayString(yuanAsWanDisplay(result.portfolio_dv01))}
              />
              <KpiCard
                title="监管口径 DV01"
                value={regulatoryDv01Display(result.regulatory_dv01)}
                detail="后端监管/限额口径字段；不得用估值 DV01 替代。"
                unit={amountUnit(result.regulatory_dv01, WAN_YUAN_UNIT)}
                tone={regulatoryDv01Tone(result.regulatory_dv01)}
              />
              <KpiCard
                title="修正久期"
                value={displayStr(result.portfolio_modified_duration)}
                detail="portfolio_modified_duration；按利率风险适用资产加权。"
                unit="年"
              />
              <KpiCard
                title="CS01"
                value={yuanAsWanDisplay(result.cs01)}
                detail="cs01（信用 spread DV01 聚合）。"
                unit={WAN_YUAN_UNIT}
                tone={toneFromSignedDisplayString(yuanAsWanDisplay(result.cs01))}
              />
              <KpiCard
                title="组合凸性"
                value={displayStr(result.portfolio_convexity)}
                detail="portfolio_convexity。"
                tone={toneFromSignedDisplayString(displayStr(result.portfolio_convexity))}
              />
              <KpiCard
                title="债券只数"
                value={String(result.bond_count)}
                detail="bond_count。"
                unit="只"
              />
              <KpiCard
                title="总市值"
                value={yuanAsYiDisplay(result.total_market_value)}
                detail="total_market_value。"
                unit={YI_YUAN_UNIT}
                tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.total_market_value))}
              />
            </div>

            {showDurationScope ? (
              <section className="risk-tensor-duration-scope" data-testid="risk-tensor-duration-scope">
                <div className="risk-tensor-duration-scope__header">
                  <span>久期口径</span>
                  <h2>利率风险适用资产覆盖</h2>
                  <p>
                    组合久期只按有到期日且正久期的资产加权；无到期日或零久期资产不造期限，DV01 仍保留在总量。
                  </p>
                </div>
                <div className="risk-tensor-duration-scope__grid">
                  <KpiCard
                    title="利率风险市值"
                    value={yuanAsYiDisplay(result.rate_risk_market_value)}
                    detail="rate_risk_market_value；进入久期分母的市值。"
                    unit={YI_YUAN_UNIT}
                    tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.rate_risk_market_value))}
                  />
                  <KpiCard
                    title="利率风险 DV01"
                    value={yuanAsWanDisplay(result.rate_risk_dv01)}
                    detail="rate_risk_dv01；进入久期分母的 DV01。"
                    unit={amountUnit(result.rate_risk_dv01, WAN_YUAN_UNIT)}
                    tone={toneFromSignedDisplayString(yuanAsWanDisplay(result.rate_risk_dv01))}
                  />
                  <KpiCard
                    title="利率风险久期"
                    value={displayStr(result.rate_risk_modified_duration)}
                    detail="rate_risk_modified_duration；应与修正久期一致。"
                    unit={amountUnit(result.rate_risk_modified_duration, "年")}
                  />
                  <KpiCard
                    title="久期排除市值"
                    value={yuanAsYiDisplay(result.duration_excluded_market_value)}
                    detail={`duration_excluded_market_value；排除行数 ${countDisplay(result.duration_excluded_count)}。`}
                    unit={amountUnit(result.duration_excluded_market_value, YI_YUAN_UNIT)}
                    tone={durationExclusionTone(result)}
                  />
                </div>
              </section>
            ) : null}

            {result.prior_period_change ? (
              <section className="risk-tensor-prior-change" data-testid="risk-tensor-prior-period-change">
                <div className="risk-tensor-prior-change__header">
                  <div>
                    <span>较上期变化</span>
                    <h2>风险变化判断</h2>
                  </div>
                  <strong>
                    {result.prior_period_change.comparison_report_date
                      ? `对比 ${result.prior_period_change.comparison_report_date}`
                      : "暂无可比日期"}
                  </strong>
                </div>
                <p className="risk-tensor-prior-change__summary">{result.prior_period_change.summary}</p>
                {result.prior_period_change.metrics.length > 0 ? (
                  <div className="risk-tensor-prior-change__metrics">
                    {result.prior_period_change.metrics.map((metric) => {
                      const targetTestId = priorChangeTargetFor(metric.key);
                      const metricContent = (
                        <>
                          <span className="risk-tensor-prior-change__metric-label">{metric.label}</span>
                          <strong>{priorMetricDisplay(metric, "delta")}</strong>
                          <span className="risk-tensor-prior-change__metric-detail">{metric.interpretation}</span>
                          <span className="risk-tensor-prior-change__metric-values">
                            当前 {priorMetricDisplay(metric, "current")} / 上期 {priorMetricDisplay(metric, "previous")}
                          </span>
                        </>
                      );
                      if (!targetTestId) {
                        return (
                          <article
                            className="risk-tensor-prior-change__metric"
                            data-tone={priorMetricTone(metric.tone)}
                            key={metric.key}
                          >
                            {metricContent}
                          </article>
                        );
                      }
                      return (
                        <button
                          className="risk-tensor-prior-change__metric"
                          data-testid={`risk-tensor-prior-change-action-${metric.key}`}
                          data-tone={priorMetricTone(metric.tone)}
                          key={metric.key}
                          type="button"
                          onClick={() => handleSectionJump(targetTestId)}
                        >
                          {metricContent}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </section>
            ) : null}

            {result.dv01_controls ? (
              <section className="risk-tensor-dv01-controls" data-testid="risk-tensor-dv01-controls">
                <div className="risk-tensor-dv01-controls__header">
                  <div>
                    <span className="risk-tensor-dv01-controls__eyebrow">DV01 控制</span>
                    <h2>DV01 限额与波动</h2>
                  </div>
                  <div className="risk-tensor-dv01-controls__status">
                    <span>{dv01ControlStatusLabel(result.dv01_controls.limit_status)}</span>
                    <strong>{dv01ControlStatusDescription(result.dv01_controls.limit_status)}</strong>
                  </div>
                </div>

                <div className="risk-tensor-dv01-controls__grid">
                  <div className="risk-tensor-dv01-controls__primary">
                    <span>监管口径 DV01</span>
                    <strong>{regulatoryDv01DisplayWithUnit(result.regulatory_dv01)}</strong>
                    <p>{result.dv01_controls.control_message}</p>
                  </div>
                  <div className="risk-tensor-dv01-controls__cell">
                    <span>审批限额</span>
                    <strong>{yuanAsWanWithUnit(result.dv01_controls.approved_limit_dv01 ?? undefined)}</strong>
                    <p>未接入正式限额前，不判定使用率。</p>
                  </div>
                  <div className="risk-tensor-dv01-controls__cell">
                    <span>限额使用率</span>
                    <strong>{ratioPercentDisplay(result.dv01_controls.limit_usage_ratio)}</strong>
                    <p>等待限额源配置后计算。</p>
                  </div>
                  <div className="risk-tensor-dv01-controls__cell">
                    <span>主风险桶</span>
                    <strong>{result.dv01_controls.dominant_krd_bucket}</strong>
                    <p>KRD {yuanAsWanWithUnit(result.dv01_controls.dominant_krd)}</p>
                  </div>
                  <div className="risk-tensor-dv01-controls__cell">
                    <span>利率波动</span>
                    <strong>{dv01VolatilityLabel(result.dv01_controls.volatility_status)}</strong>
                    <p>{dv01VolatilityDescription(result.dv01_controls.volatility_status)}</p>
                  </div>
                </div>

                <div
                  className="risk-tensor-dv01-controls__stress"
                  data-testid="risk-tensor-dv01-stress-scenarios"
                  aria-label="DV01 stress scenarios"
                >
                  {result.dv01_controls.stress_scenarios.length > 0 ? (
                    result.dv01_controls.stress_scenarios.map((scenario) => (
                      <div className="risk-tensor-dv01-controls__scenario" key={scenario.scenario_key}>
                        <span>{scenario.label}</span>
                        <strong>{yuanAsWanWithUnit(scenario.estimated_pnl_impact)}</strong>
                        <p>{displayStr(scenario.shock_bp)} 平行冲击</p>
                      </div>
                    ))
                  ) : (
                    <div className="risk-tensor-dv01-controls__empty" data-testid="risk-tensor-dv01-stress-empty">
                      <span>暂无压力情景</span>
                      <p>后端 stress_scenarios 为空，请补充正式压力情景后再判断 DV01 冲击损益。</p>
                    </div>
                  )}
                </div>

                <div className="risk-tensor-dv01-controls__judgement">
                  <span>经营判断</span>
                  <p>{result.dv01_controls.operating_judgement}</p>
                </div>

                {result.dv01_controls.control_actions.length > 0 ? (
                  <div
                    className="risk-tensor-dv01-controls__actions"
                    data-testid="risk-tensor-dv01-actions"
                    aria-label="DV01 control actions"
                  >
                    {result.dv01_controls.control_actions.map((item) => (
                      <article className="risk-tensor-dv01-controls__action-card" key={item.key}>
                        <div>
                          <span>{dv01ControlActionStatusLabel(item.status)}</span>
                          <strong>{item.title}</strong>
                        </div>
                        <p>{item.evidence}</p>
                        <p>{item.action}</p>
                      </article>
                    ))}
                  </div>
                ) : null}

                <p className="risk-tensor-dv01-controls__action">{result.dv01_controls.action_hint}</p>
              </section>
            ) : null}

            <div style={chartRowStyle}>
              <div style={chartColumnStyle}>
                <div data-testid="risk-tensor-radar-card" style={radarCardStyle}>
                  <div
                    style={{
                      marginBottom: 8,
                      fontSize: 15,
                      fontWeight: 600,
                      color: t.colorTextPrimary,
                    }}
                  >
                    风险张量雷达
                  </div>
                  {radarChartOption ? (
                    <ReactECharts
                      option={radarChartOption}
                      style={{ height: 400, width: "100%" }}
                    />
                  ) : null}
                  {invalidRadarRows.length > 0 ? (
                    <div className="risk-tensor-radar-quality" data-testid="risk-tensor-radar-quality-note">
                      {invalidRadarRows.map((row) => `${row.key} ${row.issue}`).join(" / ")}
                      ；未参与前端雷达图数值。
                    </div>
                  ) : null}
                  {radarNavigationItems.length > 0 ? (
                    <div className="risk-tensor-radar-actions" aria-label="risk tensor radar dimension navigation">
                      {radarNavigationItems.map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          data-testid={`risk-tensor-radar-action-${item.key}`}
                          onClick={() => handleSectionJump(item.targetTestId)}
                        >
                          {item.name}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
              <div style={chartColumnStyle}>
                <h2
                  style={{
                    margin: "0 0 12px",
                    fontSize: 16,
                    fontWeight: 600,
                    color: "#162033",
                  }}
                >
                  KRD 分档（估值 DV01）
                </h2>
              {krdChartOption ? (
                <ReactECharts
                  option={krdChartOption}
                  onEvents={{ click: handleKrdChartClick }}
                  style={{ height: 320, width: "100%" }}
                />
              ) : null}

              {selectedTenorRow ? (
                <div data-testid="risk-tensor-tenor-drill" style={drillPanelStyle}>
                  <div style={{ color: t.colorTextPrimary, fontSize: 15, fontWeight: 600 }}>
                    期限桶下钻
                  </div>
                  <div style={{ color: t.colorTextSecondary, fontSize: 13, marginTop: 6 }}>
                    先用现有风险张量 payload 中可解析的 KRD 字段选择最强期限桶，再查看该桶的敏感度读数。
                  </div>
                  {invalidKrdRows.length > 0 ? (
                    <div className="risk-tensor-tenor-drill__quality" data-testid="risk-tensor-krd-quality-note">
                      {invalidKrdRows.map((row) => `${row.key} ${riskTensorScalarIssue(row.value) ?? "不可解析"}`).join(" / ")}
                      ；未参与前端主风险桶排序和图表数值。
                    </div>
                  ) : null}
                  <div style={chipRowStyle}>
                    {tenorRows.map((row) => (
                      <button
                        key={row.tenor}
                        aria-pressed={row.tenor === selectedTenor}
                        type="button"
                        style={chipButtonStyle(row.tenor === selectedTenor)}
                        onClick={() => setSelectedTenor(row.tenor)}
                      >
                        {row.tenor}
                      </button>
                    ))}
                  </div>
                  <div style={{ marginTop: 14, color: t.colorTextPrimary, fontSize: 14 }}>
                    当前桶：<strong>{selectedTenorRow.tenor}</strong>
                  </div>
                  <div style={{ marginTop: 8, color: t.colorTextSecondary, fontSize: 13 }}>
                    KRD：{yuanAsWanWithUnit(selectedTenorRow.value)}
                  </div>
                </div>
              ) : null}
            </div>
          </div>

            <section data-testid="risk-tensor-issuer-concentration-detail" aria-label="发行人集中度明细">
              <h2 className="risk-tensor-section-heading">
                发行人集中度
              </h2>
              <div className="risk-tensor-summary-grid">
                <KpiCard
                  title="发行人 HHI"
                  value={displayStr(result.issuer_concentration_hhi)}
                  detail="issuer_concentration_hhi。"
                  testId="risk-tensor-issuer-hhi"
                />
                <KpiCard
                  title="前五大权重"
                  value={ratioPercentDisplay(result.issuer_top5_weight)}
                  detail="issuer_top5_weight。"
                />
              </div>
            </section>

            <section data-testid="risk-tensor-liquidity-gap-detail" aria-label="流动性现金流缺口明细">
              <h2 className="risk-tensor-section-heading">
                流动性现金流缺口
              </h2>
              <div className="risk-tensor-summary-grid">
                <KpiCard
                  title="30 日资产现金流 - 负债现金流"
                  value={yuanAsYiDisplay(result.liquidity_gap_30d)}
                  detail="liquidity_gap_30d。"
                  unit={YI_YUAN_UNIT}
                  tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.liquidity_gap_30d))}
                />
                <KpiCard
                  title="90 日资产现金流 - 负债现金流"
                  value={yuanAsYiDisplay(result.liquidity_gap_90d)}
                  detail="liquidity_gap_90d。"
                  unit={YI_YUAN_UNIT}
                  tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.liquidity_gap_90d))}
                />
                <KpiCard
                  title="30 日流动性缺口比例"
                  value={ratioPercentDisplay(result.liquidity_gap_30d_ratio)}
                  detail="liquidity_gap_30d_ratio。"
                  tone={ratioTone(result.liquidity_gap_30d_ratio)}
                  testId="risk-tensor-liquidity-gap-ratio"
                />
              </div>
            </section>

            <h2
              style={{
                margin: "24px 0 12px",
                fontSize: 16,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              现金流构成
            </h2>
            <div data-testid="risk-tensor-cashflow-grid" style={summaryGridStyle}>
              <KpiCard
                title="30 日资产现金流"
                value={yuanAsYiDisplay(result.asset_cashflow_30d)}
                detail="asset_cashflow_30d。"
                unit={YI_YUAN_UNIT}
              />
              <KpiCard
                title="30 日负债现金流"
                value={yuanAsYiDisplay(result.liability_cashflow_30d)}
                detail="liability_cashflow_30d。"
                unit={YI_YUAN_UNIT}
              />
              <KpiCard
                title="90 日资产现金流"
                value={yuanAsYiDisplay(result.asset_cashflow_90d)}
                detail="asset_cashflow_90d。"
                unit={YI_YUAN_UNIT}
              />
              <KpiCard
                title="90 日负债现金流"
                value={yuanAsYiDisplay(result.liability_cashflow_90d)}
                detail="liability_cashflow_90d。"
                unit={YI_YUAN_UNIT}
              />
            </div>

            <div
              data-testid="risk-tensor-quality-detail"
              style={{
                marginTop: 20,
                padding: 12,
                borderRadius: 12,
                border:
                  result.quality_flag === "ok"
                    ? "1px solid #d7dfea"
                    : "1px solid #e8d9a8",
                background: result.quality_flag === "ok" ? "#f6f9fc" : "#fffbeb",
                color: "#162033",
                fontSize: 14,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                质量标记：
                {result.quality_flag === "ok"
                  ? "正常"
                  : result.quality_flag === "warning"
                    ? "预警"
                    : result.quality_flag === "error"
                      ? "错误"
                      : result.quality_flag === "stale"
                        ? "陈旧"
                        : result.quality_flag}
              </div>
              <div className="risk-tensor-quality-detail__evidence" data-testid="risk-tensor-quality-evidence">
                <strong>证据范围</strong>
                <span>trace_id {tensorMeta?.trace_id ?? "未提供"}</span>
                <span>basis {tensorMeta?.basis ?? "未提供"}</span>
                <span>cache_version {tensorMeta?.cache_version ?? "未提供"}</span>
                <span>generated_at {tensorMeta?.generated_at ?? "未提供"}</span>
                <span>来源 {compactVersion(tensorMeta?.source_version)}</span>
                <span>规则 {compactVersion(tensorMeta?.rule_version)}</span>
                <span>{fallbackStatus}</span>
                {tensorMeta?.fallback_date ? <span>fallback_date {tensorMeta.fallback_date}</span> : null}
                <span>{blockedReportDateSummary}</span>
                <span>evidence_rows {typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "未提供"}</span>
                <span>tables_used {metadataTablesUsed || "未提供"}</span>
                <span>filters_applied {metadataFiltersApplied || "未提供"}</span>
              </div>
              <div className="risk-tensor-quality-detail__trace" data-testid="risk-tensor-quality-trace-priority">
                <strong>证据优先级</strong>
                <div className="risk-tensor-quality-detail__review-state" aria-live="polite">
                  复核状态：{qualityReviewStateLabel}
                </div>
                <ol>
                  <li>
                    <span>source/rule</span>
                    <p>
                      来源 {compactVersion(tensorMeta?.source_version)}；规则 {compactVersion(tensorMeta?.rule_version)}
                    </p>
                  </li>
                  <li>
                    <span>fallback</span>
                    <p>{qualityTraceFallbackDetail}</p>
                  </li>
                  <li>
                    <span>陈旧日期</span>
                    <p>{qualityTraceBlockedDetail}</p>
                  </li>
                  <li>
                    <span>warning</span>
                    <p>{qualityTraceWarningDetail}</p>
                  </li>
                  <li>
                    <span>证据范围</span>
                    <p>{qualityTraceMetadataDetail}</p>
                    <div className="risk-tensor-quality-detail__trace-actions">
                      <button
                        type="button"
                        className="risk-tensor-quality-detail__trace-action"
                        onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
                      >
                        定位元数据
                      </button>
                      <button
                        type="button"
                        className="risk-tensor-quality-detail__trace-action"
                        onClick={handleCopyQualityEvidence}
                      >
                        复制证据
                      </button>
                    </div>
                    {qualityEvidenceCopyMessage ? (
                      <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                        {qualityEvidenceCopyMessage}
                      </small>
                    ) : null}
                    {qualityEvidenceCopyStatus === "failed" ? (
                      <pre
                        className="risk-tensor-quality-detail__manual-copy"
                        data-testid="risk-tensor-quality-evidence-manual-copy"
                        tabIndex={0}
                      >
                        {qualityTraceCopyText}
                      </pre>
                    ) : null}
                    <div className="risk-tensor-quality-detail__evidence-checklist">
                      <strong>证据字段复核</strong>
                      <ul>
                        {qualityEvidenceReviewItems.map((item) => (
                          <li key={item.key} data-status={item.status === "已提供" ? "provided" : "missing"}>
                            <span>{item.label} </span>
                            <b>{item.status}</b>
                          </li>
                        ))}
                      </ul>
                      {canConfirmQualityEvidenceReview ? (
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleConfirmQualityEvidenceReview}
                          >
                            确认业务复核
                          </button>
                        </div>
                      ) : null}
                      {qualityEvidenceReviewConfirmed ? (
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleCopyQualityEvidenceReviewRecord}
                          >
                            复制确认记录
                          </button>
                          {qualityEvidenceReviewRecordCopyMessage ? (
                            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                              {qualityEvidenceReviewRecordCopyMessage}
                            </small>
                          ) : null}
                          {qualityEvidenceReviewRecordCopyStatus === "failed" ? (
                            <pre
                              className="risk-tensor-quality-detail__manual-copy"
                              data-testid="risk-tensor-quality-evidence-review-record-manual-copy"
                              tabIndex={0}
                            >
                              {qualityEvidenceReviewRecordCopyText}
                            </pre>
                          ) : null}
                        </div>
                      ) : null}
                      {hasMissingQualityEvidence ? (
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleCopyQualityEvidenceRequest}
                          >
                            复制补证请求
                          </button>
                          {qualityEvidenceRequestCopyMessage ? (
                            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                              {qualityEvidenceRequestCopyMessage}
                            </small>
                          ) : null}
                          {qualityEvidenceRequestCopyStatus === "failed" ? (
                            <pre
                              className="risk-tensor-quality-detail__manual-copy"
                              data-testid="risk-tensor-quality-evidence-request-manual-copy"
                              tabIndex={0}
                            >
                              {qualityEvidenceRequestCopyText}
                            </pre>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    {payloadQualityIssues.length > 0 ? (
                      <div
                        className="risk-tensor-quality-detail__payload-checklist"
                        data-testid="risk-tensor-quality-payload-checklist"
                      >
                        <strong>主读 payload 字段复核</strong>
                        <p>trace_id {tensorMeta?.trace_id ?? "未提供"}；不会在前端补算正式指标。</p>
                        <ul>
                          {payloadQualityIssues.map((item) => (
                            <li key={item.key}>
                              <span>{item.label}</span>
                              <b>{item.issue}</b>
                            </li>
                          ))}
                        </ul>
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleCopyPayloadQualityRequest}
                          >
                            复制字段补证请求
                          </button>
                          {payloadQualityRequestCopyMessage ? (
                            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                              {payloadQualityRequestCopyMessage}
                            </small>
                          ) : null}
                          {payloadQualityRequestCopyStatus === "failed" ? (
                            <pre
                              className="risk-tensor-quality-detail__manual-copy"
                              data-testid="risk-tensor-payload-quality-request-manual-copy"
                              tabIndex={0}
                            >
                              {payloadQualityRequestCopyText}
                            </pre>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </li>
                </ol>
              </div>
              {highlightedBlockedReportDate ? (
                <div className="risk-tensor-quality-detail__blocked" data-testid="risk-tensor-quality-blocked-date">
                  <strong>{highlightedBlockedReportDate.report_date}</strong>
                  <span>{highlightedBlockedReportDate.reason}</span>
                </div>
              ) : null}
              {result.warnings.length === 0 ? (
                <div style={{ color: "#5c6b82" }}>无预警。</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: 20, color: "#5c6b82" }}>
                  {result.warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              )}
            </div>
          </>
        ) : null}
      </AsyncSection>

      <FormalResultMetaPanel
        testId="risk-tensor-result-meta-panel"
        sections={[
          { key: "dates", title: "风险报告日列表", meta: datesQuery.data?.result_meta },
          { key: "tensor", title: "风险张量主读面", meta: envelope?.result_meta },
        ]}
      />
    </section>
  );
}
