import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { CampisiAttributionPayload } from "../../../api/contracts";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

function formatYi(value: number): string {
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

type Props = {
  data: CampisiAttributionPayload | null;
};

/**
 * Campisi 四效应：收入、国债曲线、利差、个券选择 — 组合层面分解。
 */
export function CampisiAttributionPanel({ data }: Props) {
  const barOption = useMemo<EChartsOption | null>(() => {
    if (!data) {
      return null;
    }
    const names = ["收入效应", "国债曲线", "利差效应", "选择效应"];
    const values = [
      data.total_income,
      data.total_treasury_effect,
      data.total_spread_effect,
      data.total_selection_effect,
    ].map((v) => v / 100_000_000);
    const colors = values.map((v) => (v >= 0 ? "#22c55e" : "#ef4444"));
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => {
          const n = Array.isArray(value) ? Number(value[0]) : Number(value);
          return `${Number.isFinite(n) ? n.toFixed(2) : "—"} 亿`;
        },
      },
      grid: { left: 100, right: 24, top: 16, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}`, color: "#5c6b82" },
        splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
      },
      yAxis: { type: "category", data: names, axisLabel: { fontSize: 12, color: "#5c6b82" } },
      series: [
        {
          type: "bar",
          data: values.map((v, i) => ({
            value: v,
            itemStyle: { color: colors[i], borderRadius: [0, 4, 4, 0] },
          })),
        },
      ],
    };
  }, [data]);

  if (!data) {
    return (
      <div style={cardStyle}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#162033" }}>Campisi 四效应归因</h3>
        <p style={{ margin: "12px 0 0", color: "#5c6b82" }}>暂无 Campisi 归因数据。</p>
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
        Campisi 四效应归因（组合）
      </h3>
      <p style={{ margin: "0 0 16px", fontSize: 13, color: "#5c6b82", lineHeight: 1.6 }}>
        {data.interpretation}
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 12,
          marginBottom: 16,
          fontSize: 12,
          color: "#5c6b82",
        }}
      >
        <div>
          收入 {data.income_contribution_pct.toFixed(1)}% · {formatYi(data.total_income)}
        </div>
        <div>
          国债 {data.treasury_contribution_pct.toFixed(1)}% · {formatYi(data.total_treasury_effect)}
        </div>
        <div>
          利差 {data.spread_contribution_pct.toFixed(1)}% · {formatYi(data.total_spread_effect)}
        </div>
        <div>
          选择 {data.selection_contribution_pct.toFixed(1)}% · {formatYi(data.total_selection_effect)}
        </div>
      </div>
      {barOption && <ReactECharts option={barOption} style={{ height: 220 }} notMerge lazyUpdate />}
      {data.items.length > 0 && (
        <div style={{ marginTop: 20, overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#f0f3f8" }}>
                <th style={{ textAlign: "left", padding: 8 }}>类别</th>
                <th style={{ textAlign: "right", padding: 8 }}>收入(亿)</th>
                <th style={{ textAlign: "right", padding: 8 }}>国债(亿)</th>
                <th style={{ textAlign: "right", padding: 8 }}>利差(亿)</th>
                <th style={{ textAlign: "right", padding: 8 }}>选择(亿)</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #eef2f7" }}>
                  <td style={{ padding: 8 }}>{row.category}</td>
                  <td style={{ textAlign: "right", padding: 8 }}>
                    {(row.income_return / 100_000_000).toFixed(2)}
                  </td>
                  <td style={{ textAlign: "right", padding: 8 }}>
                    {(row.treasury_effect / 100_000_000).toFixed(2)}
                  </td>
                  <td style={{ textAlign: "right", padding: 8 }}>
                    {(row.spread_effect / 100_000_000).toFixed(2)}
                  </td>
                  <td style={{ textAlign: "right", padding: 8 }}>
                    {(row.selection_effect / 100_000_000).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
