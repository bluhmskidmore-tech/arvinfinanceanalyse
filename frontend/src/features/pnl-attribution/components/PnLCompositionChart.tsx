import { useMemo } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { Numeric, PnlCompositionPayload, PnlCompositionTrendItem } from "../../../api/contracts";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

const COLORS = {
  positive: "#2f8f63",
  neutral: "#6d7f99",
  negative: "#c1554b",
  interest: "#22c55e",
  fairValue: "#3b82f6",
  capital: "#f59e0b",
  other: "#94a3b8",
} as const;

/** API 部分响应仍可能携带 trend `other_income`，但 `PnlCompositionTrendItem` 类型尚未纳入该字段。 */
type PnlCompositionTrendRow = PnlCompositionTrendItem & { other_income?: Numeric };

function rawOr(n: { raw: number | null } | null | undefined, fallback = 0): number {
  if (!n) return fallback;
  return n.raw ?? fallback;
}

function toneColor(raw: number): string {
  if (raw > 0) return COLORS.positive;
  if (raw < 0) return COLORS.negative;
  return COLORS.neutral;
}

type Props = {
  data: PnlCompositionPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

export function PnLCompositionChart({ data, state, onRetry }: Props) {
  const bipolarOption = useMemo<EChartsOption | null>(() => {
    if (!data) return null;

    const categories = [
      {
        label: "利息收入",
        rawYuan: rawOr(data.total_interest_income),
        pct: rawOr(data.interest_pct),
      },
      {
        label: "公允价值变动",
        rawYuan: rawOr(data.total_fair_value_change),
        pct: rawOr(data.fair_value_pct),
      },
      {
        label: "投资收益",
        rawYuan: rawOr(data.total_capital_gain),
        pct: rawOr(data.capital_gain_pct),
      },
      {
        label: "其他收入",
        rawYuan: rawOr(data.total_other_income),
        pct: rawOr(data.other_pct),
      },
    ];

    const hasAny = categories.some((c) => c.rawYuan !== 0);
    if (!hasAny) return null;

    // Reverse for yAxis so the first category renders at the top.
    const reversed = [...categories].reverse();

    return {
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        formatter: (params: unknown) => {
          const entries = params as Array<{
            axisValue: string;
            data: { value: number; pct: number };
          }>;
          if (!entries || entries.length === 0) return "";
          const e = entries[0];
          if (!e) return "";
          const yi = e.data.value;
          const sign = yi >= 0 ? "+" : "";
          return `${e.axisValue}<br/>${sign}${yi.toFixed(2)} 亿（占比 ${e.data.pct.toFixed(1)}%）`;
        },
      },
      grid: { left: 90, right: 24, top: 10, bottom: 30, containLabel: true },
      xAxis: {
        type: "value" as const,
        name: "亿元",
        axisLine: { show: true, lineStyle: { color: "#c4cedc" } },
        splitLine: { lineStyle: { type: "dashed" as const, color: "#e4ebf5" } },
      },
      yAxis: {
        type: "category" as const,
        data: reversed.map((c) => c.label),
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [
        {
          type: "bar" as const,
          barWidth: 20,
          data: reversed.map((c) => ({
            value: c.rawYuan / 100_000_000,
            pct: c.pct,
            itemStyle: { color: toneColor(c.rawYuan) },
          })),
          label: {
            show: true,
            formatter: (params: { value?: unknown }) => {
              const rawValue =
                typeof params.value === "number" ? params.value : Number(params.value ?? 0);
              const v = Number.isFinite(rawValue) ? rawValue : 0;
              const sign = v >= 0 ? "+" : "";
              return `${sign}${v.toFixed(2)}`;
            },
            position: "inside" as const,
            color: "#ffffff",
            fontSize: 11,
          },
        },
      ],
    };
  }, [data]);

  const trendOption = useMemo<EChartsOption | null>(() => {
    if (!data?.trend_data?.length) return null;
    const periods = data.trend_data.map((t) =>
      (t.period_label ?? t.period).replace("年", "-").replace("月", ""),
    );
    return {
      tooltip: { trigger: "axis" as const },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: { type: "category" as const, data: periods, axisLabel: { fontSize: 11, color: "#5c6b82" } },
      yAxis: {
        type: "value" as const,
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}亿`, color: "#5c6b82" },
        splitLine: { lineStyle: { type: "dashed" as const, color: "#e8edf5" } },
      },
      series: [
        {
          name: "利息收入",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => rawOr(t.interest_income) / 100_000_000),
          itemStyle: { color: COLORS.interest },
        },
        {
          name: "公允价值变动",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => rawOr(t.fair_value_change) / 100_000_000),
          itemStyle: { color: COLORS.fairValue },
        },
        {
          name: "投资收益",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => rawOr(t.capital_gain) / 100_000_000),
          itemStyle: { color: COLORS.capital, borderRadius: [4, 4, 0, 0] },
        },
        {
          name: "其他收入",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => rawOr((t as PnlCompositionTrendRow).other_income) / 100_000_000),
          itemStyle: { color: COLORS.other, borderRadius: [4, 4, 0, 0] },
        },
      ],
    };
  }, [data]);

  const hasTableRows = (data?.items ?? []).length > 0;

  return (
    <DataSection title="损益构成" state={state} onRetry={onRetry}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {data && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: 16,
              }}
            >
              <div style={{ ...cardStyle, padding: 16 }}>
                <div style={{ fontSize: 12, color: "#5c6b82" }}>总损益</div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_pnl)),
                  }}
                >
                  {`${rawOr(data.total_pnl) >= 0 ? "+" : ""}${(rawOr(data.total_pnl) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>{data.report_period}</div>
              </div>
              <div style={{ ...cardStyle, padding: 16, background: "#e8f6ee" }}>
                <div style={{ fontSize: 12, color: "#15803d" }}>利息收入</div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_interest_income)),
                  }}
                >
                  {`${(rawOr(data.total_interest_income) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: 12, color: "#2f8f63" }}>占比 {rawOr(data.interest_pct).toFixed(1)}%</div>
              </div>
              <div style={{ ...cardStyle, padding: 16, background: "#edf3ff" }}>
                <div style={{ fontSize: 12, color: "#1f5eff" }}>公允价值变动</div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_fair_value_change)),
                  }}
                >
                  {`${rawOr(data.total_fair_value_change) >= 0 ? "+" : ""}${(rawOr(data.total_fair_value_change) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: 12, color: "#5c6b82" }}>占比 {rawOr(data.fair_value_pct).toFixed(1)}%</div>
              </div>
              <div style={{ ...cardStyle, padding: 16, background: "#fff4e8" }}>
                <div style={{ fontSize: 12, color: "#b35a16" }}>投资收益</div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_capital_gain)),
                  }}
                >
                  {`${rawOr(data.total_capital_gain) >= 0 ? "+" : ""}${(rawOr(data.total_capital_gain) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: 12, color: "#5c6b82" }}>占比 {rawOr(data.capital_gain_pct).toFixed(1)}%</div>
              </div>
              <div style={{ ...cardStyle, padding: 16, background: "#f0f3f8" }}>
                <div style={{ fontSize: 12, color: "#5c6b82" }}>其他收入</div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_other_income)),
                  }}
                >
                  {`${rawOr(data.total_other_income) >= 0 ? "+" : ""}${(rawOr(data.total_other_income) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: 12, color: "#5c6b82" }}>占比 {rawOr(data.other_pct).toFixed(1)}%</div>
              </div>
            </div>

            {bipolarOption && (
              <div style={cardStyle}>
                <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
                  损益构成（带符号 · 亿元）
                </h3>
                <ReactECharts option={bipolarOption} style={{ height: 240 }} notMerge lazyUpdate />
              </div>
            )}

            {trendOption && (
              <div style={cardStyle}>
                <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
                  损益构成趋势
                </h3>
                <ReactECharts option={trendOption} style={{ height: 300 }} notMerge lazyUpdate />
              </div>
            )}

            {hasTableRows && (
              <div style={cardStyle}>
                <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
                  分类别损益构成
                </h3>
                <div style={{ overflow: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f0f3f8" }}>
                        <th style={{ textAlign: "left", padding: 10 }}>资产类别</th>
                        <th style={{ textAlign: "right", padding: 10 }}>总损益(亿)</th>
                        <th style={{ textAlign: "right", padding: 10 }}>利息(亿)</th>
                        <th style={{ textAlign: "right", padding: 10 }}>公允(亿)</th>
                        <th style={{ textAlign: "right", padding: 10 }}>投资收益(亿)</th>
                        <th style={{ textAlign: "right", padding: 10 }}>其他(亿)</th>
                        <th style={{ textAlign: "right", padding: 10 }}>利息占比</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((item, idx) => {
                        const totalPnl = rawOr(item.total_pnl);
                        const fvChange = rawOr(item.fair_value_change);
                        const capitalGain = rawOr(item.capital_gain);
                        const otherIncome = rawOr(item.other_income);
                        return (
                          <tr key={idx} style={{ borderBottom: "1px solid #eef2f7" }}>
                            <td style={{ padding: 10, fontWeight: 500 }}>{item.category}</td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: 10,
                                color: toneColor(totalPnl),
                              }}
                            >
                              {(totalPnl / 100_000_000).toFixed(2)}
                            </td>
                            <td style={{ textAlign: "right", padding: 10, color: "#15803d" }}>
                              {(rawOr(item.interest_income) / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: 10,
                                color: toneColor(fvChange),
                              }}
                            >
                              {(fvChange / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: 10,
                                color: toneColor(capitalGain),
                              }}
                            >
                              {(capitalGain / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: 10,
                                color: toneColor(otherIncome),
                              }}
                            >
                              {(otherIncome / 100_000_000).toFixed(2)}
                            </td>
                            <td style={{ textAlign: "right", padding: 10 }}>
                              {rawOr(item.interest_pct).toFixed(1)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DataSection>
  );
}
