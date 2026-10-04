import type { PnlByBusinessUntracedTrendRow } from "../../api/contracts";
import { ChartCard } from "../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../components/charts/chartCardScale";
import { buildUntracedReconciliationTrendOption } from "./untracedReconciliationTrendOption";

export type UntracedReconciliationTrendPanelProps = {
  rows: PnlByBusinessUntracedTrendRow[];
};

export function UntracedReconciliationTrendPanel({ rows }: UntracedReconciliationTrendPanelProps) {
  return (
    <ChartCard
      testId="untraced-reconciliation-trend-panel"
      title="未追溯占比趋势"
      unit="%"
      height={CHART_CARD_HEIGHTS.hero}
      legend="none"
      option={rows.length ? buildUntracedReconciliationTrendOption(rows) : null}
      emptyMessage="暂无可用的历史对账诊断数据"
    />
  );
}
