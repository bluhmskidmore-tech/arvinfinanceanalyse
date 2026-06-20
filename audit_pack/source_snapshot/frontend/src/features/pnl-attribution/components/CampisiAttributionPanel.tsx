import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { CampisiAttributionPayload, CampisiFourEffectsPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
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
  state: DataSectionState;
  onRetry: () => void;
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
    total_income: data.total_income.raw ?? 0,
    total_treasury_effect: data.total_treasury_effect.raw ?? 0,
    total_spread_effect: data.total_spread_effect.raw ?? 0,
    total_selection_effect: data.total_selection_effect.raw ?? 0,
    income_contribution_pct: data.income_contribution_pct.raw ?? 0,
    treasury_contribution_pct: data.treasury_contribution_pct.raw ?? 0,
    spread_contribution_pct: data.spread_contribution_pct.raw ?? 0,
    selection_contribution_pct: data.selection_contribution_pct.raw ?? 0,
    interpretation: data.interpretation,
    items: data.items.map((row) => ({
      category: row.category,
      income_return: row.income_return.raw ?? 0,
      treasury_effect: row.treasury_effect.raw ?? 0,
      spread_effect: row.spread_effect.raw ?? 0,
      selection_effect: row.selection_effect.raw ?? 0,
    })),
  };
}

export function CampisiAttributionPanel({ data, state, onRetry }: Props) {
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
    const colors = values.map((v) =>
      v >= 0 ? designTokens.color.semantic.profit : designTokens.color.semantic.loss,
    );
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => {
          const n = Array.isArray(value) ? Number(value[0]) : Number(value);
          return `${Number.isFinite(n) ? n.toFixed(2) : "—"} 亿`;
        },
      },
      grid: { left: 100, right: designTokens.space[6], top: designTokens.space[4], bottom: designTokens.space[6] },
      xAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}`,
          color: designTokens.color.neutral[700],
        },
        splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[100] } },
      },
      yAxis: {
        type: "category",
        data: names,
        axisLabel: { fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] },
      },
      series: [
        {
          type: "bar",
          data: values.map((v, i) => ({
            value: v,
            itemStyle: {
              color: colors[i],
              borderRadius: [0, designTokens.radius.sm, designTokens.radius.sm, 0],
            },
          })),
        },
      ],
    };
  }, [normalized]);

  return (
    <DataSection title="Campisi 四效应归因（组合）" state={state} onRetry={onRetry}>
      {!normalized ? (
        <div style={cardStyle}>
          <p style={{ margin: 0, color: designTokens.color.neutral[700] }}>暂无 Campisi 归因数据。</p>
        </div>
      ) : (
        <div style={cardStyle}>
          <p
            style={{
              margin: `0 0 ${designTokens.space[4]}px`,
              fontSize: designTokens.fontSize[13],
              color: designTokens.color.neutral[700],
              lineHeight: designTokens.lineHeight.normal,
            }}
          >
            {normalized.interpretation}
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: designTokens.space[3],
              marginBottom: designTokens.space[4],
              fontSize: designTokens.fontSize[12],
              color: designTokens.color.neutral[700],
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
            <div style={{ marginTop: designTokens.space[5], overflow: "auto" }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: designTokens.fontSize[12],
                }}
              >
                <thead>
                  <tr style={{ background: designTokens.color.neutral[100] }}>
                    <th style={{ textAlign: "left", padding: designTokens.space[2] }}>类别</th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      收入(亿)
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      国债(亿)
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      利差(亿)
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      选择(亿)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {normalized.items.map((row, index) => (
                    <tr
                      key={`${row.category}-${index}`}
                      style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                    >
                      <td style={{ padding: designTokens.space[2] }}>{row.category}</td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(row.income_return / 100_000_000).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(row.treasury_effect / 100_000_000).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(row.spread_effect / 100_000_000).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(row.selection_effect / 100_000_000).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </DataSection>
  );
}
