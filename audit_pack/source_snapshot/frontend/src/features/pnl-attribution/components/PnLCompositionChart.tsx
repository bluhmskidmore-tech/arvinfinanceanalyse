import { useMemo } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { PnlCompositionPayload } from "../../../api/contracts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
} as const;

const COLORS = {
  positive: designTokens.color.success[600],
  neutral: designTokens.color.neutral[600],
  negative: designTokens.color.danger[500],
  interest: designTokens.color.success[500],
  fairValue: designTokens.color.info[500],
  capital: designTokens.color.warning[500],
  other: designTokens.color.neutral[500],
} as const;

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
      grid: { left: 90, right: designTokens.space[6], top: 10, bottom: 30, containLabel: true },
      xAxis: {
        type: "value" as const,
        name: "亿元",
        axisLine: { show: true, lineStyle: { color: designTokens.color.neutral[300] } },
        splitLine: { lineStyle: { type: "dashed" as const, color: designTokens.color.neutral[200] } },
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
            color: designTokens.color.primary[50],
            fontSize: designTokens.fontSize[11],
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
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 48, right: designTokens.space[6], top: designTokens.space[6], bottom: 48 },
      xAxis: {
        type: "category" as const,
        data: periods,
        axisLabel: { fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          color: designTokens.color.neutral[700],
        },
        splitLine: { lineStyle: { type: "dashed" as const, color: designTokens.color.neutral[100] } },
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
          itemStyle: {
            color: COLORS.capital,
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
        {
          name: "其他收入",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => rawOr(t.other_income) / 100_000_000),
          itemStyle: {
            color: COLORS.other,
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
      ],
    };
  }, [data]);

  const hasTableRows = (data?.items ?? []).length > 0;

  return (
    <DataSection title="损益构成" state={state} onRetry={onRetry}>
      <div style={{ display: "flex", flexDirection: "column", gap: designTokens.space[5] }}>
        {data && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: designTokens.space[4],
              }}
            >
              <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>总损益</div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_pnl)),
                    ...tabularNumsStyle,
                  }}
                >
                  {`${rawOr(data.total_pnl) >= 0 ? "+" : ""}${(rawOr(data.total_pnl) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[500] }}>
                  {data.report_period}
                </div>
              </div>
              <div
                style={{ ...cardStyle, padding: designTokens.space[4], background: designTokens.color.success[50] }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.semantic.profit }}>
                  利息收入
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[18],
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_interest_income)),
                    ...tabularNumsStyle,
                  }}
                >
                  {`${(rawOr(data.total_interest_income) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.success[600] }}>
                  占比 {rawOr(data.interest_pct).toFixed(1)}%
                </div>
              </div>
              <div style={{ ...cardStyle, padding: designTokens.space[4], background: designTokens.color.info[50] }}>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.info[600] }}>
                  公允价值变动
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[18],
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_fair_value_change)),
                    ...tabularNumsStyle,
                  }}
                >
                  {`${rawOr(data.total_fair_value_change) >= 0 ? "+" : ""}${(rawOr(data.total_fair_value_change) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>
                  占比 {rawOr(data.fair_value_pct).toFixed(1)}%
                </div>
              </div>
              <div
                style={{ ...cardStyle, padding: designTokens.space[4], background: designTokens.color.warning[50] }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.warning[600] }}>
                  投资收益
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[18],
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_capital_gain)),
                    ...tabularNumsStyle,
                  }}
                >
                  {`${rawOr(data.total_capital_gain) >= 0 ? "+" : ""}${(rawOr(data.total_capital_gain) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>
                  占比 {rawOr(data.capital_gain_pct).toFixed(1)}%
                </div>
              </div>
              <div style={{ ...cardStyle, padding: designTokens.space[4], background: designTokens.color.neutral[100] }}>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>其他收入</div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[18],
                    fontWeight: 700,
                    color: toneColor(rawOr(data.total_other_income)),
                    ...tabularNumsStyle,
                  }}
                >
                  {`${rawOr(data.total_other_income) >= 0 ? "+" : ""}${(rawOr(data.total_other_income) / 100_000_000).toFixed(2)} 亿`}
                </div>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>
                  占比 {rawOr(data.other_pct).toFixed(1)}%
                </div>
              </div>
            </div>

            {bipolarOption && (
              <div style={cardStyle}>
                <h3
                  style={{
                    margin: `0 0 ${designTokens.space[3]}px`,
                    fontSize: designTokens.fontSize[16],
                    fontWeight: 600,
                    color: designTokens.color.neutral[900],
                  }}
                >
                  损益构成（带符号 · 亿元）
                </h3>
                <ReactECharts option={bipolarOption} style={{ height: 240 }} notMerge lazyUpdate />
              </div>
            )}

            {trendOption && (
              <div style={cardStyle}>
                <h3
                  style={{
                    margin: `0 0 ${designTokens.space[3]}px`,
                    fontSize: designTokens.fontSize[16],
                    fontWeight: 600,
                    color: designTokens.color.neutral[900],
                  }}
                >
                  损益构成趋势
                </h3>
                <ReactECharts option={trendOption} style={{ height: 300 }} notMerge lazyUpdate />
              </div>
            )}

            {hasTableRows && (
              <div style={cardStyle}>
                <h3
                  style={{
                    margin: `0 0 ${designTokens.space[3]}px`,
                    fontSize: designTokens.fontSize[16],
                    fontWeight: 600,
                    color: designTokens.color.neutral[900],
                  }}
                >
                  分类别损益构成
                </h3>
                <div style={{ overflow: "auto" }}>
                  <table
                    style={{
                      width: "100%",
                      borderCollapse: "collapse",
                      fontSize: designTokens.fontSize[13],
                    }}
                  >
                    <thead>
                      <tr style={{ background: designTokens.color.neutral[100] }}>
                        <th style={{ textAlign: "left", padding: designTokens.space[3] }}>资产类别</th>
                        <th style={{ textAlign: "right", padding: designTokens.space[3], ...tabularNumsStyle }}>
                          总损益(亿)
                        </th>
                        <th style={{ textAlign: "right", padding: designTokens.space[3], ...tabularNumsStyle }}>
                          利息(亿)
                        </th>
                        <th style={{ textAlign: "right", padding: designTokens.space[3], ...tabularNumsStyle }}>
                          公允(亿)
                        </th>
                        <th style={{ textAlign: "right", padding: designTokens.space[3], ...tabularNumsStyle }}>
                          投资收益(亿)
                        </th>
                        <th style={{ textAlign: "right", padding: designTokens.space[3], ...tabularNumsStyle }}>
                          其他(亿)
                        </th>
                        <th style={{ textAlign: "right", padding: designTokens.space[3], ...tabularNumsStyle }}>
                          利息占比
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((item, idx) => {
                        const totalPnl = rawOr(item.total_pnl);
                        const fvChange = rawOr(item.fair_value_change);
                        const capitalGain = rawOr(item.capital_gain);
                        const otherIncome = rawOr(item.other_income);
                        const cellPad = designTokens.space[3];
                        return (
                          <tr
                            key={idx}
                            style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                          >
                            <td style={{ padding: cellPad, fontWeight: 500 }}>{item.category}</td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: cellPad,
                                color: toneColor(totalPnl),
                                ...tabularNumsStyle,
                              }}
                            >
                              {(totalPnl / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: cellPad,
                                color: designTokens.color.semantic.profit,
                                ...tabularNumsStyle,
                              }}
                            >
                              {(rawOr(item.interest_income) / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: cellPad,
                                color: toneColor(fvChange),
                                ...tabularNumsStyle,
                              }}
                            >
                              {(fvChange / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: cellPad,
                                color: toneColor(capitalGain),
                                ...tabularNumsStyle,
                              }}
                            >
                              {(capitalGain / 100_000_000).toFixed(2)}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                padding: cellPad,
                                color: toneColor(otherIncome),
                                ...tabularNumsStyle,
                              }}
                            >
                              {(otherIncome / 100_000_000).toFixed(2)}
                            </td>
                            <td style={{ textAlign: "right", padding: cellPad, ...tabularNumsStyle }}>
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
