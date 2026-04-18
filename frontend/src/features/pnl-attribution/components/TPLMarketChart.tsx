import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { TPLMarketCorrelationPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";

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

function correlationLabel(corr: number | null): { level: string; color: string; bg: string } {
  if (corr === null) {
    return { level: "无数据", color: "#5c6b82", bg: "#f0f3f8" };
  }
  const a = Math.abs(corr);
  if (a >= 0.7) {
    return corr < 0
      ? { level: "强相关", color: "#15803d", bg: "#e8f6ee" }
      : { level: "强相关", color: "#b91c1c", bg: "#fde8e8" };
  }
  if (a >= 0.4) {
    return { level: "中等相关", color: "#1f5eff", bg: "#edf3ff" };
  }
  if (a >= 0.2) {
    return { level: "弱相关", color: "#b35a16", bg: "#fff4e8" };
  }
  return { level: "无显著相关", color: "#5c6b82", bg: "#f0f3f8" };
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
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 56, right: 56, top: 28, bottom: 52 },
      xAxis: { type: "category", data: periods, axisLabel: { fontSize: 11, color: "#5c6b82" } },
      yAxis: [
        {
          type: "value",
          name: "TPL(亿)",
          axisLabel: { formatter: (v: number) => `${v.toFixed(1)}`, color: "#5c6b82" },
          splitLine: { lineStyle: { type: "dashed", color: "#e8edf5" } },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: { formatter: (v: number) => `${v}`, color: "#5c6b82" },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "TPL公允价值变动",
          type: "bar",
          yAxisIndex: 0,
          data: tpl,
          itemStyle: { color: "#3b82f6", borderRadius: [4, 4, 0, 0] },
        },
        {
          name: "国债收益率变动",
          type: "line",
          yAxisIndex: 1,
          data: bp,
          smooth: true,
          symbolSize: 8,
          lineStyle: { color: "#ef4444", width: 2 },
        },
      ],
    };
  }, [data]);

  const corr = correlationLabel(data?.correlation_coefficient?.raw ?? null);
  const treasuryBpTotal = data ? treasuryTotalChangeBp(data) : null;

  return (
    <DataSection title="TPL 市场相关性" state={state} onRetry={onRetry}>
      {data ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 16,
            }}
          >
            <div style={{ ...cardStyle, padding: 16, background: corr.bg }}>
              <div style={{ fontSize: 12, color: "#5c6b82", marginBottom: 4 }}>相关系数</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: corr.color }}>
                {data.correlation_coefficient !== null
                  ? (data.correlation_coefficient.raw ?? 0).toFixed(3)
                  : "—"}
              </div>
              <div style={{ fontSize: 12, color: corr.color }}>{corr.level}</div>
            </div>
            <div style={{ ...cardStyle, padding: 16 }}>
              <div style={{ fontSize: 12, color: "#5c6b82", marginBottom: 4 }}>累计 TPL 公允价值变动</div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: (data.total_tpl_fv_change.raw ?? 0) >= 0 ? "#15803d" : "#b91c1c",
                }}
              >
                {formatYi(data.total_tpl_fv_change.raw ?? undefined)}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: 16 }}>
              <div style={{ fontSize: 12, color: "#5c6b82", marginBottom: 4 }}>累计国债收益率变动</div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: (treasuryBpTotal ?? 0) <= 0 ? "#15803d" : "#b91c1c",
                }}
              >
                {treasuryBpTotal !== null
                  ? `${treasuryBpTotal >= 0 ? "+" : ""}${treasuryBpTotal.toFixed(1)} BP`
                  : "—"}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: 16 }}>
              <div style={{ fontSize: 12, color: "#5c6b82", marginBottom: 4 }}>分析期间</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#162033" }}>{data.num_periods} 个月</div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>
                {data.start_period} ~ {data.end_period}
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <h4 style={{ margin: "0 0 8px", fontSize: 15, fontWeight: 600, color: "#162033" }}>相关性解读</h4>
            <p style={{ margin: 0, fontSize: 14, color: "#5c6b82", lineHeight: 1.6 }}>{data.correlation_interpretation}</p>
            {data.analysis_summary ? (
              <p style={{ margin: "10px 0 0", fontSize: 13, color: "#94a3b8" }}>{data.analysis_summary}</p>
            ) : null}
          </div>

          {chartOption && (
            <div style={cardStyle}>
              <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600, color: "#162033" }}>
                TPL 公允价值变动 vs 国债收益率变动
              </h3>
              <ReactECharts option={chartOption} style={{ height: 360 }} notMerge lazyUpdate />
              <p style={{ margin: "12px 0 0", fontSize: 12, color: "#94a3b8", textAlign: "center" }}>
                利率下行（折线下降）时，债券估值通常上行，TPL 变动多为正（蓝柱向上）。
              </p>
            </div>
          )}

          <div style={cardStyle}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600, color: "#162033" }}>月度明细</h3>
            <div style={{ overflow: "auto", maxHeight: 320 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead style={{ position: "sticky", top: 0, background: "#f0f3f8" }}>
                  <tr>
                    <th style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #e4ebf5" }}>月份</th>
                    <th style={{ textAlign: "right", padding: 10, borderBottom: "1px solid #e4ebf5" }}>TPL 规模(亿)</th>
                    <th style={{ textAlign: "right", padding: 10, borderBottom: "1px solid #e4ebf5" }}>TPL 损益(亿)</th>
                    <th style={{ textAlign: "right", padding: 10, borderBottom: "1px solid #e4ebf5" }}>10Y(%)</th>
                    <th style={{ textAlign: "right", padding: 10, borderBottom: "1px solid #e4ebf5" }}>利率变动(BP)</th>
                    <th style={{ textAlign: "right", padding: 10, borderBottom: "1px solid #e4ebf5" }}>DR007(%)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.data_points.map((point, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #eef2f7" }}>
                      <td style={{ padding: 10 }}>{point.period_label}</td>
                      <td style={{ textAlign: "right", padding: 10, fontVariantNumeric: "tabular-nums" }}>
                        {((point.tpl_scale.raw ?? 0) / 100_000_000).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: 10,
                          color: (point.tpl_fair_value_change.raw ?? 0) >= 0 ? "#15803d" : "#b91c1c",
                        }}
                      >
                        {((point.tpl_fair_value_change.raw ?? 0) / 100_000_000).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", padding: 10 }}>
                        {point.treasury_10y !== null ? (point.treasury_10y.raw ?? 0).toFixed(3) : "—"}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: 10,
                          color: (point.treasury_10y_change?.raw ?? 0) <= 0 ? "#15803d" : "#b91c1c",
                        }}
                      >
                        {point.treasury_10y_change !== null
                          ? `${(point.treasury_10y_change.raw ?? 0) >= 0 ? "+" : ""}${(point.treasury_10y_change.raw ?? 0).toFixed(1)}`
                          : "—"}
                      </td>
                      <td style={{ textAlign: "right", padding: 10 }}>
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
