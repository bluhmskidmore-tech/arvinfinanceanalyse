import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { VolumeRateAttributionPayload } from "../../../api/contracts";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

const tableShellStyle = {
  overflowX: "auto" as const,
  marginTop: 20,
  borderRadius: 12,
  border: "1px solid #e4ebf5",
};

const thStyle = {
  textAlign: "right" as const,
  padding: "8px 10px",
  fontSize: 11,
  fontWeight: 700,
  color: "#162033",
  background: "#f0f3f8",
  borderBottom: "2px solid #162033",
};

type Props = {
  data: VolumeRateAttributionPayload | null;
};

/** 量价归因：分类别当期/上期损益对比 + 明细表（规模、收益率、一阶效应与对账）。 */
export function VolumeRateAnalysisChart({ data }: Props) {
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
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: {
        type: "category",
        data: rows.map((r) => r.category),
        axisLabel: { fontSize: 11, rotate: 24, color: "#5c6b82" },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}亿`, color: "#5c6b82" },
        splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
      },
      series: [
        {
          name: "当期损益",
          type: "bar",
          data: rows.map((r) => r.current_pnl / 100_000_000),
          itemStyle: { color: "#3b82f6", borderRadius: [4, 4, 0, 0] },
        },
        {
          name: "上期损益",
          type: "bar",
          data: rows.map((r) => (r.previous_pnl ?? 0) / 100_000_000),
          itemStyle: { color: "#94a3b8", borderRadius: [4, 4, 0, 0] },
        },
      ],
    };
  }, [data]);

  if (!data) {
    return (
      <div style={{ ...cardStyle, textAlign: "center", color: "#5c6b82" }}>暂无数据</div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {categoryOption && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
            各产品类别损益对比（资产类顶层）
          </h3>
          <ReactECharts option={categoryOption} style={{ height: 300 }} notMerge lazyUpdate />
        </div>
      )}

      <div style={cardStyle}>
        <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: "#162033" }}>
          归因分析明细表（亿元）
        </h3>
        <p style={{ margin: "0 0 12px", fontSize: 12, color: "#5c6b82" }}>
          损益变动 = 规模一阶效应 + 利率一阶效应 + 交叉效应
        </p>
        <div style={tableShellStyle}>
          <table style={{ width: "100%", minWidth: 1100, borderCollapse: "collapse", fontSize: 12 }}>
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
                  <tr key={`asset-${idx}`} style={{ borderBottom: "1px solid #eef2f7" }}>
                    <td
                      style={{
                        padding: "8px 10px",
                        textAlign: "left",
                        fontWeight: item.level === 0 ? 600 : 400,
                        paddingLeft: item.level > 0 ? 28 : 10,
                        background: "#ffffff",
                      }}
                    >
                      {item.category}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px", fontVariantNumeric: "tabular-nums" }}>
                      {((item.current_scale ?? 0) / 100_000_000).toFixed(2)}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px", fontVariantNumeric: "tabular-nums" }}>
                      {item.previous_scale != null
                        ? (item.previous_scale / 100_000_000).toFixed(2)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.current_yield != null ? `${item.current_yield.toFixed(2)}%` : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.previous_yield != null ? `${item.previous_yield.toFixed(2)}%` : "—"}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: "8px 10px",
                        color: item.current_pnl >= 0 ? "#15803d" : "#b91c1c",
                      }}
                    >
                      {(item.current_pnl / 100_000_000).toFixed(2)}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: "8px 10px",
                        color:
                          (item.pnl_change ?? 0) >= 0 ? "#16a34a" : "#dc2626",
                      }}
                    >
                      {item.pnl_change != null
                        ? `${(item.pnl_change / 100_000_000) >= 0 ? "+" : ""}${(item.pnl_change / 100_000_000).toFixed(2)}`
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.volume_effect != null
                        ? (item.volume_effect / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.rate_effect != null
                        ? (item.rate_effect / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.interaction_effect != null
                        ? (item.interaction_effect / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px", fontWeight: 600 }}>
                      {item.attrib_sum != null
                        ? (item.attrib_sum / 100_000_000).toFixed(4)
                        : "0.0000"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.recon_error != null
                        ? Math.abs(item.recon_error / 100_000_000) < 0.0001
                          ? "\u2248 0"
                          : (item.recon_error / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                  </tr>
                ))}
              {data.items
                .filter((item) => item.category_type === "liability")
                .map((item, idx) => (
                  <tr key={`l-${idx}`} style={{ borderBottom: "1px solid #eef2f7" }}>
                    <td
                      style={{
                        padding: "8px 10px",
                        textAlign: "left",
                        fontWeight: item.level === 0 ? 600 : 400,
                        paddingLeft: item.level > 0 ? 28 : 10,
                      }}
                    >
                      {item.category}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px", fontVariantNumeric: "tabular-nums" }}>
                      {((item.current_scale ?? 0) / 100_000_000).toFixed(2)}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px", fontVariantNumeric: "tabular-nums" }}>
                      {item.previous_scale != null
                        ? (item.previous_scale / 100_000_000).toFixed(2)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.current_yield != null ? `${item.current_yield.toFixed(2)}%` : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.previous_yield != null ? `${item.previous_yield.toFixed(2)}%` : "—"}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: "8px 10px",
                        color: item.current_pnl >= 0 ? "#15803d" : "#b91c1c",
                      }}
                    >
                      {item.current_pnl != null
                        ? (item.current_pnl / 100_000_000).toFixed(2)
                        : "—"}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: "8px 10px",
                        color:
                          (item.pnl_change ?? 0) >= 0 ? "#16a34a" : "#dc2626",
                      }}
                    >
                      {item.pnl_change != null
                        ? `${(item.pnl_change / 100_000_000) >= 0 ? "+" : ""}${(item.pnl_change / 100_000_000).toFixed(2)}`
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.volume_effect != null
                        ? (item.volume_effect / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.rate_effect != null
                        ? (item.rate_effect / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.interaction_effect != null
                        ? (item.interaction_effect / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px", fontWeight: 600 }}>
                      {item.attrib_sum != null
                        ? (item.attrib_sum / 100_000_000).toFixed(4)
                        : "0.0000"}
                    </td>
                    <td style={{ textAlign: "right", padding: "8px 10px" }}>
                      {item.recon_error != null
                        ? Math.abs(item.recon_error / 100_000_000) < 0.0001
                          ? "\u2248 0"
                          : (item.recon_error / 100_000_000).toFixed(4)
                        : "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
