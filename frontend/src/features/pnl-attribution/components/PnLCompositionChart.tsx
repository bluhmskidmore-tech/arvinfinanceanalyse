import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { PnlCompositionPayload } from "../../../api/contracts";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

const COLORS = {
  interest: "#22c55e",
  fairValue: "#3b82f6",
  capital: "#f59e0b",
  other: "#94a3b8",
};

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi.toFixed(2)} 亿`;
}

type Props = {
  data: PnlCompositionPayload | null;
};

/** 损益构成：利息、公允价值、资本利得等占比与趋势。 */
export function PnLCompositionChart({ data }: Props) {
  const pieOption = useMemo<EChartsOption | null>(() => {
    if (!data) {
      return null;
    }
    const pieData: { name: string; value: number; orig: number; pct: number; itemStyle: { color: string } }[] = [];
    if (Math.abs(data.total_interest_income) > 0) {
      pieData.push({
        name: "利息收入",
        value: Math.abs(data.total_interest_income / 100_000_000),
        orig: data.total_interest_income / 100_000_000,
        pct: data.interest_pct,
        itemStyle: { color: COLORS.interest },
      });
    }
    if (Math.abs(data.total_fair_value_change) > 0) {
      pieData.push({
        name: "公允价值变动",
        value: Math.abs(data.total_fair_value_change / 100_000_000),
        orig: data.total_fair_value_change / 100_000_000,
        pct: data.fair_value_pct,
        itemStyle: { color: COLORS.fairValue },
      });
    }
    if (Math.abs(data.total_capital_gain) > 0) {
      pieData.push({
        name: "投资收益",
        value: Math.abs(data.total_capital_gain / 100_000_000),
        orig: data.total_capital_gain / 100_000_000,
        pct: data.capital_gain_pct,
        itemStyle: { color: COLORS.capital },
      });
    }
    if (Math.abs(data.total_other_income) > 0) {
      pieData.push({
        name: "其他收入",
        value: Math.abs(data.total_other_income / 100_000_000),
        orig: data.total_other_income / 100_000_000,
        pct: data.other_pct,
        itemStyle: { color: COLORS.other },
      });
    }
    if (pieData.length === 0) {
      return null;
    }
    return {
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const p = params as { name?: string; data?: unknown };
          const name = p.name ?? "";
          const row = p.data as { orig?: number } | undefined;
          const orig = row?.orig ?? 0;
          return `${name}: ${orig >= 0 ? "+" : ""}${orig.toFixed(2)} 亿`;
        },
      },
      series: [
        {
          type: "pie",
          radius: ["40%", "65%"],
          data: pieData.map((d) => ({
            name: `${d.name} ${d.pct.toFixed(1)}%`,
            value: d.value,
            orig: d.orig,
            itemStyle: d.itemStyle,
          })),
          label: { fontSize: 11 },
        },
      ],
    };
  }, [data]);

  const trendOption = useMemo<EChartsOption | null>(() => {
    if (!data?.trend_data?.length) {
      return null;
    }
    const periods = data.trend_data.map((t) =>
      (t.period_label ?? t.period).replace("年", "-").replace("月", ""),
    );
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: { type: "category", data: periods, axisLabel: { fontSize: 11, color: "#5c6b82" } },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}亿`, color: "#5c6b82" },
        splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
      },
      series: [
        { name: "利息收入", type: "bar", stack: "t", data: data.trend_data.map((t) => t.interest_income / 100_000_000), itemStyle: { color: COLORS.interest } },
        { name: "公允价值变动", type: "bar", stack: "t", data: data.trend_data.map((t) => t.fair_value_change / 100_000_000), itemStyle: { color: COLORS.fairValue } },
        {
          name: "投资收益",
          type: "bar",
          stack: "t",
          data: data.trend_data.map((t) => t.capital_gain / 100_000_000),
          itemStyle: { color: COLORS.capital, borderRadius: [4, 4, 0, 0] },
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
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 16,
        }}
      >
        <div style={{ ...cardStyle, padding: 16 }}>
          <div style={{ fontSize: 12, color: "#5c6b82" }}>总损益</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: data.total_pnl >= 0 ? "#15803d" : "#b91c1c" }}>
            {formatYi(data.total_pnl)}
          </div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{data.report_period}</div>
        </div>
        <div style={{ ...cardStyle, padding: 16, background: "#e8f6ee" }}>
          <div style={{ fontSize: 12, color: "#15803d" }}>利息收入</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#15803d" }}>{formatYi(data.total_interest_income)}</div>
          <div style={{ fontSize: 12, color: "#2f8f63" }}>占比 {data.interest_pct.toFixed(1)}%</div>
        </div>
        <div style={{ ...cardStyle, padding: 16, background: "#edf3ff" }}>
          <div style={{ fontSize: 12, color: "#1f5eff" }}>公允价值变动</div>
          <div
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: data.total_fair_value_change >= 0 ? "#1f5eff" : "#b91c1c",
            }}
          >
            {formatYi(data.total_fair_value_change)}
          </div>
          <div style={{ fontSize: 12, color: "#5c6b82" }}>占比 {data.fair_value_pct.toFixed(1)}%</div>
        </div>
        <div style={{ ...cardStyle, padding: 16, background: "#fff4e8" }}>
          <div style={{ fontSize: 12, color: "#b35a16" }}>投资收益</div>
          <div
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: data.total_capital_gain >= 0 ? "#b35a16" : "#b91c1c",
            }}
          >
            {formatYi(data.total_capital_gain)}
          </div>
          <div style={{ fontSize: 12, color: "#5c6b82" }}>占比 {data.capital_gain_pct.toFixed(1)}%</div>
        </div>
      </div>

      {pieOption && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>损益构成占比</h3>
          <ReactECharts option={pieOption} style={{ height: 300 }} notMerge lazyUpdate />
        </div>
      )}

      {trendOption && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>损益构成趋势</h3>
          <ReactECharts option={trendOption} style={{ height: 300 }} notMerge lazyUpdate />
        </div>
      )}

      {data.items.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>分类别损益构成</h3>
          <div style={{ overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "#f0f3f8" }}>
                  <th style={{ textAlign: "left", padding: 10 }}>资产类别</th>
                  <th style={{ textAlign: "right", padding: 10 }}>总损益(亿)</th>
                  <th style={{ textAlign: "right", padding: 10 }}>利息(亿)</th>
                  <th style={{ textAlign: "right", padding: 10 }}>公允(亿)</th>
                  <th style={{ textAlign: "right", padding: 10 }}>投资收益(亿)</th>
                  <th style={{ textAlign: "right", padding: 10 }}>利息占比</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid #eef2f7" }}>
                    <td style={{ padding: 10, fontWeight: 500 }}>{item.category}</td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: 10,
                        color: item.total_pnl >= 0 ? "#15803d" : "#b91c1c",
                      }}
                    >
                      {(item.total_pnl / 100_000_000).toFixed(2)}
                    </td>
                    <td style={{ textAlign: "right", padding: 10, color: "#15803d" }}>
                      {(item.interest_income / 100_000_000).toFixed(2)}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: 10,
                        color: item.fair_value_change >= 0 ? "#1f5eff" : "#b91c1c",
                      }}
                    >
                      {(item.fair_value_change / 100_000_000).toFixed(2)}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: 10,
                        color: item.capital_gain >= 0 ? "#b35a16" : "#b91c1c",
                      }}
                    >
                      {(item.capital_gain / 100_000_000).toFixed(2)}
                    </td>
                    <td style={{ textAlign: "right", padding: 10 }}>{item.interest_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
