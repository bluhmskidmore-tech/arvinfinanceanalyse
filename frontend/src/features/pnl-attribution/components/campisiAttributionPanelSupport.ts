import type {
  CampisiAttributionPayload,
  CampisiEffectAvailability,
  CampisiEffectAvailabilityEntry,
  CampisiEffectAvailabilityReason,
  CampisiEffectAvailabilityStatus,
  CampisiFourEffectsPayload,
  ResultMeta,
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
  insufficient_shared_positive_tenors: "两端共同的有效正收益率期限不足",
  bridge_curve_unavailable: "正式桥判定该行曲线效应不可用",
  credit_spread_input_missing: "缺信用利差输入",
  accrued_interest_missing: "缺应计利息",
  principal_change_without_cashflows: "持仓新增、退出或本金变化/缺失，且没有交易现金流，已排除相关持仓",
  bridge_second_order_not_decomposed: "bridge 一阶分解框架不拆二阶项，贡献并入选券残差",
};

export function campisiReasonLabel(reason: CampisiEffectAvailabilityReason | null | undefined): string {
  return reason ? CAMPISI_AVAILABILITY_REASON_LABELS[reason] ?? "未识别的缺失成因" : "未标注成因";
}

export type CampisiEffect = {
  key: CampisiEffectKey;
  label: string;
  amount: number | null;
  share: number | null;
  role: string;
  /** 完全不可用：金额不得以数字形式呈现。`partial` 保留已归因金额，不推断全人口差额方向。 */
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
    const excluded = data.effect_availability?.position_change?.status === "unavailable";
    const coveredValue = (value: number | null | undefined) => excluded ? null : finiteOrNull(value);
    const totalReturn = coveredValue(data.totals.total_return);
    const pct = (value: number | null) =>
      totalReturn !== null && totalReturn !== 0 && value !== null
        ? (value / totalReturn) * 100
        : null;
    const income = coveredValue(data.totals.income_return);
    const treasury = coveredValue(data.totals.treasury_effect);
    const spread = coveredValue(data.totals.spread_effect);
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
    const selection = coveredValue(data.totals.selection_effect);
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
    effect_availability: data.effect_availability,
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

/** 只有"全部债券都受影响"才允许整列改判；`partial` 保留部分覆盖的已归因金额。 */
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
  if (isFullyUnavailable(availability?.position_change)) {
    return rows.map((row) => ({ ...row, amount: null, share: null, unavailable: true,
      unavailableReason: "principal_change_without_cashflows" }));
  }
  return rows;
}

export type CampisiAvailabilityNotice = { key: string; text: string };

type CampisiBridgeSourceQuality = Pick<
  NonNullable<CampisiFourEffectsPayload["formal_closure"]>,
  "bridge_quality_flag" | "bridge_vendor_status" | "bridge_fallback_mode" | "bridge_fallback_date"
>;

/** 金额闭合与来源质量分别披露；缺少来源状态不能当作通过质量检查。 */
export function buildCampisiBridgeQualityNotice(
  closure: CampisiBridgeSourceQuality | null | undefined,
): string | null {
  if (!closure) return null;
  const messages: string[] = [];
  const quality = closure.bridge_quality_flag;
  const vendor = closure.bridge_vendor_status;
  const fallback = closure.bridge_fallback_mode;
  if (quality === "error") messages.push("正式 PnL 来源存在数据质量错误");
  else if (quality === "stale") messages.push("正式 PnL 来源数据已陈旧");
  else if (quality === "warning") messages.push("正式 PnL 来源存在质量警告");
  if (vendor === "vendor_stale") messages.push("上游行情数据已陈旧");
  else if (vendor === "vendor_unavailable") messages.push("上游行情数据不可用");
  if (fallback === "latest_snapshot") {
    messages.push(
      closure.bridge_fallback_date
        ? `已使用降级快照，来源日期为 ${closure.bridge_fallback_date}`
        : "已使用降级快照，来源日期未提供",
    );
  }
  if (
    !["ok", "warning", "error", "stale"].includes(quality ?? "") ||
    !["ok", "vendor_stale", "vendor_unavailable"].includes(vendor ?? "") ||
    !["none", "latest_snapshot"].includes(fallback ?? "")
  ) {
    messages.push("正式 PnL 来源状态未确认");
  }
  return messages.length
    ? `${messages.join("；")}。金额闭合不代表数据质量通过。`
    : null;
}

/** 增强版/到期桶没有闭合明细，直接消费同源的外层元信息。 */
export function buildCampisiResultQualityNotice(meta: ResultMeta | null): string | null {
  return meta ? buildCampisiBridgeQualityNotice({
    bridge_quality_flag: meta.quality_flag,
    bridge_vendor_status: meta.vendor_status,
    bridge_fallback_mode: meta.fallback_mode,
    bridge_fallback_date: meta.fallback_date,
  }) : null;
}

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
  if (availability.position_change) {
    entries.push({ key: "position_change", label: "持仓收益覆盖", entry: availability.position_change });
  }
  return entries
    .filter(({ entry }) => entry && entry.status !== "ok")
    .map(({ key, label, entry }) => {
      const denominator = key === "position_change"
        ? availability.bonds
        : availability.position_change?.covered_bonds ?? availability.bonds;
      const detail = key === "position_change"
        ? `排除期初市值 ${entry.unavailable_market_value_start} 元` +
          (entry.unavailable_market_value_end != null ? `、期末市值 ${entry.unavailable_market_value_end} 元` : "") +
          "（均为绝对市值）；" +
          (entry.status === "unavailable"
            ? "全部持仓均被排除，零金额只是占位，本期无法计算组合模型归因，未外推全组合。"
            : "金额仅汇总可归因持仓，未外推全组合。")
        : key === "accrued_interest"
          ? "应计利息缺口仅统计可归因持仓；它是输入质量提示，并非单列效应金额，不能由缺口数量推断合计回报偏差方向。"
          : entry.status === "unavailable"
            ? "该效应本期没有可比输入，页面不以数字形式发布，不能读成“市场没有变动”。"
            : "受影响债券的该效应缺少输入，贡献信息不完整；不能据此判断合计回报偏差方向。";
      return {
        key,
        text: `${label}${CAMPISI_AVAILABILITY_LABELS[entry.status]}：${campisiReasonLabel(entry.reason)}，` +
          `影响 ${entry.unavailable_bonds}/${denominator} 只债券。${detail}`,
      };
    });
}

/** 持仓日期与曲线观测日期分开披露；未采纳的解析日不能称为观测日。 */
export function buildCampisiTreasuryCurveDateNotice(
  payload: CampisiFourEffectsPayload | null | undefined,
): string | null {
  const curve = payload?.input_quality?.market_curve_coverage?.treasury_effect;
  if (!curve) return null;
  const date = (value: string | null | undefined) =>
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
  const startResolved = date(curve.start_resolved_date);
  const endResolved = date(curve.end_resolved_date);
  if (
    !startResolved && !endResolved &&
    curve.start_curve_used !== true && curve.start_curve_used !== false &&
    curve.end_curve_used !== true && curve.end_curve_used !== false
  ) return null;

  if (curve.start_curve_used === true && curve.end_curve_used === true && startResolved && endResolved) {
    const periodDiffers = startResolved !== payload.period_start || endResolved !== payload.period_end;
    return `${periodDiffers ? `持仓归因区间 ${payload.period_start} 至 ${payload.period_end}；` : ""}` +
      `国债曲线实际观测日 ${startResolved} 至 ${endResolved}。`;
  }

  const side = (
    label: string,
    requested: string | null,
    resolved: string | null,
    used: boolean | null | undefined,
  ) => {
    if (used === true) return `${label}实际观测日 ${resolved ?? "未提供"}`;
    if (used === false) {
      return `${label}${requested ? `请求 ${requested}，` : "曲线"}` +
        `${resolved ? `解析到 ${resolved}，` : ""}未采用`;
    }
    return resolved ? `${label}解析到 ${resolved}，采纳状态未提供` : `${label}观测日未提供`;
  };
  return `持仓归因区间 ${payload.period_start} 至 ${payload.period_end}；国债曲线：` +
    `${side("期初", date(curve.start_requested_date), startResolved, curve.start_curve_used)}；` +
    `${side("期末", date(curve.end_requested_date), endResolved, curve.end_curve_used)}。`;
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
