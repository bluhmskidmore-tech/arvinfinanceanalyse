import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { TPLMarketCorrelationPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
} as const;

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function correlationLabel(corr: number | null): { level: string; color: string; bg: string } {
  if (corr === null) {
    return {
      level: "无数据",
      color: designTokens.color.neutral[700],
      bg: designTokens.color.neutral[100],
    };
  }
  const a = Math.abs(corr);
  if (a >= 0.7) {
    return corr < 0
      ? {
          level: "强相关",
          color: designTokens.color.semantic.profit,
          bg: designTokens.color.success[50],
        }
      : {
          level: "强相关",
          color: designTokens.color.semantic.loss,
          bg: designTokens.color.danger[50],
        };
  }
  if (a >= 0.4) {
    return {
      level: "中等相关",
      color: designTokens.color.info[600],
      bg: designTokens.color.info[50],
    };
  }
  if (a >= 0.2) {
    return {
      level: "弱相关",
      color: designTokens.color.warning[600],
      bg: designTokens.color.warning[50],
    };
  }
  return {
    level: "无显著相关",
    color: designTokens.color.neutral[700],
    bg: designTokens.color.neutral[100],
  };
}

type Props = {
  data: TPLMarketCorrelationPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

/** Mock / legacy payloads may expose BP total as a plain number under `treasury_10y_total_change_bp`. */
function treasuryTotalChangeBp(data: TPLMarketCorrelationPayload): number | null {
  const n = data.treasury_10y_total_change;
  if (n != null) {
    return n.raw ?? 0;
  }
  const legacy = (data as TPLMarketCorrelationPayload & { treasury_10y_total_change_bp?: number | null })
    .treasury_10y_total_change_bp;
  return legacy ?? null;
}

/** TPL 公允价值变动与国债收益率走势的双轴对比。 */
export function TPLMarketChart({ data, state, onRetry }: Props) {
  const chartOption = useMemo<EChartsOption | null>(() => {
    if (!data?.data_points?.length) {
      return null;
    }
    const periods = data.data_points.map((p) =>
      p.period_label.replace("年", "-").replace("月", ""),
    );
    const tpl = data.data_points.map((p) => (p.tpl_fair_value_change.raw ?? 0) / 100_000_000);
    const bp = data.data_points.map((p) => p.treasury_10y_change?.raw ?? 0);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 56, right: 56, top: 28, bottom: 52 },
      xAxis: {
        type: "category",
        data: periods,
        axisLabel: { fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] },
      },
      yAxis: [
        {
          type: "value",
          name: "TPL(亿)",
          axisLabel: {
            formatter: (v: number) => `${v.toFixed(1)}`,
            color: designTokens.color.neutral[700],
          },
          splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[100] } },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: { formatter: (v: number) => `${v}`, color: designTokens.color.neutral[700] },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "TPL公允价值变动",
          type: "bar",
          yAxisIndex: 0,
          data: tpl,
          itemStyle: {
            color: designTokens.color.info[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
        {
          name: "国债收益率变动",
          type: "line",
          yAxisIndex: 1,
          data: bp,
          smooth: true,
          symbolSize: 8,
          lineStyle: { color: designTokens.color.danger[400], width: 2 },
        },
      ],
    };
  }, [data]);

  const corr = correlationLabel(data?.correlation_coefficient?.raw ?? null);
  const treasuryBpTotal = data ? treasuryTotalChangeBp(data) : null;

  return (
    <DataSection title="TPL 市场相关性" state={state} onRetry={onRetry}>
      {data ? (
        <div style={{ display: "flex", flexDirection: "column", gap: designTokens.space[5] }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: designTokens.space[4],
            }}
          >
            <div style={{ ...cardStyle, padding: designTokens.space[4], background: corr.bg }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                相关系数
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[24],
                  fontWeight: 700,
                  color: corr.color,
                  ...tabularNumsStyle,
                }}
              >
                {data.correlation_coefficient !== null
                  ? (data.correlation_coefficient.raw ?? 0).toFixed(3)
                  : "—"}
              </div>
              <div style={{ fontSize: designTokens.fontSize[12], color: corr.color }}>{corr.level}</div>
            </div>
            <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                累计 TPL 公允价值变动
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[18],
                  fontWeight: 700,
                  color:
                    (data.total_tpl_fv_change.raw ?? 0) >= 0
                      ? designTokens.color.semantic.profit
                      : designTokens.color.semantic.loss,
                  ...tabularNumsStyle,
                }}
              >
                {formatYi(data.total_tpl_fv_change.raw ?? undefined)}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                累计国债收益率变动
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[18],
                  fontWeight: 700,
                  color:
                    (treasuryBpTotal ?? 0) <= 0
                      ? designTokens.color.semantic.profit
                      : designTokens.color.semantic.loss,
                  ...tabularNumsStyle,
                }}
              >
                {treasuryBpTotal !== null
                  ? `${treasuryBpTotal >= 0 ? "+" : ""}${treasuryBpTotal.toFixed(1)} BP`
                  : "—"}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                分析期间
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[18],
                  fontWeight: 700,
                  color: designTokens.color.neutral[900],
                  ...tabularNumsStyle,
                }}
              >
                {data.num_periods} 个月
              </div>
              <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[500] }}>
                {data.start_period} ~ {data.end_period}
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <h4
              style={{
                margin: `0 0 ${designTokens.space[2]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              相关性解读
            </h4>
            <p
              style={{
                margin: 0,
                fontSize: designTokens.fontSize[14],
                color: designTokens.color.neutral[700],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              {data.correlation_interpretation}
            </p>
            {data.analysis_summary ? (
              <p
                style={{
                  margin: `${designTokens.space[3]}px 0 0`,
                  fontSize: designTokens.fontSize[13],
                  color: designTokens.color.neutral[500],
                }}
              >
                {data.analysis_summary}
              </p>
            ) : null}
          </div>

          {chartOption && (
            <div style={cardStyle}>
              <h3
                style={{
                  margin: `0 0 ${designTokens.space[4]}px`,
                  fontSize: designTokens.fontSize[16],
                  fontWeight: 600,
                  color: designTokens.color.neutral[900],
                }}
              >
                TPL 公允价值变动 vs 国债收益率变动
              </h3>
              <ReactECharts option={chartOption} style={{ height: 360 }} notMerge lazyUpdate />
              <p
                style={{
                  margin: `${designTokens.space[3]}px 0 0`,
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[500],
                  textAlign: "center",
                }}
              >
                利率下行（折线下降）时，债券估值通常上行，TPL 变动多为正（蓝柱向上）。
              </p>
            </div>
          )}

          <div style={cardStyle}>
            <h3
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              月度明细
            </h3>
            <div style={{ overflow: "auto", maxHeight: 320 }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: designTokens.fontSize[13],
                }}
              >
                <thead
                  style={{
                    position: "sticky",
                    top: 0,
                    background: designTokens.color.neutral[100],
                  }}
                >
                  <tr>
                    <th
                      style={{
                        textAlign: "left",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                      }}
                    >
                      月份
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      TPL 规模(亿)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      TPL 损益(亿)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      10Y(%)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      利率变动(BP)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      DR007(%)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.data_points.map((point, idx) => (
                    <tr
                      key={idx}
                      style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                    >
                      <td style={{ padding: designTokens.space[3] }}>{point.period_label}</td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[3],
                          ...tabularNumsStyle,
                        }}
                      >
                        {((point.tpl_scale.raw ?? 0) / 100_000_000).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[3],
                          color:
                            (point.tpl_fair_value_change.raw ?? 0) >= 0
                              ? designTokens.color.semantic.profit
                              : designTokens.color.semantic.loss,
                          ...tabularNumsStyle,
                        }}
                      >
                        {((point.tpl_fair_value_change.raw ?? 0) / 100_000_000).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[3],
                          ...tabularNumsStyle,
                        }}
                      >
                        {point.treasury_10y !== null ? (point.treasury_10y.raw ?? 0).toFixed(3) : "—"}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[3],
                          color:
                            (point.treasury_10y_change?.raw ?? 0) <= 0
                              ? designTokens.color.semantic.profit
                              : designTokens.color.semantic.loss,
                          ...tabularNumsStyle,
                        }}
                      >
                        {point.treasury_10y_change !== null
                          ? `${(point.treasury_10y_change.raw ?? 0) >= 0 ? "+" : ""}${(point.treasury_10y_change.raw ?? 0).toFixed(1)}`
                          : "—"}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[3],
                          ...tabularNumsStyle,
                        }}
                      >
                        {point.dr007 !== null ? (point.dr007.raw ?? 0).toFixed(3) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </DataSection>
  );
}
