import type { PnlByBusinessUntracedTrendRow } from "../../api/contracts";
import { BaseChart } from "../../components/charts/BaseChart";
import { buildUntracedReconciliationTrendOption } from "./untracedReconciliationTrendOption";

export type UntracedReconciliationTrendPanelProps = {
  rows: PnlByBusinessUntracedTrendRow[];
  height?: number;
};

export function UntracedReconciliationTrendPanel({ rows, height = 260 }: UntracedReconciliationTrendPanelProps) {
  if (rows.length === 0) {
    return (
      <div className="pnl-by-business-insights-trend-empty" data-testid="untraced-reconciliation-trend-empty">
        暂无可用的历史对账诊断数据
      </div>
    );
  }

  const option = buildUntracedReconciliationTrendOption(rows);
  return (
    <div data-testid="untraced-reconciliation-trend-panel">
      <BaseChart option={option} height={height} />
    </div>
  );
}
