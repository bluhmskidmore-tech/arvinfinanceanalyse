import type {
  LivermorePositionSizeHint,
  LivermorePositionSizeHintItem,
} from "../../../api/contracts";

/**
 * 候选建议仓位展示模型（position_size_hint 透传）。
 *
 * 仅做百分比格式化与披露文案归组，不重算任何业务数值；
 * 后端未返回 hint 块或该票无 hint 条目时字段为 null/缺失，不渲染。
 */
export type StockCandidateSizeHintFields = {
  /** 建议仓位徽章文案，如"仓位 ≤ 6.0%"。 */
  sizeHintLabel?: string | null;
  /** 建议仓位 tooltip 详情：止损基准、单票上限截断与样本外验证/敞口串联披露原文。 */
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

function sizeHintDetail(
  hintItem: LivermorePositionSizeHintItem,
  hint: LivermorePositionSizeHint,
): string {
  const lines = [
    `建议仓位为单票权重上限参考（${sizeHintStopBasisLabel(hintItem)}）${
      hintItem.capped ? "，已触单票上限" : ""
    }`,
  ];
  const oosNote = hint.oos_validation?.note?.trim();
  if (oosNote) lines.push(`样本外验证：${oosNote}`);
  const coverageWarning = hint.coverage_warning?.trim();
  if (coverageWarning) lines.push(coverageWarning);
  const gateNote = hint.gate_exposure_note?.trim();
  if (gateNote) lines.push(gateNote);
  return lines.join("\n");
}

function sizeHintOosStatusLabel(status: string | null | undefined): string | null {
  const normalized = status?.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "not_supported_by_walk_forward") return "样本外验证未获支持";
  return "样本外验证状态待确认";
}

/** 按 stock_code 构建候选徽章/tooltip 字段；raw_weight 为后端 0-1 权重上限，仅格式化为百分比。 */
export function buildCandidateSizeHintFieldsByStockCode(
  hint: LivermorePositionSizeHint | null | undefined,
): Map<string, Required<StockCandidateSizeHintFields>> {
  const fieldsByStockCode = new Map<string, Required<StockCandidateSizeHintFields>>();
  if (!hint) return fieldsByStockCode;
  for (const hintItem of hint.items ?? []) {
    if (!hasFiniteRawWeight(hintItem)) continue;
    fieldsByStockCode.set(hintItem.stock_code, {
      sizeHintLabel: `仓位 ≤ ${(hintItem.raw_weight * 100).toFixed(1)}%`,
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
 */
export function buildCandidatePositionSizeHintNotice(
  hint: LivermorePositionSizeHint | null | undefined,
): StockCandidatePositionSizeHintNotice | null {
  if (!hint) return null;
  const oosStatusLabel = sizeHintOosStatusLabel(hint.oos_validation?.status);
  const oosNote = hint.oos_validation?.note?.trim() || null;
  const coverageWarning = hint.coverage_warning?.trim() || null;
  const qualifiers = [oosStatusLabel, coverageWarning ? "覆盖率降级" : null].filter(
    (item): item is string => Boolean(item),
  );
  const summary = `建议仓位为单票上限参考${qualifiers.length > 0 ? `（${qualifiers.join("；")}）` : ""}`;
  const detailLines = [
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
