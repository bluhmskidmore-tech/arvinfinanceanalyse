/**
 * 研究台组件层的展示辅助。数值/单位相关的取值一律来自 lib 模型（唯一的单位表），
 * 这里只保留纯字符串语义的着色判断，避免组件层再出现第二套反解析逻辑。
 */
export {
  candidateDailyChangeLabel,
  candidateDailyChangeTone,
  candidateNumberLabel,
  candidatePercentLabel,
  candidateRawNumber,
  candidateRawValue,
  COMPOSITE_SCORE_RAW_KEYS,
  poolTabLabel,
  RESEARCH_DESK_POOL_TABS,
  statusTone,
} from "../../lib/stockAnalysisResearchDeskModel";

/** 已格式化涨跌字符串（"+1.20%" / "-0.35%"）→ 语义色。 */
export function changeTone(value: string): "positive" | "negative" | "neutral" {
  const normalized = value.trim();
  if (normalized.startsWith("-")) return "negative";
  if (normalized.startsWith("+") || /\bup\b/i.test(normalized)) return "positive";
  return "neutral";
}
