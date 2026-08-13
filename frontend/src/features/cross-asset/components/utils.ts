/** 与 market-data 联动区共用同一符号数格式化实现，避免双份漂移。 */
export { formatSignedNumber } from "../../market-data/lib/marketDataFormat";

export function correlationLedgerCellClassName(value: string) {
  if (value.includes("-")) return "cross-asset-linkage-heatmap-ledger__cell cross-asset-linkage-heatmap-ledger__cell--negative";
  if (value === "不可用") return "cross-asset-linkage-heatmap-ledger__cell cross-asset-linkage-heatmap-ledger__cell--missing";
  return "cross-asset-linkage-heatmap-ledger__cell cross-asset-linkage-heatmap-ledger__cell--positive";
}

export function splitLinkageIndicator(value: string) {
  const [source, target] = value.split("→").map((part) => part.trim());
  return { source: source || value, target: target || "" };
}
