import { useMemo } from "react";
import { ChartCard } from "../../../components/charts/ChartCard";
import type { EChartsOption } from "../../../lib/echarts";
import type {
  CampisiAttributionPayload,
  CampisiFourEffectsPayload,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH, formatYi as formatYiShared } from "../../../utils/format";
import { buildCurveAvailabilityNotices } from "../../pnl/pnlBridgePageSupport";
import {
  EFFECT_UNAVAILABLE_TEXT,
  buildCampisiAvailabilityNotices,
  buildCampisiBridgeQualityNotice,
  buildCampisiTreasuryCurveDateNotice,
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

// 既有金额走域内统一 formatYi（pnlAttributionViewModel → utils/format，signed 恒真）。
// 本面板输入经 support 层 finiteOrNull 归一化，恒为有限数或 null，输出与原实现逐字一致。
function formatOptionalYi(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? formatYi(value)
    : "不可用";
}

// 新增质量披露与首页一致：非零金额不足 0.005 亿时按元显示，避免四舍五入成 0.00 亿。
function formatMaturityQualityAmount(value: number, signed: boolean): string {
  if (value !== 0 && Math.abs(value) < 500_000) {
    return `${signed && value > 0 ? "+" : ""}${value.toLocaleString("en-US")} 元`;
  }
  return formatYiShared(value, signed && value !== 0);
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
  const formalBridgePayload = data && "totals" in data &&
    data.basis === "formal_report_pnl_bridge" ? data : null;
  const effectRows = useMemo(
    () => (normalized ? buildEffectRows(normalized) : []),
    [normalized],
  );
  const availabilityNotices = useMemo(
    () => {
      const availability = normalized?.effect_availability;
      if (!formalBridgePayload) return buildCampisiAvailabilityNotices(availability);
      const bridgeNotices = buildCurveAvailabilityNotices(availability);
      return [
        { key: "roll_down", label: "骑乘效应", block: availability?.roll_down_availability },
        { key: "treasury_curve", label: "国债曲线效应", block: availability?.treasury_curve_availability },
        { key: "credit_spread", label: "信用利差效应", block: availability?.credit_spread_availability },
      ].map(({ key, label, block }) => {
        if (!block || !Number.isSafeInteger(block.applicable_rows) || block.applicable_rows < 0 ||
          !Number.isSafeInteger(block.unavailable_rows) || block.unavailable_rows < 0 ||
          block.unavailable_rows > block.applicable_rows ||
          !["ok", "partial", "unavailable", "not_applicable"].includes(block.status) ||
          (block.status === "ok" && block.unavailable_rows !== 0) ||
          (block.status === "not_applicable" && block.applicable_rows !== 0)) {
          return { key, text: `${label}覆盖未确认：缺少适用会计行覆盖证据，不能判断全覆盖。` };
        }
        const notice = bridgeNotices.find((item) => item.key === key);
        return {
          key,
          text: notice
            ? `${label}${notice.statusText}：${notice.text}`
            : `${label}可用：${block.unavailable_rows}/${block.applicable_rows} 个适用行不可用。`,
        };
      });
    },
    [formalBridgePayload, normalized?.effect_availability],
  );
  const formalBridgeCoverage = formalBridgePayload?.input_quality?.formal_bridge_coverage;
  let formalBridgeCoverageNotice: string | null = null;
  if (formalBridgePayload) {
    if (formalBridgeCoverage?.source === "pnl.bridge.rows" &&
      formalBridgeCoverage.basis === "formal_report_pnl_bridge" &&
      formalBridgeCoverage.status === "unavailable" && formalBridgeCoverage.bridge_rows === null &&
      Number.isSafeInteger(formalBridgeCoverage.attributed_rows) && formalBridgeCoverage.attributed_rows >= 0) {
      formalBridgeCoverageNotice = `正式桥会计行纳入覆盖不可用：已纳入 ${formalBridgeCoverage.attributed_rows} 个会计记录行，正式桥总行数未提供，不能判断全覆盖。`;
    } else if (!formalBridgeCoverage || formalBridgeCoverage.source !== "pnl.bridge.rows" ||
      formalBridgeCoverage.basis !== "formal_report_pnl_bridge" ||
      formalBridgeCoverage.bridge_rows === null ||
      !Number.isSafeInteger(formalBridgeCoverage.bridge_rows) || formalBridgeCoverage.bridge_rows < 0 ||
      !Number.isSafeInteger(formalBridgeCoverage.attributed_rows) || formalBridgeCoverage.attributed_rows < 0 ||
      formalBridgeCoverage.attributed_rows > formalBridgeCoverage.bridge_rows ||
      !["ok", "partial", "unavailable"].includes(formalBridgeCoverage.status) ||
      (formalBridgeCoverage.status === "ok" &&
        formalBridgeCoverage.attributed_rows !== formalBridgeCoverage.bridge_rows)) {
      formalBridgeCoverageNotice = "正式桥会计行纳入覆盖未确认：缺少完整的会计行纳入证据，不能判断全覆盖。";
    } else {
      const statusText = formalBridgeCoverage.status === "ok"
        ? formalBridgeCoverage.bridge_rows === 0 ? "本期无会计记录行" : "已全部纳入"
        : formalBridgeCoverage.status === "partial" ? "部分纳入" : "纳入覆盖不可用";
      formalBridgeCoverageNotice = `正式桥会计行${statusText}：已纳入 ${formalBridgeCoverage.attributed_rows}/${formalBridgeCoverage.bridge_rows} 个会计记录行。`;
    }
    formalBridgeCoverageNotice += "会计行纳入不代表市场效应输入完整或本金变化检查通过。";
  }
  const hasExcludedPositions = !formalBridgePayload &&
    (normalized?.effect_availability?.position_change?.status === "partial" ||
      normalized?.effect_availability?.position_change?.status === "unavailable");
  const curveDateNotice = buildCampisiTreasuryCurveDateNotice(
    data && "totals" in data ? data : null,
  );
  const isModelFourEffects = data && "totals" in data &&
    data.basis !== "formal_report_pnl_bridge";
  const includedMaturityUnavailable = data && "totals" in data
    ? data.input_quality?.included_maturity_unavailable
    : null;
  const maturityNotice = isModelFourEffects && includedMaturityUnavailable &&
    Number.isInteger(includedMaturityUnavailable.positions) &&
    includedMaturityUnavailable.positions > 0 &&
    Number.isFinite(includedMaturityUnavailable.market_value_start_abs) &&
    includedMaturityUnavailable.market_value_start_abs >= 0 &&
    Number.isFinite(includedMaturityUnavailable.model_residual)
    ? includedMaturityUnavailable
    : null;
  const bridgeQualityNotice = buildCampisiBridgeQualityNotice(normalized?.formal_closure);
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
            },
          })),
        },
      ],
    };
  }, [effectRows, normalized]);

  return (
    <PageDataSection
      title={hasExcludedPositions ? "Campisi 四效应归因（可归因持仓小计）" : "Campisi 四效应归因（组合）"}
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
          {formalBridgeCoverageNotice ? (
            <div
              data-testid="campisi-formal-bridge-coverage"
              className="campisi-panel__note"
            >
              {formalBridgeCoverageNotice}
            </div>
          ) : null}
          {availabilityNotices.length > 0 || curveDateNotice ? (
            <div
              data-testid="campisi-effect-availability"
              className="campisi-panel__note"
            >
              {curveDateNotice ? (
                <div data-testid="campisi-treasury-curve-dates">{curveDateNotice}</div>
              ) : null}
              {availabilityNotices.map((notice) => (
                <div key={notice.key} data-testid={formalBridgePayload
                  ? `campisi-bridge-effect-availability-${notice.key}`
                  : `campisi-effect-availability-${notice.key}`}>
                  {notice.text}
                </div>
              ))}
            </div>
          ) : null}
          <div data-testid="campisi-capability-boundary" className="campisi-panel__note">
            当前实现边界：
            {isModelFourEffects
              ? "本入口展示持仓模型四效应和输入覆盖；正式损益核对以返回状态为准；"
              : "本页提供正式 PnL 金额闭合核对、票息/利率/利差/剩余拆分和到期桶查看；"}
            尚未实现交易员能力评价、FVOCI/FVTPL 浮盈浮亏专项解释、曲线形态策略归因、个券跑赢同类基准和估值噪音诊断。
          </div>
          {bridgeQualityNotice ? (
            <div
              role="alert"
              data-testid="campisi-bridge-quality-warning"
              className="campisi-callout--warning"
            >
              <div className="campisi-callout__title">来源质量需复核</div>
              <div>{bridgeQualityNotice}</div>
            </div>
          ) : null}
          {normalized.formal_closure &&
          normalized.formal_closure.status !== "closed" ? (
            <div
              data-testid="campisi-formal-closure-warning"
              className="campisi-callout--warning"
            >
              {normalized.formal_closure.status === "unavailable" ? (
                <>
                  <div className="campisi-callout__title">正式损益核对不可用</div>
                  <div>正式 PnL 与残差尚无可比数值，当前 Campisi 金额不能据此判断是否闭合。</div>
                </>
              ) : (
                <>
                  <div className="campisi-callout__title">未闭合到正式 PnL</div>
                  <div>
                    Campisi{" "}
                    {formatOptionalYi(normalized.formal_closure.campisi_total_return)}
                    ，正式 PnL{" "}
                    {formatOptionalYi(normalized.formal_closure.formal_actual_pnl)}
                    ，需要残差{" "}
                    {formatOptionalYi(normalized.formal_closure.residual_to_formal_pnl)}{" "}
                    才能闭合。
                  </div>
                </>
              )}
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
                  % 的{isModelFourEffects ? "本期模型回报" : "本期 Campisi PnL"} 来自这里。{primaryEffect.role}
                </div>
              </div>
              <div className="campisi-insight-box">
                <div className="campisi-insight-box__label">怎么读差异</div>
                <div className="campisi-insight-box__body">
                  几乎没有影响：
                  {quietEffectLabels(effectRows, normalized.total_return)}。
                  看金额时先看正负，再看占比；
                  {isModelFourEffects
                    ? "当前模型归因中，剩余项不能直接等同主动选券能力。"
                    : "“剩余/选券”在当前正式闭合口径中不能直接等同交易员主动选券能力。"}
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
          {maturityNotice ? (
            <div
              data-testid="campisi-included-maturity-unavailable"
              className="campisi-panel__note"
            >
              已纳入且到期日不可用：{maturityNotice.positions} 项持仓；期初绝对市值{" "}
              {formatMaturityQualityAmount(maturityNotice.market_value_start_abs, false)}；计入“剩余/选券”的带符号模型剩余项{" "}
              {formatMaturityQualityAmount(maturityNotice.model_residual, true)}。国债曲线可用不代表逐券久期可用；这笔模型剩余项不代表主动选券能力。
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
          {barOption && (
            <ChartCard
              flat
              ariaLabel="Campisi 四效应归因"
              unit="亿元"
              height={220}
              option={barOption}
              legend="none"
            />
          )}
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
