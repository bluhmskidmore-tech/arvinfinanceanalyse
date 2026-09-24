import { EM_DASH } from "../../../pageModel";
import type { BondDashboardKpiCell } from "../model/bondDashboardPageModel";

/**
 * 首屏 KPI 单框横带：外框 + 发丝分割（不做卡片套卡片），4×2 等高分格。
 * cells 由 bondDashboardPageModel 的 buildBondDashboardKpiBand 产出，
 * 组件只渲染不格式化；value 为 EM_DASH 时模型已把 unit 置 null。
 */
export default function BondDashboardKpiBand({
  cells,
  loading,
}: {
  cells: BondDashboardKpiCell[];
  loading: boolean;
}) {
  return (
    <div
      className="bond-dashboard-page__kpi-band"
      data-testid="bond-dashboard-headline-kpis"
      data-loading={loading ? "true" : undefined}
    >
      {cells.map((cell) => (
        <div
          key={cell.key}
          className="bond-dashboard-page__kpi-cell"
          data-testid={`bond-dashboard-kpi-${cell.key}`}
        >
          <span className="bond-dashboard-page__kpi-label" title={cell.label}>
            {cell.label}
          </span>
          <strong className="bond-dashboard-page__kpi-value">
            {cell.value}
            {cell.unit ? <span className="bond-dashboard-page__kpi-unit">{cell.unit}</span> : null}
          </strong>
          <span className="bond-dashboard-page__kpi-mom" data-tone={cell.momTone}>
            环比 {cell.mom ?? EM_DASH}
          </span>
          {cell.note ? (
            <span className="bond-dashboard-page__kpi-note" title={cell.note}>
              {cell.note}
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
