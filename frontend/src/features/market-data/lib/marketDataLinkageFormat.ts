import type { MacroBondLinkageTopCorrelation } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export function formatCorrelation(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "不可用";
  }
  return value.toFixed(2);
}

/** 流动性/综合分极性口径说明：实现细节按 DESIGN §7 收进 title，不占正文。 */
export const LIQUIDITY_COMPOSITE_POLARITY_NOTE =
  "流动性正值=宽松；综合分正值=对债偏紧，综合计算中流动性取反。";
export const LIQUIDITY_SCORE_POLARITY_TITLE = "正值偏松，负值偏紧；进入综合分时取反。";

/** 环境评分类着色的中性带阈值：|score| < 0.2 视为无方向信息，归中性。 */
export const LINKAGE_SCORE_NEUTRAL_BAND = 0.2;

export type LinkageScoreTone = "default" | "positive" | "negative";

export function linkageScoreTone(value: number | null | undefined): LinkageScoreTone {
  if (value == null || Number.isNaN(value)) {
    return "default";
  }
  if (Math.abs(value) < LINKAGE_SCORE_NEUTRAL_BAND) {
    return "default";
  }
  return value > 0 ? "positive" : "negative";
}

const RATE_DIRECTION_LABELS: Record<string, string> = {
  falling: "下行",
  rising: "上行",
  neutral: "震荡",
  sideways: "震荡",
  flat: "震荡",
};

/** 后端 rate_direction 枚举中文化；未登记枚举原样透出。 */
export function formatRateDirectionLabel(direction: string | null | undefined): string {
  if (!direction) {
    return "不可用";
  }
  return RATE_DIRECTION_LABELS[direction.trim().toLowerCase()] ?? direction;
}

/** 后端英文方法学警示的展示层中文化；未识别的原样透出（fail-open，不吞证据）。 */
export function displayLinkageWarning(warning: string): string {
  const indicatorScore = warning.match(/^Indicator score unavailable:\s*(.+)$/i);
  if (indicatorScore) {
    return `指标评分不可用：${indicatorScore[1]}`;
  }
  return warning;
}

/** 展示占比（原值为小数分数，如 0.0038）为两位百分比；非数字字符串透传。 */
export function formatImpactRatioPercent(value: number | string | null | undefined): string {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  return `${(numericValue * 100).toFixed(2)}%`;
}

/**
 * 目标维度自身及其派生期限序列（如 treasury 目标 × 中债国债到期收益率各期限）：
 * 自相关恒为 ±1、领先 0 天，无信息量，相关性表按行剔除。
 */
export function isLinkageSelfCorrelation(
  point: Pick<MacroBondLinkageTopCorrelation, "series_name" | "target_family">,
): boolean {
  const name = point.series_name;
  switch (point.target_family) {
    case "treasury":
      return /国债/.test(name) && /收益率/.test(name) && !/国开/.test(name);
    case "cdb":
      return /国开/.test(name) && /收益率/.test(name);
    case "aaa_credit":
      return /AAA/i.test(name) && /收益率/.test(name);
    case "credit_spread":
      return /利差/.test(name);
    default:
      return false;
  }
}

export type LinkageDirectionTone = "up" | "down" | "neutral";

export function linkageDirectionTone(direction: string | null | undefined): LinkageDirectionTone {
  if (!direction || direction === EM_DASH) {
    return "neutral";
  }
  if (/上|涨|升|多|强|positive/i.test(direction)) {
    return "up";
  }
  if (/下|跌|降|弱|空|negative|falling/i.test(direction)) {
    return "down";
  }
  return "neutral";
}

export function formatLinkageDirectionLabel(direction: string | null | undefined): string {
  if (!direction || direction === EM_DASH) {
    return EM_DASH;
  }
  const normalized = direction.trim().toLowerCase();
  if (normalized === "positive") {
    return "偏正";
  }
  if (normalized === "negative") {
    return "偏负";
  }
  if (normalized === "neutral") {
    return "中性";
  }
  if (/上|涨|升|多|强/.test(direction)) {
    return "偏强";
  }
  if (/下|跌|降|弱|空/.test(direction)) {
    return "偏弱";
  }
  return direction;
}

export function linkageDirectionPillClass(direction: string | null | undefined): string {
  const tone = linkageDirectionTone(direction);
  if (tone === "up") {
    return "market-data-dir-pill market-data-dir-pill--pos";
  }
  if (tone === "down") {
    return "market-data-dir-pill market-data-dir-pill--neg";
  }
  return "market-data-dir-pill market-data-dir-pill--neu";
}

export function correlationStrength(value: number | null | undefined): "none" | "weak" | "strong" {
  if (value == null || Number.isNaN(value)) {
    return "none";
  }
  return Math.abs(value) >= 0.5 ? "strong" : "weak";
}
