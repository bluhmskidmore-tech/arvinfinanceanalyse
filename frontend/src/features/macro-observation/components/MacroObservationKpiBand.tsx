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
  return (
    <div className="macro-observation-view__kpi-band" data-testid={testId}>
      {items.map((item) => (
        <div
          key={item.key}
          className="macro-observation-view__kpi-cell"
          data-status={item.status}
          data-tone={item.tone ?? "neutral"}
        >
          <span className="macro-observation-view__kpi-label" title={item.label}>
            {item.label}
          </span>
          <strong className="macro-observation-view__kpi-value">{item.value}</strong>
          {item.note ? (
            <span className="macro-observation-view__kpi-note" title={item.note}>
              {item.note}
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
