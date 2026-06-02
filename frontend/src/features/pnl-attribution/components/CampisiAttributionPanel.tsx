import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  CampisiAttributionPayload,
  CampisiFourEffectsPayload,
} from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.sm,
  border: "1px solid #ded6ca",
  background: "#ffffff",
  boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(220px, 1.2fr) minmax(220px, 1fr)",
  gap: designTokens.space[4],
  alignItems: "stretch",
  marginBottom: designTokens.space[4],
} as const;

const insightBoxStyle = {
  padding: designTokens.space[4],
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.neutral[200]}`,
} as const;

const smallLabelStyle = {
  fontSize: designTokens.fontSize[12],
  color: designTokens.color.neutral[600],
  marginBottom: designTokens.space[2],
} as const;

const capabilityBoundaryStyle = {
  marginBottom: designTokens.space[4],
  padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: "#f8fafc",
  color: designTokens.color.neutral[700],
  fontSize: designTokens.fontSize[12],
  lineHeight: designTokens.lineHeight.normal,
} as const;

function formatYi(value: number): string {
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function formatOptionalYi(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? formatYi(value)
    : "不可用";
}

function pctPoints(
  value: { raw: number | null; unit?: string } | null | undefined,
): number {
  const raw = value?.raw ?? 0;
  return value?.unit === "pct" && Math.abs(raw) <= 1 ? raw * 100 : raw;
}

type CampisiEffectKey = "income" | "treasury" | "spread" | "selection";

type CampisiEffect = {
  key: CampisiEffectKey;
  label: string;
  amount: number;
  share: number;
  role: string;
};

type NormalizedCampisiData = {
  total_return: number;
  total_income: number;
  total_treasury_effect: number;
  total_spread_effect: number;
  total_selection_effect: number;
  income_contribution_pct: number;
  treasury_contribution_pct: number;
  spread_contribution_pct: number;
  selection_contribution_pct: number;
  interpretation: string;
  formal_closure?: CampisiFourEffectsPayload["formal_closure"];
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
    const pct = (value: number) =>
      totalReturn !== 0 ? (value / totalReturn) * 100 : 0;
    return {
      total_return: totalReturn,
      total_income: data.totals.income_return,
      total_treasury_effect: data.totals.treasury_effect,
      total_spread_effect: data.totals.spread_effect,
      total_selection_effect: data.totals.selection_effect,
      income_contribution_pct: pct(data.totals.income_return),
      treasury_contribution_pct: pct(data.totals.treasury_effect),
      spread_contribution_pct: pct(data.totals.spread_effect),
      selection_contribution_pct: pct(data.totals.selection_effect),
      interpretation: `期间 ${data.period_start} 至 ${data.period_end} 的四效应归因拆解。`,
      formal_closure: data.formal_closure,
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
    total_return: data.total_return.raw ?? 0,
    total_income: data.total_income.raw ?? 0,
    total_treasury_effect: data.total_treasury_effect.raw ?? 0,
    total_spread_effect: data.total_spread_effect.raw ?? 0,
    total_selection_effect: data.total_selection_effect.raw ?? 0,
    income_contribution_pct: pctPoints(data.income_contribution_pct),
    treasury_contribution_pct: pctPoints(data.treasury_contribution_pct),
    spread_contribution_pct: pctPoints(data.spread_contribution_pct),
    selection_contribution_pct: pctPoints(data.selection_contribution_pct),
    interpretation: data.interpretation,
    formal_closure: undefined,
    items: data.items.map((row) => ({
      category: row.category,
      income_return: row.income_return.raw ?? 0,
      treasury_effect: row.treasury_effect.raw ?? 0,
      spread_effect: row.spread_effect.raw ?? 0,
      selection_effect: row.selection_effect.raw ?? 0,
    })),
  };
}

function buildEffectRows(normalized: NormalizedCampisiData): CampisiEffect[] {
  return [
    {
      key: "income",
      label: "收入效应",
      amount: normalized.total_income,
      share: normalized.income_contribution_pct,
      role: "票息和持有收益，是债券组合最稳定的收益底盘。",
    },
    {
      key: "treasury",
      label: "国债曲线",
      amount: normalized.total_treasury_effect,
      share: normalized.treasury_contribution_pct,
      role: "无风险利率曲线和 roll-down 带来的估值影响。",
    },
    {
      key: "spread",
      label: "信用利差",
      amount: normalized.total_spread_effect,
      share: normalized.spread_contribution_pct,
      role: "信用利差收窄或走阔带来的价格影响。",
    },
    {
      key: "selection",
      label: "选择效应",
      amount: normalized.total_selection_effect,
      share: normalized.selection_contribution_pct,
      role: "剩余已确认损益，包括个券表现、交易和会计口径差异。",
    },
  ];
}

function effectColor(amount: number): string {
  if (amount > 0) {
    return designTokens.color.semantic.profit;
  }
  if (amount < 0) {
    return designTokens.color.semantic.loss;
  }
  return designTokens.color.neutral[500];
}

function displayEffectLabel(effect: CampisiEffect): string {
  return effect.key === "selection" ? "剩余/选券" : effect.label;
}

function quietEffectLabels(effects: CampisiEffect[], totalReturn: number): string {
  const threshold = Math.max(Math.abs(totalReturn) * 0.005, 1_000_000);
  const labels = effects
    .filter((effect) => Math.abs(effect.amount) <= threshold)
    .map((effect) => displayEffectLabel(effect));
  return labels.length ? labels.join("、") : "无";
}

export function CampisiAttributionPanel({ data, state, onRetry }: Props) {
  const normalized = useMemo(() => normalizeCampisiData(data), [data]);
  const effectRows = useMemo(
    () => (normalized ? buildEffectRows(normalized) : []),
    [normalized],
  );
  const primaryEffect = useMemo(
    () =>
      [...effectRows].sort(
        (left, right) => Math.abs(right.amount) - Math.abs(left.amount),
      )[0],
    [effectRows],
  );
  const maxEffectAbs = Math.max(
    1,
    ...effectRows.map((effect) => Math.abs(effect.amount)),
  );

  const barOption = useMemo<EChartsOption | null>(() => {
    if (!normalized) {
      return null;
    }
    const values = effectRows.map((effect) => effect.amount / 100_000_000);
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => {
          const n = Array.isArray(value) ? Number(value[0]) : Number(value);
          return `${Number.isFinite(n) ? n.toFixed(2) : "—"} 亿`;
        },
      },
      grid: {
        left: 100,
        right: designTokens.space[6],
        top: designTokens.space[4],
        bottom: designTokens.space[6],
      },
      xAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}`,
          color: designTokens.color.neutral[700],
        },
        splitLine: {
          lineStyle: { type: "dashed", color: designTokens.color.neutral[100] },
        },
      },
      yAxis: {
        type: "category",
        data: effectRows.map((effect) => displayEffectLabel(effect)),
        axisLabel: {
          fontSize: designTokens.fontSize[12],
          color: designTokens.color.neutral[700],
        },
      },
      series: [
        {
          type: "bar",
          data: values.map((value, index) => ({
            value,
            itemStyle: {
              color: effectColor(effectRows[index]?.amount ?? 0),
              borderRadius: [
                0,
                designTokens.radius.sm,
                designTokens.radius.sm,
                0,
              ],
            },
          })),
        },
      ],
    };
  }, [effectRows, normalized]);

  return (
    <DataSection
      title="Campisi 四效应归因（组合）"
      state={state}
      onRetry={onRetry}
    >
      {!normalized ? (
        <div style={cardStyle}>
          <p style={{ margin: 0, color: designTokens.color.neutral[700] }}>
            暂无 Campisi 归因数据。
          </p>
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
          <div data-testid="campisi-capability-boundary" style={capabilityBoundaryStyle}>
            当前实现边界：本页已做到正式 PnL 闭合、票息/利率/利差/剩余拆分和到期桶查看；尚未实现交易员能力评价、FVOCI/FVTPL 浮盈浮亏专项解释、曲线形态策略归因、个券跑赢同类基准和估值噪音诊断。
          </div>
          {normalized.formal_closure &&
          normalized.formal_closure.status !== "closed" ? (
            <div
              data-testid="campisi-formal-closure-warning"
              style={{
                marginBottom: designTokens.space[4],
                padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
                borderLeft: `4px solid ${designTokens.color.neutral[600]}`,
                background: "#fff7ed",
                color: designTokens.color.neutral[800],
                fontSize: designTokens.fontSize[12],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              <div
                style={{ fontWeight: 700, marginBottom: designTokens.space[1] }}
              >
                未闭合到正式 PnL
              </div>
              <div>
                Campisi{" "}
                {formatOptionalYi(
                  normalized.formal_closure.campisi_total_return,
                )}
                ，正式 PnL{" "}
                {formatOptionalYi(normalized.formal_closure.formal_actual_pnl)}
                ，需要残差{" "}
                {formatOptionalYi(
                  normalized.formal_closure.residual_to_formal_pnl,
                )}{" "}
                才能闭合。
              </div>
            </div>
          ) : null}
          {primaryEffect ? (
            <div data-testid="campisi-driver-summary" style={summaryGridStyle}>
              <div style={{ ...insightBoxStyle, background: "#f8fafc" }}>
                <div style={smallLabelStyle}>一眼结论</div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[16],
                    fontWeight: 700,
                    color: designTokens.color.neutral[900],
                    marginBottom: designTokens.space[2],
                  }}
                >
                  主要贡献：{displayEffectLabel(primaryEffect)}
                </div>
                <div
                  style={{
                    color: designTokens.color.neutral[700],
                    fontSize: designTokens.fontSize[13],
                    lineHeight: designTokens.lineHeight.normal,
                  }}
                >
                  {formatYi(primaryEffect.amount)}，约{" "}
                  {Math.abs(primaryEffect.share).toFixed(1)}% 的本期 Campisi
                  PnL 来自这里。{primaryEffect.role}
                </div>
              </div>
              <div
                style={{
                  ...insightBoxStyle,
                  background: "#fffdf7",
                  border: "1px solid #eadfca",
                }}
              >
                <div style={smallLabelStyle}>怎么读差异</div>
                <div
                  style={{
                    color: designTokens.color.neutral[800],
                    fontSize: designTokens.fontSize[13],
                    lineHeight: designTokens.lineHeight.normal,
                  }}
                >
                  几乎没有影响：
                  {quietEffectLabels(effectRows, normalized.total_return)}。
                  看金额时先看正负，再看占比；“剩余/选券”在当前正式闭合口径中不能直接等同交易员主动选券能力。
                </div>
              </div>
            </div>
          ) : null}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: designTokens.space[3],
              marginBottom: designTokens.space[4],
              fontSize: designTokens.fontSize[12],
              color: designTokens.color.neutral[700],
            }}
          >
            {effectRows.map((effect) => (
              <div
                key={effect.key}
                style={{
                  padding: designTokens.space[3],
                  borderRadius: designTokens.radius.md,
                  border: `1px solid ${designTokens.color.neutral[200]}`,
                  background: "#ffffff",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: designTokens.space[2],
                    marginBottom: designTokens.space[2],
                  }}
                >
                  <span
                    style={{
                      fontWeight: 700,
                      color: designTokens.color.neutral[900],
                    }}
                  >
                    {displayEffectLabel(effect)}
                  </span>
                  <span style={tabularNumsStyle}>
                    {effect.share.toFixed(1)}%
                  </span>
                </div>
                <div
                  style={{
                    color: effectColor(effect.amount),
                    fontWeight: 700,
                    marginBottom: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {formatYi(effect.amount)}
                </div>
                <div
                  style={{
                    height: 6,
                    borderRadius: 999,
                    background: designTokens.color.neutral[100],
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(
                        100,
                        (Math.abs(effect.amount) / maxEffectAbs) * 100,
                      )}%`,
                      height: "100%",
                      borderRadius: 999,
                      background: effectColor(effect.amount),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          {barOption && (
            <ReactECharts
              option={barOption}
              style={{ height: 220 }}
              notMerge
              lazyUpdate
            />
          )}
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
                    <th
                      style={{
                        textAlign: "left",
                        padding: designTokens.space[2],
                      }}
                    >
                      类别
                    </th>
                    {effectRows.map((effect) => (
                      <th
                        key={effect.key}
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[2],
                          ...tabularNumsStyle,
                        }}
                      >
                        {displayEffectLabel(effect)}(亿)
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {normalized.items.map((row, index) => (
                    <tr
                      key={`${row.category}-${index}`}
                      style={{
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                      }}
                    >
                      <td style={{ padding: designTokens.space[2] }}>
                        {row.category}
                      </td>
                      {[
                        row.income_return,
                        row.treasury_effect,
                        row.spread_effect,
                        row.selection_effect,
                      ].map((value, valueIndex) => (
                        <td
                          key={`${row.category}-${valueIndex}`}
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[2],
                            ...tabularNumsStyle,
                          }}
                        >
                          {(value / 100_000_000).toFixed(2)}
                        </td>
                      ))}
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
