import type { EChartsOption } from "../../lib/echarts";

import type { DataSectionState } from "../../components/DataSection.types";
import type {
  PnlBridgeEffectAvailability,
  PnlBridgeEffectAvailabilityBlock,
  PnlBridgeEffectAvailabilityReason,
  PnlBridgeEffectCoverage,
  PnlBridgeSummary,
  ResultMeta,
} from "../../api/contracts";
import { designTokens } from "../../theme/designSystem";

// 互斥分解口径（2026-08 审计 PNL-01）：未实现公允（516）是市场效应要解释的
// 对象，不再作为解释分量进入瀑布；明细表仍保留该列作参照。
const BRIDGE_CATEGORIES = [
  "票息",
  "骑乘",
  "国债曲线",
  "信用利差",
  "汇兑",
  "已实现交易",
  "人工调整",
  "解释合计",
  "实际PnL",
] as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

// 曲线效应"归零但不是观测值"的呈现口径。后端的数值一分未改（缺曲线时仍是 0）；
// 页面要做的是不把那个 0 当成"利率没动"发布出去。Record 按联合类型收口：后端新增
// 一个取值而这里没给标签，编译就会失败，而不是把英文码泄漏到页面上。
const EFFECT_UNAVAILABLE_TEXT = "不可用";
const EFFECT_NOT_APPLICABLE_TEXT = "不适用";

const EFFECT_AVAILABILITY_TEXT: Record<PnlBridgeEffectAvailability, string | null> = {
  ok: null,
  unavailable: EFFECT_UNAVAILABLE_TEXT,
  not_applicable: EFFECT_NOT_APPLICABLE_TEXT,
};

const EFFECT_COVERAGE_TEXT: Record<PnlBridgeEffectCoverage, string> = {
  ok: "可用",
  partial: "部分不可用",
  unavailable: EFFECT_UNAVAILABLE_TEXT,
  not_applicable: EFFECT_NOT_APPLICABLE_TEXT,
};

const EFFECT_REASON_TEXT: Record<PnlBridgeEffectAvailabilityReason, string> = {
  curve_unavailable: "缺曲线",
  same_source_curve: "两端同源",
  market_value_base_missing: "余额行无可用市值基数",
  roll_window_missing: "缺上期余额行，无滚动窗口",
  tenor_outside_curve_support: "剩余期限超出曲线覆盖区间",
  non_fvtpl_basis: "非 FVTPL 口径不计市场效应",
  not_credit_book: "非信用簿",
  no_curve_sensitivity: "到期/零久期/空仓，无曲线敏感度",
  balance_row_missing: "缺当期余额行",
};

export function effectAvailabilityCellText(
  availability: PnlBridgeEffectAvailability | undefined,
  reason: PnlBridgeEffectAvailabilityReason | null | undefined,
): string | null {
  const text = EFFECT_AVAILABILITY_TEXT[availability ?? "ok"];
  if (text === null) return null;
  const reasonText = reason ? EFFECT_REASON_TEXT[reason] : null;
  return reasonText ? `${text} · ${reasonText}` : text;
}

function reasonList(reasons: PnlBridgeEffectAvailabilityReason[] | undefined): string {
  if (!reasons || reasons.length === 0) return "未标注成因";
  return reasons.map((reason) => EFFECT_REASON_TEXT[reason]).join("、");
}

export type CurveAvailabilityNotice = {
  key: string;
  label: string;
  statusText: string;
  text: string;
};

/**
 * 汇总级披露文案。`unavailable` 是"没有曲线可比"，`partial` 是"合计被低估"，
 * `not_applicable` 是"这本账按口径就不计这项"——三者的处置完全不同，塌成一条
 * 通用告警就等于没披露。
 */
export function buildCurveAvailabilityNotices(
  summary: PnlBridgeSummary | undefined,
): CurveAvailabilityNotice[] {
  if (!summary) return [];
  // 骑乘与国债曲线分开表态：它只用当期曲线沿自身斜率滚动，却额外需要一个有效的
  // 滚动窗口，所以"曲线两端同源"时它仍是观测量，而"缺上期余额行"时只有它归零。
  // 共用一个结论就会在同一页上出现"利率效应不可用、骑乘 0"这种自相矛盾。
  const effects: Array<{ key: string; label: string; block?: PnlBridgeEffectAvailabilityBlock }> = [
    { key: "roll_down", label: "骑乘效应", block: summary.roll_down_availability },
    { key: "treasury_curve", label: "国债曲线效应", block: summary.treasury_curve_availability },
    { key: "credit_spread", label: "信用利差效应", block: summary.credit_spread_availability },
  ];
  const notices: CurveAvailabilityNotice[] = [];
  for (const { key, label, block } of effects) {
    if (!block || block.status === "ok") continue;
    const statusText = EFFECT_COVERAGE_TEXT[block.status];
    if (block.status === "not_applicable") {
      notices.push({
        key,
        label,
        statusText,
        text: `本期无适用行（${reasonList(block.reasons)}），该效应不参与本期分解。`,
      });
      continue;
    }
    const scope = `${block.unavailable_rows}/${block.applicable_rows} 个适用行`;
    notices.push({
      key,
      label,
      statusText,
      text:
        block.status === "unavailable"
          ? `${scope}因${reasonList(block.reasons)}无法计算，该效应本期没有可比输入，页面不以数字形式发布，不是市场没有变动。`
          : `${scope}因${reasonList(block.reasons)}无法计算，合计因此被低估，不能按完整口径解读。`,
    });
  }
  return notices;
}

/** 合计是否还代表一个可发布的观测量：完全不可用时不画柱，也不显示 0。 */
function coverageIsUnavailable(block: PnlBridgeEffectAvailabilityBlock | undefined): boolean {
  return block?.status === "unavailable";
}

export function buildWaterfallOption(summary: PnlBridgeSummary): EChartsOption {
  // 完全不可用的效应没有已知金额，在分解图里必须是断点而不是 0 值柱。
  // `not_applicable` 相反：它对分解的贡献确实精确为 0，照常画。
  const rollDownUnavailable = coverageIsUnavailable(summary.roll_down_availability);
  const treasuryUnavailable = coverageIsUnavailable(summary.treasury_curve_availability);
  const creditUnavailable = coverageIsUnavailable(summary.credit_spread_availability);
  const unavailableDisplay = (block: PnlBridgeEffectAvailabilityBlock | undefined) =>
    `${EFFECT_UNAVAILABLE_TEXT}（${reasonList(block?.reasons)}）`;

  const displayStrings = [
    summary.total_carry.display,
    rollDownUnavailable
      ? unavailableDisplay(summary.roll_down_availability)
      : summary.total_roll_down.display,
    treasuryUnavailable
      ? unavailableDisplay(summary.treasury_curve_availability)
      : summary.total_treasury_curve.display,
    creditUnavailable
      ? unavailableDisplay(summary.credit_spread_availability)
      : summary.total_credit_spread.display,
    summary.total_fx_translation.display,
    summary.total_realized_trading.display,
    summary.total_manual_adjustment.display,
    summary.total_explained_pnl.display,
    summary.total_actual_pnl.display,
  ];

  const stepValues = [
    summary.total_carry.raw,
    rollDownUnavailable ? null : summary.total_roll_down.raw,
    treasuryUnavailable ? null : summary.total_treasury_curve.raw,
    creditUnavailable ? null : summary.total_credit_spread.raw,
    summary.total_fx_translation.raw,
    summary.total_realized_trading.raw,
    summary.total_manual_adjustment.raw,
  ];

  const helperRaw: Array<number | null> = [];
  const valueRaw: Array<number | null> = [];
  const barColors: string[] = [];

  let running = 0;
  for (const value of stepValues) {
    // 缺失效应不画 0 值柱：value/helper 传 null，让 ECharts 留出断点，且不推进累计值。
    if (value === null) {
      helperRaw.push(null);
      valueRaw.push(null);
      barColors.push(designTokens.color.neutral[400]);
    } else if (value >= 0) {
      helperRaw.push(running);
      valueRaw.push(value);
      barColors.push(designTokens.color.semantic.profit);
      running += value;
    } else {
      helperRaw.push(running + value);
      valueRaw.push(-value);
      barColors.push(designTokens.color.semantic.loss);
      running += value;
    }
  }

  helperRaw.push(0);
  valueRaw.push(summary.total_explained_pnl.raw);
  barColors.push(designTokens.color.primary[600]);

  helperRaw.push(0);
  valueRaw.push(summary.total_actual_pnl.raw);
  barColors.push(designTokens.color.primary[600]);

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((item: { seriesName?: string }) => item.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = BRIDGE_CATEGORIES[idx] ?? "";
        return `${label}<br/>${displayStrings[idx] ?? "—"}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 44, containLabel: true },
    xAxis: {
      type: "category",
      data: [...BRIDGE_CATEGORIES],
      axisLabel: { interval: 0, rotate: 22, fontSize: 11, color: designTokens.color.neutral[600] },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { type: "dashed" as const, color: designTokens.color.neutral[200] } },
      axisLabel: { fontSize: 11, color: designTokens.color.neutral[600] },
    },
    series: [
      {
        name: "辅助",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: TRANSPARENT_BAR,
        emphasis: { itemStyle: TRANSPARENT_BAR },
        data: helperRaw,
      },
      {
        name: "效应",
        type: "bar",
        stack: "waterfall",
        data: valueRaw.map((value, index) => ({
          value,
          itemStyle: { color: barColors[index] },
        })),
      },
    ],
  };
}

function pickMetaEffectiveDate(state: DataSectionState, meta: ResultMeta | null): string | undefined {
  if ((state.kind === "fallback" || state.kind === "stale") && state.effective_date) {
    return state.effective_date;
  }
  return meta?.fallback_date ?? meta?.resolved_report_date ?? meta?.as_of_date ?? undefined;
}

/** Decision-level first-screen notice from envelope result_meta (adapter state). */
export function buildPnlBridgeFirstScreenMetaNotice(
  state: DataSectionState,
  meta: ResultMeta | null,
): string | null {
  if (state.kind === "fallback") {
    const parts = ["首屏读模型已回退至最近可用快照"];
    const effectiveDate = pickMetaEffectiveDate(state, meta);
    if (meta?.requested_report_date && effectiveDate && meta.requested_report_date !== effectiveDate) {
      parts.push(`请求日 ${meta.requested_report_date} 回退至 ${effectiveDate}`);
    } else if (effectiveDate) {
      parts.push(`有效日 ${effectiveDate}`);
    }
    return `${parts.join("；")}。下方 KPI 与瀑布图基于上述回退数据，请以实际数据日期为准。`;
  }

  if (state.kind === "stale") {
    const parts = ["首屏读模型数据偏旧"];
    const effectiveDate = pickMetaEffectiveDate(state, meta);
    if (effectiveDate) {
      parts.push(`有效日 ${effectiveDate}`);
    }
    return `${parts.join("；")}。下方校验状态仍可能显示为正常，因其来自行级闭合质量，不代表读模型新鲜度。`;
  }

  return null;
}
