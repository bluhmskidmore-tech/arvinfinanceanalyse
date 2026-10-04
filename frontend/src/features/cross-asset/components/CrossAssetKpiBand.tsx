import KpiStrip, { type KpiCell } from "../../../components/layout/KpiStrip";
import type { CrossAssetKpiBandItem } from "../lib/crossAssetKpiBand";

export type CrossAssetKpiBandProps = {
  items: CrossAssetKpiBandItem[];
};

const UI = {
  sectionLabel: "关键指标横带",
  changePrefix: "日变动",
} as const;

export function CrossAssetKpiBand({ items }: CrossAssetKpiBandProps) {
  const cells: KpiCell[] = items.map((item) => ({
    key: item.key,
    label: item.label,
    value: item.valueLabel,
    unit: item.unit,
    delta: `${item.impactLabel} · ${UI.changePrefix} ${item.changeLabel}`,
    deltaTone:
      item.impact === "bullish" ? "positive" : item.impact === "bearish" ? "negative" : "neutral",
    note: `${item.sourceLabel} · ${item.dateLabel}`,
    spark: item.spark,
  }));

  return (
    <KpiStrip
      cells={cells}
      cols={{ base: 2, md: 3, lg: 3, xl: 6 }}
      testId="cross-asset-kpi-band"
      className="cross-asset-kpi-band"
      ariaLabel={UI.sectionLabel}
    />
  );
}
