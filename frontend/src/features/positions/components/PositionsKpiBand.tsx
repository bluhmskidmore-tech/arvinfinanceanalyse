import type { LabeledValue } from "../../../pageModel";

/**
 * 首屏 KPI 横带：单一外框 + 发丝竖分割（不做卡片套卡片），六格等高，
 * 标签 2 行 clamp 防同排数值错位（DESIGN.md §3/§5）。items 由
 * positionsPageModel 的 buildPositionsBondsKpiBand / buildPositionsInterbankKpiBand
 * 产出，组件只渲染不格式化。
 */
export default function PositionsKpiBand({
  items,
  testId,
}: {
  items: LabeledValue[];
  testId: string;
}) {
  return (
    <div className="positions-view__kpi-band" data-testid={testId}>
      {items.map((item) => (
        <div
          key={item.key}
          className="positions-view__kpi-cell"
          data-status={item.status ?? "ready"}
        >
          <span className="positions-view__kpi-label" title={item.label}>
            {item.label}
          </span>
          <strong className="positions-view__kpi-value">{item.value}</strong>
          {item.note ? (
            <span className="positions-view__kpi-note" title={item.note}>
              {item.note}
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
