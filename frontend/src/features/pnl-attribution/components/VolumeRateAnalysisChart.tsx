import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens } from "../../../theme/designSystem";
import { numericRaw } from "../../../pageModel";
import "./VolumeRateAnalysisChart.css";

type Props = {
  data: VolumeRateAttributionPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

type NumericLike = Numeric | null | undefined;

function rawOrNull(value: NumericLike): number | null {
  return numericRaw(value);
}

/** 缺失（对象为 null 或 raw 为 null）显示 "—"，不显示 0。 */
function yiText(value: NumericLike, digits = 2): string {
  const raw = rawOrNull(value);
  return raw === null ? "—" : (raw / 100_000_000).toFixed(digits);
}

function signedYiText(value: NumericLike, digits = 2): string {
  const raw = rawOrNull(value);
  if (raw === null) {
    return "—";
  }
  const yi = raw / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(digits)}`;
}

function reconErrorText(value: NumericLike): string {
  const raw = rawOrNull(value);
  if (raw === null) {
    return "—";
  }
  const yi = raw / 100_000_000;
  return Math.abs(yi) < 0.0001 ? "\u2248 0" : yi.toFixed(4);
}

function signedDirection(value: NumericLike): "positive" | "negative" {
  return (rawOrNull(value) ?? 0) >= 0 ? "positive" : "negative";
}

/** 量价归因：分类别当期/上期损益对比 + 明细表（规模、收益率、一阶效应与对账）。 */
export function VolumeRateAnalysisChart({ data, state, onRetry }: Props) {
  const categoryOption = useMemo<EChartsOption | null>(() => {
    if (!data) {
      return null;
    }
    const rows = data.items.filter(
      (item) => item.level === 0 && item.category_type === "asset",
    );
    if (rows.length === 0) {
      return null;
    }
    return {
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
        data: rows.map((r) => r.category),
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          rotate: 24,
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}亿`,
          color: designTokens.color.neutral[700],
        },
        splitLine: {
          lineStyle: { type: "dashed", color: designTokens.color.neutral[100] },
        },
      },
      series: [
        {
          name: "当期损益",
          type: "bar",
          // 缺失损益传 null，ECharts 留空不画 0 值柱。
          data: rows.map((r) => {
            const raw = rawOrNull(r.current_pnl);
            return raw === null ? null : raw / 100_000_000;
          }),
          itemStyle: {
            color: designTokens.color.primary[600],
            borderRadius: [
              designTokens.radius.sm,
              designTokens.radius.sm,
              0,
              0,
            ],
          },
        },
        {
          name: "上期损益",
          type: "bar",
          data: rows.map((r) => {
            const raw = rawOrNull(r.previous_pnl);
            return raw === null ? null : raw / 100_000_000;
          }),
          itemStyle: {
            color: designTokens.color.neutral[500],
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

  return (
    <PageDataSection title="量价归因明细" state={state} onRetry={onRetry}>
      {data ? (
        <div className="volume-rate-analysis-chart">
          {categoryOption && (
            <div className="volume-rate-analysis-chart__card">
              <h3 className="volume-rate-analysis-chart__section-title">
                各产品类别损益对比（资产类顶层）
              </h3>
              <ReactECharts
                option={categoryOption}
                className="volume-rate-analysis-chart__chart"
                notMerge
                lazyUpdate
              />
            </div>
          )}

          <div className="volume-rate-analysis-chart__card">
            <h3 className="volume-rate-analysis-chart__section-title volume-rate-analysis-chart__section-title--table">
              归因分析明细表（亿元）
            </h3>
            <p className="volume-rate-analysis-chart__note">
              损益变动 = 规模一阶效应 + 利率一阶效应 + 交叉效应
            </p>
            <div className="volume-rate-analysis-chart__table-shell">
              <table className="volume-rate-analysis-chart__table">
                <thead>
                  <tr>
                    <th data-align="left">产品类别</th>
                    <th>规模日均·当期</th>
                    <th>规模日均·上期</th>
                    <th>收益率·当期</th>
                    <th>收益率·上期</th>
                    <th>当期损益</th>
                    <th>损益变动</th>
                    <th>规模一阶</th>
                    <th>利率一阶</th>
                    <th>交叉</th>
                    <th>归因合计</th>
                    <th>对账差异</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items
                    .filter((item) => item.category_type === "asset")
                    .map((item, idx) => (
                      <tr key={`asset-${idx}`}>
                        <td
                          data-align="left"
                          data-level={item.level === 0 ? "0" : "1"}
                        >
                          {item.category}
                        </td>
                        <td>{yiText(item.current_scale)}</td>
                        <td>{yiText(item.previous_scale)}</td>
                        <td>
                          {item.current_yield_pct != null
                            ? item.current_yield_pct.display
                            : "—"}
                        </td>
                        <td>
                          {item.previous_yield_pct != null
                            ? item.previous_yield_pct.display
                            : "—"}
                        </td>
                        <td data-direction={signedDirection(item.current_pnl)}>
                          {yiText(item.current_pnl)}
                        </td>
                        <td data-direction={signedDirection(item.pnl_change)}>
                          {signedYiText(item.pnl_change)}
                        </td>
                        <td>{yiText(item.volume_effect, 4)}</td>
                        <td>{yiText(item.rate_effect, 4)}</td>
                        <td>{yiText(item.interaction_effect, 4)}</td>
                        <td data-weight="600">{yiText(item.attrib_sum, 4)}</td>
                        <td>{reconErrorText(item.recon_error)}</td>
                      </tr>
                    ))}
                  {data.items
                    .filter((item) => item.category_type === "liability")
                    .map((item, idx) => (
                      <tr key={`l-${idx}`}>
                        <td
                          data-align="left"
                          data-level={item.level === 0 ? "0" : "1"}
                        >
                          {item.category}
                        </td>
                        <td>{yiText(item.current_scale)}</td>
                        <td>{yiText(item.previous_scale)}</td>
                        <td>
                          {item.current_yield_pct != null
                            ? item.current_yield_pct.display
                            : "—"}
                        </td>
                        <td>
                          {item.previous_yield_pct != null
                            ? item.previous_yield_pct.display
                            : "—"}
                        </td>
                        <td data-direction={signedDirection(item.current_pnl)}>
                          {yiText(item.current_pnl)}
                        </td>
                        <td data-direction={signedDirection(item.pnl_change)}>
                          {signedYiText(item.pnl_change)}
                        </td>
                        <td>{yiText(item.volume_effect, 4)}</td>
                        <td>{yiText(item.rate_effect, 4)}</td>
                        <td>{yiText(item.interaction_effect, 4)}</td>
                        <td data-weight="600">{yiText(item.attrib_sum, 4)}</td>
                        <td>{reconErrorText(item.recon_error)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </PageDataSection>
  );
}
