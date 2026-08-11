import { useMemo } from "react";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { PageDataSection } from "../../../components/page/PageDataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { Numeric, PnlCompositionPayload } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { numericRaw } from "../../../pageModel";
import {
  pnlChartLabelOnFill,
  pnlCompositionSeriesColors,
} from "./pnlAttributionChartPalette";
import "./PnLCompositionChart.css";

function rawOr(
  n: Numeric | null | undefined,
): number | null {
  return numericRaw(n);
}

function pctPoints(
  n: Numeric | null | undefined,
): number | null {
  const raw = rawOr(n);
  if (raw === null) return null;
  // Contract: pct Numeric raw is always a decimal ratio; convert unconditionally.
  return n?.unit === "pct" ? raw * 100 : raw;
}

function pctDisplay(
  n: Numeric | null | undefined,
): string {
  const points = pctPoints(n);
  if (points === null) return "—";
  const display = n?.display?.trim();
  if (display) return display;
  return `${points.toFixed(1)}%`;
}

function toneColor(raw: number | null): string {
  if (raw === null) return pnlCompositionSeriesColors.neutral;
  if (raw > 0) return pnlCompositionSeriesColors.positive;
  if (raw < 0) return pnlCompositionSeriesColors.negative;
  return pnlCompositionSeriesColors.neutral;
}

function toneDirection(
  raw: number | null,
): "positive" | "negative" | "neutral" | undefined {
  if (raw === null) return undefined;
  if (raw > 0) return "positive";
  if (raw < 0) return "negative";
  return "neutral";
}

function yiDisplay(
  value: Numeric | null | undefined,
  signed = false,
): string {
  const raw = rawOr(value);
  if (raw === null) return "—";
  const yi = raw / 100_000_000;
  return `${signed && yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function yiCell(raw: number | null): string {
  return raw === null ? "—" : (raw / 100_000_000).toFixed(2);
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
        pct: pctPoints(data.interest_pct),
      },
      {
        label: "公允价值变动",
        rawYuan: rawOr(data.total_fair_value_change),
        pct: pctPoints(data.fair_value_pct),
      },
      {
        label: "投资收益",
        rawYuan: rawOr(data.total_capital_gain),
        pct: pctPoints(data.capital_gain_pct),
      },
      {
        label: "其他收入",
        rawYuan: rawOr(data.total_other_income),
        pct: pctPoints(data.other_pct),
      },
    ];

    const hasAny = categories.some((c) => c.rawYuan !== null);
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
            data: { value: number | null; pct: number | null };
          }>;
          if (!entries || entries.length === 0) return "";
          const e = entries[0];
          if (!e) return "";
          const yi = e.data.value;
          if (yi === null) return `${e.axisValue}<br/>—`;
          const sign = yi >= 0 ? "+" : "";
          const pct = e.data.pct === null ? "—" : `${e.data.pct.toFixed(1)}%`;
          return `${e.axisValue}<br/>${sign}${yi.toFixed(2)} 亿（占比 ${pct}）`;
        },
      },
      grid: {
        left: 90,
        right: designTokens.space[6],
        top: 10,
        bottom: 30,
        containLabel: true,
      },
      xAxis: {
        type: "value" as const,
        name: "亿元",
        axisLine: {
          show: true,
          lineStyle: { color: designTokens.color.neutral[300] },
        },
        splitLine: {
          lineStyle: {
            type: "dashed" as const,
            color: designTokens.color.neutral[200],
          },
        },
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
            value: c.rawYuan === null ? null : c.rawYuan / 100_000_000,
            pct: c.pct,
            itemStyle: { color: toneColor(c.rawYuan) },
          })),
          label: {
            show: true,
            formatter: (params: { value?: unknown }) => {
              if (params.value === null || params.value === undefined) {
                return "—";
              }
              const rawValue =
                typeof params.value === "number"
                  ? params.value
                  : Number(params.value);
              if (!Number.isFinite(rawValue)) return "—";
              const v = rawValue;
              const sign = v >= 0 ? "+" : "";
              return `${sign}${v.toFixed(2)}`;
            },
            position: "inside" as const,
            color: pnlChartLabelOnFill,
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
      grid: {
        left: 48,
        right: designTokens.space[6],
        top: designTokens.space[6],
        bottom: 48,
      },
      xAxis: {
        type: "category" as const,
        data: periods,
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          color: designTokens.color.neutral[700],
        },
        splitLine: {
          lineStyle: {
            type: "dashed" as const,
            color: designTokens.color.neutral[100],
          },
        },
      },
      series: [
        {
          name: "利息收入",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map(
            (t) => {
              const raw = rawOr(t.interest_income);
              return raw === null ? null : raw / 100_000_000;
            },
          ),
          itemStyle: { color: pnlCompositionSeriesColors.interest },
        },
        {
          name: "公允价值变动",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map(
            (t) => {
              const raw = rawOr(t.fair_value_change);
              return raw === null ? null : raw / 100_000_000;
            },
          ),
          itemStyle: { color: pnlCompositionSeriesColors.fairValue },
        },
        {
          name: "投资收益",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => {
            const raw = rawOr(t.capital_gain);
            return raw === null ? null : raw / 100_000_000;
          }),
          itemStyle: {
            color: pnlCompositionSeriesColors.capital,
            borderRadius: [
              designTokens.radius.sm,
              designTokens.radius.sm,
              0,
              0,
            ],
          },
        },
        {
          name: "其他收入",
          type: "bar" as const,
          stack: "t",
          data: data.trend_data.map((t) => {
            const raw = rawOr(t.other_income);
            return raw === null ? null : raw / 100_000_000;
          }),
          itemStyle: {
            color: pnlCompositionSeriesColors.other,
            borderRadius: [
              designTokens.radius.sm,
              designTokens.radius.sm,
              0,
              0,
            ],
          },
        },
      ],
    };
  }, [data]);

  const hasTableRows = (data?.items ?? []).length > 0;

  return (
    <PageDataSection title="损益构成" state={state} onRetry={onRetry}>
      <div className="pnl-composition-chart">
        {data && (
          <>
            <div className="pnl-composition-chart__metric-grid">
              <div className="pnl-composition-chart__card pnl-composition-chart__card--compact">
                <div className="pnl-composition-chart__label">总损益</div>
                <div
                  className="pnl-composition-chart__value"
                  data-direction={toneDirection(rawOr(data.total_pnl))}
                >
                  {yiDisplay(data.total_pnl, true)}
                </div>
                <div className="pnl-composition-chart__meta">
                  {data.report_period}
                </div>
              </div>
              <div className="pnl-composition-chart__card pnl-composition-chart__card--compact pnl-composition-chart__card--interest">
                <div className="pnl-composition-chart__label pnl-composition-chart__label--interest">
                  利息收入
                </div>
                <div
                  className="pnl-composition-chart__value pnl-composition-chart__value--medium"
                  data-direction={toneDirection(rawOr(data.total_interest_income))}
                >
                  {yiDisplay(data.total_interest_income)}
                </div>
                <div className="pnl-composition-chart__meta pnl-composition-chart__meta--interest">
                  占比 {pctDisplay(data.interest_pct)}
                </div>
              </div>
              <div className="pnl-composition-chart__card pnl-composition-chart__card--compact pnl-composition-chart__card--fair-value">
                <div className="pnl-composition-chart__label pnl-composition-chart__label--fair-value">
                  公允价值变动
                </div>
                <div
                  className="pnl-composition-chart__value pnl-composition-chart__value--medium"
                  data-direction={toneDirection(rawOr(data.total_fair_value_change))}
                >
                  {yiDisplay(data.total_fair_value_change, true)}
                </div>
                <div className="pnl-composition-chart__meta pnl-composition-chart__meta--muted">
                  占比 {pctDisplay(data.fair_value_pct)}
                </div>
              </div>
              <div className="pnl-composition-chart__card pnl-composition-chart__card--compact pnl-composition-chart__card--capital">
                <div className="pnl-composition-chart__label pnl-composition-chart__label--capital">
                  投资收益
                </div>
                <div
                  className="pnl-composition-chart__value pnl-composition-chart__value--medium"
                  data-direction={toneDirection(rawOr(data.total_capital_gain))}
                >
                  {yiDisplay(data.total_capital_gain, true)}
                </div>
                <div className="pnl-composition-chart__meta pnl-composition-chart__meta--muted">
                  占比 {pctDisplay(data.capital_gain_pct)}
                </div>
              </div>
              <div className="pnl-composition-chart__card pnl-composition-chart__card--compact pnl-composition-chart__card--other">
                <div className="pnl-composition-chart__label">其他收入</div>
                <div
                  className="pnl-composition-chart__value pnl-composition-chart__value--medium"
                  data-direction={toneDirection(rawOr(data.total_other_income))}
                >
                  {yiDisplay(data.total_other_income, true)}
                </div>
                <div className="pnl-composition-chart__meta pnl-composition-chart__meta--muted">
                  占比 {pctDisplay(data.other_pct)}
                </div>
              </div>
            </div>

            {bipolarOption && (
              <div className="pnl-composition-chart__card">
                <h3 className="pnl-composition-chart__section-title">
                  损益构成（带符号 · 亿元）
                </h3>
                <ReactECharts
                  option={bipolarOption}
                  className="pnl-composition-chart__chart"
                  notMerge
                  lazyUpdate
                />
              </div>
            )}

            {trendOption && (
              <div className="pnl-composition-chart__card">
                <h3 className="pnl-composition-chart__section-title">
                  损益构成趋势
                </h3>
                <ReactECharts
                  option={trendOption}
                  className="pnl-composition-chart__chart--trend"
                  notMerge
                  lazyUpdate
                />
              </div>
            )}

            {hasTableRows && (
              <div className="pnl-composition-chart__card">
                <h3 className="pnl-composition-chart__section-title">
                  分类别损益构成
                </h3>
                <div className="pnl-composition-chart__table-wrap">
                  <table className="pnl-composition-chart__table">
                    <thead>
                      <tr>
                        <th>资产类别</th>
                        <th data-align="right">总损益(亿)</th>
                        <th data-align="right">利息(亿)</th>
                        <th data-align="right">公允(亿)</th>
                        <th data-align="right">投资收益(亿)</th>
                        <th data-align="right">其他(亿)</th>
                        <th data-align="right">利息占比</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((item, idx) => {
                        const totalPnl = rawOr(item.total_pnl);
                        const interestIncome = rawOr(item.interest_income);
                        const fvChange = rawOr(item.fair_value_change);
                        const capitalGain = rawOr(item.capital_gain);
                        const otherIncome = rawOr(item.other_income);
                        return (
                          <tr key={idx}>
                            <td data-weight="500">{item.category}</td>
                            <td
                              data-align="right"
                              data-direction={toneDirection(totalPnl)}
                            >
                              {yiCell(totalPnl)}
                            </td>
                            <td
                              data-align="right"
                              data-tone={
                                interestIncome === null ? undefined : "profit"
                              }
                            >
                              {yiCell(interestIncome)}
                            </td>
                            <td
                              data-align="right"
                              data-direction={toneDirection(fvChange)}
                            >
                              {yiCell(fvChange)}
                            </td>
                            <td
                              data-align="right"
                              data-direction={toneDirection(capitalGain)}
                            >
                              {yiCell(capitalGain)}
                            </td>
                            <td
                              data-align="right"
                              data-direction={toneDirection(otherIncome)}
                            >
                              {yiCell(otherIncome)}
                            </td>
                            <td data-align="right">
                              {pctDisplay(item.interest_pct)}
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
    </PageDataSection>
  );
}
