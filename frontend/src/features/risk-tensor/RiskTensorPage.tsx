import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import ReactECharts, { type EChartsOption } from "../../lib/echarts";
import { useApiClient } from "../../api/client";
import { shellTokens as t } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import {
  formatRatioAsPercent,
  parseDisplayNumber,
  toneFromSignedDisplayString,
} from "../workbench/components/kpiFormat";

/** 雷达轴顺序与后端字段一一对应；max 仅用于可视化比例，不做前端金融重算。 */
const RADAR_META = [
  { key: "duration" as const, name: "久期", max: 10 },
  { key: "dv01" as const, name: "DV01", max: "dynamic_dv01" as const },
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
    border: active ? "1px solid #1f5eff" : `1px solid ${t.colorBorderSoft}`,
    background: active ? "#edf3ff" : "#ffffff",
    color: active ? "#1f5eff" : t.colorTextPrimary,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  } as const;
}

function displayStr(value: string | undefined) {
  if (value === undefined || value === "") {
    return "-";
  }
  return value;
}

function chartMagnitude(value: string) {
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

function dynamicAxisMax(raw: number, fallback: number) {
  const base = Math.abs(raw) * 1.5;
  if (!Number.isFinite(base) || base === 0) {
    return fallback;
  }
  return base;
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
    const data = keys.map((key) => chartMagnitude(result[key]));
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
          itemStyle: { color: "#1f5eff", borderRadius: [6, 6, 0, 0] },
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

  const radarChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const duration = chartMagnitude(result.portfolio_modified_duration);
    const dv01 = chartMagnitude(result.portfolio_dv01);
    const convexity = chartMagnitude(result.portfolio_convexity);
    const cs01 = chartMagnitude(result.cs01);
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
      color: ["#1f5eff"],
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
          lineStyle: { width: 1.5, color: "#1f5eff" },
          areaStyle: {
            color: "rgba(31, 94, 255, 0.15)",
          },
          itemStyle: {
            color: "#1f5eff",
            borderColor: "#1f5eff",
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
          消费正式风险张量接口，展示口径以后端 <code style={{ fontSize: 13 }}>/api/risk/tensor</code> 与
          <code style={{ fontSize: 13 }}> /api/risk/tensor/dates</code> 为准。
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
                （可用 <code style={{ fontSize: 12 }}>?report_date=YYYY-MM-DD</code> 覆盖）
              </span>
            </>
          )}
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
            <div data-testid="risk-tensor-kpi-grid" style={summaryGridStyle}>
              <KpiCard
                title="组合 DV01"
                value={displayStr(result.portfolio_dv01)}
                detail="portfolio_dv01，后端字符串口径。"
                tone={toneFromSignedDisplayString(displayStr(result.portfolio_dv01))}
              />
              <KpiCard
                title="修正久期"
                value={displayStr(result.portfolio_modified_duration)}
                detail="portfolio_modified_duration。"
                unit="年"
              />
              <KpiCard
                title="CS01"
                value={displayStr(result.cs01)}
                detail="cs01（信用 spread DV01 聚合）。"
                tone={toneFromSignedDisplayString(displayStr(result.cs01))}
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
                value={displayStr(result.total_market_value)}
                detail="total_market_value。"
                unit="亿"
                tone={toneFromSignedDisplayString(displayStr(result.total_market_value))}
              />
            </div>

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
                  KRD 分档（DV01）
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
                    KRD：{selectedTenorRow.value}
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
                value={formatRatioAsPercent(result.issuer_top5_weight, displayStr(result.issuer_top5_weight))}
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
              流动性缺口（市值）
            </h2>
            <div style={summaryGridStyle}>
              <KpiCard
                title="30 日内到期市值"
                value={displayStr(result.liquidity_gap_30d)}
                detail="liquidity_gap_30d。"
                tone={toneFromSignedDisplayString(displayStr(result.liquidity_gap_30d))}
              />
              <KpiCard
                title="90 日内到期市值"
                value={displayStr(result.liquidity_gap_90d)}
                detail="liquidity_gap_90d。"
                tone={toneFromSignedDisplayString(displayStr(result.liquidity_gap_90d))}
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
                质量标记：{result.quality_flag}
              </div>
              {result.warnings.length === 0 ? (
                <div style={{ color: "#5c6b82" }}>无 warnings。</div>
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
    </section>
  );
}
