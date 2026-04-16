import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { CarryRollDownPayload, KRDAttributionPayload, SpreadAttributionPayload } from "../../../api/contracts";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

type Props = {
  carryData: CarryRollDownPayload | null;
  spreadData: SpreadAttributionPayload | null;
  krdData: KRDAttributionPayload | null;
};

/** 高级归因：Carry / Roll-down、利差解读、KRD 久期桶分解。 */
export function AdvancedAttributionChart({ carryData, spreadData, krdData }: Props) {
  const carryOption = useMemo<EChartsOption | null>(() => {
    if (!carryData?.items?.length) {
      return null;
    }
    const rows = carryData.items.slice(0, 10);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: {
        type: "category",
        data: rows.map((r) => (r.category.length > 8 ? `${r.category.slice(0, 8)}…` : r.category)),
        axisLabel: { fontSize: 11, rotate: 20, color: "#5c6b82" },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}%`, color: "#5c6b82" },
        splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
      },
      series: [
        { name: "Carry", type: "bar", data: rows.map((r) => r.carry), itemStyle: { color: "#22c55e", borderRadius: [4, 4, 0, 0] } },
        { name: "Roll-down", type: "bar", data: rows.map((r) => r.rolldown), itemStyle: { color: "#3b82f6", borderRadius: [4, 4, 0, 0] } },
      ],
    };
  }, [carryData]);

  const krdOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    const tenors = krdData.buckets.map((b) => b.tenor);
    const contrib = krdData.buckets.map((b) => b.duration_contribution / 100_000_000);
    const ychg = krdData.buckets.map((b) => b.yield_change ?? 0);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 52, right: 52, top: 24, bottom: 48 },
      xAxis: { type: "category", data: tenors, axisLabel: { fontSize: 11, color: "#5c6b82" } },
      yAxis: [
        {
          type: "value",
          name: "久期贡献(亿)",
          axisLabel: { color: "#5c6b82" },
          splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: { color: "#5c6b82" },
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
            itemStyle: { color: v >= 0 ? "#22c55e" : "#ef4444", borderRadius: [4, 4, 0, 0] },
          })),
        },
        {
          name: "收益率变动",
          type: "line",
          yAxisIndex: 1,
          data: ychg,
          smooth: true,
          symbolSize: 8,
          lineStyle: { color: "#3b82f6", width: 2 },
        },
      ],
    };
  }, [krdData]);

  const krdCompareOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: { type: "category", data: krdData.buckets.map((b) => b.tenor), axisLabel: { fontSize: 11 } },
      yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${v}%`, color: "#5c6b82" } },
      series: [
        {
          name: "贡献占比",
          type: "bar",
          data: krdData.buckets.map((b) => b.contribution_pct),
          itemStyle: { color: "#3b82f6", borderRadius: [4, 4, 0, 0] },
        },
        {
          name: "市值占比",
          type: "bar",
          data: krdData.buckets.map((b) => b.weight),
          itemStyle: { color: "#22c55e", borderRadius: [4, 4, 0, 0] },
        },
      ],
    };
  }, [krdData]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 12,
        }}
      >
        {carryData && (
          <>
            <div style={{ ...cardStyle, padding: 16, background: "#e8f6ee", borderColor: "#c8e8d5" }}>
              <div style={{ fontSize: 12, color: "#15803d" }}>组合 Carry</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: carryData.portfolio_carry >= 0 ? "#15803d" : "#b91c1c" }}>
                {carryData.portfolio_carry.toFixed(2)}%
              </div>
              <div style={{ fontSize: 11, color: "#2f8f63" }}>票息 − FTP</div>
            </div>
            <div style={{ ...cardStyle, padding: 16, background: "#edf3ff", borderColor: "#cddcff" }}>
              <div style={{ fontSize: 12, color: "#1f5eff" }}>组合 Roll-down</div>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: carryData.portfolio_rolldown >= 0 ? "#1f5eff" : "#b35a16",
                }}
              >
                {carryData.portfolio_rolldown.toFixed(2)}%
              </div>
              <div style={{ fontSize: 11, color: "#5c6b82" }}>骑乘</div>
            </div>
            <div style={{ ...cardStyle, padding: 16, background: "#f6f0ff", borderColor: "#e4d6fb" }}>
              <div style={{ fontSize: 12, color: "#6d3bb3" }}>静态收益（年化近似）</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#6d3bb3" }}>
                {(carryData.portfolio_static_return * 12).toFixed(2)}%
              </div>
              <div style={{ fontSize: 11, color: "#5c6b82" }}>Carry + Roll-down</div>
            </div>
          </>
        )}
        {spreadData && (
          <>
            <div style={{ ...cardStyle, padding: 16, background: "#fff4e8", borderColor: "#f1d3b5" }}>
              <div style={{ fontSize: 12, color: "#b35a16" }}>国债曲线效应</div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: spreadData.total_treasury_effect >= 0 ? "#15803d" : "#b91c1c",
                }}
              >
                {formatYi(spreadData.total_treasury_effect)}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: 16, background: "#fde8e8", borderColor: "#f5c2c2" }}>
              <div style={{ fontSize: 12, color: "#b91c1c" }}>10Y 变动</div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: (spreadData.treasury_10y_change ?? 0) <= 0 ? "#15803d" : "#b91c1c",
                }}
              >
                {spreadData.treasury_10y_change !== null
                  ? `${spreadData.treasury_10y_change >= 0 ? "+" : ""}${spreadData.treasury_10y_change.toFixed(0)} BP`
                  : "—"}
              </div>
            </div>
          </>
        )}
        {krdData && (
          <div style={{ ...cardStyle, padding: 16, background: "#e6f9fc", borderColor: "#b8eaf0" }}>
            <div style={{ fontSize: 12, color: "#0e7490" }}>组合 DV01</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#0e7490" }}>
              {(krdData.portfolio_dv01 / 10_000).toFixed(0)} 万
            </div>
            <div style={{ fontSize: 11, color: "#5c6b82" }}>每 BP 价值变动</div>
          </div>
        )}
      </div>

      {carryOption && carryData && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
            {"Carry & Roll-down"} 分解
          </h3>
          <ReactECharts option={carryOption} style={{ height: 300 }} notMerge lazyUpdate />
          <div style={{ marginTop: 12, overflow: "auto", maxHeight: 220 }}>
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <thead style={{ background: "#f0f3f8", position: "sticky", top: 0 }}>
                <tr>
                  <th style={{ textAlign: "left", padding: 8 }}>类别</th>
                  <th style={{ textAlign: "right", padding: 8 }}>市值(亿)</th>
                  <th style={{ textAlign: "right", padding: 8 }}>票息%</th>
                  <th style={{ textAlign: "right", padding: 8 }}>FTP%</th>
                  <th style={{ textAlign: "right", padding: 8 }}>Carry%</th>
                  <th style={{ textAlign: "right", padding: 8 }}>久期</th>
                  <th style={{ textAlign: "right", padding: 8 }}>Roll%</th>
                </tr>
              </thead>
              <tbody>
                {carryData.items.slice(0, 8).map((item, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid #eef2f7" }}>
                    <td style={{ padding: 8 }}>{item.category}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{(item.market_value / 1e8).toFixed(1)}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{item.coupon_rate.toFixed(2)}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{item.funding_cost.toFixed(2)}</td>
                    <td style={{ textAlign: "right", padding: 8, color: item.carry >= 0 ? "#15803d" : "#b91c1c" }}>
                      {item.carry.toFixed(2)}
                    </td>
                    <td style={{ textAlign: "right", padding: 8 }}>{item.duration.toFixed(2)}</td>
                    <td style={{ textAlign: "right", padding: 8, color: item.rolldown >= 0 ? "#1f5eff" : "#b35a16" }}>
                      {item.rolldown.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {spreadData?.interpretation && (
        <div style={cardStyle}>
          <h4 style={{ margin: "0 0 8px", fontSize: 15, fontWeight: 600, color: "#162033" }}>利差归因</h4>
          <p style={{ margin: 0, fontSize: 14, color: "#5c6b82", lineHeight: 1.6 }}>{spreadData.interpretation}</p>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: "#94a3b8" }}>
            区间 {spreadData.start_date} ~ {spreadData.end_date}
          </p>
        </div>
      )}

      {krdOption && krdData && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>KRD 归因</h3>
          {krdData.curve_interpretation && (
            <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82", background: "#f7f9fc", padding: 12, borderRadius: 12 }}>
              曲线形态：{krdData.curve_interpretation}
              {krdData.max_contribution_tenor ? (
                <span style={{ marginLeft: 12, color: "#1f5eff" }}>
                  最大贡献期限 {krdData.max_contribution_tenor}（{formatYi(krdData.max_contribution_value)}）
                </span>
              ) : null}
            </p>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
            <ReactECharts option={krdOption} style={{ height: 280 }} notMerge lazyUpdate />
            {krdCompareOption && (
              <ReactECharts option={krdCompareOption} style={{ height: 280 }} notMerge lazyUpdate />
            )}
          </div>
          <div style={{ marginTop: 12, overflow: "auto" }}>
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <thead style={{ background: "#f0f3f8" }}>
                <tr>
                  <th style={{ textAlign: "left", padding: 8 }}>期限</th>
                  <th style={{ textAlign: "right", padding: 8 }}>债券数</th>
                  <th style={{ textAlign: "right", padding: 8 }}>市值(亿)</th>
                  <th style={{ textAlign: "right", padding: 8 }}>占比%</th>
                  <th style={{ textAlign: "right", padding: 8 }}>久期</th>
                  <th style={{ textAlign: "right", padding: 8 }}>Δyield</th>
                  <th style={{ textAlign: "right", padding: 8 }}>贡献(亿)</th>
                  <th style={{ textAlign: "right", padding: 8 }}>贡献占比%</th>
                </tr>
              </thead>
              <tbody>
                {krdData.buckets.map((b, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid #eef2f7" }}>
                    <td style={{ padding: 8, fontWeight: 500 }}>{b.tenor}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{b.bond_count}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{(b.market_value / 1e8).toFixed(1)}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{b.weight.toFixed(1)}</td>
                    <td style={{ textAlign: "right", padding: 8 }}>{b.bucket_duration.toFixed(2)}</td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: 8,
                        color: (b.yield_change ?? 0) <= 0 ? "#15803d" : "#b91c1c",
                      }}
                    >
                      {b.yield_change !== null ? b.yield_change.toFixed(1) : "—"}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        padding: 8,
                        color: b.duration_contribution >= 0 ? "#15803d" : "#b91c1c",
                      }}
                    >
                      {(b.duration_contribution / 1e8).toFixed(2)}
                    </td>
                    <td style={{ textAlign: "right", padding: 8, fontWeight: 600 }}>{b.contribution_pct.toFixed(1)}</td>
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
