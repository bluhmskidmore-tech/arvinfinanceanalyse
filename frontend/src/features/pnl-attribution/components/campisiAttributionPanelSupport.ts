import type {
  CampisiAttributionPayload,
  CampisiEffectAvailability,
  CampisiEffectAvailabilityEntry,
  CampisiEffectAvailabilityReason,
  CampisiEffectAvailabilityStatus,
  CampisiFourEffectsPayload,
} from "../../../api/contracts";

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
export const EFFECT_UNAVAILABLE_TEXT = "不可用";

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

export function campisiReasonLabel(reason: CampisiEffectAvailabilityReason | null | undefined): string {
  return reason ? CAMPISI_AVAILABILITY_REASON_LABELS[reason] : "未标注成因";
}

export type CampisiEffect = {
  key: CampisiEffectKey;
  label: string;
  amount: number | null;
  share: number | null;
  role: string;
  /** 完全不可用：金额不得以数字形式呈现。`partial` 仍是被低估的观测量。 */
  unavailable: boolean;
  unavailableReason: CampisiEffectAvailabilityReason | null;
};

export type NormalizedCampisiItem = {
  category: string;
  income_return: number | null;
  treasury_effect: number | null;
  spread_effect: number | null;
  realized_trading: number | null;
  manual_adjustment: number | null;
  fx_translation: number | null;
  selection_effect: number | null;
};

export type NormalizedCampisiData = {
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
