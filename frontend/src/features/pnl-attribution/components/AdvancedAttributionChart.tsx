import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  AdvancedAttributionSummary,
  CarryRollDownPayload,
  KRDAttributionPayload,
  SpreadAttributionPayload,
} from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { createBarChartOption, createBaseChartOption } from "../../../components/charts/chartTheme";
import { designTokens, ibTokens } from "../../../theme/designSystem";
import "./AdvancedAttributionChart.css";

const CONTRIBUTION_PCT_CALIBER_NOTE =
  "占比按各效应绝对值计算，方向相反时合计可能超过 100%";

const BAR_RADIUS = [
  designTokens.radius.sm,
  designTokens.radius.sm,
  0,
  0,
];

function valueDirection(value: number | null | undefined) {
  return (value ?? 0) >= 0 ? "positive" : "negative";
}

function rateMoveDirection(value: number | null | undefined) {
  return (value ?? 0) <= 0 ? "positive" : "negative";
}

function toneDirection(value: number | null | undefined, positiveTone = "info", negativeTone = "warning") {
  return (value ?? 0) >= 0 ? positiveTone : negativeTone;
}

function AttributionPctCaliberNote(props: { testId: string }) {
  return (
    <p
      data-testid={props.testId}
      className="advanced-attribution-chart__caliber-note"
      title={CONTRIBUTION_PCT_CALIBER_NOTE}
    >
      {CONTRIBUTION_PCT_CALIBER_NOTE}
    </p>
  );
}

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function numericRaw(value: { raw: number | null } | null | undefined): number {
  return value?.raw ?? 0;
}

function pctPoints(
  value: { raw: number | null; unit?: string } | null | undefined,
): number {
  const raw = numericRaw(value);
  return value?.unit === "pct" && Math.abs(raw) <= 1 ? raw * 100 : raw;
}

function numericDisplay(
  value: { raw: number | null; display?: string } | null | undefined,
  fallback = "—",
): string {
  const display = value?.display?.trim();
  if (display) return display;
  return value?.raw == null ? fallback : value.raw.toFixed(2);
}

function pctDisplay(
  value: { raw: number | null; unit?: string; display?: string } | null | undefined,
): string {
  const display = value?.display?.trim();
  if (display) return display;
  return `${pctPoints(value).toFixed(2)}%`;
}

type Props = {
  carryData: CarryRollDownPayload | null;
  spreadData: SpreadAttributionPayload | null;
  krdData: KRDAttributionPayload | null;
  summaryData?: AdvancedAttributionSummary | null;
  state: DataSectionState;
  onRetry: () => void;
};

/** 高级归因：Carry / Roll-down、利差解读、KRD 久期桶分解。 */
export function AdvancedAttributionChart({
  carryData,
  spreadData,
  krdData,
  summaryData,
  state,
  onRetry,
}: Props) {
  const carryOption = useMemo<EChartsOption | null>(() => {
    if (!carryData?.items?.length) {
      return null;
    }
    const rows = carryData.items.slice(0, 10);
    return createBarChartOption({
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: {
        left: 48,
        right: designTokens.space[6],
        top: designTokens.space[6],
        bottom: 48,
      },
      xAxis: {
        type: "category",
        data: rows.map((r) =>
          r.category.length > 8 ? `${r.category.slice(0, 8)}…` : r.category,
        ),
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          rotate: 20,
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}%`,
          color: designTokens.color.neutral[700],
        },
        splitLine: {
          lineStyle: { type: "dashed", color: designTokens.color.neutral[100] },
        },
      },
      series: [
        {
          name: "Carry",
          type: "bar",
          data: rows.map((r) => pctPoints(r.carry)),
          itemStyle: {
            color: ibTokens.color.up,
            borderRadius: BAR_RADIUS,
          },
        },
        {
          name: "Roll-down",
          type: "bar",
          data: rows.map((r) => pctPoints(r.rolldown)),
          itemStyle: {
            color: ibTokens.color.accent,
            borderRadius: BAR_RADIUS,
          },
        },
      ],
    });
  }, [carryData]);

  const krdOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    const tenors = krdData.buckets.map((b) => b.tenor);
    const contrib = krdData.buckets.map(
      (b) => (b.duration_contribution.raw ?? 0) / 100_000_000,
    );
    const ychg = krdData.buckets.map((b) => pctPoints(b.yield_change));
    return createBaseChartOption({
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 52, right: 52, top: designTokens.space[6], bottom: 48 },
      xAxis: {
        type: "category",
        data: tenors,
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: [
        {
          type: "value",
          name: "久期贡献(亿)",
          axisLabel: { color: designTokens.color.neutral[700] },
          splitLine: {
            lineStyle: {
              type: "dashed",
              color: designTokens.color.neutral[100],
            },
          },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: { color: designTokens.color.neutral[700] },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "久期贡献",
          type: "bar",
          yAxisIndex: 0,
          data: contrib.map((v) => ({
            value: v,
            itemStyle: {
              color:
                v >= 0
                  ? ibTokens.color.up
                  : ibTokens.color.down,
              borderRadius: BAR_RADIUS,
            },
          })),
        },
        {
          name: "收益率变动",
          type: "line",
          yAxisIndex: 1,
          data: ychg,
          smooth: true,
          symbolSize: 8,
          lineStyle: { color: ibTokens.color.accent, width: 2 },
        },
      ],
    });
  }, [krdData]);

  const krdCompareOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    return createBarChartOption({
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: {
        left: 48,
        right: designTokens.space[6],
        top: designTokens.space[6],
        bottom: 48,
      },
      xAxis: {
        type: "category",
        data: krdData.buckets.map((b) => b.tenor),
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v}%`,
          color: designTokens.color.neutral[700],
        },
      },
      series: [
        {
          name: "贡献占比",
          type: "bar",
          data: krdData.buckets.map((b) => pctPoints(b.contribution_pct)),
          itemStyle: {
            color: ibTokens.color.accent,
            borderRadius: BAR_RADIUS,
          },
        },
        {
          name: "市值占比",
          type: "bar",
          data: krdData.buckets.map((b) => b.weight.raw ?? 0),
          itemStyle: {
            color: ibTokens.color.up,
            borderRadius: BAR_RADIUS,
          },
        },
      ],
    });
  }, [krdData]);

  return (
    <DataSection
      title="Carry / 利差 / KRD 高级归因"
      state={state}
      onRetry={onRetry}
    >
      <div className="advanced-attribution-chart">
        <div className="advanced-attribution-chart__metric-grid">
          {carryData && (
            <>
              <div className="advanced-attribution-chart__metric-card" data-tone="profit">
                <div className="advanced-attribution-chart__metric-label">
                  组合 Carry（年化）
                </div>
                <div
                  className="advanced-attribution-chart__metric-value"
                  data-direction={valueDirection(carryData.portfolio_carry.raw)}
                >
                  {pctDisplay(carryData.portfolio_carry)}
                </div>
                <div className="advanced-attribution-chart__metric-note">
                  票息 − FTP
                </div>
              </div>
              <div className="advanced-attribution-chart__metric-card" data-tone="info">
                <div className="advanced-attribution-chart__metric-label">
                  组合 Roll-down（年化）
                </div>
                <div
                  className="advanced-attribution-chart__metric-value"
                  data-direction={toneDirection(carryData.portfolio_rolldown.raw)}
                >
                  {pctDisplay(carryData.portfolio_rolldown)}
                </div>
                <div className="advanced-attribution-chart__metric-note">
                  骑乘
                </div>
              </div>
              <div className="advanced-attribution-chart__metric-card" data-tone="neutral">
                <div className="advanced-attribution-chart__metric-label">
                  静态收益（年化）
                </div>
                <div className="advanced-attribution-chart__metric-value" data-direction="neutral">
                  {summaryData?.static_return_annualized
                    ? pctDisplay(summaryData.static_return_annualized)
                    : pctDisplay(carryData.portfolio_static_return)}
                </div>
                <div className="advanced-attribution-chart__metric-note">
                  Carry + Roll-down
                </div>
              </div>
              <div className="advanced-attribution-chart__metric-card" data-tone="profit">
                <div className="advanced-attribution-chart__metric-label">
                  Carry 合计（月度估算）
                </div>
                <div
                  className="advanced-attribution-chart__metric-value"
                  data-size="medium"
                  data-direction={valueDirection(carryData.total_carry_pnl.raw)}
                >
                  {formatYi(carryData.total_carry_pnl.raw ?? undefined)}
                </div>
              </div>
              <div className="advanced-attribution-chart__metric-card" data-tone="info">
                <div className="advanced-attribution-chart__metric-label">
                  Roll-down 合计（月度估算）
                </div>
                <div
                  className="advanced-attribution-chart__metric-value"
                  data-size="medium"
                  data-direction={toneDirection(carryData.total_rolldown_pnl.raw)}
                >
                  {formatYi(carryData.total_rolldown_pnl.raw ?? undefined)}
                </div>
              </div>
              <div className="advanced-attribution-chart__metric-card" data-tone="neutral">
                <div className="advanced-attribution-chart__metric-label">
                  Static 合计（月度估算）
                </div>
                <div className="advanced-attribution-chart__metric-value" data-size="medium" data-direction="neutral">
                  {formatYi(carryData.total_static_pnl.raw ?? undefined)}
                </div>
              </div>
            </>
          )}
          {spreadData && (
            <>
              <div className="advanced-attribution-chart__metric-card" data-tone="warning">
                <div className="advanced-attribution-chart__metric-label">
                  国债曲线效应
                </div>
                <div
                  className="advanced-attribution-chart__metric-value"
                  data-size="medium"
                  data-direction={valueDirection(spreadData.total_treasury_effect.raw)}
                >
                  {formatYi(spreadData.total_treasury_effect.raw ?? undefined)}
                </div>
              </div>
              <div className="advanced-attribution-chart__metric-card" data-tone="loss">
                <div className="advanced-attribution-chart__metric-label">
                  10Y 变动
                </div>
                <div
                  className="advanced-attribution-chart__metric-value"
                  data-size="medium"
                  data-direction={rateMoveDirection(spreadData.treasury_10y_change?.raw)}
                >
                  {spreadData.treasury_10y_change !== null
                    ? `${(spreadData.treasury_10y_change.raw ?? 0) >= 0 ? "+" : ""}${(spreadData.treasury_10y_change.raw ?? 0).toFixed(0)} BP`
                    : "—"}
                </div>
              </div>
            </>
          )}
          {krdData && (
            <div className="advanced-attribution-chart__metric-card" data-tone="info">
              <div className="advanced-attribution-chart__metric-label">
                组合 DV01
              </div>
              <div className="advanced-attribution-chart__metric-value" data-direction="info">
                {((krdData.portfolio_dv01.raw ?? 0) / 10_000).toFixed(0)} 万
              </div>
              <div className="advanced-attribution-chart__metric-note">
                每 BP 价值变动
              </div>
            </div>
          )}
        </div>

        {carryOption && carryData && (
          <div className="advanced-attribution-chart__panel">
            <h3 className="advanced-attribution-chart__section-title">
              {"Carry & Roll-down"} 分解
            </h3>
            <ReactECharts
              option={carryOption}
              className="advanced-attribution-chart__chart advanced-attribution-chart__chart--carry"
              notMerge
              lazyUpdate
            />
            <div className="advanced-attribution-chart__table-wrap advanced-attribution-chart__table-wrap--bounded">
              <table className="advanced-attribution-chart__table advanced-attribution-chart__table--sticky">
                <thead>
                  <tr>
                    <th className="advanced-attribution-chart__table-left">
                      类别
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      市值(亿)
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      票息%
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      FTP%
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Carry%（年化）
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Carry（月度估算）
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      久期
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Roll%（年化）
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Roll（月度估算）
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Static（月度估算）
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {carryData.items.slice(0, 8).map((item, idx) => (
                    <tr key={idx}>
                      <td>
                        {item.category}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {((item.market_value.raw ?? 0) / 1e8).toFixed(1)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {pctDisplay(item.coupon_rate)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {pctDisplay(item.funding_cost)}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={valueDirection(item.carry.raw)}>
                        {pctDisplay(item.carry)}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={valueDirection(item.carry_pnl.raw)}>
                        {formatYi(item.carry_pnl.raw ?? undefined)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {(item.duration.raw ?? 0).toFixed(2)}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={toneDirection(item.rolldown.raw)}>
                        {pctDisplay(item.rolldown)}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={toneDirection(item.rolldown_pnl.raw)}>
                        {formatYi(item.rolldown_pnl.raw ?? undefined)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {formatYi(item.static_pnl.raw ?? undefined)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {spreadData?.interpretation && (
          <div className="advanced-attribution-chart__panel">
            <h4 className="advanced-attribution-chart__section-title advanced-attribution-chart__section-title--compact">
              利差归因
            </h4>
            <p className="advanced-attribution-chart__section-copy">
              {spreadData.interpretation}
            </p>
            <p className="advanced-attribution-chart__section-meta">
              区间 {spreadData.start_date} ~ {spreadData.end_date}
            </p>
            {(spreadData.items?.length ?? 0) > 0 ? (
              <div className="advanced-attribution-chart__table-wrap">
                <table className="advanced-attribution-chart__table">
                  <thead>
                    <tr>
                      <th className="advanced-attribution-chart__table-left">
                        类别
                      </th>
                      <th className="advanced-attribution-chart__table-num">
                        国债贡献占比%
                      </th>
                      <th className="advanced-attribution-chart__table-num">
                        利差贡献占比%
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {spreadData.items.slice(0, 8).map((item, idx) => (
                      <tr key={idx}>
                        <td>
                          {item.category}
                        </td>
                        <td className="advanced-attribution-chart__table-num">
                          {pctDisplay(item.treasury_contribution_pct)}
                        </td>
                        <td className="advanced-attribution-chart__table-num">
                          {pctDisplay(item.spread_contribution_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <AttributionPctCaliberNote testId="spread-contribution-pct-caliber-note" />
          </div>
        )}

        {krdOption && krdData && (
          <div className="advanced-attribution-chart__panel">
            <h3 className="advanced-attribution-chart__section-title">
              KRD 归因
            </h3>
            {krdData.curve_interpretation && (
              <p className="advanced-attribution-chart__curve-note">
                曲线形态：{krdData.curve_interpretation}
                {krdData.max_contribution_tenor ? (
                  <span className="advanced-attribution-chart__curve-highlight">
                    最大贡献期限 {krdData.max_contribution_tenor}（
                    {formatYi(krdData.max_contribution_value.raw ?? undefined)}
                    ）
                  </span>
                ) : null}
              </p>
            )}
            <div className="advanced-attribution-chart__chart-grid">
              <ReactECharts
                option={krdOption}
                className="advanced-attribution-chart__chart"
                notMerge
                lazyUpdate
              />
              {krdCompareOption && (
                <ReactECharts
                  option={krdCompareOption}
                  className="advanced-attribution-chart__chart"
                  notMerge
                  lazyUpdate
                />
              )}
            </div>
            <div className="advanced-attribution-chart__table-wrap">
              <table className="advanced-attribution-chart__table">
                <thead>
                  <tr>
                    <th className="advanced-attribution-chart__table-left">
                      期限
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      债券数
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      市值(亿)
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      占比%
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      久期
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Δyield
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      贡献(亿)
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      贡献占比%
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {krdData.buckets.map((b, idx) => (
                    <tr key={idx}>
                      <td className="advanced-attribution-chart__table-left">
                        {b.tenor}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {b.bond_count}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {((b.market_value.raw ?? 0) / 1e8).toFixed(1)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {(b.weight.raw ?? 0).toFixed(1)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {numericDisplay(b.bucket_duration)}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={rateMoveDirection(b.yield_change?.raw)}>
                        {b.yield_change !== null
                          ? pctPoints(b.yield_change).toFixed(1)
                          : "—"}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={valueDirection(b.duration_contribution.raw)}>
                        {((b.duration_contribution.raw ?? 0) / 1e8).toFixed(2)}
                      </td>
                      <td className="advanced-attribution-chart__table-num advanced-attribution-chart__table-num--strong">
                        {pctDisplay(b.contribution_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <AttributionPctCaliberNote testId="krd-contribution-pct-caliber-note" />
            </div>
          </div>
        )}
      </div>
    </DataSection>
  );
}
