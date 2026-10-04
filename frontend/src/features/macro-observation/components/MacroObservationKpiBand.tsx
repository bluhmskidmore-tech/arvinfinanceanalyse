import KpiStrip, { type KpiCell } from "../../../components/layout/KpiStrip";
import type { MacroObservationKpiItem } from "../model/macroObservationPageModel";

/**
 * 首屏 KPI 单框横带（参照 /positions PositionsKpiBand）：单一外框 +
 * 发丝竖缝（不做卡片套卡片），六格等高，标签 2 行 clamp 防同排数值错位。
 * items 由 buildObservationKpiBand 产出，status 是四态
 * （loading/deferred/ready/failed）→ data-status；组件只渲染不格式化。
 */
export default function MacroObservationKpiBand({
  items,
  testId,
}: {
  items: MacroObservationKpiItem[];
  testId: string;
}) {
  const cells: KpiCell[] = items.map((item) => ({
    key: item.key,
    label: item.label,
    value: item.value,
    unit: item.unit,
    valueVariant: item.key === "stance" || item.key === "primary-signal" ? "text" : "metric",
    valueTone: item.tone,
    cellStatus: item.status,
    note: item.note,
  }));

  return <KpiStrip cells={cells} cols={{ base: 1, md: 3, lg: 3, xl: 6 }} testId={testId} />;
}
