export function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") return "不可用";
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) return String(value);
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
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
