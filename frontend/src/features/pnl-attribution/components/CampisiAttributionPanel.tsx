import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { CampisiAttributionPayload, CampisiFourEffectsPayload } from "../../../api/contracts";

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

type NormalizedCampisiData = {
  total_income: number;
  total_treasury_effect: number;
  total_spread_effect: number;
  total_selection_effect: number;
  income_contribution_pct: number;
  treasury_contribution_pct: number;
  spread_contribution_pct: number;
  selection_contribution_pct: number;
  interpretation: string;
  items: Array<{
    category: string;
    income_return: number;
    treasury_effect: number;
    spread_effect: number;
    selection_effect: number;
  }>;
};

type Props = {
  data: CampisiAttributionPayload | CampisiFourEffectsPayload | null;
};

function normalizeCampisiData(
  data: CampisiAttributionPayload | CampisiFourEffectsPayload | null,
): NormalizedCampisiData | null {
  if (!data) {
    return null;
  }

  if ("totals" in data) {
    const totalReturn = data.totals.total_return || 0;
    const pct = (value: number) => (totalReturn !== 0 ? (value / totalReturn) * 100 : 0);
    return {
      total_income: data.totals.income_return,
      total_treasury_effect: data.totals.treasury_effect,
      total_spread_effect: data.totals.spread_effect,
      total_selection_effect: data.totals.selection_effect,
      income_contribution_pct: pct(data.totals.income_return),
      treasury_contribution_pct: pct(data.totals.treasury_effect),
      spread_contribution_pct: pct(data.totals.spread_effect),
      selection_contribution_pct: pct(data.totals.selection_effect),
      interpretation: `期间 ${data.period_start} 至 ${data.period_end} 的四效应归因拆解。`,
      items: data.by_asset_class.map((row) => ({
        category: row.asset_class,
        income_return: row.income_return,
        treasury_effect: row.treasury_effect,
        spread_effect: row.spread_effect,
        selection_effect: row.selection_effect,
      })),
    };
  }

  return {
    total_income: data.total_income,
    total_treasury_effect: data.total_treasury_effect,
    total_spread_effect: data.total_spread_effect,
    total_selection_effect: data.total_selection_effect,
    income_contribution_pct: data.income_contribution_pct,
    treasury_contribution_pct: data.treasury_contribution_pct,
    spread_contribution_pct: data.spread_contribution_pct,
    selection_contribution_pct: data.selection_contribution_pct,
    interpretation: data.interpretation,
    items: data.items,
  };
}

export function CampisiAttributionPanel({ data }: Props) {
  const normalized = useMemo(() => normalizeCampisiData(data), [data]);

  const barOption = useMemo<EChartsOption | null>(() => {
    if (!normalized) {
      return null;
    }
    const names = ["收入效应", "国债曲线", "利差效应", "选择效应"];
    const values = [
      normalized.total_income,
      normalized.total_treasury_effect,
      normalized.total_spread_effect,
      normalized.total_selection_effect,
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
  }, [normalized]);

  if (!normalized) {
    return (
      <div style={cardStyle}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#162033" }}>
          Campisi 四效应归因
        </h3>
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
        {normalized.interpretation}
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
          收入 {normalized.income_contribution_pct.toFixed(1)}% · {formatYi(normalized.total_income)}
        </div>
        <div>
          国债 {normalized.treasury_contribution_pct.toFixed(1)}% · {formatYi(normalized.total_treasury_effect)}
        </div>
        <div>
          利差 {normalized.spread_contribution_pct.toFixed(1)}% · {formatYi(normalized.total_spread_effect)}
        </div>
        <div>
          选择 {normalized.selection_contribution_pct.toFixed(1)}% · {formatYi(normalized.total_selection_effect)}
        </div>
      </div>
      {barOption && <ReactECharts option={barOption} style={{ height: 220 }} notMerge lazyUpdate />}
      {normalized.items.length > 0 && (
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
              {normalized.items.map((row, index) => (
                <tr key={`${row.category}-${index}`} style={{ borderBottom: "1px solid #eef2f7" }}>
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
