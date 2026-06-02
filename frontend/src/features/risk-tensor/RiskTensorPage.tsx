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
import type { Numeric, ResultMeta, RiskTensorPayload } from "../../api/contracts";
import {
  parseDisplayNumber,
  toneFromSignedDisplayString,
} from "../workbench/components/kpiFormat";
import {
  bondChartMagnitude,
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

const YUAN_PER_WAN = 10_000;
const YUAN_PER_YI = 100_000_000;
const WAN_YUAN_UNIT = "\u4e07\u5143";
const YI_YUAN_UNIT = "\u4ebf\u5143";

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

function yuanAsWanMagnitude(value: RiskTensorDisplayValue) {
  const raw = riskTensorRawOrNull(value);
  return raw === null ? 0 : raw / YUAN_PER_WAN;
}

function isWanAmountMetric(key: string) {
  return key === "portfolio_dv01" || key === "regulatory_dv01" || key === "cs01" || key.startsWith("krd_");
}

function priorMetricDisplay(metric: RiskTensorPayload["prior_period_change"]["metrics"][number], key: PriorMetricValueKey) {
  if (!isWanAmountMetric(metric.key)) {
    const displayKey = `${key}_display` as const;
    return metric[displayKey];
  }
  return yuanAsWanWithUnit(metric[key] as Numeric);
}

function chartMagnitude(value: Parameters<typeof bondChartMagnitude>[0]) {
  return bondChartMagnitude(value);
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

function fallbackModeLabel(mode: ResultMeta["fallback_mode"] | undefined) {
  if (mode === "none") {
    return "未降级";
  }
  if (mode === "latest") {
    return "latest fallback";
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
  return base;
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
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const [selectedTenor, setSelectedTenor] = useState<string>("");

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

  const datesBlockingError = datesQuery.isError && !reportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;

  const tensorQuery = useQuery({
    queryKey: ["risk-tensor", reportDate],
    queryFn: () => client.getRiskTensor(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const envelope = tensorQuery.data;
  const result = envelope?.result;
  const isEmpty =
    !tensorQuery.isLoading &&
    !tensorQuery.isError &&
    result !== undefined &&
    result.bond_count === 0;

  const krdChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const labels = ["1Y", "3Y", "5Y", "7Y", "10Y", "30Y"];
    const keys = [
      "krd_1y",
      "krd_3y",
      "krd_5y",
      "krd_7y",
      "krd_10y",
      "krd_30y",
    ] as const;
    const data = keys.map((key) => yuanAsWanMagnitude(result[key]));
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
    return [
      { tenor: "1Y", value: result.krd_1y },
      { tenor: "3Y", value: result.krd_3y },
      { tenor: "5Y", value: result.krd_5y },
      { tenor: "7Y", value: result.krd_7y },
      { tenor: "10Y", value: result.krd_10y },
      { tenor: "30Y", value: result.krd_30y },
    ];
  }, [result]);

  useEffect(() => {
    if (tenorRows.length === 0) {
      setSelectedTenor("");
      return;
    }
    const strongest = [...tenorRows].sort(
      (left, right) => chartMagnitude(right.value) - chartMagnitude(left.value),
    )[0]?.tenor;
    if (!selectedTenor || !tenorRows.some((row) => row.tenor === selectedTenor)) {
      setSelectedTenor(strongest ?? tenorRows[0]!.tenor);
    }
  }, [selectedTenor, tenorRows]);

  const selectedTenorRow = tenorRows.find((row) => row.tenor === selectedTenor) ?? tenorRows[0];
  const tensorMeta = envelope?.result_meta;
  const primaryTenor = selectedTenorRow?.tenor ?? result?.dv01_controls?.dominant_krd_bucket ?? "--";
  const primaryTenorValue = selectedTenorRow
    ? yuanAsWanWithUnit(selectedTenorRow.value)
    : result?.dv01_controls
      ? yuanAsWanWithUnit(result.dv01_controls.dominant_krd)
      : "--";
  const liquidity30dRaw = result ? bondNumericRawOrNull(result.liquidity_gap_30d) : null;
  const requiredActions = result?.dv01_controls?.control_actions.filter((item) => item.status === "required") ?? [];
  const firstRequiredAction = requiredActions[0];
  const actionTileTone = !result?.dv01_controls || requiredActions.length > 0 ? "warning" : "ok";
  const topLineSummary = result
    ? [
        `主风险桶 ${primaryTenor}`,
        liquidityGapLabel(liquidity30dRaw),
        `质量标记：${qualityFlagLabel(result.quality_flag)}`,
      ].join(" / ")
    : "";

  const radarChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const duration = chartMagnitude(result.portfolio_modified_duration);
    const dv01 = yuanAsWanMagnitude(result.portfolio_dv01);
    const convexity = chartMagnitude(result.portfolio_convexity);
    const cs01 = yuanAsWanMagnitude(result.cs01);
    const hhi = chartMagnitude(result.issuer_concentration_hhi);
    const liqRatio = chartMagnitude(result.liquidity_gap_30d_ratio);

    const dv01Max = dynamicAxisMax(dv01, 1);
    const cs01Max = dynamicAxisMax(cs01, 1);

    const indicator = RADAR_META.map((m) => {
      if (m.max === "dynamic_dv01") {
        return { name: m.name, max: dv01Max };
      }
      if (m.max === "dynamic_cs01") {
        return { name: m.name, max: cs01Max };
      }
      return { name: m.name, max: m.max };
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

      <AsyncSection
        title="组合风险张量"
        isLoading={datesQuery.isLoading || tensorQuery.isLoading}
        isError={datesBlockingError || tensorQuery.isError}
        isEmpty={datesEmpty || isEmpty}
        onRetry={() => {
          void datesQuery.refetch();
          void tensorQuery.refetch();
        }}
      >
        {result ? (
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
                {result.warnings.length > 0 ? (
                  <ul aria-label="risk tensor warnings">
                    {result.warnings.slice(0, 2).map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                ) : null}
                <div className="risk-tensor-brief__badges" aria-label="risk tensor data status">
                  <span>报告日 {result.report_date}</span>
                  <span>{tensorMeta?.basis ?? "formal"} 口径</span>
                  <span>{fallbackModeLabel(tensorMeta?.fallback_mode)}</span>
                  <span>{blockedReportDates.length} 个陈旧日期已拦截</span>
                </div>
              </div>

              <div className="risk-tensor-brief__tiles">
                <article className="risk-tensor-brief__tile" data-tone="neutral">
                  <span>主风险桶</span>
                  <strong>{primaryTenor}</strong>
                  <p>KRD {primaryTenorValue}，按后端 KRD 桶绝对值定位。</p>
                </article>
                <article className="risk-tensor-brief__tile" data-tone="warning">
                  <span>DV01 控制</span>
                  <strong>
                    {result.dv01_controls
                      ? dv01ControlStatusLabel(result.dv01_controls.limit_status)
                      : "控制未接入"}
                  </strong>
                  <p>
                    监管口径 {regulatoryDv01DisplayWithUnit(result.regulatory_dv01)}
                    {result.dv01_controls ? `；${result.dv01_controls.control_message}` : "；后端未返回限额控制载荷。"}
                  </p>
                </article>
                <article className="risk-tensor-brief__tile" data-tone={liquidityGapTone(liquidity30dRaw)}>
                  <span>流动性</span>
                  <strong>{ratioPercentDisplay(result.liquidity_gap_30d_ratio)}</strong>
                  <p>{yuanAsYiWithUnit(result.liquidity_gap_30d)} = 30 日资产现金流 - 负债现金流。</p>
                </article>
                <article className="risk-tensor-brief__tile" data-tone="neutral">
                  <span>发行人集中度</span>
                  <strong>{ratioPercentDisplay(result.issuer_top5_weight)}</strong>
                  <p>前五大权重；HHI {displayStr(result.issuer_concentration_hhi)}。</p>
                </article>
                <article className="risk-tensor-brief__tile" data-tone={qualityTone(result.quality_flag)}>
                  <span>数据状态</span>
                  <strong>{qualityFlagLabel(result.quality_flag)}</strong>
                  <p>
                    来源 {compactVersion(tensorMeta?.source_version)}；规则{" "}
                    {compactVersion(tensorMeta?.rule_version)}。
                  </p>
                </article>
                <article className="risk-tensor-brief__tile" data-tone={actionTileTone}>
                  <span>待补信息</span>
                  <strong>{requiredActionSummary(result.dv01_controls?.control_actions)}</strong>
                  <p>
                    {firstRequiredAction?.title ??
                      result.warnings[0] ??
                      "后端未返回必做控制动作，继续按质量标记和明细核对。"}
                  </p>
                </article>
              </div>
            </section>

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
                detail="portfolio_modified_duration。"
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
                    {result.prior_period_change.metrics.map((metric) => (
                      <article
                        className="risk-tensor-prior-change__metric"
                        data-tone={priorMetricTone(metric.tone)}
                        key={metric.key}
                      >
                        <span>{metric.label}</span>
                        <strong>{priorMetricDisplay(metric, "delta")}</strong>
                        <p>{metric.interpretation}</p>
                        <small>
                          当前 {priorMetricDisplay(metric, "current")} / 上期 {priorMetricDisplay(metric, "previous")}
                        </small>
                      </article>
                    ))}
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

                <div className="risk-tensor-dv01-controls__stress" aria-label="DV01 stress scenarios">
                  {result.dv01_controls.stress_scenarios.map((scenario) => (
                    <div className="risk-tensor-dv01-controls__scenario" key={scenario.scenario_key}>
                      <span>{scenario.label}</span>
                      <strong>{yuanAsWanWithUnit(scenario.estimated_pnl_impact)}</strong>
                      <p>{displayStr(scenario.shock_bp)} 平行冲击</p>
                    </div>
                  ))}
                </div>

                <div className="risk-tensor-dv01-controls__judgement">
                  <span>经营判断</span>
                  <p>{result.dv01_controls.operating_judgement}</p>
                </div>

                {result.dv01_controls.control_actions.length > 0 ? (
                  <div className="risk-tensor-dv01-controls__actions" aria-label="DV01 control actions">
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
                <ReactECharts option={krdChartOption} style={{ height: 320, width: "100%" }} />
              ) : null}

              {selectedTenorRow ? (
                <div data-testid="risk-tensor-tenor-drill" style={drillPanelStyle}>
                  <div style={{ color: t.colorTextPrimary, fontSize: 15, fontWeight: 600 }}>
                    期限桶下钻
                  </div>
                  <div style={{ color: t.colorTextSecondary, fontSize: 13, marginTop: 6 }}>
                    先用现有风险张量 payload 选择 KRD 最强的期限桶，再查看该桶的敏感度读数。
                  </div>
                  <div style={chipRowStyle}>
                    {tenorRows.map((row) => (
                      <button
                        key={row.tenor}
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

            <h2
              style={{
                margin: "24px 0 12px",
                fontSize: 16,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              集中度
            </h2>
            <div style={summaryGridStyle}>
              <KpiCard
                title="发行人 HHI"
                value={displayStr(result.issuer_concentration_hhi)}
                detail="issuer_concentration_hhi。"
                tone={
                  (() => {
                    const n = parseDisplayNumber(displayStr(result.issuer_concentration_hhi));
                    return n != null && n > 0.15 ? "warning" : "default";
                  })()
                }
              />
              <KpiCard
                title="前五大权重"
                value={ratioPercentDisplay(result.issuer_top5_weight)}
                detail="issuer_top5_weight。"
              />
            </div>

            <h2
              style={{
                margin: "24px 0 12px",
                fontSize: 16,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              流动性现金流缺口
            </h2>
            <div style={summaryGridStyle}>
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
          { key: "tensor", title: "风险张量主读面", meta: tensorQuery.data?.result_meta },
        ]}
      />
    </section>
  );
}
