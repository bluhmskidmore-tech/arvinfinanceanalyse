import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  CampisiAttributionPayload,
  CampisiFourEffectsPayload,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, nocturneTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { TONE_DH_CSS_VAR } from "../../../utils/tone";
import {
  EFFECT_UNAVAILABLE_TEXT,
  buildCampisiAvailabilityNotices,
  buildEffectRows,
  campisiReasonLabel,
  normalizeCampisiData,
  type CampisiEffect,
  type CampisiEffectKey,
  type NormalizedCampisiItem,
} from "./campisiAttributionPanelSupport";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下，
// 面色/文字/盈亏着色一律走主题感知 CSS 变量（--dh-api-* / TONE_DH_CSS_VAR），
// 禁止浅色 hex 或 semantic.profit/loss 直灌（--ib-* 在路由边界被算成钢蓝
// 字面值再继承，Nocturne scope 翻不动，不得引用）；
// ECharts canvas 读不到 CSS 变量，按 tone.ts 指南使用 nocturneTokens 静态镜像 token。
const SURFACE_CARD = "var(--dh-api-panel)";
const SURFACE_MUTED = "var(--dh-api-panel-2)";

const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: "var(--dh-api-radius)",
  border: "1px solid var(--dh-api-line)",
  background: SURFACE_CARD,
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
  borderRadius: "var(--dh-api-radius)",
  border: "1px solid var(--dh-api-line-soft)",
} as const;

const smallLabelStyle = {
  fontSize: designTokens.fontSize[12],
  color: "var(--dh-api-muted)",
  marginBottom: designTokens.space[2],
} as const;

const capabilityBoundaryStyle = {
  marginBottom: designTokens.space[4],
  padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
  borderRadius: "var(--dh-api-radius)",
  border: "1px solid var(--dh-api-line-soft)",
  background: SURFACE_MUTED,
  color: "var(--dh-api-soft)",
  fontSize: designTokens.fontSize[12],
  lineHeight: designTokens.lineHeight.normal,
} as const;

function formatYi(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function formatOptionalYi(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? formatYi(value)
    : "不可用";
}

type Props = {
  data: CampisiAttributionPayload | CampisiFourEffectsPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

/** 不可用效应的金额不进入数字通道：显示"不可用 · 成因"而不是一个 0。 */
function effectAmountText(effect: CampisiEffect): string {
  if (effect.unavailable) {
    return `${EFFECT_UNAVAILABLE_TEXT} · ${campisiReasonLabel(effect.unavailableReason)}`;
  }
  return formatYi(effect.amount);
}

function effectShareText(effect: CampisiEffect): string {
  if (effect.unavailable || effect.share === null) return EM_DASH;
  return `${effect.share.toFixed(1)}%`;
}

/** 参与"主要贡献 / 几乎没有影响"排序的效应：不可用的没有可比金额。 */
function comparableEffects(effects: readonly CampisiEffect[]): CampisiEffect[] {
  return effects.filter((effect) => !effect.unavailable && effect.amount !== null);
}

function itemAmountForEffect(
  row: NormalizedCampisiItem,
  key: CampisiEffectKey,
): number | null {
  switch (key) {
    case "income":
      return row.income_return;
    case "treasury":
      return row.treasury_effect;
    case "spread":
      return row.spread_effect;
    case "realized_trading":
      return row.realized_trading;
    case "manual_adjustment":
      return row.manual_adjustment;
    case "fx_translation":
      return row.fx_translation;
    case "selection":
      return row.selection_effect;
  }
}

function effectColor(amount: number | null): string {
  if (amount !== null && amount > 0) {
    return TONE_DH_CSS_VAR.positive;
  }
  if (amount !== null && amount < 0) {
    return TONE_DH_CSS_VAR.negative;
  }
  return TONE_DH_CSS_VAR.neutral;
}

/** ECharts canvas 无法解析 CSS 变量，正负色向走 Nocturne TS 镜像 token。 */
function effectChartColor(amount: number | null): string {
  if (amount !== null && amount > 0) {
    return nocturneTokens.color.green;
  }
  if (amount !== null && amount < 0) {
    return nocturneTokens.color.red;
  }
  return nocturneTokens.color.inkMuted;
}

function displayEffectLabel(effect: CampisiEffect): string {
  return effect.key === "selection" ? "剩余/选券" : effect.label;
}

function quietEffectLabels(effects: CampisiEffect[], totalReturn: number | null): string {
  const threshold = Math.max(Math.abs(totalReturn ?? 0) * 0.005, 1_000_000);
  // 不可用效应的 0 不是"几乎没有影响"，把它列进这句话正是本次整改要消灭的误读。
  const labels = comparableEffects(effects)
    .filter((effect) => Math.abs(effect.amount ?? 0) <= threshold)
    .map((effect) => displayEffectLabel(effect));
  return labels.length ? labels.join("、") : "无";
}

export function CampisiAttributionPanel({ data, state, onRetry }: Props) {
  const normalized = useMemo(() => normalizeCampisiData(data), [data]);
  const effectRows = useMemo(
    () => (normalized ? buildEffectRows(normalized) : []),
    [normalized],
  );
  const availabilityNotices = useMemo(
    () => buildCampisiAvailabilityNotices(normalized?.effect_availability),
    [normalized?.effect_availability],
  );
  const primaryEffect = useMemo(
    () =>
      comparableEffects(effectRows).sort(
        (left, right) => Math.abs(right.amount ?? 0) - Math.abs(left.amount ?? 0),
      )[0],
    [effectRows],
  );
  const maxEffectAbs = Math.max(
    1,
    ...comparableEffects(effectRows).map((effect) => Math.abs(effect.amount ?? 0)),
  );

  const barOption = useMemo<EChartsOption | null>(() => {
    if (!normalized) {
      return null;
    }
    // 缺失或不可用的效应传 null，ECharts 留空不画 0 值柱。
    const values = effectRows.map((effect) =>
      effect.unavailable || effect.amount === null ? null : effect.amount / 100_000_000,
    );
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => {
          const item = Array.isArray(value) ? value[0] : value;
          if (item === null || item === undefined || item === "-") {
            return EM_DASH;
          }
          const n = Number(item);
          return `${Number.isFinite(n) ? n.toFixed(2) : EM_DASH} 亿`;
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
          color: nocturneTokens.color.inkSoft,
        },
        splitLine: {
          lineStyle: { type: "dashed", color: nocturneTokens.color.lineSoft },
        },
      },
      yAxis: {
        type: "category",
        data: effectRows.map((effect) => displayEffectLabel(effect)),
        axisLabel: {
          fontSize: designTokens.fontSize[12],
          color: nocturneTokens.color.inkSoft,
        },
      },
      series: [
        {
          type: "bar",
          data: values.map((value, index) => ({
            value,
            itemStyle: {
              color: effectChartColor(value === null ? null : effectRows[index]?.amount ?? null),
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
    <PageDataSection
      title="Campisi 四效应归因（组合）"
      state={state}
      onRetry={onRetry}
    >
      {!normalized ? (
        <div style={cardStyle}>
          <p style={{ margin: 0, color: "var(--dh-api-soft)" }}>
            暂无 Campisi 归因数据。
          </p>
        </div>
      ) : (
        <div style={cardStyle}>
          <p
            style={{
              margin: `0 0 ${designTokens.space[4]}px`,
              fontSize: designTokens.fontSize[13],
              color: "var(--dh-api-soft)",
              lineHeight: designTokens.lineHeight.normal,
            }}
          >
            {normalized.interpretation}
          </p>
          {normalized.decomposition_basis ? (
            <div
              data-testid="campisi-decomposition-basis"
              style={{
                marginBottom: designTokens.space[4],
                padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
                borderRadius: "var(--dh-api-radius)",
                border: "1px solid var(--dh-api-line-soft)",
                background: SURFACE_MUTED,
                color: "var(--dh-api-soft)",
                fontSize: designTokens.fontSize[12],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              分解口径：{normalized.decomposition_basis}
            </div>
          ) : null}
          {availabilityNotices.length > 0 ? (
            <div data-testid="campisi-effect-availability" style={capabilityBoundaryStyle}>
              {availabilityNotices.map((notice) => (
                <div key={notice.key} data-testid={`campisi-effect-availability-${notice.key}`}>
                  {notice.text}
                </div>
              ))}
            </div>
          ) : null}
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
                // 状态语义左条统一 2px（承载未闭合警示语义，非装饰）。
                borderLeft: "2px solid var(--dh-api-amber)",
                background: SURFACE_MUTED,
                color: "var(--dh-api-soft)",
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
              <div style={{ ...insightBoxStyle, background: SURFACE_MUTED }}>
                <div style={smallLabelStyle}>一眼结论</div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[16],
                    fontWeight: 700,
                    color: "var(--dh-api-ink)",
                    marginBottom: designTokens.space[2],
                  }}
                >
                  主要贡献：{displayEffectLabel(primaryEffect)}
                </div>
                <div
                  style={{
                    color: "var(--dh-api-soft)",
                    fontSize: designTokens.fontSize[13],
                    lineHeight: designTokens.lineHeight.normal,
                  }}
                >
                  {formatYi(primaryEffect.amount)}，约{" "}
                  {primaryEffect.share === null
                    ? EM_DASH
                    : Math.abs(primaryEffect.share).toFixed(1)}
                  % 的本期 Campisi PnL 来自这里。{primaryEffect.role}
                </div>
              </div>
              <div
                style={{
                  ...insightBoxStyle,
                  background: SURFACE_MUTED,
                }}
              >
                <div style={smallLabelStyle}>怎么读差异</div>
                <div
                  style={{
                    color: "var(--dh-api-soft)",
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
          {normalized.shares_frontend_derived ? (
            <div
              data-testid="campisi-share-derived-note"
              style={{
                marginBottom: designTokens.space[3],
                fontSize: designTokens.fontSize[12],
                color: "var(--dh-api-muted)",
              }}
            >
              占比为展示辅助计算（非正式指标）：按各效应金额 / 本期 Campisi 总回报折算。
            </div>
          ) : null}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: designTokens.space[3],
              marginBottom: designTokens.space[4],
              fontSize: designTokens.fontSize[12],
              color: "var(--dh-api-soft)",
            }}
          >
            {effectRows.map((effect) => (
              <div
                key={effect.key}
                style={{
                  padding: designTokens.space[3],
                  borderRadius: "var(--dh-api-radius)",
                  border: "1px solid var(--dh-api-line-soft)",
                  background: SURFACE_CARD,
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
                      color: "var(--dh-api-ink)",
                    }}
                  >
                    {displayEffectLabel(effect)}
                  </span>
                  <span style={tabularNumsStyle}>{effectShareText(effect)}</span>
                </div>
                <div
                  data-testid={`campisi-effect-amount-${effect.key}`}
                  style={{
                    color: effectColor(effect.unavailable ? null : effect.amount),
                    fontWeight: 700,
                    marginBottom: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {effectAmountText(effect)}
                </div>
                <div
                  style={{
                    height: 6,
                    borderRadius: "var(--dh-api-radius)",
                    background: SURFACE_MUTED,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${
                        effect.unavailable
                          ? 0
                          : Math.min(100, (Math.abs(effect.amount ?? 0) / maxEffectAbs) * 100)
                      }%`,
                      height: "100%",
                      borderRadius: "var(--dh-api-radius)",
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
                  <tr style={{ background: SURFACE_MUTED }}>
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
                        borderBottom: "1px solid var(--dh-api-line-soft)",
                      }}
                    >
                      <td style={{ padding: designTokens.space[2] }}>
                        {row.category}
                      </td>
                      {effectRows.map((effect) => {
                        const value = itemAmountForEffect(row, effect.key);
                        return (
                          <td
                            key={`${row.category}-${effect.key}`}
                            style={{
                              textAlign: "right",
                              padding: designTokens.space[2],
                              ...tabularNumsStyle,
                            }}
                          >
                            {effect.unavailable
                              ? EFFECT_UNAVAILABLE_TEXT
                              : value === null
                                ? EM_DASH
                                : (value / 100_000_000).toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </PageDataSection>
  );
}
