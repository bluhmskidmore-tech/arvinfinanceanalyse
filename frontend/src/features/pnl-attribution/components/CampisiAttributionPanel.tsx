import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  CampisiAttributionPayload,
  CampisiEffectAvailability,
  CampisiEffectAvailabilityEntry,
  CampisiEffectAvailabilityReason,
  CampisiEffectAvailabilityStatus,
  CampisiFourEffectsPayload,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

// 面板浅色面色集中定义，防止 hex 字面量扩散（visual_tokens ratchet）。
// cream 无 designTokens 等值色（warm.paper 为 #fffdf8），保留字面量。
const SURFACE_WHITE = designTokens.color.cockpit.white;
const SURFACE_SLATE = designTokens.color.cockpit.surface20;
const SURFACE_CREAM = "#fffdf7";

const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.sm,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: SURFACE_WHITE,
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
  background: SURFACE_SLATE,
  color: designTokens.color.neutral[700],
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

function finiteOrNull(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** 契约：`pct` 字段 raw 恒为小数比率，×100 转百分点；缺失（raw=null）返回 null，不补 0。 */
function pctPoints(
  value: { raw: number | null; unit?: string } | null | undefined,
): number | null {
  const raw = value?.raw ?? null;
  if (raw === null || !Number.isFinite(raw)) {
    return null;
  }
  return value?.unit === "pct" ? raw * 100 : raw;
}

export type CampisiEffectKey =
  | "income"
  | "treasury"
  | "spread"
  | "realized_trading"
  | "manual_adjustment"
  | "fx_translation"
  | "selection";

// 后端的 `effect_availability` 说明某个效应的数值（通常是 0）是观测出来的还是被
// 缺失输入顶出来的。金额本身不变，变的只是允不允许把它当成一个数字发布：
// `unavailable` 的 0 会被读成"利率没动"，而真相是"没有曲线可比"。
// Record 按联合类型收口，后端新增取值时编译失败，而不是把英文码泄漏到页面。
const EFFECT_UNAVAILABLE_TEXT = "不可用";

const CAMPISI_AVAILABILITY_LABELS: Record<CampisiEffectAvailabilityStatus, string> = {
  ok: "可用",
  partial: "部分不可用",
  unavailable: EFFECT_UNAVAILABLE_TEXT,
  not_decomposed: "该路径不拆分",
};

const CAMPISI_AVAILABILITY_REASON_LABELS: Record<CampisiEffectAvailabilityReason, string> = {
  curve_absent: "该交易日没有曲线事实",
  curve_unusable: "曲线有行但没有可用关键期限",
  insufficient_shared_tenors: "两端共同期限不足",
  bridge_curve_unavailable: "正式桥判定该行曲线效应不可用",
  credit_spread_input_missing: "缺信用利差输入",
  accrued_interest_missing: "缺应计利息",
  bridge_second_order_not_decomposed: "bridge 一阶分解框架不拆二阶项，贡献并入选券残差",
};

function campisiReasonLabel(reason: CampisiEffectAvailabilityReason | null | undefined): string {
  return reason ? CAMPISI_AVAILABILITY_REASON_LABELS[reason] : "未标注成因";
}

type CampisiEffect = {
  key: CampisiEffectKey;
  label: string;
  amount: number | null;
  share: number | null;
  role: string;
  /** 完全不可用：金额不得以数字形式呈现。`partial` 仍是被低估的观测量。 */
  unavailable: boolean;
  unavailableReason: CampisiEffectAvailabilityReason | null;
};

type NormalizedCampisiItem = {
  category: string;
  income_return: number | null;
  treasury_effect: number | null;
  spread_effect: number | null;
  realized_trading: number | null;
  manual_adjustment: number | null;
  fx_translation: number | null;
  selection_effect: number | null;
};

type NormalizedCampisiData = {
  total_return: number | null;
  total_income: number | null;
  total_treasury_effect: number | null;
  total_spread_effect: number | null;
  total_realized_trading: number | null;
  total_manual_adjustment: number | null;
  total_fx_translation: number | null;
  total_selection_effect: number | null;
  income_contribution_pct: number | null;
  treasury_contribution_pct: number | null;
  spread_contribution_pct: number | null;
  selection_contribution_pct: number | null;
  interpretation: string;
  decomposition_basis?: string;
  formal_closure?: CampisiFourEffectsPayload["formal_closure"];
  has_bridge_details: boolean;
  effect_availability?: CampisiEffectAvailability;
  /** true = 占比由前端按 total_return 派生（后端 totals 无占比字段）；false = 消费后端 contribution_pct。 */
  shares_frontend_derived: boolean;
  items: NormalizedCampisiItem[];
};

type Props = {
  data: CampisiAttributionPayload | CampisiFourEffectsPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

function optionalFiniteOrNull(
  value: number | undefined,
  present: boolean,
): number | null {
  if (!present) {
    return null;
  }
  return finiteOrNull(value);
}

export function normalizeCampisiData(
  data: CampisiAttributionPayload | CampisiFourEffectsPayload | null,
): NormalizedCampisiData | null {
  if (!data) {
    return null;
  }

  if ("totals" in data) {
    const totalReturn = finiteOrNull(data.totals.total_return);
    const pct = (value: number | null) =>
      totalReturn !== null && totalReturn !== 0 && value !== null
        ? (value / totalReturn) * 100
        : null;
    const income = finiteOrNull(data.totals.income_return);
    const treasury = finiteOrNull(data.totals.treasury_effect);
    const spread = finiteOrNull(data.totals.spread_effect);
    const hasBridgeDetails =
      data.totals.realized_trading !== undefined ||
      data.totals.manual_adjustment !== undefined ||
      data.totals.fx_translation !== undefined;
    const realized = optionalFiniteOrNull(
      data.totals.realized_trading,
      hasBridgeDetails,
    );
    const manual = optionalFiniteOrNull(
      data.totals.manual_adjustment,
      hasBridgeDetails,
    );
    const fx = optionalFiniteOrNull(data.totals.fx_translation, hasBridgeDetails);
    const selection = finiteOrNull(data.totals.selection_effect);
    return {
      total_return: totalReturn,
      total_income: income,
      total_treasury_effect: treasury,
      total_spread_effect: spread,
      total_realized_trading: realized,
      total_manual_adjustment: manual,
      total_fx_translation: fx,
      total_selection_effect: selection,
      income_contribution_pct: pct(income),
      treasury_contribution_pct: pct(treasury),
      spread_contribution_pct: pct(spread),
      selection_contribution_pct: pct(selection),
      interpretation: `期间 ${data.period_start} 至 ${data.period_end} 的四效应归因拆解。`,
      decomposition_basis: data.decomposition_basis,
      formal_closure: data.formal_closure,
      has_bridge_details: hasBridgeDetails,
      effect_availability: data.effect_availability,
      shares_frontend_derived: true,
      items: data.by_asset_class.map((row) => ({
        category: row.asset_class,
        income_return: finiteOrNull(row.income_return),
        treasury_effect: finiteOrNull(row.treasury_effect),
        spread_effect: finiteOrNull(row.spread_effect),
        realized_trading: optionalFiniteOrNull(
          row.realized_trading,
          hasBridgeDetails,
        ),
        manual_adjustment: optionalFiniteOrNull(
          row.manual_adjustment,
          hasBridgeDetails,
        ),
        fx_translation: optionalFiniteOrNull(row.fx_translation, hasBridgeDetails),
        selection_effect: finiteOrNull(row.selection_effect),
      })),
    };
  }

  return {
    total_return: finiteOrNull(data.total_return.raw),
    total_income: finiteOrNull(data.total_income.raw),
    total_treasury_effect: finiteOrNull(data.total_treasury_effect.raw),
    total_spread_effect: finiteOrNull(data.total_spread_effect.raw),
    total_realized_trading: null,
    total_manual_adjustment: null,
    total_fx_translation: null,
    total_selection_effect: finiteOrNull(data.total_selection_effect.raw),
    income_contribution_pct: pctPoints(data.income_contribution_pct),
    treasury_contribution_pct: pctPoints(data.treasury_contribution_pct),
    spread_contribution_pct: pctPoints(data.spread_contribution_pct),
    selection_contribution_pct: pctPoints(data.selection_contribution_pct),
    interpretation: data.interpretation,
    decomposition_basis: undefined,
    formal_closure: undefined,
    has_bridge_details: false,
    effect_availability: undefined,
    shares_frontend_derived: false,
    items: data.items.map((row) => ({
      category: row.category,
      income_return: finiteOrNull(row.income_return.raw),
      treasury_effect: finiteOrNull(row.treasury_effect.raw),
      spread_effect: finiteOrNull(row.spread_effect.raw),
      realized_trading: null,
      manual_adjustment: null,
      fx_translation: null,
      selection_effect: finiteOrNull(row.selection_effect.raw),
    })),
  };
}

/** 只有"全部债券都受影响"才允许整列改判；`partial` 仍是被低估的观测量。 */
function isFullyUnavailable(entry: CampisiEffectAvailabilityEntry | undefined): boolean {
  return entry?.status === "unavailable";
}

export function buildEffectRows(normalized: NormalizedCampisiData): CampisiEffect[] {
  const pct = (value: number | null) =>
    normalized.total_return !== null &&
    normalized.total_return !== 0 &&
    value !== null
      ? (value / normalized.total_return) * 100
      : null;
  const availability = normalized.effect_availability;
  const treasuryEntry = availability?.treasury_effect;
  const spreadEntry = availability?.spread_effect;
  const available = { unavailable: false, unavailableReason: null } as const;
  const rows: CampisiEffect[] = [
    {
      key: "income",
      label: "收入效应",
      amount: normalized.total_income,
      share: normalized.income_contribution_pct,
      role: "票息和持有收益，是债券组合最稳定的收益底盘。",
      ...available,
    },
    {
      key: "treasury",
      label: "国债曲线",
      amount: normalized.total_treasury_effect,
      share: normalized.treasury_contribution_pct,
      role: "无风险利率曲线和 roll-down 带来的估值影响。",
      unavailable: isFullyUnavailable(treasuryEntry),
      unavailableReason: treasuryEntry?.reason ?? null,
    },
    {
      key: "spread",
      label: "信用利差",
      amount: normalized.total_spread_effect,
      share: normalized.spread_contribution_pct,
      role: "信用利差收窄或走阔带来的价格影响。",
      unavailable: isFullyUnavailable(spreadEntry),
      unavailableReason: spreadEntry?.reason ?? null,
    },
  ];
  if (normalized.has_bridge_details) {
    rows.push(
      {
        key: "realized_trading",
        label: "已实现交易",
        amount: normalized.total_realized_trading,
        share: pct(normalized.total_realized_trading),
        role: "517 已实现交易损益，不等同交易员能力评价。",
        ...available,
      },
      {
        key: "manual_adjustment",
        label: "手工调整",
        amount: normalized.total_manual_adjustment,
        share: pct(normalized.total_manual_adjustment),
        role: "治理手工调整，不算主动管理能力。",
        ...available,
      },
      {
        key: "fx_translation",
        label: "汇兑",
        amount: normalized.total_fx_translation,
        share: pct(normalized.total_fx_translation),
        role: "汇兑折算影响，与选券残差分开列示。",
        ...available,
      },
    );
  }
  rows.push({
    key: "selection",
    label: "选择效应",
    amount: normalized.total_selection_effect,
    share: normalized.selection_contribution_pct,
    role: normalized.has_bridge_details
      ? "扣除票息、曲线、利差、已实现交易、手工调整与汇兑后的残差，不能直接等同选券能力。"
      : "剩余已确认损益，包括个券表现、交易和会计口径差异。",
    ...available,
  });
  return rows;
}

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

export type CampisiAvailabilityNotice = { key: string; text: string };

/** 逐效应披露：状态、覆盖面和成因缺一不可，只报"有问题"等于没报。 */
export function buildCampisiAvailabilityNotices(
  availability: CampisiEffectAvailability | undefined,
): CampisiAvailabilityNotice[] {
  if (!availability) return [];
  const entries: Array<{ key: string; label: string; entry: CampisiEffectAvailabilityEntry }> = [
    { key: "treasury_effect", label: "国债曲线效应", entry: availability.treasury_effect },
    { key: "spread_effect", label: "信用利差效应", entry: availability.spread_effect },
    { key: "accrued_interest", label: "应计利息口径", entry: availability.accrued_interest },
  ];
  return entries
    .filter(({ entry }) => entry && entry.status !== "ok")
    .map(({ key, label, entry }) => ({
      key,
      text:
        `${label}${CAMPISI_AVAILABILITY_LABELS[entry.status]}：${campisiReasonLabel(entry.reason)}，` +
        `影响 ${entry.unavailable_bonds}/${availability.bonds} 只债券。` +
        (entry.status === "unavailable"
          ? "该效应本期没有可比输入，页面不以数字形式发布，不能读成“市场没有变动”。"
          : "受影响债券的该效应缺少输入，合计因此被低估。"),
    }));
}

export function sumCampisiEffectAmounts(effects: readonly CampisiEffect[]): number | null {
  let sum = 0;
  for (const effect of effects) {
    if (effect.amount === null) {
      return null;
    }
    sum += effect.amount;
  }
  return sum;
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
    return designTokens.color.semantic.profit;
  }
  if (amount !== null && amount < 0) {
    return designTokens.color.semantic.loss;
  }
  return designTokens.color.neutral[500];
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
              color: effectColor(value === null ? null : effectRows[index]?.amount ?? null),
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
          {normalized.decomposition_basis ? (
            <div
              data-testid="campisi-decomposition-basis"
              style={{
                marginBottom: designTokens.space[4],
                padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
                borderRadius: designTokens.radius.md,
                border: `1px solid ${designTokens.color.neutral[200]}`,
                background: SURFACE_CREAM,
                color: designTokens.color.neutral[700],
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
              <div style={{ ...insightBoxStyle, background: SURFACE_SLATE }}>
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
                  {primaryEffect.share === null
                    ? EM_DASH
                    : Math.abs(primaryEffect.share).toFixed(1)}
                  % 的本期 Campisi PnL 来自这里。{primaryEffect.role}
                </div>
              </div>
              <div
                style={{
                  ...insightBoxStyle,
                  background: SURFACE_CREAM,
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
          {normalized.shares_frontend_derived ? (
            <div
              data-testid="campisi-share-derived-note"
              style={{
                marginBottom: designTokens.space[3],
                fontSize: designTokens.fontSize[12],
                color: designTokens.color.neutral[600],
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
                  background: SURFACE_WHITE,
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
                    borderRadius: 999,
                    background: designTokens.color.neutral[100],
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
