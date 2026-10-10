import type {
  LivermorePositionSizeHint,
  LivermorePositionSizeHintItem,
} from "../../../api/contracts";

/**
 * 候选建议仓位展示模型（position_size_hint 透传）。
 *
 * 仅做百分比格式化与披露文案归组，不重算任何业务数值；
 * 后端未返回 hint 块或该票无 hint 条目时字段为 null/缺失，不渲染。
 *
 * sizing_eqw_v2 起主显等权仓位（primary_basis="equal_weight"，等权=门控敞口/候选数），
 * risk_budget 值在 tooltip 降为实验参考一行；primary_basis 缺失（老响应）或
 * 等权值不可用（门控敞口缺失）时回退现行为（主显 raw_weight，文案不变）。
 */
export type StockCandidateSizeHintFields = {
  /** 建议仓位徽章文案，如"等权 12.5%"（等权主参考）或"仓位 ≤ 6.0%"（老响应回退）。 */
  sizeHintLabel?: string | null;
  /** 建议仓位 tooltip 详情：等权口径/实验参考、止损基准、单票上限截断与样本外验证/敞口串联披露原文。 */
  sizeHintDetail?: string | null;
};

export type StockCandidatePositionSizeHintNotice = {
  /** 汇总注记可见文案（低调口径披露，完整原文在 detail/tooltip）。 */
  summary: string;
  tone: "warning" | "neutral";
  oosStatusLabel: string | null;
  oosNote: string | null;
  coverageWarning: string | null;
  /** tooltip 全文：oos note、coverage warning、gate 串联与等权 shadow 披露原文逐行透传。 */
  detail: string;
};

function sizeHintStopBasisLabel(hintItem: LivermorePositionSizeHintItem): string {
  return hintItem.stop_basis === "fallback" ? "fallback 止损距离折算" : "EMA10 止损距离折算";
}

function hasFiniteRawWeight(
  hintItem: LivermorePositionSizeHintItem | undefined,
): hintItem is LivermorePositionSizeHintItem {
  return (
    hintItem != null && typeof hintItem.raw_weight === "number" && Number.isFinite(hintItem.raw_weight)
  );
}

/** primary_basis 缺失（老响应）时回退 raw_weight 主显；等权值缺失（门控敞口不可用）同样回退。 */
function equalWeightPrimaryValue(
  hintItem: LivermorePositionSizeHintItem,
  hint: LivermorePositionSizeHint,
): number | null {
  if (hint.primary_basis !== "equal_weight") return null;
  const equalWeight = hintItem.equal_weight;
  return typeof equalWeight === "number" && Number.isFinite(equalWeight) ? equalWeight : null;
}

function formatWeightPct(weight: number): string {
  return `${(weight * 100).toFixed(1)}%`;
}

/** risk_budget 值降级为实验参考一行（样本外未支持），仅在等权主显模式的 tooltip 使用。 */
function riskBudgetExperimentalLine(hintItem: LivermorePositionSizeHintItem): string | null {
  if (!hasFiniteRawWeight(hintItem)) return null;
  return `实验参考（样本外未支持）：risk_budget 仓位 ≤ ${formatWeightPct(hintItem.raw_weight)}（${sizeHintStopBasisLabel(hintItem)}${hintItem.capped ? "，已触单票上限" : ""}）`;
}

function sizeHintSharedDisclosureLines(hint: LivermorePositionSizeHint): string[] {
  const lines: string[] = [];
  const oosNote = hint.oos_validation?.note?.trim();
  if (oosNote) lines.push(`样本外验证：${oosNote}`);
  const coverageWarning = hint.coverage_warning?.trim();
  if (coverageWarning) lines.push(coverageWarning);
  const gateNote = hint.gate_exposure_note?.trim();
  if (gateNote) lines.push(gateNote);
  return lines;
}

function sizeHintDetail(
  hintItem: LivermorePositionSizeHintItem,
  hint: LivermorePositionSizeHint,
): string {
  const lines = [
    `建议仓位为单票权重上限参考（${sizeHintStopBasisLabel(hintItem)}）${
      hintItem.capped ? "，已触单票上限" : ""
    }`,
    ...sizeHintSharedDisclosureLines(hint),
  ];
  return lines.join("\n");
}

function equalWeightSizeHintDetail(
  hintItem: LivermorePositionSizeHintItem,
  hint: LivermorePositionSizeHint,
): string {
  const lines = ["建议仓位以等权为主参考（当日门控敞口÷候选数，已含门控敞口）"];
  const experimentalLine = riskBudgetExperimentalLine(hintItem);
  if (experimentalLine) lines.push(experimentalLine);
  lines.push(...sizeHintSharedDisclosureLines(hint));
  return lines.join("\n");
}

function sizeHintOosStatusLabel(status: string | null | undefined): string | null {
  const normalized = status?.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "not_supported_by_walk_forward") return "样本外验证未获支持";
  return "样本外验证状态待确认";
}

/**
 * 按 stock_code 构建候选徽章/tooltip 字段；权重均为后端 0-1 小数，仅格式化为百分比。
 * 等权主参考可用时主显"等权 x.x%"，否则回退"仓位 ≤ x.x%"（raw_weight，老响应行为不变）。
 */
export function buildCandidateSizeHintFieldsByStockCode(
  hint: LivermorePositionSizeHint | null | undefined,
): Map<string, Required<StockCandidateSizeHintFields>> {
  const fieldsByStockCode = new Map<string, Required<StockCandidateSizeHintFields>>();
  if (!hint) return fieldsByStockCode;
  for (const hintItem of hint.items ?? []) {
    const equalWeight = hintItem ? equalWeightPrimaryValue(hintItem, hint) : null;
    if (equalWeight != null) {
      fieldsByStockCode.set(hintItem.stock_code, {
        sizeHintLabel: `等权 ${formatWeightPct(equalWeight)}`,
        sizeHintDetail: equalWeightSizeHintDetail(hintItem, hint),
      });
      continue;
    }
    if (!hasFiniteRawWeight(hintItem)) continue;
    fieldsByStockCode.set(hintItem.stock_code, {
      sizeHintLabel: `仓位 ≤ ${formatWeightPct(hintItem.raw_weight)}`,
      sizeHintDetail: sizeHintDetail(hintItem, hint),
    });
  }
  return fieldsByStockCode;
}

/**
 * 给候选队列条目按 stock_code 注入建议仓位徽章字段；无 hint 块或无匹配条目时原样返回。
 * 仅应在 stock_candidates（趋势候选）队列上调用，hint 语义不适用于融合/新趋势候选。
 */
export function attachCandidateSizeHintFields<T extends { stockCode: string }>(
  queue: T[],
  hint: LivermorePositionSizeHint | null | undefined,
): T[] {
  const fieldsByStockCode = buildCandidateSizeHintFieldsByStockCode(hint);
  if (fieldsByStockCode.size === 0) return queue;
  return queue.map((item) => {
    const fields = fieldsByStockCode.get(item.stockCode);
    return fields ? { ...item, ...fields } : item;
  });
}

/**
 * 页面级建议仓位口径注记：后端未返回 hint 块时为 null。
 * stock_candidates 是否进入主展示由调用方（页面）判定后决定是否传入。
 *
 * 等权主参考（primary_basis="equal_weight"）时，表头口径条一行同时披露
 * 门控敞口口径与 risk_budget 实验参考降级；老响应保持现行文案。
 */
export function buildCandidatePositionSizeHintNotice(
  hint: LivermorePositionSizeHint | null | undefined,
): StockCandidatePositionSizeHintNotice | null {
  if (!hint) return null;
  const equalWeightPrimary = hint.primary_basis === "equal_weight";
  const oosStatusLabel = sizeHintOosStatusLabel(hint.oos_validation?.status);
  const oosNote = hint.oos_validation?.note?.trim() || null;
  const coverageWarning = hint.coverage_warning?.trim() || null;
  const qualifiers = [
    equalWeightPrimary ? "risk_budget 为实验参考" : null,
    oosStatusLabel,
    coverageWarning ? "覆盖率降级" : null,
  ].filter((item): item is string => Boolean(item));
  const summary = equalWeightPrimary
    ? `建议仓位以等权为主参考：当日门控敞口÷候选数${qualifiers.length > 0 ? `（${qualifiers.join("；")}）` : ""}`
    : `建议仓位为单票上限参考${
        qualifiers.length > 0 ? `（${qualifiers.join("；")}）` : ""
      }`;
  const detailLines = [
    equalWeightPrimary ? hint.equal_weight_note?.trim() || null : null,
    oosNote ? `样本外验证：${oosNote}` : null,
    hint.oos_validation?.evidence_ref?.trim()
      ? `验证证据：${hint.oos_validation.evidence_ref.trim()}`
      : null,
    coverageWarning,
    hint.gate_exposure_note?.trim() || null,
    hint.equal_weight_shadow_note?.trim() || null,
  ].filter((line): line is string => Boolean(line));
  return {
    summary,
    tone: coverageWarning ? "warning" : "neutral",
    oosStatusLabel,
    oosNote,
    coverageWarning,
    detail: detailLines.join("\n"),
  };
}
