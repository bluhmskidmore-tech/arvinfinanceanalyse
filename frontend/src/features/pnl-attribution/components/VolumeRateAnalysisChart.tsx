import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { VolumeRateAttributionPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
} as const;

const tableShellStyle = {
  overflowX: "auto" as const,
  marginTop: designTokens.space[5],
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.neutral[200]}`,
};

const thStyle = {
  textAlign: "right" as const,
  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
  fontSize: designTokens.fontSize[11],
  fontWeight: 700,
  color: designTokens.color.neutral[900],
  background: designTokens.color.neutral[100],
  borderBottom: `2px solid ${designTokens.color.neutral[900]}`,
};

type Props = {
  data: VolumeRateAttributionPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

/** 量价归因：分类别当期/上期损益对比 + 明细表（规模、收益率、一阶效应与对账）。 */
export function VolumeRateAnalysisChart({ data, state, onRetry }: Props) {
  const categoryOption = useMemo<EChartsOption | null>(() => {
    if (!data) {
      return null;
    }
    const rows = data.items.filter((item) => item.level === 0 && item.category_type === "asset");
    if (rows.length === 0) {
      return null;
    }
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 48, right: designTokens.space[6], top: designTokens.space[6], bottom: 48 },
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
        splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[100] } },
      },
      series: [
        {
          name: "当期损益",
          type: "bar",
          data: rows.map((r) => (r.current_pnl.raw ?? 0) / 100_000_000),
          itemStyle: {
            color: designTokens.color.info[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
        {
          name: "上期损益",
          type: "bar",
          data: rows.map((r) => (r.previous_pnl?.raw ?? 0) / 100_000_000),
          itemStyle: {
            color: designTokens.color.neutral[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
      ],
    };
  }, [data]);

  return (
    <DataSection title="量价归因明细" state={state} onRetry={onRetry}>
      {data ? (
        <div style={{ display: "flex", flexDirection: "column", gap: designTokens.space[6] }}>
          {categoryOption && (
            <div style={cardStyle}>
              <h3
                style={{
                  margin: `0 0 ${designTokens.space[4]}px`,
                  fontSize: designTokens.fontSize[16],
                  fontWeight: 600,
                  color: designTokens.color.neutral[900],
                }}
              >
                各产品类别损益对比（资产类顶层）
              </h3>
              <ReactECharts option={categoryOption} style={{ height: 300 }} notMerge lazyUpdate />
            </div>
          )}

          <div style={cardStyle}>
            <h3
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[14],
                fontWeight: 700,
                color: designTokens.color.neutral[900],
              }}
            >
              归因分析明细表（亿元）
            </h3>
            <p
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[12],
                color: designTokens.color.neutral[700],
              }}
            >
              损益变动 = 规模一阶效应 + 利率一阶效应 + 交叉效应
            </p>
            <div style={tableShellStyle}>
              <table
                style={{
                  width: "100%",
                  minWidth: 1100,
                  borderCollapse: "collapse",
                  fontSize: designTokens.fontSize[12],
                }}
              >
                <thead>
                  <tr>
                    <th
                      style={{
                        ...thStyle,
                        textAlign: "left",
                        position: "sticky",
                        left: 0,
                        zIndex: 1,
                      }}
                    >
                      产品类别
                    </th>
                    <th style={thStyle}>规模日均·当期</th>
                    <th style={thStyle}>规模日均·上期</th>
                    <th style={thStyle}>收益率·当期</th>
                    <th style={thStyle}>收益率·上期</th>
                    <th style={thStyle}>当期损益</th>
                    <th style={thStyle}>损益变动</th>
                    <th style={thStyle}>规模一阶</th>
                    <th style={thStyle}>利率一阶</th>
                    <th style={thStyle}>交叉</th>
                    <th style={thStyle}>归因合计</th>
                    <th style={thStyle}>对账差异</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items
                    .filter((item) => item.category_type === "asset")
                    .map((item, idx) => (
                      <tr
                        key={`asset-${idx}`}
                        style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                      >
                        <td
                          style={{
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            textAlign: "left",
                            fontWeight: item.level === 0 ? 600 : 400,
                            paddingLeft:
                              item.level > 0
                                ? designTokens.space[3] + designTokens.space[4]
                                : designTokens.space[3],
                            background: designTokens.color.primary[50],
                          }}
                        >
                          {item.category}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {((item.current_scale.raw ?? 0) / 100_000_000).toFixed(2)}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.previous_scale != null
                            ? ((item.previous_scale.raw ?? 0) / 100_000_000).toFixed(2)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.current_yield != null
                            ? `${(item.current_yield.raw ?? 0).toFixed(2)}%`
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.previous_yield != null ? `${(item.previous_yield.raw ?? 0).toFixed(2)}%` : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            color:
                              (item.current_pnl.raw ?? 0) >= 0
                                ? designTokens.color.semantic.profit
                                : designTokens.color.semantic.loss,
                            ...tabularNumsStyle,
                          }}
                        >
                          {((item.current_pnl.raw ?? 0) / 100_000_000).toFixed(2)}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            color:
                              (item.pnl_change?.raw ?? 0) >= 0
                                ? designTokens.color.semantic.profit
                                : designTokens.color.semantic.loss,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.pnl_change != null
                            ? `${(item.pnl_change.raw ?? 0) / 100_000_000 >= 0 ? "+" : ""}${((item.pnl_change.raw ?? 0) / 100_000_000).toFixed(2)}`
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.volume_effect != null
                            ? ((item.volume_effect.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.rate_effect != null
                            ? ((item.rate_effect.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.interaction_effect != null
                            ? ((item.interaction_effect.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            fontWeight: 600,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.attrib_sum != null
                            ? ((item.attrib_sum.raw ?? 0) / 100_000_000).toFixed(4)
                            : "0.0000"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.recon_error != null
                            ? Math.abs((item.recon_error.raw ?? 0) / 100_000_000) < 0.0001
                              ? "\u2248 0"
                              : ((item.recon_error.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  {data.items
                    .filter((item) => item.category_type === "liability")
                    .map((item, idx) => (
                      <tr
                        key={`l-${idx}`}
                        style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                      >
                        <td
                          style={{
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            textAlign: "left",
                            fontWeight: item.level === 0 ? 600 : 400,
                            paddingLeft:
                              item.level > 0
                                ? designTokens.space[3] + designTokens.space[4]
                                : designTokens.space[3],
                          }}
                        >
                          {item.category}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {((item.current_scale.raw ?? 0) / 100_000_000).toFixed(2)}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.previous_scale != null
                            ? ((item.previous_scale.raw ?? 0) / 100_000_000).toFixed(2)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.current_yield != null ? `${(item.current_yield.raw ?? 0).toFixed(2)}%` : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.previous_yield != null ? `${(item.previous_yield.raw ?? 0).toFixed(2)}%` : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            color:
                              (item.current_pnl.raw ?? 0) >= 0
                                ? designTokens.color.semantic.profit
                                : designTokens.color.semantic.loss,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.current_pnl != null
                            ? ((item.current_pnl.raw ?? 0) / 100_000_000).toFixed(2)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            color:
                              (item.pnl_change?.raw ?? 0) >= 0
                                ? designTokens.color.semantic.profit
                                : designTokens.color.semantic.loss,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.pnl_change != null
                            ? `${(item.pnl_change.raw ?? 0) / 100_000_000 >= 0 ? "+" : ""}${((item.pnl_change.raw ?? 0) / 100_000_000).toFixed(2)}`
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.volume_effect != null
                            ? ((item.volume_effect.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.rate_effect != null
                            ? ((item.rate_effect.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.interaction_effect != null
                            ? ((item.interaction_effect.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            fontWeight: 600,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.attrib_sum != null
                            ? ((item.attrib_sum.raw ?? 0) / 100_000_000).toFixed(4)
                            : "0.0000"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                            ...tabularNumsStyle,
                          }}
                        >
                          {item.recon_error != null
                            ? Math.abs((item.recon_error.raw ?? 0) / 100_000_000) < 0.0001
                              ? "\u2248 0"
                              : ((item.recon_error.raw ?? 0) / 100_000_000).toFixed(4)
                            : "—"}
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
