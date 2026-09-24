import { useMemo } from "react";
import { BaseChart } from "../../../components/charts/BaseChart";
import type { EChartsOption } from "../../../lib/echarts";
import type {
  CampisiAttributionPayload,
  CampisiFourEffectsPayload,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
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
import { formatYi } from "./pnlAttributionViewModel";
import "./campisiPanels.css";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下：
// 布局与面色收敛到共享 campisiPanels.css（--dh-api-* var 链），盈亏语义色经
// data-tone 属性映射（绿涨红跌，与 TONE_DH_CSS_VAR 同源）；仅进度条宽度等
// 动态值保留内联。ECharts canvas 读不到 CSS 变量，按 tone.ts 指南使用
// nocturneTokens 静态镜像 token。

// 金额一律走域内统一 formatYi（pnlAttributionViewModel → utils/format，signed 恒真）。
// 本面板输入经 support 层 finiteOrNull 归一化，恒为有限数或 null，输出与原实现逐字一致。
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

/** 盈亏语义 data-tone：正→绿、负→红、缺失/零→中性（CSS 侧映射色值）。 */
function effectTone(amount: number | null): "positive" | "negative" | "neutral" {
  if (amount !== null && amount > 0) {
    return "positive";
  }
  if (amount !== null && amount < 0) {
    return "negative";
  }
  return "neutral";
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
        <div className="campisi-panel">
          <p className="campisi-panel__empty">暂无 Campisi 归因数据。</p>
        </div>
      ) : (
        <div className="campisi-panel">
          <p className="campisi-panel__intro">{normalized.interpretation}</p>
          {normalized.decomposition_basis ? (
            <div
              data-testid="campisi-decomposition-basis"
              className="campisi-panel__note"
            >
              分解口径：{normalized.decomposition_basis}
            </div>
          ) : null}
          {availabilityNotices.length > 0 ? (
            <div
              data-testid="campisi-effect-availability"
              className="campisi-panel__note"
            >
              {availabilityNotices.map((notice) => (
                <div key={notice.key} data-testid={`campisi-effect-availability-${notice.key}`}>
                  {notice.text}
                </div>
              ))}
            </div>
          ) : null}
          <div data-testid="campisi-capability-boundary" className="campisi-panel__note">
            当前实现边界：本页已做到正式 PnL 闭合、票息/利率/利差/剩余拆分和到期桶查看；尚未实现交易员能力评价、FVOCI/FVTPL 浮盈浮亏专项解释、曲线形态策略归因、个券跑赢同类基准和估值噪音诊断。
          </div>
          {normalized.formal_closure &&
          normalized.formal_closure.status !== "closed" ? (
            <div
              data-testid="campisi-formal-closure-warning"
              className="campisi-callout--warning"
            >
              <div className="campisi-callout__title">未闭合到正式 PnL</div>
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
            <div data-testid="campisi-driver-summary" className="campisi-summary-grid">
              <div className="campisi-insight-box">
                <div className="campisi-insight-box__label">一眼结论</div>
                <div className="campisi-insight-box__headline">
                  主要贡献：{displayEffectLabel(primaryEffect)}
                </div>
                <div className="campisi-insight-box__body">
                  {formatYi(primaryEffect.amount)}，约{" "}
                  {primaryEffect.share === null
                    ? EM_DASH
                    : Math.abs(primaryEffect.share).toFixed(1)}
                  % 的本期 Campisi PnL 来自这里。{primaryEffect.role}
                </div>
              </div>
              <div className="campisi-insight-box">
                <div className="campisi-insight-box__label">怎么读差异</div>
                <div className="campisi-insight-box__body">
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
              className="campisi-derived-note"
            >
              占比为展示辅助计算（非正式指标）：按各效应金额 / 本期 Campisi 总回报折算。
            </div>
          ) : null}
          <div className="campisi-effect-grid">
            {effectRows.map((effect) => (
              <div key={effect.key} className="campisi-effect">
                <div className="campisi-effect__head">
                  <span className="campisi-effect__name">
                    {displayEffectLabel(effect)}
                  </span>
                  <span className="campisi-tabular">{effectShareText(effect)}</span>
                </div>
                <div
                  data-testid={`campisi-effect-amount-${effect.key}`}
                  data-tone={effectTone(effect.unavailable ? null : effect.amount)}
                  className="campisi-effect__amount"
                >
                  {effectAmountText(effect)}
                </div>
                <div className="campisi-effect__track">
                  <div
                    className="campisi-effect__fill"
                    data-tone={effectTone(effect.amount)}
                    style={{
                      width: `${
                        effect.unavailable
                          ? 0
                          : Math.min(100, (Math.abs(effect.amount ?? 0) / maxEffectAbs) * 100)
                      }%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          {barOption && <BaseChart option={barOption} height={220} />}
          {normalized.items.length > 0 && (
            <div className="campisi-table-wrap">
              <table className="campisi-table">
                <thead>
                  <tr>
                    <th>类别</th>
                    {effectRows.map((effect) => (
                      <th key={effect.key} className="campisi-table__numeric-head">
                        {displayEffectLabel(effect)}(亿)
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {normalized.items.map((row, index) => (
                    <tr key={`${row.category}-${index}`}>
                      <td>{row.category}</td>
                      {effectRows.map((effect) => {
                        const value = itemAmountForEffect(row, effect.key);
                        return (
                          <td
                            key={`${row.category}-${effect.key}`}
                            className="campisi-table__numeric-cell"
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
