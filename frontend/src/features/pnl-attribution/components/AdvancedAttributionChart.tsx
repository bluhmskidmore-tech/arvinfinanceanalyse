import { useMemo } from "react";
import type { EChartsOption } from "../../../lib/echarts";
import type {
  AdvancedAttributionSummary,
  CarryRollDownPayload,
  KRDAttributionPayload,
  Numeric,
  SpreadAttributionPayload,
} from "../../../api/contracts";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { ChartCard } from "../../../components/charts/ChartCard";
import type { DataSectionState } from "../../../components/DataSection.types";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { numericRaw } from "../../../pageModel";
import { EM_DASH } from "../../../utils/format";
import { formatYi } from "./pnlAttributionViewModel";
import "./AdvancedAttributionChart.css";

// 本图挂在 Nocturne scope 页面：基础 option 直接走共享 nocturneChartTheme
// （调色板 / tooltip / 图例 / 轴线均为 nocturneTokens 静态镜像，ECharts canvas
// 读不到 CSS 变量），组件内只保留业务系列色与网格等非主题覆盖。
const { createBarChartOption } = nocturneChartTheme;

const CONTRIBUTION_PCT_CALIBER_NOTE =
  "占比按各效应绝对值计算，方向相反时合计可能超过 100%";

const SPREAD_EXCLUSION_LABELS: Record<string, string> = {
  missing_position_key: "持仓匹配键缺失",
  duplicate_position_key: "持仓匹配键重复",
  added_position: "区间新增持仓",
  exited_position: "区间退出持仓",
  unsupported_currency: "缺少同币种基准曲线",
  invalid_market_value: "市值无效",
  missing_start_ytm: "期初收益率缺失或非观测值",
  missing_end_ytm: "期末收益率缺失或非观测值",
  invalid_start_risk: "期初期限或久期无效",
  estimated_start_duration: "期初久期为假设值",
  invalid_end_tenor: "期末期限无效",
  missing_start_curve: "期初国债曲线缺失",
  missing_end_curve: "期末国债曲线缺失",
  benchmark_start_tenor_uncovered: "期初期限超出基准覆盖",
  benchmark_end_tenor_uncovered: "期末期限超出基准覆盖",
};

function valueDirection(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "neutral";
  }
  return value >= 0 ? "positive" : "negative";
}

function rateMoveDirection(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "neutral";
  }
  return value <= 0 ? "positive" : "negative";
}

function toneDirection(value: number | null | undefined, positiveTone = "info", negativeTone = "warning") {
  if (value === null || value === undefined) {
    return "neutral";
  }
  return value >= 0 ? positiveTone : negativeTone;
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

/** 契约：`pct` 字段 raw 恒为小数比率，×100 转百分点；缺失（raw=null）返回 null，不补 0。 */
function pctPoints(value: Numeric | null | undefined): number | null {
  const raw = numericRaw(value);
  if (raw === null) {
    return null;
  }
  return value?.unit === "pct" ? raw * 100 : raw;
}

/** 图表/表格中以「亿」为单位的数值；缺失返回 null。 */
function yiOrNull(value: Numeric | null | undefined): number | null {
  const raw = numericRaw(value);
  return raw === null ? null : raw / 100_000_000;
}

function numericDisplay(
  value: { raw: number | null; display?: string } | null | undefined,
  fallback = EM_DASH,
): string {
  const display = value?.display?.trim();
  if (display) return display;
  return value?.raw == null ? fallback : value.raw.toFixed(2);
}

function pctDisplay(value: Numeric | null | undefined): string {
  const display = value?.display?.trim();
  if (display) return display;
  const points = pctPoints(value);
  return points === null ? EM_DASH : `${points.toFixed(2)}%`;
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
      grid: {
        left: 48,
        right: designTokens.space[6],
        top: designTokens.space[6],
      },
      xAxis: {
        data: rows.map((r) =>
          r.category.length > 8 ? `${r.category.slice(0, 8)}…` : r.category,
        ),
        axisLabel: { rotate: 20 },
      },
      yAxis: {
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}%` },
        splitLine: { lineStyle: { type: "dashed" } },
      },
      series: [
        {
          name: "Carry",
          type: "bar",
          data: rows.map((r) => pctPoints(r.carry)),
          itemStyle: {
            color: nocturneTokens.color.green,
          },
        },
        {
          name: "Roll-down",
          type: "bar",
          data: rows.map((r) => pctPoints(r.rolldown)),
          itemStyle: {
            color: nocturneTokens.color.blue,
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
    // 缺失贡献/收益率变动传 null，ECharts 留空不画 0 值柱/点。
    const contrib = krdData.buckets.map((b) => yiOrNull(b.duration_contribution));
    const ychg = krdData.buckets.map((b) => pctPoints(b.yield_change));
    // 双轴柱线组合仍走 createBarChartOption：主题 mergeAxis 会给数组 yAxis
    // 逐项补齐 value 轴默认（轴色/字号），此处只保留轴名与 splitLine 差异。
    return createBarChartOption({
      grid: { left: 52, right: 52, top: designTokens.space[6] },
      xAxis: { data: tenors },
      yAxis: [
        {
          name: "久期贡献(亿)",
          splitLine: { lineStyle: { type: "dashed" } },
        },
        {
          name: "BP",
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
                v !== null && v < 0
                  ? nocturneTokens.color.red
                  : nocturneTokens.color.green,
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
          lineStyle: { color: nocturneTokens.color.blue, width: 2 },
        },
      ],
    });
  }, [krdData]);

  const krdCompareOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    return createBarChartOption({
      grid: {
        left: 48,
        right: designTokens.space[6],
        top: designTokens.space[6],
      },
      xAxis: { data: krdData.buckets.map((b) => b.tenor) },
      yAxis: {
        axisLabel: { formatter: (v: number) => `${v}%` },
      },
      series: [
        {
          name: "贡献占比",
          type: "bar",
          data: krdData.buckets.map((b) => pctPoints(b.contribution_pct)),
          itemStyle: {
            color: nocturneTokens.color.blue,
          },
        },
        {
          name: "市值占比",
          type: "bar",
          // weight 契约 raw 为小数比率，经 pctPoints ×100 与「贡献占比」同轴（百分点）。
          data: krdData.buckets.map((b) => pctPoints(b.weight)),
          itemStyle: {
            color: nocturneTokens.color.green,
          },
        },
      ],
    });
  }, [krdData]);

  return (
    <PageDataSection
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
                  {spreadData.treasury_10y_change?.raw != null
                    ? `${spreadData.treasury_10y_change.raw >= 0 ? "+" : ""}${spreadData.treasury_10y_change.raw.toFixed(0)} BP`
                    : EM_DASH}
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
                {krdData.portfolio_dv01.raw != null
                  ? `${(krdData.portfolio_dv01.raw / 10_000).toFixed(0)} 万`
                  : EM_DASH}
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
            <ChartCard
              flat
              ariaLabel="Carry 与 Roll-down 分解"
              unit="%"
              height={280}
              option={carryOption}
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
                        {yiOrNull(item.market_value)?.toFixed(1) ?? EM_DASH}
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
                        {item.duration.raw != null ? item.duration.raw.toFixed(2) : EM_DASH}
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
            <p className="advanced-attribution-chart__caliber-note" data-testid="spread-method-note">
              {spreadData.method_note}
            </p>
            {spreadData.attribution_coverage && (
              <div data-testid="spread-matching-coverage">
                <p className="advanced-attribution-chart__section-copy" role={spreadData.calculation_status === "complete" ? "status" : "alert"}>
                  {spreadData.calculation_status === "unavailable" ? "无有效匹配，归因效应缺失。" : "逐券匹配期初暴露估算。"}
                  有效匹配 {spreadData.attribution_coverage.attributed_position_count} 项，期初覆盖市值
                  {formatYi(spreadData.attribution_coverage.covered_start_market_value.raw ?? undefined)}
                  （{pctDisplay(spreadData.attribution_coverage.start_coverage_pct)}）；期末覆盖
                  {pctDisplay(spreadData.attribution_coverage.end_coverage_pct)}。
                </p>
                {spreadData.attribution_coverage.exclusions.length > 0 && (
                  <div className="advanced-attribution-chart__table-wrap">
                    <table className="advanced-attribution-chart__table" aria-label="利差归因未覆盖原因">
                      <thead><tr>
                        <th className="advanced-attribution-chart__table-left">未覆盖原因</th>
                        <th className="advanced-attribution-chart__table-num">期初条数</th>
                        <th className="advanced-attribution-chart__table-num">期末条数</th>
                        <th className="advanced-attribution-chart__table-num">期初市值（亿元）</th>
                        <th className="advanced-attribution-chart__table-num">期末市值（亿元）</th>
                      </tr></thead>
                      <tbody>{spreadData.attribution_coverage.exclusions.map((item) => (
                        <tr key={item.reason}>
                          <td title={item.reason}>{SPREAD_EXCLUSION_LABELS[item.reason] ?? item.reason}</td>
                          <td className="advanced-attribution-chart__table-num">{item.start_row_count}</td>
                          <td className="advanced-attribution-chart__table-num">{item.end_row_count}</td>
                          <td className="advanced-attribution-chart__table-num">{yiOrNull(item.start_market_value)?.toFixed(2) ?? EM_DASH}</td>
                          <td className="advanced-attribution-chart__table-num">{yiOrNull(item.end_market_value)?.toFixed(2) ?? EM_DASH}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
            {(spreadData.items?.length ?? 0) > 0 ? (
              <div className="advanced-attribution-chart__table-wrap">
                <table className="advanced-attribution-chart__table">
                  <thead>
                    <tr>
                      <th className="advanced-attribution-chart__table-left">
                        类别
                      </th>
                      <th className="advanced-attribution-chart__table-num">匹配期初市值（亿元）</th>
                      <th className="advanced-attribution-chart__table-num">归因期初久期</th>
                      <th className="advanced-attribution-chart__table-num">国债效应（亿元）</th>
                      <th className="advanced-attribution-chart__table-num">利差效应（亿元）</th>
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
                        <td className="advanced-attribution-chart__table-num">{yiOrNull(item.matched_start_market_value)?.toFixed(2) ?? EM_DASH}</td>
                        <td className="advanced-attribution-chart__table-num">{numericDisplay(item.attribution_duration)}</td>
                        <td className="advanced-attribution-chart__table-num">{yiOrNull(item.treasury_effect)?.toFixed(2) ?? EM_DASH}</td>
                        <td className="advanced-attribution-chart__table-num">{yiOrNull(item.spread_effect)?.toFixed(2) ?? EM_DASH}</td>
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

        {krdData?.calculation_status === "unavailable" ? (
          <p role="alert" data-testid="krd-curve-unavailable" className="campisi-callout--warning">
            {(krdData.warnings?.length ? krdData.warnings : [krdData.curve_interpretation]).join(" ")}
          </p>
        ) : null}
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
              <ChartCard
                flat
                ariaLabel="KRD 久期贡献与收益率变动"
                unit="亿元 / BP"
                height={280}
                option={krdOption}
              />
              {krdCompareOption && (
                <ChartCard
                  flat
                  ariaLabel="KRD 贡献占比与市值占比"
                  unit="%"
                  height={280}
                  option={krdCompareOption}
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
                      占比
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      久期
                    </th>
                    <th className="advanced-attribution-chart__table-num">
                      Δyield(bp)
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
                        {yiOrNull(b.market_value)?.toFixed(1) ?? EM_DASH}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {pctDisplay(b.weight)}
                      </td>
                      <td className="advanced-attribution-chart__table-num">
                        {numericDisplay(b.bucket_duration)}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={rateMoveDirection(b.yield_change?.raw)}>
                        {pctPoints(b.yield_change)?.toFixed(1) ?? EM_DASH}
                      </td>
                      <td className="advanced-attribution-chart__table-num" data-direction={valueDirection(b.duration_contribution.raw)}>
                        {yiOrNull(b.duration_contribution)?.toFixed(2) ?? EM_DASH}
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
    </PageDataSection>
  );
}
