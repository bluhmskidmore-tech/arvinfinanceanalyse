/** 与 market-data 联动区共用同一符号数格式化实现，避免双份漂移。 */
export { formatSignedNumber } from "../../market-data/lib/marketDataFormat";

import { formatSignedCompactAmount } from "../../market-data/lib/marketDataFormat";

/**
 * 组合影响估算（元，DV01/CS01 × bp 敞口口径）→ 万元/亿元紧凑展示。
 * “不可用”与非数字字符串透传；数字结果补“元”单位，原值由调用方收进 title。
 */
export function formatEstimatedImpactCny(value: number | string | null | undefined): string {
  const compact = formatSignedCompactAmount(value);
  return /^[+-]?\d/.test(compact) ? `${compact}元` : compact;
}

/** 组合影响估算符号 tone：正=估算增益（绿），负=估算损失（红），缺失/零=中性。 */
export function impactTone(value: number | string | null | undefined): "positive" | "negative" | "neutral" {
  if (value == null || value === "") {
    return "neutral";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue) || numericValue === 0) {
    return "neutral";
  }
  return numericValue > 0 ? "positive" : "negative";
}

export function correlationLedgerCellClassName(value: string) {
  if (value.includes("-")) return "cross-asset-linkage-heatmap-ledger__cell cross-asset-linkage-heatmap-ledger__cell--negative";
  if (value === "不可用") return "cross-asset-linkage-heatmap-ledger__cell cross-asset-linkage-heatmap-ledger__cell--missing";
  return "cross-asset-linkage-heatmap-ledger__cell cross-asset-linkage-heatmap-ledger__cell--positive";
}

export function splitLinkageIndicator(value: string) {
  const [source, target] = value.split("→").map((part) => part.trim());
  return { source: source || value, target: target || "" };
}
